# SPDX-License-Identifier: Apache-2.0
"""Behavioral runner isolation, selection and failure reporting."""

import tempfile
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests import test_sharding
from tests.harness import Case, Lane, ensure
from vos import timings
from vos.cli import test as runner
from vos.sharding import Shard


def _selection_and_failures() -> None:
    visited: list[str] = []

    def fail() -> None:
        raise ValueError("seeded failure")

    def leave() -> None:
        raise SystemExit(3)

    cases = [
        Case("ordinary", lambda: visited.append("ordinary")),
        Case("slow", lambda: visited.append("slow"), slow=True),
        Case("guest", lambda: visited.append("guest"), lane="guest"),
        Case("failure", fail),
        Case("exit", leave),
        Case("after", lambda: visited.append("after")),
    ]
    report = runner._run_cases("sample", cases, False, frozenset({"any", "host"}))
    ensure(visited == ["ordinary", "after"], f"selection or continuation failed: {visited}")
    ensure(report.findings == 2, f"both failing cases need verdicts: {report.out}")
    ensure("failure: seeded failure" in "\n".join(report.out), "failure lost its diagnostic")
    report = runner._run_cases("sample", cases[:3], True, frozenset({"any", "guest"}))
    ensure(visited[-3:] == ["ordinary", "slow", "guest"], "slow and lane selection failed")
    ensure(report.findings == 0, "selected passing cases must pass")


def _load_errors() -> None:
    for value in (None, [None]):
        with patch.object(runner.importlib, "import_module",
                          return_value=SimpleNamespace(cases=lambda value=value: value)):
            ensure(isinstance(runner._load("sample"), str), "invalid cases must fail loading")
    with patch.object(runner.importlib, "import_module", side_effect=SystemExit(2)):
        ensure("SystemExit" in str(runner._load("sample")), "an import must not exit the suite")


def _captured_output() -> None:
    def noisy() -> None:
        print("module diagnostic")

    with patch.object(runner, "_load", return_value=[Case("noisy", noisy)]):
        report = runner._run_module("sample", False, frozenset({"any"}))
    ensure(report.out == ["ok sample: 1 case(s)"], "passing diagnostics should be quiet")

    def failure() -> None:
        noisy()
        raise ValueError("expected")

    with patch.object(runner, "_load", return_value=[Case("failure", failure)]):
        report = runner._run_module("sample", False, frozenset({"any"}))
    ensure(report.findings == 1 and report.out[-1] == "module diagnostic",
           f"failure output must travel with its module's verdict: {report.out}")


def _spawn_isolation() -> None:
    # A real spawn must import clean modules. Threads and forked workers inherit
    # this broken assertion helper and make otherwise passing modules fail.
    with patch.object(runner, "_module_names", return_value=["test_harness", "test_report"]), \
            patch("tests.harness.ensure", side_effect=AssertionError("patch leaked")):
        report = runner.run(jobs=2)
    ensure(report.findings == 0, f"test modules inherited a caller's patches: {report.out}")
    verdicts = [line for line in report.out if line.startswith("ok test_")]
    ensure(len(verdicts) == 2 and verdicts == sorted(verdicts),
           f"module reports must retain discovery order: {verdicts}")


def _empty_and_invalid() -> None:
    with patch.object(runner, "_module_names", return_value=[]):
        ensure(runner.run().findings == 1, "empty discovery must not pass")
    for jobs in (0, -1):
        try:
            runner.run(jobs=jobs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid worker count must be refused")
        with redirect_stderr(StringIO()):
            try:
                runner.main(["--jobs", str(jobs)])
            except SystemExit as err:
                ensure(err.code == 2, "invalid --jobs needs a usage error")
            else:
                raise AssertionError("invalid --jobs must be refused")


def _shards_execute_the_selected_modules() -> None:
    names = ["test_harness", "test_report"]
    for index, expected in enumerate(names, 1):
        with patch.object(runner, "_module_names", return_value=names):
            report = runner.run(jobs=1, shard=Shard(index, 2))
        ensure(report.findings == 0, f"a real sharded worker failed: {report.out}")
        verdicts = [line.split(":", 1)[0] for line in report.out if line.startswith("ok test_")]
        ensure(verdicts == [f"ok {expected}"], "a shard executed the wrong modules")
    with patch.object(runner, "_module_names", return_value=names):
        ensure(runner.run(shard=Shard(1, 3)).findings == 1,
               "an empty shard population must not pass")
    try:
        runner.run(only="harness", shard=Shard(1, 2))
    except ValueError:
        pass
    else:
        raise AssertionError("a filter must not silently narrow CI shards")


def _recording(ran: list[int], position: int) -> Callable[[], None]:
    return lambda: ran.append(position)


def _declared_module(ran: list[int], declared: object = True) -> SimpleNamespace:
    """Six cases, the third guest-only and the fifth slow, so a host run without --slow
    selects positions 0, 1, 3 and 5."""
    return SimpleNamespace(INDEPENDENT_CASES=declared, cases=lambda: [
        Case(f"c{j}", _recording(ran, j), slow=j == 4, lane="guest" if j == 2 else "any")
        for j in range(6)])


def _declared_modules_share_their_cases() -> None:
    lanes: frozenset[Lane] = frozenset({"any", "host"})
    for total in (1, 3, 8):
        ran: list[int] = []
        for index in range(1, total + 1):
            before = len(ran)
            with patch.object(runner.importlib, "import_module",
                              return_value=_declared_module(ran)):
                report = runner._run_module("sample", False, lanes, Shard(index, total),
                                            frozenset({"sample"}))
            share = [j for j in (0, 1, 3, 5) if j % total == index - 1]
            ensure(ran[before:] == share and report.cases == len(share) and report.out
                   == [f"ok sample: {len(share)} case(s), this shard's share of 6"],
                   f"shard {index}/{total} ran {ran[before:]}, not its share {share}, or "
                   f"reported it otherwise: {report.out}")
        ensure(sorted(ran) == [0, 1, 3, 5],
               f"across {total} shards every selected case runs exactly once: {ran}")
    # Unsharded, a declared module runs whole and reads nothing.
    ran = []
    with patch.object(runner.importlib, "import_module", return_value=_declared_module(ran)):
        report = runner._run_module("sample", False, lanes)
    ensure(ran == [0, 1, 3, 5] and report.out == ["ok sample: 4 case(s)"],
           f"an unsharded run must be unchanged: {ran}, {report.out}")
    # A declaration the source reading missed, or one it read that the module does not
    # make, is a module error on the shard rather than a silent change of its cases.
    for declared, splits, fragment in ((True, frozenset(), "does not read"),
                                       (False, frozenset({"sample"}), "does not set it"),
                                       ("yes", frozenset({"sample"}), "does not set it")):
        ran = []
        with patch.object(runner.importlib, "import_module",
                          return_value=_declared_module(ran, declared)):
            report = runner._run_module("sample", False, lanes, Shard(1, 2), splits)
        ensure(report.findings == 1 and fragment in "\n".join(report.out) and not ran,
               f"a disagreeing declaration must fail the module ({fragment!r}): {report.out}")


def _declarations_are_read_from_the_line() -> None:
    for text, declared in (("x = 1\nINDEPENDENT_CASES = True\n", True),
                           ("    INDEPENDENT_CASES = True\n", False),
                           ("INDEPENDENT_CASES = True  # why\n", False),
                           ("INDEPENDENT_CASES: bool = True\n", False),
                           ("INDEPENDENT_CASES = False\n", False)):
        ensure((runner._DECLARED.search(text) is not None) == declared,
               f"the declaration line was misread in {text!r}")
    ensure(runner._declares("test_sharding") and runner._declares("test_checks")
           and not runner._declares("test_report") and not runner._declares("test_absent"),
           "the live modules' declarations are read from their sources")


def _shards_split_declared_modules_by_case() -> None:
    # test_sharding declares its cases independent, test_report does not: the stride
    # gives each shard one module, shard 2's being the declared one, and every shard
    # runs its share of test_sharding's cases.
    names = ["test_report", "test_sharding"]
    listed = len(test_sharding.cases())
    shared = 0
    for index in (1, 2):
        with patch.object(runner, "_module_names", return_value=names):
            report = runner.run(jobs=1, shard=Shard(index, 2))
        share = len(Shard(index, 2).share(test_sharding.cases()))
        shared += share
        whole = 1 if index == 1 else 0
        ensure(report.findings == 0
               and f"shard {index}/2: {whole} of 1 modules, and its share of the cases of 1 "
                   "more; every shard must pass" in report.out
               and f"ok test_sharding: {share} case(s), this shard's share of {listed}"
                   in report.out
               and any(line.startswith("ok test_report:") for line in report.out) == (index == 1),
               f"shard {index}/2 ran the wrong modules or cases: {report.out}")
    ensure(shared == listed, "the shards' shares must add up to the module's cases")
    # A worker holds the module to the declaration the parent read: test_report read as
    # declared fails on every shard rather than running a share it never declared.
    for index in (1, 2):
        with (patch.object(runner, "_module_names", return_value=names),
              patch.object(runner, "_declares", side_effect=lambda name: name == "test_report")):
            report = runner.run(jobs=1, shard=Shard(index, 2))
        ensure(report.findings >= 1 and any("does not set it" in line for line in report.out),
               f"a declaration the module does not make must fail shard {index}: {report.out}")


def _module_timings_stay_out_of_the_report() -> None:
    names = ["test_harness", "test_report"]
    with tempfile.TemporaryDirectory(prefix="vos-runner-units-") as td:
        path = Path(td) / "units.json"
        with patch.object(runner, "_module_names", return_value=names):
            plain = runner.run(jobs=2)
            timed = runner.run(jobs=2, record=path)
        units = timings.read(path) or []
        claimed = Path(td) / "claimed.json"
        with (patch.object(runner, "_module_names", return_value=names[1:]),
              patch.dict(runner.os.environ, {timings.ENV: str(claimed)}),
              redirect_stdout(StringIO())):
            code = runner.main(["--jobs", "1"])
            ensure(timings.ENV not in runner.os.environ,
                   "the run claims its file before any worker can inherit it")
        through_main = timings.read(claimed) or []
    ensure(plain.out == timed.out and plain.findings == timed.findings == 0,
           f"recording timings changed the report: {timed.out}")
    ensure([unit["name"] for unit in units] == names
           and all(unit["kind"] == "module" and isinstance(seconds := unit["seconds"], float)
                   and seconds >= 0 for unit in units),
           f"each module is recorded once, in report order, with its seconds: {units!r}")
    ensure(all(f"ok {unit['name']}: {unit['cases']} case(s)" in timed.out for unit in units),
           f"each module's recorded case count is the count it reported: {units!r}")
    ensure(code == 0 and [unit["name"] for unit in through_main] == names[1:],
           f"the command records to the file its environment names: {through_main!r}")


def cases() -> list[Case]:
    return [
        Case("selection-and-failures", _selection_and_failures),
        Case("load-errors", _load_errors),
        Case("captured-output", _captured_output),
        Case("spawn-isolation", _spawn_isolation),
        Case("empty-and-invalid", _empty_and_invalid),
        Case("shards-execute-the-selected-modules", _shards_execute_the_selected_modules),
        Case("declared-modules-share-their-cases", _declared_modules_share_their_cases),
        Case("declarations-are-read-from-the-line", _declarations_are_read_from_the_line),
        Case("shards-split-declared-modules-by-case", _shards_split_declared_modules_by_case),
        Case("module-timings-stay-out-of-the-report", _module_timings_stay_out_of_the_report),
    ]
