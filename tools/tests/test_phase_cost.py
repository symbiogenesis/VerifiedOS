# SPDX-License-Identifier: Apache-2.0
"""Cost arithmetic rejects concealed stalls, uncertain bounds and stale identities."""

import hashlib
import json
import tempfile
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos.cli import phase_cost as cli
from vos.phase_cost import Comparison, Interval, assess, bind_schedule, parse

EXAMPLES = TOOLS.parent / "docs/implementation/phase-service/cost-examples"
EXPECTED = {
    "favorable": "favorable", "switch-stalls": "inconclusive", "deadline": "refuted",
    "overlap": "inconclusive", "unknown": "open", "area-budget": "refuted",
    "power-budget": "refuted", "baseline-infeasible": "inconclusive",
}


def _fixture(name: str = "favorable") -> Comparison:
    return parse((EXAMPLES / f"{name}.json").read_bytes())


def _examples() -> None:
    files = {path.stem for path in EXAMPLES.glob("*.json") if path.name != "schedule.json"}
    ensure(files == set(EXPECTED), "the fixture set changed without reviewed expected verdicts")
    for name, verdict in EXPECTED.items():
        path = EXAMPLES / f"{name}.json"
        model = _fixture(name)
        ensure(assess(model)["arithmetic_verdict"] == verdict, f"wrong verdict for {name}")
        ensure(bind_schedule(model, path)["sha256"] == model.schedule_sha256,
               f"unbound schedule for {name}")


def _boundary_once() -> None:
    model = _fixture()
    result = assess(model)
    ensure(result["frame_cycles"] == {"baseline": [154, 154], "candidate": [138, 138],
                                      "net_saving": [16, 16], "switch_saving": [16, 16]},
           "two switches must charge fence/drain, shared costs and trap exactly twice")
    slot = model.slots[0]
    second = replace(slot, name="second", switches=0)
    result = assess(replace(model, slots=(slot, second), frame_budget=Interval(400, 400)))
    ensure(result["frame_cycles"] == {"baseline": [268, 268], "candidate": [252, 252],
                                      "net_saving": [16, 16], "switch_saving": [16, 16]},
           "serial frame sum must include every slot without inventing a switch")
    result = assess(replace(model, slots=(slot, second), frame_budget=Interval(250, 250)))
    ensure(result["arithmetic_verdict"] == "refuted",
           "individually fitting serial slots must still satisfy the frame budget")
    result = assess(replace(model, vmclear=Interval(2, 4), opp_relock=Interval(4, 6)))
    ensure(result["frame_cycles"] == {"baseline": [150, 158], "candidate": [134, 142],
                                      "net_saving": [16, 16], "switch_saving": [16, 16]},
           "common boundary uncertainty must cancel in the saving but remain in budgets")


def _stalls_and_deadlines() -> None:
    stalled = assess(_fixture("switch-stalls"))
    ensure(stalled["frame_cycles"] == {"baseline": [154, 154], "candidate": [158, 158],
                                       "net_saving": [-4, -4], "switch_saving": [16, 16]},
           "positive switch saving must not hide service-stall regression")
    model = _fixture()
    # Aggregate frame slack cannot buy a violated slot deadline.
    slot = replace(model.slots[0], deadline=Interval(130, 130))
    result = assess(replace(model, slots=(slot,), frame_budget=Interval(1000, 1000)))
    ensure(result["arithmetic_verdict"] == "refuted", "slot deadline violation was hidden")
    # A failed baseline must not become a favorable comparison merely through savings.
    result = assess(_fixture("baseline-infeasible"))
    ensure(result["baseline_budget_status"] != result["candidate_budget_status"]
           and result["reason"] == "baseline feasibility is not established",
           "baseline infeasibility must be explicit")


def _conservative() -> None:
    model = _fixture()
    ensure(assess(replace(model, candidate_area=Interval(990, 1010)))["arithmetic_verdict"]
           == "inconclusive", "overlapping area intervals cannot establish no regression")
    ensure(assess(replace(model, candidate_power=Interval(105, 105)))["arithmetic_verdict"]
           == "inconclusive", "time savings cannot trade away a power regression")
    ensure(assess(replace(model, area_budget=Interval(800, 950)))["arithmetic_verdict"]
           == "inconclusive", "uncertain budget must not count as met")
    ensure(assess(replace(model, candidate_area=Interval(1200, 1200)))["arithmetic_verdict"]
           == "inconclusive", "equality meets a budget, but does not remove regression")
    equal = replace(model, d_pipe_completion=model.fence_t,
                    candidate_area=model.baseline_area, candidate_power=model.baseline_power)
    ensure(assess(equal)["arithmetic_verdict"] == "inconclusive", "strict improvement is required")
    partial = replace(model, baseline_power=None)
    ensure(assess(partial)["arithmetic_verdict"] == "open", "unknown baseline became zero")
    ensure(assess(replace(partial, candidate_area=Interval(1300, 1300)))["arithmetic_verdict"]
           == "refuted", "known budget violation cannot be hidden by an unrelated unknown")
    # Unbounded Python integer arithmetic must retain a one-cycle distinction.
    huge = 10 ** 50
    slot = replace(model.slots[0], deadline=Interval(huge + 200, huge + 200),
                   baseline=replace(model.slots[0].baseline, execution=Interval(huge, huge)),
                   candidate=replace(model.slots[0].candidate, execution=Interval(huge + 1, huge + 1)))
    result = assess(replace(model, slots=(slot,), frame_budget=Interval(huge + 200, huge + 200)))
    ensure(result["frame_cycles"] == {"baseline": [huge + 54, huge + 54],
                                      "candidate": [huge + 39, huge + 39],
                                      "net_saving": [15, 15], "switch_saving": [16, 16]},
           "large integer arithmetic lost a cycle")


def _refuse(raw: bytes) -> None:
    try:
        parse(raw)
    except (ValueError, TypeError):
        return
    raise AssertionError(f"malformed comparison accepted: {raw[:120]!r}")


def _invalid() -> None:
    raw = (EXAMPLES / "favorable.json").read_bytes()
    _refuse(b"[" * 10000 + b"0" + b"]" * 10000)
    for old, new in (
        (b'"version": 1', b'"version": 1, "version": 1'),
        (b'"execution": [', b'"execution": null, "execution": ['),
        (b'"version": 1', b'"version": true'),
        (b'"version": 1', b'"version": 2'),
        (b'"switches": 2', b'"switches": -1'),
        (b'"switches": 2', b'"switches": 2.0'),
        (b'"hz": 100000000', b'"hz": 0'),
        (b'"cycles"', b'"ns"'),
        (b'"serial"', b'"parallel"'),
        (b'"version": 1', b'"qualified": true, "version": 1'),
        (b'"version": 1', b'"modes": [], "version": 1'),
        (b'"switches": 2', b'"switches": NaN'),
        (b'"switches": 2', b'"switches": Infinity'),
    ):
        ensure(old in raw, f"invalid-input test stopped matching: {old!r}")
        _refuse(raw.replace(old, new, 1))
    for bad in ([2, 1], [True, 1], [-1, 2], [1.0, 2], [0], [0, 1, 2], "unknown"):
        data = json.loads(raw)
        data["boundary"]["fence_t"] = bad
        _refuse(json.dumps(data).encode())
    data = json.loads(raw)
    data["slots"].append(data["slots"][0])
    _refuse(json.dumps(data).encode())
    data = json.loads(raw)
    del data["boundary"]["vmclear"]
    result = assess(parse(json.dumps(data).encode()))
    ensure(result["arithmetic_verdict"] == "open", "omitted numeric operand became zero")


def _cli() -> None:
    path = EXAMPLES / "favorable.json"
    stream = StringIO()
    with redirect_stdout(stream):
        code = cli.main(["--input", str(path), "--json"])
    report = json.loads(stream.getvalue())
    ensure(code == 0 and report["target_comparison"] == "open", "arithmetic promoted to target")
    ensure(report["input_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest(),
           "input byte identity missing")
    for name, digest in report["sources_sha256"].items():
        ensure(hashlib.sha256((TOOLS.parent / name).read_bytes()).hexdigest() == digest,
               f"stale source identity {name}")
    with tempfile.TemporaryDirectory() as folder:
        temporary = Path(folder)
        schedule = temporary / "schedule.json"
        schedule.write_bytes((EXAMPLES / "schedule.json").read_bytes())
        comparison = temporary / "comparison.json"
        comparison.write_bytes(path.read_bytes())
        model = parse(comparison.read_bytes())
        bind_schedule(model, comparison)
        schedule.write_bytes(schedule.read_bytes() + b" ")
        with redirect_stdout(stream := StringIO()):
            code = cli.main(["--input", str(comparison), "--json"])
        ensure(code == 2 and "SHA-256 mismatch" in json.loads(stream.getvalue())["error"],
               "schedule binding must cover exact bytes including whitespace")
        comparison.write_bytes(b"[" * 10000 + b"0" + b"]" * 10000)
        with redirect_stdout(stream := StringIO()):
            code = cli.main(["--input", str(comparison), "--json"])
        ensure(code == 2 and "error" in json.loads(stream.getvalue()),
               "deep malformed JSON must produce a structured refusal")
        with redirect_stdout(stream := StringIO()):
            code = cli.main(["--input", str(temporary / "missing.json"), "--json"])
        ensure(code == 2 and "error" in json.loads(stream.getvalue()), "missing file escaped CLI")
    with redirect_stdout(stream := StringIO()):
        code = cli.main(["--input", str(EXAMPLES / "deadline.json"), "--json"])
    ensure(code == 1 and json.loads(stream.getvalue())["result"]["arithmetic_verdict"] == "refuted",
           "definite budget refusal must exit 1")


def cases() -> list[Case]:
    return [Case("examples", _examples), Case("boundary-once", _boundary_once),
            Case("stalls-and-deadlines", _stalls_and_deadlines), Case("conservative", _conservative),
            Case("invalid", _invalid), Case("cli", _cli)]
