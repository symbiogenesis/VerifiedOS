#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the tools' own behavioral tests (`tools/tests/test_*.py`).

Test modules run concurrently in spawned worker processes so environment overrides,
patched modules, and redirected streams stay isolated. Cases within a module run in
order, and module reports merge in sorted module-name order. Discovering no modules or
loading a module with no cases is a failure. Under `gate --summary`, each module's case
count and elapsed seconds are written to the file named by [vos/timings.py](../timings.py).

`--shard INDEX/TOTAL` strides across sorted modules. A module with stateless,
deterministically ordered cases may declare `INDEPENDENT_CASES = True` at the left
margin; it keeps its position in the module stride so other modules do not shift, while
every shard runs its stride of that module's cases.
"""

import argparse
import importlib
import multiprocessing
import os
import re
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

LANE: Lane = "host" if sys.platform == "win32" else "guest"

TESTS = Path(__file__).resolve().parents[2] / "tests"

# Module-level declaration opting a test module into per-case sharding.
INDEPENDENT = "INDEPENDENT_CASES"
_DECLARED = re.compile(rf"(?m)^{INDEPENDENT} = True$")


class ModuleReport(Reporter):
    """Per-module report plus case count and elapsed seconds for timing summaries."""

    def __init__(self) -> None:
        super().__init__()
        self.cases = 0
        self.seconds = 0.0


def _lanes() -> frozenset[Lane]:
    """Return the `Case.lane` values admissible in this process.

    `"toolchain"` is admitted on Linux only when the Sail opam switch is provisioned.
    """
    lanes: set[Lane] = {"any", LANE}
    if LANE == "guest" and env.SAIL_SWITCH in switches():
        lanes.add("toolchain")
    return frozenset(lanes)


def _module_names(only: str | None) -> list[str]:
    """Return sorted `test_*.py` module stems under `tools/tests/`."""
    if only is not None and not only.strip():
        raise ValueError("--only requires a nonempty module-name substring")
    names = sorted(path.stem for path in TESTS.glob("test_*.py"))
    if only is not None:
        names = [name for name in names if only in name]
    return names


def _declares(name: str) -> bool:
    """Return whether `name.py` declares `INDEPENDENT_CASES = True` at the left margin."""
    try:
        return _DECLARED.search((TESTS / f"{name}.py").read_text(encoding="utf-8")) is not None
    except OSError, UnicodeDecodeError:
        return False


def _load(name: str, split: bool | None = None) -> list[Case] | str:
    """Import `tests.<name>` in the worker and return its `cases()` list or an error string."""
    try:
        module = importlib.import_module(f"tests.{name}")
        found: object = module.cases()
    except (Exception, SystemExit) as err:  # importing a test must not exit the runner
        return f"failed to load: {err!r}"
    declared = getattr(module, INDEPENDENT, False) is True
    if split is not None and declared != split:
        return (f"sets {INDEPENDENT} in a form a sharded run does not read; state it as "
                f"'{INDEPENDENT} = True' at the left margin" if declared else
                f"its source reads '{INDEPENDENT} = True', but the module does not set it")
    if not isinstance(found, list):
        return f"cases() returned {type(found).__name__}, not a list"
    if not found:
        return "cases() returned an empty list"
    narrowed: list[Case] = []
    for item in found:
        if not isinstance(item, Case):
            return f"cases() returned a member that is not a Case: {item!r}"
        narrowed.append(item)
    return narrowed


def _run_cases(name: str, cases: list[Case] | str, slow: bool,
               lanes: frozenset[Lane], share: Shard | None = None) -> ModuleReport:
    """Run all selected cases in `name` (or `share`'s slice) and return its `ModuleReport`."""
    rep = ModuleReport()
    if isinstance(cases, str):
        rep.report(name, "module error(s):", [cases])
        return rep

    listed = len(cases)
    failures: list[str] = []
    for case in cases if share is None else share.share(cases):
        if (case.slow and not slow) or case.lane not in lanes:
            continue
        rep.cases += 1
        try:
            case.fn()
        except (Exception, SystemExit) as err:  # an unexpected exit is a failed case
            failures.append(f"{case.name}: {err}")
    rep.report(name, "failure(s):", failures,
               ok=f"{rep.cases} case(s)"
               + ("" if share is None else f", this shard's share of {listed}"))
    return rep


def _run_module(name: str, slow: bool, lanes: frozenset[Lane], shard: Shard | None = None,
                splits: frozenset[str] = frozenset()) -> ModuleReport:
    """Load and run one test module, retaining captured stdout/stderr on failure."""
    split = name in splits
    started = time.perf_counter()
    output = StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        report = _run_cases(name, _load(name, None if shard is None else split), slow, lanes,
                            shard if split else None)
    if report.findings:
        report.out.extend(output.getvalue().splitlines())
    report.seconds = time.perf_counter() - started
    return report


def run(only: str | None = None, slow: bool = False, jobs: int | None = None,
        shard: Shard | None = None, record: Path | None = None) -> Reporter:
    """Run the selected test modules and return the aggregate `Reporter`."""
    if jobs is not None and jobs < 1:
        raise ValueError("jobs must be positive")
    if only is not None and shard is not None:
        raise ValueError("--only cannot be combined with --shard")
    rep = Reporter()
    rep.line("=== tests ===")

    names = _module_names(only)
    splits = frozenset[str]()
    if shard is not None:
        total = len(names)
        try:
            selected = shard.select(names)
        except ValueError as err:
            rep.report("tests", "invalid partition:", [str(err)])
            return rep
        splits = frozenset(name for name in names if _declares(name))
        whole = [name for name in selected if name not in splits]
        rep.line(f"shard {shard}: {len(whole)} of {total - len(splits)} modules"
                 + (f", and its share of the cases of {len(splits)} more" if splits else "")
                 + "; every shard must pass")
        names = [name for name in names if name in splits or name in whole]
    units: list[timings.Unit] = []
    if not names:
        rep.report("tests", "empty suite:",
                   ["nothing under tools/tests/ matches test_*.py"
                    + (f" and --only '{only}'" if bool(only) else "")])
    else:
        lanes = _lanes()
        workers = min(jobs or min(8, os.process_cpu_count() or 1), len(names))
        with ProcessPoolExecutor(max_workers=workers,
                                 mp_context=multiprocessing.get_context("spawn")) as pool:
            parts = pool.map(partial(_run_module, slow=slow, lanes=lanes, shard=shard,
                                     splits=splits), names)
            for name, part in zip(names, parts, strict=True):
                rep.out.extend(part.out)
                rep.findings += part.findings
                units.append({"kind": "module", "name": name, "cases": part.cases,
                              "share": str(shard) if name in splits else None,
                              "seconds": round(part.seconds, 3)})
    timings.write(record, units)

    if rep.findings:
        rep.line(f"{rep.findings} finding(s).")
    else:
        rep.line("the tools behave as their tests hold them to.")
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description="Run the tools' own behavioral tests.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--only", metavar="SUBSTRING",
                        help="run only the modules whose name carries this")
    selection.add_argument("--shard", type=sharding.parse, metavar="INDEX/TOTAL",
                           help="run a disjoint partition of the discovered modules, and "
                                "this shard's share of the cases of each module declaring "
                                "INDEPENDENT_CASES = True")
    parser.add_argument("--slow", action="store_true",
                        help="include the cases marked slow")
    parser.add_argument("--jobs", type=int,
                        help="worker processes (default: available CPUs, capped at eight)")
    args = parser.parse_args(argv)
    if args.jobs is not None and args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.only is not None and not args.only.strip():
        parser.error("--only requires a nonempty module-name substring")

    report = run(only=args.only, slow=args.slow, jobs=args.jobs, shard=args.shard,
                 record=timings.claim())
    print("\n".join(report.out))
    return 1 if report.findings else 0
