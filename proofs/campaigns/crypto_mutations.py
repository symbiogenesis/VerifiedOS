#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Focused generated mutations with separate definition and proof/vector verdicts.

The foundational modules use native proof compilation as their oracle. ML-KEM
uses definitions-only extraction and pinned official vectors as a runtime oracle.
Neither a definition compile failure nor a timed-out command counts as a kill.
Run in a native lane with the matching audited modules already in --baseline.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["repo", "build", "baseline", "opam-bin"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if not str(args.build.resolve()).startswith("/root/build/lane-"):
        raise ValueError("mutation outputs require an assigned native lane")
    os.environ["PATH"] = str(args.opam_bin) + os.pathsep + os.environ.get("PATH", "")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.repo / "tools"))
    from vos.mutate import COQ, OPERATORS, Operator, mutants, regions

    extra = (
        Operator("if-condition-true", (COQ,), re.compile(r"if poly_eqb[^\n]+"),
                 lambda _: "if true", "Bypass an equality guard"),
        Operator("group-sub-to-add", (COQ,), re.compile(r"\bv_sub\b"),
                 lambda _: "v_add", "Replace group subtraction by addition"),
        Operator("group-add-to-sub", (COQ,), re.compile(r"\bv_add\b"),
                 lambda _: "v_sub", "Replace group addition by subtraction"),
    )
    selections = {
        "PqArith": [("ntt_go", 0), ("byte_encode", 0), ("bits_value", 1),
                    ("mlkem_ring", 4), ("mldsa_ring", 4)],
        "ProbingModel": [("gate_well_formed", 0), ("gate_well_formed", 1),
                         ("wf_from", 0), ("FiniteMassQualification", 0),
                         ("encode", 0), ("shift_mask", 0)],
        "MlKem": [("kem_decaps", 0), ("shake_oracles", 2), ("sample_ntt_bytes", 0),
                  ("cbd_value", 0), ("encapsulation_key_valid", 0),
                  ("decapsulation_input_valid", 0)],
    }
    args.build.mkdir(parents=True, exist_ok=True)
    report = {"selection": selections, "files": {}, "oracle_scope": {
        "PqArith": "same-source native theorem/example compilation after definition-prefix preflight",
        "ProbingModel": "same-source native theorem/example compilation after definition-prefix preflight",
        "MlKem": "definitions-only extracted Gallina against pinned official ML-KEM-1024 vectors"}}

    def run(work: Path, command: list[str], label: str) -> int:
        with (work / (label + ".log")).open("w") as stream:
            try:
                return subprocess.run(command, cwd=work, stdout=stream, stderr=subprocess.STDOUT,
                                      timeout=240, check=False).returncode
            except subprocess.TimeoutExpired:
                return 124

    for name, selection in selections.items():
        source = args.repo / "proofs" / (name + ".v")
        original = source.read_text(encoding="utf-8")
        entries = []
        report["files"][name] = {"sha256": sha(source), "mutants": entries}
        for number, (definition, index) in enumerate(selection):
            population = mutants(original, COQ, "proofs/" + name + ".v", named=(definition,),
                                 operators=OPERATORS + extra)
            mutation = population[index]
            changed = mutation.apply(original)
            row = {"definition": definition, "selected_index": index, "population_size": len(population),
                   "mutation": asdict(mutation)}
            entries.append(row)
            work = args.build / f"{name}-{number}"
            (work / "proofs").mkdir(parents=True, exist_ok=True)
            for dep in ["PqArith", "Keccak"]:
                if name != dep:
                    for suffix in [".v", ".vo"]:
                        shutil.copyfile(args.baseline / "proofs" / (dep + suffix), work / "proofs" / (dep + suffix))
            region = next(r for r in regions(changed, COQ) if r.name == definition and r.keyword in
                          ("Definition", "Fixpoint", "Record", "Inductive"))
            (work / "Preflight.v").write_text(changed[:region.end], encoding="utf-8")
            command = [str(args.opam_bin / "rocq"), "c", "-q", "-Q", "proofs", ""]
            preflight = run(work, command + ["Preflight.v"], "preflight")
            row["preflight_exit"] = preflight
            if preflight:
                row["verdict"] = "timeout" if preflight == 124 else "stillborn"
            elif name != "MlKem":
                (work / "proofs" / (name + ".v")).write_text(changed, encoding="utf-8")
                result = run(work, command + ["proofs/" + name + ".v"], "proof-oracle")
                row["oracle_exit"] = result
                row["verdict"] = "timeout" if result == 124 else "proof-killed" if result else "survived"
            else:
                # MlKem's records are data-only. No proof-defined value is erased:
                # retain definitions/imports/scopes and omit theorem/example statements
                # and their Proof/Qed commands for an independent runtime oracle.
                pieces = [changed[r.start:r.end] for r in regions(changed, COQ)
                          if r.keyword not in ("Theorem", "Lemma", "Example", "Proof", "Qed", "Print")]
                (work / "proofs" / "MlKem.v").write_text("".join(pieces), encoding="utf-8")
                result = run(work, command + ["proofs/MlKem.v"], "definitions")
                row["definitions_exit"] = result
                if result:
                    row["verdict"] = "timeout" if result == 124 else "stillborn"
                else:
                    for src, dst in [("mlkem_extract.v.in", "ExtractMlKem.v"),
                                     ("mlkem_driver.ml.in", "mlkem_driver.ml")]:
                        shutil.copyfile(args.repo / "proofs" / "campaigns" / src, work / dst)
                    extraction = run(work, command + ["ExtractMlKem.v"], "extraction")
                    native = run(work, [str(args.opam_bin / "ocamlfind"), "ocamlopt", "-package", "zarith", "-linkpkg",
                                       "mlkem_reference.mli", "mlkem_reference.ml", "mlkem_driver.ml", "-o", "mutant"], "native") if not extraction else extraction
                    row.update(extraction_exit=extraction, native_exit=native)
                    if native:
                        row["verdict"] = "timeout" if native == 124 else "stillborn"
                    else:
                        queries, expected = [], []
                        for family in ["ML-KEM-keyGen-FIPS203", "ML-KEM-encapDecap-FIPS203"]:
                            data = json.loads((args.baseline / "vectors/gen-val/json-files" / family / "internalProjection.json").read_text())
                            for group in data["testGroups"]:
                                if group["parameterSet"] != "ML-KEM-1024":
                                    continue
                                operation = group.get("function", "keygen")
                                cases = group["tests"] if "Check" in operation else group["tests"][:1]
                                for case in cases:
                                    if operation == "keygen":
                                        query, answer = f"keygen {case['d']} {case['z']}", case["ek"] + ":" + case["dk"]
                                    elif operation == "encapsulation":
                                        query, answer = f"encaps {case['ek']} {case['m']}", case["k"] + ":" + case["c"]
                                    elif operation == "decapsulation":
                                        query, answer = f"decaps {case['dk']} {case['c']}", case["k"]
                                    elif operation == "encapsulationKeyCheck":
                                        query, answer = f"ekcheck {case['ek']} -", str(case["testPassed"]).lower()
                                    else:
                                        query, answer = f"dkcheck {case['dk']} -", str(case["testPassed"]).lower()
                                    queries.append(query)
                                    expected.append((f"tg{group['tgId']}-tc{case['tcId']}-{operation}", answer))
                        try:
                            done = subprocess.run([str(work / "mutant")], input="\n".join(queries) + "\n", text=True,
                                                  capture_output=True, timeout=120, check=False)
                            (work / "runtime.stderr").write_text(done.stderr)
                            answers = done.stdout.splitlines()
                            mismatches = [label for i, (label, answer) in enumerate(expected)
                                          if i >= len(answers) or answers[i] != answer]
                            row.update(runtime_exit=done.returncode, tested_cases=[label for label, _ in expected], mismatches=mismatches)
                            row["verdict"] = "runtime-error" if done.returncode else "vector-killed" if mismatches else "survived"
                        except subprocess.TimeoutExpired:
                            row["verdict"] = "timeout"
            print(name, definition, row["verdict"], flush=True)
            (args.build / "mutation-receipt.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if all(m["verdict"] in ("proof-killed", "vector-killed", "stillborn")
                    for f in report["files"].values() for m in f["mutants"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
