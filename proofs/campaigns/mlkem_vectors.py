#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay pinned official ML-KEM-1024 vectors through extracted Gallina.

Run in the lane's native WSL build directory, with --repo naming the source
checkout and --build naming an existing native directory containing proofs/
and matching compiled PqArith, Keccak and MlKem modules. Generated OCaml and
downloaded vector data stay in that native build directory; tools/vos/acvp.py
pins the revision and every fetched file's SHA-256. This campaign tests an
extracted executable; it does not prove extraction or compiler correctness and
does not replace the native Rocq assumption/kernel audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from vos import acvp  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(build: Path, relative: str) -> tuple[bytes, dict[str, str]]:
    """A pinned file's bytes, verified whether cached or newly downloaded, and its identity."""
    data = acvp.fetch(relative, build / "vectors" / relative)
    return data, {"url": acvp.url(relative), "revision": acvp.REVISION,
                  "sha256": hashlib.sha256(data).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--opam-bin", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0,
                        help="Optional debugging limit per official group; zero runs every selected case")
    args = parser.parse_args()
    os.environ["PATH"] = str(args.opam_bin) + os.pathsep + os.environ.get("PATH", "")
    repo = args.repo.resolve()
    build = args.build.resolve()
    if not str(build).startswith("/root/build/lane-"):
        raise ValueError("campaign outputs require an assigned native lane")
    build.mkdir(parents=True, exist_ok=True)
    recipes = repo / "proofs" / "campaigns"
    for source, target in [("mlkem_extract.v.in", "ExtractMlKem.v"),
                           ("mlkem_driver.ml.in", "mlkem_driver.ml")]:
        shutil.copyfile(recipes / source, build / target)
    inputs = {}
    for name in ["PqArith", "Keccak", "MlKem"]:
        source = repo / "proofs" / f"{name}.v"
        staged = build / "proofs" / f"{name}.v"
        if digest(source) != digest(staged) or not staged.with_suffix(".vo").exists():
            raise ValueError(f"missing same-source compiled module: {name}")
        inputs[name] = {"source_sha256": digest(source), "vo_sha256": digest(staged.with_suffix(".vo"))}
    commands = [
        [str(args.opam_bin / "rocq"), "c", "-q", "-Q", "proofs", "", "ExtractMlKem.v"],
        [str(args.opam_bin / "ocamlfind"), "ocamlopt", "-package", "zarith", "-linkpkg",
         "mlkem_reference.mli", "mlkem_reference.ml", "mlkem_driver.ml", "-o", "mlkem_vectors"],
    ]
    for index, command in enumerate(commands):
        with (build / f"campaign-build-{index}.log").open("w") as stream:
            result = subprocess.run(command, cwd=build, stdout=stream, stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            raise RuntimeError(f"build command {index} exited {result.returncode}; see campaign-build-{index}.log")
    provenance = []
    # Retain the complete upstream notice, the reviewed instrument's exact bytes,
    # alongside the downloaded inputs.
    _, record = download(build, acvp.NOTICE)
    provenance.append(record)
    vector_files = []
    for family in ["ML-KEM-keyGen-FIPS203", "ML-KEM-encapDecap-FIPS203"]:
        data, record = download(build, acvp.vector_path(family))
        provenance.append(record)
        vector_files.append(json.loads(data.decode("utf-8")))
    rows = []
    start = time.monotonic()
    with (build / "campaign-driver.stderr").open("w") as errors:
        process = subprocess.Popen([str(build / "mlkem_vectors")], cwd=build, text=True,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, bufsize=1)
        assert process.stdin is not None and process.stdout is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)

        def check(operation: str, a: str, b: str, expected: str, label: str) -> None:
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(f"{operation} {a or '-'} {b or '-'}\n")
            process.stdin.flush()
            if not selector.select(timeout=180):
                raise TimeoutError(f"no executable answer for {label}")
            actual = process.stdout.readline().strip()
            row = {"label": label, "operation": operation, "pass": actual == expected,
                   "expected_sha256": hashlib.sha256(expected.encode()).hexdigest(),
                   "actual_sha256": hashlib.sha256(actual.encode()).hexdigest()}
            rows.append(row)
            print(label, "PASS" if row["pass"] else "FAIL", flush=True)
            if not row["pass"]:
                row["expected_prefix"] = expected[:96]
                row["actual_prefix"] = actual[:96]
                raise AssertionError(f"{label}: extracted output differs from official/oracle answer")

        failure = ""
        try:
            for document in vector_files:
                for group in document["testGroups"]:
                    if group["parameterSet"] != "ML-KEM-1024":
                        continue
                    tests = group["tests"][:args.limit] if args.limit else group["tests"]
                    operation = group.get("function", "keygen")
                    for case in tests:
                        label = f"official-{operation}-tg{group['tgId']}-tc{case['tcId']}"
                        if operation == "keygen":
                            check("keygen", case["d"], case["z"], case["ek"] + ":" + case["dk"], label)
                        elif operation == "encapsulation":
                            check("encaps", case["ek"], case["m"], case["k"] + ":" + case["c"], label)
                            check("decaps", case["dk"], case["c"], case["k"], label + "-decaps")
                        elif operation == "decapsulation":
                            check("decaps", case["dk"], case["c"], case["k"], label)
                        elif operation == "encapsulationKeyCheck":
                            check("ekcheck", case["ek"], "", str(case["testPassed"]).lower(), label)
                        elif operation == "decapsulationKeyCheck":
                            check("dkcheck", case["dk"], "", str(case["testPassed"]).lower(), label)
                        else:
                            raise ValueError(f"unhandled official group: {operation}")
            for length in [0, 1, 31, 32, 71, 72, 135, 136, 167, 168, 200]:
                message = bytes((i * 73 + length) % 256 for i in range(length))
                for operation, function in [("sha3-256", hashlib.sha3_256), ("sha3-512", hashlib.sha3_512),
                                            ("shake128", hashlib.shake_128), ("shake256", hashlib.shake_256)]:
                    answer = function(message).hexdigest(32) if operation.startswith("shake") else function(message).hexdigest()
                    check(operation, message.hex(), "", answer.upper(), f"hashlib-{operation}-{length}")
            # These are generated refusal cases, separate from the official corpus.
            for length in [0, 1, 31, 33, 64]:
                check("keygen", "00" * length, "00" * 32, "REJECT", f"generated-short-seed-{length}")
        except Exception as error:
            failure = str(error)
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)
            selector.close()
    receipt = {"pass": not failure and process.returncode == 0, "failure": failure,
               "process_exit": process.returncode, "elapsed_seconds": time.monotonic() - start,
               "limit_per_group": args.limit, "provenance": provenance, "inputs": inputs,
               "extracted_ml_sha256": digest(build / "mlkem_reference.ml"),
               "executable_sha256": digest(build / "mlkem_vectors"),
               "commands": commands, "checks": rows,
               "scope": "Actual extracted Gallina including Keccak; native extraction/OCaml/Zarith execution is evidence, not a proved compiler bridge"}
    (build / "mlkem-vector-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("campaign", "PASS" if receipt["pass"] else "FAIL", len(rows), "checks", flush=True)
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
