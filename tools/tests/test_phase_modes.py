# SPDX-License-Identifier: Apache-2.0
"""Hold the mode-transition product to its contract and to the single-mode checkers."""

import hashlib
import json
import shutil
import tempfile
from collections.abc import Callable
from contextlib import redirect_stdout
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from typing import cast

from tests.harness import TOOLS, Case, ensure
from vos import phase_completion, phase_modes, phase_service
from vos.cli import phase_evaluate
from vos.cli import phase_schedule as cli
from vos.cli import phase_service as service_cli
from vos.jsonc import Json
from vos.phase_modes import (
    ModeContract,
    ModeExtraction,
    Transition,
    check,
    check_completion,
    emitted_bytes,
    mode_contract_bytes,
    read,
)
from vos.phase_schedule import Extraction, contract_bytes, extract
from vos.phase_service import Contract, scenarios

PHASE_SERVICE = TOOLS.parent / "docs" / "implementation" / "phase-service"
EXAMPLES = PHASE_SERVICE / "mode-examples"
COST_EXAMPLE = PHASE_SERVICE / "schedule-examples" / "costs.json"


def _resources() -> bytes:
    return (EXAMPLES / "resources.json").read_bytes()


def _encode(value: Json) -> bytes:
    return json.dumps(value).encode("utf-8")


def _object(value: Json) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise TypeError("expected a JSON object")
    return value


def _strings(value: Json) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TypeError("expected a JSON array of strings")
    return [item for item in value if isinstance(item, str)]


def _request(bank: str = "sram0", operation: str = "read", hart: str = "cpu0") -> dict[str, Json]:
    return {"hart": hart, "bank": bank, "operation": operation}


def _phase(alternatives: list[Json], grant: int = 1, refresh: list[Json] | None = None) -> Json:
    return {"grant": grant, "alternatives": alternatives, "refresh": refresh or []}


def _edge(source: str, from_phase: int, target: str, to_phase: int) -> Json:
    return {"from": source, "from_phase": from_phase, "to": target, "to_phase": to_phase}


def _declaration(modes: dict[str, list[Json]], initial: list[Json], transitions: list[Json],
                 resources: bytes | None = None, name: str = "synthetic-modes") -> dict[str, Json]:
    raw = resources if resources is not None else _resources()
    return {"schema": "phase-schedule-v2", "name": name,
            "resources_sha256": hashlib.sha256(raw).hexdigest(),
            "modes": {mode: {"phases": phases} for mode, phases in modes.items()},
            "initial": initial, "transitions": transitions}


def _example(name: str) -> ModeExtraction:
    extraction = read((EXAMPLES / f"{name}.json").read_bytes(), _resources())
    if not isinstance(extraction, ModeExtraction):
        raise TypeError(f"{name} did not read as a v2 declaration")
    return extraction


def _refused(schedule: bytes, resources: bytes, fragment: str) -> None:
    try:
        read(schedule, resources)
    except (TypeError, ValueError) as err:
        ensure(fragment in str(err), f"wrong refusal for {fragment}: {err}")
        return
    raise AssertionError(f"invalid input accepted, expected {fragment}")


def _wrap(contract: Contract, mode: str = "only") -> ModeContract:
    return ModeContract((mode,), {mode: contract})


def _cli(command: Callable[[list[str] | None], int], args: list[str]) -> tuple[int, dict[str, Json]]:
    output = StringIO()
    with redirect_stdout(output):
        code = command([*args, "--json"])
    return code, _object(cast("Json", json.loads(output.getvalue())))


def _refusals() -> None:
    resources = _resources()
    for name, fragment in (("undeclared-transition-mode", "undeclared mode: C"),
                           ("out-of-range-phase", "from_phase 2 is out of range"),
                           ("undeclared-initial-mode", "undeclared mode: Z")):
        _refused((EXAMPLES / f"{name}.json").read_bytes(), resources, fragment)
    two: dict[str, list[Json]] = {"A": [_phase([[]]), _phase([[]])], "B": [_phase([[]])]}
    invalid: tuple[tuple[dict[str, list[Json]], list[Json], list[Json], str], ...] = (
        (two, ["A"], [_edge("A", 0, "B", 1)], "to_phase 1 is out of range"),
        (two, ["A"], [_edge("A", -1, "B", 0)], "at least 0"),
        (two, ["A"], [_edge("A", True, "B", 0)], "integer"),
        (two, ["A"], [_edge("A", 1, "A", 0)], "no-op transition"),
        (two, ["A"], [_edge("A", 0, "A", 1)], "no-op transition"),
        ({"A": [_phase([[]])]}, ["A"], [_edge("A", 0, "A", 0)], "no-op transition"),
        (two, ["A"], [_edge("A", 0, "B", 0), _edge("A", 0, "B", 0)], "duplicate transition"),
        (two, ["A"], [], "reaches declared mode(s): B"),
        (two, ["A", "A"], [_edge("A", 0, "B", 0)], "duplicate initial"),
        (two, [], [_edge("A", 0, "B", 0)], "nonempty"),
        (two, ["A"], [{**_object(_edge("A", 0, "B", 0)), "guard": True}], "exactly"),
        (two, ["A"], [{"from": "A", "to": "B", "to_phase": 0}], "exactly"),
        ({"A": []}, ["A"], [], "nonempty"),
        ({"9A": [_phase([[]])]}, ["9A"], [], "identifier"),
    )
    for modes, initial, transitions, fragment in invalid:
        _refused(_encode(_declaration(modes, initial, transitions)), resources, fragment)
    declaration = _declaration({"A": [_phase([[]])]}, ["A"], [])
    _refused(_encode({**declaration, "mode": "periodic"}), resources, "exactly")
    _refused(_encode({key: value for key, value in declaration.items() if key != "transitions"}),
             resources, "exactly")
    _refused(_encode({**declaration, "modes": {}}), resources, "nonempty object")
    _refused(_encode({**declaration, "modes": {"A": {"phases": [_phase([[]])], "power": "ON"}}}),
             resources, "exactly")
    _refused(_encode({**declaration, "resources_sha256": "0" * 64}), resources, "does not match")
    _refused(_encode({**declaration, "schema": "phase-schedule-v3"}), resources, "unsupported")
    _refused(_encode({key: value for key, value in declaration.items() if key != "schema"}),
             resources, "no schema")
    _refused(_encode([]), resources, "no schema")
    _refused(_encode(declaration).replace(b'"initial"', b'"initial": ["A"], "initial"'),
             resources, "duplicate JSON key")
    _refused(_encode(declaration).replace(b'"grant": 1', b'"grant": 1.0'), resources,
             "floating-point")
    v1: dict[str, Json] = {"schema": "phase-schedule-v1", "name": "synthetic-v1",
                           "mode": "periodic",
                           "resources_sha256": hashlib.sha256(resources).hexdigest(),
                           "phases": [_phase([[]])]}
    extras: tuple[dict[str, Json], ...] = ({"modes": {}}, {"transitions": []}, {"initial": ["A"]})
    for extra in extras:
        _refused(_encode({**v1, **extra}), resources, "exactly")
    ensure(isinstance(read(_encode(v1), resources), Extraction),
           "a v1 declaration must still read through its own reader")


def _arrival_blocked() -> None:
    result = check(_example("arrival-blocked").contract)
    ensure(not result.zero_wait and result.reason == "arrival-blocked"
           and result.failure == ("B", 0, (1, 0, 0), ())
           and result.trace == ((), ((0, 2, 0),), ((0, 1, 0),))
           and result.trace_modes == (("A", 0), ("A", 1), ("B", 0)),
           "mode A's final-phase write must survive the switch and block mode B's first phase")
    ensure(result.mode_states == {"A": 3, "B": 3} and result.states == 6
           and result.transitions_taken == (0,) and result.drain is None,
           "the product must count each mode's states and the switch it generated")
    completion = check_completion(_example("arrival-blocked").contract)
    ensure(completion.ordered is None and completion.reason == "arrival-blocked"
           and completion.failure is not None and completion.failure.mode == "B",
           "the completion product must attribute the same failure to mode B")


def _refresh_overlap() -> None:
    result = check(_example("refresh-overlap").contract)
    ensure(not result.zero_wait and result.reason == "refresh-overlap"
           and result.failure == ("B", 0, (1, 0, 0), ())
           and result.trace == ((), ((0, 2, 0),)) and result.trace_modes == (("A", 0), ("A", 1)),
           "mode B's refresh must meet the bank mode A's write still occupies")


def _path_blocked() -> None:
    result = check(_example("path-blocked").contract)
    ensure(not result.zero_wait and result.reason == "path-blocked"
           and result.failure == ("B", 0, (0, 0, 0), ((1, 1, 1, 0),))
           and result.trace_modes == (("A", 0), ("A", 1)),
           "a request in flight across the switch must find mode B's refresh holding its bank")


def _order_inverted() -> None:
    result = check(_example("order-inverted").contract)
    ensure(not result.zero_wait and result.reason == "order-inverted"
           and result.failure == ("B", 0, (0, 0, 0), ((2, 2, 1, 0),))
           and result.trace == ((), ((2, 1, 0),), ((0, 1, 0),))
           and result.trace_modes == (("A", 0), ("A", 1), ("B", 0)),
           "mode B's near request must invert the order of mode A's request still in flight")
    # Both requests issued in mode A over unequal paths: the inversion is decided at
    # the flights' arrival, which every mode sees alike, and the continuation is
    # dequeued before the switch successor, so the failure belongs to mode A.
    both = _declaration({"A": [_phase([[]]), _phase([[_request("sram2"), _request("sram1")]], 2)],
                         "B": [_phase([[]]), _phase([[]])]}, ["A"], [_edge("A", 1, "B", 0)])
    literal = check(_example_of(both).contract)
    ensure(not literal.zero_wait and literal.reason == "order-inverted"
           and literal.failure is not None and literal.failure[0] == "A"
           and literal.transitions_taken == (0,),
           "an inversion between two flights issued in one mode is that mode's continuation's")


def _example_of(declaration: dict[str, Json]) -> ModeExtraction:
    extraction = read(_encode(declaration), _resources())
    if not isinstance(extraction, ModeExtraction):
        raise TypeError("declaration did not read as v2")
    return extraction


def _closed_companion() -> None:
    contract = _example("closed-companion").contract
    result = check(contract)
    ensure(result.zero_wait and result.transitions_taken == (0, 1) and result.drain == 0
           and result.mode_states == {"A": 3, "B": 2} and result.states == 5
           and result.trace == () and result.trace_modes == () and result.failure is None,
           "moving the switch point past the carried write must close with every transition taken")
    completion = check_completion(contract)
    ensure(completion.ordered is True and completion.drain_status == "finite"
           and completion.quiescent_drain == 1 and completion.transitions_taken == (0, 1)
           and completion.mode_states == {"A": 3, "B": 2},
           "the closed product's drain is the maximum over both modes' boundaries")
    ensure(check(_example("arrival-blocked").contract).transitions_taken == (0,),
           "the refuted case takes its one transition before failing")


def _single_mode() -> None:
    extraction = _example("single-mode")
    (table,) = extraction.contract.modes.values()
    declaration = _object(cast("Json", json.loads((EXAMPLES / "single-mode.json").read_bytes())))
    phases = _object(_object(declaration["modes"])["only"])["phases"]
    v1 = extract(_encode({"schema": "phase-schedule-v1", "name": declaration["name"],
                          "mode": "periodic", "resources_sha256": declaration["resources_sha256"],
                          "phases": phases}), _resources())
    ensure(phase_modes.single_mode(extraction.contract) == table == v1.contract
           and emitted_bytes(extraction.contract) == contract_bytes(v1.contract),
           "a single-mode declaration must emit the v1 contract byte for byte")
    _projection_equal(extraction.contract, v1.contract, "single-mode")
    ensure(extraction.bank_names == v1.bank_names and extraction.hart_names == v1.hart_names
           and extraction.operation_names == v1.operation_names
           and [(e.phase, e.alternative, e.requests, e.grant) for e in extraction.injection_excesses]
           == [(e.phase, e.alternative, e.requests, e.grant) for e in v1.injection_excesses],
           "name tables and injection excesses must match the v1 extraction")
    excess = _declaration({"only": [_phase([[_request(), _request("sram1")]], grant=1)]}, ["only"], [])
    over = _example_of(excess)
    ensure(len(over.injection_excesses) == 1 and over.injection_excesses[0].mode == "only"
           and over.injection_excesses[0].requests == 2,
           "each injection excess names its mode")
    with tempfile.TemporaryDirectory() as tmp:
        v1_path = Path(tmp) / "v1.json"
        v1_path.write_bytes(_encode({"schema": "phase-schedule-v1", "name": declaration["name"],
                                     "mode": "periodic",
                                     "resources_sha256": declaration["resources_sha256"],
                                     "phases": phases}))
        v1_out, v2_out = Path(tmp) / "v1-contract.json", Path(tmp) / "v2-contract.json"
        v1_code, v1_report = _cli(cli.main, [str(v1_path), str(EXAMPLES / "resources.json"),
                                             "--output-contract", str(v1_out)])
        v2_code, v2_report = _cli(cli.main, [str(EXAMPLES / "single-mode.json"),
                                             str(EXAMPLES / "resources.json"),
                                             "--output-contract", str(v2_out)])
        ensure(v1_code == v2_code == 0 and v1_out.read_bytes() == v2_out.read_bytes()
               and v1_report["contract_sha256"] == v2_report["contract_sha256"]
               and v1_report["contract"] == v2_report["contract"]
               and v1_report["scope"] == v2_report["scope"] == "declared-single-mode-periodic-schedule",
               "--output-contract must write identical bytes for the v1 and single-mode v2 twins")
        ensure(v1_report["schema"] == "phase-schedule-v1" and v2_report["schema"] == "phase-schedule-v2"
               and "trace_modes" not in _object(v1_report["result"])
               and _object(v2_report["result"])["trace_modes"] == []
               and _object(v2_report["result"])["mode_states"] == {"only": 3}
               and _object(v2_report["result"])["transitions_taken"] == [],
               "the v1 receipt is unaffected and the v2 receipt carries the mode fields")


def _projection_equal(wrapped: ModeContract, contract: Contract, name: str) -> None:
    (mode,) = wrapped.initial
    base = phase_service.check(contract)
    product = check(wrapped)
    ensure((base.zero_wait, base.states, base.trace, base.reason, base.drain)
           == (product.zero_wait, product.states, product.trace, product.reason, product.drain),
           f"{name}: the product diverged from phase_service on a v1 field")
    ensure((base.failure is None and product.failure is None)
           or (product.failure is not None and product.failure[0] == mode
               and product.failure[1:] == base.failure),
           f"{name}: the product failure differs from phase_service beyond the mode")
    ensure(product.trace_modes == tuple((mode, step) for step in _phases_of(base.trace, contract))
           and product.mode_states == {mode: base.states} and product.transitions_taken == (),
           f"{name}: the single-mode projection's mode fields are wrong")
    base_completion = phase_completion.check(contract)
    completion = check_completion(wrapped)
    ensure((base_completion.ordered, base_completion.states, base_completion.trace,
            base_completion.reason, base_completion.quiescent_drain,
            base_completion.drain_status, base_completion.drain_cycles)
           == (completion.ordered, completion.states, completion.trace, completion.reason,
               completion.quiescent_drain, completion.drain_status, completion.drain_cycles),
           f"{name}: the completion product diverged from phase_completion on a v1 field")
    for theirs, ours in ((base_completion.failure, completion.failure),
                         (base_completion.drain_failure, completion.drain_failure)):
        ensure((theirs is None and ours is None)
               or (theirs is not None and ours is not None and ours.mode == mode
                   and (ours.phase, ours.maintenance, ours.operations)
                   == (theirs.phase, theirs.maintenance, theirs.operations)),
               f"{name}: a completion failure state differs beyond the mode")
    ensure(completion.mode_states == {mode: base_completion.states}
           and completion.transitions_taken == ()
           and completion.trace_modes
           == tuple((mode, step) for step in _phases_of(base_completion.trace, contract)),
           f"{name}: the completion projection's mode fields are wrong")
    ensure(emitted_bytes(wrapped) == contract_bytes(contract),
           f"{name}: the wrapped table must emit the v1 bytes")


def _phases_of(trace: tuple[tuple[tuple[int, ...], ...], ...], contract: Contract) -> list[int]:
    return [step % len(contract.grants) for step in range(len(trace))]


def _projection() -> None:
    compared = 0
    for folder in ("closed", "refuted"):
        for path in sorted((PHASE_SERVICE / folder).glob("*.json")):
            _projection_equal(_wrap(service_cli.load_contract(path)), service_cli.load_contract(path),
                              f"{folder}/{path.name}")
            compared += 1
    for name, contract in scenarios().items():
        _projection_equal(_wrap(contract, name), contract, name)
        compared += 1
    ensure(compared >= 14 + len(scenarios()), "the projection compared too few fixtures")
    # A seeded second initial mode with an identical table doubles the product and
    # nothing else; both copies close or fail alike.
    frame_wrap = scenarios()["frame-wrap"]
    twin = ModeContract(("x", "y"), {"x": frame_wrap, "y": frame_wrap})
    result = check(twin)
    ensure(not result.zero_wait and result.failure is not None and result.failure[0] == "x"
           and result.mode_states["y"] >= 1,
           "initial modes seed in declared order and the earliest failure is reported")


def _completion_inversion() -> None:
    contract = _example("completion-inversion").contract
    acceptance = check(contract)
    ensure(acceptance.zero_wait and acceptance.transitions_taken == (0,) and acceptance.drain == 2,
           "the completion witness must close the acceptance product")
    result = check_completion(contract)
    ensure(result.ordered is False and result.reason == "completion-order-inverted"
           and result.failure is not None and result.failure.mode == "B"
           and result.failure.phase == 1 and result.quiescent_drain is None
           and result.trace == (((2, 2, 0),), ((1, 1, 0),), ())
           and result.trace_modes == (("A", 0), ("B", 0), ("B", 1)),
           "one hart's operations issued in different modes must keep completion order")


def _drain_blocked() -> None:
    result = check_completion(_example("drain-blocked").contract)
    ensure(result.ordered is None and result.drain_status == "blocked"
           and result.reason == "drain-path-blocked" and result.drain_cycles == 1
           and result.failure is not None and result.failure.mode == "B"
           and result.failure.phase == 0 and result.drain_failure is not None
           and result.drain_failure.mode == "B" and result.drain_failure.phase == 1
           and result.quiescent_drain is None and result.trace_modes == (("A", 0), ("A", 1)),
           "a drain from mode B's boundary blocked by mode B's refresh names mode B")
    # The same flight drains in mode A's continuation, so the block is the target's.
    ensure(check_completion(_wrap(_example("drain-blocked").contract.modes["A"], "A")).drain_status
           == "finite", "mode A alone drains the flight")


def _cli_receipts() -> None:
    resources = EXAMPLES / "resources.json"
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "mode-contract.json"
        code, report = _cli(cli.main, [str(EXAMPLES / "closed-companion.json"), str(resources),
                                       "--completion", "--output-contract", str(output)])
        contract = _example("closed-companion").contract
        ensure(code == 0 and report["scope"] == "declared-mode-product-periodic-schedule"
               and report["schema"] == "phase-schedule-v2"
               and report["target_comparison"] == "open"
               and output.read_bytes() == mode_contract_bytes(contract)
               and report["contract_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
               and set(_object(report["contract"])) == {"initial", "modes", "transitions"}
               and _object(report["contract"])["transitions"]
               == [t.to_json() for t in contract.transitions]
               and _object(report["completion"])["drain_status"] == "finite",
               "a multi-mode receipt binds the mode-contract bytes and carries completion")
        sources = _object(report["sources_sha256"])
        for name in ("tools/vos/phase_modes.py", "docs/implementation/phase-service/mode-contract.md",
                     "tools/vos/phase_completion.py", "tools/vos/phase_schedule.py"):
            ensure(sources[name] == hashlib.sha256((TOOLS.parent / name).read_bytes()).hexdigest(),
                   f"receipt must bind {name}")
        code, refused = _cli(service_cli.main, ["--contract", str(output)])
        ensure(code == 2 and "error" in refused and "result" not in refused,
               "phase-service --contract must keep refusing the mode contract by its modes field")
        for name, extra, expected in (("arrival-blocked", [], 1), ("completion-inversion", [], 0),
                                      ("completion-inversion", ["--completion"], 1),
                                      ("drain-blocked", ["--completion"], 1),
                                      ("undeclared-transition-mode", [], 2)):
            code, report = _cli(cli.main, [str(EXAMPLES / f"{name}.json"), str(resources), *extra])
            ensure(code == expected and report["target_comparison"] == "open",
                   f"{name} with {extra} must exit {expected}")
        for text, fragment in ((b'{"name": "x"}', "no schema"),
                               (b'{"schema": "phase-schedule-v9"}', "unsupported"),
                               (b'{"schema": 3}', "unsupported"), (b"[]", "no schema")):
            path = Path(tmp) / "bad.json"
            path.write_bytes(text)
            code, report = _cli(cli.main, [str(path), str(resources)])
            ensure(code == 2 and fragment in str(report["error"]) and "result" not in report,
                   f"{text!r} must be malformed input at exit 2")
        v1 = PHASE_SERVICE / "schedule-examples"
        code, report = _cli(cli.main, [str(v1 / "closed-companion.json"), str(v1 / "resources.json"),
                                       "--completion"])
        ensure(code == 0 and report["schema"] == "phase-schedule-v1"
               and _object(report["completion"])["drain_status"] == "finite"
               and "tools/vos/phase_modes.py" not in _object(report["sources_sha256"])
               and "trace_modes" not in _object(report["result"]),
               "a v1 declaration gains --completion and nothing else")
        text = StringIO()
        with redirect_stdout(text):
            code = cli.main([str(EXAMPLES / "closed-companion.json"), str(resources), "--completion"])
        ensure(code == 0 and "transitions_taken=(0, 1)" in text.getvalue()
               and "drain_status=finite" in text.getvalue(), "the text report names the modes")


def _evaluate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        shutil.copy(EXAMPLES / "resources.json", folder / "resources.json")
        for name, scope, verdict, code_expected in (
                ("closed-companion", "declared-mode-product-zero-wait-comparison", "favorable", 0),
                ("single-mode", "declared-single-mode-zero-wait-comparison", "favorable", 0),
                ("arrival-blocked", "declared-mode-product-zero-wait-comparison", "refuted", 1),
                ("completion-inversion", "declared-mode-product-zero-wait-comparison", "refuted", 1)):
            schedule = folder / f"{name}.json"
            shutil.copy(EXAMPLES / f"{name}.json", schedule)
            costs = folder / f"{name}-costs.json"
            data = _object(cast("Json", json.loads(COST_EXAMPLE.read_bytes())))
            data["schedule"] = {"id": _example(name).name, "path": schedule.name,
                                "sha256": hashlib.sha256(schedule.read_bytes()).hexdigest()}
            costs.write_bytes(_encode(data))
            code, report = _cli(phase_evaluate.main, [str(schedule), str(folder / "resources.json"),
                                                      "--costs", str(costs)])
            ensure(code == code_expected and report["branch_verdict"] == verdict
                   and report["scope"] == scope and report["target_comparison"] == "open",
                   f"{name}: the join must decide {verdict} under scope {scope}")
            because = _strings(report["open_because"])
            ensure("non-empty initial states" in because
                   and "initial states and mode transitions" not in because
                   and "qualified occupancy and timing (R-15-247m)" in because
                   and "qualified memory and timing" not in because
                   and "qualified second-class service and timer-residency bounds "
                       "(R-15-247m, R-07-040)" in because
                   and any("mode-transition budget" in reason for reason in because),
                   f"{name}: open_because must carry the contract's mode terms")
            ensure(any("mode-transition budget" in term
                       for term in _strings(report["terms_not_carried"])),
                   f"{name}: the join must name the uncarried mode-transition budget")
            ensure(_object(report["sources_sha256"])["tools/vos/phase_modes.py"]
                   == hashlib.sha256((TOOLS / "vos" / "phase_modes.py").read_bytes()).hexdigest(),
                   f"{name}: the join must bind the mode module")
            if name == "closed-companion":
                ensure(_object(report["completion"])["quiescent_drain"] == 1
                       and _object(report["inputs_sha256"])["contract"]
                       == hashlib.sha256(mode_contract_bytes(_example(name).contract)).hexdigest(),
                       "the join binds the product's drain bound and the mode-contract bytes")
        v1 = PHASE_SERVICE / "schedule-examples"
        code, report = _cli(phase_evaluate.main, [str(v1 / "closed-companion.json"),
                                                  str(v1 / "resources.json"),
                                                  "--costs", str(v1 / "costs.json")])
        ensure(code == 0 and report["scope"] == "declared-single-mode-zero-wait-comparison"
               and report["schema"] == "phase-schedule-v1"
               and "tools/vos/phase_modes.py" not in _object(report["sources_sha256"]),
               "a v1 join keeps its scope and binds no mode module")


def _checker_validation() -> None:
    table = scenarios()["restricted-arrivals"]
    other = Contract((1,), (((),),), banks=2)
    for contract in (ModeContract((), {"a": table}), ModeContract(("b",), {"a": table}),
                     ModeContract(("a",), {}), ModeContract(("a",), {"a": table, "b": other}),
                     ModeContract(("a",), {"a": table, "b": table}),
                     ModeContract(("a",), {"a": table}, (Transition("a", 2, "a", 0),)),
                     ModeContract(("a",), {"a": table}, (Transition("a", 0, "a", 1),))):
        try:
            check(contract)
        except ValueError:
            try:
                check_completion(contract)
            except ValueError:
                continue
        raise AssertionError(f"invalid mode contract accepted: {contract}")
    ensure(asdict(check(_wrap(table)))["mode_states"] == {"only": 3},
           "a result serializes its mode counts as an object")


def cases() -> list[Case]:
    return [Case("refusals", _refusals), Case("arrival-blocked", _arrival_blocked),
            Case("refresh-overlap", _refresh_overlap), Case("path-blocked", _path_blocked),
            Case("order-inverted", _order_inverted), Case("closed-companion", _closed_companion),
            Case("single-mode", _single_mode), Case("projection", _projection),
            Case("completion-inversion", _completion_inversion),
            Case("drain-blocked", _drain_blocked), Case("cli-receipts", _cli_receipts),
            Case("evaluate", _evaluate), Case("checker-validation", _checker_validation)]
