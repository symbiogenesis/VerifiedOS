# SPDX-License-Identifier: Apache-2.0
"""Retain guest receipts and render diagnostics without deciding gate verdicts."""

import json
import os
import shutil
from pathlib import Path

COMMANDS = ("bootstrap", "evidence", "bundle", "lint", "crosscheck")
ROOT = Path(__file__).resolve().parents[2]


def report(logs: Path, console: Path, proof: Path, steps: dict[str, dict[str, str]],
           revision: str) -> str:
    """Keep command outcomes even when evidence is absent or unreadable."""
    logs.mkdir(parents=True, exist_ok=True)
    if console.is_file():
        shutil.copyfile(console, logs / "bootstrap-console.log")
    outcomes = {name: steps.get(name, {}).get("outcome", "skipped") for name in COMMANDS}
    result = {"revision": revision, "commands": outcomes}
    (logs / "results.json").write_text(json.dumps(result, indent=2) + "\n",
                                       encoding="utf-8", newline="")
    rows = ["### Guest gates", "", "| Command | Outcome |", "| --- | --- |"]
    rows.extend(f"| {name} | {outcome} |" for name, outcome in outcomes.items())
    record = logs / "evidence.json"
    if record.is_file():
        try:
            members = json.loads(record.read_text(encoding="utf-8"))["members"]
            rows.extend(("", "| Evidence member | Exit | Seconds |", "| --- | --- | --- |"))
            rows.extend(f"| {m['name']} | {m['exit_code']} | {m['seconds']:.1f} |" for m in members)
            if any(m["name"] == "proofs" and m["exit_code"] == 0 for m in members):
                shutil.copyfile(proof, logs / "proof-evidence.json")
        except (OSError, ValueError, KeyError, TypeError) as error:
            rows.extend(("", f"Evidence report could not be read: {type(error).__name__}. See logs."))
    else:
        rows.extend(("", "No evidence record was written; see the bootstrap and gate logs."))
    return "\n".join(rows) + "\n"


def main() -> None:
    summary = report(
        Path.home() / "verifiedos-guest" / "logs",
        Path(os.environ["RUNNER_TEMP"]) / "guest-bootstrap-console.log",
        ROOT / "proofs" / "proof-evidence.json",
        json.loads(os.environ["STEP_RESULTS"]), os.environ["GITHUB_SHA"],
    )
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8", newline="") as stream:
        stream.write(summary)


if __name__ == "__main__":
    main()
