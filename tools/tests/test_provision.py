# SPDX-License-Identifier: Apache-2.0
"""The provisioner, and idempotence held rather than claimed.

`run.py provision` states the lane as a table of facts, and the property that matters
about it is that a run against a machine already satisfying the table plans nothing and
changes nothing. That property is about the mapping from what a probe saw to what would
be run, so it is held over **injected** tables whose probes answer what a case chose,
never over the live machine: a table read off this box says only that this box is
provisioned, which is the acceptance evidence and not a test.

What the live table is held to is the shape every row owes, that each names the loop
wanting it and the artifact owning it and that no two rows share a name, because a row
is only worth having if a reader can act on its finding.

The one case that runs the command is the guest's, doubled and bracketed by
`git status --porcelain` in [test_entrypoints.py](test_entrypoints.py)'s shape: a
`--check` run is read-only or it is lying, and a probe that quietly wrote would be
exactly the defect this tool exists not to be.
"""

import os
import subprocess
import sys
from dataclasses import dataclass

from tests.harness import TOOLS, Case, ensure
from vos import env
from vos.cli import provision, rtl, typecheck

_ROOT = TOOLS.parent


def _answer(present: bool, saw: str) -> provision.Found:
    """A probe that says what a case chose, so a table describes a hypothetical
    machine rather than this one."""
    return provision.Found(present, saw)


def _fact(name: str, *, present: bool, install: tuple[tuple[str, ...], ...] = (),
          group: str = provision.GATE) -> provision.Fact:
    return provision.Fact(
        name=name, group=group, needs=f"the loop that wants {name}",
        owner=f"the artifact that fixes {name}",
        probe=lambda: _answer(present, f"{name} as this case chose it"),
        install=install)


_HERE = (("do", "the", "install"),)


def _satisfied_plans_nothing() -> None:
    """Idempotence, stated as the property it is: a satisfied probe yields no work."""
    table = (_fact("first", present=True, install=_HERE),
             _fact("second", present=True, install=_HERE, group=provision.TOOLCHAIN))
    results = provision.take(table)
    ensure(provision.plan(results) == [],
           f"every fact present must plan nothing, planned {provision.plan(results)!r}")
    report = provision.run(table)
    ensure(report.findings == 0, f"a satisfied table is clean, got {report.findings}")


def _absent_plans_its_own_command() -> None:
    table = (_fact("here", present=True, install=_HERE),
             _fact("gone", present=False, install=_HERE))
    planned = provision.plan(provision.take(table))
    ensure([fact.name for fact, _ in planned] == ["gone"],
           f"only the absent fact is planned, planned {[f.name for f, _ in planned]}")
    ensure([commands for _, commands in planned] == [_HERE],
           f"a planned fact contributes exactly its own argv, got {planned!r}")


def _absent_without_a_command_reports_only() -> None:
    """A row this tree states no command for is a finding and not a repair.

    The two halves are held apart on purpose. An empty plan because everything is
    satisfied and an empty plan because nothing may be done are the same list and
    opposite verdicts, so the verdict is what tells them apart.
    """
    table = (_fact("unownable", present=False),)
    ensure(provision.plan(provision.take(table)) == [],
           "a fact with no stated command plans nothing")
    report = provision.run(table)
    ensure(report.findings == 1, f"and still fails the run, got {report.findings}")
    said = "\n".join(report.out)
    ensure("plans nothing" in said,
           f"and says why there is nothing to run, said {said!r}")


def _verdict_is_the_exit_code() -> None:
    """The conventions fix 0 clean and 1 a finding, and this is that mapping."""
    clean = provision.run((_fact("here", present=True),))
    ensure(clean.findings == 0, "a clean run finds nothing")
    red = provision.run((_fact("here", present=True), _fact("gone", present=False)))
    ensure(red.findings == 1, f"one absent fact is one finding, got {red.findings}")
    both = provision.run((_fact("a", present=False), _fact("b", present=False)))
    ensure(both.findings == 2, f"two absent facts are two, got {both.findings}")


def _report_is_deterministic() -> None:
    """The probes run concurrently and the report does not: a person reading a run
    twice must read one report, and the order two subprocesses finished in is not a
    property of the machine being described."""
    table = tuple(_fact(f"row-{n}", present=n % 3 != 0, install=_HERE)
                  for n in range(12))
    first = provision.run(table).out
    second = provision.run(table).out
    ensure(first == second, "two runs of one table must print one report")
    names = [line.split(":")[0].removeprefix("ok ").removeprefix("FAIL ").strip()
             for line in first if line.startswith(("ok ", "FAIL "))]
    ensure(names == [fact.name for fact in table],
           f"and in the table's own order, got {names}")


def _only_narrows_and_says_what_it_skipped() -> None:
    """A narrowed run says what it did not decide, which is S13b's rule for `--rule`
    read one instrument over: a gate exiting 0 over a subset while leaving rows
    unprobed would be a gate that lies about its own reach."""
    table = (_fact("gated", present=False, group=provision.GATE),
             _fact("chained", present=False, group=provision.TOOLCHAIN))
    report = provision.run(table, group=provision.GATE)
    said = "\n".join(report.out)
    ensure(report.findings == 1,
           f"the narrowed run decides its own group alone, got {report.findings}")
    ensure("chained" in said and "did not run" in said,
           f"and names the rows it did not decide about, said {said!r}")


def _every_row_is_actionable() -> None:
    """The live table's own shape. A finding a reader cannot act on is not worth
    printing, so every row names the loop that wants the fact and the artifact that
    fixes it, and no two rows share the name a finding is filed under."""
    names = [fact.name for fact in provision.FACTS]
    ensure(len(names) == len(set(names)), f"row names must be unique, got {names}")
    ensure(bool(provision.FACTS), "an empty table would report nothing about anything")
    for fact in provision.FACTS:
        ensure(bool(fact.needs), f"{fact.name} names no loop that wants it")
        ensure(bool(fact.owner), f"{fact.name} names no artifact that fixes it")
        ensure(fact.group in provision.GROUPS,
               f"{fact.name} is in group {fact.group!r}, which --only cannot ask for")


def _versions_are_read_and_not_typed() -> None:
    """The whole point of the table: a pin appears in a row because it was imported.

    Held by the value rather than by inspection, each of these being the constant its
    own owner fixes. A row that had been hand-typed would pass today and drift on the
    first bump, which is the defect this repository exists to catch.
    """
    said = "\n".join(fact.owner + " " + fact.needs + " " +
                     " ".join(" ".join(step) for step in fact.install)
                     for fact in provision.FACTS)
    for pin in (typecheck.TY_VERSION, typecheck.RUFF_VERSION, env.SAIL_VERSION,
                env.Z3_VERSION, env.ROCQ_VERSION, rtl.VERILATOR_PIN):
        ensure(pin in said, f"the table no longer carries {pin}, so a row stopped "
                            "reading the constant that fixes it")


def _number_reads_the_banners() -> None:
    """The three shapes a version arrives in here, and the one that decides the
    pattern: `Z3 version 5.1.0` opens with a digit inside the tool's own name."""
    ensure(provision._number("Z3 version 5.1.0 - 64 bit") == "5.1.0",
           "a digit in the tool's name must not be read as its version")
    ensure(provision._number("Verilator 5.032 2025-01-01 rev (Debian 5.032-1)")
           == "5.032", "the first dotted number is the version")
    ensure(provision._number("0.9.1+9.1") == "0.9.1",
           "opam's build suffix is not part of the version")
    ensure(provision._number("no version here") == "",
           "a banner with no dotted number yields none rather than a fragment")


def _run(*argv: str) -> tuple[int, str, str]:
    done = subprocess.run(list(argv), capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=300, cwd=_ROOT)
    return done.returncode, done.stdout, done.stderr


def _git(*argv: str) -> tuple[int, str, str]:
    """git over this checkout, from whichever lane is asking.

    A linked worktree made by the host's git holds a *Windows* path in its `.git`
    file, so inside the guest a bare `git` in a lane exits 128 with `not a git
    repository`, which is I7's own finding and is a property of the lane rather than
    of anything here. `env.git_dir` is the translation that act already landed, and it
    is reached rather than repeated; it answers `None` on the primary worktree and on
    the host, where nothing needs translating.
    """
    admin = env.git_dir(_ROOT)
    overlay = None if admin is None else {**os.environ, "GIT_DIR": str(admin)}
    done = subprocess.run(["git", *argv], capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=300, cwd=_ROOT,
                          env=overlay)
    return done.returncode, done.stdout, done.stderr


@dataclass
class _Flow:
    porcelain: str | None = None


_FLOW = _Flow()


def _check_is_read_only() -> None:
    """The guest's acceptance case: `--check` twice, identical, over an unmoved tree.

    Bracketed rather than asserted empty, because the suite may run on a tree with
    untracked work in flight and what is owed is that these two runs added none of it.
    """
    code, before, err = _git("status", "--porcelain")
    ensure(code == 0, f"git status failed: {err!r}")
    _FLOW.porcelain = before

    first = _run(sys.executable, str(TOOLS / "run.py"), "provision", "--check")
    second = _run(sys.executable, str(TOOLS / "run.py"), "provision", "--check")
    ensure(first == second,
           f"provision --check answered differently on its second run:\n"
           f"first:  {first!r}\nsecond: {second!r}")

    code, after, err = _git("status", "--porcelain")
    ensure(code == 0, f"git status failed: {err!r}")
    ensure(after == before,
           f"a --check run moved the tree:\nbefore: {before!r}\nafter: {after!r}")


def cases() -> list[Case]:
    return [
        Case("satisfied-plans-nothing", _satisfied_plans_nothing),
        Case("absent-plans-its-own-command", _absent_plans_its_own_command),
        Case("absent-without-a-command-reports-only",
             _absent_without_a_command_reports_only),
        Case("verdict-is-the-exit-code", _verdict_is_the_exit_code),
        Case("report-is-deterministic", _report_is_deterministic),
        Case("only-narrows-and-says-what-it-skipped",
             _only_narrows_and_says_what_it_skipped),
        Case("every-row-is-actionable", _every_row_is_actionable),
        Case("versions-are-read-and-not-typed", _versions_are_read_and_not_typed),
        Case("number-reads-the-banners", _number_reads_the_banners),
        # guest-only: the command hops there, so on the host this case would pay for a
        # WSL launch to decide about a lane the host is not
        Case("check-is-read-only", _check_is_read_only, lane="guest"),
    ]
