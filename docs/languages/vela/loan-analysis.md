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
duties, with overlapping parent access suspended. Its error sibling restores
locally. Local-owner and exclusive escapes produce diagnostics. Closure returns
must include their transitive captures. Suspension and open-invariant cases
remain unsupported or unresolved; syntactic availability is no proof of safety.

The result distinguishes structural refusal, detected conflicts, unresolved
obligations and path-specific proposed ends/escapes. A graph with no detected
conflict still needs every restoration, capture, effect and interpretation proof.
The API must not expose an admitted-program or memory-safe verdict.

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
overlap; malformed graphs, cycles and budget exhaustion. Rejected neighbors must
reach their intended obligation instead of failing an unrelated input check.
Tests assert restoration order and retained obligations, not only conflict counts.

Run the affected host test module and Python type/lint checks, then the repository
consistency checker on settled inputs. Hosted Host CI and selected Guest CI remain
the validation handoff when publication is authorized. For this local-only session,
record focused verdicts and defer publication and hosted evidence explicitly.
Full frontend, concrete laws, checked derivations and comparative ergonomic or
performance claims retain their existing owners; this experiment claims no
superiority to Polonius.
