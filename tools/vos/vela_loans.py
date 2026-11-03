# SPDX-License-Identifier: Apache-2.0
"""Bounded diagnostic over supplied loan facts, never a source safety verdict.

The contract is docs/languages/vela/loan-analysis.md. Complete DAG paths retain
their own capture environments and loan states. All supplied interpretation,
separation, capture and restoration facts remain explicit unresolved obligations.
No operation interprets a Vela type, calls a library, runs cleanup or checks a proof.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

type Mode = Literal["shared", "exclusive"]
type AccessKind = Literal["read", "write", "move"]
type Overlap = Literal["yes", "no", "unknown"]

_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")


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


@dataclass(frozen=True)
class CloseInvariant:
    name: str


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


@dataclass(frozen=True)
class Report:
    paths: tuple[PathReport, ...]
    status: Literal["diagnostic-only"] = field(default="diagnostic-only", init=False)


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


def _validate(owners: tuple[Owner, ...], graph: Graph, limits: Limits,
              budget: _Budget) -> dict[str, Node]:
    for bound in (limits.owners, limits.nodes, limits.paths, limits.captures, limits.work):
        if type(bound) is not int or bound < 1:
            raise AnalysisRefusalError("analysis limits must be positive integers")
    if not isinstance(graph, Graph):
        raise AnalysisRefusalError("graph must be an immutable Graph record")
    if not isinstance(owners, tuple) or not isinstance(graph.nodes, tuple):
        raise AnalysisRefusalError("owners and nodes must be immutable tuples")
    if not owners or len(owners) > limits.owners or not graph.nodes or len(graph.nodes) > limits.nodes:
        raise AnalysisRefusalError("owner or node budget exhausted, or empty input")
    owner_names: set[str] = set()
    capture_count = 0
    for owner in owners:
        budget.spend()
        if not isinstance(owner, Owner):
            raise AnalysisRefusalError("owner must be an immutable Owner record")
        _name(owner.name)
        if owner.name in owner_names or type(owner.borrowed) is not bool:
            raise AnalysisRefusalError("duplicate owner identity or malformed owner mode")
        owner_names.add(owner.name)
        if not isinstance(owner.fields, tuple) or len(owner.fields) > limits.captures:
            raise AnalysisRefusalError("field declarations must be immutable")
        for path in owner.fields:
            _projection(path)
            budget.spend(len(path) + 1)
            if not path or "*" in path:
                raise AnalysisRefusalError("declared field projections cannot be empty or unknown")
        if len(set(owner.fields)) != len(owner.fields):
            raise AnalysisRefusalError("duplicate field declaration")

    nodes: dict[str, Node] = {}
    known = set(owner_names)
    invariants: set[str] = set()
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
        if isinstance(node.event, OpenInvariant):
            _name(node.event.name)
            invariants.add(node.event.name)

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
            if place.owner not in owner_names:
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
            _name(event.name)
            if event.name not in invariants:
                raise AnalysisRefusalError("missing invariant reference")
        if isinstance(event, (Return, Checkpoint)):
            label = event.outcome if isinstance(event, Return) else event.kind
            _name(label)

    # Kahn's order checks the entire supplied graph, including unreachable cycles.
    incoming = dict.fromkeys(nodes, 0)
    for node in graph.nodes:
        for successor in node.successors:
            budget.spend()
            incoming[successor] += 1
    ready = [name for name, count in incoming.items() if count == 0]
    visited = 0
    while ready:
        budget.spend()
        name = ready.pop()
        visited += 1
        for successor in nodes[name].successors:
            budget.spend()
            incoming[successor] -= 1
            if incoming[successor] == 0:
                ready.append(successor)
    if visited != len(nodes):
        raise AnalysisRefusalError("cyclic control flow requires an invariant interpretation")
    return nodes


def _paths(graph: Graph, nodes: dict[str, Node], limit: int,
           budget: _Budget) -> tuple[tuple[Node, ...], ...]:
    pending: list[tuple[str, tuple[Node, ...]]] = [(graph.entry, ())]
    result: list[tuple[Node, ...]] = []
    reached: set[str] = set()
    while pending:
        budget.spend()
        name, prefix = pending.pop()
        node = nodes[name]
        reached.add(name)
        path = (*prefix, node)
        if not node.successors:
            result.append(path)
            if len(result) > limit:
                raise AnalysisRefusalError("complete path budget exhausted")
        else:
            for successor in reversed(node.successors):
                budget.spend()
                pending.append((successor, path))
    if reached != set(nodes):
        raise AnalysisRefusalError("unreachable graph nodes")
    return tuple(result)


def _capture_cycles(path: tuple[Node, ...], budget: _Budget) -> None:
    """Refuse cyclic supplied retention facts, without conflating shadowed names."""
    counts: dict[str, int] = {}
    for node in path:
        budget.spend()
        name = _binder(node.event)
        if name is not None:
            counts[name] = counts.get(name, 0) + 1
    dependencies: dict[str, set[str]] = {}
    for node in path:
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


@dataclass(frozen=True)
class _Step:
    uses: frozenset[str]
    creates: str | None = None
    route: str | None = None


class _Path:
    def __init__(self, owners: dict[str, Owner], fields: dict[str, frozenset[tuple[str, ...]]],
                 path: tuple[Node, ...], budget: _Budget) -> None:
        self.owners = owners
        self.fields = fields
        self.path = path
        self.budget = budget
        self.issues: list[Issue] = []
        self.obligations = [Obligation(path[0].name, "supplied-interpretation", tuple(owners)),
                            Obligation(path[0].name, "supplied-separation", tuple(owners))]
        self.restorations: list[Restoration] = []
        self.loans: dict[str, Loan] = {}
        self.parents: dict[str, str] = {}
        self.returned: frozenset[str] = frozenset()
        self.moved: set[str] = set()
        self.invalid: set[str] = set()

    def issue(self, node: Node, kind: str, *resources: str) -> None:
        self.issues.append(Issue(node.name, kind, resources))

    def obligation(self, node: Node, kind: str, *resources: str) -> None:
        self.obligations.append(Obligation(node.name, kind, resources))

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

    def prepare(self) -> tuple[_Step, ...]:
        """Resolve names per path, then flatten retained captures before liveness."""
        values: dict[str, _Value] = {}
        seen = set(self.owners)
        steps: list[_Step] = []
        for node in self.path:
            self.budget.spend()
            event = node.event
            used: set[str] = set()
            for name in _references(event):
                self.budget.spend()
                if name in self.owners:
                    continue
                if name not in values:
                    self.issue(node, "unavailable-name", name)
                elif not isinstance(event, Drop):
                    self.budget.spend(len(values[name].captures))
                    used.update(values[name].captures)
            binder = _binder(event)
            fresh = binder is None or binder not in seen
            if not fresh:
                self.issue(node, "ambiguous-name", binder or "")
            if binder is not None:
                seen.add(binder)
            creates: str | None = None
            route: str | None = None
            match event:
                case Borrow(loan):
                    if fresh:
                        parent = values.get(loan.parent)
                        if loan.parent in self.owners:
                            route = loan.parent
                        elif parent is not None and parent.handle is not None:
                            route = parent.handle
                        else:
                            self.issue(node, "borrow-parent-has-no-grant", loan.parent)
                        if route is not None:
                            self.loans[loan.name] = loan
                            self.parents[loan.name] = route
                            values[loan.name] = _Value(frozenset({loan.name}), loan.name)
                            creates = loan.name
                case Access(via=via) if via is not None:
                    value = values.get(via)
                    if value is not None:
                        route = value.handle
                    if route is None:
                        self.issue(node, "access-route-has-no-grant", via)
                case Bind(name, captures):
                    if fresh:
                        if set(captures) & self.owners.keys():
                            self.issue(node, "owner-capture-unsupported", name)
                        values[name] = _Value(frozenset(used))
                        self.obligation(node, "capture-interpretation", name, *sorted(used))
                case Move(source, target):
                    if source in self.owners:
                        self.issue(node, "owner-handle-move-unsupported", source)
                    elif fresh and source in values:
                        values[target] = values.pop(source)
                case Drop(name):
                    if name in self.owners:
                        self.issue(node, "owner-drop-unsupported", name)
                    else:
                        values.pop(name, None)
                case Return(captures=names):
                    if set(names) & self.owners.keys():
                        self.issue(node, "owner-return-unsupported", *sorted(set(names) & self.owners.keys()))
                    self.returned = frozenset(used)
                case _:
                    pass
            steps.append(_Step(frozenset(used), creates, route))
        return tuple(steps)

    def liveness(self, steps: tuple[_Step, ...]) -> tuple[frozenset[str], ...]:
        after: list[frozenset[str]] = [frozenset()] * len(steps)
        live = self.ancestors(self.returned)
        for index in range(len(steps) - 1, -1, -1):
            self.budget.spend()
            after[index] = live
            step = steps[index]
            before = set(live)
            if step.creates is not None:
                before.discard(step.creates)
            before.update(step.uses)
            live = self.ancestors(before)
        return tuple(after)

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

    def borrow(self, node: Node, name: str, active: set[str], opened: set[str]) -> None:
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
            if parent not in active:
                self.issue(node, "borrow-parent-has-no-grant", name, parent)
            if parent_loan.mode == "shared" and loan.mode == "exclusive":
                self.issue(node, "exclusive-from-shared", name, parent)
        if self.containment(node, loan.place, parent_place, parent) == "no":
            self.issue(node, "reborrow-outside-parent", name, parent)
        if loan.invariant is not None and loan.invariant not in opened:
            self.issue(node, "loan-invariant-not-open", name, loan.invariant)
        ancestors = self.ancestors({name}) - {name}
        for other in sorted(active - ancestors):
            if loan.mode == "exclusive" or self.loans[other].mode == "exclusive":
                overlap = self.compare(node, loan.place, other)
                if overlap == "yes":
                    self.issue(node, "competing-loans", name, other)
        if len(self.issues) == prior_issues:
            active.add(name)
        else:
            self.invalid.add(name)

    def access(self, node: Node, event: Access, route: str | None, active: set[str]) -> None:
        self.obligation(node, "access-interpretation", event.place.owner, event.kind)
        self.obligation(node, "effect-interpretation", event.place.owner, event.kind)
        if "*" in event.place.fields:
            self.obligation(node, "unknown-footprint", event.place.owner, *event.place.fields)
        if event.kind != "read":
            self.obligation(node, "content-refinement-invalidation", event.place.owner)
        if event.place.owner in self.moved:
            self.issue(node, "use-after-owner-move", event.place.owner)
        if event.via is not None:
            if route is None:
                return
            if route not in active:
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
        for other in sorted(active - ancestors):
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

    def end(self, node: Node, active: set[str], live: frozenset[str]) -> None:
        # Every child is deeper than its ancestor. Lexical names only break ties.
        ending = sorted(active - live, key=lambda name: (-len(self.ancestors({name})), name))
        for name in ending:
            self.budget.spend()
            loan = self.loans[name]
            self.restorations.append(Restoration(node.name, name, self.parents[name], loan.place))
            self.obligation(node, "restoration", name, self.parents[name])
            active.remove(name)

    def run(self) -> PathReport:
        _capture_cycles(self.path, self.budget)
        steps = self.prepare()
        live_after = self.liveness(steps)
        active: set[str] = set()
        opened: set[str] = set()
        outcome = "fallthrough"
        for node, step, live in zip(self.path, steps, live_after, strict=True):
            self.budget.spend()
            event = node.event
            match event:
                case Borrow() if step.creates is not None:
                    self.borrow(node, step.creates, active, opened)
                case Access():
                    self.access(node, event, step.route, active)
                case Use(name):
                    if name in self.owners:
                        self.access(node, Access(Place(name)), None, active)
                    else:
                        for captured in sorted(step.uses):
                            self.access(node, Access(self.loans[captured].place, via=name),
                                        captured, active)
                case OpenInvariant(name):
                    if name in opened:
                        self.issue(node, "invariant-already-open", name)
                    opened.add(name)
                    self.obligation(node, "invariant-open", name)
                case CloseInvariant(name):
                    if name not in opened:
                        self.issue(node, "invariant-not-open", name)
                    for loan in sorted(active):
                        if self.loans[loan].invariant == name and loan in live:
                            self.issue(node, "invariant-closed-with-live-loan", name, loan)
                    opened.discard(name)
                    self.obligation(node, "invariant-close", name)
                case Checkpoint(kind):
                    self.issue(node, "unsupported-boundary", kind)
                    self.obligation(node, "boundary-interpretation", kind, *sorted(active))
                    for invariant in sorted(opened):
                        self.issue(node, "open-invariant-at-boundary", invariant)
                    for loan in sorted(active & live):
                        if self.loans[loan].scoped:
                            self.issue(node, "scoped-loan-at-boundary", loan)
                case Return(tag, _):
                    outcome = tag
                case _:
                    pass
            self.end(node, active, live)
        terminal = self.path[-1]
        for invariant in sorted(opened):
            self.issue(terminal, "unclosed-invariant", invariant)
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
        suspended = tuple(sorted({self.loans[name].place for name in active},
                                 key=lambda place: (place.owner, place.fields)))
        return PathReport(tuple(node.name for node in self.path), outcome, tuple(self.issues),
                          tuple(self.obligations), tuple(self.restorations), tuple(sorted(self.returned)),
                          tuple(sorted(active)), suspended, tuple(sorted(self.moved)))


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
    nodes = _validate(owners, graph, limits, budget)
    paths = _paths(graph, nodes, limits.paths, budget)
    owner_map = {owner.name: owner for owner in owners}
    budget.spend(sum(len(owner.fields) for owner in owners))
    fields = {owner.name: frozenset(owner.fields) for owner in owners}
    return Report(tuple(_Path(owner_map, fields, path, budget).run() for path in paths))
