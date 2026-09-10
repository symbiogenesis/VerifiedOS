# SPDX-License-Identifier: Apache-2.0
"""Behavioral runner isolation, selection and failure reporting."""

from contextlib import redirect_stderr
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from tests.harness import Case, ensure
from vos.cli import test as runner


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


def cases() -> list[Case]:
    return [
        Case("selection-and-failures", _selection_and_failures),
        Case("load-errors", _load_errors),
        Case("captured-output", _captured_output),
        Case("spawn-isolation", _spawn_isolation),
        Case("empty-and-invalid", _empty_and_invalid),
    ]
