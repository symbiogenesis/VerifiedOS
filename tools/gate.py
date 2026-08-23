#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run every gate this repository keeps on the host, as one command and one verdict.

There are three, and each decides about a different artifact:

    check.py           the documents   every derived fact against the artifact that owns it
    check-selftest.py  the checker     every rule it carries, against its own mutant
    typecheck.py       the Python      every expression and every signature, under two pins

Nothing runs them but a person, by hand, before anything lands, so three commands
are three chances to remember two. This is the one command that removes that: one
launch, one exit code, and each member's own report printed whole under its own
heading, in the order declared here rather than the order the three finished in.

**They run together because they contend for nothing.** All three only read the
checkout, and the two small ones fit inside the slack of the large one. Measured
warm on a twelve-core host, three alternated runs of each arm: the selftest alone
at a 22.8 s median, the wave at 23.9 s, the same three in sequence at 26.0 s. The
other two cost about a second inside the wave where they cost three beside it, and
the wave's spread is the tighter of the two, 23.8 to 24.2 s against 23.7 to 26.6.
The saving is the smaller half of why this exists. The one verdict is the other
half, and the larger.

**`--fix` is the exception to the wave, and a correctness one.** `check.py --fix`
rewrites the documents whose arithmetic moved, and the selftest opens by copying
the working tree into the template every sandbox links against, so a repair landing
mid-copy would seed the sandboxes a half-written tree. That reports as a baseline
that does not pass, which is a red run about nothing at all. So the repair runs
alone and to completion, and the other two follow it.

**`test.py` is deliberately not a member.** It is the gate over the tools' own
behavior rather than over this tree, and it is the one gate that runs the others:
its entry-point module launches check.py and typecheck.py itself and brackets them
with the tree's git status, so nesting it here would put two answers to one
question in one report. It stays its own command, run when what changed is what a
tool does.

Exit 0 when every member exits 0, 1 otherwise. It may be run from anywhere: the
repository root is found from this file, never from the working directory.
"""

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import corpus as corpus_mod
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
    """One member: the tool, the arguments it takes here, and what it decides."""

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
    Launch("check.py", (), "every derived fact against the artifact that owns it"),
    Launch("check-selftest.py", (), "every rule the checker carries, against its mutant"),
    Launch("typecheck.py", (), "the tools' own Python, under two pinned checkers"),
)

# The one member with a --fix branch, named rather than taken by position so that
# reordering the table above cannot quietly move which member the repair wave holds.
REPAIRS = "check.py"


def _plan(fix: bool) -> list[list[Launch]]:
    """The launch plan: one list per wave, waves in order, a wave's members together.

    Without `--fix` that is one wave, because no member writes anything any other
    member reads. With it the repair goes in a wave of its own ahead of the rest,
    for the reason this module's docstring states: the selftest copies the working
    tree, and a document rewritten while it is being copied seeds a torn sandbox.

    Every member appears exactly once either way. An empty wave is dropped rather
    than launched, so a table that ever loses its repairing member still plans.
    """
    if not fix:
        return [list(MEMBERS)]
    repair = [Launch(m.tool, (*m.args, "--fix"), m.decides)
              for m in MEMBERS if m.tool == REPAIRS]
    rest = [m for m in MEMBERS if m.tool != REPAIRS]
    return [wave for wave in (repair, rest) if wave]


def _launch(root: Path, member: Launch) -> Result:
    """One member, in its own process, as what it printed and the code it exited.

    A subprocess rather than an import, and for reasons rather than for symmetry.
    One member cannot be imported at all, `check-selftest.py` carrying a hyphen no
    module name admits; that one also reports by printing as it goes rather than by
    handing back a slate, so its verdict is a stream and this is what reads it. And
    a member's exit code is its own to decide, which keeps this tool from
    re-deriving three verdicts it would then have to keep in agreement with three
    `main` functions.

    Neither of the two ways a run can fail short of a verdict is allowed to become
    a traceback here: a member that hangs and a member that cannot be executed are
    both findings, on the convention typecheck.py's own runner keeps.
    """
    argv = [sys.executable, str(root / "tools" / member.tool), *member.args]
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


def _verdict(rep: Reporter, results: list[Result]) -> None:
    """Every member's own report under its own heading, then the line over them all.

    A member that exited 1 has already printed the findings it is being counted
    for, so what is said here is which member to go and read. A member that exited
    anything else printed no verdict at all, and saying so is the difference
    between a tree with a finding in it and a tool that did not run.
    """
    for result in results:
        rep.line(f"--- {result.launch.name}: {result.launch.decides} ---")
        rep.out.extend(result.out)
        rep.line()

    rep.report("gate", "gate(s) that did not come back clean:",
               [f"{r.launch.name}: reported, above"
                if r.code == 1 else
                f"{r.launch.name}: exited {r.code} without reaching a verdict"
                for r in results if r.code != 0],
               f"all {len(results)} host gate(s) green")


def run(root: Path, fix: bool = False) -> Reporter:
    """One whole run, as data, on the convention `check.py` set: the caller decides
    what to do with the verdict rather than parsing what was printed.

    A wave's members are separate processes over one tree and none reads another's
    result, so they run concurrently and are collected in the order they were
    declared, which is what makes the report read the same however the three
    finished."""
    rep = Reporter()
    rep.line(HEADING)

    results: list[Result] = []
    for wave in _plan(fix):
        with ThreadPoolExecutor(max_workers=len(wave)) as pool:
            running = [pool.submit(_launch, root, member) for member in wave]
        results += [one.result() for one in running]

    _verdict(rep, results)
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the host's gates together and answer with one verdict.")
    parser.add_argument("--fix", action="store_true",
                        help="pass --fix to check.py, which then runs alone, first")
    args = parser.parse_args(argv)

    plan = _plan(args.fix)
    # Printed rather than accumulated, which the report itself is not: the longest
    # member is most of a minute and this is the only line that can say what is
    # being waited for while it runs.
    print(f"running {sum(len(w) for w in plan)} gate(s): "
          + ", ".join(m.name for wave in plan for m in wave), flush=True)

    report = run(corpus_mod.find_root(), fix=args.fix)
    print("\n".join(report.out))
    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())
