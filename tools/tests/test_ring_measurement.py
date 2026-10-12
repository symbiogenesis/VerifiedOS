# SPDX-License-Identifier: Apache-2.0
"""Synthetic finite-capture accounting, boundary and identity refusal controls."""

import copy
import hashlib
import json
import sys
import tempfile
from collections.abc import Callable
from contextlib import redirect_stdout
from io import BytesIO, StringIO, TextIOWrapper
from pathlib import Path
from typing import Any
from unittest.mock import patch

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


def _two_world_fixture(root: Path, *, scale: int = 1, start: int = 0,
                       reverse_worlds: bool = False, reverse_rings: bool = False
                       ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    declaration = json.loads((corpus.find_root() / ring_owner.DECLARATION).read_text(encoding="utf-8"))
    worlds = declaration["worlds"]
    names = [world["world"] for world in worlds]
    operations = [operation["name"] for operation in worlds[0]["operations"][:2]]
    for index, world in enumerate(worlds):
        world["ring"].update(capacity=5 - 3 * index, max_batch_size=3 - index,
                             slot_budget=(31 - 2 * index) * scale)
        fields = world["operation_record_fields"]
        for operation, name in zip(world["operations"][:2], operations, strict=True):
            operation["name"] = name
            bounds = dict(zip(fields, operation["record"], strict=True))
            bounds.update(validation_cost=(2 + index) * scale,
                          device_service_bound=(3 + index) * scale,
                          cancellation_cleanup_cost=(4 + index) * scale,
                          completion_publication_cost=(5 + index) * scale,
                          max_payload_bytes=6 + index, max_segment_count=3 + index,
                          max_notifications=(2 + index) * scale, max_requests_drained=3 - index)
            operation["record"] = [bounds[field] for field in fields]
        # Reorder each world's fields with its values. A positional second table
        # or a record borrowed from another world must fail the checks below.
        order = list(reversed(fields)) if index == 0 else fields[3:] + fields[:3]
        for operation in world["operations"]:
            bounds = dict(zip(fields, operation["record"], strict=True))
            operation["record"] = [bounds[field] for field in order]
        world["operation_record_fields"] = order
    if reverse_worlds:
        worlds.reverse()
    (root / ring_owner.DECLARATION).write_text(json.dumps(declaration), encoding="utf-8", newline="")
    capture, expected = _fixture(root)
    capture["window"].update(start_tick=start, end_tick=start + 100)
    first = capture["rings"][0]
    first.update(ring_id="first-ring", world=names[0])
    for activation in first["activations"]:
        activation["tick"] += start
        activation["notifications"] *= scale
        activation["activation_overhead_cost"] *= scale
        for request in activation["requests"]:
            for field in (*COST_FIELDS, "notifications"):
                request[field] *= scale
    request = copy.deepcopy(first["activations"][0]["requests"][0])
    second = {"ring_id": "second-ring", "world": names[1], "activations": [
        {"tick": start + 20, "queue_high_water": 2, "notifications": 2 * scale,
         "activation_overhead_cost": 9 * scale,
         "requests": [request, {**request, "operation": operations[1]}]},
        {"tick": start + 60, "queue_high_water": 0, "notifications": 3 * scale,
         "activation_overhead_cost": 0, "requests": []}]}
    capture["rings"].append(second)
    if reverse_rings:
        capture["rings"].reverse()
    return capture, expected, declaration


def _independent_multi_world_accounting() -> None:
    # Sixteen deterministic captures cross both orderings, an integer translation
    # and charges above float precision. Their totals come from the fixed witness:
    # first (10 + 4 + 5, 2), second (10 + 10 + 9, 0), never analyzer helpers.
    with sandbox_tree({ring_owner.DECLARATION: "{}"}) as root:
        for scale in (1, 2**54 + 1):
            for start in (0, 2**54 + 1):
                for reverse_worlds in (False, True):
                    for reverse_rings in (False, True):
                        capture, expected, _ = _two_world_fixture(
                            root, scale=scale, start=start, reverse_worlds=reverse_worlds,
                            reverse_rings=reverse_rings)
                        result = _run(capture, expected, root)
                        ensure(result.verdict == "within_limits", "independent two-world witness passes")
                        summaries = {ring.ring_id: ring for ring in result.rings}
                        witnesses = (("first-ring", 5, 3, 31, 19, 2, 4, 30, 20, 14, 15),
                                     ("second-ring", 2, 2, 29, 29, 0, 5, 60, 40, 7, 12))
                        for index, (name, capacity, batch, budget, cost, empty_cost, hints,
                                    span, gap, numerator, denominator) in enumerate(witnesses):
                            ring = summaries[name]
                            ensure((ring.capacity, ring.max_batch_size, ring.slot_budget)
                                   == (capacity, batch, budget * scale), "each ring owns its world limits")
                            ensure((ring.queue_high_water, ring.batch_high_water, ring.request_count)
                                   == (capacity, 2, 2), "queue and batch maxima stay local to each ring")
                            ensure((ring.max_activation_cost, ring.activations[0].remaining_budget,
                                    ring.activations[1].cost)
                                   == (cost * scale, (budget - cost) * scale, empty_cost * scale),
                                   "per-ring charges and overhead retain exact integer arithmetic")
                            ensure((ring.observed_notifications, ring.generated_notifications)
                                   == (hints * scale, 2 * scale), "observed and generated hints stay distinct")
                            ensure((ring.observed_interval_ticks, ring.activation_gaps_ticks,
                                    ring.unmeasured_tail_ticks) == (span, (gap,), 100 - span),
                                   "cadence excludes each ring's own unmeasured tail")
                            rate = ring.observed_notifications_per_second
                            ensure(rate is not None, "positive observed interval supplies a rate")
                            if rate is not None:
                                ensure(rate.numerator * denominator
                                       == numerator * scale * rate.denominator,
                                       "exact cadence agrees with the independent rational witness")
                            for request in ring.activations[0].requests:
                                ensure(request.declared_bounds["validation_cost"] == (2 + index) * scale
                                       and request.declared_bounds["max_payload_bytes"] == 6 + index
                                       and request.declared_bounds["max_requests_drained"] == 3 - index,
                                       "same operation spelling selects the world's reordered record")


def _multi_world_limit_isolation() -> None:
    with sandbox_tree({ring_owner.DECLARATION: "{}"}) as root:
        capture, expected, declaration = _two_world_fixture(root, reverse_worlds=True, reverse_rings=True)
        base = copy.deepcopy(capture)
        for ring in base["rings"]:
            world = next(world for world in declaration["worlds"] if world["world"] == ring["world"])
            activation = ring["activations"][0]
            # Put both activations on their own exact budget before one-past tests.
            activation["activation_overhead_cost"] = world["ring"]["slot_budget"] - sum(
                request[field] for request in activation["requests"] for field in COST_FIELDS)
        ensure(not _run(base, expected, root).findings, "both worlds' exact slot budgets pass together")
        for index, ring in enumerate(base["rings"]):
            world = next(world for world in declaration["worlds"] if world["world"] == ring["world"])
            location = f"{ring['ring_id']}/activations/0"
            for field in ("queue_high_water", "activation_overhead_cost", *REQUEST_BOUNDS):
                changed = copy.deepcopy(base)
                activation = changed["rings"][index]["activations"][0]
                if field in ("queue_high_water", "activation_overhead_cost"):
                    activation[field] += 1
                    suffix = "queue_high_water" if field == "queue_high_water" else "activation_cost"
                else:
                    bounds = dict(zip(world["operation_record_fields"], world["operations"][0]["record"],
                                      strict=True))
                    activation["requests"][0][field] = bounds[REQUEST_BOUNDS[field]] + 1
                    suffix = f"requests/0/{field}"
                result = _run(changed, expected, root)
                ensure(any(f"{location}/{suffix}:" in finding for finding in result.findings),
                       f"the selected world's one-past {field} is detected")
                ensure(all(finding.startswith(location + "/") for finding in result.findings),
                       "one ring's excess cannot contaminate another ring's findings")
            changed = copy.deepcopy(base)
            activation = changed["rings"][index]["activations"][0]
            empty_request = {**activation["requests"][0], **dict.fromkeys(REQUEST_BOUNDS, 0)}
            activation["activation_overhead_cost"] = 0
            activation["requests"] = [copy.deepcopy(empty_request)
                                      for _ in range(world["ring"]["max_batch_size"])]
            ensure(not _run(changed, expected, root).findings,
                   "each world's batch equality passes independently of slot charges")
            activation["requests"].append(copy.deepcopy(empty_request))
            findings = _run(changed, expected, root).findings
            ensure(any(finding.startswith(location + "/batch_size:") for finding in findings)
                   and all(finding.startswith(location + "/") for finding in findings),
                   "each world's batch one-past fails without leaking to the other ring")
            changed_declaration = copy.deepcopy(declaration)
            changed_world = next(member for member in changed_declaration["worlds"]
                                 if member["world"] == ring["world"])
            position = changed_world["operation_record_fields"].index("max_requests_drained")
            changed_world["operations"][1]["record"][position] = 1
            path = root / ring_owner.DECLARATION
            path.write_text(json.dumps(changed_declaration), encoding="utf-8", newline="")
            changed = copy.deepcopy(base)
            changed["declaration_sha256"] = _hash(path.read_bytes())
            findings = _run(changed, expected, root).findings
            ensure(len(findings) == 1 and findings[0].startswith(location + "/")
                   and "/max_requests_drained:" in findings[0],
                   "mixed batch uses the whole batch against each world's represented operation")
            path.write_text(json.dumps(declaration), encoding="utf-8", newline="")
        changed = copy.deepcopy(base)
        first_world_only = declaration["worlds"][1]["operations"][2]["name"]
        changed["rings"][0]["activations"][0]["requests"][0]["operation"] = first_world_only
        _refused(changed, expected, root)


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


def _declaration_numeric_domains() -> None:
    declaration = json.loads((corpus.find_root() / ring_owner.DECLARATION).read_text(encoding="utf-8"))
    with sandbox_tree({ring_owner.DECLARATION: json.dumps(declaration)}) as root:
        for field in ("capacity", "max_batch_size", "slot_budget", *REQUEST_BOUNDS.values(),
                      "max_requests_drained"):
            for value in (0, -1):
                changed = copy.deepcopy(declaration)
                world = changed["worlds"][0]
                if field in ("capacity", "max_batch_size", "slot_budget"):
                    world["ring"][field] = value
                else:
                    index = world["operation_record_fields"].index(field)
                    # Leave this operation unused: a malformed declared bound must not
                    # become acceptable merely because the capture never invokes it.
                    world["operations"][1]["record"][index] = value
                (root / ring_owner.DECLARATION).write_text(json.dumps(changed),
                                                         encoding="utf-8", newline="")
                capture, expected = _fixture(root)
                for activation in capture["rings"][0]["activations"]:
                    activation["requests"] = []
                    activation["queue_high_water"] = 0
                    activation["activation_overhead_cost"] = 0
                if value == 0:
                    ensure(not _run(capture, expected, root).findings,
                           f"zero {field} is a valid comparison bound for zero activity")
                else:
                    try:
                        _run(capture, expected, root)
                    except ValueError as error:
                        ensure(field in str(error) and "nonnegative integer" in str(error),
                               f"negative declared {field} identifies its invalid domain")
                    else:
                        raise AssertionError(f"negative declared {field} was not refused")


def _declared_operation_names() -> None:
    declaration = json.loads((corpus.find_root() / ring_owner.DECLARATION).read_text(encoding="utf-8"))
    with sandbox_tree({ring_owner.DECLARATION: json.dumps(declaration)}) as root:
        capture, expected = _fixture(root)
        _first(capture)["requests"] = [_request(capture)]
        ensure(not _run(capture, expected, root).findings,
               "a valid consumed world can include an unused operation")
        for name in ("", " ", "\t\n", " unused_operation", "unused_operation "):
            changed = copy.deepcopy(declaration)
            changed["worlds"][0]["operations"][1]["name"] = name
            path = root / ring_owner.DECLARATION
            path.write_text(json.dumps(changed), encoding="utf-8", newline="")
            capture["declaration_sha256"] = _hash(path.read_bytes())
            # No captured request names this operation. Refusal must validate the
            # consumed declaration rather than rely on a failed request lookup.
            try:
                _run(capture, expected, root)
            except ValueError as error:
                ensure("operations/1/name" in str(error) and "nonempty identifier" in str(error),
                       "invalid declared identifier names its location")
            else:
                raise AssertionError("unused declared operation with an invalid name was accepted")


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


def _declaration_snapshot_owns_selected_limits() -> None:
    original = json.loads((corpus.find_root() / ring_owner.DECLARATION).read_text(encoding="utf-8"))
    changed = copy.deepcopy(original)
    changed["worlds"][0]["ring"]["slot_budget"] = 0
    read_text = Path.read_text

    def transient_reader(path: Path, text: str) -> Callable[..., str]:
        def read(file: Path, encoding: str | None = None, errors: str | None = None) -> str:
            return text if file == path else read_text(file, encoding=encoding, errors=errors)

        return read

    # Swap only the owner's text read, while both fingerprint reads see the
    # bound bytes. This models a declaration changed and restored between reads.
    for bound, transient, budget, verdict in (
            (changed, original, 0, "exceeds_limits"),
            (original, changed, original["worlds"][0]["ring"]["slot_budget"], "within_limits")):
        with sandbox_tree({ring_owner.DECLARATION: json.dumps(bound)}) as root:
            path = root / ring_owner.DECLARATION
            capture, expected = _fixture(root)
            control = _run(capture, expected, root)
            ensure(control.verdict == verdict, "the bound declaration supplies the control verdict")
            with patch.object(Path, "read_text", transient_reader(path, json.dumps(transient))):
                result = _run(capture, expected, root)
            ring = result.rings[0]
            ensure(result.verdict == verdict and ring.slot_budget == budget,
                   "selected limits must come from the exact fingerprinted declaration snapshot")
            ensure(result.declaration_sha256 == _hash(path.read_bytes()),
                   "selected limits and declaration identity describe the same bytes")
            ensure(ring.activations[0].remaining_budget == budget - 19,
                   "remaining budget uses the bound declaration, including a negative excess")
            ensure(result.findings == control.findings,
                   "a transient second read cannot hide or invent captured limit excess")


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
                        ensure(len(report["sources_sha256"]) == 5
                               and "tools/vos/jsonutil.py" in report["sources_sha256"],
                               "source and contract identities")
        with redirect_stdout(StringIO()):
            ensure(cli.main([str(root / "missing"), "--expected-identity", str(expected_path)]) == 2,
                   "missing capture is malformed input")


def _cli_refusal_evidence() -> None:
    source_names = ("tools/vos/ring_measurement.py", "tools/vos/jsonutil.py",
                    "tools/vos/cli/ring_measurement.py", "tools/vos/cli/ring.py",
                    "docs/implementation/contracts/roster-measurement.md")
    checkout = corpus.find_root()
    source_hashes = {name: _hash((checkout / name).read_bytes()) for name in source_names}
    declaration_hash = _hash((checkout / ring_owner.DECLARATION).read_bytes())
    with tempfile.TemporaryDirectory(prefix="vos-ring-refusal-evidence-") as directory:
        root = Path(directory)
        capture_path, expected_path = root / "capture.json", root / "expected.json"
        for defect in ("none", "negative-charge", "duplicate-key", "stale-identity"):
            capture, expected = _fixture()
            if defect == "negative-charge":
                _request(capture)["validation_cost"] = -1
            # Different whitespace must retain its byte identity, not a reserialization.
            capture_blob = b"\n " + _blob(capture) + b" \n"
            if defect == "duplicate-key":
                capture_blob = capture_blob.replace(b'"complete": true',
                                                    b'"complete": true, "complete": true')
            expected["capture_sha256"] = _hash(capture_blob)
            if defect == "stale-identity":
                expected["image_sha256"] = "0" * 64
            expected_blob = b"\n" + _blob(expected) + b"\n"
            capture_path.write_bytes(capture_blob)
            expected_path.write_bytes(expected_blob)
            evidence = {"capture_sha256": _hash(capture_blob),
                        "expected_identity_sha256": _hash(expected_blob),
                        "declaration_sha256": declaration_hash, "sources_sha256": source_hashes}
            for flags in ([], ["--json"]):
                output = StringIO()
                with redirect_stdout(output):
                    code = cli.main([str(capture_path), "--expected-identity", str(expected_path), *flags])
                rendered = output.getvalue()
                ensure(code == (0 if defect == "none" else 2), "evidence retains the input verdict")
                if flags:
                    report = json.loads(rendered)
                    ensure(all(report.get(field) == value for field, value in evidence.items()),
                           f"{defect}: every available raw-byte and implementation identity survives")
                    ensure(report["milestone_acceptance"] == "open", "refusal cannot qualify target")
                    if defect == "none":
                        ensure(report["identity"] == capture["identity"], "accepted identity is validated")
                    else:
                        ensure(report["verdict"] == "malformed" and "identity" not in report,
                               "unvalidated roster identities are not published on refusal")
                else:
                    ensure(all(f"  {field}: {json.dumps(value, sort_keys=True)}\n" in rendered
                               for field, value in evidence.items()),
                           f"{defect}: text report retains the same exact evidence")
                    if defect != "none":
                        ensure(rendered.startswith("FAIL ring-measurement:")
                               and "  identity:" not in rendered and "queue " not in rendered,
                               "refusal publishes no validated identity or partial measurements")


def _cli_missing_input_evidence() -> None:
    checkout = corpus.find_root()
    source_names = ("tools/vos/ring_measurement.py", "tools/vos/jsonutil.py",
                    "tools/vos/cli/ring_measurement.py", "tools/vos/cli/ring.py",
                    "docs/implementation/contracts/roster-measurement.md")
    sources = {name: (checkout / name).read_bytes() for name in source_names}
    capture, expected = _fixture()
    capture_blob = b"\n" + _blob(capture) + b"\n"
    expected_blob = _blob({**expected, "capture_sha256": _hash(capture_blob)})
    declaration_blob = (checkout / ring_owner.DECLARATION).read_bytes()
    with tempfile.TemporaryDirectory(prefix="vos-ring-missing-input-") as directory:
        root = Path(directory).resolve()
        for name, blob in sources.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
        paths = {"capture": root / "capture.json", "expected_identity": root / "expected.json",
                 "declaration": root / ring_owner.DECLARATION}
        blobs = {"capture": capture_blob, "expected_identity": expected_blob,
                 "declaration": declaration_blob}
        paths["declaration"].parent.mkdir(parents=True, exist_ok=True)
        for missing in ((), ("capture",), ("expected_identity",), ("declaration",),
                        ("capture", "expected_identity", "declaration")):
            for field, path in paths.items():
                if field in missing:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(blobs[field])
            available: dict[str, object] = {
                "sources_sha256": {name: _hash(blob) for name, blob in sources.items()},
                **{f"{field}_sha256": _hash(blob) for field, blob in blobs.items() if field not in missing},
            }
            for flags in ([], ["--json"]):
                output = StringIO()
                with patch.object(corpus, "find_root", return_value=root), redirect_stdout(output):
                    code = cli.main([str(paths["capture"]), "--expected-identity",
                                     str(paths["expected_identity"]), *flags])
                rendered = output.getvalue()
                ensure(code == (2 if missing else 0), "missing input retains the refusal verdict")
                if flags:
                    report = json.loads(rendered)
                    actual = {field: report[field] for field in
                              ("sources_sha256", "capture_sha256", "expected_identity_sha256",
                               "declaration_sha256") if field in report}
                    ensure(actual == available, "every readable input retains its exact byte identity")
                    ensure(report["milestone_acceptance"] == "open", "missing input cannot qualify target")
                    if missing:
                        ensure(report["verdict"] == "malformed" and "identity" not in report
                               and "rings" not in report and "findings" not in report,
                               "missing input publishes no roster identity or partial measurements")
                        ensure(paths[missing[0]].name in report["reason"],
                               "multiple missing inputs retain deterministic first-input refusal")
                    else:
                        ensure(report["identity"] == capture["identity"]
                               and report["verdict"] == "within_limits", "passing control preserves accounting")
                else:
                    ensure(all(f"  {field}: {json.dumps(value, sort_keys=True)}\n" in rendered
                               for field, value in available.items()),
                           "text refusal retains every readable input fingerprint")
                    if missing:
                        ensure(rendered.startswith("FAIL ring-measurement:")
                               and "  identity:" not in rendered and "queue " not in rendered,
                               "text refusal publishes no validated identity or partial measurements")


def _cli_escaped_identifiers() -> None:
    # JSON identifiers may contain Unicode, control characters and lone surrogates.
    # Rendering must preserve all three verdicts even on a strict output stream.
    with tempfile.TemporaryDirectory(prefix="vos-ring-unicode-") as directory:
        root = Path(directory)
        capture_path, expected_path = root / "capture.json", root / "expected.json"
        for name in ("ring-\ud800", "ring-\u2603\n\x1b-tail"):
            for defect in ("none", "excess", "charge", "chronology", "world", "operation", "key"):
                capture, expected = _fixture()
                capture["rings"][0]["ring_id"] = name
                code = 0 if defect == "none" else 1 if defect == "excess" else 2
                if defect == "excess":
                    _first(capture)["activation_overhead_cost"] = 10**9
                elif defect == "charge":
                    _request(capture)["validation_cost"] = -1
                elif defect == "chronology":
                    _first(capture)["tick"] = 100
                elif defect == "world":
                    capture["rings"][0]["world"] = name
                elif defect == "operation":
                    _request(capture)["operation"] = name
                raw = _blob(capture)
                if defect == "key":
                    key = _blob(name)
                    raw = b"{" + key + b": 0, " + key + b": 0, " + raw[1:]
                capture_path.write_bytes(raw)
                expected_path.write_bytes(_blob({**expected, "capture_sha256": _hash(raw)}))
                for encoding in ("utf-8", "ascii"):
                    for flags in ([], ["--json"]):
                        buffer = BytesIO()
                        with TextIOWrapper(buffer, encoding=encoding, errors="strict") as output:
                            with redirect_stdout(output):
                                actual = cli.main([str(capture_path), "--expected-identity",
                                                   str(expected_path), *flags])
                            output.flush()
                            rendered = buffer.getvalue().decode(encoding)
                        ensure(actual == code, f"{defect}: escaped identifiers retain the verdict")
                        ensure("\\ud800" in rendered or "\\u2603" in rendered,
                               f"{defect}: output escapes non-ASCII identifiers")
                        ensure("\x1b" not in rendered, "identifiers cannot emit terminal controls")
                        if flags:
                            report = json.loads(rendered)
                            ensure(report["milestone_acceptance"] == "open", "target remains open")
                            if code != 2:
                                ensure(report["rings"][0]["ring_id"] == name,
                                       "JSON retains the exact identifier")


def _cli_large_integer_refusal() -> None:
    # Each observation fits the active decimal conversion limit. Nine such
    # counts still fit; ten produce a total and exact rate one digit too wide.
    limit = sys.get_int_max_str_digits()
    amount = 10 ** ((limit or 4300) - 1)
    with tempfile.TemporaryDirectory(prefix="vos-ring-integer-") as directory:
        root = Path(directory).resolve()
        capture_path, expected_path = root / "capture.json", root / "expected.json"
        for count, frequency, excess in ((9, 9, False), (9, 9, True),
                                         (10, 10, False), (10, 10, True), (1, 10, False)):
            capture, expected = _fixture()
            capture["window"] = {"start_tick": 0, "end_tick": count + 1, "tick_hz": frequency}
            capture["rings"][0]["activations"] = [
                {"tick": index + 1, "queue_high_water": 0, "notifications": amount,
                 "activation_overhead_cost": 0, "requests": []}
                for index in range(count)
            ]
            if excess:
                world = ring_owner.declaration(corpus.find_root())["worlds"][0]
                _first(capture)["activation_overhead_cost"] = world["ring"]["slot_budget"] + 1
            raw = _blob(capture)
            expected["capture_sha256"] = _hash(raw)
            result = analyze(raw, _blob(expected), corpus.find_root())
            ring = result.rings[0]
            verdict = "exceeds_limits" if excess else "within_limits"
            ensure(result.verdict == verdict and ring.observed_notifications == count * amount,
                   "uncapped observed hints retain their exact hand-counted total")
            rate = ring.observed_notifications_per_second
            ensure(rate is not None and (rate.numerator, rate.denominator) == (frequency * amount, 1),
                   "exact cadence counts every observed hint over its measured span")
            capture_path.write_bytes(raw)
            expected_path.write_bytes(_blob(expected))
            refused = bool(limit and frequency == 10)
            for flags in ([], ["--json"]):
                output = StringIO()
                with redirect_stdout(output):
                    actual = cli.main([str(capture_path), "--expected-identity",
                                       str(expected_path), *flags])
                rendered = output.getvalue()
                ensure(actual == (2 if refused else int(excess)),
                       "unrepresentable reports refuse before publishing a measurement verdict")
                if flags:
                    report = json.loads(rendered)
                    ensure(report["identity"] == capture["identity"]
                           and report["capture_sha256"] == _hash(raw)
                           and report["expected_identity_sha256"] == _hash(_blob(expected))
                           and report["declaration_sha256"] == capture["declaration_sha256"]
                           and len(report["sources_sha256"]) == 5
                           and report["milestone_acceptance"] == "open",
                           "both outcomes preserve input and implementation identities")
                    if refused:
                        ensure(report["verdict"] == "malformed"
                               and "exact measurement report" in report["reason"]
                               and "rings" not in report and "findings" not in report,
                               "output refusal has no partial arithmetic or passing verdict")
                    else:
                        ensure(report["verdict"] == verdict
                               and report["rings"][0]["observed_notifications"] == count * amount,
                               "representable output retains exact measurements")
                elif refused:
                    ensure(rendered.startswith("FAIL ring-measurement:")
                           and "exact measurement report" in rendered
                           and "ok ring-measurement:" not in rendered
                           and "within_limits" not in rendered and "queue " not in rendered
                           and "  identity:" in rendered and "  sources_sha256:" in rendered,
                           "text refusal preserves evidence without partial success output")
            ensure(sys.get_int_max_str_digits() == limit,
                   "reporting leaves the process-wide integer conversion limit unchanged")


def cases() -> list[Case]:
    return [Case("hand-computed-mixed-and-empty-accounting", _hand_accounting),
            Case("declared-boundary-equality-and-one-past", _declared_boundaries),
            Case("declaration-driven-drain-and-schema", _declaration_is_the_owner),
            Case("independent-multi-world-accounting", _independent_multi_world_accounting),
            Case("multi-world-limit-isolation", _multi_world_limit_isolation),
            Case("declared-operation-identifier-domain", _declared_operation_names),
            Case("ambiguous-declaration-is-refused", _ambiguous_declaration_is_refused),
            Case("declaration-snapshot-owns-selected-limits", _declaration_snapshot_owns_selected_limits),
            Case("declaration-bound-numeric-domains", _declaration_numeric_domains),
            Case("identity-bindings-and-chronology", _identities_and_chronology),
            Case("closed-shapes-and-integer-domains", _closed_shapes_and_numbers),
            Case("cli-scope-evidence-and-exits", _cli_evidence),
            Case("cli-refusal-byte-and-source-evidence", _cli_refusal_evidence),
            Case("cli-missing-input-independent-evidence", _cli_missing_input_evidence),
            Case("cli-large-integer-refusal", _cli_large_integer_refusal),
            Case("cli-escaped-identifiers-and-verdicts", _cli_escaped_identifiers)]
