# SPDX-License-Identifier: Apache-2.0
"""Portable offline placement with an independently checked retained baseline.

Addresses are pool-relative bytes. Lifetimes are unions of half-open intervals;
explicit conflicts add coexistence obligations. Empty intervals express a pure
conflict graph. Direct aliases constrain views into a root buffer, not ownership
or safe device completion. Every such upstream fact remains a supplied assumption.

The checker never calls search. Optional exact evidence is bounded Cartesian
replay over every legal integer placement, not a proof about this Python program
and not an imported SAT/CP certificate. A replay budget limit is always unknown.
"""

import hashlib
import itertools
import json
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass
from typing import Any

MAX_INTEGER = (1 << 63) - 1
CHECKER_VERSION = "portable-memory-checker-v1"
MODEL = "fixed-byte-extents-half-open-unions-direct-aliases-v1"


class PlannerError(ValueError):
    """Malformed input cannot become a placement claim."""


class UnsupportedError(PlannerError):
    """An unmodeled constraint must not disappear during conversion."""


@dataclass(frozen=True)
class Pool:
    id: str
    capacity: int
    reserved: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class Buffer:
    id: str
    size: int
    alignment: int
    intervals: tuple[tuple[int, int], ...]
    allowed_pools: tuple[str, ...]
    fixed_pool: str | None = None
    fixed_offset: int | None = None
    alias_of: str | None = None
    alias_offset: int = 0


@dataclass(frozen=True)
class Instance:
    name: str
    pools: tuple[Pool, ...]
    buffers: tuple[Buffer, ...]
    conflicts: tuple[tuple[str, str], ...] = ()
    assumptions: tuple[str, ...] = ()


type Placement = list[dict[str, Any]]
type Candidate = Placement | Callable[[Instance], Placement]


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise PlannerError(f"{label}: expected an object with string keys")
    return value


def _fields(row: dict[str, Any], required: set[str], optional: set[str], label: str) -> None:
    if set(row) - required - optional:
        raise UnsupportedError(f"{label}: unsupported fields {sorted(set(row) - required - optional)}")
    if required - set(row):
        raise PlannerError(f"{label}: missing fields {sorted(required - set(row))}")


def _sequence(value: object, label: str) -> list[Any] | tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise PlannerError(f"{label}: expected a list")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlannerError(f"{label}: expected a nonempty string")
    return value


def _number(value: object, label: str, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= MAX_INTEGER:
        raise PlannerError(f"{label}: expected an integer in [{minimum}, {MAX_INTEGER}]")
    return value


def _ranges(value: object, label: str, maximum: int = MAX_INTEGER) -> tuple[tuple[int, int], ...]:
    result = []
    for raw in _sequence(value, label):
        pair = _sequence(raw, label)
        if len(pair) != 2:
            raise PlannerError(f"{label}: expected interval pairs")
        start, end = _number(pair[0], label), _number(pair[1], label)
        if not start < end <= maximum:
            raise PlannerError(f"{label}: require 0 <= start < end <= {maximum}")
        result.append((start, end))
    # Canonicalize overlapping/adjacent ranges without changing their byte/time set.
    merged: list[tuple[int, int]] = []
    for start, end in sorted(result):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return tuple(merged)


def parse_instance(raw: object) -> Instance:
    """Validate every constraint and detach all input containers from the caller."""
    data = _mapping(raw, "instance")
    _fields(data, {"name", "pools", "buffers"}, {"conflicts", "assumptions"}, "instance")
    name = _text(data["name"], "name")
    pools = []
    for raw_pool in _sequence(data["pools"], "pools"):
        row = _mapping(raw_pool, "pool")
        _fields(row, {"id", "capacity"}, {"reserved"}, "pool")
        capacity = _number(row["capacity"], "capacity")
        pools.append(Pool(_text(row["id"], "pool.id"), capacity,
                          _ranges(row.get("reserved", ()), "reserved", capacity)))
    pool_ids = {p.id for p in pools}
    if not pools or len(pool_ids) != len(pools):
        raise PlannerError("pools: require nonempty unique identities")
    buffers = []
    for raw_buffer in _sequence(data["buffers"], "buffers"):
        row = _mapping(raw_buffer, "buffer")
        _fields(row, {"id", "size", "allowed_pools"},
                {"alignment", "intervals", "fixed_pool", "fixed_offset", "alias_of", "alias_offset"},
                "buffer")
        identifier = _text(row["id"], "buffer.id")
        allowed = tuple(_text(p, "allowed_pools")
                        for p in _sequence(row["allowed_pools"], "allowed_pools"))
        if not allowed or len(set(allowed)) != len(allowed) or not set(allowed) <= pool_ids:
            raise PlannerError(f"{identifier}: allowed_pools must name unique known pools")
        fixed_pool = row.get("fixed_pool")
        if fixed_pool is not None and fixed_pool not in allowed:
            raise PlannerError(f"{identifier}: fixed_pool must be allowed")
        fixed_offset = row.get("fixed_offset")
        if fixed_offset is not None:
            fixed_offset = _number(fixed_offset, "fixed_offset")
        alias_of = row.get("alias_of")
        if alias_of is not None:
            alias_of = _text(alias_of, "alias_of")
        alias_offset = _number(row.get("alias_offset", 0), "alias_offset")
        if alias_of is None and alias_offset:
            raise PlannerError(f"{identifier}: alias_offset requires alias_of")
        buffers.append(Buffer(identifier, _number(row["size"], "size"),
                              _number(row.get("alignment", 1), "alignment", 1),
                              _ranges(row.get("intervals", ()), "intervals"), allowed,
                              fixed_pool, fixed_offset, alias_of, alias_offset))
    by_id = {b.id: b for b in buffers}
    if len(by_id) != len(buffers):
        raise PlannerError("buffers: duplicate identity")
    for buffer in buffers:
        if buffer.alias_of is None:
            continue
        root = by_id.get(buffer.alias_of)
        if root is None or root.id == buffer.id:
            raise PlannerError(f"{buffer.id}: alias root is missing or self-referential")
        if root.alias_of is not None:
            raise UnsupportedError("alias chains: flatten the view relation explicitly")
        if buffer.alias_offset + buffer.size > root.size:
            raise PlannerError(f"{buffer.id}: alias view exceeds root extent")
    conflicts = set()
    for raw_pair in _sequence(data.get("conflicts", ()), "conflicts"):
        pair = _sequence(raw_pair, "conflict")
        if len(pair) != 2 or any(not isinstance(x, str) or x not in by_id for x in pair):
            raise PlannerError("conflicts: expected pairs of known buffer identities")
        if pair[0] == pair[1]:
            raise PlannerError("conflicts: self-conflict")
        if (by_id[pair[0]].alias_of or pair[0]) == (by_id[pair[1]].alias_of or pair[1]):
            raise PlannerError("conflicts: explicitly conflicting aliases are contradictory")
        conflicts.add(tuple(sorted(pair)))
    assumptions = tuple(_text(a, "assumption")
                        for a in _sequence(data.get("assumptions", ()), "assumptions"))
    return Instance(name, tuple(pools), tuple(buffers), tuple(sorted(conflicts)), assumptions)


def _snapshot(instance: Instance) -> Instance:
    # Frozen dataclasses can still be constructed incorrectly or deliberately modified
    # through object.__setattr__. Revalidate and detach at each public trust boundary.
    if not isinstance(instance, Instance):
        raise PlannerError("expected an Instance from parse_instance")
    return parse_instance(asdict(instance))


def instance_digest(instance: Instance) -> str:
    data = json.dumps(asdict(_snapshot(instance)), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def check_placement(instance: Instance, placement: object) -> list[str]:
    """Independent feasibility decision; never trust candidate extents or heights."""
    instance = _snapshot(instance)
    if not isinstance(placement, list):
        return ["schema: placement must be a list"]
    errors: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    buffers = {b.id: b for b in instance.buffers}
    pools = {p.id: p for p in instance.pools}
    for raw in placement:
        try:
            row = _mapping(raw, "placement")
            _fields(row, {"id", "pool", "offset"}, set(), "placement")
            identifier = _text(row["id"], "placement.id")
            _text(row["pool"], "placement.pool")
            _number(row["offset"], "placement.offset")
        except PlannerError as error:
            errors.append(f"schema: {error}")
            continue
        if identifier in by_id:
            errors.append(f"identity: duplicate {identifier}")
        if identifier not in buffers:
            errors.append(f"identity: unknown {identifier}")
        by_id[identifier] = row
    for buffer in instance.buffers:
        row = by_id.get(buffer.id)
        if row is None:
            errors.append(f"identity: missing {buffer.id}")
            continue
        pool, offset = row["pool"], row["offset"]
        if pool not in buffer.allowed_pools or (buffer.fixed_pool is not None and pool != buffer.fixed_pool):
            errors.append(f"pool: illegal assignment for {buffer.id}")
        if offset % buffer.alignment:
            errors.append(f"alignment: {buffer.id}")
        if buffer.fixed_offset is not None and offset != buffer.fixed_offset:
            errors.append(f"fixed-offset: {buffer.id}")
        if pool not in pools or offset + buffer.size > pools[pool].capacity:
            errors.append(f"capacity: {buffer.id}")
        if pool in pools and buffer.size and any(
                max(offset, start) < min(offset + buffer.size, end)
                for start, end in pools[pool].reserved):
            errors.append(f"reserved: {buffer.id}")
        if buffer.alias_of is not None and buffer.alias_of in by_id:
            root = by_id[buffer.alias_of]
            if pool != root["pool"] or offset != root["offset"] + buffer.alias_offset:
                errors.append(f"alias: {buffer.id}")
    for i, left in enumerate(instance.buffers):
        if left.id not in by_id or not left.size:
            continue
        for right in instance.buffers[i + 1:]:
            if right.id not in by_id or not right.size:
                continue
            if (left.alias_of or left.id) == (right.alias_of or right.id):
                continue
            lrow, rrow = by_id[left.id], by_id[right.id]
            if lrow["pool"] != rrow["pool"]:
                continue
            coexist = tuple(sorted((left.id, right.id))) in instance.conflicts or any(
                max(ls, rs) < min(le, re)
                for ls, le in left.intervals for rs, re in right.intervals)
            if coexist and max(lrow["offset"], rrow["offset"]) < min(
                    lrow["offset"] + left.size, rrow["offset"] + right.size):
                errors.append(f"overlap: {left.id}/{right.id}")
    return errors


def pool_heights(instance: Instance, placement: object) -> dict[str, int]:
    """Extent objective, including reserved regions; zero-sized views charge no bytes."""
    instance = _snapshot(instance)
    findings = check_placement(instance, placement)
    if findings:
        raise PlannerError("invalid placement: " + "; ".join(findings))
    heights = {p.id: max((end for _, end in p.reserved), default=0) for p in instance.pools}
    sizes = {b.id: b.size for b in instance.buffers}
    for row in _sequence(placement, "placement"):
        if sizes[row["id"]]:
            heights[row["pool"]] = max(heights[row["pool"]], row["offset"] + sizes[row["id"]])
    return heights


def _ordered(instance: Instance, placement: object) -> Placement:
    by_id = {row["id"]: row for row in _sequence(placement, "placement")}
    return [{"id": b.id, "pool": by_id[b.id]["pool"], "offset": by_id[b.id]["offset"]}
            for b in instance.buffers]


def _key(instance: Instance, placement: Placement) -> tuple[int, tuple[tuple[str, int], ...]]:
    return (sum(pool_heights(instance, placement).values()),
            tuple((_text(r["pool"], "pool"), _number(r["offset"], "offset"))
                  for r in _ordered(instance, placement)))


def _limits(instance: Instance, limits: object) -> dict[str, int]:
    if limits is None:
        return {p.id: p.capacity for p in instance.pools}
    row = _mapping(limits, "pool_limits")
    if set(row) != {p.id for p in instance.pools}:
        raise PlannerError("pool_limits: exactly one limit for every pool is required")
    result = {p.id: _number(row[p.id], "pool_limit") for p in instance.pools}
    if any(result[p.id] > p.capacity for p in instance.pools):
        raise PlannerError("pool_limits exceed capacity")
    return result


def _domains(instance: Instance, limits: dict[str, int]) -> Iterator[Placement]:
    """Complete product without materializing address ranges or Cartesian tuples.

    A legal placement's pool occurs in allowed_pools and its nonnegative aligned
    base occurs in this range (or the fixed singleton). Alias constraints are
    checked after enumeration. Zero-size offsets range over full pool capacity:
    the extent objective places no bound on their observable address.
    """
    buffers = instance.buffers
    pool_options = [tuple(p for p in b.allowed_pools if b.fixed_pool in (None, p)) for b in buffers]
    capacities = {p.id: p.capacity for p in instance.pools}
    for pool_choices in itertools.product(*pool_options):
        domains: list[range | tuple[int, ...]] = []
        for buffer, pool in zip(buffers, pool_choices, strict=True):
            maximum = (limits[pool] if buffer.size else capacities[pool]) - buffer.size
            if buffer.fixed_offset is not None:
                domains.append((buffer.fixed_offset,) if buffer.fixed_offset <= maximum else ())
            else:
                domains.append(range(0, maximum + 1, buffer.alignment))
        # itertools.product eagerly caches ranges: a mixed-radix counter is bounded
        # by buffer count even for a 63-bit capacity.
        counts = [(max(0, domain.stop - domain.start) + domain.step - 1) // domain.step
                  if isinstance(domain, range) else len(domain) for domain in domains]
        if any(count == 0 for count in counts):
            continue
        indices = [0] * len(domains)
        while True:
            yield [{"id": b.id, "pool": p, "offset": domain[index]}
                   for b, p, domain, index in zip(buffers, pool_choices, domains, indices, strict=True)]
            digit = len(indices) - 1
            while digit >= 0:
                indices[digit] += 1
                if indices[digit] < counts[digit]:
                    break
                indices[digit] = 0
                digit -= 1
            if digit < 0:
                break


def _search_candidates(instance: Instance, limits: dict[str, int]) -> Iterator[Placement]:
    """Untrusted size-first mixed-radix generator, separate from certificate replay.

    A candidate's ordinal is decoded into each buffer's pool and aligned offset.
    No arrays proportional to capacities are created. The replay above uses its
    own original-order pool products and per-pool ranges, and trusts no search
    pruning, ordering, progress counter, or claimed exhaustion.
    """
    order = sorted(instance.buffers, key=lambda b: (-b.size, b.id))
    capacities = {p.id: p.capacity for p in instance.pools}
    options: list[list[tuple[str, int, int, int]]] = []
    counts = []
    for buffer in order:
        choices = []
        for pool in sorted(buffer.allowed_pools):
            if buffer.fixed_pool not in (None, pool):
                continue
            maximum = (limits[pool] if buffer.size else capacities[pool]) - buffer.size
            if maximum < 0:
                continue
            if buffer.fixed_offset is not None:
                if buffer.fixed_offset <= maximum:
                    choices.append((pool, 1, buffer.fixed_offset, 1))
            else:
                choices.append((pool, maximum // buffer.alignment + 1, 0, buffer.alignment))
        options.append(choices)
        counts.append(sum(count for _, count, _, _ in choices))
    total = 1
    for count in counts:
        total *= count
    ordinal = 0
    while ordinal < total:
        remaining = ordinal
        candidate = []
        for buffer, choices, count in zip(order, options, counts, strict=True):
            index = remaining % count
            remaining //= count
            for pool, pool_count, start, stride in choices:
                if index < pool_count:
                    candidate.append({"id": buffer.id, "pool": pool, "offset": start + index * stride})
                    break
                index -= pool_count
        yield candidate
        ordinal += 1


def _receipt(instance: Instance, status: str, placement: Placement | None,
             limits: dict[str, int], **extra: object) -> dict[str, Any]:
    return {"status": status, "instance_digest": instance_digest(instance),
            "model": MODEL, "checker_version": CHECKER_VERSION,
            "objective": {"metric": "sum-pool-extents-in-bytes", "pool_limits": limits,
                          "scope": "legal layouts satisfying the stated componentwise pool limits",
                          "includes": "buffer extents, alignment holes, reserved regions",
                          "excludes": "host search memory, runtime metadata not supplied as buffers or reservations"},
            "assumptions": ["sizes and coexistence describe all execution paths and late access",
                            "direct aliases denote authorized views of the same backing storage",
                            "offsets do not change source behavior or device completion",
                            *instance.assumptions],
            "proof_endpoint": ("independent finite-model lower bound or complete Cartesian replay; "
                               "no proof of Python implementation, source or target refinement"
                               if status in {"checked optimal", "checked infeasible"} else
                               "independent Python feasibility checker; no source or target refinement"),
            "pool_heights": pool_heights(instance, placement) if placement is not None else None,
            **extra}


def certify_placement(instance: Instance, placement: Placement | None, *,
                      pool_limits: object = None, work_budget: int = 100000) -> dict[str, Any]:
    """Independently exclude every better layout, or every layout for infeasibility.

    The result's checked optimal status is relative to its explicit pool limits.
    No solver-reported search completeness is trusted. Work counts complete tuples;
    this keeps memory bounded and makes cutoff/output independent of wall time.
    """
    instance = _snapshot(instance)
    budget = _number(work_budget, "work_budget")
    limits = _limits(instance, pool_limits)
    if placement is not None:
        findings = check_placement(instance, placement)
        if findings:
            return _receipt(instance, "unknown", None, limits, findings=findings, replay_work=0)
        placement = _ordered(instance, placement)
        if any(h > limits[p] for p, h in pool_heights(instance, placement).items()):
            return _receipt(instance, "unknown", None, limits,
                            findings=["candidate exceeds stated pool limits"], replay_work=0)
    bound = sum(pool_heights(instance, placement).values()) if placement is not None else None
    # Every forced-pool positive extent charges at least its size (or fixed end).
    # Taking a max within each pool avoids unsoundly summing aliases or lifetimes.
    # This bound remains sound for unrestricted conflicts and arbitrary alignments.
    lower_bounds = {p.id: max((end for _, end in p.reserved), default=0) for p in instance.pools}
    for buffer in instance.buffers:
        forced = buffer.fixed_pool or (buffer.allowed_pools[0] if len(buffer.allowed_pools) == 1 else None)
        if forced is not None and buffer.size:
            lower_bounds[forced] = max(lower_bounds[forced], (buffer.fixed_offset or 0) + buffer.size)
    if bound is not None and bound == sum(lower_bounds.values()):
        return _receipt(instance, "checked optimal", placement, limits, replay_work=0,
                        certificate={"method": "independent-forced-extent-lower-bound",
                                     "pool_lower_bounds": lower_bounds})
    work = 0
    for candidate in _domains(instance, limits):
        if work >= budget:
            return _receipt(instance, "unknown", placement, limits, replay_work=work,
                            reason="replay budget exhausted")
        work += 1
        if check_placement(instance, candidate):
            continue
        heights = pool_heights(instance, candidate)
        if any(h > limits[p] for p, h in heights.items()):
            continue
        if bound is None or sum(heights.values()) < bound:
            return _receipt(instance, "unknown", placement, limits, replay_work=work,
                            reason="counterexample to requested certificate", counterexample=candidate)
    status = "checked optimal" if placement is not None else "checked infeasible"
    return _receipt(instance, status, placement, limits, replay_work=work,
                    certificate={"method": "complete-cartesian-replay", "strict_objective_bound": bound})


def verify_evidence(instance: Instance, result: object, *, work_budget: int = 100000) -> dict[str, Any]:
    """Replay a serialized result without accepting its digest, heights or status on trust."""
    instance = _snapshot(instance)
    data = _mapping(result, "result")
    evidence = _mapping(data.get("evidence"), "evidence")
    if evidence.get("instance_digest") != instance_digest(instance):
        return {"status": "unknown", "findings": ["instance digest mismatch"]}
    if evidence.get("checker_version") != CHECKER_VERSION or evidence.get("model") != MODEL:
        return {"status": "unsupported", "findings": ["checker or model version mismatch"]}
    placement = data.get("placement")
    objective = _mapping(evidence.get("objective"), "objective")
    limits = _limits(instance, objective.get("pool_limits"))
    if objective != _receipt(instance, "unknown", None, limits)["objective"]:
        return {"status": "unsupported", "findings": ["objective mismatch"]}
    status = evidence.get("status")
    if status not in {"checked feasible", "checked optimal", "checked infeasible"}:
        return {"status": "unknown", "findings": ["result makes no checked claim"]}
    if status == "checked infeasible" and placement is not None:
        return {"status": "unknown", "findings": ["infeasible result carries a placement"]}
    if status != "checked infeasible":
        findings = check_placement(instance, placement)
        if findings:
            return {"status": "unknown", "findings": findings}
        heights = pool_heights(instance, placement)
        if heights != evidence.get("pool_heights") or any(h > limits[p] for p, h in heights.items()):
            return {"status": "unknown", "findings": ["height or pool-limit mismatch"]}
        if "baseline_placement" in evidence:
            baseline = evidence["baseline_placement"]
            findings = check_placement(instance, baseline)
            if findings:
                return {"status": "unknown", "findings": ["baseline: " + f for f in findings]}
            baseline_heights = pool_heights(instance, baseline)
            if baseline_heights != evidence.get("baseline_pool_heights") or baseline_heights != limits:
                return {"status": "unknown", "findings": ["baseline height mismatch"]}
    if status == "checked feasible":
        return _receipt(instance, status, placement, limits)
    return certify_placement(instance, placement, pool_limits=limits, work_budget=work_budget)


def plan(instance: Instance, baseline: object, *, candidates: Iterable[Candidate] = (),
         work_budget: int = 0, certify: bool = False, replay_budget: int = 100000) -> dict[str, Any]:
    """Retain a checked baseline, then optionally consider isolated untrusted candidates.

    The caller runs its normal planner first and supplies its ordinary result here.
    Candidate callbacks are synchronous host code and must bound their own work;
    work_budget bounds only this module's optional deterministic finite search.
    """
    instance = _snapshot(instance)
    _number(work_budget, "work_budget")
    _number(replay_budget, "replay_budget")
    findings = check_placement(instance, baseline)
    capacities = {p.id: p.capacity for p in instance.pools}
    if findings:
        return {"placement": None, "evidence": _receipt(
            instance, "unknown", None, capacities, reason="invalid baseline refused",
            findings=findings, search_work=0)}
    retained = _ordered(instance, baseline)
    limits = pool_heights(instance, retained)
    selected = _ordered(instance, retained)
    rejected: list[dict[str, Any]] = []

    def consider(candidate: object, label: str) -> None:
        nonlocal selected
        candidate_findings = check_placement(instance, candidate)
        if candidate_findings:
            rejected.append({"candidate": label, "findings": candidate_findings})
            return
        canonical = _ordered(instance, candidate)
        if any(h > limits[p] for p, h in pool_heights(instance, canonical).items()):
            rejected.append({"candidate": label, "findings": ["componentwise pool regression"]})
            return
        if _key(instance, canonical) < _key(instance, selected):
            selected = canonical

    try:
        for i, generator in enumerate(candidates):
            try:
                candidate = generator(_snapshot(instance)) if callable(generator) else generator
            except Exception as error:  # Optional callback failure must keep the checked fallback.
                rejected.append({"candidate": str(i), "findings": [f"generator failed: {type(error).__name__}"]})
                continue
            consider(candidate, str(i))
    except Exception as error:  # A candidate iterator can also fail before yielding.
        rejected.append({"candidate": "iterator", "findings": [f"iterator failed: {type(error).__name__}"]})
    work = 0
    if work_budget:
        for candidate in _search_candidates(instance, limits):
            if work >= work_budget:
                break
            work += 1
            if not check_placement(instance, candidate):
                consider(candidate, f"search-{work}")
    evidence = _receipt(instance, "checked feasible", selected, limits,
                        baseline_pool_heights=limits, baseline_placement=retained,
                        search_work=work, search_budget=work_budget, rejected=rejected,
                        non_regression="selected pool heights <= checked retained baseline in every pool")
    if certify:
        certification = certify_placement(instance, selected, pool_limits=limits, work_budget=replay_budget)
        evidence["certification"] = certification
        if certification["status"] == "checked optimal":
            evidence["status"] = "checked optimal"
            evidence["certificate"] = certification["certificate"]
            evidence["proof_endpoint"] = certification["proof_endpoint"]
    return {"placement": selected, "evidence": evidence}


def solve(instance: Instance, *, work_budget: int = 100000,
          certify: bool = False, replay_budget: int = 100000) -> dict[str, Any]:
    """Find a first baseline when none exists; budget exhaustion never means infeasible."""
    instance = _snapshot(instance)
    _number(work_budget, "work_budget")
    _number(replay_budget, "replay_budget")
    capacities = {p.id: p.capacity for p in instance.pools}
    work = 0
    for next_work, candidate in enumerate(_search_candidates(instance, capacities), start=1):
        if next_work > work_budget:
            return {"placement": None, "evidence": _receipt(
                instance, "unknown", None, capacities, search_work=work, reason="search budget exhausted")}
        work = next_work
        if not check_placement(instance, candidate):
            result = plan(instance, candidate, work_budget=work_budget - work,
                          certify=certify, replay_budget=replay_budget)
            result["evidence"]["baseline_search_work"] = work
            return result
    certification = certify_placement(instance, None, work_budget=replay_budget)
    return {"placement": None, "evidence": certification}
