# SPDX-License-Identifier: Apache-2.0
"""The type gate's bounded execution, structured policy and coverage controls.

Configuration fixtures preserve reviewed acceptance and refusal cases while
schemas own shape decisions and diagnostic wording. The remaining controls hold
explicit filename coverage, suppression scope and platform-import behavior.
"""

import json
import os
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

from tests.harness import Case, ensure
from vos.cli import typecheck
from vos.report import Reporter

# Each case writes its fixtures only under directories it creates and patches only
# inside a `with`, so the cases share no state, and a sharded run spreads them over
# every shard (vos/cli/test.py).
INDEPENDENT_CASES = True

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
    """`_settings` over a ty.toml holding `text`, or over none at all."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        config = Path(td) / "ty.toml"
        if text is not None:
            config.write_text(text, encoding="utf-8", newline="")
        return typecheck._settings(config)


def _ty_settings_admitted() -> None:
    ensure(typecheck._settings(_TY_TOML) == [],
           f"the committed ty.toml must pass its own gate: {typecheck._settings(_TY_TOML)!r}")
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
                 _ADMITTED + '\n[analysis]\n'):
        ensure(_settings(text) == [], f"an admissible ty.toml was refused: {text!r}")


def _refused_settings(fixtures: list[str | None], policy: str = "ty") -> None:
    for text in fixtures:
        found = _settings(text) if policy == "ty" else _ruff_settings(text)
        ensure(bool(found) and all(f"{policy}.toml" in line for line in found),
               f"the {policy} policy admitted a refused setting: {text!r}; {found!r}")


def _ty_settings_refuse_rules() -> None:
    _refused_settings([_HELD, '[rules]\nall = "warn"\n' + _HELD,
                       *(_ALL_ERROR + f'unresolved-import = "{severity}"\n' + _HELD
                         for severity in ("ignore", "error"))])


def _ty_settings_refuse_overrides() -> None:
    first = '\n[[overrides]]\ninclude = ["vos/**"]\n'
    second = '\n[[overrides]]\ninclude = ["tests/**"]\n'
    rules = '\n[overrides.rules]\nunresolved-import = "ignore"\n'
    _refused_settings([
        _ADMITTED + first + second + rules,
        _ADMITTED + first + '\n[overrides.rules]\nall = "error"\n',
        *(_ADMITTED + first + f'\n[overrides.analysis]\n{key} = {value}\n'
          for key, value in (("allowed-unresolved-imports", '["x.**"]'),
                             ("replace-imports-with-any", '["x.**"]'),
                             ("strict-generic-narrowing", "true"))),
        _ADMITTED + first + 'future-setting = 1\n',
        _ADMITTED + first + '\n[overrides.rules]\nall = "error"\n'
                  '\n[overrides.analysis]\nallowed-unresolved-imports = ["x.**"]\n',
        'overrides = "tests"\n' + _ADMITTED,
        _ADMITTED + '\n[overrides]\ninclude = ["tests/**"]\n',
        '[rules]\nall = "warn"\n' + _HELD + first + second + rules])


def _ty_settings_refuse_analysis() -> None:
    _refused_settings([
        *(_ADMITTED + '\n[analysis]\n' + line + '\n' for line in (
            'allowed-unresolved-imports = ["x.**"]', 'allowed-unresolved-imports = []',
            'replace-imports-with-any = ["x.**"]', 'future-setting = true')),
        _ADMITTED + '\n[analysis]\nstrict-equality-semantics = true\n'
                  'replace-imports-with-any = ["y"]\nallowed-unresolved-imports = ["x"]\n',
        'analysis = "none"\n' + _ADMITTED])


def _ty_settings_refuse_environment() -> None:
    _refused_settings([
        *(_ALL_ERROR + _ENV + line + '\n' + _SRC for line in (
            'typeshed = "stubs"', 'root = ["src"]', 'python = ".venv"',
            'future-setting = 1', 'python-version = "3.12"')),
        *(_ALL_ERROR + '\n[environment]\n' + body + _SRC for body in (
            'python-platform = "win32"\nextra-paths = ["."]\n',
            'python-platform = "all"\nextra-paths = ["."]\n',
            'python-platform = "linux"\nextra-paths = [".", "stubs"]\n',
            'python-platform = "linux"\nextra-paths = []\n', 'extra-paths = ["."]\n', '',
            'python-platform = "win32"\nextra-paths = ["stubs"]\n',
            'python-platform = "win32"\nextra-paths = ["."]\ntypeshed = "stubs"\n')),
        _ALL_ERROR + _SRC, 'environment = "linux"\n' + _ALL_ERROR + _SRC])


def _ty_settings_refuse_src() -> None:
    head = _ALL_ERROR + _ENV
    _refused_settings([
        head, head + '\n[src]\n',
        *(head + '\n[src]\nexclude = ' + exclude + '\nrespect-ignore-files = false\n'
          for exclude in ('["**/__pycache__/**", "vos/**"]', '["vos/**"]')),
        *(head + _SRC + line + '\n' for line in (
            'include = ["tests"]', 'exclude-scripts = true')),
        head + '\n[src]\nexclude = ["**/__pycache__/**"]\nrespect-ignore-files = true\n',
        head + '\n[src]\nexclude = ["**/__pycache__/**"]\n',
        head + '\n[src]\nrespect-ignore-files = false\n'])


def _ty_settings_fail_closed() -> None:
    _refused_settings([None, '[rules\nall = "error"\n',
                       'baseline = "baseline.json"\n' + _ADMITTED,
                       'future-setting = true\n' + _ADMITTED])


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
    ensure(typecheck.TY_PLATFORMS == ("linux", "win32"),
           "the gate must retain its Linux and Windows platform passes")
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
    ensure(all(run.targets is None for run in _passes(unheld)),
           f"an unspecified inventory remains unspecified: {_passes(unheld)!r}")
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
        ensure(run.targets == {"kept.py"} and "." not in run.args
               and run.args[run.args.index("--python-version") + 1] == typecheck.PYTHON_VERSION,
               f"the {platform} pass must name its indexed input files: {run!r}")
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


def _explicit_commands_are_bounded() -> None:
    targets = frozenset({"dist/a.py", "two words.py", "long-" + "x" * 45 + ".py",
                         "unicode-\U0001f642.py", "nested/stub.pyi"})
    exe, args = "C:/tools/checker.exe", ["check", "--no-force-exclude"]
    with patch.object(typecheck, "COMMAND_LIMIT", 125):
        commands = list(typecheck._target_commands(exe, args, targets))
    base = [exe, *args, "--"]
    ensure(len(commands) > 1 and all(command[:len(base)] == base for command in commands),
           f"every bounded batch retains the executable, options and option terminator: {commands!r}")
    ensure([name for command in commands for name in command[len(base):]] == sorted(targets)
           and all(len(subprocess.list2cmdline(command).encode("utf-16-le")) <= 250
                   for command in commands),
           f"every filename appears once and Windows' quoted UTF-16 limit holds: {commands!r}")
    for bad in (frozenset(), frozenset({"x" * typecheck.COMMAND_LIMIT})):
        try:
            list(typecheck._target_commands(exe, args, bad))
        except ValueError:
            pass
        else:
            ensure(False, "empty inputs and unrepresentable command arguments must refuse")


def _batches_share_one_verdict() -> None:
    rep = Reporter()
    run = _stub_pass()._replace(targets=frozenset({"a.py", "b.py"}))
    commands = [["stub", "a.py"], ["stub", "b.py"]]
    outcomes = [subprocess.CompletedProcess(commands[0], 1,
                                           "a.py:1:1: ANN001 first\n", ""),
                subprocess.CompletedProcess(commands[1], 1,
                                           "b.py:1:1: ANN001 second\n", "")]
    with patch.object(typecheck, "_target_commands", return_value=iter(commands)), \
            patch.object(typecheck.subprocess, "run", side_effect=outcomes), \
            patch.object(Path, "is_file", return_value=True):
        typecheck._run_pass(rep, "stub", "stub", run, Path.cwd(), False,
                            typecheck._parse_ruff)
    ensure(rep.findings == 2 and sum(line.startswith("FAIL stub:") for line in rep.out) == 1
           and "       ANN001: 2" in rep.out,
           f"batch findings form one combined verdict: {rep.out!r}")
    crashed = Reporter()
    outcomes[1] = subprocess.CompletedProcess(commands[1], 5, "", "checker panicked")
    with patch.object(typecheck, "_target_commands", return_value=iter(commands)), \
            patch.object(typecheck.subprocess, "run", side_effect=outcomes), \
            patch.object(Path, "is_file", return_value=True):
        typecheck._run_pass(crashed, "stub", "stub", run, Path.cwd(), False,
                            typecheck._parse_ruff)
    ensure(crashed.findings == 2 and any("exited 5" in line for line in crashed.out)
           and any("first" in line for line in crashed.out)
           and not any(line.startswith("ok ") for line in crashed.out),
           f"a failed batch refuses the pass beside findings from another: {crashed.out!r}")


def _module_tree(tools: Path, modules: list[str]) -> None:
    """Each module in `modules` under `tools`, holding one annotated line."""
    for module in modules:
        path = tools / module
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("count: int = 1\n", encoding="utf-8", newline="")


def _ruff_explicit_targets_bypass_exclusions() -> None:
    modules = ["kept.py", "stub.pyi", "dist/mod.py", "extended.py", "linted.py",
               "replaced.py"]
    for config, refused in (
            ('extend-exclude = ["extended.py"]\n[lint]\nselect = ["ANN"]\n'
             'exclude = ["linted.py"]\n', 2),
            ('exclude = ["replaced.py"]\nforce-exclude = true\n'
             '[lint]\nselect = ["ANN"]\n', 2)):
        rep = Reporter()
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            root = Path(td)
            _module_tree(root / "tools", modules)
            for module in modules:
                (root / "tools" / module).write_text("def f(x):\n    return x\n",
                                                     encoding="utf-8", newline="")
            (root / "tools" / "ruff.toml").write_text(config, encoding="utf-8", newline="")
            (root / "tools" / ".ignore").write_text("kept.py\n", encoding="utf-8", newline="")
            typecheck._run_ruff(rep, root, frozenset(modules))
        joined = "\n".join(rep.out).replace("\\", "/")
        ensure(rep.findings == refused + 2 * len(modules)
               and all(module + ":1:" in joined for module in modules),
               f"explicit filenames must bypass discovery and lint exclusions: {rep.out!r}")


def _ty_explicit_targets_bypass_exclusions() -> None:
    modules = ["kept.py", "stub.pyi", "dist/mod.py", "node_modules/mod.py"]
    rep = Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        _module_tree(root / "tools", modules)
        for module in modules:
            (root / "tools" / module).write_text('count: int = "one"\n',
                                                 encoding="utf-8", newline="")
        (root / "tools" / "ty.toml").write_text(_ADMITTED, encoding="utf-8", newline="")
        (root / "tools" / ".ignore").write_text("kept.py\n", encoding="utf-8", newline="")
        with patch.dict(os.environ), \
                patch.object(typecheck, "_user_config", return_value=None):
            os.environ.pop("PYTHONPATH", None)
            typecheck._run_ty(rep, root, frozenset(modules))
    joined = "\n".join(rep.out).replace("\\", "/")
    ensure(rep.findings == len(modules) * len(typecheck.TY_PLATFORMS)
           and all(joined.count(module + ":1:") == len(typecheck.TY_PLATFORMS)
                   for module in modules),
           f"both platforms must diagnose every explicit file: {rep.out!r}")


def _missing_explicit_inputs_refuse() -> None:
    for checker in (typecheck._run_ty, typecheck._run_ruff):
        rep = Reporter()
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            root = Path(td)
            tools = root / "tools"
            tools.mkdir()
            (tools / "ty.toml").write_text(_ADMITTED, encoding="utf-8", newline="")
            (tools / "ruff.toml").write_text('[lint]\nselect = ["ANN"]\n',
                                             encoding="utf-8", newline="")
            with patch.dict(os.environ), \
                    patch.object(typecheck, "_user_config", return_value=None):
                os.environ.pop("PYTHONPATH", None)
                checker(rep, root, frozenset({"missing.py"}))
        ensure(rep.findings > 0 and not any(line.startswith("ok ") for line in rep.out),
               f"an explicit file that disappears must refuse: {rep.out!r}")


def _ruff_settings(text: str | None) -> list[str]:
    """`_settings` over a ruff.toml holding `text`, or over none at all."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        config = Path(td) / "ruff.toml"
        if text is not None:
            config.write_text(text, encoding="utf-8", newline="")
        return typecheck._settings(config)


def _ruff_settings_refuse_per_file_suppressions() -> None:
    committed = Path(typecheck.__file__).resolve().parents[2] / "ruff.toml"
    ensure(typecheck._settings(committed) == [], "the committed Ruff settings must pass")
    lint = '[lint]\nselect = ["ANN"]\n'
    ensure(_ruff_settings(lint) == [], "a reviewed Ruff subset must pass")
    _refused_settings([
        *(lint + line + '\n' for line in (
            'per-file-ignores = {"x.py" = ["ALL"]}',
            '[lint.per-file-ignores]\n"x.py" = ["ANN"]',
            'extend-per-file-ignores = {}', 'future-setting = 1',
            '[lint.flake8-annotations]\nignore-fully-untyped = true',
            '[lint.isort]\nforce-single-line = true\nknown-first-party = ["vos"]')),
        *(line + '\n' + lint for line in (
            'per-file-ignores = {"x.py" = ["ANN"]}',
            'extend-per-file-ignores = {"x.py" = ["ANN"]}', 'extend = "other.toml"',
            'per-file-target-version = {"x.py" = "py37"}',
            'exclude = ["x.py"]', 'future-setting = 1')),
        'per-file-ignores = {}\n' + lint + 'per-file-ignores = {}\n',
        None, "[lint\n"], policy="ruff")


def _file_suppressions_refused() -> None:
    # Each comment ruff reads as a file-level suppression, in any of ruff's spellings
    # and wherever it sits, is refused unless it names only N999, and so is one after
    # trailing code, which ruff ignores. A code with no colon before it names nothing,
    # and ruff reads that directive as switching every rule off. Each comment of a range
    # is refused too: both ends of a pair at module level or in a class body, a disable
    # with no enable, which runs to the end of its block, and one spaced as ruff still
    # reads it; and so are a file-ignore and isort's skip_file and off, a trailing
    # skip_file among them, which ruff reads wherever it sits. A string spelling either, a
    # spelling ruff does not read, and a suppression reaching one logical line or one line
    # are not refused.
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
        "nocolon.py": "# ruff: noqa N999\n",
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
                     "joined.py:1 # ruff: noqa:N999ANN001", "nocolon.py:1 # ruff: noqa N999",
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


def _ruff_ignore_reaches_one_line() -> None:
    # The reading under which the gate admits ruff's `ignore[...]` comment, held against
    # the pinned ruff: on a line of its own it reaches the one logical line beneath it,
    # past blank and comment lines, a multi-line one whole, a compound statement's header
    # but not its block unless the block shares the header's line, a decorator but not
    # the definition beneath, and every statement a semicolon joins; inside brackets it
    # reaches the one line of code beneath it, past blank and comment lines, including
    # backslash and multi-line-string continuations; one ending a line reaches that same
    # code line alone. The module's E711 findings are what ruff leaves.
    text = "\n".join([
        "x = y = None",                          # 1
        "# ruff: ignore[E711]",                  # 2
        "",                                      # 3
        "# a comment between",                   # 4
        "a = (x == None,",                       # 5 reached, with 6
        "     y == None)",                       # 6
        "b = x == None",                         # 7
        "# ruff: ignore[E711]",                  # 8
        "if x == None:",                         # 9 reached, not its block
        "    c = y == None",                     # 10
        "# ruff: ignore[E711]",                  # 11
        "if x == None: d = y == None",           # 12 reached whole
        "# ruff: ignore[E711]",                  # 13
        "@print(x == None)",                     # 14 reached, not the definition
        "def f(e: object = y == None) -> None:",  # 15
        "    pass",                              # 16
        "g = (",                                 # 17
        "    # ruff: ignore[E711]",              # 18
        "    # a comment inside brackets",       # 19
        "",                                      # 20
        "    x == None,",                        # 21 reached, not 22
        "    y == None,",                        # 22
        ")",                                     # 23
        "h = (x == None,  # ruff: ignore[E711]",  # 24 reached, not 25
        "     y == None)",                       # 25
        "i = x == None or \\",                   # 26 joined to 27
        "    y == None  # ruff: ignore[E711]",   # 27
        "j = (x == None, '''",                   # 28 joined to 30
        "text",                                  # 29
        "''')  # ruff: ignore[E711]",            # 30
        "# ruff: ignore[E711]",                  # 31
        "k = x == None; m = y == None",          # 32 reached, both statements
        "n = x == None",                         # 33
        "o = (",                                 # 34
        "    # ruff: ignore[E711]",              # 35
        "    x == None or \\",                   # 36 reached, with 37
        "    y == None,",                        # 37
        "    x == None,",                        # 38
        ")",                                     # 39
        "p = (",                                 # 40
        "    # ruff: ignore[E711]",              # 41
        "    (x == None, '''",                   # 42 reached, with 44
        "    text",                              # 43
        "    ''', y == None),",                  # 44
        "    y == None,",                        # 45
        ")",                                     # 46
        "q = x == None",                         # 47
        ""])
    rep = Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        _write_tools(Path(td), {"reach.py": text}, '[lint]\nselect = ["E711"]\n')
        exe = typecheck._pinned(rep, "ruff", typecheck.RUFF_VERSION)
        ensure(exe is not None, f"the pinned ruff must be installed: {rep.out!r}")
        done = subprocess.run([cast("str", exe), "check", "--config",
                               str(Path(td) / "tools" / "ruff.toml"), "--no-cache",
                               "--output-format", "concise", "--no-fix", "reach.py"],
                              cwd=Path(td) / "tools", capture_output=True, encoding="utf-8",
                              errors="replace", check=False, timeout=typecheck.TIMEOUT)
    found = typecheck._parse_ruff(done.stdout)
    lines = sorted(int(where.partition(" ")[0].split(":")[1]) for _, where in found)
    ensure(done.returncode == 1 and {code for code, _ in found} == {"E711"}
           and lines == [7, 10, 15, 22, 25, 33, 38, 45, 47],
           f"ruff: ignore must reach the lines the reading says and no others: {lines!r} "
           f"{done.stdout!r} {done.stderr!r}")


def _suppressions_reported_beside_the_run() -> None:
    # The real ruff under a per-file-ignores entry, a file-level directive, a range
    # spanning the module and a file-ignore, each switching ANN off for a module with an
    # unannotated function, under a per-file target version of py37, which switches UP006
    # off for a module annotating with `typing.List`, and under isort's skip_file, which
    # switches I001 off for an unsorted import block: ruff reports nothing and its log
    # names the module as checked, so the floor alone passes, and the refusal is what
    # fails the gate, one finding per refused key or comment; the run's verdict then
    # claims no more than it showed. Without a suppression ruff reports each module.
    def ruff_run(config: str, text: str) -> Reporter:
        rep = Reporter()
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            _write_tools(Path(td), {"x.py": text}, config)
            typecheck._run_ruff(rep, Path(td), frozenset({"x.py"}))
        return rep

    body = "def f(x):\n    return x\n"
    lint = '[lint]\nselect = ["ANN"]\n'
    annotated = "from typing import List\nX: List[int] = []\n"
    upgrade = '[lint]\nselect = ["UP006"]\n'
    unsorted = "import sys\nimport os\n"
    isort = '[lint]\nselect = ["I001"]\n'
    for config, text, code, count in ((lint, body, "ANN001", 2),
                                      (upgrade, annotated, "UP006", 1),
                                      (isort, unsorted, "I001", 1)):
        rep = ruff_run(config, text)
        ensure(rep.findings == count and rep.out[0] == f"FAIL ruff: {count} lint finding(s):"
               and f"{code}: 1" in "\n".join(rep.out),
               f"without a suppression ruff must report the module: {rep.out!r}")
    settings = "ruff.toml setting(s) the gate refuses:"
    comments = "file-level or range suppression(s) the gate refuses:"
    for config, text, refusal, count in (
            (lint + 'per-file-ignores = {"x.py" = ["ANN"]}\n', body, settings, 1),
            (lint, "# ruff: noqa: ANN001, ANN201\n" + body, comments, 1),
            (lint, "# ruff: disable[ANN001, ANN201]\n" + body
             + "# ruff: enable[ANN001, ANN201]\n", comments, 2),
            (lint, "# ruff: file-ignore[ANN001, ANN201]\n" + body, comments, 1),
            ('per-file-target-version = {"x.py" = "py37"}\n' + upgrade, annotated, settings, 1),
            (isort, "# isort: skip_file\n" + unsorted, comments, 1)):
        rep = ruff_run(config, text)
        ensure(rep.findings == count and rep.out[0] == f"FAIL ruff: {count} {refusal}"
               and rep.out[1 + count:] == [(f"ok ruff: every function is annotated and "
                                            f"ruff {typecheck.RUFF_VERSION} is clean under "
                                            "the suppressions refused above")],
               f"a suppression must be the one refusal beside a clean run: {rep.out!r}")


def _ty_log_variables_removed() -> None:
    modules = ["kept.py", "sub/stub.pyi"]
    rep = Reporter()
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        _module_tree(root / "tools", modules)
        (root / "tools" / "ty.toml").write_text(_ADMITTED, encoding="utf-8", newline="")
        with patch.dict(os.environ, {"TY_LOG": "info", "TY_LOG_PROFILE": "1"}), \
                patch.object(typecheck, "_user_config", return_value=None):
            os.environ.pop("PYTHONPATH", None)
            typecheck._run_ty(rep, root, frozenset(modules))
        profiled = sorted(path.name for path in (root / "tools").iterdir()
                          if path.name not in {"ty.toml", "kept.py", "sub"})
    ensure(rep.findings == 0 and not profiled,
           f"logging variables must not create incidental profile output: {rep.out!r} {profiled!r}")


# A ruff.toml banning two modules at module level, one of them dotted.
_BANNING = ('[lint.flake8-tidy-imports]\n'
            'banned-module-level-imports = ["fcntl", "asyncio.unix_events"]\n')
_SCAN_OK = ("ok imports: every import of a module ruff.toml bans at module level sits in a "
            "function body or where a sys.platform check keeps a platform from it")
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


def _unadmitted(site: str, test: str, names: str = "fcntl") -> str:
    return (f"       {site} imports {names} outside a function body, behind `{test}`, a "
            "sys.platform test the scan does not admit as separating platforms")


def _imports_refused_outside_functions() -> None:
    # An import of a banned module, or of a banned submodule by its parent, that runs
    # outside a function body is refused wherever it sits: unnested at module level, in
    # a class body at any depth, and in a module-level block such as the main guard. A
    # name spelled with a fullwidth letter is the banned module, since Python
    # NFKC-normalizes identifiers, though the text never spells it in ASCII. An `if`
    # reading a `platform` other than `sys.platform`, another object's or one imported
    # from sys and read bare, is not the check the scan admits, and neither is one
    # reading `sys.platform` other than by comparing it with string literals: by truth
    # value, beside a constant or another operand, beside a comparison of something
    # other than `sys.platform` with literals by `==`, `in` or startswith, through a call
    # other than startswith, against a name or with `in` against a string. Both branches
    # of such an `if` are refused, each import naming the nearest such test above it.
    #
    # A comparison the scan reads is refused where both platforms take the branch: a
    # tautology built from the admitted forms, a test only another platform fails, a
    # display or a prefix both platforms match, and an empty `not in`. So is a test of a
    # form the scan does not read beneath one that keeps both platforms, nested in its
    # body, in its `else` or as its `elif`; each names the nearest test above it.
    refused = {
        "receiver.py": "if args.platform == 'linux':\n    import fcntl\n",
        "fromsys.py": "from sys import platform\n\nif platform == 'linux':\n    import fcntl\n",
        "truthy.py": "import sys\n\nif sys.platform:\n    import fcntl\n",
        "always.py": "import sys\n\nif sys.platform or True:\n    import fcntl\n",
        "length.py": "import sys\n\nif len(sys.platform):\n    import fcntl\n",
        "operand.py": ("import sys\n\nif sys.platform == 'linux' or args.force:\n"
                       "    import fcntl\n"),
        "otherequal.py": ("import os, sys\n\nif sys.platform == 'linux' or os.name == 'nt':\n"
                          "    import fcntl\n"),
        "otherin.py": ("import os, sys\n\nif sys.platform == 'linux' or os.name in ('nt',):\n"
                       "    import fcntl\n"),
        "otherprefix.py": ("import os, sys\n\n"
                           "if sys.platform == 'linux' or os.name.startswith('nt'):\n"
                           "    import fcntl\n"),
        "named.py": "import sys\n\nPOSIX = 'linux'\nif sys.platform == POSIX:\n    import fcntl\n",
        "substring.py": "import sys\n\nif sys.platform in 'linux':\n    import fcntl\n",
        "elsebranch.py": "import sys\n\nif not sys.platform:\n    pass\nelse:\n    import fcntl\n",
        "innermost.py": ("import sys\n\nif sys.platform:\n    if len(sys.platform):\n"
                         "        import fcntl\n"),
        "toplevel.py": "import os, fcntl\n",
        "classbody.py": "class Locks:\n    import fcntl\n",
        "nested.py": "class Outer:\n    class Inner:\n        import fcntl\n",
        "nfkc.py": "class Locks:\n    import \uff46cntl\n",
        "moduleif.py": "import os\n\nif os.name == 'posix':\n    import fcntl\n",
        "mainblock.py": "if __name__ == '__main__':\n    import fcntl\n",
        "tryblock.py": "try:\n    from fcntl import flock\nexcept ImportError:\n    pass\n",
        "member.py": "class Loop:\n    from asyncio import events, unix_events\n",
        "dotted.py": "with open(__file__):\n    import asyncio.unix_events as ue\n",
    }
    rep = _scan(refused)
    ensure(rep.findings == len(refused) and rep.out == [
        f"FAIL imports: {len(refused)} {_SCAN_FAIL}",
        _unadmitted("always.py:4", "sys.platform or True"),
        _refused("classbody.py:2"), _refused("dotted.py:2", "asyncio.unix_events"),
        _unadmitted("elsebranch.py:6", "not sys.platform"),
        _refused("fromsys.py:4"), _unadmitted("innermost.py:5", "len(sys.platform)"),
        _unadmitted("length.py:4", "len(sys.platform)"), _refused("mainblock.py:2"),
        _refused("member.py:2", "asyncio.unix_events"), _refused("moduleif.py:4"),
        _unadmitted("named.py:5", "sys.platform == POSIX"),
        _refused("nested.py:3"), _refused("nfkc.py:2"),
        _unadmitted("operand.py:4", "sys.platform == 'linux' or args.force"),
        _unadmitted("otherequal.py:4", "sys.platform == 'linux' or os.name == 'nt'"),
        _unadmitted("otherin.py:4", "sys.platform == 'linux' or os.name in ('nt',)"),
        _unadmitted("otherprefix.py:4", "sys.platform == 'linux' or os.name.startswith('nt')"),
        _refused("receiver.py:2"), _unadmitted("substring.py:4", "sys.platform in 'linux'"),
        _refused("toplevel.py:1"), _unadmitted("truthy.py:4", "sys.platform"),
        _refused("tryblock.py:2")],
        f"each import outside a function body must be refused: {rep.out!r}")
    both = {
        "tautology.py": ("import sys\n\nif sys.platform == 'linux' or sys.platform != 'linux':\n"
                         "    import fcntl\n"),
        "otherplatform.py": "import sys\n\nif sys.platform != 'darwin':\n    import fcntl\n",
        "bothlisted.py": ("import sys\n\nif sys.platform in ('linux', 'win32'):\n"
                          "    import fcntl\nelse:\n    pass\n"),
        "bothprefix.py": ("import sys\n\nif sys.platform.startswith(('lin', 'win')):\n"
                          "    import fcntl\n"),
        "neither.py": ("import sys\n\n"
                       "if not (sys.platform == 'linux' and sys.platform == 'win32'):\n"
                       "    import fcntl\n"),
        "emptynotin.py": "import sys\n\nif sys.platform not in ():\n    import fcntl\n",
        "nestedtruthy.py": ("import sys\n\nif sys.platform != 'darwin':\n    if sys.platform:\n"
                            "        import fcntl\n"),
        "elselength.py": ("import sys\n\nif sys.platform == 'darwin':\n    pass\nelse:\n"
                          "    if len(sys.platform):\n        import fcntl\n"),
        "eliftruthy.py": ("import sys\n\nif sys.platform == 'darwin':\n    pass\n"
                          "elif sys.platform:\n    import fcntl\n"),
        "elifadmitted.py": ("import sys\n\nif sys.platform == 'darwin':\n    pass\n"
                            "elif sys.platform != 'cygwin':\n    import fcntl\n"),
        "elseclass.py": ("import sys\n\nif sys.platform == 'darwin':\n    pass\nelse:\n"
                         "    class Locks:\n        import fcntl\n"),
    }
    rep = _scan(both)
    ensure(rep.findings == len(both) and rep.out == [
        f"FAIL imports: {len(both)} {_SCAN_FAIL}",
        _unadmitted("bothlisted.py:4", "sys.platform in ('linux', 'win32')"),
        _unadmitted("bothprefix.py:4", "sys.platform.startswith(('lin', 'win'))"),
        _unadmitted("elifadmitted.py:6", "sys.platform != 'cygwin'"),
        _unadmitted("eliftruthy.py:6", "sys.platform"),
        _unadmitted("elseclass.py:7", "sys.platform == 'darwin'"),
        _unadmitted("elselength.py:7", "len(sys.platform)"),
        _unadmitted("emptynotin.py:4", "sys.platform not in ()"),
        _unadmitted("neither.py:4", "not (sys.platform == 'linux' and sys.platform == 'win32')"),
        _unadmitted("nestedtruthy.py:5", "sys.platform"),
        _unadmitted("otherplatform.py:4", "sys.platform != 'darwin'"),
        _unadmitted("tautology.py:4", "sys.platform == 'linux' or sys.platform != 'linux'")],
        f"each import both platforms reach must be refused: {rep.out!r}")


def _run_wires_in_the_scan() -> None:
    # The whole run, with the index fixed and both checkers' runs replaced by no-ops,
    # over a tree whose one module imports a banned module in a class body: the scan
    # runs beside the checkers, and its refusal is in the run's report and its count.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        _write_tools(Path(td), {"classbody.py": "class Locks:\n    import fcntl\n"}, _BANNING)
        with patch.object(typecheck, "_tracked", return_value=frozenset({"classbody.py"})), \
                patch.object(typecheck, "_run_ty"), patch.object(typecheck, "_run_ruff"):
            rep = typecheck.run(Path(td))
    ensure(rep.findings == 1 and rep.out == ["=== tools ===", f"FAIL imports: 1 {_SCAN_FAIL}",
                                             _refused("classbody.py:2"), "1 finding(s)."],
           f"the run must carry the scan's refusal: {rep.out!r}")


def _imports_admitted_in_functions_and_platform_blocks() -> None:
    # A function body runs only when called, and an if comparing sys.platform with string
    # literals keeps each of its branches to the platforms that take it, at module level
    # or in a class body: by == or != with one, by in or not in with a tuple, list or set
    # of them, or through startswith with one or a tuple of them, alone, under not, or
    # joined by and or or. Each import below is kept to linux, where fcntl is found, and
    # stays so beneath a test of any form nested in the branch, in its body or its elif;
    # one no platform reaches, behind another platform or an empty display, is admitted
    # too. A name that only begins like a banned one, a banned module's parent, a relative
    # import and a string are none of them an import of a banned module.
    admitted = {
        "platformin.py": ("import sys\n\nif sys.platform in ('linux', 'darwin'):\n"
                          "    import fcntl\n"),
        "platformnotin.py": "import sys\n\nif sys.platform not in ['win32']:\n    import fcntl\n",
        "platformset.py": "import sys\n\nif sys.platform in {'linux'}:\n    import fcntl\n",
        "platformprefix.py": ("import sys\n\nif sys.platform.startswith('linux'):\n"
                              "    import fcntl\n"),
        "platformprefixes.py": ("import sys\n\nif sys.platform.startswith(('linux', 'darwin')):\n"
                                "    import fcntl\n"),
        "platformnot.py": "import sys\n\nif not sys.platform == 'win32':\n    import fcntl\n",
        "platformjoined.py": ("import sys\n\nif sys.platform != 'win32' and not (\n"
                              "        sys.platform == 'cygwin' or sys.platform.startswith('msys')):\n"
                              "    import fcntl\n"),
        "function.py": "def lock() -> None:\n    import fcntl\n",
        "coroutine.py": "async def lock() -> None:\n    from fcntl import flock\n",
        "method.py": "class Locks:\n    def lock(self) -> None:\n        import fcntl\n",
        "classinfunction.py": "def make() -> None:\n    class Locks:\n        import fcntl\n",
        "platformif.py": "import sys\n\nif sys.platform != 'win32':\n    import fcntl\n",
        "platformelse.py": ("import sys\n\nif sys.platform == 'win32':\n    pass\n"
                            "elif __name__ == '__main__':\n    import fcntl\n"),
        "platformclass.py": ("import sys\n\nclass Locks:\n    if sys.platform != 'win32':\n"
                             "        import fcntl\n"),
        "narrowed.py": ("import sys\n\nif sys.platform != 'darwin':\n"
                        "    if sys.platform == 'linux':\n        import fcntl\n"),
        "narrowedtruthy.py": ("import sys\n\nif sys.platform == 'linux':\n    if sys.platform:\n"
                              "        import fcntl\n"),
        "elifnarrowed.py": ("import sys\n\nif sys.platform == 'win32':\n    pass\n"
                            "elif len(sys.platform):\n    import fcntl\n"),
        "nowhere.py": "import sys\n\nif sys.platform == 'darwin':\n    import fcntl\n",
        "emptyin.py": "import sys\n\nif sys.platform in ():\n    import fcntl\n",
        "unrelated.py": ("import asyncio\nimport fcntlx\nfrom asyncio import events\n"
                         "from . import fcntl\nTEXT = 'import fcntl'\n"),
    }
    rep = _scan(admitted)
    ensure(rep.findings == 0 and rep.out == [_SCAN_OK],
           f"an import in a function body or behind sys.platform must be admitted: {rep.out!r}")


def _missing(site: str, test: str, names: str, platform: str) -> str:
    return (f"       {site} imports {names} outside a function body, behind `{test}`, on a "
            f"branch {platform} takes, where this interpreter cannot find it")


def _imports_refused_where_the_running_platform_lacks_them() -> None:
    # Keeping an import from one platform does not say which platform has the module, so
    # on each lane an import the running platform reaches is refused where this
    # interpreter cannot find its top-level module, naming the nearest test reading
    # `sys.platform`, whose body or `else` the running platform takes, in a class body as
    # at module level. The same import kept to the other platform is admitted, and so are
    # one of a module the interpreter finds and one of a submodule whose package it
    # finds, which this reading does not catch. With modules no interpreter finds, the
    # refusal follows the running platform: each of the two refuses the import it
    # reaches, and a platform outside them refuses neither. A name the finder refuses,
    # raising rather than answering, is refused as one it cannot find, fail-closed, even
    # where the interpreter has the module.
    config = ('[lint.flake8-tidy-imports]\nbanned-module-level-imports = ["fcntl", "msvcrt", '
              '"asyncio.unix_events", "asyncio.windows_events", "vosnolinux", "vosnowin32"]\n')
    running = sys.platform
    lacking, having = ("fcntl", "msvcrt") if running == "win32" else ("msvcrt", "fcntl")
    submodule = "asyncio.unix_events" if running == "win32" else "asyncio.windows_events"
    modules = {
        "wrongside.py": f"import sys\n\nif sys.platform == {running!r}:\n    import {lacking}\n",
        "elseside.py": (f"import sys\n\nif sys.platform != {running!r}:\n    pass\nelse:\n"
                        f"    import {lacking}\n"),
        "classside.py": (f"import sys\n\nclass Locks:\n    if sys.platform.startswith("
                         f"{running[:3]!r}):\n        from {lacking} import flags\n"),
        "rightside.py": f"import sys\n\nif sys.platform != {running!r}:\n    import {lacking}\n",
        "having.py": f"import sys\n\nif sys.platform == {running!r}:\n    import {having}\n",
        "submodule.py": f"import sys\n\nif sys.platform == {running!r}:\n    import {submodule}\n",
    }
    rep = _scan(modules, config)
    ensure(rep.findings == 3 and rep.out == [
        f"FAIL imports: 3 {_SCAN_FAIL}",
        _missing("classside.py:5", f"sys.platform.startswith({running[:3]!r})", lacking,
                 running),
        _missing("elseside.py:6", f"sys.platform != {running!r}", lacking, running),
        _missing("wrongside.py:4", f"sys.platform == {running!r}", lacking, running)],
        f"an import this platform reaches of a module it lacks must be refused: {rep.out!r}")
    lanes = {"lanes.py": ("import sys\n\nif sys.platform == 'linux':\n    import vosnolinux\n"
                          "if sys.platform == 'win32':\n    import vosnowin32\n")}
    for platform, expected in (
            ("linux", [_missing("lanes.py:4", "sys.platform == 'linux'", "vosnolinux", "linux")]),
            ("win32", [_missing("lanes.py:6", "sys.platform == 'win32'", "vosnowin32", "win32")]),
            ("darwin", [])):
        with patch.object(typecheck, "sys", SimpleNamespace(platform=platform)):
            rep = _scan(lanes, config)
        ensure(rep.out == ([f"FAIL imports: 1 {_SCAN_FAIL}", *expected] if expected
                           else [_SCAN_OK]),
               f"under {platform}, only the import it reaches may be refused: {rep.out!r}")
    for error in (ValueError, ImportError):
        with patch.object(typecheck.importlib.util, "find_spec", side_effect=error("refused")):
            rep = _scan({"having.py": modules["having.py"]}, config)
        ensure(rep.findings == 1 and rep.out == [
            f"FAIL imports: 1 {_SCAN_FAIL}",
            _missing("having.py:4", f"sys.platform == {running!r}", having, running)],
            f"a name the finder refuses with {error.__name__} must be refused as one it "
            f"cannot find: {rep.out!r}")


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


# The program `_import_failures` runs in a child of the running interpreter: each module
# the interpreter lists as its standard library, and each submodule of a package among
# them that imports, imported in turn, then one line after `_PROBED`, a JSON object
# naming each that fails with the module its ImportError names, where that module did not
# load, or null where it names none, names one that loaded, as `cannot import name` does,
# or the failure is another exception. The marker keeps the line apart from anything a
# module prints as it imports. A `__main__` submodule runs a program, and the trees left
# out run one or open a browser when imported.
_PROBED = "vos-import-probe: "
_IMPORT_PROBE = """\
import importlib, json, pkgutil, sys

SKIP = {"antigravity", "idlelib", "test", "this", "turtledemo"}

def skipped(name):
    parts = name.split(".")
    return parts[0] in SKIP or parts[-1] == "__main__"

failed = {}
queue = sorted(name for name in sys.stdlib_module_names if not skipped(name))
while queue:
    name = queue.pop()
    try:
        module = importlib.import_module(name)
    except BaseException as err:
        missing = err.name if isinstance(err, ImportError) else None
        failed[name] = None if missing in sys.modules else missing
        continue
    queue.extend(info.name for info in pkgutil.iter_modules(getattr(module, "__path__", []),
                                                            name + ".")
                 if not skipped(info.name))
""" + f"print({_PROBED!r} + json.dumps(failed))\n"


def _import_failures(program: str = _IMPORT_PROBE) -> dict[str, str | None]:
    """Each standard-library module or submodule the running interpreter cannot import,
    with the module its ImportError names, where that module did not load, or `None`
    where it names none, names one that loaded, or the failure is another exception, as
    `program`, the probe unless a case gives another, reports them."""
    done = subprocess.run([sys.executable, "-B", "-I", "-c", program],
                          stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=typecheck.TIMEOUT)
    lines = [line.removeprefix(_PROBED) for line in done.stdout.splitlines()
             if line.startswith(_PROBED)]
    ensure(done.returncode == 0 and len(lines) == 1,
           f"the import probe exited {done.returncode}: {done.stderr.strip()[-400:]!r}")
    return cast("dict[str, str | None]", json.loads(lines[0]))


def _import_probe_names_modules_that_did_not_load() -> None:
    # The probe over modules of its own in place of the standard library: one failing for
    # want of a module that is nowhere names it; one failing to import a name from a
    # module that loaded, as `cannot import name` does, and one raising another exception
    # name nothing; and one that imports is not recorded.
    modules = {"vosprobeloaded": "VALUE = 1\n", "vosprobeabsent": "import vosprobenowhere\n",
               "vosprobename": "from vosprobeloaded import MISSING\n",
               "vosprobeerror": "raise RuntimeError('refused')\n"}
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        for name, text in modules.items():
            (Path(td) / f"{name}.py").write_text(text, encoding="utf-8", newline="")
        program = f"import sys\nsys.path.insert(0, {td!r})\n" + _IMPORT_PROBE.replace(
            "sys.stdlib_module_names", repr(sorted(modules)), 1)
        found = _import_failures(program)
    ensure(found == {"vosprobeabsent": "vosprobenowhere", "vosprobename": None,
                     "vosprobeerror": None},
           f"the probe must name only a module that did not load: {found!r}")


def _ty_unresolved(modules: list[str]) -> set[str]:
    """Each of `modules` the gate's own ty run, under the ty.toml it admits, cannot
    resolve under one of its platforms or more, read from the findings each run gives."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        _write_tools(root, {"probe.py": "".join(f"import {name}\n" for name in modules),
                            "ty.toml": _ADMITTED}, None)
        with patch.dict(os.environ), \
                patch.object(typecheck, "_user_config", return_value=None), \
                patch.object(typecheck, "_summarize") as verdicts:
            os.environ.pop("PYTHONPATH", None)
            rep = Reporter()
            typecheck._run_ty(rep, root, None)
    ensure(rep.findings == 0 and verdicts.call_count == len(typecheck.TY_PLATFORMS),
           f"each ty run must give a verdict: {rep.out!r} {verdicts.call_args_list!r}")
    found = [finding for call in verdicts.call_args_list
             for finding in cast("list[tuple[str, str]]", call.args[3])]
    ensure(all(code == "unresolved-import" for code, _ in found),
           f"an import alone must give no finding but an unresolved one: {found!r}")
    return {modules[int(text.partition(" ")[0].rsplit(":", 2)[1]) - 1] for _, text in found}


# The standard-library packages no platform lacks that an installer may leave out or a
# distribution ships apart from the rest, by top-level name, each with where. An
# interpreter short of one is short of its build's standard library, not of a platform's.
_TCL_TK = ("python.org's Windows installer makes Tcl/Tk optional, and Debian and Ubuntu "
           "ship tkinter in the package python3-tk installs")
_SEPARABLE = {"_tkinter": _TCL_TK, "tkinter": _TCL_TK,
              "ensurepip": "Debian and Ubuntu ship ensurepip in python3.X-venv"}


def _banned_list_covers_what_cannot_be_imported() -> None:
    # The list's claim, held on this lane: each standard-library module the running
    # interpreter cannot import, that the gate's ty resolves under both of its platforms,
    # is covered by a listed name, itself or a parent. A module whose import fails for want
    # of one that did not load and that configure records as built, missing or disabled,
    # any state but n/a, is the build's rather than the platform's: one a build left out
    # for want of an optional library, or one it built whose shared library is absent at
    # run time. A failure naming a module that loaded, as `cannot import name` does, is not
    # read as the build's. The Windows lane holds the half Windows lacks and the Linux lane
    # the other. The control is that the search finds the best-known module this lane's
    # platform lacks, so an empty search cannot pass for a clean one. The case decides the
    # list only on an interpreter carrying its build's whole standard library, as the
    # interpreters Host CI's setup-python installs do: a Windows build records no state,
    # and a distribution ships some pure-Python packages apart, so an interpreter short of
    # a package `_SEPARABLE` names fails the case as short of its library rather than
    # asked to ban it.
    def omitted(missing: str | None) -> bool:
        return missing is not None and sysconfig.get_config_var(
            f"MODULE_{missing.upper()}_STATE") not in {None, "n/a"}

    def covered(name: str, listed: frozenset[str]) -> bool:
        return any(name == ban or name.startswith(ban + ".") for ban in listed)

    def separated(name: str) -> list[str]:
        roots = {module.partition(".")[0] for module in (name, failed[name]) if bool(module)}
        return [_SEPARABLE[root] for root in sorted(roots) if root in _SEPARABLE]

    failed = _import_failures()
    candidates = sorted(name for name, missing in failed.items() if not omitted(missing))
    unresolved = _ty_unresolved(candidates)
    required = [name for name in candidates if name not in unresolved]
    known = "fcntl" if sys.platform == "win32" else "msvcrt"
    ensure(known in required,
           f"the search must find {known}, which this platform lacks: {failed!r} "
           f"{sorted(unresolved)!r}")
    committed = Path(typecheck.__file__).resolve().parents[2] / "ruff.toml"
    banned, unread = typecheck._banned(committed)
    uncovered = [name for name in required if not covered(name, banned)]
    apart = [name for name in uncovered if separated(name)]
    ensure(not apart,
           f"this interpreter lacks {apart!r}, which no platform lacks, so it does not carry "
           f"its build's whole standard library and the case cannot decide the list on it: "
           f"{'; '.join(sorted({why for name in apart for why in separated(name)}))}")
    ensure(not unread and not uncovered,
           f"ruff.toml must list each module this interpreter cannot import that ty "
           f"resolves under both platforms: {unread!r} {uncovered!r}")


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
        Case("explicit-commands-are-bounded", _explicit_commands_are_bounded),
        Case("batches-share-one-verdict", _batches_share_one_verdict),
        Case("ruff-explicit-targets-bypass-exclusions", _ruff_explicit_targets_bypass_exclusions),
        Case("ty-explicit-targets-bypass-exclusions", _ty_explicit_targets_bypass_exclusions),
        Case("missing-explicit-inputs-refuse", _missing_explicit_inputs_refuse),
        Case("ruff-settings-refuse-per-file-suppressions",
             _ruff_settings_refuse_per_file_suppressions),
        Case("file-suppressions-refused", _file_suppressions_refused),
        Case("ruff-ignore-reaches-one-line", _ruff_ignore_reaches_one_line),
        Case("suppressions-reported-beside-the-run", _suppressions_reported_beside_the_run),
        Case("ty-log-variables-removed", _ty_log_variables_removed),
        Case("imports-refused-outside-functions", _imports_refused_outside_functions),
        Case("run-wires-in-the-scan", _run_wires_in_the_scan),
        Case("imports-admitted-in-functions-and-platform-blocks",
             _imports_admitted_in_functions_and_platform_blocks),
        Case("imports-refused-where-the-running-platform-lacks-them",
             _imports_refused_where_the_running_platform_lacks_them),
        Case("imports-fail-closed", _imports_fail_closed),
        Case("imports-close-what-ruff-leaves-open", _imports_close_what_ruff_leaves_open),
        Case("import-probe-names-modules-that-did-not-load",
             _import_probe_names_modules_that_did_not_load),
        Case("banned-list-covers-what-cannot-be-imported",
             _banned_list_covers_what_cannot_be_imported),
        Case("tracked-reads-the-index", _tracked_reads_the_index),
        Case("live-tree-reaches-every-tracked-module", _live_tree_reaches_every_tracked_module),
    ]
