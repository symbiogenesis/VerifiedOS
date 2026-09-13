# SPDX-License-Identifier: Apache-2.0
"""Three executable placement models over one finite family of admitted modes.

The single-trace contract answers one schedule. A mode family declares shared
object identities, a finite set of admitted modes each carrying its own
lifetimes, and one switch rule. An identity absent from a mode is dead there.

Three computations answer three different questions and never substitute for one
another. The per-mode optimum runs the existing exact oracle on each mode's own
trace and binds nothing across modes. The conservative model places one fixed
layout against the relation joining two identities that overlap in any admitted
mode; that graph is not an interval graph in general, so no interval-only search
decides it. The binding family keeps one checked layout per mode and is valid
only under the declared switch rule, whose refusals are findings here.

Every witness goes through a checker that shares no conflict predicate, ordering
or adjacency structure with the search that produced it. Search is bounded and
untrusted: exhaustion of a work budget is unfinished research, never
infeasibility, and no search writes a plan or changes an input.

Which model an admitted artifact supplies is decided by the compiler or the
composition exporter, never here. Nothing in this module is an admission input.
"""

import itertools
import json
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, TypedDict

from vos import static_memory as memory

MAX_GRAPH_NODES = 12
MAX_SUBSETS = 4096
RULES: tuple[str, ...] = ("dead-at-switch", "retained-bases-equal")
METHODS: tuple[str, ...] = ("first-fit-degree", "first-fit-size", "first-fit-identity")
SHARINGS: tuple[str, ...] = ("per-mode", "conservative", "binding")


@dataclass(frozen=True)
class Identity:
    """One object identity, shared by every mode that activates it."""

    id: str
    arena: str
    size: int
    payload: int
    alignment: int


@dataclass(frozen=True)
class Mode:
    """One admitted mode, carried as the single-trace case its lifetimes denote."""

    name: str
    case: memory.Case


@dataclass(frozen=True)
class Transition:
    """One declared switch, with the instant on each side and what it retains."""

    source: str
    target: str
    at_source: int
    at_target: int
    retained: tuple[str, ...]


@dataclass(frozen=True)
class Binding:
    rule: str
    transitions: tuple[Transition, ...]


@dataclass(frozen=True)
class ModeFamily:
    name: str
    provenance: str
    arenas: tuple[memory.Arena, ...]
    identities: tuple[Identity, ...]
    modes: tuple[Mode, ...]
    binding: Binding


@dataclass(frozen=True)
class Variable:
    """One base a model chooses, and the (mode, identity) pairs sharing that base."""

    name: str
    arena: str
    size: int
    alignment: int
    members: tuple[tuple[str, str], ...]


class Expectation(TypedDict):
    """What a declared witness is a witness of, checked against its own receipt."""

    conservative_exceeds_per_mode: bool
    binding_matches_per_mode: bool
    binding_matches_conservative: bool
    binding_refused: bool
    not_interval: bool


@dataclass
class Work:
    """Bounded work counter over search roots and candidate bases, never wall time."""

    limit: int
    spent: int = 0

    def take(self) -> bool:
        if self.spent >= self.limit:
            return False
        self.spent += 1
        return True


def _object(value: object, names: set[str], label: str) -> dict[str, Any]:
    """Read one wrapper object with exactly the declared field set.

    Identity, arena and lifetime numbers are deliberately not validated here. They
    are handed to the placement contract's own parser, so the lifecycle ordering,
    payload and alignment rules keep one statement in one place.
    """
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise memory.CaseError(f"{label}: expected an object with string keys")
    if set(value) != names:
        raise memory.CaseError(f"{label}: missing {sorted(names - set(value))}; "
                               f"unknown {sorted(set(value) - names)}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise memory.CaseError(f"{label}: expected a nonempty string")
    return value


def _count(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise memory.CaseError(f"{label}: expected a nonnegative integer")
    return value


def _entries(value: object, label: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise memory.CaseError(f"{label}: expected a nonempty list")
    return value


def standing_bases(identities: Iterable[Identity]) -> dict[str, int]:
    """One globally disjoint aligned address per identity, in declaration order.

    Distinct extents share no byte in any mode, so this is the trivially feasible
    single layout. It bounds the search from above and is never an optimum claim.
    """
    cursor: dict[str, int] = {}
    bases: dict[str, int] = {}
    for identity in identities:
        start = cursor.get(identity.arena, 0)
        base = (start + identity.alignment - 1) // identity.alignment * identity.alignment
        bases[identity.id] = base
        cursor[identity.arena] = base + identity.size
    return bases


def parse_family(raw: object) -> ModeFamily:
    """Read the mode family once, with exact field sets at every level.

    An identity no mode activates is refused rather than silently carried: the
    declared mode set is the whole admitted set in this model, so such an identity
    would make the family's charge a claim about nothing. Lifetimes reach the
    placement contract's parser, which owns their ordering and extent rules.
    """
    data = _object(raw, {"name", "provenance", "arenas", "identities", "modes", "binding"},
                   "family")
    name = _text(data["name"], "family.name")
    provenance = _text(data["provenance"], "family.provenance")
    identities: list[Identity] = []
    for index, entry in enumerate(_entries(data["identities"], "family.identities")):
        label = f"identities[{index}]"
        row = _object(entry, {"id", "arena", "size", "payload", "alignment"}, label)
        identities.append(Identity(_text(row["id"], f"{label}.id"),
                                   _text(row["arena"], f"{label}.arena"),
                                   _count(row["size"], f"{label}.size"),
                                   _count(row["payload"], f"{label}.payload"),
                                   _count(row["alignment"], f"{label}.alignment")))
    declared = {identity.id: identity for identity in identities}
    if len(declared) != len(identities):
        raise memory.CaseError("family.identities: duplicate id")
    bases = standing_bases(identities)
    lifetime_fields = {"id", "start", "payload_end", "authority_end", "sweep_end", "reuse"}
    modes: list[Mode] = []
    named: set[str] = set()
    activated: set[str] = set()
    for index, entry in enumerate(_entries(data["modes"], "family.modes")):
        label = f"modes[{index}]"
        row = _object(entry, {"name", "lifetimes"}, label)
        mode_name = _text(row["name"], f"{label}.name")
        if mode_name in named:
            raise memory.CaseError(f"{label}: duplicate mode {mode_name}")
        named.add(mode_name)
        objects: list[dict[str, Any]] = []
        live: set[str] = set()
        for position, raw_lifetime in enumerate(_entries(row["lifetimes"], f"{label}.lifetimes")):
            spot = f"{label}.lifetimes[{position}]"
            lifetime = _object(raw_lifetime, lifetime_fields, spot)
            identifier = _text(lifetime["id"], f"{spot}.id")
            if identifier not in declared:
                raise memory.CaseError(f"{spot}: unknown identity {identifier}")
            if identifier in live:
                raise memory.CaseError(f"{spot}: {identifier} already has a lifetime here")
            live.add(identifier)
            identity = declared[identifier]
            objects.append({**lifetime, "arena": identity.arena, "size": identity.size,
                            "payload": identity.payload, "alignment": identity.alignment,
                            "base": bases[identifier]})
        activated |= live
        modes.append(Mode(mode_name, memory.parse_case(
            {"name": f"{name}::{mode_name}", "provenance": provenance, "mode": mode_name,
             "arenas": data["arenas"], "objects": objects})))
    absent = sorted(set(declared) - activated)
    if absent:
        raise memory.CaseError(f"family.identities: {absent} are activated by no mode")
    return ModeFamily(name, provenance, modes[0].case.arenas, tuple(identities), tuple(modes),
                      _binding(data["binding"], named, set(declared)))


def _binding(raw: object, modes: set[str], identities: set[str]) -> Binding:
    """Read the switch rule and its transitions; an unknown mode or id is refused."""
    data = _object(raw, {"rule", "transitions"}, "family.binding")
    rule = _text(data["rule"], "family.binding.rule")
    if rule not in RULES:
        raise memory.CaseError(f"family.binding.rule: expected one of {list(RULES)}")
    transitions: list[Transition] = []
    seen: set[tuple[str, str]] = set()
    for index, entry in enumerate(_entries(data["transitions"], "family.binding.transitions")):
        label = f"transitions[{index}]"
        row = _object(entry, {"source", "target", "at_source", "at_target", "retained"}, label)
        source = _text(row["source"], f"{label}.source")
        target = _text(row["target"], f"{label}.target")
        if source not in modes or target not in modes:
            raise memory.CaseError(f"{label}: unknown mode in {source}->{target}")
        if (source, target) in seen:
            raise memory.CaseError(f"{label}: duplicate transition {source}->{target}")
        seen.add((source, target))
        if not isinstance(row["retained"], list):
            raise memory.CaseError(f"{label}.retained: expected a list")
        retained = tuple(_text(item, f"{label}.retained[{position}]")
                         for position, item in enumerate(row["retained"]))
        if len(set(retained)) != len(retained):
            raise memory.CaseError(f"{label}.retained: duplicate identity")
        if not identities.issuperset(retained):
            raise memory.CaseError(f"{label}.retained: unknown identity")
        if rule == "dead-at-switch" and retained:
            raise memory.CaseError(f"{label}.retained: this rule carries nothing across a switch")
        transitions.append(Transition(source, target,
                                      _count(row["at_source"], f"{label}.at_source"),
                                      _count(row["at_target"], f"{label}.at_target"), retained))
    if rule == "retained-bases-equal" and not any(row.retained for row in transitions):
        raise memory.CaseError("family.binding: the retained rule needs a retained identity")
    return Binding(rule, tuple(transitions))


def family_hash(family: ModeFamily) -> str:
    """Bind every parsed field, each mode through the placement contract's own hash.

    The wrapper adds exactly what one trace cannot carry: the identity set, the
    switch rule and its transitions. Mode digests are not recomputed here.
    """
    payload = {
        "name": family.name, "provenance": family.provenance,
        "arenas": [asdict(arena) for arena in family.arenas],
        "identities": [asdict(identity) for identity in family.identities],
        "modes": {mode.name: memory.contract_hash(mode.case) for mode in family.modes},
        "binding": asdict(family.binding),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def live_at(case: memory.Case, instant: int) -> tuple[str, ...]:
    """Identities holding their reservation at one instant; release precedes acquisition."""
    return tuple(sorted(obj.id for obj in case.objects if obj.start <= instant < obj.reuse))


def check_switch_rule(family: ModeFamily) -> list[str]:
    """Decide the declared rule at every declared switch instant, on both sides.

    An identity live where a mode is left or entered, and not retained by that
    transition, refuses the family: its bytes would carry across a boundary the
    layouts do not agree on. A retained identity that is dead there is refused too,
    because a retained set that retains nothing binds nothing. The instants are
    supplied premises about the composed schedule, exactly as lifetime milestones
    are; R-08-015's temporal-safety discipline at a slot's reuse points, which
    composes the containment barrier with the complete reuse gate, stays owed.
    """
    cases = {mode.name: mode.case for mode in family.modes}
    findings: list[str] = []
    for transition in family.binding.transitions:
        edge = f"{transition.source}->{transition.target}"
        retained = set(transition.retained)
        sides = ((transition.source, transition.at_source, "leaves"),
                 (transition.target, transition.at_target, "enters"))
        for mode_name, instant, side in sides:
            live = set(live_at(cases[mode_name], instant))
            findings.extend(f"{edge}: {name} is live where {mode_name} {side} at {instant} "
                            "and no transition retains it" for name in sorted(live - retained))
            findings.extend(f"{edge}: retained {name} is dead where {mode_name} {side} "
                            f"at {instant}" for name in sorted(retained - live))
    return findings


def variables(family: ModeFamily, sharing: str) -> tuple[Variable, ...]:
    """One base per mode occurrence, per retained equality class, or per identity.

    The three models differ only here. Conservative sharing is the fully retained
    limit, where every mode's copy of an identity is one base; per-mode sharing is
    the fully dead one, where no copy binds another. The binding family lies
    between them and is decided by the declared transitions, not by this function.
    """
    if sharing not in SHARINGS:
        raise memory.CaseError(f"unknown sharing model {sharing}")
    occurrences = [(mode.name, obj.id) for mode in family.modes for obj in mode.case.objects]
    parent = {pair: pair for pair in occurrences}

    def root(pair: tuple[str, str]) -> tuple[str, str]:
        while parent[pair] != pair:
            parent[pair] = parent[parent[pair]]
            pair = parent[pair]
        return pair

    def union(left: tuple[str, str], right: tuple[str, str]) -> None:
        first, second = sorted((root(left), root(right)))
        parent[second] = first

    if sharing == "conservative":
        for identity in family.identities:
            members = [pair for pair in occurrences if pair[1] == identity.id]
            for pair in members[1:]:
                union(members[0], pair)
    elif sharing == "binding":
        for transition in family.binding.transitions:
            for name in transition.retained:
                left, right = (transition.source, name), (transition.target, name)
                if left in parent and right in parent:
                    union(left, right)
    groups: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for pair in occurrences:
        groups.setdefault(root(pair), []).append(pair)
    declared = {identity.id: identity for identity in family.identities}
    result: list[Variable] = []
    for representative, members in sorted(groups.items()):
        identity = declared[representative[1]]
        name = identity.id if sharing == "conservative" else f"{representative[0]}/{identity.id}"
        result.append(Variable(name, identity.arena, identity.size, identity.alignment,
                               tuple(sorted(members))))
    return tuple(result)


def interference(family: ModeFamily, nodes: tuple[Variable, ...]) -> list[tuple[str, str]]:
    """Two variables interfere where one admitted mode holds both, overlapping.

    Under conservative sharing this is the baseline's all-mode relation: two
    identities interfere if their reservations overlap in any admitted mode. It is
    a union of interval relations and need not be an interval relation itself.
    """
    holder = {member: node.name for node in nodes for member in node.members}
    edges: set[tuple[str, str]] = set()
    for mode in family.modes:
        for index, left in enumerate(mode.case.objects):
            for right in mode.case.objects[index + 1:]:
                if left.arena != right.arena:
                    continue
                if left.start >= right.reuse or right.start >= left.reuse:
                    continue
                one, other = holder[(mode.name, left.id)], holder[(mode.name, right.id)]
                edges.add((min(one, other), max(one, other)))
    return sorted(edges)


def adjacency(nodes: tuple[Variable, ...],
              edges: list[tuple[str, str]]) -> dict[str, set[str]]:
    neighbours: dict[str, set[str]] = {node.name: set() for node in nodes}
    for left, right in edges:
        neighbours[left].add(right)
        neighbours[right].add(left)
    return neighbours


def _connected(subset: tuple[str, ...], neighbours: dict[str, set[str]]) -> bool:
    chosen = set(subset)
    reached = {subset[0]}
    frontier = [subset[0]]
    while frontier:
        name = frontier.pop()
        for other in sorted(neighbours[name] & chosen):
            if other not in reached:
                reached.add(other)
                frontier.append(other)
    return reached == chosen


def _walk(subset: tuple[str, ...], neighbours: dict[str, set[str]]) -> list[str]:
    chosen = set(subset)
    order = [min(subset)]
    while len(order) < len(subset):
        candidates = sorted((neighbours[order[-1]] & chosen) - set(order))
        order.append(candidates[0])
    return order


def chordless_cycle(nodes: tuple[Variable, ...], edges: list[tuple[str, str]],
                    max_subsets: int = MAX_SUBSETS) -> dict[str, Any]:
    """Bounded search for an induced cycle of length four or more.

    Interval graphs are chordal. That classical containment is a premise this tool
    uses and does not prove, and under it such a cycle witnesses that the relation
    has no interval model, so an interval-only search cannot decide the instance.
    Finding none decides nothing in the other direction: the search is bounded, and
    a chordal graph need not be an interval graph either.
    """
    if type(max_subsets) is not int or max_subsets < 1:
        raise memory.CaseError("max_subsets must be a positive integer")
    neighbours = adjacency(nodes, edges)
    names = sorted(node.name for node in nodes)
    subsets = 0
    for size in range(4, len(names) + 1):
        for subset in itertools.combinations(names, size):
            if subsets >= max_subsets:
                return {"status": "incomplete", "cycle": None, "subsets": subsets}
            subsets += 1
            chosen = set(subset)
            if any(len(neighbours[name] & chosen) != 2 for name in subset):
                continue
            if _connected(subset, neighbours):
                return {"status": "induced-cycle", "cycle": _walk(subset, neighbours),
                        "subsets": subsets}
    return {"status": "none-found", "cycle": None, "subsets": subsets}


def projections(family: ModeFamily,
                placement: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """One fixed layout read as the family of per-mode placements it denotes."""
    rows = [row for row in placement if isinstance(row, dict) and isinstance(row.get("id"), str)]
    return {mode.name: [row for row in rows
                        if row["id"] in {obj.id for obj in mode.case.objects}]
            for mode in family.modes}


def layouts(family: ModeFamily, nodes: tuple[Variable, ...],
            bases: dict[str, int]) -> dict[str, list[dict[str, Any]]]:
    """The per-mode placements one assignment of variable bases denotes."""
    plans: dict[str, list[dict[str, Any]]] = {mode.name: [] for mode in family.modes}
    for node in nodes:
        for mode_name, identifier in node.members:
            plans[mode_name].append({"id": identifier, "arena": node.arena,
                                     "base": bases[node.name]})
    return {name: sorted(rows, key=lambda row: row["id"]) for name, rows in plans.items()}


def check_layout_family(family: ModeFamily, plans: object) -> list[str]:
    """Each mode's own layout through the single-trace checker; no switch rule here."""
    if not isinstance(plans, dict) or set(plans) != {mode.name for mode in family.modes}:
        return ["schema: one placement is required for each admitted mode"]
    return [f"{mode.name}: {finding}" for mode in family.modes
            for finding in memory.check_placement(mode.case, plans[mode.name])]


def check_single_layout(family: ModeFamily, placement: object) -> list[str]:
    """Independent pairwise check of one fixed layout against the all-mode relation.

    The overlap test and the extent test are restated here on purpose: this checker
    shares no conflict predicate, ordering or adjacency structure with the search it
    checks, and it reaches the relation directly from the declared lifetimes. Every
    identity needs a base, because one layout has to serve every admitted mode.
    """
    if not isinstance(placement, list):
        return ["schema: placement must be a list"]
    findings: list[str] = []
    bases: dict[str, int] = {}
    declared = {identity.id: identity for identity in family.identities}
    capacities = {arena.id: arena.capacity for arena in family.arenas}
    for index, raw in enumerate(placement):
        label = f"placement[{index}]"
        try:
            row = _object(raw, {"id", "arena", "base"}, label)
            identifier = _text(row["id"], f"{label}.id")
            arena_id = _text(row["arena"], f"{label}.arena")
            base = _count(row["base"], f"{label}.base")
        except memory.CaseError as error:
            findings.append(f"schema: {error}")
            continue
        if identifier in bases:
            findings.append(f"identity: duplicate object {identifier}")
        if identifier not in declared:
            findings.append(f"identity: unknown object {identifier}")
            continue
        identity = declared[identifier]
        if arena_id != identity.arena:
            findings.append(f"ownership: {identifier} cannot change arena {identity.arena}")
        if base % identity.alignment:
            findings.append(f"alignment: {identifier} base is not a multiple of "
                            f"{identity.alignment}")
        if base + identity.size > capacities[identity.arena]:
            findings.append(f"capacity: {identifier} exceeds arena {identity.arena}")
        bases[identifier] = base
    findings.extend(f"identity: missing object {name}"
                    for name in sorted(set(declared) - set(bases)))
    for mode in family.modes:
        for index, left in enumerate(mode.case.objects):
            for right in mode.case.objects[index + 1:]:
                if left.id not in bases or right.id not in bases or left.arena != right.arena:
                    continue
                if left.start >= right.reuse or right.start >= left.reuse:
                    continue
                low, high = bases[left.id], bases[right.id]
                if max(low, high) < min(low + left.size, high + right.size):
                    findings.append(f"overlap: {left.id}/{right.id} share bytes while both are "
                                    f"reserved in mode {mode.name}")
    return findings


def replay_by_mode(family: ModeFamily, placement: object) -> list[str]:
    """A second, independent reading of one fixed layout, mode by mode.

    The single-trace checker decides one schedule. A layout serving every mode is
    exactly one every mode's own checker accepts, so agreement between this reading
    and the pairwise one is a cross-check rather than a restatement.
    """
    if not isinstance(placement, list):
        return ["schema: placement must be a list"]
    return check_layout_family(family, projections(family, placement))


def check_binding_family(family: ModeFamily, plans: object) -> list[str]:
    """Check one layout per mode, the declared switch rule and the retained bases.

    Per-mode legality is the single-trace checker's. What is added is the only thing
    that makes a family of layouts one claim: nothing may be live where a mode is
    left or entered unless that transition retains it, and a retained identity keeps
    one base on both sides of the switch.
    """
    findings = check_layout_family(family, plans)
    if not isinstance(plans, dict):
        return findings
    findings.extend(check_switch_rule(family))
    bases: dict[str, dict[str, int]] = {}
    for name, rows in plans.items():
        if not isinstance(rows, list):
            continue
        bases[name] = {row["id"]: row["base"] for row in rows
                       if isinstance(row, dict) and isinstance(row.get("id"), str)
                       and type(row.get("base")) is int}
    for transition in family.binding.transitions:
        left = bases.get(transition.source, {})
        right = bases.get(transition.target, {})
        findings.extend(
            f"{transition.source}->{transition.target}: retained {name} moves from "
            f"{left[name]} to {right[name]} across the switch"
            for name in transition.retained
            if name in left and name in right and left[name] != right[name])
    return findings


def charge(family: ModeFamily, plans: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    """The family's charge: the maximum over modes of each arena's own span.

    Spans come from the single-trace function, one mode at a time, so the quantity
    is the existing one. Bytes in distinct arenas never compensate one another, so
    the maximum is taken inside an arena and the arenas are never summed. Call this
    only on checked plans; an invalid one raises rather than returning a number.
    """
    spans = [memory.placement_spans(mode.case, plans[mode.name]) for mode in family.modes]
    return {arena.id: max(row[arena.id] for row in spans) for arena in family.arenas}


def _fit(nodes: tuple[Variable, ...], neighbours: dict[str, set[str]], height: int,
         work: Work) -> tuple[str, dict[str, int] | None]:
    """Complete aligned integer DFS over the graph; no interval order is assumed.

    Ordering is a heuristic over degree and size and decides nothing: every base in
    the aligned range is tried for every variable, so refusal at a height is a
    complete refusal for that height unless the budget cut the search short.
    """
    if not work.take():
        return "incomplete", None
    order = sorted(nodes, key=lambda node: (-len(neighbours[node.name]), -node.size, node.name))
    chosen: list[tuple[Variable, int]] = []

    def visit(index: int) -> tuple[str, dict[str, int] | None]:
        if index == len(order):
            return "feasible", {node.name: base for node, base in chosen}
        node = order[index]
        for base in range(0, height - node.size + 1, node.alignment):
            if not work.take():
                return "incomplete", None
            if any(previous.name in neighbours[node.name] and base < offset + previous.size
                   and offset < base + node.size for previous, offset in chosen):
                continue
            chosen.append((node, base))
            status, found = visit(index + 1)
            chosen.pop()
            if status != "infeasible":
                return status, found
        return "infeasible", None

    return visit(0)


def solve_model(family: ModeFamily, sharing: str, work_budget: int = 100_000) -> dict[str, Any]:
    """Minimize each arena's charge under one sharing model, by bounded enumeration.

    The lower bound is the maximum over admitted modes of that mode's independently
    computed charged load: any model must fit every mode it admits. The upper bound
    is the globally disjoint standing layout, capped by the declared capacity.
    Enumerating aligned integer bases is knowingly pseudopolynomial in the numerical
    height and says nothing about parameterized complexity. `nodes` counts search
    roots and candidate bases, not wall time or checking cost.
    """
    if type(work_budget) is not int or work_budget < 1:
        raise memory.CaseError("work_budget must be a positive integer")
    work = Work(work_budget)
    nodes = variables(family, sharing)
    edges = interference(family, nodes)
    neighbours = adjacency(nodes, edges)
    standing = standing_bases(family.identities)
    bases: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for arena in family.arenas:
        group = tuple(node for node in nodes if node.arena == arena.id)
        lower = max((memory.peak_load(mode.case, arena.id) for mode in family.modes), default=0)
        ceiling = max((standing[identity.id] + identity.size for identity in family.identities
                       if identity.arena == arena.id), default=0)
        upper = min(ceiling, arena.capacity)
        row: dict[str, Any] = {"arena": arena.id, "owner": arena.owner,
                               "charged_load_lower_bound": lower, "best_span": None,
                               "status": "incomplete", "certificate": None, "attempts": []}
        if not group:
            row.update(status="optimal", best_span=0,
                       certificate={"method": "load-equality", "infeasible_through": None})
        elif lower > arena.capacity:
            row.update(status="infeasible",
                       certificate={"method": "load-exceeds-capacity",
                                    "infeasible_through": arena.capacity})
        elif len(group) > MAX_GRAPH_NODES:
            row["reason"] = f"more than {MAX_GRAPH_NODES} variables in this arena"
        else:
            for height in range(lower, upper + 1):
                before = work.spent
                status, found = _fit(group, neighbours, height, work)
                row["attempts"].append({"height": height, "status": status,
                                        "nodes": work.spent - before})
                if status == "incomplete":
                    row["reason"] = "work budget exhausted"
                    break
                if status == "feasible":
                    if found is None:
                        raise RuntimeError("feasible search returned no witness")
                    bases.update(found)
                    row.update(best_span=height, status="optimal", certificate={
                        "method": "load-equality" if height == lower else "exhaustive",
                        "infeasible_through": None if height == lower else height - 1})
                    break
            else:
                row.update(status="infeasible", certificate={"method": "exhaustive",
                                                             "infeasible_through": upper})
        rows.append(row)
    statuses = {row["status"] for row in rows}
    status = "infeasible" if "infeasible" in statuses else (
        "incomplete" if "incomplete" in statuses else "optimal")
    complete = status == "optimal" and len(bases) == len(nodes)
    return {"model": sharing, "status": status, "work_budget": work.limit, "nodes": work.spent,
            "arenas": rows, "variables": [asdict(node) for node in nodes],
            "edges": [list(edge) for edge in edges],
            "bases": bases if complete else None}


def replay_optimum(nodes: tuple[Variable, ...], receipt: dict[str, Any],
                   accept: Callable[[dict[str, int]], list[str]],
                   work_budget: int = 100_000) -> dict[str, Any]:
    """Independently refuse every layout one unit shorter, by Cartesian enumeration.

    The replay calls neither the search's ordering, pruning nor conflict test: it
    builds whole assignments and asks the independent checker. Arenas carry no edge
    between them, so each is replayed with the witness held fixed elsewhere. A
    cutoff leaves the optimality claim unchecked and never refutes it.
    """
    work = Work(work_budget)
    scope = ("the claimed span and its witness; search traces, heuristics and timing "
             "are not replayed")
    bases = receipt.get("bases")
    if receipt.get("status") != "optimal" or not isinstance(bases, dict):
        return {"status": "not-claimed", "findings": ["receipt claims no complete optimum"],
                "nodes": work.spent, "work_budget": work.limit, "scope": scope}
    findings = accept(bases)
    if findings:
        return {"status": "rejected", "findings": findings, "nodes": work.spent,
                "work_budget": work.limit, "scope": scope}
    for row in receipt["arenas"]:
        group = [node for node in nodes if node.arena == row["arena"]]
        height = row["best_span"]
        if not group or height is None or height <= row["charged_load_lower_bound"]:
            continue
        # Bases legal at height - 1 are exactly these ranges. itertools.product pools
        # each range eagerly, so refuse an oversized pool before building it and then
        # charge one unit of work per whole candidate.
        domains = [range(0, height - node.size, node.alignment) for node in group]
        counts = [len(domain) for domain in domains]
        if any(count == 0 for count in counts):
            continue
        if sum(counts) > work.limit - work.spent:
            return {"status": "incomplete",
                    "findings": [f"{row['arena']}: Cartesian replay exceeds budget"],
                    "nodes": work.spent, "work_budget": work.limit, "scope": scope}
        for candidate in itertools.product(*domains):
            if not work.take():
                return {"status": "incomplete",
                        "findings": [f"{row['arena']}: replay work budget exhausted"],
                        "nodes": work.spent, "work_budget": work.limit, "scope": scope}
            trial = dict(bases) | {node.name: base for node, base
                                   in zip(group, candidate, strict=True)}
            if not accept(trial):
                return {"status": "rejected",
                        "findings": [f"{row['arena']}: a shorter checked layout exists"],
                        "nodes": work.spent, "work_budget": work.limit, "scope": scope}
    return {"status": "verified", "findings": [], "nodes": work.spent,
            "work_budget": work.limit, "scope": scope}


def heuristics(family: ModeFamily, nodes: tuple[Variable, ...],
               edges: list[tuple[str, str]], work_budget: int = 100_000) -> list[dict[str, Any]]:
    """Deterministic first fit at zero and at aligned ends of placed neighbours.

    Every candidate goes through the independent checker; a first fit that finds no
    base, or runs out of budget, yields no candidate rather than a partial one.
    """
    neighbours = adjacency(nodes, edges)
    sizes = {node.name: node.size for node in nodes}
    capacities = {arena.id: arena.capacity for arena in family.arenas}
    reports: list[dict[str, Any]] = []
    for method in METHODS:
        work = Work(work_budget)
        if method == "first-fit-degree":
            order = sorted(nodes, key=lambda n: (-len(neighbours[n.name]), -n.size, n.name))
        elif method == "first-fit-size":
            order = sorted(nodes, key=lambda n: (-n.size, -len(neighbours[n.name]), n.name))
        else:
            order = sorted(nodes, key=lambda n: n.name)
        placed: dict[str, int] = {}
        status = "feasible"
        for node in order:
            conflicts = [(other, placed[other]) for other in sorted(neighbours[node.name])
                         if other in placed]
            candidates = {0} | {(base + sizes[other] + node.alignment - 1)
                                // node.alignment * node.alignment for other, base in conflicts}
            found: int | None = None
            for base in sorted(candidates):
                if not work.take():
                    status = "incomplete"
                    break
                if base + node.size > capacities[node.arena]:
                    continue
                if any(base < other + sizes[name] and other < base + node.size
                       for name, other in conflicts):
                    continue
                found = base
                break
            if found is None:
                if status != "incomplete":
                    status = "no-fit"
                break
            placed[node.name] = found
        candidate: list[dict[str, Any]] | None = None
        findings: list[str] = []
        spans: dict[str, int] | None = None
        if status == "feasible":
            candidate = [{"id": node.name, "arena": node.arena, "base": placed[node.name]}
                         for node in nodes]
            findings = check_single_layout(family, candidate)
            if not findings:
                spans = charge(family, projections(family, candidate))
        reports.append({"method": method, "status": status, "nodes": work.spent,
                        "work_budget": work.limit, "candidate": candidate,
                        "checker_findings": findings, "spans": spans})
    return reports


def per_mode_model(family: ModeFamily, work_budget: int = 100_000) -> dict[str, Any]:
    """(a) Each admitted mode's own optimum, through the existing exact oracle.

    Nothing here binds one mode to another. The charge is the maximum over modes
    because arenas are per owner and modes are alternatives, and it is a lower bound
    no single layout can beat rather than a cost a single layout attains.
    """
    rows: list[dict[str, Any]] = []
    charges: dict[str, int] | None = {arena.id: 0 for arena in family.arenas}
    for mode in family.modes:
        receipt = memory.solve_exact(mode.case, work_budget=work_budget)
        replay = (memory.verify_optimality(mode.case, receipt, work_budget=work_budget)
                  if receipt["status"] == "optimal"
                  else {"status": "not-claimed", "findings": ["no complete optimum claimed"]})
        spans = {row["arena"]: row["best_span"] for row in receipt["arenas"]}
        rows.append({"mode": mode.name, "exact": receipt, "optimality_replay": replay,
                     "spans": spans})
        if receipt["status"] != "optimal" or replay["status"] != "verified":
            charges = None
        elif charges is not None:
            charges = {name: max(value, spans[name]) for name, value in charges.items()}
    nodes = variables(family, "per-mode")
    cross = solve_model(family, "per-mode", work_budget)
    cross_charge: dict[str, int] | None = None
    cross_findings = ["no complete optimum claimed"]
    if cross["bases"] is not None:
        plans = layouts(family, nodes, cross["bases"])
        cross_findings = check_layout_family(family, plans)
        if not cross_findings:
            cross_charge = charge(family, plans)
    return {
        "model": "per-mode optimum", "modes": rows, "charge": charges,
        "graph_cross_check": {"status": cross["status"], "charge": cross_charge,
                              "checker_findings": cross_findings,
                              "agrees": charges is not None and cross_charge == charges},
        "question": "what each admitted mode costs when its layout binds nothing else",
        "scope": "one optimum per trace, checked and replayed by the single-trace oracle; "
                 "two modes solved here do not give one layout for both",
    }


def conservative_model(family: ModeFamily, work_budget: int = 100_000) -> dict[str, Any]:
    """(b) One fixed layout against the all-mode interference graph, checked twice."""
    nodes = variables(family, "conservative")
    edges = interference(family, nodes)
    receipt = solve_model(family, "conservative", work_budget)
    result: dict[str, Any] = {
        "model": "conservative interference graph", "exact": receipt,
        "edges": [list(edge) for edge in edges],
        "not_interval_certificate": chordless_cycle(nodes, edges),
        "heuristics": heuristics(family, nodes, edges, work_budget),
        "question": "what one immutable layout valid in every admitted mode costs",
        "scope": "a graph colouring problem, not an interval one; the search enumerates "
                 "aligned integer bases and proves no complexity result",
    }
    bases = receipt["bases"]
    if bases is None:
        result.update(placement=None, checker_findings=[], mode_replay_findings=[],
                      checkers_agree=True, optimality_replay=None, charge=None)
        return result
    placement = [{"id": node.name, "arena": node.arena, "base": bases[node.name]}
                 for node in nodes]
    pairwise = check_single_layout(family, placement)
    by_mode = replay_by_mode(family, placement)
    result.update(placement=placement, checker_findings=pairwise, mode_replay_findings=by_mode,
                  checkers_agree=bool(pairwise) == bool(by_mode),
                  charge=None if pairwise or by_mode
                  else charge(family, projections(family, placement)),
                  optimality_replay=replay_optimum(
                      nodes, receipt,
                      lambda trial: check_single_layout(
                          family, [{"id": node.name, "arena": node.arena,
                                    "base": trial[node.name]} for node in nodes]),
                      work_budget))
    return result


def binding_model(family: ModeFamily, work_budget: int = 100_000) -> dict[str, Any]:
    """(c) One checked layout per mode, valid only under the declared switch rule.

    A refusal is a result: a family claiming a per-mode layout while an identity is
    live at a switch it does not retain buys nothing, and the findings name it.
    """
    switch = check_switch_rule(family)
    nodes = variables(family, "binding")
    result: dict[str, Any] = {
        "model": "finite binding family", "rule": family.binding.rule,
        "transitions": [asdict(row) for row in family.binding.transitions],
        "switch_findings": switch, "variables": [asdict(node) for node in nodes],
        "question": "what a finite family of prechecked bindings costs, and what makes it valid",
        "scope": "the switch instants and the retained set are supplied premises about the "
                 "composed schedule; R-08-015's temporal-safety discipline at a slot's reuse "
                 "points is a separate obligation this tool does not discharge",
    }
    if switch:
        result.update(status="refused", exact=None, layouts=None, charge=None,
                      checker_findings=switch, optimality_replay=None)
        return result
    receipt = solve_model(family, "binding", work_budget)
    bases = receipt["bases"]
    if bases is None:
        result.update(status=receipt["status"], exact=receipt, layouts=None, charge=None,
                      checker_findings=[], optimality_replay=None)
        return result
    plans = layouts(family, nodes, bases)
    findings = check_binding_family(family, plans)
    result.update(status="checked" if not findings else "refused", exact=receipt, layouts=plans,
                  checker_findings=findings,
                  charge=None if findings else charge(family, plans),
                  optimality_replay=replay_optimum(
                      nodes, receipt,
                      lambda trial: check_binding_family(family, layouts(family, nodes, trial)),
                      work_budget))
    return result


def compare(family: ModeFamily, per_mode: dict[str, Any], conservative: dict[str, Any],
            binding: dict[str, Any]) -> dict[str, Any]:
    """Read the three charges against one another, per arena and never summed."""
    charges = {"per_mode": per_mode["charge"], "binding": binding["charge"],
               "conservative": conservative["charge"]}
    ordered: bool | None = None
    if all(value is not None for value in charges.values()):
        ordered = all(charges["per_mode"][arena.id] <= charges["binding"][arena.id]
                      <= charges["conservative"][arena.id] for arena in family.arenas)
    return {
        "charges": charges, "ordering_holds": ordered,
        "ordering": "per-mode <= binding family <= one conservative layout, in every arena",
        "reason": "a binding family's layout for one mode is a legal layout for that mode, "
                  "and one conservative layout repeated in every mode is a binding family",
        "decides": "what each model costs on this declared family, once an artifact says "
                   "which model it supplies",
        "does_not_decide": "which model an admitted artifact supplies, which the compiler or "
                           "composition exporter decides; and no admission input, R-08-018a "
                           "still admitting non-co-occurrence only where the admitted frame "
                           "or the region structure proves it",
    }


def _family(name: str, identities: list[tuple[str, int]],
            modes: list[tuple[str, list[tuple[str, int, int]]]], rule: str,
            transitions: list[tuple[str, str, int, int, list[str]]],
            capacity: int = 8, alignment: int = 1) -> dict[str, Any]:
    """Build one declared research contract in synthetic byte and time units."""
    return {
        "name": name, "provenance": "synthetic mode-family witness",
        "arenas": [{"id": "arena", "owner": "research-owner", "capacity": capacity}],
        "identities": [{"id": identifier, "arena": "arena", "size": size, "payload": size,
                        "alignment": alignment} for identifier, size in identities],
        "modes": [{"name": mode_name,
                   "lifetimes": [{"id": identifier, "start": start, "payload_end": end,
                                  "authority_end": end, "sweep_end": end, "reuse": end}
                                 for identifier, start, end in rows]}
                  for mode_name, rows in modes],
        "binding": {"rule": rule,
                    "transitions": [{"source": source, "target": target, "at_source": out,
                                     "at_target": back, "retained": retained}
                                    for source, target, out, back, retained in transitions]},
    }


def _pairwise(name: str, pairs: list[tuple[str, str]], instant: int) -> dict[str, Any]:
    """A family whose modes activate one declared pair each, dead at every switch."""
    identities = sorted({identifier for pair in pairs for identifier in pair})
    order = [f"{left}{right}" for left, right in pairs]
    return _family(
        name, [(identifier, 1) for identifier in identities],
        [(f"{left}{right}", [(left, 1, 3), (right, 1, 3)]) for left, right in pairs],
        "dead-at-switch",
        [(order[index], order[(index + 1) % len(order)], instant, 0, [])
         for index in range(len(order))])


def witnesses() -> list[tuple[dict[str, Any], Expectation]]:
    """The declared families and what each is a witness of."""
    triangle: Expectation = {"conservative_exceeds_per_mode": True,
                             "binding_matches_per_mode": True,
                             "binding_matches_conservative": False,
                             "binding_refused": False, "not_interval": False}
    cycle: Expectation = {"conservative_exceeds_per_mode": True,
                          "binding_matches_per_mode": True,
                          "binding_matches_conservative": False,
                          "binding_refused": False, "not_interval": True}
    retained: Expectation = {"conservative_exceeds_per_mode": True,
                             "binding_matches_per_mode": False,
                             "binding_matches_conservative": True,
                             "binding_refused": False, "not_interval": False}
    refused: Expectation = {"conservative_exceeds_per_mode": True,
                            "binding_matches_per_mode": False,
                            "binding_matches_conservative": False,
                            "binding_refused": True, "not_interval": False}
    return [
        (_pairwise("pairwise-modes-ab-ac-bc", [("a", "b"), ("a", "c"), ("b", "c")], 3), triangle),
        (_pairwise("induced-five-cycle", [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"),
                                          ("e", "a")], 3), cycle),
        (_family("retained-cycle-rebinds", [("a", 1), ("b", 1), ("c", 1)],
                 [("m1", [("b", 0, 4), ("a", 2, 6)]), ("m2", [("a", 0, 4), ("c", 2, 6)]),
                  ("m3", [("c", 0, 4), ("b", 2, 6)])],
                 "retained-bases-equal",
                 [("m1", "m2", 4, 0, ["a"]), ("m2", "m3", 4, 0, ["c"]),
                  ("m3", "m1", 4, 0, ["b"])]), retained),
        (_pairwise("live-identity-at-switch", [("a", "b"), ("a", "c"), ("b", "c")], 2), refused),
    ]


def _expected(name: str, item: dict[str, Any], expectation: Expectation) -> list[str]:
    """Bind each witness's verdict to its own computed receipt."""
    charges = item["comparison"]["charges"]
    per_mode, bound, single = charges["per_mode"], charges["binding"], charges["conservative"]
    findings: list[str] = []
    if per_mode is None or single is None:
        return [f"{name}: the per-mode and conservative charges must both complete"]
    greater = all(single[arena] > per_mode[arena] for arena in per_mode)
    if greater != expectation["conservative_exceeds_per_mode"]:
        findings.append(f"{name}: one layout costing more than every per-mode optimum is "
                        f"{expectation['conservative_exceeds_per_mode']}, computed {greater}")
    refused = item["binding"]["status"] == "refused"
    if refused != expectation["binding_refused"]:
        findings.append(f"{name}: binding refusal is {expectation['binding_refused']}, "
                        f"computed {refused}")
    if not refused and bound is None:
        findings.append(f"{name}: an admitted binding family must carry a checked charge")
    if bound is not None:
        if (bound == per_mode) != expectation["binding_matches_per_mode"]:
            findings.append(f"{name}: binding equal to the per-mode charge is "
                            f"{expectation['binding_matches_per_mode']}")
        if (bound == single) != expectation["binding_matches_conservative"]:
            findings.append(f"{name}: binding equal to the one-layout charge is "
                            f"{expectation['binding_matches_conservative']}")
    interval = item["conservative"]["not_interval_certificate"]["status"] == "induced-cycle"
    if interval != expectation["not_interval"]:
        findings.append(f"{name}: an induced cycle of length four or more is "
                        f"{expectation['not_interval']}, computed {interval}")
    return findings


def _invariants(name: str, item: dict[str, Any]) -> list[str]:
    """Checks every case owes, whatever it is a witness of."""
    findings: list[str] = []
    conservative, binding = item["conservative"], item["binding"]
    if conservative["checker_findings"] or conservative["mode_replay_findings"]:
        findings.append(f"{name}: the searched single layout failed its independent checker")
    if not conservative["checkers_agree"]:
        findings.append(f"{name}: the two independent readings of one layout disagree")
    replay = conservative["optimality_replay"]
    if replay is not None and replay["status"] != "verified":
        findings.append(f"{name}: the one-layout optimum did not replay: {replay['findings']}")
    if binding["status"] == "checked":
        if binding["checker_findings"]:
            findings.append(f"{name}: an admitted binding family failed its checker")
        if binding["optimality_replay"]["status"] != "verified":
            findings.append(f"{name}: the binding-family optimum did not replay")
    if not item["per_mode"]["graph_cross_check"]["agrees"]:
        findings.append(f"{name}: the graph search and the single-trace oracle disagree "
                        "on the per-mode charge")
    if item["comparison"]["ordering_holds"] is False:
        findings.append(f"{name}: the three charges are not ordered")
    findings.extend(f"{name}: heuristic {row['method']} emitted a refused candidate"
                    for row in item["conservative"]["heuristics"] if row["checker_findings"])
    return findings


def report(source_revision: str = "unspecified", work_budget: int = 100_000) -> dict[str, Any]:
    """Replay the declared mode families under all three models, with their checks."""
    cases: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw, expectation in witnesses():
        family = parse_family(raw)
        per_mode = per_mode_model(family, work_budget)
        conservative = conservative_model(family, work_budget)
        binding = binding_model(family, work_budget)
        item: dict[str, Any] = {
            "contract": raw, "contract_sha256": family_hash(family),
            "per_mode": per_mode, "conservative": conservative, "binding": binding,
            "comparison": compare(family, per_mode, conservative, binding),
        }
        errors.extend(_invariants(family.name, item))
        errors.extend(_expected(family.name, item, expectation))
        cases.append(item)
    return {
        "schema": "static-memory-modes-v1", "source_revision": source_revision,
        "scope": "finite host research over declared mode families; three checked models, "
                 "no theorem, no measured workload and no admission input",
        "settings": {"work_budget": work_budget, "max_graph_nodes": MAX_GRAPH_NODES,
                     "max_subsets": MAX_SUBSETS,
                     "address_enumeration_in_search": True,
                     "interval_search_used_for_the_graph_model": False},
        "cases": cases, "errors": errors,
        "open_obligations": [
            "which model an admitted artifact supplies, decided by the compiler or the "
            "composition exporter and not by this tool",
            "a proof that a declared mode set is the admitted set, and that each mode's "
            "reservation intervals cover every execution it admits",
            "an implemented switch barrier: the switch rule here is a supplied premise, "
            "and R-08-015's temporal-safety discipline at a slot's reuse points stays owed",
            "a machine-checked optimality argument; the searches and replays are finite",
            "a complexity result for the conservative graph model under the baseline's "
            "binary input encoding",
            "full CHERI representability, bank, owner and pinning constraints",
        ],
    }
