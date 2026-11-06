# SPDX-License-Identifier: Apache-2.0
"""Independent complete-path loan-flow fixtures and rejected neighbors."""

from collections.abc import Callable
from itertools import product
from typing import cast

from tests.harness import Case, ensure
from vos.vela.loans import (
    Access,
    AnalysisRefusalError,
    Bind,
    Borrow,
    Checkpoint,
    CloseInvariant,
    Drop,
    Event,
    Graph,
    Limits,
    Loan,
    Move,
    Node,
    Nop,
    OpenInvariant,
    Owner,
    PathReport,
    Place,
    Return,
    Use,
    analyze,
    analyze_function,
    analyze_module,
    lower_module,
)

INDEPENDENT_CASES = True

_ROOT = Place("workspace")
_BYTES = Place("workspace", ("bytes",))
_AUDIT = Place("workspace", ("audit",))
_OWNERS = (Owner("workspace", borrowed=True, fields=(("bytes",), ("audit",))),)


def _graph(*events: Event) -> Graph:
    return Graph("n0", tuple(Node(f"n{index}", event,
                                 (f"n{index + 1}",) if index + 1 < len(events) else ())
                             for index, event in enumerate(events)))


def _path(*events: Event) -> PathReport:
    report = analyze(_OWNERS, _graph(*events))
    ensure(report.status == "diagnostic-only", "analysis exposed a safety verdict")
    ensure(len(report.paths) == 1, "linear fixture acquired extra paths")
    return report.paths[0]


def _kinds(path: PathReport) -> set[str]:
    return {issue.kind for issue in path.issues}


def _ends(path: PathReport) -> list[tuple[str, str, str]]:
    return [(end.node, end.loan, end.parent) for end in path.restorations]


def _refuses(action: Callable[[], object], text: str) -> None:
    try:
        action()
    except AnalysisRefusalError as error:
        ensure(text in str(error), f"wrong structural refusal: {error}")
    else:
        raise AssertionError(f"analysis did not refuse {text}")


def _last_use_and_residuals() -> None:
    path = _path(Borrow(Loan("reader", "workspace", _BYTES)), Use("reader"),
                 Access(_BYTES, "write"), Return("done"))
    ensure(not path.issues, f"last-use fixture conflicts: {path.issues}")
    ensure(_ends(path) == [("n1", "reader", "workspace")], "loan did not end exactly after its use")
    ensure(not path.retained_loans and not path.suspended, "ended loan still suspends its parent")
    ensure(all(end.status == "unresolved" for end in path.restorations), "restoration was called proved")
    obligations = {(item.node, item.kind, item.resources) for item in path.obligations}
    for expected in (("n0", "supplied-interpretation", ("workspace",)),
                     ("n0", "supplied-separation", ("workspace",)),
                     ("n1", "restoration", ("reader", "workspace")),
                     ("n2", "content-refinement-invalidation", ("workspace",))):
        ensure(expected in obligations, f"lost unresolved model obligation {expected}")
    ensure(all(item.status == "unresolved" for item in path.obligations), "residual status changed")
    unused = _path(Borrow(Loan("unused", "workspace", _BYTES)))
    ensure(_ends(unused) == [("n0", "unused", "workspace")], "terminal unused loan escaped accounting")


def _nested_restoration_and_suspension() -> None:
    prefix = (Borrow(Loan("writer", "workspace", _BYTES, "exclusive")),
              Borrow(Loan("reader", "writer", _BYTES)))
    path = _path(*prefix, Use("reader"), Access(_BYTES, "write"))
    ensure(not path.issues, "nested loan did not restore its parent before owner write")
    ensure(_ends(path) == [("n2", "reader", "writer"), ("n2", "writer", "workspace")],
           "nested restoration lost descendant-first order at last use")
    for interaction in (Use("writer"), Access(_BYTES, "read", "writer"), Access(_ROOT, "read")):
        neighbor = _path(*prefix, interaction, Use("reader"))
        ensure("suspended-parent" in _kinds(neighbor), "live child did not suspend ancestor access")
        ensure(_ends(neighbor)[-2:] == [("n3", "reader", "writer"), ("n3", "writer", "workspace")],
               "rejected parent use prematurely restored a descendant")


def _field_partitions_and_unknowns() -> None:
    path = _path(Borrow(Loan("reader", "workspace", _BYTES)), Access(_AUDIT, "write"), Use("reader"))
    ensure(not path.issues and not any(item.kind == "overlap" for item in path.obligations),
           "declared disjoint audit field was not framed")
    overlap = _path(Borrow(Loan("reader", "workspace", _BYTES)), Access(_ROOT, "write"), Use("reader"))
    ensure("suspended-parent" in _kinds(overlap), "containing footprint did not conflict")
    unknown = Place("workspace", ("other",))
    residual = _path(Borrow(Loan("reader", "workspace", _BYTES)), Access(unknown, "write"), Use("reader"))
    ensure(any(item.kind == "overlap" and item.node == "n1" for item in residual.obligations),
           "undeclared fields were assumed disjoint by spelling")
    indexed = Place("workspace", ("bytes", "*"))
    residual = _path(Borrow(Loan("reader", "workspace", indexed)),
                     Access(indexed, "write"), Use("reader"))
    ensure(any(item.kind == "overlap" for item in residual.obligations),
           "unknown array index was treated as an exact location")
    # A split below an unknown common projection cannot justify array disjointness.
    owner = (Owner("array", fields=(("*", "left"),)),)
    _refuses(lambda: analyze(owner, Graph("entry", (Node("entry"),))), "unknown")


def _unknown_footprints_without_competitors() -> None:
    indexed = Place("workspace", ("bytes", "*"))
    path = _path(Borrow(Loan("reader", "workspace", indexed)),
                 Access(indexed, via="reader"))
    ensure(not path.issues, "unknown projection was mislabeled as definitely outside its grant")
    residuals = {(item.node, item.kind) for item in path.obligations}
    ensure({("n0", "unknown-footprint"), ("n1", "unknown-footprint"),
            ("n1", "footprint-containment")} <= residuals,
           "a lone loan/access assumed equal unknown indices without a specific residual")
    direct = _path(Access(indexed))
    ensure(any(item.kind == "unknown-footprint" for item in direct.obligations),
           "direct owner projection silently resolved its unknown footprint")
    named = Place("workspace", ("bytes", "element"))
    for parent, child in ((indexed, named), (named, indexed)):
        path = _path(Borrow(Loan("writer", "workspace", parent, "exclusive")),
                     Borrow(Loan("reader", "writer", child)), Access(child, via="reader"))
        ensure("reborrow-outside-parent" not in _kinds(path)
               and any(item.node == "n1" and item.kind == "footprint-containment"
                       for item in path.obligations),
               "unknown/named reborrow relation was reported as definitely outside or contained")
    shared_write = _path(Borrow(Loan("reader", "workspace", indexed)),
                         Access(indexed, "write", "reader"))
    ensure("write-through-shared" in _kinds(shared_write),
           "an unknown footprint concealed the independent shared-write violation")
    malformed = _graph(Borrow(Loan("reader", "workspace", Place("workspace", ("bytes", "**")))))
    _refuses(lambda: analyze(_OWNERS, malformed), "normalized identifiers")


def _shared_and_exclusive_grants() -> None:
    shared = _path(Borrow(Loan("first", "workspace", _BYTES)),
                   Borrow(Loan("second", "workspace", _BYTES)), Use("first"), Use("second"))
    ensure(not shared.issues, "compatible shared sibling handles conflict")
    for mode in ("shared", "exclusive"):
        loan = Loan("second", "workspace", _BYTES, "shared" if mode == "shared" else "exclusive")
        neighbor = _path(Borrow(Loan("first", "workspace", _BYTES, "exclusive")),
                         Borrow(loan), Use("first"), Use("second"))
        ensure("competing-loans" in _kinds(neighbor), "exclusive grant did not exclude overlapping sibling")
    for operation in ("write", "move"):
        event = Access(_BYTES, "write" if operation == "write" else "move", "reader")
        neighbor = _path(Borrow(Loan("reader", "workspace", _BYTES)), event)
        ensure("write-through-shared" in _kinds(neighbor), "shared grant authorized mutation")
    exclusive = _path(Borrow(Loan("writer", "workspace", _BYTES, "exclusive")),
                      Access(_BYTES, "write", "writer"))
    ensure(not exclusive.issues, "exclusive grant could not write its own footprint")
    outside = _path(Borrow(Loan("writer", "workspace", _BYTES, "exclusive")),
                    Access(_AUDIT, "write", "writer"))
    ensure("access-outside-loan" in _kinds(outside), "grant escaped its supplied footprint")
    invalid = _path(Borrow(Loan("reader", "workspace", _BYTES)),
                    Borrow(Loan("writer", "reader", _BYTES, "exclusive")), Use("writer"))
    ensure("exclusive-from-shared" in _kinds(invalid), "shared ancestor manufactured exclusivity")
    ensure("access-route-has-no-grant" in _kinds(invalid)
           and all(end.loan != "writer" for end in invalid.restorations),
           "invalid reborrow installed/restored a usable grant")
    escaped = _path(Borrow(Loan("writer", "workspace", _BYTES, "exclusive")),
                    Borrow(Loan("reader", "writer", _AUDIT)), Use("reader"))
    ensure("reborrow-outside-parent" in _kinds(escaped), "child footprint escaped its parent")
    ensure("access-route-has-no-grant" in _kinds(escaped), "out-of-footprint child received a grant")


def _transitive_captures_and_moves() -> None:
    path = _path(Borrow(Loan("reader", "workspace", _BYTES)), Bind("inner", ("reader",)),
                 Bind("outer", ("inner",)), Move("outer", "moved"),
                 Access(_BYTES, "write"), Use("moved"), Access(_BYTES, "write"))
    ensure([issue.node for issue in path.issues if issue.kind == "suspended-parent"] == ["n4"],
           "wrapper/move failed to retain transitive capture until its use")
    ensure(_ends(path) == [("n5", "reader", "workspace")], "capture loan ended at lexical binding/move")
    ensure(any(item.kind == "capture-interpretation" and item.resources == ("outer", "reader")
               for item in path.obligations), "outer capture lost its transitive loan")
    unavailable = _path(Borrow(Loan("reader", "workspace", _BYTES)), Move("reader", "next"),
                        Use("reader"), Use("next"))
    ensure([(issue.node, issue.resources) for issue in unavailable.issues
            if issue.kind == "unavailable-name"] == [("n2", ("reader",))], "move kept old handle available")
    ensure(_ends(unavailable) == [("n3", "reader", "workspace")], "moved handle lost its canonical loan")
    retained = _path(Borrow(Loan("reader", "workspace", _BYTES)), Bind("inner", ("reader",)),
                     Bind("outer", ("inner",)), Drop("inner"), Drop("reader"), Use("outer"))
    ensure(not retained.issues and _ends(retained) == [("n5", "reader", "workspace")],
           "dropping original descriptors invalidated a retained capture-of-capture")
    aliases = _path(Borrow(Loan("reader", "workspace", _BYTES)), Bind("inner", ("reader",)),
                    Bind("outer", ("inner",)), Move("reader", "moved"), Drop("inner"),
                    Use("reader"), Use("outer"), Access(_BYTES, "read", "moved"))
    ensure([(issue.node, issue.kind) for issue in aliases.issues] == [("n5", "unavailable-name")],
           "canonical loan identity bypassed moved lexical name availability")
    ensure(_ends(aliases) == [("n7", "reader", "workspace")],
           "capture and moved access lost the shared canonical loan's final use")
    dropped = _path(Borrow(Loan("reader", "workspace", _BYTES)), Drop("reader"), Use("reader"))
    ensure("unavailable-name" in _kinds(dropped), "drop did not remove source availability")
    duplicate = _path(Borrow(Loan("reader", "workspace", _BYTES)), Bind("reader", ("reader",)), Use("reader"))
    ensure("ambiguous-name" in _kinds(duplicate), "shadowing merged two unnormalized resource identities")


def _branch_alternatives_and_returned_wrappers() -> None:
    graph = Graph("choose", (
        Node("choose", successors=("lend", "error")),
        Node("lend", Borrow(Loan("view", "workspace", _BYTES)), ("wrap",)),
        Node("wrap", Bind("packet", ("view",)), ("ready",)),
        Node("ready", Return("Ready", ("packet",))),
        Node("error", Access(_BYTES, "write"), ("reject",)),
        Node("reject", Return("Rejected")),
    ))
    report = analyze(_OWNERS, graph)
    ready, rejected = report.paths
    ensure(ready.outcome == "Ready" and rejected.outcome == "Rejected", "branch outcomes were merged")
    ensure(not ready.issues and not rejected.issues, "exclusive alternatives contaminated each other")
    ensure(ready.returned_loans == ("view",) and ready.retained_loans == ("view",)
           and ready.suspended == (_BYTES,) and not ready.restorations,
           "returned wrapper lost its parent suspension/restoration duty")
    ensure(any(item.kind == "returned-loan-lifetime" for item in ready.obligations),
           "returned view did not expose its lifetime proof")
    ensure(not rejected.retained_loans and not rejected.suspended, "error branch inherited success view")
    # Both paths reach one lexical join, but only one has created the name.
    graph = Graph("choose", (Node("choose", successors=("lend", "empty")),
                             Node("lend", Borrow(Loan("view", "workspace", _BYTES)), ("join",)),
                             Node("empty", successors=("join",)), Node("join", Use("view"))))
    present, absent = analyze(_OWNERS, graph).paths
    ensure(not present.issues and "unavailable-name" in _kinds(absent),
           "join invented a loan defined only on the sibling path")


def _drop_is_availability_only() -> None:
    direct = _path(Borrow(Loan("reader", "workspace", _BYTES)), Use("reader"),
                   Access(_BYTES, "write"), Drop("reader"))
    ensure(not direct.issues and _ends(direct) == [("n1", "reader", "workspace")],
           "availability-only drop extended the loan beyond its actual last use")
    wrapper = _path(Borrow(Loan("reader", "workspace", _BYTES)), Bind("wrapper", ("reader",)),
                    Use("wrapper"), Access(_BYTES, "write"), Drop("wrapper"), Drop("reader"))
    ensure(not wrapper.issues and _ends(wrapper) == [("n2", "reader", "workspace")],
           "dropping a wrapper extended its captured loan after the wrapper's last use")
    retained = _path(Borrow(Loan("reader", "workspace", _BYTES)), Bind("inner", ("reader",)),
                     Bind("outer", ("inner",)), Drop("inner"), Drop("reader"),
                     Access(_BYTES, "write"), Use("outer"), Drop("outer"))
    ensure([(issue.node, issue.kind) for issue in retained.issues] == [("n5", "suspended-parent")]
           and _ends(retained) == [("n6", "reader", "workspace")],
           "dropping original descriptors ended a loan retained by another live wrapper")
    stale = _path(Borrow(Loan("reader", "workspace", _BYTES)), Drop("reader"), Drop("reader"))
    ensure([(issue.node, issue.kind) for issue in stale.issues] == [("n2", "unavailable-name")],
           "demand-free drop stopped validating name availability")


def _escape_limits_and_ancestor_duties() -> None:
    graph = _graph(Borrow(Loan("writer", "workspace", _BYTES, "exclusive")),
                   Borrow(Loan("reader", "writer", _BYTES)), Return("Ready", ("reader",)))
    path = analyze(_OWNERS, graph).paths[0]
    ensure(not path.issues and path.returned_loans == ("reader",)
           and path.retained_loans == ("reader", "writer") and not path.restorations,
           "shared child escape lost its internal ancestor duty or exposed an exclusive grant")
    local = analyze((Owner("workspace"),), _graph(Borrow(Loan("reader", "workspace", _BYTES)),
                                                       Return("Ready", ("reader",)))).paths[0]
    ensure("local-loan-escape" in _kinds(local), "local storage outlived its owner")
    exclusive = _path(Borrow(Loan("writer", "workspace", _BYTES, "exclusive")), Return("Ready", ("writer",)))
    ensure("exclusive-loan-escape" in _kinds(exclusive), "unsupported exclusive escape was accepted")
    scoped = _path(Borrow(Loan("reader", "workspace", _BYTES, scoped=True)),
                   Bind("hidden", ("reader",)), Return("Ready", ("hidden",)))
    ensure("scoped-loan-escape" in _kinds(scoped), "wrapper hid a scoped escape")


def _scoped_ancestor_escapes() -> None:
    for scoped in (False, True):
        path = _path(Borrow(Loan("parent", "workspace", _BYTES, "exclusive", scoped=scoped)),
                     Move("parent", "moved"), Borrow(Loan("middle", "moved", _BYTES)),
                     Borrow(Loan("view", "middle", _BYTES)), Bind("wrapper", ("view",)),
                     Return("Ready", ("wrapper",)))
        expected = [("n5", "scoped-loan-escape", ("parent",))] if scoped else []
        ensure([(issue.node, issue.kind, issue.resources) for issue in path.issues] == expected,
               "a moved, transitively retained scoped ancestor escaped through an unscoped child")
        ensure(path.returned_loans == ("view",) and path.retained_loans == ("middle", "parent", "view")
               and not path.restorations,
               "escape diagnostics lost the child or its unresolved ancestor restoration duties")
    shared = _path(Borrow(Loan("scope", "workspace", _BYTES, scoped=True)),
                   Borrow(Loan("first", "scope", _BYTES)), Borrow(Loan("second", "scope", _BYTES)),
                   Return("Ready", ("first", "second")))
    ensure([(issue.node, issue.kind, issue.resources) for issue in shared.issues]
           == [("n3", "scoped-loan-escape", ("scope",))],
           "multiple returned descendants hid or duplicated their common scoped-ancestor diagnostic")
    local = _path(Borrow(Loan("scope", "workspace", _BYTES, "exclusive", scoped=True)),
                  Borrow(Loan("view", "scope", _BYTES)), Use("view"), Return("done"))
    ensure(not local.issues and _ends(local) == [("n2", "view", "scope"), ("n2", "scope", "workspace")],
           "transitive escape checks rejected locally restored descendants")


def _branch_local_names_and_moved_returns() -> None:
    # Identical resource spellings on exclusive paths denote different loans.
    # Both paths move parent and wrapper handles, then drop the original names.
    graph = Graph("choose", (
        Node("choose", successors=("lend", "reject")),
        Node("lend", Borrow(Loan("parent", "workspace", _BYTES, "exclusive")), ("lendMove",)),
        Node("lendMove", Move("parent", "movedParent"), ("lendView",)),
        Node("lendView", Borrow(Loan("view", "movedParent", _BYTES)), ("lendWrap",)),
        Node("lendWrap", Bind("packet", ("view",)), ("lendResult",)),
        Node("lendResult", Move("packet", "result"), ("lendDropView",)),
        Node("lendDropView", Drop("view"), ("lendDropParent",)),
        Node("lendDropParent", Drop("movedParent"), ("ready",)),
        Node("ready", Return("Ready", ("result",))),
        Node("reject", Borrow(Loan("parent", "workspace", _AUDIT, "exclusive", scoped=True)),
             ("rejectMove",)),
        Node("rejectMove", Move("parent", "movedParent"), ("rejectView",)),
        Node("rejectView", Borrow(Loan("view", "movedParent", _AUDIT)), ("rejectWrap",)),
        Node("rejectWrap", Bind("packet", ("view",)), ("rejectResult",)),
        Node("rejectResult", Move("packet", "result"), ("rejectUse",)),
        Node("rejectUse", Use("result"), ("rejectDropView",)),
        Node("rejectDropView", Drop("view"), ("rejectDropParent",)),
        Node("rejectDropParent", Drop("movedParent"), ("rejected",)),
        Node("rejected", Return("Rejected")),
    ))
    ready, rejected = analyze(_OWNERS, graph).paths
    ensure(not ready.issues and not rejected.issues,
           "exclusive paths merged same-spelled identities or moved captures")
    ensure(ready.outcome == "Ready" and ready.returned_loans == ("view",)
           and ready.retained_loans == ("parent", "view") and ready.suspended == (_BYTES,)
           and not ready.restorations,
           "success lost its returned child, canonical moved ancestor or byte footprint")
    ensure(rejected.outcome == "Rejected" and not rejected.returned_loans
           and not rejected.retained_loans and not rejected.suspended
           and _ends(rejected) == [("rejectUse", "view", "parent"),
                                   ("rejectUse", "parent", "workspace")],
           "failure retained the sibling's byte view or lost local audit restoration")
    for path, node in ((ready, "lendWrap"), (rejected, "rejectWrap")):
        ensure(any(item.node == node and item.kind == "capture-interpretation"
                   and item.resources == ("packet", "view") for item in path.obligations),
               "branch-local wrapper lost its independent capture premise")
    escaped = Graph(graph.entry, tuple(
        Node(node.name, Return("Rejected", ("result",))) if node.name == "rejected" else node
        for node in graph.nodes))
    ready, rejected = analyze(_OWNERS, escaped).paths
    ensure(not ready.issues and [(issue.node, issue.kind, issue.resources) for issue in rejected.issues]
           == [("rejected", "scoped-loan-escape", ("parent",))],
           "returning the moved audit wrapper hid its scoped ancestor or tainted its sibling")
    ensure(rejected.retained_loans == ("parent", "view") and rejected.suspended == (_AUDIT,)
           and not rejected.restorations,
           "rejected escape erased the audit path's retained restoration obligations")


def _invalid_returned_capture_has_no_grant() -> None:
    path = _path(Borrow(Loan("writer", "workspace", _BYTES, "exclusive")),
                 Move("writer", "movedWriter"), Borrow(Loan("view", "movedWriter", _AUDIT)),
                 Bind("inner", ("view",)), Bind("outer", ("inner",)),
                 Move("outer", "result"), Drop("inner"), Drop("view"),
                 Return("Ready", ("result",)))
    ensure([(issue.node, issue.kind, issue.resources) for issue in path.issues]
           == [("n2", "reborrow-outside-parent", ("view", "writer")),
               ("n8", "invalid-loan-escape", ("view",))],
           "nested moved return concealed an out-of-footprint grant's invalidity")
    ensure(path.returned_loans == ("view",) and path.retained_loans == ("writer",)
           and path.suspended == (_BYTES,) and not path.restorations,
           "invalid child installed authority or erased its real ancestor's unresolved duty")
    ensure(any(item.kind == "returned-loan-lifetime" and item.resources == ("view", "workspace")
               for item in path.obligations), "invalid escape silently discarded its lifetime premise")


def _owner_moves() -> None:
    path = _path(Borrow(Loan("reader", "workspace", _BYTES)), Access(_ROOT, "move"), Use("reader"))
    ensure("suspended-parent" in _kinds(path), "owner moved under its live child")
    moved = _path(Access(_ROOT, "move"), Access(_BYTES), Borrow(Loan("reader", "workspace", _BYTES)), Use("reader"))
    ensure("use-after-owner-move" in _kinds(moved) and moved.moved_owners == ("workspace",),
           "old owner route survived move")
    partial = _path(Access(_BYTES, "move"))
    ensure("partial-owner-move-unsupported" in _kinds(partial), "partial move acquired an implicit rule")


def _invariants_and_boundaries() -> None:
    path = _path(OpenInvariant("cell"), Borrow(Loan("guard", "workspace", _BYTES,
                                                 "exclusive", scoped=True, invariant="cell")),
                 Bind("wrapper", ("guard",)), Checkpoint(), Use("wrapper"), CloseInvariant("cell"))
    ensure({"unsupported-boundary", "scoped-loan-at-boundary", "open-invariant-at-boundary"} <= _kinds(path),
           "capture wrapper concealed a live guard/open invariant at await")
    ensure(_ends(path) == [("n4", "guard", "workspace")], "boundary ended a live guard")
    ensure(any(item.kind == "invariant-close" and item.status == "unresolved" for item in path.obligations),
           "last use silently discharged the close debt")
    early = _path(OpenInvariant("cell"), Borrow(Loan("guard", "workspace", _BYTES,
                                                  scoped=True, invariant="cell")),
                  CloseInvariant("cell"), Use("guard"))
    ensure("invariant-closed-with-live-loan" in _kinds(early), "close bypassed a retained descendant")
    unclosed = _path(OpenInvariant("cell"), Return())
    ensure("unclosed-invariant" in _kinds(unclosed), "return discarded its close debt")
    dead = _path(Borrow(Loan("guard", "workspace", _BYTES, scoped=True)), Use("guard"), Checkpoint())
    ensure("scoped-loan-at-boundary" not in _kinds(dead) and "unsupported-boundary" in _kinds(dead),
           "unused guard was retained, or ready/empty await was silently qualified")


def _structural_refusals() -> None:
    examples: tuple[tuple[Graph, str], ...] = (
        (Graph("start", (Node("start"), Node("start"))), "duplicate graph"),
        (Graph("absent", (Node("start"),)), "missing entry"),
        (Graph("start", (Node("start", successors=("absent",)),)), "missing successor"),
        (Graph("start", (Node("start", successors=("end", "end")), Node("end"))), "duplicate edges"),
        (Graph("start", (Node("start", successors=("start",)),)), "cyclic"),
        (Graph("start", (Node("start"), Node("unreachable"))), "unreachable"),
        (Graph("start", (Node("start", Return(), ("end",)), Node("end"))), "return node"),
        (_graph(Use("absent")), "missing resource"),
        (_graph(Access(Place("absent"))), "missing place"),
        (_graph(CloseInvariant("absent")), "missing invariant"),
        (_graph(Bind("first", ("second",)), Bind("second", ("first",))), "cyclic loan/capture"),
    )
    for graph, message in examples:
        _refuses(lambda graph=graph: analyze(_OWNERS, graph), message)
    duplicate = (Owner("workspace"), Owner("workspace"))
    _refuses(lambda: analyze(duplicate, _graph(Return())), "duplicate owner")
    _refuses(lambda: analyze(_OWNERS, _graph(Return()), Limits(work=0)), "positive integers")


def _complete_exploration_and_budgets() -> None:
    graph = Graph("choose", (Node("choose", successors=("left", "right")),
                             Node("left", Return("left")), Node("right", Return("right"))))
    _refuses(lambda: analyze(_OWNERS, graph, Limits(paths=1)), "path budget")
    _refuses(lambda: analyze(_OWNERS, graph, Limits(nodes=2)), "node budget")
    _refuses(lambda: analyze((*_OWNERS, Owner("second")), graph, Limits(owners=1)), "owner")
    _refuses(lambda: analyze(_OWNERS, _graph(Borrow(Loan("view", "workspace", _BYTES)),
                                            Bind("wrapper", ("view", "view"))), Limits(captures=2)),
             "capture/reference")
    _refuses(lambda: analyze(_OWNERS, graph, Limits(work=1)), "work budget")
    # Determinism includes proposed ends, residual order and complete alternatives.
    ensure(analyze(_OWNERS, graph) == analyze(_OWNERS, graph), "unchanged inputs changed diagnostics")
    # Exhaustion during analysis, after preflight/enumeration, still returns no prefix.
    for work in range(1, 60):
        try:
            report = analyze(_OWNERS, graph, Limits(work=work))
        except AnalysisRefusalError:
            continue
        ensure(len(report.paths) == 2, "budget exhaustion exposed a partial report")


def _generated_branch_demand_oracle() -> None:
    # Independent finite model: only explicit reads demand the shared loan.
    # A parent write before that path's last read conflicts; an audit-field
    # write never does. The sibling's reads must not affect either decision.
    alternatives = tuple(product(("use", "write", "audit", "idle"), repeat=2))

    def event(operation: str) -> Event:
        match operation:
            case "use":
                return Use("reader")
            case "write":
                return Access(_BYTES, "write")
            case "audit":
                return Access(_AUDIT, "write")
            case _:
                return Nop()

    for left, right in product(alternatives, repeat=2):
        nodes = [Node("lend", Borrow(Loan("reader", "workspace", _BYTES)), ("left0", "right0"))]
        for branch, operations in (("left", left), ("right", right)):
            nodes.extend(Node(f"{branch}{index}", event(operation),
                              (f"{branch}1",) if index == 0 else ())
                         for index, operation in enumerate(operations))
        reports = analyze(_OWNERS, Graph("lend", tuple(nodes))).paths
        ensure(len(reports) == 2, "finite branch oracle lost an alternative")
        for report, branch, operations in zip(reports, ("left", "right"), (left, right), strict=True):
            last_read = max((index for index, operation in enumerate(operations) if operation == "use"),
                            default=-1)
            end_node = "lend" if last_read < 0 else f"{branch}{last_read}"
            expected = [(f"{branch}{index}", "suspended-parent", ("reader",))
                        for index, operation in enumerate(operations)
                        if operation == "write" and index < last_read]
            ensure([(issue.node, issue.kind, issue.resources) for issue in report.issues] == expected,
                   f"branch demand/conflict differs from independent oracle: {branch}, {operations}")
            ensure(_ends(report) == [(end_node, "reader", "workspace")],
                   f"restoration differs from explicit last-read oracle: {branch}, {operations}")
            ensure(not report.retained_loans and not report.suspended and not report.returned_loans,
                   "finite branch retained a loan after its last demand")
            ensure(all(item.status == "unresolved" for item in report.obligations),
                   "finite oracle promoted supplied facts into checked obligations")


def _malformed_records_and_edges() -> None:
    # Deliberately cross the annotated API boundary: malformed supplied facts
    # must refuse the whole analysis rather than leak an incidental Python error.
    def supplied(value: object) -> object:
        return value

    examples: tuple[tuple[object, str], ...] = (
        (None, "Graph record"),
        (Graph(cast("str", supplied([])), (Node("entry"),)), "normalized identifiers"),
        (Graph("entry", cast("tuple[Node, ...]", supplied([Node("entry")]))), "immutable tuples"),
        (Graph("entry", (cast("Node", supplied(None)),)), "Node record"),
        (Graph("entry", (Node("entry", successors=(cast("str", supplied([])),)),)), "normalized identifiers"),
        (Graph("entry", (Node("entry", successors=cast("tuple[str, ...]", supplied(["entry"]))),)), "edges"),
        (_graph(Borrow(cast("Loan", supplied(None)))), "Loan record"),
        (_graph(Borrow(Loan(cast("str", supplied(None)), "workspace", _BYTES))), "normalized identifiers"),
        (_graph(Bind(cast("str", supplied(None)), ())), "normalized identifiers"),
        (_graph(Move("workspace", cast("str", supplied(None)))), "normalized identifiers"),
        (_graph(Borrow(Loan("view", "workspace", cast("Place", supplied(None))))), "Place record"),
        (_graph(Access(cast("Place", supplied(None)))), "Place record"),
        (_graph(Access(Place(cast("str", supplied([]))))), "normalized identifiers"),
        (_graph(Access(Place("workspace", cast("tuple[str, ...]", supplied(None))))), "projection"),
        (_graph(Borrow(Loan("view", "workspace", _BYTES, invariant=cast("str", supplied([]))))),
         "normalized identifiers"),
        (_graph(CloseInvariant(cast("str", supplied([])))), "normalized identifiers"),
    )
    for graph, message in examples:
        _refuses(lambda graph=graph: analyze(_OWNERS, cast("Graph", graph)), message)
    for owners, message in (
        ((cast("Owner", supplied(None)),), "Owner record"),
        ((Owner("workspace", fields=(cast("tuple[str, ...]", supplied(7)),)),), "projection"),
    ):
        _refuses(lambda owners=owners: analyze(owners, _graph(Return())), message)
    _refuses(lambda: analyze(_OWNERS, _graph(Return()), cast("Limits", supplied({}))), "Limits record")


def _selective_invariant_lifting() -> None:
    buffer_owners = (
        Owner(
            "this",
            borrowed=True,
            fields=(("length",), ("slots",)),
            invariants=("LengthBound", "InitializedPrefix", "VacantSuffix"),
        ),
    )
    slots = Place("this", ("slots",))
    length = Place("this", ("length",))
    graph = _graph(
        OpenInvariant("this", ("InitializedPrefix", "VacantSuffix")),
        Access(slots, "write"),
        Access(length, "write"),
        CloseInvariant("this", ("InitializedPrefix", "VacantSuffix")),
        Return("done"),
    )
    path = analyze(buffer_owners, graph).paths[0]
    ensure(not path.issues, f"selective invariant lifting reported unexpected issues: {path.issues}")
    ensure(
        ("n0", "invariant-active", ("this", "LengthBound"))
        in {(item.node, item.kind, item.resources) for item in path.obligations},
        "unlifted invariant clause was not kept active when sibling clauses were lifted",
    )
    ensure(
        path.active_invariants
        == (
            ("this", "InitializedPrefix"),
            ("this", "LengthBound"),
            ("this", "VacantSuffix"),
        )
        and not path.open_invariants,
        "closing lifted clauses did not restore full active invariant set",
    )

    early_return = analyze(
        buffer_owners,
        _graph(
            OpenInvariant("this", ("InitializedPrefix", "VacantSuffix")),
            Access(slots, "write"),
            Return("early"),
        ),
    ).paths[0]
    ensure(
        [(issue.kind, issue.resources) for issue in early_return.issues]
        == [
            ("unclosed-invariant", ("this", "InitializedPrefix")),
            ("unclosed-invariant", ("this", "VacantSuffix")),
        ],
        "early return while clauses were lifted did not report per-conjunct unclosed-invariant debt",
    )
    ensure(
        early_return.active_invariants == (("this", "LengthBound"),)
        and early_return.open_invariants
        == (("this", "InitializedPrefix"), ("this", "VacantSuffix")),
        "early return lost active vs lifted conjunct partition",
    )

    boundary = analyze(
        buffer_owners,
        _graph(
            OpenInvariant("this", ("InitializedPrefix", "VacantSuffix")),
            Checkpoint("await"),
            CloseInvariant("this", ("InitializedPrefix", "VacantSuffix")),
        ),
    ).paths[0]
    ensure(
        ("open-invariant-at-boundary", ("this", "InitializedPrefix"))
        in {(issue.kind, issue.resources) for issue in boundary.issues}
        and ("open-invariant-at-boundary", ("this", "VacantSuffix"))
        in {(issue.kind, issue.resources) for issue in boundary.issues},
        "checkpoint while clauses were lifted missed per-conjunct boundary issue",
    )

    whole_receiver = analyze(
        buffer_owners,
        _graph(
            OpenInvariant("this", ("InitializedPrefix",)),
            Access(Place("this"), "read"),
            CloseInvariant("this", ("InitializedPrefix",)),
        ),
    ).paths[0]
    ensure(
        ("open-invariant-whole-receiver", ("this", "InitializedPrefix"))
        in {(issue.kind, issue.resources) for issue in whole_receiver.issues},
        "whole-receiver access while a clause was lifted did not report an issue",
    )

    _refuses(
        lambda: analyze(
            buffer_owners,
            _graph(OpenInvariant("this", ("UnknownClause",)), CloseInvariant("this", ("UnknownClause",))),
        ),
        "missing invariant",
    )


def _cfg_join_merging_and_bounded_loops() -> None:
    # 12 sequential if-diamonds would require 2^12 = 4096 paths under full path enumeration
    # (exceeding Limits.paths = 128), but merge at each join point in linear time.
    nodes: list[Node] = []
    for idx in range(12):
        split = f"split_{idx}"
        then_borrow = f"then_b_{idx}"
        then_use = f"then_u_{idx}"
        else_borrow = f"else_b_{idx}"
        else_use = f"else_u_{idx}"
        join = f"join_{idx}"
        next_node = f"split_{idx + 1}" if idx + 1 < 12 else "done"
        nodes.extend(
            (
                Node(split, Nop(), (then_borrow, else_borrow)),
                Node(
                    then_borrow,
                    Borrow(Loan(f"tloan_{idx}", "workspace", _BYTES)),
                    (then_use,),
                ),
                Node(then_use, Use(f"tloan_{idx}"), (join,)),
                Node(
                    else_borrow,
                    Borrow(Loan(f"eloan_{idx}", "workspace", _AUDIT, "exclusive")),
                    (else_use,),
                ),
                Node(else_use, Access(_AUDIT, "write", f"eloan_{idx}"), (join,)),
                Node(join, Access(_BYTES, "write"), (next_node,)),
            )
        )
    nodes.append(Node("done", Return("ok")))
    report = analyze(_OWNERS, Graph("split_0", tuple(nodes)))
    ensure(len(report.paths) == 1, "join-point merging did not coalesce compatible branch states")
    merged = report.paths[0]
    ensure(not merged.issues, f"merged 12-diamond CFG reported unexpected issues: {merged.issues}")
    ensure(len(merged.restorations) == 24, "merged 12-diamond CFG lost branch loan restorations")

    # Bounded foreach loop over the CFG: header -> (body_borrow, exit), body_drop -> header.
    loop_graph = Graph(
        "entry",
        (
            Node("entry", Nop(), ("header",)),
            Node("header", Nop(), ("body_borrow", "exit")),
            Node(
                "body_borrow",
                Borrow(Loan("elem", "workspace", Place("workspace", ("bytes", "*")), scoped=True)),
                ("body_use",),
            ),
            Node("body_use", Use("elem"), ("body_drop",)),
            Node("body_drop", Drop("elem"), ("header",)),
            Node("exit", Access(_BYTES, "write"), ("done",)),
            Node("done", Return("ok")),
        ),
    )
    loop_report = analyze(_OWNERS, loop_graph)
    ensure(len(loop_report.paths) == 1 and not loop_report.paths[0].issues, "bounded loop failed")
    ensure(
        _ends(loop_report.paths[0]) == [("body_use", "elem", "workspace")],
        "bounded loop did not restore scoped element loan at body_use",
    )

    # Loop-carried owner move must be detected on the second iteration at fixpoint.
    move_in_loop = Graph(
        "entry",
        (
            Node("entry", Nop(), ("header",)),
            Node("header", Nop(), ("body_move", "exit")),
            Node("body_move", Access(_ROOT, "move"), ("header",)),
            Node("exit", Return("done")),
        ),
    )
    move_path = analyze(_OWNERS, move_in_loop).paths[0]
    ensure(
        "use-after-owner-move" in _kinds(move_path),
        "kleene fixpoint over loop header missed loop-carried use-after-owner-move",
    )


def _surface_ast_to_loan_graph_lowering() -> None:
    def id_node(text: str) -> dict[str, object]:
        return {"text": text, "span": [0, len(text)]}

    def ident(name: str) -> dict[str, object]:
        return {"kind": "identifier", "name": id_node(name), "span": [0, 1]}

    def member(recv: dict[str, object], field_name: str) -> dict[str, object]:
        return {"kind": "member", "receiver": recv, "member": id_node(field_name), "span": [0, 1]}

    def borrow_expr(mode: str, value: dict[str, object]) -> dict[str, object]:
        return {"kind": "borrow", "mode": mode, "value": value, "span": [0, 1]}

    def call_arg(mode: str, value: dict[str, object]) -> dict[str, object]:
        return {"kind": "call_argument", "mode": mode, "value": value, "span": [0, 1]}

    def call_expr(name: str, *args: dict[str, object]) -> dict[str, object]:
        return {
            "kind": "call",
            "callee": ident(name),
            "type_arguments": [],
            "arguments": list(args),
            "span": [0, 1],
        }

    # Module with BoundedBuffer struct (fields, views, invariants) and functions:
    # 1. RelocateInto: selective `scope (ref this, ref destination) lifts InitializedPrefix, VacantSuffix`
    # 2. DisjointViews: borrows `in this.Entries` and `ref this.Tail` simultaneously (no conflict)
    # 3. ConflictingViewWrite: borrows `in this.Entries` then mutates `this.slots` (suspended-parent)
    # 4. EarlyExitInScope: `let ... else { return; }` inside `scope (ref this) lifts InitializedPrefix`
    # 5. ManyBranchesAndLoop: 9 sequential `if` statements + `foreach_collection` loop
    # 6. ReceiverAliasCall: `Format.Write(ref builder, $"len={builder.Length}")` (suspended-parent)
    if_chain = [
        {
            "kind": "if",
            "condition": ident("cond"),
            "then_body": [
                {
                    "kind": "let",
                    "name": id_node(f"r_{idx}"),
                    "value": borrow_expr("in", member(ident("this"), "slots")),
                },
                {"kind": "expression", "expression": call_expr("Inspect", call_arg("in", ident(f"r_{idx}")))},
            ],
            "else_body": [
                {
                    "kind": "assign",
                    "operator": "=",
                    "target": member(ident("this"), "length"),
                    "value": {"kind": "nat", "value": "0", "span": [0, 1]},
                }
            ],
        }
        for idx in range(9)
    ]

    module_ast: dict[str, object] = {
        "schema": 2,
        "ast": {
            "kind": "surface_file",
            "name": id_node("BorrowCheckModule"),
            "declarations": [
                {
                    "kind": "struct",
                    "name": id_node("BoundedBuffer"),
                    "contracts": [
                        {"kind": "invariant", "label": id_node("LengthBound"), "expression": ident("true")},
                        {"kind": "invariant", "label": id_node("InitializedPrefix"), "expression": ident("true")},
                        {"kind": "invariant", "label": id_node("VacantSuffix"), "expression": ident("true")},
                    ],
                    "members": [
                        {"kind": "field", "name": id_node("length"), "field_type": {"kind": "type", "name": id_node("usize"), "arguments": []}},
                        {"kind": "field", "name": id_node("slots"), "field_type": {"kind": "type", "name": id_node("Slots"), "arguments": []}},
                        {
                            "kind": "view",
                            "name": id_node("Entries"),
                            "clauses": [{"kind": "view_range", "name": id_node("slots"), "start": ident("zero"), "end": ident("length")}],
                        },
                        {
                            "kind": "view",
                            "name": id_node("Tail"),
                            "clauses": [{"kind": "view_index", "name": id_node("slots"), "index": ident("length")}],
                        },
                        {
                            "kind": "method",
                            "name": id_node("RelocateInto"),
                            "parameters": [
                                {
                                    "kind": "parameter",
                                    "mode": "ref",
                                    "name": id_node("destination"),
                                    "parameter_type": {"kind": "type", "name": id_node("BoundedBuffer"), "arguments": []},
                                }
                            ],
                            "contracts": [],
                            "body": [
                                {
                                    "kind": "scope",
                                    "target": {
                                        "kind": "tuple",
                                        "elements": [borrow_expr("ref", ident("this")), borrow_expr("ref", ident("destination"))],
                                    },
                                    "lifts": [id_node("InitializedPrefix"), id_node("VacantSuffix")],
                                    "body": [
                                        {
                                            "kind": "expression",
                                            "expression": call_expr(
                                                "CopyRepresentation",
                                                call_arg("in", member(ident("this"), "slots")),
                                                call_arg("ref", member(ident("destination"), "slots")),
                                                call_arg("value", member(ident("this"), "length")),
                                            ),
                                        },
                                        {
                                            "kind": "expression",
                                            "expression": call_expr(
                                                "TransferType",
                                                call_arg("ref", member(ident("this"), "slots")),
                                                call_arg("ref", member(ident("destination"), "slots")),
                                                call_arg("value", member(ident("this"), "length")),
                                            ),
                                        },
                                        {
                                            "kind": "assign",
                                            "operator": "=",
                                            "target": member(ident("destination"), "length"),
                                            "value": member(ident("this"), "length"),
                                        },
                                        {
                                            "kind": "assign",
                                            "operator": "=",
                                            "target": member(ident("this"), "length"),
                                            "value": {"kind": "nat", "value": "0", "span": [0, 1]},
                                        },
                                    ],
                                }
                            ],
                        },
                        {
                            "kind": "method",
                            "name": id_node("DisjointViews"),
                            "parameters": [],
                            "contracts": [],
                            "body": [
                                {
                                    "kind": "let",
                                    "name": id_node("entries"),
                                    "value": borrow_expr("in", member(ident("this"), "Entries")),
                                },
                                {
                                    "kind": "var",
                                    "name": id_node("tail"),
                                    "value": borrow_expr("ref", member(ident("this"), "Tail")),
                                },
                                {
                                    "kind": "expression",
                                    "expression": call_expr("WriteSlot", call_arg("ref", ident("tail"))),
                                },
                                {
                                    "kind": "expression",
                                    "expression": call_expr("ReadEntries", call_arg("in", ident("entries"))),
                                },
                            ],
                        },
                        {
                            "kind": "method",
                            "name": id_node("ConflictingViewWrite"),
                            "parameters": [],
                            "contracts": [],
                            "body": [
                                {
                                    "kind": "let",
                                    "name": id_node("entries"),
                                    "value": borrow_expr("in", member(ident("this"), "Entries")),
                                },
                                {
                                    "kind": "assign",
                                    "operator": "=",
                                    "target": member(ident("this"), "slots"),
                                    "value": ident("emptySlots"),
                                },
                                {
                                    "kind": "expression",
                                    "expression": call_expr("ReadEntries", call_arg("in", ident("entries"))),
                                },
                            ],
                        },
                        {
                            "kind": "method",
                            "name": id_node("EarlyExitInScope"),
                            "parameters": [{"kind": "parameter", "mode": "value", "name": id_node("candidate"), "parameter_type": None}],
                            "contracts": [],
                            "body": [
                                {
                                    "kind": "scope",
                                    "target": borrow_expr("ref", ident("this")),
                                    "lifts": [id_node("InitializedPrefix")],
                                    "body": [
                                        {
                                            "kind": "let_else",
                                            "pattern": {
                                                "kind": "constructor_pattern",
                                                "name": id_node("Some"),
                                                "arguments": [{"kind": "binding_pattern", "name": id_node("val")}],
                                            },
                                            "value": ident("candidate"),
                                            "else_body": [{"kind": "return", "value": None}],
                                        },
                                        {
                                            "kind": "assign",
                                            "operator": "=",
                                            "target": member(ident("this"), "length"),
                                            "value": ident("val"),
                                        },
                                    ],
                                }
                            ],
                        },
                        {
                            "kind": "method",
                            "name": id_node("ManyBranchesAndLoop"),
                            "parameters": [{"kind": "parameter", "mode": "value", "name": id_node("cond"), "parameter_type": None}],
                            "contracts": [],
                            "body": [
                                *if_chain,
                                {
                                    "kind": "foreach_collection",
                                    "mode": "in",
                                    "name": id_node("item"),
                                    "collection": member(ident("this"), "slots"),
                                    "contracts": [],
                                    "body": [
                                        {
                                            "kind": "expression",
                                            "expression": call_expr("Inspect", call_arg("in", ident("item"))),
                                        }
                                    ],
                                },
                            ],
                        },
                    ],
                },
                {
                    "kind": "function",
                    "name": id_node("ReceiverAliasCall"),
                    "parameters": [
                        {
                            "kind": "parameter",
                            "mode": "ref",
                            "name": id_node("builder"),
                            "parameter_type": {"kind": "type", "name": id_node("TextBuilder"), "arguments": []},
                        }
                    ],
                    "contracts": [],
                    "body": [
                        {
                            "kind": "expression",
                            "expression": call_expr(
                                "FormatWrite",
                                call_arg("ref", ident("builder")),
                                call_arg(
                                    "value",
                                    {
                                        "kind": "interpolated_string",
                                        "parts": [
                                            {"kind": "text", "value": "len="},
                                            {"kind": "interpolation", "expression": member(ident("builder"), "Length"), "format": None},
                                        ],
                                    },
                                ),
                            ),
                        }
                    ],
                },
            ],
        },
    }

    lowered_all = lower_module(module_ast)
    ensure(len(lowered_all) == 6, f"expected 6 lowered functions, got {len(lowered_all)}")
    reports = analyze_module(module_ast)

    relocate = reports["BoundedBuffer.RelocateInto"].paths[0]
    ensure(not relocate.issues, f"RelocateInto reported unexpected issues: {relocate.issues}")
    ensure(
        ("this", "LengthBound") in relocate.active_invariants
        and ("destination", "LengthBound") in relocate.active_invariants
        and not relocate.open_invariants,
        "RelocateInto did not keep LengthBound active or close lifted clauses",
    )

    disjoint_views = reports["BoundedBuffer.DisjointViews"].paths[0]
    ensure(
        not disjoint_views.issues,
        f"disjoint named views Entries and Tail conflicted: {disjoint_views.issues}",
    )

    conflict_view = reports["BoundedBuffer.ConflictingViewWrite"].paths[0]
    ensure(
        "suspended-parent" in _kinds(conflict_view),
        "writing backing field `slots` while `Entries` view loan was live did not conflict",
    )

    early_scope = reports["BoundedBuffer.EarlyExitInScope"]
    ensure(
        any(
            ("unclosed-invariant", ("this", "InitializedPrefix"))
            in {(issue.kind, issue.resources) for issue in path.issues}
            for path in early_scope.paths
        ),
        "let-else early return inside `scope ... lifts` did not report unclosed-invariant",
    )

    many_branches = reports["BoundedBuffer.ManyBranchesAndLoop"]
    ensure(
        len(many_branches.paths) == 1 and not many_branches.paths[0].issues,
        f"9-branch + foreach function failed or did not merge: {many_branches.paths}",
    )

    alias_call = analyze_function(module_ast, "ReceiverAliasCall").paths[0]
    ensure(
        "suspended-parent" in _kinds(alias_call),
        "reading builder.Length inside interpolated string under active `ref builder` loan did not conflict",
    )


def cases() -> list[Case]:
    return [Case("last-use restoration and unresolved facts", _last_use_and_residuals),
            Case("nested restoration and suspended ancestors", _nested_restoration_and_suspension),
            Case("declared field partitions and unknown overlap", _field_partitions_and_unknowns),
            Case("unknown footprints and containment without competing loans", _unknown_footprints_without_competitors),
            Case("shared/exclusive access and reborrow grants", _shared_and_exclusive_grants),
            Case("transitive captures, moves and availability", _transitive_captures_and_moves),
            Case("branch-specific returned views and unavailable names", _branch_alternatives_and_returned_wrappers),
            Case("availability-only drops preserve actual last use", _drop_is_availability_only),
            Case("escape restrictions and retained ancestor duties", _escape_limits_and_ancestor_duties),
            Case("scoped ancestors cannot escape through returned descendants", _scoped_ancestor_escapes),
            Case("branch-local identities and moved returned captures stay separate",
                 _branch_local_names_and_moved_returns),
            Case("invalid returned captures never install a grant", _invalid_returned_capture_has_no_grant),
            Case("owner movement and blocked routes", _owner_moves),
            Case("invariant and suspension boundaries", _invariants_and_boundaries),
            Case("malformed graphs and absent references", _structural_refusals),
            Case("malformed records and edge identities refuse completely", _malformed_records_and_edges),
            Case("generated independent branch-demand and restoration oracle", _generated_branch_demand_oracle),
            Case("complete deterministic exploration and bounded refusal", _complete_exploration_and_budgets),
            Case("selective per-conjunct invariant lifting and unlifted active clauses", _selective_invariant_lifting),
            Case("cfg join-point state merging and bounded loop fixpoint", _cfg_join_merging_and_bounded_loops),
            Case("schema-2 surface ast to loan graph lowering pass", _surface_ast_to_loan_graph_lowering)]
