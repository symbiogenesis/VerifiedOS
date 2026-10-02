#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the tools' own behavioral tests.

`check` checks the documents, `selftest` checks the checker's rules by mutation, and
`typecheck` checks the Python's discipline. What none of them checks is the tools'
*behavior*: that a repair reaches its fixpoint, that a parse answers what its
docstring promises, that a CLI's exit code means what the conventions say. The
modules under `tools/tests/` hold exactly that, one subject per module, and this is
their runner.

Concurrent modules run in separate processes so environment overrides, patched
modules and redirected streams cannot interfere with each other. Workers may be
reused for later modules; tests still restore their temporary state. Cases inside
a module run in order, and reports merge in sorted-module order regardless of
scheduling. Discovering no modules is a failure: an empty suite decides nothing.
Under the gate's `--summary`, each module's case count and seconds go to the file
[vos/timings.py](../timings.py) names, never into the printed report.

Exit 0 clean, 1 on any failure. It may be run from anywhere: the modules are found
from this file's own location, never from the working directory.
"""

import argparse
import importlib
import multiprocessing
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from functools import partial
from io import StringIO
from pathlib import Path

from tests.harness import Case, Lane
from vos import env, sharding, timings
from vos.cli.provision import switches
from vos.report import Reporter
from vos.sharding import Shard

# The lane this process is, spelled the way Case.lane spells it.
LANE: Lane = "host" if sys.platform == "win32" else "guest"


class ModuleReport(Reporter):
    """One module's report, with what the gate's summary records beside it: how many
    cases ran, and the seconds loading and running them took. Neither is printed."""

    def __init__(self) -> None:
        super().__init__()
        self.cases = 0
        self.seconds = 0.0


def _lanes() -> frozenset[Lane]:
    """The lane values a case may carry and still run in this process.

    Platform alone decides "host" against "guest", and it is not enough to decide
    whether the guest is the lane the toolchain stands in: the CI runner is Linux and
    has never been provisioned, so a case that drives the toolchain would run there and
    fail on a precondition about the machine rather than about the tools. "toolchain"
    is therefore admitted only where the Sail switch is one opam answers for, which is
    the provisioner's own probe rather than a second reading of the same fact.
    """
    lanes: set[Lane] = {"any", LANE}
    if LANE == "guest" and env.SAIL_SWITCH in switches():
        lanes.add("toolchain")
    return frozenset(lanes)


def _module_names(only: str | None) -> list[str]:
    """Every test module under `tools/tests/`, sorted so the report order is fixed."""
    here = Path(__file__).resolve().parents[2] / "tests"
    names = sorted(path.stem for path in here.glob("test_*.py"))
    if only:
        names = [name for name in names if only in name]
    return names


def _load(name: str) -> list[Case] | str:
    """One module's cases, or the sentence saying why there are none.

    Imported inside the worker, so cases may carry closures without having to be
    pickled. Imports and module patches remain private to that worker.
    """
    try:
        found: object = importlib.import_module(f"tests.{name}").cases()
    except (Exception, SystemExit) as err:  # importing a test must not exit the runner
        return f"failed to load: {err!r}"
    # Narrowed rather than trusted: cases() crosses a dynamic import, so its shape is
    # this runner's to check, and a module returning the wrong thing is a finding.
    if not isinstance(found, list):
        return f"cases() returned {type(found).__name__}, not a list"
    narrowed: list[Case] = []
    for item in found:
        if not isinstance(item, Case):
            return f"cases() returned a member that is not a Case: {item!r}"
        narrowed.append(item)
    return narrowed


def _run_cases(name: str, cases: list[Case] | str, slow: bool,
               lanes: frozenset[Lane]) -> ModuleReport:
    """One module's whole verdict, on its own slate."""
    rep = ModuleReport()
    if isinstance(cases, str):
        rep.report(name, "module error(s):", [cases])
        return rep

    failures: list[str] = []
    for case in cases:
        if (case.slow and not slow) or case.lane not in lanes:
            continue
        rep.cases += 1
        try:
            case.fn()
        except (Exception, SystemExit) as err:  # an unexpected exit is a failed case
            failures.append(f"{case.name}: {err}")
    rep.report(name, "failure(s):", failures, ok=f"{rep.cases} case(s)")
    return rep


def _run_module(name: str, slow: bool, lanes: frozenset[Lane]) -> ModuleReport:
    """Load and run one module, retaining its captured output on failure."""
    started = time.perf_counter()
    output = StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        report = _run_cases(name, _load(name), slow, lanes)
    if report.findings:
        report.out.extend(output.getvalue().splitlines())
    report.seconds = time.perf_counter() - started
    return report


def run(only: str | None = None, slow: bool = False, jobs: int | None = None,
        shard: Shard | None = None, record: Path | None = None) -> Reporter:
    """One whole run, as data, on the convention `check.py` set: the caller decides
    what to do with the verdict rather than parsing what was printed. `record` names
    the file that receives each module's case count and seconds."""
    if jobs is not None and jobs < 1:
        raise ValueError("jobs must be positive")
    if only is not None and shard is not None:
        raise ValueError("--only cannot be combined with --shard")
    rep = Reporter()
    rep.line("=== tests ===")

    names = _module_names(only)
    if shard is not None:
        total = len(names)
        try:
            names = shard.select(names)
        except ValueError as err:
            rep.report("tests", "invalid partition:", [str(err)])
            return rep
        rep.line(f"shard {shard}: {len(names)} of {total} modules; every shard must pass")
    units: list[timings.Unit] = []
    if not names:
        rep.report("tests", "empty suite:",
                   ["nothing under tools/tests/ matches test_*.py"
                    + (f" and --only '{only}'" if only else "")])
    else:
        # decided once, ahead of the pool: the probe is a subprocess, and every module
        # would otherwise pay for it and could in principle be answered differently
        lanes = _lanes()
        workers = min(jobs or min(8, os.process_cpu_count() or 1), len(names))
        # Spawn on both platforms: forking a caller's live threads or patches would
        # retain exactly the shared state the workers are meant to isolate.
        with ProcessPoolExecutor(max_workers=workers,
                                 mp_context=multiprocessing.get_context("spawn")) as pool:
            parts = pool.map(partial(_run_module, slow=slow, lanes=lanes), names)
            for name, part in zip(names, parts, strict=True):
                rep.out.extend(part.out)
                rep.findings += part.findings
                units.append({"kind": "module", "name": name, "cases": part.cases,
                              "seconds": round(part.seconds, 3)})
    timings.write(record, units)

    if rep.findings:
        rep.line(f"{rep.findings} finding(s).")
    else:
        rep.line("the tools behave as their tests hold them to.")
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the tools' own behavioral tests.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--only", metavar="SUBSTRING",
                        help="run only the modules whose name carries this")
    selection.add_argument("--shard", type=sharding.parse, metavar="INDEX/TOTAL",
                           help="run a disjoint partition of the discovered modules")
    parser.add_argument("--slow", action="store_true",
                        help="include the cases marked slow")
    parser.add_argument("--jobs", type=int,
                        help="worker processes (default: available CPUs, capped at eight)")
    args = parser.parse_args(argv)
    if args.jobs is not None and args.jobs < 1:
        parser.error("--jobs must be positive")

    report = run(only=args.only, slow=args.slow, jobs=args.jobs, shard=args.shard,
                 record=timings.claim())
    print("\n".join(report.out))
    return 1 if report.findings else 0
