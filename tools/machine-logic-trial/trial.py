# SPDX-License-Identifier: Apache-2.0
"""Reproduce Q35m's focused refusal in a prepared, private native source prefix.

This is a qualification client, not a proof gate or package installer. See the
machine-logic dependency trial document for exact source acquisition commands.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SOURCES = {
    "islaris": "c978e10f50db5c40f0fdf113f5f76a779782c6f9",
    "katamaran": "47bc545117348495f71aad9e20d5c9bb9ed3a757",
    "isla-lang": "bda86c9f0bd28bbaa2481f50ddc986ede342805a",
    "iris": "b909adcc698a6c38f4c3b2645936bdd0d870d412",
    "lithium": "7945a29d1647970709a9b5ad2ffc53c757e130cc",
    "record-update": "50e45e9f4ed52840427c3bfddc9037a645d9bf19",
}
SWITCH = "verifiedos-rocq-9.3.0-ocaml-5.4.1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    prefix = args.prefix.resolve()
    if sys.platform != "linux" or not args.prefix.is_absolute():
        parser.error("run in the Linux guest with an absolute native prefix")
    if not prefix.is_relative_to(Path("/root/build")) or prefix.is_relative_to(checkout):
        parser.error("prefix must be a private directory under /root/build")
    evidence = prefix / "evidence"
    evidence.mkdir(exist_ok=True)
    # Native diagnostic startup, including imports, has a temp process directory.
    # Build subprocesses use their explicitly named native source/build directories.
    scratch = Path(tempfile.mkdtemp(prefix="vos-q35m-"))
    os.chdir(scratch)
    sys.path.insert(0, str(checkout / "tools"))
    # Import the validated checkout only after native diagnostic startup is isolated.
    from vos import proofaudit  # noqa: PLC0415
    from vos.cli.proofs import STRICT  # noqa: PLC0415

    receipt: dict[str, Any] = {
        "schema": "q35m-dependency-trial-v1", "started_utc": now(),
        "checkout": str(checkout), "prefix": str(prefix), "scratch": str(scratch),
        "attended_cap_hours": 12, "strict": list(STRICT), "runs": [],
        "assumption_closures": {"islaris": None, "katamaran": None},
        "frozen_elaborated_comparisons": {"islaris": None, "katamaran": None},
        "qualified_result": "unavailable",
    }
    started = time.monotonic()

    def run(name: str, argv: list[str], cwd: Path = scratch, timeout: int = 300) -> int:
        log = evidence / (name + ".log")
        entry: dict[str, Any] = {"name": name, "argv": argv, "cwd": str(cwd),
                                 "started_utc": now(), "log": log.name}
        tick = time.monotonic()
        with log.open("wb") as stream:
            try:
                done = subprocess.run(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                      check=False, timeout=timeout)
                code = done.returncode
            except subprocess.TimeoutExpired:
                code = 124
                stream.write(b"\nQ35m client: command timed out; no passing evidence.\n")
        entry.update(exit_code=code, elapsed_seconds=time.monotonic() - tick,
                     log_sha256=digest(log))
        receipt["runs"].append(entry)
        write(evidence / "receipt.json", receipt)
        print(name, code, flush=True)
        return code

    identities: dict[str, Any] = {}
    for name, revision in SOURCES.items():
        source = prefix / name
        head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"],
                                       cwd=scratch, text=True).strip()
        if head != revision:
            raise ValueError(f"{name}: expected {revision}, got {head}")
        files = subprocess.check_output(["git", "-C", str(source), "ls-files", "-z"],
                                        cwd=scratch).decode().split("\0")
        hashes = {rel: digest(source / rel) for rel in files if rel}
        identities[name] = {"revision": head, "files": hashes}
        for rel, sha in hashes.items():
            if Path(rel).name.startswith("LICENSE") or Path(rel).name == "THIRD_PARTY_FILES.md":
                identities[name].setdefault("licenses", {})[rel] = sha
        run(name + "-source-diff-before", ["git", "-C", str(source), "diff", "HEAD"])
    write(evidence / "source-identities.json", identities)
    receipt["source_identities_sha256"] = digest(evidence / "source-identities.json")
    receipt["client_sha256"] = digest(Path(__file__))
    compiler = Path("/root/.opam") / SWITCH / "bin/rocq"
    checker = compiler.with_name("rocqchk")
    receipt["binaries"] = {str(path): digest(path) for path in (compiler, checker)}
    run("prover-version", [str(compiler), "-v"])
    run("switch-inventory", ["opam", "list", f"--switch={SWITCH}", "--installed",
                             "--columns=name,version", "--color=never"])
    before = evidence / "switch-before.export"
    after = evidence / "switch-after.export"
    run("switch-export-before", ["opam", "switch", "export", f"--switch={SWITCH}", str(before)])

    iris_maps = ["-Q", str(prefix / "iris/iris"), "iris"]
    islaris_maps = [*iris_maps, "-Q", str(prefix / "islaris/theories"), "isla",
                    "-Q", str(prefix / "islaris/instructions"), "isla.instructions",
                    "-Q", str(prefix / "islaris/examples"), "isla.examples",
                    "-Q", str(prefix / "lithium/theories/lithium"), "lithium",
                    "-Q", str(prefix / "record-update/src"), "RecordUpdate"]
    katamaran_maps = [*iris_maps, "-R", str(prefix / "katamaran/theories"), "Katamaran"]
    preflight = {}
    for name, rel in [("islaris", "theories/base.v"), ("lithium", "theories/lithium/base.v")]:
        preflight[name] = {"path": rel, "sha256": digest(prefix / name / rel),
                           "pinned_overrides": proofaudit.pinned_overrides(
                               (prefix / name / rel).read_text())}
    write(evidence / "source-policy.json", preflight)

    # The stock Iris package was built separately with its own published builder.
    # This confirmation does not qualify either framework's closure.
    run("iris-build-confirmation", ["opam", "exec", f"--switch={SWITCH}", "--",
                                    "sh", "./make-package", "iris", "-j2"], prefix / "iris", 1800)
    probes = {
        "IrisProbe": "From iris.program_logic Require Import weakestpre adequacy.\n"
                     "Print Assumptions wp_adequacy.\n",
        "ProgramEqualityProbe": "From Stdlib Require Import Program.Equality.\n"
                                "Print Assumptions Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq.\n",
        "SelectedExampleAudit": "From isla.examples Require Import riscv64_test.\n"
                                "Set Printing All.\nSet Printing Universes.\n"
                                "Check isla.examples.riscv64_test.riscv_test.\n"
                                "Check isla.examples.riscv64_test.riscv_test_adequate.\n"
                                "Print Assumptions isla.examples.riscv64_test.riscv_test.\n"
                                "Print Assumptions isla.examples.riscv64_test.riscv_test_adequate.\n",
        "KatamaranAudit": "From Katamaran.Iris Require Import Instance BinaryAdequacy.\n"
                          "Set Printing All.\nSet Printing Universes.\n"
                          "Print Katamaran.Iris.Instance.IrisInstance.\n"
                          "Print Katamaran.Iris.BinaryAdequacy.IrisAdequacy2.\n",
    }
    for name, text in probes.items():
        (evidence / (name + ".v")).write_text(text, encoding="utf-8")
    for name in ("IrisProbe", "ProgramEqualityProbe"):
        run(name + "-strict", [str(compiler), "c", "-q", *STRICT, *iris_maps,
                                str(evidence / (name + ".v"))], evidence)
        run(name + "-kernel", [str(checker), "-silent", "-o", *iris_maps,
                                "-Q", str(evidence), "", name], evidence)
    for name, rel in [("record-update", "src/RecordSet.v"),
                      ("lithium", "theories/lithium/base.v"),
                      ("islaris", "theories/base.v")]:
        run(name + "-strict-frontier", [str(compiler), "c", "-q", *STRICT,
                                        *islaris_maps, str(prefix / name / rel)], prefix / name)
    for rel in ("theories/Notations.v", "theories/Prelude.v", "theories/Iris/Instance.v",
                "theories/Iris/BinaryAdequacy.v"):
        run("katamaran-" + Path(rel).stem + "-strict", [str(compiler), "c", "-q", *STRICT,
                                                       *katamaran_maps, str(prefix / "katamaran" / rel)],
            prefix / "katamaran")
    for name, maps, roots in [
        ("SelectedExampleAudit", islaris_maps, ["isla.examples.riscv64_test"]),
        ("KatamaranAudit", katamaran_maps, ["Katamaran.Iris.Instance", "Katamaran.Iris.BinaryAdequacy"]),
    ]:
        run(name + "-strict", [str(compiler), "c", "-q", *STRICT, *maps,
                                str(evidence / (name + ".v"))], evidence)
        run(name + "-kernel", [str(checker), "-silent", "-o", *maps, *roots], evidence)
    for name in SOURCES:
        run(name + "-source-diff-after", ["git", "-C", str(prefix / name), "diff", "HEAD"])
    run("switch-export-after", ["opam", "switch", "export", f"--switch={SWITCH}", str(after)])
    receipt.update(ended_utc=now(), elapsed_seconds=time.monotonic() - started,
                   switch_unchanged=before.read_bytes() == after.read_bytes(),
                   switch_before_sha256=digest(before), switch_after_sha256=digest(after),
                   qualified_result="refusal" if
                   any(entry["exit_code"] for entry in receipt["runs"]
                       if entry["name"] in {"islaris-strict-frontier", "lithium-strict-frontier",
                                            "record-update-strict-frontier",
                                            "katamaran-Notations-strict"})
                   else "requires-manual-audit")
    write(evidence / "receipt.json", receipt)
    keep = {"receipt.json", "source-identities.json", "source-policy.json",
            "switch-before.export", "switch-after.export"}
    keep.update(entry["log"] for entry in receipt["runs"]
                if "-source-diff-" not in entry["name"])
    keep.update(name + ".v" for name in probes)
    write(prefix / "evidence-catalog.json", {
        "generator": "tools/machine-logic-trial/trial.py",
        "schema": "q35m-retained-evidence-catalog-v1",
        "files": [{"path": str(evidence / name), "sha256": digest(evidence / name)}
                  for name in sorted(keep)],
    })
    return 0 if receipt["switch_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
