#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Hold this directory's own Python to the discipline it holds the documents to.

`check.py` checks the documents against each other. Nothing checked the tool that
does the checking, and the tools are the one artifact in this repository with no
proof, no model, and no reviewer but the person who wrote them. This is that gate.

It runs two checkers, because one of them cannot do the whole job:

    ty     the types      every expression reachable under python-platform linux,
                          and every one reachable under win32, against the types
                          it can infer
    ruff   the coverage   every function, against whether it is annotated at all

The split is not a preference. ty infers aggressively and reports what it can prove
wrong, which means a wholly unannotated function is not a finding to it: there is
nothing to contradict. That is exactly the shape the defect takes here. The gap was
172 unannotated parameters when this gate was written, and all but a handful sat in
the two newest modules, where a dispatch table held callbacks whose signatures
nothing checked. ruff's `ANN` group is what closes it, so ruff is here for one group
and stays for the correctness rules it carries besides.

Both are pinned, for the reason Rocq and z3 are pinned: a checker that changes
underneath the tree changes what the tree is allowed to say without anyone
deciding it. A version other than the pinned one is a finding, not a warning.

ty runs once per platform, because it reports nothing in a branch the platform
makes unreachable and the tools run on the Windows host as well as in the Linux
guest. Under linux it types the guest's POSIX-only code; under win32 it types the
branches only the host takes, and holds every call typeshed declares absent on
Windows behind a `sys.platform` check. Each run is its own verdict.

Every rule ty carries runs at error, including the ones it ships as warnings or
switched off. `ty.toml` states that in its `[rules]` table, and it and `ruff.toml`
hold the rest of the settings, so an editor's language server decides what this
decides. The gate also passes ty `--error all`, which overrides the `[rules]`
table, and `--python-platform`, which overrides the platform an editor reads from
`[environment]`, and it reads `ty.toml` itself. Each of these is a ty finding,
because an editor reads the file without the flags or because a flag cannot restore
what the setting takes away:

    [rules]        a table other than exactly `all = "error"`
    [[overrides]]  an entry carrying any key but `include` and `exclude`: its
                   `rules` can lower the flag's severities, and its `analysis` can
                   suppress diagnostics, for the files it matches
    [analysis]     a key outside the ones that suppress nothing, which refuses
                   `allowed-unresolved-imports` and `replace-imports-with-any`
    [environment]  a key other than `python-version`, `python-platform` and
                   `extra-paths`, or either of the last two at a value other than
                   `"linux"` and `["."]`, since the platform decides which branches
                   an editor's ty checks and `python`, `root`, `typeshed` or another
                   search path changes where it resolves imports; K-75 holds
                   `python-version`
    [src]          a table other than exactly `exclude = ["**/__pycache__/**"]` and
                   `respect-ignore-files = false`, since an `include`, a further
                   `exclude`, `exclude-scripts` or honoring ignore files takes
                   files out of the run

A user-level ty configuration is a ty finding too: ty merges it beneath `ty.toml`
even beside `--config-file`, so a setting `ty.toml` leaves out would come from it.
So is a set `PYTHONPATH`, whose directories ty searches just after `extra-paths` and
ahead of the standard library, which is what `typeshed` and a further `extra-paths`
entry are refused for.

Holding the settings does not hold what each run reaches. Both checkers skip
directories such as `dist/` and `venv/` by default, and `ruff.toml`'s `exclude`,
`extend-exclude` and `lint.exclude` each drop files with nothing reported. So every
run logs each file it checks, and each module the index tracks under `tools/` that
a run's log does not name is a finding under that run's checker. The log is the
pinned version's verbose output: a log of another shape names no file, and every
tracked module then reads as unchecked. ty takes its log filter from `TY_LOG` ahead of
its verbosity flag, so each ty run is made without that variable, and without
`TY_LOG_PROFILE`, which has it write a profile into `tools/`; neither changes what ty
checks or reports.

ruff's log names a file whose rules are switched off as checked, so the floor cannot
see a suppression, and the gate refuses each reaching past a line as a ruff finding: a
`per-file-ignores` or `extend-per-file-ignores` key in `ruff.toml`, in `[lint]` or at
the top level; an `extend` key, which merges another file's settings beneath it; a
comment anywhere in a tracked module carrying ruff's file-level suppression,
`# ruff: noqa` or `# flake8: noqa`, unless it names N999 and no other rule, since ruff
reports N999 against the file's name rather than a line of it; and one carrying
`# ruff: file-ignore[...]`, a `# ruff: disable[...]` or `# ruff: enable[...]` range
comment, whose `disable` with no matching `enable` runs to the end of its block, or
isort's `skip_file`, `off` or `on` action comment. `# ruff: ignore[...]` reaches one
logical line, as `# noqa` does, and is not refused.

`ruff.toml` lists the modules the interpreter lacks on one platform that ty resolves on
both, and ruff's TID253 refuses an import of one only where it is unnested at module
level; with the module listed, PLC0415 no longer reports it in a class body. So the
gate reads the same list and refuses an import of a listed module in any tracked module
anywhere outside a function body, in a class body or a module-level block alike, unless
an enclosing `if` reads `sys.platform`.

Exit 0 clean, 1 on any finding. It may be run from anywhere: the repository root is
found from this file, never from the working directory.
"""

import argparse
import ast
import io
import os
import re
import subprocess
import sys
import sysconfig
import tokenize
import tomllib
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NamedTuple

from vos import corpus as corpus_mod
from vos import toolenv
from vos.report import Reporter

_PINS = toolenv.checker_pins(Path(__file__).resolve().parents[3])
TY_VERSION = _PINS["ty"]
RUFF_VERSION = _PINS["ruff"]

# The one `[rules]` table ty.toml may carry: every rule at error, and nothing else.
TY_RULES = {"all": "error"}

# The one `[src]` table ty.toml may carry. `include`, a further `exclude` glob and
# `exclude-scripts` each take files out of the run, where no severity reaches them,
# and so does `respect-ignore-files`, which defaults to true: a `.gitignore`,
# `.ignore`, `.git/info/exclude` or global gitignore pattern matching a tracked
# module would otherwise drop it.
TY_SRC = {"exclude": ["**/__pycache__/**"], "respect-ignore-files": False}

# The keys an `[[overrides]]` entry may carry: which files it matches, and nothing
# it does to them. ty also accepts `rules`, which can lower `--error all` for those
# files, and `analysis`, which can suppress their diagnostics under it.
TY_OVERRIDE_KEYS = frozenset({"include", "exclude"})

# The `[analysis]` settings that suppress no diagnostic the defaults report. ty's
# other two, `allowed-unresolved-imports` and `replace-imports-with-any`, suppress
# diagnostics for the modules they match under `--error all`, and a key the gate has
# not read is refused with them. `strict-literal-narrowing` is ty's alias for
# `strict-equality-semantics`.
TY_ANALYSIS_KEYS = frozenset({"respect-type-ignore-comments", "strict-equality-semantics",
                              "strict-literal-narrowing", "strict-generic-narrowing"})

# The `[environment]` values the gate holds, and the keys it admits beside them. ty
# reports nothing in a branch `python-platform` makes unreachable, so the platform
# decides which `sys.platform` branches an editor's ty server checks at all, the
# gate's `--python-platform` overriding it, and an `extra-paths` entry comes first in
# resolving every import. ty's other three keys each move a resolution: `python`
# another environment's packages for an editor, the gate's `--python` overriding it,
# `root` the first-party modules, and `typeshed` the standard library. A key the gate
# has not read is refused with them. `python-version` is admitted and K-75 holds its
# value.
TY_ENVIRONMENT = {"python-platform": "linux", "extra-paths": ["."]}
TY_ENVIRONMENT_KEYS = frozenset({"python-version", *TY_ENVIRONMENT})

# The platforms the gate types the tools under, one ty run each, named on its
# command line. Neither alone reaches every branch, so the gate runs both: the first
# is the one `TY_ENVIRONMENT` holds for an editor, and the second is the host's.
TY_PLATFORMS = ("linux", "win32")

# How many findings of one rule are printed before the rest are counted. A run that
# has just switched a rule on is a list of hundreds of one thing, and the verdict is
# the count; the individual sites are what the editor is for.
PER_RULE = 8

# The bound every subprocess must answer within, version probes included. Both
# checkers finish in about a second on this tree, so a run that reaches it is hung,
# and a hung checker must become a finding rather than a gate that never returns.
TIMEOUT = 120

# Each checker's verbose log, in the pinned version's shape: `LOG` matches every
# line of it below warning level, which is what tells the log from the checker's own
# output and keeps it out of the parse and out of a crash's message, and `CHECKED`
# matches the one line naming a file the run checked, with its path in group 1. A
# warning or an error the log carries stays with the checker's output.
TY_VERBOSE = ["-vv"]
# The variables every ty run is made without. ty takes its log filter from `TY_LOG` ahead
# of `-vv`, so under `TY_LOG=info` a run logs no checked file and every tracked module
# reads as unchecked, and `TY_LOG_PROFILE` has a run write a profile into its working
# directory, `tools/`. Neither changes what ty checks or reports, so they are removed
# rather than reported as `PYTHONPATH` is.
TY_UNSET = frozenset({"TY_LOG", "TY_LOG_PROFILE"})
TY_LOG = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)? +(?:TRACE|DEBUG|INFO) ")
TY_CHECKED = re.compile(r" DEBUG Checking file '(.+)'$")
RUFF_VERBOSE = ["--verbose"]
RUFF_LOG = re.compile(r"^\[\d{4}-\d{2}-\d{2}\]\[\d{2}:\d{2}:\d{2}\]\[[^\]]+\]"
                      r"\[(?:TRACE|DEBUG|INFO)\] ")
RUFF_CHECKED = re.compile(r"\[ruff::diagnostics\]\[DEBUG\] Checking: (.+)$")

# The tracked modules the gate's runs must reach: the index's Python sources and stubs
# under `tools/`, where both checkers run.
TOOLS = "tools/"
MODULE_SUFFIXES = (".py", ".pyi")

# Where `ruff.toml` lists the modules TID253 refuses an unnested module-level import of,
# the list the gate holds every import outside a function body to.
BANNED = ("lint", "flake8-tidy-imports", "banned-module-level-imports")

# The `ruff.toml` keys that switch rules off for the files a pattern matches, which ruff
# reads in `[lint]` and, deprecated, at the top level. ruff's log still names a file
# whose rules are off as checked, so the coverage floor cannot see what they take away.
RUFF_PER_FILE = ("per-file-ignores", "extend-per-file-ignores")

# A comment ruff reads as a file-level suppression, matched as ruff's lexer matches it:
# `ruff` or `flake8`, a colon and `noqa` in any case, after any `#` in the comment. It
# switches off the rules it names, or every rule, for the whole file.
FILE_NOQA = re.compile(r"#\s*(?:ruff|flake8)\s*:\s*(?i:noqa)")
# The rules a file-level suppression may name. ruff reports N999 against the file's name
# rather than any line of it, so exempting a file from it leaves every line of the file
# under every rule.
FILE_SCOPED = frozenset({"N999"})
# A comment carrying one of ruff's other suppressions that reach past their own line,
# matched in ruff's case and more loosely than ruff parses it, after any `#` in the
# comment: `ruff: file-ignore[...]`, which switches the rules it names off for the whole
# file; `ruff: disable[...]` and `ruff: enable[...]`, whose range runs from the one to
# the other or, with no matching `enable`, to the end of the block the `disable` sits in,
# the whole file at module level; and isort's `skip_file`, `off` and `on`, alone or after
# `ruff:`, which switch import sorting off for the whole file or from `off` to `on` or
# the file's end. `ruff: ignore[...]`, which reaches one logical line, and isort's
# `skip`, which reaches one line, suppress no more than `# noqa` does and are not matched.
FILE_RANGE = re.compile(r"#\s*(?:ruff\s*:\s*(?:disable|enable|file-ignore)\b"
                        r"|(?:ruff\s*:\s*)?isort\s*:\s*(?:skip_file|off|on)\b)")


def _tool(name: str) -> str | None:
    """Only the running interpreter's checker, never a global shim or PATH fallback."""
    suffix = ".exe" if sys.platform == "win32" else ""
    candidate = Path(sysconfig.get_path("scripts")) / (name + suffix)
    return str(candidate) if candidate.is_file() else None


def _version(exe: str) -> str:
    """The version a checker reports, reduced to its number.

    Both spell it `<name> <version>` and ty adds its build and date, so the second
    token is the whole of what is compared.
    """
    done = subprocess.run([exe, "--version"], capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=TIMEOUT)
    parts = (done.stdout.strip() or done.stderr.strip()).split()
    return parts[1] if len(parts) > 1 else "unknown"


def _pinned(rep: Reporter, name: str, pin: str) -> str | None:
    """The checker to run, or `None` having already reported why there is not one.

    The probe itself can fail two ways short of a wrong number: an executable that
    exists but cannot be run, and one that never answers. Both are findings, because
    the gate's answer is a verdict and never a traceback and never silence.
    """
    exe = _tool(name)
    if exe is None:
        rep.report(name, "not installed:",
                   [f"{name} {pin} is not in {sysconfig.get_path('scripts')}: "
                    "rerun python tools/run.py typecheck to synchronize tools/uv.lock"])
        return None
    try:
        found = _version(exe)
    except subprocess.TimeoutExpired:
        rep.report(name, "checker error(s):",
                   [f"{exe} answered no --version within {TIMEOUT}s"])
        return None
    except OSError as err:
        rep.report(name, "checker error(s):", [f"{exe} could not be run: {err}"])
        return None
    if found != pin:
        rep.report(name, "version(s) other than the pinned one:",
                   [f"{name} {found} is installed and this tree pins {pin}: "
                    "rerun python tools/run.py typecheck to synchronize tools/uv.lock"])
        return None
    return exe


def _summarize(rep: Reporter, rule: str, label: str, findings: list[tuple[str, str]],
               ok: str) -> None:
    """Report one checker's findings, grouped by the rule each fell under.

    Grouped rather than listed, because these two tools report per site and a
    directory that has just had a rule switched on reports the same rule hundreds of
    times. The count is the verdict; the sites under it are a sample.
    """
    if not findings:
        rep.report(rule, label, [], ok)
        return

    by_rule: dict[str, list[str]] = defaultdict(list)
    for code, text in findings:
        by_rule[code].append(text)

    lines = []
    for code in sorted(by_rule, key=lambda c: (-len(by_rule[c]), c)):
        hits = by_rule[code]
        lines.append(f"{code}: {len(hits)}")
        lines.extend(f"  {h}" for h in hits[:PER_RULE])
        if len(hits) > PER_RULE:
            lines.append(f"  ... and {len(hits) - PER_RULE} more")
    # `count` because `lines` is a summary: a rule header sits above each sample and a
    # tail line stands in for whatever the cap held back, so the verdict is the length
    # of `findings` and never the length of what is printed for them.
    rep.report(rule, label, lines, ok, count=len(findings))


def _parse_ty(text: str) -> list[tuple[str, str]]:
    """ty's concise lines: `path:line:col: error[rule-name] message`, with a trailing
    summary line the pattern deliberately does not match."""
    findings: list[tuple[str, str]] = []
    for line in text.splitlines():
        if "] " not in line or (": error[" not in line and ": warning[" not in line):
            continue
        where, _, rest = line.partition(": ")
        code = rest.partition("[")[2].partition("]")[0]
        findings.append((code, f"{where} {rest.partition('] ')[2]}"))
    return findings


def _parse_ruff(text: str) -> list[tuple[str, str]]:
    """ruff's concise lines: `path:line:col: CODE message`."""
    findings: list[tuple[str, str]] = []
    for line in text.splitlines():
        head, _, rest = line.partition(": ")
        code, _, message = rest.partition(" ")
        if not head or not code or not code[0].isalpha() or not code[-1].isdigit():
            continue
        findings.append((code, f"{head} {message}"))
    return findings


class Coverage(NamedTuple):
    """What a run must reach, and how its verbose log says what it did: the `LOG` and
    `CHECKED` patterns of its checker, and the tracked modules, each relative to the
    directory the run checks."""
    log: re.Pattern[str]
    checked: re.Pattern[str]
    tracked: frozenset[str]


class Pass(NamedTuple):
    """One run of a pinned checker: its arguments, the name its failures are reported
    under, the verdict its findings or its clean exit read as, for a run whose
    arguments turn its log on, the modules that log must name, and the environment
    variables the run is made without."""
    args: list[str]
    who: str
    label: str
    ok: str
    coverage: Coverage | None = None
    unset: frozenset[str] = frozenset[str]()


def _read_log(stderr: str, coverage: Coverage, cwd: Path) -> tuple[str, set[str]]:
    """A run's stderr without its log, and the files the log names as checked, each
    relative to `cwd` where it lies under it.

    A path is read against `cwd` as printed, and against both resolved only where it
    does not lie under `cwd` as printed, which is what a shortened or linked spelling
    of the same directory needs. A path outside `cwd` either way stays absolute, and
    so names no tracked module.
    """
    kept: list[str] = []
    checked: set[str] = set()
    for line in stderr.splitlines():
        if not coverage.log.match(line):
            kept.append(line)
        elif found := coverage.checked.search(line):
            path = cwd / found.group(1)
            try:
                checked.add(path.relative_to(cwd).as_posix())
            except ValueError:
                try:
                    checked.add(path.resolve().relative_to(cwd.resolve()).as_posix())
                except (ValueError, OSError):
                    checked.add(path.as_posix())
    return "\n".join(kept), checked


def _cover(rep: Reporter, name: str, run: Pass, coverage: Coverage,
           checked: set[str]) -> None:
    """Each tracked module the run's log does not name, as a finding under `name`.

    Nothing is reported for a run that reached every one: the pass's own verdict is
    the line that says what it checked. A log naming no file at all says so first,
    since a changed log shape reads as exactly that.
    """
    missing = sorted(coverage.tracked - checked)
    if not missing:
        return
    lines = [] if checked else [
        f"{run.who} logged no checked file at all, as a log in a shape other than "
        "the pinned version's would"]
    lines.extend(missing[:PER_RULE])
    if len(missing) > PER_RULE:
        lines.append(f"... and {len(missing) - PER_RULE} more")
    rep.report(name, f"tracked module(s) {run.who} did not check:", lines,
               count=len(missing))


def _run_checker(rep: Reporter, name: str, pin: str, passes: list[Pass], cwd: Path,
                 with_stderr: bool, parse: Callable[[str], list[tuple[str, str]]]) -> None:
    """One checker: the pin gate once, then each pass's run, parse and verdict.

    The pin is probed once because it is one fact about one executable: a drifted
    version is one finding, and no pass runs under it.
    """
    exe = _pinned(rep, name, pin)
    if exe is None:
        return
    for run in passes:
        _run_pass(rep, name, exe, run, cwd, with_stderr, parse)


def _run_pass(rep: Reporter, name: str, exe: str, run: Pass, cwd: Path,
              with_stderr: bool, parse: Callable[[str], list[tuple[str, str]]]) -> None:
    """One pass: the run, the parse, and the verdict, reported under `name`.

    A returncode outside (0, 1) is a crash whatever was printed first, so it is
    always reported, beside whatever findings did parse: a checker that died partway
    has not cleared the files it never reached, and its partial list must not read as
    the whole verdict. A checker that hangs or cannot be executed is a finding for
    the same reason the version probe's failures are.

    A pass carrying a `Coverage` has its log taken out of stderr before anything
    else reads it, and once the run has given its verdict, each tracked module the
    log does not name is a finding beside that verdict. A crash is not held to it,
    having already been reported as not clearing what it never reached.

    A pass naming variables in `unset` runs in this process's environment without
    them, and otherwise inherits it whole.
    """
    env = None if not run.unset else {
        key: value for key, value in os.environ.items() if key not in run.unset}
    try:
        done = subprocess.run([exe, *run.args], capture_output=True, encoding="utf-8",
                              errors="replace", cwd=cwd, env=env, check=False,
                              timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        rep.report(name, "checker error(s):",
                   [f"{run.who} gave no verdict within {TIMEOUT}s"])
        return
    except OSError as err:
        rep.report(name, "checker error(s):", [f"{exe} could not be run: {err}"])
        return

    stderr = done.stderr
    checked: set[str] = set()
    if run.coverage is not None:
        stderr, checked = _read_log(done.stderr, run.coverage, cwd)
    findings = parse(done.stdout + stderr if with_stderr else done.stdout)

    if done.returncode == 1 and not findings:
        rep.report(name, "checker error(s):",
                   [f"{run.who} exited 1 but no diagnostic was recognized: "
                    f"{(done.stdout + stderr).strip()[:400] or '(no output)'}"])
        return
    if done.returncode not in (0, 1):
        rep.report(name, "checker error(s):",
                   [f"{run.who} exited {done.returncode}: "
                    f"{(stderr or done.stdout).strip()[:400]}"])
        if not findings:
            return
    _summarize(rep, name, run.label, findings, run.ok)
    if run.coverage is not None and done.returncode in (0, 1):
        _cover(rep, name, run, run.coverage, checked)


def _ty_settings(config: Path) -> list[str]:
    """The `ty.toml` settings the gate refuses, as findings.

    What is held, and nothing else: `[rules]` is exactly `TY_RULES` and `[src]`
    exactly `TY_SRC`; `[analysis]` carries only `TY_ANALYSIS_KEYS` and each
    `[[overrides]]` entry only `TY_OVERRIDE_KEYS`; `[environment]` carries only
    `TY_ENVIRONMENT_KEYS`, with the two names `TY_ENVIRONMENT` gives at exactly its
    values. `--error all` overrides the `[rules]` table, so the gate's own run cannot
    see a lowered entry there; an editor's language server reads the table without
    the flag, which is why the table is held exactly rather than by what it means.
    The flag does not reach the rest, so the keys are held by shape rather than by
    what they say, and an override restating `all = "error"` and an empty
    suppression list are refused too.

    Not held here: the value of `python-version`, which K-75 holds against the
    project's interpreter constraint; `[terminal]`, whose `output-format` the gate's
    own flag overrides and whose `error-on-warning` cannot clear a warning the gate
    reads from the output; and a top-level table or key, or a `[terminal]` key, that
    ty does not accept, which ty refuses as an invalid `ty.toml`, exiting 2 before it
    checks anything, and the gate's run reports as a checker error. A key ty does not
    accept inside `[rules]`, `[src]`, `[analysis]`, `[environment]` or an
    `[[overrides]]` entry is refused here as well, being outside what each admits.

    Fail-closed: a file that cannot be read or parsed, an `overrides` value that is
    not an array of tables, or an `analysis` or `environment` value that is not a
    table is a finding, never a pass, and a key the gate has not admitted is
    refused, never assumed harmless.
    """
    name = f"tools/{config.name}"
    try:
        settings = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as err:
        return [f"{name} cannot be read: {err}"]

    findings: list[str] = []
    rules = settings.get("rules")
    if rules != TY_RULES:
        found = "carries no [rules] table" if rules is None else f"sets [rules] to {rules!r}"
        findings.append(f"{name} {found}; the gate holds it to exactly {TY_RULES!r}, "
                        "the table an editor's ty server reads without --error all")
    src = settings.get("src")
    if src != TY_SRC:
        found = "carries no [src] table" if src is None else f"sets [src] to {src!r}"
        findings.append(f"{name} {found}; the gate holds it to exactly {TY_SRC!r}, "
                        "because an include, a further exclude, exclude-scripts or "
                        "honoring ignore files takes files out of the run")
    analysis = settings.get("analysis", {})
    if not isinstance(analysis, dict):
        findings.append(f"{name}'s analysis must be a table, found {analysis!r}")
    elif refused := sorted(set(analysis) - TY_ANALYSIS_KEYS):
        findings.append(
            f"{name}'s [analysis] carries "
            + ", ".join(f"{key} {analysis[key]!r}" for key in refused)
            + f"; the gate admits only {', '.join(sorted(TY_ANALYSIS_KEYS))}, "
            "the settings that suppress no diagnostic the defaults report")
    held = " and ".join(f"{key} to {value!r}" for key, value in TY_ENVIRONMENT.items())
    why = ("because the platform decides which sys.platform branches an editor's ty "
           "checks and extra-paths comes first in resolving every import")
    environment = settings.get("environment")
    if environment is None:
        findings.append(f"{name} carries no [environment] table; the gate holds {held}, {why}")
    elif not isinstance(environment, dict):
        findings.append(f"{name}'s environment must be a table, found {environment!r}")
    else:
        if refused := sorted(set(environment) - TY_ENVIRONMENT_KEYS):
            findings.append(
                f"{name}'s [environment] carries "
                + ", ".join(f"{key} {environment[key]!r}" for key in refused)
                + f"; the gate admits only {', '.join(sorted(TY_ENVIRONMENT_KEYS))}, "
                "because python, root and typeshed each move where ty resolves imports, "
                "and a key the gate has not read is refused with them")
        if changed := [key for key, want in TY_ENVIRONMENT.items()
                       if environment.get(key) != want]:
            findings.append(
                f"{name}'s [environment] "
                + ", ".join(f"sets {key} to {environment[key]!r}" if key in environment
                            else f"carries no {key}" for key in changed)
                + f"; the gate holds {held}, {why}")
    overrides = settings.get("overrides", [])
    if not isinstance(overrides, list) or not all(isinstance(o, dict) for o in overrides):
        findings.append(f"{name}'s overrides must be an array of tables, found {overrides!r}")
        return findings
    for index, entry in enumerate(overrides, start=1):
        if carried := sorted(set(entry) - TY_OVERRIDE_KEYS):
            findings.append(
                f"{name}'s [[overrides]] entry {index} (include {entry.get('include')!r}) "
                "carries " + ", ".join(f"{key} {entry[key]!r}" for key in carried)
                + "; an entry may carry only include and exclude, because its rules can "
                "lower --error all and its analysis can suppress diagnostics for the "
                "files it matches")
    return findings


def _user_config() -> Path | None:
    """The user-level `ty.toml` ty merges beneath the one it is given, if one exists.

    ty reads `ty/ty.toml` under the user configuration directory: `%APPDATA%` on
    Windows, or the roaming application-data folder when that is unset or empty,
    which this reads as `AppData\\Roaming` under the home directory; and
    `$XDG_CONFIG_HOME` on Linux and macOS when it is an absolute path, else
    `~/.config`. The environment is the one the gate's own ty inherits.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", "")
        fallback = ("AppData", "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", "")
        base = base if Path(base).is_absolute() else ""
        fallback = (".config",)
    if base:
        directory = Path(base)
    else:
        try:
            directory = Path.home().joinpath(*fallback)
        except RuntimeError:
            return None
    candidate = directory / "ty" / "ty.toml"
    return candidate if candidate.is_file() else None


def _tracked(root: Path) -> frozenset[str]:
    """The modules the index tracks under `tools/` that the working tree holds, each
    relative to `tools/`.

    A tracked module deleted from the working tree is left out, since no run can
    check it and the deletion is the index's to record. A module a run reaches that
    the index does not track is held to nothing: this is a floor, not a ceiling.
    """
    return frozenset(path.removeprefix(TOOLS) for path in corpus_mod.read_index(root).files
                     if path.startswith(TOOLS) and path.endswith(MODULE_SUFFIXES)
                     and (root / path).is_file())


def _run_ty(rep: Reporter, root: Path, tracked: frozenset[str] | None) -> None:
    """Every expression in the directory reachable under each of `TY_PLATFORMS`,
    against the types ty can infer for it, one run and one verdict per platform, and
    each run held to reaching every module in `tracked` unless that is `None`.

    The settings are held first and the checker runs regardless: a refused setting
    stands beside the checker's verdict rather than hiding the findings it would
    still report, and that verdict then claims no more than the run showed. A
    user-level configuration is reported rather than redirected away from, because
    ty merges it into this run and the finding is what tells its owner so.

    A set `PYTHONPATH` is reported on the same ground rather than removed from ty's
    environment. ty searches each directory it names just after `extra-paths` and
    ahead of the standard library, which is what `typeshed` and a further
    `extra-paths` entry are refused for; an editor's ty server inherits the variable
    as this run does, so removing it here alone would pass what the editor resolves
    differently. The variable is reported whenever it is present, an empty value
    included, because ty reads it whenever it is present. `TY_UNSET` is removed
    instead, since neither of its variables changes what ty checks or reports."""
    tools = root / "tools"
    held = ", all rules at error"
    if refused := _ty_settings(tools / "ty.toml"):
        rep.report("ty", "ty.toml setting(s) the gate refuses:", refused)
        held = " under the settings refused above"
    if (user := _user_config()) is not None:
        rep.report("ty", "user-level configuration(s) the gate refuses:",
                   [f"a user-level ty configuration at {user} merges into the gate's run"])
        held = " under the settings refused above"
    if (search := os.environ.get("PYTHONPATH")) is not None:
        rep.report("ty", "environment variable(s) the gate refuses:",
                   [f"PYTHONPATH is set to {search!r}, and ty searches each directory it "
                    "names ahead of the standard library in the gate's run"])
        held = " under the settings refused above"
    coverage = None if tracked is None else Coverage(TY_LOG, TY_CHECKED, tracked)
    verbose = [] if coverage is None else TY_VERBOSE
    _run_checker(
        rep, "ty", TY_VERSION,
        [Pass(["check", "--config-file", str(tools / "ty.toml"), "--error", "all",
               "--python", sys.executable, "--python-platform", platform,
               "--output-format", "concise", "--color", "never", *verbose, "."],
              f"ty under python-platform {platform}",
              f"type error(s) under python-platform {platform}:",
              f"every expression reachable under python-platform {platform} typechecks "
              f"under ty {TY_VERSION}{held}", coverage, TY_UNSET)
         for platform in TY_PLATFORMS],
        tools, with_stderr=True, parse=_parse_ty)


def _ruff_settings(config: Path) -> list[str]:
    """The `ruff.toml` settings the gate refuses, as findings: a `RUFF_PER_FILE` key in
    `[lint]` or at the top level, and an `extend` key, which merges the settings of a
    file the gate does not read beneath this one's. Each is refused whatever it says, an
    empty table included, as ty.toml's `[src]` is held by shape.

    Fail-closed: a file that cannot be read or parsed is a finding. A `lint` value that
    is not a table is ruff's to refuse, which it does as an invalid configuration before
    it checks anything, and the gate's run reports as a checker error."""
    name = f"tools/{config.name}"
    try:
        settings = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as err:
        return [f"{name} cannot be read: {err}"]
    lint = settings.get("lint")
    tables = [("", settings), *([("lint.", lint)] if isinstance(lint, dict) else [])]
    findings = [f"{name} sets {prefix}{key} to {table[key]!r}; a rule switched off for the "
                "files a pattern matches is refused, since ruff's log names a file whose "
                "rules are off as checked"
                for prefix, table in tables for key in RUFF_PER_FILE if key in table]
    if "extend" in settings:
        findings.append(f"{name} sets extend to {settings['extend']!r}; the gate reads only "
                        "this file, and extend merges another file's settings beneath it")
    return findings


def _file_suppressions(tools: Path, tracked: frozenset[str]) -> list[str]:
    """Each comment in a tracked module carrying a suppression that reaches past its own
    line: a file-level `noqa` naming a rule outside `FILE_SCOPED`, or naming none, which
    suppresses every rule, and any comment `FILE_RANGE` matches.

    Comments are read with the tokenizer, so a string that spells a directive is not
    one, and only a module whose text matches `FILE_NOQA` or `FILE_RANGE` is tokenized.
    A directive ruff would ignore, for trailing code or another comment before it on its
    line or for sitting in a class or function body, is refused all the same.
    Fail-closed: a module that cannot be read or tokenized is a finding."""
    findings: list[str] = []
    for module in sorted(tracked):
        try:
            text = (tools / module).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            findings.append(f"{module} cannot be read: {err}")
            continue
        if not (FILE_NOQA.search(text) or FILE_RANGE.search(text)):
            continue
        try:
            comments = [(token.start[0], token.string)
                        for token in tokenize.generate_tokens(io.StringIO(text).readline)
                        if token.type == tokenize.COMMENT]
        except (tokenize.TokenError, SyntaxError) as err:
            findings.append(f"{module} cannot be tokenized: {err}")
            continue
        findings.extend(f"{module}:{line} {comment}" for line, comment in comments
                        if FILE_RANGE.search(comment)
                        or any(not _names_file_scoped(comment[found.end():])
                               for found in FILE_NOQA.finditer(comment)))
    return findings


def _names_file_scoped(rest: str) -> bool:
    """Whether the text after a directive's `noqa` names rules, each in `FILE_SCOPED`.

    Every code in the run of capitals, digits, commas and whitespace after the colon is
    read, which is each code ruff reads and possibly more; a directive naming none
    suppresses every rule."""
    named = re.match(r"\s*:([A-Z0-9,\s]*)", rest)
    codes = set(re.findall(r"[A-Z]+[0-9]+", named.group(1))) if named else set()
    return bool(codes) and codes <= FILE_SCOPED


def _run_ruff(rep: Reporter, root: Path, tracked: frozenset[str] | None) -> None:
    """Every function, against whether it is annotated, and the correctness rules
    `ruff.toml` admits besides, with the run held to reaching every module in
    `tracked` unless that is `None`.

    `--no-respect-gitignore` restates `ruff.toml`'s `respect-gitignore = false` for
    this run: ruff otherwise skips whatever an ignore file matches, and a tracked
    module an ignore pattern matched would leave the run with nothing reported. The
    run's log is what holds the rest, `lint.exclude` among them, which drops a file
    from the lint but not from what `--show-files` lists.

    The log still names a file whose rules are switched off, so the suppressions that
    switch rules off past a line are held first: the `ruff.toml` keys `_ruff_settings`
    refuses, and the file-level and range directives `_file_suppressions` finds in the
    tracked modules. The checker runs regardless, and a clean run beside a refused
    suppression claims no more than the run showed."""
    tools = root / "tools"
    held = ""
    if refused := _ruff_settings(tools / "ruff.toml"):
        rep.report("ruff", "ruff.toml setting(s) the gate refuses:", refused)
        held = " under the suppressions refused above"
    if tracked is not None and (suppressed := _file_suppressions(tools, tracked)):
        rep.report("ruff", "file-level or range suppression(s) the gate refuses:",
                   suppressed)
        held = " under the suppressions refused above"
    coverage = None if tracked is None else Coverage(RUFF_LOG, RUFF_CHECKED, tracked)
    verbose = [] if coverage is None else RUFF_VERBOSE
    _run_checker(
        rep, "ruff", RUFF_VERSION,
        [Pass(["check", "--config", str(tools / "ruff.toml"), "--no-cache",
               "--no-respect-gitignore",
               "--output-format", "concise", "--no-fix", *verbose, "."],
              "ruff", "lint finding(s):",
              f"every function is annotated and ruff {RUFF_VERSION} is clean{held}",
              coverage)],
        tools, with_stderr=False, parse=_parse_ruff)


def _banned(config: Path) -> tuple[frozenset[str], list[str]]:
    """The modules `ruff.toml` bans at module level, or none and why, as findings.

    Fail-closed: a file that cannot be read or parsed, and a list that is absent, empty
    or holds anything but module names, is a finding, since the scan would then hold no
    import to anything."""
    name = f"tools/{config.name}"
    none = frozenset[str]()
    try:
        settings = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as err:
        return none, [f"{name} cannot be read: {err}"]
    listed: object = settings
    for key in BANNED:
        listed = listed.get(key) if isinstance(listed, dict) else None
    modules = [module for module in listed if isinstance(module, str) and module] \
        if isinstance(listed, list) else []
    if not modules or not isinstance(listed, list) or len(modules) != len(listed):
        return none, [f"{name} sets {'.'.join(BANNED)} to {listed!r}; the gate holds "
                      "imports to a non-empty list of module names"]
    return frozenset(modules), []


def _banned_names(node: ast.Import | ast.ImportFrom, banned: frozenset[str]) -> list[str]:
    """The modules `node` imports that `banned` names or is a parent of, matched as
    TID253 matches them: each name an `import` gives, and a `from` import's module or,
    where that is not banned, each member it names, since a member can be a submodule.
    A relative import names the tools' own packages and never a banned module."""
    def listed(module: str) -> bool:
        return any(module == ban or module.startswith(ban + ".") for ban in banned)

    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names if listed(alias.name)]
    if node.level or node.module is None:
        return []
    if listed(node.module):
        return [node.module]
    return [member for alias in node.names
            if alias.name != "*" and listed(member := f"{node.module}.{alias.name}")]


def _reads_platform(test: ast.expr) -> bool:
    """Whether an `if` condition reads `sys.platform`."""
    return any(isinstance(node, ast.Attribute) and node.attr == "platform"
               and isinstance(node.value, ast.Name) and node.value.id == "sys"
               for node in ast.walk(test))


def _platform_imports(tree: ast.Module, banned: frozenset[str]) -> list[tuple[int, list[str]]]:
    """Each import of a module `banned` names, with its line and the modules it names,
    that runs outside a function body with no enclosing `if` reading `sys.platform`.

    A function body runs only when the function is called, and an `if` that reads
    `sys.platform` keeps both its branches off the platform its test excludes, so the
    walk does not descend into either. Everything else it descends into: an unnested
    module-level statement, a class body, and any module-level or class-level block."""
    found: list[tuple[int, list[str]]] = []
    stack: list[ast.AST] = [tree]
    while stack:
        for child in ast.iter_child_nodes(stack.pop()):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) or (
                    isinstance(child, ast.If) and _reads_platform(child.test)):
                continue
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                if names := _banned_names(child, banned):
                    found.append((child.lineno, names))
            else:
                stack.append(child)
    return sorted(found)


def _run_imports(rep: Reporter, root: Path, tracked: frozenset[str]) -> None:
    """Every tracked module, against an import of a module `ruff.toml` bans at module
    level anywhere outside a function body with no enclosing `if` reading `sys.platform`.

    TID253 refuses such an import only where it is unnested at module level, and with
    the module banned PLC0415 no longer reports it in a class body; neither reads a
    module-level block. A module whose text never spells the last component of a banned
    name as a word cannot import it, so only the rest are parsed. Fail-closed: a module
    that cannot be read or parsed is a finding."""
    tools = root / "tools"
    banned, unread = _banned(tools / "ruff.toml")
    if unread:
        rep.report("imports", "ruff.toml list(s) the gate cannot read:", unread)
        return
    spelled = re.compile(r"\b(?:" + "|".join(sorted(re.escape(ban.rpartition(".")[2])
                                                    for ban in banned)) + r")\b")
    findings: list[str] = []
    for module in sorted(tracked):
        try:
            text = (tools / module).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            findings.append(f"{module} cannot be read: {err}")
            continue
        if not spelled.search(text):
            continue
        try:
            tree = ast.parse(text, module)
        except (SyntaxError, ValueError) as err:
            findings.append(f"{module} cannot be parsed: {err}")
            continue
        findings.extend(f"{module}:{line} imports {', '.join(names)} outside a function "
                        "body, behind no sys.platform check"
                        for line, names in _platform_imports(tree, banned))
    rep.report("imports", "import(s) of a module ruff.toml bans at module level outside a "
               "function body:", findings,
               "every import of a module ruff.toml bans at module level sits in a function "
               "body or behind a sys.platform check")


def run(root: Path) -> Reporter:
    """One whole run, as data, on the convention `check.py` set: the caller decides
    what to do with the verdict rather than parsing what was printed.

    The two checkers are separate processes over the same tree and neither reads the
    other's result, so they run concurrently, and the import scan beside them. Each
    accumulates onto its own slate and the slates are merged ty, ruff, then the scan,
    so the report reads the same however they finished.

    The tracked modules are read once for all three. An index that cannot be read is a
    finding, and the runs then go ahead held to nothing, since no floor can be
    decided without it, and the scan, which has no modules to read, does not run."""
    rep = Reporter()
    rep.line("=== tools ===")

    tracked: frozenset[str] | None = None
    try:
        tracked = _tracked(root)
    except (RuntimeError, OSError, ValueError) as err:
        rep.report("coverage", "tracked module listing error(s):",
                   [f"the index cannot be read, so no run is held to the modules it "
                    f"tracks: {err}"])

    ty_rep, ruff_rep, imports_rep = Reporter(), Reporter(), Reporter()
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks = [pool.submit(_run_ty, ty_rep, root, tracked),
                 pool.submit(_run_ruff, ruff_rep, root, tracked)]
        if tracked is not None:
            tasks.append(pool.submit(_run_imports, imports_rep, root, tracked))
        for done in tasks:
            done.result()
    for part in (ty_rep, ruff_rep, imports_rep):
        rep.out.extend(part.out)
        rep.findings += part.findings

    if rep.findings:
        rep.line(f"{rep.findings} finding(s).")
    else:
        rep.line("the tools hold to their own discipline.")
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Typecheck and lint this repository's own tools.")
    parser.parse_args(argv)

    report = run(corpus_mod.find_root())
    print("\n".join(report.out))
    return 1 if report.findings else 0
