# Evaluated Architectural Alternatives (non-normative)

> Externalized from [verification-maximal-os.md](verification-maximal-os.md).
> This document records evaluated architectural alternatives and their disposition; it is **not** part of the normative spec.
> Cross-references of the form §N point to sections of that specification.

It exists so the living document carries the reasoning behind what was *not* adopted.

## Belt / Mill-class architecture: deferred to a hypothetical gen-2, on one ground

Mill's security features were run through the §15 admission test and the import discipline:
- **Protection ≠ translation, turfs, portal calls (PLB separate from TLB)**: Mill's headline model is **already subsumed by CHERI**, and more generally: capabilities bound memory irrespective of page tables, and sealed-capability domain crossing is the portal. The spec converges on Mill's single-address-space-with-per-domain-protection vision from a substrate that has a formal model (Sail, Cerise) Mill lacks: a convergence the base makes literal by deleting the MMU outright (below), so protection is by capability alone and there is no translation to separate from.
- **Backless memory / implicit zero-on-allocate**: elegant, but *fails the admission test*: read latency depends on whether a page has been written (a data-dependent timing signal about allocation state).
  The security goal (no uninitialized-memory disclosure) is already met by eager-zeroize + `cbo.zero`; importing the mechanism would add a channel the spec forbids.
  Its rejection is the admission test working correctly.
- **The spiller (secure call/return; return addresses unreachable by code, structural anti-ROP)**: a genuine win, but **inseparable from the belt**; the RISC-V analog is a hardware shadow stack, which §15 excludes as retrofit complexity.
  Logged as an intrinsic belt advantage, not a base import.
  (Note the static-prediction/no-RAS decision makes call/return relatively more expensive on the base, marginally sharpening the spiller's *performance* appeal, but not its importability.)
- **The belt itself** contributes less security than the framing implies: its wins are ILP and register-file-elimination hygiene, while the *security* comes from turfs (→ CHERI) and the spiller.

**Net for the base spec:** nothing imports into the normative body: the relevant *security* ideas are already present via CHERI, and the rest is inseparable from the belt.

**The one non-redundant gen-2 argument is ILP without speculation.**
The in-order scalar cores pay a large IPC tax for the no-speculation guarantee (and an additional forward/indirect-branch and call/return tax for the no-dynamic-prediction guarantee).
A Mill-style machine recovers wide ILP through exposed, statically-scheduled parallelism plus **metadata speculation**: NaR ("Not a Result") poison values let loads be hoisted and only fault when consumed, giving speculative *scheduling* benefit with **no microarchitectural rollback and therefore no transient-execution class**: the same security posture at higher ILP.
Counterweights: (1) even ignoring verification *effort*, a belt gen-2 means rebuilding the entire substrate this spec depends on: RISC-V Sail model, CHERI-CompCert backend, Islaris, Cerise, RVV; none of which transfers; "ignore verification effort" does not make the ecosystem exist.
(2) If leaving RISC-V anyway, the belt may not be the most spec-coherent target: **EDGE / block-atomic execution** (TRIPS/EDGE lineage) issues dataflow blocks that **commit atomically as a unit**: instruction-level transactionality, a direct downward extension of G4 and §11 all the way into the pipeline.
A belt is a clever operand-lifetime trick; block-atomic execution *rhymes* with the rest of the architecture.
EDGE is even less mature than Mill, so it is a research program, not a spec.

**Disposition:** gen-2 candidate iff ILP-without-speculation becomes the binding constraint and a formal/toolchain ecosystem can be built around the target; **block-atomic (EDGE) is the preferred "abandon the register file" direction** over the belt for this design, on transactional-coherence grounds.
Both remain non-normative.

---

## Itanium / EPIC / VLIW: ILP without a belt, but the substrate cost *is* the belt's; the one importable atom is already NaR

"Itanium-style VLIW" is not one mechanism but four separable ones, and the import discipline resolves them individually against the §15 admission test: the same decomposition that logged the belt's spiller while rejecting its backless memory.
The premise (recover in-order ILP without a belt and without leaving RISC-V) is only half-answerable: **EPIC is a distinct ISA, not a RISC-V extension**, so its bundle substrate abandons the platform exactly as the belt does, and into a *deader* ecosystem; IA-64 was discontinued in 2021 and dropped from the Linux kernel, so there is no Sail model, no CHERI-IA64, no verified CompCert backend, no Cerise, no RVV analog to inherit.
The counterweight (1) written against the belt, "rebuilding the entire substrate this spec depends on," applies verbatim and harder: a belt is at least live research; EPIC's ecosystem is post-mortem.

Run the four ingredients through the admission test:
- **Static bundling (the VLIW core: template/stop bits, explicit issue groups)**: the genuine ILP source, and microarchitecturally it *passes* on the no-hidden-state axis (no rename, no reorder buffer, no scoreboard).
  But it is a new instruction encoding, not an extension of RV64: the substrate cost above is entirely this bullet's; and its scheduling dividend is *already banked* by the base being in-order: the §15 C-class is **in-order single/dual-issue** already, so widening in-order issue and letting the bespoke CompCert/SECOMP scheduler pack independent operations recovers most of the ILP **with zero ISA change and zero substrate cost**.
  VLIW's distinctive hardware win over an in-order superscalar (deleting the interlock/scoreboard) is marginal, and does not survive its own binary-portability curse (below).
- **NaT / control speculation (deferred-fault poison loads)**: **the one importable atom, and the belt entry already banked it under another name: NaR.**
  Itanium's NaT bit *is* metadata speculation: hoist a load, and on a deferred exception set poison and trap only at consumption, with **no microarchitectural rollback and therefore no transient-execution class**.
  It *passes* all five (architecturally-visible poison, deterministic, Sail-expressible, no hidden shared state, no autonomous behavior), and (the load being architecturally completed) carries data-independent latency, clearing test (2) besides.
  Crucially it is **separable from the bundle**: NaR/NaT can be a *small* RV64 extension (a poison tag bit + a speculative-load + a check/consume op), lifted out of both the belt and EPIC and dropped straight into RISC-V.
  Its residual is exactly the one already accepted for wrong-path static fetch (§15, "Control-flow prediction"): a hoisted load's cache footprint is a deterministic function of the compiler-fixed instruction stream, not of learned history, so it falls in the cache-partitioning/`fence.t` bucket, the sole caveat being that a *secret-dependent* speculative address is an ordinary `Zkt`/`Zvkt` flow-label obligation, no different from any load.
- **ALAT / data speculation (advanced loads hoisted over possibly-aliasing stores)**: **fails the admission test, twice.**
  The ALAT is a hidden microarchitectural table whose occupancy records which speculative loads are outstanding and whether a later store aliased them: new hidden shared state surviving a partition switch (test 3) and a data-dependent load↔store aliasing signal (test 2).
  It is the same shape as the LR/SC reservation set and the dynamic predictors §15 *deletes* rather than flushes; its rejection is the admission test working correctly.
- **Full predication (predicate register file, near-universal guarding)**: double-edged, and the spec already took the admitted half.
  Converting branches to predicated dataflow *would* erase the forward/indirect-branch and call/return penalty the static-only-prediction posture pays, and predicated-off timing is fixed (constant-time-friendly); but full predication is an enormous ISA-surface addition to a profile that *deleted the C extension* purely to buy unambiguous 4-byte decode, and it would inflate the Sail model, the RTL ⊑ Sail proof, and CHERI integration.
  The **minimal** form of exactly this idea is already adopted: `Zicond` (branchless select), "doubly load-bearing" for precisely this reason; full predication is its un-admitted maximal cousin.
- **Register rotation + the Register Stack Engine (RSE)**: **fails hardest.**
  The RSE spills and fills the register stack to memory *autonomously* at data-dependent moments: an autonomous memory-writing engine (test 5, the same ground the `Svadu` page-walker updater is excluded on, and the MMU deleted with it, below) whose unpredictable traffic falsifies the per-(class, OPP) WCET tables the entire §11/§13 temporal-admission edifice consumes.
  Reject outright; software-pipelined loops fall back to the compiler's static allocation.

**Nothing gets deleted: the load-bearing misconception.**
The hoped-for simplification runs backwards.
The IPC tax the base pays is not the cost of *owning* a verifiable speculation engine VLIW would let it remove: the base is *already* in-order, *already* forbids speculation, *already* forbids dynamic prediction (§15).
**The tax is the price of *forbidding* speculation, not of a removable mechanism.**
VLIW deletes nothing here; it *adds* a mechanism to claw performance back under the forbiddance, and that mechanism *enlarges* the verified surface at every layer: a bigger Sail model (bundles, poison, predication, rotation), a bigger RTL ⊑ Sail proof (already the least-built arrow, §17), CHERI re-integrated against a new encoding, and, decisively, a **verified trace scheduler for EPIC's predicated, poison-tagged, rotating-register bundles**, which Chamois/KVX-CompCert's verified bundle scheduling and software pipelining do not reach, targeting only the far simpler Kalray VLIW; net-new, hard proof.
VLIW's famous dividend, moving scheduling out of hardware into the compiler, is already spent: an in-order core has no hardware scheduler to move.
And the sting compounds: EPIC's own ILP mechanisms (ALAT, RSE) make WCET *worse*, so importing them *costs* §11 determinism.
By the platform axiom this is the wrong trade in the wrong direction: spending the scarce currency (trust, proof surface) to buy the free one (performance).

**Bespoke, microarchitecture-coupled binaries: the disqualifier, not an inconvenience.**
The instinct that VLIW needs specially compiled binaries is right, and it is fatal, on three compounding counts.
(1) VLIW bundles are a distinct encoding, so standard RV64IMV+CHERI binaries do not run: forking the single-recompile-target premise of [userspace-porting.md](userspace-porting.md) (certifying Rust → RV64+CHERI) into two.
(2) VLIW's classic curse: a schedule encodes the *specific* issue width and operation latencies it was packed for, so a pipeline change forces a recompile: re-coupling ISA to microarchitecture, the exact thing RISC-V's abstract contract exists to prevent, and violating §15's "one base ISA, one kernel binary, one parameterized model; classes differ only in datapath" property (a bundle schedule is not portable across the C/V/M scalar front ends).
(3) Every FPCC artifact (the binary-level proofs, memory-safety certificates, and constant-time certificates of §5/§6/§13) is stated *at binary level against the CHERI-RISC-V Sail model*, so a new ISA means restating the Sail model and re-minting every certificate, retargeting the whole Tier-1/2 toolchain.
The bespoke-binary requirement thus re-imports precisely the microarchitecture-in-the-binary coupling RISC-V's abstract ISA was chosen to delete.

**Where EPIC ranks among the "abandon RISC-V for ILP" targets.**
The belt entry already ordered EDGE ≻ belt on transactional-coherence grounds (block-atomic commit *rhymes* with G4 and §11).
EPIC ranks **below both**: its one edge over Mill and TRIPS is that it *shipped*, but it shipped and *died*, so the ecosystem advantage is negative; its ILP recipe leans on ALAT and RSE, which fail the admission test where the belt's spiller and EDGE's block commit do not; and it *rhymes* with nothing in the architecture.
A belt is a clever operand-lifetime trick and EDGE a transactional pipeline; EPIC is a compiler-scheduling bet whose hardware crutches this spec forbids.

**Disposition:** rejected as a base direction: EPIC abandons the RISC-V substrate as fully as the belt (into a post-mortem ecosystem), *inverts* the hoped-for simplification (the in-order IPC tax is the price of forbidding speculation, not a removable engine; VLIW only adds verified surface), and mandates bespoke, microarchitecture-coupled binaries that fork both the ecosystem and the proof base.
**Two non-redundant atoms are distilled and kept inside RISC-V:** (1) **NaR/NaT deferred-fault poison loads**: separable from both belt and bundle, admissible as a *small* extension, the genuine "ILP without speculation" lever, logged here as the sharper form of the belt entry's metadata-speculation argument and the first candidate should that constraint bind; and (2) **wider in-order superscalar + verified static scheduling on plain RV64**: already licensed by §15's *in-order single/dual-issue* C-class and ideally served by the bespoke compiler, the actual answer to "the in-order path is slow," strictly *before* any ISA fork.
Both remain non-normative; **VLIW as a whole imports nothing**, and ranks below both the belt and EDGE as an abandon-the-register-file target.

---

## Minimal-ISA extremes: OISC and transport-triggered architectures; parsimony past the point the substrate and the proof survive

The proposal pushes the profile's own parsimony instinct (deleting the C extension for unambiguous decode, curating `A` to `Zaamo`, folding scalar float onto the vector unit, §15) to its absolute limit: a **one-instruction-set computer** (OISC, a single instruction such as *subtract-and-branch-if-≤0*, from which all computation is synthesized) or a **transport-triggered architecture** (TTA / the MOVE machine: the only operation is a register-to-functional-unit-port move, and arithmetic is a *side effect* of moving operands to a unit's input ports).
The pitch is a decode surface and a formal model small enough to hold on a page: the smallest thing a Sail model and an RTL ⊑ Sail proof could describe.

**The steelman: one real card.**
A minimal ISA is a minimal Sail model, a minimal decoder, and the least surface for the least-built arrow (RTL ⊑ Sail, §18) to refine: exactly the scarce axis the platform spends engineering to shrink, and the same argument that deleted the C extension.

**Why it fails: the EPIC disqualifier, plus an inverted proof-shrink.**
- **It abandons RISC-V for a dead ecosystem: the EPIC/Wasm cost verbatim.**
  OISC and TTA are not RV64 extensions; they fork the CHERI-RISC-V Sail model, CHERI itself, CHERI-CompCert, Cerise, Islaris, and **re-mint every FPCC / memory-safety / constant-time certificate**, all stated *at binary level against the CHERI-RISC-V Sail model* (§5, §6, §13): the exact cost the Itanium/EPIC entry ruled fatal, into an ecosystem with no CHERI, no verified compiler, and no RVV to inherit.
- **TTA re-couples the binary to the microarchitecture.**
  A transport-triggered schedule encodes the *specific* functional-unit ports and latencies it was compiled against, so a pipeline change forces a recompile: the VLIW binary-portability curse (the EPIC entry's third count), violating §15's *"one base ISA, one parameterized model; classes differ only in datapath"* property.
- **Minimal *instruction count* is not minimal *proof surface*: the shrink inverts.**
  An OISC moves complexity out of the decoder and into gigantic synthesized instruction *counts* and control flow; once capabilities, DMA, interrupts, and the timing contract are expressed, the Sail model is not smaller; and the verified compiler must now target a pathological ISA (an OISC has no register file to allocate, a TTA exposes the pipeline the compiler must schedule against by hand), *enlarging* the CHERI-CompCert proof rather than shrinking it, the same inversion the EPIC entry found ("VLIW deletes nothing here; it *adds* a mechanism").

**The distilled atom: already banked.**
ISA parsimony as a proof-shrink lever is the whole §15 curation posture: unambiguous 4-byte decode (no C extension), `Zaamo`-only atomics, no scalar FP, `Zifencei` dropped; extracting *real* Sail-model and decode savings **inside** RV64, where the CHERI / CompCert / Cerise substrate is kept.
The minimal-ISA entries add nothing but substrate abandonment on top of a parsimony the design already practices.

**Where it ranks.**
Beside EPIC on the "abandon RISC-V" scale and below the belt and EDGE: more radical in decode-minimalism than any of them, but into a *deader* ecosystem (OISC/TTA never shipped an application platform, let alone a verified one) and *inverting* the proof-shrink it promises, so it clears none of the bars the belt's spiller or EDGE's block-atomic commit clear.

**Disposition:** rejected as a substrate: OISC/TTA abandon RV64 and re-mint every artifact stated against its Sail model (the EPIC disqualifier), TTA re-couples binary to microarchitecture, and neither actually shrinks the proof surface once capabilities, DMA, interrupts, and timing are modeled; the genuine parsimony atom (minimal decode, curated extensions) is already banked **inside** RISC-V (§15).
The platform axiom decides it as ever (*trust is the scarce resource, engineering is free, delete rather than defend*): parsimony is spent where it shrinks the proof without forfeiting the substrate, not past the point the substrate and the proof survive.
Non-normative; no spec-body change.

---

## Asynchronous (clockless) logic: rejected at the timing axiom; data-dependent latency is the channel the profile is built to forbid

The proposal is to implement the datapath as **self-timed / clockless** logic (delay-insensitive or bundled-data asynchronous circuits with handshake-driven completion) rather than a globally-clocked synchronous pipeline, trading worst-case for **average-case** completion and shedding the clock-distribution network, with lower power and electromagnetic emission as the draw.

**The steelman.**
Asynchronous logic completes in *average*-case time (a carry chain that resolves early finishes early), radiates less (no clock spectral peak), and dissolves clock-tree design: a genuine power/EMI story, and the EMI angle even grazes the side-channel surface the platform cares about.

**Why it is structurally inadmissible here.**
- **Average-case completion *is* a data-dependent timing channel: admission test 2, by construction.**
  A self-timed unit's latency is a function of its *operands* (the early-terminating carry chain, the fast-resolving comparison); that is precisely the data-dependent latency the `Zkt`/`Zvkt` data-independent-timing contract, the constant-time layer (§5), and the whole timing-channel argument (§15, §17) exist to forbid.
  Where the fixed-latency mandate makes timing *independent* of data, asynchronous logic makes it a *function* of data: the direct negation, and a channel that under any secret-touching operation carries the secret.
- **It falsifies WCET soundness at the root.**
  The §11 temporal-admission edifice consumes per-(class, OPP) *fixed-latency* tables made sound to the metal by RTL ⊑ Sail; a clockless datapath has no fixed per-operation latency to tabulate, so its worst case is a separate and harder bound and the average-case dividend is worthless to a worst-case-scheduled, non-work-conserving system (§11).
- **The trade is on the wrong axes.**
  The power/EMI win lands on the freely-spent axis (*performance and efficiency deliberately subordinated*, §2); the cost (a new timing-channel class and a broken WCET model) lands on the scarce one.

**The distilled atom: none in the gates; the one admissible cousin, GALS, is already banked.**
The security posture *wants* latency independent of data, which is the synchronous fixed-latency, in-order, non-speculative profile's defining choice (§15); asynchronous logic *in the datapath* is that choice's structural opposite, so there is nothing to distill from the gates: importing any of it would reintroduce the exact channel the profile deletes.
The one structurally-adjacent idea that *is* admissible (dropping the *single global clock* so the machine is not one lock-stepped timing domain) the design already took, in its **globally-asynchronous, locally-synchronous (GALS)** form: the coherence islands share no coherence and communicate only by message-passing across the TDM NoC (§15), so they are independent timing domains by construction (per-island SRAM banks or macros and per-(class, OPP) operating points already imply the islands need not run at one frequency), yet each island stays *internally* synchronous, which is exactly what keeps its fixed-latency WCET tables and its RTL ⊑ Sail refinement tractable.
The asynchrony is therefore confined to the **island boundary** (ring message-passing with explicit cache-management fences under Ztso, §12, §15) where the sole metastability obligation is the ordinary clock-domain-crossing synchronizer, not a datapath whose latency has become data-dependent.
So the platform already banks the admissible half of the idea (system-level timing-domain decoupling) while rejecting the inadmissible half (data-dependent completion in the logic): **GALS *between* islands, synchronous fixed-latency *within* them**: the split this entry turns on.

**Where it ranks.**
Off the abandon-substrate scale: it is a circuit-implementation style, not an ISA; and it fails for the same reason the dynamic predictor, the LR/SC reservation set, and the EPIC ALAT do: hidden, data-dependent timing behavior the admission test rejects, here one layer below the ISA, in the gates themselves.

**Disposition:** rejected: self-timed logic makes latency data-dependent by construction (admission test 2) and destroys the fixed-latency WCET tables the temporal-admission and timing-channel arguments consume (§11, §15, §17), spending the freely-available power/EMI axis to buy a cost on the scarce timing-determinism one.
The synchronous, fixed-latency, in-order profile is the deliberate opposite, chosen for exactly this reason.
Non-normative; no spec-body change.

---

## Fine-grained multithreading and timing-predictable architectures: PRET, PATMOS/T-CREST, FlexPRET; the non-speculative throughput lever the SMT rejection over-rejected

The profile deletes **simultaneous multithreading** (SMT) uniformly (§15) on admission-test-3 grounds: SMT threads share issue ports, functional units, and caches *dynamically*, so one thread's occupancy is hidden shared state surviving a partition switch that makes the other's timing data-dependent: the co-residency channel.
That rejection is correct, but it kills only *simultaneous* (dynamic-issue) multithreading, and it has been read too broadly.
**Fine-grained (barrel / temporal) multithreading** is a structurally different mechanism: N hardware threads with **replicated per-thread register files**, interleaved onto one pipeline by a **fixed, statically-scheduled round-robin**: thread *t* owns issue slot *t mod N* unconditionally, whether or not it has work.
This is the lineage of the CDC 6600 peripheral barrel, the Denelcor HEP and Tera MTA (Burton Smith), and (shipping, sold on determinism) **XMOS xCORE** (guaranteed-MIPS logical cores for hard-real-time I/O).
It is separable from SMT exactly as EPIC's NaR was separable from the bundle, and the separated form clears the admission test the dynamic one fails.

**The steelman: two real cards, both the platform's own currency.**
(a) **It is the non-speculative throughput lever the belt entry (above) went looking for.**
Interleaving hides load-use, functional-unit, and branch-resolution latency by filling the shadow of a stalled thread with *another partition's* independent work: recovering much of the in-order IPC tax **with no speculation, no dynamic prediction, and no rollback**: the "ILP without speculation" the belt chases through exposed scheduling and NaR, here obtained by temporal interleaving instead.
(b) **It is the platform's timing discipline as a microarchitecture program.**
The **PRET** machine (Edwards & Lee, DAC '07, *precision-timed*, timing a first-class controllable property), **PATMOS / T-CREST** (Schoeberl, a time-predictable multicore whose **Argo TDM NoC** is the design's own §15 TDM NoC by another name), and **FlexPRET** (Zimmer/Broman/Shaver/Lee, a RISC-V fine-grained-multithreaded PRET core) are an entire architecture lineage built around *repeatable, controllable timing*: the property §11 and §15 construct from scratch.
The design is *already a PRET-class machine on the timing axis*, reached from the security side (fixed-latency, in-order, static-only prediction) rather than the real-time side; PRET/PATMOS/FlexPRET are the convergent prior art the WCET entry (below) and the timing profile (§15) should cite.

**Why the static-slot form passes where SMT fails.**
Run barrel MT through the five-part §15 admission test in its *fixed-schedule* form: (1) deterministic: a thread's timeline is a function of its own instruction stream and its fixed slot allotment, nothing else; (2) no data-dependent latency: the schedule being fixed, thread A's stalls **cannot** shift thread B's issue cycles (the inter-thread interference SMT reintroduces is exactly what a static round-robin removes, providing *stronger* temporal isolation than a single fast thread, not weaker); (3) no hidden shared state surviving a partition switch: per-thread register files are architectural and replicated, the slot assignment is a composition-time constant, and threads map to partitions so the interleave *is* the partition boundary; (4) Sail-expressible: thread ID and slot table are architectural state; (5) no autonomous behavior: the round-robin is a fixed counter, not an address-dependent engine.
It is the **pipeline-level analog of the TDM NoC and cache coloring** the design already runs (§15): time-division of one datapath among fixed tenants, which is precisely why T-CREST pairs barrel-predictable cores with a TDM NoC: the same instinct, one level down.
The **dynamic** variant (fill an idle slot with any ready thread, FlexPRET's *soft* threads, SMT's issue logic) reintroduces the data-dependent contention and **stays rejected**; the design takes FlexPRET's *hard-real-time-thread* discipline (every thread a guaranteed fixed slot) for **all** threads and drops the soft-thread slot-filling.

**Where it ranks: the cheapest throughput lever, and it stays in RISC-V.**
It **abandons no substrate** (FlexPRET is RV32; a barrel front end is an RV64+CHERI datapath option, not a new ISA), so it is off the belt/EPIC/OISC "abandon RISC-V for ILP" scale entirely, and it ranks **above** all of them as the *first* non-speculative throughput lever to reach for: it joins the two stay-in-RISC-V atoms the EPIC entry distilled: NaR poison loads and wider in-order superscalar + verified static scheduling; as a **third**, and the most directly latency-hiding of the set, at zero substrate cost and no new proof base beyond a per-thread-state Sail addition.
Its natural home is the scalar in-order cores that actually pay the IPC tax (the V/M datapaths already hide latency through vector length and the systolic array), and its deterministic per-thread interrupt latency (XMOS's selling point) sharpens the §12 hard-real-time tasks, though the sub-slot radio turnaround stays in the fixed-function sequencer (the link-layer-timing entry below), which needs no thread at all.

**The distilled atom: the methodology is banked, the mechanism is genuinely new.**
Following the belt→spiller / EPIC→NaR discipline: the PRET *timing-first methodology* is already present as the fixed-latency profile (§15) ⋈ the timing-annotated Sail model (§11): the design converged on it from security, so nothing imports there but the name and the citation.
Barrel MT *itself* is the one un-banked atom: a real, admissible, non-speculative throughput mechanism the profile has not considered; and, unlike every other performance lever in this document, it is a pure *addition* of Sail surface (per-thread register files, a slot-schedule register), not a deletion.

**Disposition (non-normative; gen-2 throughput candidate + prior-art grounding).**
**Static-slot fine-grained (barrel) multithreading is admissible**: it passes the five-part admission test as the pipeline-level sibling of the TDM NoC (fixed schedule, replicated per-thread state, no inter-thread timing dependence), and is **logged as the first-choice non-speculative throughput lever should the in-order IPC tax bind**: ahead of the belt and any ISA fork, beside the EPIC entry's NaR and wider-superscalar atoms, on plain RV64+CHERI.
**Dynamic-issue SMT (and FlexPRET-style soft-thread slot-filling) stays rejected** (§15): the data-dependent contention the static schedule removes.
**PRET / PATMOS / T-CREST / FlexPRET** are logged as the timing-predictable-architecture lineage the profile's timing discipline (§11, §15) converges on from the security side: the design is a PRET-class machine already, and T-CREST's Argo TDM NoC is its §15 NoC by another name.
The platform axiom decides it as ever (*engineering is free, performance is subordinated*): a throughput lever that buys back IPC (the free axis) without speculation and without leaving the substrate is a gen-2 candidate, not a base move, unless the vector/matrix-memory-latency-hiding case ever justifies banking it at base.
**Honest residual (§17):** barrel MT is the rare performance entry that *grows* the Sail model rather than shrinking it: per-thread register files, a slot-schedule table, and thread-ID architectural state join the model and the partition-switch/flush accounting; admissible only in the fixed-schedule form and only where a partition carries enough independent threads to fill its slots (else they idle, which the non-work-conserving §11 model already tolerates); it buys throughput, the freely-spent axis, so it is booked as a bounded, deferrable extrapolation like the belt, not a standing obligation.

---

## CHERI-Wasm as a hardware ISA: the interface half is already imported (WIT → §12), the execution half is the substrate §14 deletes

"Should the hardware natively target CHERI-based Wasm" bundles three separable proposals, resolved individually against the §15 admission test and the import discipline: the same decomposition that logged the belt's spiller and EPIC's NaR while rejecting the rest.
(1) **Wasm-as-ISA**: the machine's instruction set *is* Wasm bytecode, a structured stack machine executed in silicon; (2) **CHERI-as-Wasm-sandbox**: capabilities enforce a module's linear-memory bound in hardware, deleting the per-access bounds check; (3) **Wasm-as-substrate**: the system's portable deployment/execution format is (CHERI-hardened) Wasm.
Proposal (3) is **already dispositioned**: §14 states *"'WASI-shaped' is API vocabulary, not substrate: everything compiles to native RV64+CHERI… Wasm is not a system execution target,"* and §5 repeats it (*"Wasm/WASI is not an execution target anywhere in the system"*): so lifting Wasm into *silicon* is the maximal form of a decision already made twice, and the only live questions are (1) and (2).

**The steelman: Wasm's three real cards.**
Unlike the belt/EPIC targets, Wasm is not ILP bait; its appeal is orthogonal and genuine.
(a) **It is one of the best-formalized ISAs in existence, and its semantics live in *Coq***: WasmCert-Coq (with WasmCert-Isabelle) carries full machine-checked type soundness, so a single-Coq-prover design that calls specifications the crown jewels (§5) is looking at a target already mechanized in its own prover.
(b) **Linear memory is capability-shaped**: a module's heap is exactly `base + length`, i.e. one CHERI capability, so bounding the sandbox with a cap and deleting the software bounds check is a real, published CHERI-Wasm result.
(c) **Sandbox-by-construction** for untrusted code with no custom silicon.

**Why it fails for *this* design: four load-bearing objections.**
- **Wasm secures the host from the module, never the module from itself.**
  Its sandbox is *coarse, inter-module* isolation and supplies **zero intra-module memory safety**: a C-to-Wasm heap overflow is fully exploitable *inside* the linear memory (Lehmann/Kinder/Pradel, "Everything Old is New Again: Binary Security of WebAssembly," USENIX Security 2020).
  So the Tier-2 **temporal-safety + control-flow-integrity certificate** (§13) is *still owed on top* of Wasm: it interposes a bytecode/validator/stack-machine layer without retiring a single proof obligation.
  And CHERI already delivers **byte-granular** safety for *every* pointer, not merely the heap base: so card (b), the one hardware-relevant Wasm idea, is **already fully banked by purecap RV64**.
- **The substrate cost is the EPIC disqualifier, verbatim.**
  A stack-machine bytecode is a *distinct ISA*, not an RV64 extension, so it forks the RISC-V Sail model, the CHERI-CompCert backend, Cerise, and Islaris, and **re-mints every FPCC, memory-safety, and constant-time certificate**: all of them stated *at binary level against the CHERI-RISC-V Sail model* (§5, §6, §13).
  This is exactly the cost the Itanium/EPIC entry ruled fatal: *"a new ISA means restating the Sail model and re-minting every certificate."*
  It spends the scarce currency (trust, proof surface) to buy cross-ISA portability the **Goals declare a non-goal** ("no requirement for broad software or hardware compatibility"; §2).
- **It fights the decode, WCET, and memory-model discipline head-on.**
  The C extension was deleted *purely* to buy unambiguous 4-byte decode (§15); Wasm's binary format is **variable-length, byte-aligned, LEB128-immediate, with structured control-flow blocks**: a strictly *worse* decode surface for the binary-level proofs.
  A hardware stack machine then faces a forced choice, both branches inadmissible for the performant case: **JIT** the bytecode to an internal register form: hidden translation-cache microarchitectural state surviving a partition switch (fails admission test 3) and runtime codegen the W^X invariant forbids (§14); or **interpret** it, slow *and* still carrying the decode/validation surface.
  Wasm threads, moreover, ride a **relaxed memory model** (C++/JS-derived), colliding with the normatively adopted **Ztso** that deletes RVWMO (§15).
- **The one admissible realization is the one §14 already allows: in software.**
  A *pure software interpreter* over Wasm is not a hardware feature at all: it is ordinary contained code on native RV64+CHERI, and §14 already permits exactly that (*"an app may embed an interpreter-mode Wasm engine as its private plugin mechanism… invisible to the architecture"*): its linear memory hardened by the surrounding CHERI process for free.
  Moving it into silicon buys only **speed**: the single currency the platform spends freely (*performance deliberately subordinated to security*); while enlarging every scarce one.

**The distilled atoms: both already banked, so nothing new imports.**
Following the belt→spiller / EPIC→NaR discipline, the non-redundant ideas are extracted and found *already present*: (1) **Wasm's interface/type calculus is already imported**: the §12 IDL is **"WIT-derived, fork-and-frozen"** (worlds → manifests, resources → capabilities), so the design took the Component Model's *type layer* and deliberately dropped its *bytecode/linear-memory execution model*; hardware-Wasm would re-adopt precisely the discarded half.
(2) **Linear-memory-as-capability is already CHERI**: byte-granular and universal, strictly exceeding Wasm's single-heap sandbox.
The enviable third property: the **Coq-mechanized semantics**; it buys nothing the design lacks: the CHERI-RISC-V Sail model ⋈ FPCC already give a Coq-checkable *binary-level* story, and Wasm's theorem is *type* soundness (sandbox integrity), not the functional-refinement, constant-time, and WCET properties this stack proves.

**Where it ranks among "abandon RISC-V" targets: off the scale, because the motivation differs.**
The belt and EPIC entries ranked EDGE ≻ belt ≻ EPIC on *ILP-without-speculation* and transactional-coherence grounds.
Wasm does not enter that ranking: those targets trade the substrate for **ILP** (a real if non-binding constraint), whereas Wasm trades it for **portability + sandboxing**: a declared non-goal and a property CHERI already exceeds, respectively.
It is rejected on *motivation*, one level above the cost argument that sinks EPIC.

**Disposition:** rejected as a hardware ISA, as a CHERI-sandbox target, and as a substrate: the execution substrate stays **native RV64+CHERI + FPCC**, itself the *stronger* "portable safe target" (a machine-checked proof travels with the artifact, not merely a sandbox claim).
Both distillable atoms already sit in the design (WIT → §12 IDL; linear-memory = capability → CHERI), so **nothing imports**.
Wasm's sole admissible role is the §14 **contained interpreter-mode plugin engine**: software, not silicon, an application-internal choice the spec already sanctions.
Non-normative; no spec-body change.

---

## The executable and package format: ELF declined on-device for a content-addressed capability image

The format the device admits and loads is a design decision with the same shape as the ISA-profile ones, so it runs through the §15 admission discipline and the import discipline like any mechanism: the scarce resource is the on-device trust and decode surface.

**ELF is the incumbent, and it is declined as the on-device artifact.**
ELF is the System-V executable and shared-object container: program-header and section-header tables reached by internal offset, string tables cross-referenced by index, ELF32/ELF64 and endianness variants, dynamic-linking and relocation sections, an interpreter path, and RWX segment permissions.
Almost all of that machinery serves facilities this design deletes: dynamic linking and `ld.so` (static composition, §7, §13), PLT/GOT lazy binding (W^X and no runtime codegen, §14), RWX segments and `mprotect` (the W^X invariant admits no writable-to-executable promotion, §14), and symbol and section tables for a runtime linker and debugger (an off-device concern).
What remains after subtracting those is not a small ELF profile but a different and much smaller object, and the residue ELF still forces on-device is the worst part for this project: a loader that parses offset-linked header tables is an attacker-facing grammar in the trust base, and by the §5 Narcissus rule its decoder would have to be verified over that whole cross-referencing structure.
This is the same decode-surface objection the CHERI-Wasm entry (above) raises against Wasm's variable-length, LEB128, structured-block encoding, one step worse, because ELF's tables are offset-linked, not merely variable-length.

**What replaces it (normative in §13) is a content-addressed capability image.**
A small typed manifest names content-addressed store objects (§10): the immutable, hash-verified code-and-rodata image separated from a writable data-initializer eager-zeroized under the Write-before-Read plane (§7, §15), the CHERI-TAL typing derivation carried as a first-class component (§5, §13), and relocations expressed as an explicit capability-wiring table (source object, offset, bounds, permissions, monotone from the initial distribution, §7).
Its decoder is a Narcissus copy-once verified reader over a fixed-layout, cross-reference-free schema (§5), and that schema is a crown-jewel spec discharged by compiling it, not hand-writing it, exactly as the wire-format descriptors are.
Purecap makes this natural rather than exotic: CheriBSD carries capability relocations (`__cap_relocs` and dynamic `R_MORELLO_*` records) bolted onto ELF, and the friction of that bolt-on is the evidence that materializing capabilities wants a first-class wiring table, not a relocation section.

**A single self-contained file is not the ELF property being declined.**
The objection is to ELF's interpreted, offset-linked grammar, not to shipping one file, so the content-addressed image also serializes to a single self-contained pack: a hash-indexed archive of the manifest, the object closure needed to run, and the derivation, as convenient to distribute, sign, and run as an executable.
It is the Fuchsia-archive and `blobfs`, IPFS-CAR, `fs-verity` read-only-image, and Nix-NAR lineage: one file whose *contents* are still named and verified by hash.
Installation inserts its objects into the content-addressed store, where anything already present deduplicates (Git-packfile and OSTree behavior), and a portable image instead maps in place and executes from its hash-verified read-only region; single-file convenience and content-addressed dedup are the same objects in two containers, not a choice between them.
The decode surface stays a flat header plus a hash-indexed object table plus a blob region with every object independently hash-verified, so a bad offset fails a hash check rather than driving a parser, which is the whole distance from ELF's cross-referencing header, section, string, and dynamic tables.

**The distilled loading structure is already banked as CHERIoT.**
CHERIoT already replaces container-style loading with compartment export and import tables and sealed entry points, sealed by a loader; the platform adopts that structure (sentries and the switcher, §7, §8, §15) and re-grounds it on RV64 128-bit capabilities and a verified reader, rejecting CHERIoT's compressed encoding and unverified loader, the same adopt-the-structure, reject-the-encoding move the ISA profile makes for the rest of CHERIoT.

**ELF is retained off-device, as build interchange.**
The certifying toolchain (§5, §18) may emit ELF, and CHERI-LLVM already does, because off-device artifacts are re-checked and their parsers never enter the on-device TCB; package build transforms ELF into the content-addressed image and derivation at store-insertion time (§10).
The on-device loader is therefore *deleted rather than hardened*, the *verify rather than hedge* disposition the MMU, PMP, and IOMMU take (§15), one layer up, at the format.

**Disposition:** stock ELF is declined as the on-device admitted and loaded artifact and retained only as off-device build interchange; the on-device format is the content-addressed capability image, normative in §13 (with §10, §14, §5).
A minimal always-on ELF profile is the tempting middle option and is rejected: it still forces the on-device decoder to parse ELF's offset-linked tables to find the profiled content, paying the decode-surface cost without buying the content-addressed store's per-object sharing.
No new §17 residual: the change deletes an on-device loader (a net trust shrink), and the format descriptor rides the existing Narcissus crown-jewel-spec obligation (§5, §17).

---

## High-level-language computer architectures (HLLCA): the semantic gap belongs to the verified compiler; the one hardware atom is already CHERI

A high-level-language computer architecture makes the machine's ISA *directly execute* a high-level language: closing the "semantic gap" (Wulf) in silicon rather than in a compiler.
It is the genus of which the **CHERI-Wasm entry above** is one species (Wasm-as-ISA = a structured stack machine executed in hardware), and completeness asks whether the broader tradition imports anything that entry did not already settle.
The lineage: the **Lisp machines** (Symbolics, LMI: hardware-tagged cells, hardware-assisted GC, microcoded `car`/`cdr`); the **Burroughs B5000/B6500** (an ALGOL stack machine, descriptor-addressed, arguably the first HLLCA); Intel's **iAPX 432** (Ada objects in microcode; its *capability* axis is the historical-capability-machines entry below, its *language-machine* axis is here); the **Java processors** (Sun picoJava, ARM Jazelle: bytecode in silicon); and the **graph-reduction machines** (Reduceron for lazy Haskell, SKIM, the Rekursiv, SOAR).
The RISC reaction (Patterson/Ditzel's "The Case for the Reduced Instruction Set Computer," and the general verdict that a compiler bridges the semantic gap better than microcode) is the historical judgment this entry restates in the platform's own currency.

**The three separable claims** (the import discipline, as for Wasm and EPIC): (1) **language-as-ISA**: the instruction set *is* the language's execution model (stack machine, graph reduction, tagged Lisp cells, object dispatch); (2) **safety-by-hardware-typing**: the hardware enforces the language's memory and type discipline (tagged memory, typed references, descriptor bounds); (3) **semantic-gap closure**: the hardware executes source constructs directly, deleting the compiler's lowering pass.

**The steelman: it is spec-sympathetic in spirit, not ILP bait.**
Unlike the belt/EPIC targets the appeal is not parallelism; it is *safety and formalization by construction*, which rhymes with this design.
(a) The platform is itself a *mild* HLLCA: CHERI puts a **language-level abstraction (the bounded, unforgeable reference) into the ISA**, exactly the HLLCA move of hardware-enforcing a high-level memory model.
(b) A tagged, typed machine has a **Coq-friendly formal story**: the SAFE/micro-policies lineage mechanized precisely such machines (the tagged-architecture entry below).
(c) The strongest modern form: a machine for a *typed or proof-carrying* language; it grazes a single-Coq-prover design that calls specifications the crown jewels (§5).

**Why it fails for *this* design: four load-bearing objections.**
- **The safety atom (2) is already CHERI, and the tag-monitor entry already settled it.**
  Hardware-tagged Lisp cells, Java typed references, and 432 object descriptors are all *tagged metadata checked in the datapath*: the SAFE/micro-policies genus the tagged-architecture entry (below) dispositions: CHERI **is** a fixed-policy tagged architecture, byte-granular and universal, with the Write-before-Read initialization plane (§15) a second fixed tag plane, strictly exceeding any HLLCA's per-object typing.
  Card (a) of the steelman is the concession, not the case for import: the design already took the one HLLCA atom that survives.
- **The language-ISA claim (1) is the Wasm/EPIC substrate-cost disqualifier, verbatim.**
  A Lisp/bytecode/graph-reduction ISA is a *distinct instruction set*, not an RV64+CHERI extension, so it forks the RISC-V Sail model, the CHERI-CompCert backend, Cerise, and Islaris, and **re-mints every FPCC, memory-safety, and constant-time certificate**: all stated at binary level against the CHERI-RISC-V Sail model (§5, §6, §13); and the one-language execution target is the cross-ISA portability the **Goals declare a non-goal** (§2).
- **The semantic-gap closure (3) belongs to the verified compiler: the load-bearing inversion.**
  The platform's thesis is that verification is *"a property of the artifact, not its pedigree"* (FPCC, §5), and **CHERI-TAL** (below) makes the compiler carry source-level types down to the binary as a checkable typing derivation: so the gap is closed by a **Coq-theorem'd compiler over a small, frozen, verified RV64+CHERI**, not by enlarging the ISA.
  HLLCA closes the same gap in *hardware*, spending the scarce currency (a large language-semantics Sail model, a re-minted proof stack) to buy a language front end the verified compiler already provides on the free axis: the RISC verdict recast: the compiler bridges the gap at lower cost on the axis this platform counts.
- **The managed-runtime realizations fail admission test 5 outright.**
  The Lisp- and Java-machine branch drags **hardware-assisted garbage collection** into silicon: an autonomous, address-dependent memory-walking-and-updating engine, the exact shape admission test 5 bans (the ground the Sv39 walker and Itanium's RSE are deleted on); whose unbounded pauses falsify the §11 WCET tables, and §10 bans the managed runtime outright.
  The 432's other lesson: capability and type checks on the critical path in *microcode* were ruinous; this is the fatal-performance verdict the historical-capability-machines entry (below) already books; CHERI does those checks in fixed silicon instead.

**The distilled atom: already banked (the belt→spiller / EPIC→NaR discipline).**
The single non-redundant HLLCA idea is *put the high-level safety type into the hardware as a fixed, frozen, verified tag*: and it is already present twice: **CHERI** (bounded references, a language abstraction in the ISA) and the **WIT-derived §12 IDL** (the interface/type calculus taken as a type layer, the bytecode/execution model deliberately dropped: the same split the Wasm entry above makes).
The maximal move: the whole *language* in silicon; is rejected exactly as Wasm-as-ISA and the programmable PUMP are (the tagged-architecture entry below): **frozen-minimal-verified beats expressive-general**.
And the tempting Coq-native extreme: *a machine that executes a proof or dependently-typed language natively*; fails hardest of all: CIC/Gallina is **not an execution target**, the design *compiles* every artifact to RV64+CHERI and *checks* proofs against the Sail model; executing a proof language in silicon would re-import the semantic-gap-in-hardware mistake at the one layer the design most wants small.

**Where it ranks.**
With Wasm: off the EDGE ≻ belt ≻ EPIC ILP ranking, because the motivation is language-affinity and safety-by-construction, not ILP, so it is rejected one level up, on *motivation* and substrate cost.
It is the genus over three entries already present: **CHERI-Wasm** (above) is its one live species, **historical capability machines** (below) takes the 432's capability axis, and **language-based isolation** (below) is its *software* pole; this entry records that the hardware-language-machine tradition distills, like the capability tradition, into **CHERI ⋈ the verified compiler ⋈ the §12 IDL** rather than importing as a machine.

**Disposition:** rejected as an architecture: the safety atom is already CHERI ⋈ the WIT-derived §12 IDL (byte-granular and universal, exceeding any HLLCA's typed memory), the semantic-gap closure is the verified compiler's job (FPCC ⋈ CHERI-TAL, §5), and the language-as-ISA realizations fork the whole Sail/proof substrate (the Wasm/EPIC disqualifier) while their managed-runtime forms bring the hardware GC and microcode-path checks the admission test and §10/§11 delete.
Nothing imports.
Non-normative; no spec-body change.

---

## Language-based isolation: Singularity, Midori, Verve, Tock, Theseus; the software-safety pole, already banked as the contained-code discipline, CHERI kept for the unverified residual

The proposal is to isolate *not* with hardware (no MMU, no capabilities, no rings) but with a **type-safe language and a trusted runtime**: Microsoft **Singularity** (Software-Isolated Processes in Sing#, one physical address space, ring 0, isolation by language safety plus verified channel contracts), its machine-checked successor **Verve** (Yang/Hawblitzel, PLDI '10, *"Safe to the Last Instruction"*: a verified type-safe kernel over a typed-assembly nucleus), and the embedded lineage **Tock** (Rust *capsules* isolated by the borrow checker atop a thin MPU).
Two later systems in the same lineage sharpen the claim without changing it: Microsoft **Midori** (Singularity's successor; an ahead-of-time-compiled, capability-secure, asynchronous C#-derived language and OS whose distinctive contribution is its *error model*: recoverable errors carried as typed results, program *bugs* answered by fail-fast *abandonment* of the isolated process, contracts throughout), and **Theseus** (Boos et al., OSDI '20; a Rust single-address-space, single-privilege-level OS whose *intralingual* design pushes OS invariants into the compiler and whose tiny crate-granular components minimize *state spill* to make fault recovery and live evolution first-class).
The radical claim: if every instruction is type-safe, hardware memory protection is redundant.
It decomposes into three separable parts: (a) language safety as the isolation *mechanism*; (b) the *typed-assembly* carrier that pushes source types to the binary (Verve); (c) the trusted *runtime* the guarantee rests on.

**The steelman: the purest reading of the platform's own axiom.**
It is *"trust is the scarce resource"* taken further than this design takes it: delete the MMU **and** the capability hardware, spend only language safety.
The design already deletes the MMU (the MMU-deletion entry above); this would delete CHERI too.
And the design already banks the language half wholesale: `#![forbid(unsafe_code)]` safe-Rust data planes, Coq-verified Lustre/Vélus control planes, verified C, definite-initialization (§5); so most of Singularity's SIP guarantee is *already* a property of contained code here, and Verve's verified typed-assembly kernel is the direct ancestor of the CHERI-TAL admission discipline (below).

**Why language safety cannot be the *sole* mechanism.**
- **It has no bound on unverified native code: the platform's defining case.**
  Singularity's isolation holds only for code its trusted compiler certified; one `unsafe` block, one miscompilation, or one wholly-unverified binary breaches the shared single address space with *nothing beneath it*.
  This platform's defining property is the hardware universal contract (Cerise-style, §13) that bounds **arbitrary unverified code**: precisely what language safety cannot reach; and CHERI is kept for exactly that residual.
  This is *verify rather than hedge* applied to the software-safety pole: the proof establishes safety where it can, and the one verified hardware mechanism bounds the code the proof does not cover: the drop-PMP logic (above) with language safety, not PMP, as the layer being reasoned about.
- **The trusted runtime is a TCB the design already refuses.**
  Singularity's SIPs and Verve's kernel rest on a trusted language runtime (and, for Singularity, a garbage collector); the platform bans the GC (§10) and drives contained code to GC-free lowering (Vélus, verified C, arena extraction), so that runtime is a *foreign trust base*, not an import.
- **Verve's prover is declined; its design is carried: the seL4 move.**
  Verve is verified with Boogie/Z3, the same SMT trust-base widening the platform declines for F\*/Z3 and EasyCrypt (§5); its *design* (a verified TAL kernel) is carried onto RV64+CHERI and Coq as the CHERI-TAL discipline (below), its *prover* is not: adopt the design, re-home the proof, exactly as with seL4.

**The distilled atoms: both already banked.**
Following the belt→spiller / EPIC→NaR / Mon CHÉRI→Write-before-Read discipline: (1) **language safety at the source** is safe Rust ⋈ Vélus ⋈ verified C (§5): the SIP guarantee for contained code, established by proof rather than by a trusted runtime; (2) **typed assembly carrying source types to the binary** is the CHERI-TAL admission discipline (below): Verve's TAL idea, re-homed onto RV64+CHERI and the one prover, with CHERI discharging the spatial half in hardware so the types carry only the temporal / CFI residual.
The *"both, not either"* position (language safety proves it at source, CHERI enforces it on the artifact and backstops the unverified residual) is the design's, made explicit.

**Midori and Theseus each contribute one further atom already banked here, and one (live evolution) declined.**
Midori's *error model* (recoverable errors carried as typed results, program *bugs* answered by fail-fast *abandonment* of the isolated process, contracts checked at runtime and elided where the compiler proves them) is this platform's fail-stop / fail-closed / crash-only discipline (§16) under another name: abandonment is the sentinel tearing a compartment down to a pre-proved safe subset or fail-stopping (§16), contracts are the admission obligations and the atomic-requirements register (§5), and Midori's transient-versus-persistent split (journal the durable state, discard and recreate the rest) is crash-only reinitialization over the verified journal (§10).
The one refinement the platform adds is that a bug is *proven absent* at admission wherever it can be, so abandonment covers only the residual: *verify rather than hedge* applied to the error model, exactly as CHERI is kept for the code the proof does not reach (above).
Theseus is the closest sibling of all: a Rust single-address-space, single-privilege-level, GC-free OS, differing only in isolating by language safety alone where this platform adds CHERI and proof.
Its *state spill* (the coupling that arises when one component holds state on behalf of another, which Theseus minimizes for fault isolation and clean restart) is the analytical name for exactly what the share-nothing multikernel (§7), crash-only explicit state (§12, §16), and static composition already minimize by construction; its *intralingual* move (push OS invariants into the compiler) is the weaker sibling of carrying *proof*, not merely types, to the artifact (CHERI-TAL, below).
Its *live evolution* (runtime hot-swap of a running component, core ones included) is the atom **declined**: it is the dynamic in-place code mutation that static composition, measured boot (§9), and W^X with no runtime code generation (§14) exist to forbid; the platform evolves the running system the safe way instead, by A/B signed generations committed through the one transactor and the rollback manager (§9, §11), coarse-grained and gated by the measured chain rather than fine-grained and unverified.

**Where it ranks.**
It is the **software-mechanism dual of the deletion trilogy** (MMU / privilege / PMP): where those delete a hardware mechanism and keep the verified one, this would delete the hardware and keep only language safety.
The platform takes the *converse*: keep the one deeply-verified hardware mechanism *and* add the proof; because hardware must bound code the proof does not cover; off the abandon-RISC-V ranking, since it changes no ISA.

**Disposition:** rejected as the *sole* isolation mechanism: language safety leaves unverified native code unbounded and leans on a trusted runtime / GC the platform refuses; its two atoms are already present: language safety at source (safe Rust / Vélus / verified C, §5) and typed assembly at the binary (CHERI-TAL, below); and Verve's verified-TAL *design* corroborates the CHERI-TAL route while its Boogie/Z3 prover is declined (the seL4 discipline).
Midori's *error model* and Theseus's *state spill* are banked the same way (fail-stop / crash-only §16; the share-nothing multikernel and static composition §7), and Theseus's *live evolution* is declined for A/B signed generations under the measured chain (§9, §11).
The platform axiom decides it as ever (*verify rather than hedge*): the proof carries safety as far as it reaches, CHERI bounds the rest.
Non-normative; no spec-body change.

---

## Exokernel and unikernel structure: already converged; secure bindings are the powerbox, the type-safe image is the compartment

The proposal is a radical OS *structure*: the **exokernel** (MIT; Engler/Kaashoek, SOSP '95: a minimal kernel that only *securely multiplexes* hardware, exposing resources to application-linked **library OSes** rather than abstracting them), or the **unikernel** (MirageOS: a single application compiled with only the library-OS pieces it needs into one type-safe image, in OCaml).
Both collapse the kernel/user boundary the classical OS erects, for the same reason the platform values: less trusted mechanism between the application and the metal.

**Already converged: the design sits between the two poles.**
- The kernel is a minimal **capability multiplexer** (§7), not an abstraction layer: the exokernel's *"securely expose, don't abstract"* thesis, realized with capabilities rather than with software TLBs and packet filters.
- The exokernel's **secure bindings**: the mechanism that lets a library OS use a resource without the kernel interpreting each access; *are* the capability + **powerbox** model (§8, §12): authority handed out once at compose time, checked cheaply by the hardware thereafter.
- The unikernel's **single-purpose type-safe image** *is* the per-app compartment with its private manifest namespace (§14), linked against only the contained servers it needs (§12) and specialized at build time by static composition (§7): MirageOS's whole-program specialization, reached from capabilities.

**What does not import.**
- **The exokernel leaves protection to the library OS; the platform proves it.**
  Exokernel minimality pushes safety *up* into unverified library OSes; the platform instead makes the kernel the *verified* capability enforcer and adds the hardware universal contract (§13): minimal in *mechanism* but maximal in *assurance*, the opposite of the exokernel's trust posture (which optimized performance, the freely-spent axis).
- **MirageOS is OCaml on an unverified runtime with a GC** (§10): a foreign trust base; so the *artifact* is declined; the *structure* (specialized type-safe image) is the compartment model, built from safe Rust / Vélus (§5) instead.

**The distilled atom: already banked.**
Minimal-multiplexer kernel → §7; secure binding → capability / powerbox (§8, §12); single-purpose type-safe image → per-app compartment (§14).
Nothing new imports; the two lineages are the OS-structure *names* for decisions the design already took from the capability side.

**Where it ranks.**
Off the abandon-substrate scale (no ISA change): a convergent-structure entry like the Mill single-address-space cross-reference: the design is *already* an exokernel-style multiplexer running unikernel-shaped applications, reached from capabilities and static composition rather than from resource-exposure minimalism, and reaching *higher* assurance by verifying the multiplexer the exokernel left thin.

**Disposition:** no import: the exokernel's secure multiplexing and the unikernel's specialized type-safe image are already the capability kernel (§7), the powerbox (§8, §12), and the per-app compartment (§14); the OCaml / library-OS *artifacts* carry a foreign runtime and GC the platform declines.
The structure is convergent, the assurance is higher (the multiplexer is verified, not merely minimal), and nothing lifts.
Non-normative; no spec-body change.

---

## Decentralized-information-flow OS architectures: HiStar, Asbestos, Flume; the label-centric minimal-TCB design, reached from the capability side

The proposal is an OS organized around **decentralized information flow control (DIFC)** as the primary mechanism: every object carries secrecy and integrity **labels**, the kernel's whole job is to forbid any data flow that would violate the label lattice, and the trusted base shrinks to a small label-checker.
The lineage: **Asbestos** (Efstathopoulos et al., SOSP '05: labels on processes and messages, event processes for per-request isolation); **HiStar** (Zeldovich/Boyd-Wickizer/Kohler/Mazières, OSDI '06: six object types (segment, thread, gate, address space, container, device), labels on all, a minimal kernel enforcing *only* information flow, famously running a taint-tracking web server and a Unix emulation over a tiny TCB); and **Flume** (Krohn et al., SOSP '07: DIFC as a reference monitor over standard Linux, tags and endpoints).

**The steelman: squarely in the project's spirit.**
(a) **Minimal TCB by making information flow the sole mechanism**: HiStar's thesis is that privacy and integrity policies need only a tiny kernel if information flow is the organizing principle, the platform's own least-authority, smallest-trusted-set instinct (G1/G2).
(b) **Decentralized declassification**: any principal may declassify its own secrets; this is the no-ambient-authority, delegate-don't-grant stance (§2, §8) exactly.
(c) **It targets confidentiality/non-interference head-on**: the very property the design proves as the §8 non-interference theorem over the flow-label / IFC machinery (§8, §13).

**Why it does not import as an *architecture*: the design already runs DIFC as a mechanism over a stronger substrate.**
- **The design is capability-centric with DIFC layered on, not label-centric.**
  The §8/§13 flow-label / IFC machinery *is* decentralized information flow control: but carried over a **capability** kernel (seL4-design, §7) and **CHERI** hardware, so the platform has HiStar's information-flow enforcement **plus** byte-granular spatial capability isolation HiStar lacks (HiStar isolates with coarse address-space containers and labels; CHERI bounds every pointer).
  The lattice rides *on* capabilities, not *instead of* them: strictly more mechanism where it counts, reached from the capability side the historical-capability-machines entry (below) already traces.
- **HiStar's minimal TCB is a runtime reference monitor; the platform's is a proof.**
  HiStar shrinks the trusted *code*; the design shrinks the trusted *set* and then **proves** the kernel correct in Coq (§5) and bounds even wholly-unverified code with the hardware universal contract (§13).
  HiStar's label-checker is small but unverified; the design's is small **and** verified: the same "minimal but *verified* beats minimal" upgrade the exokernel and enclave entries make.
- **Timing channels are the platform's separate, deeper effort.**
  DIFC labels track explicit and storage flows; the covert **timing** channels are closed here by construction (in-order, non-speculative, partitioned caches/memory/NoC, §15) and by the constant-time layer (§5), not by labels: so a DIFC OS would still owe the timing-channel story the profile already discharges.
- **HiStar's Unix emulation is a foreign trust base**: the POSIX ambient-authority surface [userspace-porting.md](userspace-porting.md) deletes; the design reimplements capability-native (§14) rather than emulating Unix over labels.

**The distilled atom: already banked (the belt→spiller discipline).**
Decentralized information flow control = the §8/§13 flow-label / IFC machinery and the §8 non-interference theorem; minimal-TCB-via-one-mechanism = the capability kernel (§7) ⋈ the hardware universal contract (§13); decentralized declassification = the powerbox / capability-delegation model (§8, §12).
The DIFC-OS tradition distills into **CHERI ⋈ the capability kernel ⋈ the flow-label/IFC machinery ⋈ the non-interference theorem**: all present, the OS-structure *name* for decisions taken from the capability side, exactly as the exokernel/unikernel entry (above) found for resource multiplexing.

**Where it ranks.**
Off the abandon-substrate scale (an OS structure, no ISA change): a **convergent-structure entry** beside exokernel/unikernel and enclaves: the design is *already* a DIFC OS (labels ⋈ non-interference) reached from capabilities and **verified**, reaching HiStar's minimal-TCB goal with byte-granular isolation and a machine-checked proof HiStar has neither of.

**Disposition:** no import as an architecture: DIFC is present as the §8/§13 flow-label / IFC machinery and the §8 non-interference theorem, carried over the capability kernel (§7) and CHERI (byte-granular, exceeding HiStar's coarse container-plus-label isolation) and **proved** in Coq (§5) rather than enforced by an unverified reference monitor; HiStar's Unix emulation is the POSIX ambient-authority surface the design deletes ([userspace-porting.md](userspace-porting.md), §14).
The label-centric structure is convergent, the assurance is higher (verified, byte-granular), and nothing lifts.
Non-normative; no spec-body change.

---

## HexFive MultiZone: already covered, strictly dominated, nothing to import

MultiZone is a policy-driven separation kernel: a small nanokernel orchestrating standard RISC-V **PMP** to isolate zones, a no-shared-memory messenger between zones, and a configurator fusing linked zone binaries + policy + kernel into a signed image (running unmodified code by trap-and-emulate of privileged instructions).
Each component maps onto a strictly stronger mechanism already mandated here: PMP zones → **CHERI + capability-checked DMA + coherence islands** (byte-granular, unforgeable, formally modeled vs. a handful of coarse power-of-two regions); nanokernel → the **seL4-design capability microkernel** (re-proved in Coq, §5) with a completed refinement + non-interference proof (MultiZone advertises "formally verifiable," not a finished machine-checked proof); messenger → the **verified ring data plane** under Ztso; configurator → **static composition + signed generation + proof-checked admission**.
Its distinctive selling point (zero hardware change, zero code change, commodity cores) is the pragmatic *inverse* of a spec that mandates custom CHERI silicon and native capability code, and its trap-and-emulate method opposes the no-ambient-authority stance.
**There is no clean pure-win to extract; it is a lightweight point on the same design axis already taken to the maximum.**

**The inverse question: descend the base to MultiZone rather than import it upward.**
The symmetric proposal is not to lift a MultiZone idea into this spec but to collapse the isolation substrate *down* to MultiZone's: an **M-mode + U-mode processor** (no S-mode; the trusted kernel resident in M-mode), no Sv39 MMU, no CHERI, isolation by **PMP alone**.
The appeal is real and almost entirely about *realization*: PMP ships in every commodity RISC-V core, so the binding CHERI-silicon and CHERI-CompCert dependencies (§6, §18) evaporate; the proof stack drops to mature plain-C CompCert with no CHERI-C mechanization gap (§7, §17); and shedding a privilege mode plus the MMU is a genuine silicon- and Sail-surface reduction that even rhymes with static composition (§7), since a stateless single-address-space design leaves most MMU machinery idle.

**Rejected as the *base* on the goal function, not the effort function.**
Four objections are load-bearing.
(1) **Granularity ceiling:** PMP is a handful of coarse power-of-two/TOR regions per hart, whereas the design names thousands of fine domains (per-origin, per-session ring table, per-surface/per-input, per-element gather/scatter, §8, §12, §14): a count and byte-granularity PMP structurally cannot express, gutting G1/G2 least-authority.
(2) **No intra-domain safety:** PMP isolates domains but does nothing *inside* one, so memory-safe-by-construction apps (§5, §14), the Cerise universal contract that bounds *wholly unverified* code (§13 Tier-2), the W^X capability-monotonicity invariant (§14), and per-element vector bounds (§8) lose their hardware footing and fall back onto the Rust toolchain: enlarging the very containment trust FPCC exists to remove.
(3) **"PMP only" is not even sufficient:** malicious DMA still needs capability-checked DMA and cross-domain timing/coherence still needs the islands and TDM NoC (§3, §15), so PMP retires no other mechanism: it is a weaker spatial layer, not a one-mechanism simplification.
(4) **It reopens ambient authority:** MultiZone's trap-and-emulate of privileged instructions is exactly the ambient-authority pocket §2/§14 forbid.
The defect is the trap-and-emulate model and PMP-as-primary, *not* Machine-mode kernel residence itself: which the platform embraces under capability-gated privilege (the single-privilege-mode entry below): once CHERI governs privilege as a PCC permission, a Machine-mode kernel is confined by unforgeable capabilities, whereas MultiZone's M-mode code is confined by nothing finer than coarse PMP.
"More robust" is genuinely two-sided: PMP is more mature *today*, but CHERI is the stronger, more *uniform* guarantee once built (subsuming MMU-split, shadow stacks, and software W^X into one monotone mechanism), covering the same ground with fewer orthogonal parts.

**Disposition:** the M-mode/PMP-only design is **rejected as the base, not a stage the plan passes through**: the platform is purecap from first bring-up (§18) with no capability-degraded instantiation to descend to, and "trust is the scarce resource, engineering is free" resolves the base toward CHERI's smaller, deeper, byte-granular story.
Taking PMP-only as the *goal* would trade the platform's defining property: hardware that bounds arbitrary unverified code; for buildability the spec deliberately declines to optimize.

**PMP is dominated in both roles: and dropped entirely.**
The domination verdict above is specific to PMP as a *primary, fine-grained compartmentalization* mechanism, where CHERI + capability-checked DMA + islands strictly exceed it.
A tempting alternative *banks* PMP in a *secondary, coarse, sub-kernel backstop* role (immutable-text/W^X, per-core partition bound, crown-jewel secret fencing) on the ground that, being CHERI-disjoint, it would hedge a CHERI *logic* fault no in-band mechanism otherwise could.
**That backstop is dropped too** (the drop-PMP entry below): with CHERI formally verified (the Oxford/Google CHERIoT-Ibex conformance proof; the RTL ⊑ Sail workstream, §18) and application-class silicon removing PMP on exactly this ground (Codasip's A730: PMP *"can be removed and replaced by more power- and area-efficient circuits"*), the disjoint hedge is judged redundant Sail surface, and the three roles collapse onto CHERI monotonicity (§7, §14), the crypto core's hardware boundary, and TME (§15).
So the full disposition is unqualified: nothing of MultiZone's *architecture* imports, the base does not descend to it, and PMP is not retained even as a backstop: CHERI is the sole in-band spatial mechanism, hedged by its own verification rather than by a coarse subset of itself.

---

## Historical capability machines: iAPX 432, System/38 → AS/400, KeyKOS/EROS, the M-Machine; the ancestry CHERI and seL4 already distill; orthogonal persistence is the one distinct idea, and it is declined

Before CHERI and seL4 there was a lineage of capability *hardware* and capability *operating systems* this design descends from, and completeness asks whether any of it imports beyond what CHERI and seL4 already carry.
The machines: Intel's **iAPX 432** (capability-based, microcoded, famously ruinous in performance); IBM's **System/38 → AS/400** (a capability-addressed **single-level store** behind a technology-independent machine interface); the **KeyKOS → EROS → Coyotos** capability-OS line (capabilities with orthogonal persistence); the Cambridge **CAP** and **Plessey System 250**; and the MIT **M-Machine**'s **guarded pointers** (Carter/Keckler/Dally, ASPLOS '94: an in-register capability scheme, the direct hardware ancestor of CHERI).

**Already distilled: the lineage is the substrate, not an alternative to it.**
- **Capability addressing**: unforgeable, bounded references as the sole naming mechanism; is CHERI (§1, §8), byte-granular and formally modeled, strictly exceeding the coarse segment / descriptor capabilities of the 432 and System/38.
- **The capability-OS design**: untyped memory, endpoints, a derivation tree, revocation; is seL4 (§7, §8), itself a KeyKOS/EROS descendant, re-proved in Coq (the seL4 entry below).
- The 432's **lesson**: capability checks on the critical path in *microcode* are fatal to performance; is answered by CHERI doing them in *fixed silicon* on the fast path, which is why the design can rest on capabilities where the 432 collapsed under them.

**The one genuinely distinct idea: and why it is declined.**
- **Orthogonal persistence / single-level store** (AS/400, EROS) erases the memory/storage distinction: objects simply persist, transparently, with no serialize/load boundary; tempting against a single-address-space design whose MMU is *already* gone.
  It is declined because it collides with three adopted invariants.
  The **crash-only** model with explicit, re-initializable state (§12, §16) wants a clean state boundary that transparent persistence dissolves; **eager-zeroize** and the **Write-before-Read** initialization plane (§7, §15) assume memory starts *empty*, not silently repopulated from a persistent image; and the **verified storage stack** (§10) is a content-addressed CoW B-tree with an *explicit, provable* crash-refinement semantics that orthogonal persistence would replace with an implicit one no theorem covers.
  Persistence here is **explicit and verified** (§10), not orthogonal: the crash-safety proof *needs* the boundary the single-level store deletes.

**Where it ranks.**
Ancestry, not an alternative: off every ranking; the entry grounds the capability lineage the way the Mill entry grounds single-address-space, recording that the capability-machine tradition is **distilled into CHERI ⋈ seL4** rather than imported as a machine, and that its one separable idea (orthogonal persistence) is actively *incompatible* with the verified-crash-refinement storage the design chose.

**Disposition:** no import as an architecture: capability addressing is CHERI (§1, §8) and the capability-OS design is seL4 (§7, §8), both exceeding their ancestors, and the 432's microcode-checking failure is exactly what CHERI's fixed-silicon checks avoid; the single distinct idea, orthogonal persistence / single-level store (AS/400, EROS), is **declined** because it dissolves the explicit state boundary the crash-only model (§12, §16), eager-zeroize / Write-before-Read (§7, §15), and the verified crash-refinement storage stack (§10) each depend on.
Non-normative; no spec-body change.

---

## Object Memory Architecture: object-granular naming against byte-granular capabilities; the elegant synthesis is already the design, the deeper one is the MMU it deleted

Where the Historical capability machines entry (above) took the object *machines* as ancestry, this entry takes their shared *memory model*, idealized to its most elegant form, as an axis in its own right: an **Object Memory Architecture** (OMA) in which memory is not a flat array of bytes but a graph of **objects**, each with an unforgeable **object identifier (OID)**, an implicit boundary, an optional type, and object-granular access rights, so that a reference is an **(OID, offset)** pair naming an *identity* rather than a *location*.
The lineage: Intel's **iAPX 432** (access descriptors indexing an object table to reach an object segment); IBM's **System/38 → AS/400** (a single-level store whose 128-bit pointers carry a hardware **tag bit** ordinary stores cannot forge, the object model living behind the Machine Interface); **MONADS** (Rosenberg/Keedy: a persistent object store in one enormous address space, password capabilities); the **Rekursiv**; and the modern non-volatile-memory instance **Twizzler** (Bittman et al., USENIX ATC '20: 128-bit object IDs and cross-object pointers over persistent memory).
It decomposes, in this document's manner, into five separable claims: (1) **object-granular naming** (reference = (OID, offset)); (2) **identity-based temporal safety** (a dangling reference is a reference to a retired OID); (3) **hardware object typing**; (4) **single-level store / orthogonal persistence** (memory and storage unified, no serialize/load boundary); (5) **location independence** (objects relocate, compact, swap, or persist behind the OID indirection).

**The steelman: the most elegant OMA, four real cards.**
(a) **Safety is a consequence of *naming*, not a check bolted onto an address.**
You address *within* an object, running past the end is not expressible because the object is the unit of naming, and the OID is unforgeable, so spatial safety falls out of the reference scheme rather than out of a bounds comparison.
(b) **Temporal safety by *identity*, with no sweep: the strongest card.**
Freeing an object retires its OID, and any surviving reference simply fails its next validity check, so use-after-free is caught without CHERI's revocation *sweep*, the genuinely awkward part of capability temporal safety (Cornucopia-class).
(c) **One uniform model spanning register, memory, storage, and the authority graph.**
The single-level store deletes the serialize/load boundary and the memory/file distinction, and authority rides the object graph: the "everything is an object" dual of this platform's "everything is a byte plus a capability," a genuine conceptual economy.
(d) **It is spec-sympathetic in spirit.**
A single global space (the design is already single-address-space, §15), a location-independent identity (the design is already content-addressed, §10), and authority on the object graph (the capability graph) are all present here already, and the AS/400 tagged pointer is a spiritual CHERI ancestor, reaching "tag equals unforgeability" from the object side decades early.

**Why the most elegant OMA still does not win: five objections.**
- **The OID → location indirection is the MMU this design deleted, generalized to per-object.**
  A reference (OID, offset) must resolve to a location, and there are only two ways.
  A **hardware object table with a cache** (an object TLB) is a mapping structure with data-dependent hit/miss latency (admission test 2) and hidden state surviving a partition switch (admission test 3): the Sv39 walker / ALAT / PUMP-rule-cache shape the profile deletes, here made *finer than a page table* (per-object, so more entries and worse), and the iAPX 432's access-descriptor-to-object-table indirection is the object-model instance of the microcode-critical-path cost the Historical entry books (above), a central reason the 432 was "ruinous in performance," the exact structure the MMU-deletion entry (below) rejects.
  Or the location is **inlined** into the reference, so the reference is (location, OID-for-validation): but that is a CHERI capability with an extra OID field, and the validation is a tag (CHERI's tag) or another lookup, so "identity, not address" collapses into "CHERI capability plus an OID that buys only persistence and relocation," which the design declines (below).
- **CHERI is byte-granular and sub-object; the object model is object-granular, hence coarser.**
  OMA's boundary is the object, so intra-object overflow (one field into the next) is uncaught unless every field becomes its own object, which explodes the table and the indirection; CHERI's `csetbounds` narrows to any byte range, delivering the object boundary *and* sub-object bounds *and* per-element gather/scatter bounds (§8) with no OID table, so on the actual memory-safety axis CHERI strictly exceeds the object model, the same "byte-granular and universal, exceeding X" verdict the Wasm-linear-memory, HiStar-container, and micro-policy entries reach.
- **The temporal card is a real trade, not a win, and this design's low allocation churn already blunts it.**
  That *OMA avoids the sweep* is right, but the sweep is not a hot-path cost: the design's dereference path already carries a deterministic per-capability-load **revocation check** (the load filter, fixed-latency, §8), so OMA's per-access validity check is not a *new* hot-path tax, and the honest difference is on the *free* path, where CHERI pays a budgeted background **sweep plus quarantine** (freed memory reused only after the sweep, the §11 model accounts for it) and OMA pays **generation storage plus a non-aliasing discipline** and reuses immediately.
  That trade is workload-dependent (allocation-churn-heavy favors OMA's no-sweep, pointer-chase-heavy favors CHERI's already-cheap dereference) and it lands on the performance axis the platform spends freely (§2); and decisively, this design's **static composition (§7), GC-free storage (§10), and crash-only explicit state (§16)** minimize allocation churn, so the sweep the OMA scheme targets is already small here (the sweep is awkward in a malloc-heavy C program, not in a low-churn static system), while the generation scheme is not free on the scarce axes either (below).
- **Single-level store, relocation, and GC are already declined or banned.**
  Orthogonal persistence is *already declined* (the Historical capability machines entry, above) for dissolving the crash-only state boundary (§12, §16), the eager-zeroize / Write-before-Read assumption that memory starts empty (§7, §15), and the explicit, provable crash-refinement of the verified storage stack (§10); transparent object *relocation* (compacting GC, swap) is an autonomous memory-touching engine (admission test 5, the ground the Sv39 walker and Itanium's RSE are deleted on, and §10 bans the GC outright), so OMA's two most distinctive advantages, persistence and relocation, land on axes the design deliberately refuses, not on the scarce one.
- **Object-as-ISA is the substrate-cost disqualifier, verbatim.**
  An object-addressed machine is a distinct ISA and memory model, not an RV64+CHERI extension, so it forks the CHERI-RISC-V Sail model, CHERI-CompCert, Cerise, and Islaris, and re-mints every FPCC / memory-safety / constant-time certificate stated at binary level against that model: the exact cost the EPIC, Wasm, and OISC entries ruled fatal, spent to buy a naming model whose distinctive features the design declines.

**The synthesis, and why the elegant one is already here.**
The admissible synthesis of object identity ⋈ capability enforcement is *already the design*, reached from the capability side and moved off the runtime path.
Object **identity** is the content-addressed store (§10): objects named by hash, a location-independent unforgeable identity, resolved to a CHERI capability *once, at install and compose time* by the capability-wiring table of the content-addressed capability image (the executable-and-package-format entry above: source object, offset, bounds, permissions), not by a per-dereference hardware table, so the wiring table *is* an object graph materialized into capabilities.
Object **bounds** are CHERI capability bounds (byte-granular, sub-object); object **type** is the CHERI-TAL typing derivation carried to the binary (the HLLCA entry's verdict, above: semantic-gap closure belongs to the verified compiler, not the hardware) plus otype for sealing; object **persistence** is the explicit, verified content-addressed CoW storage stack (§10), not orthogonal; object **access control** is capabilities ⋈ the powerbox (§8).
So the design already *is* an object system: a graph of content-addressed, hash-named, capability-bounded, TAL-typed objects with authority riding the graph, and the one thing separating it from OMA is *where the object graph is resolved*: at composition and storage time, statically, verified, once, lowered to CHERI capabilities, rather than at run time, per dereference, in a hardware object table.
That is the platform's signature move (do it once, statically, verified, then delete the runtime mechanism), the same one it makes deleting the MMU, the dynamic predictor, and the on-device loader; the *deeper* synthesis (an OID indirection in the hardware) is inadmissible for reasons already on the record, being the object-table-with-a-cache the MMU-deletion entry (below) rejects, generalized per-object, and dragging in the persistence, relocation, and GC the design declines.

**The distilled atom: identity temporal safety, already met or already a tag plane.**
Following the belt→spiller / EPIC→NaR / Mon-CHÉRI→Write-before-Read discipline, the one non-redundant OMA idea is *identity/generation-tagged temporal safety*, and it is either already met or already shaped as a fixed tag plane.
The property (freed ⇒ unreachable) is already the design's, discharged by budgeted revocation and the deterministic load filter (§8) beside CHERI-TAL linear/affine types (§5, §13); the *generation-tag* realization (a version stamped in the capability, compared against the object's current generation on access) is an *implementation option* for that same property, not a new capability, and its admissible form is a fixed, address-indexed generation-tag plane checked in-line at fixed latency, the transparent tag-plane shape the Write-before-Read plane already models (the Mon CHÉRI entry below), never the OID *table*.
It is therefore a parameter for the §15 proof-aware design-space exploration (a way to spend the tag-storage budget on determinism-preserving temporal safety) weighed against sweep-based revocation, and note the *probabilistic* memory-tagging cousin (MTE) is already excluded (§15) as a statistic rather than a theorem, so a deterministic full-width generation tag is the admissible form should the sweep ever prove too costly.
On the proof axis the intuition holds but is already spent: identity-based temporal safety *is* simpler to state than global revocation (a local per-access invariant rather than a sweep-completeness-plus-quarantine argument), but the design banked that simplification one level higher as the **CHERI-TAL linear/affine types** (static ownership is compile-time identity tracking, the cheapest proof, discharging most use-after-free at type-check, revocation left only the runtime backstop for the residual), and the hardware-OID generation scheme does not extend it: it *moves* the hard argument (sweep-completeness becomes generation-non-aliasing / ABA-freedom), adds a generation-state clause to the one Iris-over-Sail metatheorem (§13) and its Sail surface, and leaves the already-mechanized revocation lineage (Cornucopia, Cerise) net-new to restate for generations.

**Where it ranks.**
With HLLCA and the Historical capability machines entry (above), off the EDGE ≻ belt ≻ EPIC ILP ranking: not an ILP play but a safety, naming, and persistence play, rejected on *motivation* and substrate cost one level above the performance argument.
Its safety atom is exceeded by CHERI, its identity-temporal atom is banked (or a design-space-exploration tag-plane option), its persistence and relocation atoms are declined or banned, and its uniformity is matched from the capability side, so nothing imports as a machine, exactly as for the capability-machine ancestry it idealizes.

**Disposition:** no import as an architecture: the object memory model's spatial safety is byte-granularly exceeded by CHERI (§1, §8) without the OID indirection; its identity-based temporal safety is already met by budgeted revocation ⋈ the load filter (§8) ⋈ CHERI-TAL linear/affine types (§5, §13) and admissible only as a transparent generation-tag plane, never the hardware object table (which is the MMU this design deleted, below, generalized per-object); and its single-level store, relocation, and GC are the orthogonal persistence the Historical capability machines entry (above) declines and the autonomous relocation / managed runtime the admission test and §10 ban.
The elegant synthesis (object identity ⋈ capability enforcement) is *already the design*: content-addressed objects (§10) resolved to CHERI capabilities at compose and storage time by the wiring table (the content-addressed capability image entry above), TAL-typed (HLLCA, above) and explicitly, verifiably persisted (§10), the object graph resolved statically and once rather than by a runtime hardware table.
The platform axiom decides it as ever (*trust is the scarce resource, engineering is free, delete rather than defend* → *verify rather than hedge*): resolve the object model into capabilities ahead of time and delete the runtime indirection, rather than pay a per-dereference object-table tax to buy persistence and relocation the design refuses.
Non-normative; no spec-body change.

---

## Enclave architectures: Sanctum, MI6, Keystone; defending against the speculation and sharing this design already deleted

The proposal is hardware **enclaves**: a privileged security monitor carving isolated, attested execution environments out of a shared machine: MIT's **Sanctum** (SGX-class isolation with a small monitor; Costan/Lebedev/Devadas, USENIX Security '16), **MI6** (enclaves on a *speculative, out-of-order* core; Bourgeat et al., MICRO '19: from the same MIT group as Kôika), and **Keystone** (a RISC-V enclave framework built on **PMP**; EuroSys '20).
The pitch is strong isolation for mutually-distrusting workloads on shared silicon, with a small trusted monitor and remote attestation.

**Why it is already subsumed: the threats it fights are deleted, not defended.**
- **Enclaves exist to claw isolation back from mechanisms this platform removed.**
  MI6's hard problem is isolating enclaves on a *speculative, out-of-order, cache-sharing* core; the platform is **in-order, non-speculative**, with **partitioned caches and coherence islands** (§15), so the transient-execution and shared-microarchitecture channels enclaves are engineered to close are absent by construction: the same reason the design needs no enclave-grade speculation fences.
- **Keystone's isolation *is* PMP**: dropped here (the drop-PMP entry above) for CHERI as the sole spatial mechanism; a PMP-region enclave is exactly the coarse mechanism CHERI byte-granularly exceeds.
- **The attested, isolated compartment is already the platform's compartment.**
  A per-app compartment with its own manifest, capability-bounded, attested through the measured root and the sealing service (§9, §12, §14), *is* an enclave: reached from capabilities and single-address-space isolation rather than from a monitor carving regions out of a shared VM.
  The concrete CHERI-native form of the idea is **CHERI-TrEE** (Van Strydonck et al., EuroS&P 2023), which adds flexible enclave primitives (dynamically sized, nested, non-contiguous, memory-sharing enclaves with local attestation) to a capability machine.
  The platform reaches the same isolation from CHERIoT sealing and sentries (§7) under RoT-central rather than per-enclave attestation (§9), and declines CHERI-TrEE's enclave primitives themselves: their runtime create, grow, and nest is exactly the dynamic composition static build-time composition forbids (§7), so the property is kept without a second mechanism.
  The *reasoning* about attestation on such a machine is now Coq/Iris prior art: **Cerisier** (Rousseau et al., PLDI 2026) formalizes exactly the CHERI-TrEE primitives as an extension of the Cerise universal contract (§13), a program logic for trusted, untrusted, and attested code demonstrated on a modeled trusted-sensor component of exactly this shape, so the attested-compartment claim rests on a verified account rather than an assertion.
- **The small *verified* monitor idea is taken further.**
  Sanctum's minimal monitor beside an unverified OS becomes the *whole* verified microkernel (§7) plus the RoT (§9): not a trusted monitor next to untrusted supervision, but a verified supervisor throughout.

**The distilled atom: already banked; the shared lineage is the HDL, not the product.**
Strong isolated attested execution = the CHERI compartment ⋈ measured root ⋈ sealing (§9, §12, §14); the verified-monitor idea = the verified kernel ⋈ RoT (§7, §9).
The MI6/Kôika author overlap is worth naming: the **formal-semantics HDL** lineage (Kami/Kôika) the platform uses to close RTL ⊑ Sail (§18) is *shared* with the enclave-hardware group: but it is the *verification vehicle* that transfers, not the enclave *product*, which addresses threats (speculation, cache-sharing) the profile does not have.

**A software capability-monitor sibling, Tyche, confirms the convergence and the foil.**
Tyche (EPFL DCSL; Ghosn, Castes, Kalani, Bugnion; arXiv 2507.12364) is a recent security monitor of exactly this small-privileged-monitor shape that composes attestable isolation out of **capabilities**: nested *security domains* (enclaves, sandboxes, CVMs) over two monotonic capability-derivation trees with cascading revocation, a platform-independent **capability engine** (a few thousand lines of Rust with no `unsafe`) above a thin hardware **backend** (x86 EPT, RISC-V PMP), and region-transfer attributes: *clean* (zero-on-revoke), *hash* (measure-on-transfer), *vital* (revoke-the-receiver): the intents of which this platform already carries (eager-zeroize §15, reference-integrity-manifest attestation §9, revocation-driven teardown §8).
It independently reaches this design's own structure: the capability model split from the enforcement substrate, monotonic-CDT revocation, a root domain with no special privilege: so it *validates* those choices rather than proposing an alternative to them.
Its motivation, though, is the **foil**: it exists to *retrofit* composable isolation beneath an **untrusted commodity OS** on legacy hardware (Linux domains, KVM/Gramine/Keystone compatibility), it is **unverified** (a fuzzed monitor, not a proved one), it puts side channels and physical attacks out of scope, and its RISC-V enforcement *is* the **PMP** this design drops (drop-PMP, above).
Its cross-core capability-update protocol (IPI-driven, two-barrier atomic) is a concrete reference, but for a **shared-state** engine coherent across cores: the opposite of the share-nothing island model, so the distributed non-coherent revocation reference is [SemperOS](inspirations.md), not Tyche.

**Where it ranks.**
Off the abandon-substrate scale: a convergent / subsumed entry: the design is an *all-enclave machine* (every compartment is one) *without an enclave mechanism*, because it removed the shared-and-speculative substrate enclaves were invented to partition, and it verifies the monitor enclaves keep small-but-trusted.

**Disposition:** no import: hardware enclaves defend against transient-execution and shared-microarchitecture channels the in-order, non-speculative, cache-partitioned, single-address-space profile deletes (§15), and their coarse PMP realization (Keystone) is the mechanism CHERI exceeds (drop-PMP, above); the attested isolated compartment and the small verified monitor are already the CHERI compartment ⋈ measured root (§9, §12, §14) and the verified kernel ⋈ RoT (§7, §9).
The MI6/Kôika formal-HDL lineage is shared as a *verification* vehicle (§18); the enclave product is not needed.
Non-normative; no spec-body change.

---

## Redundant-execution architectures: DIVA checker cores, lockstep, TMR; the asymmetric-trust pattern is the platform's own, spent on simplicity rather than redundancy

The proposal keeps a fast, complex, *unverified* core and buys trust in its results with **hardware redundancy** rather than by simplifying and verifying the core itself.
Three forms: **DIVA** (Austin, MICRO '99: a small, in-order, *formally verifiable* **checker** core re-validates the complex core's every result at commit and overrides it on disagreement, so only the tiny checker need be trusted); **dual-core lockstep** (two identical cores, a comparator flags divergence: random-fault *detection*, as in ARM Cortex-R and the **COSMIC** work); and **TMR / N-modular redundancy** (triple copies plus majority vote: fault *masking* for the SEU/radiation case).

**The steelman: DIVA is philosophically the platform's own move.**
The **asymmetric-trust structure**: a small verified thing validates a large untrusted thing; is exactly what the design runs everywhere: the §6 FPCC checker over untrusted compilers, the CryptOpt Coq-verified equivalence-checker over an untrusted superoptimizer (§5), the §13 admission checker over untrusted binaries.
DIVA is that pattern at the *microarchitecture* level, and if it held it would let a fast out-of-order core be used while keeping the trusted base small: an apparent escape from the in-order IPC tax that seems, at first glance, to spend the platform's own currency.
Lockstep, meanwhile, is **already logged for G5** (COSMIC dual-core lockstep, a fault-*detection* complement to §7's per-core kernel duplication; [inspirations.md](inspirations.md)).

**Why DIVA fails as a strategy: it restores the wrong half of trust.**
- **A DIVA checker validates the *result*, not the *channels*.**
  The complex core it checks is still out-of-order and speculative, so it still carries the **transient-execution, branch-predictor-state, and co-residency timing channels** the profile deletes by construction (§15).
  DIVA lets the design trust *what* a speculative core computed while leaving *how long it took*: and what it prefetched, mispredicted, and evicted; a systematic leak the checker never inspects.
  The platform's threat is not "the fast core computes a wrong result" (rare, and what DIVA catches) but "the fast core leaks through microarchitecture" (systematic, and what DIVA ignores): so DIVA buys down the wrong risk.
- **The design already took the stronger horn of the same asymmetry.**
  Its answer to "small trusted, large untrusted" is to make the **core** the small verified thing: in-order, non-speculative, with RTL ⊑ Sail (§18); so there is *nothing complex to check and no channel to leak*, rather than keep a complex core and bolt a checker beside it.
  *Delete rather than defend*: delete the speculative core, do not defend against it with a checker.
- **Static proof beats per-execution check: the zkVM argument, one layer down.**
  RTL ⊑ Sail proves the one simple core correct **for all inputs, once**; a DIVA checker re-establishes correctness **per execution**, and only functionally: precisely the ordering the zkVM entry (below) draws between a static all-inputs proof and a per-run transcript, DIVA the microarchitectural instance of the weaker side.

**Why lockstep/TMR is orthogonal, not missing.**
Random-fault redundancy addresses *reliability* (SEU, aging, glitch), not the *security* threat, and the reliability case is already partly carried: **ECC across all SRAM** (main memory and every on-die array, caches, register files, scratchpads, native tag bits, and the integrity-tree-node cache, §15), **SRAM's freedom from the Rowhammer disturbance primitive** (§15), **per-core kernel duplication** for blast-radius containment, and crash-only fault containment (§16).
Lockstep/TMR would add fault *detection/masking* on top: genuinely useful for a safety (**G5**) case; but at **2×/3× core area**, and it is already logged on exactly those terms ([inspirations.md](inspirations.md)): a deferred option weighed on cost, not an unconsidered gap.

**The distilled atom: banked at the proof level, deferred at the silicon level.**
The DIVA "small verified checker over large untrusted producer" pattern is banked *pervasively* as the FPCC/CryptOpt/admission discipline (§5, §6, §13): reached where it costs proof surface rather than silicon area, and where the checker validates the **certificate** (memory safety, constant-time, refinement) rather than merely the register file.
RTL ⊑ Sail (§18) is the design's answer to core correctness, static and for all inputs, strictly exceeding DIVA's per-execution functional check.
Lockstep/TMR random-fault masking stays a **G5 gen-2 option**, subtractively admissible at its honest 2–3× area if a safety case ever demands masking over containment.

**Where it ranks.**
Off the abandon-substrate scale (a reliability/verification microarchitecture, not an ISA): DIVA ranks as the *microarchitectural sibling* of the zkVM entry and below the adopted approach on the same "static all-inputs proof beats per-run check" grounds; lockstep/TMR ranks as a deferred G5 reliability option, already logged.

**Disposition:** **DIVA is rejected as a strategy**: it restores functional trust in a complex core while leaving its timing channels (the actual threat) open, and the design takes the stronger horn of the same asymmetric-trust insight: a simple verified core (RTL ⊑ Sail, §18) with nothing complex to check and no channels to leak, its static all-inputs proof exceeding DIVA's per-execution functional check.
The asymmetric-trust *pattern* DIVA embodies is banked at the proof level (FPCC §6, CryptOpt §5, admission §13), checking certificates rather than results.
**Lockstep / TMR** random-fault redundancy is a reliability mechanism orthogonal to the security threat, partly present (ECC, the absence of a Rowhammer primitive in SRAM, kernel duplication; §15, §16) and otherwise **logged for G5** (COSMIC lockstep, [inspirations.md](inspirations.md)) as a deferred 2–3×-area option, not carried by default.
The platform axiom decides it as ever (*trust is the scarce resource, engineering is free, delete rather than defend → verify rather than hedge*): verify one simple core rather than check a complex one, contain random faults rather than replicate against them, until a safety case pays for masking.
**Honest residual (§17):** the single simple verified core has no functional-fault *masking*: a random SEU mid-computation is *contained* (blast radius, ECC; §16) but not voted out the way TMR would; the deferred G5 lockstep/TMR option at 2–3× area; the bet is that ECC ⋈ fault containment ⋈ a verified core with no design faults to outvote covers the random-fault case without N-modular redundancy, replicate-and-vote the cheapest re-admission if avionics/automotive-class fault masking is ever required.

---

## Delete the MMU: purecap single-address-space, CHERI is the sole in-core spatial mechanism

The proposal is to remove **Sv39 and the MMU entirely** and run the die as a **single physical address space** under CHERI, with `satp` fixed to Bare and no translation anywhere.
The claim is redundancy: **CHERI + capability-checked DMA + coherence islands** (§8, §15) already supply the three things an MMU is kept for: byte-granular in-core spatial isolation, a physical-reach bound, and DMA confinement; so Sv39 is a *second, in-band* isolation mechanism bought at the price of the page-table walker, the TLB and walk-cache state, the entire kernel VM subsystem (VSpace / page-table / frame-mapping objects, map/unmap, `satp` management, TLB shootdown), and their share of the Sail model.

**The spec had already converged here without taking the step.**
The Mill entry (above) records that the design *"converges on Mill's single-address-space-with-per-domain-protection vision"* because *"capabilities bound memory irrespective of page tables"*; the MultiZone descend-the-base analysis (above) concedes that *"a stateless single-address-space design leaves most MMU machinery idle"*; and the §13 hardware universal contract is stated as **CHERI + caps + capability-checked DMA**: the MMU already absent from it.
Deleting Sv39 makes the base what the rest of the document already describes.

**It resolves the walker contradiction outright rather than by exemption.**
Admission test 5 (§15) bans *"hardware walkers, updaters, or feedback loops,"* and Sv39's page-table walker is exactly that: an autonomous, address-dependent memory-reader with TLB and walk-cache state that the fence.t flush-set, the WCET model, and the partitioning story never booked (the same ground `Svadu`'s A/D-update walker was excluded on).
The choices were to *state an exemption principle* for the read-side walker or to *delete it*; deleting the MMU takes the second and stronger horn, so test 5 stands with **no in-profile exception**, the flush-set and WCET tables shed the walk terms, and the composition-frozen-page-table fallback (a fixed-table walker that still needs that exemption, and TLB state that still joins the flush-set) is subsumed: deleting the walker is strictly stronger than freezing what it reads.

**The honest counterargument: and why it does not hold at the base.**
Sv39 would give an **MMU-disjoint intra-core isolation layer** that could still separate compartments if CHERI itself had a logic fault; deleting it concentrates in-core spatial isolation on one mechanism.
Three things answer this.
(1) The coarse **PMP backstop** that could supply a CHERI-disjoint failure domain is itself dropped (the drop-PMP entry below): rather than hedge a CHERI *logic* fault with a second in-band mechanism, the platform hedges it with the **formal verification of CHERI** (RTL ⊑ Sail §18; the Oxford/Google CHERIoT-Ibex conformance proof; Codasip's app-class deployment): *verify rather than hedge*.
(2) In the single-address-space model the design already converges on (the Mill entry above), the MMU **never supplied a per-compartment second layer to begin with**: intra-core compartments are separated by CHERI bounds over one shared map, so the page tables would be an identity-shaped translation, not the disjoint per-compartment isolation the fault argument imagines: the "second layer" was largely notional. (3) Keeping it would mean **carrying an admission-test-5 violation** (the autonomous walker) as standing defense-in-depth, trading the profile's own determinism rule for a layer whose fine-grained disjointness the SAS design does not actually instantiate.

**The bet, stated.**
Single-address-space CHERI at *application-class* scale rests on **CheriOS** and **CHERIoT** as existence proofs, and both are small-scale; app-class SAS-purecap is the wager this takes.
It is bounded, not blind: CHERI is the **primary, byte-granular, formally-modeled** mechanism the whole design already leans on (§8, §13); capability-checked DMA and coherence-island separation cover the device-access and cross-domain-timing residuals a page table never addressed anyway (physical-reach resting on CHERI partition bounds, PMP dropped: the drop-PMP entry below); and because the kernel is **bespoke** (seL4's capability / IPC *design* re-proved in Coq, not stock seL4's C), it is built single-address-space-native, dropping the VSpace object classes, rather than retrofitting SAS onto a page-table kernel.

**This is not the descend-to-PMP-only move.**
The rejected MultiZone descent (above) shed the MMU *and CHERI*, falling back on coarse PMP as the primary mechanism; this sheds **only** the MMU and keeps CHERI as the byte-granular primary.
The two share a silhouette (no Sv39) and nothing else: one deletes the redundant second layer and keeps the strong first, the other deletes the strong first and keeps the weak second.

**Where it ranks, and its relation to kernel-in-gateware.**
This lands one of the three simplifications the kernel-in-gateware entry (below) names as its kernel-shrink terminus: **single-address-space CHERI isolation deleting the VM subsystem**; as a *base* move rather than a gen-2 one, and it subsumes the composition-frozen-page-table fallback (there are no tables left to freeze).
The remaining kernel-shrink simplification the terminus names: the table-driven cyclic executive replacing MCS; is **also adopted** (§7, §11).

**Disposition (adopted; normative in §7, §8, §14, §15).**
The MMU is **deleted**: `satp` is Bare, there is no Sv39 / Sv48 / Sv57 and no `Svadu` / `Svade` A/D machinery (§15), the kernel drops seL4's VSpace / page-table / frame-mapping object classes for a single physical address space (§7), and **CHERI is the sole in-core spatial mechanism** (with PMP dropped too: the drop-PMP entry below; so no disjoint in-band backstop remains), capability-checked DMA + coherence islands (§15) the device-access and timing boundaries.
The platform axiom decides it as ever (*trust is the scarce resource, engineering is free, delete rather than defend*): the MMU is a second in-band mechanism whose fine-grained defense-in-depth the SAS design does not instantiate, purchased with a walker the admission test bans and a kernel subsystem the proof must carry.
**Honest residual (§17):** in-core spatial isolation rests on CHERI alone (a logic fault has no in-band fallback; the coarse PMP backstop is dropped too, below; only CHERI's own verification), and application-class single-address-space purecap is less battle-tested than page-table isolation (CheriOS/CHERIoT are small-scale): offset against a net deletion of the walker, the TLB/walk-cache state, the VM subsystem, and their Sail surface.

---

## Single privilege mode: Machine mode only, capability-gated privilege (CHERIoT-lineage)

The proposal is to delete **Supervisor and User modes** and run the die in **Machine mode only**, expressing privilege as a **CHERI permission on the program-counter capability** (the access-system-registers permission, CHERIoT-style) rather than a hardware privilege ring.
The claim is the same redundancy the MMU-deletion took one step earlier: once CHERI is *"the sole in-core spatial mechanism"* (§15), the S/U ring is a *second, in-band* privilege mechanism: a compartment is already confined by the capabilities it holds, so gating privileged operations (CSR access, interrupt-enable, context switch, sealing) by a **permission** rather than a **mode** removes the ring, its CSR bank (`sstatus`/`stvec`/`sepc`/…/`scounteren`), trap delegation (`medeleg`/`mideleg`), `sret`, and `Sstc`: and the mode-transition reasoning from the kernel proof; while losing nothing CHERI was not already enforcing.

**CHERIoT is the existence proof, and it has silicon.**
CHERIoT (Microsoft/lowRISC, contributed to the RISC-V standardization effort) is Machine-mode only by design (*"hierarchical privilege modes are unnecessary, so CHERIoT CPUs support only Machine Mode"*): with privilege carried by *"a permission that allows access to certain control and status registers … when a capability with that permission is installed as the program counter capability."*
Its trusted **switcher** (~300 instructions, seL4-scale) mediates cross-compartment and cross-thread transitions holding one reserved register, is itself CHERI-constrained, and is under formal verification (Oxford against the Sail model; Google on the switcher's isolation properties); first CHERIoT silicon taped out in early 2026.
The single-Machine-mode model is thus a verified, fabricated one: the privilege-architecture analog of the CheriOS/CHERIoT single-address-space existence proof the MMU deletion already leans on.

**The spec had already converged here.**
The per-core inventory (§7) had M-mode *"quiescent after boot"* and the kernel as the sole S-mode occupant with U-mode *"everything else"*: three rings for what is really *one trusted kernel beside many CHERI-confined compartments*.
The powerbox, the capability manifests, the ring data plane, and W^X are already **capability** statements, not ring statements.
Collapsing to one mode makes the enforcement substrate match the design the rest of the document already describes: authority is a capability, top to bottom.

**The honest counterargument: and why it holds at the base.**
The S/U ring gave (a) a hardware-privilege boundary preventing an app from executing privileged instructions regardless of CHERI, and (b) the privilege-layering that let the **PMP backstop** sit *below* the kernel.
Both are answered.
(1) In the CHERIoT model, privileged instructions are gated by the **PCC system-register permission**, which no compartment's PCC carries: so a compartment cannot execute a privileged CSR access for the same reason it cannot forge a pointer: the authorizing capability is *absent*, an unforgeable condition, not a mode bit an exploit might flip.
(2) The crown-jewel backstop role needs **no privilege ring**: and, as the drop-PMP entry below records, no PMP either: immutable-text/W^X, the per-core partition bound, and crown-jewel secret fencing rest on CHERI monotonicity (§7, §14), the crypto core's hardware boundary, and TME (§15), with the CHERI-*logic*-fault hedge being CHERI's own verification, not a coarse disjoint layer.
The boot/M-mode firmware still runs first, establishes the initial capability distribution, and goes quiescent; the microkernel is the resident Machine-mode holder of the system-register permission; nothing else holds it.

**The bet, stated.**
CHERIoT is **single-core, microcontroller-scale** (2–7-stage pipelines, tens of KiB–MiB), and its own multicore is future work; this platform is an **application-class multikernel** on multicore.
Single-privilege-mode purecap at that scale is a genuine extrapolation: the privilege-architecture sibling of the single-address-space bet (§17).
It is bounded, not blind: privilege-as-capability is *more* fine-grained and *more* uniform than the ring it replaces (CHERIoT's whole thesis), verified CHERI is the safety net (the coarse PMP backstop is dropped too: the drop-PMP entry below), the kernel is verified, and the in-order non-speculative core is exactly the target CHERIoT's permission/sentry model was designed for (the source notes it *"would be difficult on very large out-of-order cores"*, which this platform is not).

**This is not the descend-to-PMP-only move.**
The rejected MultiZone descent (above) shed the MMU, the S-mode ring, **and CHERI**, falling back on coarse PMP as the *primary* mechanism with trap-and-emulate ambient authority.
This sheds the rings and keeps **CHERI as the byte-granular primary**, with PMP only the locked coarse backstop.
The two again share a silhouette (a Machine-mode kernel) and nothing else: one governs privilege with unforgeable capabilities, the other with a handful of coarse regions and instruction emulation.

**Disposition (adopted; normative in §7, §8, §15).**
Supervisor and User modes are **deleted**: the platform runs Machine mode only, privilege is the CHERIoT-lineage access-system-registers permission on the PCC, the S-mode CSR bank / trap delegation / `sret` / `Sstc` are removed (§15), and the microkernel is the resident Machine-mode holder of the system-register and switch/seal authority (§7); PMP itself is dropped too (the drop-PMP entry below), so CHERI is the sole in-band spatial mechanism and no disjoint backstop remains.
The platform axiom decides it as ever (*trust is the scarce resource, engineering is free, delete rather than defend*): the S/U ring is a second in-band privilege mechanism, and its one non-redundant service (the sub-kernel backstop) is itself dropped as redundant against verified CHERI (below).
**Honest residual (§17):** privilege rests on CHERI alone (PMP dropped too, below) with no privilege-ring or disjoint-backstop redundancy, and single-privilege-mode purecap is unproven at application-class multicore scale (CHERIoT is single-core microcontroller): offset against the deletion of the mode-transition machinery, the S-mode CSR bank, and trap delegation from the microarchitecture and the kernel proof.

---

## Drop PMP: CHERI is the sole memory-protection mechanism, verified rather than hedged

The proposal is to remove **physical memory protection (PMP)** and `Smepmp` with it, leaving **CHERI as the only memory-protection mechanism on the die**.
It completes the arc the MMU deletion and the mode collapse began: PMP is a *third* in-band spatial mechanism (after Sv39 and the S/U ring, both likewise deleted), and RISC-V PMP provides a **strict subset** of CHERI's protection at coarse (≈16-region) granularity, so once CHERI is present and formally modeled, PMP is redundant Sail surface.

**The industry has already taken this step at application-class scale.**
CHERIoT drops PMP outright (*"the RISC-V PMP provides a subset of the protections of a CHERI system and so it, too, can be removed"*).
More tellingly for a platform of this class, **Codasip's A730**: a dual-issue *application* core, not a microcontroller; removes the PMP unit on exactly this ground: *"Most RISC-V cores included a physical memory protection (PMP) unit… both costly in area and power hungry.
With the fine-grained protection and compartmentalization of CHERI this unit can be removed and replaced by more power- and area-efficient circuits."*
The CHERI research program (Cambridge/SRI, with Microsoft Research and INRIA) is the assurance base that makes dropping the coarse hedge defensible: CHERI's fundamental architectural security property, **reachable-capability monotonicity**, is *already machine-checked over a full-scale CHERI ISA* (Bauereiss et al., *Verified Security for the Morello Capability-enhanced Prototype Arm Architecture*, ESOP 2022, in Isabelle, via an abstraction that holds for arbitrary CHERI ISAs), so what remains for this profile is the **RTL ⊑ Sail** arrow (the least-built layer, §18) and a Coq-native restatement over the CHERI-RISC-V model, with the Oxford/Google CHERIoT-Ibex conformance proof the microcontroller-scale bring-up evidence.

**Where PMP's three backstop roles go.**
A locked-PMP backstop (weighed in the MultiZone entry above) would serve three coarse crown-jewel roles, each of which instead collapses onto a mechanism already present: (a) **immutable-text / W^X** on kernel and firmware text and the read-only content-addressed image is the CHERI capability-monotonicity invariant of §14: no writable capability to those regions is ever derived, so there is nothing for a second mechanism to re-enforce; (b) the **per-core physical-partition bound** is CHERI, each core's kernel instance is delegated a root capability bounded to its partition, and monotonicity (§7) lets it derive nothing outside it; (c) **crown-jewel secret fencing** is the crypto core's own hardware boundary plus TME (§15), keys never leave the core, and anything resident outside it is ciphertext.

**The honest counterargument: the one thing genuinely lost.**
PMP's unique value is that it is **disjoint from CHERI**: an independent failure domain that would still bound each core if the CHERI machinery itself had a *logic* fault.
Dropping it means in-core spatial isolation, W^X, and the partition bound rest on **one** mechanism with no in-band redundancy.
This is answered the way the whole platform answers single-mechanism concentration: not with a second mechanism but with **proof**: CHERI is the mechanism the design verifies most deeply (the RTL ⊑ Sail workstream §18, the Oxford/Google CHERIoT-Ibex conformance result, Codasip's shipping app-class core), so the hedge against a CHERI implementation fault is the *verification* of CHERI, not a coarse subset of it running alongside.
And the residual that actually persists: fabricated silicon vs. verified RTL; is unchanged by keeping or dropping PMP (both share the one mask set, §17), so PMP bought no protection against it.

**The bet, stated.**
Resting all in-core spatial protection on CHERI is the same wager as single-address-space and single-privilege-mode, with no coarse fallback at all.
It is bounded, not blind: CHERI is byte-granular, formally modeled, and the most-scrutinized mechanism on the die; capability-checked DMA still confines device access and the coherence islands still bound cross-domain timing (neither was ever PMP's job); and the disjoint hedge is replaced by the strongest assurance the project has.
If a future analysis judged the CHERI-logic-fault residual intolerable, the composition-static locked-PMP backstop is the cheapest thing to re-admit (subtractive, static, Sail-modeled): but it is not carried by default.

**Disposition (adopted; normative in §7, §14, §15).**
PMP and `Smepmp` are **removed**: CHERI is the sole memory-protection mechanism, W^X and the per-core partition bound rest on CHERI monotonicity (§7, §14), crown-jewel secrets on the crypto core's boundary and TME (§15), and device DMA on capability-checked DMA (§15).
The platform axiom decides it as ever (*trust is the scarce resource, engineering is free, delete rather than defend*), with the twist the whole design turns on: what lets a **single** mechanism replace a defense-in-depth stack is that this one is **formally verified**, so *delete rather than defend* becomes *verify rather than hedge*.
**Honest residual (§17):** in-core spatial isolation, W^X, and the partition bound rest on CHERI alone with no in-band disjoint backstop; the sole hedge against a CHERI logic fault is CHERI's own verification (its reachable-capability-monotonicity property already machine-checked over a full-scale CHERI ISA, Bauereiss et al. ESOP 2022; the RTL ⊑ Sail arrow, §18, the residual, plus Oxford/Google and Codasip), the fab residual unchanged.

---

## Drop the IOMMU: capability-checked DMA, CHERI as the sole spatial mechanism system-wide

The proposal is to remove the **IOMMU** and to decline its device-side-PMP cousin the **IOPMP** with it, confining device DMA by **CHERI capabilities carried into the interconnect** rather than by an address-translation unit or a region-protection table.
It is the device-side completion of the arc the MMU deletion, the mode collapse, and the PMP drop began: the IOMMU is to the DMA path what the MMU is in-core: an address-translation unit with a page-table walker, translation caches (IOATC), and in-memory device/context structures; and in the single physical address space this platform already adopts (the MMU-deletion entry above), its *translation* is unused; only its *protection* is wanted, and CHERI supplies that unforgeably and byte-granularly.

**The mechanism, and why it is not merely IOPMP.**
Every DMA-capable block becomes one of two capability-checked shapes: a **core-issued capability-operand mover** (the §15 coprocessor-line discipline the matrix and FEC units already follow: no independent mastership), or an **autonomous streaming engine holding a delegated, bounds-checked, revocable capability** for its window (scanout, transceiver-I/Q, NIC), with the fabric checking each access against a capability at the point of issue.
This both **deletes translation** and is stronger than switching to an **IOPMP**: the IOPMP would confine DMA, but as a coarse, ambient, per-source-ID region table **disjoint from CHERI**: the device-side PMP, rejected on the identical ground the in-core PMP is (the drop-PMP entry above).
Adopting IOPMP would trade the IOMMU's translation weight for a *second ambient spatial mechanism*; adopting capability-checked DMA *unifies* the device path onto the one mechanism the die already carries, so "who may DMA where" is a capability in the static topology (§7/§8), not a side table: *verify rather than hedge* taken to the device edge, and a device MSI (a store to an interrupt file, §8) confined by the same check rather than an interrupt-remapping table.

**The prior art is proposed and prototyped, not hoped for.**
The Cambridge/SRI position paper **"Defending Direct Memory Access with CHERI Capabilities"** (Markettos, Baldwin, Bukin, Neumann, Moore, Watson; HASP 2020) proposes exactly a capability-configured DMA controller that bounds-checks accesses from malicious peripherals (pluggable and SoC-embedded alike) and contrasts it with the IOMMU's nested-page-table translation.
The **CHERI Alliance "CHERI at SoC Level"** guide (2025) specifies passing **capabilities, tags, and revocation** between CHERI-enabled IP blocks of varying CHERI-awareness, clearing tags on non-capability IP writes: the SoC-integration discipline this needs.
Capability-holding DMA is demonstrated at **CHERIoT** scale (first silicon 2026).
The deletion is sound *only because* the device model is already curated register-slave / transducer / on-die RTL (§4, §12): there is no foreign PCIe bus-master ecosystem issuing raw physical addresses the IOMMU exists to catch.

**The one accelerator alternative it declines: retrofitting CHERI-unaware IP.**
A newer result from the same group, **CapChecker** ("Adaptive CHERI Compartmentalization for Heterogeneous Accelerators"; Cheng, Markettos et al., ISCA 2025), takes the converse tack to the native path above: it interposes a capability-checking unit at the memory interface of a **CHERI-*unaware*** accelerator, so unmodified (often third-party or opaque) accelerator IP gains fine-grained protection at low overhead.
That is exactly the road the no-foreign-computers mandate (§4) forecloses: the unaware, self-mastering, opaque accelerator is the category it excludes by name, and the coprocessor line (§15) makes the compute units (V/M-class, FEC) CHERI-native, core-issued capability-operand movement, no independent mastership, so no unaware self-mastering block remains to wrap.
Its checking *function* is in any case what the capability-checked fabric above already performs at the point of issue: for the curated firmware-free streaming engines the platform does keep, the fabric *is* the checker, and a CapChecker shim would be the hedge *verify rather than hedge* declines.
What survives the mandate is CapChecker as a **feasibility datapoint**, boundary capability-checking on real heterogeneous accelerators at low single-digit overhead (quantified in performance-estimates.md), corroborating that the capability- and tag-carrying-fabric obligation above is cheap, not a reason to admit the CHERI-unaware accelerator it was built to rescue.

**The honest counterargument: the two obligations it names.**
Dropping the IOMMU removes the one DMA-side mechanism *disjoint* from CHERI, so device access now rests on CHERI too: the single-mechanism concentration the PMP drop books, extended to the device edge, hedged the same way (CHERI's own verification: RTL ⊑ Sail §18, the Oxford/Google CHERIoT-Ibex result).
Two obligations are genuinely new relative to a translation-IOMMU and are booked in §17: (1) **in-flight-DMA revocation**: a capability held by a running transfer must honour the §8 revocation sweep so time-to-containment stays bounded (a load-barrier / revocation-epoch check, Cornucopia-Reloaded-lineage, or bounded re-authorized windows); (2) a **capability- and tag-carrying fabric**: the interconnect must propagate capabilities, tags, and revocation state to the DMA blocks (new Sail / RTL ⊑ Sail surface, §15/§18).
Application-class capability-DMA at NIC / scanout / radio-I/Q bandwidth is net-new (§18); microcontroller-scale is the existence proof.

**Disposition (adopted; normative in §4, §12, §15).**
The IOMMU is **deleted** and the IOPMP **declined**: device DMA is capability-checked by the fabric, every DMA-capable block is a core-issued capability-operand mover or a delegated-capability-holding streamer, and CHERI becomes the sole spatial mechanism **system-wide**: cores and devices alike.
The platform axiom decides it as ever (*trust is the scarce resource, engineering is free, delete rather than defend* → *verify rather than hedge*): the IOMMU is a second, device-side spatial mechanism (carrying a walker and caches the profile bans in-core), redundant once the fabric carries capabilities, and the IOPMP is the coarse subset of CHERI it is in-core.
**Honest residual (§17):** device access rests on CHERI alone with no IOMMU-disjoint backstop; in-flight-DMA revocation and a capability/tag-carrying fabric are new obligations (Markettos-2020 and the CHERI-at-SoC-Level guide anchor feasibility, Cornucopia-Reloaded the revocation), and application-class capability-DMA is net-new (§18), microcontroller-scale the existence proof.

---

## Delete scalar floating-point: fold all float onto the vector FPU, static rounding

The proposal is to remove the **scalar `F`/`D` floating-point extensions** (the `f0`–`f31` register file, the scalar FP instruction set, and the dynamic rounding-mode CSR) and route **all** floating point through the **RVV floating-point unit every core already carries**.
It is the profile-parsimony move the MMU deletion, the mode collapse, and the PMP drop made, applied to the largest remaining orphaned *datapath* rather than a protection mechanism: the profile is RV64IM**V**, and even the C-class control cores carry VLEN=256 vector (§15), so scalar `F`/`D` is a *second* FP datapath behind a vector FPU that can already do everything it does.

**What is redundant, and what is not.**
The vector FPU performs the same IEEE-754 arithmetic; a "scalar" float is just a single-element (VL=1) vector operation on it.
So the scalar instruction class, the `f`-register file (context-switch state and a fence.t flush-set member), and, decisively, the *scalar* fixed-latency-FPU-including-subnormals timing contract plus the scalar `FDIV`/`FSQRT` constant-time carve-out are all redundant.
That last item is the prize: it is **one of the two floating-point timing crown jewels** (§15), and folding onto the vector unit *deletes* it rather than re-proving it: the contract is stated once, for the one FPU, not twice.
What does **not** vanish is the FP arithmetic itself (adders, multipliers, subnormal handling, divide/sqrt): it lives on the retained vector FPU, which still owes the fixed-latency-including-subnormals contract.
This is a consolidation-and-deletion of the *scalar wrapper*, honestly, not an elimination of floating point.

**Static rounding falls out for free.**
With no scalar FP, the only remaining rounding-mode consumer is vector FP, and mandating **static rounding** (the mode encoded per-instruction, default round-to-nearest-even) deletes the dynamic `frm` CSR: a mutable field that would otherwise context-switch and join the fence.t set; exactly the determinism the profile already imposes on branch prediction and atomics (no hidden mutable state surviving a partition switch).

**The honest counterargument: and why the axiom overrides it.**
Two things are genuinely given up.
(1) **Ubiquity of scalar float.**
Ported userspace (UI layout, coordinate math, general numerics; §12/[userspace-porting.md](userspace-porting.md)) uses scalar float pervasively, and the standard RISC-V `lp64d` ABI passes it in `f` registers; folding it onto VL=1 vector ops means a **soft-float-register ABI** and per-operation `vsetvli`/`vmv` setup.
(2) **A non-standard ISA.**
The application-class `V` extension formally *requires* `F`/`D` (it depends on `Zve64d`, which depends on `D`), so vector-FP-without-scalar-FP is a **fork** of the base ISA, carrying its own Sail surface for the integer-register-to-vector-FP move path.
Both costs land on the axes the platform spends freely (*engineering is free; performance is subordinated*, §1): and buy down the scarce one: a deleted timing crown jewel, a deleted register file, and deleted rounding-mode state, on a Sail model and toolchain the project already curates from scratch.

**The bet, stated.**
Vector-FP-without-scalar-FP at application scale is uncommon (most RVV cores keep scalar `F`/`D` for exactly the ABI reasons above), so this is a bounded extrapolation like the single-address-space and single-privilege-mode bets: bounded because the vector FPU is the *same* IEEE-754 unit, the fold is a mechanical compiler lowering (VL=1 ops in the `Zfinx`-adjacent idiom of sourcing FP operands outside a scalar-FP register file), and nothing about correctness changes, only where the operands live and what they cost per op.

**Disposition (adopted; normative in §15).**
Scalar `F`/`D`, the `f`-register file, and the dynamic rounding-mode CSR are **removed**; all floating point is vector (VL=1 for scalars), rounding is static, and the ABI is soft-float-register.
The FP timing contract is stated once, for the vector FPU (§15).
The platform axiom decides it as ever (*trust is the scarce resource, engineering is free, delete rather than defend*): a redundant FP datapath and one of the two FP timing crown jewels are deleted for an ABI change and a per-op vector-setup cost the subordinated-performance goal absorbs.
**Honest residual (§17):** floating point rests on the single vector FPU under a non-standard vector-FP-without-scalar-FP profile (a small new Sail surface for the operand-move path, an uncommon configuration at application scale): offset against the deleted scalar datapath, `f`-register file, scalar FP timing contract, and dynamic rounding-mode state; a net shrink, booked in §17's proof-trust-base accounting.

---

## Mon CHÉRI conditional capabilities: reject the binary-side extension, adopt Write-before-Read as a transparent initialization-tag plane

Where the trilogy above *deletes* mechanisms down to CHERI, this entry weighs *extending* CHERI.
**Mon CHÉRI** (Gülmez/Englund/Mühlberg/Nyman, IEEE S&P '25) adds **conditional permissions** to the capability model: a permission conferred only once a prior operation has occurred (a write, after which read or execute is granted); tracked by an **operation-specific bound (OB)** recording the sub-range of a capability's bounds a given operation has already covered.
The flagship policy is **Write-before-Read** ("no read of memory that has not been the subject of at least one write"); the paper defines seven such permissions (the Write-before-{Read,Execute} family with their exactly-once "-Only" variants, plus Write-Once, Read-Once, Execute-Once).
It targets the one memory-safety class CHERI leaves open: Microsoft's CHERI-ISA analysis found that ~12% of its assessed vulnerabilities need uninitialized-memory protection that spatial capabilities and revocation-based temporal safety do not provide.
The prototype is a CHERI-Flute64 FPGA softcore plus a CHERI-LLVM toolchain: ~3.5% CoreMark overhead over purecap (~2% area), 100% detection with ~1% false positives on the Juliet CWE-457 suite.
The steer ("implement even a subset; a small part might be transparent to the compiler and run on normal CHERI binaries; write-then-read is a universal requirement") decomposes, in this document's manner, into three separable questions: (a) the general conditional-permission / operation-bound machinery; (b) Write-before-Read specifically; (c) the *transparent, always-on, stock-binary* reading of it.

**The steelman: four real cards.**
(1) **A genuine gap.**
The platform has concentrated all in-core spatial safety on CHERI and its temporal safety on revocation (§8, the drop-PMP entry above), and uninitialized-memory *use* is the one memory-safety class neither covers: the Tier-2 certificate (§13) proves *spatial + temporal* safety and is silent on initialization.
(2) **The encoding is admission-test-clean.**
Mon CHÉRI keeps the write-progress state *in the capability itself* (16 bits stolen from the top of the cursor), not in shadow memory: so it passes all five parts of the §15 admission test for the same reason the design likes CHERI: the state is the architecturally-visible capability, not hidden per-address metadata surviving a partition switch, and the OB advances only as the direct writeback of an executed store, not as an autonomous walker.
(3) **It extends the one hedge the platform deliberately keeps.**
The CHERI universal contract (Cerise-style, §13) is retained *beneath* the Tier-2 certificate as defense-in-depth; Write-before-Read is the initialization sibling of that spatial backstop.
(4) **It abandons no substrate**: a backward-compatible CHERI-RISC-V extension the bespoke CHERI (§1) could absorb, unlike the belt/EPIC/Wasm targets.

**What is rejected, and what is adopted: the binary encoding versus the property.**
The steer resolves it: *no bespoke CHERI extension on the binary side, but a custom microarchitecture that runs stock CHERI binaries is fine, ideally Coq-verified.*
That line runs exactly between Mon CHÉRI's two halves.
- **The binary-side conditional-capability *encoding* is rejected: it is the bespoke binary extension the platform declines.**
  Mon CHÉRI is **opt-in per capability** (the default disables enforcement; the allocator or compiler must emit a `CSetOpBounds`-family instruction such as `csetwbrbound`), **needs a store-linearization compiler pass** (21% false positives without it, because the operation-bound rides *in* the capability and ordinary codegen spills and duplicates capabilities into stale copies), **assumes sequential writes**, and steals capability-cursor bits: a change to the capability format and to the compiled instruction stream, i.e. special binaries.
  That is precisely what the steer rules out, and it enlarges the CHERI-RISC-V Sail model, the RTL ⊑ Sail refinement, CHERI-CompCert, and the CHERI-TAL soundness metatheorem (non-monotonic permission *regain* against the linear/affine capability discipline).
- **But the *property* separates from the encoding, and the separated form is transparent: this is adopted (§15).**
  Move the write-progress state out of the capability and into an **address-indexed initialization-tag plane**: a sibling of the CHERI validity tag, reset to *uninitialized* by eager-zeroize (`cbo.zero`, §7), set by any ordinary store, checked on data loads: and Write-before-Read runs on **stock CHERI binaries** with **no capability-encoding change, no new instruction the binary emits, and no store-linearization** (any store to the granule discharges its obligation, so correct code never false-faults; the false-positive problem that forced Mon CHÉRI's compiler pass was an artifact of the in-capability encoding).
  It is a custom microarchitecture, not a binary-side change: exactly the deviation the steer permits; and it rides the *existing* validity-tag datapath, so it is cheap in silicon and in proof.
  The compiler-transparent alternative Mon CHÉRI's authors themselves float: a shadow-memory "written" bitmap; is a *separate, hidden* per-address structure; the tag-plane form instead extends the metadata plane CHERI already maintains and reasons about, keeping it architectural state reset by eager-zeroize, not hidden microarchitectural state.
- **The value is scoped by what is already discharged: which is why the mechanism is defense-in-depth, not a universal fault.**
  Disclosure is already the platform's position (eager-zeroize + `Zicboz`, §7/§15); the exploitable *pointer* case is already the validity tag (an uninitialized granule bears no tag) plus the absence of ASLR under the single address space (§7); and uninitialized *use* in trusted and contained code is proven or enforced absent (safe-Rust definite-initialization, verified C, Lustre, §5).
  So the tag plane's marginal guarantee is fail-stop on uninitialized *data* use in `unsafe` blocks and wholly-unverified code: strengthening the hardware universal contract (§13) exactly where hardware is the only guarantee, which is consistent with *verify rather than hedge* (it hedges no verified mechanism, it adds a guarantee for code with no proof), not a breach of it.

**The distilled atom: Write-before-Read, and its verified vehicle is already in the trust base.**
Of the seven conditional permissions, **Write-before-Read is the one non-redundant atom** for this platform: Write-before-Execute and Execute-Only/XOM are already covered by W^X under CHERI monotonicity (no writable-then-executable capability is ever derived, §14), Execute-Once anti-code-reuse by no-runtime-codegen + CFI + CHERI (§13, §14), and Write-Once/Read-Once are niche.
Two facts make the atom unusually cheap to re-home.
First, the store-linearization obligation the paper carries as an LLVM pass is a *linearity* problem, and the paper's own future work observes it is simpler in borrow-checked languages, Rust the prominent example, the platform's contained code *is* safe Rust carrying **CHERI-TAL** linear/affine capability types (below), so the compiler half is largely already discharged.
Second, and decisively, the **Coq-verified vehicle already sits in the trust base**: Georges et al.'s *uninitialized capabilities* (POPL '21) mechanize exactly Write-before-Read in the **Iris/Cerise** capability-machine logic the platform already relies on for its universal contract (§13).
The adopted mechanism re-homes onto that verified lineage: the **address-indexed sibling** of its theorem, proved in the one prover; the same move this document makes elsewhere (adopt the *design*, re-home the *proof* onto Coq: seL4 below, VeriBetrFS in §10), here applied to a capability *extension*.
Mon CHÉRI's own LLVM/Bluespec prototype is unverified and finer-grained (sub-object, stack and heap, FPGA-real); the platform trades that precision for the transparent, verified, tag-plane form.

**Where it ranks.**
It is the **most importable of the "change the ISA" entries**: it abandons no substrate and fuses nothing; and, once the property is decoupled from the binary encoding, it is not merely importable but **imported**: the transparent tag-plane form is the rare CHERI *extension* that costs almost nothing on the scarce axes (one bit on an existing plane, one invariant in the existing prover) while running stock binaries.

**Disposition (adopted in part; normative in §15).**
The **property**: Write-before-Read; is adopted as a **transparent, address-indexed initialization-tag plane** (a sibling of the CHERI validity tag, reset by eager-zeroize), enforced on **stock CHERI binaries** by microarchitecture and verified in the one prover as the address-indexed sibling of the Coq-verified Iris/Cerise uninitialized-capabilities result (§15).
Mon CHÉRI's **binary-side conditional-capability *encoding***: the per-capability operation-bound, its `CSetOpBounds` instructions, and the store-linearization it forces; is **rejected**: it is the bespoke binary-side CHERI change the platform declines, and its extra precision is not worth special binaries plus the Sail / RTL / toolchain / CHERI-TAL surface.
The other six conditional permissions do not import (already covered by W^X, by no-codegen + CFI, or niche).
**Honest residual (§17):** the tag plane is the one place the profile *adds* a mechanism rather than deleting one: booked as cheap defense-in-depth (granule-granular, heap/static-first, stack precision an optional compiler assist), strengthening the universal contract where hardware is the only guarantee, consistent with *verify rather than hedge*.

---

## Tagged metadata-processing architectures: the SAFE project, micro-policies, the PUMP; the tag-monitor genus *is* the substrate, the programmable rule-cache fails the admission test

Where the Mon CHÉRI entry above *extends* CHERI with one conditional-permission policy, the DARPA CRASH/SAFE lineage proposes the maximal form of the same move: a **programmable engine for arbitrary tag policies**.
The SAFE machine's tagged architecture, its **micro-policies** framework (Azevedo de Amorim/Dénès/Giannarakis/Hriţcu/Pierce/Spector-Zabusky/Tolmach, IEEE S&P '15, mechanized in **Coq**), the **PUMP** (Programmable Unit for Metadata Processing; Dhawan/Hriţcu/Rubin/Vasilakis/Chiricescu/Smith/Knight/Pierce/DeHon, ASPLOS '15), and its commercial realization **Dover CoreGuard** (software-defined metadata processing, SDMP) all rest on one idea: every word carries a large metadata tag, and on every instruction a hardware **rule cache** checks a software-defined policy over the operand tags, trapping to a software **policy monitor** on a miss (which resolves the rule and installs it).
Run it through the import discipline: the decomposition that logged the belt's spiller and EPIC's NaR while rejecting the rest; and it splits into four separable parts: (a) the **tag-monitor *model*** (security as a property of per-word metadata checked in the datapath); (b) the **programmability** (arbitrary policies loaded as software, hardware-accelerated by the rule cache); (c) the **policy *catalog*** (the specific verified micro-policies: IFC, memory safety, CFI, compartmentalization, dynamic sealing); (d) the **Coq metatheory** (a machine-checked generic monitor + per-policy refinement).

**The steelman: four real cards, and it is unusually spec-coherent in genus.**
Unlike the belt/EPIC/Wasm targets it **abandons no substrate**: the PUMP is a tag coprocessor beside a conventional host, and CoreGuard rides a *RISC-V* host; so the substrate-cost objection fatal to EPIC does not apply.
(a) **The metatheory lives in Coq.** Micro-policies ship a machine-checked generic-monitor theorem with per-policy refinements in the platform's own prover, and **"A Verified Information-Flow Architecture"** (Azevedo de Amorim et al., POPL '14) carries a tagged IFC machine end-to-end, hardware to abstract: the *hardware* sibling of the seL4/Cerise verification the design already leans on.
(b) **One mechanism, many policies**: memory safety, IFC, CFI, compartmentalization, and sealing are all instances of the same tag-check, a genuine economy-of-mechanism claim.
(c) **It is CHERI's own genus.** A capability is metadata bound to a word and checked in the datapath; CHERI *is* a tag-monitor, so the model is not foreign: it is the family the design already belongs to.
(d) **It targets the same gap Mon CHÉRI does**: the IFC and initialization micro-policies address exactly the residual memory-safety classes the design chases with flow labels and the Write-before-Read plane.

**Why it fails for *this* design: the programmability is the cost, not the win.**
- **The rule cache fails the admission test, twice: the ALAT disposition verbatim.**
  The PUMP's defining mechanism is a hardware **rule cache**: a hidden table whose occupancy records which (opcode, operand-tag-tuple) combinations have been seen and admitted.
  That is **new hidden shared microarchitectural state surviving a partition switch**: it **fails test 3** exactly as the dynamic predictor, the LR/SC reservation set, and EPIC's ALAT do (the state the profile *deletes* rather than flushes).
  And a rule-cache **miss** traps to the software monitor at a large, tag-pattern-dependent latency, so hit/miss timing is **data-dependent on the operand tags**: which, under the flagship IFC policy, *are the secret labels*; so it **fails test 2** (a tag-history timing channel that is neither constant-time nor provably secret-unreachable, landing squarely on that test's "no secret-labeled operand can reach it" clause), and its variable miss cost falsifies the per-(class, OPP) WCET tables (§11) the way the RSE does.
  Its rejection is the admission test working correctly.
- **Programmable security semantics invert the platform axiom.**
  The PUMP's value proposition is a *general* engine that expresses *any* policy loaded at runtime; this platform's thesis is the opposite (*delete rather than defend, verify rather than hedge*): the **fewest, most-deeply-verified, frozen** mechanisms, not an engine whose expressiveness is the selling point.
  A runtime-loadable policy monitor is (i) the large hidden-state cache above and (ii) a *general* trusted base where the platform wants a *specific* one; the profile is **"frozen with the proof like the IDL"** (§15), and programmability is the antithesis of freezing.
  This is the deepest objection: micro-policies optimize **expressiveness** (one hardware mechanism spans many policies), this platform optimizes **minimality** (delete mechanisms until one verified primitive remains): dual philosophies, and the axiom picks the frozen instance.

**The distilled atom: already banked, twice, following the belt→spiller / EPIC→NaR / Mon CHÉRI→Write-before-Read discipline.**
The non-redundant idea is *a fixed tag plane checked in the datapath*, and the design already carries **two**:
- **CHERI *is* a micro-policy machine with a single hardwired policy.** The validity tag is precisely the SAFE "every word carries metadata" idea, frozen to the capability policy rather than left programmable: byte-granular and universal, so the memory-safety and compartmentalization micro-policies are already discharged, *deterministically*, by the substrate.
- **The Write-before-Read initialization-tag plane** (the Mon CHÉRI entry above; §15) is a *second* fixed tag plane: an initialization micro-policy realized as an address-indexed tag in the CHERI metadata plane, checked at fixed latency in the datapath: literally a micro-policy in the transparent, non-programmable form, whose adoption already demonstrates the rule: take the *policy*, reject the *programmable engine*.

And the **policy catalog imports nothing new**: IFC → the flow-label / IFC machinery (§8, §13); memory safety (spatial + temporal) → CHERI + budgeted revocation (§8); CFI + no-code-reuse → CFI under W^X capability-monotonicity (§14); compartmentalization → the capability/compartment model (§7, §12); dynamic sealing → CHERI **sealed capabilities**.
Each micro-policy the framework verifies is either already the substrate or already a dedicated mechanism.

**Where it ranks.**
It **abandons no substrate** (a RISC-V-host tag coprocessor), so it is off the belt/EPIC/Wasm "abandon RISC-V for X" ranking entirely: its genus *is* the substrate.
It ranks instead as the **maximal generalization of the Mon CHÉRI entry**: Mon CHÉRI proposed one extra tag policy and had its binary-side *encoding* rejected while its *property* (Write-before-Read) was banked; micro-policies propose a *programmable engine* for arbitrary policies and are rejected one level higher: not the encoding but the **programmability**; because the engine is a hidden-state admission-test failure and a programmable-vs-frozen inversion of the axiom.
Among the "add a mechanism" entries it is the most spec-coherent in *lineage* (Coq-native, tag-based, substrate-preserving) yet imports the least, because everything importable is already present.

**Disposition (nothing imports; confirms §15's tag-plane discipline).**
The **programmable PUMP / software-defined-metadata engine** is **rejected**: its rule cache fails the admission test on tests 2 and 3 (a tag-history timing channel and hidden state surviving a partition switch), and runtime-loadable policy is the programmable-vs-frozen inversion of *delete rather than defend, verify rather than hedge*.
The **tag-monitor *model* imports nothing because it is already the substrate**: CHERI is a fixed-policy tag-monitor and the Write-before-Read plane (§15) is a second fixed tag plane, so the platform is **already a fixed-policy tagged architecture**, reached not by adopting the PUMP but by freezing its genus to the policies the design proves.
The **micro-policy catalog imports nothing new** (IFC → §8/§13 flow labels; memory safety → CHERI + revocation; CFI → W^X + CHERI §14; compartmentalization → §7/§12 capabilities; sealing → CHERI sealing).
The **Coq metatheory** is logged as *methodological confirmation, not an import*: "verify a tag machine in Coq" is exactly the move the design makes for CHERI and for the Write-before-Read plane (re-homed onto the Coq-verified Iris/Cerise uninitialized-capabilities lineage, §13/§15), so the SAFE/micro-policies corpus is a **reference** for that discipline, not a component to lift.
The platform axiom decides it as ever (*trust is the scarce resource, engineering is free, delete rather than defend* → *verify rather than hedge*): a programmable policy engine buys expressiveness (the free axis, here not even wanted) at the price of hidden state and a general trust base (the scarce one).
Non-normative; no spec-body change.

**Honest residual (§17):** what the design forgoes is *programmable, post-hoc* policy: the ability to load a new tag policy without a respin, the PUMP's one genuine capability.
The bet is that the frozen catalog (CHERI ⋈ flow labels ⋈ W^X ⋈ Write-before-Read) is complete enough that field-loadable policy is never needed; if a genuinely new tag policy ever *were* required, the admissible way to add it is the transparent fixed-plane form the Write-before-Read plane already models (a datapath-checked, address-indexed tag reset by eager-zeroize), **never** the programmable rule cache: the same "cheapest thing to re-admit is the subtractive, static, Sail-modeled form" hedge the drop-PMP entry above books.
No mechanism is added, so there is no new proof surface; the residual is purely the forgone flexibility, which the *frozen-with-the-proof* discipline (§15) treats as a feature, not a loss.

---

## Link-layer timing: a fixed-function turnaround sequencer, not a Bluetooth/Wi-Fi controller

The dissolved-modem thesis (§4, §12) puts the whole radio stack in contained software on the pinned V-cores, but one class of deadline is too tight for software under interrupt jitter: the sub-slot *turnaround*, where a device must flip the RX/TX path and be transmitting within a fixed inter-frame gap of the previous packet: the BLE inter-frame space (`T_IFS` = 150 µs ± 2 µs), the 802.11 short interframe space (SIFS = 10/16 µs), the 802.15.4 turnaround (~192 µs).
This is the gap worth flagging: BLE link-layer timing "arguably harder than LTE HARQ"; and it is real: a general-purpose core's interrupt-and-schedule path cannot reliably hit a ±2 µs window, which is exactly why every shipping radio implements this turnaround below the software line.

**Three ways to meet it, and the fork the axiom forces.**
(a) A **Bluetooth/Wi-Fi controller** runs the entire link layer/MAC as firmware on a hidden core (the industry's *FullMAC*), meeting the timing trivially but as precisely the "Wi-Fi/BT controller firmware" §4 bans: an opaque processor with its own DMA, the largest foreign computer the radio architecture exists to delete.
Rejected.
(b) **Pure software on dedicated cores** meets the turnaround by pinning a core and precomputing the response: the Microsoft *Sora* approach (NSDI '09), which used core-dedication and lookahead to hit Wi-Fi SIFS in software.
It keeps everything in the trust structure but spends the tightest real-time budget on the most jitter-sensitive path; it is the "harder than HARQ" horn, and at 150 µs / 16 µs it is fragile.
(c) A **fixed-function timing sequencer in the register-slave transceiver datapath** (§15): a hardware packet-end event starting a fixed timer that drives the RX/TX switch and gates a software-prepared buffer out at the exact deadline, with no instruction fetch, no writable program, no firmware, and no protocol decision.
This is the *SoftMAC / split-MAC* partition: time-critical turnaround in fixed hardware, the link layer and everything above it in software; and it is what the platform adopts.

**The line between (a) and (c) is the "no foreign computers" line itself.**
A controller is a processor running firmware; the sequencer is a timer plus a small finite state machine, fully described in RTL, Sail-modeled, capability-gated: the FEC-unit / digital-front-end category, "matter, not software," the same tolerance the design already extends to the DFE, the FEC blocks, and the I/Q-streaming DMA.
It passes the five-part §15 admission test the way those do: deterministic; a fixed 150 µs constant independent of packet contents, so no data-timing channel; bounded FSM/timer state reset per event, architectural not hidden; a register slave with no authority beyond its capability-bounded DMA window; and its autonomy is the scheduled-DMA kind (a timer firing a pre-designated buffer), not the address-dependent memory walker admission-test 5 bans.

**Prior art: the partition is standard; the firmware-free realization is the part that is imported.**
The SoftMAC/FullMAC split is the mainstream Wi-Fi architecture: Linux's `mac80211` SoftMAC stack runs the timing-critical MAC (ACK/SIFS/backoff) in hardware and the management MAC in host software: exactly this decomposition.
On the exact protocol, **Nordic's nRF radios with Zephyr's open Link Layer** meet BLE `T_IFS` with a hardware *tIFS timer* (dedicated capture/compare registers) while the LL state machine, L2CAP, and GATT run in software.
The closest match to the *no-firmware* form the platform needs is **openwifi** (open FPGA RTL, already the §18 radio start-from): its "DCF low-MAC layer in FPGA" meets the 10 µs SIFS ACK in Verilog, not on a core: the firmware-free, open-RTL existence proof for exactly the fixed-function turnaround block, harvestable under the open-RTL mandate.
None of these is formally verified or Sail-modeled; consistent with the platform's thesis, the split is off-the-shelf and the *verified, capability-gated, firmware-free* realization is the contribution.

**Disposition (adopted; normative in §12, §15).**
The sub-slot turnaround (BLE `T_IFS`, 802.11 SIFS, 802.15.4) is met by a fixed-function timing sequencer inside the register-slave transceiver datapath: a hardware timer + FSM, no instruction fetch, no firmware, one more fixed-latency entry in the timing-annotated Sail model (§11) riding the RTL ⊑ Sail refinement.
Everything with protocol semantics (connection-event/slot scheduling, a §11 software hard task; channel selection; framing/whitening/CRC; link-layer encryption via the crypto core; and the link-layer state machine as a Lustre control plane) stays in software (§12).
A Bluetooth/Wi-Fi *controller* (FullMAC firmware) is rejected as a §4 foreign computer; pure-software turnaround (Sora-style) is rejected as spending the tightest real-time budget on the most jitter-sensitive path.
This is the same "hardness at the boundary, patchable software above it" rule the regulatory layering (§12) applies to the emission envelope, applied to timing.
**Honest residual (§17):** the sequencer is a small fixed-function block folded into the transceiver datapath already in the Sail model (§17 "grows the Sail model"): no firmware, no new trust axiom, its correctness and its 150 µs latency riding the existing transceiver RTL ⊑ Sail and WCET obligations; no new residual bullet, since the block is within the register-slave-datapath category the radio subsystem already books.

**Generalization: the same partition is the standing sensor-front-end doctrine (§12, §15).**
The split-MAC line drawn here is not radio-specific; it is the platform's rule for every transducer.
The analog front-end plus a fixed-cadence scan/sample sequencer stays *matter*: a register-slave AFE streaming raw samples over a capability-bounded DMA window, no per-sensor DSP core and no firmware; while all signal processing dissolves onto the host V-cores.
Capacitive touch (raw capacitance → host touch DSP), the audio front-end (microphone/speaker converters → host filtering, echo-cancellation, and beamforming), the image sensor (raw Bayer → the software ISP), IMU/motion (raw reads → host fusion), and the fingerprint/biometric AFE (raw frames → the host matcher) are all instances.
The one honesty the radio case does not carry: sensor front-ends have no off-the-shelf firmware-free part; commodity touch, audio, and image controllers co-design the AFE with tuned DSP firmware; so the raw-AFE silicon and its host-side DSP are a genuine net-new co-design, booked in §17; that booking is the resolution of the capacitive-touch AFE gap.

---

## Physical bifurcation of the radio: a second die is declined; the single-die realization takes the top rung of every graded axis

The candidate: instead of the radio stack living as a coherence island on the one die (absorbing the booked die-internal residuals, shared power and thermal coupling, §17), put it on a **second, identical, attested instance of the same die**, linked by a ring-over-SerDes: not a foreign computer (§4), a second copy of the one computer.
It deletes the highest-value cross-domain residuals outright and simplifies the island machinery on the main die, at the cost of a package and an inter-die link that becomes a new (IDL-shaped, Narcissus-parsed) boundary.

**What it targets, and what it keeps.**
The win is deleting the radio↔rest **power and thermal coupling** a shared die leaves (the refresh and PRAC coupling a DRAM design would add being absent in the first place, main memory being SRAM, §15).
It does *not* delete the shared **mask set**: the second instance is "the same die" by design; so a mask- or dopant-level trojan is common to both copies regardless; the target is only the die-internal power and thermal coupling.

**Why the second die is declined.**
The platform already climbs a **graded physical-isolation hierarchy** on every other axis: coherence (island exclusivity), main memory (whole-macro/tier down to bank), LLC (per-island slice), NoC (TDM non-interference), clock (GALS between islands).
The radio already holds the coherence-island half, so the disciplined move is to take that hierarchy's **top on-die rung on every axis** rather than jump to a second package:
- **Main memory**: the radio island takes a **separate SRAM macro or tier** (the existing top rung, §15); because main memory is SRAM the shared refresh, RFM, and PRAC coupling a DRAM design would book for sub-channel sharing is already absent, so this rung now deletes only the shared power and periphery: no new mechanism, just the strong rung.
- **Power and clock**: the radio island gets its **own clock/power island**, the identical treatment the RoT already carries (§15, §16) and the mitigation §17 already names (*power-island isolation*), deleting the on-die power-delivery droop coupling and completing the GALS story on the power axis (islands already run at independent clocks; now an independent rail).
- **Thermal**: no new mechanism: the channel is already deleted (thermal fail-stop, §15; SRAM has no PRAC to demote); a floorplan keep-out narrows the residual thermal-mass coupling.

On the in-model residuals the second die targets this **deletes the same things**, and avoids paying what the second die charges: it keeps the **single-die inspectability** the §17 supply-chain residual leans on (one die to image under IRIS, not a board of opaque packages), and it adds **no new boundary**: the ring-over-SerDes would be a fresh IDL-shaped boundary needing a Narcissus parser, a clock-domain-crossing/metastability obligation, new RTL ⊑ Sail surface, two-die attestation, and SerDes power and latency; reusing island, memory-binding, and clock/power-island boundaries already modeled.

**What the second die uniquely buys: and why it is not enough.**
It alone gives physically separate substrate and thermal mass: the last epsilon of analog-emission (TEMPEST-class) and power-probe coupling between the transmitter and secret-processing logic.
But that is (a) already physical-scope, outside the remote-attacker model (§17), and (b) *not actually closed by the second die either*, which reuses the same die design (same mask) and whose radio radiates by function: so the package buys an out-of-model epsilon it does not cleanly deliver.

**Disposition (adopted in part; normative in §15):** the second die and the inter-die link are **declined**; the **single-die realization**: the radio island taking a separate SRAM macro or tier and its own clock/power island; is **adopted** and normative in §15 (Interconnect and coherence, Power architecture), deleting the power and thermal coupling on one die (the refresh and PRAC coupling a DRAM design would leave being absent in SRAM).
It is the same graded-hierarchy discipline the design already applies on four axes, extended one axis (power/thermal) to the block that already holds the coherence-island half.

**Honest residual (§17):** the physical substrate and thermal mass stay shared: analog-emission and power-probe coupling remain physical-scope, exactly as the §17 physical residual books; bought back against a new inter-die trust boundary and the single-die inspectability the supply-chain residual leans on.

---

## SRAM main memory: capacity traded for the deletion of the refresh, RowHammer, and PRAC machinery

The choice: make main memory bespoke **on-die and in-package SRAM** rather than DRAM (LPDDR-class), accepting far lower capacity in exchange for latency, bandwidth, and, decisively for a verification-maximal design, the *deletion* of a whole class of mechanism.
The alternatives weighed are keeping DRAM (the conventional choice) and a hybrid (an SRAM near tier over a retained DRAM far tier); both are declined, the switch is total.

**What the deletion buys, on the scarce axis.**
DRAM stores each bit as charge on a capacitor that leaks and must be refreshed, and that same charge-disturbance physics is the RowHammer primitive: repeated activation of an aggressor row flips bits in a victim row.
SRAM stores each bit in a bistable cross-coupled latch: no leakage, no refresh, and no remote charge-disturbance primitive, so the probability of a RowHammer-class flip is *dramatically lower* (SRAM has its own far weaker, local read/write-disturb and half-select modes at aggressive nodes, covered by ECC and cell margin, not a remote flip).
And because there is no refresh there is nothing to *manage*: the entire deterministic-refresh-management (RFM) cadence, the per-row-activation-counting (PRAC) counters, and their alert-and-back-off feedback loop are **deleted, not merely tuned**.
That loop is a load-reactive coupling on the most-shared resource, the very thing a DRAM design must demote to a fail-stop tripwire and book as a §17 residual; removing it removes that residual, shrinks the proof surface (no refresh-cadence or PRAC crown-jewel spec, no reactive-refresh timing channel to argue closed, and the DRAM channel and sub-channel structure with its row-buffer state gone from the Sail model, so the worst-case memory-access latency is a flat SRAM constant rather than a pessimistic row-miss bound), and cleans the graded memory-tier isolation hierarchy: the sub-channel sharing a DRAM design must grade as *weaker* (two sub-channels of a die share its refresh and PRAC) has no such coupling to grade around when the memory is SRAM (§15).
SRAM's higher speed also *improves* performance (lower latency, higher bandwidth, no activate, precharge, or refresh stalls), a rare case where the security-motivated choice is not on the subordinated performance axis.

**What it costs, on the free axis, and how the cost is paid.**
An SRAM cell is far larger than a DRAM cell, so capacity is much smaller per unit area and static leakage (idle power) higher: the honest, and only, downside.
Both are bought back by static, transistor-level levers that add *no runtime behavior* (so none disturbs the admission tests): **3D die stacking** and **CFET-stacked cells** raise density, **backside power delivery** improves the power grid (lower droop, lower operating voltage) and frees front-side routing for density, and **asymmetric-threshold (asymmetric-Vt)** cells cut leakage and raise stability statically.
A **chiplet** realization (manufacturing the SRAM as a separate die on an SRAM-optimized process and integrating it in-package) is admissible where capacity demands specialized, modular fabrication; the in-package die-to-die link carries passive memory, not a foreign computer (§4).

**Assist circuits: the static form only.**
SRAM read/write *assist* circuits (negative bitline, wordline underdrive, VDD collapse, and the like) recover low-voltage margin and can lower operating voltage further.
Only a **fixed, composition-time-configured** assist is admitted; the dynamic, adaptive, or data-dependent assist that would add runtime state or a data-timing channel is declined, on the same *verify rather than hedge* grounds that keep the whole microarchitecture static and reactive-mechanism-free (§15): the exploitable, complex form is exactly what a design that ranks simplicity, reliability, and security above capacity should refuse, and asymmetric-Vt plus backside power carry most of the same low-voltage benefit statically.

**What is kept: encryption and the integrity tree, as defense-in-depth.**
On-die memory is within the physical boundary (like the on-die scratchpads the design already exempts), so an all-monolithic SRAM would need no memory encryption at all.
But a stacked or chiplet realization places main memory just outside the compute die, across an in-package die-to-die interface, so the **transparent memory encryption and the integrity and anti-replay Merkle tree are retained over main memory** as defense-in-depth (§15): a far narrower physical surface than the external removable module and long bus a DRAM design exposes (bus interposer, module splice and replay, and cold-boot all gone), but retained rather than dropped so the chiplet case is covered and the monolithic case is belt-and-suspenders.
The one clean simplification the bespoke SRAM buys here is **native tag bits**: a tag-less DRAM forces CHERI validity and initialization tags into a reserved-memory tag table behind a partitioned tag cache, but SRAM is widened to carry the tags *in the word*, deleting the table, the cache, and with them a whole element of shared microarchitectural state and its admission-test bookkeeping (§15).

**Disposition (adopted; normative in §15):** main memory is bespoke on-die and in-package SRAM; refresh, RFM, PRAC, self-refresh, and the DRAM-side autonomous power modes are deleted; RowHammer drops from a live remote primitive to a narrowed ECC-covered residual; CHERI tags are native SRAM bits; TME and the integrity tree are retained as defense-in-depth over the in-package interface; the static density and idle-power levers (3D and CFET stacking, backside power, asymmetric-Vt) and a static-only assist are admitted, the dynamic assist declined; a chiplet realization is admissible.

**Honest residual (§17):** capacity is materially lower than a DRAM design's, the accepted price; idle leakage is higher, mitigated but not erased by the static levers; a chiplet realization adds one in-package die-to-die interface (the surface the retained encryption and tree defend) and one further die to image under IRIS, a smaller inspection and physical surface than a socketed-module board but not zero.

---

## Emergency calling: the unauthenticated-attach exception, taken as a separate zero-authority mode rather than a legacy fallback

The tension: §12 makes *no downgrade, no null cipher, mutual authentication (5G-AKA)* a verified property of the L2/L3 servers, and §15 removes the 2G/3G/4G channel codes and RF from the silicon, so a legacy or downgraded attach is *unexpressible*.
But emergency service (E911/E112) is legally required to connect a device with **no SIM and no valid credential**, over an *unauthenticated* emergency-registration path that by construction has no mutual authentication and may run a null cipher, and, on some deployed networks, only over a legacy generation.
A verified stack that cannot express an unauthenticated attach cannot place that call, and a radio with no legacy silicon cannot fall back where legacy is the only coverage.
There are two separable sub-problems (the unauthenticated *session*, and legacy-only *coverage*) and the tempting single fix, a small legacy emergency-only receiver, solves the second by reintroducing exactly what the first deletes.

**The tempting fix, and why it is declined.**
Returning a minimal turbo/convolutional decoder and legacy RF band "for emergency use only" would let the device attach to 2G/3G/4G for E911/E112.
It is **declined**: the demodulation hardware, once present, is a bid-down target regardless of the "emergency-only" software intent, so a rogue base station is handed something to bid down *to* again, reopening the downgrade-attack class the generation floor (§15) deletes at the silicon.
This is the *verify rather than hedge* clause (§15) in its usual shape: a fallback path is not admitted merely because a real need motivates it, when it reintroduces the surface the design exists to delete.

**What is adopted instead: move the guarantee, do not lower it.**
The unauthenticated-session sub-problem is taken by the critique's first horn, made precise as a **separate, separately-verified, zero-authority emergency mode** (§12): the *no downgrade / no null cipher / mutual auth* property is scoped to **non-emergency service**, and emergency calling runs in a compartment holding no keys, no user data, and no identity beyond the regulation-mandated IMEI and location.
Its unauthenticated, possibly null-ciphered bearer can therefore carry only what emergency regulation already compels the device to disclose and can reach nothing else: the security posture (protection of the user's data and identity) is preserved by **non-interference** and zero authority, not by the network crypto the mode cannot have, and entry is an unspoofable local act (never network-initiated, §8, §9), so the downgrade class stays deleted.
This is the eUICC's own zero-platform-authority containment (the one tolerated foreign trust domain, §4) applied to the *session* instead of the credential.

**The coverage sub-problem is taken by the critique's second horn, as a decision.**
Emergency calling is placed over **5G-standalone (and 6G) emergency registration**; where only legacy or 5G-non-standalone coverage (including EPS-fallback-to-LTE emergency voice) offers an emergency path, the device cannot place the call.
Emergency reach equals 5G/6G coverage reach: a deliberate coverage-for-security trade, the same one the §15 generation floor already makes for ordinary service, extended to emergency service and stated rather than left to silence.

**Disposition (adopted; normative in §12, §15, §17):** the legacy emergency-only receiver is **declined**; the unauthenticated-attach exception is adopted as a **zero-authority emergency mode** scoped out of the no-downgrade property, and the legacy-only-coverage limit is booked as a stated coverage decision.

**Honest residual (§17):** the emergency mode admits an unauthenticated, possibly null-ciphered network session (contained by non-interference and zero authority, the one place the radio's verified crypto posture is deliberately not in force), and the coverage limit means no emergency call where only legacy or 5G-non-standalone coverage exists.

---

## seL4 vs. CertiKOS: re-examined; seL4's *design* retained as the object-model base for a bespoke minimal capability core, proved end-to-end in Coq

The §5/§7 choice of a **CertiKOS-lineage** kernel proof over **seL4** rested, as written, on *one prover, Coq*.
The first pass (bullets below, kept as the reasoning trail) concluded "no pure-win substitution: a trade of the single-checker TCB for maturity."
Promoting seL4's 2024 program (a verified **multikernel** on multicore, and **CHERI-seL4**) to in-scope, and spending the platform's own axiom (*engineering is free; trust is the scarce resource*), overturns that conclusion.
A **third option dominates both**: keep seL4's *design* and re-prove it **end-to-end in Coq**, compiled through **CompCert/SECOMP**.

- **Direction of travel: the "simplification" is seL4's own, not CertiKOS's.** seL4 remains on **Isabelle/HOL** (l4v), with no migration to Coq and none to CertiKOS's method.
  CertiKOS's distinctive contribution is the *opposite* of a simplification: **Certified Concurrent Abstraction Layers** (Coq, CompCertX) verifying a *fine-grained concurrent, shared-memory* kernel (mC2). seL4's multicore roadmap is the **multikernel**: one verified single-core instance per core, **zero shared kernel state**, inter-kernel IPIs (seL4 RFC-0170), concurrency pushed to user level *explicitly "for better verification."*
  That share-nothing, per-core-sequential model **is already this spec's §7 architecture** (capability/memory lineage: Barrelfish → seL4).
  **CertiKOS's one distinctive asset: proven shared-memory concurrency; is therefore dead weight here:** the multikernel forbids the shared mutable kernel state it verifies.

- **The spec already *is* seL4 in all but the prover.**
  Untyped memory / zero post-boot kernel allocation (§7), synchronous endpoints + notifications (§7), derivation-tree (CDT) revocation (§8), and the non-interference theorem (§8) are seL4's model in every particular; "CertiKOS" named only the **Coq proof engine**.
  "CertiKOS-lineage kernel proof" was always shorthand for *verify this (seL4) design in Coq*: a label on the method, not a second kernel.
  The coherent artifact is a Coq proof **of the seL4 design already written down here**, not an import of CertiKOS's different kernel.

- **The two decisive objections bind the prover, not the design: and dissolve on re-proof.**
  (1) **Trust-base fragmentation:** *adopting* seL4's Isabelle proof puts **Isabelle *and* Coq**: two proof checkers; permanently in a TCB whose §6 story is one self-verifying checker; a first-order regression.
  (2) **Compilation seam:** seL4's shipped binary-correctness is a *different* toolchain (decompilation + SMT translation validation), not the §5–§6 CompCert/SECOMP/Islaris/Cerise path.
  Both are artifacts of *inheriting seL4's existing proof*; **redoing the proof in Coq on CompCert/SECOMP erases the first and inverts the second into native composition.**

- **CHERI is a wash, with an implementation to verify against.**
  CHERI-seL4 builds purecap (Morello + CHERI-RISC-V, sel4test/sel4bench passing) but is **not verified**: CHERI serves *user-level* safety, and seL4's existing functional-correctness proof does not extend to the capability hardware.
  The design mandates a **verified purecap kernel** (§7), so the CHERI-C mechanization gap (§7/§17) is net-new under *either* kernel.
  Promoting the 2024 CHERI-seL4 work in-scope supplies the purecap *implementation and bring-up* to verify against; it does not supply the proof.

**The third option, stated.
Methodology is portable; maturity is not.**
The design chose CertiKOS for a *portable* property (a Coq proof method: deep specifications, abstraction layers, CompCertX-style verified compilation) at the price of an *intrinsic* one: a mature, deployed, exhaustively specified, independently reviewed kernel design.
With labor priced at zero, the move is forced: **carry the portable property to the design with the better intrinsic property.**
Apply Coq/CompCert/SECOMP to seL4's design rather than accept CertiKOS's thinner, concurrency-oriented, here-unused kernel for the sake of a method that travels.
By the platform's *own* decision criterion (smallest trusted set, deepest proof): the result wins on both axes: an identical single-prover trust base (Coq), over a design carrying the broader proved-property set (functional correctness + integrity + availability + confidentiality/NI + binary-level) and the longer-scrutinized specification; and §5 calls specifications "the crown jewels," of which seL4's has had the most independent eyes of any kernel spec in existence.

**The honest residual: freshness, not trust.**
What transfers from seL4's maturity is the **design, ABI, C implementation, abstract specification, and the in-scope multikernel/CHERI engineering**: *not the proof.*
A Coq re-verification is a **fresh** proof and spec-mechanization, as unbattle-tested as CertiKOS's, and a faithful re-proof may pull the code marginally off mainline seL4 (spending a sliver of the very battle-testing invoked).
The search for an existing Coq artifact to inherit comes back empty: seL4 is **Isabelle-only, and actively so**: the `l4v` proof and every current extension (MCS, multicore, the seL4 Core Platform) stay in Isabelle/HOL; so the route is genuinely greenfield in Coq: design, spec, and C carry across, but there is no proof to port.
The freshness that bites is therefore **not** the authored refinement proofs, which fail *loudly* when they are wrong, but the **silent** kind: a mis-transcribed specification verifies perfectly (§5's crown-jewel failure mode).
Bound it by transcribing the spec **mechanically, not by hand**: seL4's executable model is Haskell, and **hs-to-coq** (Gallina from Haskell) carries the scrutinized prototype into Coq without a paraphrase pass, so the artifact that earned the independent eyes is *preserved*, not re-typed; only the abstract spec and the refinement are authored fresh.
That fresh abstract spec is not unmoored: it is **disciplined by the refinement against the hs-to-coq executable model**: any *divergence* fails the proof loudly, so the sole silent residual is a *too-weak-but-faithful* abstract spec, the **generic crown-jewel risk seL4 already carries in Isabelle** (§5), not one the Coq move introduces.
And the two-checker alternative's edge is narrower than it looks: the proofs it would let you *inherit* do **not** cover this platform's purecap-CHERI kernel or the multikernel configuration: both unverified in seL4 today; so that proof mass is **fresh under either option**, and what the maturity actually buys is the *design and specification*, not a discharged proof of the configuration shipped here.
That is a real cost: but a *labor-and-freshness* cost, the class the engineering-free axiom exists to absorb, not a *trust* cost: the trusted set does not grow.
The claim is thus conditional and honest: **superior iff (a) engineering is free and (b) seL4's 2024 completion is in-scope**, both stipulated.

**What the stripping leaves is a minimal capability core, and that is what makes the greenfield proof feasible.**
This platform commits to a specific set of deletions: the MMU with its VSpace and paging objects, MCS, SMP, the S/U privilege ring, and PMP with the IOMMU (the MMU-deletion, single-privilege-mode, drop-PMP, and capability-checked-DMA entries above; §7, §15). These preferentially remove the *proof-heaviest* layer of `l4v` (the arch-specific VM refinement) and its *least-maintained* ones (MCS, and the SMP concurrency the multikernel never incurs).
What survives is seL4's architecture-independent core (untyped memory, retype, the capability space, the CDT and its revocation, endpoints and notifications; §7, §8), joined to a realization that is *not* seL4's: the single-address-space CHERI isolation CheriOS demonstrates, the CHERIoT-lineage switcher, sealing, and interrupt-state sentries (§15), and the table-driven cyclic executive (§7, §11).
The artifact is therefore a **synthesis, not a transcription**: seL4's object model ⋈ the CheriOS/CHERIoT CHERI-SAS realization ⋈ Barrelfish's multikernel composition ⋈ a static cyclic executive. Reading the route as "re-prove seL4" *overstates* the maturity that transfers (the deployed kernel is a heavily-forked minimal variant, not mainline seL4) while *understating* the genuinely novel proof: the purecap CHERI-C *kernel refinement* (the CHERI-C language semantics itself now mechanized in Coq, Zaliva et al. ASPLOS 2024, so the novelty is this kernel's proof over it, not the semantics), the multikernel non-interference composition, and the switcher and sentries, none of which any base supplies.
Naming it a **bespoke minimal capability core** sizes the effort correctly and frees the object model to be designed for *minimum proof surface* rather than inheriting seL4's hooks for the features this platform deleted.
It also **relocates the decision**: with the kernel this small, the dominant fresh proof mass is no longer *in* the kernel but in the CHERI-C kernel refinement over the now-mechanized CHERI-C semantics (§7, §17), the multikernel non-interference composition (§8, §17), and the switcher and sentry verification against the Sail model, so the seL4-versus-CertiKOS-versus-CheriOS basis question is second-order to getting those right.

**Disposition:** adopt seL4's **design** as the object-model base for a **bespoke minimal capability core**, proved **end-to-end in Coq** and compiled via **CompCert/SECOMP** (§5, §7); **CertiKOS is demoted from kernel to proof-method lineage**: deep specifications, certified abstraction layers, CompCertX-style verified compilation; supplying the *how* while seL4 supplies the *what*.
What transfers from that lineage is the abstraction-layer discipline, the deep-specification method, CompCertX-style verified compilation, and the generic lower-layer proofs (physical-memory management: the single-address-space design carries no paging layer) any kernel needs, **not** CCAL's *concurrency* machinery, which the share-nothing multikernel (above) makes dead weight; for a per-core *sequential* kernel, plain **VST** (sequential separation logic over CompCert) is the more parsimonious closing logic.
The make-or-break subproof, never yet done in Coq for an seL4-class capability model, is **CDT revocation** (the hardest part of the l4v corpus): so it is the piece to attempt *first*, the early kill-switch on the route.
**Importing seL4's Isabelle proof wholesale stays rejected** (the two-prover TCB).
The earlier "no pure-win" verdict is **superseded**: it held only under the unstated assumption of *inheriting* seL4's proof; the engineering-free axiom licenses lifting that assumption, and the Coq-re-proved seL4 then dominates.

---

## Kernel-in-gateware: the benefit needs the whole kernel, the safety only a frozen subset; the one separable primitive worth fusing is already CHERI

The proposal is to express the capability/endpoint/scheduler machine **directly in a formal-semantics HDL** (Kôika/Kami) rather than as Machine-mode software, so the kernel's correctness proof folds into the **RTL ⊑ Sail** refinement already in scope (§18) and the Machine-mode software TCB on application cores collapses toward zero.
Its strongest premise is real and already in the spec: the kernel ABI is *"on the order of a dozen invocations… frozen with the proof"* (§7), and a per-core multikernel instance is share-nothing, sequential, event-driven, with **zero post-boot allocation** (§7): architecturally a synthesizable object.
It is best read as the **terminus of the kernel-shrinking directions**: the **table-driven cyclic executive in place of MCS** (§7, §11) atop the **single-address-space CHERI isolation that deletes the VM subsystem** (the MMU-deletion entry above), the two base simplifications collapsing the kernel to exactly that frozen state machine.

**The steelman, and the prior art.**
RTOS primitives *are* synthesizable and deterministic: the RealFast **RTU / Sierra** line (the Mälardalen real-time-unit work) put scheduling, IPC, semaphores, flags, and timers into VHDL behind memory-mapped registers, reporting large system-call speedups and, tellingly, **timing independent of waiter count**: the determinism dividend a hardware control plane offers over a software one.
If the kernel spec were genuinely frozen forever, fusing it would merge the kernel proof into the hardware refinement at no new prover.

**Why it fails as a base move: five load-bearing objections, and narrowing to "the most-proven subset of the most battle-tested spec" sharpens two of them rather than escaping them.**
- **The benefit/safety scissor: decisive.**
  The payoff (software TCB → 0) requires fusing the **whole** kernel; the part that is *safe* to fuse: proven **and** frozen; is only a **subset**.
  Fuse the subset and the software kernel remnant (cyclic-executive scheduling, multikernel coordination, capability management, the powerbox/re-grant paths §8/§12) stays in Machine mode, so the TCB does not collapse: it is **split across a hardware/software boundary with a new verified seam added**.
  This is precisely the RTU pattern: RTU keeps its host RTOS (µC/OS-II) in software and offloads hot paths, so even the canonical hardware-microkernel product never collapsed the software TCB.
  Partial fusion *adds* surface; only whole fusion pays off, and whole fusion needs the whole spec frozen.
- **The most-proven subset is not the kernel this platform runs.** seL4's deepest guarantees hold for a **unicore, non-MCS, static-partition** configuration: functional correctness there, and the **non-interference proof only for non-MCS, unicore, static-partition configurations**: the least-maintained layer of l4v.
  This platform is a **multikernel** on multicore, **purecap CHERI-C**: and although dropping MCS for a static cyclic executive (§7) moves the *scheduling* dimension back toward the non-MCS static-partition one seL4's proof covers, the multikernel and purecap-CHERI dimensions keep its non-interference a *fresh* theorem wearing an old name.
  "Fuse the proven subset" therefore fuses a kernel you do not deploy; the configuration you *do* deploy is the unfrozen one.
- **Pedigree does not transfer across the prover or the transcription.** seL4's battle-testing is a property of the **Isabelle** proof, the C implementation, and fifteen years of deployment; the design is Isabelle-only and greenfield in Coq (seL4 vs. CertiKOS, above).
  Fusing to Kôika produces a **new** artifact: RTL; whose correctness is a **new** Coq proof (RTL ⊑ a fresh Coq transcription of the spec), riding the **least-built arrow in the whole stack** (RTL ⊑ Sail, §18).
  The independent eyes were on the Isabelle artifact, not the gateware, so fusion inherits the *design* and re-proves *fresh* on the hardest tooling: strictly worse than the software re-proof, which at least rides the more-mature CompCert/VST path.
- **The radio/MTTR self-defeat softens under narrowing but survives.**
  Restricting to the most-scrutinized subset genuinely lowers P(functional defect): the crown-jewel doctrine (§5) working as designed.
  But the defect classes fusion forecloses response to are **uncorrelated with the functional proof**: **timing channels** (outside seL4's functional *and* non-interference proofs: time protection is a separate, still-maturing, hardware-dependent effort), hardware-model drift, assumption-boundary violations, and errata interactions.
  Scrutiny buys none of those down, and fusion concentrates its cost exactly there: on the **highest-privilege layer**, where the spec's own rule bites hardest: *"a fully fused radio could never patch its most-attacked surface"* (§12), so patch latency becomes fab latency.
  Lower P(defect) × maximal-severity-and-zero-remediation is still a bad tail trade.
- **There is nothing left to accelerate.**
  RTU's motivation is performance, the currency this platform spends freely (performance deliberately subordinated to security, §2).
  And the overhead it removes is already gone: the **table-driven cyclic executive** (the base scheduler, §7) makes the schedule a compile-time constant (no dynamic decision to offload), **SPSC single-writer rings** (§12) replace the semaphore/flag mailbox, the M-mode timer (`mtimecmp`) gives deterministic timers, and the §11 WCET tables already assume fixed latency.
  RTU accelerates the *dynamism* out of a dynamic RTOS; this kernel has the dynamism designed out: so even the accelerator reading buys nothing.

**The distilled atom: already banked, following the belt→spiller / EPIC→NaR discipline.**
The non-redundant idea is *a single genuinely-frozen, cleanly-separable primitive as a verified hardware block*, and it is **already present**: the highest-value such primitive: **spatial capability enforcement** (bounds, tags, monotonicity); is in gateware as **CHERI**, with its own Sail semantics and RTL ⊑ Sail obligation (§1, §18), reached **not** by fusing seL4 but by a hardware capability model.
A verified **Kôika scheduler/timer block** is admissible *in principle* (a cyclic-executive table lookup, a windowed timer) but is far too small to deliver the proposal's TCB-collapse and is orthogonal to the capability/endpoint machine it actually names.
So the separable primitive worth fusing is already fused; the rest is **control-plane sequencing best kept patchable, in software, in the same prover as everything else**.

**Where it ranks.**
Unlike the belt, EPIC, and Wasm targets, kernel-in-gateware does **not** abandon the RISC-V substrate: it keeps the substrate and moves the *kernel* into it; so it is off that ranking.
It is the terminus of the kernel-shrink path (the adopted cyclic executive ⋈ the adopted single-address-space MMU-deletion, above, which subsumes the frozen-page-table step), coherent only **after** those simplifications land: as the base has them; **and** the seL4-in-Coq specification and proof are complete and frozen; a gen-2 direction contingent on spec-freeze, in the same "iff the binding constraint appears" slot as the belt, not a base move.

**Disposition:** the fusion of the **capability/endpoint/scheduler machine** is **rejected as a base direction**: the benefit needs the whole kernel while the proven-and-frozen safety covers only a subset (the scissor), the proven subset is not this platform's multikernel/purecap configuration, the maturity lives in Isabelle and does not transfer to a fresh Coq → Kôika → RTL artifact on the least-built arrow, and fusion forecloses remediation of the timing/assumption/errata defect classes the functional proof never covered, on the most-privileged layer.
It is logged as a **spec-freeze-contingent gen-2 direction** (terminus of the adopted cyclic-executive and MMU-deletion simplifications, above).
The one distilled atom: a verified hardware block for a genuinely-frozen separable primitive; is **already banked as CHERI** (§1); a verified **Kôika scheduler/timer** block is admissible in principle but too small to be the proposal, and stays non-normative.
The **RealFast RTU / Sierra** line is a functional reference that RTOS-in-gates is real and deterministic, **not** an admissible artifact: unverified VHDL, a dynamic-priority/semaphore shape the §15 admission test deletes, and an accelerator that keeps the software kernel rather than replacing it.
Non-normative; no spec-body change.

---

## Crypto verification depth: implementation-correct is not reduction-secure

Functional correctness plus constant-time (Fiat-Crypto + libcrux/HACL\*, §5) cover two of the three properties a verified cryptosystem needs and leave the third unstated: the reverse of this spec's "deepest proof over the smallest trusted set" criterion.

- **The missing layer.**
  Functional correctness says the code computes ML-KEM; constant-time says it leaks nothing through timing.
  **Neither says the scheme is secure.**
  IND-CCA (KEM) and EUF-CMA (signatures) are *game-based* properties established by **reduction** to a hardness assumption: proofs about the *scheme*, not the *code*.
  Proving the implementation while assuming the cryptography inverts the priority: the most consequential property: that the primitive is actually hard to break; was the one left unproven.
- **The widening must be minimized, not merely accepted.**
  §5 elsewhere *minimizes* F\*/Z3 by construction, picking **Narcissus over EverParse** for parsers purely on trust-base uniformity.
  Merely accepting the crypto widening ("ports don't exist yet") would leave the largest attacker-facing trust widening un-attacked.

The tools, each run through the §5 trust-base test, close both gaps:

- **Constant-time on the artifact + CryptOpt translation validation (layers 1–2).**
  Constant-time is verified **directly on the binary** against the §15 leakage model, for the verified-C crypto core exactly as for every other secret-touching artifact: there is **no verified-compiler CT route**, so a single CHERI-CompCert carries the whole toolchain and "trust a C compiler to preserve constant-time" is replaced by a *mechanized relational proof over the binary* (the binary-level constant-time entry below; the declined preservation route is the CompCert-CT entry below).
  The performance-critical **field-arithmetic kernels** are then recovered by **CryptOpt**: an *untrusted* randomized-search superoptimizer emits assembly faster than GCC/Clang at top optimization (at times beating hand-written asm), admitted by a **Coq-verified program-equivalence checker** back to its **Fiat-Crypto** functional spec; so the trusted artifact is a *small verified checker*, not a second optimizing backend, and hand-assembly-grade speed and Coq-checkable correctness are both had at **zero trust-base fragmentation** (the crypto instantiation of the artifact-not-pedigree / CHERI-TAL discipline below).
  Costs, and why it is a *deferrable* recovery rather than a hard dependency: **CryptOpt targets x86-64 today**, so the CHERI-RISC-V retarget of the equivalence checker over the one Sail model is a §18 workstream beside CHERI-CompCert: but the crypto core is already correct *and*, its field arithmetic being straight-line, constant-time on the stock CHERI-CompCert output verified on the artifact, so this only buys back speed on the hot path and can be deferred.
  Two honest asterisks: CryptOpt's headline results come from randomized search **benchmarked on real silicon**, which does not exist here yet: the fitness function must ride the timing-annotated Sail model or the FPGA (§11), though the in-order fixed-latency profile (§15) makes that cost model *transparent* rather than the opaque superscalar it fights on x86; and its scope is *straight-line field arithmetic*, so control-flow-heavy primitives (Keccak, AES, ChaCha, the ML-KEM/ML-DSA NTT and samplers) stay verified C, branchless-hardened and constant-time-verified on the artifact (the binary-level constant-time entry below): acceptable with performance subordinated.
- **SSProve / FCF (layer 3).**
  Coq-native game-based reduction frameworks.
  Choosing them for the security proofs is the **identical decision** §5 made choosing Narcissus over EverParse: the reduction rides the one Coq kernel (§6) at **zero new trust base**.
  This is the spec-coherent home for the missing layer.
- **EasyCrypt (layer 3, mature complement).**
  The standard game-based prover and the one carrying the **formosa-crypto** ML-KEM/ML-DSA reductions: the fastest path to a *finished* proof.
  But it discharges via **Why3/SMT**, a trust base distinct from Coq; by this spec's own logic it is a widening of the same character as the libcrux/HACL\* F\*/Z3 one: **adopted as pragmatic interim assurance, SSProve/FCF the destination.**

**Disposition (adopted; normative in §5).**
Crypto assurance becomes **three composed layers** (functional correctness (Fiat-Crypto; libcrux/HACL\* interim) ⋈ constant-time (verified on the artifact, with CryptOpt-checked field-arithmetic kernels) ⋈ reduction-level security (SSProve/FCF Coq-native, EasyCrypt mature complement)): joined at each primitive's functional specification, which joins the crown-jewel spec list.
The platform axiom decides the toolchain exactly as it did for seL4: **methodology is portable, maturity is not**: carry the Coq-native property (on-artifact constant-time verification, CryptOpt equivalence-checking to Fiat-Crypto, SSProve/FCF) to the mature artifacts (formosa-crypto, Fiat-Crypto/CryptOpt), spending engineering to shrink the trusted set.
**Honest residual (§17):** a reduction *isolates and names* the hardness assumptions (MLWE/MSIS; ECDLP/CDH) but cannot prove them: the irreducible cryptographic axiom; the implementation ⋈ reduction join is a new seam at the functional spec; EasyCrypt-borne reductions carry an SMT base until restated Coq-native; and scheme-level IND-CCA/EUF-CMA is still below protocol-level security (TLS/AKA), a further layer.
What this buys is the deepest-available crypto proof: from "correct, constant-time code for a scheme we *assume* is secure" to "the scheme is IND-CCA/EUF-CMA under a named, minimal hardness assumption, implemented by constant-time code a verified checker admits on the artifact"; with the residual pushed down to conjectures no proof system can discharge.

---

## Sound WCET derivation: the analyzer the timing discipline was built for

§11 checks *schedulability given WCET numbers* (for the static cyclic executive an interval-arithmetic check, §7, not Prosa-style response-time analysis) but on its own names **no vehicle to derive those numbers soundly**: the whole temporal-admission edifice (OPP/mode selection, TDM NoC schedule, watchdog windows) and much of the §17 timing-channel argument rested on WCET inputs a wrong value silently falsifies.
Sound, mechanized WCET is barely a field: **aiT (AbsInt)** is the commercial gold standard but unverified, and there is no widely-used Coq-native WCET analyzer.
The irony the gap sharpens: the design's **in-order + static-only-prediction + fixed-latency** posture exists precisely to make WCET tractable, yet the tool computing it would otherwise go unnamed.

- **The layer decomposes exactly as RTL ⊑ Sail does: a functional part ⋈ a hyperproperty part.**
  WCET analysis is classically two halves: a **low-level micro-architectural model** (per-basic-block timing: aiT's abstract interpretation over pipeline and cache state) and a **high-level path analysis** (loop bounds + IPET over the CFG).
  On this platform the two halves land in two *already-present* layers, so almost nothing is net-new theory.
- **The low-level model is not a new artifact: it is the timing-annotated Sail model (§15).**
  The timing discipline the profile adopted for other reasons: in-order issue, static-only prediction (no predictor-state variance), fixed-latency DIV/FPU/AMO, Ztso, cache/memory/NoC partitioning, TDM NoC, WCET-exact scratchpads, deterministic profile-guided layout (§10); *collapses* the low-level model from aiT's pipeline-and-cache abstract interpretation to a **per-(class, OPP) latency table** plus reproducible cache/fetch/memory terms, sound to the metal by RTL ⊑ Sail (Kami/Kôika).
  The non-speculative posture is itself a WCET-soundness argument.
- **The high-level model is a syntax-directed max-path sum, not IPET.**
  On an in-order, fixed-latency, statically-predicted core there is no pipeline overlap, timing anomaly, or dynamic predictor for the Implicit Path Enumeration Technique to resolve, so structured-code WCET reduces to **Shaw's timing schema**: a syntax-directed max over the control-flow graph with loop bounds.
  That CFG is **already typed** by the CHERI-TAL, so the bound rides as **cost annotations on the typing derivation** the on-device checker validates, and the **ILP / LP-solver machinery is deleted, not retargeted**: IPET exists only to *tighten* pessimism the deleted microarchitecture never introduces, and the standing rule is *take the trivial sound bound* (§5), so a whole net-new verified estimator is deleted with it.
- **Measurement-based / probabilistic WCET (MBPTA/EVT): rejected as the bound.**
  Extreme-value-theory tail estimates give a *probabilistic* bound; that is a statistic, not a theorem: the same disposition as MTE's ~93% (§15), antithetical to the proof-based determinism (G3/G4).
  Admissible only as an out-of-band cross-check that flags a wrong timing annotation, never as the admitted WCET.

**Disposition (adopted; normative in §5, §11).**
Put the low-level half *inside* the timing-annotated Sail model (discharged by the RTL ⊑ Sail proof already in scope) and derive the high-level half **syntax-directed** (Shaw's timing schema) as cost annotations on the CHERI-TAL typing derivation: **no IPET, no LP solver, no standalone estimator** (deleted by *take the trivial sound bound*, §5).
**aiT** stays the unverified complement; **MBPTA** an out-of-band cross-check only.
The general rule this case establishes, written into §5: **any verified tool that exists only to *tighten* an already-sound bound is inadmissible, take the trivial bound** (pessimism is free by axiom, performance subordinate, §1).
**Honest residual (§17):** WCET is only as sound as the timing-annotated model's latency magnitudes (crown-jewel specs) and inherits the RTL ⊑ Sail residual (no sound bound before that least-built arrow closes); composability across partitions rests on the §15 isolation non-interference the timing-channel story already needs.

---

## Binary-level constant-time verification: CT as a property of the artifact, not its pedigree

**Constant-time (CT)** is discharged **directly on the binary** for *every* secret-touching artifact, the verified-C crypto core included: there is no verified-compiler CT route (no CompCert-CT-class preservation, the entry below), so CT is a property of the artifact and one verified compiler suffices.
Where the code is **structured** (the CryptOpt kernels, the Tier-1 secret paths) that discharge is a **decidable taint-type check in the CHERI-TAL** (CT-Wasm lineage, per-install), and only genuinely unstructured secret-dependent code falls to a relational proof (below).
The FPCC discipline's own principle is *"verification is a property of the artifact, not its pedigree"* (§5); carrying CT by *preservation* would be the one place that principle goes unmet, leaving CT a fact about **which compiler produced the binary**, so the platform declines the preservation route and verifies CT on the binary instead.

- **The scope is all secret-touching code, the crypto core included.**
  No path carries a CT-preserving compiler: the crypto core is compiled by the stock CHERI-CompCert, the FPCC **Islaris "no verified compiler in the loop"** path (§5) has none in the loop, and **every Tier-1/2 binary** goes through the certifying userspace toolchain (§5, §13), which emits a *memory-safety* certificate but preserves nothing about timing: so every secret-touching binary is verified on the artifact.
  A key-handling server (the radio key hierarchy, §12) or a PIN-handling app compiled by that toolchain gets memory-safety PCC and **no CT**.
  This is the exact shape of the gap the memory-safety certificate already avoids (§13): trusted-by-pedigree where it should be proven-on-artifact; one property later.
- **Artifact-level CT decomposes as RTL ⊑ Sail and WCET do: functional ⋈ hyperproperty, and mostly *type-level*.**
  Constant-time is a **2-safety hyperproperty** (it relates two executions differing only in secrets), which a *functional* program logic does not carry.
  But **CT-Wasm** (Watt et al.) shows it decidable as a **taint-type discipline** (secret-labeled values the type system forbids from reaching a branch, an address, or a variable-latency op), with mechanized type-soundness: so for structured code CT is a **type-checking obligation in the CHERI-TAL**, not a proof term, and the bare Islaris/Iris-over-Sail refinement need be extended with a **relational** layer only for the unstructured residual.
- **The residual close: a relational program logic over the leakage-annotated Sail model.**
  For the unstructured code the taint discipline cannot type, self-composition / relational-Hoare reasoning (ReLoC-in-Iris lineage) over the Sail semantics *instrumented with the §15 `Zkt`/`Zvkt` leakage model* proves the leakage trace (load addresses, branch conditions, variable-latency operands) independent of secrets, **at binary level, in the one Coq prover** (the 2-safety theory of the §13 Iris-over-Sail base): the corner-case vehicle after the taint-type check, covering the crypto core, the CryptOpt kernels, and the structured Tier-1 paths where a lowering resists typing.
  It emits an FPCC **constant-time certificate** the §6 checker validates at zero new trust base.
- **Binsec/Rel: the better-fit mature tool, run through the §5 trust-base test.**
  Binsec/Rel does exactly the binary-level job: **relational symbolic execution for constant-time and secret-erasure, directly on the binary against a leakage model**, and it scales to production crypto (BearSSL, OpenSSL, HACL\*, libsodium: finding real violations).
  It is the better-fit tool for this path because the FPCC statement is *binary-level against the Sail model* and Binsec/Rel is binary-level.
  So, exactly like **riscv-formal BMC** and **aiT**, it is adopted as the **unverified complement / bring-up gate**, bounded evidence and untrusted evidence-producing machinery, with the relational-Sail-logic certificate the unbounded close.

---

## CompCert-CT: constant-time by compiler preservation, declined for on-artifact verification

**CompCert-CT** (Barthe, Blazy, et al., POPL 2020) is a modified CompCert that *preserves* constant-time: if the C source is constant-time against a leakage model, the compiled assembly is too.
It exists because **stock CompCert does not preserve CT**: instruction selection, if-conversion, and the lowering of a conditional expression can turn a branchless source into a secret-dependent branch, so ordinary verified compilation gives functional correctness but not timing.
An earlier form of this specification carried the crypto core's constant-time this way (one verified-compiler CT route, itself already a narrowing from a two-route CompCert-CT ⋈ Jasmin form).
The property is real and its guarantee the strongest available (CT *by construction*, at the source, discharged once), but three things decide against it here.

- **It has no CHERI backend, and would inherit the one being built from scratch.**
  There is no functional CHERI-CompCert yet (§18 builds it as priority zero); CompCert-CT is an x86 / Arm / RISC-V research branch of mainline CompCert.
  Keeping it means re-establishing the CT-preservation proofs across every pass *on top of* the net-new CHERI backend, a substantial research merge, for a guarantee whose floor is shared (below).
  So the realistic unification was never "adopt CompCert-CT for everything" but "one stock CHERI-CompCert plus on-artifact CT," the direction taken.
- **It buys earliness, not strength: the constant-time floor is identical either way.**
  A preservation theorem and an on-artifact relational proof bottom out at the *same* `Zkt`/`Zvkt` leakage model and the *same* RTL ⊑ Sail arrow (§15, §17): CompCert-CT gives CT *earlier* (at the source, by construction) against that floor, not a *stronger* CT.
  Earliness via a compiler that does not yet exist is not earliness in hand.
- **Preservation is pedigree-bound; the doctrine is artifact-borne.**
  CT by preservation reaches only binaries built through that compiler, leaving the FPCC Islaris path and every certifying-toolchain-compiled Tier-1/2 binary uncovered: the one place §5's *"property of the artifact, not its pedigree"* rule goes unmet (the binary-level constant-time entry above).
  The platform already owes a binary-level CT verifier for those paths, and once it exists it is strictly more general and subsumes preservation.

What is **kept** is exactly the destination: constant-time verified **on the binary** for every secret-touching artifact, the crypto core included, against the one leakage model (above).
The cost of dropping preservation is the honest one: a stock compiler does not guarantee CT, so straight-line crypto is constant-time structurally but the control-flow-heavy primitives are branchless-hardened (`Zicond` selects) and verified on the artifact, or admitted as checker-admitted assembly leaves where a lowering resists (§5): a check-and-harden discipline on the free (engineering) axis in place of a by-construction guarantee that would require a compiler that does not exist.
This is the same shape as the field-arithmetic kernels (CryptOpt: untrusted producer, small verified checker) and the same trade the platform makes dropping PMP (*verify rather than hedge*) and dropping Jasmin (fewer constant-time compilers), carried to zero verified-compiler CT routes.

**Disposition:** declined as a mechanism; its property is retained, verified on the artifact instead (§5, §15, §17).
Non-normative; the drop is normative in §5, §6, §15, §17.

---

## Translation validation: the alternative to the verified compiler, already run for the residual, the hedge for the CHERI-CompCert workstream

**Translation validation** (TV) proves a *specific* compilation correct after the fact: compile with an ordinary unmodified optimizing compiler, then prove that *this binary* refines *this source*, instead of proving *the compiler* correct once for all inputs.
seL4's own extension to the binary level takes exactly this route (Sewell, Myreen, Klein, PLDI 2013): stock `gcc` compiles the verified C (proven at `-O1`, most of the binary at `-O2`), the binary is decompiled into logic over the validated Cambridge ISA semantics, source and binary are lowered into a common control-flow-graph intermediate language, and refinement is discharged function by function by SMT.
It composes with seL4's functional-correctness, integrity, authority-confinement, and non-interference proofs and carries them all to the binary, and its headline is a trust-base result: the C parser *and* the compiler leave the trusted computing base, because the source proof and the binary proof connect to the *same* formal artifact (the parser's output), so how that artifact was produced stops mattering.

This is not a foreign technique to import but one the platform already runs, in three places:
- §5 already reads *"CompCert compiles all trusted C; translation validation against the RISC-V Sail model covers the assembly/link/image steps outside CompCert's theorem"*: TV for the verified compiler's residual.
- **CryptOpt** (§5) is verified translation validation for the field-arithmetic kernels: an untrusted superoptimizer admitted by a small Coq-verified equivalence checker.
- **Islaris**-style Iris-over-Sail (§5, §13) is direct binary-level proof for binaries with no verified compiler in the loop.

And the trust win TV is famous for, the parser and compiler leaving the TCB, is already banked by FPCC's *artifact-not-pedigree* rule (§5, §13).
So the question is not *whether* to use TV but *how far*: seL4 covers the **whole** C-to-binary compilation with it and ships on stock `gcc` with no verified compiler in its TCB, whereas this platform scopes TV to the residual and builds a verified **CHERI-CompCert** backend (§6, §18) as priority zero.
The paper raises whether extending the TV role already in the spec could **shrink or retire that prerequisite**, the single largest, least-built, net-new workstream on the books.

- **The ingredients are largely present, and performance-subordination helps.**
  The CHERI-RISC-V Sail model exists, Islaris is decompilation-into-logic already *in Coq* (the paper's is HOL4), **SMTCoq** (§5) pulls the SMT refinement back under the one kernel, and CryptOpt is the in-house precedent.
  seL4's TV produced no proof failures at `-O1`; the `-O2` cases (loop unrolling, aggressive interprocedural optimization) were the hard part, and this platform subordinates performance (§2) over a *tiny* TCB it can compile at `-O1` or below, the regime where TV is robust.
- **But it trades the scarce resource for the free one, the platform's own inversion.**
  A verified compiler is *one* theorem, proved once and reused across every TCB build; TV is *per-build* proof search that must succeed for each binary, and to stay single-prover its SMT step must be reconstructed in the kernel (SMTCoq) or the solvers become *checkers* and widen the trust base (§5).
  So TV spends trust (a new pipeline, per-build fragility, seL4's own `-O2` failures and small source tweaks) to save compiler engineering, and engineering is the free axis (§2): by the platform's own currency a verified compiler, once built, is the cleaner trust story.
- **TV gives functional refinement, not robust preservation.**
  The CHERI-CompCert backend must satisfy a *secure-compilation* criterion (robust preservation of compartment isolation against an adversarial linked context, the SECOMP2CHERI lineage, §5, §6), a hyperproperty over *all* contexts that per-program TV does not establish.
  The softening is that CHERI hardware plus the **Cerise** universal contract (§13) already bound an arbitrary adversarial context at runtime, so on a purecap platform CHERI ⋈ Cerise already delivers most of what the robust-preservation theorem asserts, and TV under that contract recovers the practical guarantee, short of the compiler-level hyperproperty.
- **The CHERI dimension is real rework.**
  seL4's TV was non-CHERI Arm; the stack heuristic, the calling convention, the memory model, and the pointer-validity and aliasing reasoning are all purecap-sensitive, so a lift is not free even with the Sail model and Islaris in hand.

What is **kept** is what the platform already does: TV for the compiler residual, CryptOpt for the crypto kernels, Islaris for the no-compiler path, FPCC for artifact-not-pedigree.
What is **logged** is the extension: translation-validating the *whole* TCB base image off a stock CHERI-LLVM `-O1` build, retiring or shrinking the CHERI-CompCert prerequisite, as the fallback if that backend proves intractable, with the direct evidence that the horn is viable being seL4 itself, the design this platform's kernel descends from (the seL4 vs. CertiKOS entry above).

**Disposition:** adopted in part and already normative (§5: TV covers the compiler residual, CryptOpt the crypto kernels, Islaris the no-compiler path); the full-coverage extension that would retire the CHERI-CompCert prerequisite (§6, §18) is logged as the fallback if that backend proves intractable, not a wholesale replacement, because a verified compiler is one reused theorem where TV is per-build search plus an SMTCoq reconstruction, and because only the compiler carries the robust-preservation hyperproperty (§5) that TV leaves to CHERI ⋈ Cerise at runtime (§13).
Non-normative; no spec-body change.

---

## Gate-level information-flow tracking and IFT-typed HDLs: GLIFT, SecVerilog; the hyperproperty half by another route, a bounded complement, not the Coq close

The proposal targets the same non-interference and timing-channel obligation the RTL ⊑ Sail *hyperproperty* half and the constant-time layer already carry, but via a **hardware information-flow method**: **GLIFT** (gate-level information-flow tracking; Tiwari/Wassel/Mao/Chong/Sherwood/Kastner, ASPLOS '09: track every bit's influence, including implicit and timing flows, from the gates up), and the information-flow-*typed* hardware-description languages that grew from it, **Caisson** (PLDI '11), **Sapper** (ASPLOS '14), and especially **SecVerilog** (Zhang/Wang/Suh/Myers, ASPLOS '15, Verilog with information-flow *types* that statically prove **timing-sensitive** non-interference at synthesis).

**The steelman: genuinely on target.**
It attacks a crown-jewel obligation directly: SecVerilog proves *timing-sensitive* non-interference: exactly the property the `Zkt`/`Zvkt` leakage model, the constant-time layer (§5), and the timing-annotated Sail model exist to establish; but at the **RTL**, where the transceiver, crypto core, and cache/NoC-partition logic actually live, and GLIFT catches the implicit and timing flows a *functional* refinement does not carry (the same hyperproperty gap the CT and WCET entries name).
It is an HDL / synthesis discipline, so it could sit on the very RTL the RTL ⊑ Sail arrow refines.

**Why it is a complement, not the closing vehicle.**
- **Trust base.**
  SecVerilog discharges via a type system plus **Z3**; Caisson/Sapper via their own checkers; GLIFT via logic synthesis: **none is Coq**.
  By the single-prover rule the platform applies to Binsec/Rel, EasyCrypt, aiT, and riscv-formal, an SMT / typed-HDL information-flow tool is a **trust-base widening**, admissible as bounded bring-up *evidence*, never the closing axiom.
- **The close is already chosen and Coq-native.**
  The timing-annotated Sail model ⋈ the **relational-Sail-logic constant-time certificate** (§5, §15, the binary-CT entry above) discharge the *same* hyperproperty in the one prover, at binary level against the model the silicon refines, so SecVerilog would duplicate, in a second trust base, a property already closed in the first.
- **The profile has less to track than GLIFT assumes.**
  GLIFT's shadow-logic (a tag bit per wire propagated in added gates) is priced for the *out-of-order, speculative* designs it was built to tame; the in-order, non-speculative, fixed-latency datapath (§15) gets timing-determinism *structurally* (no predictor state, fixed-latency units), so the flows GLIFT would instrument are largely designed out, not tracked.

**The distilled atom: the method, imported as a complement.**
Following the aiT / Binsec/Rel / riscv-formal pattern: *information flow as a hyperproperty discharged against a leakage model* is already the design's frame (the CT and RTL ⊑ Sail entries), and **SecVerilog-style IFT typing of the transceiver, crypto-core, and cache/NoC-partition RTL is logged as a bounded cross-check** in the same slot: bring-up evidence that flags a leak *before* the Coq relational proof closes it, exactly as riscv-formal BMC gates the functional refinement it does not prove.

**Where it ranks.**
Off the abandon-substrate scale: a verification *technique*, not an architecture; ranking alongside aiT, Binsec/Rel, and riscv-formal as an unverified complement to a Coq-native close: the *hardware-IFT sibling* of the binary-level constant-time tooling.

**Disposition:** logged as a bounded **complement**: SecVerilog-style IFT types (and GLIFT gate-level tracking) as a bring-up cross-check on the transceiver, crypto-core, and cache/NoC-partition RTL; **not** the closing axiom; the timing-sensitive non-interference obligation is closed Coq-native by the relational-Sail-logic certificate over the timing-annotated model (§5, §15), and a Z3 / typed-HDL information-flow tool is the same trust-base widening the platform books for Binsec/Rel and aiT.
It rides the existing hyperproperty slot, so nothing new imports.
Non-normative; no spec-body change.

---

## zkVM and proof-carrying execution: the rhyme with FPCC, and why static proof over the smaller trusted set wins

The proposal is **verifiable computation**: a zero-knowledge virtual machine (RISC Zero, SP1, Jolt, Valida; several are RISC-V zkVMs) that emits a succinct cryptographic proof that a *specific execution* ran faithfully to the ISA, checkable by a party who never saw the run.
It is a genuinely different meaning of *"verification"*: not *"the program is correct for all inputs"* (static, ahead of time) but *"this run produced this output"* (dynamic, per-execution, cryptographic).

**The steelman: the rhyme is real.**
It shares FPCC's headline shape (a proof travels with the artifact, checking is cheap and local, the producer is untrusted, §5, §6): so a single-prover project that already thinks in proof-carrying terms is looking at a proof-carrying *execution* model, and several instances are RISC-V-native, so it abandons no substrate.
It would add *remote* verifiability of a computation to a mutually-distrusting third party, something the local admission check does not directly provide.

**Why it does not import as a substrate.**
- **It buys a property outside the threat model, at the scarce-currency price.**
  zk-proving carries **10³–10⁶× execution overhead**; the platform spends performance freely, but not by six orders of magnitude, and the property bought: *a third party can check a run happened*; is not the platform's problem: the attested measured-boot root ⋈ reference integrity manifest (§9) already give a remote party a **reproduced-not-asserted** account of *what* is running, and FPCC gives the *static* guarantee it is correct **for all inputs**: strictly stronger, per input, than a per-execution transcript.
- **Per-execution proof is weaker than ahead-of-time proof for local security.**
  A zk-proof that *this* run was faithful to the ISA says nothing about whether the program is memory-safe, constant-time, or non-interfering *across* runs; the FPCC / CHERI-TAL stack (§13, below) proves those for **all** runs.
  And *"the machine executed the bytecode faithfully"* is exactly what **RTL ⊑ Sail** (§18) already establishes for the real silicon: once, structurally; without a per-run proof.

**The distilled atom: already banked.**
Proof-carrying *artifact* is the FPCC discipline (§5, §6); attested *what-is-running* is the measured root ⋈ reference manifest (§9).
The zk primitives themselves (a SNARK/STARK verifier) are ordinary contained crypto the platform could run as an *application* if a specific need ever arose: verifying an untrusted third party's *off-device* computation, say; an app-level tool, never a system execution substrate.

**Where it ranks.**
Rejected on **motivation**, one level above cost: like Wasm-as-substrate, it trades for a property the Goals do not seek (third-party verifiability of a remote execution) that FPCC ⋈ attestation already exceed for the local threat model; off the ILP ranking entirely, since it is not an ILP play.

**Disposition:** rejected as an execution substrate, the FPCC discipline already banks proof-carrying artifacts *statically and per-input* (stronger than a per-execution transcript), attestation already gives a remote party a reproduced account of what runs (§9), and RTL ⊑ Sail already proves the machine executes the ISA faithfully (§18); a zk verifier is admissible only as an ordinary **application-level tool** for checking a specific untrusted third-party computation, never a system execution model, and its six-order overhead is the wrong trade on the one axis the platform spends.
Non-normative; no spec-body change.

---

## Homomorphic encryption and secure multiparty computation as compute substrates: the privacy-preserving sibling of zkVM, rejected on the same two grounds

The proposal makes the execution substrate a **privacy-preserving computation** model: **fully homomorphic encryption** (FHE; Gentry, STOC '09: compute directly on ciphertext, the data never decrypted, so the executing machine never sees plaintext) or **secure multiparty computation** (MPC; Yao garbled circuits, GMW, secret-sharing: split a computation across mutually-distrusting parties so none sees another's inputs).
It is the confidentiality sibling of the zkVM entry (above): where zkVM adds *verifiability* of a remote execution, FHE/MPC add *confidentiality against the executor*.

**The steelman.**
FHE gives **data-in-use confidentiality against the host itself**: the strongest possible data-confidentiality, stronger even than the platform's TME (which encrypts at rest and in transit but decrypts in-core to compute, §15); and it is a genuinely different security model: confidentiality by *cryptography* rather than by *isolation*.
Some FHE/MPC implementations are formalization-adjacent, so it is not off the verification map.

**Why it does not import as a substrate: the zkVM rejection, verbatim, on two grounds.**
- **Threat model.**
  FHE/MPC protect a computation *from the machine running it*: the outsourced/cloud model where the executor is the adversary.
  This platform **is** the trusted machine: a personal device whose CHERI, kernel, and crypto core the owner trusts and the design *verifies*, whose confidentiality boundary is TME ⋈ the crypto core's hardware boundary (keys never leave) ⋈ CHERI/IFC in-core (§8, §15), and whose whole point is that computing on plaintext on-core is safe.
  Protecting the computation from its own trusted CPU is a property **outside the threat model**: the same "buys a property the Goals do not seek" rejection the zkVM (third-party verifiability) and Wasm-as-substrate (portability) entries make.
- **Overhead.**
  FHE carries **10³–10⁶×** slowdown (bootstrapping-dominated); MPC carries round-complexity and communication blowup, and its parameter- and noise-management structure is data-dependent in ways that fight the fixed-latency WCET tables (§11).
  The platform spends performance freely, but not six orders of magnitude to buy a property it does not need, the identical cost argument the zkVM entry books.

**The distilled atom: already banked / app-level.**
Data confidentiality here is **TME** (§15) at rest and in transit ⋈ the **crypto core's hardware boundary** ⋈ **CHERI/IFC** in-core (§8): confidentiality by isolation and at-rest encryption, matched to a threat model in which the CPU is trusted.
The FHE/MPC *primitives* are ordinary contained crypto the platform could run **as an application** if a specific need arose (private set intersection, a sealed-bid or private-contact-discovery protocol with an untrusted **remote** party): an app-level tool over native RV64+CHERI, never a system execution substrate, exactly the zkVM verifier's sole admissible role.

**Where it ranks.**
Rejected on **motivation**, one level above cost: with zkVM and Wasm-as-substrate, it trades the substrate for a property (confidentiality against a distrusted executor) the Goals do not seek for the local threat model, where TME ⋈ isolation already give confidentiality against the threats that *are* in scope; off the ILP ranking (not an ILP play), and paired with the zkVM entry as the two cryptographic-computing models rejected on threat-model + overhead.

**Disposition:** rejected as an execution substrate, FHE/MPC protect a computation from a distrusted host, a threat model this trusted, verified personal device is not in (confidentiality here is TME ⋈ the crypto-core boundary ⋈ CHERI/IFC, §8/§15, against the threats actually in scope), and their 10³–10⁶× overhead is the wrong trade on the one axis the platform spends; FHE/MPC primitives are admissible only as **application-level tools** for privacy-preserving interaction with an untrusted *remote* party, never a system execution model, the confidentiality sibling of the zkVM entry's verifiable-computation rejection.
Non-normative; no spec-body change.

---

## CHERI-TAL admission: type-check the artifact where a type system suffices, prove it where it does not

The proposal is to replace the bespoke per-property certificate formats with a **typed assembly language (TAL) for RV64+CHERI**: Tier-2 admission becomes **type-checking annotated binaries**, compilers **emit typing derivations rather than proof terms**, the on-device checker shrinks to a decidable type-checker, and the certifying-compiler workstream (§18) collapses to *"target the TAL."*
This is the **Necula → Morrisett arc** (proof-carrying code narrowed to a type discipline: TALx86, then foundational TAL) and it is the proposed structural fix to the two admission contradictions the spec still carries: the checker-size claim (a ~10³-line *CIC term* checker does not exist: MetaCoq's is tens of kLoC and axiomatizes guard/termination) and the pedigree seam (§5 calls verification a property of the artifact yet mandates the build path).
It lands unusually cleanly here because **CHERI already discharges spatial safety in hardware**, so the type system need not encode bounds proofs, the capability *is* the bound.

**The decomposition: and why the whole certificate scheme does not collapse into types.**
The assurance obligations split along a line this document already draws three times (RTL ⊑ Sail, WCET, CT: each a *functional ⋈ hyperproperty* split):
- The **type-level obligations** (memory safety (temporal + spatial), control-flow integrity, no-runtime-codegen (W^X, §14), ABI/type conformance, the **constant-time** of structured secret code (a taint-type discipline, below), and the **WCET** of structured code (a syntax-directed cost annotation, below)) are exactly what a TAL type system *decides*.
  These are the whole of Tier-2, the structural half of Tier-1, and (for the structured population) the constant-time and worst-case-timing obligations that would otherwise be release-time proof terms.
- The **deep** obligations (Tier-0 functional refinement, the binary refines the seL4 abstract spec, whole-graph non-interference (§8), crypto **reduction** security (IND-CCA/EUF-CMA, §5), filesystem linearizability + liveness (§10)) are **not typing judgments**: no decidable type system states "this binary refines the abstract kernel", so those need a full higher-order logic and a proof term.
  **Constant-time and WCET are the boundary cases, and for structured code they *do* type-check.**
  CT is a 2-safety hyperproperty, but **CT-Wasm** (Watt et al.) shows it decidable as a *taint-type discipline* (secret-labeled values that provably never reach a branch, an address, or a variable-latency op), with mechanized type-soundness (Isabelle there, a Coq restatement here); and structured-code WCET is a syntax-directed max-path sum over the typed control-flow graph (Shaw's timing schema).
  So both **join the type-level tier for the structured population** the obligations actually cover (the straight-line CryptOpt kernels, the structured Tier-1 secret paths), leaving only the genuinely unstructured CT/WCET residual as proof terms: the relational-Sail 2-safety logic shrinks from *the* CT vehicle to a corner case (§5).

So the TAL does not *replace* the certificate scheme, it **stratifies** it, taking the tier where a type system is complete and leaving the tier where only a proof will do.
This is the crypto/WCET/CT move run in reverse: those dispositions showed the *hyperproperties* need more than a functional logic; the TAL shows the *type-level* properties need less than a proof kernel.

**What CHERI buys the type system.**
TALx86 had to encode array-bounds and initialization proofs into its types because x86 had no hardware notion of a bound; on a purecap machine the bound, the tag, and monotonicity are architectural, so the CHERI-TAL types shrink to the *residual* CHERI does not enforce at runtime: **temporal** safety (linear/affine capability types, the discipline **StkTokens** (Skorstengaard/Devriese/Birkedal, POPL 2019) formalizes in the same capability-machine-logic lineage as Cerise; a revocation-coloured heap in the CHERIoT lineage) and **typed control flow** (well-typed jump targets *are* CFI).
And that residual is precisely what safe Rust's ownership discipline already establishes at source (§5): the TAL is the vehicle that *carries those source types down to the binary as a checkable derivation*, turning §5's "the compiler preserves and certifies rather than re-discovers" from a promise into a concrete artifact format: the memory-safety analog of carrying constant-time to the binary as a checkable certificate (§5).

- **It fixes the checker-size contradiction: by splitting the checker, not by shrinking a CIC checker.**
  A TAL type-checker is decidable, syntactic, obviously terminating (no guard/termination side-condition to axiomatize), and genuinely on the order of 10³ lines: so the **on-device admission checker** that runs on every install and sits in the boot TCB *is* that type-checker, and the ~10³-line claim, false for a CIC term checker, is **true for this one**.
  The full **CIC proof kernel** (MetaCoq-lineage, honestly tens of kLoC) does not vanish: it validates the deep Tier-0/hyperproperty proofs; but it moves to where those proofs actually live: **release-time, over the fixed base-image TCB**, its result bound into the signed measured-boot root (§9), not a per-install on-device cost.
  "Checking is cheap and local" becomes *literally true* for the TAL admission path and is **honestly retracted** for Tier-0 (an seL4-scale refinement is machine-hours to check).
  Both horns the contradiction offered ("a genuinely tiny logic" and "a larger checker named as the axiom") are taken, each in its proper tier.
- **It fixes the pedigree contradiction: admission gates on the derivation, not the producer.**
  Once the certificate *is* a typing derivation the checker re-checks, **any** producer of a well-typed CHERI-TAL binary is admissible by definition; the certifying Rust→CHERI compiler (§18) becomes the *reference producer*, not a gate.
  The "mandatory build path" language conflated "we ship one reference toolchain" with "only its output is admitted": the TAL drops the second, making admission genuinely language- and pedigree-agnostic (§5), while the hardware universal contract (Cerise, §13) stays beneath as defense-in-depth against a checker or TAL-soundness error.
- **The one new axiom is the TAL's soundness metatheorem: a crown jewel, paid once.**
  Type-checking is only as sound as the theorem *"well-typed CHERI-TAL ⇒ the safety properties hold over the Sail model"*, a foundational-TAL syntactic-soundness proof (WasmCert-Coq / RustBelt lineage), authored once in Coq against the §15 model.
  It joins the crown-jewel specs (§5): a mis-stated typing rule admits an unsafe binary that type-checks perfectly.
  But it is a *smaller and more scrutable* axiom than "a hand-built ~10³-line CIC checker is correct," which is the trade the contradiction was pushing for.

**Prior art, and where it ranks.**
The lineage is real and mechanized (Necula's PCC, Morrisett's TALx86, Appel's foundational PCC, Crary's foundational TAL, and on the memory-safety-type side RustBelt (Iris) and WasmCert-Coq (mechanized type soundness)); so nothing here gambles on the *type-soundness* half; the net-new work is the CHERI-RISC-V *instantiation* (the temporal-safety type discipline over capabilities) and the compiler emitting derivations, which is a **refactor of the §18 certifying-compiler deliverable, not a new one**, its certificate format changes from ad-hoc Islaris terms to TAL derivations and its checker shrinks.
Unlike the belt/EPIC/Wasm targets this abandons no substrate choice (RV64 + CHERI + FPCC all stay); it changes only the *shape of the evidence* on the type-level tier, so it is off that ranking: a structural refinement of the admission discipline, not an alternative to it.

**Disposition (adopted in part; normative in §5, §6, §13).**
Admission is **stratified into two checkers along this document's own functional ⋈ hyperproperty line**.
A small, decidable **CHERI-TAL type-checker** is the on-device admission checker for the **type-level** obligations: Tier-2 in full (temporal + spatial memory safety, CFI, no-codegen, ABI/type conformance) and the memory/ABI-conformance half of Tier-1; with the certifying compiler *targeting the TAL* and certificates carried as **typing derivations**, so admission is genuinely pedigree-independent and the ~10³-line / "cheap and local" claim is true of it.
The **CIC proof kernel** is retained for the **deep** obligations no type system states (Tier-0 functional refinement + non-interference (§8), crypto reduction security, the *residual unstructured* constant-time and WCET, filesystem linearizability/liveness): validated predominantly **at release time over the base-image TCB** and bound into the measured root (§9).
The platform axiom decides this exactly as it did for seL4 and crypto (**methodology is portable, the smallest trusted set wins**): spend the engineering to make the per-install admission checker a type-checker whose soundness is one Coq theorem, rather than a general proof checker no one can hold to 10³ lines.
**Honest residual (§17):** the CHERI-TAL soundness metatheorem is a new crown-jewel spec; the deep-proof CIC kernel is *named* as the larger admission axiom rather than hidden inside a 10³-line claim (so "checking is cheap" holds only for the TAL tier); and the temporal-safety type discipline over CHERI capabilities is the net-new instantiation the certifying-compiler workstream (§18) carries in place of a bespoke certificate format.

---

## Synchronous control planes via Vélus: the sequencing logic is already dataflow; write it where determinism, WCET, and causality are structural

The proposal takes the observation that the platform has already imposed every precondition of the **synchronous-dataflow** model (TDM schedules, static composition (§7), bounded IDL (§12), non-work-conserving partitioning (§11), crash-only servers with explicit re-initializable state (§12, §16)): and draws the conclusion: the **control planes** of §12 (the sequencing, supervision, and protocol state-machine logic, as opposed to the bulk **data planes** that move bytes) are *morally* Lustre programs already, written the long way in imperative Rust.
**Vélus** is a **Coq-verified compiler for Lustre** (Bourke/Pouzet lineage, PLDI'17 and after) that emits **CompCert Clight** and whose correctness theorem *composes with CompCert's*: so writing a control plane in Lustre and compiling it through Vélus → CompCert buys **verified compilation, structural WCET, and causality/determinism by construction, at zero new prover**, with Rust retained for the data planes.
Of the rearchitecture candidates this is the only one that *reduces* net-new tooling rather than trading one workstream for another.

**The control/data split the section already draws.**
§12 is written around exactly this line without naming it: the **ring data plane** moves bulk bytes over SPSC rings and "authority physically cannot cross" it, while "new authority arrives via **control-plane IPC** only."
The data planes, ring processing, the PHY long-vector math, wire parsing (Narcissus, §5), the crypto core (§5), are throughput code over unbounded streams and stay safe Rust / verified C.
The control planes are **reactive state machines over bounded events**: the service manager's supervision tree (start-order, crash detection, restart-with-backoff, capability re-grant), the protocol sequencers (RRC/NAS/MLME/L2CAP-GATT/PDCP-RLC state and their T3xx-class timers: the *control* half of the L2/L3 servers whose *data* half stays Narcissus-parsed Rust), the power/mode/DRX/HARQ timing controllers (§11, §15), and the sentinel's detection→response logic (§12).
These are the textbook domain of Lustre/SCADE, the language family that certifies avionics and nuclear-reactor control (DO-178C) precisely because a synchronous program is *deterministic and bounded by construction*.

**What the synchronous model makes structural: three obligations this document works hard for elsewhere:**
- **WCET is structural, not derived.**
  A Lustre node compiles to a **loop-free, statically-bounded reaction**: one activation is a fixed amount of computation over a statically-sized state, no dynamic allocation, no unbounded loop.
  So the control tier's worst-case execution time falls out of Vélus compilation *by construction*, not from the syntax-directed WCET cost annotation (§5, §11) an arbitrary Rust control-flow graph needs; that harder loop-bound/path work is left to the data planes.
  This is a direct **shrink** of the §11 WCET surface, and it is why *structural WCET* is the headline dividend here.
- **No hidden state survives an activation.**
  A synchronous node's entire state is the explicit, statically-sized Lustre memory; there is nothing latent between ticks.
  This is admission-test-3 (*no hidden state survives a partition switch*, §15) discharged by construction for the control tier, and it makes **crash-only** re-initialization (§12) a well-defined state reset rather than an audit of imperative heap.
- **Determinism and causality are compiler-checked.**
  Vélus's clock calculus rejects instantaneous cycles and fixes evaluation order, so a control plane is deterministic and causally well-formed *before* it compiles, feeding the non-interference-over-a-fixed-graph theorem (§8) a control tier with no schedule-dependent behavior to reason about, and the memory-safety certificate (§13) a body whose static allocation makes the temporal-safety obligation trivial.

**Why this is not a third language.**
The realization plan's discipline is *"two languages, one machine"* (Sail and Coq/Gallina) and Lustre could look like a violation.
It is not, at the level that matters: **Vélus's Lustre semantics *and* its compiler correctness are both formalized in Coq**, and it emits Clight into the CompCert (→ CHERI-CompCert, §6) pipeline already in the trust base.
So Lustre is not a new *trust base*: it is a **Coq-verified domain-specific generator emitting Clight**, exactly the shape of **Narcissus** (Coq-native parser DSL) and **Fiat-Crypto** (Coq-native field-arithmetic DSL) already relied on in §5; the two trust languages stay Sail + Coq.
Vélus is in fact the *strongest* member of that family, because unlike a synthesis tactic it is a *whole verified compiler* whose theorem chains with CompCert's rather than terminating at a synthesized term.

**Prior art, and where it ranks.**
The lineage is mature and mechanized, Lustre/SCADE in certified avionics, and Vélus itself a published Coq artifact that compiles a real Lustre subset, nodes, reset, control blocks, and **state machines** (POPL'23), through CompCert with an end-to-end correctness proof, the state-machine result landing exactly on the protocol-sequencer use case.
Unlike the belt/EPIC/Wasm targets this **abandons no substrate** (RV64 + CHERI + FPCC + the Rust data planes all stay) and unlike kernel-in-gateware it fuses nothing; it changes only the *source language of one tier of one non-TCB layer*, so it is off that ranking, a structural refinement of how §12 control logic is written, and the rare one that *removes* tooling (the control tier's WCET and memory-safety obligations become structural) rather than adding it.

**Disposition (adopted; normative in §5, §11, §12).**
The **control-plane** logic of §12 servers, supervision/sequencing, protocol state machines, mode/timing control, is written in **Lustre and compiled by Vélus** (Coq-verified, → Clight → CHERI-CompCert), a Coq-verified DSL alongside Narcissus and Fiat-Crypto (§5); the **data planes** stay `#![forbid(unsafe_code)]` safe Rust.
Scope is honest: the adoption covers the logic that *is* reactive dataflow, and Rust is retained wherever a control path is genuinely imperative request/response rather than a state machine, a mis-drawn boundary is a spec error, not a silent failure.
The platform axiom decides it as ever, *methodology is portable, the smallest trusted set wins, and engineering is the free axis*: spend the engineering to move sequencing onto a language where determinism, causality, and WCET are theorems of the compiler rather than fresh per-server proof obligations.
**Honest residual (§17):** Vélus enters the build path as a new front end: Coq-verified, so it adds *no fresh axiom* and rides the already-priority-zero CHERI-CompCert backend (§18), but its Lustre-semantics faithfulness joins the crown-jewel specs and the **control/data boundary is a new crown-jewel interface**; offset against this, the control tier's structural WCET (§11), structural memory-safety certificate (§13), and by-construction determinism (§8, §15) are a net reduction in proof surface.
- **ct-verif: the IR-level sibling, not the binary-level answer.** ct-verif verifies CT by product programs over **LLVM IR** (SMT-discharged).
  It is real and usable, but IR-level: the platform verifies CT **on the binary** for every secret-touching artifact (no verified-compiler CT path), and there is no trusted IR to check at that point: the binary is the artifact.
  So ct-verif is the sibling to note, Binsec/Rel the complement to adopt: analogous to **EverParse** being noted-but-not-adopted for parsing (§5), though here the mismatch is level-of-abstraction, not trust base.
- **Scope is a labeling obligation, not a blanket tax.**
  CT is required only of compartments that receive **secret-labeled** material over an IDL confidentiality channel (§12); ordinary apps that touch no secrets carry no CT obligation.
  This matches the profile's *"tighter guarantees sharpen the holder's stopwatch"* scaling (§17) and hooks CT into the existing IFC/flow-label machinery (§8, §13) rather than inventing a new trigger: a secret reaching an un-CT-verified compartment is a *flow-label* error the Tier-1 flow theorems must catch.

**Disposition (adopted; normative in §5, §13, §15).**
Verify CT **on the artifact** against the one `Zkt`/`Zvkt` leakage model for every secret-touching binary (there is no verified-compiler CT route); split it functional ⋈ hyperproperty like RTL ⊑ Sail, with the **relational-Sail-logic constant-time certificate** the Coq-native close and **Binsec/Rel** the mature bounded complement (**ct-verif** the IR-level sibling).
The platform axiom decides the toolchain as ever, *methodology is portable, maturity is not*: carry the Coq-native property to Binsec/Rel's demonstrated binary-level capability, spending engineering to keep CT on the single prover and make it *artifact*-borne.
**Honest residual (§17):** Binsec/Rel is path-bounded evidence (the certificate is the unbounded close); CT verification inherits the RTL ⊑ Sail residual (the leakage model is sound only once that arrow closes) and leans on the `Zkt`/`Zvkt` leakage-model statement as a shared crown-jewel spec; and correctness of *scope* rests on the flow labels (§8, §12, §13), so a mislabeled secret is a spec error no CT proof catches.
Like WCET it **degrades gracefully**, bounded Binsec/Rel evidence carries bring-up, the certificate closes it, so it gates *strong* CT assurance, not boot.
