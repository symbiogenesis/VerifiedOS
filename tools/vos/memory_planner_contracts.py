# SPDX-License-Identifier: Apache-2.0
"""Extract placement conflicts from bounded component protocol contracts.

This is an executable contract IR, not a Vela parser or a proved compiler pass.
Every declared control-flow alternative is interpreted; a budget refusal never
returns a partial conflict graph. Storage remains occupied after lexical release
until retained values, authority, accepted device work, the post-revocation sweep
and the scrub have all cleared. Each terminal outcome must return every slot.

``MemoryPlannerContracts.v`` proves the corresponding graph and reuse rules over
its mathematical model. Python-to-Gallina refinement, completeness of a caller's
branches and target enforcement of events remain separate obligations.
"""

import copy
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import combinations, product
from typing import Any

SCHEMA = "memory-component-contract-v1"
VERSION = "memory-planner-contracts-v1"
LIMIT = (1 << 63) - 1
OUTCOMES = frozenset({"normal", "exception", "cancel", "timeout"})
SIMPLE = frozenset({"acquire", "use", "release", "retain", "drop", "revoke",
                    "sweep", "scrub", "barrier"})
ASSUMPTIONS = (
    "The supplied contract includes every program branch and protocol outcome.",
    "Each event is enforced by the target; device completion means all accepted accesses ended.",
    "Revocation stops authority, sweep clears representations after completion, and scrub erases bytes.",
    "Requests reuse a slot only after a terminal outcome drains it; simultaneous requests fit the slot bound.",
    "Object sizes and placement constraints bound every execution represented by this contract.",
    "The Python extractor and placement checker are not extracted from the Gallina proof.",
)


class ContractError(ValueError):
    """Malformed contract or a declared path that violates its resource protocol."""


class UnsupportedContractError(ContractError):
    """Unsupported input or exhausted extraction budget; no safety verdict exists."""


@dataclass(frozen=True)
class Limits:
    """Deterministic extraction bounds, including pair-generation work."""

    max_paths: int = 4096
    max_events: int = 100000
    max_depth: int = 64
    max_objects: int = 1024
    max_pair_checks: int = 1000000
    max_expansion_work: int = 1000000


@dataclass
class _ExpansionBudget:
    """Charge projected path and annotation copies before allocating them."""

    limit: int
    used: int = 0

    def charge(self, work: int) -> None:
        if work > self.limit - self.used:
            raise UnsupportedContractError("control expansion exceeds max_expansion_work budget")
        self.used += work


@dataclass(frozen=True)
class Path:
    events: tuple[dict[str, Any], ...] = ()
    labels: tuple[str, ...] = ()


@dataclass
class Lease:
    """Occupancy includes every hazard until the checked reuse barrier."""

    held: bool = True
    retained: bool = False
    authority: bool = True
    devices: set[str] = field(default_factory=set)
    swept: bool = False
    scrubbed: bool = False

    def no_users(self) -> bool:
        return not (self.held or self.retained or self.authority or self.devices)


def _object(raw: object, where: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or any(not isinstance(k, str) for k in raw):
        raise ContractError(f"{where}: expected an object with string keys")
    return raw


def _fields(raw: dict[str, Any], required: set[str], optional: set[str], where: str) -> None:
    missing = required - raw.keys()
    extra = raw.keys() - required - optional
    if missing:
        raise ContractError(f"{where}: missing fields {sorted(missing)}")
    if extra:
        raise UnsupportedContractError(f"{where}: unsupported fields {sorted(extra)}")


def _list(raw: object, where: str) -> list[Any]:
    if not isinstance(raw, list):
        raise ContractError(f"{where}: expected a list")
    return raw


def _name(raw: object, where: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ContractError(f"{where}: expected a nonempty string")
    return raw


def _nat(raw: object, where: str, minimum: int = 0) -> int:
    if type(raw) is not int or not minimum <= raw <= LIMIT:
        raise ContractError(f"{where}: expected an integer in [{minimum}, {LIMIT}]")
    return raw


def _digest(raw: object) -> str:
    return hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _snapshot(raw: object, limits: Limits, budget: _ExpansionBudget) -> dict[str, Any]:
    """Bound JSON traversal before the recursive snapshot copy can allocate it.

    Iterator frames keep traversal storage proportional to nesting, not the input
    width. Visiting a container charges its width before descending. The physical
    nesting bound also protects deepcopy, independently of the IR nesting limit.
    """
    nesting_limit = min(4 * limits.max_depth + 16, 256)
    stack: list[tuple[Iterator[object], int]] = [(iter((raw,)), 0)]
    while stack:
        iterator, depth = stack[-1]
        try:
            value = next(iterator)
        except StopIteration:
            stack.pop()
            continue
        budget.charge(1)
        if depth > nesting_limit:
            raise UnsupportedContractError("contract JSON nesting exceeds bounded snapshot depth")
        if type(value) is dict:
            budget.charge(len(value))
            stack.append((iter(value.values()), depth + 1))
        elif type(value) is list:
            budget.charge(len(value))
            stack.append((iter(value), depth + 1))
        elif type(value) not in (str, int, float, bool, type(None)):
            raise ContractError("contract must contain only JSON values")
    try:
        return copy.deepcopy(_object(raw, "contract"))
    except RecursionError as exc:
        raise UnsupportedContractError("contract exceeds snapshot recursion capacity") from exc


def _guard(paths: list[Path], limits: Limits, budget: _ExpansionBudget) -> list[Path]:
    budget.charge(len(paths))
    if len(paths) > limits.max_paths:
        raise UnsupportedContractError("branch expansion exceeds max_paths budget; no partial graph emitted")
    if sum(len(path.events) for path in paths) > limits.max_events:
        raise UnsupportedContractError("branch expansion exceeds max_events budget; no partial graph emitted")
    return paths


def _join(left: list[Path], right: list[Path], limits: Limits,
          budget: _ExpansionBudget) -> list[Path]:
    count = len(left) * len(right)
    events = sum(len(p.events) for p in left) * len(right)
    events += sum(len(p.events) for p in right) * len(left)
    if count > limits.max_paths or events > limits.max_events:
        raise UnsupportedContractError("control-flow product exceeds extraction budget")
    labels = sum(len(p.labels) for p in left) * len(right)
    labels += sum(len(p.labels) for p in right) * len(left)
    budget.charge(count + events + labels)
    return [Path(a.events + b.events, a.labels + b.labels) for a, b in product(left, right)]


def _annotate(paths: list[Path], label: str, budget: _ExpansionBudget) -> list[Path]:
    budget.charge(sum(len(p.labels) + 2 for p in paths))
    return [Path(p.events, (label, *p.labels)) for p in paths]


def _expand(nodes: object, limits: Limits, budget: _ExpansionBudget,
            depth: int = 0) -> list[Path]:
    if depth > limits.max_depth:
        raise UnsupportedContractError("control-flow nesting exceeds max_depth")
    budget.charge(1)
    paths = [Path()]
    for raw in _list(nodes, "body"):
        budget.charge(1)
        node = _object(raw, "instruction")
        op = _name(node.get("op"), "instruction.op")
        variants: list[Path] = []
        if op == "choice":
            _fields(node, {"op", "branches"}, set(), op)
            labels: set[str] = set()
            for raw_branch in _list(node["branches"], "choice.branches"):
                branch = _object(raw_branch, "branch")
                _fields(branch, {"label", "body"}, set(), "branch")
                label = _name(branch["label"], "branch.label")
                if label in labels:
                    raise ContractError(f"duplicate branch label: {label}")
                labels.add(label)
                expanded = _expand(branch["body"], limits, budget, depth + 1)
                variants.extend(_annotate(expanded, label, budget))
                _guard(variants, limits, budget)
            if not variants:
                raise ContractError("choice requires at least one branch")
        elif op == "repeat":
            _fields(node, {"op", "min", "max", "body"}, set(), op)
            low, high = _nat(node["min"], "repeat.min"), _nat(node["max"], "repeat.max")
            if low > high:
                raise ContractError("repeat.min exceeds repeat.max")
            if high > limits.max_events or high - low + 1 > limits.max_paths:
                raise UnsupportedContractError("repeat exceeds extraction budget")
            one = _expand(node["body"], limits, budget, depth + 1)
            repeated = [Path()]
            for count in range(high + 1):
                budget.charge(1)
                if count >= low:
                    variants.extend(_annotate(repeated, f"repeat={count}", budget))
                    _guard(variants, limits, budget)
                if count < high:
                    repeated = _join(repeated, one, limits, budget)
        else:
            if op in SIMPLE:
                _fields(node, {"op", "object"}, set(), op)
                _name(node["object"], f"{op}.object")
            elif op in {"submit", "complete"}:
                _fields(node, {"op", "object", "token"}, set(), op)
                _name(node["object"], f"{op}.object")
                _name(node["token"], f"{op}.token")
            elif op == "finish":
                _fields(node, {"op", "outcome"}, set(), op)
                if _name(node["outcome"], "finish.outcome") not in OUTCOMES:
                    raise UnsupportedContractError("finish.outcome: unsupported protocol outcome")
            else:
                raise UnsupportedContractError(f"unsupported operation: {op}")
            variants = [Path((copy.deepcopy(node),))]
        paths = _join(paths, variants, limits, budget)
    return _guard(paths, limits, budget)


def _step(event: dict[str, Any], live: dict[str, Lease], tokens: dict[str, str],
          names: set[str]) -> str | None:
    op = event["op"]
    if op == "finish":
        if live or tokens:
            raise ContractError("terminal outcome retains occupied storage or accepted device work")
        return _name(event["outcome"], "finish.outcome")
    name = event["object"]
    if name not in names:
        raise ContractError(f"unknown object: {name}")
    if op == "acquire":
        if name in live:
            raise ContractError(f"{name}: reacquired before its safe-reuse barrier")
        live[name] = Lease()
        return None
    if name not in live:
        raise ContractError(f"{name}: {op} without an active lease")
    lease = live[name]
    if op in {"use", "submit", "retain"}:
        if not lease.authority or not (lease.held or lease.retained):
            raise ContractError(f"{name}: {op} without live authority and a value holder")
        if op == "submit":
            token = event["token"]
            if token in tokens:
                raise ContractError(f"duplicate outstanding device token: {token}")
            tokens[token] = name
            lease.devices.add(token)
        if op == "retain":
            if lease.retained:
                raise UnsupportedContractError(f"{name}: multiple retained holders need a richer contract")
            lease.retained = True
    elif op == "release":
        if not lease.held:
            raise ContractError(f"{name}: double lexical release")
        lease.held = False
    elif op == "drop":
        if not lease.retained:
            raise ContractError(f"{name}: drop without a retained value")
        lease.retained = False
    elif op == "complete":
        token = event["token"]
        if tokens.get(token) != name or token not in lease.devices:
            raise ContractError(f"{name}: unmatched device completion {token}")
        del tokens[token]
        lease.devices.remove(token)
    elif op == "revoke":
        if lease.held or not lease.authority:
            raise ContractError(f"{name}: revocation requires lexical release and live authority")
        lease.authority = False
    elif op in {"sweep", "scrub", "barrier"}:
        if not lease.no_users():
            raise ContractError(f"{name}: {op} before holders, authority and device work drain")
        if op == "sweep":
            lease.swept = True
        elif op == "scrub":
            if not lease.swept:
                raise ContractError(f"{name}: scrub before the post-completion revocation sweep")
            lease.scrubbed = True
        else:
            if not lease.swept or not lease.scrubbed:
                raise ContractError(f"{name}: reuse barrier requires sweep and scrub")
            del live[name]
    return None


def _declarations(contract: dict[str, Any], limits: Limits) -> tuple[list[dict[str, Any]],
                                                                    list[dict[str, Any]], int]:
    pools: list[dict[str, Any]] = []
    pool_ids: set[str] = set()
    for raw in _list(contract["pools"], "pools"):
        pool = _object(raw, "pool")
        _fields(pool, {"id", "capacity"}, {"reserved"}, "pool")
        ident = _name(pool["id"], "pool.id")
        if ident in pool_ids:
            raise ContractError(f"duplicate pool: {ident}")
        pool_ids.add(ident)
        cap = _nat(pool["capacity"], "pool.capacity")
        for interval in _list(pool.get("reserved", []), "pool.reserved"):
            pair = _list(interval, "reserved extent")
            if len(pair) != 2:
                raise ContractError("reserved extent needs two endpoints")
            start, end = (_nat(n, "reserved endpoint") for n in pair)
            if not start < end <= cap:
                raise ContractError("reserved extent must be nonempty and inside its pool")
        pools.append(copy.deepcopy(pool))
    if not pools:
        raise ContractError("at least one memory pool is required")
    objects: list[dict[str, Any]] = []
    names: set[str] = set()
    for raw in _list(contract["objects"], "objects"):
        obj = _object(raw, "object")
        _fields(obj, {"id", "size", "allowed_pools"},
                {"alignment", "fixed_pool", "fixed_offset"}, "object")
        ident = _name(obj["id"], "object.id")
        if ident in names:
            raise ContractError(f"duplicate object: {ident}")
        names.add(ident)
        _nat(obj["size"], "object.size")
        _nat(obj.get("alignment", 1), "object.alignment", 1)
        allowed = [_name(p, "allowed pool")
                   for p in _list(obj["allowed_pools"], "object.allowed_pools")]
        if not allowed or len(set(allowed)) != len(allowed) or not set(allowed) <= pool_ids:
            raise ContractError("allowed_pools must uniquely name declared pools")
        if obj.get("fixed_pool") is not None and obj["fixed_pool"] not in allowed:
            raise ContractError("fixed_pool is not allowed")
        if obj.get("fixed_offset") is not None:
            _nat(obj["fixed_offset"], "object.fixed_offset")
        objects.append(copy.deepcopy(obj))
    slots = _nat(contract.get("slots", 1), "slots", 1)
    if len(objects) * slots > limits.max_objects or slots > limits.max_objects:
        raise UnsupportedContractError("expanded slot objects exceed max_objects")
    return pools, objects, slots


def extract_contract(raw: object, *, max_paths: int = 4096, max_events: int = 100000,
                     max_depth: int = 64, max_objects: int = 1024,
                     max_pair_checks: int = 1000000,
                     max_expansion_work: int = 1000000) -> dict[str, Any]:
    """Return a portable instance and content-bound, conditional extraction evidence.

    Inputs have schema/name/pools/objects/outcomes/body and optional slots/assumptions.
    The body is an array of events, choices or bounded repeats. Repeats enumerate
    every iteration count from min through max, including each body's alternatives.
    Every finished path must be drained and the declared outcome set must match it.
    Slot requests are independent: every used object in distinct slots conflicts.
    max_expansion_work separately bounds input traversal, structural visits and
    projected copies of paths, events and labels, including nested empty loops.
    """
    limits = Limits(max_paths, max_events, max_depth, max_objects, max_pair_checks,
                    max_expansion_work)
    for key, value in vars(limits).items():
        _nat(value, key, 1)
    expansion_budget = _ExpansionBudget(limits.max_expansion_work)
    contract = _snapshot(raw, limits, expansion_budget)
    _fields(contract, {"schema", "name", "pools", "objects", "outcomes", "body"},
            {"slots", "assumptions"}, "contract")
    if contract["schema"] != SCHEMA:
        raise UnsupportedContractError("unsupported component contract schema")
    name = _name(contract["name"], "contract.name")
    outcomes = [_name(o, "outcome") for o in _list(contract["outcomes"], "outcomes")]
    if not outcomes or len(set(outcomes)) != len(outcomes) or not set(outcomes) <= OUTCOMES:
        raise ContractError("outcomes must uniquely name supported terminal outcomes")
    assumptions = [_name(a, "assumption")
                   for a in _list(contract.get("assumptions", []), "assumptions")]
    pools, objects, slots = _declarations(contract, limits)
    names = {obj["id"] for obj in objects}
    paths = _expand(contract["body"], limits, expansion_budget)
    conflicts: set[tuple[str, str]] = set()
    witnesses: dict[tuple[str, str], dict[str, Any]] = {}
    path_records: list[dict[str, Any]] = []
    used: set[str] = set()
    pair_checks = barriers = event_count = 0
    for index, path in enumerate(paths):
        live: dict[str, Lease] = {}
        tokens: dict[str, str] = {}
        outcome: str | None = None
        for tick, event in enumerate(path.events):
            if outcome is not None:
                raise ContractError(f"path {index}: instruction after terminal outcome")
            try:
                outcome = _step(event, live, tokens, names)
            except ContractError as exc:
                raise type(exc)(f"path {index}, event {tick}: {exc}") from exc
            event_count += 1
            barriers += event["op"] == "barrier"
            used.update(live)
            pair_checks += len(live) * (len(live) - 1) // 2
            if pair_checks > limits.max_pair_checks:
                raise UnsupportedContractError("coexistence extraction exceeds max_pair_checks")
            for pair in combinations(sorted(live), 2):
                conflicts.add(pair)
                witnesses.setdefault(pair, {"objects": list(pair), "path": index, "event": tick})
        if outcome is None:
            raise ContractError(f"path {index}: missing terminal outcome")
        path_records.append({"labels": list(path.labels), "outcome": outcome,
                             "events": len(path.events)})
    if {p["outcome"] for p in path_records} != set(outcomes):
        raise ContractError("declared outcomes differ from the expanded terminal outcomes")
    if used != names:
        raise ContractError(f"objects never acquired in any declared path: {sorted(names - used)}")
    buffers: list[dict[str, Any]] = []
    expanded: set[tuple[str, str]] = set()
    for slot in range(slots):
        buffers.extend({**copy.deepcopy(obj), "id": f"{obj['id']}@{slot}", "intervals": []}
                       for obj in objects)
        expanded.update(_pair(f"{a}@{slot}", f"{b}@{slot}") for a, b in conflicts)
    for left_slot, right_slot in combinations(range(slots), 2):
        pair_checks += len(used) ** 2
        if pair_checks > limits.max_pair_checks:
            raise UnsupportedContractError("independent-slot coexistence exceeds max_pair_checks")
        expanded.update(_pair(f"{a}@{left_slot}", f"{b}@{right_slot}")
                        for a, b in product(sorted(used), repeat=2))
    instance: dict[str, Any] = {"name": name, "pools": pools, "buffers": buffers,
                              "conflicts": [list(pair) for pair in sorted(expanded)],
                              "assumptions": [*ASSUMPTIONS, *assumptions]}
    return {"instance": instance, "evidence": {
        "schema": VERSION, "status": "checked contract model",
        "contract_sha256": _digest(contract), "instance_sha256": _digest(instance),
        "proof_endpoint": "MemoryPlannerContracts.extracted_placement_safe; MemoryPlannerContracts.barrier_sound",
        "scope": "all expanded contract paths; source and target refinement remain assumptions",
        "slots": slots, "paths": path_records, "expanded_paths": len(paths),
        "interpreted_events": event_count, "checked_barriers": barriers,
        "expansion_work": expansion_budget.used,
        "conflict_count": len(expanded), "pair_checks": pair_checks,
        "local_conflict_witnesses": [witnesses[p] for p in sorted(witnesses)],
        "assumptions": instance["assumptions"], "limits": vars(limits),
    }}


def replay_extraction(raw: object, report: object) -> list[str]:
    """Reconstruct both outputs; supplied evidence cannot weaken extraction limits."""
    try:
        supplied = _object(report, "report")
        expected = extract_contract(raw)
    except ContractError as exc:
        return [str(exc)]
    return [] if supplied == expected else ["extraction report differs from deterministic replay"]


def demo_contract(*, late_completion: bool = False, slots: int = 4) -> dict[str, Any]:
    """A synthetic bounded desktop service, including exceptional cleanup paths.

    Normal execution uses 4 MiB then 3 MiB of scratch. The late variant acquires
    the second buffer before the first buffer's accepted device work finishes,
    producing a conflict despite lexical release and revocation of the first.
    """
    def event(op: str, obj: str = "phase-a", *, transfer: str | None = None) -> dict[str, Any]:
        result = {"op": op, "object": obj}
        if transfer is not None:
            result["token"] = transfer
        return result

    def drain(obj: str) -> list[dict[str, Any]]:
        return [event(op, obj) for op in ("release", "revoke", "sweep", "scrub", "barrier")]

    branches = []
    for outcome in ("normal", "exception", "cancel", "timeout"):
        body = []
        if outcome == "normal" and late_completion:
            body.append(event("acquire", "phase-b"))
        body.extend([event("complete", transfer="read-frame"), event("sweep"),
                     event("scrub"), event("barrier")])
        if outcome == "normal":
            if not late_completion:
                body.append(event("acquire", "phase-b"))
            body.extend([event("use", "phase-b"), *drain("phase-b")])
        body.append({"op": "finish", "outcome": outcome})
        branches.append({"label": outcome, "body": body})
    return {"schema": SCHEMA, "name": "bounded-desktop-service", "slots": slots,
            "pools": [{"id": "scratch", "capacity": slots * 7 * 1024 * 1024}],
            "objects": [{"id": name, "size": size * 1024 * 1024,
                         "alignment": 64, "allowed_pools": ["scratch"]}
                        for name, size in (("phase-a", 4), ("phase-b", 3))],
            "outcomes": ["normal", "exception", "cancel", "timeout"],
            "body": [event("acquire"), event("submit", transfer="read-frame"),
                     event("release"), event("revoke"), {"op": "choice", "branches": branches}],
            "assumptions": ["Synthetic service contract; sizes are illustrative, not measurements."]}
