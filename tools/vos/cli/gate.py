# SPDX-License-Identifier: Apache-2.0
"""Validate the checkout with one host-gate verdict.

The default (`--check`) runs the checker, selftest, typecheck, and Markdown linter
read-only in separate processes. `--fix` runs `check --fix` first, then runs a fresh
read-only wave across all host gates. If the repair pass crashes without reaching a
verdict, execution stops before the validation wave.

Independent gates run concurrently and report in declaration order. `--tests` adds the
behavioral test suite (`test`). Exit 0 means every final gate passed, 1 otherwise.

`--shard INDEX/TOTAL` runs one partition of `selftest` and (with `--tests`) `test`.
`--unpartitioned` runs `check`, `typecheck`, `markdown`, and `selftest --repair-only`.

`--summary PATH` writes the per-member verdict and [vos/timings.py](../timings.py) unit
measurements to `PATH` as JSON.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from vos import corpus as corpus_mod
from vos import process_tree, sharding, timings
from vos.report import Reporter
from vos.sharding import Shard

HEADING = "=== gate: every host gate over this tree, in one run ==="

# Per-member timeout in seconds (must stay inside the hosted job timeout).
TIMEOUT = 1200

# Sentinel exit code for a member that timed out or could not be launched.
NO_VERDICT = -1


@dataclass(frozen=True)
class Launch:
    """A host-gate member command, its arguments, and what it decides."""

    tool: str
    args: tuple[str, ...]
    decides: str

    @property
    def name(self) -> str:
        """Command string displayed in reports."""
        return " ".join((self.tool, *self.args))


@dataclass
class Result:
    """Output, exit code, elapsed time, and timing units for a single gate member."""

    launch: Launch
    code: int
    out: list[str]
    elapsed_seconds: float = 0.0
    units: list[timings.Unit] | None = None


MEMBERS: tuple[Launch, ...] = (
    Launch("check", (), "every derived fact against the artifact that owns it"),
    Launch("selftest", (), "every rule the checker carries, against its mutant"),
    Launch("typecheck", (), "the tools' own Python, under two pinned checkers"),
    Launch("markdown", (), "standard table syntax, once outside semantic mutation replay"),
)

TESTS = Launch("test", (), "the tools' own behavior, against the cases that hold it")
REPAIRS = "check"

PARTITIONED = ("selftest", "test")
REPAIR_PATH = Launch("selftest", ("--repair-only",),
                     "every --fix branch the checker carries, against its seeded figure")


def _plan(fix: bool, tests: bool, shard: Shard | None = None,
          unpartitioned: bool = False) -> list[list[Launch]]:
    """Build the execution waves: an optional repair wave followed by the read-only wave."""
    members = [*MEMBERS, *([TESTS] if tests else [])]
    if fix and (shard is not None or unpartitioned):
        raise ValueError("--fix cannot be combined with --shard or --unpartitioned")
    if shard is not None and unpartitioned:
        raise ValueError("--shard cannot be combined with --unpartitioned")
    if shard is not None:
        members = [Launch(m.tool, (*m.args, "--shard", str(shard)), m.decides)
                   for m in members if m.tool in PARTITIONED]
    elif unpartitioned:
        members = [REPAIR_PATH if m.tool == REPAIR_PATH.tool else m
                   for m in members if m.tool != TESTS.tool]
    if not fix:
        return [members]
    repair = [Launch(m.tool, (*m.args, "--fix"), m.decides)
              for m in members if m.tool == REPAIRS]
    return [repair, members]


def _launch(root: Path, member: Launch, record: Path | None = None) -> Result:
    """Run `member` in a subprocess and capture its output, exit code, and timing units.

    Timeouts and launch failures return `NO_VERDICT` rather than raising a traceback.
    """
    argv = [sys.executable, str(root / "tools" / "run.py"), member.tool, *member.args]
    environment = {key: value for key, value in os.environ.items() if key != timings.ENV}
    environment["PYTHONUNBUFFERED"] = "1"
    if record is not None:
        environment[timings.ENV] = str(record)
    started = time.perf_counter()
    try:
        done = process_tree.run(argv, cwd=root, timeout=TIMEOUT, env=environment)
    except subprocess.TimeoutExpired as err:
        units = timings.read(record) if record is not None else None
        output = (_partial_text(err.stdout) + _partial_text(err.stderr)).splitlines()
        output.append(f"{member.name} gave no verdict within {TIMEOUT}s")
        for unit in units or []:
            if unit.get("status") == "running":
                output.append(f"running at last timing snapshot: {unit.get('kind')} "
                              f"{unit.get('name')}")
        return Result(member, NO_VERDICT,
                      output, time.perf_counter() - started, units)
    except OSError as err:
        return Result(member, NO_VERDICT, [f"{member.name} could not be run: {err}"],
                      time.perf_counter() - started)
    return Result(member, done.returncode, (done.stdout + done.stderr).splitlines(),
                  time.perf_counter() - started,
                  timings.read(record) if record is not None else None)


def _partial_text(value: str | bytes | None) -> str:
    """Decode `TimeoutExpired` stdout/stderr, which may be raw bytes even in text mode."""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""


def _show(rep: Reporter, result: Result) -> None:
    """Append a member's diagnostic output to `rep`."""
    rep.line(f"--- {result.launch.name}: {result.launch.decides} ---")
    rep.line(f"elapsed: {result.elapsed_seconds:.2f}s")
    rep.out.extend(result.out)
    rep.line()


def _verdict(rep: Reporter, results: list[Result]) -> None:
    """Append each member's report followed by the aggregate gate verdict."""
    for result in results:
        _show(rep, result)

    rep.report("gate", "gate(s) that did not come back clean:",
               [f"{r.launch.name}: reported, above"
                if r.code == 1 else
                f"{r.launch.name}: exited {r.code} without reaching a verdict"
                for r in results if r.code != 0],
               f"all {len(results)} host gate(s) green")


def _verdict_data(results: list[Result], stopped: str = "") -> dict[str, object]:
    """Serialize the wave's results for `--summary`."""
    return {
        "green": bool(results) and all(r.code == 0 for r in results),
        "stopped": stopped,
        "members": [{"name": r.launch.name,
                     "decides": r.launch.decides,
                     "code": r.code,
                     "elapsed_seconds": r.elapsed_seconds,
                     "reached_verdict": r.code in (0, 1),
                     "clean": r.code == 0,
                     "units": r.units}
                    for r in results],
    }


def _write_summary(rep: Reporter, path: Path, data: dict[str, object]) -> None:
    """Write `data` as JSON to `path`, reporting any I/O failure on `rep`."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError as err:
        rep.report("summary", "per-member verdict:", [f"{path} could not be written: {err}"])
        return
    rep.report("summary", "per-member verdict:", [], ok=f"written to {path}")


def run(root: Path, fix: bool = False, tests: bool = False, check: bool = False,
        summary: Path | None = None, shard: Shard | None = None,
        unpartitioned: bool = False) -> Reporter:
    """Run the optional repair wave, then execute and report the final validation wave."""
    if fix and check:
        raise ValueError("--fix and --check are mutually exclusive")
    rep = Reporter()
    if shard is not None:
        rep.line(f"=== gate: shard {shard}; every shard and the unpartitioned run must pass ===")
    elif unpartitioned:
        rep.line("=== gate: the unpartitioned members; every shard must pass too ===")
    else:
        rep.line(HEADING)

    plan = _plan(fix, tests, shard, unpartitioned)
    if fix:
        repair = _launch(root, plan[0][0])
        _show(rep, repair)
        if repair.code not in (0, 1):
            stopped = (f"repair did not complete: {repair.launch.name} exited "
                       f"{repair.code} without reaching a verdict")
            rep.report("gate", "repair did not complete:",
                       [f"{repair.launch.name}: exited {repair.code} without reaching a verdict"])
            if summary is not None:
                _write_summary(rep, summary, _verdict_data([], stopped))
            return rep
        rep.line("repair pass complete; the fresh validation below decides the repaired tree")

    wave = plan[-1]
    with ExitStack() as stack:
        scratch = None if summary is None else Path(stack.enter_context(
            tempfile.TemporaryDirectory(prefix="vos-gate-", ignore_cleanup_errors=True)))
        records = [None if scratch is None else scratch / f"{n}.json"
                   for n in range(len(wave))]
        with ThreadPoolExecutor(max_workers=len(wave)) as pool:
            results = list(pool.map(lambda member, record: _launch(root, member, record),
                                    wave, records))
    if summary is not None:
        data = _verdict_data(results)
        if shard is not None:
            data["shard"] = {"index": shard.index, "total": shard.total}
        if unpartitioned:
            data["unpartitioned"] = True
        _write_summary(rep, summary, data)
    _verdict(rep, results)
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        suggest_on_error=True, prog="run.py gate",
        description="Run the host's gates together and answer with one verdict.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fix", action="store_true",
                      help="repair derived facts, then validate")
    mode.add_argument("--check", action="store_true",
                      help="validate without repairing files")
    parser.add_argument("--tests", action="store_true",
                        help="add the tools' own behavioral tests to the wave")
    parser.add_argument("--summary", metavar="PATH", type=Path,
                        help="also write the per-member verdict there as JSON, for a "
                             "caller that has only this run's exit code")
    part = parser.add_mutually_exclusive_group()
    part.add_argument("--shard", type=sharding.parse, metavar="INDEX/TOTAL",
                      help="run this partition of the selftest's cases and, with --tests, "
                           "of the tests, and nothing else")
    part.add_argument("--unpartitioned", action="store_true",
                      help="run what no shard holds: check, typecheck and the selftest's "
                           "repair path; every shard and this run, with the same --tests, "
                           "make a complete verdict")
    args = parser.parse_args(argv)
    if args.fix and (args.shard is not None or args.unpartitioned):
        parser.error("--fix cannot be combined with --shard or --unpartitioned")

    plan = _plan(args.fix, args.tests, args.shard, args.unpartitioned)
    # The member reports remain accumulated in declaration order; this preflight
    # states what is running while the wave has not yet returned.
    preflight = "repairing derived facts; " if args.fix else ""
    print(preflight + f"running {len(plan[-1])} host gate(s): "
          + ", ".join(m.name for m in plan[-1]), flush=True)

    report = run(corpus_mod.find_root(), fix=args.fix, tests=args.tests, check=args.check,
                 summary=args.summary, shard=args.shard, unpartitioned=args.unpartitioned)
    print("\n".join(report.out))
    return 1 if report.findings else 0
