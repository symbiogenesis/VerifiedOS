# SPDX-License-Identifier: Apache-2.0
"""Independent complete-path loan-flow fixtures and rejected neighbors."""

from collections.abc import Callable

from tests.harness import Case, ensure
from vos.vela_loans import (
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
    OpenInvariant,
    Owner,
    PathReport,
    Place,
    Return,
    Use,
    analyze,
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
            Case("owner movement and blocked routes", _owner_moves),
            Case("invariant and suspension boundaries", _invariants_and_boundaries),
            Case("malformed graphs and absent references", _structural_refusals),
            Case("complete deterministic exploration and bounded refusal", _complete_exploration_and_budgets)]
