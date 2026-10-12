# SPDX-License-Identifier: Apache-2.0
"""Independent payload/refusal/lifecycle oracles for the bounded resident reference."""

import json
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO

from tests.harness import Case, ensure
from vos import resident_reads as rr
from vos.cli import resident_reads as cli


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
           "resident/quarantine slot capacity exceeded")
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
            Case("resident current authority and admitted-transfer cuts", _authority_and_lifecycle_cuts),
            Case("resident retained version and holder-independent retirement", _replacement_and_bounded_retirement),
            Case("resident finite metadata backing transfer and counter refusals", _resource_limits),
            Case("resident executed defects and complete modeled observer", _executed_controls_and_observer),
            Case("resident source-bound CLI scope and evidence", _source_bound_cli)]
