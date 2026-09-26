# Service authoring contracts

These contracts bind the host-authorable portions of M6.3b, M4.4, M6.6 through M6.8 and Q23d. The [requirements register](../../requirements-register.md) and the [implementation checklist](../implementation-checklist.md) remain normative. This document owns the interfaces and acceptance scope of the service source artifacts. It does not record an independent review, a target run, or completion of those checklist items.

## 1. Object router and credential handles

The namespace and live-query statement is `proofs/ObjectRouter.v`. The credential extension is additive to `proofs/CredentialHandles.v`; it must consume that file's authorization, delegation, expiry and shared-account predicates rather than introducing a competing credential policy.

R-10-005b's query input is a live session's presented namespace capability, the requested confidentiality domain, stable namespace identifier, object identity and attenuated rights. Persisted index keys contain typed data and identifiers, never capabilities; no tagged write may occur inside the declared key/index extent. Index extents must remain inside one confidentiality domain. A returned object capability must be derivable from that session's presented namespace capability. The router's namespace/rights records are logical descriptors, not claims that a hardware capability has been built or authenticated.

R-10-005c's subscription has composition-fixed result and queue bounds. Only committed transactions publish ordered add/remove deltas. Overflow transitions to a rescan-required state with exactly one marker, bounded storage and no subsequent delta until rescan. Publication and ring fullness never change the committing transaction's progress result. Reboot removes subscriptions, and re-establishment begins with rescan. Atomic agreement of stored objects and indexes remains the storage join, not a property obtained merely by setting a committed Boolean.

R-12-015a enumerates exactly these seven credential bindings: protocol role, principal, peer/origin scope, permitted operation, transcript/domain separator, use count and expiry. The extension must expose an opaque sealed-handle boundary carrying all seven, reject client export, and refuse widening protocol role, peer/origin scope and permitted operation. Logical handle constructors do not establish unforgeability of real CHERI sentries, cryptographic key custody or the concrete protocol IDL. Fresh consent and time remain the existing trusted callbacks; atomic charging and storage/ring target integration remain explicit joins.

Acceptance for the authorable scope:

- A valid namespace fixture is accepted. A tagged key, cross-domain index and widened query each have a named rejected construction.
- A publication exactly at the queue bound retains its deltas. One beyond the bound emits exactly one rescan marker; a later publication adds no delta. Two-marker, backpressure, pre-commit publication and reboot-survival constructions are rejected, and recovery begins with rescan.
- Valid opaque-handle use reaches the existing authorization operation. Raw export and each of the three requested scope widenings are rejected. The seven bindings are explicit and survive issuance/resolution unchanged.
- Native Rocq compilation, complete constant/assumption and record-witness audits, and a joint kernel recheck of the changed modules and their actual local dependencies pass. Selected mutation regions and every survivor disposition are recorded with exact scope.

The intent variants and ambiguity policy remain owner decisions at R-12-013a and R-12-024b. The first/last-match arms in `HandlerGraph.v` must remain distinguishable; no predicate here chooses one. Deterministic translation-cache integration remains open with those decisions. Real namespace writes, queries and credential operations await M5.3's storage and an executable ring service.

### Research handoff for the future index implementation

M6.3b's unimplemented namespace and query indexes may compare the survey's
[dynamic ordered indexes](../../background/open-math-conjectures.md#compact-static-dictionaries-and-dynamic-ordered-indexes),
[hashing](../../background/open-math-conjectures.md#hashing-beyond-the-uniform-probing-conjecture)
and [BST optimality](../../background/open-math-conjectures.md#dynamic-optimality-of-binary-search-trees)
leads only after selecting an actual bounded workload. The
[workload handoff](wasm-execution.md#mathematical-research-handoff) records their
distinct models and cost limits; it does not choose this service's representation.
A candidate here would still need a concrete index invariant and refinement of
lookup, update, deletion and exhaustion, preserving domain confinement, untagged
keys, committed publication and rescan behavior. Exercise absent and duplicate
keys, the full-capacity boundary, a refused cross-domain query and restart during
an update. Expected/amortized operations do not establish bounded service phases
or crash consistency. Immutable composer tables have the separate
[resident-producer comparison](../../performance/toolchain-residency.md#research-leads-for-bounded-resident-passes).
These are optional research inputs, with no change to this contract's acceptance
predicate, index selection or implementation scope.

## 2. Single kernel instance

`proofs/KernelInstance.v` consumes `PartitionContext.v` and `CyclicExecutive.v`. `RunAnswersM44` supplies the three trace questions with unique attempts and exact observed-write multiplicity; `QualifiedRunAnswersM44` adds the semantic barrier and sanitized-image join. Both have reference/refuting traces. The [scalar ABI contract](purecap-abi.md) and the differential corpus schema own register, primitive and target conventions.

The partition-root clause checks declared in-program derivation attempts past the partition root and every declared shared window. Refusal is the resulting cleared capability tag; the trace reader must not independently decode capability bounds. Attempt coverage, result identity and observation presence must be checked, so absence of an attempted derivation cannot pass as refusal.

The switch clause consumes the exact merged-register value/tag restoration and the profile-owned nameable CSR obligations. A roster used for enumeration must cover the owner predicate. The trace may omit architectural zero-register writes only under an explicit architectural invariant. The contract must distinguish the merged register/CSR observation clause from out-of-file capability registers and pending interrupt state, rather than treating an unobserved component as proved restored.

The revocation join must connect a barrier-sanitized saved image or the defined filtered-load result to exact restored values/tags. Completion requires the resident-register, saved-context, loan and device conditions from [revocation-qualification.md](../../assurance/revocation-qualification.md), not an epoch counter alone. A faithfully restored stale image is a negative example, not a successful revocation test.

The frame predicate reads instruction PCs against declared partition and switch extents, requires the table's sequence and exactly one occurrence of each reserved slot, rejects astray PCs and extraneous switches, and makes no runtime scheduling choice. It does not read a cycle counter or infer duration from retire order; duration is the static admitted max-path sum.

Acceptance for the authorable scope:

- A concrete valid fixture satisfies all stated decidable clauses. Missing root/window attempts and tagged over-bound results are refused.
- Truncated register restore, lost validity tag and omitted nameable CSR each fail. An epoch-only completion and a stale saved image fail the revocation clause. The supported sanitized/filtered join has a positive witness with its prerequisites explicit.
- Reordered, duplicate, missing and unreserved slot/switch sequences fail. Altering a trace's order numerals does not manufacture duration evidence.
- Focused native proof/audit/recheck and selected trace/restore mutation evidence pass. Every extra architectural or semantic premise is recorded rather than silently counted as observed.

A corpus executable requires M1.2f's backend, M1.7's target path, an agreed primitive and initial-capability interface, and M3.5's actual handoff. Unbuilt C may be authored only against those explicit interfaces and must be labelled unbuilt; neither a fixture nor this Gallina predicate closes M4.4. R2 owns the multi-instance join.

The [scalar final-restore primitive](../../../kernel/README.md#scalar-final-restore)
owns an executable C-class subset with an empty partition-nameable CSR roster.
Its setup, exact register-restore and dispatch extents are separate: MEPCC setup
and the dispatching `mret`'s `mstatus` effect are observed outside the register
restore burst. This supplies an emitter and generated target controls for that
subset. The caller's stable protected save image, semantic revocation completion,
initial capability handoff and trap/timer installation remain required inputs.
General CSR, vector and pending-state restoration retain their existing owners.

## 3. Inference descriptor and admission

`proofs/InferenceAdmission.v` owns a single common shape descriptor and session interface consumed by the residency and grant-to-rate arithmetic. A shape carries resident bytes, context length, quantization format, expert count, fixed top-k and KV bytes per token. The composition's ceiling carries those bounds/admitted formats plus the bank grant, the seven terms enumerated by R-12-085. `composition_opening` is the full admission entry point, `opening` its ceiling/resource core, and `checked_routed_work` the guarded route operation. Slot, worker identifiers, pools and session capacity are composition constants; opening a session changes occupancy or returns a typed refusal, never enlarges them.

The reference wire schema is a fixed sequence of bounded-width fields. Admissible bytes must be in byte range, consume exactly the declared schema extent and have no ignored tail or alternate normalization. Decoding is injective on accepted byte strings; re-encoding a decoded descriptor reproduces the identical input; encoding a shape satisfying field bounds decodes to that shape. The descriptor is data and gives weights no execute authority. A standalone reference codec does not itself establish the required Narcissus derivation or an executable parser join; that correspondence must be identified explicitly.

Session admission refuses malformed/noncanonical descriptors, every exceeded model ceiling, unresident experts, zero/undeclared per-token byte demand, exhausted session capacity and rates above the derived grant. Fixed top-k means a fixed number of resident expert contributions; its work function must be independent of which valid expert indices are selected. Routed storage fetch returns a typed refusal. Rate is the integer bound derived from the symbolic bank grant and declared per-token traffic, never a host timing result and never an elastic degraded rate.

Acceptance for the authorable scope:

- Round-trip, byte reproduction, decode-injectivity and fixed-schema-size theorems hold. At least one noncanonical alias/ignored-field decoder is refuted, with concrete valid and invalid descriptors.
- Every ceiling field is tested at its boundary and above it; an above-ceiling model is refused at open. Server placement/resource fields remain equal before and after both successful and refused opens.
- Every expert is resident at admission, invalid expert indices/routes are refused, and two valid fixed-top-k routes have identical work. A storage-fetching implementation and an expert-dependent work function are refuted.
- The admitted rate spends no more than the declared bank grant; an above-grant request is refused, not degraded. Session exhaustion neither overcommits nor alters other server resources.
- Focused native proof/audit/recheck and selected parser/admission arithmetic mutations pass with all survivors investigated.

All bandwidth, latency, work, format widths and residency capacities that DSE or qualification owns remain symbolic composition fields. [Inference demand](../../performance/inference-demand.md) and its manifest supply demand provenance only. Q4b owns timed target figures; these contracts claim none. Optional module qualification failure must not silently forward a request to another destination (R-12-085f).

## 4. Ensemble schedule statement and emission

`proofs/EnsembleSchedule.v` extends the existing cyclic-executive record by importing it. Per-core task admission remains `CyclicExecutive.admits`. The fourth output contains each member's link-slot views, frame length, guard bands, leap/cadence, leader-tree information, oscillator tolerances, derived skew and table digest commitments. The link contract and sharding traffic report supply symbolic inputs, not measured constants invented in the examples.

`qualified_emission_admits` checks the attested bound against the derived bound and the separately supplied qualification measurement against that bound. One emission decision checks both views of each link. A directed send/receive pair must identify matching slots and frame length, and each digest must be computed over the selected table representation. Guards cover derived skew plus link latency, and cadence times both endpoint tolerances must fit the guard. The root does not leap; every follower has exactly one leader link. A follower's leap is a kernel-owned idle window simultaneously covering every core and after the verifying crypto slot. It never retunes a clock and is not a partition's slot.

Link-hop chain cost is computed from slot period plus guard band and composed with the other declared hop terms. No supplied asserted chain magnitude can bypass that computation. Exceeding a declared chain deadline fails admission.

Acceptance for the authorable scope:

- A concrete symbolic two-member reference emission is admitted by the statement. Mismatched views/digests, too-small guard, excessive cadence, a leap missing a core, a leap before verification and an unadmitted link task are refused by name.
- The derived skew and chain bound have theorems connecting them to their operands; deadline excess is refused. Perturbing an irrelevant asserted fixture bound cannot affect the computed accepted result.
- The per-core admission record is reused, not reimplemented. Focused native proof/audit/recheck and selected guard/leap/chain mutation evidence pass with scoped verdicts.
- The statement/emission function is distinct from a production composition-tool emitter. Search the existing composition tooling before extending emission; if the required synthesizer or schema is absent, identify the missing interface and retain that integration as open rather than author a second production emitter.

The frame synthesizer is not needed to state and prove these predicates over symbolic records. It is required to close Q23d's one-production-composition-act emission and admission, with the Q23b constants, Q23e traffic, real digest binding and all four attested outputs. Independent owner decisions about units or unresolved schema interpretations remain explicit and may not be chosen merely to make a fixture pass.

## 5. Shared validation and status

All new proof sources need live requirement manifests, native enumerated assumption and witness audits and concrete positive/negative examples. `python tools/run.py check` runs after intended deliverables are tracked. Shared generated ledger repairs and the final combined host/proof waves belong to the integrator. A worker's narrow verification does not claim a fresh full-tree proof receipt.

These criteria add no register requirement, change no estimate and claim no checklist completion. Each original task's recovery report records the tested revision, source scope, commands, exact results, deferred owner acts and target joins.
