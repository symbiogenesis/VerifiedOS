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

ty is asked for `--error all`, which escalates every rule it carries, including the
ones it ships as warnings or switched off. `ty.toml` and `ruff.toml` hold the rest
of the settings, so an editor's language server decides what this decides.

Exit 0 clean, 1 on any finding. It may be run from anywhere: the repository root is
found from this file, never from the working directory.
"""

import argparse
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from vos import corpus as corpus_mod
from vos.report import Reporter

# The pins. Both are recorded in tools/README.md, and both are installed with
# `uv tool install <name>==<v>` on either lane, one command per checker because that
# is what uv's tool installs are: one environment each, holding one pinned tool and
# nothing else. Neither is a dependency of anything here, so neither belongs in the
# environment ty resolves this directory's imports against.
TY_VERSION = "0.0.74"
RUFF_VERSION = "0.16.4"

# How many findings of one rule are printed before the rest are counted. A run that
# has just switched a rule on is a list of hundreds of one thing, and the verdict is
# the count; the individual sites are what the editor is for.
PER_RULE = 8

# The bound every subprocess must answer within, version probes included. Both
# checkers finish in about a second on this tree, so a run that reaches it is hung,
# and a hung checker must become a finding rather than a gate that never returns.
TIMEOUT = 120


def _uv_tool_bin() -> Path:
    """Where `uv tool install` drops its shims, resolved the way uv resolves it.

    Asked of the environment rather than of `uv tool dir --bin`, so that a lane which
    has the tools uv installed but not uv itself on `PATH` still finds them, and so
    that the lookup costs no subprocess and carries no timeout of its own.
    """
    for variable in ("UV_TOOL_BIN_DIR", "XDG_BIN_HOME"):
        if directory := os.environ.get(variable):
            return Path(directory)
    return Path.home() / ".local" / "bin"


def _tool(name: str) -> str | None:
    """The checker's executable, preferring the isolated install this tree asks for.

    Both are installed with `uv tool install`, which gives each checker its own
    environment and drops a shim in uv's tool bin directory rather than into any
    interpreter's site-packages. That is what makes the pinned checker the same one
    whichever interpreter runs this file, and what keeps two developer tools out of
    the environment ty resolves this directory's own imports against.

    Three places are looked at and the order decides which install wins. uv's tool
    bin directory is first, because it is where this tree says to put them. The
    interpreter's own script directories are second, because a virtual environment
    carrying the checkers is still a correct place to have them and was the only
    place before uv; there are two of those and the lane decides which, a POSIX
    interpreter and a Windows virtual environment putting `python` and its console
    scripts in one directory while a Windows *system* install puts `python.exe` at
    the root of the installation and its scripts in `Scripts/` beside it. `PATH` is
    last, and answers for a lane that puts them somewhere else entirely.

    All three are kept rather than the first alone. Looking only at the interpreter
    made a stock host install read as *not installed* however many times it was
    installed, and looking only at uv's directory would do exactly the same to a venv
    that has them; a pinned-version gate is the one thing that must not report absent
    what is present.
    """
    suffix = ".exe" if sys.platform == "win32" else ""
    root = Path(sys.executable).parent
    for directory in (_uv_tool_bin(), root, root / "Scripts"):
        candidate = directory / (name + suffix)
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)


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
                   [f"{name} {pin} is not in {_uv_tool_bin()}, beside {sys.executable}, "
                    f"or on PATH: uv tool install {name}=={pin}"])
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
                    f"uv tool install {name}=={pin}"])
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

    if done.returncode not in (0, 1):
        rep.report(name, "checker error(s):",
                   [f"{name} exited {done.returncode}: "
                    f"{(done.stderr or done.stdout).strip()[:400]}"])
        if not findings:
            return
    _summarize(rep, name, label, findings, ok)


def _run_ty(rep: Reporter, root: Path) -> None:
    """Every expression in the directory, against the types ty can infer for it."""
    tools = root / "tools"
    _run_checker(
        rep, "ty", TY_VERSION,
        ["check", "--config-file", str(tools / "ty.toml"), "--error", "all",
         "--output-format", "concise", "--color", "never", "."],
        tools, with_stderr=True, parse=_parse_ty, label="type error(s):",
        ok=f"every expression typechecks under ty {TY_VERSION}, all rules at error")


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

