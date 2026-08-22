#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the tools' own behavioral tests.

`check.py` checks the documents, `check-selftest.py` checks the checker's rules by
mutation, and `typecheck.py` checks the Python's discipline. What none of them
checks is the tools' *behavior*: that a repair reaches its fixpoint, that a parse
answers what its docstring promises, that a CLI's exit code means what the
conventions say. The modules under `tests/` hold exactly that, one subject per
module, and this is their runner.

Modules run concurrently (most cases wait on subprocesses, which releases the
lock the interpreter holds); the cases inside a module run in order, and every
module accumulates onto its own slate, merged in sorted-module order, so the
report reads the same however the pool scheduled them. Discovering no modules at
all is a failure, not a green run: an empty suite decides nothing, and this tool
must say so rather than pass vacuously.

Exit 0 clean, 1 on any failure. It may be run from anywhere: modules are found
beside this file, never from the working directory.
"""

import argparse
import importlib
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# The tools import `vos` and `tests` without being installed, so each puts its own
# directory on the path first. Every import below this line is deliberately not at
# the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tests.harness import Case
from vos.report import Reporter

# The lane this process is, spelled the way Case.lane spells it.
LANE = "host" if sys.platform == "win32" else "guest"


def _module_names(only: str | None) -> list[str]:
    """Every test module beside this file, sorted so the report order is fixed."""
    here = Path(__file__).resolve().parent / "tests"
    names = sorted(path.stem for path in here.glob("test_*.py"))
    if only:
        names = [name for name in names if only in name]
    return names


def _load(name: str) -> list[Case] | str:
    """One module's cases, or the sentence saying why there are none.

    Called serially from the main thread, never from the pool: two threads
    importing overlapping dependency graphs trip Python's import-deadlock
    avoidance, which hands one of them a partially initialized module rather
    than blocking, and the failure lands in whatever stdlib module lost the
    race instead of in the test that raced.
    """
    try:
        found = importlib.import_module(f"tests.{name}").cases()
    except Exception as err:  # an unimportable module is this run's finding, not its crash
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


def _run_module(name: str, cases: list[Case] | str, slow: bool) -> Reporter:
    """One module's whole verdict, on its own slate."""
    rep = Reporter()
    if isinstance(cases, str):
        rep.report(name, "module error(s):", [cases])
        return rep

    failures: list[str] = []
    ran = 0
    for case in cases:
        if (case.slow and not slow) or case.lane not in ("any", LANE):
            continue
        ran += 1
        try:
            case.fn()
        except Exception as err:  # a case decides by raising; whatever it raised is its verdict
            failures.append(f"{case.name}: {err}")
    rep.report(name, "failure(s):", failures, ok=f"{ran} case(s)")
    return rep


def run(only: str | None = None, slow: bool = False) -> Reporter:
    """One whole run, as data, on the convention `check.py` set: the caller decides
    what to do with the verdict rather than parsing what was printed."""
    rep = Reporter()
    rep.line("=== tests ===")

    names = _module_names(only)
    if not names:
        rep.report("tests", "empty suite:",
                   ["nothing under tools/tests/ matches test_*.py"
                    + (f" and --only '{only}'" if only else "")])
    else:
        loaded = [(name, _load(name)) for name in names]
        with ThreadPoolExecutor(max_workers=min(8, len(names))) as pool:
            parts = list(pool.map(lambda entry: _run_module(entry[0], entry[1], slow), loaded))
        for part in parts:
            rep.out.extend(part.out)
            rep.findings += part.findings

    if rep.findings:
        rep.line(f"{rep.findings} finding(s).")
    else:
        rep.line("the tools behave as their tests hold them to.")
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the tools' own behavioral tests.")
    parser.add_argument("--only", metavar="SUBSTRING",
                        help="run only the modules whose name carries this")
    parser.add_argument("--slow", action="store_true",
                        help="include the cases marked slow")
    args = parser.parse_args(argv)

    report = run(only=args.only, slow=args.slow)
    print("\n".join(report.out))
    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())
