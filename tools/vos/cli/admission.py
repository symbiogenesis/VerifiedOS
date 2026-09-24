# SPDX-License-Identifier: Apache-2.0
"""Execute composition-time admission metadata and compare the Gallina reference.

Every record is fixture-reference evidence. Real derivation checking remains open.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from vos import admission, boot, corpus, env


def _compare(root: Path) -> int:
    if sys.platform == "win32":
        raise admission.AdmissionError("compare runs in the guest's native lane")
    folder = env.load(toolchain=False).lane_root / "admission-reference"
    logs = env.lane_dir(env.log_root(), env.lane_of(root)) / "admission-reference"
    folder.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    (folder / "comparison.json").unlink(missing_ok=True)
    owners = (admission.SOURCE, admission.CHECKER, "tools/vos/cli/admission.py")
    before = {name: admission.digest((root / name).read_bytes()) for name in owners}
    reference = admission.read_reference(root)
    (folder / "AdmissionPath.v").write_bytes((root / admission.SOURCE).read_bytes())
    (folder / "AdmissionComparison.v").write_text(admission.comparison_source(reference),
                                                 encoding="utf-8", newline="\n")
    commands = []
    for name in ("AdmissionPath.v", "AdmissionComparison.v"):
        command = [*env.rocq_command(), "-q", "-Q", str(folder), "", str(folder / name)]
        completed = subprocess.run(command, cwd=folder, capture_output=True, text=True,
                                   encoding="utf-8", check=False, timeout=180)
        (logs / (name + ".log")).write_text(completed.stdout + completed.stderr,
                                           encoding="utf-8", newline="\n")
        commands.append({"source": name, "command": command, "returncode": completed.returncode})
        if completed.returncode:
            print(f"FAIL admission compare: {name}; see {logs / (name + '.log')}")
            return 1
    after = {name: admission.digest((root / name).read_bytes()) for name in owners}
    if before != after or admission.digest((folder / "AdmissionPath.v").read_bytes()) != before[admission.SOURCE]:
        print("FAIL admission compare: inputs changed during comparison")
        return 1
    report = {"schema_version": 1, "scope": "finite reference comparison, not refinement",
              "cases": len(admission.generated_cases(reference)), "commands": commands,
              "inputs_before": before, "inputs_after": after, "logs": str(logs),
              "reference_sha256": admission.digest((folder / "AdmissionPath.v").read_bytes()),
              "comparison_sha256": admission.digest((folder / "AdmissionComparison.v").read_bytes()),
              "checker_sha256": admission.digest((root / admission.CHECKER).read_bytes())}
    (folder / "comparison.json").write_bytes(admission.canonical(report))
    print(f"ok admission compare: {report['cases']} generated decisions; {folder / 'comparison.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, prog="run.py admission")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("compare", help="compile generated comparisons against AdmissionPath.v")
    emit = commands.add_parser("emit-reference", help="write generated Gallina comparison source")
    emit.add_argument("--out", required=True)
    record = commands.add_parser("record", help="bind a fixture decision to image and graph bytes")
    record.add_argument("request")
    record.add_argument("--image", required=True)
    record.add_argument("--graph", required=True)
    record.add_argument("--roster", default=boot.CONTRACT)
    record.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    root = corpus.find_root()
    try:
        if args.command == "compare":
            return _compare(root)
        if args.command == "emit-reference":
            Path(args.out).write_text(admission.comparison_source(admission.read_reference(root)),
                                      encoding="utf-8", newline="\n")
            return 0
        result = admission.make_record(root, args.request, Path(args.image).read_bytes(),
                                        Path(args.graph).read_bytes(), boot.load_roster(root, args.roster))
        Path(args.out).write_bytes(admission.canonical(result))
        print(json.dumps({"decision": result["decision"], "scope": result["scope"],
                          "production_admission": False, "open": result["open"]}))
        return 0 if result["decision"] == "accepted" else 1
    except (admission.AdmissionError, boot.RecipeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL admission: {exc}")
        return 2
