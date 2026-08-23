# SPDX-License-Identifier: Apache-2.0
"""The type gate's own seams: the parses, the version probe, and the crash contract.

`typecheck.py` runs two pinned checkers and reduces their output to one verdict per
tool. What is held here is everything that can be decided without the real checkers:
both concise-line parses against canned output, the per-rule summary's ordering and
truncation, and, through a stub executable, the unified runner's wave-1 contract
that a returncode outside (0, 1) is reported as a checker error even when findings
parsed, because a checker that died partway has not cleared the files it never
reached.
"""

import os
import tempfile
from pathlib import Path

import typecheck
from tests.harness import Case, ensure
from vos.report import Reporter

# What the version-probing stubs answer, chosen not to collide with any real tool
# name so the PATH lookup in `_tool` can only find the stub this module wrote.
_STUB_NAME = "vostestfakechk"
_STUB_PIN = "9.9.9"


def _parse_ty() -> None:
    text = (
        "checks/meta.py:10:5: error[unresolved-import] Cannot resolve import `nope`\n"
        "vos/corpus.py:2:1: warning[unused-ignore-comment] Unused `ty: ignore`\n"
        "Found 2 diagnostics\n"
        "All checks passed!\n"
    )
    found = typecheck._parse_ty(text)
    ensure(found == [
        ("unresolved-import", "checks/meta.py:10:5 Cannot resolve import `nope`"),
        ("unused-ignore-comment", "vos/corpus.py:2:1 Unused `ty: ignore`"),
    ], f"ty's concise lines parsed as {found!r}")


def _parse_ty_skips_summary() -> None:
    # The trailing summary line and anything else without the `error[`/`warning[`
    # shape must not read as findings.
    ensure(typecheck._parse_ty("Found 12 diagnostics\n") == [],
           "ty's trailing summary line must parse to nothing")
    ensure(typecheck._parse_ty("") == [], "empty output must parse to nothing")


def _parse_ruff() -> None:
    text = (
        "test.py:3:1: ANN001 Missing type annotation for `x`\n"
        "vos/env.py:7:9: F401 `os` imported but unused\n"
        "warning: The top-level linter settings are deprecated\n"
        "Found 2 errors.\n"
        "\n"
    )
    found = typecheck._parse_ruff(text)
    ensure(found == [
        ("ANN001", "test.py:3:1 Missing type annotation for `x`"),
        ("F401", "vos/env.py:7:9 `os` imported but unused"),
    ], f"ruff's concise lines parsed as {found!r}")


def _summarize_ordering() -> None:
    # Codes sort by falling count and then by code; within one code the tool's own
    # order is preserved.
    rep = Reporter()
    findings = [("B900", "b-one"), ("A100", "a-one"), ("B900", "b-two"),
                ("A100", "a-two"), ("C500", "c-one")]
    typecheck._summarize(rep, "stub", "finding(s):", findings, "clean")
    body = [line.removeprefix("       ") for line in rep.out[1:]]
    ensure(body == ["A100: 2", "  a-one", "  a-two", "B900: 2", "  b-one", "  b-two",
                    "C500: 1", "  c-one"],
           f"the summary ordered itself as {body!r}")


def _summarize_truncation() -> None:
    rep = Reporter()
    findings = [("Z999", f"site-{n}") for n in range(typecheck.PER_RULE + 2)]
    typecheck._summarize(rep, "stub", "finding(s):", findings, "clean")
    body = [line.removeprefix("       ") for line in rep.out[1:]]
    ensure(body[0] == f"Z999: {typecheck.PER_RULE + 2}",
           f"the count line read {body[0]!r}")
    ensure(len([b for b in body if b.startswith("  site-")]) == typecheck.PER_RULE,
           "exactly PER_RULE sites are printed before the rest are counted")
    ensure(body[-1] == "  ... and 2 more", f"the truncation line read {body[-1]!r}")

    clean = Reporter()
    typecheck._summarize(clean, "stub", "finding(s):", [], "clean")
    ensure(clean.out == ["ok stub: clean"] and clean.findings == 0,
           f"no findings must report the ok line, got {clean.out!r}")


def _summarize_counts_findings_not_lines() -> None:
    # The verdict is how many findings there are, and the lines are never that number:
    # a rule header sits above each sample, so under the cap they run long, and a
    # single tail line stands in for everything the cap held back, so over it they run
    # short. Both directions are pinned because the first is what a clean tree meeting
    # a newly escalated rule sees, and the second is what a large regression sees.
    rep = Reporter()
    findings = [("A100", "a-one"), ("A100", "a-two"), ("B900", "b-one")]
    typecheck._summarize(rep, "stub", "finding(s):", findings, "clean")
    ensure(rep.findings == 3, f"three findings must decide 3, not {rep.findings}")
    ensure(rep.out[0] == "FAIL stub: 3 finding(s):",
           f"the verdict line read {rep.out[0]!r}")
    ensure(len(rep.out) - 1 > 3,
           "this sample prints more lines than there are findings, which is the point")

    over = Reporter()
    many = [("Z999", f"site-{n}") for n in range(typecheck.PER_RULE + 5)]
    typecheck._summarize(over, "stub", "finding(s):", many, "clean")
    ensure(over.findings == typecheck.PER_RULE + 5,
           f"the sample cap must not lower the verdict: {over.findings}")
    ensure(over.out[0] == f"FAIL stub: {typecheck.PER_RULE + 5} finding(s):",
           f"the verdict line read {over.out[0]!r}")
    ensure(len(over.out) - 1 < typecheck.PER_RULE + 5,
           "this sample prints fewer lines than there are findings, which is the point")


def _stub(directory: Path, name: str, body: str) -> Path:
    # A .bat file is the one stub shape CreateProcess runs from a bare argv on this
    # lane, which is why the cases that need one are marked host.
    path = directory / f"{name}.bat"
    path.write_text(body, encoding="utf-8", newline="")
    return path


def _version_probe() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        directory = Path(td)
        ty_like = _stub(directory, "tylike",
                        "@echo off\r\necho ty 0.0.73 (abc 2025)\r\n")
        ensure(typecheck._version(str(ty_like)) == "0.0.73",
               "ty's `<name> <version> (<build>)` must reduce to its second token")
        ruff_like = _stub(directory, "rufflike", "@echo off\r\necho ruff 0.16.4\r\n")
        ensure(typecheck._version(str(ruff_like)) == "0.16.4",
               "ruff's `<name> <version>` must reduce to its second token")
        silent = _stub(directory, "silent", "@echo off\r\n")
        ensure(typecheck._version(str(silent)) == "unknown",
               "an executable answering nothing must probe as `unknown`")


def _checker_stub_body(exit_code: int, finding: bool) -> str:
    line = "echo x.py:1:1: ANN001 stub finding\r\n" if finding else ""
    return (f'@echo off\r\nif "%~1"=="--version" (\r\necho {_STUB_NAME} {_STUB_PIN}\r\n'
            f"exit /b 0\r\n)\r\n{line}exit /b {exit_code}\r\n")


def _run_stub_checker(body: str, pin: str) -> Reporter:
    """One `_run_checker` pass routed at a stub on PATH, so the pin gate, the run,
    the parse and the verdict are all the real code's."""
    rep = Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        directory = Path(td)
        _stub(directory, _STUB_NAME, body)
        was = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{directory}{os.pathsep}{was}"
        try:
            typecheck._run_checker(
                rep, _STUB_NAME, pin, ["check"], directory, with_stderr=False,
                parse=typecheck._parse_ruff, label="lint finding(s):", ok="clean")
        finally:
            os.environ["PATH"] = was
    return rep


def _crash_reported_beside_findings() -> None:
    # The wave-1 contract: exit 5 with diagnostics printed first is a crash whatever
    # parsed, so the checker error is reported AND the partial findings stand beside
    # it rather than reading as the whole verdict.
    rep = _run_stub_checker(_checker_stub_body(5, finding=True), _STUB_PIN)
    joined = "\n".join(rep.out)
    ensure(f"FAIL {_STUB_NAME}: 1 checker error(s):" in joined
           and f"{_STUB_NAME} exited 5" in joined,
           f"a returncode outside (0, 1) must be reported as a crash, got {rep.out!r}")
    ensure("ANN001: 1" in joined and "x.py:1:1 stub finding" in joined,
           f"the findings that did parse must still be summarized, got {rep.out!r}")


def _crash_with_nothing_parsed() -> None:
    rep = _run_stub_checker(_checker_stub_body(3, finding=False), _STUB_PIN)
    joined = "\n".join(rep.out)
    ensure(f"{_STUB_NAME} exited 3" in joined,
           f"a silent crash must still be a checker error, got {rep.out!r}")
    ensure("lint finding(s):" not in joined
           and not any(line.startswith("ok ") for line in rep.out),
           f"a silent crash must not also report a findings verdict, got {rep.out!r}")


def _ordinary_finding_exit() -> None:
    # Exit 1 is the findings convention, not a crash: no checker error, one summary.
    rep = _run_stub_checker(_checker_stub_body(1, finding=True), _STUB_PIN)
    joined = "\n".join(rep.out)
    ensure("checker error(s):" not in joined,
           f"exit 1 with findings is not a crash, got {rep.out!r}")
    ensure(f"FAIL {_STUB_NAME}" in joined and "ANN001: 1" in joined,
           f"exit 1's findings must be summarized, got {rep.out!r}")


def _pin_gate_refusals() -> None:
    # A drifted version and an absent tool are each one worded finding, and neither
    # lets the check run at all.
    rep = _run_stub_checker(_checker_stub_body(0, finding=False), "1.0.0")
    joined = "\n".join(rep.out)
    ensure("version(s) other than the pinned one:" in joined
           and f"{_STUB_NAME} {_STUB_PIN} is installed and this tree pins 1.0.0" in joined,
           f"a drifted pin must be the reported refusal, got {rep.out!r}")

    absent = Reporter()
    typecheck._run_checker(
        absent, "vostest-absent-tool", "1.0.0", ["check"], Path.cwd(),
        with_stderr=False, parse=typecheck._parse_ruff, label="lint finding(s):",
        ok="clean")
    ensure("not installed:" in "\n".join(absent.out)
           and "pip install vostest-absent-tool==1.0.0" in "\n".join(absent.out),
           f"an absent tool must name the pip remedy, got {absent.out!r}")


def cases() -> list[Case]:
    return [
        Case("parse-ty", _parse_ty),
        Case("parse-ty-skips-summary", _parse_ty_skips_summary),
        Case("parse-ruff", _parse_ruff),
        Case("summarize-ordering", _summarize_ordering),
        Case("summarize-truncation", _summarize_truncation),
        Case("summarize-counts-findings", _summarize_counts_findings_not_lines),
        Case("version-probe", _version_probe, lane="host"),
        Case("crash-reported-beside-findings", _crash_reported_beside_findings, lane="host"),
        Case("crash-with-nothing-parsed", _crash_with_nothing_parsed, lane="host"),
        Case("ordinary-finding-exit", _ordinary_finding_exit, lane="host"),
        Case("pin-gate-refusals", _pin_gate_refusals, lane="host"),
    ]
