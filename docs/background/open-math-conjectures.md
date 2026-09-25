# Open mathematical conjectures and their possible impact on VerifiedOS

> Non-normative research survey. Sources checked on 24 September 2026. The [requirements register](../requirements-register.md) remains authoritative. This survey admits no new axiom or implementation decision and supplies no evidence that a platform guarantee has been established. Existing declared cryptographic premises retain their current status.

The strongest connections are to memory placement, scheduling, proof production, computational security, and arithmetic kernels. Some resolutions could improve an algorithm; others would establish limits or invalidate a security assumption. A proof of existence need not provide a usable construction, and a faster asymptotic algorithm need not be faster at this machine's sizes.

There is no exhaustive, stable list of **all** open mathematics that could affect a general-purpose computer. This survey covers named conjectures and concrete unresolved questions for which a causal connection to the present design can be stated. It includes open complexity classifications and cryptographic hypotheses, explicitly labeled because they are not all conjectures in the same sense. Project-specific research questions appear separately. Famous problems without an identified consumer are excluded rather than assigned an invented benefit.

The mathematical statements and status come from the linked sources. **The proposed VerifiedOS applications are this survey's inferences**, unless an existing project contract already states the connection. Recent preprints are identified as such; finding a claimed proof is not the same as establishing its acceptance or checking it in the project's prover.

## How the connections fit this machine

| Project surface | Mathematical opportunity | Boundary that still applies |
| --- | --- | --- |
| [Fixed memory placement](../implementation/placement-search.md) and [portable planner](../implementation/portable-memory-planner.md) | Tighter packing, smaller search, stronger lower bounds | Fixed backing, exact capability bounds, alignment, islands, safe-reuse lifetimes and independently checked candidates |
| [Elastic domain](../implementation/contracts/elastic-domain.md) | Better resource assignments and bounded allocation policies | Composition-fixed envelope, quarantine and revocation costs, permitted in-label contention |
| [Phase service](../implementation/phase-service/prerequisite-contract.md) and [schedule records](../implementation/contracts/schedule-record.md) | Shorter schedules and smaller intermediate buffers | WCET, dependencies, nonpreemption, communication slots and confidentiality boundaries |
| [Proof assistance](../assurance/proof-assistance.md) and [CIC qualification](../assurance/cic-checker-qualification.md) | Faster proof search, smaller certificates and tractable restricted verification | Frozen claims, exact assumptions, kernel checking and non-vacuity review |
| [Wasm execution](../implementation/contracts/wasm-execution.md) | Better guest algorithms, preparation, representations and arithmetic | Pure interpretation, bounded native phases, no JIT, no new performance-only trusted checker |
| [Cryptographic premises](../assurance/proof-reuse/crypto.md) and [entropy qualification](../hardware/trng-source-model-contract.md) | Stronger reductions, better finite parameters, explicit constructions | Concrete security games, attack budgets, source independence and physical qualification |
| [Compute compatibility](../implementation/compute-compatibility.md) and [inference](../performance/inference-demand.md) | Fewer arithmetic operations, transfers and resident intermediates | Exact or explicitly permitted numerical semantics, fixed traffic budgets and measured target costs |

The [static-memory research agenda](static-memory-research.md) already separates live payload, legal address span, stranded reservations and reclamation overhead. That distinction governs every allocation entry below. A better placement does not shorten an object's lifetime or remove a quarantined capability. Likewise, an amortized data-structure theorem does not establish a per-slot deadline.

## Allocation, fragmentation and scheduling

### Dynamic Storage Allocation below a factor of two

**Open approximation problem; direct connection.** Given known object sizes and lifetime intervals, assign each object one fixed contiguous address interval. Objects whose lifetimes overlap must occupy disjoint addresses. Minimize the resulting address span. Can a polynomial-time algorithm achieve a worst-case approximation factor strictly below two for the unrestricted problem? Khan's [open-problem collection](https://www.csa.iisc.ac.in/~arindamkhan/FGA_OpenProblems.pdf) lists this frontier, with a known `2 + epsilon` guarantee; [Buchsbaum et al.](https://epubs.siam.org/doi/10.1137/S0097539703423941) establish the classical approximation and load analysis.

A constructive improvement could reduce the backing needed by the fixed-tier [memory plan](../spec.md#r-08-012). A hardness result would sharpen the reason to exploit structured lifetimes. Neither outcome says that optimal span equals peak live bytes. Alignment, CHERI representability, pinned locations, distinct memory classes and revocation may invalidate a direct transfer of the classical guarantee.

### Modified Integer Round-Up Property for bin packing

**Named conjecture; conditional allocation connection.** Let `OPT` be the minimum number of unit-capacity bins and `LP` the optimum of the Gilmore-Gomory configuration relaxation for the same item multiset. The Modified Integer Round-Up Property, MIRUP, asserts `OPT <= ceil(LP) + 1`. The stricter assertion `OPT = ceil(LP)` is false. See the [bin-packing discrepancy paper](https://sites.math.washington.edu/~rothvoss/publications/BinPackingViaDiscrepancyOfPermutations-talg.pdf) and a [2026 temporal-bin-packing study](https://doi.org/10.1007/s10288-025-00602-1).

Related unresolved targets are a universal constant additive LP gap and an efficient algorithm returning at most `OPT + O(1)` bins. These are different assertions: an existence bound does not itself supply the algorithm. [Hoberg and Rothvoss](https://arxiv.org/abs/1503.08796) give a logarithmic additive guarantee.

Such results could tighten packing of equal-capacity banks or storage containers and estimates of unavoidable slack. Ordinary bin packing has no lifetimes or cross-bin contiguity requirement. It therefore does not directly solve [size-class waste](../spec.md#r-08-018b), elastic-heap fragmentation, or the full physical placement problem.

### Strong, or prefix, Komlós conjecture

**Named conjecture; conditional resource-balancing connection.** For every fixed ordered sequence of vectors `v_i` in `R^d` with Euclidean norm at most one, can signs `epsilon_i` be chosen so that every prefix sum has maximum-coordinate magnitude at most a universal constant, independent of both sequence length and dimension? The signs may use knowledge of the entire sequence. [Karingula and Lovett's September 2026 preprint](https://arxiv.org/html/2609.20979v1) explicitly leaves this stronger question open; [earlier prefix-discrepancy work](https://arxiv.org/abs/2111.07049) supplies its algorithmic context.

If a composition's legal binary assignments admit this vector model, a constructive theorem could bound accumulated imbalance across several resources at every phase, potentially reducing [buffer reservations](../spec.md#r-08-046). Failure would rule out that universal constant. It is not an online dispatch theorem: signs, nonnegative inventory, precedence and per-coordinate capacities all need a faithful interpretation.

### Efficient constant-discrepancy Komlós construction

**Open algorithmic follow-on; recent-proof watch item.** Ordinary Komlós asks for a constant bound on the final signed vector sum, rather than every prefix. September 2026 papers by [Guo, Fang and Lu](https://arxiv.org/abs/2609.11189) and [Karingula and Lovett](https://arxiv.org/abs/2609.20979) announce proofs. The latter gives a finite construction for rational inputs but explicitly does not establish polynomial running time. Ordinary Komlós and its Beck-Fiala consequence should therefore not be presented here as uncomplicated, untouched open conjectures.

The remaining constructive question is whether a polynomial-time algorithm finds such a constant-discrepancy signing. That could make multidimensional balancing useful inside the [offline composer](../implementation/placement-search.md), subject to a reduction from actual legal decisions. The recent existence claims remain literature evidence, not machine-checked platform results, and do not imply a feasible memory layout.

### Euclidean Steinitz conjecture

**Named conjecture; conditional buffer connection.** Given vectors of Euclidean norm at most one whose total is zero in `R^d`, is there a permutation for which every partial sum has norm `O(sqrt(d))`, with a universal constant? The general assertion remains open in [2026 work on Steinitz constants](https://londmathsoc.onlinelibrary.wiley.com/doi/10.1112/mtk.70085). [April 2026 algorithmic progress](https://arxiv.org/abs/2604.13355) achieves the desired scale in restricted dimensional regimes.

Production and consumption operations can sometimes be modeled as signed resource vectors. A suitable ordering could reduce temporary inventories in [joint scheduling and memory planning](static-memory-research.md#certified-offline-placement-and-joint-scheduling). An arbitrary permutation is not necessarily executable: dependencies may prohibit it or it may consume unavailable data. The result would require a legal ordering, a baseline inventory, and translation of the norm bound into the exact capacities charged by admission.

### Three identical processors with unit jobs and precedence

**Open complexity classification; conditional static-scheduling connection.** For unit-duration jobs with arbitrary precedence constraints on exactly three identical processors, is minimum makespan computable in polynomial time, or is its decision version NP-hard? This is the classical `P3 | prec, p_j=1 | C_max` problem. [Nederlof, Swennenhuis and Węgrzycki](https://arxiv.org/abs/2312.03495), published in [ACM TALG in 2026](https://doi.org/10.1145/3785365), make subexponential progress without closing the classification.

An efficient exact algorithm could improve [static schedules](../spec.md#r-07-013) for a matching restricted reaction graph; hardness would clarify scaling limits. Real workloads add varying WCET, communication, labels and recurring deadlines. Arbitrarily splitting a job into unit pieces would introduce preemption or migration that the original service may not permit.

### Unrelated-machine makespan approximation

**Open approximation problem; conditional heterogeneous-core connection.** Each job has a processing time `p_ij` on machine `i`; assign each job to one machine to minimize the greatest total assigned processing time. The general polynomial-time approximation frontier has a factor-two algorithm and hardness below `3/2`. Improving the general factor-two guarantee and identifying the optimal threshold remain unresolved; see [the 2025 scheduling study](https://ora.ox.ac.uk/objects/uuid%3A0e0229d0-ca8a-473f-955d-a75a5ebaae66/files/r3b591b19x) and [2026 work](https://arxiv.org/html/2606.13133v1).

This resembles assigning compatible work to [scalar, vector and matrix cores](../implementation/compute-compatibility.md), so progress could reduce the most heavily loaded core or required core count. Fixed-machine-count special cases already have stronger algorithms. Neither the general ratio nor a prediction-assisted result covers the platform's full dependency, slot, label and fabric constraints.

### Pinwheel scheduling certificates and complexity

**Open complexity questions; conditional repetitive-service connection.** Task `i` needs one unit of service in every `a_i` consecutive slots, forever, on one server. Does every feasible instance have a polynomial-size certificate checkable in polynomial time, placing feasibility in NP? Is general feasibility PSPACE-complete? [ICALP 2026 research](https://drops.dagstuhl.de/storage/00lipics/lipics-vol374-icalp2026/html/LIPIcs.ICALP.2026.122/LIPIcs.ICALP.2026.122.html) identifies these unresolved questions. A periodic schedule can exist without an explicitly written period having polynomial length.

Compact certificates could help express maintenance or replenishment cadences without enormous schedule tables. This model omits WCET variation and the complete [schedule contract](../implementation/contracts/schedule-record.md). The same paper notes a new NP-hardness claim; the open entry here is certificate size and exact classification, not an unqualified claim that NP-hardness is still unknown.

### Small Set Expansion conjecture

**Hardness conjecture; direct connection to limits on memory optimization.** Roughly, for arbitrarily small fixed error there is a sufficiently small fixed set-size fraction for which it is NP-hard to distinguish a regular graph containing a set of that size with almost no escaping edges from one where every set of that size has almost all edges escaping. [Raghavendra, Steurer and Tulsiani](https://arxiv.org/abs/1011.2586) state the formal hypothesis and its relation to Unique Games.

Assuming it, [Austrin, Pitassi and Wu](https://arxiv.org/abs/1109.4910) derive constant-factor inapproximability for several layout problems and one-shot pebbling, where intermediates must be retained until their consumers run and recomputation is forbidden. This is a concrete barrier relevant to [lifetime and execution-order optimization](static-memory-research.md). It motivates restricted graph families and checked instance-specific search. It says neither that all real workloads are hard nor that ordinary fixed-lifetime contiguous placement has exactly the same lower bound. Disproving the conjecture alone would not provide a better planner.

## Proofs, verification and compilation

### P versus NP

**Foundational conjecture, usually stated `P != NP`; direct connection.** Can every decision problem with polynomial-size, polynomial-time-checkable witnesses also be decided in deterministic polynomial time? [Clay's official problem page](https://www.claymath.org/millennium/p-vs-np/) continues to list it as unsolved.

A constructive equality could transform exact finite packing, schedule synthesis, bounded superoptimization and proof search with an explicit polynomial witness bound. A separation would establish worst-case limits. Input encoding matters: a numerically enormous schedule is not a short certificate merely because its duration has few binary digits. Polynomial algorithms can also have unusable constants or exponents.

Neither answer decides unrestricted termination, arbitrary program equivalence or every theorem. `P != NP` is not a proof of cryptographic one-wayness; `P = NP` would defeat the usual asymptotic one-way-function definition. The [resident toolchain](../spec.md#r-13-027) would still produce artifacts checked by existing admission mechanisms.

### NP versus coNP and short propositional proofs

**Foundational conjecture, usually stated `NP != coNP`; direct certificate connection.** Is there a sound, complete, polynomial-time-checkable propositional proof system in which every tautology has a proof polynomial in its formula length? Existence of such a polynomially bounded system is equivalent to `NP = coNP`, by [Cook and Reckhow](https://www.cs.toronto.edu/~sacook/homepage/cook_reckhow.pdf). Strong proof-size lower bounds remain a subject of [current research](https://eccc.weizmann.ac.il/report/2025/080/download/).

Equality could permit uniformly compact certificates for finite Boolean validity or unsatisfiability. It would not promise efficient discovery, a compact encoding of an entire physical system, or short proofs in this repository's particular logic. Inequality would mean that every such propositional system has hard families. This matters to proof artifact storage and checking budgets, while [the proof kernel](../assurance/cic-checker-qualification.md) remains responsible for each accepted claim.

### A p-optimal propositional proof system

**Open existence question; conditional certificate-interface connection.** Does one Cook-Reckhow proof system polynomially simulate every other, with polynomial-time translations and bounds allowed to depend on the source system? [Egidy's 2026 paper](https://arxiv.org/abs/2602.02294) studies barriers around this unresolved question; [Krajíček](https://arxiv.org/abs/2104.04711) connects it to optimal proof search.

A constructive positive answer could inform a common representation for certificates from heterogeneous solvers. This is relative efficiency, not a promise that every theorem has a short proof. It is also not the weaker notion of an optimal system that only bounds translated proof length without requiring an efficient translation. The [portable proof workflow](../assurance/proof-assistance.md) would still need concrete reconstruction, assumption auditing and a qualified checker; the conjecture authorizes none of those changes by itself.

### P versus PSPACE

**Foundational conjecture, usually stated `P != PSPACE`; direct finite-state connection.** Can every problem decidable with polynomial working space also be decided in polynomial time? It remains unresolved. [Williams's 2025 time-to-space simulation](https://arxiv.org/html/2502.17779v1) is a major partial result, not an equality or separation of these classes.

Some reachability and temporal-verification problems over succinctly represented finite machines are PSPACE-complete: the state graph can be exponentially larger than its description. Equality could change the cost of exhaustive assurance for those models; separation would establish limits while leaving restricted methods useful. A finite deployed machine does not make its entire graph affordable to enumerate. Conversely, infinite-state undecidability should not be attributed to a fixed finite configuration. No general Turing-machine simulation supplies the target memory traffic, slowdown or WCET needed for this project's [assurance pipeline](../assurance/coverage-matrix.md).

### P versus uniform NC

**Foundational conjecture, usually stated `P != NC`; conditional parallelism connection.** Does every polynomial-time decision problem admit uniform polynomial-size circuits of polylogarithmic depth, equivalently a suitable highly parallel algorithm with polynomially many processors? See the [University of Illinois complexity lecture](https://www.cs.uic.edu/~block/courses/cs505-spring2025/lecture-18.html). The processor count and uniformity condition are essential.

A constructive equality could expand parallel compilation and analysis. A separation would establish that some efficient sequential computations resist this strong parallelization target. Neither predicts speedup on the finite number of cores and fixed communication grants of [this ensemble design](../spec.md#r-15-171a). Many useful restricted tasks are already parallelizable: [Ganardi and Lohrey](https://arxiv.org/html/2512.19060v1) distinguish efficient parallel register planning for explicit expression trees from harder succinct representations. Ordinary register planning need not wait for a resolution.

### Derandomization: P equals BPP

**Named complexity conjecture; conditional toolchain connection.** Every bounded-error randomized polynomial-time decision procedure would have a deterministic polynomial-time counterpart. [Doron, Moshkovitz, Oh and Zuckerman's 2026 work](https://eccc.weizmann.ac.il/report/2026/082/) continues to study the hardness assumptions and overheads of such derandomization.

Useful constructions could remove random choices and probabilistic error from some offline search and analysis, helping reproducibility and deterministic resource accounting. They need not preserve the original runtime exponent. Untrusted randomized search can already be safe when its output is independently checked. Derandomization does not generate secret entropy, replace a physical entropy root, or establish constant-time handling of secrets. Its benefit belongs to the [composer and proof producer](../spec.md#r-13-001c), not to a relaxation of admission.

### Deterministic polynomial-time polynomial identity testing

**Open algorithmic problem; conditional rewrite-verification connection.** Given an arithmetic circuit over an appropriately represented field, decide whether the formal polynomial it computes is identically zero in deterministic polynomial time, with circuit, degree and field-operation costs specified. General derandomization remains open in [2026 PIT research](https://eccc.weizmann.ac.il/report/2026/076/download/).

This could improve exact algebraic simplification and validation of candidate [vector and matrix kernels](../implementation/compute-compatibility.md), reducing dependence on randomized fingerprints. It is narrower than all of `P = BPP`. Formal polynomial equality is not floating-point equivalence, equal trap order, equal memory effects, or equality of machine arithmetic with overflow. Any use in the certifying toolchain needs the actual semantics and the existing theorem-checking path.

## Computational performance and Wasm workloads

These entries concern algorithmic work performed by applications, native services, or offline producers. They are not conjectures that every Wasm interpreter can match native execution. The [selected execution contract](../implementation/contracts/wasm-execution.md) already provides the place to study validated internal representations, fused handlers, bounded whole-loop operations and native-service calls, with effects, traps, authority and polling preserved.

### Exponential Time Hypothesis and Strong Exponential Time Hypothesis

**Related hardness hypotheses; direct limits on exact search.** ETH says that 3-SAT has no `2^o(n)`-time algorithm in its number of variables. SETH makes the stronger quantitative assertion that for every fixed improvement below base two, some fixed clause width prevents that improved exponential runtime for `k`-SAT. See the [original exponential-complexity research](https://www.sciencedirect.com/science/article/pii/S0022000000917276) and [SETH formulations and consequences](https://arxiv.org/abs/1112.2275). The deterministic or randomized algorithm model must be stated when using a consequence.

These hypotheses constrain some exact scheduling, packing and finite verification methods more sharply than `P != NP`; [2026 high-multiplicity bin-packing research](https://drops.dagstuhl.de/storage/00lipics/lipics-vol374-icalp2026/html/LIPIcs.ICALP.2026.116/LIPIcs.ICALP.2026.116.html) illustrates such a connection. A refutation could improve exponential search without proving `P = NP`. A transfer to the [memory planner](../implementation/portable-memory-planner.md) needs a reduction preserving the relevant size parameter, not just an NP-hardness label.

### Orthogonal Vectors conjecture

**Fine-grained hardness conjecture; conditional guest-workload connection.** For every `epsilon > 0`, there is a constant `c` for which finding an orthogonal pair between two sets of `n` Boolean vectors of dimension `c log n` has no `O(n^(2-epsilon))` algorithm in the stipulated computation model. [July 2026 research](https://arxiv.org/abs/2607.23799) proves restricted circuit and formula results, not the full conjecture.

It underlies barriers for certain exact similarity, string and attention problems. These can matter to inference and applications hosted in Wasm. Connections to [attention complexity](https://proceedings.iclr.cc/paper_files/paper/2026/hash/8a01099096c85890b1d1aff3c6b4ea56-Abstract-Conference.html) depend on dimension, approximation error, magnitudes and other parameters. A refutation would invalidate particular conditional lower bounds, not make every attention variant linear or remove the [resident model's memory traffic](../performance/inference-demand.md).

### Weighted All-Pairs Shortest Paths hypothesis

**Fine-grained hardness hypothesis; conditional graph-analysis connection.** For every fixed positive `epsilon`, there is no `O(n^(3-epsilon))` algorithm for general weighted all-pairs shortest paths on `n` vertices in the stated model, commonly with polynomially bounded integer weights and distances well-defined. [Fischer's STOC 2026 work](https://arxiv.org/abs/2603.27736) studies conditional equivalences around this still-used hypothesis.

Progress could improve graph analyses or min-plus computations if profiling identifies those kernels in the composer or guest applications. This is not a demonstrated current bottleneck. Fast ordinary matrix multiplication does not automatically accelerate min-plus multiplication, and graph-analysis savings do not directly reduce interpreter dispatch overhead.

### Modern 3SUM conjecture

**Fine-grained hardness conjecture; conditional geometry and data-structure connection.** In a specified integer or real-number model, deciding whether three distinct input positions have values summing to zero is conjectured to require `n^(2-o(1))` time in the worst case. The modern claim excludes a fixed polynomial improvement, not every logarithmic improvement below quadratic. See [Dallant and Iacono's 2025 research](https://dipot.ulb.ac.be/dspace/bitstream/2013/398079/3/j47.pdf).

Consequences can constrain exact computational geometry and dynamic data structures used by desktop applications. A refutation could change those algorithm choices. A specific reduction is required before using it to bound [placement](../implementation/placement-search.md), graphics or Wasm performance; numerical representation and the machine model cannot be dropped from the claim.

### Matrix multiplication exponent equals two

**Named conjecture; direct arithmetic-kernel connection.** The conjecture `omega = 2` means that, for every fixed `epsilon > 0`, square matrix multiplication in the applicable algebraic model has an `O(n^(2+epsilon))` arithmetic-operation algorithm. It does not assert a literal `O(n^2)` implementation. An [August 2026 preprint by Dupont et al.](https://arxiv.org/abs/2608.16884) reports further progress without resolving `omega = 2`.

Practical constructions could improve dense inference, graphics and certified native kernels. Constants, scratch space, communication, rectangular shapes and numerical semantics still determine target value. Matrix-vector autoregressive decoding does not inherit the same benefit as large matrix-matrix multiplication. No operation-count theorem removes the cost of reading weights under the [fixed memory grants](../performance/inference-demand.md), or permits numerically different reassociation without an accepted semantic contract.

### Dynamic optimality of binary search trees

**Named conjecture; conditional application data-structure connection.** Does splaying serve every access sequence within a universal constant factor of the best offline binary-search-tree execution in the same model, with the usual initial-state accounting? The broader existence question asks for any online BST with this guarantee. A [July 2026 preprint](https://arxiv.org/abs/2607.18498) gives a near-log-log competitive bound for splay trees, leaving the constant-factor target open.

A proof would strengthen sequence-level efficiency guarantees for adaptive indexes or application maps. A counterexample would delimit the algorithm's universal claim. It would not establish bounded latency for each access: amortized and competitive guarantees can hide an expensive operation. Nor would it justify replacing the project's [storage index](../implementation/comparisons/storage-index.md), whose block traffic, persistence, recovery and endurance have different costs. The most plausible initial consumer is a bounded, in-label application data structure.

### Strong Descartes' Rule over finite fields

**Specialized proposed conjecture; conditional optimizer connection.** There are constants `0 < epsilon, delta < 1` such that, for sufficiently large primes `p,q` with `q` dividing `p-1`, a nonzero polynomial over `F_p` with at most `q^delta` nonzero terms and distinct exponents modulo `q` has at most `epsilon*q` roots in the order-`q` subgroup of the multiplicative group of `F_p`. [Li and Wu, ITCS 2026](https://drops.dagstuhl.de/storage/00lipics/lipics-vol362-itcs2026/html/LIPIcs.ITCS.2026.95/LIPIcs.ITCS.2026.95.html), pose this as Conjecture 9.

The conjecture would improve soundness bounds for randomized identity tests on restricted circuits with exponentiation, motivated by neural-network optimization. Such tests could filter candidate [compute rewrites](../implementation/compute-compatibility.md). They would not replace an exact admission theorem or establish equivalence of floating-point, quantized or effectful execution. This is a narrower research lead than general PIT, not an established platform optimization.

## Security, entropy and reliable communication

For these entries, a negative resolution may be more consequential than a performance gain. A verified implementation can correctly execute a cryptographically weak construction. The [cryptographic premise inventory](../assurance/proof-reuse/crypto.md) distinguishes mathematical reductions, concrete hardness assumptions, ideal-oracle models and attack-cost estimates; those categories remain separate here.

### Existence of one-way functions

**Foundational conjecture; direct assurance connection.** Does there exist a polynomial-time computable function family for which every probabilistic polynomial-time adversary has negligible probability of finding a preimage of the image of a uniformly sampled input? Classical and quantum-adversary formulations differ. See [Barak's public-key complexity survey](https://eccc.weizmann.ac.il/report/2017/065/download/) and [research on deriving one-wayness from NP problems](https://eprint.iacr.org/2021/513.pdf).

Existence would establish a foundation for general computational cryptography; nonexistence would undermine broad classes of encryption, signatures and pseudorandom generation. Neither outcome should be casually equated to a finite-cost attack on a deployed key size. Existence also would not prove this project's AES, hash or lattice choices secure. Worst-case `P != NP` is not known to imply the average-case hardness required here.

### Module Learning With Errors hardness

**Current computational assumption; direct, critical connection.** Over the specified polynomial quotient ring, distinguish `(A, A*s + e)` from `(A, u)`, where `A` is uniform, `s,e` follow the selected small-noise distributions and `u` is uniform. Search formulations instead seek the secret. Parameters, distribution and classical or quantum adversary access are part of the statement. [FIPS 203](https://csrc.nist.gov/pubs/fips/203/final) connects ML-KEM security to Module Learning With Errors.

This bears directly on the selected key establishment and its [qualification contract](../assurance/pq-reference-contract.md). Better attacks could require migration or larger parameters, with memory, bandwidth and crypto-slot costs. Stronger reductions could improve the justification of a margin. A reduction to worst-case lattice problems does not prove those problems hard.

**Status sensitivity:** a [2026 quantum-algorithm announcement](https://eprint.iacr.org/2026/1591) acknowledges correction and dispute; a [September-updated refutation](https://eprint.iacr.org/2026/1693) challenges its required advantage. This is not recorded as an accepted break, and rejecting an attack does not prove hardness. The existing [attack review](../assurance/proof-reuse/crypto.md#what-the-attack-corrections-establish) owns the project's disposition.

### Module SIS and SelfTargetMSIS hardness

**Current assumption family; direct signature connection.** Module Short Integer Solution asks for a nonzero short vector `z` with `A*z = 0 mod q` for a sampled module matrix. SelfTargetMSIS additionally couples the short-vector relation to a hash-derived challenge containing part of the sought solution. Norms, parameters and oracle access must match the security theorem. The [Dilithium specification](https://pq-crystals.org/dilithium/data/dilithium-specification-round3.pdf) distinguishes the assumptions; [FIPS 204](https://csrc.nist.gov/pubs/fips/204/final) specifies ML-DSA.

These assumptions affect generation signatures, attestation and replaceable boot stages. A break can defeat authenticity despite correct implementation. Tighter concrete reductions can improve justified parameter choices, but not automatically reduce costs. A [quantum reduction involving SelfTargetMSIS](https://arxiv.org/abs/2312.16619) already exists under stated conditions; the unresolved matter is hardness and the selected finite-parameter security claim, not the blanket existence of any reduction. See the [lattice premise ledger](../assurance/proof-reuse/crypto.md#lattice-conjectures-and-core-svp-estimates).

### Classical elliptic-curve discrete logarithm and Diffie-Hellman hardness

**Current assumption family; direct classical-hedge connection.** For the selected group, discrete logarithm asks for `a` from `G,aG`; computational Diffie-Hellman asks for `abG` from `G,aG,bG`. These related problems are not interchangeable. Their unresolved hardness here is classical: [Shor's polynomial-time quantum algorithms](https://arxiv.org/abs/quant-ph/9508027) already remove the corresponding asymptotic quantum-hardness claim.

A fast classical attack would remove the classical component's contribution to hybrid key establishment. It need not defeat a correctly proved combiner whose other component remains secure. Improvements in security analysis or arithmetic could alter the cost and confidence of that hedge. The [project's assumption inventory](../assurance/proof-reuse/crypto.md) requires the exact group, game and combiner theorem. This is not an RSA dependency or a claim that a single generic group lower bound proves the selected curve secure.

### Concrete AES pseudorandom-permutation security

**Concrete security assumption family; direct storage and session connection.** Can adversaries with specified resources and oracle access distinguish secret-key AES from a uniformly selected permutation with advantage above the claimed bound? This is a game-indexed quantitative question, not the assertion that AES is impossible to attack. [FIPS 197](https://csrc.nist.gov/pubs/fips/197/final) defines AES; the [GCM security analysis](https://eprint.iacr.org/2004/193.pdf) explains its role in composition.

The [AES-GCM premise dossier](../assurance/aes-gcm-premise-dossier.md) already identifies the unresolved AES-256 forward-PRP premise. Stronger concrete evidence could improve defensible rekeying and data-volume budgets; a suitable attack could invalidate confidentiality or authenticity claims. Correct AES code does not prove pseudorandomness, and stronger AES security does not remove nonce requirements or GCM's finite-message bounds.

### Concrete SHA and Keccak security properties

**Concrete assumption family; direct and partly immutable connection.** Do the selected hashes provide the collision, preimage and second-preimage resistance each consumer needs? Do keyed constructions satisfy their particular PRF, MAC or DRBG games? These are distinct claims with explicit query and resource bounds. [FIPS 202](https://csrc.nist.gov/pubs/fips/202/final) defines SHA-3/SHAKE; [FIPS 205](https://csrc.nist.gov/pubs/fips/205/final) specifies the hash-based signature standard used by the boot design.

Consumers include content addressing, Merkle binding, measured boot, derivation and the ROM's signature verifier. New attacks can reach guarantees that software updates cannot repair in immutable hardware. Stronger constructions or reductions may improve justified signature, verification or randomness budgets. A proof in an ideal-permutation model does not prove concrete Keccak ideal. Fixed keyless hashing also needs careful adversary quantification, as [Rogaway explains](https://www.cs.ucdavis.edu/~rogaway/papers/ignorance.pdf); the [project ledger](../assurance/proof-reuse/crypto.md#idealized-models-and-keyless-hashing) records that boundary.

### Public-key cryptography from arbitrary one-way functions

**Open foundational construction problem; speculative diversification connection.** Does existence of arbitrary one-way functions suffice to construct public-key encryption or secure key agreement? Known black-box barriers exclude broad generic approaches, not every possible non-black-box construction. See [Barak's survey](https://eccc.weizmann.ac.il/report/2017/065/download/) and [limits of random-oracle constructions](https://arxiv.org/abs/1205.3554).

A positive answer might diversify the assumptions available to future session protocols beyond today's structured lattice and classical choices. It promises neither small keys nor practical speed, and one-way functions would still be an assumption unless proved to exist. Any replacement would need concrete security, protocol composition, implementation refinement and the existing [admission and qualification path](../assurance/pq-reference-contract.md).

### Explicit low-error two-source extraction

**Open construction frontier; direct entropy-root connection.** Obtain a deterministic polynomial-time extractor for two independent `n`-bit sources, each with polylogarithmic min-entropy, producing at least one output bit with negligible statistical error `n^(-omega(1))`. The entropy and error requirements must be met together; more output is a further target. [Chattopadhyay and Goodman](https://eccc.weizmann.ac.il/report/2025/075/download/) identify improving low-error two-source extraction as an outstanding challenge.

Better constructions could reduce raw samples, buffers and latency for a specified statistical guarantee in the [TRNG source contract](../hardware/trng-source-model-contract.md). They cannot create missing entropy, prove physical independence or automatically cover quantum side information. The broad `O(log n)`-entropy target at constant error is already achieved by [Li's 2023 result](https://arxiv.org/abs/2303.06802). Building and qualifying a finite instance of an existing extractor is project work, not an unresolved theorem.

### Optimal binary-code rate versus distance

**Open mathematical optimization problem; direct reliability and capacity connection.** Determine `R_2(delta) = limsup_n log_2(A_2(n,ceil(delta*n)))/n`, where `A_2(n,d)` is the largest binary code of length `n` and minimum Hamming distance at least `d`. Exact general tradeoffs remain unknown. See [research on coding bounds](https://chrisjones.space/assets/papers/ho-delsarte.pdf) and [Alrabiah and Guruswami's August 2026 preprint](https://arxiv.org/abs/2608.09347); the latter announces improved upper bounds, not a complete solution.

Constructive progress could reduce redundancy or improve protection within fixed memory and frame budgets. The [hardware ECC and link design](../spec.md#r-15-175) still requires concrete short block lengths, decoding latency, area, failure behavior and a qualified error model. An asymptotic existence bound does not supply a fixed-latency SECDED or DECTED implementation. Capacity under random errors and minimum-distance protection against adversarial errors are different questions.

### Li-Li undirected multiple-unicast conjecture

**Named conjecture; speculative ensemble connection.** For independent unicast sessions in an undirected capacitated network, network coding offers no throughput advantage over fractional routing. [Liu, Que, Li and Li's August 2026 paper](https://arxiv.org/abs/2608.06070) proves further special cases while leaving the general conjecture open.

A proof would delimit coding-based capacity optimization; a counterexample could identify topologies and traffic where coding helps. Applying this to a future [ensemble](../spec.md#r-15-228b) first requires a matching multi-hop network model. A single point-to-point link, directed time-slot graph, multicast, or correlated inference traffic does not automatically fit. Coding would still have to preserve fixed schedules, bounded buffers, session integrity and authority confinement.

## More indirect mathematical opportunities

### Generalized Riemann Hypothesis for Dirichlet L-functions

**Named conjecture; limited offline number-theory connection.** The nontrivial zeros of these L-functions are conjectured to have real part one half. This is stronger than the ordinary Riemann Hypothesis. Its algorithmic consequences include short-witness bounds used in deterministic number-theory algorithms; see [Bach's explicit bounds](https://www.ams.org/mcom/1990-55-191/S0025-5718-1990-1023756-8/S0025-5718-1990-1023756-8.pdf) and [Miller's primality work](https://www.cs.cmu.edu/~glmiller/Publications/Papers/Mi76.pdf).

A proof could remove a hypothesis from some offline field-parameter or witness-search procedures. This is a weak connection to the project's [finite-field arithmetic generation](../implementation/fiat-crypto-emission.md), whose selected constants can instead carry direct finite certificates. Deterministic polynomial-time primality testing already exists without GRH. GRH would prove neither factoring hardness nor the security of this cryptographic suite, and no current runtime speedup is claimed.

### Hadamard matrix conjecture

**Named conjecture; limited representation connection.** For every positive integer `k`, does there exist a `4k` by `4k` matrix with entries `+1,-1` whose rows are orthogonal, so that `H*H^T = 4k*I`? [Glazyrin's August 2026 paper](https://arxiv.org/html/2608.16116v1) identifies this unrestricted real-matrix existence problem as open. Solving particular orders or classifying complex Hadamard matrices does not settle it.

Constructions for more dimensions could broaden orthogonal sign transforms used in signal processing or quantization, sometimes avoiding padding. This is only a possible future representation choice. The [Bonsai assessment](../performance/bonsai2-assessment.md) already names block-1024 Hadamard rotations; that power-of-two transform requires no solution of the conjecture. General existence would not imply an `O(n log n)` transform, better model quality, smaller scratch space or permitted changes to frozen weight semantics.

### Shannon capacity of the seven-cycle

**Open exact-value problem; speculative zero-error coding connection.** For the seven-cycle confusability graph `C_7`, determine `Theta(C_7) = sup_m alpha(C_7 strong-power m)^(1/m)`, where `alpha` is the maximum independent-set size. [Polak and Schrijver](https://arxiv.org/abs/1808.07438) give a constructive lower bound; [August 2026 research](https://arxiv.org/abs/2608.30273) continues to improve constructions without determining the exact capacity.

The general method studies how distinguishable messages can be packed under a specified zero-error confusion model. It could inspire more efficient codes for a matching future channel. No evidence identifies `C_7` as this platform's electrical, storage or fault model. Its exact value would therefore be mathematical background, not an immediate change to [fixed-frame communication](../spec.md#r-15-228b), authentication or ECC.

## Project-specific questions, not established named conjectures

The closest opportunities need not await a famous theorem. The [existing research agenda](static-memory-research.md) owns these questions; this survey does not create another implementation backlog.

- **Exact planning near laminar lifetimes.** In the binary-encoded, unit-alignment, unrestricted-base model, let `k` be the minimum number of intervals deleted to make the lifetime family laminar. Is exact placement possible in `f(k) * poly(input length)` time? What hardness can be shown, potentially even at a small fixed `k`? The [structural analysis](../implementation/static-memory/structure.md) already solves the deletion parameter and gives exact packing for bipartite crossing graphs. The remaining general parameterized problem is different from those solved cases.
- **The deletion-number-two load gap.** In that same model, must every instance with `k = 2` attain its maximum simultaneous load as legal span? The [structural analysis](../implementation/static-memory/structure.md) proves equality for `k <= 1` and for bipartite crossing graphs, and gives a gap at `k = 3`. The remaining `k = 2` question concerns unrestricted crossing graphs, necessarily involving a triangle if there is a gap. A counterexample would not itself prove computational hardness.
- **Compositional public-phase reuse.** Can component certificates establish global safe reuse efficiently without enumerating every state combination, while accounting for asynchronous completion, retained authority and revocation? Existing [phase experiments](../implementation/static-memory/phases.md) do not establish the full implementation theorem.
- **Capacity sharing versus private demand.** Under an explicit observation model, what headroom, padding, public release rule or declassification permits useful sharing without leaking another label's demand? [Lending experiments](../implementation/static-memory/lending.md) give scoped counterexamples. Fixed-tier cross-owner lending remains excluded; this explores changed assumptions rather than an authorized allocator feature. It is not a universal impossibility conjecture independent of the chosen service guarantees.
- **Reclamation-aware scheduling and bounded segmentation.** Do these transformations admit a larger real workload after charging metadata, copy traffic, zeroization, quarantine and deadlines? These are workload hypotheses, not universal mathematical conjectures. The [experiments and byte ledger](../implementation/static-memory/experiments.md) provide the comparison framework.

## Results and misconceptions excluded from the open list

| Topic | Why it is not an unresolved opportunity in the stated form |
| --- | --- |
| Integer-period pinwheel 5/6 density conjecture | [Kawamura's paper and supporting material](https://www.kurims.kyoto-u.ac.jp/~kawamura/pinwheel/) identify a published August 2026 proof. The certificate-complexity questions above remain distinct. |
| Ordinary Komlós and Beck-Fiala discrepancy | September 2026 proof claims require the status qualification given above. The remaining prefix and efficient-construction questions are separately stated. |
| Sensitivity conjecture | [Huang proved it in 2019](https://arxiv.org/abs/1907.00847). It is not an open source of general compiler speedups. |
| Constant-error two-source extraction at logarithmic min-entropy | [Li's result](https://arxiv.org/abs/2303.06802) achieves this target. Lower error and useful finite parameters are separate questions. |
| Universal terminating verification of unrestricted programs | General undecidability is an established limit, not an unproved conjecture that `P = NP` would resolve. Bounded finite-state models and restricted languages require separate analysis. |
| Automatically replacing random oracles with concrete hashes | [Canetti, Goldreich and Halevi](https://arxiv.org/abs/cs/0010019) give counterexamples to that universal inference. A scheme-specific proof and its concrete premises remain necessary. |
| Perfect online packing with no movement, slack or failure for arbitrary requests | Even elementary separated-free-extent examples defeat the unqualified claim. The [allocation baseline](../implementation/static-memory/baseline.md) specifies which waste is placement, reservation or reuse cost; deleting one premise changes the problem. |
| Collatz, Goldbach, Hodge and other famous open problems | No concrete reduction to a present VerifiedOS bottleneck or admission obligation is identified here. Their absence is a relevance decision, not a claim that they cannot ever affect computing. |

## How to use this survey

For allocation work, start with Dynamic Storage Allocation, bin-packing gaps and the project's near-laminar questions. For scheduling, start with the precise job and service models, then test whether discrepancy or ordering results preserve their dependencies. For guarantees, distinguish the cost of finding proofs from their size, checking cost and truth under stated assumptions. For Wasm, profile the selected interpreter and guest algorithms before assigning value to an asymptotic result. For cryptography, maintain the existing concrete premise and attack ledger.

A proposed adoption needs a precise mathematical statement, a matching workload or reduction, and a constructive implementation or checked finite witness. Charge its memory, metadata, communication, initialization, reclamation and worst-case timing; preserve numerical semantics and the authorized information flows. Existing checkers must validate the resulting artifacts. A paper, a heuristic success, or a conjectural ratio supplies none of that evidence by itself.

Refresh status before using an entry in a design decision. Record the actual remaining question when a special case is solved, and distinguish an announced proof, a reviewed theorem, a mechanized theorem and its implementation bridge. This document is a research map; the owning contracts decide whether any result can change the machine.
