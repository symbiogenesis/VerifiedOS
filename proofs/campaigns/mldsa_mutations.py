# SPDX-License-Identifier: Apache-2.0
"""Compile selected algorithm mutants, then ask the official byte oracle.

This is a focused sensitivity campaign, not exhaustive semantic coverage.
Compile failures are stillborn; only a compiled mutant with a mismatching
executed oracle result is killed. Every output stays under the assigned lane.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
import sys

sys.dont_write_bytecode = True
import mldsa_vectors as campaign
from vos import env, gallina

MUTANTS = (
    ("matrix-index-order", "[Z.of_nat s; Z.of_nat r]", "[Z.of_nat r; Z.of_nat s]", "keyGen"),
    ("keygen-domain", "seed ++ [8;7]", "seed ++ [7;8]", "keyGen"),
    ("noise-nibble-order", "[b mod 16; b / 16]", "[b / 16; b mod 16]", "keyGen"),
    ("noise-rejection", "if b <? 15 then", "if b <? 16 then", "keyGen"),
    ("mask-nonce", "dsa_nonce (kappa + r)", "dsa_nonce (kappa + r + 1)", "sigGen"),
    ("challenge-domain-order", "let ct:=dsa_h 64 (mu ++ dsa_pack_vec 4 w1)",
     "let ct:=dsa_h 64 (dsa_pack_vec 4 w1 ++ mu)", "sigGen"),
    ("challenge-sign", "if sign then -1 else 1", "if sign then 1 else -1", "sigGen"),
    ("signature-signed-packing", "ct ++ dsa_pack_signed_vec 20 dsa_gamma1 z",
     "ct ++ dsa_pack_signed_vec 20 (dsa_gamma1-1) z", "sigGen"),
    ("verification-hint-direction", "if 0 <? lo then (hi+1) mod 16 else (hi-1) mod 16",
     "if 0 <? lo then (hi-1) mod 16 else (hi+1) mod 16", "verifyValid"),
    ("verification-high-scale", "(dsa_ntt (vscale dsa_q 8192 p))) t1",
     "(dsa_ntt (vscale dsa_q 4096 p))) t1", "verifyValid"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    work, baseline = args.work.resolve(), args.baseline.resolve()
    if not all(str(p).startswith("/root/build/lane-") for p in (work, baseline)):
        parser.error("both paths must be inside the assigned native lane")
    if work.parent != baseline.parent:
        parser.error("baseline and mutants must be siblings within the same assigned lane")
    work.mkdir(parents=True, exist_ok=True)
    os.environ.update(gallina.switch_env(env.ROCQ_SWITCH))
    source = (campaign.ROOT / "proofs/MlDsa.v").read_text()
    receipt = json.loads((baseline / "receipt.json").read_text())
    if not receipt["passed"] or receipt["bindings"]["proofs/MlDsa.v"] != campaign.sha(source.encode()):
        raise ValueError("a passing baseline for the identical source is required")
    for module in ("PqArith", "Keccak", "MlDsa"):
        source_path = campaign.ROOT / "proofs" / (module + ".v")
        key = str(source_path.relative_to(campaign.ROOT))
        if receipt["bindings"][key] != campaign.sha(source_path.read_bytes()):
            raise ValueError(f"baseline source drift: {module}")
        object_key = module + ".vo"
        if object_key not in receipt["bindings"] or receipt["bindings"][object_key] != campaign.sha((baseline / object_key).read_bytes()):
            raise ValueError(f"baseline object drift or missing identity: {module}")
    vectors = {}
    for op in ("keyGen", "sigGen"):
        doc, _ = campaign.source(baseline, op)
        group = next(g for g in doc["testGroups"] if g["parameterSet"] == "ML-DSA-87"
                     and (op == "keyGen" or g["preHash"] == "pure"))
        vectors[op] = (group, group["tests"][0])
    results = []
    for name, before, after, op in MUTANTS:
        if source.count(before) != 1:
            raise ValueError(f"{name}: expected exactly one source match")
        stage = work / name; stage.mkdir(exist_ok=True)
        (stage / "Focus.v").write_text(source.replace(before, after))
        flags = ["-Q", str(baseline), "", "-Q", str(stage), ""]
        start = time.monotonic()
        result = campaign.run(env.rocq_command() + flags + [str(stage / "Focus.v")], stage)
        (stage / "compile.log").write_text(result.stdout + result.stderr)
        record = {"name": name, "source_sha256": campaign.sha((stage / "Focus.v").read_bytes()),
                  "before": before, "after": after, "compile_exit": result.returncode}
        if result.returncode:
            record["outcome"] = "stillborn"
        else:
            (stage / "ExtractDsa.v").write_text(campaign.EXTRACTION.replace("Require Import MlDsa.", "Require Import Focus."))
            campaign.checked(env.rocq_command() + flags + [str(stage / "ExtractDsa.v")], stage, "extraction.log")
            (stage / "driver.ml").write_text(campaign.DRIVER)
            campaign.checked(["ocamlfind", "ocamlopt", "-package", "zarith", "-linkpkg",
                              "mldsa.mli", "mldsa.ml", "driver.ml", "-o", "dsa.exe"], stage, "link.log")
            group, case = vectors["sigGen" if op == "verifyValid" else op]
            command, operands, expected = campaign.adapted("sigVer" if op == "verifyValid" else op,
                                                          group, dict(case, testPassed=True))
            actual = campaign.invoke(stage, command, operands)
            record.update({"outcome": "killed" if actual != expected else "survived",
                           "tcId": case["tcId"], "oracle": op,
                           "executable_sha256": campaign.sha((stage / "dsa.exe").read_bytes()),
                           "expected_output_sha256": campaign.sha("\n".join(expected).encode()),
                           "actual_output_sha256": campaign.sha("\n".join(actual).encode())})
        record["seconds"] = round(time.monotonic() - start, 3)
        results.append(record)
        print(name, record["outcome"], flush=True)
    report = {"baseline_source_sha256": campaign.sha(source.encode()),
              "source_revision": campaign.REVISION, "selected": len(results),
              "killed": sum(r["outcome"] == "killed" for r in results),
              "stillborn": sum(r["outcome"] == "stillborn" for r in results),
              "survived": sum(r["outcome"] == "survived" for r in results), "results": results}
    (work / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}), flush=True)
    return 0 if report["killed"] == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())