# SPDX-License-Identifier: Apache-2.0
"""The type gate's own seams: the parses, the version probe, the crash contract, and
the gate's reading of ty.toml.

`typecheck.py` runs two pinned checkers and reduces their output to one verdict per
tool. What is held here is everything that can be decided without the real checkers:
both concise-line parses against canned output, the per-rule summary's ordering and
truncation, and, through a stub executable, the unified runner's wave-1 contract
that a returncode outside (0, 1) is reported as a checker error even when findings
parsed, because a checker that died partway has not cleared the files it never
reached. The ty.toml cases hold the settings the gate refuses: a `[rules]` table
other than exactly `all = "error"`, an `[[overrides]]` entry carrying any key but
`include` and `exclude`, an `[analysis]` key outside the ones that suppress nothing,
an `[environment]` key other than the three it admits or either held value changed,
a `[src]` table other than exactly the committed one, and a file it cannot read.
The run cases hold one pin probe for a checker's passes, one ty pass per platform,
linux and then win32, with the real ty showing the win32 pass reaching a branch the
linux pass cannot, a user-level configuration or a set `PYTHONPATH` reported
beside the run, and the real ruff keeping a module an ignore file matches.
The coverage cases hold the floor under both checkers: the log read out of stderr
and the files it names, each tracked module a run's log does not name reported
under its checker and a crash not held to it, the real ruff and ty each reporting a
module a default exclusion or a ruff.toml exclusion drops, the real ty reaching every
module and writing no profile with `TY_LOG` and `TY_LOG_PROFILE` set, a ruff.toml
per-file suppression, `extend` or any key outside the committed file's, a file-level
`noqa` directive naming anything but N999 alone, and a range, `file-ignore` or isort
`skip_file` or `off` comment each refused, the real ruff showing the floor alone passes
each of them, the index
read for the tracked modules, and each live-tree run giving a verdict and reaching
every module the tree tracks, a missing or another installed checker refused. The
import cases hold the scan beside the checkers: an import of a module ruff.toml bans at
module level refused outside a function body, in a class body, a module-level block or
the main guard, and admitted in a function body or behind a `sys.platform` check, a
ruff.toml or module the scan cannot read refused, and the real ruff leaving open what
the scan refuses.
"""

import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

from tests.harness import Case, ensure
from vos.cli import typecheck
from vos.report import Reporter

# The fake executable's version banner, independent of installed checkers.
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


def _environment_tool_resolution() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        directory = Path(td)
        for platform, filename in (("win32", "ty.exe"), ("linux", "ty")):
            candidate = directory / filename
            candidate.touch()
            with patch.object(typecheck, "sys", SimpleNamespace(platform=platform)), \
                    patch.object(typecheck, "sysconfig", SimpleNamespace(
                        get_path=lambda _: td)):
                ensure(typecheck._tool("ty") == str(candidate),
                       "the running environment supplies the checker on either OS")
                ensure(typecheck._tool("uv") is None,
                       "a missing environment tool must not fall back to PATH")
            candidate.unlink()


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


def _stub_pass(detail: str = "") -> typecheck.Pass:
    """A pass over the stub, reported under its name and `detail`, if any."""
    who = f"{_STUB_NAME} {detail}".strip()
    return typecheck.Pass(["check", detail] if detail else ["check"], who,
                          f"lint finding(s){' ' + detail if detail else ''}:",
                          f"clean{' ' + detail if detail else ''}")


def _run_stub_checker(body: str, pin: str,
                      passes: list[typecheck.Pass] | None = None) -> Reporter:
    """One `_run_checker` call routed at a stub, one pass unless `passes` says
    otherwise, so the pin gate, each run, the parse and the verdict are all the real
    code's."""
    rep = Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        directory = Path(td)
        stub = _stub(directory, _STUB_NAME, body)
        with patch.object(typecheck, "_tool", return_value=str(stub)):
            typecheck._run_checker(
                rep, _STUB_NAME, pin, passes or [_stub_pass()], directory,
                with_stderr=False, parse=typecheck._parse_ruff)
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


def _failed_check_requires_a_diagnostic() -> None:
    """Neither missing output nor a changed output dialect can clear a failed checker."""
    for output in ("", "echo a diagnostic in an unfamiliar format\r\n"):
        body = _checker_stub_body(1, finding=False).replace(
            "exit /b 1", output + "exit /b 1")
        rep = _run_stub_checker(body, _STUB_PIN)
        ensure(rep.findings > 0 and not any(line.startswith("ok ") for line in rep.out),
               f"an unparsed failing check reported success: {rep.out!r}")
        ensure("no diagnostic was recognized" in "\n".join(rep.out),
               f"the refusal must explain the missing diagnostic: {rep.out!r}")


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
        absent, "vostest-absent-tool", "1.0.0", [_stub_pass()], Path.cwd(),
        with_stderr=False, parse=typecheck._parse_ruff)
    ensure("not installed:" in "\n".join(absent.out)
            and "synchronize tools/uv.lock" in "\n".join(absent.out),
           f"an absent tool must name the uv remedy, got {absent.out!r}")


def _passes_share_one_pin_probe() -> None:
    # Each pass is its own verdict under the checker's one rule, in the order given,
    # and a crash names the pass it came from. The pin is one fact about one
    # executable: probed once, so a drifted pin is one finding and no pass runs.
    two = [_stub_pass("first"), _stub_pass("second")]
    clean = _run_stub_checker(_checker_stub_body(0, finding=False), _STUB_PIN, two)
    ensure(clean.findings == 0 and clean.out == [f"ok {_STUB_NAME}: clean first",
                                                 f"ok {_STUB_NAME}: clean second"],
           f"two clean passes must be two verdicts, in order: {clean.out!r}")
    found = _run_stub_checker(_checker_stub_body(1, finding=True), _STUB_PIN, two)
    ensure(found.findings == 2
           and [line for line in found.out if line.startswith("FAIL ")]
           == [f"FAIL {_STUB_NAME}: 1 lint finding(s) first:",
               f"FAIL {_STUB_NAME}: 1 lint finding(s) second:"],
           f"a finding in each pass must be reported under each: {found.out!r}")
    crashed = _run_stub_checker(_checker_stub_body(4, finding=False), _STUB_PIN, two)
    joined = "\n".join(crashed.out)
    ensure(f"{_STUB_NAME} first exited 4" in joined
           and f"{_STUB_NAME} second exited 4" in joined,
           f"a crash must name the pass it came from: {crashed.out!r}")
    drifted = _run_stub_checker(_checker_stub_body(0, finding=False), "1.0.0", two)
    ensure(drifted.findings == 1
           and "version(s) other than the pinned one:" in "\n".join(drifted.out)
           and not any(line.startswith("ok ") for line in drifted.out),
           f"a drifted pin must be one finding and run no pass: {drifted.out!r}")


# The ty.toml this tree carries, which the gate reads from the same place.
_TY_TOML = Path(typecheck.__file__).resolve().parents[2] / "ty.toml"
_ALL_ERROR = '[rules]\nall = "error"\n'
_ENV = '\n[environment]\npython-platform = "linux"\nextra-paths = ["."]\n'
_SRC = '\n[src]\nexclude = ["**/__pycache__/**"]\nrespect-ignore-files = false\n'
# The tables beside `[rules]` that the gate requires, `[src]` last so that a case
# can append a key to it.
_HELD = _ENV + _SRC
# The smallest ty.toml the gate admits: the tables it holds exactly, and the two
# environment values it holds.
_ADMITTED = _ALL_ERROR + _HELD


def _settings(text: str | None) -> list[str]:
    """`_ty_settings` over a ty.toml holding `text`, or over none at all."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        config = Path(td) / "ty.toml"
        if text is not None:
            config.write_text(text, encoding="utf-8", newline="")
        return typecheck._ty_settings(config)


def _ty_settings_admitted() -> None:
    ensure(typecheck._ty_settings(_TY_TOML) == [],
           f"the committed ty.toml must pass its own gate: {typecheck._ty_settings(_TY_TOML)!r}")
    for text in (_ADMITTED,
                 # An override that only selects files does nothing to them.
                 _ADMITTED + '\n[[overrides]]\ninclude = ["tests/**"]\n',
                 _ADMITTED + '\n[[overrides]]\ninclude = ["tests/**"]\n'
                             'exclude = ["tests/data/**"]\n',
                 _ADMITTED + '\n[[overrides]]\n',
                 # The analysis settings that only make ty stricter, or restate its
                 # default, are admitted, the alias among them.
                 _ADMITTED + '\n[analysis]\nrespect-type-ignore-comments = false\n'
                             'strict-equality-semantics = true\n'
                             'strict-generic-narrowing = true\n',
                 _ADMITTED + '\n[analysis]\nstrict-literal-narrowing = true\n',
                 _ADMITTED + '\n[analysis]\n',
                 # python-version's value is K-75's to hold, so this gate admits the
                 # key whatever it says, and its absence.
                 _ALL_ERROR + _ENV + 'python-version = "3.14"\n' + _SRC,
                 _ALL_ERROR + _ENV + 'python-version = "3.12"\n' + _SRC):
        ensure(_settings(text) == [], f"an admissible ty.toml was refused: {text!r}")


def _ty_settings_refuse_rules() -> None:
    # The table is held exactly: a lowered `all`, an entry beside it, and no table are
    # each one finding, even the entry that restates what `all` already says.
    for text, expected in (
            ('[rules]\nall = "warn"\n' + _HELD, "sets [rules] to {'all': 'warn'}"),
            (_ALL_ERROR + 'unresolved-import = "ignore"\n' + _HELD,
             "'unresolved-import': 'ignore'"),
            (_ALL_ERROR + 'unresolved-import = "error"\n' + _HELD,
             "'unresolved-import': 'error'"),
            (_HELD, "carries no [rules] table")):
        found = _settings(text)
        ensure(len(found) == 1 and expected in found[0]
               and "exactly {'all': 'error'}" in found[0],
               f"a [rules] table other than all = error must be one finding: {found!r}")


def _ty_settings_refuse_overrides() -> None:
    carrying = ('\n[[overrides]]\ninclude = ["vos/**"]\n'
                '\n[[overrides]]\ninclude = ["tests/**"]\n'
                '\n[overrides.rules]\nunresolved-import = "ignore"\n')
    found = _settings(_ADMITTED + carrying)
    ensure(len(found) == 1 and "[[overrides]] entry 2" in found[0]
           and "unresolved-import" in found[0] and "tests/**" in found[0]
           and "can lower --error all" in found[0],
           f"an override carrying rules must be named by its entry: {found!r}")
    # The gate holds the shape, not the severity: an override carrying rules is
    # refused even when every rule it names stays at error.
    raised = _settings(_ADMITTED + '\n[[overrides]]\ninclude = ["x/**"]\n'
                       '\n[overrides.rules]\nall = "error"\n')
    ensure(len(raised) == 1 and "entry 1" in raised[0],
           f"any override carrying rules must be refused: {raised!r}")
    # An override's analysis suppresses diagnostics that no severity restores, and a
    # key the gate has not admitted is refused beside the two it knows.
    for table, key in (('\n[overrides.analysis]\nallowed-unresolved-imports = ["x.**"]\n',
                        "allowed-unresolved-imports"),
                       ('\n[overrides.analysis]\nreplace-imports-with-any = ["x.**"]\n',
                        "replace-imports-with-any"),
                       ('\n[overrides.analysis]\nstrict-generic-narrowing = true\n',
                        "strict-generic-narrowing"),
                       ('future-setting = 1\n', "future-setting")):
        carried = _settings(_ADMITTED + '\n[[overrides]]\ninclude = ["x/**"]\n' + table)
        ensure(len(carried) == 1 and "entry 1" in carried[0] and key in carried[0]
               and "only include and exclude" in carried[0],
               f"an override carrying {key} must be refused: {carried!r}")
    # One entry carrying both is one finding naming both.
    two = _settings(_ADMITTED + '\n[[overrides]]\ninclude = ["x/**"]\n'
                    '\n[overrides.rules]\nall = "error"\n'
                    '\n[overrides.analysis]\nallowed-unresolved-imports = ["x.**"]\n')
    ensure(len(two) == 1 and "carries analysis" in two[0] and "rules {" in two[0],
           f"an entry carrying rules and analysis must be one finding: {two!r}")
    for text in ('overrides = "tests"\n' + _ADMITTED,
                 _ADMITTED + '\n[overrides]\ninclude = ["tests/**"]\n'):
        shaped = _settings(text)
        ensure(len(shaped) == 1 and "must be an array of tables" in shaped[0],
               f"an overrides value of another shape must be refused: {shaped!r}")
    both = _settings('[rules]\nall = "warn"\n' + _HELD + carrying)
    ensure(len(both) == 2, f"each refused half must be its own finding: {both!r}")


def _ty_settings_refuse_analysis() -> None:
    # The two tree-wide suppressions are refused whatever they list, the empty list
    # included, and so is a key the gate has not admitted.
    for table, key in (('allowed-unresolved-imports = ["x.**"]\n',
                        "allowed-unresolved-imports ['x.**']"),
                       ('allowed-unresolved-imports = []\n', "allowed-unresolved-imports []"),
                       ('replace-imports-with-any = ["x.**"]\n',
                        "replace-imports-with-any ['x.**']"),
                       ('future-setting = true\n', "future-setting True")):
        found = _settings(_ADMITTED + '\n[analysis]\n' + table)
        ensure(len(found) == 1 and f"[analysis] carries {key}" in found[0]
               and "strict-generic-narrowing" in found[0],
               f"an [analysis] key outside the admitted ones must be refused: {found!r}")
    # Several refused keys in the table are one finding, and an admitted key beside
    # them is not named.
    several = _settings(_ADMITTED + '\n[analysis]\nstrict-equality-semantics = true\n'
                        'replace-imports-with-any = ["y"]\n'
                        'allowed-unresolved-imports = ["x"]\n')
    ensure(len(several) == 1
           and "carries allowed-unresolved-imports ['x'], replace-imports-with-any ['y'];"
           in several[0],
           f"one [analysis] table must be one finding naming each refused key: {several!r}")
    shaped = _settings('analysis = "none"\n' + _ADMITTED)
    ensure(len(shaped) == 1 and "analysis must be a table" in shaped[0],
           f"an analysis value of another shape must be refused: {shaped!r}")


def _ty_settings_refuse_environment() -> None:
    # Each key that moves where ty resolves imports is refused whatever it says, and
    # so is a key the gate has not read.
    for line, key in (('typeshed = "stubs"\n', "typeshed 'stubs'"),
                      ('root = ["src"]\n', "root ['src']"),
                      ('python = ".venv"\n', "python '.venv'"),
                      ('future-setting = 1\n', "future-setting 1")):
        found = _settings(_ALL_ERROR + _ENV + line + _SRC)
        ensure(len(found) == 1 and f"[environment] carries {key};" in found[0]
               and "admits only extra-paths, python-platform, python-version" in found[0]
               and "a key the gate has not read is refused with them" in found[0],
               f"an [environment] key outside the admitted ones must be refused: {found!r}")
    # The two held values are held exactly: another platform, an added or a missing
    # search path, and an absent key are each named, and one table is one finding.
    for text, expected in (
            ('\n[environment]\npython-platform = "win32"\nextra-paths = ["."]\n',
             "sets python-platform to 'win32';"),
            ('\n[environment]\npython-platform = "all"\nextra-paths = ["."]\n',
             "sets python-platform to 'all';"),
            ('\n[environment]\npython-platform = "linux"\nextra-paths = [".", "stubs"]\n',
             "sets extra-paths to ['.', 'stubs'];"),
            ('\n[environment]\npython-platform = "linux"\nextra-paths = []\n',
             "sets extra-paths to [];"),
            ('\n[environment]\nextra-paths = ["."]\n', "carries no python-platform;"),
            ('\n[environment]\npython-version = "3.14"\n',
             "carries no python-platform, carries no extra-paths;"),
            ('\n[environment]\npython-platform = "win32"\nextra-paths = ["stubs"]\n',
             "sets python-platform to 'win32', sets extra-paths to ['stubs'];"),
            ('', "carries no [environment] table;")):
        found = _settings(_ALL_ERROR + text + _SRC)
        ensure(len(found) == 1 and expected in found[0]
               and "python-platform to 'linux' and extra-paths to ['.']" in found[0],
               f"an [environment] value other than the held one must be refused: {found!r}")
    # A refused key and a changed value are two findings; another shape is one.
    two = _settings(_ALL_ERROR + '\n[environment]\npython-platform = "win32"\n'
                    'extra-paths = ["."]\ntypeshed = "stubs"\n' + _SRC)
    ensure(len(two) == 2, f"a refused key beside a changed value must be two findings: {two!r}")
    shaped = _settings('environment = "linux"\n' + _ALL_ERROR + _SRC)
    ensure(len(shaped) == 1 and "environment must be a table" in shaped[0],
           f"an environment value of another shape must be refused: {shaped!r}")


def _ty_settings_refuse_src() -> None:
    # The table is held exactly: each way of taking files out of the run, a changed
    # glob, and no table at all are each one finding. Ignore files are honored unless
    # the table says otherwise, so a table that is silent on them is refused with one
    # that honors them.
    head = _ALL_ERROR + _ENV
    ignore = 'respect-ignore-files = false\n'
    for text, expected in (
            (head, "carries no [src] table"),
            (head + '\n[src]\nexclude = ["**/__pycache__/**", "vos/**"]\n' + ignore,
             "'vos/**'"),
            (head + '\n[src]\nexclude = ["vos/**"]\n' + ignore, "'vos/**'"),
            (head + _SRC + 'include = ["tests"]\n', "'include': ['tests']"),
            (head + _SRC + 'exclude-scripts = true\n', "'exclude-scripts': True"),
            (head + '\n[src]\nexclude = ["**/__pycache__/**"]\n'
                    'respect-ignore-files = true\n', "'respect-ignore-files': True"),
            (head + '\n[src]\nexclude = ["**/__pycache__/**"]\n',
             "sets [src] to {'exclude': ['**/__pycache__/**']}"),
            (head + '\n[src]\n' + ignore, "sets [src] to {'respect-ignore-files'"),
            (head + '\n[src]\n', "sets [src] to {}")):
        found = _settings(text)
        ensure(len(found) == 1 and expected in found[0]
               and "exactly {'exclude': ['**/__pycache__/**'], 'respect-ignore-files': "
                   "False}" in found[0]
               and "honoring ignore files" in found[0],
               f"a [src] table other than the committed one must be one finding: {found!r}")


def _ty_settings_fail_closed() -> None:
    for text in (None, "[rules\nall = \"error\"\n"):
        found = _settings(text)
        ensure(len(found) == 1 and "cannot be read" in found[0],
               f"an absent or malformed ty.toml must be a finding: {found!r}")


def _passes(checker: MagicMock) -> list[typecheck.Pass]:
    """The passes the patched `_run_checker` was given, one per platform."""
    passes = cast("list[typecheck.Pass]", checker.call_args.args[3])
    ensure(all(isinstance(run, typecheck.Pass) for run in passes)
           and len(passes) == len(typecheck.TY_PLATFORMS),
           f"ty must run once per platform, got {passes!r}")
    return passes


def _claims(checker: MagicMock) -> list[bool]:
    """Whether each ty pass the patched `_run_checker` was given claims every rule at
    error, one entry per pass."""
    return [run.ok.endswith("all rules at error") for run in _passes(checker)]


def _ty_runs_every_platform() -> None:
    # One ty pass per platform, linux and then win32, each naming its platform on the
    # command line, in its verdict and in its failures, with every other argument
    # the same; the first is the platform ty.toml holds for an editor.
    ensure(typecheck.TY_PLATFORMS[0] == typecheck.TY_ENVIRONMENT["python-platform"],
           "the gate's first platform must be the one ty.toml holds for an editor")
    rep = Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        (root / "tools").mkdir()
        (root / "tools" / "ty.toml").write_text(_ADMITTED, encoding="utf-8", newline="")
        with patch.dict(os.environ), \
                patch.object(typecheck, "_user_config", return_value=None), \
                patch.object(typecheck, "_run_checker") as checker:
            os.environ.pop("PYTHONPATH", None)
            typecheck._run_ty(rep, root, frozenset({"kept.py"}))
        with patch.dict(os.environ), \
                patch.object(typecheck, "_user_config", return_value=None), \
                patch.object(typecheck, "_run_checker") as unheld:
            os.environ.pop("PYTHONPATH", None)
            typecheck._run_ty(Reporter(), root, None)
    # With no tracked modules to hold a run to, no pass logs or is held.
    ensure(all(run.coverage is None and not set(typecheck.TY_VERBOSE) & set(run.args)
               for run in _passes(unheld)),
           f"a pass held to nothing must not turn its log on: {_passes(unheld)!r}")
    passes = _passes(checker)
    platforms = [run.args[run.args.index("--python-platform") + 1] for run in passes]
    ensure(platforms == ["linux", "win32"],
           f"the gate must run ty under linux and then win32, got {platforms!r}")
    shared = {tuple(a for a in run.args if a not in platforms) for run in passes}
    ensure(len(shared) == 1, f"the passes may differ only in the platform: {passes!r}")
    for run, platform in zip(passes, platforms, strict=True):
        ensure(run.ok == f"every expression reachable under python-platform {platform} "
                        f"typechecks under ty {typecheck.TY_VERSION}, all rules at error"
               and run.label == f"type error(s) under python-platform {platform}:"
               and run.who == f"ty under python-platform {platform}",
               f"the {platform} pass must name its platform: {run!r}")
        # Each pass turns its log on and is held to the tracked modules, and is made
        # without the variables that would replace its log filter or write a profile.
        ensure(run.coverage == typecheck.Coverage(typecheck.TY_LOG, typecheck.TY_CHECKED,
                                                  frozenset({"kept.py"}))
               and run.args[-1 - len(typecheck.TY_VERBOSE):-1] == typecheck.TY_VERBOSE,
               f"the {platform} pass must log what it checks and be held to it: {run!r}")
        ensure(run.unset == {"TY_LOG", "TY_LOG_PROFILE"},
               f"the {platform} pass must be made without TY_LOG and TY_LOG_PROFILE: {run!r}")


def _win32_pass_types_host_branches() -> None:
    # The real ty over a module whose one error sits in a branch only win32 takes.
    # The linux pass, which is ty.toml's platform and the whole of what one run under
    # it would check, reports nothing; the win32 pass reports the error.
    rep = Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        (root / "tools").mkdir()
        (root / "tools" / "ty.toml").write_text(_ADMITTED, encoding="utf-8", newline="")
        (root / "tools" / "hostonly.py").write_text(
            'import sys\n\nif sys.platform == "win32":\n    count: int = "one"\n',
            encoding="utf-8", newline="")
        with patch.dict(os.environ), \
                patch.object(typecheck, "_user_config", return_value=None):
            os.environ.pop("PYTHONPATH", None)
            typecheck._run_ty(rep, root, frozenset({"hostonly.py"}))
    joined = "\n".join(rep.out)
    ensure(rep.out[:1] == ["ok ty: every expression reachable under python-platform linux "
                           f"typechecks under ty {typecheck.TY_VERSION}, all rules at error"],
           f"the linux pass cannot reach the win32 branch: {rep.out!r}")
    ensure(rep.findings == 1
           and "FAIL ty: 1 type error(s) under python-platform win32:" in joined
           and "hostonly.py:4:" in joined,
           f"the win32 pass must report the error in the win32 branch: {rep.out!r}")


def _ruff_checks_ignored_modules() -> None:
    # The real ruff over a module an ignore file matches, under a ruff.toml that does
    # not say respect-gitignore = false: ruff would skip the module and report
    # nothing, so the gate's own flag is what keeps it in the run.
    rep = Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        tools = root / "tools"
        tools.mkdir()
        (tools / "ruff.toml").write_text('[lint]\nselect = ["ANN"]\n', encoding="utf-8",
                                         newline="")
        (tools / ".ignore").write_text("ignored.py\n", encoding="utf-8", newline="")
        (tools / "ignored.py").write_text("def f(x):\n    return x\n", encoding="utf-8",
                                          newline="")
        typecheck._run_ruff(rep, root, frozenset({"ignored.py"}))
    joined = "\n".join(rep.out)
    ensure(rep.findings == 2 and "FAIL ruff: 2 lint finding(s):" in joined
           and "ANN001: 1" in joined and "ignored.py:1:" in joined,
           f"a module an ignore file matches must stay in the ruff run: {rep.out!r}")


def _ty_settings_reported_beside_the_run() -> None:
    # The refusal is a ty finding in the gate's own report, and the checker still runs.
    for text, refused in ((_ADMITTED, False), ('[rules]\nall = "warn"\n' + _HELD, True)):
        rep = Reporter()
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "tools" / "ty.toml").write_text(text, encoding="utf-8", newline="")
            with patch.object(typecheck, "_run_checker") as checker, \
                    patch.object(typecheck, "_user_config", return_value=None), \
                    patch.dict(os.environ):
                os.environ.pop("PYTHONPATH", None)
                typecheck._run_ty(rep, root, None)
        ensure(checker.call_count == 1, "the checker must run whatever the settings say")
        joined = "\n".join(rep.out)
        claims = _claims(checker)
        if refused:
            ensure(rep.findings == 1
                   and "FAIL ty: 1 ty.toml setting(s) the gate refuses:" in joined,
                   f"a refused setting must fail the gate under ty: {rep.out!r}")
            ensure(not any(claims), "a clean run beside refused settings must not claim "
                                    "every rule ran at error")
        else:
            ensure(rep.findings == 0 and rep.out == [],
                   f"an admitted ty.toml must add nothing to the report: {rep.out!r}")
            ensure(all(claims), "a clean run under admitted settings claims every rule at "
                                "error")


def _user_config_located() -> None:
    # ty's user configuration directory on each platform, read from the environment
    # ty inherits: the variable when it names a usable directory, the home directory's
    # default otherwise, and nothing where no file is.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        base, home = Path(td) / "base", Path(td) / "home"
        home.mkdir()
        for platform, variable, default in (("win32", "APPDATA", ("AppData", "Roaming")),
                                            ("linux", "XDG_CONFIG_HOME", (".config",))):
            under_base = base / platform / "ty" / "ty.toml"
            under_home = home.joinpath(*default, "ty", "ty.toml")
            environment = {"HOME": str(home), "USERPROFILE": str(home)}
            with patch.object(typecheck, "sys", SimpleNamespace(platform=platform)):
                with patch.dict(os.environ, {**environment,
                                             variable: str(base / platform)}):
                    ensure(typecheck._user_config() is None,
                           f"{platform}: no file must locate nothing")
                    under_base.parent.mkdir(parents=True)
                    under_base.write_text("", encoding="utf-8")
                    ensure(typecheck._user_config() == under_base,
                           f"{platform}: the {variable} file must be located")
                under_home.parent.mkdir(parents=True)
                under_home.write_text("", encoding="utf-8")
                with patch.dict(os.environ, {**environment, variable: ""}):
                    ensure(typecheck._user_config() == under_home,
                           f"{platform}: an empty {variable} must fall back to the home "
                           "directory's default")
                with patch.dict(os.environ, environment):
                    os.environ.pop(variable, None)
                    ensure(typecheck._user_config() == under_home,
                           f"{platform}: an unset {variable} must fall back to the home "
                           "directory's default")
        # ty ignores an XDG_CONFIG_HOME that is not absolute.
        with patch.object(typecheck, "sys", SimpleNamespace(platform="linux")), \
                patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home),
                                        "XDG_CONFIG_HOME": "base/linux"}):
            ensure(typecheck._user_config() == home / ".config" / "ty" / "ty.toml",
                   "a relative XDG_CONFIG_HOME must fall back to ~/.config")


def _user_config_reported_beside_the_run() -> None:
    # A user-level ty.toml that ty would merge is a ty finding naming its path, the
    # checker still runs, and the run no longer claims every rule at error.
    variable = "APPDATA" if sys.platform == "win32" else "XDG_CONFIG_HOME"
    for present in (False, True):
        rep = Reporter()
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "tools" / "ty.toml").write_text(_ADMITTED, encoding="utf-8", newline="")
            user = root / "config" / "ty" / "ty.toml"
            user.parent.mkdir(parents=True)
            if present:
                user.write_text('[analysis]\nallowed-unresolved-imports = ["**"]\n',
                                encoding="utf-8", newline="")
            with patch.dict(os.environ, {variable: str(root / "config")}), \
                    patch.object(typecheck, "_run_checker") as checker:
                os.environ.pop("PYTHONPATH", None)
                typecheck._run_ty(rep, root, None)
        ensure(checker.call_count == 1, "the checker must run whatever the settings say")
        joined = "\n".join(rep.out)
        claims = _claims(checker)
        if present:
            ensure(rep.findings == 1
                   and "FAIL ty: 1 user-level configuration(s) the gate refuses:" in joined
                   and f"a user-level ty configuration at {user} merges into the gate's "
                       "run" in joined,
                   f"a user-level ty.toml must be a ty finding naming it: {rep.out!r}")
            ensure(not any(claims), "a run beside a user-level ty.toml must not claim every "
                                    "rule ran at error")
        else:
            ensure(rep.findings == 0 and rep.out == [] and all(claims),
                   f"an empty user configuration directory must add nothing: {rep.out!r}")


def _pythonpath_reported_beside_the_run() -> None:
    # A PYTHONPATH that ty would search ahead of the standard library is a ty finding
    # naming its value, an empty one included; the checker still runs, and the run no
    # longer claims every rule at error. Without the variable nothing is added.
    for value in (None, "", "shadow"):
        rep = Reporter()
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "tools" / "ty.toml").write_text(_ADMITTED, encoding="utf-8", newline="")
            with patch.dict(os.environ), \
                    patch.object(typecheck, "_user_config", return_value=None), \
                    patch.object(typecheck, "_run_checker") as checker:
                os.environ.pop("PYTHONPATH", None)
                if value is not None:
                    os.environ["PYTHONPATH"] = value
                typecheck._run_ty(rep, root, None)
        ensure(checker.call_count == 1, "the checker must run whatever the environment says")
        joined = "\n".join(rep.out)
        claims = _claims(checker)
        if value is None:
            ensure(rep.findings == 0 and rep.out == [] and all(claims),
                   f"an unset PYTHONPATH must add nothing: {rep.out!r}")
        else:
            ensure(rep.findings == 1
                   and "FAIL ty: 1 environment variable(s) the gate refuses:" in joined
                   and f"PYTHONPATH is set to {value!r}" in joined,
                   f"a set PYTHONPATH must be a ty finding naming it: {rep.out!r}")
            ensure(not any(claims), "a run beside a set PYTHONPATH must not claim every rule "
                                    "ran at error")


def _read_log_separates_the_log() -> None:
    # Each checker's log below warning level leaves stderr, its checked-file lines
    # naming files relative to the run's directory, an absolute or a relative path
    # alike; a file outside the directory stays absolute. ty's slow-file line names a
    # file too but is not the checked-file line. A warning and anything that is not
    # the log stay for the parse and a crash's message.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        cwd = Path(td)
        outside = cwd.parent / "outside.py"
        ty_stderr = "\n".join([
            "2026-09-29 23:26:43.6945617 DEBUG Version: 0.0.84 (8dd9a7f7f 2026-09-24)",
            f"2026-09-29 23:26:43.7106384 DEBUG Checking file '{cwd / 'vos' / 'a.py'}'",
            f"2026-09-29 23:26:43.7106392 DEBUG Checking file '{cwd / 'b.pyi'}'",
            "2026-09-29 23:26:43.7106393 DEBUG Checking file 'tests/c.py'",
            f"2026-09-29 23:26:43.7106394 DEBUG Checking file '{outside}'",
            f"2026-09-29 23:26:07.4495777 INFO Checking file `{cwd / 'slow.py'}` took more "
            "than 100ms (100.4931ms)",
            "2026-09-29 23:26:43.73598 WARN a warning the checker gives",
            "thread 'main' panicked at src/main.rs",
        ])
        kept, checked = typecheck._read_log(
            ty_stderr, typecheck.Coverage(typecheck.TY_LOG, typecheck.TY_CHECKED,
                                          frozenset()), cwd)
        ensure(checked == {"vos/a.py", "b.pyi", "tests/c.py", outside.as_posix()},
               f"ty's log named {checked!r}")
        ensure(kept.splitlines() == ["2026-09-29 23:26:43.73598 WARN a warning the checker "
                                     "gives", "thread 'main' panicked at src/main.rs"],
               f"ty's stderr kept {kept!r}")
        head = "[2026-09-29][23:29:35]"
        ruff_stderr = "\n".join([
            f"{head}[ruff::resolve][DEBUG] Using user-specified configuration file at: x",
            f'{head}[ruff_workspace::resolver][DEBUG] Included path via `include`: '
            f'"{cwd / "skipped.py"}"',
            f"{head}[ruff::diagnostics][DEBUG] Checking: {cwd / 'vos' / 'a.py'}",
            f"{head}[ruff::diagnostics][DEBUG] Checking: {cwd / 'ruff.toml'}",
            f"{head}[ruff::commands::check][DEBUG] Checked 2 files in: 22.7095ms",
            f"{head}[ruff_workspace::pyproject][WARN] a warning the checker gives",
            "error: Failed to parse ruff.toml",
        ])
        kept, checked = typecheck._read_log(
            ruff_stderr, typecheck.Coverage(typecheck.RUFF_LOG, typecheck.RUFF_CHECKED,
                                            frozenset()), cwd)
        ensure(checked == {"vos/a.py", "ruff.toml"}, f"ruff's log named {checked!r}")
        ensure(kept.splitlines() == [f"{head}[ruff_workspace::pyproject][WARN] a warning the "
                                     "checker gives", "error: Failed to parse ruff.toml"],
               f"ruff's stderr kept {kept!r}")


def _cover_reports_what_the_log_missed() -> None:
    # Each tracked module the log does not name is one finding under the checker, in
    # order; a file the log names that the index does not track is held to nothing.
    run, coverage = _stub_pass(), typecheck.Coverage(
        typecheck.RUFF_LOG, typecheck.RUFF_CHECKED, frozenset({"a.py", "b.py", "c.pyi"}))
    short = Reporter()
    typecheck._cover(short, "stub", run, coverage, {"a.py", "ruff.toml"})
    ensure(short.findings == 2 and short.out == [
        f"FAIL stub: 2 tracked module(s) {_STUB_NAME} did not check:",
        "       b.py", "       c.pyi"], f"the shortfall reported as {short.out!r}")
    whole = Reporter()
    typecheck._cover(whole, "stub", run, coverage, {"a.py", "b.py", "c.pyi", "extra.py"})
    ensure(whole.findings == 0 and whole.out == [],
           f"a run reaching every tracked module must add nothing: {whole.out!r}")
    # A log naming nothing says so first, since a changed log shape reads that way,
    # and the sample cap does not lower the count.
    many = typecheck.Coverage(typecheck.RUFF_LOG, typecheck.RUFF_CHECKED,
                              frozenset(f"m{n:02}.py" for n in range(typecheck.PER_RULE + 3)))
    silent = Reporter()
    typecheck._cover(silent, "stub", run, many, set())
    ensure(silent.findings == typecheck.PER_RULE + 3
           and "logged no checked file" in silent.out[1]
           and silent.out[-1] == "       ... and 3 more",
           f"a log naming nothing must be reported as such: {silent.out!r}")


def _logging_stub_body(exit_code: int, logged: str, extra: str = "") -> str:
    """A stub whose run logs, in ruff's shape, each file in `logged` as checked in its
    working directory, then prints `extra` to stderr and exits `exit_code`."""
    head = "[2026-09-29][23:29:35]"
    lines = f">&2 echo {head}[ruff::resolve][DEBUG] a log line naming no file\r\n"
    lines += "".join(f">&2 echo {head}[ruff::diagnostics][DEBUG] Checking: %CD%\\{name}\r\n"
                     for name in logged.split())
    if extra:
        lines += f">&2 echo {extra}\r\n"
    return (f'@echo off\r\nif "%~1"=="--version" (\r\necho {_STUB_NAME} {_STUB_PIN}\r\n'
            f"exit /b 0\r\n)\r\n{lines}exit /b {exit_code}\r\n")


def _coverage_read_from_the_run() -> None:
    # The unified runner reads a pass's log out of the run it made: a tracked module
    # the log leaves out is a finding beside the clean verdict, one it names is not,
    # and a crash is reported with its own message, never the log, and is not held to
    # the floor, having already been reported as not clearing what it never reached.
    held = _stub_pass()._replace(coverage=typecheck.Coverage(
        typecheck.RUFF_LOG, typecheck.RUFF_CHECKED, frozenset({"kept.py", "lost.py"})))
    short = _run_stub_checker(_logging_stub_body(0, "kept.py"), _STUB_PIN, [held])
    ensure(short.findings == 1 and short.out == [
        f"ok {_STUB_NAME}: clean",
        f"FAIL {_STUB_NAME}: 1 tracked module(s) {_STUB_NAME} did not check:",
        "       lost.py"], f"the run's shortfall reported as {short.out!r}")
    whole = _run_stub_checker(_logging_stub_body(0, "kept.py lost.py"), _STUB_PIN, [held])
    ensure(whole.findings == 0 and whole.out == [f"ok {_STUB_NAME}: clean"],
           f"a run logging every tracked module must pass: {whole.out!r}")
    crashed = _run_stub_checker(_logging_stub_body(5, "kept.py", "the checker panicked"),
                                _STUB_PIN, [held])
    joined = "\n".join(crashed.out)
    ensure(crashed.findings == 1
           and f"{_STUB_NAME} exited 5: the checker panicked" in joined
           and "did not check" not in joined,
           f"a crash must quote its own message and not be held to the floor: {crashed.out!r}")


def _module_tree(tools: Path, modules: list[str]) -> None:
    """Each module in `modules` under `tools`, holding one annotated line."""
    for module in modules:
        path = tools / module
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("count: int = 1\n", encoding="utf-8", newline="")


def _ruff_coverage_floor() -> None:
    # The real ruff under ruff.toml settings that each take a tracked module out of
    # the lint with nothing reported: a directory ruff skips by default, an
    # extend-exclude, a lint.exclude, which `--show-files` still lists, and an exclude,
    # which replaces the defaults and so brings the default-skipped module back. Each
    # exclusion key is refused as one the gate has not read, and beside that refusal
    # each module dropped is a finding under ruff; the ones every setting leaves are not.
    modules = ["kept.py", "stub.pyi", "dist/mod.py", "extended.py", "linted.py",
               "replaced.py"]
    for config, refused, missing in (
            ('extend-exclude = ["extended.py"]\n[lint]\nselect = ["ANN"]\n'
             'exclude = ["linted.py"]\n', 2, ["dist/mod.py", "extended.py", "linted.py"]),
            ('exclude = ["replaced.py"]\n[lint]\nselect = ["ANN"]\n', 1, ["replaced.py"])):
        rep = Reporter()
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            root = Path(td)
            _module_tree(root / "tools", modules)
            (root / "tools" / "ruff.toml").write_text(config, encoding="utf-8", newline="")
            typecheck._run_ruff(rep, root, frozenset(modules))
        ensure(rep.findings == refused + len(missing)
               and rep.out[0] == f"FAIL ruff: {refused} ruff.toml setting(s) the gate refuses:"
               and rep.out[1 + refused].startswith("ok ruff:")
               and rep.out[2 + refused:] == [f"FAIL ruff: {len(missing)} tracked module(s) "
                                             "ruff did not check:",
                                             *(f"       {m}" for m in missing)],
               f"ruff must report each module {config!r} drops: {rep.out!r}")
    with patch.object(typecheck, "_run_checker") as unheld:
        typecheck._run_ruff(Reporter(), Path.cwd(), None)
    ensure(all(run.coverage is None and not set(typecheck.RUFF_VERBOSE) & set(run.args)
               for run in cast("list[typecheck.Pass]", unheld.call_args.args[3])),
           "a ruff pass held to nothing must not turn its log on")


def _ty_coverage_floor() -> None:
    # The real ty, under the ty.toml the gate admits, over modules in two directories
    # ty skips by default: each platform's run reports both under ty, and not the
    # modules beside them.
    modules = ["kept.py", "stub.pyi", "dist/mod.py", "node_modules/mod.py"]
    rep = Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        _module_tree(root / "tools", modules)
        (root / "tools" / "ty.toml").write_text(_ADMITTED, encoding="utf-8", newline="")
        with patch.dict(os.environ), \
                patch.object(typecheck, "_user_config", return_value=None):
            os.environ.pop("PYTHONPATH", None)
            typecheck._run_ty(rep, root, frozenset(modules))
    for platform in typecheck.TY_PLATFORMS:
        header = (f"FAIL ty: 2 tracked module(s) ty under python-platform {platform} did "
                  "not check:")
        ensure(header in rep.out
               and rep.out[rep.out.index(header) + 1:rep.out.index(header) + 3]
               == ["       dist/mod.py", "       node_modules/mod.py"],
               f"the {platform} run must report each default-skipped module: {rep.out!r}")
    ensure(rep.findings == 2 * len(typecheck.TY_PLATFORMS),
           f"only the skipped modules may be findings: {rep.out!r}")


def _ruff_settings(text: str | None) -> list[str]:
    """`_ruff_settings` over a ruff.toml holding `text`, or over none at all."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        config = Path(td) / "ruff.toml"
        if text is not None:
            config.write_text(text, encoding="utf-8", newline="")
        return typecheck._ruff_settings(config)


def _ruff_settings_refuse_per_file_suppressions() -> None:
    # Each key that switches rules off for the files a pattern matches is refused in
    # [lint] and at the top level, as a table or inline, empty or not, and so is an
    # extend, which merges a file the gate does not read; one key is one finding.
    committed = Path(typecheck.__file__).resolve().parents[2] / "ruff.toml"
    ensure(typecheck._ruff_settings(committed) == [],
           f"the committed ruff.toml must pass: {typecheck._ruff_settings(committed)!r}")
    # The keys the gate admits are exactly the ones the committed file carries.
    carried = {path for path, _ in typecheck._ruff_keys(
        tomllib.loads(committed.read_text(encoding="utf-8")), "")}
    ensure(carried == typecheck.RUFF_KEYS,
           f"RUFF_KEYS must be the committed ruff.toml's keys: "
           f"{sorted(carried ^ typecheck.RUFF_KEYS)!r}")
    lint = '[lint]\nselect = ["ANN"]\n'
    ensure(_ruff_settings(lint) == [], "a ruff.toml without per-file suppressions must pass")
    for text, expected in (
            (lint + 'per-file-ignores = {"x.py" = ["ALL"]}\n',
             "sets lint.per-file-ignores to {'x.py': ['ALL']};"),
            (lint + '[lint.per-file-ignores]\n"x.py" = ["ANN"]\n',
             "sets lint.per-file-ignores to {'x.py': ['ANN']};"),
            (lint + 'extend-per-file-ignores = {}\n',
             "sets lint.extend-per-file-ignores to {};"),
            ('per-file-ignores = {"x.py" = ["ANN"]}\n' + lint,
             "sets per-file-ignores to {'x.py': ['ANN']};"),
            ('extend-per-file-ignores = {"x.py" = ["ANN"]}\n' + lint,
             "sets extend-per-file-ignores to {'x.py': ['ANN']};")):
        found = _ruff_settings(text)
        ensure(len(found) == 1 and expected in found[0]
               and "since ruff's log names a file whose rules are off as checked" in found[0],
               f"a per-file suppression must be one finding: {found!r}")
    extended = _ruff_settings('extend = "other.toml"\n' + lint)
    ensure(len(extended) == 1 and "sets extend to 'other.toml';" in extended[0],
           f"an extend must be refused: {extended!r}")
    both = _ruff_settings('per-file-ignores = {}\n' + lint + 'per-file-ignores = {}\n')
    ensure(len(both) == 2, f"each table's key must be its own finding: {both!r}")
    # Any other key the gate has not read is refused at any depth of the tables it
    # admits, one finding per key and one for a table it does not admit: the per-file
    # target version, which switches version-gated rules off for the files it matches,
    # an exclusion, and a key the gate has never seen.
    for text, expected in (
            ('per-file-target-version = {"x.py" = "py37"}\n' + lint,
             "sets per-file-target-version to {'x.py': 'py37'}, a key the gate has not read;"),
            ('exclude = ["x.py"]\n' + lint, "sets exclude to ['x.py'], a key"),
            ('future-setting = 1\n' + lint, "sets future-setting to 1, a key"),
            (lint + 'future-setting = 1\n', "sets lint.future-setting to 1, a key"),
            (lint + '[lint.flake8-annotations]\nignore-fully-untyped = true\n',
             "sets lint.flake8-annotations.ignore-fully-untyped to True, a key"),
            (lint + '[lint.isort]\nforce-single-line = true\nknown-first-party = ["vos"]\n',
             "sets lint.isort to {'force-single-line': True, 'known-first-party': ['vos']}, "
             "a key")):
        found = _ruff_settings(text)
        ensure(len(found) == 1 and expected in found[0]
               and "it admits only the keys in RUFF_KEYS" in found[0],
               f"a key the gate has not read must be one finding: {found!r}")
    for text in (None, "[lint\n"):
        unread = _ruff_settings(text)
        ensure(len(unread) == 1 and "cannot be read" in unread[0],
               f"an absent or malformed ruff.toml must be a finding: {unread!r}")


def _file_suppressions_refused() -> None:
    # Each comment ruff reads as a file-level suppression, in any of ruff's spellings
    # and wherever it sits, is refused unless it names only N999, and so is one after
    # trailing code, which ruff ignores. Each comment of a range is refused too: both
    # ends of a pair at module level or in a class body, a disable with no enable, which
    # runs to the end of its block, and one spaced as ruff still reads it; and so are a
    # file-ignore and isort's skip_file and off, a trailing skip_file among them, which
    # ruff reads wherever it sits. A string spelling either, a spelling ruff does not
    # read, and a suppression reaching one line are not refused.
    refused = {
        "codes.py": "# ruff: noqa: ANN001\n",
        "flake8.py": "# flake8: noqa: ANN001,ANN201\n",
        "cased.py": "#ruff:NOQA:ANN001 ANN201\n",
        "blanket.py": "x = 1\n# ruff: noqa\n",
        "second.py": "# a note # ruff: noqa: ANN001\n",
        "indented.py": "if True:\n    pass\n    # ruff: noqa: ANN001\n",
        "trailing.py": "x = 1  # ruff: noqa: ANN001\n",
        "beside.py": "# ruff: noqa: N999, ANN001\n",
        "joined.py": "# ruff: noqa:N999ANN001\n",
        "twice.py": "# ruff: noqa: N999 # ruff: noqa: ANN001\n",
        "pair.py": "# ruff: disable[ANN001]\nx = 1\n# ruff: enable[ANN001]\n",
        "unmatched.py": "# ruff: disable[ANN001]\ndef f(x):\n    return x\n",
        "spaced.py": "#  ruff :  disable [ANN001]\n",
        "classrange.py": "class C:\n    # ruff: disable[ANN001]\n    x = 1\n"
                         "    # ruff: enable[ANN001]\n",
        "fileignore.py": "x = 1\n# ruff: file-ignore[ANN001]\n",
        "skipfile.py": "import os  # isort: skip_file\n",
        "isortoff.py": "# ruff: isort: off\nimport os\n",
    }
    admitted = {
        "named.py": "#!/usr/bin/env python3\n# ruff: noqa: N999\n# the name has a hyphen\n",
        "reason.py": "# ruff: noqa: N999 because the command's name has a hyphen\n",
        "string.py": 'TEXT = "# ruff: noqa: ANN001"\n',
        "docstring.py": '"""The gate refuses\n# ruff: noqa: ANN001\n"""\n',
        "upper.py": "# RUFF: noqa: ANN001\n",
        "line.py": "x = 1  # noqa: ANN001\n",
        "rangestring.py": 'TEXT = "# ruff: disable[ANN001]"\n',
        "capital.py": "# ruff: Disable[ANN001]\n",
        "ignore.py": "# ruff: ignore[ANN001]\n",
        "isortskip.py": "import os  # isort: skip\n",
    }
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        _write_tools(Path(td), {**refused, **admitted}, None)
        found = typecheck._file_suppressions(Path(td) / "tools",
                                             frozenset({**refused, **admitted}))
    ensure(found == ["beside.py:1 # ruff: noqa: N999, ANN001", "blanket.py:2 # ruff: noqa",
                     "cased.py:1 #ruff:NOQA:ANN001 ANN201",
                     "classrange.py:2 # ruff: disable[ANN001]",
                     "classrange.py:4 # ruff: enable[ANN001]",
                     "codes.py:1 # ruff: noqa: ANN001",
                     "fileignore.py:2 # ruff: file-ignore[ANN001]",
                     "flake8.py:1 # flake8: noqa: ANN001,ANN201",
                     "indented.py:3 # ruff: noqa: ANN001", "isortoff.py:1 # ruff: isort: off",
                     "joined.py:1 # ruff: noqa:N999ANN001",
                     "pair.py:1 # ruff: disable[ANN001]", "pair.py:3 # ruff: enable[ANN001]",
                     "second.py:1 # a note # ruff: noqa: ANN001",
                     "skipfile.py:1 # isort: skip_file", "spaced.py:1 #  ruff :  disable [ANN001]",
                     "trailing.py:1 # ruff: noqa: ANN001",
                     "twice.py:1 # ruff: noqa: N999 # ruff: noqa: ANN001",
                     "unmatched.py:1 # ruff: disable[ANN001]"],
           f"each suppression reaching past a line but N999 must be refused: {found!r}")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        _write_tools(Path(td), {"open.py": '# ruff: noqa: ANN001\nTEXT = """\n'}, None)
        (Path(td) / "tools" / "latin.py").write_bytes(b"# \xe9\n")
        failed = typecheck._file_suppressions(Path(td) / "tools",
                                              frozenset({"open.py", "latin.py"}))
    ensure(len(failed) == 2 and failed[0].startswith("latin.py cannot be read: ")
           and failed[1].startswith("open.py cannot be tokenized: "),
           f"a module that cannot be read or tokenized must be refused: {failed!r}")


def _suppressions_reported_beside_the_run() -> None:
    # The real ruff under a per-file-ignores entry, a file-level directive, a range
    # spanning the module and a file-ignore, each switching ANN off for a module with an
    # unannotated function: ruff reports nothing and its log names the module as
    # checked, so the floor alone passes, and the refusal is what fails the gate, one
    # finding per refused key or comment; the run's verdict then claims no more than it
    # showed. Without a suppression ruff reports the function.
    body = "def f(x):\n    return x\n"
    lint = '[lint]\nselect = ["ANN"]\n'
    comments = "file-level or range suppression(s) the gate refuses:"
    for config, text, refusal, count in (
            (lint, body, None, 0),
            (lint + 'per-file-ignores = {"x.py" = ["ANN"]}\n', body,
             "ruff.toml setting(s) the gate refuses:", 1),
            (lint, "# ruff: noqa: ANN001, ANN201\n" + body, comments, 1),
            (lint, "# ruff: disable[ANN001, ANN201]\n" + body
             + "# ruff: enable[ANN001, ANN201]\n", comments, 2),
            (lint, "# ruff: file-ignore[ANN001, ANN201]\n" + body, comments, 1)):
        rep = Reporter()
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            _write_tools(Path(td), {"x.py": text}, config)
            typecheck._run_ruff(rep, Path(td), frozenset({"x.py"}))
        if refusal is None:
            ensure(rep.findings == 2 and "ANN001: 1" in "\n".join(rep.out),
                   f"without a suppression ruff must report the function: {rep.out!r}")
            continue
        ensure(rep.findings == count and rep.out[0] == f"FAIL ruff: {count} {refusal}"
               and rep.out[1 + count:] == [(f"ok ruff: every function is annotated and "
                                            f"ruff {typecheck.RUFF_VERSION} is clean under "
                                            "the suppressions refused above")],
               f"a suppression must be the one refusal beside a clean run: {rep.out!r}")


def _ty_log_variables_removed() -> None:
    # The real ty with TY_LOG and TY_LOG_PROFILE set in the gate's environment. ty takes
    # TY_LOG ahead of -vv, so a run inheriting TY_LOG=info logs no checked file and every
    # tracked module reads as unchecked, which the control shows by running with the
    # removal switched off; the gate's own runs reach every module and leave no profile.
    modules = ["kept.py", "sub/stub.pyi"]
    for removed in (True, False):
        rep = Reporter()
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            root = Path(td)
            _module_tree(root / "tools", modules)
            (root / "tools" / "ty.toml").write_text(_ADMITTED, encoding="utf-8", newline="")
            with patch.dict(os.environ, {"TY_LOG": "info", "TY_LOG_PROFILE": "1"}), \
                    patch.object(typecheck, "_user_config", return_value=None), \
                    patch.object(typecheck, "TY_UNSET",
                                 typecheck.TY_UNSET if removed else frozenset()):
                os.environ.pop("PYTHONPATH", None)
                typecheck._run_ty(rep, root, frozenset(modules))
            profiled = sorted(path.name for path in (root / "tools").iterdir()
                              if path.name not in {"ty.toml", "kept.py", "sub"})
        unchecked = [line for line in rep.out if "did not check" in line]
        if removed:
            ensure(rep.findings == 0 and not unchecked and not profiled
                   and rep.out == [f"ok ty: every expression reachable under python-platform "
                                   f"{platform} typechecks under ty {typecheck.TY_VERSION}, "
                                   "all rules at error" for platform in typecheck.TY_PLATFORMS],
                   f"a run under TY_LOG must still reach every module: {rep.out!r} {profiled!r}")
        else:
            ensure(len(unchecked) == len(typecheck.TY_PLATFORMS)
                   and rep.findings == len(modules) * len(typecheck.TY_PLATFORMS)
                   and profiled == ["tracing.folded"],
                   f"the control must show TY_LOG hiding the log and TY_LOG_PROFILE "
                   f"writing a profile: {rep.out!r} {profiled!r}")


# A ruff.toml banning two modules at module level, one of them dotted.
_BANNING = ('[lint.flake8-tidy-imports]\n'
            'banned-module-level-imports = ["fcntl", "asyncio.unix_events"]\n')
_SCAN_OK = ("ok imports: every import of a module ruff.toml bans at module level sits in a "
            "function body or behind a sys.platform check")
_SCAN_FAIL = ("import(s) of a module ruff.toml bans at module level outside a function "
              "body:")


def _write_tools(root: Path, modules: dict[str, str], config: str | None) -> None:
    """A tools tree under `root` holding `modules`, under a ruff.toml holding `config`,
    or none at all."""
    tools = root / "tools"
    tools.mkdir()
    if config is not None:
        (tools / "ruff.toml").write_text(config, encoding="utf-8", newline="")
    for name, text in modules.items():
        path = tools / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")


def _scan(modules: dict[str, str], config: str | None = _BANNING) -> Reporter:
    """`_run_imports` over a tools tree holding `modules`, each tracked."""
    rep = Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        _write_tools(Path(td), modules, config)
        typecheck._run_imports(rep, Path(td), frozenset(modules))
    return rep


def _refused(site: str, names: str = "fcntl") -> str:
    return (f"       {site} imports {names} outside a function body, behind no sys.platform "
            "check")


def _imports_refused_outside_functions() -> None:
    # An import of a banned module, or of a banned submodule by its parent, that runs
    # outside a function body is refused wherever it sits: unnested at module level, in
    # a class body at any depth, and in a module-level block such as the main guard.
    refused = {
        "toplevel.py": "import os, fcntl\n",
        "classbody.py": "class Locks:\n    import fcntl\n",
        "nested.py": "class Outer:\n    class Inner:\n        import fcntl\n",
        "moduleif.py": "import os\n\nif os.name == 'posix':\n    import fcntl\n",
        "mainblock.py": "if __name__ == '__main__':\n    import fcntl\n",
        "tryblock.py": "try:\n    from fcntl import flock\nexcept ImportError:\n    pass\n",
        "member.py": "class Loop:\n    from asyncio import events, unix_events\n",
        "dotted.py": "with open(__file__):\n    import asyncio.unix_events as ue\n",
    }
    rep = _scan(refused)
    ensure(rep.findings == len(refused) and rep.out == [
        f"FAIL imports: {len(refused)} {_SCAN_FAIL}",
        _refused("classbody.py:2"), _refused("dotted.py:2", "asyncio.unix_events"),
        _refused("mainblock.py:2"), _refused("member.py:2", "asyncio.unix_events"),
        _refused("moduleif.py:4"), _refused("nested.py:3"), _refused("toplevel.py:1"),
        _refused("tryblock.py:2")], f"each import outside a function body must be refused: "
                                    f"{rep.out!r}")


def _imports_admitted_in_functions_and_platform_blocks() -> None:
    # A function body runs only when called, and an if reading sys.platform keeps both
    # its branches off the platform its test excludes, at module level or in a class
    # body. A name that only begins like a banned one, a banned module's parent, a
    # relative import and a string are none of them an import of a banned module.
    admitted = {
        "function.py": "def lock() -> None:\n    import fcntl\n",
        "coroutine.py": "async def lock() -> None:\n    from fcntl import flock\n",
        "method.py": "class Locks:\n    def lock(self) -> None:\n        import fcntl\n",
        "classinfunction.py": "def make() -> None:\n    class Locks:\n        import fcntl\n",
        "platformif.py": "import sys\n\nif sys.platform != 'win32':\n    import fcntl\n",
        "platformelse.py": ("import sys\n\nif sys.platform == 'win32':\n    pass\n"
                            "elif __name__ == '__main__':\n    import fcntl\n"),
        "platformclass.py": ("import sys\n\nclass Locks:\n    if sys.platform != 'win32':\n"
                             "        import fcntl\n"),
        "unrelated.py": ("import asyncio\nimport fcntlx\nfrom asyncio import events\n"
                         "from . import fcntl\nTEXT = 'import fcntl'\n"),
    }
    rep = _scan(admitted)
    ensure(rep.findings == 0 and rep.out == [_SCAN_OK],
           f"an import in a function body or behind sys.platform must be admitted: {rep.out!r}")


def _imports_fail_closed() -> None:
    # A ruff.toml the scan cannot read a non-empty list of module names from is one
    # finding and scans nothing; a module that spells a banned name and cannot be read
    # or parsed is a finding. A module spelling no banned name is not parsed, its syntax
    # being ruff's E9 finding.
    for config, expected in ((None, "cannot be read"),
                             ('[lint\n', "cannot be read"),
                             ('[lint]\nselect = ["ANN"]\n', "to None;"),
                             ('[lint]\nflake8-tidy-imports = 1\n', "to None;"),
                             ('[lint.flake8-tidy-imports]\nbanned-module-level-imports = []\n',
                              "to [];"),
                             ('[lint.flake8-tidy-imports]\n'
                              'banned-module-level-imports = ["fcntl", 1]\n', "to ['fcntl', 1];"),
                             ('[lint.flake8-tidy-imports]\n'
                              'banned-module-level-imports = ["fcntl", ""]\n', "to ['fcntl', ''];")):
        rep = _scan({"classbody.py": "class Locks:\n    import fcntl\n"}, config)
        ensure(rep.findings == 1 and rep.out[0] == "FAIL imports: 1 ruff.toml list(s) the gate "
                                                   "cannot read:" and expected in rep.out[1],
               f"a ruff.toml without a list of module names must be one finding: {rep.out!r}")
    rep = _scan({"broken.py": "import fcntl\ndef (:\n", "quiet.py": "def (:\n"})
    ensure(rep.findings == 1 and rep.out[1].startswith("       broken.py cannot be parsed: "),
           f"a module spelling a banned name that cannot be parsed must be refused: {rep.out!r}")
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        _write_tools(Path(td), {}, _BANNING)
        (Path(td) / "tools" / "latin.py").write_bytes(b"# \xe9\nimport fcntl\n")
        unread = Reporter()
        typecheck._run_imports(unread, Path(td), frozenset({"latin.py"}))
    ensure(unread.findings == 1 and unread.out[1].startswith("       latin.py cannot be read: "),
           f"a module that cannot be read must be refused: {unread.out!r}")


def _imports_close_what_ruff_leaves_open() -> None:
    # The positive control. Under the committed ruff.toml, whose list the scan reads,
    # the real ruff reports TID253 for an unnested module-level import of a banned
    # module and nothing, neither TID253 nor PLC0415, for one in a class body, a
    # module-level block or the main guard; the scan refuses all four.
    committed = Path(typecheck.__file__).resolve().parents[2] / "ruff.toml"
    banned, unread = typecheck._banned(committed)
    ensure(not unread and {"fcntl", "curses", "readline", "nt", "_winapi"} <= banned,
           f"the committed ruff.toml must list the platform-only modules: {unread!r}")
    modules = {
        "toplevel.py": "import fcntl\n\nLOCK = fcntl.LOCK_EX\n",
        "classbody.py": "class Locks:\n    import fcntl\n\n    LOCK = fcntl.LOCK_EX\n",
        "moduleif.py": ('import os\n\nif os.name == "posix":\n    import fcntl\n\n'
                        '    LOCK = fcntl.LOCK_EX\n'),
        "mainblock.py": ('if __name__ == "__main__":\n    import fcntl\n\n'
                         '    fcntl.flock(0, fcntl.LOCK_EX)\n'),
    }
    config = committed.read_text(encoding="utf-8")
    lint, scan = Reporter(), Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        _write_tools(Path(td), modules, config)
        typecheck._run_ruff(lint, Path(td), frozenset(modules))
        typecheck._run_imports(scan, Path(td), frozenset(modules))
    codes = [line.strip() for line in lint.out if line.startswith("       ")
             and not line.startswith("         ")]
    banned_sites = [line.strip() for line in lint.out if "is banned at the module level" in line]
    ensure("TID253: 1" in codes and not any(code.startswith("PLC0415") for code in codes)
           and len(banned_sites) == 1 and banned_sites[0].startswith("toplevel.py:1:"),
           f"ruff must report only the unnested import: {lint.out!r}")
    ensure(scan.out == [f"FAIL imports: 4 {_SCAN_FAIL}", _refused("classbody.py:2"),
                        _refused("mainblock.py:2"), _refused("moduleif.py:4"),
                        _refused("toplevel.py:1")],
           f"the scan must refuse every import ruff leaves open: {scan.out!r}")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)


def _tracked_reads_the_index() -> None:
    # The index's Python sources and stubs under tools/, relative to it: not another
    # file there, not a module elsewhere, not an untracked module, and not a tracked
    # one the working tree has deleted.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        _git(root, "init", "--quiet")
        for name in ("tools/a.py", "tools/sub/b.pyi", "tools/notes.txt", "other/d.py",
                     "tools/gone.py", "tools/untracked.py"):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        _git(root, "add", "--", "tools/a.py", "tools/sub/b.pyi", "tools/notes.txt",
             "other/d.py", "tools/gone.py")
        (root / "tools" / "gone.py").unlink()
        found = typecheck._tracked(root)
    ensure(found == {"a.py", "sub/b.pyi"}, f"the tracked modules read as {sorted(found)!r}")


def _unreached(out: list[str]) -> list[str]:
    """Why a report of the gate's ty and ruff runs does not show every run reaching
    every tracked module: a line saying a run left a module unchecked, crashed, or never
    ran for want of the pinned checker, and each run giving no verdict line, since a
    run that never happened reports no module unchecked."""
    refusals = ("did not check", "checker error(s)", "not installed",
                "other than the pinned one")
    def ty_verdict(line: str, platform: str) -> bool:
        return (line.startswith(f"ok ty: every expression reachable under python-platform "
                                f"{platform} ")
                or (line.startswith("FAIL ty: ")
                    and line.endswith(f" type error(s) under python-platform {platform}:")))

    problems = [line for line in out if any(refusal in line for refusal in refusals)]
    problems.extend(f"no verdict from ty under python-platform {platform}"
                    for platform in typecheck.TY_PLATFORMS
                    if not any(ty_verdict(line, platform) for line in out))
    if not any(line.startswith("ok ruff: every function is annotated")
               or (line.startswith("FAIL ruff: ") and line.endswith(" lint finding(s):"))
               for line in out):
        problems.append("no verdict from ruff")
    return problems


def _live_runs(root: Path, tracked: frozenset[str]) -> Reporter:
    """The gate's ty runs and its ruff run over `root`, held to `tracked`."""
    rep = Reporter()
    typecheck._run_ty(rep, root, tracked)
    typecheck._run_ruff(rep, root, tracked)
    return rep


def _live_tree_reaches_every_tracked_module() -> None:
    # This checkout: the index's modules include this file and the gate's, and each of
    # the gate's ty runs and its ruff run gives a verdict and reaches every one of them.
    # The controls run the gate with its checker missing and with another version
    # installed: neither run happens, so neither reports a module unchecked, and each is
    # refused for the missing verdict and the pin gate's own line.
    root = Path(typecheck.__file__).resolve().parents[3]
    tracked = typecheck._tracked(root)
    ensure({"vos/cli/typecheck.py", "tests/test_typecheck.py"} <= tracked,
           f"the live index must track the gate and its tests: {len(tracked)} module(s)")
    rep = _live_runs(root, tracked)
    ensure(not _unreached(rep.out),
           f"the live tree must reach every module it tracks: {_unreached(rep.out)!r} "
           f"{rep.out!r}")
    for control, refusal in ((patch.object(typecheck, "_tool", return_value=None),
                              "not installed"),
                             (patch.object(typecheck, "_version", return_value="0.0.0"),
                              "other than the pinned one")):
        with control:
            missed = _unreached(_live_runs(root, tracked).out)
        ensure(any(refusal in line for line in missed)
               and "no verdict from ruff" in missed
               and all(f"no verdict from ty under python-platform {platform}" in missed
                       for platform in typecheck.TY_PLATFORMS),
               f"a run that never happened must not read as reaching the tree: {missed!r}")


def cases() -> list[Case]:
    return [
        Case("parse-ty", _parse_ty),
        Case("parse-ty-skips-summary", _parse_ty_skips_summary),
        Case("parse-ruff", _parse_ruff),
        Case("summarize-ordering", _summarize_ordering),
        Case("summarize-truncation", _summarize_truncation),
        Case("summarize-counts-findings", _summarize_counts_findings_not_lines),
        Case("environment-tool-resolution", _environment_tool_resolution),
        Case("version-probe", _version_probe, lane="host"),
        Case("crash-reported-beside-findings", _crash_reported_beside_findings, lane="host"),
        Case("crash-with-nothing-parsed", _crash_with_nothing_parsed, lane="host"),
        Case("ordinary-finding-exit", _ordinary_finding_exit, lane="host"),
        Case("failed-check-requires-a-diagnostic",
             _failed_check_requires_a_diagnostic, lane="host"),
        Case("pin-gate-refusals", _pin_gate_refusals, lane="host"),
        Case("passes-share-one-pin-probe", _passes_share_one_pin_probe, lane="host"),
        Case("ty-settings-admitted", _ty_settings_admitted),
        Case("ty-settings-refuse-rules", _ty_settings_refuse_rules),
        Case("ty-settings-refuse-overrides", _ty_settings_refuse_overrides),
        Case("ty-settings-refuse-analysis", _ty_settings_refuse_analysis),
        Case("ty-settings-refuse-environment", _ty_settings_refuse_environment),
        Case("ty-settings-refuse-src", _ty_settings_refuse_src),
        Case("ty-settings-fail-closed", _ty_settings_fail_closed),
        Case("ty-runs-every-platform", _ty_runs_every_platform),
        Case("win32-pass-types-host-branches", _win32_pass_types_host_branches),
        Case("ruff-checks-ignored-modules", _ruff_checks_ignored_modules),
        Case("ty-settings-reported-beside-the-run", _ty_settings_reported_beside_the_run),
        Case("user-config-located", _user_config_located),
        Case("user-config-reported-beside-the-run", _user_config_reported_beside_the_run),
        Case("pythonpath-reported-beside-the-run", _pythonpath_reported_beside_the_run),
        Case("read-log-separates-the-log", _read_log_separates_the_log),
        Case("cover-reports-what-the-log-missed", _cover_reports_what_the_log_missed),
        Case("coverage-read-from-the-run", _coverage_read_from_the_run, lane="host"),
        Case("ruff-coverage-floor", _ruff_coverage_floor),
        Case("ty-coverage-floor", _ty_coverage_floor),
        Case("ruff-settings-refuse-per-file-suppressions",
             _ruff_settings_refuse_per_file_suppressions),
        Case("file-suppressions-refused", _file_suppressions_refused),
        Case("suppressions-reported-beside-the-run", _suppressions_reported_beside_the_run),
        Case("ty-log-variables-removed", _ty_log_variables_removed),
        Case("imports-refused-outside-functions", _imports_refused_outside_functions),
        Case("imports-admitted-in-functions-and-platform-blocks",
             _imports_admitted_in_functions_and_platform_blocks),
        Case("imports-fail-closed", _imports_fail_closed),
        Case("imports-close-what-ruff-leaves-open", _imports_close_what_ruff_leaves_open),
        Case("tracked-reads-the-index", _tracked_reads_the_index),
        Case("live-tree-reaches-every-tracked-module", _live_tree_reaches_every_tracked_module),
    ]
