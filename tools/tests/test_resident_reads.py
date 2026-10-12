# SPDX-License-Identifier: Apache-2.0
"""Independent payload/refusal/lifecycle oracles for the bounded resident reference."""

import json
import operator
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from io import StringIO
from typing import TYPE_CHECKING, cast

from tests.harness import Case, ensure
from vos import resident_reads as rr
from vos.cli import resident_reads as cli

if TYPE_CHECKING:
    from collections.abc import MutableMapping


def _inhabited_traffic() -> None:
    for kind in ("system-image", "user-data"):
        for count in (1, 2, 4, 8):
            observed = rr.witness(count, kind)
            ensure(observed["accepted"] is True, "inhabited repeated reader refused")
            ensure(observed["N"] == 2 * count and observed["bytes_returned"] == 32 * count,
                   "both independent sessions must actually return independently expected bytes")
            ensure(observed["reservation_events"] == 2, "reservation schedule changed with N")
            ensure(observed["writes"] == {"common": 0, "session-private": 10 * count,
                                         "spsc": 10 * count}, "complete modeled write counts changed")
    service, identity, handles = rr.fixture()
    for handle in handles:
        ensure(service.read(handle, 7, identity, 15, 1) == b"F", "last-byte boundary differs")
        ensure(service.read(handle, 7, identity, 16, 0) == b"", "exact-end empty read differs")
    service.close(handles[0])
    subwindow = service.reserve(0, 7, identity, 4, 8)
    ensure(subwindow is not None, "exact subwindow refused")
    if subwindow is None:
        raise AssertionError("missing subwindow")
    ensure(service.read(subwindow, 7, identity, 0, 8) == b"456789AB", "window start ignored")
    ensure(service.read(subwindow, 7, identity, 8, 1) is None, "subwindow escape returned payload")


def _identity_and_authentication() -> None:
    service, identity, handles = rr.fixture()
    handle = handles[0]
    ensure(service.read(handle, 7, identity, 0, 1) == b"0", "positive authority control refused")
    for supplied in (replace(identity, owner=2), replace(identity, domain=8),
                     replace(identity, object_id=2), replace(identity, version=2),
                     replace(identity, root=replace(identity.root, digest="wrong")),
                     replace(identity, root=replace(identity.root, kind="system-image"))):
        ensure(service.read(handle, 7, supplied, 0, 1) is None,
               "wrong owner/domain/object/version/root returned payload")
        ensure(service.response(0) is None, "refusal retained an earlier reply")
    ensure(service.read(handle, 8, identity, 0, 1) is None, "caller domain ignored")
    for changed in (replace(handle, token=15), replace(handle, boot=1),
                    replace(handle, holder=1), replace(handle, slot=1),
                    replace(handle, start=1), replace(handle, length=15)):
        ensure(service.read(changed, 7, identity, 0, 1) is None, "forged reservation accepted")
    for offset, length in ((-1, 1), (16, 1), (0, 17), (0, -1)):
        ensure(service.read(handle, 7, identity, offset, length) is None,
               "invalid interval returned payload")
    ensure(service.begin(handle, 7, identity, 0, 16), "corruption cut lacked a transfer")
    resident = service.resident(handle.slot)
    ensure(resident is not None, "missing admitted backing")
    if resident is None:
        raise AssertionError("missing backing")
    service.operation = "external-corruption"
    service._put(f"backing.{handle.slot}", replace(resident, payload=b"X" * 16))
    ensure(service.finish(0) is None and service.response(0) is None,
           "admission authentication replaced every-read authentication")


def _integral_read_intervals() -> None:
    malformed = ((0.5, 8), (0, 8.5), (False, 8), (0, True),
                 (float("nan"), 8), (0, float("nan")))
    for kind in ("system-image", "user-data"):
        service, identity, handles = rr.fixture(kind)
        ensure(service.close(handles[0]), "interval control could not release its holder")
        for start, length in malformed:
            before = len(service.writes)
            ensure(service.reserve(0, 7, identity, cast("int", start), cast("int", length)) is None,
                   "non-integral resident window was acknowledged")
            ensure(service.reservation(0) is None and len(service.writes) == before,
                   "malformed resident window consumed admission state")
        for holder in (0.5, False, True, float("nan")):
            before = len(service.writes)
            index = cast("int", holder)
            ensure(service.reserve(index, 7, identity, 0, 8) is None
                   and service.finish(index) is None and not service.revoke(index),
                   "non-integral holder accessed the declared inventory")
            ensure(len(service.writes) == before, "malformed holder changed stored state")

        handle = service.reserve(0, 7, identity, 4, 8)
        if handle is None:
            raise AssertionError("integral subwindow control refused")
        ensure(service.read(handle, 7, identity, 0, 8) == b"456789AB"
               and service.read(handle, 7, identity, 8, 0) == b"",
               "integral subwindow payload or exact-end empty read differs")
        for offset, length in malformed:
            sequence = service._integer("sequence.0")
            ensure(not service.begin(handle, 7, identity, cast("int", offset), cast("int", length)),
                   "non-integral byte request was acknowledged")
            ensure(service.pending(0) is None and service.response(0) is None
                   and service._integer("sequence.0") == sequence,
                   "malformed byte request consumed an outstanding-transfer slot or sequence")
        ensure(service.begin(handle, 7, identity, 1, 2),
               "accepted-transfer control refused after malformed requests")
        pending = service.pending(0)
        for offset, length in malformed:
            ensure(not service.begin(handle, 7, identity, cast("int", offset), cast("int", length))
                   and service.pending(0) == pending,
                   "malformed byte request displaced an accepted transfer")
        ensure(service.finish(0) == b"56"
               and service.read(handles[1], 7, identity, 15, 1) == b"F",
               "malformed inputs lost accepted payload or independent-holder authority")
        ensure(service.close(handle), "handle-alias control could not release its holder")
        unit = service.reserve(0, 7, identity, 0, 1)
        if unit is None:
            raise AssertionError("integral unit-window control refused")
        for field, value in (("start", 0.0), ("start", False),
                             ("length", 1.0), ("length", True)):
            changed = replace(unit, **{field: value})
            # Python equality aliases these malformed fields to the stored integers.
            ensure(changed == unit, "same-valued handle alias control did not execute")
            sequence = service._integer("sequence.0")
            ensure(not service.begin(changed, 7, identity, 0, 1) and not service.renew(changed),
                   "non-integral handle interval bypassed exact reservation validation")
            ensure(service.pending(0) is None and service.response(0) is None
                   and service._integer("sequence.0") == sequence,
                   "malformed handle interval consumed read state")
        ensure(service.read(unit, 7, identity, 0, 1) == b"0",
               "refused handle aliases damaged the stored integral reservation")
        ensure(service.traffic()["common"] == 0 and service.safe_backing(),
               "integral boundary checks added common read writes or lost retained backing")


def _authority_and_lifecycle_cuts() -> None:
    for cut in ("revocation", "close", "delete", "eviction", "teardown", "holder-failure", "crash"):
        service, identity, handles = rr.fixture()
        ensure(service.begin(handles[0], 7, identity, 0, 16), "cut lacked an accepted transfer")
        if cut in ("revocation", "holder-failure"):
            service.revoke(0)
        elif cut == "close":
            service.close(handles[0])
        elif cut == "crash":
            service.crash()
        else:
            service.stop(handles[0].slot)
        ensure(service.finish(0) is None and service.response(0) is None,
               f"{cut} returned payload under stale authority")
        ensure(service.read(handles[0], 7, identity, 0, 16) is None,
               f"{cut} accepted a new read")
        ensure(service.safe_backing(), f"{cut} freed live backing")
    for kind in ("system-image", "user-data"):
        service, identity, handles = rr.fixture(kind)
        service.begin(handles[0], 7, identity, 0, 16)
        service.generation_change()
        expected = None if kind == "system-image" else b"0123456789ABCDEF"
        ensure(service.finish(0) == expected, "generation identity or user-data independence lost")
        ensure(service.reserve(2, 7, identity, 0, 16) is None, "unknown holder accepted")


def _replacement_and_bounded_retirement() -> None:
    service, identity, handles = rr.fixture()
    ensure(service.begin(handles[0], 7, identity, 0, 16), "replacement cut lacked transfer")
    successor = replace(identity, version=2,
                        root=rr.authenticated_root("user-data", 1, b"abcdefghijklmnop"))
    new_slot = service.publish(rr.Resident(successor, b"abcdefghijklmnop"))
    ensure(new_slot is not None and new_slot != handles[0].slot, "replacement reused retained slot")
    ensure(service.finish(0) == b"0123456789ABCDEF", "accepted transfer rebound to new bytes")
    ensure(service.read(handles[1], 7, identity, 0, 16) == b"0123456789ABCDEF",
           "old retained handle identity changed after replacement")
    ensure(service.publish(rr.Resident(replace(successor, version=3), b"abcdefghijklmnop")) is None,
           "retained-predecessor/backing charge omitted")
    ensure(service.begin(handles[1], 7, identity, 0, 16), "retirement cut lacked transfer")
    complete, steps = service.retire(handles[0].slot, cooperative_holder=False)
    ensure(complete and steps <= service.bounds.retirement_steps and service.safe_backing(),
           "retirement depended on holder acknowledgment or freed live backing")
    ensure(service.resident(handles[0].slot) is None and service.pending(1) is None,
           "retirement omitted the modeled sweep")
    backing_stores = [write for write in service.writes
                      if write.operation == "retirement" and write.cell == f"backing.{handles[0].slot}"]
    ensure(len(backing_stores) == 2 and isinstance(backing_stores[0].value, rr.Resident)
           and backing_stores[0].value.payload == bytes(16) and backing_stores[1].value is None,
           "backing release lacked observed prior zeroization")
    ensure(service.read(handles[0], 7, identity, 0, 16) is None, "retired handle resurrected")
    current = service.reserve(0, 7, successor, 0, 16)
    ensure(current is not None, "fresh replacement reservation refused")
    if current is None:
        raise AssertionError("missing successor reservation")
    ensure(service.read(current, 7, successor, 0, 16) == b"abcdefghijklmnop",
           "new reservation returned predecessor")
    service.begin(current, 7, successor, 0, 16)
    complete, steps = service.retire(current.slot, barrier_available=False)
    ensure(not complete and steps <= service.bounds.retirement_steps and service.safe_backing(),
           "unavailable machine operation fabricated reusable-backing evidence")
    ensure(service.resident(current.slot) is not None and service.pending(0) is None,
           "bounded refusal failed to keep quarantine charged or cancel transfer")
    complete, steps = service.retire(current.slot)
    ensure(complete and steps <= service.bounds.retirement_steps,
           "retained quarantine could not be retired on a later modeled barrier")


def _resource_limits() -> None:
    service, identity, handles = rr.fixture()
    ensure(service.reserve(0, 7, identity, 0, 16) is None, "metadata over-admission")
    ensure(service.begin(handles[0], 7, identity, 0, 16), "first transfer refused")
    ensure(not service.begin(handles[0], 7, identity, 0, 16), "private SPSC capacity exceeded")
    ensure(service.begin(handles[1], 7, identity, 0, 16), "second independent transfer refused")
    ensure(service.finish(0) == b"0123456789ABCDEF" and service.finish(1) == b"0123456789ABCDEF",
           "capacity refusal destroyed an accepted transfer")
    for _ in range(service.bounds.counter_limit - 1):
        ensure(service.read(handles[0], 7, identity, 0, 1) == b"0", "premature read counter refusal")
    ensure(service.read(handles[0], 7, identity, 0, 1) is None, "read counter wrapped")
    ensure(service.renew(handles[1]), "finite first renewal refused")
    ensure(not service.renew(handles[1]), "renewal policy exceeded")
    for _ in range(service.bounds.retention):
        ensure(service.advance_clock(), "clock exhausted before expiry")
    ensure(service.read(handles[1], 7, identity, 0, 1) is None, "expired reservation read")
    ensure(not service.renew(handles[1]), "expired reservation renewed")
    for _ in range(service.bounds.counter_limit - service.bounds.retention):
        ensure(service.advance_clock(), "clock exhausted early")
    ensure(not service.advance_clock(), "clock counter wrapped")
    service.close(handles[0])
    ensure(service.reserve(0, 7, identity, 0, 16) is None, "expiry counter overflow admitted")
    limited = rr.Service(rr.Bounds(backing_bytes=16))
    ensure(limited.publish(rr.Resident(identity, b"0123456789ABCDEF")) == 0,
           "single backing control refused")
    ensure(limited.publish(rr.Resident(replace(identity, version=2), b"0123456789ABCDEF")) is None,
           "retained backing byte capacity exceeded")
    no_predecessors = rr.Service(rr.Bounds(predecessors=0))
    no_predecessors.publish(rr.Resident(identity, b"0123456789ABCDEF"))
    ensure(no_predecessors.publish(rr.Resident(replace(identity, version=2), b"0123456789ABCDEF")) is None,
           "retained-predecessor capacity exceeded")
    quarantine = rr.Service(rr.Bounds(backing_bytes=64, residents=2))
    for version in (1, 2):
        slot = quarantine.publish(rr.Resident(replace(identity, version=version), b"0123456789ABCDEF"))
        ensure(slot is not None, "quarantine slots exhausted early")
        if slot is None:
            raise AssertionError("missing quarantine slot")
        complete, _ = quarantine.retire(slot, barrier_available=False)
        ensure(not complete, "unavailable barrier freed quarantine slot")
    ensure(quarantine.publish(rr.Resident(replace(identity, version=3), b"0123456789ABCDEF")) is None,
           "resident and quarantine slot capacity exceeded")
    small = rr.Service(rr.Bounds(counter_limit=2, retention=1, backing_bytes=64))
    small.publish(rr.Resident(identity, b"0123456789ABCDEF"))
    tokens: list[int] = []
    for _ in range(2):
        handle = small.reserve(0, 7, identity, 0, 16)
        ensure(handle is not None, "token exhausted early")
        if handle is None:
            raise AssertionError("missing finite token")
        tokens.append(handle.token)
        small.close(handle)
    ensure(tokens == [1, 2] and small.reserve(0, 7, identity, 0, 16) is None,
           "reservation token wrapped")
    ensure(small.generation_change() and not small.generation_change(), "generation counter wrapped")
    ensure(small.crash() and small.crash() and not small.crash(), "boot epoch wrapped")
    ensure(small.publish(rr.Resident(replace(identity, version=3), b"0123456789ABCDEF")) is None,
           "version counter overflow accepted")


def _integral_composition() -> None:
    bounds = rr.Bounds()
    cyclic: list[object] = []
    cyclic.append(cyclic)
    for field, value in cast("dict[str, int]", asdict(bounds)).items():
        for malformed in (True, False, float(value), value + 0.5,
                          float("nan"), float("inf"), str(value), None,
                          {"value": value}, cyclic):
            try:
                replace(bounds, **{field: malformed})
            except ValueError:
                pass
            else:
                raise AssertionError(f"non-integral composition accepted for {field}: {malformed!r}")

    # Integer compositions remain inhabited at both ends of the declared ranges.
    for admitted in (rr.Bounds(backing_bytes=1, residents=2, holders=2, request_bytes=1,
                               retention=1, renewals=0, predecessors=0, counter_limit=1),
                     rr.Bounds(backing_bytes=64, residents=4, holders=4, request_bytes=64,
                               retention=255, renewals=4, predecessors=3, counter_limit=255)):
        service = rr.Service(admitted)
        identity = rr.Identity(1, 7, 1, 1, rr.authenticated_root("user-data", 1, b"x"))
        ensure(service.publish(rr.Resident(identity, b"x")) == 0,
               "integer composition boundary refused its backing control")
        handle = service.reserve(0, 7, identity, 0, 1)
        if handle is None:
            raise AssertionError("integer composition boundary refused its reservation control")
        for _ in range(admitted.counter_limit):
            ensure(service.read(handle, 7, identity, 0, 1) == b"x",
                   "integer composition counter refused before its declared limit")
        ensure(service.read(handle, 7, identity, 0, 1) is None
               and service._integer("sequence.0") == admitted.counter_limit,
               "integer composition counter admitted a sequence past its declared limit")
        complete, steps = service.retire(handle.slot, cooperative_holder=False)
        ensure(complete and steps <= admitted.retirement_steps and service.safe_backing(),
               "integer composition boundary exceeded holder-independent retirement")
        ensure(service.traffic()["common"] == 0,
               "integer composition validation added common read writes")


def _reused_slot_identity() -> None:
    for outstanding in (False, True):
        service, identity, handles = rr.fixture()
        if outstanding:
            ensure(service.begin(handles[0], 7, identity, 0, 16),
                   "retained predecessor control lacked a transfer")
        successor = replace(identity, version=2,
                            root=rr.authenticated_root("user-data", 1, b"abcdefghijklmnop"))
        slot = service.publish(rr.Resident(successor, b"abcdefghijklmnop"))
        ensure(slot is not None and slot != handles[0].slot and service.safe_backing(),
               "valid retained predecessor reported unsafe backing")
        if outstanding:
            ensure(service.finish(0) == b"0123456789ABCDEF",
                   "valid predecessor transfer changed identity")
        else:
            ensure(service.read(handles[0], 7, identity, 0, 16) == b"0123456789ABCDEF",
                   "valid predecessor reservation changed identity")

        bad, bad_identity, bad_handles = rr.fixture(defect="premature-reuse")
        if outstanding:
            ensure(bad.begin(bad_handles[0], 7, bad_identity, 0, 16),
                   "reuse control lacked an accepted transfer")
        complete, _ = bad.retire(bad_handles[0].slot)
        ensure(complete and bad.reservation(0) is not None,
               "reuse defect failed to retain old metadata")
        if outstanding:
            ensure(bad.pending(0) is not None, "reuse defect omitted the pending transfer")
        reused = bad.publish(rr.Resident(successor, b"abcdefghijklmnop"))
        if reused is None:
            raise AssertionError("reuse defect failed to publish replacement")
        ensure(reused == bad_handles[0].slot and bad.resident(reused) is not None,
               "reuse defect did not repopulate the same backing slot")
        if outstanding:
            # Isolate the accepted-transfer oracle from the reservation oracle.
            bad.operation = "external-control"
            for holder in range(bad.bounds.holders):
                bad._put(f"reservation.{holder}", None)
        ensure(not bad.safe_backing(), "slot presence hid old metadata bound to a replacement identity")
        if outstanding:
            ensure(bad.finish(0) is None and bad.response(0) is None,
                   "old transfer returned replacement bytes")
        ensure(bad.read(bad_handles[0], 7, bad_identity, 0, 16) is None,
               "old reservation returned replacement bytes")


def _closed_predecessor_capacity() -> None:
    payloads = (b"0123456789ABCDEF", b"abcdefghijklmnop", b"ABCDEFGHIJKLMNOP")
    for predecessors in (0, 1):
        service = rr.Service(rr.Bounds(backing_bytes=64, predecessors=predecessors))
        identities = [rr.Identity(1, 7, 1, version, rr.authenticated_root("user-data", 1, payload))
                      for version, payload in enumerate(payloads, 1)]
        closed_slots: list[int] = []
        for identity, payload in zip(identities[:predecessors + 1], payloads[:predecessors + 1], strict=True):
            slot = service.publish(rr.Resident(identity, payload))
            if slot is None:
                raise AssertionError("closed predecessor setup refused before its capacity")
            handle = service.reserve(0, 7, identity, 0, 16)
            if handle is None:
                raise AssertionError("closed predecessor setup lacked a live reservation")
            ensure(service.read(handle, 7, identity, 0, 16) == payload,
                   "closed predecessor setup failed its independent payload control")
            ensure(service.begin(handle, 7, identity, 0, 16),
                   "quarantine cut lacked an accepted transfer")
            complete, steps = service.retire(slot, barrier_available=False)
            ensure(not complete and steps <= service.bounds.retirement_steps
                   and service.resident(slot) is not None and service.safe_backing(),
                   "unavailable barrier failed to keep closed backing charged")
            ensure(service.finish(0) is None and service.read(handle, 7, identity, 0, 16) is None,
                   "quarantine retained live read authority")
            closed_slots.append(slot)

        candidate = rr.Resident(identities[predecessors + 1], payloads[predecessors + 1])
        before = len(service.writes)
        ensure(service.publish(candidate) is None,
               "closed current bypassed the retained-predecessor admission bound")
        ensure(len(service.writes) == before,
               "predecessor-capacity refusal changed the catalog or version counter")
        complete, steps = service.retire(closed_slots[0])
        ensure(complete and steps <= service.bounds.retirement_steps,
               "closed backing failed its bounded recovery control")
        slot = service.publish(candidate)
        ensure(slot == closed_slots[0], "discharged predecessor capacity was not reusable")
        handle = service.reserve(0, 7, candidate.identity, 0, 16)
        if handle is None:
            raise AssertionError("recovered predecessor capacity lacked a reservation")
        ensure(service.read(handle, 7, candidate.identity, 0, 16) == candidate.payload,
               "recovered admission returned the wrong version's bytes")


def _executed_controls_and_observer() -> None:
    controls = rr.controls()
    ensure(set(controls) == {"common-counter", "replacement-touch", "hidden-reacquire",
                            "wrong-domain", "wrong-root", "no-auth", "old-rebind",
                            "premature-reuse", "counter-wrap", "holder-wait"},
           "control campaign omitted a required defect class")
    ensure(all(controls.values()), f"executed defect survived its intended oracle: {controls}")
    service, identity, handles = rr.fixture(defect="common-counter")
    service.read(handles[0], 7, identity, 0, 16)
    ensure(service._integer("counter") == 0 and service.traffic()["common"] == 2,
           "net-state equality hid a common increment/decrement")
    ensure(all(write.cell in service.classes and write.classification == service.classes[write.cell]
               for write in service.writes), "stored writer escaped declared classification")
    try:
        service._put("unobserved-statistic", 1)
    except ValueError:
        pass
    else:
        raise AssertionError("undeclared concrete writer accepted")
    for argument in (0, 9):
        try:
            rr.witness(argument)
        except ValueError:
            continue
        raise AssertionError("out-of-domain witness accepted")


def _frozen_stored_inventory() -> None:
    service, identity, handles = rr.fixture(defect="common-counter")
    ensure(service.read(handles[0], 7, identity, 0, 16) == b"0123456789ABCDEF",
           "frozen inventory control failed its independent payload")
    ensure(service.traffic()["common"] == 2, "common-counter control did not execute")
    classes = dict(service.classes)
    sequence = service._integer("sequence.0")
    writes = list(service.writes)
    for cell, classification in (("counter", "session-private"),
                                 ("sequence.0", "session-private"),
                                 ("unobserved-statistic", "common")):
        try:
            service._declare(cell, 0, classification)
        except ValueError:
            pass
        else:
            raise AssertionError("execution redeclared stored state without an observed write")
    try:
        # Exercise the mutable interface deliberately; runtime must refuse it.
        operator.setitem(cast("MutableMapping[str, rr.WriteClass]", service.classes),
                         "counter", "session-private")
    except TypeError:
        pass
    else:
        raise AssertionError("public inventory relabeled a common writer")
    try:
        attribute = "classes"
        setattr(service, attribute, {"counter": "session-private"})
    except AttributeError:
        pass
    else:
        raise AssertionError("public inventory was replaced after initialization")
    ensure(dict(service.classes) == classes and service._integer("sequence.0") == sequence
           and service.writes == writes, "refused inventory mutation changed state or observation")
    ensure(service.read(handles[0], 7, identity, 0, 16) == b"0123456789ABCDEF"
           and service.traffic()["common"] == 4,
           "inventory mutation hid a subsequent common-counter defect")


def _frozen_composition() -> None:
    service, identity, handles = rr.fixture()
    handle = handles[0]
    ensure(service.renew(handle) and not service.renew(handle),
           "fixed renewal policy lacked its positive and exhaustion controls")
    ensure(service.begin(handle, 7, identity, 0, 16),
           "composition control lacked an accepted transfer")
    bounds = service.bounds
    classes = dict(service.classes)
    writes = list(service.writes)
    pending = service.pending(0)
    for replacement in (replace(bounds, renewals=4), replace(bounds, counter_limit=31),
                        replace(bounds, holders=3)):
        try:
            attribute = "bounds"
            setattr(service, attribute, replacement)
        except AttributeError:
            pass
        else:
            raise AssertionError("public composition replacement changed admitted resource bounds")
    ensure(service.bounds == bounds and dict(service.classes) == classes
           and service.writes == writes and service.pending(0) == pending,
           "refused composition replacement changed state, observation or an accepted transfer")
    ensure(service.finish(0) == b"0123456789ABCDEF" and not service.renew(handle),
           "refused composition replacement lost payload or widened the renewal policy")
    for _ in range(bounds.counter_limit - 1):
        ensure(service.read(handle, 7, identity, 0, 1) == b"0",
               "fixed read counter refused before its admitted limit")
    ensure(service.read(handle, 7, identity, 0, 1) is None,
           "public composition replacement widened the admitted read counter")
    ensure(service.reserve(2, 7, identity, 0, 16) is None,
           "public composition replacement added an undeclared holder")

    # Wider bounds are legitimate composition inputs before the inventory is declared.
    admitted = rr.Bounds(renewals=2, counter_limit=16, holders=3)
    wider, wider_identity, wider_handles = rr.fixture(bounds=admitted)
    third = wider.reserve(2, 7, wider_identity, 0, 16)
    if third is None:
        raise AssertionError("declared third holder refused")
    ensure(wider.read(third, 7, wider_identity, 0, 16) == b"0123456789ABCDEF",
           "declared third holder returned unexpected bytes")
    ensure(wider.renew(wider_handles[0]) and wider.renew(wider_handles[0])
           and not wider.renew(wider_handles[0]), "declared wider renewal policy differs")
    for _ in range(admitted.counter_limit):
        ensure(wider.read(wider_handles[0], 7, wider_identity, 0, 1) == b"0",
               "declared wider read counter refused early")
    ensure(wider.read(wider_handles[0], 7, wider_identity, 0, 1) is None,
           "declared wider read counter failed to refuse at its own limit")


def _source_bound_cli() -> None:
    output = StringIO()
    with redirect_stdout(output):
        code = cli.main(["--json"])
    report = json.loads(output.getvalue())
    ensure(code == 0 and report["scope"] == "finite Python host reference", "CLI scope or verdict differs")
    ensure(len(report["witnesses"]) == 8 and len(report["executed_python_controls"]) == 10,
           "CLI omitted executed witnesses or controls")
    ensure("tools/vos/cli/resident_reads.py" in report["sources"]
           and len(report["runtime"]["sha256"]) == 64 and report["remaining"],
           "report omitted runtime/source binding or unfinished qualification")


def cases() -> list[Case]:
    return [Case("resident two-session payload and complete traffic witness", _inhabited_traffic),
            Case("resident exact identity and every-read authentication", _identity_and_authentication),
            Case("resident integral intervals and holder refusals", _integral_read_intervals),
            Case("resident current authority and admitted-transfer cuts", _authority_and_lifecycle_cuts),
            Case("resident retained version and holder-independent retirement", _replacement_and_bounded_retirement),
            Case("resident finite metadata backing transfer and counter refusals", _resource_limits),
            Case("resident exact integer composition and finite boundary controls", _integral_composition),
            Case("resident reused slot preserves exact backing identity", _reused_slot_identity),
            Case("resident closed predecessor capacity and bounded recovery", _closed_predecessor_capacity),
            Case("resident executed defects and complete modeled observer", _executed_controls_and_observer),
            Case("resident frozen stored inventory refuses hidden writers", _frozen_stored_inventory),
            Case("resident fixed composition preserves admitted resource limits", _frozen_composition),
            Case("resident source-bound CLI scope and evidence", _source_bound_cli)]
