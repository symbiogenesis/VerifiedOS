# SPDX-License-Identifier: Apache-2.0
"""Run the evidence sweep against current build receipts and record its verdicts.

--no-build requires matching sources, tools, artifacts and test log. Model consumers
hold the build lock. Proofs run in a separate process alongside those consumers;
each member preserves its output and exit status in a unique JSON execution record.
"""

import argparse
import contextlib
import json
import os
import re
import signal
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO

from vos import cli, env, receipts
from vos.cli import model as model_cli
from vos.cli import proofs as proofs_cli
from vos.report import Reporter

HEADING = "=== evidence: the exit-evidence sweep over the curated model ==="
_CTEST_RE = re.compile(r"(\d+)% tests passed, (\d+) tests failed out of (\d+)")


@dataclass(frozen=True)
class Member:
    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class Result:
    name: str
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    seconds: float


MEMBERS = (
    Member("build", ("model", "build")),
    Member("reference", ("model", "reference")),
    Member("sweep", ("model", "sweep")),
    Member("corpus", ("model", "corpus")),
    Member("devicetree", ("model", "devicetree")),
    Member("proofs", ("proofs",)),
)

TIMEOUTS = {"build": 7200, "proofs": 3600}


def _launch(member: Member) -> Result:
    started = time.perf_counter()
    print(f"running evidence member: {member.name}", flush=True)
    try:
        with subprocess.Popen(
                cli.entry(*member.command), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                encoding="utf-8", errors="replace", start_new_session=True) as child:
            try:
                stdout, stderr = child.communicate(timeout=TIMEOUTS.get(member.name, 900))
            except subprocess.TimeoutExpired:
                # This command runs in the guest. End its process group as well, so
                # a hung compiler cannot keep writing after the sweep releases locks.
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGKILL)
                stdout, stderr = child.communicate()
                return Result(member.name, member.command, 1, stdout,
                              stderr + "\nevidence member timed out", time.perf_counter() - started)
            return Result(member.name, member.command, child.returncode,
                          stdout, stderr, time.perf_counter() - started)
    except OSError as err:
        return Result(member.name, member.command, 1, "", str(err),
                      time.perf_counter() - started)


def _ctest(log: Path) -> str:
    """A complete successful test tally from the verified build's own log."""
    text = log.read_text(encoding="utf-8")
    matches = list(_CTEST_RE.finditer(text))
    if not matches or not text.rstrip().endswith("ALL_DONE"):
        raise ValueError("the verified build log carries no complete ctest result")
    found = matches[-1]
    percentage, failed, total = map(int, found.groups())
    if percentage != 100 or failed or total == 0:
        raise ValueError("the build's ctest result is empty or failing")
    return f"{total} of {total}"


def _figures(results: list[Result], log: Path) -> dict[str, str]:
    """Display measurements only after every producing process succeeded."""
    said = {result.name: result.stdout for result in results}
    fields: tuple[tuple[str, str, str], ...] = (
        ("model revision", "reference", r"model revision\s+(\S+)"),
        ("$[test] harness", "reference", r"properties\s+(\d+)"),
        ("profile sweep", "sweep", r"TOTAL pass=\d+ refuse=\d+ hang=\d+ of \d+"),
        ("differential corpus", "corpus", r"TOTAL pass=\d+ fail=\d+ of \d+"),
        ("corpus size", "reference", r"corpus\s+v\d+, \d+ members, \d+ checks, \d+ records"),
        ("devicetree", "devicetree", r"at (\d+) bytes"),
        ("proof gate", "proofs", r"ok: (\d+) constant"),
    )
    figures: dict[str, str] = {"ctest": _ctest(log)}
    for label, member, pattern in fields:
        found = re.search(pattern, said.get(member, ""))
        if found is None:
            raise ValueError(f"{member} produced no {label} measurement")
        figures[label] = found.group(1) if found.lastindex else found.group(0)
    return figures


def _proof_record(root: Path) -> dict[str, object]:
    """Revalidate compiled proofs after every consumer finishes, under their lock."""
    held = proofs_cli._hold(root / proofs_cli.PROOFS)
    try:
        proofs_cli._validate_receipt(root)
        path = root / proofs_cli.RECEIPT
        return {"sha256": receipts.digest(path),
                "receipt": json.loads(path.read_text(encoding="utf-8"))}
    finally:
        os.close(held)


def run(build: bool = True, out: Path | None = None) -> Reporter:
    e = env.load()
    rep = Reporter()
    rep.line(HEADING)
    run_id = uuid.uuid4().hex
    record_path = out or e.root / "out" / "evidence" / f"{run_id}.json"
    results: list[Result] = []
    faults: list[str] = []
    figures: dict[str, str] = {}
    build_record: dict[str, object] = {}
    proof_record: dict[str, object] = {}
    consumer_tools: dict[str, str] = {}
    sources: dict[str, str] = {}
    held: IO[str] | None = None
    try:
        held = env.hold_lock(e.lane_root / "exit-evidence", "an evidence sweep")
        sources = receipts.inputs(e.root, *model_cli.BUILD_INPUTS,
                                  "proofs", "docs/requirements-register.md")
        consumer_tools = receipts.executables("dtc")
        if build:
            print(f"model build log: {e.log('model-build')}", flush=True)
            results.append(_launch(MEMBERS[0]))
            if results[-1].exit_code:
                faults.append("build failed; no model evidence was collected")
        if not faults:
            lock = env.build_lock(e.build_dir)
            try:
                build_record = model_cli.verified_build(e)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    proof = pool.submit(_launch, MEMBERS[-1])
                    results.extend(_launch(member) for member in MEMBERS[1:-1])
                    results.append(proof.result())
                faults.extend(f"{result.name}: exited {result.exit_code}"
                              for result in results if result.exit_code)
                if model_cli.verified_build(e) != build_record:
                    faults.append("the build identity changed during the sweep")
                if not faults:
                    proof_record = _proof_record(e.root)
                    figures = _figures(results, e.log("model-build"))
            finally:
                if lock is not None:
                    lock.close()
        if receipts.inputs(e.root, *model_cli.BUILD_INPUTS,
                           "proofs", "docs/requirements-register.md") != sources:
            faults.append("the evidence inputs changed during the sweep")
        if receipts.executables("dtc") != consumer_tools:
            faults.append("the evidence consumer tools changed during the sweep")
    except (OSError, ValueError, TypeError, RuntimeError, SystemExit) as err:
        faults.append(str(err))
    finally:
        if held is not None:
            held.close()

    for result in results:
        rep.line(f"--- {result.name}: exit {result.exit_code}, {result.seconds:.1f} s ---")
        rep.out.extend((result.stdout + result.stderr).splitlines())
    if not faults:
        rep.line("=== exit evidence ===")
        rep.out.extend(f"  {label}: {value}" for label, value in figures.items())
    rep.report("evidence", "incomplete or stale evidence:", faults,
               f"all {len(results)} executed member(s) green")
    receipts.write(record_path, {
        "schema": 1, "run_id": run_id, "exit_code": 1 if faults else 0,
        "inputs": sources, "build": build_record, "proofs": proof_record,
        "consumer_tools": consumer_tools,
        "members": [asdict(result) for result in results],
        "measurements": figures if not faults else {}, "failures": faults,
    })
    rep.line(f"execution record: {record_path}")
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true",
                        help="require current build evidence without rebuilding")
    parser.add_argument("--out", type=Path, help="where to write the JSON execution record")
    args = parser.parse_args(argv)
    report = run(build=not args.no_build, out=args.out)
    print("\n".join(report.out))
    return 1 if report.findings else 0
