# SPDX-License-Identifier: Apache-2.0
"""Replay the authored ML-DSA-87 reference against pinned official ACVP bytes.

Run inside WSL with --work under the assigned native /root/build/lane-* root.
No upstream implementation or extracted runtime source is incorporated. The
notice beside this file governs the downloaded NIST test data. Pure ML-DSA,
internal bit-message, and external-mu test adapters are supported; HashML-DSA
prehash groups are deliberately excluded, never sent through the pure adapter.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from vos import env, gallina  # noqa: E402

REVISION = "975de31eb83d87039ec88934fdc47d8c312b892d"
BASE = "https://raw.githubusercontent.com/usnistgov/ACVP-Server/" + REVISION + "/"
SOURCES = {
    "keyGen": "e67ee6540d40e11506c3c4e3b1f79fc1cefcd49820db99fc61f87cc8ba463baf",
    "sigGen": "72dcaf5f69853ca267ccd16af9cb40949786aca0fcfbf05d1ebeba132b93af22",
    "sigVer": "47cdd6314c7f746d02421ffcba89d4dbc7bb875ac49e07a029fdfc26fba55437",
}
README_SHA = "d5a569884ee83bd1c4737042d0a2cc7d68c6950690f75a73ef14f505a9aa3555"
EXTRACTION = '''From Stdlib Require Import Extraction.
From Stdlib.extraction Require Import ExtrOcamlBasic ExtrOcamlNatInt ExtrOcamlZBigInt.
Require Import MlDsa.
Extraction Language OCaml.
Extraction "mldsa.ml" dsa_keygen dsa_sign dsa_verify dsa_sign_internal
 dsa_verify_internal dsa_sign_mu dsa_verify_mu dsa_bits dsa_response_ok
 dsa_hint_unpack dsa_sk_decode dsa_sign_mu_test_fuel.
'''
DRIVER = r'''open Mldsa
let read () = read_line ()
let hex s =
 if String.length s mod 2 <> 0 then failwith "odd hex length";
 List.init (String.length s / 2) (fun i -> Big_int_Z.big_int_of_int
   (int_of_string ("0x" ^ String.sub s (2*i) 2)))
let get () = hex (read ())
let out xs = String.concat "" (List.map (fun n -> Printf.sprintf "%02x"
  (Big_int_Z.int_of_big_int n)) xs)
let result = function DsaOk x -> print_endline (out x)
 | DsaInvalid -> print_endline "INVALID" | DsaExhausted -> print_endline "EXHAUSTED"
let bits s = List.init (String.length s) (fun i -> match s.[i] with
 | '0' -> false | '1' -> true | _ -> failwith "bad bit")
let () = match Sys.argv.(1) with
| "keygen" -> (match dsa_keygen (get ()) with DsaOk (pk,sk) ->
 print_endline (out pk); print_endline (out sk)
 | DsaInvalid -> print_endline "INVALID" | DsaExhausted -> print_endline "EXHAUSTED")
| "sign_mu" -> let sk=get () in let mu=get () in let rnd=get () in
 result (dsa_sign_mu sk mu rnd)
| "sign_internal" -> let sk=get () in let msg=get () in let rnd=get () in
 result (dsa_sign_internal sk (dsa_bits msg) rnd)
| "sign_bits" -> let sk=get () in let msg=bits (read ()) in let rnd=get () in
 result (dsa_sign_internal sk msg rnd)
| "sign" -> let sk=get () in let ctx=get () in let msg=get () in let rnd=get () in
 result (dsa_sign sk ctx (dsa_bits msg) rnd)
| "verify_mu" -> let pk=get () in let mu=get () in let sig_=get () in
 print_endline (string_of_bool (dsa_verify_mu pk mu sig_))
| "verify_internal" -> let pk=get () in let msg=get () in let sig_=get () in
 print_endline (string_of_bool (dsa_verify_internal pk (dsa_bits msg) sig_))
| "verify_bits" -> let pk=get () in let msg=bits (read ()) in let sig_=get () in
 print_endline (string_of_bool (dsa_verify_internal pk msg sig_))
| "verify" -> let pk=get () in let ctx=get () in let msg=get () in let sig_=get () in
 print_endline (string_of_bool (dsa_verify pk ctx (dsa_bits msg) sig_))
| "response" -> let z=Big_int_Z.big_int_of_string (read ()) in
 print_endline (string_of_bool (dsa_response_ok [[z]]))
| "hint" -> print_endline (string_of_bool (dsa_hint_unpack (get ()) <> None))
| "secret" -> print_endline (string_of_bool (dsa_sk_decode (get ()) <> None))
| "exhaust" -> let sk=get () in let mu=get () in let rnd=get () in
 result (dsa_sign_mu_test_fuel 0 sk mu rnd)
| _ -> failwith "unsupported operation (including prehash)"
'''


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(cmd: list[str], cwd: Path, timeout: int = 240,
        input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise
    return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)


def checked(cmd: list[str], work: Path, log: str) -> str:
    result = run(cmd, work)
    (work / log).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"command exited {result.returncode}: see {work / log}")
    return result.stdout


def build(work: Path) -> dict[str, str]:
    os.environ.update(gallina.switch_env(env.ROCQ_SWITCH))
    bindings = {}
    for module in ("PqArith", "Keccak", "MlDsa"):
        source = ROOT / "proofs" / (module + ".v")
        data = source.read_bytes()
        target = work / source.name
        changed = not target.exists() or target.read_bytes() != data
        if changed:
            target.write_bytes(data)
        compiled = target.with_suffix(".vo")
        stamp = work / (module + ".compiled.json")
        identity = {"source": sha(data), "object": sha(compiled.read_bytes()) if compiled.exists() else None,
                    "dependencies": {key: value for key, value in bindings.items() if key.endswith(".vo")}}
        cached = json.loads(stamp.read_text()) if stamp.exists() else None
        if changed or cached != identity or identity["object"] is None:
            checked(env.rocq_command() + ["-Q", str(work), "", str(target)],
                    work, module + ".compile.log")
            identity["object"] = sha(compiled.read_bytes())
            stamp.write_text(json.dumps(identity) + "\n")
        bindings[str(source.relative_to(ROOT))] = sha(data)
        bindings[module + ".vo"] = sha(compiled.read_bytes())
    (work / "ExtractDsa.v").write_text(EXTRACTION)
    checked(env.rocq_command() + ["-Q", str(work), "", str(work / "ExtractDsa.v")],
            work, "extraction.log")
    (work / "driver.ml").write_text(DRIVER)
    checked(["ocamlfind", "ocamlopt", "-package", "zarith", "-linkpkg",
             "mldsa.mli", "mldsa.ml", "driver.ml", "-o", "dsa.exe"], work, "link.log")
    for name in ("ExtractDsa.v", "mldsa.ml", "mldsa.mli", "driver.ml", "dsa.exe"):
        bindings[name] = sha((work / name).read_bytes())
    bindings["proofs/campaigns/mldsa_vectors.py"] = sha(Path(__file__).read_bytes())
    return bindings


def source(work: Path, op: str) -> tuple[dict, dict]:
    rel = f"gen-val/json-files/ML-DSA-{op}-FIPS204/internalProjection.json"
    dest = work / f"ML-DSA-{op}-FIPS204.json"
    if not dest.exists():
        dest.write_bytes(urllib.request.urlopen(BASE + rel, timeout=60).read())
    data = dest.read_bytes()
    if sha(data) != SOURCES[op]:
        raise ValueError(f"source identity mismatch: {dest}")
    return json.loads(data), {"url": BASE + rel, "sha256": sha(data), "bytes": len(data)}


def invoke(work: Path, operation: str, args: list[str]) -> list[str]:
    result = run([str(work / "dsa.exe"), operation], work,
                 input_text="\n".join(args) + "\n")
    if result.returncode:
        raise RuntimeError(f"{operation} exited {result.returncode}: {result.stderr}")
    return result.stdout.splitlines()


def adapted(op: str, group: dict, case: dict) -> tuple[str, list[str], list[str]]:
    if group.get("preHash") == "preHash":
        raise ValueError("HashML-DSA is outside the pure ML-DSA API")
    if op == "keyGen":
        return "keygen", [case["seed"]], [case["pk"].lower(), case["sk"].lower()]
    suffix = ("_mu" if group["externalMu"] else "_internal"
              if group["signatureInterface"] == "internal" else "")
    operation = ("sign" if op == "sigGen" else "verify") + suffix
    args = [case["sk"] if op == "sigGen" else case["pk"]]
    if not suffix:
        args.append(case["context"])
    args.append(case["mu"] if group["externalMu"] else case["message"])
    args.append(case.get("rnd", "00" * 32) if op == "sigGen" else case["signature"])
    expected = ([case["signature"].lower()] if op == "sigGen"
                else [str(case["testPassed"]).lower()])
    return operation, args, expected


def one(work: Path, item: tuple[str, dict, dict]) -> dict:
    op, group, case = item
    start = time.monotonic()
    operation, args, expected = adapted(op, group, case)
    actual = invoke(work, operation, args)
    passed = actual == expected
    verification = None
    if op == "sigGen" and passed:
        verify_operation, verify_args, _ = adapted("sigVer", group,
            dict(case, testPassed=True))
        verification = invoke(work, verify_operation, verify_args) == ["true"]
        passed = passed and verification
    record = {"operation": op, "tgId": group["tgId"], "tcId": case["tcId"],
              "adapter": operation, "passed": passed,
              "expected_sha256": sha("\n".join(expected).encode()),
              "actual_sha256": sha("\n".join(actual).encode()),
              "expected_valid": case.get("testPassed"),
              "reason": case.get("reason"), "generated_signature_verified": verification,
              "seconds": round(time.monotonic() - start, 3)}
    if not passed:
        (work / f"failure-{op}-{case['tcId']}.json").write_text(
            json.dumps({"expected": expected, "actual": actual}, indent=2) + "\n")
    print(f"{op} tc{case['tcId']}: {'PASS' if passed else 'FAIL'}", flush=True)
    return record


def local_cases(work: Path, key_case: dict, sign_case: dict) -> list[dict]:
    """Authored boundary/corruption tests, deliberately not called standard KATs."""
    records = []
    def check(name: str, operation: str, args: list[str], expected: list[str]) -> None:
        got = invoke(work, operation, args)
        records.append({"name": name, "passed": got == expected})
    pk, sk = key_case["pk"], key_case["sk"]
    check("seed-short", "keygen", ["00" * 31], ["INVALID"])
    check("seed-long", "keygen", ["00" * 33], ["INVALID"])
    check("secret-short", "secret", [sk[:-2]], ["false"])
    bad_sk = bytearray.fromhex(sk); bad_sk[128] = (bad_sk[128] & 248) | 7
    check("secret-noncanonical-eta-field", "secret", [bad_sk.hex()], ["false"])
    check("response-positive-below", "response", ["524167"], ["true"])
    check("response-positive-at", "response", ["524168"], ["false"])
    check("response-negative-below", "response", ["-524167"], ["true"])
    check("response-negative-at", "response", ["-524168"], ["false"])
    check("hint-empty-valid", "hint", ["00" * 83], ["true"])
    check("hint-nonzero-unused-padding", "hint", ["01" + "00" * 82], ["false"])
    check("hint-duplicate-index", "hint", ["0404" + "00" * 73 + "02" * 8], ["false"])
    check("hint-descending-index", "hint", ["0403" + "00" * 73 + "02" * 8], ["false"])
    check("hint-overweight", "hint", ["00" * 75 + "4c" * 8], ["false"])
    check("hint-endpoint-regression", "hint", ["00" * 75 + "01" + "00" * 7], ["false"])
    check("hint-short", "hint", ["00" * 82], ["false"])
    check("zero-budget-exhaustion", "exhaust", [sk, "00" * 64, "00" * 32], ["EXHAUSTED"])
    check("randomness-short", "sign_mu", [sk, "00" * 64, "00" * 31], ["INVALID"])
    check("representative-short", "verify_mu", [pk, "00" * 63, "00" * 4627], ["false"])
    check("context-overflow-sign", "sign", [sk, "00" * 256, "", "00" * 32], ["INVALID"])
    check("context-overflow-verify", "verify", [pk, "00" * 256, "", "00" * 4627], ["false"])
    sig = sign_case["signature"]
    check("public-key-short", "verify", [sign_case["pk"][:-2], sign_case["context"],
                                          sign_case["message"], sig], ["false"])
    check("signature-short", "verify", [sign_case["pk"], sign_case["context"],
                                        sign_case["message"], sig[:-2]], ["false"])
    wrong_context = ("00" if not sign_case["context"] else
                     f"{int(sign_case['context'][:2], 16) ^ 1:02x}" + sign_case["context"][2:])
    check("context-binding", "verify", [sign_case["pk"], wrong_context,
                                         sign_case["message"], sig], ["false"])
    bits_sig = invoke(work, "sign_bits", [sk, "101", "00" * 32])
    if len(bits_sig) == 1 and len(bits_sig[0]) == 9254:
        check("partial-byte-bit-message-roundtrip", "verify_bits", [pk, "101", bits_sig[0]], ["true"])
        check("partial-byte-length-binding", "verify_bits", [pk, "10100000", bits_sig[0]], ["false"])
    else:
        records.append({"name": "partial-byte-bit-message-roundtrip", "passed": False})
    try:
        adapted("sigGen", {"preHash": "preHash"}, {})
    except ValueError:
        records.append({"name": "unsupported-prehash-refused", "passed": True})
    else:
        records.append({"name": "unsupported-prehash-refused", "passed": False})
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--quick", action="store_true", help="only first case in each supported group")
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    work = args.work.resolve()
    if sys.platform != "linux" or not str(work).startswith("/root/build/lane-"):
        parser.error("use the assigned native /root/build/lane-* directory inside WSL")
    work.mkdir(parents=True, exist_ok=True)
    started = time.time()
    bindings = build(work)
    documents, identities, items, excluded = {}, {}, [], []
    for op in SOURCES:
        documents[op], identities[op] = source(work, op)
        for group in documents[op]["testGroups"]:
            if group["parameterSet"] != "ML-DSA-87":
                continue
            if group.get("preHash") == "preHash":
                excluded.append({"operation": op, "tgId": group["tgId"],
                                 "reason": "HashML-DSA is outside the selected pure API"})
                continue
            cases = group["tests"][:1] if args.quick else group["tests"]
            items.extend((op, group, case) for case in cases)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda item: one(work, item), items))
    key_case = next(case for op, _, case in items if op == "keyGen")
    sign_case = next(case for op, group, case in items
                     if op == "sigGen" and group["signatureInterface"] == "external")
    local = local_cases(work, key_case, sign_case)
    toolchain = {"rocq": checked(env.rocq_command() + ["--version"], work, "rocq-version.log").strip(),
                 "ocaml": checked(["ocamlopt", "-version"], work, "ocaml-version.log").strip(),
                 "zarith": checked(["ocamlfind", "query", "-format", "%v", "zarith"], work, "zarith-version.log").strip()}
    receipt = {"source_revision": REVISION, "sources": identities, "bindings": bindings,
               "toolchain": toolchain, "started_unix": started, "finished_unix": time.time(),
               "comparison": "complete byte equality; sigVer boolean equality; generated signatures additionally verified",
               "boundary": "Rocq standard extraction, OCaml native compiler/runtime and Zarith Big_int_Z; local Keccak is executed without substitution; extracted nat uses bounded host integers on this finite campaign",
               "excluded_groups": excluded, "official_cases": results, "authored_cases": local,
               "passed": all(r["passed"] for r in results + local)}
    (work / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"official": len(results), "authored": len(local), "passed": receipt["passed"],
                      "receipt": str(work / "receipt.json")}), flush=True)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())