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
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import corpus as corpus_mod
from vos.report import Reporter

# The pins. Both are recorded in tools/README.md, and both are installed with
# `pip install ty==<v> ruff==<v>` on either lane; neither needs a toolchain beyond
# pip, which is what kept them in reach of a directory that is one language.
TY_VERSION = "0.0.73"
RUFF_VERSION = "0.16.4"

# How many findings of one rule are printed before the rest are counted. A run that
# has just switched a rule on is a list of hundreds of one thing, and the verdict is
# the count; the individual sites are what the editor is for.
PER_RULE = 8


def _tool(name: str) -> str | None:
    """The checker's executable, preferring the interpreter's own environment.

    Both ship as console scripts beside the running interpreter, so a virtual
    environment that has them is found without being activated, which is what makes
    this runnable from an editor and from a shell with the same result.
    """
    beside = Path(sys.executable).parent / (name + (".exe" if sys.platform == "win32" else ""))
    if beside.is_file():
        return str(beside)
    return shutil.which(name)


def _version(exe: str) -> str:
    """The version a checker reports, reduced to its number.

    Both spell it `<name> <version>` and ty adds its build and date, so the second
    token is the whole of what is compared.
    """
    done = subprocess.run([exe, "--version"], capture_output=True, text=True, check=False)
    parts = (done.stdout.strip() or done.stderr.strip()).split()
    return parts[1] if len(parts) > 1 else "unknown"


def _pinned(rep: Reporter, name: str, pin: str) -> str | None:
    """The checker to run, or `None` having already reported why there is not one."""
    exe = _tool(name)
    if exe is None:
        rep.report(name, "not installed:", [f"{name} {pin} is not on PATH or beside "
                                            f"{sys.executable}: pip install {name}=={pin}"])
        return None
    found = _version(exe)
    if found != pin:
        rep.report(name, "version(s) other than the pinned one:",
                   [f"{name} {found} is installed and this tree pins {pin}: "
                    f"pip install {name}=={pin}"])
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
    rep.report(rule, label, lines, ok)


def _run_ty(rep: Reporter, root: Path) -> None:
    """Every expression in the directory, against the types ty can infer for it."""
    exe = _pinned(rep, "ty", TY_VERSION)
    if exe is None:
        return

    tools = root / "tools"
    done = subprocess.run(
        [exe, "check", "--config-file", str(tools / "ty.toml"), "--error", "all",
         "--output-format", "concise", "--color", "never", "."],
        capture_output=True, text=True, cwd=tools, check=False)

    findings = []
    for line in (done.stdout + done.stderr).splitlines():
        # `path:line:col: error[rule-name] message`, and the trailing summary line
        if "] " not in line or (": error[" not in line and ": warning[" not in line):
            continue
        where, _, rest = line.partition(": ")
        code = rest.partition("[")[2].partition("]")[0]
        findings.append((code, f"{where} {rest.partition('] ')[2]}"))

    if done.returncode not in (0, 1) and not findings:
        rep.report("ty", "checker error(s):",
                   [f"ty exited {done.returncode}: {(done.stderr or done.stdout).strip()[:400]}"])
        return

    _summarize(rep, "ty", "type error(s):", findings,
               f"every expression typechecks under ty {TY_VERSION}, all rules at error")


def _run_ruff(rep: Reporter, root: Path) -> None:
    """Every function, against whether it is annotated, and the correctness rules
    `ruff.toml` admits besides."""
    exe = _pinned(rep, "ruff", RUFF_VERSION)
    if exe is None:
        return

    tools = root / "tools"
    done = subprocess.run(
        [exe, "check", "--config", str(tools / "ruff.toml"), "--no-cache",
         "--output-format", "concise", "--no-fix", "."],
        capture_output=True, text=True, cwd=tools, check=False)

    findings = []
    for line in done.stdout.splitlines():
        # `path:line:col: CODE message`
        head, _, rest = line.partition(": ")
        code, _, message = rest.partition(" ")
        if not head or not code or not code[0].isalpha() or not code[-1].isdigit():
            continue
        findings.append((code, f"{head} {message}"))

    if done.returncode not in (0, 1) and not findings:
        rep.report("ruff", "checker error(s):",
                   [f"ruff exited {done.returncode}: {(done.stderr or done.stdout).strip()[:400]}"])
        return

    _summarize(rep, "ruff", "lint finding(s):", findings,
               f"every function is annotated and ruff {RUFF_VERSION} is clean")


def run(root: Path) -> Reporter:
    """One whole run, as data, on the convention `check.py` set: the caller decides
    what to do with the verdict rather than parsing what was printed."""
    rep = Reporter()
    rep.line("=== tools ===")
    _run_ty(rep, root)
    _run_ruff(rep, root)

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


if __name__ == "__main__":
    sys.exit(main())
