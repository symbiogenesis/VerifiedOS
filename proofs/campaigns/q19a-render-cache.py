#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reproduce Q19a's rejected cache in a fresh native experiment directory.

This is a qualification experiment, not a presentation or proof-acceptance tool.
It uses an explicitly supplied, separately installed Alectryon/VsRocq tuple.
No repository proof, installed package or previous experiment is modified.
"""

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--renderer", required=True, type=Path)
    parser.add_argument("--switch", required=True, type=Path)
    args = parser.parse_args()
    work = args.work.resolve()
    if not work.is_relative_to(Path("/root/build")):
        parser.error("--work must be a fresh directory under /root/build")
    repo = Path(__file__).resolve().parents[2]
    sources = {name: repo / "proofs" / name
               for name in ("RingContract.v", "CopyRingService.v")}
    original = {name: source.read_bytes() for name, source in sources.items()}
    work.mkdir(parents=True, exist_ok=False)
    staged = work / "proofs"
    staged.mkdir()
    for name, data in original.items():
        (staged / name).write_bytes(data)
    config = work / "_RocqProject"
    config.write_text('-Q proofs ""\n')
    switch = args.switch.resolve()
    renderer = args.renderer.resolve()
    rocq = switch / "bin" / "rocq"
    prefix = original["CopyRingService.v"].decode("utf-8")
    end = prefix.index("Qed.", prefix.index(
        "Theorem the_invariant_survives_every_interleaving")) + len("Qed.")
    prefix = prefix[:end] + "\n"
    review = work / "Review.v"
    review.write_text(prefix)
    dependency = staged / "RingContract.v"
    report = {
        "schema": 1,
        "purpose": "Q19a candidate rejection, not proof acceptance",
        "experiment_sha256": digest(Path(__file__)),
        "source_sha256": {name: digest(path) for name, path in sources.items()},
        "tool_sha256": {str(path): digest(path) for path in
                        (rocq, renderer, switch / "bin" / "vsrocqtop")},
        "config_sha256": digest(config),
        "cases": [],
        "verdict": "incomplete",
    }

    def save():
        (work / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")

    def run(name, command, expected):
        start = time.monotonic()
        result = subprocess.run(command, cwd=work, capture_output=True,
                                text=True, timeout=240)
        row = {"name": name, "command": [str(x) for x in command],
               "exit": result.returncode, "seconds": time.monotonic() - start,
               "dependency_sha256": digest(dependency),
               "source_sha256": digest(review),
               "stdout": result.stdout, "stderr": result.stderr}
        report["cases"].append(row)
        save()
        print(f"{name}: exit {result.returncode}, {row['seconds']:.3f} s", flush=True)
        if (result.returncode == 0) != expected:
            raise RuntimeError(f"{name}: unexpected exit {result.returncode}")
        return row

    def compile_dependency(name):
        run(name, [rocq, "c", "-q", "-Q", "proofs", "",
                   "proofs/RingContract.v"], True)

    def render(name, cache="cache", extra=(), expected=True):
        output = work / (name + ".html")
        row = run(name, ["opam", "exec", "--root=" + str(switch.parent),
                         "--switch=" + switch.name, "--",
                         renderer, "--frontend", "coq", "--coq-driver", "vsrocq",
                         "--backend", "webpage", "--cache-directory", work / cache,
                         "-Q", staged, "", *extra, review, "-o", output], expected)
        row["html_sha256"] = digest(output)
        save()
        return row

    try:
        run("candidate-packages", ["opam", "list", "--root=" + str(switch.parent),
                                   "--switch=" + switch.name,
                                   "--installed", "--short", "--columns=name,version"], True)
        compile_dependency("baseline-import")
        cold = render("cold")
        warm = render("warm")
        if cold["html_sha256"] != warm["html_sha256"]:
            raise RuntimeError("baseline cache did not reproduce the cold page")
        admitted, count = re.subn(
            r"(Lemma eqb_reflexive\s*:.*?\n)Proof\..*?Qed\.",
            r"\1Admitted.", original["RingContract.v"].decode("utf-8"),
            count=1, flags=re.S)
        if count != 1:
            raise RuntimeError("imported-lemma mutation did not apply")
        dependency.write_text(admitted)
        compile_dependency("admitted-import")
        stale = render("changed-import")
        if (stale["dependency_sha256"] == cold["dependency_sha256"]
                or stale["html_sha256"] != cold["html_sha256"]):
            raise RuntimeError("recorded stale-import result did not reproduce")
        # A stronger control makes the unchanged review invalid under its import.
        # A fresh backend must fail, while the previously filled cache may pass.
        renamed, count = re.subn(r"\bring_capacity\b", "q19a_renamed_capacity",
                                 original["RingContract.v"].decode("utf-8"))
        if count == 0:
            raise RuntimeError("imported-name mutation did not apply")
        dependency.write_text(renamed)
        compile_dependency("renamed-import")
        stale = render("renamed-import-cached")
        if stale["html_sha256"] != cold["html_sha256"]:
            raise RuntimeError("renamed-import cache result differs from baseline")
        fresh = render("renamed-import-fresh", cache="fresh-cache", expected=False)
        if "ring_capacity" not in fresh["stderr"]:
            raise RuntimeError("fresh renderer failed for an unrelated reason")
        dependency.write_bytes(original["RingContract.v"])
        compile_dependency("restored-import")
        render("changed-config", extra=("--rocq-arg=-noinit",), expected=False)
        review.write_text(prefix.replace("Nat.ltb (rv_occupancy v) ring_capacity",
                                        "Nat.leb (rv_occupancy v) ring_capacity"))
        broken = render("broken-bound", expected=False)
        if "Hg" not in broken["stderr"] or "Nat.ltb" not in broken["stderr"]:
            raise RuntimeError("broken source failed for an unrelated reason")
        report["verdict"] = "reproduced-candidate-rejection"
    finally:
        review.write_text(prefix)
        dependency.write_bytes(original["RingContract.v"])
        report["repository_sources_unchanged"] = all(
            path.read_bytes() == original[name] for name, path in sources.items())
        save()
    if not report["repository_sources_unchanged"]:
        raise RuntimeError("repository sources changed during the experiment")
    print(report["verdict"], flush=True)


if __name__ == "__main__":
    main()
