# SPDX-License-Identifier: Apache-2.0
"""Independent payload/refusal/lifecycle oracles for the bounded resident reference."""

import hashlib
import json
import operator
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from io import StringIO
from typing import TYPE_CHECKING, cast, override

from tests.harness import Case, ensure
from vos import resident_reads as rr
from vos.cli import resident_reads as cli

if TYPE_CHECKING:
    from collections.abc import MutableMapping


def _finish(service: rr.Service, holder: int) -> bytes | None:
    """Synchronous fixture caller obtains the admitted sequence before completion."""
    request = service.pending(holder)
    return service.finish(holder, 0 if request is None else request.sequence)


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
                     replace(identity, root=replace(identity.root, digest="0" * 64)),
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
    ensure(_finish(service, 0) is None and service.response(0) is None,
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
                   and service.finish(index, 0) is None and not service.revoke(index),
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
        ensure(_finish(service, 0) == b"56"
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


def _integral_handle_fields() -> None:
    service, identity, handles = rr.fixture()
    handle = handles[0]
    ensure(service.begin(handle, 7, identity, 0, 16),
           "malformed-close control lacked an accepted transfer")
    malformed_window = {"start": 0.0}
    ensure(not service.close(replace(handle, **malformed_window)),
           "numerically equal non-integral window cancelled a live reservation")
    ensure(_finish(service, 0) == b"0123456789ABCDEF",
           "malformed-close refusal lost the independently expected transfer")

    cyclic: list[object] = []
    cyclic.append(cyclic)
    for field, value in (("token", handle.token), ("boot", handle.boot),
                         ("holder", handle.holder), ("slot", handle.slot),
                         ("start", handle.start), ("length", handle.length),
                         ("owner", identity.owner), ("domain", identity.domain),
                         ("object_id", identity.object_id), ("version", identity.version),
                         ("generation", identity.root.generation)):
        for malformed in (float(value), bool(value), value + 0.5, float("nan"), float("inf"),
                          str(value), None, {"value": 0}, cyclic):
            service, identity, handles = rr.fixture()
            handle = handles[0]
            if field == "generation":
                changed = replace(handle, identity=replace(identity,
                    root=replace(identity.root, generation=cast("int", malformed))))
            elif field in ("owner", "domain", "object_id", "version"):
                changed = replace(handle, identity=replace(identity, **{field: malformed}))
            else:
                changed = replace(handle, **{field: malformed})
            before = len(service.writes)
            ensure(service.read(changed, 7, identity, 0, 16) is None,
                   f"malformed handle {field} returned payload")
            ensure(not service.renew(changed) and not service.close(changed),
                   f"malformed handle {field} changed its reservation")
            ensure(len(service.writes) == before,
                   f"malformed handle {field} wrote service state before refusal")

            ensure(service.begin(handle, 7, identity, 0, 16),
                   "integral handle control lacked an accepted transfer")
            pending = service.pending(0)
            held = service.reservation(0)
            before = len(service.writes)
            ensure(service.read(changed, 7, identity, 0, 16) is None
                   and not service.renew(changed) and not service.close(changed),
                   f"malformed handle {field} was accepted beside a pending transfer")
            ensure(service.pending(0) == pending and service.reservation(0) == held
                   and len(service.writes) == before,
                   f"malformed handle {field} disturbed an accepted transfer")
            ensure(_finish(service, 0) == b"0123456789ABCDEF" and service.renew(handle),
                   "integral handle refused its independent payload or renewal control")
            ensure(service.revoke(0) and service.close(handle),
                   "integral close failed to discharge a revoked reservation")
            ensure(service.traffic()["common"] == 0,
                   "integral handle guard added common per-read writes")


def _canonical_handle_container() -> None:
    class HandleAlias(rr.Handle):
        pass

    class HandleSpoof(rr.Handle):
        __hash__ = object.__hash__

        @override
        def __eq__(self, other: object) -> bool:
            return True

        @override
        def __ne__(self, other: object) -> bool:
            return False

    for kind in ("system-image", "user-data"):
        for changed_field in ("token", "start", "length", "window", "alias"):
            service, identity, handles = rr.fixture(kind)
            ensure(service.close(handles[0]), "handle-container control could not release its holder")
            handle = service.reserve(0, 7, identity, 4, 8)
            if handle is None:
                raise AssertionError("handle-container control lacked its admitted subwindow")
            token = 15 if changed_field == "token" else handle.token
            start = 0 if changed_field in ("start", "window") else handle.start
            length = 16 if changed_field in ("length", "window") else handle.length
            container = HandleAlias if changed_field == "alias" else HandleSpoof
            supplied = container(token, handle.boot, handle.holder, handle.slot, identity, start, length)
            if changed_field != "alias":
                inequality = handle != supplied
                ensure(supplied == handle and handle == supplied and inequality is False,
                       "handle equality-spoof control did not execute")
            ensure((handle.token, handle.start, handle.length) == (3, 4, 8),
                   "canonical reservation changed the independent token/window expectation")
            ensure(service.read(handle, 7, identity, 0, 8) == b"456789AB",
                   "canonical subwindow did not return independently expected bytes")
            before = len(service.writes)
            ensure(service.read(supplied, 7, identity, 0, 1) is None
                   and service.read(supplied, 7, identity, 0, 16) is None
                   and not service.renew(supplied) and not service.close(supplied),
                   f"{changed_field} handle subclass bypassed its reservation or window")
            ensure(len(service.writes) == before and service.response(0) == b"456789AB",
                   "handle-container refusal wrote stored state or erased a canonical response")

            ensure(service.begin(handle, 7, identity, 0, 8)
                   and service.begin(handles[1], 7, identity, 0, 16),
                   "handle-container control lacked two independent accepted transfers")
            pending = (service.pending(0), service.pending(1))
            held = service.reservation(0)
            before = len(service.writes)
            ensure(service.read(supplied, 7, identity, 0, 16) is None
                   and not service.renew(supplied) and not service.close(supplied),
                   "handle subclass changed authority beside accepted transfers")
            ensure((service.pending(0), service.pending(1)) == pending
                   and service.reservation(0) == held and len(service.writes) == before,
                   "handle-container refusal disturbed accepted transfers or renewal state")
            ensure(_finish(service, 0) == b"456789AB"
                   and _finish(service, 1) == b"0123456789ABCDEF",
                   "handle-container refusal lost subwindow or independent-holder payload")
            ensure(service.renew(handle) and service.revoke(0) and service.close(handle),
                   "handle-container refusal prevented canonical renewal or revoked close")
            ensure(service.traffic()["common"] == 0 and service.safe_backing(),
                   "handle-container guard added common read writes or lost retained backing")


def _integral_supplied_identities() -> None:
    payload = b"0123456789ABCDEF"
    cyclic: list[object] = []
    cyclic.append(cyclic)
    for kind in ("system-image", "user-data"):
        identity = rr.Identity(1, 7, 1, 1, rr.authenticated_root(kind, 1, payload))
        malformed_identities: list[rr.Identity] = []
        for field, value in (("owner", 1), ("domain", 7), ("object_id", 1),
                             ("version", 1), ("generation", 1)):
            for malformed in (float(value), bool(value), value + 0.5, float("nan"),
                              float("inf"), str(value), None, {"value": value}, cyclic):
                if field == "generation":
                    changed = replace(identity, root=replace(identity.root,
                        generation=cast("int", malformed)))
                else:
                    changed = replace(identity, **{field: malformed})
                malformed_identities.append(changed)
        for malformed in (None, "identity", {"owner": 1}, cyclic):
            malformed_identities.append(cast("rr.Identity", malformed))
            malformed_identities.append(replace(identity, root=cast("rr.Root", malformed)))

        for supplied in malformed_identities:
            service = rr.Service()
            before = len(service.writes)
            ensure(service.publish(rr.Resident(supplied, payload)) is None,
                   "malformed supplied identity entered the resident catalog")
            ensure(len(service.writes) == before and service._integer("last-version") == 0,
                   "malformed publication consumed backing or the integer version counter")
            ensure(service.publish(rr.Resident(identity, payload)) == 0,
                   "malformed publication damaged the canonical integer control")
            before = len(service.writes)
            ensure(service.reserve(0, 7, supplied, 0, 16) is None
                   and service.reservation(0) is None and len(service.writes) == before,
                   "malformed supplied identity consumed a reservation or token")
            handle = service.reserve(0, 7, identity, 0, 16)
            if handle is None:
                raise AssertionError("canonical integer admission refused after malformed input")
            before = len(service.writes)
            ensure(not service.begin(handle, 7, supplied, 0, 16)
                   and service.pending(0) is None and len(service.writes) == before,
                   "malformed supplied identity consumed read state")
            ensure(service.begin(handle, 7, identity, 0, 16),
                   "canonical identity control lacked an accepted transfer")
            pending = service.pending(0)
            before = len(service.writes)
            ensure(not service.begin(handle, 7, supplied, 0, 16)
                   and service.pending(0) == pending and len(service.writes) == before,
                   "malformed supplied identity disturbed an accepted transfer")
            changed_handle = replace(handle, identity=supplied)
            ensure(service.read(changed_handle, 7, identity, 0, 16) is None
                   and not service.renew(changed_handle) and not service.close(changed_handle)
                   and service.pending(0) == pending and len(service.writes) == before,
                   "malformed nested handle identity disturbed an accepted transfer")
            ensure(_finish(service, 0) == payload and service.close(handle),
                   "malformed identity lost canonical payload or releasable authority")
            ensure(service.traffic()["common"] == 0 and service.safe_backing(),
                   "supplied identity checks added common read writes or lost backing")

        service, identity, handles = rr.fixture(kind)
        ensure(service.close(handles[0]), "domain-alias control could not release its holder")
        for malformed in (7.0, True, 7.5, float("nan"), float("inf"), "7", None,
                          {"value": 7}, cyclic):
            domain = cast("int", malformed)
            before = len(service.writes)
            ensure(service.reserve(0, domain, identity, 0, 16) is None
                   and len(service.writes) == before,
                   "non-integral caller domain consumed admission state")
        handle = service.reserve(0, 7, identity, 0, 16)
        if handle is None:
            raise AssertionError("canonical domain admission refused")
        ensure(service.begin(handle, 7, identity, 0, 16),
               "domain-alias control lacked an accepted transfer")
        pending = service.pending(0)
        for malformed in (7.0, True, 7.5, float("nan"), float("inf"), "7", None,
                          {"value": 7}, cyclic):
            before = len(service.writes)
            ensure(not service.begin(handle, cast("int", malformed), identity, 0, 16)
                   and service.pending(0) == pending and len(service.writes) == before,
                   "non-integral caller domain disturbed an accepted transfer")
        ensure(_finish(service, 0) == payload
               and service.read(handles[1], 7, identity, 15, 1) == b"F",
               "domain refusal lost accepted or independent-holder payload")


def _canonical_root_fields() -> None:
    class EqualitySpoof:
        __hash__ = object.__hash__

        @override
        def __eq__(self, other: object) -> bool:
            return True

    class StringAlias(str):
        __slots__ = ()
        __hash__ = str.__hash__

        @override
        def __eq__(self, other: object) -> bool:
            return True

    class RootAlias(rr.Root):
        pass

    class RootSpoof(rr.Root):
        __hash__ = object.__hash__

        @override
        def __eq__(self, other: object) -> bool:
            return True

    class IdentityAlias(rr.Identity):
        pass

    class IdentitySpoof(rr.Identity):
        __hash__ = object.__hash__

        @override
        def __eq__(self, other: object) -> bool:
            return True

    payload = b"0123456789ABCDEF"
    for kind in ("system-image", "user-data"):
        identity = rr.Identity(1, 7, 1, 1, rr.authenticated_root(kind, 1, payload))
        malformed_kinds: tuple[object, ...] = ("unknown", "", None, [], {}, True,
                                              EqualitySpoof(), StringAlias(kind))
        roots = [replace(identity.root, kind=malformed)
                 for malformed in malformed_kinds]
        roots += [replace(identity.root, digest=cast("str", malformed))
                  for malformed in ("", "wrong", "0" * 63, "0" * 65, "g" * 64,
                                    identity.root.digest.upper(), None, [], {}, b"0" * 64,
                                    EqualitySpoof(), StringAlias(identity.root.digest))]
        root_spoof = RootSpoof(kind, 1, "0" * 64)
        identity_spoof = IdentitySpoof(1, 7, 2, 2, identity.root)
        ensure(root_spoof == identity.root and identity_spoof == identity,
               "root and identity equality-spoof controls did not execute")
        roots += [RootAlias(kind, 1, identity.root.digest), root_spoof]
        supplied_identities = [replace(identity, root=root) for root in roots]
        supplied_identities += [IdentityAlias(1, 7, 1, 1, identity.root), identity_spoof]
        for supplied in supplied_identities:
            service = rr.Service()
            before = len(service.writes)
            ensure(service.publish(rr.Resident(supplied, payload)) is None
                   and len(service.writes) == before and service._integer("last-version") == 0,
                   "malformed root consumed initial backing or a version")
            ensure(service.publish(rr.Resident(identity, payload)) == 0,
                   "malformed root prevented a canonical same-version publication")
            before = len(service.writes)
            ensure(service.reserve(0, 7, supplied, 0, 16) is None
                   and len(service.writes) == before and service._integer("next-token") == 0,
                   "malformed root consumed admission state")
            first = service.reserve(0, 7, identity, 0, 16)
            second = service.reserve(1, 7, identity, 0, 16)
            if first is None or second is None:
                raise AssertionError("canonical root lacked two independent reservations")
            ensure(service.begin(first, 7, identity, 0, 16)
                   and service.begin(second, 7, identity, 0, 16),
                   "canonical roots lacked accepted independent transfers")
            pending = (service.pending(0), service.pending(1))
            before = len(service.writes)
            changed = replace(first, identity=supplied)
            ensure(service.read(first, 7, supplied, 0, 16) is None
                   and service.read(changed, 7, identity, 0, 16) is None
                   and not service.renew(changed) and not service.close(changed),
                   "malformed root entered read, renewal or close")
            ensure(service.publish(rr.Resident(replace(supplied, version=2), payload)) is None
                   and len(service.writes) == before and service._integer("last-version") == 1
                   and (service.pending(0), service.pending(1)) == pending,
                   "malformed replacement root disturbed version or accepted transfers")
            ensure(_finish(service, 0) == payload and _finish(service, 1) == payload,
                   "malformed root lost independently expected accepted payloads")
            ensure(service.publish(rr.Resident(replace(identity, version=2), payload)) == 1
                   and service.read(first, 7, identity, 15, 1) == b"F",
                   "malformed replacement root consumed a version or displaced retained bytes")
            ensure(service.traffic()["common"] == 0 and service.safe_backing(),
                   "root guards added common read writes or lost exact retained backing")

        service, identity, handles = rr.fixture(kind)
        ensure(service.generation_change(), "generation refusal control did not execute")
        expected = None if kind == "system-image" else payload
        ensure(service.read(handles[0], 7, identity, 0, 16) == expected,
               "canonical root kind failed its independent generation policy")


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
        ensure(_finish(service, 0) is None and service.response(0) is None,
               f"{cut} returned payload under stale authority")
        ensure(service.read(handles[0], 7, identity, 0, 16) is None,
               f"{cut} accepted a new read")
        ensure(service.safe_backing(), f"{cut} freed live backing")
    for kind in ("system-image", "user-data"):
        service, identity, handles = rr.fixture(kind)
        service.begin(handles[0], 7, identity, 0, 16)
        service.generation_change()
        expected = None if kind == "system-image" else b"0123456789ABCDEF"
        ensure(_finish(service, 0) == expected, "generation identity or user-data independence lost")
        ensure(service.reserve(2, 7, identity, 0, 16) is None, "unknown holder accepted")


def _completion_request_binding() -> None:
    for kind in ("system-image", "user-data"):
        for cut in ("repeat", "close", "replacement", "retirement"):
            service, identity, handles = rr.fixture(kind)
            ensure(service.begin(handles[0], 7, identity, 1, 2)
                   and service.begin(handles[1], 7, identity, 14, 2),
                   "completion cut lacked two admitted requests")
            old = service.pending(0)
            if old is None:
                raise AssertionError("missing predecessor completion identity")
            if cut == "repeat":
                ensure(service.finish(0, old.sequence) == b"12", "predecessor completion refused")
                current_handle, current_identity = handles[0], identity
                offset, length, expected, other_expected = 16, 0, b"", b"EF"
            elif cut == "close":
                ensure(service.close(handles[0]), "close did not cancel predecessor transfer")
                admitted = service.reserve(0, 7, identity, 4, 8)
                if admitted is None:
                    raise AssertionError("successor subwindow reservation refused")
                current_handle, current_identity = admitted, identity
                offset, length, expected, other_expected = 1, 2, b"56", b"EF"
            else:
                successor_payload = b"abcdefghijklmno!"
                current_identity = replace(identity, version=2,
                                           root=rr.authenticated_root(kind, 1, successor_payload))
                if cut == "replacement":
                    ensure(service.close(handles[0]), "replacement did not cancel predecessor transfer")
                else:
                    complete, steps = service.retire(handles[0].slot, cooperative_holder=False)
                    ensure(complete and steps <= service.bounds.retirement_steps,
                           "completion cut could not retire without its holders")
                slot = service.publish(rr.Resident(current_identity, successor_payload))
                ensure(slot is not None, "successor resident refused")
                if cut == "retirement":
                    ensure(slot == handles[0].slot, "retirement control did not reuse the backing slot")
                    other = service.reserve(1, 7, current_identity, 0, 16)
                    ensure(other is not None, "independent successor reservation refused")
                    if other is None:
                        raise AssertionError("missing independent successor")
                    ensure(service.begin(other, 7, current_identity, 14, 2),
                           "independent successor transfer refused")
                admitted = service.reserve(0, 7, current_identity, 0, 16)
                if admitted is None:
                    raise AssertionError("successor reservation refused")
                current_handle = admitted
                offset, length, expected = 1, 2, b"bc"
                other_expected = b"o!" if cut == "retirement" else b"EF"
            ensure(service.begin(current_handle, 7, current_identity, offset, length),
                   "successor transfer refused")
            current, independent = service.pending(0), service.pending(1)
            if current is None or independent is None:
                raise AssertionError("missing successor or independent completion identity")
            ensure(current.sequence > old.sequence, "holder reuse reset its request identifier")
            before = len(service.writes)
            for delayed in (old.sequence, current.sequence + 1):
                ensure(service.finish(0, delayed) is None and len(service.writes) == before
                       and service.pending(0) == current and service.pending(1) == independent,
                       "delayed or foreign completion consumed a current accepted transfer")
            ensure(service.finish(0, current.sequence) == expected and service.response(0) == expected,
                   "matching successor completion lost its exact authenticated window")
            before = len(service.writes)
            for replay in (old.sequence, current.sequence):
                ensure(service.finish(0, replay) is None and len(service.writes) == before
                       and service.response(0) == expected and service.pending(1) == independent,
                       "replayed completion cleared a newer reply or independent transfer")
            ensure(service.finish(1, independent.sequence) == other_expected
                   and service.traffic()["common"] == 0 and service.safe_backing(),
                   "completion binding lost independent payload, traffic or backing safety")
        service, identity, handles = rr.fixture(kind, bounds=rr.Bounds(counter_limit=2, retention=1))
        ensure(service.begin(handles[0], 7, identity, 0, 1), "finite first request refused")
        first = service.pending(0)
        if first is None:
            raise AssertionError("missing finite first completion identity")
        ensure(service.finish(0, first.sequence) == b"0"
               and service.begin(handles[0], 7, identity, 16, 0),
               "finite last request refused")
        last = service.pending(0)
        if last is None:
            raise AssertionError("missing finite last completion identity")
        before = len(service.writes)
        ensure(last.sequence == 2 and service.finish(0, first.sequence) is None
               and service.pending(0) == last and len(service.writes) == before,
               "stale completion consumed the last finite request")
        ensure(service.finish(0, last.sequence) == b""
               and not service.begin(handles[0], 7, identity, 0, 1)
               and service.pending(0) is None and service._integer("sequence.0") == 2,
               "exhaustion wrapped a completion identifier")
        ensure(service.crash() and service._integer("sequence.0") == 2,
               "crash reset a completion identifier")
        before = len(service.writes)
        ensure(service.finish(0, last.sequence) is None and len(service.writes) == before,
               "crash resurrected a canceled completion")


def _integral_backing_slots() -> None:
    for kind in ("system-image", "user-data"):
        service, identity, handles = rr.fixture(kind, bounds=rr.Bounds(residents=2))
        ensure(service.close(handles[1]), "slot control could not release its second holder")
        successor_payload = b"abcdefghijklmnop"
        successor = replace(identity, version=2,
                            root=rr.authenticated_root(kind, 1, successor_payload))
        successor_slot = service.publish(rr.Resident(successor, successor_payload))
        ensure(successor_slot == service.bounds.residents - 1,
               "slot control did not inhabit both backing-index boundaries")
        second = service.reserve(1, 7, successor, 0, 16)
        if second is None:
            raise AssertionError("successor slot control lacked its reservation")
        ensure(service.begin(handles[0], 7, identity, 1, 2)
               and service.begin(second, 7, successor, 1, 2),
               "slot controls lacked independent accepted transfers")
        pending = (service.pending(0), service.pending(1))
        held = (service.reservation(0), service.reservation(1))
        backing = (service.resident(0), service.resident(1))
        for malformed in ("0", "1", False, True, 0.0, 1.0, 0.5,
                          float("nan"), float("inf"), -1, service.bounds.residents,
                          None, [0], {"slot": 0}):
            slot = cast("int", malformed)
            before = len(service.writes)
            ensure(not service.stop(slot), "malformed backing slot closed live admission")
            ensure(service.retire(slot) == (False, 0)
                   and service.retire(slot, barrier_available=False) == (False, 0),
                   "malformed backing slot acknowledged retirement or freed live backing")
            ensure(len(service.writes) == before
                   and (service.pending(0), service.pending(1)) == pending
                   and (service.reservation(0), service.reservation(1)) == held
                   and (service.resident(0), service.resident(1)) == backing
                   and service.safe_backing(),
                   "refused backing slot changed stored state or displaced an accepted transfer")
        ensure(_finish(service, 0) == b"12" and _finish(service, 1) == b"bc",
               "malformed slot requests lost exact retained-version payloads")
        ensure(service.begin(handles[0], 7, identity, 0, 16)
               and service.begin(second, 7, successor, 0, 16),
               "integer retirement controls lacked independent transfers")
        complete, steps = service.retire(handles[0].slot, barrier_available=False)
        ensure(not complete and steps <= service.bounds.retirement_steps
               and service.pending(0) is None and service.reservation(0) is None
               and service.resident(handles[0].slot) is not None
               and service.pending(1) is not None and service.safe_backing(),
               "integer retirement did not quarantine only its selected backing slot")
        complete, steps = service.retire(handles[0].slot, cooperative_holder=False)
        ensure(complete and steps <= service.bounds.retirement_steps
               and service.resident(handles[0].slot) is None and service.safe_backing(),
               "integer slot failed holder-independent bounded retirement")
        ensure(_finish(service, 1) == successor_payload,
               "retiring a predecessor disturbed the successor transfer")
        ensure(service.stop(second.slot), "integer final-slot stop control refused")
        complete, steps = service.retire(second.slot, cooperative_holder=False)
        ensure(complete and steps <= service.bounds.retirement_steps and service.safe_backing(),
               "integer final-slot retirement control refused")
        ensure(service.traffic()["common"] == 0,
               "backing-slot validation added common read writes")


def _immutable_backing_publication() -> None:
    class UnderchargedBytes(bytes):
        @override
        def __len__(self) -> int:
            return 1

    payload = b"0123456789ABCDEF"
    successor_payload = b"abcdefghijklmnop"
    for kind in ("system-image", "user-data"):
        identity = rr.Identity(1, 7, 1, 1, rr.authenticated_root(kind, 1, payload))
        successor = replace(identity, version=2,
                            root=rr.authenticated_root(kind, 1, successor_payload))
        mutable = bytearray(payload)
        undercharged = UnderchargedBytes(b"X" * 80)
        ensure(len(undercharged) == 1 and len(bytes(undercharged)) == 80,
               "undercharged backing control did not exceed the declared byte bound")
        for supplied in (mutable, memoryview(mutable), undercharged):
            resident = rr.Resident(identity, cast("bytes", supplied))
            service = rr.Service()
            before = len(service.writes)
            ensure(service.publish(resident) is None and len(service.writes) == before
                   and service._integer("last-version") == 0 and service.resident(0) is None,
                   "noncanonical backing consumed initial publication state")
            ensure(service.publish(rr.Resident(identity, payload)) == 0,
                   "refused backing consumed the version or blocked a canonical retry")

            handles = [service.reserve(holder, 7, identity, 0, 16) for holder in (0, 1)]
            if any(handle is None for handle in handles):
                raise AssertionError("canonical retry lacked both independent reservations")
            for handle in handles:
                if handle is None:
                    raise AssertionError("missing canonical reservation")
                ensure(service.begin(handle, 7, identity, 0, 16),
                       "replacement refusal control lacked independent accepted transfers")
            held = (service.reservation(0), service.reservation(1))
            pending = (service.pending(0), service.pending(1))
            before = len(service.writes)
            ensure(service.publish(replace(resident, identity=successor)) is None
                   and len(service.writes) == before
                   and service._integer("last-version") == 1
                   and (service.reservation(0), service.reservation(1)) == held
                   and (service.pending(0), service.pending(1)) == pending
                   and service.resident(1) is None and service.safe_backing(),
                   "noncanonical replacement consumed capacity or displaced accepted transfers")
            ensure(service.publish(rr.Resident(successor, successor_payload)) == 1,
                   "replacement refusal consumed its version or blocked a canonical retry")
            ensure(_finish(service, 0) == payload and _finish(service, 1) == payload,
                   "refused backing or successor publication changed retained transfer bytes")
            if handles[0] is None:
                raise AssertionError("missing releasable predecessor reservation")
            ensure(service.close(handles[0]), "canonical predecessor close refused")
            current = service.reserve(0, 7, successor, 0, 16)
            if current is None:
                raise AssertionError("canonical successor retry lacked a reservation")
            ensure(service.read(current, 7, successor, 0, 16) == successor_payload
                   and service.traffic()["common"] == 0 and service.safe_backing(),
                   "canonical immutable backing retry lost payload, traffic or lifetime safety")


def _stable_resident_container() -> None:
    class DerivedResident(rr.Resident):
        pass

    class SwitchingResident(rr.Resident):
        def arm(self) -> None:
            object.__setattr__(self, "payload_reads", 0)

        @override
        def __getattribute__(self, name: str) -> object:
            if name == "payload":
                reads = object.__getattribute__(self, "payload_reads")
                object.__setattr__(self, "payload_reads", reads + 1)
                if reads:
                    return b"UNAUTHENTICATED!!"
            return object.__getattribute__(self, name)

    payload = b"0123456789ABCDEF"
    successor_payload = b"abcdefghijklmnop"
    for kind in ("system-image", "user-data"):
        identity = rr.Identity(1, 7, 1, 1, rr.authenticated_root(kind, 1, payload))
        successor = replace(identity, version=2,
                            root=rr.authenticated_root(kind, 1, successor_payload))
        switching = SwitchingResident(identity, payload)
        switching.arm()
        ensure(hashlib.sha256(switching.payload).hexdigest() == identity.root.digest
               and switching.payload[:16] == b"UNAUTHENTICATED!",
               "derived resident control did not change bytes between authentication and copying")
        for container in (DerivedResident, SwitchingResident):
            service = rr.Service()
            supplied = container(identity, payload)
            replacement = container(successor, successor_payload)
            if isinstance(supplied, SwitchingResident):
                supplied.arm()
            if isinstance(replacement, SwitchingResident):
                replacement.arm()
            before = list(service.writes)
            ensure(service.publish(supplied) is None and service.writes == before
                   and service._integer("last-version") == 0
                   and all(service.resident(slot) is None for slot in range(service.bounds.residents)),
                   "derived resident consumed backing or version state during initial publication")
            ensure(service.publish(rr.Resident(identity, payload)) == 0,
                   "refused derived resident prevented a canonical same-version retry")
            first = service.reserve(0, 7, identity, 4, 8)
            second = service.reserve(1, 7, identity, 0, 16)
            if first is None or second is None:
                raise AssertionError("canonical resident retry lacked independent reservations")
            ensure(service.begin(first, 7, identity, 1, 2)
                   and service.begin(second, 7, identity, 15, 1),
                   "derived replacement refusal lacked independent accepted transfers")
            held = (service.reservation(0), service.reservation(1))
            pending = (service.pending(0), service.pending(1))
            before = list(service.writes)
            ensure(service.publish(replacement) is None and service.writes == before
                   and service._integer("last-version") == 1 and service.resident(1) is None
                   and (service.reservation(0), service.reservation(1)) == held
                   and (service.pending(0), service.pending(1)) == pending,
                   "derived replacement changed backing, version or accepted transfers")
            if isinstance(supplied, SwitchingResident) and isinstance(replacement, SwitchingResident):
                ensure(object.__getattribute__(supplied, "payload_reads") == 0
                       and object.__getattribute__(replacement, "payload_reads") == 0,
                       "publication inspected the derived payload before refusing its container")
            ensure(service.publish(rr.Resident(successor, successor_payload)) == 1,
                   "derived replacement refusal consumed the canonical successor's version")
            ensure(_finish(service, 0) == b"56" and _finish(service, 1) == b"F",
                   "derived publication or canonical replacement redirected retained transfers")
            ensure(service.close(first), "canonical predecessor close refused")
            current = service.reserve(0, 7, successor, 0, 16)
            if current is None:
                raise AssertionError("canonical successor retry lacked a reservation")
            ensure(service.read(current, 7, successor, 0, 16) == successor_payload
                   and service.read(second, 7, identity, 0, 16) == payload
                   and service.safe_backing() and service.traffic()["common"] == 0,
                   "canonical resident retries lost authenticated version bytes or traffic safety")


def _replacement_and_bounded_retirement() -> None:
    service, identity, handles = rr.fixture()
    ensure(service.begin(handles[0], 7, identity, 0, 16), "replacement cut lacked transfer")
    successor = replace(identity, version=2,
                        root=rr.authenticated_root("user-data", 1, b"abcdefghijklmnop"))
    new_slot = service.publish(rr.Resident(successor, b"abcdefghijklmnop"))
    ensure(new_slot is not None and new_slot != handles[0].slot, "replacement reused retained slot")
    ensure(_finish(service, 0) == b"0123456789ABCDEF", "accepted transfer rebound to new bytes")
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
    ensure(_finish(service, 0) == b"0123456789ABCDEF" and _finish(service, 1) == b"0123456789ABCDEF",
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
            ensure(_finish(service, 0) == b"0123456789ABCDEF",
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
            ensure(_finish(bad, 0) is None and bad.response(0) is None,
                   "old transfer returned replacement bytes")
        ensure(bad.read(bad_handles[0], 7, bad_identity, 0, 16) is None,
               "old reservation returned replacement bytes")


def _retained_byte_safety() -> None:
    for kind in ("system-image", "user-data"):
        for outstanding in (False, True):
            for construction in ("none", "premature-zeroize"):
                service, identity, handles = rr.fixture(kind, construction)
                for handle, offset, expected in ((handles[0], 1, b"12"), (handles[1], 14, b"EF")):
                    ensure(service.read(handle, 7, identity, offset, 2) == expected,
                           "zeroization control failed its independent retained-window payload")
                    if outstanding:
                        ensure(service.begin(handle, 7, identity, offset, 2),
                               "zeroization control lacked independent accepted transfers")
                ensure(service.safe_backing(), "unchanged retained version reported unsafe backing")
                complete, steps = service.retire(handles[0].slot, cooperative_holder=False)
                ensure(complete and steps <= service.bounds.retirement_steps,
                       "zeroization control failed to execute its bounded retirement cut")
                if construction == "none":
                    ensure(service.resident(handles[0].slot) is None and service.safe_backing()
                           and all(service.reservation(holder) is None and service.pending(holder) is None
                                   for holder in range(service.bounds.holders)),
                           "lawful retirement did not cancel authority before zeroization")
                else:
                    resident = service.resident(handles[0].slot)
                    ensure(resident is not None and resident.identity == identity
                           and resident.payload == bytes(16),
                           "premature zeroization did not retain identity while changing version bytes")
                    ensure(all(service.reservation(holder) is not None
                               for holder in range(service.bounds.holders)),
                           "zeroization defect omitted live reservation authority")
                    if outstanding:
                        # Isolate accepted-transfer retention from the reservation oracle.
                        service.operation = "external-control"
                        for holder in range(service.bounds.holders):
                            service._put(f"reservation.{holder}", None)
                        ensure(all(service.pending(holder) is not None
                                   for holder in range(service.bounds.holders)),
                               "zeroization defect omitted independent accepted transfers")
                    ensure(not service.safe_backing(),
                           "unchanged identity hid zeroization of a still-retained immutable version")
                ensure(service.traffic()["common"] == 0,
                       "retained-byte observation added common per-read writes")

        service, identity, handles = rr.fixture(kind)
        ensure(service.begin(handles[0], 7, identity, 16, 0)
               and service.begin(handles[1], 7, identity, 14, 2),
               "mutation control lacked empty and nonempty accepted transfers")
        resident = service.resident(handles[0].slot)
        if resident is None:
            raise AssertionError("mutation control lacked retained backing")
        service.operation = "external-control"
        service._put(f"backing.{handles[0].slot}", replace(resident, payload=b"0123456789ABCDE!"))
        ensure(not service.safe_backing(), "same-identity mutation escaped the retention oracle")
        ensure(_finish(service, 0) is None and _finish(service, 1) is None
               and service.response(0) is None and service.response(1) is None,
               "mutated version returned an empty or nonempty payload")

        # Zero-valued backing is lawful when its independently supplied root binds those bytes.
        service = rr.Service()
        zero_bytes = bytes(16)
        zero_identity = rr.Identity(1, 7, 1, 1, rr.authenticated_root(kind, 1, zero_bytes))
        ensure(service.publish(rr.Resident(zero_identity, zero_bytes)) is not None,
               "correctly authenticated zero-valued version refused publication")
        for holder in range(service.bounds.holders):
            handle = service.reserve(holder, 7, zero_identity, 0, 16)
            if handle is None:
                raise AssertionError("zero-valued control lacked independent holders")
            ensure(service.read(handle, 7, zero_identity, 0, 16) == bytes(16)
                   and service.read(handle, 7, zero_identity, 16, 0) == b""
                   and service.begin(handle, 7, zero_identity, 16, 0),
                   "zero-valued version lost its exact payload or empty boundary read")
        before = len(service.writes)
        ensure(service.safe_backing() and len(service.writes) == before
               and service.traffic()["common"] == 0,
               "read-only lifetime oracle rejected zero-valued bytes or added a modeled store")
        ensure(_finish(service, 0) == b"" and _finish(service, 1) == b"",
               "zero-valued version lost independently accepted empty completions")


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
            ensure(_finish(service, 0) is None and service.read(handle, 7, identity, 0, 16) is None,
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
                            "premature-reuse", "premature-zeroize", "counter-wrap", "holder-wait", "completion-rebind"},
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
    ensure(_finish(service, 0) == b"0123456789ABCDEF" and not service.renew(handle),
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


def _canonical_composition() -> None:
    class DerivedBounds(rr.Bounds):
        pass

    overrides: dict[str, int] = {}
    touched: list[str] = []
    bound_fields = set(asdict(rr.Bounds()))

    class DynamicBounds(rr.Bounds):
        @override
        def __getattribute__(self, name: str) -> object:
            if name in bound_fields:
                touched.append(name)
                if name in overrides:
                    return overrides[name]
            return object.__getattribute__(self, name)

    fixed = rr.Bounds(counter_limit=2, retention=1, renewals=0)
    dynamic = DynamicBounds(counter_limit=2, retention=1, renewals=0)
    ensure(dynamic.counter_limit == 2 and dynamic.renewals == 0,
           "dynamic composition lacked its initially admitted limits")
    overrides.update(counter_limit=3, renewals=1, holders=3)
    ensure(dynamic.counter_limit == 3 and dynamic.renewals == 1 and dynamic.holders == 3,
           "getter-backed composition did not widen its limits without replacing the container")

    for kind in ("system-image", "user-data"):
        service, identity, handles = rr.fixture(kind, bounds=fixed)
        ensure(service.begin(handles[0], 7, identity, 0, 16)
               and service.begin(handles[1], 7, identity, 4, 8),
               "canonical composition control lacked independent accepted transfers")
        pending = (service.pending(0), service.pending(1))
        held = (service.reservation(0), service.reservation(1))
        before = len(service.writes)
        classes = dict(service.classes)
        for supplied in (dynamic, DerivedBounds(), asdict(fixed), None, object()):
            touched.clear()
            try:
                rr.Service(cast("rr.Bounds", supplied))
            except ValueError:
                pass
            else:
                raise AssertionError("noncanonical composition declared a stored inventory")
            ensure(not touched, "composition refusal evaluated an overridden bound getter")
        ensure(service.bounds is fixed and dict(service.classes) == classes
               and len(service.writes) == before
               and (service.pending(0), service.pending(1)) == pending
               and (service.reservation(0), service.reservation(1)) == held,
               "refused composition changed fixed bounds, stored inventory or accepted transfers")
        ensure(_finish(service, 0) == b"0123456789ABCDEF"
               and _finish(service, 1) == b"456789AB" and not service.renew(handles[0]),
               "fixed composition lost exact payloads or widened its exhausted renewal policy")
        ensure(service.read(handles[0], 7, identity, 15, 1) == b"F"
               and service.read(handles[0], 7, identity, 15, 1) is None
               and service._integer("sequence.0") == 2,
               "getter-backed composition widened the canonical service's admitted read limit")
        ensure(service.reserve(2, 7, identity, 0, 16) is None
               and service.traffic()["common"] == 0 and service.safe_backing(),
               "composition refusal changed holder inventory, read traffic or retained backing")


def _source_bound_cli() -> None:
    output = StringIO()
    with redirect_stdout(output):
        code = cli.main(["--json"])
    report = json.loads(output.getvalue())
    ensure(code == 0 and report["scope"] == "finite Python host reference", "CLI scope or verdict differs")
    ensure(len(report["witnesses"]) == 8 and len(report["executed_python_controls"]) == 12,
           "CLI omitted executed witnesses or controls")
    ensure("tools/vos/cli/resident_reads.py" in report["sources"]
           and len(report["runtime"]["sha256"]) == 64 and report["remaining"],
           "report omitted runtime/source binding or unfinished qualification")


def cases() -> list[Case]:
    return [Case("resident two-session payload and complete traffic witness", _inhabited_traffic),
            Case("resident exact identity and every-read authentication", _identity_and_authentication),
            Case("resident integral intervals and holder refusals", _integral_read_intervals),
            Case("resident integral handle fields preserve accepted transfers", _integral_handle_fields),
            Case("resident canonical handles refuse equality-spoofing containers", _canonical_handle_container),
            Case("resident integral supplied identities and caller domains", _integral_supplied_identities),
            Case("resident canonical root identities preserve accepted transfers", _canonical_root_fields),
            Case("resident current authority and admitted-transfer cuts", _authority_and_lifecycle_cuts),
            Case("resident exact request completions preserve successor transfers", _completion_request_binding),
            Case("resident exact integer backing slots preserve accepted transfers", _integral_backing_slots),
            Case("resident immutable backing refuses aliases before publication", _immutable_backing_publication),
            Case("resident stable containers preserve authenticated retained bytes", _stable_resident_container),
            Case("resident retained version and holder-independent retirement", _replacement_and_bounded_retirement),
            Case("resident finite metadata backing transfer and counter refusals", _resource_limits),
            Case("resident exact integer composition and finite boundary controls", _integral_composition),
            Case("resident reused slot preserves exact backing identity", _reused_slot_identity),
            Case("resident retained version refuses premature zeroization", _retained_byte_safety),
            Case("resident closed predecessor capacity and bounded recovery", _closed_predecessor_capacity),
            Case("resident executed defects and complete modeled observer", _executed_controls_and_observer),
            Case("resident frozen stored inventory refuses hidden writers", _frozen_stored_inventory),
            Case("resident fixed composition preserves admitted resource limits", _frozen_composition),
            Case("resident canonical composition refuses getter-backed limits", _canonical_composition),
            Case("resident source-bound CLI scope and evidence", _source_bound_cli)]
