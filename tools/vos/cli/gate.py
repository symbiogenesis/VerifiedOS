# SPDX-License-Identifier: Apache-2.0
"""Synchronize instructions, then validate the checkout with one host-gate verdict.

The default synchronizes AGENTS.md and CLAUDE.md before any reader starts. `--check`
is read-only and leaves disagreement for K-110. `--fix` synchronizes, repairs derived
facts alone, then runs a fresh read-only checker alongside the selftest and typecheck.
Repair findings describe the old tree; only the final wave decides the repaired tree.
A failed sync or a repair without a verdict stops before that wave.

Independent gates run concurrently and report in declaration order. `--tests` adds the
tools' behavioral tests; those stay optional to keep document checks small and avoid
recursive test launches. Exit 0 means every final gate passed, 1 otherwise.
"""

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from vos import corpus as corpus_mod
from vos.cli import sync_instructions
from vos.report import Reporter

HEADING = "=== gate: every host gate over this tree, in one run ==="

# The bound a member must answer within. The selftest is the only one that comes
# near a minute, and it is a whole checker run per rule over sandboxes it builds
# first, so the bound is sized for a cold cache on a slow machine rather than for
# the half-minute it takes here. A member that reaches it is hung, and a hung gate
# must become a finding rather than a command that never returns.
TIMEOUT = 900

# What a member that never answered exited with. It has no code of its own, and a
# number outside the (0, 1) the conventions define is what makes it read as the
# crash it is rather than as the finding it is not.
NO_VERDICT = -1


@dataclass(frozen=True)
class Launch:
    """One member: the command, the arguments it takes here, and what it decides."""

    tool: str
    args: tuple[str, ...]
    decides: str

    @property
    def name(self) -> str:
        """How the member is named in the report, which is the command that ran."""
        return " ".join((self.tool, *self.args))


@dataclass
class Result:
    """What one member answered: its own whole output, and the code it exited."""

    launch: Launch
    code: int
    out: list[str]


MEMBERS: tuple[Launch, ...] = (
    Launch("check", (), "every derived fact against the artifact that owns it"),
    Launch("selftest", (), "every rule the checker carries, against its mutant"),
    Launch("typecheck", (), "the tools' own Python, under two pinned checkers"),
)

# The member `--tests` adds, named here rather than spelled at its call site so that
# the wave's membership is one table.
TESTS = Launch("test", (), "the tools' own behavior, against the cases that hold it")

# The one member with a --fix branch, named rather than taken by position so that
# reordering the table above cannot quietly move which member the repair wave holds.
REPAIRS = "check"


def _plan(fix: bool, tests: bool) -> list[list[Launch]]:
    """An optional isolated repair, then every read-only gate, including a fresh check."""
    members = [*MEMBERS, *([TESTS] if tests else [])]
    if not fix:
        return [members]
    repair = [Launch(m.tool, (*m.args, "--fix"), m.decides)
              for m in members if m.tool == REPAIRS]
    return [repair, members]


def _launch(root: Path, member: Launch) -> Result:
    """One member, in its own process, as what it printed and the code it exited.

    A subprocess rather than an import, and for reasons rather than for symmetry.
    The selftest reports by printing as it goes rather than by handing back a slate,
    so its verdict is a stream and this is what reads it. And a member's exit code is
    its own to decide, which keeps this tool from re-deriving three verdicts it would
    then have to keep in agreement with three `main` functions.

    Neither of the two ways a run can fail short of a verdict is allowed to become
    a traceback here: a member that hangs and a member that cannot be executed are
    both findings, on the convention typecheck.py's own runner keeps.
    """
    argv = [sys.executable, str(root / "tools" / "run.py"), member.tool, *member.args]
    try:
        done = subprocess.run(argv, capture_output=True, encoding="utf-8",
                              errors="replace", cwd=root, check=False, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return Result(member, NO_VERDICT,
                      [f"{member.name} gave no verdict within {TIMEOUT}s"])
    except OSError as err:
        return Result(member, NO_VERDICT, [f"{member.name} could not be run: {err}"])
    # stderr after stdout and never instead of it: a member reports on stdout, so
    # anything on stderr is what it said while dying and belongs under its heading
    # rather than lost.
    return Result(member, done.returncode, (done.stdout + done.stderr).splitlines())


def _show(rep: Reporter, result: Result) -> None:
    """Keep a process's diagnostic output even when a later check supersedes it."""
    rep.line(f"--- {result.launch.name}: {result.launch.decides} ---")
    rep.out.extend(result.out)
    rep.line()


def _verdict(rep: Reporter, results: list[Result]) -> None:
    """Every member's own report under its own heading, then the line over them all.

    A member that exited 1 has already printed the findings it is being counted
    for, so what is said here is which member to go and read. A member that exited
    anything else printed no verdict at all, and saying so is the difference
    between a tree with a finding in it and a tool that did not run.
    """
    for result in results:
        _show(rep, result)

    rep.report("gate", "gate(s) that did not come back clean:",
               [f"{r.launch.name}: reported, above"
                if r.code == 1 else
                f"{r.launch.name}: exited {r.code} without reaching a verdict"
                for r in results if r.code != 0],
               f"all {len(results)} host gate(s) green")


def run(root: Path, fix: bool = False, tests: bool = False, check: bool = False) -> Reporter:
    """Complete mutations before readers, then decide only the final validation wave."""
    if fix and check:
        raise ValueError("--fix and --check are mutually exclusive")
    rep = Reporter()
    rep.line(HEADING)
    if not check:
        try:
            rep.line(sync_instructions.sync(root))
        except (sync_instructions.SyncError, OSError, subprocess.SubprocessError) as err:
            rep.report("gate", "instruction synchronization failed:", [str(err)])
            return rep

    plan = _plan(fix, tests)
    if fix:
        repair = _launch(root, plan[0][0])
        _show(rep, repair)
        if repair.code not in (0, 1):
            rep.report("gate", "repair did not complete:",
                       [f"{repair.launch.name}: exited {repair.code} without reaching a verdict"])
            return rep
        rep.line("repair pass complete; the fresh validation below decides the repaired tree")

    wave = plan[-1]
    with ThreadPoolExecutor(max_workers=len(wave)) as pool:
        results = list(pool.map(lambda member: _launch(root, member), wave))
    _verdict(rep, results)
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run.py gate",
        description="Run the host's gates together and answer with one verdict.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fix", action="store_true",
                      help="synchronize instructions, repair derived facts, then validate again")
    mode.add_argument("--check", action="store_true",
                      help="validate without synchronizing instructions or repairing files")
    parser.add_argument("--tests", action="store_true",
                        help="add the tools' own behavioral tests to the wave")
    args = parser.parse_args(argv)

    plan = _plan(args.fix, args.tests)
    # Printed rather than accumulated, which the report itself is not: the longest
    # member is most of a minute and this is the only line that can say what is
    # being waited for while it runs.
    preflight = ("" if args.check else "synchronizing instructions; ")
    if args.fix:
        preflight += "repairing derived facts; "
    print(preflight + f"running {len(plan[-1])} host gate(s): "
          + ", ".join(m.name for m in plan[-1]), flush=True)

    report = run(corpus_mod.find_root(), fix=args.fix, tests=args.tests, check=args.check)
    print("\n".join(report.out))
    return 1 if report.findings else 0
