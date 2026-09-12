# Static memory without an MMU: capacity limits and a research agenda

> Non-normative research companion. The [requirements register](../requirements-register.md) remains authoritative. This document identifies limits, surveys research, and proposes experiments; it changes no admission criterion or architectural exclusion. Literature status is checked through 12 September 2026. Proposed conjectures below are this document's research questions, not established results or claims made by the cited authors.

Static allocation makes memory use explicit and bounds interference. It does not make every unused byte available to every request. A useful research objective is to **increase the workload a fixed physical memory budget can admit, while retaining bounded execution, capability isolation, and no address translation**. Zero waste is too broad a target: some reservation is the cost of an unconditional service guarantee, some is required for safe reuse, and some is avoidable layout or representation overhead.

The most promising first work is offline: improve physical placement, change object lifetimes and representations, and jointly schedule computation and reclamation. More flexible sharing and movement deserve separate experiments with their changed assumptions visible. Neither a new allocator nor a new MMU is a prerequisite for studying the first group.

## What remains valuable

The [static memory plan](../spec.md#r-08-010) gives every object a bounded home before execution. The [capacity contract](../spec.md#r-08-045) refuses an image whose physical reservations do not fit; runtime occupancy remains variable, and a [full pool](../spec.md#r-08-047) can decline service. This is a useful separation of admission from operation, even when utilization is poor.

The design's retained advantages have different causes. Removing online placement removes its search, allocator state, and synchronization costs. Fixed ownership prevents one compartment's burst from consuming another's reservation. CHERI bounds supply access control without page translation; the absence of page tables, TLBs, faults for demand paging, and shootdowns removes their state and proof obligations. The fixed memory classes and fabric schedule support timing analysis. Exact slot plans expose initialization, revocation, and capacity costs to checking before deployment. No single one of these properties establishes all the others: in particular, an MMU-free system can have a dynamic allocator, and a statically allocated system can have wasted space.

Keeping these advantages is the baseline for comparison. A capacity gain is useful only after charging its additional instructions, metadata, zeroization, reclamation, memory traffic, deadlines, and proof obligations.

## What fragmentation and stranded capacity mean here

"Free" needs an owner, a size, a location, a time, and permission to reuse. A byte holding no useful payload can still be unavailable to the request under consideration. This is usually **stranded capacity**, not a lost-pointer memory leak. Safe revocation deliberately makes old authority unusable; eventual reuse is a separate property.

| Cause | How capacity becomes unavailable | What could improve it |
| --- | --- | --- |
| Physical packing gaps | Contiguous objects with overlapping lifetimes constrain where other objects fit, even in an offline plan | Better packing; a different schedule or object representation |
| Alignment and bounds granularity | Object bases and extents satisfy native access, tag, and exactly representable capability bounds | Layout and representation changes with exact narrowing retained |
| Fixed size classes | A small payload occupies a larger slot; one class fills while another is empty | Compose different classes; bounded segmented representations |
| Peak reservation | Backing remains reserved while a pool is below its admitted peak | Prove mutually exclusive use, stream state, or change the promised service |
| Ownership and placement restrictions | A different island, pool, memory class, or bank has space the requester cannot use | Recompose ownership or placement; runtime borrowing needs a different contract |
| Extended retention | A region, saved state, alias, or asynchronous operation keeps storage unavailable after its last useful computation | More precise ownership transitions; smaller regions; earlier completion |
| Quarantine and recovery | Retired objects await containment, sweep and initialization; restart workspaces require room during failure | Jointly budget retirement bursts, sweep service and recovery overlap |
| Duplicate contents | Independently owned mutable state happens to contain the same data | Statically justified sharing or recomputation; value-based runtime deduplication changes assumptions |

These categories are diagnostic, not an additive accounting formula. A quarantined slot can also contain alignment padding. A measurement needs a disjoint byte ledger and may attach several explanations to the same byte; adding independent estimates double-counts it.

Consider a deliberately synthetic composition with two owners, each holding a pool of four 64-byte slots. If one pool is full and the other empty, a fifth request to the first owner fails despite idle backing at the second. No online allocator has created a hole, and no pointer is lost. The existing no-borrowing rule makes the unused capacity unreachable to that request. More accurate placement within either pool cannot fix this example.

Likewise, two free 32-byte extents separated by a pinned live object do not satisfy one contiguous 64-byte request. This is an example of a particular layout, not proof that the best offline layout must have that gap. The distinction between a poor assignment and an unavoidable optimum matters.

### Live payload is a lower bound, not a placement theorem

For one fixed execution schedule and one allocatable address arena, let each object have size `s_i` and lifetime `[b_i, e_i)`. Define:

```text
L = max_t sum of s_i over objects live at t
OPT = minimum span of a legal, fixed, contiguous placement
P = span of the particular legal placement emitted by a planner

L <= OPT <= P
```

The inequalities assume the same objects, lifetime endpoints, and legal constraints in all comparisons. `OPT - L` is the unavoidable gap for that model; `P - OPT` is planner suboptimality. Neither equals total platform overhead. Apply the model separately to physically distinct arenas; adding capacities from different memory classes does not make their bytes interchangeable. For a real image, lifetimes extend through safe reuse, and metadata and recovery reservations belong in the charged model.

General offline dynamic storage allocation can require `OPT > L`. Buchsbaum, Karloff, Kenyon, Reingold and Thorup study precisely this separation and provide approximation results, including a polynomial-time `(2 + epsilon)` approximation in the general problem. That result assumes the paper's rectangle/interval model; it is neither equality with live load nor a guarantee for an arbitrary greedy planner with added CHERI, island, and bank constraints. [*OPT Versus LOAD in Dynamic Storage Allocation*, SIAM Journal on Computing, 2004](https://epubs.siam.org/doi/10.1137/S0097539703423941)

A useful exact special case is a fixed family of laminar object lifetimes: any two are disjoint or one contains the other. With fixed sizes, one arena, and no extra alignment or pinning restrictions, placing each object above its ancestors achieves the maximum simultaneous load. This elementary stack argument concerns those object lifetimes. Nested region scopes do not establish that all objects inside them die at their last use, and changing arbitrary lifetimes into nested ones can increase retention. Tofte and Talpin's region calculus establishes a safe region discipline with runtime allocation into regions; it does not establish a fixed physical slot and a tight whole-program capacity bound for every allocation. [*Region-Based Memory Management*, 1997](https://www.sciencedirect.com/science/article/pii/S0890540196926139)

Ownership alone also does not determine exact sizes, allocation multiplicity, or elapsed lifetime. An exclusively owned list can grow with input; an exclusively owned buffer can remain live until an external response. A composition needs explicit bounds and checked control-flow or protocol premises. A workload trace can suggest useful transformations, but one trace is not evidence that two reservations never overlap on any admitted execution.

There is another gap between one trace and all inputs. Suppose `N` unit-sized object identities each have one immutable offset, and the allowed modes activate any pair but never three. Every mode's peak payload is two units, yet every pair needs distinct offsets because it coexists in some mode. One layout valid for every mode therefore needs `N` units. This elementary example does not describe every possible pool implementation: generic reusable slots or different precomputed bindings can avoid its fixed-identity premise. It shows why the research must specify whether it optimizes one known trace, a conservative interference graph over all executions, or a finite family of checked bindings.

### Claims that need reconciliation

R-08-012 states that external fragmentation disappears and footprint equals peak liveness. Read universally for heterogeneous contiguous objects, it is stronger than the offline result above. R-08-011 and R-08-013 also need a precise bridge from the admitted language's ownership and regions to the claimed lifetime class. R-08-018's equal-slot pool has no variable-sized holes *within that pool*; R-08-018b already acknowledges size-class waste, R-08-019 acknowledges peak-versus-average capacity, and R-15-007k requires quantized placement. Those qualifications cannot be silently discarded or used to turn the stronger claim into a proved theorem.

These are scope questions for the [memory-plan specification](../../proofs/MemoryPlan.v) and the register, left explicit by this non-normative document. The [placement-search contract](../implementation/placement-search.md) already distinguishes live footprint from address span and padding, and refuses a footprint-gain claim from moving bases alone. Its witness plan is not a measured product roster. The research agenda starts with reconciling these quantities, not with assuming a universal zero-fragmentation theorem.

The same contract documents [R-08-014's lifetime-predicate inversion](../implementation/placement-search.md#4-the-constraints-and-who-decides-them): physical slots must be disjoint when lifetimes overlap, whereas the entry says disjoint live ranges. A new formalization needs the correct predicate and an explicit disposition of that existing gap.

## Research with a plausible path to this design

The sources below supply methods and counterexamples. Their measured gains belong to their workloads and machines; this document transfers none of those percentages to VerifiedOS.

### Certified offline placement and joint scheduling

**Established method, unfinished integration.** OLLA jointly optimizes tensor lifetimes and physical locations using an integer program. Its useful lesson is that changing execution order can reduce live load while moving addresses alone cannot. Applying this to VerifiedOS requires preserving data dependencies, observable I/O order, functional results, and each admitted slot bound; training-graph freedom is not permission to reorder arbitrary operating-system effects. [Steiner et al., *OLLA*, 2022 preprint](https://arxiv.org/abs/2210.12924v2)

**Recent empirical candidate.** Lamprakos et al.'s *Futureproof Static Memory Planning* develops idealloc for large offline instances, including difficult cases beyond small tensor examples. The April 2025 version is a preprint submitted to TOPLAS. It motivates scalable heuristics and a harder benchmark corpus, but its empirical success does not certify optimality or the feasibility of a VerifiedOS placement. [Paper and implementation discussion](https://arxiv.org/html/2504.04874v1)

The first experiment reuses Q5's exporter and independent candidate checks. Compare existing enumeration with deterministic heuristics, then consider a solver only for a demonstrated coupled problem. An untrusted search can emit a checkable placement; proving optimality additionally needs a lower bound or an independently checkable infeasibility argument. Solver timeout means the search is unfinished. The current objective still preserves footprint before locality and changes no island assignment. Q5 conditionally discusses a solver, while R-05-104's criterion says no ILP machinery exists in the toolchain; any proposed solver integration needs that scope tension resolved first.

R-08-012b also excludes sampled profiles, learned weights, and runtime feedback from placement. Research traces may evaluate a candidate but cannot silently become production placement inputs. R-08-018b separately permits a workload size histogram to inform the composition-fixed size-class set; that is a distinct input with a distinct purpose.

Q5's present enumerator ranks span and then padding while holding lifetimes fixed. Joint scheduling is a proposed extension that changes the emitted artifact and its live load; it is not a capability of that base enumerator.

TensorFlow Lite Micro is a useful engineering control: its documented arena distinguishes reusable head buffers, temporary storage, and persistent tail allocations. Measure all of them when reproducing its approach. A planned tensor head alone is not a whole operating system's memory budget. [TFLM memory-management documentation](https://github.com/tensorflow/tflite-micro/blob/main/tensorflow/lite/micro/docs/memory_management.md)

### Regions, resource types, and explicit phase structure

**Published language research.** Spegion supplies implicit non-lexical, splittable regions, sized allocations, and a type-safety result. It offers a concrete basis for studying earlier region release and bounded subregions. Less lexical retention may improve capacity while making lifetimes less laminar and physical placement harder; both effects need measurement. Its source-language theorem does not supply CHERI-TAL lowering, quarantine, DMA ownership, or whole-image reservations. [Hughes, Vollmer and Batty, *Spegion*, ECOOP 2025](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ECOOP.2025.15)

**Published resource analysis.** RaRust uses resource-aware types and prophecy potentials to infer linear resource bounds through Rust borrowing. This is evidence that ownership and quantitative resource reasoning can be combined, not that ordinary ownership already proves a bound. A transfer needs a cost semantics that counts peak resident storage and delayed reuse, not merely accumulated allocation or abstract ticks. [Lian and Wang, *Automatic Linear Resource Bound Analysis for Rust via Prophecy Potentials*, OOPSLA 2025](https://stonebuddha.github.io/publication/lianw25/)

There is a local policy boundary: R-05-105 rejects a verified tool whose only yield is tightening an already sound bound. A research analyzer can diagnose retention and guide transformations. Admission of a new analysis requires another demonstrated yield or an explicit policy revision; a tighter inferred number alone is not an adopted lever. Under the current rules, prioritize changing the program into bounded phases whose existing certificate exposes the improvement.

### Recomputation, streaming, and representation changes

**Established optimization, workload-dependent transfer.** Checkmate formulates tensor rematerialization as a computation-versus-memory optimization and emits a static schedule. Adapt its method to pure computations whose inputs remain available: recompute an intermediate, tile a frame, stream a parser, or fuse adjacent stages so less data stays resident. Keep irreversible I/O, nonce consumption, and mutable observations outside replay unless a functional proof permits it. Use admitted worst-case costs and traffic, not the paper's profiled accelerator costs. [Jain et al., *Checkmate*, MLSys 2020](https://proceedings.mlsys.org/paper_files/paper/2020/hash/0b816ae8f06f8dd3543dc3d9ef196cab-Abstract.html)

R-08-019e already admits recomputation and changes to the committed occupancy limit. The research contribution is a checked transformation and a useful frontier of bytes, cycles, bandwidth, code size, and energy. Repeatedly streaming weights from another machine changes the resident-inference contract; it is not an uncharged version of local recomputation. Reducing an occupancy promise or evicting state is a service change, reported separately from an equivalent implementation's capacity gain.

### Bounded pieces instead of mandatory contiguity

**Very recent theoretical lead.** Bender et al.'s August 2026 submission studies *request fragmentation*, meaning deliberately splitting an allocation into pieces. For constant aggregate factor `k > 1`, it reports an optimal online ratio `Theta(log log Mbar)` when the actual peak live volume is unknown and bounded above by `Mbar`. The budget compares all-time peak simultaneous fragments with all-time peak simultaneous requests. A fixed small segment limit per object is a different model and does not inherit that result; knowing the actual peak volume also changes the bounds. This is an in-submission preprint about online allocation, not a theorem for fixed offline slots. [*Tight Bounds for Memory Allocation With and Without Request Fragmentation*, v1](https://arxiv.org/abs/2608.28462v1)

The plausible local experiment is narrower: compile selected arrays, queues, or object collections into a bounded set of fixed chunks within one owner. Each chunk has its own valid capability and declared slot; no page-table translation is necessary. Bound descriptor count, tail slack, indexing, tag traffic, revocation, and DMA/vector access costs. A contiguous external ABI can force copying and erase the saving. Allowing the runtime to choose arbitrary chunks from a shared free set would add online placement and needs a separate architecture decision. The paper motivates exploring representation freedom; it supplies neither this implementation nor its proof.

### Reclamation as a capacity scheduling problem

**Existing mechanism, open composed cost.** CHERIoT's documented heap quarantine illustrates why logical deallocation and physical reuse differ. Its allocator and revoker are not implementations of this repository's software sweep and fixed schedule. Here the controlling obligations are [containment and reuse](../spec.md#r-08-007a), [bounded sweep service](../spec.md#r-08-007), and [the unmeasured teardown rate](../spec.md#r-08-008a). [CHERIoT memory guide](https://cheriot.org/book/memory.html)

A research model can describe release arrivals by a worst-case envelope `alpha(T)`, the maximum charged physical extents entering release-to-reuse in any interval of length `T`, including slot padding. If every release becomes reusable within a proved bound `T_reuse`, unreusable released storage is bounded by `alpha(T_reuse)` after the initial backlog clears, with a declared order for events at the same timestamp. Count Quiescing retention before containment as well as quarantine after it. Derive `T_reuse` from containment, outstanding authority, complete sweep coverage, and initialization service; do not substitute an average free rate. Optimize sweep slots and reserved capacity together, accounting for their feedback and each pool's service guarantees. A faster sweep is not free memory if it removes bandwidth required by the admitted workload.

## Exploratory branches that change assumptions

| Branch | Potential benefit | Boundary and decisive experiment |
| --- | --- | --- |
| Public, predeclared phase overlays | Reuse the same addresses for different objects when the earlier phase is completely dead | Same-owner reuse with proved non-overlap is already available under R-08-018a. Extending it to new runtime modes or owners needs transition, residency and authority proofs; inactivity alone does not kill saved application state |
| Bounded handle-based relocation | Compact movable state without an MMU by resolving a stable typed handle through bounded software metadata | R-08-020 forbids runtime relocation. Measure metadata, copy workspace and worst-case pause, and account for every direct capability, interior pointer, saved register, sentry and device loan; a handle indirection alone does not revoke escaped pointers |
| Cross-owner capacity lending | Use slack where another owner needs it | R-08-012c and R-08-047 forbid moving island boundaries and borrowing. Prove a new ownership transition, reserve return capacity, and specify whether denial or timing reveals the lender's private demand |
| Runtime value deduplication or compression | Recover capacity that static contents and occupancy analysis cannot predict | R-08-019a names this residue. Charge equality checks, labels, dictionaries, expansion reserves and worst-case decode; cross-owner equality and success can disclose data |
| Recomposition at reboot | Redistribute reservations for a different installed workload | Fits the generation model; quantify downtime and migration workspace. It cannot rescue the current generation's full pool during execution |

The phase experiments concern data. [Executable overlays](architectural-alternatives.md#static-code-overlays-a-deterministic-instruction-scratchpad-deferred-until-a-measured-resident-image-fails-the-capacity-budget) have their own deferral under R-15-100b and reopen loader and executable-memory obligations. Likewise, the existing [compression and deduplication disposition](architectural-alternatives.md#transparent-variable-rate-memory-compression-and-runtime-deduplication-declined) governs that table's exploratory branch; naming its potential gain does not admit it.

Two outside comparators sharpen the boundary. Mesh uses virtual-memory operations to compact physical backing while preserving C/C++ addresses, so importing its central mechanism would undo the no-MMU choice. Recent reallocation theory studies space and expected normalized movement cost with live-object relocation allowed; that does not establish a worst-case pause for a fixed-slot machine. [Powers et al., *Mesh*, PLDI 2019](https://people.cs.umass.edu/~mcgregor/papers/19-pldi.pdf), [Farach-Colton et al., *A Nearly Quadratic Improvement for Memory Reallocation*, SPAA 2024](https://arxiv.org/abs/2405.12152)

The absence of an MMU is not the reason every movable design fails. Software handles, copying, and typed reconstruction are possible design choices. They add runtime work and authority transitions which the present design excludes. Study their cost explicitly if the offline approaches leave a demonstrated capacity failure.

## Open questions and falsifiable hypotheses

**A lower bound to keep honest.** Suppose `n` owners each require an unconditional reservation of `B` bytes, reservations cannot move between owners, and any owner may be selected to run. Each owner still needs its own `B` even if an external service rule permits only one active owner at once. Total reservation is at least `n * B`, whereas that rule's peak active payload is `B`. This is an elementary consequence of those premises, not an open conjecture. Fixed public phases with reusable ownership, weaker service guarantees, or runtime transfer change a premise. An optimizer cannot remove this cost while claiming all premises unchanged.

**Hypothesis: restricted lifetime structure can make exact planning practical.** Start with positive integer object sizes and lifetime endpoints encoded in binary, one arena, unit alignment, every nonnegative integer base legal, and no pinning. Let `k` be the minimum number of intervals whose removal makes the actual lifetime family laminar. Can exact placement be solved in time `f(k) * poly(input length)`, without dependence polynomial in the numerical address-space size, or is it hard even for a small fixed `k`? This is a proposed parameterized-complexity question. Small enumerations can expose counterexamples to candidate decompositions; they cannot establish the complexity claim. Non-unit alignment, restricted positions, owner and bank constraints need separately stated variants and input encodings.

**Hypothesis: bounded segmentation buys useful capacity after its costs.** For at least one representative service with variable-sized state, an equivalent implementation using a composition-fixed segment limit admits a strictly larger demand envelope at the same physical capacity and no worse admitted deadlines than its contiguous baseline. Falsify the hypothesis for the selected workload if descriptors, padding, copy staging, code growth or bank traffic consume the improvement. This is an empirical claim about an identified service, not a universal approximation theorem.

**Open proof problem: compositional reuse under public phases.** Can per-component phase certificates establish global non-overlap and bounded reuse without enumerating every combination of component states? A useful theorem would compose fixed phase schedules with asynchronous completion, retained state, and the complete authority-revocation barrier. A counterexample in which a late device completion crosses a reuse boundary refutes a proposed rule. Secret-dependent phase selection additionally needs an explicit leakage model; public labels alone do not prove non-interference.

**Open tradeoff: useful slack versus private demand.** State a relational model in which a borrower's acceptance and completion time are observations, while another owner's occupancy is secret. Compare identical borrower requests under different lender demand. A lending policy whose observed result differs violates that model. Determine the minimal reserved headroom, padding, public release rule or deliberate declassification needed for useful sharing. No universal impossibility result is asserted here: the answer depends on which service guarantees and observations are required.

**Hypothesis: reclamation-aware scheduling outperforms placement alone.** On a bursty but bounded service, jointly choosing retirement phases, sweep slots and quarantine reservation admits more useful state than optimizing placement with reclamation costs fixed, at unchanged external service guarantees. Refute it on that workload if the required sweep traffic or worst-case arrival envelope removes the gain. A result showing that quarantine dominates packing is valuable even when no transformation wins.

## Research todo list

This backlog tracks a research project, not an additional implementation schedule. Work selected for execution is scoped in the [implementation checklist](../implementation/implementation-checklist.md); Q5 owns placement comparisons, Q4 inference demand, Q6 memory topology, Q8 measured bottlenecks, Q22 assurance boundaries, and Q10 the product judgment. The research reuses those artifacts and returns findings to their owners. Research outputs do not confer implementation landing credit or accept a new requirement.

The [replayable first experiments](../implementation/static-memory-experiments.md)
provide a mathematical baseline, synthetic corpus, diagnostic ledger and bounded
placement comparison. The unchecked items below retain their full acceptance
conditions: a witness implementation advances an item without completing its
product, proof or generality obligations.

- [ ] **Define the mathematical and operational baseline.** Produce a reviewed model of payload liveness, retained authority, safe reuse, legal placement, and per-arena physical charge. Reconcile R-08-011 through R-08-013 with the exact theorem assumptions and the placement-search quantities. Deliver a proof or minimal counterexample for each disputed implication before optimizing it.
  Current output: the [baseline](../implementation/static-memory-baseline.md) states the model, laminar argument, assumption-breaking witnesses and proposed requirement dispositions. The admitted-language bridge and normative reconciliation remain open.
- [ ] **Build a reproducible capacity corpus.** Start from Q5's exporter and the real composed roster when available. Include bounded parsers, sessions, rings, saved application state, frame pipelines and inference, plus synthetic crossing lifetimes, adversarial sizes, burst teardown and delayed device completion. Record source revision, manifest, all cost assumptions and demand envelope. Keep witness demonstrations labeled as such.
  Current output: the [corpus and Q5 bridge](../implementation/static-memory-corpus.md) emit identified synthetic contracts and report absent source fields. A real roster remains required.
- [ ] **Implement a diagnostic byte ledger.** For each owner, arena and admitted mode, report useful payload, reserved span, disjoint overhead charges, occupancy, unreusable retired bytes, largest legally usable extent and typed refusals. Preserve telemetry labels. Derive every figure from artifacts; measure equivalent service and alternative service contracts separately.
  Current output: the [event ledger](../implementation/static-memory-corpus.md) partitions bytes and diagnoses bounded requests under explicit witness premises. Target telemetry and compiled-service cost extraction remain open.
- [ ] **Establish exact small-instance oracles.** Exhaustively enumerate small layouts and use independently checked lower bounds to separate unavoidable fragmentation from planner error. Mutate lifetimes, alignment, owner assignment, slot overlap and reuse barriers; invalid candidates must fail. A feasible certificate and an optimality certificate are different deliverables.
  Current output: the [bounded exact oracle and independent replay](../implementation/static-memory-experiments.md) cover the declared finite integer model. Full CHERI placement constraints and semantic reuse evidence remain outside that model.
- [ ] **Scale offline planning.** Benchmark deterministic heuristics and coupled search against the existing enumeration and exact oracles. Report best feasible span, proved lower bound, remaining gap, build time and reproducibility. Preserve the standing plan on timeout or failure to find improvement. Introduce and license-review dependencies only when that comparison justifies them.
  Current output: the [comparison command](../implementation/static-memory-experiments.md) records deterministic heuristic and exact-search results on the witnesses. Large-instance and actual-roster comparisons remain open.
- [ ] **Prototype lifetime and representation transformations.** Compare lexical regions, explicit bounded phases and selected non-lexical release; compile one service both contiguously and into fixed bounded chunks. Prove result equivalence and account for aliases, capability narrowing, descriptors, vectorization and DMA staging. Record whether each gain is due to less live data or better placement.
- [ ] **Explore the bytes-versus-work frontier.** Generate static rematerialization, tiling and fusion variants. Derive worst-case execution and traffic from the emitted code, including zeroization and code-size growth. A candidate closes only if the same service fits its original deadlines, memory classes, power constraints and admitted image.
- [ ] **Co-design reclamation and capacity.** Derive worst-case retirement envelopes and complete release-to-reuse bounds. Exercise saved-register retention, grant loans, stalled endpoints, restart storms and stale capabilities behind the sweep cursor. Compare quarantine bytes and service availability across fixed sweep schedules, using Q22's boundary obligations.
  Current output: the [baseline's reuse analysis](../implementation/static-memory-baseline.md) states the envelope premises and links the existing Q22 barrier evidence; the corpus exposes retention charges. Qualified service rates and the joint scheduling experiment remain open.
- [ ] **Prove or refute the structural questions.** Formalize the laminar special case and the restricted-lifetime parameterization, then characterize which added constraints break them. Publish negative results and minimal witnesses as first-class outputs. A mechanized feasibility check does not close the algorithmic optimality problem.
  Current output: the [baseline](../implementation/static-memory-baseline.md) supplies the elementary laminar proof and separates it from the open parameterized-complexity question.
- [ ] **Isolate one architecture experiment if justified.** Select public phase reuse, typed relocation, or capacity lending only after baseline measurements show the limitation it addresses. Keep an explicit changed-assumption ledger and prove the transition's authority, timing and information-flow claims. Reject a candidate with an unbounded pause, hidden reserve, or unreconciled exclusion.
- [ ] **Run a composition-level comparison.** Feed promising variants into Q5b and the product gate on the same roster and functional contract. Report which additional workload is admitted, all resource deltas, exhaustion behavior and any weakened promise. Perform ablations so packing, lifetime changes, segmentation and reclamation do not each claim the same recovered bytes.
- [ ] **Publish a reproducible research artifact and disposition.** Release definitions, proofs, generators, minimized counterexamples, checker inputs, search settings and replayable measurements. Identify peer-reviewed results, preprints, new conjectures and measured outcomes separately. Propose register changes only with the precise theorem or measured contract that replaces the current claim; an inconclusive experiment remains open.
  Current output: [local replay instructions and dispositions](../implementation/static-memory-experiments.md) bind source identities and inputs. External publication, mechanized proof and a measured product comparison remain open.

A credible project combines programming-language semantics, algorithms, real-time systems, capability security, and compiler engineering. Its success criterion is a checked increase in useful admitted work with the costs exposed. A proof that a particular reservation is unavoidable, or that a tempting optimization breaks isolation, is also a substantive result.
