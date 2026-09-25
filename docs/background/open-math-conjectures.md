# Open mathematical problems and recent advances relevant to VerifiedOS

> Non-normative research survey. Sources checked on 24 September 2026. The [requirements register](../requirements-register.md) remains authoritative. This survey admits no new axiom or implementation decision and supplies no evidence that a platform guarantee has been established. Existing declared cryptographic premises retain their current status.

The strongest connections are to memory placement, scheduling, proof production, computational security, and arithmetic kernels. Some resolutions could improve an algorithm; others would establish limits or invalidate a security assumption. A proof of existence need not provide a usable construction, and a faster asymptotic algorithm need not be faster at this machine's sizes.

There is no exhaustive, stable list of **all** open mathematics that could affect a general-purpose computer. This survey covers named conjectures and concrete unresolved questions for which a causal connection to the present design can be stated. It includes open complexity classifications and cryptographic hypotheses, explicitly labeled because they are not all conjectures in the same sense. It also covers [recent solutions and advances](#recent-solutions-and-advances-worth-evaluating), including results that offer something useful before a broader conjecture is settled. Project-specific research questions appear separately. Famous problems without an identified consumer are excluded rather than assigned an invented benefit.

The mathematical statements and status come from the linked sources. **The proposed VerifiedOS applications are this survey's inferences**, unless an existing project contract already states the connection. Recent preprints are identified as such; finding a claimed proof is not the same as establishing its acceptance or checking it in the project's prover.

The status review includes recent manuscripts, their revisions, and public GitHub proof and implementation repositories. Repository age, popularity, author affiliation and AI assistance do not decide mathematical validity. A new repository can supply a decisive counterexample or a complete proof before journal review. Its evidence must still match the original statement: inspect definitions, quantifiers, assumptions, imported dependencies and the computational model, then distinguish source inspection, supplied build or kernel records, independent reproduction and external mathematical review. A declaration named after a conjecture, an empty placeholder type, or a clean search for `sorry` does not establish that correspondence. The artifact notes below identify what was actually inspected; this review did not rerun external Lean proof packages.

## How the connections fit this machine

| Project surface | Mathematical opportunity | Boundary that still applies |
| --- | --- | --- |
| [Fixed memory placement](../implementation/placement-search.md#8-research-handoff-for-future-placement-proofs) and [portable planner](../implementation/portable-memory-planner.md) | Tighter packing, smaller search, stronger lower bounds | Fixed backing, exact capability bounds, alignment, islands, safe-reuse lifetimes and independently checked candidates |
| [Elastic domain](../implementation/contracts/elastic-domain.md#research-handoff-for-movable-storage) | Better resource assignments and bounded allocation policies | Composition-fixed envelope, quarantine and revocation costs, permitted in-label contention |
| [Phase service](../implementation/phase-service/prerequisite-contract.md#schedule-and-resource-extraction) and [schedule synthesis](../implementation/contracts/schedule-record.md#research-handoff-for-schedule-synthesis) | Shorter schedules and smaller intermediate buffers | WCET, dependencies, nonpreemption, communication slots and confidentiality boundaries |
| [Proof producers](../assurance/proof-assistance.md#research-handoff-for-future-proof-producers) and [CIC qualification](../assurance/cic-checker-qualification.md#research-boundary-for-certificate-and-checker-cost) | Faster proof search, smaller certificates and tractable restricted verification | Frozen claims, exact assumptions, kernel checking and non-vacuity review |
| [Resident passes](../performance/toolchain-residency.md#research-leads-for-bounded-resident-passes) and [service indexes](../implementation/contracts/service-authoring.md#research-handoff-for-the-future-index-implementation) | Parallel graph algorithms, recomputation, compact dictionaries and private catalytic workspace | Result equivalence, finite backing, exact restoration, bounded activations and service semantics |
| [Wasm execution](../implementation/contracts/wasm-execution.md#mathematical-research-handoff) | Better guest algorithms, preparation, representations and arithmetic | Pure interpretation, bounded native phases, no JIT, no new performance-only trusted checker |
| [Cryptographic premises](../assurance/proof-reuse/crypto.md#research-handoff-for-unfinished-security-proofs) and [entropy qualification](../hardware/trng-source-model-contract.md#research-handoff-for-alternative-extractors) | Stronger reductions, better finite parameters, explicit constructions | Concrete security games, attack budgets, source independence and physical qualification |
| [Coding proofs](../assurance/proof-reuse/hardware.md#research-handoff-for-future-code-and-decoder-proofs) and [communication proofs](../assurance/proof-reuse/protocols.md#research-handoff-for-future-communication-proofs) | Finite code certificates, smaller decoder scratch and topology-specific traffic comparisons | Actual channel and code family, total resident storage, decoded interface, fixed schedules and authenticated sessions |
| [Compute proofs](../implementation/contracts/compute-semantic.md#arithmetic-research-handoff) and [inference](../performance/inference-demand.md#research-handoff-to-unwritten-inference-proofs) | Fewer arithmetic operations, transfers and resident intermediates | Exact or explicitly permitted numerical semantics, fixed traffic budgets and measured target costs |
| [Field/code parameter generation](../implementation/fiat-crypto-emission.md#research-handoff-for-future-field-and-code-parameters) and [finite rotations](../performance/bonsai2-assessment.md#finite-rotation-proof-handoff) | Checked algebraic witnesses for selected constants and transforms | Finite representation and certificates, construction costs and executable arithmetic correspondence |

The [static-memory research agenda](static-memory-research.md) already separates live payload, legal address span, stranded reservations and reclamation overhead. That distinction governs every allocation entry below. A better placement does not shorten an object's lifetime or remove a quarantined capability. Likewise, an amortized data-structure theorem does not establish a per-slot deadline.

## Allocation, fragmentation and scheduling

### Dynamic Storage Allocation below a factor of two

**Open approximation problem; direct connection.** Given known object sizes and lifetime intervals, assign each object one fixed contiguous address interval. Objects whose lifetimes overlap must occupy disjoint addresses. Minimize the resulting address span. Can a polynomial-time algorithm achieve a worst-case approximation factor strictly below two for the unrestricted problem? Khan's [open-problem collection](https://www.csa.iisc.ac.in/~arindamkhan/FGA_OpenProblems.pdf) lists this frontier, with a known `2 + epsilon` guarantee; [Buchsbaum et al.](https://epubs.siam.org/doi/10.1137/S0097539703423941) establish the classical approximation and load analysis.

A constructive improvement could reduce the backing needed by the fixed-tier [memory plan](../spec.md#r-08-012). A hardness result would sharpen the reason to exploit structured lifetimes. Neither outcome says that optimal span equals peak live bytes. Alignment, CHERI representability, pinned locations, distinct memory classes and revocation may invalidate a direct transfer of the classical guarantee.

A related [August 2026 tree-scan preprint](https://arxiv.org/abs/2608.14471v1) bounds space by maximum live memory plus the largest buffer for constant-bounded programs, using defragmentation, and obtains optimality when in-place swapping is allowed. Moving objects and transforming execution distinguish that result from the fixed-address approximation question here.

### Modified Integer Round-Up Property for bin packing

**Named conjecture; conditional allocation connection.** Let `OPT` be the minimum number of unit-capacity bins and `LP` the optimum of the Gilmore-Gomory configuration relaxation for the same item multiset. The Modified Integer Round-Up Property, MIRUP, asserts `OPT <= ceil(LP) + 1`. The stricter assertion `OPT = ceil(LP)` is false. See the [bin-packing discrepancy paper](https://sites.math.washington.edu/~rothvoss/publications/BinPackingViaDiscrepancyOfPermutations-talg.pdf) and a [2026 temporal-bin-packing study](https://doi.org/10.1007/s10288-025-00602-1).

Related unresolved targets are a universal constant additive LP gap and an efficient algorithm returning at most `OPT + O(1)` bins. These are different assertions: an existence bound does not itself supply the algorithm. [Hoberg and Rothvoss](https://arxiv.org/abs/1503.08796) give a logarithmic additive guarantee.

Such results could tighten packing of equal-capacity banks or storage containers and estimates of unavoidable slack. Ordinary bin packing has no lifetimes or cross-bin contiguity requirement. It therefore does not directly solve [size-class waste](../spec.md#r-08-018b), elastic-heap fragmentation, or the full physical placement problem.

A [4 June 2026 revision](https://arxiv.org/abs/2604.05152v2) gives polynomial algorithms for the Augmented IRUP benchmark class and pseudopolynomial algorithms for Augmented Non-IRUP instances. Their scoped optimality guarantees make them preprocessing leads, without resolving MIRUP or the unrestricted constant-additive-gap target.

### Optimal copying overhead for memory reallocation

**Open tight-bound and implementation problems, with a major 2026 advance; direct fragmentation connection.** In `M` cells, maintain contiguous objects under insertions and deletions, with live volume at most `(1-epsilon)M` and relocation allowed. For an update of size `s`, charge `1 + moved_existing_volume/s`. [Jin's STOC 2026 result](https://arxiv.org/html/2602.15417v1) gives `O(log^4(1/epsilon) * (log log(1/epsilon))^2)` worst-case expected per-update overhead against an oblivious adversary. The general lower bound is `Omega(log(1/epsilon))`; closing that gap and obtaining a time-efficient implementation remain open. The same paper rules out the corresponding blanket high-probability subpolynomial-overhead hope. Moved volume is not computation time.

This sharpens the fragmentation-versus-copying tradeoff for explicitly movable application storage. It does not alter the fixed tier's static backing. Native CHERI capabilities and guest Wasm offsets do not update themselves when bytes move: an application needs a proved relocation or indirection discipline, authorized reference updates, revocation accounting, intermediate space and bounded yield behavior. Expected costs do not establish a deadline, and an oblivious-adversary analysis does not cover arbitrary adaptive requests. Any experiment belongs within the [elastic envelope](../implementation/contracts/elastic-domain.md) and its existing authority rules.

### Strong, or prefix, Komlós conjecture

**Constant-bound conjecture refuted in a September 2026 manuscript; optimal growth remains open.** The conjecture asked whether every fixed ordered sequence of vectors of Euclidean norm at most one admits signs making every prefix's maximum-coordinate magnitude universally bounded, even when the signs can use the entire sequence. [Kintali's 15 September manuscript](https://shivakintali.github.io/papers/StrongKomlos.pdf) constructs square `n` by `n` examples requiring `Omega(sqrt(log log n))` prefix discrepancy. [Karingula and Lovett's 22 September revision](https://arxiv.org/html/2609.20979v2) incorporates this refutation and contrasts it with the dimension-independent `O(sqrt(log n))` upper bound. The remaining question is the optimal growth between these bounds, not whether a universal constant exists. No independent mechanization of the lower bound was located in this review.

If a composition's legal binary assignments admit this vector model, constructive bounds could constrain accumulated resource imbalance at every phase and inform [buffer reservations](../spec.md#r-08-046). The refutation rules out a universal constant for unrestricted instances; structured workloads may still allow one. It is not an online dispatch theorem: signs, nonnegative inventory, precedence and per-coordinate capacities all need a faithful interpretation.

The local [resource-credit proof contract](../implementation/static-memory/resource-contracts.md#prefix-and-sequential-composition-proof-contract) applies the distinction between final balance and intermediate demand to the existing finite take/return semantics. Its extension characterizes success at every prefix and composes sequential requirements exactly, with balanced traces of equal totals but different peaks as witnesses. This does not formalize the Komlós result or infer permission to reorder operations.

### Efficient constant-discrepancy Komlós construction

**Polynomial-time construction announced in the real-RAM model; finite-arithmetic implementation remains separate.** Ordinary Komlós controls the final signed sum. Following the September existence proofs, [Guo, Fang and Lu's 20 September preprint](https://arxiv.org/html/2609.23540v1) gives a deterministic constant-discrepancy signing algorithm using `O((m*n^9 + n^10) log(2+m+n))` exact arithmetic operations and comparisons for `n` vectors in `R^m`. This is a unit-cost real-RAM result, also yielding an `O(sqrt(t))` Beck-Fiala construction. The authors credit Odin AI assistance and describe their revision and verification of the proofs. The elementary proof's own finite rational construction is not the frontier for algorithmic existence.

This makes multidimensional balancing a stronger lead for the [offline composer](../implementation/placement-search.md). A reduction from actual legal assignments, bit complexity and precision, finite constants, and a checked implementation still need to be established. A unit-cost real-RAM theorem alone does not supply polynomial bit complexity or a feasible memory layout. The [formal existence artifact](#ordinary-komlós-and-beck-fiala-proof-announcements) also does not certify the follow-on algorithm's running time.

### Euclidean Steinitz conjecture

**Named conjecture; conditional buffer connection.** Given vectors of Euclidean norm at most one whose total is zero in `R^d`, is there a permutation for which every partial sum has norm `O(sqrt(d))`, with a universal constant? The general assertion remains open in [2026 work on Steinitz constants](https://londmathsoc.onlinelibrary.wiley.com/doi/10.1112/mtk.70085). [Dutta, Jha and Jiang's April 2026 preprint](https://arxiv.org/abs/2604.13355v1) gives an efficient `O(sqrt(d))` construction for `n` vectors when `d >= Omega(log^7 n)`. This leaves the dimension-unrestricted question open.

Production and consumption operations can sometimes be modeled as signed resource vectors. A suitable ordering could reduce temporary inventories in [joint scheduling and memory planning](static-memory-research.md#certified-offline-placement-and-joint-scheduling). An arbitrary permutation is not necessarily executable: dependencies may prohibit it or it may consume unavailable data. The result would require a legal ordering, a baseline inventory, and translation of the norm bound into the exact capacities charged by admission.

### Three identical processors with unit jobs and precedence

**Open complexity classification; conditional static-scheduling connection.** For unit-duration jobs with arbitrary precedence constraints on exactly three identical processors, is minimum makespan computable in polynomial time, or is its decision version NP-hard? This is the classical `P3 | prec, p_j=1 | C_max` problem. [Nederlof, Swennenhuis and Węgrzycki](https://arxiv.org/abs/2312.03495), published in [ACM TALG in 2026](https://doi.org/10.1145/3785365), make subexponential progress without closing the classification.

An efficient exact algorithm could improve [static schedules](../spec.md#r-07-013) for a matching restricted reaction graph; hardness would clarify scaling limits. Real workloads add varying WCET, communication, labels and recurring deadlines. Arbitrarily splitting a job into unit pieces would introduce preemption or migration that the original service may not permit.

### Unrelated-machine makespan approximation

**Open approximation problem; conditional heterogeneous-core connection.** Each job has a processing time `p_ij` on machine `i`; assign each job to one machine to minimize the greatest total assigned processing time. The general polynomial-time approximation frontier has a factor-two algorithm and hardness below `3/2`. Improving the general factor-two guarantee and identifying the optimal threshold remain unresolved; see [the 2025 scheduling study](https://ora.ox.ac.uk/objects/uuid%3A0e0229d0-ca8a-473f-955d-a75a5ebaae66/files/r3b591b19x) and [2026 work](https://arxiv.org/html/2606.13133v1).

This resembles assigning compatible work to [scalar, vector and matrix cores](../implementation/compute-compatibility.md), so progress could reduce the most heavily loaded core or required core count. Fixed-machine-count special cases already have stronger algorithms. Neither the general ratio nor a prediction-assisted result covers the platform's full dependency, slot, label and fabric constraints.

### Pinwheel scheduling certificates and complexity

**Open complexity questions; conditional repetitive-service connection.** Task `i` needs one unit of service in every `a_i` consecutive slots, forever, on one server. Does every feasible instance have a polynomial-size certificate checkable in polynomial time, placing feasibility in NP? Is general feasibility PSPACE-complete? [ICALP 2026 research](https://drops.dagstuhl.de/storage/00lipics/lipics-vol374-icalp2026/html/LIPIcs.ICALP.2026.122/LIPIcs.ICALP.2026.122.html) identifies these unresolved questions. A periodic schedule can exist without an explicitly written period having polynomial length.

Compact certificates could help express maintenance or replenishment cadences without enormous schedule tables. This model omits WCET variation and the complete [schedule contract](../implementation/contracts/schedule-record.md). [Kobayashi, Lin and Swernofsky's 17 September preprint](https://arxiv.org/abs/2609.20075v1) strengthens the hardness frontier: dense instances with `sum_i 1/a_i = 1` are NP-complete even for unary periods and explicitly listed repeated tasks. Hence general feasibility is strongly NP-hard. NP membership for the dense restriction does not establish NP membership for general feasibility; its certificate-size and PSPACE-completeness questions remain open.

### Small Set Expansion conjecture

**Hardness conjecture; direct connection to limits on memory optimization.** Roughly, for arbitrarily small fixed error there is a sufficiently small fixed set-size fraction for which it is NP-hard to distinguish a regular graph containing a set of that size with almost no escaping edges from one where every set of that size has almost all edges escaping. [Raghavendra, Steurer and Tulsiani](https://arxiv.org/abs/1011.2586) state the formal hypothesis and its relation to Unique Games.

Assuming it, [Austrin, Pitassi and Wu](https://arxiv.org/abs/1109.4910) derive constant-factor inapproximability for several layout problems and one-shot pebbling, where intermediates must be retained until their consumers run and recomputation is forbidden. This is a concrete barrier relevant to [lifetime and execution-order optimization](static-memory-research.md). It motivates restricted graph families and checked instance-specific search. It says neither that all real workloads are hard nor that ordinary fixed-lifetime contiguous placement has exactly the same lower bound. Disproving the conjecture alone would not provide a better planner.

### Strongly polynomial linear programming

**Open algorithmic problem, associated with Smale's ninth problem; direct offline-optimization connection.** Can every rational linear program with `m` constraints and `n` variables be solved using `poly(m,n)` arithmetic operations, independent of coefficient bit lengths, while all intermediate numbers have polynomially bounded encoding size? Ordinary polynomial-time solvability is already established. [Dadush et al.'s STACS 2025 account](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.STACS.2025.2) states the general frontier and the solved case with at most two nonzero entries per row or column.

Such an algorithm could improve predictable search budgets for packing relaxations, resource assignments and lower-bound certificates used by the [planner](../implementation/portable-memory-planner.md). It would not make arbitrary integer placement strongly polynomial or eliminate rounding gaps. Bit operations, finite arithmetic and target memory still cost resources. [Natura's February 2026 preprint](https://arxiv.org/abs/2602.06958) proves short monotone circuit walks through polyhedra; finding them within the required algorithmic bound remains open. A [separate claimed general solution](https://arxiv.org/abs/2503.12041) is not treated here as an established resolution; the distinction is between a proof announcement and an accepted algorithmic theorem.

### List Edge-Coloring Conjecture

**Named conjecture; conditional flexibility in static slot assignment.** Is the list chromatic index of every loopless multigraph equal to its ordinary chromatic index? If `k` colors suffice with a common palette, the conjecture says that giving each edge any list of `k` permitted colors still suffices. A [June 2026 survey](https://arxiv.org/abs/2606.31702) discusses the open general case and known cases such as bipartite graphs; [Jafari's 16 September revision](https://arxiv.org/abs/2608.22895v2) proves the stronger online form for `K_(p-1)` and `K_(2p)` for odd primes `p`, plus specified matching-deletion families. It does not settle arbitrary loopless multigraphs.

For unit transfers whose conflicts are exactly shared endpoints, edges can represent transfers and colors can represent time slots. Lists express allowed slots, so a constructive resolution could support more flexible [static schedule synthesis](../implementation/contracts/schedule-record.md). Routed fabric conflicts, unequal durations, precedence and additional shared resources do not automatically fit this graph. A bipartite endpoint model already has a theorem and need not await the general conjecture. The related ordinary edge-coloring bound is now a [published result](#goldberg-seymour-and-the-number-of-transfer-rounds).

## Proofs, verification and compilation

### P versus NP

**Foundational conjecture, usually stated `P != NP`; direct connection.** Can every decision problem with polynomial-size, polynomial-time-checkable witnesses also be decided in deterministic polynomial time? [Clay's official problem page](https://www.claymath.org/millennium/p-vs-np/) continues to list it as unsolved.

A constructive equality could transform exact finite packing, schedule synthesis, bounded superoptimization and proof search with an explicit polynomial witness bound. A separation would establish worst-case limits. Input encoding matters: a numerically enormous schedule is not a short certificate merely because its duration has few binary digits. Polynomial algorithms can also have unusable constants or exponents.

Neither answer decides unrestricted termination, arbitrary program equivalence or every theorem. `P != NP` is not a proof of cryptographic one-wayness; `P = NP` would defeat the usual asymptotic one-way-function definition. The [resident toolchain](../spec.md#r-13-027) would still produce artifacts checked by existing admission mechanisms.

**Concrete proof-claim audit.** A [June 2026 preprint](https://arxiv.org/abs/2606.03194) claims a machine-verified equality, but its [Lean target at revision `3c9c90ed`](https://github.com/TiruArt/Pedigree-Polytopes-Lean4/blob/3c9c90ed2e38dd3a679891029c8e7622b5801988/MembershipProject/Core/N_PEqualsNP.lean) declares `P_equals_NP : Prop` without defining the standard classes, sets `An n := Unit`, and assumes bridges including `tardos_strongly_polynomial`, `membership_An_of_Pn` and `mi_objective_solves_stsp_ax`. Source inspection therefore does not establish the advertised theorem. These are statement and assumption gaps, independent of the author's identity or the repository's age; the proof package was not built here.

### NP versus coNP and short propositional proofs

**Foundational conjecture, usually stated `NP != coNP`; direct certificate connection.** Is there a sound, complete, polynomial-time-checkable propositional proof system in which every tautology has a proof polynomial in its formula length? Existence of such a polynomially bounded system is equivalent to `NP = coNP`, by [Cook and Reckhow](https://www.cs.toronto.edu/~sacook/homepage/cook_reckhow.pdf). Strong proof-size lower bounds remain a subject of [current research](https://eccc.weizmann.ac.il/report/2025/080/download/).

Equality could permit uniformly compact certificates for finite Boolean validity or unsatisfiability. It would not promise efficient discovery, a compact encoding of an entire physical system, or short proofs in this repository's particular logic. Inequality would mean that every such propositional system has hard families. This matters to proof artifact storage and checking budgets, while [the proof kernel](../assurance/cic-checker-qualification.md) remains responsible for each accepted claim.

[De Rezende et al., May 2026](https://eccc.weizmann.ac.il/report/2026/078/), prove superpolynomial lower bounds for tree-like semantic Frege with bounded line size and related bounded-degree threshold systems. Tree structure and line restrictions are essential: this is proof-system progress, not a lower bound covering every Cook-Reckhow system.

### A p-optimal propositional proof system

**Open existence question; conditional certificate-interface connection.** Does one Cook-Reckhow proof system polynomially simulate every other, with polynomial-time translations and bounds allowed to depend on the source system? [Egidy's 2026 paper](https://arxiv.org/abs/2602.02294) studies barriers around this unresolved question; [Krajíček](https://arxiv.org/abs/2104.04711) connects it to optimal proof search.

A constructive positive answer could inform a common representation for certificates from heterogeneous solvers. This is relative efficiency, not a promise that every theorem has a short proof. It is also not the weaker notion of an optimal system that only bounds translated proof length without requiring an efficient translation. The [portable proof workflow](../assurance/proof-assistance.md) would still need concrete reconstruction, assumption auditing and a qualified checker; the conjecture authorizes none of those changes by itself.

### P versus PSPACE

**Foundational conjecture, usually stated `P != PSPACE`; direct finite-state connection.** Can every problem decidable with polynomial working space also be decided in polynomial time? It remains unresolved. [Williams's 2025 time-to-space simulation](https://arxiv.org/html/2502.17779v1) is a major partial result, not an equality or separation of these classes.

Some reachability and temporal-verification problems over succinctly represented finite machines are PSPACE-complete: the state graph can be exponentially larger than its description. Equality could change the cost of exhaustive assurance for those models; separation would establish limits while leaving restricted methods useful. A finite deployed machine does not make its entire graph affordable to enumerate. Conversely, infinite-state undecidability should not be attributed to a fixed finite configuration. No general Turing-machine simulation supplies the target memory traffic, slowdown or WCET needed for this project's [assurance pipeline](../assurance/coverage-matrix.md).

### P versus uniform NC

**Foundational conjecture, usually stated `P != NC`; conditional parallelism connection.** Does every polynomial-time decision problem admit uniform polynomial-size circuits of polylogarithmic depth, equivalently a suitable highly parallel algorithm with polynomially many processors? See the [University of Illinois complexity lecture](https://www.cs.uic.edu/~block/courses/cs505-spring2025/lecture-18.html). The processor count and uniformity condition are essential.

A constructive equality could expand parallel compilation and analysis. A separation would establish that some efficient sequential computations resist this strong parallelization target. Neither predicts speedup on the finite number of cores and fixed communication grants of [this ensemble design](../spec.md#r-15-171a). Many useful restricted tasks are already parallelizable: [Ganardi and Lohrey](https://arxiv.org/html/2512.19060v1) distinguish efficient parallel register planning for explicit expression trees from harder succinct representations. Ordinary register planning need not wait for a resolution.

**June-July 2026 preprint advance.** [Chatterjee et al., revision 2](https://eccc.weizmann.ac.il/report/2026/100/revision/2/download/), give deterministic NC algorithms for bipartite matching, including finding a maximum-weight perfect matching for polynomially bounded edge weights, and extend weighted/search results to linear matroid intersection. This is a concrete lead for parallel offline assignments that reduce to these problems. Processor count, memory, field/weight representation and checking the resulting assignment still matter; the general `P = NC` question is unchanged.

### L versus NL: directed reachability in logarithmic workspace

**Open complexity question; direct verification-memory connection.** Can reachability between two vertices of an explicitly represented directed graph be decided deterministically with `O(log n)` writable workspace? This is equivalent to `L = NL`; read-only input storage is excluded from the space bound. [Jeffery and Pass, ICALP 2026](https://drops.dagstuhl.de/storage/00lipics/lipics-vol374-icalp2026/html/LIPIcs.ICALP.2026.117/LIPIcs.ICALP.2026.117.html), record the unresolved classical question. Undirected reachability already has a logarithmic-space algorithm.

A constructive answer could reduce scratch reservations for dependency analysis and graph-based checking in the [resident toolchain](../spec.md#r-13-027). It would not shrink an implicitly exponential state graph, remove input storage, or guarantee near-linear time. The cited paper's new quantum result is not an algorithm for this classical machine. The relevant target is a complete classical implementation with explicit time and memory bounds.

### The power of catalytic memory

**Open computational-model questions; direct allocation-flexibility connection.** A catalytic computation has clean scratch space plus writable storage initially holding an arbitrary string, which it must restore exactly on termination. `CL` allows `O(log n)` clean workspace and polynomially many catalytic bits. Does `CL = L`? Does every polynomial-time problem belong to `CL`? [Koucky's account](https://bulletin.eatcs.org/index.php/beatcs/article/download/400/380) and [Henzinger, Pyne and Ragavan's February 2026 paper](https://arxiv.org/html/2602.14320v1) discuss the unresolved power of this model.

This explores whether already occupied memory can help compute without losing its original information. It could reduce additional scratch reservations inside one owner's authorized, quiescent region. It does not reduce physical capacity charged to composition, authorize cross-label access, preserve concurrent reads, or guarantee restoration after faults or forced termination. Restoring raw bits also needs a separate proof for capability tags, initialization and typed-object invariants. [Recent explicit algorithms](#catalytic-graph-and-sequence-algorithms) make this more concrete than an existence question, while leaving those implementation obligations intact.

### Minimum Circuit Size Problem

**Open complexity classification; conditional synthesis connection.** Given the complete `2^n`-bit truth table of a Boolean function and a threshold `s`, is there a circuit of at most `s` gates computing it? MCSP is in NP, but membership in P and NP-hardness under standard polynomial-time reductions remain unresolved. [Hirahara and Ilango, FOCS 2025](https://www.rahulilango.com/papers/MCSP-Proceedings-2025.pdf), and [Goldberg, Juvekar and Kabanets, June 2026](https://eccc.weizmann.ac.il/report/2026/091/), establish conditional results rather than unconditional NP-completeness of ordinary MCSP.

Constructive progress could aid minimization of small finite Boolean kernels or candidate hardware circuits. The input is the entire truth table, so polynomial time here can still be exponential in the number of Boolean inputs. This is not a universal efficient optimizer for source programs or succinct RTL. Gate count also differs from delay, energy and proof cost; the [certifying compute path](../implementation/compute-compatibility.md) still needs semantic equivalence and target measurements.

### Derandomization: P equals BPP

**Named complexity conjecture; conditional toolchain connection.** Every bounded-error randomized polynomial-time decision procedure would have a deterministic polynomial-time counterpart. [Doron, Moshkovitz, Oh and Zuckerman's 2026 work](https://eccc.weizmann.ac.il/report/2026/082/) continues to study the hardness assumptions and overheads of such derandomization.

Useful constructions could remove random choices and probabilistic error from some offline search and analysis, helping reproducibility and deterministic resource accounting. They need not preserve the original runtime exponent. Untrusted randomized search can already be safe when its output is independently checked. Derandomization does not generate secret entropy, replace a physical entropy root, or establish constant-time handling of secrets. Its benefit belongs to the [composer and proof producer](../spec.md#r-13-001c), not to a relaxation of admission.

### Deterministic polynomial-time polynomial identity testing

**Open algorithmic problem; conditional rewrite-verification connection.** Given an arithmetic circuit over an appropriately represented field, decide whether the formal polynomial it computes is identically zero in deterministic polynomial time, with circuit, degree and field-operation costs specified. General derandomization remains open in [2026 PIT research](https://eccc.weizmann.ac.il/report/2026/076/download/).

This could improve exact algebraic simplification and validation of candidate [vector and matrix kernels](../implementation/compute-compatibility.md), reducing dependence on randomized fingerprints. It is narrower than all of `P = BPP`. Formal polynomial equality is not floating-point equivalence, equal trap order, equal memory effects, or equality of machine arithmetic with overflow. Any use in the certifying toolchain needs the actual semantics and the existing theorem-checking path.

The cited [Kaplan-Shpilka result](https://eccc.weizmann.ac.il/report/2026/076/) gives deterministic polynomial-time white-box and quasipolynomial-time black-box tests for non-multilinear read-4 formulas over characteristic zero or at least five. The formula and field restrictions identify a usable special case without resolving arbitrary-circuit PIT.

### Deterministic polynomial factorization over finite fields

**Open algorithmic problem; conditional algebraic-toolchain connection.** Given a dense degree-`d` polynomial over `F_q`, can its irreducible factors and multiplicities be computed deterministically in `poly(d,log q)` bit operations? Supply the field explicitly, for example as `F_p[t]/(h)` with binary-encoded prime `p` and an irreducible polynomial `h`; constructing that representation is a separate task. Efficient randomized algorithms exist. [Chatterjee, Harsha and Kumar's March 2026 revision](https://arxiv.org/abs/2511.05176) distinguishes the open general problem, even quadratics over varying prime fields, from the structured instances it solves for Reed-Solomon decoding.

Progress could make future field/code construction and exact algebraic preprocessing reproducible with stronger runtime bounds. This is a prospective connection to [arithmetic generation](../implementation/fiat-crypto-emission.md), not an identified bottleneck in the pinned primitives. GRH alone is not a known solution of the unrestricted factorization problem; [Ivanyos et al.](https://arxiv.org/abs/1205.5653) explain the remaining GRH-conditional frontier. Factorization of polynomials over finite fields is also distinct from factoring integers and from proving cryptographic hardness.

## Computational performance and Wasm workloads

These entries concern algorithmic work performed by applications, native services, or offline producers. They are not conjectures that every Wasm interpreter can match native execution. The [selected execution contract](../implementation/contracts/wasm-execution.md) already provides the place to study validated internal representations, fused handlers, bounded whole-loop operations and native-service calls, with effects, traps, authority and polling preserved.

### Exponential Time Hypothesis and Strong Exponential Time Hypothesis

**Related hardness hypotheses; direct limits on exact search.** ETH says that 3-SAT has no `2^o(n)`-time algorithm in its number of variables. SETH makes the stronger quantitative assertion that for every fixed improvement below base two, some fixed clause width prevents that improved exponential runtime for `k`-SAT. See the [original exponential-complexity research](https://www.sciencedirect.com/science/article/pii/S0022000000917276) and [SETH formulations and consequences](https://arxiv.org/abs/1112.2275). The deterministic or randomized algorithm model must be stated when using a consequence.

These hypotheses constrain some exact scheduling, packing and finite verification methods more sharply than `P != NP`; [2026 high-multiplicity bin-packing research](https://drops.dagstuhl.de/storage/00lipics/lipics-vol374-icalp2026/html/LIPIcs.ICALP.2026.116/LIPIcs.ICALP.2026.116.html) illustrates such a connection. A refutation could improve exponential search without proving `P = NP`. A transfer to the [memory planner](../implementation/portable-memory-planner.md) needs a reduction preserving the relevant size parameter, not just an NP-hardness label.

### Orthogonal Vectors conjecture

**Fine-grained hardness conjecture; conditional guest-workload connection.** For every `epsilon > 0`, there is a constant `c` for which finding an orthogonal pair between two sets of `n` Boolean vectors of dimension `c log n` has no `O(n^(2-epsilon))` algorithm in the stipulated computation model. [July 2026 research](https://arxiv.org/abs/2607.23799) proves restricted circuit and formula results, not the full conjecture.

It underlies barriers for certain exact similarity, string and attention problems. These can matter to inference and applications hosted in Wasm. Connections to [attention complexity](https://proceedings.iclr.cc/paper_files/paper/2026/hash/8a01099096c85890b1d1aff3c6b4ea56-Abstract-Conference.html) depend on dimension, approximation error, magnitudes and other parameters. A refutation would invalidate particular conditional lower bounds, not make every attention variant linear or remove the [resident model's memory traffic](../performance/inference-demand.md).

[May 2026 work on Online Orthogonal Vectors](https://arxiv.org/abs/2605.04798) gives deterministic data structures refuting a particular OnlineOV data-structure conjecture. Its preprocessing/query model is distinct from the standard offline conjecture stated here; that refutation must not be transferred without accounting for preprocessing and parameters.

### Weighted All-Pairs Shortest Paths hypothesis

**Fine-grained hardness hypothesis; conditional graph-analysis connection.** For every fixed positive `epsilon`, there is no `O(n^(3-epsilon))` algorithm for general weighted all-pairs shortest paths on `n` vertices in the stated model, commonly with polynomially bounded integer weights and distances well-defined. [Fischer's STOC 2026 work](https://arxiv.org/abs/2603.27736) studies conditional equivalences around this still-used hypothesis.

Progress could improve graph analyses or min-plus computations if profiling identifies those kernels in the composer or guest applications. This is not a demonstrated current bottleneck. Fast ordinary matrix multiplication does not automatically accelerate min-plus multiplication, and graph-analysis savings do not directly reduce interpreter dispatch overhead.

### Modern 3SUM conjecture

**Fine-grained hardness conjecture; conditional geometry and data-structure connection.** In a specified integer or real-number model, deciding whether three distinct input positions have values summing to zero is conjectured to require `n^(2-o(1))` time in the worst case. The modern claim excludes a fixed polynomial improvement, not every logarithmic improvement below quadratic. See [Dallant and Iacono's 2025 research](https://dipot.ulb.ac.be/dspace/bitstream/2013/398079/3/j47.pdf).

Consequences can constrain exact computational geometry and dynamic data structures used by desktop applications. A refutation could change those algorithm choices. A specific reduction is required before using it to bound [placement](../implementation/placement-search.md), graphics or Wasm performance; numerical representation and the machine model cannot be dropped from the claim.

[Kirkpatrick et al., February 2026](https://arxiv.org/abs/2602.11363v1), obtain simultaneous subquadratic query and storage bounds for the preprocessed-universe variant: about `n^(1.5+epsilon)` randomized query time and `n^(2-2*epsilon/3)` space, suppressing polylogarithms, after roughly quadratic preprocessing. That initial cost prevents an immediate refutation of ordinary 3SUM; reuse across many queries is the prospective application.

### Online Boolean matrix-vector multiplication conjecture

**Fine-grained hardness hypothesis; dynamic-workload connection.** Given an `n` by `n` Boolean matrix, receive `n` Boolean vectors sequentially and output each Boolean-semiring product before the next vector arrives. The OMv conjecture excludes total time `O(n^(3-epsilon))` for any constant positive `epsilon` in its stipulated randomized model. [Henzinger et al.](https://arxiv.org/abs/1511.06773) give the formulation; [current dynamic graph research](https://arxiv.org/abs/2403.02582) continues to use it for conditional bounds.

Its reductions constrain some incremental reachability and dynamic indexes relevant to applications and analysis tools. It highlights why a generation known at composition can admit optimizations unavailable to an application receiving unknown future updates. This concerns Boolean products and online response order, not arbitrary numerical matrix-vector inference. Preprocessing, total cost and per-operation latency must be kept distinct when applying it to [Wasm workloads](../implementation/contracts/wasm-execution.md).

A [February 2026 revision of the NeurIPS 2025 result](https://arxiv.org/abs/2502.21240v3) gives about `n^(2-1/d)` per-vector query time after roughly quadratic preprocessing for Boolean matrices of bounded VC-dimension `d`, suppressing polylogarithms. This is a structural opportunity for suitable dynamic graphs, not a general OMv refutation.

### Matrix multiplication exponent equals two

**Named conjecture; direct arithmetic-kernel connection.** The conjecture `omega = 2` means that, for every fixed `epsilon > 0`, square matrix multiplication in the applicable algebraic model has an `O(n^(2+epsilon))` arithmetic-operation algorithm. It does not assert a literal `O(n^2)` implementation. An [August 2026 preprint by Dupont et al.](https://arxiv.org/html/2608.16884v1) reports `omega < 2.371177`, using optimization assisted by AlphaEvolve. It describes exact-rational certification with directed logarithm bounds, but says verification code and candidate data are being prepared for release. This review did not locate that promised artifact; the preprint bound is not independently reproduced evidence and does not resolve `omega = 2`.

Practical constructions could improve dense inference, graphics and certified native kernels. Constants, scratch space, communication, rectangular shapes and numerical semantics still determine target value. Matrix-vector autoregressive decoding does not inherit the same benefit as large matrix-matrix multiplication. No operation-count theorem removes the cost of reading weights under the [fixed memory grants](../performance/inference-demand.md), or permits numerically different reassociation without an accepted semantic contract.

### Optimal bit complexity of integer multiplication

**Open lower-bound conjecture; arithmetic and proof-production connection.** Is multiplying two `n`-bit integers intrinsically an `Omega(n log n)`-time task in the multitape Turing-machine bit model? [Harvey and van der Hoeven](https://www.texmacs.org/joris/nlogn/nlogn.pdf) achieve the matching upper bound and explicitly distinguish it from the unproved lower bound. The upper bound was announced in 2019 and [published in 2021](https://annals.math.princeton.edu/2021/193-2/p04); it is not a newly solved 2026 problem.

A faster construction could improve sufficiently large exact arithmetic in proof producers, symbolic tools and guest libraries; a lower bound would establish an asymptotic limit. Neither determines the best fixed-width cryptographic multiplier or the practical crossover against simpler algorithms. Bit complexity differs from counting word multiplications, and secret-dependent arithmetic still needs the [cryptographic implementation's](../implementation/fiat-crypto-emission.md) timing and correctness evidence.

[Harvey and van der Hoeven, FOCS 2025](https://arxiv.org/abs/2503.22848), reduce binary matrix transposition to multiplication. A conjectured transposition lower bound would therefore imply the desired multiplication lower bound. This sharpens the conditional route to optimality without proving the lower bound itself.

### Dynamic optimality of binary search trees

**Named conjecture; conditional application data-structure connection.** Does splaying serve every access sequence within a universal constant factor of the best offline binary-search-tree execution in the same model, with the usual initial-state accounting? The broader existence question asks for any online BST with this guarantee. A [July 2026 preprint](https://arxiv.org/abs/2607.18498v1) gives `O(log log n * (log log log n)^2)` competitiveness for splay trees, leaving the constant-factor target open.

A proof would strengthen sequence-level efficiency guarantees for adaptive indexes or application maps. A counterexample would delimit the algorithm's universal claim. It would not establish bounded latency for each access: amortized and competitive guarantees can hide an expensive operation. Nor would it justify replacing the project's [storage index](../implementation/comparisons/storage-index.md), whose block traffic, persistence, recovery and endurance have different costs. The most plausible initial consumer is a bounded, in-label application data structure.

### Strong Descartes' Rule over finite fields

**Specialized proposed conjecture; conditional optimizer connection.** There are constants `0 < epsilon, delta < 1` such that, for sufficiently large primes `p,q` with `q` dividing `p-1`, a nonzero polynomial over `F_p` with at most `q^delta` nonzero terms and distinct exponents modulo `q` has at most `epsilon*q` roots in the order-`q` subgroup of the multiplicative group of `F_p`. [Li and Wu, ITCS 2026](https://drops.dagstuhl.de/storage/00lipics/lipics-vol362-itcs2026/html/LIPIcs.ITCS.2026.95/LIPIcs.ITCS.2026.95.html), pose this as Conjecture 9.

The conjecture would improve soundness bounds for randomized identity tests on restricted circuits with exponentiation, motivated by neural-network optimization. Such tests could filter candidate [compute rewrites](../implementation/compute-compatibility.md). They would not replace an exact admission theorem or establish equivalence of floating-point, quantized or effectful execution. This is a narrower research lead than general PIT, not an established platform optimization.

## Security, entropy and reliable communication

For these entries, a negative resolution may be more consequential than a performance gain. A verified implementation can correctly execute a cryptographically weak construction. The [cryptographic premise inventory](../assurance/proof-reuse/crypto.md) distinguishes mathematical reductions, concrete hardness assumptions, ideal-oracle models and attack-cost estimates; those categories remain separate here.

### Existence of one-way functions

**Foundational conjecture; direct assurance connection.** Does there exist a polynomial-time computable function family for which every probabilistic polynomial-time adversary has negligible probability of finding a preimage of the image of a uniformly sampled input? Classical and quantum-adversary formulations differ. See [Barak's public-key complexity survey](https://eccc.weizmann.ac.il/report/2017/065/download/) and [research on deriving one-wayness from NP problems](https://eprint.iacr.org/2021/513.pdf).

Existence would establish a foundation for general computational cryptography; nonexistence would undermine broad classes of encryption, signatures and pseudorandom generation. Neither outcome should be casually equated to a finite-cost attack on a deployed key size. Existence also would not prove this project's AES, hash or lattice choices secure. Worst-case `P != NP` is not known to imply the average-case hardness required here.

A [February 2026 preprint](https://arxiv.org/abs/2602.17651) derives one-way functions from nontrivial non-interactive zero-knowledge arguments, or constant-round public-coin zero-knowledge arguments, for NP under `NP` not contained in `ioP/poly`. The nontriviality condition allows an inverse-polynomial gap between the sum of completeness, soundness and zero-knowledge errors and one. This extends the permitted error range without establishing unconditional one-wayness.

[Nandakumar et al., RANDOM 2026, published 9 September](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.APPROX/RANDOM.2026.44), relate one-way functions to a separation between polynomial-time dimension and polynomial-time Kolmogorov-complexity rate over efficiently samplable infinite sequences. One-way functions imply an almost-sure uniform separation; the converse yields infinitely-often one-way functions. This connects another mathematical frontier without proving unconditional existence.

### Module Learning With Errors hardness

**Current computational assumption; direct, critical connection.** Over the specified polynomial quotient ring, distinguish `(A, A*s + e)` from `(A, u)`, where `A` is uniform, `s,e` follow the selected small-noise distributions and `u` is uniform. Search formulations instead seek the secret. Parameters, distribution and classical or quantum adversary access are part of the statement. [FIPS 203](https://csrc.nist.gov/pubs/fips/203/final) connects ML-KEM security to Module Learning With Errors.

This bears directly on the selected key establishment and its [qualification contract](../assurance/pq-reference-contract.md). Better attacks could require migration or larger parameters, with memory, bandwidth and crypto-slot costs. Stronger reductions could improve the justification of a margin. A reduction to worst-case lattice problems does not prove those problems hard.

**Status sensitivity:** a [2026 quantum-algorithm announcement](https://eprint.iacr.org/2026/1591) acknowledges correction and dispute; a [September-updated refutation](https://eprint.iacr.org/2026/1693) challenges its required advantage. This is not recorded as an accepted break, and rejecting an attack does not prove hardness. The existing [attack review](../assurance/proof-reuse/crypto.md#what-the-attack-corrections-establish) owns the project's disposition.

The refutation has an [AI-assisted Lean artifact at revision `6de8c1db`](https://github.com/sragavan99/lean-ePrint-2026-1591-refutation/tree/6de8c1dbffec10b4b44b2cae3aeadeb1cf0cfc83), with an exact `Q*sqrt(K/N)` distinguishing-advantage bound for its specified dihedral-coset algorithm model. This review inspected the documented theorem scope, including register and rounding conventions, but did not build or audit the complete dependency closure. It is concrete evidence to examine for that attack, not a proof of Module LWE hardness. Separately, [Wen and Zheng, CRYPTO 2026](https://eprint.iacr.org/2026/155), relate constant-rank search MLWE over power-of-two cyclotomic rings to structured extrapolated dihedral cosets; a reduction is not an efficient attack.

### Module SIS and SelfTargetMSIS hardness

**Current assumption family; direct signature connection.** Module Short Integer Solution asks for a nonzero short vector `z` with `A*z = 0 mod q` for a sampled module matrix. SelfTargetMSIS additionally couples the short-vector relation to a hash-derived challenge containing part of the sought solution. Norms, parameters and oracle access must match the security theorem. The [Dilithium specification](https://pq-crystals.org/dilithium/data/dilithium-specification-round3.pdf) distinguishes the assumptions; [FIPS 204](https://csrc.nist.gov/pubs/fips/204/final) specifies ML-DSA.

These assumptions affect generation signatures, attestation and replaceable boot stages. A break can defeat authenticity despite correct implementation. Tighter concrete reductions can improve justified parameter choices, but not automatically reduce costs. A [quantum reduction involving SelfTargetMSIS](https://arxiv.org/abs/2312.16619) already exists under stated conditions; the unresolved matter is hardness and the selected finite-parameter security claim, not the blanket existence of any reduction. See the [lattice premise ledger](../assurance/proof-reuse/crypto.md#lattice-conjectures-and-core-svp-estimates).

A candidate [ML-DSA Lean development at revision `1bda60f6`](https://github.com/Verified-zkEVM/VCVio/blob/1bda60f6e7048fb6f9338945b77b0a75d965068a/LatticeCrypto/MLDSA/Security.lean), dated 23 September, states an `euf_cma_security` reduction but ends its proof with `sorry`. This source inspection establishes that the named theorem is unfinished, not formal security evidence. Even a completed reduction would retain its hardness assumptions, parameters and oracle model.

### Classical elliptic-curve discrete logarithm and Diffie-Hellman hardness

**Current assumption family; direct classical-hedge connection.** For the selected group, discrete logarithm asks for `a` from `G,aG`; computational Diffie-Hellman asks for `abG` from `G,aG,bG`. These related problems are not interchangeable. Their unresolved hardness here is classical: [Shor's polynomial-time quantum algorithms](https://arxiv.org/abs/quant-ph/9508027) already remove the corresponding asymptotic quantum-hardness claim.

A fast classical attack would remove the classical component's contribution to hybrid key establishment. It need not defeat a correctly proved combiner whose other component remains secure. Improvements in security analysis or arithmetic could alter the cost and confidence of that hedge. The [project's assumption inventory](../assurance/proof-reuse/crypto.md) requires the exact group, game and combiner theorem. This is not an RSA dependency or a claim that a single generic group lower bound proves the selected curve secure.

A [July 2026 classical guess-and-determine proposal](https://arxiv.org/html/2607.09814v1#S5.SS1) leaves large-field success probability and total complexity unresolved, so it does not establish a break. [September quantum resource estimates for secp256k1](https://arxiv.org/abs/2609.05625) reach about 1,450 logical qubits and 40 million Toffoli gates under their model. [Jo and Lee, 14 September](https://eprint.iacr.org/2026/2014), separately announce an asymptotic quantum algorithm over an `n`-bit prime field using `5n/2 + o(n)` logical qubits and `O(n^2 polylog(n))` Toffoli gates. Its measurement-based uncomputation and hidden terms require their own finite resource assessment. These results sharpen the quantum threat assessment but are neither classical algorithms nor demonstrated attacks on deployed keys.

### Concrete AES pseudorandom-permutation security

**Concrete security assumption family; direct storage and session connection.** Can adversaries with specified resources and oracle access distinguish secret-key AES from a uniformly selected permutation with advantage above the claimed bound? This is a game-indexed quantitative question, not the assertion that AES is impossible to attack. [FIPS 197](https://csrc.nist.gov/pubs/fips/197/final) defines AES; the [GCM security analysis](https://eprint.iacr.org/2004/193.pdf) explains its role in composition.

The [AES-GCM premise dossier](../assurance/aes-gcm-premise-dossier.md) already identifies the unresolved AES-256 forward-PRP premise. Stronger concrete evidence could improve defensible rekeying and data-volume budgets; a suitable attack could invalidate confidentiality or authenticity claims. Correct AES code does not prove pseudorandomness, and stronger AES security does not remove nonce requirements or GCM's finite-message bounds.

**AI-assisted reduced-round advance, July 2026.** [Nasr and Carlini's cryptanalysis](https://anthropic.com/document/aes_mobius_bridge.pdf), [announced on 28 July](https://www.anthropic.com/research/discovering-cryptographic-weaknesses), improves single-key seven-round AES-128 attack work from about `2^99` to `2^89.3` through `2^91.4`, retaining `2^105` chosen plaintexts. An LLM discovered the central method. This is substantive cryptanalytic progress against seven of AES-128's ten rounds, not a full-round AES-128 or AES-256 break, and it does not discharge or invalidate the selected forward-PRP premise.

### Concrete SHA and Keccak security properties

**Concrete assumption family; direct and partly immutable connection.** Do the selected hashes provide the collision, preimage and second-preimage resistance each consumer needs? Do keyed constructions satisfy their particular PRF, MAC or DRBG games? These are distinct claims with explicit query and resource bounds. [FIPS 202](https://csrc.nist.gov/pubs/fips/202/final) defines SHA-3/SHAKE; [FIPS 205](https://csrc.nist.gov/pubs/fips/205/final) specifies the hash-based signature standard used by the boot design.

Consumers include content addressing, Merkle binding, measured boot, derivation and the ROM's signature verifier. New attacks can reach guarantees that software updates cannot repair in immutable hardware. Stronger constructions or reductions may improve justified signature, verification or randomness budgets. A proof in an ideal-permutation model does not prove concrete Keccak ideal. Fixed keyless hashing also needs careful adversary quantification, as [Rogaway explains](https://www.cs.ucdavis.edu/~rogaway/papers/ignorance.pdf); the [project ledger](../assurance/proof-reuse/crypto.md#idealized-models-and-keyless-hashing) records that boundary.

[Li et al.'s 9 September revision](https://eprint.iacr.org/2026/1120) announces collisions for 38-step SHA-256 at `2^104.3` work, 38-step SHA-512 at `2^125.4`, and 39-step SHA-512 at `2^178`, plus an explicit 36-step SHA-256 collision. These reduced-step results do not cover the standardized full functions. The [Keccak designers' cryptanalysis inventory](https://keccak.team/third_party.html) also records a practical five-round preimage attack on `Keccak[r=640,c=160]`; its round count and capacity differ from the selected SHA-3/SHAKE instances. Preserve those parameters when assessing any impact on the premise ledger.

A [GitHub schedule-compliance experiment](https://github.com/kodareef5/sha256-probe) illustrates another boundary: its `sr=59` claim uses 64 compression rounds with only 43 of the 48 message-schedule equations enforced. The [underlying report](https://stateofutopia.com/papers/2/we-broke-92-percent-of-sha-256.pdf) explicitly frees schedule words 57 through 61. This is an altered compression problem, not a standard SHA-256 collision or a 59-round attack with the prescribed schedule. The report was inspected; its experiments were not rerun.

### Public-key cryptography from arbitrary one-way functions

**Open foundational construction problem; speculative diversification connection.** Does existence of arbitrary one-way functions suffice to construct public-key encryption or secure key agreement? Known black-box barriers exclude broad generic approaches, not every possible non-black-box construction. See [Barak's survey](https://eccc.weizmann.ac.il/report/2017/065/download/) and [limits of random-oracle constructions](https://arxiv.org/abs/1205.3554).

A positive answer might diversify the assumptions available to future session protocols beyond today's structured lattice and classical choices. It promises neither small keys nor practical speed, and one-way functions would still be an assumption unless proved to exist. Any replacement would need concrete security, protocol composition, implementation refinement and the existing [admission and qualification path](../assurance/pq-reference-contract.md).

A neighboring [May 2026 secret-key private-information-retrieval result](https://eccc.weizmann.ac.il/report/2026/067/) uses arbitrary one-way functions and approximately square-root online communication. Its offline client secret-key processing is essential; it does not construct public-key encryption or key agreement from arbitrary one-way functions.

**AI-assisted barrier, August 2026.** [Li, Li, Li and Liu](https://arxiv.org/html/2608.03824v1) prove a query-complexity impossibility for perfectly complete key agreement with quantum local computation and classical communication in the Boolean-output quantum random-oracle model. For arbitrary finite rounds and independent initial private states, an eavesdropper recovers the key with certainty using `O((q_A+q_B)^5)` classical oracle queries. Computation is unbounded; pre-shared entanglement, correlated setup and quantum communication are excluded. The authors credit an AI-discovered argument that they checked and refined. Perfect completeness is essential. This strengthens a black-box barrier without resolving arbitrary non-black-box constructions or supplying an efficient attack on a deployed protocol.

### Explicit low-error two-source extraction

**Open construction frontier; direct entropy-root connection.** Obtain a deterministic polynomial-time extractor for two independent `n`-bit sources, each with polylogarithmic min-entropy, producing at least one output bit with negligible statistical error `n^(-omega(1))`. The entropy and error requirements must be met together; more output is a further target. [Chattopadhyay and Goodman](https://eccc.weizmann.ac.il/report/2025/075/download/) identify improving low-error two-source extraction as an outstanding challenge.

Better constructions could reduce raw samples, buffers and latency for a specified statistical guarantee in the [TRNG source contract](../hardware/trng-source-model-contract.md). They cannot create missing entropy, prove physical independence or automatically cover quantum side information. The broad `O(log n)`-entropy target at constant error is already achieved by [Li's 2023 result](https://arxiv.org/abs/2303.06802). Building and qualifying a finite instance of an existing extractor is project work, not an unresolved theorem.

Revision checks matter here: [the May revision of TR26-011](https://eccc.weizmann.ac.il/report/2026/011/) withdraws its efficient negligible-error DAG-source construction while retaining an existence result, and [TR26-089](https://eccc.weizmann.ac.il/report/2026/089/) was retracted in June because of an error in Lemma 5.9. Neither supplies the required efficient two-independent-source theorem.

The local [finite composition and parameter proof contract](../hardware/trng-source-model-contract.md#finite-composition-and-parameter-proof-contract) retains the existing inner-product construction. Its extension adds the conditioner-image error to the final seed budget and proves that some parameter records passing the arithmetic admissibility test have no realizing source pair. These strengthen the existing proof's use at its stated parameters; they do not claim an improved extractor or supply missing physical premises.

### Optimal binary-code rate versus distance

**Open mathematical optimization problem; direct reliability and capacity connection.** Determine `R_2(delta) = limsup_n log_2(A_2(n,ceil(delta*n)))/n`, where `A_2(n,d)` is the largest binary code of length `n` and minimum Hamming distance at least `d`. Exact general tradeoffs remain unknown. See [research on coding bounds](https://chrisjones.space/assets/papers/ho-delsarte.pdf) and [Alrabiah and Guruswami's August 2026 preprint](https://arxiv.org/abs/2608.09347); the latter announces mixed-qubit-channel upper bounds strictly improving the first MRRW bound throughout `0 < delta < 1/2`, and a masked construction strictly improving the second MRRW bound throughout that interval, for both linear and nonlinear codes. This is a substantial bound improvement, not the exact tradeoff or a constructive decoder.

**AI-produced formal artifact, August 2026.** [OpenAI's `MetricCodes.lean` at revision `94bc0feb`](https://github.com/openai/ten-proofs/blob/94bc0feb6a9ff12c7d31d6de640a725c9d43d2b6/MetricCodes.lean) defines the same asymptotic binary-code rate and proves `exists_binaryRate_mrrw_improvement`: for every `0 < delta < 1/2`, a positive gap below the second MRRW rate exists. The source theorem has a proof body; the separate Comparator challenge placeholders are not that proof. [Barg's 1 September comparison](https://arxiv.org/html/2609.01860v1) explains why this subspace-certificate argument and Alrabiah-Guruswami's channel argument yield the same bound. This review inspected the rate definition and theorem; it did not replay the build or audit the imported proof closure. The [metadata](https://github.com/openai/ten-proofs/blob/94bc0feb6a9ff12c7d31d6de640a725c9d43d2b6/formalization.yaml) reports only standard Lean axioms. This artifact is a proof source for an upper bound, not an encoder or decoder.

Constructive progress could reduce redundancy or improve protection within fixed memory and frame budgets. The [hardware ECC and link design](../spec.md#r-15-175) still requires concrete short block lengths, decoding latency, area, failure behavior and a qualified error model. An asymptotic existence bound does not supply a fixed-latency SECDED or DECTED implementation. Capacity under random errors and minimum-distance protection against adversarial errors are different questions.

### Deterministic fully polynomial list decoding

**Open algorithmic target, alongside a recently solved fixed-gap case; conditional recovery connection.** For suitably parameterized families of folded Reed-Solomon codes of rate `R`, can every candidate within error fraction `1-R-epsilon` be found deterministically in time polynomial in both block length `n` and `1/epsilon`? [Ashvinkumar, Habib and Srivastava, SODA 2026](https://doi.org/10.1137/1.9781611978971.35), give deterministic near-linear time for fixed `epsilon`, and randomized `poly(1/epsilon)` times near-linear-in-`n` time. Their [discussion](https://arxiv.org/html/2508.12548v1#S1.SS3) leaves the combined deterministic fully polynomial target open. The folding parameter must match the capacity gap, and the deterministic dependence on that gap is large.

Progress could reduce redundancy while retaining predictable recovery algorithms for sufficiently large storage or communication blocks. These are large-alphabet list-decoding guarantees, not binary SECDED bounds. A list can contain several plausible messages; authenticated selection and bounded processing remain necessary. The [fixed-frame link contract](../spec.md#r-15-228b) still needs finite block lengths, fixed traffic, latency and failure behavior. A separate recent result improves [decoder scratch space](#capacity-approaching-decoding-with-small-workspace).

**Separate September 2026 advance for ordinary Reed-Solomon codes.** [Brakensiek et al., 5 September revision](https://eccc.weizmann.ac.il/report/2026/164/revision/1/download), give deterministic polynomial-time capacity-approaching list decoding for every distinct evaluation set over sufficiently large prime fields, for any fixed rate `R` and fixed gap `0 < delta < 1-R`. The field requires `q >= C(R,delta)*n`, sufficiently large block length, and list size `n^{O_{R,delta}(1)}`. The exponent's parameter dependence does not settle polynomial time jointly in block length and inverse gap, and ordinary RS and folded RS remain distinct code families.

### Finite-length optimality of single-deletion VT codes

**Named optimality conjecture; prospective framing connection.** Let `VT_0(n)` contain the binary strings satisfying `sum_i i*x_i = 0 mod (n+1)`. Is it a largest possible length-`n` code correcting one deletion for every `n`? Asymptotic optimality does not settle exact finite lengths. [Weindel and Heckel, TMLR, June 2026](https://openreview.net/pdf/3877b05d22c2dc202b1750b4a1ecf7b3aaafbf50.pdf), still treat this as a conjecture, with exact optimality established only through length 11; recovering the known construction does not prove maximality.

A resolution could establish short-block redundancy limits for a matching synchronization-loss channel. Deletions are different from substitutions or erasures at known locations. The present memory and link contracts do not identify that channel model, so this is a possible future framing application rather than an improvement to the selected ECC.

The [June revision](https://arxiv.org/abs/2504.00613v2) proves that an LLM-discovered function generates the VT family. Its broader multiple-deletion and quaternary-edit experiments remain finite construction/search results. Recovering a conjectured-optimal family, even with a proof of the construction, does not establish its finite-length maximality.

### Log-rank conjecture

**Named conjecture; conditional communication-budget connection.** For a Boolean two-party communication matrix `M`, is deterministic worst-case communication complexity bounded by `poly(log(2 + rank_R(M)))`? The rank is over the reals. A [February 2026 paper on equivalent formulations](https://eccc.weizmann.ac.il/report/2025/141/revision/1/download/) and [Song's August 2026 preprint](https://arxiv.org/abs/2608.01812) leave the conjecture open. The approximate-log-rank variant is a different conjecture and must not be conflated with this one.

A constructive result could reduce communication for matching exact predicates on separately held inputs, potentially reducing [ensemble slot reservations](../spec.md#r-15-228b). It would not compress arbitrary tensor payloads or automatically extend to many parties. Protocol rounds, local work, confidentiality and padding to the permitted fixed schedule must all be charged. A short unpadded transcript that reveals private information is not a valid replacement for the platform's communication contract.

[Song's August result](https://arxiv.org/abs/2608.01812) improves explicit lower bounds to `Omega((log r)^2/log log r)`, while recording the general `O(sqrt(r))` upper bound. This narrows one side of the gap; it neither gives the conjectured polylogarithmic upper bound nor refutes the existence of some polynomial in `log r`.

### Li-Li undirected multiple-unicast conjecture

**Named conjecture; speculative ensemble connection.** For independent unicast sessions in an undirected capacitated network, network coding offers no throughput advantage over fractional routing. [Liu, Que, Li and Li's August 2026 paper](https://arxiv.org/abs/2608.06070) proves further special cases while leaving the general conjecture open.

A proof would delimit coding-based capacity optimization; a counterexample could identify topologies and traffic where coding helps. Applying this to a future [ensemble](../spec.md#r-15-228b) first requires a matching multi-hop network model. A single point-to-point link, directed time-slot graph, multicast, or correlated inference traffic does not automatically fit. Coding would still have to preserve fixed schedules, bounded buffers, session integrity and authority confinement.

The [August paper](https://arxiv.org/html/2608.06070v1) includes all instances with at most five terminal locations, planar networks with at most three designated faces and both endpoints of each session on the same designated face, and demand graphs contained in the union of a triangle and a star. These identify concrete solved topology families; the unrestricted undirected multiple-unicast statement remains open.

## More indirect mathematical opportunities

### Generalized Riemann Hypothesis for Dirichlet L-functions

**Named conjecture; limited offline number-theory connection.** The nontrivial zeros of these L-functions are conjectured to have real part one half. This is stronger than the ordinary Riemann Hypothesis. Its algorithmic consequences include short-witness bounds used in deterministic number-theory algorithms; see [Bach's explicit bounds](https://www.ams.org/mcom/1990-55-191/S0025-5718-1990-1023756-8/S0025-5718-1990-1023756-8.pdf) and [Miller's primality work](https://www.cs.cmu.edu/~glmiller/Publications/Papers/Mi76.pdf).

A proof could remove a hypothesis from some offline field-parameter or witness-search procedures. This is a weak connection to the project's [finite-field arithmetic generation](../implementation/fiat-crypto-emission.md), whose selected constants can instead carry direct finite certificates. Deterministic polynomial-time primality testing already exists without GRH. GRH would prove neither factoring hardness nor the security of this cryptographic suite, and no current runtime speedup is claimed.

### Hadamard matrix conjecture

**Named conjecture; limited representation connection.** For every positive integer `k`, does there exist a `4k` by `4k` matrix with entries `+1,-1` whose rows are orthogonal, so that `H*H^T = 4k*I`? [Glazyrin's August 2026 paper](https://arxiv.org/html/2608.16116v1) identifies this unrestricted real-matrix existence problem as open. Solving particular orders or classifying complex Hadamard matrices does not settle it.

Constructions for more dimensions could broaden orthogonal sign transforms used in signal processing or quantization, sometimes avoiding padding. This is only a possible future representation choice. The [Bonsai assessment](../performance/bonsai2-assessment.md) already names block-1024 Hadamard rotations; that power-of-two transform requires no solution of the conjecture. General existence would not imply an `O(n log n)` transform, better model quality, smaller scratch space or permitted changes to frozen weight semantics.

**Twelve finite orders resolved, August 2026.** [Epoch's solution update](https://epoch.ai/frontiermath/open-problems/hadamard) records a three-person Anthropic team and Claude producing matrices for the formerly unresolved orders below 2000, including 668. This review independently checked all twelve matrices from the [public data mirror at revision `d8252010`](https://github.com/bbeartheancient/hoa64/tree/d825201089123126ce792d4921cba4ae1b8977a3/matrices): 668, 716, 892, 1132, 1244, 1388, 1436, 1676, 1772, 1916, 1948 and 1964. A separate exact-integer checker verified square dimensions, the sign alphabet and Hamming distance `n/2` for every distinct pair of rows; positive and corrupted negative controls passed. Thus `H*H^T = n*I` holds for each supplied matrix. The order-668 decompressed CSV has SHA-256 `afd95960604159441497bbc5f507aa5ff820682a5b11f19d6667c6e31a00d2ee`. This establishes those finite existence claims, not the universal conjecture or a fast transform.

[Ramos, Hulak and de Queiroz's multiplier restrictions](https://arxiv.org/abs/2607.20765) concern particular length-333 Legendre-pair symmetries, not nonexistence of all order-668 matrices. A [Lean repository at revision `d1f22fc0`](https://github.com/SamuelSchlesinger/hadamard-conjecture/tree/d1f22fc03782292dddf44b9052eb5d8aee2be96b) formalizes Paley and Kronecker constructions while leaving the universal `hadamard_conjecture` target open.

### Shannon capacity of the seven-cycle

**Open exact-value problem; speculative zero-error coding connection.** For the seven-cycle confusability graph `C_7`, determine `Theta(C_7) = sup_m alpha(C_7 strong-power m)^(1/m)`, where `alpha` is the maximum independent-set size. [Polak and Schrijver](https://arxiv.org/abs/1808.07438) give a constructive lower bound; [August 2026 research](https://arxiv.org/abs/2608.30273) continues to improve constructions without determining the exact capacity.

The general method studies how distinguishable messages can be packed under a specified zero-error confusion model. It could inspire more efficient codes for a matching future channel. No evidence identifies `C_7` as this platform's electrical, storage or fault model. Its exact value would therefore be mathematical background, not an immediate change to [fixed-frame communication](../spec.md#r-15-228b), authentication or ECC.

**AI-assisted construction with a public checker.** [Tandon's 31 August preprint](https://arxiv.org/abs/2608.30273) raises the constructive lower bound to `3.25883262...` using a dimension-500 construction. The [companion package at revision `c7534084`](https://github.com/tandonravi/C7-Shannon-Capacity-Heterogeneous-Recursion/tree/c753408492dde92a239708986d16c15dbf6c3235) contains exact finite-certificate and recursive-arithmetic checks. Source inspection found that the default arithmetic check assumes supplied certificate counts; `--recomputed` derives them from the base certificate. Neither path was executed in this review. The package explicitly does not formalize the new heterogeneous theorem in Lean. A [separate Buys-Polak-Zuiddam Lean development](https://github.com/spectra-research/shannon-capacity-lean/blob/main/ShannonBounds/Main.lean) states the weaker lower bound `3.258827985920007`; it is not a formal proof of Tandon's improvement. These are reproducible-construction leads, with the finite-certificate and recursion obligations explicit, not exact determinations of capacity.

## Project-specific questions, not established named conjectures

The closest opportunities need not await a famous theorem. The [existing research agenda](static-memory-research.md) owns these questions; this survey does not create another implementation backlog.

- **Exact planning near laminar lifetimes.** In the binary-encoded, unit-alignment, unrestricted-base model, let `k` be the minimum number of intervals deleted to make the lifetime family laminar. Is exact placement possible in `f(k) * poly(input length)` time? What hardness can be shown, potentially even at a small fixed `k`? The [structural analysis](../implementation/static-memory/structure.md) already solves the deletion parameter and gives exact packing for bipartite crossing graphs. The remaining general parameterized problem is different from those solved cases.
- **The deletion-number-two load gap.** In that same model, must every instance with `k = 2` attain its maximum simultaneous load as legal span? The [structural analysis](../implementation/static-memory/structure.md) proves equality for `k <= 1` and for bipartite crossing graphs, and gives a gap at `k = 3`. The remaining `k = 2` question concerns unrestricted crossing graphs, necessarily involving a triangle if there is a gap. A counterexample would not itself prove computational hardness.
- **Compositional public-phase reuse.** Can component certificates establish global safe reuse efficiently without enumerating every state combination, while accounting for asynchronous completion, retained authority and revocation? Existing [phase experiments](../implementation/static-memory/phases.md) do not establish the full implementation theorem.
- **Capacity sharing versus private demand.** Under an explicit observation model, what headroom, padding, public release rule or declassification permits useful sharing without leaking another label's demand? [Lending experiments](../implementation/static-memory/lending.md) give scoped counterexamples. Fixed-tier cross-owner lending remains excluded; this explores changed assumptions rather than an authorized allocator feature. It is not a universal impossibility conjecture independent of the chosen service guarantees.
- **Reclamation-aware scheduling and bounded segmentation.** Do these transformations admit a larger real workload after charging metadata, copy traffic, zeroization, quarantine and deadlines? These are workload hypotheses, not universal mathematical conjectures. The [experiments and byte ledger](../implementation/static-memory/experiments.md) provide the comparison framework.

## Recent solutions and advances worth evaluating

These entries include published resolutions, published partial results and explicitly labeled preprint announcements. Dates refer to the stated publication or announcement, not to a claim that all of the underlying work happened in the last few months. Their potential applications remain subject to the same implementation bridge as the open problems. Recent results with an important remaining frontier also appear above under [memory reallocation](#optimal-copying-overhead-for-memory-reallocation), [finite-field factorization](#deterministic-polynomial-factorization-over-finite-fields) and [list decoding](#deterministic-fully-polynomial-list-decoding).

### Pinwheel scheduling: the 5/6 theorem and relaxed synthesis

**Published resolution, August 2026.** Kawamura proves that integer-period, unit-service pinwheel instances with `sum_i 1/a_i <= 5/6` are schedulable. The [paper and supporting material](https://www.kurims.kyoto-u.ac.jp/~kawamura/pinwheel/) provide computer-assisted proof data and schedules for reduced instances. This is a sufficient condition: density above `5/6` does not alone establish infeasibility. Candidate maintenance or replenishment cadences could be checked against the [schedule-record contract](../implementation/contracts/schedule-record.md), provided each service and its overhead fit a common unit slot and additional conflicts are modeled.

**Separate April 2026 preprint advance.** [Kleinberg and Mishra](https://arxiv.org/abs/2604.13974) announce NP-hardness of ordinary explicitly listed instances, and an EPTAS that either correctly reports original periods `A` infeasible or certifies relaxed periods `(1+epsilon)A` feasible. Its parameter dependence is extremely large. This offers a theoretical service-versus-resource tradeoff, not permission to relax an admitted deadline. The [certificate-size questions](#pinwheel-scheduling-certificates-and-complexity) remain distinct.

### Ordinary Komlós and Beck-Fiala proof announcements

**September 2026 preprint claims.** [Guo, Fang and Lu](https://arxiv.org/abs/2609.11189) announce final-sum discrepancy below `3*sqrt(2*pi)` for unit-Euclidean-norm vectors, implying below `3*sqrt(2*pi*t)` for a set system in which each element occurs in at most `t` sets. [Karingula and Lovett](https://arxiv.org/abs/2609.20979) give a simplified proof with constant `36`. The [prefix counterexample](#strong-or-prefix-komlós-conjecture) and [polynomial real-RAM construction](#efficient-constant-discrepancy-komlós-construction) are separate subsequent results.

Useful algorithms need not wait: [Bansal and Jiang's 2025 work](https://arxiv.org/abs/2508.03961) gives polynomial-time `O(sqrt(t))` Beck-Fiala discrepancy when `t >= log^2 n`, plus improved general Komlós bounds. Sparse resource assignments could use such algorithms to propose checked candidates. Normalization, legal placement choices and actual capacity constraints still need to match the theorem.

**Formal artifact inspected.** [Dahia's Lean solution at revision `d8028574`](https://github.com/gdahia/Komlos/blob/d802857449234318d557361b1dbb0a27e0258528/Solution.lean) gives the constant-36 real-vector theorem and `36*sqrt(t)` Beck-Fiala consequence. Its solution imports the completed library, excluding the separate challenge placeholders. The [external CI build passed at that revision](https://github.com/gdahia/Komlos/actions/runs/35320354586), and [formalization metadata](https://github.com/gdahia/Komlos/blob/d802857449234318d557361b1dbb0a27e0258528/formalization.yaml) reports only `propext`, `Classical.choice` and `Quot.sound`. This review inspected sources and that build record, without independently replaying or fully auditing the proof. The artifact documents AI assistance; it formalizes neither the sharper constant, prefix discrepancy nor the polynomial-time algorithm.

### Square-root-space simulation and circuit evaluation

**2025 theorem and related preprint result.** [Williams, STOC 2025](https://arxiv.org/abs/2502.17779), proves that a multitape Turing computation taking time `t >= n` can be simulated in `O(sqrt(t log t))` space, building on Cook and Mertz's tree-evaluation technique. [Shalunov's June 2025 revision](https://arxiv.org/abs/2504.20950) gives the corresponding `O(sqrt(s log s))` workspace bound for evaluating a circuit of size `s`.

These results support exploring recomputation and alternative evaluation orders to reduce intermediate storage. They do not preserve the original runtime, provide a direct arbitrary-RAM transformation, or merely repack an unchanged live set. A bounded implementation could be investigated in the [resident compiler](../spec.md#r-13-027) or a guest algorithm, with explicit costs for recomputation, input access and polling. This is distinct from reducing allocator fragmentation.

A [separate claim of `O(sqrt(t))` simulation space](https://arxiv.org/abs/2508.14831v4) was withdrawn on 1 January 2026: its interval-based associative summary tree did not model the dependencies in Williams's simulation. That withdrawn strengthening does not supersede the established bound.

### Catalytic graph and sequence algorithms

**Published 2026 algorithms.** [Cook and Pyne, ITCS 2026](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ITCS.2026.43), give explicit catalytic graph algorithms, including directed reachability. [Chmel et al., CCC 2026](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CCC.2026.29), obtain polynomial-time algorithms using `O(log n)` clean workspace and sublinear catalytic storage `n / 2^(Theta(sqrt(log n)))` for directed reachability and several sequence problems, including edit distance and longest common subsequence.

Compiler graph passes and text tools are plausible consumers inside a private memory envelope. The retained payload remains physically present, and all work needed to restore it must be charged. [Catalytic memory's](#the-power-of-catalytic-memory) authority, quiescence, capability-tag and interruption qualifications are essential. A separate [April 2026 claim of polynomial-time, almost-logarithmic-total-space tree evaluation](https://arxiv.org/abs/2604.02606) was withdrawn because its polynomial-degree analysis was incorrect; it is not evidence of that stronger result.

**Further July-September 2026 preprints.** [Becker et al.](https://arxiv.org/abs/2607.08559) and [Kaplan et al.](https://arxiv.org/abs/2607.09475) develop multi-pass catalytic streaming algorithms, with no asymptotic clean-space advantage in the one-pass model. Replaying input and retaining catalyst capacity are part of the cost. [Vinciguerra's 16 September operator approach](https://arxiv.org/html/2609.18692v1) proves at least four input accesses necessary for passive-output polynomial programs computing polynomials of degree at least three over characteristic-zero fields and constructs `x^(2t-1)` using four accesses and `t` registers in characteristic zero or greater than `2t-1`. It credits AI assistance and derives streaming and matrix-powering improvements. These scoped algebraic results leave `CL = L` and `P` containment in `CL` unresolved.

### Sparse linear programs and short circuit walks

**Solved restricted algorithm and February 2026 preprint advance.** [Dadush et al.](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.STACS.2025.2) give strongly polynomial optimization when every row, or every column, has at most two nonzero coefficients. [Natura](https://arxiv.org/abs/2602.06958) proves an `O(m^2 log m)` monotone circuit-diameter bound for standard-form polyhedra with `m` equality constraints. Circuit steps are more general than edge steps; this is not a proof of the ordinary polynomial Hirsch conjecture or a general strongly polynomial LP algorithm.

The sparse theorem is a concrete option when a resource-assignment subproblem actually has that structure. The circuit-walk theorem offers a new target for search algorithms. Neither turns arbitrary contiguous placement into a linear program, and the [general algorithmic question](#strongly-polynomial-linear-programming) remains open.

### Goldberg-Seymour and the number of transfer rounds

**Published resolution, September 2025.** For a loopless multigraph with maximum degree `Delta`, let `Gamma` be the maximum of `2*|E(U)|/(|U|-1)` over odd vertex sets `U` of size at least three, with zero when there is no such set. [Chen, Jing and Zang](https://link.springer.com/article/10.1007/s10878-025-01348-6) prove `chi'(G) <= max(Delta+1,ceil(Gamma))`.

Under the [endpoint-conflict transfer model](#list-edge-coloring-conjecture), this bounds the number of matching rounds, with repeated transfers represented by parallel edges. It gives a useful lower-bound comparison and target for checked schedule synthesis. Per-transfer slot lists, routed conflicts and unequal durations remain additional problems; the theorem is not a complete schedule generator for the platform.

A separate [Chen-Hao-Yu-Zang proof preprint](https://arxiv.org/abs/2407.09403v1) gives an `O(|V|^5 |E|^3)` algorithm attaining the same coloring bound, whereas the published proof above is nonalgorithmic. This supplies a constructive synthesis lead; its exponent and the platform's additional scheduling constraints still matter.

### Hashing beyond the uniform-probing conjecture

**FOCS 2024 result, with a 2025 preprint and further STOC 2026 progress.** [Farach-Colton, Krapivin and Kuszmaul](https://arxiv.org/abs/2501.02305) disprove Yao's conjectured optimal worst-case expected search cost for greedy open addressing without reordering. Their funnel hashing improves the dependence on empty fraction `delta` from order `1/delta` to order `log^2(1/delta)` in its stated range. Their non-greedy elastic hashing also achieves constant amortized expected search cost without relocating existing entries. The [FOCS paper](https://ieee-focs.org/FOCS-2024-Papers/pdfs/FOCS2024-1oojWxXs5YAKfs3z3lBRMF/167400a594/167400a594.pdf) establishes the publication date. The [STOC 2026 follow-on](https://acm-stoc.org/stoc2026/toc.html), *Greedy Open Addressing Revisited: Beyond Yao's Lower Bound*, separates query probe order from insertion order: greedy insertion can then coexist with `O(1)` amortized expected queries and `O(log(1/delta))` worst-case expected queries. These guarantees concern that relaxed probing model.

This can inform denser fixed-capacity application tables, reducing spare slots and avoiding some entry movement. Expected and high-probability costs are not deterministic WCET, successful searches are not every dictionary operation, and deletion/resizing support requires its own result. Hash-table slack is also distinct from general heap fragmentation. Applications must qualify a bounded implementation within their existing memory and authority envelope.

An [experimental Rust implementation, `opthash-rs` revision `d7a408a3`](https://github.com/aaron-ang/opthash-rs/tree/d7a408a3dccdd48ccd5cc62f83397f35a0995412), makes the elastic and funnel constructions available for finite-workload evaluation. Its own comparison documents deterministic mixing, tombstones, growth, rebuilds and exhaustion fallbacks outside the paper's fixed-table insertion-only analysis. This is an implementation lead, not evidence that every library operation inherits the theorem; no target benchmark was run in this review.

### Compact static dictionaries and dynamic ordered indexes

**Published 2025 and 2026 results, with an August 2026 preprint advance.** [Hu et al., STOC 2025](https://arxiv.org/abs/2412.10655), obtain static dictionaries with worst-case constant query time and `OPT+n^epsilon` total bits for fixed positive `epsilon`, under stated word-RAM and universe assumptions; `OPT = log_2 binom(U,n) + n log_2 sigma`. Construction uses randomness, and auxiliary tables/hash descriptions count toward the total. [Kuszmaul, Liang and Zhou, SODA 2026](https://arxiv.org/abs/2510.19175), obtain dynamic ordered dictionaries with sublinear redundancy for polynomial-size universes and optimal amortized expected operation time.

[Blelloch et al., 6 August 2026](https://arxiv.org/abs/2608.06077), address clustered keys through difference encoding. Their preprint gives space `(1+O(epsilon))*gap(S) + O(n log(gap(S)/n))` bits and expected amortized operation time `O(log(1/epsilon)/log log(1/epsilon))`, for `0 < epsilon < 1/4` and `n = U^(1-Theta(1))`, with a matching tradeoff lower bound even for static queries. Gap entropy can be much smaller than the unrestricted-set information bound; this is a distinct opportunity for clustered application indexes, without a per-operation deadline guarantee.

The static result is especially compatible with composition-time construction of immutable metadata. The dynamic result could reduce index overhead inside applications. Neither eliminates CHERI representation costs or supplies a bound in target cycles. A checked construction needs to account for every lookup table, hash seed, encoded field, initialization step and construction workspace; expected update bounds do not establish a fixed-tier deadline.

### Dynamic entropy-encoded arrays

**August 2026 preprint announcement.** [Blelloch et al.](https://arxiv.org/html/2608.06066v1) present mutable arrays with constant-time indexed reads and updates and space approaching empirical zero-order entropy, plus alphabet-support and lower-order terms. This addresses the longstanding tension between compression and constant-time modification. Crucially, the theorem uses a virtual-memory model and gives its time and space bounds with high probability. It does not claim the same bounds for every random choice on this platform.

Possible consumers include compressible application metadata and symbol arrays. The paper's virtual memory is an abstract resizable-buffer model with a software simulation, so hardware address translation is not a prerequisite. A VerifiedOS implementation still needs to qualify that simulation and charge its physical backing, pointers, capability bounds and allocation overhead. Content-dependent compressed size must stay within the authorized observation model. This is a representation lead; it does not change the fixed-memory contract or make incompressible data smaller.

### Directed shortest paths below the sorting barrier

**Published 2025 breakthrough and 2026 improvement.** [Duan et al., STOC 2025](https://arxiv.org/abs/2504.17033), give deterministic directed single-source shortest paths with nonnegative real weights in `O(m log^(2/3) n)` comparison-addition operations. [The ICALP 2026 improvement](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ICALP.2026.81) gives `O(m sqrt(log n) + sqrt(m n log n log log n))`. These results break the old sorting barrier for sparse graphs; they do not settle the [weighted APSP hypothesis](#weighted-all-pairs-shortest-paths-hypothesis).

Matching graph kernels in planning or guest applications could benefit at sufficient scale. The result does not imply general faster sorting or faster interpreter dispatch. Concrete weight encoding, overflow, graph representation, scratch space and actual workload sizes must be evaluated before changing an implementation.

**AI-produced formal artifact, September 2026.** [Vals AI's C-HD announcement](https://www.vals.ai/blogs/faster-shortest-path-algorithm) links a [frozen proof package at revision `98c53acc`](https://github.com/spicylemonade/c-hd-proof/tree/98c53accb47a505482a1781597ae14bf67e81cec). Its closed Lean theorem covers exact directed nonnegative-real SSSP and charged runtime in its RAM/comparison-addition model. The improved branch requires `m <= n*floor(floor(log2 n)^(3/4))`; along `m` of order `n log^(3/4) n`, its bound is `O(n log^(11/12) n)`. Small inputs and other densities use a Bellman-Ford fallback. The inspected theorem and package report a full build and kernel replays with standard Lean axioms; these records were not rerun here. One internal agent review is complete and another remains provisional. The broader paper range and linear-space bound are not formalized. This is a concrete new research artifact with enormous constants, no demonstrated practical speedup, and computational-model correspondence and novelty still requiring external review.

### Capacity-approaching decoding with small workspace

**August 2026 preprint announcement.** [Fathollahi, Ron-Zewi and Wootters](https://arxiv.org/html/2608.15937v1) give explicit code families, for infinitely many block lengths `N`, with rate at least `R`, deterministic list decoding at error fraction `1-R-tau`, time `N^(1+tau)` and workspace `N^tau`, for fixed `R` and suitable constant `tau`. Alphabet and list sizes are constant in `N`. The workspace definition excludes read-only random-access input and sequential write-only output. This is not sublinear total resident storage or a streaming-input theorem.

The result could inform scratch budgets for bulk recovery while preserving a high code rate. Finite constants, authenticated selection among candidates, bounded output and target WCET still matter. It does not directly replace tiny fixed-latency memory ECC or imply an attack on a lattice cryptosystem. The [deterministic fully polynomial gap-dependence problem](#deterministic-fully-polynomial-list-decoding) remains a separate frontier.

## Misconceptions excluded from the open list

| Topic | Why it is not an unresolved opportunity in the stated form |
| --- | --- |
| Integer-period pinwheel 5/6 density conjecture | A [published theorem](#pinwheel-scheduling-the-56-theorem-and-relaxed-synthesis), included above for its useful consequences. The certificate-complexity questions remain distinct. |
| Ordinary Komlós and Beck-Fiala discrepancy | [September 2026 proof claims](#ordinary-komlós-and-beck-fiala-proof-announcements) require explicit status qualification. The fixed-order prefix constant has a counterexample manuscript, while polynomial constant signing has a real-RAM algorithm announcement; their remaining quantitative and implementation questions are separately stated. |
| Sensitivity conjecture | [Huang proved it in 2019](https://arxiv.org/abs/1907.00847). It is not an open source of general compiler speedups. |
| Constant-error two-source extraction at logarithmic min-entropy | [Li's result](https://arxiv.org/abs/2303.06802) achieves this target. Lower error and useful finite parameters are separate questions. |
| Universal terminating verification of unrestricted programs | General undecidability is an established limit, not an unproved conjecture that `P = NP` would resolve. Bounded finite-state models and restricted languages require separate analysis. |
| Automatically replacing random oracles with concrete hashes | [Canetti, Goldreich and Halevi](https://arxiv.org/abs/cs/0010019) give counterexamples to that universal inference. A scheme-specific proof and its concrete premises remain necessary. |
| Perfect online packing with no movement, slack or failure for arbitrary requests | Even elementary separated-free-extent examples defeat the unqualified claim. The [allocation baseline](../implementation/static-memory/baseline.md) specifies which waste is placement, reservation or reuse cost; deleting one premise changes the problem. |
| Collatz, Goldbach, Hodge and other famous open problems | No concrete reduction to a present VerifiedOS bottleneck or admission obligation is identified here. Their absence is a relevance decision, not a claim that they cannot ever affect computing. |

## How to use this survey

The [owner links above](#how-the-connections-fit-this-machine) lead to research
handoffs beside unfinished proof work. Each handoff identifies a matching
consumer or explicitly deferred workload, the missing reduction or refinement,
and useful positive/refuting examples. The
[static-memory handoff](static-memory-research.md#survey-handoff-to-unfinished-proofs)
also routes the project-specific questions to their existing owners. Relevant
open checklist leaves link to these contracts; the survey owns research status,
while those contracts own the local application. These notes change no estimate,
completion state, accepted premise or implementation selection.

For allocation work, start with Dynamic Storage Allocation, bin-packing gaps and the project's near-laminar questions. For scheduling, start with the precise job and service models, then test whether discrepancy or ordering results preserve their dependencies. For guarantees, distinguish the cost of finding proofs from their size, checking cost and truth under stated assumptions. For Wasm, profile the selected interpreter and guest algorithms before assigning value to an asymptotic result. For cryptography, maintain the existing concrete premise and attack ledger.

Among recent results, compact static dictionaries have a particularly natural composition-time consumer. Pinwheel and edge-coloring theorems offer checkable schedule candidates when their service models match. Memory reallocation and catalytic computation address different ways to use a tight private envelope, but require explicit movement or restoration semantics. Compressed arrays and small-workspace decoding merit finite-size memory measurements before any performance claim. These are evaluation priorities inferred from the design, not new implementation commitments.

A proposed adoption needs a precise mathematical statement, a matching workload or reduction, and a constructive implementation or checked finite witness. Charge its memory, metadata, communication, initialization, reclamation and worst-case timing; preserve numerical semantics and the authorized information flows. Existing checkers must validate the resulting artifacts. A paper, a heuristic success, or a conjectural ratio supplies none of that evidence by itself.

Refresh status before using an entry in a design decision. Record the actual remaining question when a special case is solved, and distinguish an announced proof, a reviewed theorem, a mechanized theorem and its implementation bridge. This document is a research map; the owning contracts decide whether any result can change the machine.
