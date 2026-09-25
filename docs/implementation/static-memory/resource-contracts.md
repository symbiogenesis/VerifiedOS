# Static memory resource contracts

This artifact gives bounded component contracts a conditional guaranteed-success
specification: every admitted request slot has a checked fixed placement, enough
prepaid backing, a balanced resource ledger, and an explicit upper bound from
lexical release to safe reuse. It is a host analysis of an admitted contract.
Source completeness, compiler preservation, hardware behavior and real elapsed
bounds remain separate proof obligations. No requirement is discharged here.

The implementation is [memory_planner_resources.py](../../../tools/vos/memory_planner_resources.py),
over the bounded interpreter in
[memory_planner_contracts.py](../../../tools/vos/memory_planner_contracts.py).
The mathematical models are
[MemoryPlannerResources.v](../../../proofs/MemoryPlannerResources.v) and
[MemoryPlannerContracts.v](../../../proofs/MemoryPlannerContracts.v).
The [planner contract](../portable-memory-planner.md) owns the placement
checker and its evidence boundaries.

## Backing and release semantics

The physical check comes first. The independently checked placement establishes
alignment, pool containment, reservations and separation of every interfering
object. The resource wrapper reserves, in each pool, the layout span plus an
explicit overhead tail. That tail must cover its own alignment and all additional
metadata, padding and representation costs. The complete reservation must fit the
physical pool capacity and be backed before request activation.

Each acquisition takes the object's declared byte charge from its request slot.
Only a validated reuse barrier returns that charge. Lexical release leaves the
object charged while retained holders, accepted device work, revocation, sweeping
or scrubbing remain. Every normal, exception, cancellation and timeout path must
return all its obligations. Independent slots cannot borrow one another's credits
or placement. Their per-pool peak requirements add, including the possibility
that different slots take different branches.

A backward calculation finds the exact initial credit needed by each finite
take/return trace; an independent forward execution checks success and restoration.
A separate identity ledger matches every return to its acquisition. Scalar credit
does not establish the availability of a suitably shaped extent: both the ledger
and checked fixed offsets are required. Prepaid fixed slots avoid an online
allocator's fragmentation and refill questions within this admitted model.

Each operation has a caller-supplied elapsed upper bound in a named unit. A
lease's reuse bound sums operations from the start of its lexical release
request through completion of its barrier, including the release operation
itself. A bound for `complete` must include any waiting for
device completion; other bounds must likewise include scheduling, preemption and
blocking. The analysis checks every path against `reuse_deadline`. An event count,
fairness assumption or eventual-completion theorem alone supplies no such bound.
The demo uses synthetic admitted ticks, with no hardware timing claim.

## Retained obligations and in-place eligibility

An object declaration may set `retained_limit`, defaulting to one. `retain`,
`drop` and `use` accept a `holder` identity. Every named holder is separately
tracked, a dropped holder cannot be used, and every holder must drain before safe
reuse. A named identity cannot be retained again later on the same object's path;
device submission identities are likewise one-shot along the path. Distinct
identities permit bounded object reincarnation without confusing an old completion
or retained reference with a new obligation.

These are static contract identities. They implement neither runtime epoch
counters nor transferable bearer tokens. Omitted holders retain the existing
single-holder contract behavior and do not distinguish runtime aliases. A bounded
loop with named holders or device submissions must provide distinct identities
for its incarnations; automatic token generation is outside this IR.

`unique-use` requires active lexical ownership, no retained holder and no pending
device work. This checks an eligibility condition for in-place reuse. The IR
contains no data transformation or type-preservation proof for a compiler rewrite.
Region lifetimes may cross lexical boundaries, but every region here is an
explicit bounded object rather than an inferred language region.

Extraction evidence exposes every path's operations, acquisition/release/barrier
indices, peak charged bytes, post-release charged bytes, retained holder count
and device obligation count. Its version and content digest bind the normalized
contract to the generated placement instance and path evidence.

## Resource wrapper and public API

The resource JSON object has schema `memory-resource-contract-v1` and these fields:

| Field | Meaning |
| --- | --- |
| `contract` | Complete `memory-component-contract-v1` component input |
| `placement` | Candidate rows containing `id`, `pool` and `offset` |
| `reserved_bytes` | Byte budget for every pool, with no missing or additional pool |
| `overhead_bytes` | Additional permanently charged tail for every pool |
| `step_bounds` | Nonnegative elapsed bound for exactly every operation used by an expanded path |
| `reuse_deadline` | Maximum admitted release-to-barrier elapsed bound |
| `time_unit` | Explicit unit for bounds and deadline |
| `assumptions` | Optional additional caller assumptions |

Input quantities fit the portable signed-64 range; booleans are not quantities.
Structural, path and metering limits refuse incomplete analysis. The wrapper does
not accept an unknown field by silently ignoring it.

`analyze_resources(raw, max_work=1000000)` returns a content-bound report with
`checked resource contract` or `refused resource contract` status, errors,
per-pool footprints and slot credits, and every path's credit and deadline traces.
Malformed input, exhausted analysis bounds or an invalid placement raises a
`ValueError` subclass. Underfunding and missed deadlines produce explicit refusal
reports. `replay_resources(raw, report)` recomputes the report and detects altered
evidence. `demo_resources()` supplies a complete synthetic wrapper.

`emit_resource_certificate(raw, max_work=1000000)` performs fresh analysis under
the supplied budget and refuses an invalid resource contract. It emits Rocq
examples that compute the actual finite credit
actions and deadline sums, plus source and report digests. Emission is proof
source, pending kernel compilation. Neither the digest nor the generated numeric
examples prove that the source extractor selected the right events. The optional
artifact is host output and does not alter target execution.

## Mechanized statements and the remaining bridge

### Prefix and sequential-composition proof contract

The [prefix-discrepancy research review](../../background/open-math-conjectures.md#strong-or-prefix-komlós-conjecture)
motivates checking intermediate demand independently of final balance. The finite
credit model can establish that distinction directly, without assuming a
discrepancy theorem. This extension keeps `CreditEvent`, `required_credit`,
`run_credit`, `taken`, `returned` and all existing theorem statements unchanged.
Its acceptance predicate is an axiom-free proof that sufficient credit is
equivalent to `taken prefix <= initial + returned prefix` for every prefix;
an exact requirement for concatenation; and the maximum-of-requirements law when
the first phase is balanced. Concrete serial and overlapping traces must have
the same totals but different peak requirements, and a balanced trace with
arbitrary demand must refute any bound inferred from final balance alone.

Review covers the unchanged placement and return-identity premises below.
Acceptance uses the exact assumption audit, non-vacuity review and fresh kernel
check through Guest CI with `cold: true`, together with green Host CI. Dispatch
is recorded with its revision; a pending guest verdict is not proof acceptance.
These are finite accounting results, not the prefix Komlós lower bound or a
resource guarantee for catalytic computation.

### Existing accounting and refinement boundary

`required_credit_exact` equates successful finite execution with sufficient
initial credit. `below_requirement_fails` establishes the failing side.
`credit_conservation` accounts for issued and returned bytes;
`balanced_trace_restores_credit` supplies the reusable-slot postcondition and
`repeated_balanced_traces_fit` extends it to any finite repetition.
`resource_aware_refines_partial` derives a weaker specification that permits
allocation failure while the stronger precondition excludes that failure.

The prefix extension states the same success condition at every cut of a trace:
issued bytes cannot exceed initial credit plus the bytes already returned.
For sequential traces `a` and `b`, the exact initial requirement is
`max(required_credit a, required_credit b + taken a - returned a)`, with
natural-number subtraction. When `a` is balanced, this reduces to the maximum
of the two phase requirements. The rule permits compositional accounting for
one slot; it neither reorders operations nor lends credit between slots. Equal
final totals alone do not determine the requirement: taking and returning four
bytes before taking three needs four credits, while overlapping those takes
needs seven.

`release_deadline_sound` sums pointwise admitted elapsed bounds. Its premise is a
real obligation on each operation, including device waiting and cleanup.
`retained_alias_blocks_barrier` and the existing device barrier theorem in the
component model establish that any outstanding holder count or device work blocks
reuse. These are authored finite semantics, with concrete success, insufficient
credit, missing-return and delayed-cleanup examples.

The next meaningful refinement proof must relate the executable interpreter's
named holder/device ledger and extracted lease traces to the Gallina barrier and
credit semantics, then relate the admitted component contract to actual source
execution. The current credit model treats returns as supplied protocol facts;
its arithmetic theorem alone cannot establish correct return identity or physical
revocation. A subsequent target proof must establish backing, complete footprint
charges, slot admission and the elapsed bounds used by the report. The full Vela
language, compiler and target machine are outside these finite models.

### Research handoff for ordering and prefix bounds

The [prefix Komlós review](../../background/open-math-conjectures.md#strong-or-prefix-komlós-conjecture)
rules out using a universal constant-prefix assertion for unrestricted signed
vector instances; its manuscript lower bound is not a theorem of this module.
The missing source/interpreter refinement above can instead consume the exact
finite prefix and concatenation lemmas already present. A future multidimensional
extension would need a coordinate-to-pool correspondence and nonnegative inventory
at every prefix, preserving object identity and return authorization. A final-sum
signing theorem alone cannot discharge those facts.

The [Steinitz lead](../../background/open-math-conjectures.md#euclidean-steinitz-conjecture)
belongs to an optional transformation before extraction: show the total-zero and
norm premises, meet the announced dimension restriction when using that special
case, and prove that the chosen permutation preserves dependencies and observable
effects. Translate the norm guarantee into charged capacity with an explicit
initial inventory. A consumption-before-production permutation and a precedence
violation are negative witnesses even when their final sum is zero; a legal
reordering with checked prefix demand is the positive case. These are research
handoffs, not permission to reorder the fixed credit trace or add an analysis
whose only yield is bound tightening.

## Literature disposition and provenance

Every adoption below is an adaptation of a specification or accounting idea into
repository-authored code and proofs. No donor source, proof library, runtime,
collector or allocator is imported. The broader
[static-memory literature disposition](literature.md) owns the
implementation mapping beyond this bounded interface; the proof inventory and
Q27 retain source qualification, policy disposition and consumer assignment.

| Review entry and primary source | Adopted here | Separate work or excluded mechanism |
| --- | --- | --- |
| 22, [Spegion](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ECOOP.2025.15) | Explicit nonlexical object lifetimes and retained aliases contribute to occupancy | Its inferred regions, splitting and effect/type soundness are not implemented; Spegion does not require substructural types |
| 23, [RaRust](https://arxiv.org/abs/2502.19810) | An explicit resource requirement is carried alongside the admitted behavior | Prophecy potentials, Rust borrow analysis and automatic bound inference remain separate; a linear cost bound is not automatically a peak-space bound |
| 24, [RaML](https://www.raml.co/about/) | Separate byte and elapsed-cost metrics; bounded paths yield independently checked resource requirements | Polynomial inference and its optimization toolchain are not imported |
| 25, [FP2](https://www.microsoft.com/en-us/research/wp-content/uploads/2023/05/fbip.pdf) | `unique-use` makes an ownership precondition for in-place eligibility executable | No general functional-language transformation or fully in-place typing theorem is claimed |
| 26, [Perceus/Koka](https://www.microsoft.com/en-us/research/project/koka/?lang=fr-ca) | Multiple holders remain obligations until each is dropped; unique ownership is checked explicitly | Reference-count insertion, reuse specialization and Koka runtime mechanisms remain separate |
| 27, [IrisFit](https://iris-project.org/pdfs/2025-toplas-willitfit.pdf) | Retained roots remain charged, and space and elapsed availability have separate obligations | Its tracing-GC model and sufficient polling premises are not the revocation protocol; its bounded-time result also requires those premises |
| 49, [Leaf](https://arxiv.org/abs/2309.04851) | Temporary sharing must drain every named holder before exclusive reuse | No guarding connective, modular lock verification or Iris proof import |
| 50, [Nextgen](https://iris-project.org/pdfs/2025-cpp-nextgen.pdf) | Distinct static identities prevent an old obligation from being treated as a new incarnation | No Nextgen modality or runtime epoch machinery; generation-changing resource reasoning remains a future semantic bridge |
| 51, [Actris 2.0](https://iris-project.org/pdfs/2022-lmcs-actris2-final.pdf), and 52, [Mixtris](https://iris-project.org/pdfs/2026-oopsla-mixtris.pdf) | Accepted asynchronous work carries an explicit completion obligation across release | Session typing, mixed choice and multiparty protocol verification remain outside the finite resource interface |
| 54, Prosa, and 55, [RefinedProsa](https://iris-project.org/pdfs/2025-pldi-refinedprosa.pdf) | Deadline checking requires elapsed bounds that include execution overheads and scheduling assumptions | No response-time analysis is imported; RefinedProsa's verified interrupt-free scheduler does not directly supply this target's bounds |
| 56, [Parcas](https://iris-project.org/pdfs/2026-icfp-parcas.pdf) | Costs carry an explicit interpretation; work or span is not silently treated as elapsed completion time | Parallel work/span credits and their program logic remain separate |
| 57, [wait-freedom logic](https://iris-project.org/pdfs/2026-ecoop-wfree.pdf) | Safe-reuse admission requires a quantitative completion bound in addition to safety | No higher-order concurrent wait-freedom proof or inferred wall-clock bound |
| 58, [Lawyer](https://iris-project.org/pdfs/2026-oopsla-lawyer.pdf), and 59, [Lilo](https://iris-project.org/pdfs/2025-oopsla-lilo.pdf) | Terminal cleanup cannot discard an outstanding obligation; every exceptional path is checked | Modular concurrent liveness and relational service reasoning remain separate; eventual progress alone does not establish the configured deadline |
| 60, [general-purpose RCU](https://iris-project.org/pdfs/2025-pldi-weak-smr.pdf), and 61, [hazard-pointer optimistic traversals](https://iris-project.org/pdfs/2025-pldi-hp-revisited.pdf) | Completion and every retained user block reclamation independently of lexical lifetime | Relaxed-memory ordering, RCU and hazard-pointer algorithms are not implemented or claimed equivalent to the target protocol |
| 62, [Iron](https://iris-project.org/pdfs/2019-popl-iron-final.pdf) | The identity ledger must restore every outstanding resource at terminal outcomes | Iron's core tracks resources in an affine logic and Iron++ offers a linear layer; this implementation imports neither logic and derives no deadline from leak freedom |
| 102, [Verified Sequential Malloc/Free](https://www.cs.princeton.edu/~appel/papers/memmgr.pdf) | Strong resource-aware success specification, weaker failure-permitting specification, prepaid backing and restored credits | The donor uses size-class resource vectors because fragmentation defeats scalar byte budgets; our fixed placement supplies the corresponding shape obligation without importing its allocator or VST proof |

Koka's own [license file](https://raw.githubusercontent.com/koka-lang/koka/master/LICENSE)
states Apache-2.0. This establishes the inspected candidate's terms, not an import.
The [SYS-MEMMGR qualification](../../assurance/proof-reuse/systems.md#sys-memmgr-a-resource-aware-allocator-specification-under-reciprocal-terms)
records LGPL v3 from the DeepSpecDB README, `COPYING` and `COPYING.LESSER`.
Those are the allocator artifact's terms; VST's separate license does not replace
them. This implementation adapts the specification idea and conveys no donor
source or proof. Any future incorporation must inspect the actual pinned files
and their terms at that milestone.
