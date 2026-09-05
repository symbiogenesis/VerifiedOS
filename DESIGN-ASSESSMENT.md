# VerifiedOS: A Blunt Assessment

Non-normative architectural review. This assesses the design in this checkout, not a working device, a measured processor, or a qualified semiconductor process. The [requirements register](docs/requirements-register.md) governs what the project requires; this review deliberately questions some of those requirements. The existing [critique](docs/critique.md) carries the detailed open agenda. This document gives the product-level judgment without changing the specification. It is not an exhaustive security audit.

## Verdict

**VerifiedOS has a strong security thesis and an unproved product thesis.** The former is capability isolation, artifact-level admission, explicit authority, bounded resources, and a proof chain reaching down to hardware. The latter is that a phone remains useful after giving up most of the mechanisms conventional computers use to accommodate unpredictable work, while depending on a memory process not qualified for this machine.

Those are separate propositions. Success at the first does not establish the second.

My assessment: this is a serious research direction for a tightly provisioned, high-assurance appliance, but not yet a credible commitment to a broadly useful personal computer. The danger is not merely slowness. It is a device that refuses ordinary work, depends on external infrastructure to change its software, and cannot exploit idle resources while the foreground task waits. Every refusal could be perfectly correct under its specification.

**Engineering effort may be declared free. Battery energy, usable capacity, physical latency, manufacturing availability, and a user's patience cannot.** Independent scrutiny is not interchangeable with unlimited project labor either.

The design should preserve its security objectives and become much less protective of the particular mechanisms chosen to achieve them.

## What This Project Is

This is not seL4 with CHERI added. It is a new computer architecture, operating system, binary-admission language, compiler integration, packaging system, and hardware realization program.

- The processor is a bespoke pure-capability RISC-V-derived machine, not a drop-in standard application platform. It removes translation, conventional privilege rings, speculative execution, dynamic prediction, and the cache hierarchy.
- A kernel instance on each core manages statically composed partitions. Capability bounds and permissions carry authority; fixed schedules carry temporal isolation.
- Applications arrive in offline-composed, certified generations. Memory placement, interfaces, and resource reservations are settled ahead of execution.
- Cores with specialized vector, matrix, cryptographic, and other datapaths take over work normally performed by controllers and accelerators with separate firmware.
- Main memory uses SRAM for latency-critical work and oxide-semiconductor gain cells for bulk capacity. Placement is explicit, not a transparent cache hierarchy.
- The intended proof chain connects specifications, source, machine code, ISA semantics, and modeled hardware. Existing models, tools, statement artifacts, and differential tests are real progress, but are not the implemented end-to-end system.

The [crown-jewel inventory](docs/crown-jewels.md), [field bindings](docs/field-bindings.md), and [implementation checklist](docs/implementation-checklist.md) are better indicators of maturity than the length of the security inventory in the [README](README.md). A theorem about a record a file defines is not yet a theorem about the machine that might instantiate it.

## The Biggest Problems

### A Correct Refusal Can Still Be a Product Failure

Static resource ownership gives a strong guarantee: a hostile compartment cannot seize another's allocation. It also means an idle allocation is not necessarily available to the task that needs it.

The [memory plan](docs/spec.md#r-08-012c) cannot borrow another island's banks. A [full pool](docs/spec.md#r-08-047) returns a typed capacity failure rather than growing. The [non-work-conserving schedule](docs/spec.md#r-07-036) preserves other partitions' timing rather than donating unused slots across confidentiality labels. These are deliberate choices, not bugs.

Together they create **reservation fragmentation in both memory and time**. Excellent offline packing does not abolish uncertainty about what a person will do next. Proving that a declared population fits does not prove that its limit is comfortable.

The design has bounded pools, same-label scheduling accommodations, and mode changes. It would be wrong to claim it cannot handle variable input. The objection is that variable demand must fit its predetermined envelope, and resources outside that envelope cannot generally rescue it.

For a fixed communications terminal this can be excellent. For an exploratory personal computer, it is a loss of function, not just a slower implementation of the same function. The README's heading "No wasted memory" is consequently indefensible as an unqualified product claim. It means certain allocator waste is removed, not that fabricated memory is usefully occupied.

### The Performance Headline Overrules Its Own Tables

The [performance headline](docs/performance-estimates.md#headline-total) says accelerated paths bring symmetric crypto and AI inference back to parity-or-better. Its detailed rows do not establish that:

- Large vector-crypto gains explicitly exclude secret operands. The masked datapath handling actual secret-key workloads has no measured throughput figure.
- The matrix gain is a compute comparison against scalar execution. The same document says low-batch inference is bandwidth-bound, so that gain is not a token-rate prediction.
- The graphics row accepts a major loss against a real GPU. Fast vector arithmetic does not make a software renderer equivalent to a contemporary graphics pipeline.
- Several favorable ratios use scalar or software baselines rather than the equipped application processor named as the headline comparator.

**The synthesis is more optimistic than its own evidence.** The row-level qualifications are candid; the headline loses qualifications that determine the answer.

The percentage ranges are engineering judgments, not measurements. Checking their multiplication does not make their premises empirical. Declaring an optimization mandatory does not establish its recovery. Requiring a matrix unit to beat an alternative is an acceptance test, not evidence that a realizable unit meets it.

The project needs absolute results: response time, sustained frame rate, admitted token rate, energy, and recovery time on one simultaneous workload. Relative arithmetic cannot substitute for them.

### The Memory Process Is a Dependency, Not a Component You Can Order

The [two-class requirement](docs/spec.md#r-15-247) is clear. The [macro qualification requirement](docs/spec.md#r-15-247m) is also clear: useful density, retention, latency, and repair behavior must come from a measured macro with its overheads, not an attractive isolated cell. The [bank-count contract](docs/bank-count-dse-contract.md) still needs physical and implementation inputs.

Most bluntly, [R-17-063b](docs/spec.md#r-17-063b) calls the combined process stack "an offering of no foundry." That is not a minor supply-chain inconvenience. It is a central feasibility assumption.

The unresolved problem is the combination: capacity, bank bandwidth, activation current, repair and yield, predictable access, thermal compatibility with logic, and manufacturable integration. A good result on one axis does not establish the others. A fixed constant in Sail can be the name of an unsolved analog system.

Memory is not interchangeable here. Its properties determine the workload roster, schedule, compiler placement, and plausibility of resident local inference. If it disappoints, several layers disappoint together.

### The Executable Model Is Not the Deployable Implementation

**This is a substantial architectural cost, not just an unfortunate build step.** The user's objection is right for important parts of the software: running the convenient reference successfully does not mean the deployable system is nearly finished.

The [implementation plan's lowering discipline](docs/implementation-checklist.md#0-the-discipline-two-languages-two-golden-models) distinguishes these artifacts:

| Artifact | What Executes | What Still Separates It From the Product |
| --- | --- | --- |
| Sail-generated emulator | A host-native simulator of the target machine | The simulator is not a fabricated processor; RTL implementation and its correspondence remain |
| Gallina functional oracle | Extracted host-side Wasm, or the documented OCaml fallback | Its runtime and memory behavior are not the admitted GC-free device implementation |
| Refined GC-free software | CompCert-C implementations for important components, compiled to purecap code | The C implementation must refine the Gallina specification; the plan defers those proofs during bring-up |
| Generated imperative software | Synthesis, arena lowering, and verified DSL compilation where applicable | Generation and compilation need their correctness arguments, but need not create independently maintained source implementations |
| Device image | The same purecap binary on emulator, RTL co-simulation, and FPGA | This identity is valuable: those execution environments do not require separate OS ports |

The strongest accurate criticism is **separate semantic and operational representations, with independently authored implementations in significant paths**, not necessarily two complete unrelated codebases everywhere.

For kernel and storage code, an elegant executable specification may use convenient values and abstract state while the implementation needs explicit layout, bounded storage, ownership transfer, and device effects. The project must maintain both descriptions and their refinement. Optimization can create a third source of difficulty: the easiest implementation to relate to the model may not meet the physical budget.

That creates two ways to fail after the reference works: the real implementation may be too expensive, or the practical implementation may be too difficult to connect to the reference. A change can require a model edit, an implementation edit, and a proof repair. The model's development velocity is not the product's velocity.

There are important limits to the complaint. The Sail emulator already is compiled native host code; it is not slow merely because it is called a model. Running that emulator as the product on commodity hardware would, however, make the host processor, host runtime, and their timing behavior part of a different assurance argument. Similarly, compiling Gallina directly does not automatically supply GC-free execution, bounded allocation, capability enforcement, or the intended timing contract. Those obligations cannot be removed by calling extraction optimization.

Nor is this split unique to VerifiedOS: many verified systems distinguish abstract specifications, executable specifications, and implementation code. What makes the cost acute here is how many layers are new simultaneously and how little of the complete correspondence chain is inherited unchanged.

**The better direction is to minimize hand-maintained semantic duplication.** Prefer an executable, bounded implementation language as the authoritative operational source; derive an abstract model from it or compile it through a correctness-preserving path wherever practical. The existing synthesis and synchronous-DSL routes already pursue parts of this. Use manual refinement where abstraction genuinely earns its cost, not as the default consequence of starting every component in unrestricted Gallina.

A verified bounded runtime, region inference, or specialized restricted Gallina subset could be investigated as ways to reduce the split. None is a free drop-in: predictable memory use, target code quality, runtime correctness, and the no-GC policy must be confronted explicitly. The right comparison is total maintained implementation plus proofs, not just elegance of the host oracle. Do not add another grand compiler project without first demonstrating a small component reaching the device through it.

### Local Simplifications Can Increase Whole-System Risk

A custom capability encoding, custom code encoding, new admission language, modified compiler path, new kernel, and bespoke memory system are not independent simplifications. Each may reduce a local state machine while increasing the correspondence work the project owns.

One proof kernel reduces the trusted implementation of inference. It does not make the specifications and physical assumptions small. A mistake in a shared semantic anchor can be inherited consistently by every proof above it.

The next important milestone is a production-path vertical slice that executes useful work. Documentation gates are valuable, but must not become the easiest visible measure of progress while implementation feasibility remains untested.

## Would It Be Borderline Unusable?

**For ordinary expectations of a phone or laptop, that is a serious risk. For a curated appliance, it is not inevitable.** A slower machine can have excellent interaction if foreground budgets are sensible. Conversely, a fast arithmetic unit cannot compensate for missing applications, incompatible services, capacity refusals, or a long update round trip.

The [first-release floor](docs/spec.md#r-18-004a) is better than a feature list: its activities must coexist on one configuration. But a minimum demonstration is not a representative personal workload. Comfort requires headroom and awkward transitions: a call during camera work, a large incoming object while inference retains context, lost connectivity, a full pool, and an update with durable work pending.

Browser deferral excludes a substantial fraction of ordinary phone workflows. That may be the correct scope reduction, but it makes the first product a specialized communications device rather than a general smartphone replacement.

The [installation rule](docs/spec.md#r-13-001a) makes package changes new generations activated at boot, and the [composer is off-device](docs/spec.md#r-13-001c). That buys whole-image reasoning and an immutable runtime. It also makes a mundane software change a distributed build-and-admit operation. The relevant user-visible cost is not only proof-checking time: it includes network access, composition turnaround, restart, and restoration of declared durable state.

The [no-self-hosting rule](docs/spec.md#r-02-008) makes a development-oriented user dependent on another machine even with an excellent editor and coding-agent interface. Availability of the external build infrastructure becomes part of practical ownership of the device.

Finally, fail-stop is not availability. Correctly refusing corrupt memory, a bad clock state, or an unsafe transition can still interrupt a call. Emergency-call isolation already exists in the specification; that should not be misreported as a missing feature. It does not manufacture coverage, spare physical resources, or availability through faults.

## Is Compatibility Sacrificed Needlessly?

**Some losses are necessary for the chosen guarantees. Others follow from policies stronger than those guarantees require.** The alternatives document often proves that a proposal violates a commitment already selected. That establishes consistency, not that the commitment is the best trade.

### Losses I Would Accept

Unrestricted legacy binaries, arbitrary privileged firmware, unrestricted DMA, and transparent execution of uncertified native code directly conflict with the intended authority and admission model. A stock Linux personality is not a small compatibility patch. Keeping these exclusions is reasonable.

The absence of speculative execution and unrestricted cross-domain resource borrowing also has a concrete security rationale. Neither should be casually restored merely to recover benchmark scores.

### Losses I Would Reconsider

**Source-level APIs are not the same thing as ambient authority.** Bounded adapters for useful library interfaces, explicit-context filesystem APIs, and familiar typed application interfaces can preserve capability confinement. Full POSIX semantics may be inappropriate; refusing useful subsets merely because they resemble existing APIs throws away reusable code without establishing an extra theorem.

**Computing code as data is not executing newly generated native code.** W^X does not by itself forbid a compiler producing an artifact, a local proof search, or execution inside a verified interpreter. The project already [permits compartment-private interpreter caches](docs/spec.md#r-14-008c), explicitly conceding intra-compartment timing variability. The broader ban on local compilation is therefore a resource and product policy as well as a security choice. A bounded local development facility would require new work and admission constraints, but is not logically incompatible with capability isolation or immutable executable memory.

**An external authenticator is not necessarily a platform protection authority.** The [roaming-key exclusion](docs/spec.md#r-12-020) avoids firmware and parser exposure, but a bounded, capability-confined protocol client need not give the key access to platform memory or control. The key's behavior would remain outside the platform's end-to-end theorem, especially for credentials it holds; that is an honest external-service boundary, not automatically a failure of platform isolation. A separate possession factor also has value the built-in authenticator does not reproduce, including independence from loss or compromise of this device. The current choice gives that up for a very broad interpretation of "foreign computer."

**Firmware-free does not imply general-purpose software.** A verified fixed-function media block with bounded interfaces could satisfy the core authority and verification goals. The design already admits fixed-function arithmetic, cryptographic, and maintenance mechanisms. Moving another appropriate bounded operation into hardware adds proof work, but keeping it in software adds timing, power, compiler, and scheduling obligations too. Compare the total cost. "No opaque firmware" is a strong principle; "no specialized implementation" is not its consequence.

**A permanent dialect deserves stronger justification than local compactness.** The [narrow capability format](docs/spec.md#r-15-007) has a genuine footprint benefit. The custom instruction representation also addresses real image pressure. Together they forfeit standard binaries, portions of upstream validation, and tooling reuse while adding local representation obligations. That might be worth it, but the relevant comparator is the entire delivered system and its maintenance, not just a smaller field or decoder.

Compatibility supplies independent implementations, testing, replacement components, and accumulated failure knowledge. Losing that diversity can reduce practical assurance even when the trusted code count falls.

## The Memory Question

### More-Transistor SRAM Is Cleaner, Not a Capacity Solution

Your preference is reasonable: a latch-based all-SRAM machine has a simpler retention story than one that also carries gain cells, refresh, and discharge sequencing. Read-decoupled SRAM cells can improve read stability and minimum operating voltage. Depending on topology and process, that can reduce energy.

But a higher transistor count is not a free improvement in either power or speed. It usually consumes more cell area; extra ports, longer lines, sensing choices, and periphery matter. A voltage reduction can repay the area in energy for one operating point and fail to do so at another. The current [low-leakage discussion](docs/performance-estimates.md) itself qualifies both density and access speed.

**All-SRAM becomes an excellent answer by choosing a workload that fits it, not by assuming better SRAM circuits will deliver dense-memory capacity.** A bigger latch does not solve a shortage of bits. Stacking latches on this particular monolithic process also needs complementary-device manufacturing that the [first-class grading](docs/spec.md#r-15-173a) does not treat as solved.

That does not prove all-SRAM impossible. It means the current product floor and physical restrictions do not have a demonstrated all-SRAM realization.

### Flat Addressing Is Not Uniform Physical Cost

A large SRAM is not a register file scaled up. Decoders, wires, bank arbitration, ECC, and the interconnect remain. One memory technology does not give every physical location the latency of a small nearby SRAM.

Uniform latency can be purchased by padding to a worst case. That simplifies reasoning while potentially slowing the common case. Alternatively, explicitly banked local memories and fixed access classes expose geometry without introducing transparent caches. The latter is less visually elegant and may be much better engineering.

Separate three questions: one capability-addressed space, one cell technology, and one latency contract. None entails the others. The undesirable thing is uncontrolled, hidden, history-dependent behavior, not the mere existence of more than one physical cost.

### Two Classes Are Not the Main Offense

Explicit SRAM plus bulk storage can be a sensible architecture. It does not automatically imply cache replacement, coherence, dynamic migration, or a second authority model. In that respect the existing design is better than the phrase "multiple tiers" suggests.

Its problem is the combination of an unqualified bulk technology, rigid placement, missing absolute performance evidence, and an insistence on preserving the physical restrictions even when they might defeat the product. **Two proven memory classes would be a better product foundation than one hypothetically perfect class.**

The gain-cell compromise also spends real security properties. [R-17-058f](docs/spec.md#r-17-058f) explicitly leaves a power-off plaintext remanence window without a confidentiality construction. [R-17-058e](docs/spec.md#r-17-058e) books refresh-related power and near-field leakage. Erasing capability tags prevents stale authority from being used by the machine; it does not erase the plaintext a physical observer might recover.

The [no-trust-gradient wording](docs/spec.md#r-15-247s) is defensible for architectural authority checks, which are shared. It must not be read as equal physical confidentiality. The residuals explicitly say otherwise.

### Capacity Has More Than One Ceiling

The [36-bit space](docs/spec.md#r-15-002a) is an encoding limit. The [product limit](docs/spec.md#r-15-002c) includes both memory classes and non-memory apertures. Fabricated usable bits, bits available to a particular island, and bandwidth available to its workload are different limits again.

Widening the address field alone supplies no cells, no bandwidth, and no energy. Conversely, restricting one fabrication proposal today is not a physical proof that a permanent address-width restriction will remain sufficient. The register itself calls model-size sufficiency a bet.

The wider-format option is costly because it gives back pointer density and changes representation and tooling. But this is an unreleased design: reconsidering it now is not a migration crisis involving an installed population. Future growth should be judged before the format becomes an actual deployed commitment.

### The Most Promising Escape Routes

These are alternatives to evaluate, not claims that they preserve every current axiom.

| Option | What It Preserves or Improves | What It Costs | Judgment |
| --- | --- | --- | --- |
| Smaller workload on qualified all-SRAM | Simple retention, no bulk refresh, fewer physical assumptions | Smaller local models and less application breadth | Best near-term demonstrator; reduce scope openly |
| Explicit bulk store for public immutable weights | Keeps authority-bearing working state local; external data can be checked against a signed root | Transfer bandwidth, verification buffers, stalls, and visible access patterns | Strongest candidate for capacity with a limited confidentiality concession |
| Encrypted, authenticated mutable external bulk | More capacity without giving external memory authority over plaintext or capability validity | Freshness metadata, crypto throughput, access-pattern exposure, and more proof work | Serious alternative, not a free substitute |
| Separate SRAM dies with a protected interface | Keeps latch-based storage and separates fabrication choices | Density and leakage remain; link and packaging obligations return | Manufacturability option, not an automatic capacity or power cure |
| Public weights in suitable read-mostly nonvolatile storage | Avoids treating publicly available model weights as secret volatile state | Read bandwidth, endurance where writes occur, interface behavior, and image integrity | Worth testing as a weight store, not assuming suitable as general RAM |
| Quantization, smaller models, shorter contexts | Less traffic and storage under the present architecture | Quality and functionality; application state still needs capacity | Low-mechanism lever, but measure actual usefulness |

For public weights, require authentication before consumption against a trusted model identity. Do not import executable authority or hardware tags from an external store. Keep keys, trusted metadata, and small verification buffers on-die. Use bounded explicit transfers, not transparent demand paging.

There are real limits. With sparse or expert-routed inference, addresses can reveal prompt-dependent behavior even when the fetched weights are public. A fixed transfer schedule or fetching a larger public set can reduce that leak while spending bandwidth. Confidential KV state and user-derived media do not inherit the public-weight argument. An untrusted store can always deny service; hard deadlines need buffering, redundancy, or a separately established delivery bound.

For mutable confidential bulk, encryption alone is insufficient: integrity, freshness, address binding, and atomic updates of data and metadata matter. A bounded explicit store can avoid rebuilding a general MMU and cache hierarchy, but it still adds a substantial verified subsystem. It may nevertheless be a smaller total dependency than a new memory process.

The existing [memory-cryptography discussion](docs/spec.md#r-17-059a) already recognizes a threat window where a key can disappear before bulk plaintext decays. That is a reason to compare an authenticated-encryption design concretely, not to assume the current unencrypted bulk policy dominates every alternative.

**My preferred experiment is public immutable bulk first, not general external RAM.** It tests the flagship capacity demand with the least authority and confidentiality baggage. It conflicts with the present physical topology, so adopting it would change the architecture. It need not abandon the central CHERI and proof-carrying-software thesis.

### Fitting a Model Is Not Serving It Well

For dense low-batch decoding that reads the participating weights each token, a first-order bound is:

$$
\text{tokens per second} \leq
\frac{\text{sustained bandwidth granted to inference}}
     {\text{weight bytes read per token}}
$$

KV traffic, dequantization, scheduling, and other overheads make the achieved result worse than this idealized bound. Batching, reuse, sparse models, and different algorithms change the denominator and must be assessed on their own behavior.

More matrix operations per second do not move a bandwidth ceiling. More banks can improve bandwidth but cost periphery, current, and capacity efficiency. Quantization helps directly, but its accuracy and decoding costs cannot be wished away. The desired artifact is a useful model delivering an acceptable response rate within a sustained power budget, not a memory capacity or TOPS figure.

## Other Obvious Overclaims and Weak Arguments

**"Nothing for timing to leak" is too broad.** The README's memory highlight omits the bank-address term and the need for secret-address rejection that its later table correctly states. Fixed per-class access latency eliminates particular history-dependent channels, not all timing leakage, control-flow variation, or physical emissions.

**Exact subobject bounds are not supplied automatically by the tag.** The README's hardware-only overflow description needs the [bounds-precision qualification](docs/spec.md#r-15-007c) and the layout and typing obligations that compensate for representability. CHERI checks the represented bounds; making them correspond to the intended object is additional work. This is not evidence that the whole stack is unsafe, but it is evidence that the hardware-only explanation is incomplete.

**ECC does not mean arbitrary corruption is never silent.** A finite-distance code can miss some larger error patterns or miscorrect outside its guaranteed fault model. Interleaving and scrubbing reduce risk under spatial and temporal assumptions; they cannot make every multi-bit event correctable. The README's "never silently" definition of detection needs its stated fault-model boundary. The issue is not specific to gain cells.

**Known latency does not make latency hiding irrelevant.** The [non-speculative out-of-order discussion](docs/architectural-alternatives.md) overstates the claim that compile-time knowledge settles the issue. Knowing that a load takes a fixed time does not create independent instructions to fill it, reveal every runtime dependency, or remove register and window limits. The extra verification cost can justify rejecting dynamic scheduling; claiming that a deterministic SRAM removes the underlying latency problem is a weaker argument than that genuine cost argument.

**A verified primary is not immune to all reasons for an independent backstop.** Removing duplicate protection can shrink the implementation and its proof obligations. It does not remove specification mistakes, model mismatch, fabrication defects, or every transient fault. A second mechanism may share failures and may not earn its cost, but that is a fault-domain analysis, not a consequence of the word "verified." This is not a recommendation to reintroduce an entire MMU as a precaution.

**The shell wording is contradictory at the overview level.** The README promises a shell, then says "There is no shell" in its injection row. The intended distinction is a typed command interpreter versus string-to-process shell execution. That is a useful design distinction obscured by an absolute claim.

**Naming a cost does not pay it.** Booking a residual is much better than hiding it. It does not establish that the residual is tolerable in the proposed deployment. Similarly, a proof gate refusing an unusable composition is sound behavior by the gate, not success by the product.

## What I Would Change First

1. **Build a small production-path vertical slice.** Boot the actual GC-free device implementation, exercise a capability transfer, a bounded persistent operation, a failure and restart, and a timing budget. Run the same binary in the model and against the corresponding RTL. Include a real refinement result, not only a satisfiable statement of the desired relation.
2. **Prove the product envelope before expanding it.** Measure representative interaction and simultaneous workloads with explicit acceptance limits for energy, sustained heat, latency, and capacity failures. Include update turnaround and offline operation. Treat these as rejection gates, not descriptive figures.
3. **Reduce model-to-implementation duplication.** Demonstrate one repeatable generation or verified-compilation path for a useful class of components. Compare its total maintained source and proofs with manual Gallina-to-C refinement before standardizing either pattern broadly.
4. **Run a genuine memory comparison.** Compare a smaller all-SRAM product, the current gain-cell design, and SRAM plus explicitly authenticated public bulk. Hold useful workload, physical threat claims, sustained energy, and implementation maturity visible. Do not disqualify the alternatives merely because the present topology says they are forbidden.
5. **Reopen restrictions that are product policy rather than necessary isolation.** Bounded source-compatibility interfaces, local code-as-data workflows, and confined external authenticators deserve an explicit marginal-cost assessment. Keep uncertified native execution and ambient authority excluded.
6. **Stop presenting specialization as a security failure.** Evaluate small verified fixed-function blocks when software threatens the mobile budget. Demand bounded semantics and interfaces, not that all useful acceleration wear the shape of a general-purpose core.
7. **Repair the summary claims.** Align the performance headline with its own scope restrictions, and the README with the bounds, fault-model, memory-utilization, and interpreter qualifications already present deeper in the corpus.

## Bottom Line

The strongest idea here is a capability-confined, proof-admitted machine whose authority and resource use are explicit. The weakest idea is that the cleanest local restriction must remain the best global architecture after enough other restrictions have accumulated around it.

**Higher-transistor-count all-SRAM is the cleaner memory design if the useful workload fits. It is not a demonstrated escape from the capacity constraint. Two explicit memory classes are not intrinsically a mistake. Making an unqualified one mandatory while closing off mature physical alternatives is the much larger gamble.**

The golden-model concern belongs beside that memory gamble: the convenient thing you can execute is not automatically the thing you can ship, and the distance between them contains much of the project's hardest work. Minimize that distance before multiplying the components that must cross it.

I would proceed with a smaller, measurable appliance and a real implementation chain. I would not yet promise a general personal computer, and I would not accept architectural purity as sufficient justification for a device that cannot comfortably perform the work used to justify building it.