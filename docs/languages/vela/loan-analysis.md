# Vela loan-analysis diagnostic

This is [Q25j's](../../../PLAN.md#q-assessment-actions) bounded experimental
contract. It commissions inference over supplied flow facts, independently of
source elaboration. The [core loan rules](core-design.md#loans-and-control-flow),
[capture rules](graded-foundation.md#functions-and-application) and
[frontend disposition](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows)
retain their meanings and prerequisites. This diagnostic supplies no source
acceptance, checked interpretation, memory-safety theorem or machine law.

## Input and composition

The Python API consumes an explicit finite acyclic control-flow graph with named
owners, declared field projections, shared/exclusive loans and parent links.
Events describe borrowing, access, resource moves, binding capture environments,
uses, outcome-specific returns and unsupported suspension boundaries. Each
operation's facts are explicit inputs: a library call does not obtain authority
from its name. Boxes, optional values, cells, callbacks and protocol wrappers use
the same capture and loan facts, without dedicated cases for their type names.
Owner identities and field partitions are supplied abstract facts, not inferred
from source spelling or pointer inequality. Unknown overlap remains unresolved.

Names must be unambiguous within a path. A child loan must stay within its parent
footprint; a shared parent cannot produce an exclusive child. Missing references,
duplicate graph identities, malformed edges, cycles and exhausted node/path/work
budgets refuse analysis. No partial exploration may produce a complete result.
Loops need a separately checked invariant/back-edge interpretation; unrolling
supplied finite paths does not establish termination or loop-carried borrowing.

The current [implementation](../../../tools/vos/vela_loans.py) materializes every
complete path and analyzes each separately. Independent branches can therefore
produce exponentially many paths as the graph grows; this follows from the
algorithm and is not a measured latency result. `Limits` owns the bounded node,
path, capture and work budgets. Exhaustion refuses the complete analysis without
returning partial success. This diagnostic establishes neither production
scalability nor a choice of production algorithm; the
[promotion contract](core-design.md#borrow-analysis-promotion) retains that decision.

## Inference and obligations

Analyze complete reachable paths separately so a join never unions mutually
exclusive loans into one resource state. Backward demand follows transitive
captures and loan ancestry; forward analysis detects competing access, use before
creation, use after move and invalid reborrows. Loan ends are inferred at last
use, with descendants ended before ancestors. Each inferred end records a
restoration obligation with its path and location. It does not prove restoration,
run cleanup, discard a tracked value or erase a required verdict.

Access through a loan requires its grant and respects overlapping descendant
suspension. Declared disjoint fields remain accessible. Unknown projections or
alias relations produce residual overlap obligations rather than permission.
A shared loan may escape only into a declared borrowed parameter under an
explicit return summary. That outcome retains the loan and ancestor restoration
duties, with overlapping parent access suspended. A scoped ancestor also retains
its scope restriction through moved handles, nested reborrows and wrapper
captures; returning an unscoped descendant cannot hide that restriction. Its
error sibling restores locally. Local-owner and exclusive escapes produce
diagnostics. Closure returns must include their transitive captures. Suspension and open-invariant cases
remain unsupported or unresolved; syntactic availability is no proof of safety.

The result distinguishes structural refusal, detected conflicts, unresolved
obligations and path-specific proposed ends/escapes. A graph with no detected
conflict still needs every restoration, capture, effect and interpretation proof.
The API must not expose an admitted-program or memory-safe verdict.

## Using the diagnostic

[vela_loans.py](../../../tools/vos/vela_loans.py) exposes immutable graph/event
records and `analyze(owners, graph, limits)`. Run its focused behavioral checks
with `python tools/run.py test --only test_vela_loans --jobs 1` on Windows.
An explicit result split can be modeled as follows:

```python
from vos.vela_loans import Access, Borrow, Graph, Loan, Node, Owner, Place, Return, analyze

input_place = Place("input")
report = analyze((Owner("input", borrowed=True),), Graph("lend", (
    Node("lend", Borrow(Loan("view", "input", input_place)), ("ready", "error")),
    Node("ready", Return("Ready", ("view",))),
    Node("error", Access(input_place, "write"), ("rejected",)),
    Node("rejected", Return("Rejected")),
)))
```

The `Ready` path retains the shared view and suspended parent footprint. On
`Rejected`, no later use demands the view: its proposed end precedes the write,
and its restoration remains an unresolved obligation. `PathReport` keeps those
outcomes separate. `Issue` describes a detected conflict or unsupported operation;
`Obligation` and `Restoration` retain unresolved premises. `AnalysisRefusalError`
means malformed input or incomplete exploration and returns no report.

`Use` means reading through a handle's retained loans. `Bind` retains captures
without accessing their contents; `Move` transfers a descriptor's availability.
`Drop` removes availability without running resource disposal or extending a
dead loan's demand. Moving an owner root is an explicit `Access(..., "move")`;
partial owner moves remain unsupported. Array projections use `"*"` and retain
explicit overlap/containment obligations. The graph is a supplied model, not an
extraction from the Menhir tree.

## Acceptance

The design inputs have separate jobs. [Ante-style invalidation](interior-mutability.md#ante-as-a-candidate-for-static-invalidation)
distinguishes address validity from current-content facts;
[Granule/Gerty and the graded foundation](verification-strategy.md#reading-the-graded-type-claims)
inform lawful demand without creating memory permission;
[Polonius](verification-strategy.md#research-that-changes-the-experiments)
informs branch-sensitive lifetime inference; and
[borrow-end reasoning](core-design.md#reuse-decisions) informs restoration.
This increment implements only the explicit flow/capture/restoration experiment.
Static invalidation of dependent facts, grade checking and their combined checked
interpretation remain open at those owners. A loan-end proposal does not certify
any of them.

Independent focused tests cover last-use restoration; named disjoint fields and
overlapping prefixes; nested reborrows and ancestor suspension; shared versus
exclusive interference; transitive captures and retained wrappers; moves;
separate returned-view/error outcomes; invalid local/exclusive escape; unknown
overlap; malformed records, edge identities, graphs, cycles and budget exhaustion.
Malformed supplied records produce a structural refusal, including nested
loan/footprint records and field paths; they produce no partial diagnostic.
Rejected neighbors must reach their intended obligation instead of failing an
unrelated input check.
Tests assert restoration order and retained obligations, not only conflict counts.

Run the affected host test module and Python type/lint checks, then the repository
consistency checker on settled inputs. Hosted Host CI and selected Guest CI remain
the validation handoff when publication is authorized. Record focused verdicts
separately from the exact-revision hosted evidence.
Full frontend, concrete laws, checked derivations and comparative ergonomic or
performance claims retain their existing owners; this experiment claims no
superiority to Polonius.

## Conditional borrowing comparison

A comparison commissioned through the existing
[client qualification](first-release.md#qualification) freezes independently
reviewed client behavior, expected decisions and the compared guarantee
endpoints. Pin the compiler/analyzer revision and configuration, explicitly
distinguishing original Polonius from Polonius Alpha. Pin the selected
[Ante design](interior-mutability.md#ante-as-a-candidate-for-static-invalidation)
and identify its implemented subset; a design example supplies no compiler
verdict. Supplied graph diagnostics and source checking have different endpoints.

Record accepted, semantically rejected, unsupported and incomplete cases
separately. A diagnostic with no detected conflict still carries its unresolved
proof obligations and supplies no source acceptance. Compare matching behavior
without weakening ownership, dependent facts, effects or required guarantees.
Retain manual rewrites, annotations and the first intended diagnostic; an
unrelated parse/type failure supplies no borrowing rejection evidence.

Reuse the applicable [measurement record and sampling](workflow-contract.md#measurement-record-and-sampling)
for diagnostic latency, elapsed/CPU time, peak memory and environment identity.
Record graph size, branching, captures, configured budgets and budget refusals
alongside successful cases. State each claimed improvement's objective and
supported workload, including regressions and endpoint differences. A finite
comparison establishes no universal optimality. This contract commissions no
additional benchmark, source integration or production-analysis implementation
within Q25j.
