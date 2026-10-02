# SPDX-License-Identifier: Apache-2.0
"""Repair and validation waves, and the one verdict they close on.

Temporary state and synchronized workers exercise ordering and a repair that leaves
either a clean or still-failing tree. Real subprocess checks preserve successful and
unsupported-argument exits. The optional slow case runs the complete read-only gate
over this checkout.
"""

import io
import json
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import redirect_stderr
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import timings
from vos.cli import gate
from vos.commands import BY_NAME
from vos.report import Reporter
from vos.sharding import Shard

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


def _sharded_plan_and_failures() -> None:
    def launch(root: Path, member: gate.Launch, record: Path | None = None) -> gate.Result:
        return gate.Result(member, 1 if member.tool in ("test", "typecheck") else 0, [])

    def summarized(shard: Shard | None = None,
                   unpartitioned: bool = False) -> tuple[Reporter, dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="vos-shard-") as td:
            path = Path(td) / "verdict.json"
            with patch.object(gate, "_launch", launch):
                report = gate.run(_ROOT, tests=True, summary=path, shard=shard,
                                  unpartitioned=unpartitioned)
            return report, json.loads(path.read_text(encoding="utf-8"))

    # Every shard of one count and the unpartitioned run together are the whole
    # read-only wave: each shard both suites' partition and nothing else, and the
    # unpartitioned run the rest, the selftest narrowed to its repair path.
    whole = [m.tool for m in gate._plan(False, True)[0]]
    rest = gate._plan(False, True, unpartitioned=True)[0]
    ensure([m.name for m in rest] == ["check", "selftest --repair-only", "typecheck"],
           f"the unpartitioned run is the checker, the repair path and typecheck: {rest!r}")
    for index in range(1, 5):
        shard = Shard(index, 4)
        wave = gate._plan(False, True, shard)[0]
        ensure([m.name for m in wave] == [f"selftest --shard {shard}", f"test --shard {shard}"],
               f"a shard runs its partition of both suites and nothing else: {wave!r}")
        ensure(sorted({*(m.tool for m in wave), *(m.tool for m in rest)}) == sorted(whole),
               "a shard and the unpartitioned run leave no member of the wave unrun")
        report, data = summarized(shard=shard)
        ensure(report.findings == 1 and data["green"] is False,
               "a failed partition must fail the gate")
        ensure(data["shard"] == {"index": index, "total": 4} and "unpartitioned" not in data,
               "partial verdicts must identify their shard")
    report, data = summarized(unpartitioned=True)
    ensure(report.findings == 1 and data["green"] is False
           and [m["name"] for m in data["members"]] == [m.name for m in rest],
           "a failed unpartitioned member must fail the gate")
    ensure(data.get("unpartitioned") is True and "shard" not in data,
           "the unpartitioned verdict identifies itself rather than a shard")
    for fix, shard, unpartitioned in ((True, Shard(1, 4), False), (True, None, True),
                                      (False, Shard(1, 4), True)):
        try:
            gate._plan(fix, True, shard, unpartitioned)
        except ValueError:
            pass
        else:
            raise AssertionError("repairing a checkout must not overlap partial readers, "
                                 "and a run is one shard or the unpartitioned members")
    for argv in (["--check", "--shard", "1/4", "--unpartitioned"], ["--fix", "--unpartitioned"]):
        with redirect_stderr(io.StringIO()):
            try:
                gate.main(argv)
            except SystemExit as err:
                ensure(err.code == 2, f"{argv!r} must be an argument error")
            else:
                raise AssertionError(f"the CLI accepted {argv!r}")


def _members_run_in_parallel() -> None:
    barrier = threading.Barrier(len(gate.MEMBERS) + 1)
    calls: list[str] = []

    def launch(root: Path, member: gate.Launch, record: Path | None = None) -> gate.Result:
        ensure(root == _ROOT, "a reader used a different checkout")
        ensure(record is None, "a run asked for no summary names no timings file")
        calls.append(member.name)
        barrier.wait(timeout=10)
        return gate.Result(member, 0, [f"completed {member.name}"])

    with patch.object(gate, "_launch", launch):
        rep = gate.run(_ROOT, tests=True)
    ensure(rep.findings == 0 and len(calls) == len(gate.MEMBERS) + 1,
           f"all parallel readers must run once: {calls}, {rep.out}")
    headings = [line for line in rep.out if line.startswith("--- ")]
    ensure([line.split(":", 1)[0] for line in headings]
           == [f"--- {m.name}" for m in (*gate.MEMBERS, gate.TESTS)],
           "parallel completion changed the declared report order")


def _repair_verdict_comes_from_the_fresh_wave() -> None:
    def scenario(remaining: bool) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-gate-") as td:
            root = Path(td)
            state = root / "state.txt"
            state.write_text("old", encoding="utf-8")
            calls: list[str] = []

            def launch(found: Path, member: gate.Launch,
                       record: Path | None = None) -> gate.Result:
                ensure(found == root, "repair used the wrong root")
                calls.append(member.name)
                if member.args == ("--fix",):
                    state.write_text("repaired", encoding="utf-8")
                    return gate.Result(member, 1, ["FAIL K-24: old arithmetic", "fixed: arithmetic"])
                ensure(state.read_text(encoding="utf-8") == "repaired",
                       "a reader saw the tree before the repair completed")
                code = 1 if remaining and member.tool == "check" else 0
                return gate.Result(member, code, ["FAIL K-24: unresolved"] if code else [])

            with patch.object(gate, "_launch", launch):
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
        def launch(root: Path, member: gate.Launch, record: Path | None = None) -> gate.Result:
            ensure(root == _ROOT and member.args == ("--fix",),
                   "a validation reader ran after a repair without a verdict")
            return gate.Result(member, code, ["repair failed to execute"])

        with patch.object(gate, "_launch", launch):
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


def _launch_times_success_findings_and_missing_verdicts() -> None:
    member = gate.MEMBERS[0]
    outcomes = [
        (subprocess.CompletedProcess([], 0, "ok\n", ""), 0),
        (subprocess.CompletedProcess([], 1, "FAIL\n", "diagnostic\n"), 1),
        (subprocess.CompletedProcess([], 2, "", "usage\n"), 2),
        (subprocess.TimeoutExpired("check", gate.TIMEOUT), gate.NO_VERDICT),
        (OSError("cannot launch"), gate.NO_VERDICT),
    ]
    for outcome, expected in outcomes:
        with (patch.object(gate.subprocess, "run") as launched,
              patch.object(gate.time, "perf_counter", side_effect=[10.0, 12.75])):
            if isinstance(outcome, Exception):
                launched.side_effect = outcome
            else:
                launched.return_value = outcome
            result = gate._launch(_ROOT, member)
        ensure(result.code == expected and result.elapsed_seconds == 2.75,
               f"timing lost the member's verdict or duration: {result}")
        if isinstance(outcome, subprocess.CompletedProcess):
            ensure(result.out == (outcome.stdout + outcome.stderr).splitlines(),
                   "timing changed the member's diagnostics")
        rep = Reporter()
        gate._show(rep, result)
        ensure(rep.out[1] == "elapsed: 2.75s", "the log must carry the measured duration")


def _launch_hands_a_member_its_timings_file() -> None:
    """A member is named the file the gate asked for, or none, never one this process
    inherited, and the parts it wrote there come back with its result."""
    member = next(m for m in gate.MEMBERS if m.tool == "selftest")
    units: list[timings.Unit] = [{"kind": "phase", "name": "baseline", "seconds": 1.5}]
    named: list[str | None] = []

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        environment = kwargs.get("env")
        if not isinstance(environment, dict):
            raise TypeError("a member is launched with an environment of its own")
        record = environment.get(timings.ENV)
        named.append(record)
        if record:
            Path(record).write_text(json.dumps(units), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "ok\n", "")

    with tempfile.TemporaryDirectory(prefix="vos-gate-units-") as td:
        outer, record = Path(td) / "outer.json", Path(td) / "member.json"
        with (patch.object(gate.subprocess, "run", side_effect=run),
              patch.dict(gate.os.environ, {timings.ENV: str(outer)})):
            given = gate._launch(_ROOT, member, record)
            bare = gate._launch(_ROOT, member)
        ensure(named == [str(record), None] and not outer.exists(),
               f"a member is named the gate's file or none, never an inherited one: {named!r}")
    ensure(given.code == 0 and given.out == ["ok"] and given.units == units,
           f"the member's parts return with its unchanged verdict: {given!r}")
    ensure(bare.units is None, f"a member given no file records no parts: {bare!r}")


def _timings_round_trip_and_never_fail_the_run() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-timings-") as td:
        path = Path(td) / "units.json"
        with patch.dict(timings.os.environ, {timings.ENV: str(path)}):
            ensure(timings.claim() == path and timings.ENV not in timings.os.environ,
                   "claiming the file takes it out of the environment children inherit")
            ensure(timings.claim() is None, "a claimed file is not claimed twice")
        clock = timings.Clock()
        clock.add("phase", "teardown", 0.25)
        with clock.timing("case", "K-02: b"):
            pass
        clock.add("case", "K-01: a", 2.0)
        units = clock.units()
        ensure([(unit["kind"], unit["name"]) for unit in units]
               == [("case", "K-01: a"), ("case", "K-02: b"), ("phase", "teardown")],
               f"units are listed by kind and name, not by finishing order: {units!r}")
        ensure(all(set(unit) == {"kind", "name", "seconds", "start", "at"} for unit in units),
               f"a wall clock records each unit's start and no CPU seconds: {units!r}")
        placed = timings.Clock(cpu=True, origin=10.0)
        placed.add("case", "K-03: c", 1.5, 12.25)
        with placed.timing("phase", "baseline"):
            pass
        placed.span("phase", "imports", timings.Reading(10.5, 1.0, 0.5),
                    timings.Reading(11.0, 1.25, 1.0))
        added, timed, spanned = placed.units()
        # The wall-clock time at the origin, the `perf_counter` reading 10.0, to which each
        # unit's `at` adds its start.
        origin_at = time.time() - (time.perf_counter() - 10.0)
        for unit in (added, timed, spanned):
            at, start = unit.pop("at", None), unit.get("start")
            ensure(isinstance(at, float) and isinstance(start, float)
                   and abs(at - start - origin_at) < 0.5,
                   f"a unit's at is the wall-clock time of its start: {at!r}, {unit!r}")
        ensure(added == {"kind": "case", "name": "K-03: c", "seconds": 1.5, "start": 2.25},
               f"a unit starts at its offset from the clock's origin: {added!r}")
        children = sys.platform != "win32"
        ensure(isinstance(cpu := timed.get("cpu_seconds"), float) and cpu >= 0
               and ("child_cpu_seconds" in timed) == children,
               f"a CPU clock records the CPU seconds of each block it times: {timed!r}")
        ensure(spanned == {"kind": "phase", "name": "imports", "seconds": 0.5, "start": 0.5,
                           "cpu_seconds": 0.25, **({"child_cpu_seconds": 0.5} if children
                                                   else {})},
               "a span records its own CPU seconds and, except on Windows, its waited "
               f"children's: {spanned!r}")
        timings.write(path, units)
        ensure(timings.read(path) == units, "written units must read back unchanged")
        timings.write(None, units)
        missing = Path(td) / "absent" / "units.json"
        timings.write(missing, units)
        ensure(timings.read(missing) is None, "an unwritable file records nothing, quietly")
        for text in ("not json", "{}", "[1]"):
            path.write_text(text, encoding="utf-8")
            ensure(timings.read(path) is None, f"{text!r} is no list of units")


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


def _summary_names_every_member_and_its_code() -> None:
    """The verdict a caller reads who has only this run's exit code.

    Held against the three states a member can be in at once, because they are what the
    exit code collapses: clean, a verdict of findings, and no verdict at all. The last
    is the one a reader most needs separated out, a member that crashed being a broken
    tool rather than a tree with something wrong in it.
    """
    codes = {"check": 0, "selftest": 1, "typecheck": gate.NO_VERDICT, "test": 0}
    measured: list[timings.Unit] = [{"kind": "module", "name": "test_a", "cases": 2,
                                     "seconds": 0.5}]
    records: list[Path | None] = []

    def launch(root: Path, member: gate.Launch, record: Path | None = None) -> gate.Result:
        records.append(record)
        return gate.Result(member, codes[member.tool], [], 1.25,
                           measured if member.tool == "test" else None)

    with tempfile.TemporaryDirectory(prefix="vos-gate-summary-") as td:
        path = Path(td) / "nested" / "verdict.json"
        with patch.object(gate, "_launch", launch):
            rep = gate.run(_ROOT, tests=True, summary=path)
        written = json.loads(path.read_text(encoding="utf-8"))

    named = [record for record in records if record is not None]
    ensure(len(named) == len(records) == len(gate.MEMBERS) + 1
           and len({record.parent for record in named}) == 1 and len(set(named)) == len(named),
           f"each member is named its own timings file in one directory, got {records!r}")
    ensure(not named[0].parent.exists(), "the timings directory leaves with the run")

    ensure(written["green"] is False and written["stopped"] == "",
           f"a wave that ran and reported is neither green nor stopped, got {written!r}")
    ensure([m["name"] for m in written["members"]]
           == [m.tool for m in (*gate.MEMBERS, gate.TESTS)],
           f"every member is named, in declaration order, got {written['members']!r}")
    by_name = {m["name"]: m for m in written["members"]}
    # by tool rather than by position, on the convention the module under test states
    # at REPAIRS: reordering MEMBERS must not quietly move which member this holds.
    selftest = next(m for m in gate.MEMBERS if m.tool == "selftest")
    ensure(by_name["selftest"] == {"name": "selftest", "decides": selftest.decides,
                                   "code": 1, "elapsed_seconds": 1.25,
                                   "reached_verdict": True, "clean": False, "units": None},
           f"a member that reported findings reached a verdict, got {by_name['selftest']!r}")
    ensure(by_name["test"]["units"] == measured,
           f"a member's measured parts reach its record, got {by_name['test']!r}")
    ensure(by_name["typecheck"]["reached_verdict"] is False
           and by_name["typecheck"]["code"] == gate.NO_VERDICT,
           f"a member that never decided says so, got {by_name['typecheck']!r}")
    ensure(by_name["check"]["clean"] is True and by_name["test"]["clean"] is True,
           f"a member that exited 0 is clean, got {by_name!r}")
    ensure(all(m["elapsed_seconds"] == 1.25 for m in written["members"]),
           "every member's JSON record must retain its measured duration")
    written_at = [i for i, line in enumerate(rep.out)
                  if line.startswith("ok summary: written to")]
    decided_at = [i for i, line in enumerate(rep.out) if line.startswith("FAIL gate:")]
    ensure(len(written_at) == 1 and len(decided_at) == 1 and written_at[0] < decided_at[0],
           f"the file is reported once, ahead of the wave's own verdict, got {rep.out!r}")


def _summary_names_a_wave_that_never_ran() -> None:
    """A stopped run writes the sentence a bare exit code cannot carry.

    A repair that crashes fails before any validation member starts, so there is no
    member to name and the reason is the whole answer; written as an empty member
    list alone it would be indistinguishable from a wave nobody asked for.
    """
    def launch(root: Path, member: gate.Launch, record: Path | None = None) -> gate.Result:
        return gate.Result(member, 2, ["repair failed to execute"])

    with tempfile.TemporaryDirectory(prefix="vos-gate-stopped-") as td:
        path = Path(td) / "verdict.json"
        with patch.object(gate, "_launch", launch):
            gate.run(_ROOT, fix=True, summary=path)
        written = json.loads(path.read_text(encoding="utf-8"))

    ensure(written["members"] == [] and written["green"] is False,
           f"no member ran, so none is named and nothing is green, got {written!r}")
    ensure("repair did not complete" in written["stopped"],
           f"the reason the wave never ran is the answer, got {written['stopped']!r}")


def _unwritable_summary_is_a_finding() -> None:
    """Asked to say what it decided and unable to, the gate says that instead of
    passing over it. Silence here is the exact defect the flag exists to end."""
    def launch(root: Path, member: gate.Launch, record: Path | None = None) -> gate.Result:
        return gate.Result(member, 0, [])

    with tempfile.TemporaryDirectory(prefix="vos-gate-unwritable-") as td:
        # a file where the verdict's parent directory must be, so `mkdir` refuses
        blocked = Path(td) / "occupied"
        blocked.write_text("not a directory", encoding="utf-8")
        with patch.object(gate, "_launch", launch):
            rep = gate.run(_ROOT, summary=blocked / "verdict.json")

    ensure(rep.findings == 1 and any("could not be written" in line for line in rep.out),
           f"an unwritable verdict is one finding naming the path, got {rep.out!r}")
    ensure(rep.out[-1] == f"ok gate: all {len(gate.MEMBERS)} host gate(s) green",
           f"the wave's own verdict is unchanged by the reporting failure, got {rep.out!r}")


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
        Case("sharded-plan-and-failures", _sharded_plan_and_failures),
        Case("members-run-in-parallel", _members_run_in_parallel),
        Case("repair-verdict-comes-from-the-fresh-wave", _repair_verdict_comes_from_the_fresh_wave),
        Case("crashed-repair-stops-before-readers", _crashed_repair_stops_before_readers),
        Case("repair-and-readonly-flags-are-exclusive", _repair_and_readonly_flags_are_exclusive),
        Case("launch-carries-the-members-verdict", _launch_carries_the_members_verdict,
             lane="host"),
        Case("launch-names-a-member-that-gave-no-verdict",
             _launch_names_a_member_that_gave_no_verdict, lane="host"),
        Case("launch-times-success-findings-and-missing-verdicts",
             _launch_times_success_findings_and_missing_verdicts),
        Case("launch-hands-a-member-its-timings-file", _launch_hands_a_member_its_timings_file),
        Case("timings-round-trip-and-never-fail-the-run",
             _timings_round_trip_and_never_fail_the_run),
        Case("verdict-names-the-member-that-reported",
             _verdict_names_the_member_that_reported),
        Case("summary-names-every-member-and-its-code",
             _summary_names_every_member_and_its_code),
        Case("summary-names-a-wave-that-never-ran", _summary_names_a_wave_that_never_ran),
        Case("unwritable-summary-is-a-finding", _unwritable_summary_is_a_finding),
        Case("gate-over-the-live-tree", _gate_over_the_live_tree, slow=True, lane="host"),
    ]
