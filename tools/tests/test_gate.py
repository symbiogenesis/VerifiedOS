# SPDX-License-Identifier: Apache-2.0
"""Instruction preparation and repair finish before parallel readers.

Temporary state and synchronized workers exercise ordering, conflict refusal, read-only
behavior and a repair that leaves either a clean or still-failing tree. Real subprocess
checks preserve successful and unsupported-argument exits. The optional slow case runs
the complete read-only gate over this checkout.
"""

import io
import subprocess
import sys
import tempfile
import threading
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos.cli import BY_NAME, gate
from vos.report import Reporter

_ROOT = TOOLS.parent


def _plan_is_one_wave() -> None:
    plan = gate._plan(fix=False, tests=False)
    ensure(len(plan) == 1, f"with no repair every member goes in one wave, got {plan!r}")
    ensure([m.name for m in plan[0]] == [m.tool for m in gate.MEMBERS],
           f"the wave carries every member, in the order declared, got "
           f"{[m.name for m in plan[0]]!r}")


def _plan_repairs_ahead_of_the_wave() -> None:
    plan = gate._plan(fix=True, tests=False)
    ensure(len(plan) == 2, f"the repair is a wave of its own ahead of the rest, got {plan!r}")
    ensure([m.name for m in plan[0]] == [f"{gate.REPAIRS} --fix"],
           f"the first wave is the repair alone, got {[m.name for m in plan[0]]!r}")

    # the property the wave exists for: nothing that reads the working tree runs
    # while the repair is rewriting it
    ensure(plan[1] == list(gate.MEMBERS) and all(not m.args for m in plan[1]),
           f"the final wave reruns every member read-only, got {plan!r}")


def _members_name_commands_the_table_carries() -> None:
    missing = [m.tool for m in (*gate.MEMBERS, gate.TESTS) if m.tool not in BY_NAME]
    ensure(not missing, f"every member names a command run.py dispatches, missing {missing!r}")


def _tests_join_the_wave_only_when_asked() -> None:
    default = [m.tool for wave in gate._plan(fix=False, tests=False) for m in wave]
    asked = [m.tool for wave in gate._plan(fix=False, tests=True) for m in wave]
    ensure(gate.TESTS.tool not in default,
           f"the tools' own tests are not in the default wave, got {default!r}")
    ensure(asked == [*default, gate.TESTS.tool],
           f"--tests adds them once, after the three, got {asked!r}")
    repair = gate._plan(fix=True, tests=True)
    ensure(repair[-1][-1] == gate.TESTS and gate.TESTS not in repair[0],
           "tests must only join the final read-only wave after repair")


def _sync_precedes_parallel_readers() -> None:
    synchronized = threading.Event()
    barrier = threading.Barrier(len(gate.MEMBERS) + 1)
    calls: list[str] = []

    def sync(root: Path) -> str:
        ensure(root == _ROOT, "synchronization used a different checkout")
        calls.append("sync")
        synchronized.set()
        return "ok sync: fixture instructions agree"

    def launch(root: Path, member: gate.Launch) -> gate.Result:
        ensure(root == _ROOT and synchronized.is_set(), "a reader began before synchronization")
        calls.append(member.name)
        barrier.wait(timeout=10)
        return gate.Result(member, 0, [f"completed {member.name}"])

    isolated = SimpleNamespace(sync=sync, SyncError=gate.sync_instructions.SyncError)
    with patch.object(gate, "sync_instructions", isolated), patch.object(gate, "_launch", launch):
        rep = gate.run(_ROOT, tests=True)
    ensure(rep.findings == 0 and calls[0] == "sync"
           and len(calls) == len(gate.MEMBERS) + 2,
           f"synchronization and all four parallel readers must run once: {calls}, {rep.out}")
    headings = [line for line in rep.out if line.startswith("--- ")]
    ensure([line.split(":", 1)[0] for line in headings]
           == [f"--- {m.name}" for m in (*gate.MEMBERS, gate.TESTS)],
           "parallel completion changed the declared report order")


def _readonly_mode_never_synchronizes() -> None:
    def sync(root: Path) -> str:
        raise AssertionError(f"read-only validation invoked synchronization at {root}")

    def launch(root: Path, member: gate.Launch) -> gate.Result:
        ensure(root == _ROOT and not member.args, "read-only validation launched a repair")
        code = 1 if member.tool == "check" else 0
        return gate.Result(member, code, ["FAIL K-110: invalid instruction import"] if code else [])

    isolated = SimpleNamespace(sync=sync, SyncError=gate.sync_instructions.SyncError)
    with patch.object(gate, "sync_instructions", isolated), patch.object(gate, "_launch", launch):
        rep = gate.run(_ROOT, check=True)
    ensure(rep.findings == 1 and "FAIL K-110:" in "\n".join(rep.out),
           "read-only mode must preserve the checker's instruction-drift failure")


def _invalid_import_prevents_every_reader() -> None:
    error = gate.sync_instructions.SyncError

    def sync(root: Path) -> str:
        raise error(f"unexpected CLAUDE.md content at {root}")

    def launch(root: Path, member: gate.Launch) -> gate.Result:
        raise AssertionError(f"{member.name} read {root} after synchronization failed")

    isolated = SimpleNamespace(sync=sync, SyncError=error)
    with patch.object(gate, "sync_instructions", isolated), patch.object(gate, "_launch", launch):
        for fix in (False, True):
            rep = gate.run(_ROOT, fix=fix)
            ensure(rep.findings == 1 and "unexpected CLAUDE.md content" in "\n".join(rep.out),
                   "the invalid import must be the final failed verdict")


def _repair_verdict_comes_from_the_fresh_wave() -> None:
    def scenario(remaining: bool) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-gate-") as td:
            root = Path(td)
            state = root / "state.txt"
            state.write_text("old", encoding="utf-8")
            synchronized = threading.Event()
            calls: list[str] = []

            def sync(found: Path) -> str:
                ensure(found == root, "synchronization used the wrong root")
                synchronized.set()
                return "ok sync: instructions agree"

            def launch(found: Path, member: gate.Launch) -> gate.Result:
                ensure(found == root and synchronized.is_set(), "repair preceded synchronization")
                calls.append(member.name)
                if member.args == ("--fix",):
                    state.write_text("repaired", encoding="utf-8")
                    return gate.Result(member, 1, ["FAIL K-24: old arithmetic", "fixed: arithmetic"])
                ensure(state.read_text(encoding="utf-8") == "repaired",
                       "a reader saw the tree before the repair completed")
                code = 1 if remaining and member.tool == "check" else 0
                return gate.Result(member, code, ["FAIL K-24: unresolved"] if code else [])

            isolated = SimpleNamespace(sync=sync, SyncError=gate.sync_instructions.SyncError)
            with patch.object(gate, "sync_instructions", isolated), \
                    patch.object(gate, "_launch", launch):
                rep = gate.run(root, fix=True)
            ensure(rep.findings == int(remaining),
                   f"the old finding must not override the final checker: {rep.out}")
            ensure(calls[0] == "check --fix" and calls.count("check") == 1
                   and calls.count("selftest") == 1 and calls.count("typecheck") == 1,
                   f"repair must precede exactly one full validation wave: {calls}")
            ensure("FAIL K-24: old arithmetic" in rep.out,
                   "the repair's original diagnostic was lost")
            if not remaining:
                ensure(rep.out[-1] == "ok gate: all 3 host gate(s) green",
                       "preparation must not inflate the count of successful final gates")

    scenario(remaining=False)
    scenario(remaining=True)


def _crashed_repair_stops_before_readers() -> None:
    def scenario(code: int) -> None:
        def launch(root: Path, member: gate.Launch) -> gate.Result:
            ensure(root == _ROOT and member.args == ("--fix",),
                   "a validation reader ran after a repair without a verdict")
            return gate.Result(member, code, ["repair failed to execute"])

        isolated = SimpleNamespace(sync=lambda _: "ok sync: instructions agree",
                                   SyncError=gate.sync_instructions.SyncError)
        with patch.object(gate, "sync_instructions", isolated), patch.object(gate, "_launch", launch):
            rep = gate.run(_ROOT, fix=True)
        ensure(rep.findings == 1 and "repair did not complete" in "\n".join(rep.out),
               "a crashed or timed-out repair must remain fatal")

    scenario(2)
    scenario(gate.NO_VERDICT)


def _repair_and_readonly_flags_are_exclusive() -> None:
    with redirect_stderr(io.StringIO()):
        try:
            gate.main(["--fix", "--check"])
        except SystemExit as err:
            ensure(err.code == 2, "conflicting modes must be an argument error")
        else:
            raise AssertionError("the CLI accepted both repair and read-only mode")


def _launch_carries_the_members_verdict() -> None:
    member = next(m for m in gate.MEMBERS if m.tool == "typecheck")
    result = gate._launch(_ROOT, member)
    ensure(result.code == 0,
           f"the type gate is green on this tree, got {result.code}: {result.out!r}")
    ensure(result.out[:1] == ["=== tools ==="],
           f"the member's own report comes back whole, got {result.out[:2]!r}")

    rep = Reporter()
    gate._verdict(rep, [result])
    ensure(rep.findings == 0, f"a member that exited 0 is no finding, got {rep.out!r}")
    ensure(rep.out[0] == "--- typecheck: the tools' own Python, under two pinned "
                         "checkers ---",
           f"the member reports under a heading naming what it decides, got {rep.out[0]!r}")
    ensure(rep.out[-1] == "ok gate: all 1 host gate(s) green",
           f"the verdict closes on one line over them all, got {rep.out[-1]!r}")


def _launch_names_a_member_that_gave_no_verdict() -> None:
    # argparse answers a usage error with 2, which is neither clean nor a finding:
    # the gate must say the member never got as far as deciding anything.
    refused = gate.Launch("typecheck", ("--no-such-flag",), "a flag it does not take")
    result = gate._launch(_ROOT, refused)
    ensure(result.code == 2,
           f"a usage error exits 2, got {result.code}: {result.out!r}")

    rep = Reporter()
    gate._verdict(rep, [result])
    ensure(rep.findings == 1, f"a member that never decided is one finding, got {rep.out!r}")
    ensure("typecheck --no-such-flag: exited 2 without reaching a verdict"
           in "\n".join(rep.out),
           f"the finding names the command and that it reached no verdict, got {rep.out!r}")


def _verdict_names_the_member_that_reported() -> None:
    results = [gate.Result(gate.MEMBERS[0], 0, ["ok whatever: fine"]),
               gate.Result(gate.MEMBERS[1], 1, ["FAIL K-99: 1 thing"]),
               gate.Result(gate.MEMBERS[2], 0, ["ok whatever: fine"])]
    rep = Reporter()
    gate._verdict(rep, results)
    ensure(rep.findings == 1, f"one member reported, so one finding, got {rep.findings}")
    ensure("selftest: reported, above" in "\n".join(rep.out),
           f"the finding names which member to go and read, got {rep.out!r}")
    ensure(all(any(line.startswith(f"--- {m.name}:") for line in rep.out)
               for m in gate.MEMBERS),
           f"every member reports, green or not, got {rep.out!r}")


def _gate_over_the_live_tree() -> None:
    done = subprocess.run([sys.executable, str(TOOLS / "run.py"), "--check"], cwd=_ROOT,
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
        Case("members-name-commands-the-table-carries",
             _members_name_commands_the_table_carries),
        Case("tests-join-the-wave-only-when-asked",
             _tests_join_the_wave_only_when_asked),
        Case("sync-precedes-parallel-readers", _sync_precedes_parallel_readers),
        Case("readonly-mode-never-synchronizes", _readonly_mode_never_synchronizes),
        Case("invalid-import-prevents-every-reader", _invalid_import_prevents_every_reader),
        Case("repair-verdict-comes-from-the-fresh-wave", _repair_verdict_comes_from_the_fresh_wave),
        Case("crashed-repair-stops-before-readers", _crashed_repair_stops_before_readers),
        Case("repair-and-readonly-flags-are-exclusive", _repair_and_readonly_flags_are_exclusive),
        Case("launch-carries-the-members-verdict", _launch_carries_the_members_verdict,
             lane="host"),
        Case("launch-names-a-member-that-gave-no-verdict",
             _launch_names_a_member_that_gave_no_verdict, lane="host"),
        Case("verdict-names-the-member-that-reported",
             _verdict_names_the_member_that_reported),
        Case("gate-over-the-live-tree", _gate_over_the_live_tree, slow=True, lane="host"),
    ]
