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
"""

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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


def _run_stub_checker(body: str, pin: str) -> Reporter:
    """One `_run_checker` pass routed at a stub, so the pin gate, the run,
    the parse and the verdict are all the real code's."""
    rep = Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        directory = Path(td)
        stub = _stub(directory, _STUB_NAME, body)
        with patch.object(typecheck, "_tool", return_value=str(stub)):
            typecheck._run_checker(
                rep, _STUB_NAME, pin, ["check"], directory, with_stderr=False,
                parse=typecheck._parse_ruff, label="lint finding(s):", ok="clean")
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
        absent, "vostest-absent-tool", "1.0.0", ["check"], Path.cwd(),
        with_stderr=False, parse=typecheck._parse_ruff, label="lint finding(s):",
        ok="clean")
    ensure("not installed:" in "\n".join(absent.out)
            and "synchronize tools/uv.lock" in "\n".join(absent.out),
           f"an absent tool must name the uv remedy, got {absent.out!r}")


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


def _ty_settings_reported_beside_the_run() -> None:
    # The refusal is a ty finding in the gate's own report, and the checker still runs.
    for text, refused in ((_ADMITTED, False), ('[rules]\nall = "warn"\n' + _HELD, True)):
        rep = Reporter()
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            root = Path(td)
            (root / "tools").mkdir()
            (root / "tools" / "ty.toml").write_text(text, encoding="utf-8", newline="")
            with patch.object(typecheck, "_run_checker") as checker, \
                    patch.object(typecheck, "_user_config", return_value=None):
                typecheck._run_ty(rep, root)
        ensure(checker.call_count == 1, "the checker must run whatever the settings say")
        joined = "\n".join(rep.out)
        claims = str(checker.call_args.kwargs["ok"]).endswith("all rules at error")
        if refused:
            ensure(rep.findings == 1
                   and "FAIL ty: 1 ty.toml setting(s) the gate refuses:" in joined,
                   f"a refused setting must fail the gate under ty: {rep.out!r}")
            ensure(not claims, "a clean run beside refused settings must not claim "
                               "every rule ran at error")
        else:
            ensure(rep.findings == 0 and rep.out == [],
                   f"an admitted ty.toml must add nothing to the report: {rep.out!r}")
            ensure(claims, "a clean run under admitted settings claims every rule at error")


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
                typecheck._run_ty(rep, root)
        ensure(checker.call_count == 1, "the checker must run whatever the settings say")
        joined = "\n".join(rep.out)
        claims = str(checker.call_args.kwargs["ok"]).endswith("all rules at error")
        if present:
            ensure(rep.findings == 1
                   and "FAIL ty: 1 user-level configuration(s) the gate refuses:" in joined
                   and f"a user-level ty configuration at {user} merges into the gate's "
                       "run" in joined,
                   f"a user-level ty.toml must be a ty finding naming it: {rep.out!r}")
            ensure(not claims, "a run beside a user-level ty.toml must not claim every "
                               "rule ran at error")
        else:
            ensure(rep.findings == 0 and rep.out == [] and claims,
                   f"an empty user configuration directory must add nothing: {rep.out!r}")


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
        Case("ty-settings-admitted", _ty_settings_admitted),
        Case("ty-settings-refuse-rules", _ty_settings_refuse_rules),
        Case("ty-settings-refuse-overrides", _ty_settings_refuse_overrides),
        Case("ty-settings-refuse-analysis", _ty_settings_refuse_analysis),
        Case("ty-settings-refuse-environment", _ty_settings_refuse_environment),
        Case("ty-settings-refuse-src", _ty_settings_refuse_src),
        Case("ty-settings-fail-closed", _ty_settings_fail_closed),
        Case("ty-settings-reported-beside-the-run", _ty_settings_reported_beside_the_run),
        Case("user-config-located", _user_config_located),
        Case("user-config-reported-beside-the-run", _user_config_reported_beside_the_run),
    ]
