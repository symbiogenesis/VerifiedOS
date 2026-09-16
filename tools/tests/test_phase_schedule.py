# SPDX-License-Identifier: Apache-2.0
"""Hold declared schedule extraction to the finite service contract and its scope."""

import hashlib
import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import cast

from tests.harness import TOOLS, Case, ensure
from vos.cli import phase_schedule as cli
from vos.cli.phase_service import load_contract
from vos.jsonc import Json
from vos.phase_schedule import contract_bytes, extract
from vos.phase_service import check

EXAMPLES = TOOLS.parent / "docs" / "implementation" / "phase-service" / "schedule-examples"


def _encode(value: Json) -> bytes:
    return json.dumps(value).encode("utf-8")


def _resources() -> dict[str, Json]:
    return {
        "schema": "phase-resources-v1", "operations": ["read", "write"],
        "harts": [{"name": "h0", "issue_limit": 2}, {"name": "h1", "issue_limit": 1}],
        "banks": [{"name": "b0", "path_cycles": 0, "refresh_cycles": 1,
                   "occupancy_cycles": {"read": 1, "write": 2}},
                  {"name": "b1", "path_cycles": 1, "refresh_cycles": None,
                   "occupancy_cycles": {"read": 1}}],
    }


def _request(bank: str = "b0", hart: str = "h0", operation: str = "read") -> dict[str, Json]:
    return {"bank": bank, "hart": hart, "operation": operation}


def _phase(alternatives: list[Json], grant: int = 2, refresh: list[Json] | None = None) -> Json:
    return {"grant": grant, "alternatives": alternatives, "refresh": refresh or []}


def _schedule(resources: bytes, phases: list[Json] | None = None) -> dict[str, Json]:
    return {"schema": "phase-schedule-v1", "name": "synthetic-test", "mode": "periodic",
            "resources_sha256": hashlib.sha256(resources).hexdigest(),
            "phases": phases if phases is not None else [_phase([[], [_request()]])]}


def _refused(schedule: bytes, resources: bytes, fragment: str) -> None:
    try:
        extract(schedule, resources)
    except (TypeError, ValueError) as err:
        ensure(fragment in str(err), f"wrong refusal: {err}")
        return
    raise AssertionError(f"invalid input accepted, expected {fragment}")


def _counterexamples() -> None:
    resources = (EXAMPLES / "resources.json").read_bytes()
    expected = {"grant-gap": (False, 1, 2), "same-bank-joint": (False, 0, 1),
                "frame-wrap": (False, 0, 3), "closed-companion": (True, None, 0)}
    for name, (zero_wait, phase, trace_length) in expected.items():
        extraction = extract((EXAMPLES / f"{name}.json").read_bytes(), resources)
        result = check(extraction.contract)
        ensure(result.zero_wait is zero_wait and len(result.trace) == trace_length,
               f"{name} lost its verdict or trace")
        ensure((result.failure[0] if result.failure else None) == phase,
               f"{name} lost phase or frame-wrap state")
        if name == "grant-gap":
            ensure(extraction.contract.grants == (2, 0)
                   and len(extraction.injection_excesses) == 1
                   and extraction.injection_excesses[0].phase == 1,
                   "over-grant alternatives must be retained for a service refutation")
        if name == "same-bank-joint":
            ensure(len(result.trace[-1]) == 2, "individually legal requests were split")


def _joint_order_and_paths() -> None:
    resources = _encode(_resources())
    phases = [_phase([[], [_request("b0"), _request("b1", "h1")], [_request("b1")]])]
    extraction = extract(_encode(_schedule(resources, phases)), resources)
    ensure(extraction.contract.arrivals == (((), ((0, 1, 0), (1, 1, 1)), ((1, 1, 0),)),),
           "alternatives or batch order changed, or joint alternatives were factored")
    ensure(extraction.bank_names == ("b0", "b1") and extraction.hart_names == ("h0", "h1")
           and extraction.operation_names == ("read", "write")
           and extraction.contract.paths == (0, 1), "stable names and paths lost")
    first_far = [_phase([[_request("b1"), _request("b0")]])]
    inverted = check(extract(_encode(_schedule(resources, first_far)), resources).contract)
    ensure(not inverted.zero_wait and inverted.reason == "order-inverted",
           "request order within a batch must reach the service checker")
    near_first = [_phase([[_request("b0"), _request("b1")]])]
    ensure(check(extract(_encode(_schedule(resources, near_first)), resources).contract).zero_wait,
           "the ordered path companion should close")
    # Each hart respects its own limit and the requests use different banks, but
    # the phase still has just one aggregate injection grant.
    simultaneous = [_phase([[_request(), _request("b1", "h1")]], grant=1)]
    extraction = extract(_encode(_schedule(resources, simultaneous)), resources)
    result = check(extraction.contract)
    ensure(not result.zero_wait and result.reason == "arrival-blocked"
           and extraction.injection_excesses[0].requests == 2,
           "per-hart legality cannot hide aggregate simultaneous grant excess")
    duplicates = [_phase([[], [], [_request()], [_request()]])]
    extraction = extract(_encode(_schedule(resources, duplicates)), resources)
    ensure(extraction.contract.arrivals == (((), (), ((0, 1, 0),), ((0, 1, 0),)),),
           "even repeated alternatives must retain their declared indices")


def _refresh_and_wrap() -> None:
    resources = _encode(_resources())
    phases = [_phase([[]], refresh=["b0"]), _phase([[_request(operation="write")]])]
    extraction = extract(_encode(_schedule(resources, phases)), resources)
    ensure(extraction.contract.refresh == (((0, 1),), ()), "refresh table changed")
    result = check(extraction.contract)
    ensure(result.reason == "refresh-overlap" and result.failure is not None
           and result.failure[0] == 0 and result.failure[1] == (1, 0),
           "bank occupancy must survive wrap into scheduled refresh")


def _issue_and_references() -> None:
    resources = _encode(_resources())
    _refused(_encode(_schedule(resources, [_phase([[_request()] * 3], grant=3)])),
             resources, "issue_limit")
    for request in (_request(bank="missing"), _request(hart="missing"),
                    _request(operation="missing"), _request(bank="b1", operation="write")):
        _refused(_encode(_schedule(resources, [_phase([[request]])])), resources,
                 "unknown" if "missing" in (request["bank"], request["hart"]) else "occupancy")
    for banks in (["missing"], ["b0", "b0"], ["b1"]):
        _refused(_encode(_schedule(resources, [_phase([[]], refresh=list(banks))])), resources,
                 "refresh")


def _strict_inputs() -> None:
    resources = _encode(_resources())
    invalid: tuple[tuple[dict[str, Json], str], ...] = (({"mode": "multi-mode"}, "periodic"),
                              ({"transitions": []}, "exactly"),
                              ({"modes": []}, "exactly"),
                              ({"qualified": True}, "exactly"),
                              ({"resources_sha256": "0" * 64}, "does not match"),
                              ({"resources_sha256": "x"}, "digest"),
                              ({"name": ""}, "identifier"),
                              ({"phases": []}, "nonempty"),
                              ({"phases": [_phase([])]}, "nonempty"),
                              ({"phases": [{"grant": 1, "alternatives": [[]]}]}, "exactly"),
                              ({"phases": [{"grant": 1, "alternatives": [[]], "refresh": [],
                                            "qualified": True}]}, "exactly"),
                              ({"phases": [_phase([[{**_request(), "wait": 0}]])]}, "exactly"),
                              ({"phases": [{"grant": True, "alternatives": [[]], "refresh": []}]},
                               "integer"))
    for changes, fragment in invalid:
        _refused(_encode({**_schedule(resources), **changes}), resources, fragment)
    schedule = _encode(_schedule(resources))
    _refused(schedule.replace(b'"mode": "periodic"', b'"mode": "periodic", "mode": "periodic"'),
             resources, "duplicate")
    _refused(schedule.replace(b'"grant": 2', b'"grant": 2.0'), resources, "floating-point")
    _refused(schedule.replace(b'"grant": 2', b'"grant": NaN'), resources, "floating-point")
    _refused(b"\xff", resources, "utf-8")
    # Byte identity, including harmless whitespace, is the producer's commitment.
    _refused(schedule, resources + b"\n", "does not match")


def _resource_shapes() -> None:
    invalid: tuple[tuple[dict[str, Json], str], ...] = (({"qualified": True}, "exactly"),
                              ({"operations": ["read", "read"]}, "duplicate"),
                              ({"operations": []}, "nonempty"),
                              ({"harts": [{"name": "h0", "issue_limit": 1}] * 2}, "duplicate"),
                              ({"harts": [{"name": "h0", "issue_limit": False}]}, "integer"),
                              ({"banks": []}, "nonempty"))
    for changes, fragment in invalid:
        resources = _encode({**_resources(), **changes})
        _refused(_encode(_schedule(resources)), resources, fragment)
    banks: list[Json] = [{"name": "b0", "path_cycles": 0, "refresh_cycles": None,
                         "occupancy_cycles": {"read": 1}}]
    resources = _encode({**_resources(), "banks": banks * 2})
    _refused(_encode(_schedule(resources)), resources, "duplicate bank")
    invalid_banks: tuple[tuple[str, Json, str], ...] = (("path_cycles", -1, "integer"),
                                    ("refresh_cycles", 0, "integer"),
                                    ("occupancy_cycles", {"read": 0}, "integer"),
                                    ("occupancy_cycles", {"unknown": 1}, "unknown"),
                                    ("occupancy_cycles", {}, "nonempty"))
    for field, value, fragment in invalid_banks:
        bank = cast(dict[str, Json], banks[0])
        resources = _encode({**_resources(), "banks": [{**bank, field: value}]})
        _refused(_encode(_schedule(resources)), resources, fragment)
    resources = _encode(_resources()).replace(b'"read": 1', b'"read": 1, "read": 2')
    _refused(_encode(_schedule(resources)), resources, "duplicate JSON")


def _cli_receipt_and_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as directory:
        output_path = Path(directory) / "contract.json"
        schedule_path = EXAMPLES / "closed-companion.json"
        resources_path = EXAMPLES / "resources.json"
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main([str(schedule_path), str(resources_path), "--json",
                             "--output-contract", str(output_path)])
        report = json.loads(output.getvalue())
        ensure(code == 0 and report["result"]["zero_wait"] and report["target_comparison"] == "open",
               "a closed declaration cannot qualify the target")
        ensure(report["schedule_sha256"] == hashlib.sha256(schedule_path.read_bytes()).hexdigest()
               and report["resources_sha256"] == hashlib.sha256(resources_path.read_bytes()).hexdigest()
               and report["contract_sha256"] == hashlib.sha256(output_path.read_bytes()).hexdigest(),
               "receipt must bind both sources and the emitted bytes")
        contract = load_contract(output_path)
        ensure(check(contract).zero_wait and output_path.read_bytes() == contract_bytes(contract),
               "canonical output must round-trip through phase-service")
        ensure(report["sources_sha256"]["tools/vos/phase_service.py"]
               == hashlib.sha256((TOOLS / "vos" / "phase_service.py").read_bytes()).hexdigest(),
               "receipt must bind the deciding service implementation")
        for schedule, resources, extra, expected in (
                (EXAMPLES / "grant-gap.json", resources_path, [], 1),
                (Path(directory) / "missing.json", resources_path, [], 2),
                (schedule_path, Path(directory), [], 2),
                (schedule_path, resources_path, ["--output-contract", str(output_path)], 2),
                (schedule_path, resources_path, ["--output-contract", str(resources_path)], 2)):
            output = StringIO()
            with redirect_stdout(output):
                code = cli.main([str(schedule), str(resources), "--json", *extra])
            report = json.loads(output.getvalue())
            ensure(code == expected and report["target_comparison"] == "open",
                   "CLI exit must distinguish a service refutation from malformed input")
            ensure(expected != 2 or "error" in report, "exit 2 requires a structured reason")
        refused_path = Path(directory) / "refused-contract.json"
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main([str(EXAMPLES / "frame-wrap.json"), str(resources_path),
                             "--output-contract", str(refused_path)])
        ensure(code == 1 and not check(load_contract(refused_path)).zero_wait
               and "target comparison open" in output.getvalue(),
               "a refuted contract must remain exportable and scope visible without JSON")


def cases() -> list[Case]:
    return [Case("counterexamples", _counterexamples),
            Case("joint-order-and-paths", _joint_order_and_paths),
            Case("refresh-and-wrap", _refresh_and_wrap),
            Case("issue-and-references", _issue_and_references),
            Case("strict-inputs", _strict_inputs), Case("resource-shapes", _resource_shapes),
            Case("cli-receipt-and-roundtrip", _cli_receipt_and_roundtrip)]
