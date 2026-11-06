# SPDX-License-Identifier: Apache-2.0
"""Bounded diagnostic over supplied loan facts, never a source safety verdict.

The contract is docs/languages/vela/loan-analysis.md. Abstract states over the
control-flow graph retain their own capture environments, loan states and
per-conjunct invariant debt sets, merging compatible states at join points and
loop headers. All supplied interpretation, separation, capture and restoration
facts remain explicit unresolved obligations. No operation interprets a Vela
type, calls a library, runs cleanup or checks a proof.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

type Mode = Literal["shared", "exclusive"]
type AccessKind = Literal["read", "write", "move"]
type Overlap = Literal["yes", "no", "unknown"]

_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_MAX_JOIN_STATES = 2


class AnalysisRefusalError(ValueError):
    """Malformed or incompletely explored input; no partial report is returned."""


@dataclass(frozen=True)
class Place:
    owner: str
    fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class Owner:
    name: str
    borrowed: bool = False
    # A projection prefix is a declared field; distinct siblings may be split.
    fields: tuple[tuple[str, ...], ...] = ()
    invariants: tuple[str, ...] = ()


@dataclass(frozen=True)
class Loan:
    name: str
    parent: str
    place: Place
    mode: Mode = "shared"
    scoped: bool = False
    invariant: str | None = None


@dataclass(frozen=True)
class Borrow:
    loan: Loan


@dataclass(frozen=True)
class Access:
    place: Place
    kind: AccessKind = "read"
    via: str | None = None


@dataclass(frozen=True)
class Bind:
    """A wrapper/environment retaining its inputs' complete loan captures."""

    name: str
    captures: tuple[str, ...]


@dataclass(frozen=True)
class Use:
    """Read through retained loans, or read an owner root; not just a name mention.

    Binding, moving and returning descriptors retain their demands without this
    implicit read. This distinction makes suspended-parent diagnostics explicit.
    """

    name: str


@dataclass(frozen=True)
class Drop:
    """End a handle's availability; this never disposes a protocol resource."""

    name: str


@dataclass(frozen=True)
class Move:
    source: str
    target: str


@dataclass(frozen=True)
class Return:
    outcome: str = "return"
    captures: tuple[str, ...] = ()


@dataclass(frozen=True)
class Checkpoint:
    kind: str = "await"


@dataclass(frozen=True)
class OpenInvariant:
    name: str
    clauses: tuple[str, ...] = ()


@dataclass(frozen=True)
class CloseInvariant:
    name: str
    clauses: tuple[str, ...] = ()


@dataclass(frozen=True)
class Nop:
    pass


type Event = (Borrow | Access | Bind | Use | Drop | Move | Return | Checkpoint
              | OpenInvariant | CloseInvariant | Nop)


@dataclass(frozen=True)
class Node:
    name: str
    event: Event = Nop()
    successors: tuple[str, ...] = ()


@dataclass(frozen=True)
class Graph:
    entry: str
    nodes: tuple[Node, ...]


@dataclass(frozen=True)
class Limits:
    owners: int = 64
    nodes: int = 256
    paths: int = 128
    captures: int = 2048
    work: int = 100_000


@dataclass(frozen=True)
class Issue:
    node: str
    kind: str
    resources: tuple[str, ...] = ()


@dataclass(frozen=True)
class Obligation:
    node: str
    kind: str
    resources: tuple[str, ...] = ()
    status: Literal["unresolved"] = field(default="unresolved", init=False)


@dataclass(frozen=True)
class Restoration:
    node: str
    loan: str
    parent: str
    place: Place
    # This is a proposed proof step, with no concrete memory predicate supplied.
    status: Literal["unresolved"] = field(default="unresolved", init=False)


@dataclass(frozen=True)
class PathReport:
    nodes: tuple[str, ...]
    outcome: str
    issues: tuple[Issue, ...]
    obligations: tuple[Obligation, ...]
    restorations: tuple[Restoration, ...]
    returned_loans: tuple[str, ...]
    retained_loans: tuple[str, ...]
    suspended: tuple[Place, ...]
    moved_owners: tuple[str, ...]
    active_invariants: tuple[tuple[str, str], ...] = ()
    open_invariants: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Report:
    paths: tuple[PathReport, ...]
    status: Literal["diagnostic-only"] = field(default="diagnostic-only", init=False)


@dataclass(frozen=True)
class LoweredFunction:
    name: str
    owners: tuple[Owner, ...]
    graph: Graph


class _Budget:
    def __init__(self, limit: int) -> None:
        self.remaining = limit

    def spend(self, amount: int = 1) -> None:
        self.remaining -= amount
        if self.remaining < 0:
            raise AnalysisRefusalError("analysis work budget exhausted; no complete report")


def _name(value: object) -> None:
    if not isinstance(value, str) or len(value) > 128 or not _NAME.fullmatch(value):
        raise AnalysisRefusalError("identities must be nonempty normalized identifiers")


def _projection(value: tuple[str, ...]) -> None:
    if not isinstance(value, tuple) or len(value) > 32:
        raise AnalysisRefusalError("projection must be an immutable path of at most 32 fields")
    for part in value:
        if part != "*":
            _name(part)


def _references(event: Event) -> tuple[str, ...]:
    match event:
        case Borrow(loan):
            return (loan.parent,)
        case Access(via=via) if via is not None:
            return (via,)
        case Bind(captures=names) | Return(captures=names):
            return names
        case Use(name) | Drop(name):
            return (name,)
        case Move(source, _):
            return (source,)
        case _:
            return ()


def _binder(event: Event) -> str | None:
    match event:
        case Borrow(loan):
            return loan.name
        case Bind(name, _) | Move(_, name):
            return name
        case _:
            return None


def _invariant_conjuncts(
    owners: Mapping[str, Owner], name: str, clauses: tuple[str, ...]
) -> tuple[tuple[tuple[str, str], ...], bool]:
    if clauses:
        return tuple((name, clause) for clause in clauses), True
    owner = owners.get(name)
    if owner is not None and owner.invariants:
        return tuple((name, clause) for clause in owner.invariants), True
    return ((name, name),), False


def _validate(
    owners: tuple[Owner, ...], graph: Graph, limits: Limits, budget: _Budget
) -> tuple[dict[str, Node], dict[str, frozenset[str]]]:
    for bound in (limits.owners, limits.nodes, limits.paths, limits.captures, limits.work):
        if type(bound) is not int or bound < 1:
            raise AnalysisRefusalError("analysis limits must be positive integers")
    if not isinstance(graph, Graph):
        raise AnalysisRefusalError("graph must be an immutable Graph record")
    if not isinstance(owners, tuple) or not isinstance(graph.nodes, tuple):
        raise AnalysisRefusalError("owners and nodes must be immutable tuples")
    if not owners or len(owners) > limits.owners or not graph.nodes or len(graph.nodes) > limits.nodes:
        raise AnalysisRefusalError("owner or node budget exhausted, or empty input")
    owner_map: dict[str, Owner] = {}
    capture_count = 0
    for owner in owners:
        budget.spend()
        if not isinstance(owner, Owner):
            raise AnalysisRefusalError("owner must be an immutable Owner record")
        _name(owner.name)
        if owner.name in owner_map or type(owner.borrowed) is not bool:
            raise AnalysisRefusalError("duplicate owner identity or malformed owner mode")
        if not isinstance(owner.fields, tuple) or len(owner.fields) > limits.captures:
            raise AnalysisRefusalError("field declarations must be immutable")
        for path in owner.fields:
            _projection(path)
            budget.spend(len(path) + 1)
            if not path or "*" in path:
                raise AnalysisRefusalError("declared field projections cannot be empty or unknown")
        if len(set(owner.fields)) != len(owner.fields):
            raise AnalysisRefusalError("duplicate field declaration")
        if not isinstance(owner.invariants, tuple) or len(owner.invariants) > limits.captures:
            raise AnalysisRefusalError("invariant declarations must be immutable")
        for clause in owner.invariants:
            _name(clause)
            budget.spend()
        if len(set(owner.invariants)) != len(owner.invariants):
            raise AnalysisRefusalError("duplicate invariant declaration")
        owner_map[owner.name] = owner

    nodes: dict[str, Node] = {}
    known = set(owner_map)
    invariants: set[str] = set()
    opened_conjuncts: set[tuple[str, str]] = set()
    for owner in owners:
        for clause in owner.invariants:
            invariants.add(clause)
            invariants.add(owner.name)
    for node in graph.nodes:
        budget.spend()
        if not isinstance(node, Node):
            raise AnalysisRefusalError("node must be an immutable Node record")
        _name(node.name)
        if node.name in nodes:
            raise AnalysisRefusalError("duplicate graph identity")
        nodes[node.name] = node
        if not isinstance(node.event, (Borrow, Access, Bind, Use, Drop, Move, Return,
                                       Checkpoint, OpenInvariant, CloseInvariant, Nop)):
            raise AnalysisRefusalError("unknown event")
        if isinstance(node.event, Borrow) and not isinstance(node.event.loan, Loan):
            raise AnalysisRefusalError("borrow must contain an immutable Loan record")
        binder = _binder(node.event)
        if isinstance(node.event, (Borrow, Bind, Move)):
            _name(binder)
            if binder is not None:
                known.add(binder)
        if isinstance(node.event, (OpenInvariant, CloseInvariant)):
            _name(node.event.name)
            if not isinstance(node.event.clauses, tuple) or len(node.event.clauses) > limits.captures:
                raise AnalysisRefusalError("invariant clauses must be an immutable tuple")
            for clause in node.event.clauses:
                _name(clause)
                budget.spend()
            if len(set(node.event.clauses)) != len(node.event.clauses):
                raise AnalysisRefusalError("duplicate invariant clause")
            target_owner = owner_map.get(node.event.name)
            if target_owner is not None and target_owner.invariants:
                for clause in node.event.clauses:
                    if clause not in target_owner.invariants:
                        raise AnalysisRefusalError("missing invariant reference")
            if isinstance(node.event, OpenInvariant):
                conjuncts, _ = _invariant_conjuncts(owner_map, node.event.name, node.event.clauses)
                opened_conjuncts.update(conjuncts)
                invariants.add(node.event.name)
                for owner_name, clause in conjuncts:
                    invariants.add(owner_name)
                    invariants.add(clause)

    _name(graph.entry)
    if graph.entry not in nodes:
        raise AnalysisRefusalError("missing entry node")
    for node in graph.nodes:
        budget.spend()
        if not isinstance(node.successors, tuple) or len(node.successors) > limits.nodes:
            raise AnalysisRefusalError("malformed or duplicate edges")
        for successor in node.successors:
            budget.spend()
            _name(successor)
            if successor not in nodes:
                raise AnalysisRefusalError("missing successor")
        if len(set(node.successors)) != len(node.successors):
            raise AnalysisRefusalError("malformed or duplicate edges")
        if isinstance(node.event, Return) and node.successors:
            raise AnalysisRefusalError("return node has successors")
        references = _references(node.event)
        if not isinstance(references, tuple):
            raise AnalysisRefusalError("capture references must be immutable")
        capture_count += len(references)
        if capture_count > limits.captures:
            raise AnalysisRefusalError("capture/reference budget exhausted")
        for reference in references:
            budget.spend()
            _name(reference)
            if reference not in known:
                raise AnalysisRefusalError(f"missing resource reference: {reference}")
        event = node.event
        if isinstance(event, (Borrow, Access)):
            place = event.loan.place if isinstance(event, Borrow) else event.place
            if not isinstance(place, Place):
                raise AnalysisRefusalError("footprint must be an immutable Place record")
            _name(place.owner)
            _projection(place.fields)
            if place.owner not in owner_map:
                raise AnalysisRefusalError("missing place owner")
        if isinstance(event, Borrow):
            if event.loan.mode not in ("shared", "exclusive") or type(event.loan.scoped) is not bool:
                raise AnalysisRefusalError("malformed loan mode")
            if event.loan.invariant is not None:
                _name(event.loan.invariant)
                if event.loan.invariant not in invariants:
                    raise AnalysisRefusalError("missing invariant reference")
        if isinstance(event, Access) and event.kind not in ("read", "write", "move"):
            raise AnalysisRefusalError("unknown access kind")
        if isinstance(event, CloseInvariant):
            conjuncts, _ = _invariant_conjuncts(owner_map, event.name, event.clauses)
            if not all(pair in opened_conjuncts for pair in conjuncts):
                raise AnalysisRefusalError("missing invariant reference")
        if isinstance(event, (Return, Checkpoint)):
            label = event.outcome if isinstance(event, Return) else event.kind
            _name(label)

    # Check forward reachability from entry.
    reached: set[str] = set()
    stack = [graph.entry]
    while stack:
        budget.spend()
        current = stack.pop()
        if current in reached:
            continue
        reached.add(current)
        stack.extend(
            successor for successor in reversed(nodes[current].successors) if successor not in reached
        )
    if reached != set(nodes):
        raise AnalysisRefusalError("unreachable graph nodes")

    # Refuse direct self-loops, non-terminating cycles, or irreducible cycles.
    predecessors: dict[str, list[str]] = {name: [] for name in nodes}
    for node in graph.nodes:
        if node.name in node.successors:
            raise AnalysisRefusalError("cyclic control flow requires an invariant interpretation")
        for successor in node.successors:
            predecessors[successor].append(node.name)

    can_terminate = {name for name, node in nodes.items() if not node.successors}
    rev_stack = list(can_terminate)
    while rev_stack:
        budget.spend()
        current = rev_stack.pop()
        for pred in predecessors[current]:
            if pred not in can_terminate:
                can_terminate.add(pred)
                rev_stack.append(pred)
    if can_terminate != set(nodes):
        raise AnalysisRefusalError("cyclic control flow requires an invariant interpretation")

    # Compute dominators to ensure any cycle is a reducible natural loop.
    all_names = frozenset(nodes)
    dominators: dict[str, frozenset[str]] = {
        name: frozenset({graph.entry}) if name == graph.entry else all_names
        for name in nodes
    }
    changed = True
    while changed:
        changed = False
        for node in graph.nodes:
            if node.name == graph.entry:
                continue
            budget.spend()
            preds = predecessors[node.name]
            if not preds:
                continue
            intersected = set(dominators[preds[0]])
            for pred in preds[1:]:
                intersected &= dominators[pred]
            intersected.add(node.name)
            updated = frozenset(intersected)
            if updated != dominators[node.name]:
                dominators[node.name] = updated
                changed = True

    for node in graph.nodes:
        for successor in node.successors:
            # Natural loop back-edge: header `successor` must have an exit edge.
            if successor in dominators[node.name] and len(nodes[successor].successors) < 2:
                raise AnalysisRefusalError(
                    "cyclic control flow requires an invariant interpretation"
                )

    # Check that removing natural-loop back-edges leaves a DAG (no irreducible cycle).
    incoming = dict.fromkeys(nodes, 0)
    for node in graph.nodes:
        for successor in node.successors:
            if successor not in dominators[node.name]:
                incoming[successor] += 1
    ready = [name for name, count in incoming.items() if count == 0]
    visited = 0
    while ready:
        budget.spend()
        name = ready.pop()
        visited += 1
        for successor in nodes[name].successors:
            if successor not in dominators[name]:
                incoming[successor] -= 1
                if incoming[successor] == 0:
                    ready.append(successor)
    if visited != len(nodes):
        raise AnalysisRefusalError("cyclic control flow requires an invariant interpretation")

    _capture_cycles(graph.nodes, budget)
    return nodes, dominators


def _capture_cycles(nodes: tuple[Node, ...], budget: _Budget) -> None:
    """Refuse cyclic supplied retention facts, without conflating shadowed names."""
    counts: dict[str, int] = {}
    for node in nodes:
        budget.spend()
        name = _binder(node.event)
        if name is not None:
            counts[name] = counts.get(name, 0) + 1
    dependencies: dict[str, set[str]] = {}
    for node in nodes:
        budget.spend()
        name = _binder(node.event)
        if name is not None and counts[name] == 1:
            references = _references(node.event)
            budget.spend(len(references))
            dependencies[name] = set(references)
    pending = set(dependencies)
    while pending:
        ready: set[str] = set()
        for name in pending:
            budget.spend(len(dependencies[name]) + 1)
            if not dependencies[name] & pending:
                ready.add(name)
        if not ready:
            raise AnalysisRefusalError("cyclic loan/capture dependencies")
        pending.difference_update(ready)


def _within(child: Place, parent: Place) -> bool:
    return child.owner == parent.owner and child.fields[:len(parent.fields)] == parent.fields


def _containment(child: Place, parent: Place) -> Overlap:
    """A repeated unknown index spelling establishes no index identity."""
    if child.owner != parent.owner:
        return "no"
    unknown = False
    for child_field, parent_field in zip(child.fields, parent.fields, strict=False):
        if child_field == "*" or parent_field == "*":
            unknown = True
        elif child_field != parent_field:
            return "no"
    if len(child.fields) < len(parent.fields):
        return "unknown" if unknown else "no"
    return "unknown" if unknown else "yes"


def _overlap(left: Place, right: Place,
             fields_by_owner: dict[str, frozenset[tuple[str, ...]]]) -> Overlap:
    if left.owner != right.owner:
        return "no"
    if _within(left, right):
        return "unknown" if "*" in right.fields else "yes"
    if _within(right, left):
        return "unknown" if "*" in left.fields else "yes"
    for index, (first, second) in enumerate(zip(left.fields, right.fields, strict=False)):
        if first != second:
            fields = fields_by_owner[left.owner]
            if (first != "*" and second != "*" and left.fields[:index + 1] in fields
                    and right.fields[:index + 1] in fields):
                return "no"
            return "unknown"
        if first == "*":
            return "unknown"
    return "unknown"


@dataclass(frozen=True)
class _Value:
    captures: frozenset[str]
    # Only a direct handle (or its move) grants a route for an access/reborrow.
    handle: str | None = None


def _transfer_demand_backward(node: Node, demanded_after: frozenset[str]) -> frozenset[str]:
    before = set(demanded_after)
    match node.event:
        case Drop(name):
            before.discard(name)
        case Move(source, target):
            before.discard(target)
            before.add(source)
        case Bind(name, captures):
            before.discard(name)
            before.update(captures)
        case Borrow(loan):
            before.discard(loan.name)
            before.add(loan.parent)
        case Use(name):
            before.add(name)
        case Access(via=via) if via is not None:
            before.add(via)
        case Return(captures=names):
            before.update(names)
        case _:
            pass
    return frozenset(before)


def _compute_cfg_liveness(
    graph: Graph, nodes: dict[str, Node], budget: _Budget
) -> tuple[dict[str, frozenset[str]], dict[str, frozenset[str]], dict[str, frozenset[str]]]:
    demanded_before: dict[str, frozenset[str]] = dict.fromkeys(nodes, frozenset())
    demanded_after: dict[str, frozenset[str]] = dict.fromkeys(nodes, frozenset())
    reachable_refs: dict[str, frozenset[str]] = {
        name: frozenset(_references(node.event)) for name, node in nodes.items()
    }
    ordered = tuple(reversed(graph.nodes))
    changed = True
    while changed:
        changed = False
        for node in ordered:
            budget.spend()
            after = frozenset().union(*(demanded_before[succ] for succ in node.successors))
            before = _transfer_demand_backward(node, after)
            refs = frozenset(_references(node.event)).union(
                *(reachable_refs[succ] for succ in node.successors)
            )
            if (after != demanded_after[node.name]
                    or before != demanded_before[node.name]
                    or refs != reachable_refs[node.name]):
                demanded_after[node.name] = after
                demanded_before[node.name] = before
                reachable_refs[node.name] = refs
                changed = True
    return demanded_before, demanded_after, reachable_refs


class _State:
    def __init__(
        self,
        owners: dict[str, Owner],
        fields: dict[str, frozenset[tuple[str, ...]]],
        budget: _Budget,
        entry_name: str,
    ) -> None:
        self.owners = owners
        self.fields = fields
        self.budget = budget
        self.nodes: tuple[str, ...] = ()
        self.outcome = "fallthrough"
        self.issues: list[Issue] = []
        self.obligations: list[Obligation] = [
            Obligation(entry_name, "supplied-interpretation", tuple(owners)),
            Obligation(entry_name, "supplied-separation", tuple(owners)),
        ]
        self.restorations: list[Restoration] = []
        self.values: dict[str, _Value] = {}
        self.loans: dict[str, Loan] = {}
        self.parents: dict[str, str] = {}
        self.last_demand_node: dict[str, str] = {}
        self.seen_binders: dict[str, str] = {}
        self.active: set[str] = set()
        self.opened: set[tuple[str, str]] = set()
        self.active_invariants: set[tuple[str, str]] = {
            (owner.name, clause)
            for owner in owners.values()
            for clause in owner.invariants
        }
        self.explicit_invariants: dict[tuple[str, str], bool] = {
            (owner.name, clause): True
            for owner in owners.values()
            for clause in owner.invariants
        }
        self.returned: frozenset[str] = frozenset()
        self.moved: set[str] = set()
        self.invalid: set[str] = set()

    def clone(self) -> _State:
        self.budget.spend()
        copy = _State.__new__(_State)
        copy.owners = self.owners
        copy.fields = self.fields
        copy.budget = self.budget
        copy.nodes = self.nodes
        copy.outcome = self.outcome
        copy.issues = list(self.issues)
        copy.obligations = list(self.obligations)
        copy.restorations = list(self.restorations)
        copy.values = dict(self.values)
        copy.loans = dict(self.loans)
        copy.parents = dict(self.parents)
        copy.last_demand_node = dict(self.last_demand_node)
        copy.seen_binders = dict(self.seen_binders)
        copy.active = set(self.active)
        copy.opened = set(self.opened)
        copy.active_invariants = set(self.active_invariants)
        copy.explicit_invariants = dict(self.explicit_invariants)
        copy.returned = self.returned
        copy.moved = set(self.moved)
        copy.invalid = set(self.invalid)
        return copy

    def domain_signature(self) -> object:
        return (
            frozenset(self.values.items()),
            frozenset(self.active),
            frozenset(self.opened),
            frozenset(self.active_invariants),
            frozenset(self.moved),
            frozenset(self.invalid),
            frozenset(self.issues),
            frozenset(self.obligations),
            frozenset(self.restorations),
        )

    def merge_from(self, other: _State, live_refs: frozenset[str]) -> bool:
        self.budget.spend()
        before_sig = self.domain_signature()
        self.nodes = tuple(dict.fromkeys((*self.nodes, *other.nodes)))
        merged_values: dict[str, _Value] = {}
        for key in self.values.keys() | other.values.keys():
            if key in self.values and key in other.values:
                left = self.values[key]
                right = other.values[key]
                handle = left.handle if left.handle == right.handle else (left.handle or right.handle)
                merged_values[key] = _Value(left.captures | right.captures, handle)
            elif key not in live_refs:
                merged_values[key] = self.values.get(key) or other.values[key]
        self.values = merged_values
        self.loans.update(other.loans)
        self.parents.update(other.parents)
        self.last_demand_node.update(other.last_demand_node)
        self.seen_binders.update(other.seen_binders)
        self.active |= other.active
        self.opened |= other.opened
        self.active_invariants &= other.active_invariants
        self.explicit_invariants.update(other.explicit_invariants)
        self.returned |= other.returned
        self.moved |= other.moved
        self.invalid |= other.invalid
        seen_issues = set(self.issues)
        for issue in other.issues:
            if issue not in seen_issues:
                self.issues.append(issue)
                seen_issues.add(issue)
        seen_obligations = set(self.obligations)
        for obligation in other.obligations:
            if obligation not in seen_obligations:
                self.obligations.append(obligation)
                seen_obligations.add(obligation)
        seen_restorations = set(self.restorations)
        for restoration in other.restorations:
            if restoration not in seen_restorations:
                self.restorations.append(restoration)
                seen_restorations.add(restoration)
        return self.domain_signature() != before_sig

    def issue(self, node: Node, kind: str, *resources: str) -> None:
        item = Issue(node.name, kind, resources)
        if item not in self.issues:
            self.issues.append(item)

    def obligation(self, node: Node, kind: str, *resources: str) -> None:
        item = Obligation(node.name, kind, resources)
        if item not in self.obligations:
            self.obligations.append(item)

    def _invariant_res(self, pair: tuple[str, str]) -> tuple[str, ...]:
        if self.explicit_invariants.get(pair, pair[0] != pair[1]):
            return pair
        return (pair[0],)

    def _is_invariant_open(self, place_owner: str, invariant: str) -> bool:
        if (place_owner, invariant) in self.opened or (invariant, invariant) in self.opened:
            return True
        return any(owner == invariant or clause == invariant for owner, clause in self.opened)

    def ancestors(self, names: frozenset[str] | set[str]) -> frozenset[str]:
        result = set(names)
        pending = list(names)
        while pending:
            self.budget.spend()
            parent = self.parents.get(pending.pop())
            if parent in self.loans and parent not in result:
                result.add(parent)
                pending.append(parent)
        return frozenset(result)

    def live_loans(self, demanded_names: frozenset[str]) -> frozenset[str]:
        seeds: set[str] = set()
        for name in demanded_names:
            value = self.values.get(name)
            if value is not None:
                seeds.update(value.captures)
        return self.ancestors(seeds)

    def compare(self, node: Node, place: Place, other: str) -> Overlap:
        self.budget.spend()
        overlap = _overlap(place, self.loans[other].place, self.fields)
        if overlap == "unknown":
            self.obligation(node, "overlap", place.owner, *place.fields, other)
        return overlap

    def containment(self, node: Node, child: Place, parent: Place, grant: str) -> Overlap:
        self.budget.spend()
        relation = _containment(child, parent)
        if relation == "unknown":
            self.obligation(node, "footprint-containment", grant, child.owner, *child.fields)
        return relation

    def borrow(self, node: Node, name: str) -> None:
        loan = self.loans[name]
        parent = self.parents[name]
        prior_issues = len(self.issues)
        self.obligation(node, "loan-interpretation", name, parent)
        if "*" in loan.place.fields:
            self.obligation(node, "unknown-footprint", name, loan.place.owner, *loan.place.fields)
        if loan.place.owner in self.moved:
            self.issue(node, "use-after-owner-move", loan.place.owner)
        if parent in self.owners:
            parent_place = Place(parent)
        else:
            parent_loan = self.loans[parent]
            parent_place = parent_loan.place
            if parent not in self.active:
                self.issue(node, "borrow-parent-has-no-grant", name, parent)
            if parent_loan.mode == "shared" and loan.mode == "exclusive":
                self.issue(node, "exclusive-from-shared", name, parent)
        if self.containment(node, loan.place, parent_place, parent) == "no":
            self.issue(node, "reborrow-outside-parent", name, parent)
        if loan.invariant is not None and not self._is_invariant_open(loan.place.owner, loan.invariant):
            self.issue(node, "loan-invariant-not-open", name, loan.invariant)
        ancestors = self.ancestors({name}) - {name}
        for other in sorted(self.active - ancestors):
            if loan.mode == "exclusive" or self.loans[other].mode == "exclusive":
                overlap = self.compare(node, loan.place, other)
                if overlap == "yes":
                    self.issue(node, "competing-loans", name, other)
        if len(self.issues) == prior_issues:
            self.active.add(name)
        else:
            self.invalid.add(name)

    def access(self, node: Node, event: Access, route: str | None) -> None:
        self.obligation(node, "access-interpretation", event.place.owner, event.kind)
        self.obligation(node, "effect-interpretation", event.place.owner, event.kind)
        if "*" in event.place.fields:
            self.obligation(node, "unknown-footprint", event.place.owner, *event.place.fields)
        if event.kind != "read":
            self.obligation(node, "content-refinement-invalidation", event.place.owner)
        if event.place.owner in self.moved:
            self.issue(node, "use-after-owner-move", event.place.owner)
        if not event.place.fields:
            for pair in sorted(self.opened):
                if pair[0] == event.place.owner and self.explicit_invariants.get(pair, False):
                    self.issue(node, "open-invariant-whole-receiver", *self._invariant_res(pair))
        if event.via is not None:
            if route is None:
                return
            if route not in self.active:
                self.issue(node, "access-route-has-no-grant", route)
                return
            loan = self.loans[route]
            if self.containment(node, event.place, loan.place, route) == "no":
                self.issue(node, "access-outside-loan", route)
            if event.kind != "read" and loan.mode != "exclusive":
                self.issue(node, "write-through-shared", route)
            if event.kind == "move":
                self.issue(node, "move-through-loan-unsupported", route)
        ancestors = self.ancestors({route}) if route is not None else frozenset()
        for other in sorted(self.active - ancestors):
            overlap = self.compare(node, event.place, other)
            if overlap == "no":
                continue
            # An owner/ancestor route cannot bypass a live descendant permission.
            descendant = route is None or route in self.ancestors({other})
            if overlap == "yes" and (descendant or event.kind != "read"
                                     or self.loans[other].mode == "exclusive"):
                self.issue(node, "suspended-parent" if descendant else "conflicting-access", other)
        if event.kind == "move" and event.via is None:
            if event.place.fields:
                self.issue(node, "partial-owner-move-unsupported", event.place.owner)
            else:
                self.moved.add(event.place.owner)

    def end_dead(self, fallback_node: str, live: frozenset[str]) -> None:
        # Every child is deeper than its ancestor. Lexical names only break ties.
        ending = sorted(
            self.active - live,
            key=lambda name: (-len(self.ancestors({name})), name),
        )
        for name in ending:
            self.budget.spend()
            loan = self.loans[name]
            at_node = self.last_demand_node.get(name, fallback_node)
            restoration = Restoration(at_node, name, self.parents[name], loan.place)
            if restoration not in self.restorations:
                self.restorations.append(restoration)
            obligation = Obligation(at_node, "restoration", (name, self.parents[name]))
            if obligation not in self.obligations:
                self.obligations.append(obligation)
            self.active.remove(name)

    def step(self, node: Node, demanded_after: frozenset[str]) -> None:
        self.budget.spend()
        if not self.nodes or self.nodes[-1] != node.name:
            self.nodes = (*self.nodes, node.name)
        event = node.event
        used: set[str] = set()
        for name in _references(event):
            self.budget.spend()
            if name in self.owners:
                continue
            if name not in self.values:
                self.issue(node, "unavailable-name", name)
            elif not isinstance(event, Drop):
                self.budget.spend(len(self.values[name].captures))
                used.update(self.values[name].captures)
        binder = _binder(event)
        fresh = True
        if binder is not None:
            prior = self.seen_binders.get(binder)
            if binder in self.owners or (prior is not None and prior != node.name):
                fresh = False
                self.issue(node, "ambiguous-name", binder)
            else:
                self.seen_binders[binder] = node.name
        creates: str | None = None
        route: str | None = None
        match event:
            case Borrow(loan):
                if fresh:
                    parent = self.values.get(loan.parent)
                    if loan.parent in self.owners:
                        route = loan.parent
                    elif parent is not None and parent.handle is not None:
                        route = parent.handle
                    else:
                        self.issue(node, "borrow-parent-has-no-grant", loan.parent)
                    if route is not None:
                        self.loans[loan.name] = loan
                        self.parents[loan.name] = route
                        self.values[loan.name] = _Value(frozenset({loan.name}), loan.name)
                        creates = loan.name
            case Access(via=via) if via is not None:
                value = self.values.get(via)
                if value is not None:
                    route = value.handle
                if route is None:
                    self.issue(node, "access-route-has-no-grant", via)
            case Bind(name, captures):
                if fresh:
                    if set(captures) & self.owners.keys():
                        self.issue(node, "owner-capture-unsupported", name)
                    self.values[name] = _Value(frozenset(used))
                    self.obligation(node, "capture-interpretation", name, *sorted(used))
            case Move(source, target):
                if source in self.owners:
                    self.issue(node, "owner-handle-move-unsupported", source)
                elif fresh and source in self.values:
                    self.values[target] = self.values.pop(source)
            case Drop(name):
                if name in self.owners:
                    self.issue(node, "owner-drop-unsupported", name)
                else:
                    self.values.pop(name, None)
            case Return(captures=names):
                if set(names) & self.owners.keys():
                    self.issue(
                        node,
                        "owner-return-unsupported",
                        *sorted(set(names) & self.owners.keys()),
                    )
                self.returned = frozenset(used)
            case _:
                pass

        if creates is not None:
            for anc in self.ancestors({creates}):
                self.last_demand_node[anc] = node.name
        if used and not isinstance(event, Drop):
            for anc in self.ancestors(used):
                self.last_demand_node[anc] = node.name

        live_after = (
            self.ancestors(self.returned)
            if not node.successors
            else self.live_loans(demanded_after)
        )
        match event:
            case Borrow() if creates is not None:
                self.borrow(node, creates)
            case Access():
                self.access(node, event, route)
            case Use(name):
                if name in self.owners:
                    self.access(node, Access(Place(name)), None)
                else:
                    for captured in sorted(used):
                        self.access(node, Access(self.loans[captured].place, via=name), captured)
            case OpenInvariant(name, clauses):
                conjuncts, is_explicit = _invariant_conjuncts(self.owners, name, clauses)
                for pair in conjuncts:
                    self.explicit_invariants[pair] = is_explicit
                    res = self._invariant_res(pair)
                    if pair in self.opened:
                        self.issue(node, "invariant-already-open", *res)
                    self.opened.add(pair)
                    self.active_invariants.discard(pair)
                    self.obligation(node, "invariant-open", *res)
                owner = self.owners.get(name)
                if owner is not None and owner.invariants:
                    for clause in owner.invariants:
                        if (name, clause) in self.active_invariants:
                            self.obligation(node, "invariant-active", name, clause)
            case CloseInvariant(name, clauses):
                conjuncts, is_explicit = _invariant_conjuncts(self.owners, name, clauses)
                for pair in conjuncts:
                    if pair not in self.explicit_invariants:
                        self.explicit_invariants[pair] = is_explicit
                    res = self._invariant_res(pair)
                    if pair not in self.opened:
                        self.issue(node, "invariant-not-open", *res)
                    for loan in sorted(self.active):
                        inv = self.loans[loan].invariant
                        if (inv is not None
                                and loan in live_after
                                and inv in (pair[0], pair[1], f"{pair[0]}.{pair[1]}")):
                            self.issue(node, "invariant-closed-with-live-loan", *res, loan)
                    self.opened.discard(pair)
                    owner = self.owners.get(pair[0])
                    if owner is not None and pair[1] in owner.invariants:
                        self.active_invariants.add(pair)
                    self.obligation(node, "invariant-close", *res)
            case Checkpoint(kind):
                self.issue(node, "unsupported-boundary", kind)
                self.obligation(node, "boundary-interpretation", kind, *sorted(self.active))
                for pair in sorted(self.opened):
                    self.issue(node, "open-invariant-at-boundary", *self._invariant_res(pair))
                for loan in sorted(self.active & live_after):
                    if self.loans[loan].scoped:
                        self.issue(node, "scoped-loan-at-boundary", loan)
            case Return(tag, _):
                self.outcome = tag
            case _:
                pass

        self.end_dead(node.name, live_after)

    def finalize(self, terminal: Node) -> PathReport:
        for pair in sorted(self.opened):
            self.issue(terminal, "unclosed-invariant", *self._invariant_res(pair))
        # Retaining a descendant retains every ancestor's restoration duty and
        # scope. An unscoped descriptor cannot launder a scoped parent grant.
        for name in sorted(self.ancestors(self.returned)):
            if self.loans[name].scoped:
                self.issue(terminal, "scoped-loan-escape", name)
        for name in sorted(self.returned):
            loan = self.loans[name]
            if name in self.invalid:
                self.issue(terminal, "invalid-loan-escape", name)
            if loan.mode != "shared":
                self.issue(terminal, "exclusive-loan-escape", name)
            if not self.owners[loan.place.owner].borrowed:
                self.issue(terminal, "local-loan-escape", name)
            self.obligation(terminal, "returned-loan-lifetime", name, loan.place.owner)
        suspended = tuple(
            sorted(
                {self.loans[name].place for name in self.active},
                key=lambda place: (place.owner, place.fields),
            )
        )
        return PathReport(
            self.nodes,
            self.outcome,
            tuple(self.issues),
            tuple(self.obligations),
            tuple(self.restorations),
            tuple(sorted(self.returned)),
            tuple(sorted(self.active)),
            suspended,
            tuple(sorted(self.moved)),
            tuple(sorted(self.active_invariants)),
            tuple(sorted(self.opened)),
        )


def analyze(owners: tuple[Owner, ...], graph: Graph, limits: Limits | None = None) -> Report:
    """Return a complete, deterministic diagnostic or raise AnalysisRefusalError.

    Facts are supplied abstract inputs, not source interpretation or proved laws.
    Even a report with no issues contains unresolved interpretation obligations.
    Exhaustion at any stage discards all path results rather than returning a
    deceptively complete prefix. The API performs no file or external I/O.

    For example, ``analyze((Owner("input", borrowed=True),), Graph("lend", (
    Node("lend", Borrow(Loan("view", "input", Place("input"))), ("read",)),
    Node("read", Use("view")),)))`` proposes ending ``view`` after ``read``.
    The resulting restoration and interpretation obligations remain unresolved.
    """
    if limits is None:
        limits = Limits()
    if not isinstance(limits, Limits):
        raise AnalysisRefusalError("limits must be an immutable Limits record")
    budget = _Budget(limits.work)
    nodes, dominators = _validate(owners, graph, limits, budget)
    demanded_before, demanded_after, reachable_refs = _compute_cfg_liveness(graph, nodes, budget)
    owner_map = {owner.name: owner for owner in owners}
    budget.spend(sum(len(owner.fields) for owner in owners))
    fields = {owner.name: frozenset(owner.fields) for owner in owners}

    in_degree = dict.fromkeys(nodes, 0)
    for node in graph.nodes:
        for successor in node.successors:
            in_degree[successor] += 1
    has_loops = any(
        successor in dominators[node.name]
        for node in graph.nodes
        for successor in node.successors
    )

    # Topological order of the forward DAG (excluding natural-loop back-edges).
    postorder: list[str] = []
    visited_rpo: set[str] = set()

    def _dfs_rpo(curr: str) -> None:
        visited_rpo.add(curr)
        for succ in nodes[curr].successors:
            if succ not in dominators[curr] and succ not in visited_rpo:
                _dfs_rpo(succ)
        postorder.append(curr)

    _dfs_rpo(graph.entry)
    rpo_index = {name: idx for idx, name in enumerate(reversed(postorder))}

    # Forward abstract interpretation with join-point and loop-header merging.
    join_states: dict[str, dict[frozenset[str], _State]] = {
        name: {} for name, deg in in_degree.items() if deg > 1
    }
    pending_joins: dict[str, list[frozenset[str]]] = {
        name: [] for name, deg in in_degree.items() if deg > 1
    }
    branch_worklist: list[tuple[str, _State]] = [
        (graph.entry, _State(owner_map, fields, budget, graph.entry))
    ]
    terminal_reports: list[PathReport] = []
    loop_terminals: dict[tuple[str, str], int] = {}

    while branch_worklist or any(pending_joins.values()):
        budget.spend()
        if branch_worklist:
            node_name, state = branch_worklist.pop()
        else:
            next_join = min(
                (name for name, keys in pending_joins.items() if keys),
                key=lambda name: rpo_index.get(name, 0),
            )
            env_key = pending_joins[next_join].pop(0)
            node_name = next_join
            state = join_states[next_join][env_key].clone()

        node = nodes[node_name]
        state.step(node, demanded_after[node_name])
        if not node.successors:
            report_item = state.finalize(node)
            if has_loops:
                tkey = (node_name, report_item.outcome)
                if tkey in loop_terminals:
                    terminal_reports[loop_terminals[tkey]] = report_item
                    continue
                loop_terminals[tkey] = len(terminal_reports)
            terminal_reports.append(report_item)
            if len(terminal_reports) > limits.paths:
                raise AnalysisRefusalError("complete path budget exhausted")
            continue

        for index, successor in enumerate(reversed(node.successors)):
            branch = state if index == len(node.successors) - 1 else state.clone()
            branch.end_dead(node.name, branch.live_loans(demanded_before[successor]))
            if in_degree[successor] > 1:
                live_refs = reachable_refs[successor]
                # Prune dead local bindings before join comparison.
                for key in list(branch.values):
                    if key not in live_refs and not (branch.values[key].captures & branch.active):
                        branch.values.pop(key, None)
                env_key = frozenset(key for key in branch.values if key in live_refs)
                buckets = join_states[successor]
                if env_key in buckets:
                    if not buckets[env_key].merge_from(branch, live_refs):
                        continue
                    queued_key = env_key
                elif len(buckets) < _MAX_JOIN_STATES:
                    buckets[env_key] = branch.clone()
                    queued_key = env_key
                else:
                    queued_key = next(iter(buckets))
                    if not buckets[queued_key].merge_from(branch, live_refs):
                        continue
                if queued_key not in pending_joins[successor]:
                    pending_joins[successor].append(queued_key)
            else:
                branch_worklist.append((successor, branch))

    return Report(tuple(terminal_reports))


# ---------------------------------------------------------------------------
# AST-to-Loan-Graph Lowering Pass (Schema-2 Surface AST -> vela_loans.Graph)
# ---------------------------------------------------------------------------


@dataclass
class _StructInfo:
    fields: tuple[tuple[str, ...], ...]
    views: dict[str, tuple[str, ...]]
    invariants: tuple[str, ...]


def _ast_node(value: object, role: str = "AST node") -> dict[str, object]:
    if not isinstance(value, dict):
        raise AnalysisRefusalError(f"expected {role} mapping")
    return cast("dict[str, object]", value)


def _ast_nodes(value: object, role: str = "AST node list") -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise AnalysisRefusalError(f"expected {role} list")
    return [_ast_node(item, role) for item in value]


def _id_text(value: object) -> str:
    if isinstance(value, str):
        return value
    node = _ast_node(value, "identifier")
    text = node.get("text") or node.get("name")
    if isinstance(text, dict):
        text = text.get("text")
    if not isinstance(text, str):
        raise AnalysisRefusalError("missing identifier text")
    return text.replace(".", "_")


def _type_base_name(type_node: object) -> str | None:
    if not isinstance(type_node, dict):
        return None
    kind = type_node.get("kind")
    if kind == "type":
        name_node = type_node.get("name")
        if isinstance(name_node, dict) and isinstance(name_node.get("text"), str):
            return str(name_node["text"]).split(".")[-1]
    if kind == "modified_type":
        return _type_base_name(type_node.get("type"))
    if kind == "group_type":
        return _type_base_name(type_node.get("type"))
    return None


def _extract_return_lifetime_place(type_node: object) -> Place | None:
    if not isinstance(type_node, dict):
        return None
    kind = type_node.get("kind")
    if kind == "modified_type":
        lifetime = type_node.get("lifetime")
        if isinstance(lifetime, dict) and isinstance(lifetime.get("text"), str):
            parts = [part for part in str(lifetime["text"]).split(".") if part]
            if parts and _NAME.fullmatch(parts[0]):
                return Place(parts[0], tuple(parts[1:]))
        return _extract_return_lifetime_place(type_node.get("type"))
    if kind == "type":
        for arg in _ast_nodes(type_node.get("arguments", [])):
            found = _extract_return_lifetime_place(arg)
            if found is not None:
                return found
    if kind in {"tuple_type", "function_type"}:
        for item in _ast_nodes(type_node.get("elements", type_node.get("parameters", []))):
            found = _extract_return_lifetime_place(item)
            if found is not None:
                return found
    return None


def _collect_structs(declarations: list[dict[str, object]]) -> dict[str, _StructInfo]:
    structs: dict[str, _StructInfo] = {}
    for decl in declarations:
        kind = decl.get("kind")
        if kind == "namespace":
            structs.update(_collect_structs(_ast_nodes(decl.get("declarations", []))))
            continue
        if kind not in {"struct", "record"}:
            continue
        name = _id_text(decl["name"])
        field_paths: list[tuple[str, ...]] = []
        views: dict[str, tuple[str, ...]] = {}
        invariants: list[str] = []
        for field_decl in _ast_nodes(decl.get("fields", [])):
            if field_decl.get("kind") == "field":
                fname = _id_text(field_decl["name"])
                if (fname,) not in field_paths:
                    field_paths.append((fname,))
        for member in _ast_nodes(decl.get("members", [])):
            mkind = member.get("kind")
            if mkind in {"field", "property"}:
                fname = _id_text(member["name"])
                if (fname,) not in field_paths:
                    field_paths.append((fname,))
            elif mkind == "view":
                vname = _id_text(member["name"])
                clauses = _ast_nodes(member.get("clauses", []))
                primary_field: str | None = None
                for clause in clauses:
                    if "name" in clause:
                        primary_field = _id_text(clause["name"])
                        break
                if primary_field is not None:
                    if (primary_field,) not in field_paths:
                        field_paths.append((primary_field,))
                    vpath = (primary_field, vname)
                else:
                    vpath = (vname,)
                views[vname] = vpath
                if vpath not in field_paths:
                    field_paths.append(vpath)
        for contract in _ast_nodes(decl.get("contracts", [])):
            if contract.get("kind") == "invariant":
                label = contract.get("label")
                if isinstance(label, dict) and isinstance(label.get("text"), str):
                    cname = _id_text(label)
                else:
                    cname = name
                if cname not in invariants:
                    invariants.append(cname)
        structs[name] = _StructInfo(tuple(field_paths), views, tuple(invariants))
    return structs


def _find_functions(
    declarations: list[dict[str, object]],
    enclosing_type: str | None = None,
) -> list[tuple[str, dict[str, object], str | None]]:
    found: list[tuple[str, dict[str, object], str | None]] = []
    for decl in declarations:
        kind = decl.get("kind")
        if kind == "namespace":
            found.extend(_find_functions(_ast_nodes(decl.get("declarations", [])), enclosing_type))
        elif kind in {"struct", "record"}:
            tname = _id_text(decl["name"])
            for member in _ast_nodes(decl.get("members", [])):
                if member.get("kind") in {"method", "function"} and member.get("body") is not None:
                    mname = _id_text(member["name"])
                    found.append((f"{tname}.{mname}", member, tname))
                    found.append((mname, member, tname))
        elif kind == "impl":
            tname = _type_base_name(decl.get("target"))
            for member in _ast_nodes(decl.get("members", [])):
                if member.get("kind") in {"method", "function"} and member.get("body") is not None:
                    mname = _id_text(member["name"])
                    if tname is not None:
                        found.append((f"{tname}.{mname}", member, tname))
                    found.append((mname, member, tname))
        elif kind in {"function", "method", "definition"} and decl.get("body") is not None:
            fname = _id_text(decl["name"])
            if enclosing_type is not None:
                found.append((f"{enclosing_type}.{fname}", decl, enclosing_type))
            found.append((fname, decl, enclosing_type))
    return found


class _FunctionLowerer:
    def __init__(
        self,
        fn_name: str,
        fn_node: dict[str, object],
        enclosing_type: str | None,
        structs: dict[str, _StructInfo],
    ) -> None:
        self.fn_name = fn_name
        self.fn_node = fn_node
        self.enclosing_type = enclosing_type
        self.structs = structs
        self.owners: dict[str, Owner] = {}
        self.owner_types: dict[str, str] = {}
        self.owner_fields: dict[str, set[tuple[str, ...]]] = {}
        self.owner_views: dict[str, dict[str, tuple[str, ...]]] = {}
        self.owner_invariants: dict[str, list[str]] = {}
        # Map variable name -> canonical handle name (for loans or wrappers).
        self.handles: dict[str, str] = {}
        # Map loan handle name -> Place.
        self.handle_places: dict[str, Place] = {}
        self.handle_modes: dict[str, Mode] = {}
        self.nodes: list[Node] = []
        self.edges: dict[str, list[str]] = {}
        self.events: dict[str, Event] = {}
        self.counter = 0
        self.loan_counter = 0
        self.return_lifetime_place = _extract_return_lifetime_place(fn_node.get("return_type"))

    def _fresh_node(self, prefix: str = "n", event: Event | None = None) -> str:
        self.counter += 1
        name = f"{prefix}_{self.counter}"
        self.events[name] = Nop() if event is None else event
        self.edges[name] = []
        return name

    def _fresh_loan(self, prefix: str = "loan") -> str:
        self.loan_counter += 1
        return f"_{prefix}_{self.loan_counter}"

    def _connect(self, src: str | None, dst: str) -> None:
        if src is not None and isinstance(self.events.get(src), Return):
            return
        if src is not None and dst not in self.edges[src]:
            self.edges[src].append(dst)

    def _emit(self, current: str | None, event: Event, prefix: str = "n") -> str:
        if (
            current is not None
            and self.events[current] == Nop()
            and not self.edges[current]
            and not prefix.startswith(("join", "header"))
        ):
            self.events[current] = event
            return current
        nxt = self._fresh_node(prefix, event)
        self._connect(current, nxt)
        return nxt

    def _register_owner(
        self,
        name: str,
        *,
        borrowed: bool,
        type_name: str | None = None,
    ) -> None:
        if not _NAME.fullmatch(name):
            return
        if name not in self.owner_fields:
            self.owner_fields[name] = set()
            self.owner_views[name] = {}
            self.owner_invariants[name] = []
        if type_name is not None:
            self.owner_types[name] = type_name
            info = self.structs.get(type_name)
            if info is not None:
                self.owner_fields[name].update(info.fields)
                self.owner_views[name].update(info.views)
                for inv in info.invariants:
                    if inv not in self.owner_invariants[name]:
                        self.owner_invariants[name].append(inv)
        self.owners[name] = Owner(
            name,
            borrowed=borrowed,
            fields=tuple(sorted(self.owner_fields[name])),
            invariants=tuple(self.owner_invariants[name]),
        )

    def _add_owner_field(self, owner_name: str, path: tuple[str, ...]) -> None:
        if owner_name not in self.owners or not path or "*" in path:
            return
        self.owner_fields[owner_name].add(path)
        existing = self.owners[owner_name]
        self.owners[owner_name] = Owner(
            owner_name,
            borrowed=existing.borrowed,
            fields=tuple(sorted(self.owner_fields[owner_name])),
            invariants=existing.invariants,
        )

    def _add_owner_invariants(self, owner_name: str, clauses: Sequence[str]) -> None:
        if owner_name not in self.owners:
            self._register_owner(owner_name, borrowed=True)
        inv_list = self.owner_invariants[owner_name]
        for clause in clauses:
            if _NAME.fullmatch(clause) and clause not in inv_list:
                inv_list.append(clause)
        existing = self.owners[owner_name]
        self.owners[owner_name] = Owner(
            owner_name,
            borrowed=existing.borrowed,
            fields=existing.fields,
            invariants=tuple(inv_list),
        )

    def _collect_signature_facts(self) -> None:
        if self.enclosing_type is not None:
            self._register_owner("this", borrowed=True, type_name=self.enclosing_type)
        for param in _ast_nodes(self.fn_node.get("parameters", [])):
            pkind = param.get("kind")
            if pkind == "receiver_view_parameter":
                self._register_owner("this", borrowed=True, type_name=self.enclosing_type)
                vname = _id_text(param["view"])
                vpath = self.owner_views.get("this", {}).get(vname, (vname,))
                self._add_owner_field("this", vpath)
            elif pkind == "parameter":
                pname = _id_text(param["name"])
                pmode = param.get("mode", "value")
                ptype_node = param.get("parameter_type")
                ptype = _type_base_name(ptype_node)
                borrowed = pmode in {"in", "ref", "out"}
                if isinstance(ptype_node, dict) and ptype_node.get("kind") == "modified_type":
                    mods = ptype_node.get("modifiers", [])
                    if isinstance(mods, list) and any(m in {"in", "ref", "out"} for m in mods):
                        borrowed = True
                self._register_owner(pname, borrowed=borrowed, type_name=ptype)

        for contract in _ast_nodes(self.fn_node.get("contracts", [])):
            if contract.get("kind") == "effects":
                for eff in _ast_nodes(contract.get("effects", [])):
                    if eff.get("kind") == "call":
                        for arg in _ast_nodes(eff.get("arguments", [])):
                            val = _ast_node(arg["value"]) if arg.get("kind") == "call_argument" else arg
                            place = self._try_place(val)
                            if place is not None and place.owner in self.owners and place.fields:
                                self._add_owner_field(place.owner, place.fields)

        if not self.owners:
            self._register_owner("_unit", borrowed=False)

    def _try_place(self, expr: dict[str, object]) -> Place | None:
        kind = expr.get("kind")
        if kind == "identifier":
            name = _id_text(expr["name"])
            if name in self.handles and name in self.handle_places:
                return self.handle_places[name]
            if name == "this" and "this" not in self.owners:
                self._register_owner("this", borrowed=True, type_name=self.enclosing_type)
            if name in self.owners:
                return Place(name)
            return None
        if kind == "group":
            inner = expr.get("expression") or expr.get("value")
            if isinstance(inner, dict):
                return self._try_place(inner)
        if kind == "member":
            recv = expr.get("receiver")
            if isinstance(recv, dict):
                base = self._try_place(recv)
                if base is not None:
                    member_name = _id_text(expr["member"])
                    view_path = self.owner_views.get(base.owner, {}).get(member_name)
                    if view_path is not None and not base.fields:
                        return Place(base.owner, view_path)
                    return Place(base.owner, (*base.fields, member_name))
        if kind in {"index", "range_index"}:
            recv = expr.get("receiver")
            if isinstance(recv, dict):
                base = self._try_place(recv)
                if base is not None:
                    return Place(base.owner, (*base.fields, "*"))
        if kind == "borrow":
            inner = expr.get("value")
            if isinstance(inner, dict):
                return self._try_place(inner)
        return None

    def _resolve_borrow_target(
        self, current: str | None, expr: dict[str, object]
    ) -> tuple[str | None, str, Place]:
        # Evaluate any index subexpressions first.
        current = self._eval_index_subexpressions(current, expr)
        if expr.get("kind") == "identifier":
            name = _id_text(expr["name"])
            if name in self.handles:
                place = self.handle_places.get(name, Place(next(iter(self.owners))))
                return current, self.handles[name], place
            if name == "this" and "this" not in self.owners:
                self._register_owner("this", borrowed=True, type_name=self.enclosing_type)
            if name not in self.owners:
                self._register_owner(name, borrowed=False)
            return current, name, Place(name)

        root = expr
        fields: list[str] = []
        while root.get("kind") in {"member", "index", "range_index", "group"}:
            rkind = root.get("kind")
            if rkind == "group":
                root = cast("dict[str, object]", root.get("expression") or root.get("value"))
            elif rkind == "member":
                fields.append(_id_text(root["member"]))
                root = cast("dict[str, object]", root["receiver"])
            else:
                fields.append("*")
                root = cast("dict[str, object]", root["receiver"])
        fields.reverse()
        if root.get("kind") == "identifier":
            rname = _id_text(root["name"])
            if rname in self.handles:
                base_place = self.handle_places.get(rname, Place(next(iter(self.owners))))
                return current, self.handles[rname], Place(base_place.owner, (*base_place.fields, *fields))
            if rname == "this" and "this" not in self.owners:
                self._register_owner("this", borrowed=True, type_name=self.enclosing_type)
            if rname not in self.owners:
                self._register_owner(rname, borrowed=False)
            if len(fields) == 1 and fields[0] in self.owner_views.get(rname, {}):
                vpath = self.owner_views[rname][fields[0]]
                return current, rname, Place(rname, vpath)
            return current, rname, Place(rname, tuple(fields))

        fallback_owner = next(iter(self.owners))
        return current, fallback_owner, Place(fallback_owner)

    def _eval_index_subexpressions(
        self, current: str | None, expr: dict[str, object]
    ) -> str | None:
        kind = expr.get("kind")
        if kind == "member":
            recv = expr.get("receiver")
            if isinstance(recv, dict):
                return self._eval_index_subexpressions(current, recv)
        elif kind == "index":
            recv = expr.get("receiver")
            idx = expr.get("index")
            if isinstance(recv, dict):
                current = self._eval_index_subexpressions(current, recv)
            if isinstance(idx, dict):
                current, _ = self._lower_expr(current, idx)
        elif kind == "range_index":
            recv = expr.get("receiver")
            start = expr.get("start")
            end = expr.get("end")
            if isinstance(recv, dict):
                current = self._eval_index_subexpressions(current, recv)
            if isinstance(start, dict):
                current, _ = self._lower_expr(current, start)
            if isinstance(end, dict):
                current, _ = self._lower_expr(current, end)
        return current

    def _pattern_binders(self, pattern: dict[str, object]) -> list[str]:
        pkind = pattern.get("kind")
        if pkind == "binding_pattern":
            return [_id_text(pattern["name"])]
        if pkind == "labeled_pattern":
            inner = pattern.get("pattern")
            return self._pattern_binders(_ast_node(inner)) if inner is not None else []
        if pkind == "group_pattern":
            return self._pattern_binders(_ast_node(pattern["pattern"]))
        if pkind in {"tuple_pattern", "constructor_pattern"}:
            items = pattern.get("elements") if pkind == "tuple_pattern" else pattern.get("arguments", [])
            result: list[str] = []
            for item in _ast_nodes(items):
                result.extend(self._pattern_binders(item))
            return result
        return []

    def _bind_pattern_from_captures(
        self,
        current: str | None,
        pattern: dict[str, object],
        captures: tuple[str, ...],
        source_place: Place | None = None,
    ) -> str | None:
        binders = self._pattern_binders(pattern)
        for bname in binders:
            if not _NAME.fullmatch(bname) or bname == "_":
                continue
            if captures:
                if len(captures) == 1 and captures[0] in self.handle_places:
                    parent_handle = captures[0]
                    place = self.handle_places[parent_handle]
                    mode = self.handle_modes.get(parent_handle, "shared")
                    loan_name = bname if bname not in self.owners else self._fresh_loan(bname)
                    current = self._emit(
                        current,
                        Borrow(Loan(loan_name, parent_handle, place, mode=mode)),
                        f"pat_{bname}",
                    )
                    self.handles[bname] = loan_name
                    self.handle_places[bname] = place
                    self.handle_modes[bname] = mode
                else:
                    bind_name = bname if bname not in self.owners else self._fresh_loan(bname)
                    current = self._emit(current, Bind(bind_name, captures), f"pat_{bname}")
                    self.handles[bname] = bind_name
            elif source_place is not None and self.return_lifetime_place is not None:
                place = self.return_lifetime_place
                if place.owner in self.owners:
                    if place.fields:
                        self._add_owner_field(place.owner, place.fields)
                    loan_name = bname if bname not in self.owners else self._fresh_loan(bname)
                    current = self._emit(
                        current,
                        Borrow(Loan(loan_name, place.owner, place, mode="shared")),
                        f"pat_{bname}",
                    )
                    self.handles[bname] = loan_name
                    self.handle_places[bname] = place
                    self.handle_modes[bname] = "shared"
            else:
                self._register_owner(bname, borrowed=False)
        return current

    def _lower_expr(
        self, current: str | None, expr: dict[str, object]
    ) -> tuple[str | None, tuple[str, ...]]:
        if current is None:
            return None, ()
        kind = expr.get("kind")
        if kind in {"nat", "bool", "unit", "string", "bytes", "character", "hole", "operator", "type_expression"}:
            return current, ()

        if kind == "identifier":
            name = _id_text(expr["name"])
            if name in self.handles:
                handle = self.handles[name]
                current = self._emit(current, Use(handle), f"use_{name}")
                return current, (handle,)
            if name in self.owners:
                current = self._emit(current, Access(Place(name), "read"), f"read_{name}")
            return current, ()

        if kind == "member":
            current = self._eval_index_subexpressions(current, expr)
            place = self._try_place(expr)
            if place is not None:
                recv = expr.get("receiver")
                if isinstance(recv, dict) and recv.get("kind") == "identifier":
                    rname = _id_text(recv["name"])
                    if rname in self.handles:
                        via = self.handles[rname]
                        current = self._emit(current, Access(place, "read", via=via), "read_member")
                        return current, (via,)
                current = self._emit(current, Access(place, "read"), "read_member")
                return current, ()
            recv = expr.get("receiver")
            if isinstance(recv, dict):
                return self._lower_expr(current, recv)
            return current, ()

        if kind in {"index", "range_index"}:
            current = self._eval_index_subexpressions(current, expr)
            place = self._try_place(expr)
            if place is not None:
                recv = expr.get("receiver")
                if isinstance(recv, dict) and recv.get("kind") == "identifier":
                    rname = _id_text(recv["name"])
                    if rname in self.handles:
                        via = self.handles[rname]
                        current = self._emit(current, Access(place, "read", via=via), "read_index")
                        return current, (via,)
                current = self._emit(current, Access(place, "read"), "read_index")
                return current, ()
            return current, ()

        if kind == "borrow":
            mode = str(expr.get("mode", "in"))
            inner = _ast_node(expr["value"])
            if mode == "move":
                if inner.get("kind") == "identifier":
                    sname = _id_text(inner["name"])
                    if sname in self.handles:
                        old_handle = self.handles.pop(sname)
                        moved_handle = self._fresh_loan(f"moved_{sname}")
                        current = self._emit(current, Move(old_handle, moved_handle), f"move_{sname}")
                        return current, (moved_handle,)
                current, _, place = self._resolve_borrow_target(current, inner)
                current = self._emit(current, Access(place, "move"), "move_owner")
                return current, ()
            loan_mode: Mode = "shared" if mode == "in" else "exclusive"
            current, parent, place = self._resolve_borrow_target(current, inner)
            loan_name = self._fresh_loan("borrow")
            current = self._emit(
                current,
                Borrow(Loan(loan_name, parent, place, mode=loan_mode)),
                "borrow",
            )
            self.handle_places[loan_name] = place
            self.handle_modes[loan_name] = loan_mode
            return current, (loan_name,)

        if kind == "interpolated_string":
            for part in _ast_nodes(expr.get("parts", [])):
                if part.get("kind") == "interpolation":
                    hole_expr = _ast_node(part["expression"])
                    current, _ = self._lower_expr(current, hole_expr)
            return current, ()

        if kind in {"tuple", "array"}:
            captures: list[str] = []
            for elem in _ast_nodes(expr.get("elements", [])):
                current, caps = self._lower_expr(current, elem)
                for cap in caps:
                    if cap not in captures:
                        captures.append(cap)
            return current, tuple(captures)

        if kind == "unary":
            op = expr.get("operator")
            operand = _ast_node(expr["operand"])
            current, caps = self._lower_expr(current, operand)
            if op == "await":
                current = self._emit(current, Checkpoint("await"), "await")
            return current, caps

        if kind == "binary":
            left = _ast_node(expr["left"])
            right = _ast_node(expr["right"])
            current, lcaps = self._lower_expr(current, left)
            current, rcaps = self._lower_expr(current, right)
            return current, tuple(dict.fromkeys((*lcaps, *rcaps)))

        if kind == "group":
            inner = _ast_node(expr.get("expression") or expr.get("value"))
            return self._lower_expr(current, inner)

        if kind == "is":
            val = _ast_node(expr["value"])
            return self._lower_expr(current, val)

        if kind == "as":
            val = _ast_node(expr["value"])
            return self._lower_expr(current, val)

        if kind == "update":
            src = _ast_node(expr["source"])
            current, caps = self._lower_expr(current, src)
            for fitem in _ast_nodes(expr.get("fields", [])):
                fval = _ast_node(fitem["value"])
                current, _ = self._lower_expr(current, fval)
            return current, caps

        if kind == "let_expression":
            bname = _id_text(expr["name"])
            val = _ast_node(expr["value"])
            body = _ast_node(expr["body"])
            current = self._lower_binding(current, bname, val, local_type=expr.get("local_type"))
            return self._lower_expr(current, body)

        if kind == "if_expression":
            cond = _ast_node(expr["condition"])
            then_br = _ast_node(expr["then_branch"])
            else_br = _ast_node(expr["else_branch"])
            current, cond_caps = self._lower_expr(current, cond)
            split = self._emit(current, Nop(), "if_split")
            then_entry = self._fresh_node("if_then")
            else_entry = self._fresh_node("if_else")
            self._connect(split, then_entry)
            self._connect(split, else_entry)
            saved_handles = dict(self.handles)
            if cond.get("kind") == "is":
                pat = _ast_node(cond["pattern"])
                src_place = self._try_place(_ast_node(cond["value"]))
                then_entry = self._bind_pattern_from_captures(then_entry, pat, cond_caps, src_place)
            then_exit, then_caps = self._lower_expr(then_entry, then_br)
            self.handles = dict(saved_handles)
            else_exit, else_caps = self._lower_expr(else_entry, else_br)
            self.handles = saved_handles
            join = self._fresh_node("join_if")
            self._connect(then_exit, join)
            self._connect(else_exit, join)
            return join, tuple(dict.fromkeys((*then_caps, *else_caps)))

        if kind == "match_expression":
            scrutinee = _ast_node(expr["scrutinee"])
            current, scrut_caps = self._lower_expr(current, scrutinee)
            scrut_place = self._try_place(scrutinee)
            arms = _ast_nodes(expr.get("arms", []))
            if not arms:
                return current, ()
            split = self._emit(current, Nop(), "match_split")
            join = self._fresh_node("join_match")
            all_caps: list[str] = []
            saved_handles = dict(self.handles)
            for idx, arm in enumerate(arms):
                arm_entry = self._fresh_node(f"arm_{idx}")
                self._connect(split, arm_entry)
                self.handles = dict(saved_handles)
                pat = _ast_node(arm["pattern"])
                arm_curr: str | None = self._bind_pattern_from_captures(
                    arm_entry, pat, scrut_caps, scrut_place
                )
                guard = arm.get("guard")
                if isinstance(guard, dict):
                    arm_curr, _ = self._lower_expr(arm_curr, guard)
                body = _ast_node(arm["body"])
                arm_exit, arm_caps = self._lower_expr(arm_curr, body)
                self._connect(arm_exit, join)
                for cap in arm_caps:
                    if cap not in all_caps:
                        all_caps.append(cap)
            self.handles = saved_handles
            return join, tuple(all_caps)

        if kind == "call":
            return self._lower_call(current, expr)

        if kind == "propagate":
            inner = _ast_node(expr["value"])
            current, caps = self._lower_expr(current, inner)
            split = self._emit(current, Nop(), "try_split")
            err_node = self._fresh_node("try_err", Return("Err"))
            ok_node = self._fresh_node("try_ok")
            self._connect(split, ok_node)
            self._connect(split, err_node)
            return ok_node, caps

        return current, ()

    def _lower_call(
        self, current: str | None, expr: dict[str, object]
    ) -> tuple[str | None, tuple[str, ...]]:
        callee = _ast_node(expr["callee"])
        args = _ast_nodes(expr.get("arguments", []))
        arg_loans: list[tuple[str, Mode, Place, bool]] = []
        captured_handles: list[str] = []

        # Receiver member call: e.g. `workspace.TryFirst()`.
        if callee.get("kind") == "member":
            recv = _ast_node(callee["receiver"])
            rplace = self._try_place(recv)
            if (
                rplace is not None
                and rplace.owner in self.owners
                and self.return_lifetime_place is not None
                and self.return_lifetime_place.owner == rplace.owner
            ):
                target_place = self.return_lifetime_place
                if target_place.fields:
                    self._add_owner_field(target_place.owner, target_place.fields)
                loan_name = self._fresh_loan("recv")
                current = self._emit(
                    current,
                    Borrow(Loan(loan_name, target_place.owner, target_place, mode="shared")),
                    "call_recv",
                )
                self.handle_places[loan_name] = target_place
                self.handle_modes[loan_name] = "shared"
                captured_handles.append(loan_name)

        # Evaluate arguments left-to-right; create scoped borrows for `in`/`ref`/`out` args first
        # as each argument is reached, keeping them live until the call step completes.
        for arg in args:
            if arg.get("kind") == "call_argument":
                amode = str(arg.get("mode", "value"))
                aval = _ast_node(arg["value"])
            else:
                amode = "value"
                aval = arg
            if amode == "value" and aval.get("kind") == "borrow":
                amode = str(aval.get("mode", "in"))
                aval = _ast_node(aval["value"])

            if amode in {"in", "ref", "out"}:
                loan_mode: Mode = "shared" if amode == "in" else "exclusive"
                if aval.get("kind") == "identifier":
                    aname = _id_text(aval["name"])
                    if aname in self.handles and self.handle_modes.get(aname) == loan_mode:
                        hname = self.handles[aname]
                        hplace = self.handle_places.get(aname, Place(next(iter(self.owners))))
                        arg_loans.append((hname, loan_mode, hplace, False))
                        captured_handles.append(hname)
                        continue
                current, parent, place = self._resolve_borrow_target(current, aval)
                tmp_loan = self._fresh_loan("arg")
                current = self._emit(
                    current,
                    Borrow(Loan(tmp_loan, parent, place, mode=loan_mode, scoped=True)),
                    "arg_borrow",
                )
                self.handle_places[tmp_loan] = place
                self.handle_modes[tmp_loan] = loan_mode
                arg_loans.append((tmp_loan, loan_mode, place, True))
            elif amode == "move":
                if aval.get("kind") == "identifier":
                    sname = _id_text(aval["name"])
                    if sname in self.handles:
                        old_handle = self.handles.pop(sname)
                        moved_handle = self._fresh_loan(f"moved_{sname}")
                        current = self._emit(current, Move(old_handle, moved_handle), f"move_{sname}")
                        captured_handles.append(moved_handle)
                        continue
                current, _, place = self._resolve_borrow_target(current, aval)
                current = self._emit(current, Access(place, "move"), "arg_move")
            else:
                if aval.get("kind") == "identifier":
                    aname = _id_text(aval["name"])
                    if aname in self.handles:
                        captured_handles.append(self.handles[aname])
                        continue
                current, caps = self._lower_expr(current, aval)
                for cap in caps:
                    if cap not in captured_handles:
                        captured_handles.append(cap)

        # At the call execution point, demand all active `in`/`ref`/`out` argument loans.
        for loan_name, loan_mode, place, is_temp in arg_loans:
            if loan_mode == "shared":
                current = self._emit(current, Use(loan_name), "call_use")
            else:
                current = self._emit(current, Access(place, "write", via=loan_name), "call_write")
            if is_temp:
                current = self._emit(current, Drop(loan_name), "call_drop")

        return current, tuple(captured_handles)

    def _lower_binding(
        self,
        current: str | None,
        binder_name: str,
        value_expr: dict[str, object],
        *,
        local_type: object = None,
    ) -> str | None:
        if current is None:
            return None
        scoped = False
        explicit_loan_mode: Mode | None = None
        if isinstance(local_type, dict) and local_type.get("kind") == "modified_type":
            mods = local_type.get("modifiers", [])
            if isinstance(mods, list):
                if "scoped" in mods:
                    scoped = True
                if "ref" in mods or "out" in mods:
                    explicit_loan_mode = "exclusive"
                elif "in" in mods:
                    explicit_loan_mode = "shared"

        if value_expr.get("kind") == "borrow":
            mode = str(value_expr.get("mode", "in"))
            inner = _ast_node(value_expr["value"])
            if mode == "move":
                if inner.get("kind") == "identifier":
                    sname = _id_text(inner["name"])
                    if sname in self.handles:
                        old_handle = self.handles.pop(sname)
                        target_handle = binder_name if binder_name not in self.owners else self._fresh_loan(binder_name)
                        current = self._emit(current, Move(old_handle, target_handle), f"move_{binder_name}")
                        self.handles[binder_name] = target_handle
                        if sname in self.handle_places:
                            self.handle_places[binder_name] = self.handle_places[sname]
                            self.handle_places[target_handle] = self.handle_places[sname]
                        if sname in self.handle_modes:
                            self.handle_modes[binder_name] = self.handle_modes[sname]
                            self.handle_modes[target_handle] = self.handle_modes[sname]
                        return current
                current, _, place = self._resolve_borrow_target(current, inner)
                current = self._emit(current, Access(place, "move"), f"move_{binder_name}")
                self._register_owner(binder_name, borrowed=False, type_name=_type_base_name(local_type))
                return current

            loan_mode: Mode = "shared" if mode == "in" else "exclusive"
            current, parent, place = self._resolve_borrow_target(current, inner)
            loan_name = binder_name if binder_name not in self.owners else self._fresh_loan(binder_name)
            current = self._emit(
                current,
                Borrow(Loan(loan_name, parent, place, mode=loan_mode, scoped=scoped)),
                f"borrow_{binder_name}",
            )
            self.handles[binder_name] = loan_name
            self.handle_places[binder_name] = place
            self.handle_places[loan_name] = place
            self.handle_modes[binder_name] = loan_mode
            self.handle_modes[loan_name] = loan_mode
            return current

        current, caps = self._lower_expr(current, value_expr)
        if caps:
            if len(caps) == 1 and explicit_loan_mode is not None and caps[0] in self.handle_places:
                parent_handle = caps[0]
                place = self.handle_places[parent_handle]
                loan_name = binder_name if binder_name not in self.owners else self._fresh_loan(binder_name)
                current = self._emit(
                    current,
                    Borrow(Loan(loan_name, parent_handle, place, mode=explicit_loan_mode, scoped=scoped)),
                    f"reborrow_{binder_name}",
                )
                self.handles[binder_name] = loan_name
                self.handle_places[binder_name] = place
                self.handle_places[loan_name] = place
                self.handle_modes[binder_name] = explicit_loan_mode
                self.handle_modes[loan_name] = explicit_loan_mode
            else:
                bind_name = binder_name if binder_name not in self.owners else self._fresh_loan(binder_name)
                current = self._emit(current, Bind(bind_name, caps), f"bind_{binder_name}")
                self.handles[binder_name] = bind_name
            return current

        self._register_owner(binder_name, borrowed=False, type_name=_type_base_name(local_type))
        return current

    def _lower_statements(
        self,
        current: str | None,
        statements: list[dict[str, object]],
        *,
        loop_header: str | None = None,
        loop_exit: str | None = None,
    ) -> str | None:
        for stmt in statements:
            if current is None:
                break
            current = self._lower_statement(
                current, stmt, loop_header=loop_header, loop_exit=loop_exit
            )
        return current

    def _lower_statement(
        self,
        current: str | None,
        stmt: dict[str, object],
        *,
        loop_header: str | None = None,
        loop_exit: str | None = None,
    ) -> str | None:
        if current is None:
            return None
        kind = stmt.get("kind")

        if kind in {"let", "var", "typed_local"}:
            bname = _id_text(stmt["name"])
            val = _ast_node(stmt["value"])
            return self._lower_binding(current, bname, val, local_type=stmt.get("local_type"))

        if kind in {"let_pattern", "var_pattern"}:
            pat = _ast_node(stmt["pattern"])
            val = _ast_node(stmt["value"])
            current, caps = self._lower_expr(current, val)
            return self._bind_pattern_from_captures(current, pat, caps, self._try_place(val))

        if kind in {"let_else", "var_else"}:
            pat = _ast_node(stmt["pattern"])
            val = _ast_node(stmt["value"])
            else_body = _ast_nodes(stmt.get("else_body", []))
            current, caps = self._lower_expr(current, val)
            split = self._emit(current, Nop(), "let_else_split")
            ok_entry = self._fresh_node("let_else_ok")
            else_entry = self._fresh_node("let_else_err")
            self._connect(split, ok_entry)
            self._connect(split, else_entry)
            saved_handles = dict(self.handles)
            else_exit = self._lower_statements(
                else_entry, else_body, loop_header=loop_header, loop_exit=loop_exit
            )
            if else_exit is not None and not isinstance(self.events.get(else_exit), Return):
                self._emit(else_exit, Return("else"), "let_else_ret")
            self.handles = saved_handles
            return self._bind_pattern_from_captures(ok_entry, pat, caps, self._try_place(val))

        if kind == "assign":
            target = _ast_node(stmt["target"])
            val = _ast_node(stmt["value"])
            op = str(stmt.get("operator", "="))
            current, _ = self._lower_expr(current, val)
            current = self._eval_index_subexpressions(current, target)
            if op != "=":
                current, _ = self._lower_expr(current, target)
            if target.get("kind") == "identifier":
                tname = _id_text(target["name"])
                if tname in self.handles and tname in self.handle_places:
                    via = self.handles[tname]
                    return self._emit(
                        current,
                        Access(self.handle_places[tname], "write", via=via),
                        f"write_{tname}",
                    )
            place = self._try_place(target)
            if place is not None:
                if place.fields:
                    self._add_owner_field(place.owner, place.fields)
                recv = target.get("receiver")
                if isinstance(recv, dict) and recv.get("kind") == "identifier":
                    rname = _id_text(recv["name"])
                    if rname in self.handles:
                        return self._emit(
                            current,
                            Access(place, "write", via=self.handles[rname]),
                            "write_field",
                        )
                return self._emit(current, Access(place, "write"), "write_field")
            return current

        if kind == "if":
            cond = _ast_node(stmt["condition"])
            then_body = _ast_nodes(stmt.get("then_body", []))
            else_body = _ast_nodes(stmt.get("else_body", []))
            current, cond_caps = self._lower_expr(current, cond)
            split = self._emit(current, Nop(), "if_split")
            then_entry = self._fresh_node("if_then")
            else_entry = self._fresh_node("if_else")
            self._connect(split, then_entry)
            self._connect(split, else_entry)
            saved_handles = dict(self.handles)
            if cond.get("kind") == "is":
                pat = _ast_node(cond["pattern"])
                src_place = self._try_place(_ast_node(cond["value"]))
                then_entry = self._bind_pattern_from_captures(then_entry, pat, cond_caps, src_place)
            then_exit = self._lower_statements(
                then_entry, then_body, loop_header=loop_header, loop_exit=loop_exit
            )
            self.handles = dict(saved_handles)
            else_exit = self._lower_statements(
                else_entry, else_body, loop_header=loop_header, loop_exit=loop_exit
            )
            self.handles = saved_handles
            if then_exit is None and else_exit is None:
                return None
            join = self._fresh_node("join_if")
            if then_exit is not None:
                self._connect(then_exit, join)
            if else_exit is not None:
                self._connect(else_exit, join)
            return join

        if kind == "match":
            scrutinee = _ast_node(stmt["scrutinee"])
            current, scrut_caps = self._lower_expr(current, scrutinee)
            scrut_place = self._try_place(scrutinee)
            arms = _ast_nodes(stmt.get("arms", []))
            if not arms:
                return current
            split = self._emit(current, Nop(), "match_split")
            join = self._fresh_node("join_match")
            any_fallthrough = False
            saved_handles = dict(self.handles)
            for idx, arm in enumerate(arms):
                arm_entry = self._fresh_node(f"arm_{idx}")
                self._connect(split, arm_entry)
                self.handles = dict(saved_handles)
                pat = _ast_node(arm["pattern"])
                arm_curr = self._bind_pattern_from_captures(
                    arm_entry, pat, scrut_caps, scrut_place
                )
                guard = arm.get("guard")
                if isinstance(guard, dict):
                    arm_curr, _ = self._lower_expr(arm_curr, guard)
                arm_body = _ast_nodes(arm.get("body", []))
                arm_exit = self._lower_statements(
                    arm_curr, arm_body, loop_header=loop_header, loop_exit=loop_exit
                )
                if arm_exit is not None:
                    any_fallthrough = True
                    self._connect(arm_exit, join)
            self.handles = saved_handles
            return join if any_fallthrough else None

        if kind == "scope":
            target_expr = _ast_node(stmt["target"])
            lifts = tuple(_id_text(item) for item in _ast_nodes(stmt.get("lifts", [])))
            targets: list[str] = []
            items = (
                _ast_nodes(target_expr.get("elements", []))
                if target_expr.get("kind") == "tuple"
                else [target_expr]
            )
            for item in items:
                place = self._try_place(item)
                if place is not None:
                    targets.append(place.owner)
            if not targets and "this" in self.owners:
                targets.append("this")
            for owner_name in targets:
                if lifts:
                    self._add_owner_invariants(owner_name, lifts)
                current = self._emit(current, OpenInvariant(owner_name, lifts), f"open_{owner_name}")
            body = _ast_nodes(stmt.get("body", []))
            current = self._lower_statements(
                current, body, loop_header=loop_header, loop_exit=loop_exit
            )
            if current is not None:
                for owner_name in reversed(targets):
                    current = self._emit(
                        current, CloseInvariant(owner_name, lifts), f"close_{owner_name}"
                    )
            return current

        if kind in {"foreach", "foreach_collection", "while"}:
            if kind == "foreach":
                current, _ = self._lower_expr(current, _ast_node(stmt["start"]))
                current, _ = self._lower_expr(current, _ast_node(stmt["end"]))
            elif kind == "foreach_collection":
                current, _ = self._lower_expr(current, _ast_node(stmt["collection"]))
            header = self._fresh_node("header_loop")
            self._connect(current, header)
            body_entry = self._fresh_node("loop_body")
            exit_node = self._fresh_node("loop_exit")
            self._connect(header, body_entry)
            self._connect(header, exit_node)
            saved_handles = dict(self.handles)
            body_curr: str | None = body_entry
            iter_loan: str | None = None
            if kind == "while":
                body_curr, _ = self._lower_expr(body_curr, _ast_node(stmt["condition"]))
            elif kind == "foreach":
                iname = _id_text(stmt["name"])
                self._register_owner(iname, borrowed=False)
            elif kind == "foreach_collection":
                iname = _id_text(stmt["name"])
                imode = str(stmt.get("mode", "value"))
                coll = _ast_node(stmt["collection"])
                if imode in {"in", "ref"}:
                    body_curr, parent, cplace = self._resolve_borrow_target(body_curr, coll)
                    elem_place = Place(cplace.owner, (*cplace.fields, "*"))
                    loan_mode = "shared" if imode == "in" else "exclusive"
                    iter_loan = iname if iname not in self.owners else self._fresh_loan(iname)
                    body_curr = self._emit(
                        body_curr,
                        Borrow(Loan(iter_loan, parent, elem_place, mode=loan_mode, scoped=True)),
                        f"iter_{iname}",
                    )
                    self.handles[iname] = iter_loan
                    self.handle_places[iname] = elem_place
                    self.handle_places[iter_loan] = elem_place
                    self.handle_modes[iname] = loan_mode
                    self.handle_modes[iter_loan] = loan_mode
                else:
                    self._register_owner(iname, borrowed=False)
            body_exit = self._lower_statements(
                body_curr,
                _ast_nodes(stmt.get("body", [])),
                loop_header=header,
                loop_exit=exit_node,
            )
            if body_exit is not None:
                if iter_loan is not None:
                    body_exit = self._emit(body_exit, Drop(iter_loan), f"drop_{iter_loan}")
                self._connect(body_exit, header)
            self.handles = saved_handles
            return exit_node

        if kind == "break":
            if loop_exit is not None:
                self._connect(current, loop_exit)
            return None

        if kind == "continue":
            if loop_header is not None:
                self._connect(current, loop_header)
            return None

        if kind == "return":
            val = stmt.get("value")
            if isinstance(val, dict):
                outcome = "return"
                if val.get("kind") == "call":
                    callee = _ast_node(val["callee"])
                    if callee.get("kind") == "identifier":
                        cname = _id_text(callee["name"])
                        if cname and cname[0].isupper():
                            outcome = cname
                current, caps = self._lower_expr(current, val)
                self._emit(current, Return(outcome, caps), "ret")
            else:
                self._emit(current, Return("return"), "ret")
            return None

        if kind == "expression":
            expr = _ast_node(stmt["expression"])
            current, _ = self._lower_expr(current, expr)
            return current

        if kind == "assert":
            expr = _ast_node(stmt["expression"])
            current, _ = self._lower_expr(current, expr)
            return current

        return current

    def build(self) -> LoweredFunction:
        self._collect_signature_facts()
        entry = self._fresh_node("entry")
        body = self.fn_node.get("body")
        if isinstance(body, list):
            end = self._lower_statements(entry, _ast_nodes(body))
            if end is not None and not isinstance(self.events.get(end), Return):
                self._emit(end, Return("return"), "ret")
        elif isinstance(body, dict):
            end, caps = self._lower_expr(entry, body)
            if end is not None and not isinstance(self.events.get(end), Return):
                self._emit(end, Return("return", caps), "ret")
        else:
            self._emit(entry, Return("return"), "ret")

        # Keep only reachable nodes from entry so dead post-return placeholders are excluded.
        reached: set[str] = set()
        stack = [entry]
        while stack:
            curr = stack.pop()
            if curr in reached:
                continue
            reached.add(curr)
            stack.extend(
                succ for succ in reversed(self.edges.get(curr, [])) if succ not in reached
            )

        built_nodes = tuple(
            Node(
                name,
                self.events[name],
                tuple(succ for succ in self.edges[name] if succ in reached),
            )
            for name in self.events
            if name in reached
        )
        return LoweredFunction(
            self.fn_name,
            tuple(self.owners.values()),
            Graph(entry, built_nodes),
        )


def _unwrap_ast_root(ast: object) -> dict[str, object]:
    node = _ast_node(ast, "AST root")
    if "ast" in node and isinstance(node["ast"], dict):
        return _ast_node(node["ast"], "inner AST root")
    return node


def lower_function(ast: object, function_name: str | None = None) -> LoweredFunction:
    """Lower a parsed schema-2 function, method or definition into a loan Graph."""
    root = _unwrap_ast_root(ast)
    kind = root.get("kind")
    if kind in {"function", "method", "definition"}:
        fname = _id_text(root["name"])
        if function_name is not None and function_name != fname:
            raise AnalysisRefusalError(f"function {function_name!r} not found")
        return _FunctionLowerer(fname, root, None, {}).build()

    if kind not in {"surface_file", "module", "file"}:
        raise AnalysisRefusalError("expected a parsed module or function AST node")

    declarations = _ast_nodes(root.get("declarations", []))
    structs = _collect_structs(declarations)
    functions = _find_functions(declarations)
    if not functions:
        raise AnalysisRefusalError("no function with a body found in module")
    if function_name is None:
        selected_name, selected_node, enclosing = functions[0]
        return _FunctionLowerer(selected_name, selected_node, enclosing, structs).build()
    for candidate_name, candidate_node, enclosing in functions:
        if candidate_name == function_name:
            return _FunctionLowerer(candidate_name, candidate_node, enclosing, structs).build()
    raise AnalysisRefusalError(f"function {function_name!r} not found in module")


def lower_module(ast: object) -> tuple[LoweredFunction, ...]:
    """Lower all functions, methods and definitions with bodies in a schema-2 module."""
    root = _unwrap_ast_root(ast)
    if root.get("kind") not in {"surface_file", "module", "file"}:
        return (lower_function(root),)
    declarations = _ast_nodes(root.get("declarations", []))
    structs = _collect_structs(declarations)
    seen_nodes: set[int] = set()
    lowered: list[LoweredFunction] = []
    for candidate_name, candidate_node, enclosing in _find_functions(declarations):
        if id(candidate_node) in seen_nodes:
            continue
        seen_nodes.add(id(candidate_node))
        lowered.append(_FunctionLowerer(candidate_name, candidate_node, enclosing, structs).build())
    if not lowered:
        raise AnalysisRefusalError("no function with a body found in module")
    return tuple(lowered)


def analyze_function(
    ast: object, function_name: str | None = None, limits: Limits | None = None
) -> Report:
    """Lower and analyze one schema-2 function, method or definition."""
    lowered = lower_function(ast, function_name)
    return analyze(lowered.owners, lowered.graph, limits)


def analyze_module(
    ast: object, limits: Limits | None = None
) -> dict[str, Report]:
    """Lower and analyze every function with a body in a schema-2 module."""
    return {
        lowered.name: analyze(lowered.owners, lowered.graph, limits)
        for lowered in lower_module(ast)
    }
