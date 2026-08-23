# SPDX-License-Identifier: Apache-2.0
"""The one-command gate's seams: the plan, the launch, and the verdict over both.

`gate.py` runs the host's three gates and answers with one exit code. Almost all of
what it decides is decided before any of them runs, in the plan: which members go
in which wave, and that the repair never shares a wave with the selftest that
copies the tree it rewrites. That is a pure function and it is held here directly.

What is left is the launch and the verdict, and both are held against a real member
rather than a stub: `typecheck.py` is the cheap one, it exits 0 on this tree and 2
on an argument it does not take, and those are exactly the two contracts this tool
draws a line between, a gate that reported and a gate that never reached a verdict.

The whole gate over the live tree is one case and it is slow, being the selftest
plus the other two: it is the only case that proves the three actually run
together, so it is here rather than nowhere, under `--slow` rather than in the
default run.
"""

import subprocess
import sys

import gate
from tests.harness import TOOLS, Case, ensure
from vos.report import Reporter

_ROOT = TOOLS.parent


def _plan_is_one_wave() -> None:
    plan = gate._plan(fix=False)
    ensure(len(plan) == 1, f"with no repair every member goes in one wave, got {plan!r}")
    ensure([m.name for m in plan[0]] == [m.tool for m in gate.MEMBERS],
           f"the wave carries every member, in the order declared, got "
           f"{[m.name for m in plan[0]]!r}")


def _plan_repairs_ahead_of_the_wave() -> None:
    plan = gate._plan(fix=True)
    ensure(len(plan) == 2, f"the repair is a wave of its own ahead of the rest, got {plan!r}")
    ensure([m.name for m in plan[0]] == [f"{gate.REPAIRS} --fix"],
           f"the first wave is the repair alone, got {[m.name for m in plan[0]]!r}")

    # the property the wave exists for: nothing that reads the working tree runs
    # while the repair is rewriting it
    ensure(all(m.tool != gate.REPAIRS for m in plan[1]),
           f"the repairing member appears once, in its own wave, got {plan!r}")
    planned = [m.tool for wave in plan for m in wave]
    ensure(sorted(planned) == sorted(m.tool for m in gate.MEMBERS),
           f"every member is planned exactly once, got {planned!r}")


def _members_name_tools_that_exist() -> None:
    missing = [m.tool for m in gate.MEMBERS if not (TOOLS / m.tool).is_file()]
    ensure(not missing, f"every member names a tool on disk, missing {missing!r}")


def _launch_carries_the_members_verdict() -> None:
    member = next(m for m in gate.MEMBERS if m.tool == "typecheck.py")
    result = gate._launch(_ROOT, member)
    ensure(result.code == 0,
           f"the type gate is green on this tree, got {result.code}: {result.out!r}")
    ensure(result.out[:1] == ["=== tools ==="],
           f"the member's own report comes back whole, got {result.out[:2]!r}")

    rep = Reporter()
    gate._verdict(rep, [result])
    ensure(rep.findings == 0, f"a member that exited 0 is no finding, got {rep.out!r}")
    ensure(rep.out[0] == "--- typecheck.py: the tools' own Python, under two pinned "
                         "checkers ---",
           f"the member reports under a heading naming what it decides, got {rep.out[0]!r}")
    ensure(rep.out[-1] == "ok gate: all 1 host gate(s) green",
           f"the verdict closes on one line over them all, got {rep.out[-1]!r}")


def _launch_names_a_member_that_gave_no_verdict() -> None:
    # argparse answers a usage error with 2, which is neither clean nor a finding:
    # the gate must say the member never got as far as deciding anything.
    refused = gate.Launch("typecheck.py", ("--no-such-flag",), "a flag it does not take")
    result = gate._launch(_ROOT, refused)
    ensure(result.code == 2,
           f"a usage error exits 2, got {result.code}: {result.out!r}")

    rep = Reporter()
    gate._verdict(rep, [result])
    ensure(rep.findings == 1, f"a member that never decided is one finding, got {rep.out!r}")
    ensure("typecheck.py --no-such-flag: exited 2 without reaching a verdict"
           in "\n".join(rep.out),
           f"the finding names the command and that it reached no verdict, got {rep.out!r}")


def _verdict_names_the_member_that_reported() -> None:
    results = [gate.Result(gate.MEMBERS[0], 0, ["ok whatever: fine"]),
               gate.Result(gate.MEMBERS[1], 1, ["FAIL K-99: 1 thing"]),
               gate.Result(gate.MEMBERS[2], 0, ["ok whatever: fine"])]
    rep = Reporter()
    gate._verdict(rep, results)
    ensure(rep.findings == 1, f"one member reported, so one finding, got {rep.findings}")
    ensure("check-selftest.py: reported, above" in "\n".join(rep.out),
           f"the finding names which member to go and read, got {rep.out!r}")
    ensure(all(any(line.startswith(f"--- {m.name}:") for line in rep.out)
               for m in gate.MEMBERS),
           f"every member reports, green or not, got {rep.out!r}")


def _gate_over_the_live_tree() -> None:
    done = subprocess.run([sys.executable, str(TOOLS / "gate.py")], cwd=_ROOT,
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False, timeout=gate.TIMEOUT)
    ensure(done.returncode == 0,
           f"the live tree passes every host gate, got {done.returncode}: "
           f"{done.stdout[-2000:]!r} {done.stderr[-2000:]!r}")
    for member in gate.MEMBERS:
        ensure(f"--- {member.name}:" in done.stdout,
               f"{member.tool} reported under its own heading, got {done.stdout[:400]!r}")
    ensure(done.stdout.rstrip().endswith(f"ok gate: all {len(gate.MEMBERS)} host gate(s) green"),
           f"the run closes on its one verdict, got {done.stdout[-400:]!r}")


def cases() -> list[Case]:
    return [
        Case("plan-is-one-wave", _plan_is_one_wave),
        Case("plan-repairs-ahead-of-the-wave", _plan_repairs_ahead_of_the_wave),
        Case("members-name-tools-that-exist", _members_name_tools_that_exist),
        Case("launch-carries-the-members-verdict", _launch_carries_the_members_verdict,
             lane="host"),
        Case("launch-names-a-member-that-gave-no-verdict",
             _launch_names_a_member_that_gave_no_verdict, lane="host"),
        Case("verdict-names-the-member-that-reported",
             _verdict_names_the_member_that_reported),
        Case("gate-over-the-live-tree", _gate_over_the_live_tree, slow=True, lane="host"),
    ]
