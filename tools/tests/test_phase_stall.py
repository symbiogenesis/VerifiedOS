# SPDX-License-Identifier: Apache-2.0
"""Stall, residency and drain bounds over declared programs, and their cost join."""

import hashlib
import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import cast

from tests.harness import TOOLS, Case, ensure
from vos.cli import phase_stall as cli
from vos.jsonc import Json
from vos.phase_cost import parse
from vos.phase_stall import Analysis, SlotReport, analyze, join, read, verify_identity

EXAMPLES = TOOLS.parent / "docs" / "implementation" / "phase-service" / "program-examples"

# Every analysis the cases below run, for the two-way consistency obligation.
ANALYSES: list[tuple[str, Analysis]] = []


def _resources() -> bytes:
    return (EXAMPLES / "resources.json").read_bytes()


def _encode(value: Json) -> bytes:
    return json.dumps(value).encode("utf-8")


def _req(bank: str, operation: str, gap: int) -> dict[str, Json]:
    return {"bank": bank, "operation": operation, "gap": gap}


def _phases(grants: list[int], refresh: dict[int, list[str]] | None = None) -> list[Json]:
    return [{"grant": grant, "refresh": list((refresh or {}).get(index, []))}
            for index, grant in enumerate(grants)]


def _slot(name: str, start: int, length: int, *alternatives: list[Json]) -> dict[str, Json]:
    return {"id": name, "start": start, "length": length, "alternatives": list(alternatives)}


def _program(phases: list[Json], x: list[Json], y: list[Json] | None = None,
             resources: bytes | None = None) -> dict[str, Json]:
    return {"schema": "phase-program-v1", "name": "synthetic-relation",
            "resources_sha256": hashlib.sha256(resources or _resources()).hexdigest(),
            "phases": phases, "harts": {"X": x, "Y": y or []}}


def _custom_resources() -> bytes:
    return _encode({
        "schema": "phase-resources-v1", "operations": ["rd"],
        "harts": [{"name": "X", "issue_limit": 2}, {"name": "Y", "issue_limit": 1}],
        "banks": [{"name": "p1a", "path_cycles": 1, "occupancy_cycles": {"rd": 1}, "refresh_cycles": None},
                  {"name": "p1b", "path_cycles": 1, "occupancy_cycles": {"rd": 1}, "refresh_cycles": None},
                  {"name": "p2", "path_cycles": 2, "occupancy_cycles": {"rd": 1}, "refresh_cycles": None}],
    })


def _consistent(name: str, analysis: Analysis) -> None:
    ensure(analysis.expansion != "closed" or analysis.program_zero_wait,
           f"{name}: a closed expansion requires program_zero_wait")
    ensure(not analysis.program_zero_wait or analysis.expansion != "refuted",
           f"{name}: program_zero_wait requires an expansion not refuted by a realizable trace")
    expected = ("closed" if analysis.zero_wait else "refuted" if analysis.realizable
                else "unrealizable")
    ensure(analysis.expansion == expected and analysis.zero_wait is analysis.acceptance.zero_wait,
           f"{name}: expansion verdict disagrees with the acceptance predicate")
    ensure(analysis.program_zero_wait is analysis.stalled.program_zero_wait
           and analysis.program_zero_wait == (analysis.stalled.closed and all(
               slot.stall_total_max == 0 and slot.stall_single_max == 0
               and not slot.boundary_outstanding for slot in analysis.stalled.slots)),
           f"{name}: program_zero_wait is not the stalled exploration's own verdict")


def _analyze(name: str, program: Json, resources: bytes | None = None) -> Analysis:
    analysis = analyze(_encode(program), resources or _resources())
    _consistent(name, analysis)
    ANALYSES.append((name, analysis))
    return analysis


def _fixture(name: str) -> Analysis:
    analysis = analyze((EXAMPLES / f"{name}.json").read_bytes(), _resources())
    _consistent(name, analysis)
    ANALYSES.append((name, analysis))
    return analysis


def _slot_report(analysis: Analysis, name: str) -> SlotReport:
    for report in analysis.stalled.slots:
        if report.slot == name:
            return report
    raise AssertionError(f"no report for slot {name}")


def _expect(analysis: Analysis, name: str, total: int, single: int, outstanding: bool,
            residency: int, drain: int) -> None:
    report = _slot_report(analysis, name)
    ensure((report.stall_total_max, report.stall_single_max, report.boundary_outstanding,
            report.boundary_residency_max, report.drain_max)
           == (total, single, outstanding, residency, drain),
           f"{name}: reported {report}, expected {(total, single, outstanding, residency, drain)}")
    ensure((report.boundary_witness is not None) is outstanding,
           f"{name}: a boundary-outstanding slot carries its witness and no other does")


def _refresh_stall() -> None:
    analysis = _fixture("refresh-stall")
    ensure(analysis.stalled.closed and analysis.stalled.ordered is True, "must close")
    _expect(analysis, "sx", 2, 2, False, 0, 0)
    ensure(not analysis.program_zero_wait and not analysis.zero_wait
           and analysis.expansion == "refuted" and analysis.realizable is True
           and analysis.acceptance.reason == "arrival-blocked",
           "the reservation must refute zero wait by a realizable trace")


def _joint_loser() -> None:
    analysis = _fixture("joint-loser")
    ensure(analysis.stalled.closed, "must close")
    _expect(analysis, "sx", 3, 3, False, 0, 0)
    _expect(analysis, "sy", 3, 3, False, 0, 0)
    ensure(analysis.expansion == "refuted" and len(analysis.acceptance.trace) == 1
           and len(analysis.acceptance.trace[0]) == 2,
           "two harts on one bank refute zero wait jointly and realizably")
    ensure(analysis.stalled.states > 2, "both arbiter choices must be explored")


def _split_run() -> None:
    analysis = _fixture("split-run")
    ensure(analysis.stalled.closed, "must close")
    _expect(analysis, "sx", 1, 1, False, 0, 0)
    ensure(analysis.expansion == "refuted", "the joint run exceeds grant 1 under zero wait")


def _path_wait() -> None:
    analysis = _fixture("path-wait")
    ensure(analysis.stalled.closed and analysis.stalled.ordered is True, "must close ordered")
    _expect(analysis, "sx", 1, 1, False, 0, 0)
    ensure(analysis.expansion == "refuted" and analysis.acceptance.reason == "order-inverted",
           "the interlock wait coincides with the expansion's order-inverted refutation")


def _boundary_outstanding() -> None:
    analysis = _fixture("boundary-outstanding")
    ensure(analysis.stalled.closed, "must close")
    _expect(analysis, "sx", 1, 1, True, 4, 0)
    witness = _slot_report(analysis, "sx").boundary_witness
    ensure(witness is not None and len(witness) == 2 and not witness[1][0].accepted,
           "the shortest witness ends at the slot end with the refused write")


def _worked_tail() -> None:
    analysis = _fixture("worked-tail")
    ensure(analysis.stalled.closed and analysis.stalled.ordered is True, "must close ordered")
    _expect(analysis, "sx", 3, 3, True, 4, 0)
    _expect(analysis, "sy", 0, 0, False, 0, 1)
    witness = _slot_report(analysis, "sx").boundary_witness
    ensure(witness is not None and [len(cycle) for cycle in witness] == [2, 2, 1]
           and [request.accepted for request in witness[0]] == [True, False]
           and witness[1][0].hart == "X" and witness[1][1].hart == "Y",
           "traces list presented requests in hart order and then declared order")


def _grant_gap() -> None:
    # The read is due in the zero-grant phase, is held across the frame wrap and is
    # accepted in the next frame's granted phase, before its next occurrence begins.
    analysis = _analyze("grant-gap", _program(
        _phases([2, 0]), [_slot("sx", 1, 1, [_req("b0", "rd", 0)])]))
    ensure(analysis.stalled.closed, "the grant gap yields a finite bound")
    _expect(analysis, "sx", 1, 1, True, 1, 0)
    ensure(not analysis.zero_wait and analysis.expansion == "refuted"
           and analysis.contract.grants == (2, 0), "zero wait stays refuted by a realizable trace")


def _frame_wrap() -> None:
    analysis = _analyze("frame-wrap", _program(
        _phases([1, 1, 1, 1]), [_slot("sx", 0, 3, [_req("b0", "rd", 0)])],
        [_slot("sy", 3, 1, [_req("b0", "wr", 0)])]))
    ensure(analysis.stalled.closed, "the final-cycle write yields a finite bound")
    _expect(analysis, "sx", 2, 2, False, 0, 0)
    _expect(analysis, "sy", 0, 0, False, 0, 2)
    ensure(not analysis.zero_wait and analysis.expansion == "refuted"
           and len(analysis.acceptance.trace) == 5, "occupancy must survive frame wrap")


def _zero_wait_paths() -> None:
    resources = _custom_resources()
    equal = _analyze("equal-paths", _program(
        _phases([1, 1, 1]), [_slot("sx", 0, 3, [_req("p1a", "rd", 0), _req("p1b", "rd", 1)])],
        resources=resources), resources)
    ensure(equal.program_zero_wait and equal.zero_wait and equal.expansion == "closed",
           "equal paths give zero wait")
    ordered = _analyze("path-2-then-1", _program(
        _phases([1, 1, 1]), [_slot("sx", 0, 3, [_req("p2", "rd", 0), _req("p1a", "rd", 1)])],
        resources=resources), resources)
    ensure(ordered.program_zero_wait and ordered.zero_wait and ordered.stalled.ordered is True,
           "a path-2 request followed one cycle later by a path-1 request gives zero wait")
    inverted = _analyze("path-2-then-1-same-cycle", _program(
        _phases([2, 1, 1]), [_slot("sx", 0, 3, [_req("p2", "rd", 0), _req("p1a", "rd", 0)])],
        resources=resources), resources)
    _expect(inverted, "sx", 1, 1, False, 0, 0)
    ensure(inverted.acceptance.reason == "order-inverted", "the same-cycle pair waits once")


def _path_blocked() -> None:
    analysis = _analyze("path-blocked", _program(
        _phases([2, 0, 0]), [_slot("sx", 0, 1, [_req("f2", "rd", 0)])],
        [_slot("sy", 0, 1, [_req("f2", "rd", 0)])]))
    ensure(not analysis.stalled.closed and analysis.stalled.reason == "path-blocked"
           and analysis.stalled.ordered is None and len(analysis.stalled.trace) == 2
           and not analysis.stalled.slots and not analysis.program_zero_wait,
           "a nonzero-path arrival at a busy bank stays the path-blocked refutation")
    ensure(analysis.acceptance.reason == "path-blocked", "the expansion agrees")


def _refresh_overlap() -> None:
    analysis = _analyze("refresh-overlap", _program(
        _phases([1, 1, 1, 1, 1], {2: ["b0"]}),
        [_slot("sx", 0, 5, [_req("b0", "rd", 0), _req("b0", "wr", 0)])]))
    ensure(not analysis.stalled.closed and analysis.stalled.reason == "refresh-overlap"
           and len(analysis.stalled.trace) == 2
           and [request.accepted for request in analysis.stalled.trace[0]] == [True, False]
           and analysis.stalled.trace[1][0].accepted,
           "a held request accepted into a reservation is refuted as refresh-overlap")


def _completion_inversion() -> None:
    analysis = _analyze("completion-inversion", _program(
        _phases([1, 1, 1]), [_slot("sx", 0, 3, [_req("b0", "wr", 0), _req("b1", "rd", 1)])]))
    ensure(analysis.stalled.closed and analysis.stalled.ordered is False
           and analysis.stalled.refuted and analysis.stalled.inversion is not None
           and len(analysis.stalled.inversion) == 2,
           "the shorter later operation completing first is a completion inversion with its trace")
    _expect(analysis, "sx", 0, 0, False, 0, 0)
    ensure(analysis.expansion == "closed", "acceptance closes while completion order fails")


def _residency_overrun() -> None:
    analysis = _analyze("residency-overrun", _program(
        _phases([1, 1]), [_slot("sx", 0, 1, [_req("b0", "rd", 0)])],
        [_slot("sy", 1, 1, [_req("b0", "wr", 0)])]))
    overrun = analysis.stalled.overrun
    ensure(not analysis.stalled.closed and analysis.stalled.reason == "residency-overrun"
           and overrun is not None and (overrun.hart, overrun.slot, overrun.residency)
           == ("X", "sx", 1) and len(analysis.stalled.trace) == 4,
           "a request held into its next occurrence reports hart, slot, residency and trace")


def _unrealizable() -> None:
    analysis = _analyze("unrealizable", _program(
        _phases([1, 1, 1]), [_slot("sx", 0, 3, [_req("b0", "wr", 0)], [_req("b0", "rd", 1)])]))
    ensure(analysis.expansion == "unrealizable" and analysis.realizable is False
           and not analysis.zero_wait and analysis.program_zero_wait
           and len(analysis.acceptance.trace) == 2,
           "the product's cross-phase refutation is inconclusive; the program language decides")


def _refused(program: Json | bytes, fragment: str, resources: bytes | None = None) -> None:
    raw = program if isinstance(program, bytes) else _encode(program)
    try:
        read(raw, resources or _resources())
    except (TypeError, ValueError) as err:
        ensure(fragment in str(err), f"wrong refusal: {err}")
        return
    raise AssertionError(f"invalid program accepted, expected {fragment}")


def _refusals() -> None:
    base = _program(_phases([1, 1]), [_slot("sx", 0, 2, [_req("b0", "rd", 0)])])
    _refused(_program(_phases([2, 2]), [], [_slot("sy", 0, 2, [_req("b0", "rd", 0), _req("b1", "rd", 0)])]),
             "issue_limit")
    _refused(_program(_phases([1, 1]), [_slot("sx", 0, 2, [_req("b0", "rd", 0), _req("b1", "rd", 2)])]),
             "leaves its slot")
    _refused({**base, "resources_sha256": "0" * 64}, "does not match")
    _refused({**base, "resources_sha256": "x"}, "digest")
    _refused({**base, "mode": "periodic"}, "exactly")
    _refused({**base, "schema": "phase-schedule-v1"}, "phase-program-v1")
    _refused({**base, "name": ""}, "identifier")
    _refused({**base, "phases": []}, "nonempty")
    _refused({**base, "phases": [{"grant": 1, "refresh": [], "alternatives": []}]}, "exactly")
    _refused({**base, "phases": [{"grant": True, "refresh": []}]}, "integer")
    _refused({**base, "phases": _phases([1, 1], {0: ["b1"]})}, "refresh")
    _refused({**base, "harts": {"X": []}}, "declared hart names")
    _refused({**base, "harts": {"X": [], "Y": [], "Z": []}}, "declared hart names")
    _refused(_program(_phases([1, 1]), [_slot("sx", 0, 2, [_req("b0", "rd", 0)]), _slot("sx", 1, 1, [])]),
             "duplicate slot id")
    _refused(_program(_phases([1, 1]), [_slot("sx", 0, 2, []), _slot("sz", 1, 1, [])]), "overlap")
    _refused(_program(_phases([1, 1]), [_slot("sx", 1, 2, [])]), "phase count")
    _refused(_program(_phases([1, 1]), [_slot("sx", 0, 0, [])]), "integer")
    _refused(_program(_phases([1, 1]), [_slot("sx", 0, 2)]), "nonempty")
    _refused(_program(_phases([1, 1]), [_slot("sx", 0, 2, [_req("missing", "rd", 0)])]), "unknown bank")
    _refused(_program(_phases([1, 1]), [_slot("sx", 0, 2, [_req("b1", "wr", 0)])]), "occupancy")
    _refused(_program(_phases([1, 1]), [_slot("sx", 0, 2, [{**_req("b0", "rd", 0), "hart": "X"}])]),
             "exactly")
    _refused(_program(_phases([1, 1]), [_slot("sx", 0, 2, [_req("b0", "rd", -1)])]), "integer")
    raw = _encode(base)
    _refused(raw.replace(b'"gap": 0', b'"gap": 0.0'), "floating-point")
    _refused(raw.replace(b'"gap": 0', b'"gap": false'), "integer")
    _refused(raw.replace(b'"start": 0', b'"start": 0, "start": 0'), "duplicate")
    _refused(raw, "does not match", _resources() + b"\n")


def _cost_identity() -> None:
    analysis = _fixture("worked-tail")
    favorable = EXAMPLES / "costs-favorable.json"
    comparison = parse(favorable.read_bytes())
    verify_identity(comparison, analysis, favorable, EXAMPLES / "worked-tail.json")
    data = cast("dict[str, Json]", json.loads(favorable.read_bytes()))
    slots = cast("list[Json]", data["slots"])
    cast("dict[str, Json]", slots[0])["id"] = "missing"
    try:
        join(analysis, parse(_encode(data)))
    except ValueError as err:
        ensure("no program slot" in str(err), f"wrong refusal: {err}")
    else:
        raise AssertionError("a cost slot naming no program slot was joined")
    for field, wrong in (("id", "synthetic-other"), ("sha256", "0" * 64), ("path", "split-run.json")):
        data = cast("dict[str, Json]", json.loads(favorable.read_bytes()))
        cast("dict[str, Json]", data["schedule"])[field] = wrong
        try:
            verify_identity(parse(_encode(data)), analysis, favorable, EXAMPLES / "worked-tail.json")
        except ValueError:
            continue
        raise AssertionError(f"a schedule object with a wrong {field} named the program")


def _all_zero() -> None:
    analysis = _analyze("all-zero", _program(_phases([1, 1]), [_slot("sx", 0, 2, [_req("b0", "rd", 0)])]))
    _expect(analysis, "sx", 0, 0, False, 0, 0)
    ensure(analysis.program_zero_wait and analysis.zero_wait and analysis.expansion == "closed"
           and analysis.stalled.ordered is True, "every bound zero closes both predicates")


def _call(args: list[str]) -> tuple[int, dict[str, Json]]:
    output = StringIO()
    with redirect_stdout(output):
        code = cli.main([*args, "--json"])
    report = cast("Json", json.loads(output.getvalue()))
    if not isinstance(report, dict):
        raise TypeError("the receipt is an object")
    return code, report


def _joins() -> None:
    analysis = _fixture("worked-tail")
    expected: tuple[tuple[str, str, int], ...] = (
        ("favorable", "favorable", 0), ("understated-stalls", "refuted", 1),
        ("trap-below-residency", "refuted", 1), ("overlap", "inconclusive", 0),
        ("unknown-trap", "open", 0), ("drain-below", "refuted", 1))
    for name, verdict, exit_code in expected:
        joined = join(analysis, parse((EXAMPLES / f"costs-{name}.json").read_bytes()))
        ensure(joined["join_verdict"] == verdict, f"costs-{name} joined {joined['join_verdict']}")
        ensure(joined["unjoined"] == [], f"costs-{name} names every program slot")
        code, report = _call([str(EXAMPLES / "worked-tail.json"), str(EXAMPLES / "resources.json"),
                              "--costs", str(EXAMPLES / f"costs-{name}.json")])
        ensure(code == exit_code and cast("dict[str, Json]", report["join"])["join_verdict"] == verdict,
               f"costs-{name}: exit {code}")
    joined = join(analysis, parse((EXAMPLES / "costs-unknown-trap.json").read_bytes()))
    ensure("boundary-outstanding-uncovered" in cast("list[Json]", joined["reasons"]),
           "an unknown residency operand at an outstanding slot names its reason")
    joined = join(analysis, parse((EXAMPLES / "costs-drain-below.json").read_bytes()))
    ensure(cast("dict[str, Json]", joined["drain"])["modeled"] == 1
           and cast("dict[str, Json]", joined["arithmetic"])["arithmetic_verdict"] == "favorable",
           "favorable arithmetic never outweighs a refuted drain term")
    data = cast("dict[str, Json]", json.loads((EXAMPLES / "costs-favorable.json").read_bytes()))
    data["slots"] = [cast("list[Json]", data["slots"])[0]]
    joined = join(analysis, parse(_encode(data)))
    ensure(joined["unjoined"] == [{"hart": "Y", "slot": "sy"}]
           and cast("dict[str, Json]", joined["drain"])["modeled"] == 0,
           "unnamed program slots act as contention only and are reported unjoined")


def _receipt() -> None:
    program = EXAMPLES / "worked-tail.json"
    resources = EXAMPLES / "resources.json"
    code, report = _call([str(program), str(resources)])
    ensure(code == 0 and report["target_comparison"] == "open" and report["join"] is None,
           "a closed exploration exits 0 whatever zero_wait reports")
    digests = cast("dict[str, Json]", report["inputs_sha256"])
    ensure(digests == {"program": hashlib.sha256(program.read_bytes()).hexdigest(),
                       "resources": hashlib.sha256(resources.read_bytes()).hexdigest()},
           "the receipt binds the program and resource bytes")
    sources = cast("dict[str, Json]", report["sources_sha256"])
    ensure(set(sources) == set(cli.SOURCES) and all(
        sources[name] == hashlib.sha256((TOOLS.parent / name).read_bytes()).hexdigest()
        for name in cli.SOURCES), "the receipt binds the instrument, CLI, tests and contract")
    ensure("WCET" in cast("list[Json]", report["not_established"])
           and "instruction-stream correspondence" in cast("list[Json]", report["not_established"]),
           "the receipt names what the analysis does not establish")
    statements = cast("dict[str, Json]", report["statements"])
    ensure("cannot check" in str(statements["serial_domain"])
           and "no residency coverage" in str(statements["residency_coverage"]),
           "the receipt states the uncheckable domain condition and the residency scope")
    analysis = cast("dict[str, Json]", report["analysis"])
    ensure(analysis["expansion"] == "refuted" and analysis["zero_wait"] is False
           and analysis["program_zero_wait"] is False, "the receipt carries the verdicts")
    code, report = _call([str(program), str(resources), "--costs", str(EXAMPLES / "costs-favorable.json")])
    ensure(code == 0 and "costs" in cast("dict[str, Json]", report["inputs_sha256"]),
           "the receipt binds the cost bytes")
    with tempfile.TemporaryDirectory() as tmp:
        blocked = Path(tmp) / "blocked.json"
        blocked.write_bytes(_encode(_program(
            _phases([2, 0, 0]), [_slot("sx", 0, 1, [_req("f2", "rd", 0)])],
            [_slot("sy", 0, 1, [_req("f2", "rd", 0)])])))
        code, report = _call([str(blocked), str(resources)])
        ensure(code == 1 and cast("dict[str, Json]", cast("dict[str, Json]", report["analysis"])["stalled"])["reason"]
               == "path-blocked", "a program-contract refutation exits 1")
        code, report = _call([str(Path(tmp) / "missing.json"), str(resources)])
        ensure(code == 2 and "error" in report, "a missing program exits 2 with a reason")
        stale = Path(tmp) / "resources.json"
        stale.write_bytes(resources.read_bytes() + b"\n")
        code, report = _call([str(program), str(stale)])
        ensure(code == 2 and "does not match" in str(report["error"]), "stale resources exit 2")
        costs = Path(tmp) / "costs.json"
        costs.write_bytes((EXAMPLES / "costs-favorable.json").read_bytes())
        code, report = _call([str(program), str(resources), "--costs", str(costs)])
        ensure(code == 2 and "name the program" in str(report["error"]),
               "a schedule object resolving to another path is a stale-input refusal")


def _consistency() -> None:
    ensure(len(ANALYSES) >= 15, "the consistency obligation covered too few analyses")
    for name, analysis in ANALYSES:
        _consistent(name, analysis)


def cases() -> list[Case]:
    return [Case("refresh-stall", _refresh_stall), Case("joint-loser", _joint_loser),
            Case("split-run", _split_run), Case("path-wait", _path_wait),
            Case("boundary-outstanding", _boundary_outstanding), Case("worked-tail", _worked_tail),
            Case("grant-gap", _grant_gap), Case("frame-wrap", _frame_wrap),
            Case("zero-wait-paths", _zero_wait_paths), Case("path-blocked", _path_blocked),
            Case("refresh-overlap", _refresh_overlap),
            Case("completion-inversion", _completion_inversion),
            Case("residency-overrun", _residency_overrun), Case("unrealizable", _unrealizable),
            Case("refusals", _refusals), Case("cost-identity", _cost_identity),
            Case("all-zero", _all_zero), Case("joins", _joins), Case("receipt", _receipt),
            Case("consistency", _consistency)]
