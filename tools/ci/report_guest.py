# SPDX-License-Identifier: Apache-2.0
"""Retain guest receipts and render diagnostics without deciding gate verdicts."""

import html
import json
import math
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from vos import receipts  # noqa: E402  (standalone reporting needs no locked environment)

# Each lane's workflow step ids, in execution order.
LANES: dict[str, tuple[str, ...]] = {
    "model": ("bootstrap", "evidence", "bundle", "lint", "crosscheck"),
    "proofs": ("bootstrap", "proofs"),
}


@dataclass(frozen=True)
class Member:
    name: str
    exit_code: int
    seconds: float


def read_members(path: Path) -> list[Member]:
    """Validate the entire table before rendering it or retaining a proof receipt."""
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or not isinstance(record.get("members"), list):
        raise TypeError("evidence must contain a members array")
    members: list[Member] = []
    names: set[str] = set()
    for item in record["members"]:
        if not isinstance(item, dict):
            raise TypeError("evidence members must be objects")
        name, code, seconds = (item.get(key) for key in ("name", "exit_code", "seconds"))
        if not isinstance(name, str):
            raise TypeError("evidence member names must be strings")
        if not name or name in names:
            raise ValueError("evidence member names must be nonempty and unique")
        if not isinstance(code, int) or isinstance(code, bool):
            raise TypeError(f"{name}: exit_code must be an integer")
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
            raise TypeError(f"{name}: seconds must be numeric")
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError(f"{name}: seconds must be finite and nonnegative")
        names.add(name)
        members.append(Member(name, code, float(seconds)))
    return members


def retain(source: Path, destination: Path, rows: list[str]) -> None:
    """A missing diagnostic must not discard the command outcomes or other diagnostics."""
    try:
        with receipts.atomic_path(destination) as pending:
            shutil.copyfile(source, pending)
    except OSError as error:
        print(f"Could not retain {destination}: {error}", file=sys.stderr)
        rows.extend(("", f"Could not retain {destination.name}: {type(error).__name__}. See logs."))


def cell(value: str) -> str:
    return html.escape(value).replace("|", "&#124;").replace("\r", " ").replace("\n", " ")


def evidence_rows(logs: Path, outcome: str) -> list[str]:
    """Render only a record that the current evidence step finished writing."""
    if outcome not in {"success", "failure"}:
        return ["", "No evidence record for this run: the evidence step did not finish."]
    try:
        members = read_members(logs / "evidence.json")
    except FileNotFoundError:
        return ["", "No evidence record was written; see the bootstrap and gate logs."]
    except (OSError, ValueError, TypeError, OverflowError) as error:
        print(f"Could not read guest evidence: {error}", file=sys.stderr)
        return ["", f"Evidence report could not be read: {type(error).__name__}. See logs."]
    return ["", "| Evidence member | Exit | Seconds |", "| --- | --- | --- |",
            *(f"| {cell(m.name)} | {m.exit_code} | {m.seconds:.1f} |" for m in members)]


def report(lane: str, logs: Path, console: Path, proof: Path,
           steps: dict[str, dict[str, str]], revision: str) -> str:
    """Keep command outcomes even when evidence is absent or unreadable."""
    logs.mkdir(parents=True, exist_ok=True)
    outcomes = {name: steps.get(name, {}).get("outcome", "skipped") for name in LANES[lane]}
    receipts.write(logs / "results.json",
                   {"revision": revision, "lane": lane, "commands": outcomes})
    rows = [f"### Guest gates: {lane}", "", "| Command | Outcome |", "| --- | --- |"]
    rows.extend(f"| {name} | {outcome} |" for name, outcome in outcomes.items())
    retained_proof = logs / "proof-evidence.json"
    retained_proof.unlink(missing_ok=True)
    if console.is_file():
        retain(console, logs / "bootstrap-console.log", rows)
    # The checkout's tracked receipt predates this run unless this lane's gate passed.
    if outcomes.get("proofs") == "success":
        retain(proof, retained_proof, rows)
    if "evidence" in outcomes:
        rows.extend(evidence_rows(logs, outcomes["evidence"]))
    return "\n".join(rows) + "\n"


def main() -> None:
    lane = os.environ["GUEST_LANE"]
    if lane not in LANES:
        raise SystemExit(f"unknown guest lane {lane!r}; expected one of {', '.join(LANES)}")
    summary = report(
        lane,
        Path(os.environ.get("VOS_LOG_DIR", Path.home() / "verifiedos-guest" / "logs")),
        Path(os.environ["RUNNER_TEMP"]) / "guest-bootstrap-console.log",
        ROOT / "proofs" / "proof-evidence.json",
        json.loads(os.environ["STEP_RESULTS"]), os.environ["GITHUB_SHA"],
    )
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8", newline="") as stream:
        stream.write(summary)


if __name__ == "__main__":
    main()
