# SPDX-License-Identifier: Apache-2.0
"""Q44's finite host reference; no storage target or machine receipt is supplied.

Every modeled stored cell is declared before execution and every store goes through
_put, including stores of unchanged values. The observer is an external harness,
not a trace of Python memory stores. Authentication uses a trusted fixture digest;
it does not implement generation admission, signatures or the storage Merkle tree.
"""

import hashlib
import sys
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from vos import receipts

if TYPE_CHECKING:
    from collections.abc import Mapping

type Kind = Literal["system-image", "user-data"]
type WriteClass = Literal["common", "session-private", "spsc"]
type Defect = Literal["none", "common-counter", "replacement-touch", "hidden-reacquire",
                      "wrong-domain", "wrong-root", "no-auth", "old-rebind",
                      "premature-reuse", "counter-wrap", "holder-wait"]


@dataclass(frozen=True)
class Bounds:
    backing_bytes: int = 32
    residents: int = 3
    holders: int = 2
    request_bytes: int = 16
    retention: int = 4
    renewals: int = 1
    predecessors: int = 1
    counter_limit: int = 15

    def __post_init__(self) -> None:
        if (any(type(getattr(self, field.name)) is not int for field in fields(self))
                or not 2 <= self.holders <= 4 or not 2 <= self.residents <= 4
                or not 1 <= self.request_bytes <= self.backing_bytes <= 64
                or not 1 <= self.retention <= self.counter_limit <= 255
                or not 0 <= self.renewals <= 4
                or not 0 <= self.predecessors < self.residents):
            raise ValueError("outside the finite resident reference bounds")

    @property
    def retirement_steps(self) -> int:
        return 2 * self.holders + 4


DEFAULT_BOUNDS = Bounds()


@dataclass(frozen=True)
class Root:
    kind: Kind
    generation: int
    digest: str


@dataclass(frozen=True)
class Identity:
    owner: int
    domain: int
    object_id: int
    version: int
    root: Root


@dataclass(frozen=True)
class Resident:
    identity: Identity
    payload: bytes
    accepting: bool = True


@dataclass(frozen=True)
class Handle:
    token: int
    boot: int
    holder: int
    slot: int
    identity: Identity
    start: int
    length: int


@dataclass(frozen=True)
class Reservation:
    handle: Handle
    expires: int
    renewed: int = 0


@dataclass(frozen=True)
class Request:
    handle: Handle
    caller_domain: int
    identity: Identity
    offset: int
    length: int
    sequence: int


type Value = int | bool | bytes | Resident | Reservation | Request | None


@dataclass(frozen=True)
class Write:
    operation: str
    cell: str
    classification: WriteClass
    value: Value


def authenticated_root(kind: Kind, generation: int, payload: bytes) -> Root:
    """Trusted known-answer fixture input, separate from read's comparison."""
    return Root(kind, generation, hashlib.sha256(payload).hexdigest())


class Service:
    """One owner, one logical object, a closed finite holder/backing inventory.

    One outstanding transfer per holder is the SPSC capacity. Metadata capacity is
    exactly one reservation per holder; backing and quarantine capacity is residents.
    The modeled barrier is deliberately separate from accepted scalar observations.
    A caller needing an unavailable barrier receives bounded refusal with backing
    still charged. No host observation authorizes physical backing reuse.
    """

    __slots__ = ("_bounds", "_cells", "_classes", "defect", "operation", "writes")

    def __init__(self, bounds: Bounds = DEFAULT_BOUNDS, defect: Defect = "none") -> None:
        self._bounds = bounds
        self.defect = defect
        self._cells: dict[str, Value] = {}
        self._classes: dict[str, WriteClass] | MappingProxyType[str, WriteClass] = {}
        self.writes: list[Write] = []
        self.operation = "initialization"
        for name, value in (("next-token", 0), ("last-version", 0), ("boot", 0),
                            ("clock", 0), ("generation", 1), ("current", None),
                            ("retired", 0), ("counter", 0), ("recency", 0)):
            self._declare(name, value, "common")
        for slot in range(bounds.residents):
            self._declare(f"backing.{slot}", None, "common")
        for holder in range(bounds.holders):
            self._declare(f"reservation.{holder}", None, "common")
            self._declare(f"grant.{holder}", True, "common")
            for name, value in (("pending", None), ("sequence", 0), ("reads", 0),
                                ("authentications", 0)):
                self._declare(f"{name}.{holder}", value, "session-private")
            self._declare(f"request.{holder}", None, "spsc")
            self._declare(f"response.{holder}", None, "spsc")
        self._classes = MappingProxyType(self._classes)

    @property
    def bounds(self) -> Bounds:
        """Composition stays fixed beside the stored inventory it declared."""
        return self._bounds

    @property
    def classes(self) -> Mapping[str, WriteClass]:
        """Stored inventory is read-only once initialization has declared every cell."""
        return self._classes

    def _declare(self, cell: str, value: Value, classification: WriteClass) -> None:
        if not isinstance(self._classes, dict) or cell in self._classes:
            raise ValueError(f"stored inventory declaration is closed or duplicate: {cell}")
        self._cells[cell] = value
        self._classes[cell] = classification

    def _put(self, cell: str, value: Value) -> None:
        if cell not in self.classes:
            raise ValueError(f"undeclared stored cell: {cell}")
        self.writes.append(Write(self.operation, cell, self.classes[cell], value))
        self._cells[cell] = value

    def _integer(self, cell: str) -> int:
        value = self._cells[cell]
        if not isinstance(value, int):
            raise TypeError(f"not an integer cell: {cell}")
        return value

    def resident(self, slot: int) -> Resident | None:
        # Stop/retire use this lookup before stores; cell-name aliases are not slots.
        if type(slot) is not int or not 0 <= slot < self.bounds.residents:
            return None
        value = self._cells.get(f"backing.{slot}")
        return value if isinstance(value, Resident) else None

    def reservation(self, holder: int) -> Reservation | None:
        value = self._cells.get(f"reservation.{holder}")
        return value if isinstance(value, Reservation) else None

    def pending(self, holder: int) -> Request | None:
        value = self._cells.get(f"pending.{holder}")
        return value if isinstance(value, Request) else None

    def response(self, holder: int) -> bytes | None:
        value = self._cells.get(f"response.{holder}")
        return value if isinstance(value, bytes) else None

    def _holder(self, holder: int) -> bool:
        return type(holder) is int and 0 <= holder < self.bounds.holders

    def _integral_identity(self, identity: Identity) -> bool:
        # Validate both the published and supplied identity before equality or storage.
        return (type(identity) is Identity and type(identity.root) is Root
                and type(identity.root.kind) is str
                and identity.root.kind in ("system-image", "user-data")
                and type(identity.root.digest) is str and len(identity.root.digest) == 64
                and all(character in "0123456789abcdef" for character in identity.root.digest)
                and all(type(value) is int for value in (
                    identity.owner, identity.domain, identity.object_id,
                    identity.version, identity.root.generation)))

    def _integral_handle(self, handle: Handle) -> bool:
        # Dataclass equality otherwise aliases bool/float fields to integer authority.
        return (isinstance(handle, Handle) and self._integral_identity(handle.identity)
                and all(type(value) is int for value in (
                    handle.token, handle.boot, handle.holder, handle.slot, handle.start, handle.length)))

    def _valid(self, handle: Handle, domain: int, identity: Identity) -> bool:
        if (not self._integral_handle(handle) or type(domain) is not int
                or not self._integral_identity(identity)):
            return False
        held = self.reservation(handle.holder)
        resident = self.resident(handle.slot)
        domain_ok = domain == handle.identity.domain or self.defect == "wrong-domain"
        supplied = identity
        if self.defect == "wrong-root":
            supplied = replace(identity, root=handle.identity.root)
        return (self._holder(handle.holder) and held is not None and held.handle == handle
                and resident is not None and resident.accepting
                and resident.identity == handle.identity and supplied == handle.identity
                and domain_ok and self._cells[f"grant.{handle.holder}"] is True
                and handle.boot == self._integer("boot")
                and self._integer("clock") < held.expires
                and (handle.identity.root.kind != "system-image"
                     or handle.identity.root.generation == self._integer("generation")))

    def publish(self, resident: Resident) -> int | None:
        """Fresh version only. Replacement retains predecessor bytes and identity."""
        self.operation = "replacement"
        # Retain only immutable byte values whose length and slicing cannot be overridden.
        # Mutable buffers would let callers change backing and its charge outside _put.
        if type(resident.payload) is not bytes or not self._integral_identity(resident.identity):
            return None
        version = resident.identity.version
        live = [slot for slot in range(self.bounds.residents) if self.resident(slot) is not None]
        # Every existing resident becomes a predecessor of the newly published version,
        # including closed backing whose retirement barrier is still unavailable.
        if ((resident.identity.owner, resident.identity.domain, resident.identity.object_id) != (1, 7, 1)
                or not 1 <= resident.identity.root.generation <= self.bounds.counter_limit
                or not 1 <= version <= self.bounds.counter_limit
                or version <= self._integer("last-version") or not resident.accepting
                or not resident.payload or len(resident.payload) > self.bounds.backing_bytes
                or len(live) > self.bounds.predecessors
                or sum(len(item.payload) for slot in live
                       if (item := self.resident(slot)) is not None) + len(resident.payload)
                > self.bounds.backing_bytes):
            return None
        for slot in range(self.bounds.residents):
            if self.resident(slot) is None:
                self._put(f"backing.{slot}", resident)
                self._put("current", slot)
                self._put("last-version", version)
                return slot
        return None

    def reserve(self, holder: int, domain: int, identity: Identity,
                start: int, length: int) -> Handle | None:
        self.operation = "admission"
        slot = self._cells["current"]
        if (not isinstance(slot, int) or not self._holder(holder)
                or type(domain) is not int or not self._integral_identity(identity)):
            return None
        resident = self.resident(slot)
        if (resident is None or not resident.accepting or resident.identity != identity
                or domain != identity.domain or self.reservation(holder) is not None
                or self._cells[f"grant.{holder}"] is not True
                or type(start) is not int or type(length) is not int
                or start < 0 or length <= 0 or start + length > len(resident.payload)
                or self._integer("clock") + self.bounds.retention > self.bounds.counter_limit
                or (identity.root.kind == "system-image"
                    and identity.root.generation != self._integer("generation"))):
            return None
        token = self._integer("next-token") + 1
        if token > self.bounds.counter_limit:
            if self.defect != "counter-wrap":
                return None
            token = 1
        handle = Handle(token, self._integer("boot"), holder, slot, identity, start, length)
        self._put("next-token", token)
        self._put(f"reservation.{holder}", Reservation(
            handle, self._integer("clock") + self.bounds.retention))
        return handle

    def begin(self, handle: Handle, domain: int, identity: Identity,
              offset: int, length: int) -> bool:
        self.operation = "read"
        if (not self._integral_handle(handle) or type(domain) is not int
                or not self._integral_identity(identity) or not self._holder(handle.holder)):
            return False
        holder = handle.holder
        self._put(f"response.{holder}", None)
        if (not self._valid(handle, domain, identity) or self.pending(holder) is not None
                or type(offset) is not int or type(length) is not int
                or offset < 0 or not 0 <= length <= self.bounds.request_bytes
                or offset + length > handle.length
                or self._integer(f"sequence.{holder}") >= self.bounds.counter_limit):
            return False
        if self.defect == "common-counter":
            self._put("counter", self._integer("counter") + 1)
            self._put("counter", self._integer("counter") - 1)
        elif self.defect == "replacement-touch":
            self._put("recency", self._integer("recency") + 1)
        elif self.defect == "hidden-reacquire":
            held = self.reservation(holder)
            self._put(f"reservation.{holder}", None)
            self._put(f"reservation.{holder}", held)
        sequence = self._integer(f"sequence.{holder}") + 1
        request = Request(handle, domain, identity, offset, length, sequence)
        self._put(f"sequence.{holder}", sequence)
        self._put(f"pending.{holder}", request)
        self._put(f"request.{holder}", request)
        return True

    def finish(self, holder: int) -> bytes | None:
        """Recheck current authority and authenticate actual bytes before publication."""
        self.operation = "read"
        if not self._holder(holder):
            return None
        request = self.pending(holder)
        self._put(f"response.{holder}", None)
        if request is None:
            return None
        self._put(f"pending.{holder}", None)
        self._put(f"request.{holder}", None)
        if not self._valid(request.handle, request.caller_domain, request.identity):
            return None
        resident = self.resident(request.handle.slot)
        if self.defect == "old-rebind" and isinstance(self._cells["current"], int):
            resident = self.resident(self._integer("current"))
        if resident is None:
            return None
        authenticated = hashlib.sha256(resident.payload).hexdigest() == resident.identity.root.digest
        self._put(f"authentications.{holder}", self._integer(f"authentications.{holder}") + 1)
        if not authenticated and self.defect != "no-auth":
            return None
        start = request.handle.start + request.offset
        payload = resident.payload[start:start + request.length]
        self._put(f"reads.{holder}", self._integer(f"reads.{holder}") + 1)
        self._put(f"response.{holder}", payload)
        return payload

    def read(self, handle: Handle, domain: int, identity: Identity,
             offset: int, length: int) -> bytes | None:
        return self.finish(handle.holder) if self.begin(handle, domain, identity, offset, length) else None

    def renew(self, handle: Handle) -> bool:
        self.operation = "renewal"
        if not self._integral_handle(handle):
            return False
        held = self.reservation(handle.holder)
        if (held is None or not self._valid(handle, handle.identity.domain, handle.identity)
                or held.renewed >= self.bounds.renewals
                or self._integer("clock") + self.bounds.retention > self.bounds.counter_limit):
            return False
        self._put(f"reservation.{handle.holder}", replace(
            held, expires=self._integer("clock") + self.bounds.retention, renewed=held.renewed + 1))
        return True

    def advance_clock(self) -> bool:
        self.operation = "clock"
        value = self._integer("clock")
        if value >= self.bounds.counter_limit:
            return False
        self._put("clock", value + 1)
        return True

    def revoke(self, holder: int) -> bool:
        self.operation = "revocation"
        if not self._holder(holder):
            return False
        self._put(f"grant.{holder}", False)
        return True

    def close(self, handle: Handle) -> bool:
        self.operation = "close"
        if not self._integral_handle(handle):
            return False
        held = self.reservation(handle.holder)
        if held is None or held.handle != handle:
            return False
        self._put(f"reservation.{handle.holder}", None)
        self._put(f"pending.{handle.holder}", None)
        self._put(f"request.{handle.holder}", None)
        self._put(f"response.{handle.holder}", None)
        return True

    def generation_change(self) -> bool:
        self.operation = "generation"
        generation = self._integer("generation")
        if generation >= self.bounds.counter_limit:
            return False
        self._put("generation", generation + 1)
        return True

    def stop(self, slot: int) -> bool:
        """Eviction/delete/teardown closes admission before any retirement step."""
        self.operation = "stop"
        resident = self.resident(slot)
        if resident is None:
            return False
        self._put(f"backing.{slot}", replace(resident, accepting=False))
        if self._cells["current"] == slot:
            self._put("current", None)
        return True

    def retire(self, slot: int, *, barrier_available: bool = True,
               cooperative_holder: bool = False) -> tuple[bool, int]:
        """Finite abstract sweep/zeroization, never a physical reusable-backing receipt."""
        resident = self.resident(slot)
        if resident is None:
            return False, 0
        self.stop(slot)
        self.operation = "retirement"
        steps = 1
        if self.defect == "holder-wait" and not cooperative_holder:
            return False, self.bounds.retirement_steps + 1
        if self.defect == "premature-reuse":
            self._put(f"backing.{slot}", None)
            return True, steps
        for holder in range(self.bounds.holders):
            request = self.pending(holder)
            if request is not None and request.handle.slot == slot:
                self._put(f"pending.{holder}", None)
                self._put(f"request.{holder}", None)
                self._put(f"response.{holder}", None)
            steps += 1
            held = self.reservation(holder)
            if held is not None and held.handle.slot == slot:
                self._put(f"reservation.{holder}", None)
            steps += 1
        if not barrier_available:
            return False, steps
        self._put("retired", self._integer("retired") | (1 << slot))
        steps += 1
        self._put(f"backing.{slot}", replace(resident, accepting=False,
                                             payload=bytes(len(resident.payload))))
        steps += 1
        self._put(f"backing.{slot}", None)
        return True, steps + 1

    def crash(self) -> bool:
        """Recovery retains data only; old volatile handles and replies never survive."""
        self.operation = "crash"
        boot = self._integer("boot")
        for holder in range(self.bounds.holders):
            for name in ("reservation", "pending", "request", "response"):
                self._put(f"{name}.{holder}", None)
            self._put(f"grant.{holder}", False)
        for slot in range(self.bounds.residents):
            resident = self.resident(slot)
            if resident is not None:
                self._put(f"backing.{slot}", replace(resident, accepting=False))
        self._put("current", None)
        if boot >= self.bounds.counter_limit:
            return False
        self._put("boot", boot + 1)
        return True

    def safe_backing(self) -> bool:
        """Live metadata and transfers retain the exact identity at their backing slot."""
        def retained(handle: Handle) -> bool:
            resident = self.resident(handle.slot)
            return resident is not None and resident.identity == handle.identity

        return all((held is None or retained(held.handle))
                   and (request is None or retained(request.handle))
                   for holder in range(self.bounds.holders)
                   for held, request in [(self.reservation(holder), self.pending(holder))])

    def traffic(self) -> dict[str, int]:
        return {classification: sum(write.operation == "read"
                                    and write.classification == classification for write in self.writes)
                for classification in ("common", "session-private", "spsc")}


def fixture(kind: Kind = "user-data", defect: Defect = "none",
            bounds: Bounds = DEFAULT_BOUNDS) -> tuple[Service, Identity, tuple[Handle, Handle]]:
    payload = b"0123456789ABCDEF"
    identity = Identity(1, 7, 1, 1, authenticated_root(kind, 1, payload))
    service = Service(bounds, defect)
    if service.publish(Resident(identity, payload)) is None:
        raise ValueError("fixture backing refused")
    first = service.reserve(0, 7, identity, 0, 16)
    second = service.reserve(1, 7, identity, 0, 16)
    if first is None or second is None:
        raise ValueError("fixture is uninhabited")
    return service, identity, (first, second)


def witness(reads_per_holder: int, kind: Kind = "user-data",
            defect: Defect = "none") -> dict[str, int | str | bool | dict[str, int]]:
    if not 1 <= reads_per_holder <= 8:
        raise ValueError("outside the declared read witness range")
    service, identity, handles = fixture(kind, defect)
    returned = 0
    successful = 0
    for _ in range(reads_per_holder):
        for handle in handles:
            payload = service.read(handle, 7, identity, 0, 16)
            if payload != b"0123456789ABCDEF":
                raise ValueError("independent expected payload disagrees")
            returned += len(payload)
            successful += 1
    traffic = service.traffic()
    events = sum(write.operation == "admission" and write.cell.startswith("reservation.")
                 for write in service.writes)
    return {"kind": kind, "N": successful, "reservation_events": events,
            "bytes_returned": returned, "writes": traffic,
            "accepted": traffic["common"] == 0 and successful == reads_per_holder * 2}


def controls() -> dict[str, bool]:
    """Executed Python defective constructions; True means the intended oracle killed it."""
    verdicts: dict[str, bool] = {}
    for defect in ("common-counter", "replacement-touch", "hidden-reacquire"):
        verdicts[defect] = witness(3, defect=defect)["accepted"] is False
    for defect in ("wrong-domain", "wrong-root", "no-auth"):
        passing, identity, handles = fixture()
        bad, bad_identity, bad_handles = fixture(defect=defect)
        domain = 8 if defect == "wrong-domain" else 7
        different_digest = authenticated_root("user-data", 1, b"different root").digest
        supplied = replace(identity, root=replace(identity.root, digest=different_digest)) if defect == "wrong-root" else identity
        bad_supplied = replace(bad_identity, root=replace(bad_identity.root, digest=different_digest)) if defect == "wrong-root" else bad_identity
        if defect == "no-auth":
            for service, handle in ((passing, handles[0]), (bad, bad_handles[0])):
                resident = service.resident(handle.slot)
                if resident is None:
                    raise ValueError("missing corruption backing")
                service.operation = "external-corruption"
                service._put(f"backing.{handle.slot}", replace(resident, payload=b"X" * 16))
        baseline = passing.read(handles[0], domain, supplied, 0, 16)
        mutant = bad.read(bad_handles[0], domain, bad_supplied, 0, 16)
        verdicts[defect] = baseline is None and mutant is not None
    for defect in ("old-rebind", "premature-reuse", "holder-wait"):
        observations: list[bool] = []
        for construction in ("none", defect):
            service, identity, handles = fixture(defect=construction)
            if defect == "old-rebind":
                new = replace(identity, version=2, root=authenticated_root("user-data", 1, b"X" * 16))
                if service.publish(Resident(new, b"X" * 16)) is None:
                    raise ValueError("replacement control did not execute")
                observations.append(service.read(handles[0], 7, identity, 0, 16) == b"0123456789ABCDEF")
            else:
                if not service.begin(handles[0], 7, identity, 0, 16):
                    raise ValueError("retirement control lacked an accepted transfer")
                complete, steps = service.retire(handles[0].slot, cooperative_holder=False)
                if defect == "premature-reuse":
                    successor = replace(identity, version=2,
                                        root=authenticated_root("user-data", 1, b"X" * 16))
                    if service.publish(Resident(successor, b"X" * 16)) != handles[0].slot:
                        raise ValueError("same-slot reuse control did not execute")
                observations.append(complete and steps <= service.bounds.retirement_steps
                                    and service.safe_backing())
        verdicts[defect] = observations == [True, False]
    unique: list[bool] = []
    for construction in ("none", "counter-wrap"):
        bounds = Bounds(counter_limit=2, retention=1)
        service = Service(bounds, construction)
        payload = b"0123456789ABCDEF"
        identity = Identity(1, 7, 1, 1, authenticated_root("user-data", 1, payload))
        service.publish(Resident(identity, payload))
        tokens: list[int] = []
        for _ in range(3):
            handle = service.reserve(0, 7, identity, 0, 16)
            if handle is not None:
                tokens.append(handle.token)
                service.close(handle)
        unique.append(len(tokens) == len(set(tokens)))
    verdicts["counter-wrap"] = unique == [True, False]
    return verdicts


def qualify(root: Path) -> dict[str, object]:
    """Source-bound behavioral report, deliberately without a target acceptance field."""
    inputs = receipts.snapshot(root, [root / name for name in (
        "tools/vos/resident_reads.py", "tools/vos/cli/resident_reads.py", "tools/tests/test_resident_reads.py",
        "tools/resident-reads/README.md", "docs/implementation/contracts/resident-object-reads.md")])
    cases = [witness(count, kind) for kind in ("system-image", "user-data") for count in (1, 2, 4, 8)]
    killed = controls()
    if not all(case["accepted"] for case in cases) or not all(killed.values()):
        raise ValueError("finite witness or an executed defect control failed")
    if inputs != receipts.snapshot(root, [root / name for name in inputs]):
        raise ValueError("reference sources changed during execution")
    return {"scope": "finite Python host reference", "sources": inputs,
            "runtime": {"executable": str(Path(sys.executable).resolve()),
                        "sha256": receipts.digest(Path(sys.executable)), "version": sys.version},
            "bounds": asdict(Bounds()), "retirement_steps": Bounds().retirement_steps,
            "stored_cells": dict(Service().classes), "witnesses": cases,
            "executed_python_controls": killed,
            "remaining": ["locked reference theorem and assumption audit",
                          "accepted scalar producer correspondence and reusable-backing evidence",
                          "concrete storage authentication/system-image/user-data target join",
                          "compiled defect controls and complete target write observation"]}
