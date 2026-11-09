#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the tools' own behavioral tests (`tools/tests/test_*.py`).

Test modules run concurrently in spawned worker processes so environment overrides,
patched modules, and redirected streams stay isolated. Cases within a module run in
order, and module reports merge in sorted module-name order. Discovering no modules or
loading a module with no cases is a failure. Under `gate --summary`, each module's case
count and elapsed seconds are written to the file named by [vos/timings.py](../timings.py).
While work is running, that file checkpoints queued/running modules and completed
failures without waiting for earlier modules. Final reports remain in module order.

`--shard INDEX/TOTAL` strides across sorted modules. A module with stateless,
deterministically ordered cases may declare `INDEPENDENT_CASES = True` at the left
margin; it keeps its position in the module stride so other modules do not shift, while
every shard runs its stride of that module's cases.

`--native-controls` selects only slow toolchain cases and requires the provisioned
guest Sail toolchain. Ordinary cases and host-only slow gate recursion are excluded.
"""

import argparse
import importlib
import multiprocessing
import os
import re
import sys
import threading
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout, suppress
from functools import partial
from io import StringIO
from pathlib import Path
from queue import Empty
from typing import TYPE_CHECKING

from tests.harness import Case, Lane
from vos import env, sharding, timings
from vos.cli.provision import switches
from vos.report import Reporter
from vos.sharding import Shard

if TYPE_CHECKING:
    from multiprocessing.context import BaseContext
    from multiprocessing.queues import Queue
    from typing import ClassVar

LANE: Lane = "host" if sys.platform == "win32" else "guest"

TESTS = Path(__file__).resolve().parents[2] / "tests"

# Module-level declaration opting a test module into per-case sharding.
INDEPENDENT = "INDEPENDENT_CASES"
_DECLARED = re.compile(rf"(?m)^{INDEPENDENT} = True$")

class _WorkerProgress:
    """The diagnostic channel installed once in each spawned worker process."""

    queue: ClassVar[Queue[tuple[str, float, float]] | None] = None


def _progress_init(queue: Queue[tuple[str, float, float]] | None) -> None:
    """Give each spawned worker its parent's diagnostic-only start channel."""
    _WorkerProgress.queue = queue


class Progress:
    """Checkpoint actual module starts and completions without ordering verdicts."""

    def __init__(self, context: BaseContext, path: Path, names: list[str]) -> None:
        self.queue: Queue[tuple[str, float, float]] = context.Queue()
        self.path = path
        self.names = names
        self.running: dict[str, tuple[float, float]] = {}
        self.completed: dict[str, timings.Unit] = {}
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self._checkpoint()
        self.thread.start()

    def _watch(self) -> None:
        while not self.stopped.is_set():
            try:
                name, started, at = self.queue.get(timeout=0.1)
            except Empty:
                continue
            except (EOFError, OSError):
                return
            with self.lock:
                if name not in self.completed:
                    self.running[name] = (started, at)
                    self._checkpoint()

    def complete(self, name: str, unit: timings.Unit) -> None:
        with self.lock:
            self.completed[name] = unit
            self.running.pop(name, None)
            self._checkpoint()

    def _checkpoint(self) -> None:
        now = time.perf_counter()
        units: list[timings.Unit] = []
        for name in self.names:
            if name in self.completed:
                units.append(self.completed[name])
            elif name in self.running:
                started, at = self.running[name]
                units.append({"kind": "module", "name": name, "status": "running",
                              "seconds": round(now - started, 3), "at": at})
            else:
                units.append({"kind": "module", "name": name, "status": "queued",
                              "seconds": 0.0})
        timings.write(self.path, units)

    def close(self) -> None:
        self.stopped.set()
        self.thread.join()
        self.queue.close()
        self.queue.join_thread()


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
        return f"failed to load: {err!r}\n{traceback.format_exc().rstrip()}"
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
               lanes: frozenset[Lane], share: Shard | None = None, *,
               native_controls: bool = False) -> ModuleReport:
    """Run all selected cases in `name` (or `share`'s slice) and return its `ModuleReport`."""
    rep = ModuleReport()
    if isinstance(cases, str):
        rep.report(name, "module error(s):", cases.splitlines(), count=1)
        return rep

    if native_controls:
        cases = [case for case in cases if case.slow and case.lane == "toolchain"]
        if not cases:
            return rep
        slow = True

    listed = len(cases)
    failures: list[str] = []
    skipped: dict[str, int] = {}
    for case in cases if share is None else share.share(cases):
        reasons: list[str] = []
        if case.slow and not slow:
            reasons.append("slow (requires --slow)")
        if case.lane not in lanes:
            reasons.append(f"lane '{case.lane}' unavailable")
        if reasons:
            reason = " and ".join(reasons)
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        rep.cases += 1
        try:
            case.fn()
        except (Exception, SystemExit) as err:  # an unexpected exit is a failed case
            failures.append(f"{case.name}: {err}\n{traceback.format_exc().rstrip()}")
    rep.report(name, "failure(s):",
               (line for failure in failures for line in failure.splitlines()),
               ok=(f"{rep.cases} case(s)" if rep.cases else "no cases selected (0 executed)")
               + ("" if share is None else f", this shard's share of {listed}"),
               count=len(failures))
    if skipped:
        summary = "; ".join(f"{count} {reason}" for reason, count in sorted(skipped.items()))
        rep.line(f"skipped {name}: {sum(skipped.values())} case(s) ({summary})")
    return rep


def _run_module(name: str, slow: bool, lanes: frozenset[Lane], shard: Shard | None = None,
                splits: frozenset[str] = frozenset(), *,
                native_controls: bool = False) -> ModuleReport:
    """Load and run one test module, retaining captured stdout/stderr on failure."""
    split = name in splits
    started = time.perf_counter()
    if (queue := _WorkerProgress.queue) is not None:
        with suppress(OSError, ValueError):
            queue.put((name, started, time.time()))
    output = StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        report = _run_cases(name, _load(name, None if shard is None else split), slow, lanes,
                            shard if split else None, native_controls=native_controls)
    if report.findings:
        report.out.extend(output.getvalue().splitlines())
    report.seconds = time.perf_counter() - started
    return report


def run(only: str | None = None, slow: bool = False, jobs: int | None = None,
        shard: Shard | None = None, record: Path | None = None, *,
        native_controls: bool = False) -> Reporter:
    """Run the selected test modules and return the aggregate `Reporter`."""
    if jobs is not None and jobs < 1:
        raise ValueError("jobs must be positive")
    if only is not None and shard is not None:
        raise ValueError("--only cannot be combined with --shard")
    if native_controls and (only is not None or shard is not None):
        raise ValueError("--native-controls cannot be combined with --only or --shard")
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
            timings.write(record, [])
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
        if native_controls and "toolchain" not in lanes:
            rep.report("tests", "native controls unavailable:",
                       ["--native-controls requires the provisioned Sail toolchain in the guest"])
            timings.write(record, [])
            return rep
        workers = min(jobs or min(8, os.process_cpu_count() or 1), len(names))
        context = multiprocessing.get_context("spawn")
        progress = Progress(context, record, names) if record is not None else None
        reports: dict[str, ModuleReport] = {}
        try:
            with ProcessPoolExecutor(max_workers=workers, mp_context=context,
                                     initializer=_progress_init,
                                     initargs=(progress.queue if progress else None,)) as pool:
                task = partial(_run_module, slow=slow, lanes=lanes, shard=shard,
                               splits=splits, native_controls=native_controls)
                pending = {pool.submit(task, name): name for name in names}
                for future in as_completed(pending):
                    name = pending[future]
                    part = future.result()
                    reports[name] = part
                    unit: timings.Unit = {"kind": "module", "name": name, "cases": part.cases,
                                          "share": str(shard) if name in splits else None,
                                          "seconds": round(part.seconds, 3)}
                    if progress is not None:
                        progress.complete(name, {**unit, "findings": part.findings,
                                                 **({"output": part.out} if part.findings else {})})
            for name in names:
                part = reports[name]
                rep.out.extend(part.out)
                rep.findings += part.findings
                units.append({"kind": "module", "name": name, "cases": part.cases,
                              "share": str(shard) if name in splits else None,
                              "seconds": round(part.seconds, 3)})
            if native_controls and not sum(part.cases for part in reports.values()):
                rep.report("tests", "empty native-control suite:",
                           ["no slow toolchain cases were selected"])
        finally:
            if progress is not None:
                progress.close()
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
    selection.add_argument("--native-controls", action="store_true",
                           help="run only slow toolchain controls; require the guest Sail toolchain")
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
                 record=timings.claim(), native_controls=args.native_controls)
    print("\n".join(report.out))
    return 1 if report.findings else 0
