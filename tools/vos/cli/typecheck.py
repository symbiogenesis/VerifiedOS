#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Hold this directory's own Python to the discipline it holds the documents to.

`check.py` checks the documents against each other. Nothing checked the tool that
does the checking, and the tools are the one artifact in this repository with no
proof, no model, and no reviewer but the person who wrote them. This is that gate.

It runs two checkers, because one of them cannot do the whole job:

    ty     the types      every expression, against the types it can infer
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

Every rule ty carries runs at error, including the ones it ships as warnings or
switched off. `ty.toml` states that in its `[rules]` table, and it and `ruff.toml`
hold the rest of the settings, so an editor's language server decides what this
decides. The gate also passes ty `--error all`, which overrides the `[rules]`
table, and it reads `ty.toml` itself. Each of these is a ty finding, because an
editor reads the file without the flag or because the flag cannot restore what the
setting takes away:

    [rules]        a table other than exactly `all = "error"`
    [[overrides]]  an entry carrying any key but `include` and `exclude`: its
                   `rules` can lower the flag's severities, and its `analysis` can
                   suppress diagnostics, for the files it matches
    [analysis]     a key outside the ones that suppress nothing, which refuses
                   `allowed-unresolved-imports` and `replace-imports-with-any`
    [src]          a table other than exactly `exclude = ["**/__pycache__/**"]` and
                   `respect-ignore-files = false`, since an `include`, a further
                   `exclude`, `exclude-scripts` or honoring ignore files takes
                   files out of the run

Exit 0 clean, 1 on any finding. It may be run from anywhere: the repository root is
found from this file, never from the working directory.
"""

import argparse
import subprocess
import sys
import sysconfig
import tomllib
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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

# How many findings of one rule are printed before the rest are counted. A run that
# has just switched a rule on is a list of hundreds of one thing, and the verdict is
# the count; the individual sites are what the editor is for.
PER_RULE = 8

# The bound every subprocess must answer within, version probes included. Both
# checkers finish in about a second on this tree, so a run that reaches it is hung,
# and a hung checker must become a finding rather than a gate that never returns.
TIMEOUT = 120


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


def _run_checker(rep: Reporter, name: str, pin: str, args: list[str], cwd: Path,
                 with_stderr: bool, parse: Callable[[str], list[tuple[str, str]]],
                 label: str, ok: str) -> None:
    """One checker: the pin gate, the run, the parse, and the verdict.

    A returncode outside (0, 1) is a crash whatever was printed first, so it is
    always reported, beside whatever findings did parse: a checker that died partway
    has not cleared the files it never reached, and its partial list must not read as
    the whole verdict. A checker that hangs or cannot be executed is a finding for
    the same reason the version probe's failures are.
    """
    exe = _pinned(rep, name, pin)
    if exe is None:
        return

    try:
        done = subprocess.run([exe, *args], capture_output=True, encoding="utf-8",
                              errors="replace", cwd=cwd, check=False, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        rep.report(name, "checker error(s):",
                   [f"{name} gave no verdict within {TIMEOUT}s"])
        return
    except OSError as err:
        rep.report(name, "checker error(s):", [f"{exe} could not be run: {err}"])
        return

    findings = parse(done.stdout + done.stderr if with_stderr else done.stdout)

    if done.returncode == 1 and not findings:
        rep.report(name, "checker error(s):",
                   [f"{name} exited 1 but no diagnostic was recognized: "
                    f"{(done.stdout + done.stderr).strip()[:400] or '(no output)'}"])
        return
    if done.returncode not in (0, 1):
        rep.report(name, "checker error(s):",
                   [f"{name} exited {done.returncode}: "
                    f"{(done.stderr or done.stdout).strip()[:400]}"])
        if not findings:
            return
    _summarize(rep, name, label, findings, ok)


def _ty_settings(config: Path) -> list[str]:
    """Whatever in `ty.toml` would split the editor from the gate or narrow the gate.

    `--error all` overrides the `[rules]` table, so the gate's own run cannot see a
    lowered entry there; an editor's language server reads the table without the
    flag, which is why the table is held exactly rather than by what it means. The
    flag does not reach the rest, so it is held by shape: an `[[overrides]]` entry
    carries only `TY_OVERRIDE_KEYS`, `[analysis]` only `TY_ANALYSIS_KEYS`, and
    `[src]` is exactly `TY_SRC`. The shape is held rather than the values, so an
    override restating `all = "error"` and an empty suppression list are refused too.

    Fail-closed: a file that cannot be read or parsed, an `overrides` value that is
    not an array of tables, or an `analysis` value that is not a table is a finding,
    never a pass, and a key the gate has not admitted is refused, never assumed
    harmless.
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


def _run_ty(rep: Reporter, root: Path) -> None:
    """Every expression in the directory, against the types ty can infer for it.

    The settings are held first and the checker runs regardless: a refused setting
    stands beside the checker's verdict rather than hiding the findings it would
    still report, and that verdict then claims no more than the run showed."""
    tools = root / "tools"
    held = ", all rules at error"
    if refused := _ty_settings(tools / "ty.toml"):
        rep.report("ty", "ty.toml setting(s) the gate refuses:", refused)
        held = " under the settings refused above"
    _run_checker(
        rep, "ty", TY_VERSION,
        ["check", "--config-file", str(tools / "ty.toml"), "--error", "all",
         "--python", sys.executable,
         "--output-format", "concise", "--color", "never", "."],
        tools, with_stderr=True, parse=_parse_ty, label="type error(s):",
        ok=f"every expression typechecks under ty {TY_VERSION}{held}")


def _run_ruff(rep: Reporter, root: Path) -> None:
    """Every function, against whether it is annotated, and the correctness rules
    `ruff.toml` admits besides."""
    tools = root / "tools"
    _run_checker(
        rep, "ruff", RUFF_VERSION,
        ["check", "--config", str(tools / "ruff.toml"), "--no-cache",
         "--output-format", "concise", "--no-fix", "."],
        tools, with_stderr=False, parse=_parse_ruff, label="lint finding(s):",
        ok=f"every function is annotated and ruff {RUFF_VERSION} is clean")


def run(root: Path) -> Reporter:
    """One whole run, as data, on the convention `check.py` set: the caller decides
    what to do with the verdict rather than parsing what was printed.

    The two checkers are separate processes over the same tree and neither reads the
    other's result, so they run concurrently. Each accumulates onto its own slate and
    the slates are merged ty-then-ruff, so the report reads the same however the two
    finished."""
    rep = Reporter()
    rep.line("=== tools ===")

    ty_rep, ruff_rep = Reporter(), Reporter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        for done in (pool.submit(_run_ty, ty_rep, root),
                     pool.submit(_run_ruff, ruff_rep, root)):
            done.result()
    for part in (ty_rep, ruff_rep):
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
