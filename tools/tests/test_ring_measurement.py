# SPDX-License-Identifier: Apache-2.0
"""Synthetic finite-capture accounting, boundary and identity refusal controls."""

import copy
import hashlib
import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus
from vos.cli import ring as ring_owner
from vos.cli import ring_measurement as cli
from vos.ring_measurement import COST_FIELDS, REQUEST_BOUNDS, Analysis, analyze


def _blob(value: object) -> bytes:
    return json.dumps(value).encode("utf-8")


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fixture(root: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root or corpus.find_root()
    world = ring_owner.declaration(root)["worlds"][0]
    identity = {"roster_revision": "a" * 40, "image_sha256": "b" * 64,
                "composition_sha256": "c" * 64}
    request = {"operation": world["operations"][0]["name"],
               "validation_cost": 1, "device_service_bound": 2,
               "cancellation_cleanup_cost": 3, "completion_publication_cost": 4,
               "payload_bytes": 1, "segment_count": 1, "notifications": 1}
    mixed = {**request, "operation": world["operations"][1]["name"],
             **dict.fromkeys(COST_FIELDS, 1)}
    capture = {"schema_version": 1, "complete": True, "identity": identity,
               "window": {"start_tick": 0, "end_tick": 100, "tick_hz": 7},
               "declaration_sha256": _hash((root / ring_owner.DECLARATION).read_bytes()),
               "cost_unit": "declaration_units",
               "rings": [{"ring_id": "fixture-ring", "world": world["world"],
                          "activations": [
                              {"tick": 10, "queue_high_water": 5, "notifications": 3,
                               "activation_overhead_cost": 5, "requests": [request, mixed]},
                              {"tick": 30, "queue_high_water": 0, "notifications": 1,
                               "activation_overhead_cost": 2, "requests": []}]}]}
    expected = {**identity, "capture_sha256": _hash(_blob(capture))}
    return capture, expected


def _run(capture: dict[str, Any], expected: dict[str, Any], root: Path | None = None) -> Analysis:
    encoded = _blob(capture)
    return analyze(encoded, _blob({**expected, "capture_sha256": _hash(encoded)}),
                   root or corpus.find_root())


def _first(capture: dict[str, Any]) -> dict[str, Any]:
    return capture["rings"][0]["activations"][0]


def _request(capture: dict[str, Any]) -> dict[str, Any]:
    return _first(capture)["requests"][0]


def _refused(capture: dict[str, Any], expected: dict[str, Any], root: Path | None = None) -> None:
    try:
        _run(capture, expected, root)
    except ValueError:
        return
    raise AssertionError("malformed capture or identity accepted")


def _hand_accounting() -> None:
    capture, expected = _fixture()
    result = _run(capture, expected)
    ring = result.rings[0]
    ensure(not result.findings and result.verdict == "within_limits", "valid synthetic capture")
    # Independent arithmetic: (1+2+3+4) + (1+1+1+1) + 5 = 19, with overhead once.
    ensure(ring.activations[0].cost == 19, "mixed request accounting")
    ensure(ring.activations[1].cost == 2, "empty spurious drain charges overhead")
    ensure(ring.request_count == 2 and ring.batch_high_water == 2, "requests are counted individually")
    ensure(ring.queue_high_water == 5, "producer-provided queue maximum")
    ensure(ring.observed_notifications == 4 and ring.generated_notifications == 2,
           "spurious and coalesced observed notifications differ from generated counts")
    rate = ring.observed_notifications_per_second
    if rate is None:
        raise AssertionError("observed interval has a measurable duration")
    ensure((rate.numerator, rate.denominator) == (14, 15),
           "four observed hints times 7 ticks/second divided by 30 observed ticks")
    ensure(ring.observed_interval_ticks == 30, "unmeasured tail cannot dilute cadence")
    ensure(ring.activation_gaps_ticks == (20,) and ring.unmeasured_tail_ticks == 70,
           "finite observation gaps and unmeasured tail stay explicit")
    ensure(ring.activations[0].remaining_budget == ring.slot_budget - 19, "slot subtraction")
    ensure(result.milestone_acceptance == "open" and "host" in result.scope, "fixture cannot qualify target")
    ensure(result.capture_sha256 == _hash(_blob(capture)), "actual raw capture bytes")
    only = _first(capture)
    only["tick"] = capture["window"]["start_tick"]
    capture["rings"][0]["activations"] = [only]
    boundary = _run(capture, expected).rings[0]
    ensure(boundary.observed_interval_ticks == 0
           and boundary.observed_notifications_per_second is None,
           "a boundary-only observation supplies no elapsed-time rate")


def _declared_boundaries() -> None:
    capture, expected = _fixture()
    world = ring_owner.declaration(corpus.find_root())["worlds"][0]
    limits = dict(zip(world["operation_record_fields"], world["operations"][0]["record"], strict=True))
    base = copy.deepcopy(capture)
    first = _first(base)
    first["requests"] = [_request(base)]
    request = _request(base)
    for field, declared in REQUEST_BOUNDS.items():
        request[field] = limits[declared]
    first["queue_high_water"] = world["ring"]["capacity"]
    first["activation_overhead_cost"] = world["ring"]["slot_budget"] - sum(request[f] for f in COST_FIELDS)
    ensure(not _run(base, expected).findings, "all per-request limits and slot equality pass")
    for field in REQUEST_BOUNDS:
        changed = copy.deepcopy(base)
        _request(changed)[field] += 1
        findings = _run(changed, expected).findings
        ensure(any(f"/requests/0/{field}:" in finding for finding in findings),
               f"one-past per-operation {field} is diagnosed")
    for field in ("queue_high_water", "activation_overhead_cost"):
        changed = copy.deepcopy(base)
        _first(changed)[field] += 1
        ensure(bool(_run(changed, expected).findings), f"one-past {field} fails")
    # Zero-cost observations isolate batch equality from the separate slot test.
    first["activation_overhead_cost"] = 0
    for field in REQUEST_BOUNDS:
        request[field] = 0
    first["requests"] = [copy.deepcopy(request) for _ in range(world["ring"]["max_batch_size"])]
    ensure(not _run(base, expected).findings, "declaration's batch equality passes")
    first["requests"].append(copy.deepcopy(request))
    ensure(any("/batch_size:" in finding for finding in _run(base, expected).findings),
           "batch one-past fails independently")
    first["requests"] = []
    first["activation_overhead_cost"] = world["ring"]["slot_budget"] + 1
    first["notifications"] = 10000
    findings = _run(base, expected).findings
    ensure(len(findings) == 1 and "/activation_cost:" in findings[0],
           "empty overhead exceeds slot; observed spurious hint count is uncapped")


def _declaration_is_the_owner() -> None:
    declaration = json.loads((corpus.find_root() / ring_owner.DECLARATION).read_text(encoding="utf-8"))
    world = declaration["worlds"][0]
    field = world["operation_record_fields"].index("max_requests_drained")
    world["operations"][0]["record"][field] = 1
    with sandbox_tree({ring_owner.DECLARATION: json.dumps(declaration)}) as root:
        capture, expected = _fixture(root)
        result = _run(capture, expected, root)
        ensure(len(result.findings) == 1 and "/max_requests_drained:" in result.findings[0],
               "mixed batch obeys each represented op's changed drain limit")
        _first(capture)["requests"] = [_request(capture)]
        ensure(not _run(capture, expected, root).findings, "changed drain equality passes")
        for mutation in ("duplicate_operation", "duplicate_field", "extra_field"):
            changed = copy.deepcopy(declaration)
            member = changed["worlds"][0]
            if mutation == "duplicate_operation":
                member["operations"].append(copy.deepcopy(member["operations"][0]))
            elif mutation == "duplicate_field":
                member["operation_record_fields"][0] = member["operation_record_fields"][1]
            else:
                member["operation_record_fields"].append("unaccounted_cost")
                for operation in member["operations"]:
                    operation["record"].append(1)
            path = root / ring_owner.DECLARATION
            path.write_text(json.dumps(changed), encoding="utf-8", newline="")
            capture["declaration_sha256"] = _hash(path.read_bytes())
            _refused(capture, expected, root)


def _identities_and_chronology() -> None:
    base, expected = _fixture()
    for field in ("roster_revision", "image_sha256", "composition_sha256"):
        changed = copy.deepcopy(base)
        changed["identity"][field] = "d" * len(changed["identity"][field])
        _refused(changed, expected)
    for value in ("", "g" * 64, "a" * 39):
        changed = copy.deepcopy(base)
        changed["identity"]["roster_revision"] = value
        _refused(changed, expected)
    changed = copy.deepcopy(base)
    changed["declaration_sha256"] = "d" * 64
    _refused(changed, expected)
    for capture_blob in (_blob(base) + b"\n", _blob(base).replace(b'"tick": 10', b'"tick": 11')):
        try:
            analyze(capture_blob, _blob(expected), corpus.find_root())
        except ValueError:
            continue
        raise AssertionError("changed raw capture bytes accepted against stale hash")
    for tick in (-1, 30, 31, 100):
        changed = copy.deepcopy(base)
        _first(changed)["tick"] = tick
        _refused(changed, expected)
    for start, end, frequency in ((100, 100, 1), (2, 1, 1), (0, 100, 0), (20, 100, 1)):
        changed = copy.deepcopy(base)
        changed["window"] = {"start_tick": start, "end_tick": end, "tick_hz": frequency}
        _refused(changed, expected)
    _first(base)["tick"] = 0
    ensure(not _run(base, expected).findings, "activation at inclusive start is allowed")


def _ambiguous_declaration_is_refused() -> None:
    declaration = json.loads((corpus.find_root() / ring_owner.DECLARATION).read_text(encoding="utf-8"))
    world = declaration["worlds"][0]
    budget = world["ring"]["slot_budget"]
    original = json.dumps(declaration)
    for key in ('"slot_budget"', '"slot_budg\\u0065t"'):
        ambiguous = original.replace(f'"slot_budget": {budget}',
                                     f'"slot_budget": 0, {key}: {budget}', 1)
        with sandbox_tree({ring_owner.DECLARATION: ambiguous}) as root:
            capture, expected = _fixture(root)
            # The first budget rejects the fixture; a last-key-wins reader accepts it.
            ensure(_first(capture)["activation_overhead_cost"] > 0,
                   "zero budget cannot accommodate the observed overhead")
            try:
                _run(capture, expected, root)
            except ValueError as error:
                ensure("duplicate JSON key: slot_budget" in str(error),
                       "refuse the ambiguous declaration before accounting")
            else:
                raise AssertionError("duplicate declaration budget silently selected its last value")


def _closed_shapes_and_numbers() -> None:
    base, expected = _fixture()
    for location in ("capture", "window", "ring", "activation", "request", "identity"):
        for mutation in ("extra", "missing"):
            changed = copy.deepcopy(base)
            objects = {"capture": changed, "window": changed["window"], "ring": changed["rings"][0],
                       "activation": _first(changed), "request": _request(changed),
                       "identity": changed["identity"]}
            row = objects[location]
            if mutation == "extra":
                row["unexpected"] = 0
            else:
                del row[next(iter(row))]
            _refused(changed, expected)
    for value in (True, False, 1.0, -1, "1", None):
        for field in REQUEST_BOUNDS:
            changed = copy.deepcopy(base)
            _request(changed)[field] = value
            _refused(changed, expected)
        for field in ("tick", "queue_high_water", "notifications", "activation_overhead_cost"):
            changed = copy.deepcopy(base)
            _first(changed)[field] = value
            _refused(changed, expected)
    mutations: list[tuple[str, object]] = [("complete", False), ("complete", 1),
                                         ("schema_version", True), ("schema_version", 2),
                                         ("cost_unit", "cycles"), ("rings", [])]
    for field, value in mutations:
        changed = copy.deepcopy(base)
        changed[field] = value
        _refused(changed, expected)
    for world in ("unknown_world", ""):
        changed = copy.deepcopy(base)
        changed["rings"][0]["world"] = world
        _refused(changed, expected)
    changed = copy.deepcopy(base)
    _request(changed)["operation"] = "unknown_operation"
    _refused(changed, expected)
    changed = copy.deepcopy(base)
    changed["rings"].append(copy.deepcopy(changed["rings"][0]))
    _refused(changed, expected)
    changed = copy.deepcopy(base)
    changed["rings"][0]["activations"] = []
    _refused(changed, expected)
    for raw in (b'{"schema_version":1,"schema_version":1}', b'{"x":NaN}',
                b'{"x":Infinity}', b'{"x":1.0}', b"\xff", b"{"):
        try:
            analyze(raw, _blob({**expected, "capture_sha256": _hash(raw)}), corpus.find_root())
        except ValueError:
            continue
        raise AssertionError("malformed JSON accepted")


def _cli_evidence() -> None:
    capture, expected = _fixture()
    with tempfile.TemporaryDirectory(prefix="vos-ring-measurement-") as directory:
        root = Path(directory)
        capture_path, expected_path = root / "capture.json", root / "expected.json"
        for verdict, exit_code in (("within_limits", 0), ("exceeds_limits", 1), ("malformed", 2)):
            if exit_code == 1:
                _first(capture)["activation_overhead_cost"] = 10**9
            if exit_code == 2:
                capture["complete"] = False
            capture_path.write_bytes(_blob(capture))
            expected_path.write_bytes(_blob({**expected, "capture_sha256": _hash(capture_path.read_bytes())}))
            for flags in ([], ["--json"]):
                output = StringIO()
                with redirect_stdout(output):
                    code = cli.main([str(capture_path), "--expected-identity", str(expected_path), *flags])
                ensure(code == exit_code, f"CLI exit for {verdict}")
                if flags:
                    report = json.loads(output.getvalue())
                    ensure(report["verdict"] == verdict, "machine-readable verdict")
                    ensure(report["milestone_acceptance"] == "open", "no target acceptance")
                    if exit_code != 2:
                        ensure(report["capture_sha256"] == _hash(capture_path.read_bytes()), "byte identity")
                        ensure(len(report["sources_sha256"]) == 4, "source and contract identities")
        with redirect_stdout(StringIO()):
            ensure(cli.main([str(root / "missing"), "--expected-identity", str(expected_path)]) == 2,
                   "missing capture is malformed input")


def cases() -> list[Case]:
    return [Case("hand-computed-mixed-and-empty-accounting", _hand_accounting),
            Case("declared-boundary-equality-and-one-past", _declared_boundaries),
            Case("declaration-driven-drain-and-schema", _declaration_is_the_owner),
            Case("ambiguous-declaration-is-refused", _ambiguous_declaration_is_refused),
            Case("identity-bindings-and-chronology", _identities_and_chronology),
            Case("closed-shapes-and-integer-domains", _closed_shapes_and_numbers),
            Case("cli-scope-evidence-and-exits", _cli_evidence)]
