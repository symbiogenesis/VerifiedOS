# Evaluated Architectural Alternatives (non-normative)

> Companion to [spec.md](spec.md).
> This document records only evaluated proposals that were **rejected, deferred, or imported in no part**; it is **not** part of the normative spec.
> Decisions and prior art that the normative design actually adopted live in [inspirations.md](inspirations.md), not here.
> Cross-references of the form §N point to sections of that specification.

It exists so the living document carries the reasoning behind what was *not* adopted.

## Belt / Mill-class architecture: deferred to a hypothetical gen-2, on one ground

Mill's security features were run through the §15 admission test and the import discipline:
- **Protection ≠ translation, turfs, portal calls (PLB separate from TLB)**: Mill's headline model is **already subsumed by CHERI**: capabilities bound memory irrespective of page tables, and sealed-capability domain crossing is the portal. The spec converges on Mill's single-address-space-with-per-domain-protection vision from a substrate that has a formal model (Sail, Cerise) Mill lacks, and the base makes the convergence literal by deleting the MMU outright (below): protection is by capability alone, with no translation to separate from.
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
  Its residual is exactly the one already accepted for wrong-path static fetch (§15, "Control-flow prediction"): a hoisted load's memory access is a deterministic function of the compiler-fixed instruction stream, not of learned history, so there is no cache footprint to perturb (§15) and it needs no special treatment, the sole caveat being that a *secret-dependent* speculative address is an ordinary `Zkt`/`Zvkt` flow-label obligation, no different from any load.
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
The IPC tax is not the cost of *owning* a speculation engine VLIW would let it remove: the base is *already* in-order and *already* forbids speculation and dynamic prediction (§15), so **the tax is the price of *forbidding* speculation, not of a removable mechanism.**
VLIW deletes nothing here; it *adds* a mechanism to claw performance back, and that mechanism *enlarges* the verified surface at every layer: a bigger Sail model (bundles, poison, predication, rotation), a bigger RTL ⊑ Sail proof (already the least-built arrow, §17), CHERI re-integrated against a new encoding, and, decisively, a **verified trace scheduler for EPIC's predicated, poison-tagged, rotating-register bundles** that Chamois/KVX-CompCert's verified bundle scheduling does not reach (it targets only the far simpler Kalray VLIW): net-new, hard proof.
Its famous dividend, moving scheduling from hardware into the compiler, is already spent, since an in-order core has no hardware scheduler to move; and EPIC's own ILP mechanisms (ALAT, RSE) make WCET *worse*, so importing them *costs* §11 determinism.
By the platform axiom this is the wrong trade: spending the scarce currency (trust, proof surface) to buy the free one (performance).

**Bespoke, microarchitecture-coupled binaries: the disqualifier, not an inconvenience.**
The instinct that VLIW needs specially compiled binaries is right, and it is fatal, on three compounding counts.
(1) VLIW bundles are a distinct encoding, so standard RV64IMV+CHERI binaries do not run: forking the single-recompile-target premise of [userspace-porting.md](userspace-porting.md) (certifying Rust → RV64+CHERI) into two.
(2) VLIW's classic curse: a schedule encodes the *specific* issue width and operation latencies it was packed for, so a pipeline change forces a recompile: re-coupling ISA to microarchitecture, the exact thing RISC-V's abstract contract exists to prevent, and violating §15's "one base ISA, one kernel binary, one parameterized model; classes differ only in datapath" property (a bundle schedule is not portable across the C/V/M scalar front ends).
(3) Every FPCC artifact (the binary-level proofs, memory-safety certificates, and constant-time certificates of §5/§6/§13) is stated *at binary level against the CHERI-RISC-V Sail model*, so a new ISA forks that model, CHERI itself, the CHERI-CompCert backend, Cerise, and Islaris, and **re-mints every certificate stated against it**, retargeting the whole Tier-1/2 toolchain.
This count is the **substrate-cost disqualifier**, and it is stated here once: every later entry proposing a distinct instruction set pays it in full and cites it rather than re-deriving it.
The bespoke-binary requirement thus re-imports precisely the microarchitecture-in-the-binary coupling RISC-V's abstract ISA was chosen to delete.

**Where EPIC ranks among the "abandon RISC-V for ILP" targets.**
The belt entry already ordered EDGE ≻ belt on transactional-coherence grounds (block-atomic commit *rhymes* with G4 and §11).
EPIC ranks **below both**: its one edge over Mill and TRIPS is that it *shipped*, but it shipped and *died*, so the ecosystem advantage is negative; its ILP recipe leans on ALAT and RSE, which fail the admission test where the belt's spiller and EDGE's block commit do not; and it *rhymes* with nothing in the architecture.
A belt is a clever operand-lifetime trick and EDGE a transactional pipeline; EPIC is a compiler-scheduling bet whose hardware crutches this spec forbids.

**Disposition:** rejected as a base direction: EPIC abandons the RISC-V substrate as fully as the belt (into a post-mortem ecosystem), *inverts* the hoped-for simplification (the in-order IPC tax is the price of forbidding speculation, not a removable engine; VLIW only adds verified surface), and mandates bespoke, microarchitecture-coupled binaries that fork both the ecosystem and the proof base.
**Two non-redundant atoms are distilled and kept inside RISC-V:** (1) **NaR/NaT deferred-fault poison loads**: separable from both belt and bundle, admissible as a *small* extension, the genuine "ILP without speculation" lever, logged here as the sharper form of the belt entry's metadata-speculation argument and the first candidate should that constraint bind; and (2) **wider in-order superscalar + verified static scheduling on plain RV64**: already licensed by §15's *in-order single/dual-issue* C-class and ideally served by the bespoke compiler, the actual answer to "the in-order path is slow," strictly *before* any ISA fork.
Both remain non-normative; **VLIW as a whole imports nothing**, and ranks below both the belt and EDGE as an abandon-the-register-file target.

---

## Secure speculation via information-flow tracking: SecureBOOM, STT, DOLMA; the leak is bounded in a foreign prover, the timing and proof costs it leaves behind are not

The proposal is the direct counterpoint to the belt and EPIC entries (above): where they recover instruction-level parallelism by *avoiding* speculation (NaR metadata speculation, no rollback, no transient-execution class), this line *keeps* full out-of-order speculation and proves the transient leak closed.
The strongest instance is **SecureBOOM** (Jauch, Wezel, Fadiheh, Schmitz, Ray, Fung, Fletcher, Stoffel, Kunz; ICCAD 2023; RPTU Kaiserslautern), which augments a full out-of-order BOOMv3 with a generic dynamic **taint** layer and an **information-flow controller** that selectively stalls or squashes the instructions ("transmitters") capable of turning transiently-accessed data into a microarchitectural signal, refined iteratively until the RTL passes **UPEC** (Unique Program Execution Checking; Fadiheh et al.), an exhaustive SAT-based, cycle- and bit-accurate property check for transient-execution side channels.
It is the register-transfer realization of the software-mitigation lineage (**STT**, Speculative Taint Tracking, Yu et al., MICRO 2019; **DOLMA**, Loughlin et al., USENIX Security 2021).

**The steelman: a real result, and an elegant one.**
SecureBOOM is, to its authors' knowledge, the first formally-verified RTL out-of-order core featuring secure speculation with competitive performance (BOOMv3, RV64GC, boots Linux), at 5.2% overhead under its weaker (`spectre`) threat model and 36% under the stricter (`futuristic`) one.
The flow is genuinely attractive on its own terms: the taint-plus-controller infrastructure is generic and needs no security expertise, UPEC's exhaustive counterexamples pinpoint the exact transmitter to fence rather than forcing a blanket flush, and the proof catches *unknown* channels, not only known Spectre variants.
If the only objection to speculation were that it leaks secrets, this would be a serious dent in the profile's deletion of it.
The deployed-silicon record marks the same dividing line the profile draws: the first systematic Spectre study of commercial RISC-V parts (Gerlach, Bognar, Weber, Schwarz, Van Bulck; USENIX Security 2026) finds the shipping out-of-order cores (SiFive P550, T-Head C910/C920) exploitable across the PHT/BTB/RSB/STL variants, with the x86/Arm mitigations not transferring and the in-order parts resistant: unfenced speculation in the field is a live adversary, and no shipped core carries a SecureBOOM-class proof.

**Why it does not clear the admission bar: it answers a question this design does not ask, in a currency it does not spend.**
The profile's speculation stance is not "speculation leaks," it is "speculation and its entire proof-and-timing burden are deleted (§15)," and SecureBOOM lowers the price of a *different* trade along *four* separate axes, only one of which it touches.
- **The guarantee is in a foreign prover: an oracle, never the closing axiom.**
  UPEC is an exhaustive RTL property checker, not a Coq refinement; by the single-prover rule the platform applies to riscv-formal, aiT, Binsec/Rel, and EasyCrypt, it is a **trust-base widening**, admissible only as bounded bring-up *evidence* that enters no trust base, exactly the disposition the GLIFT / SecVerilog entry (below) gives every RTL information-flow tool.
  Even granting UPEC a complete proof of its property, it establishes a fact about the RTL *directly*, not the RTL ⊑ Sail refinement the WCET, constant-time, and non-interference theorems are quantified over: that refinement would still be owed, over a far larger model.
- **It maximally inflates the least-built arrow.**
  RTL ⊑ Sail is the design's hardest and least-built proof, and an out-of-order speculative core is the canonical state-space-explosion case; the proof-aware design-space exploration (§15) weighs *proof simplicity* as a first-class objective precisely so a smaller microarchitecture yields a smaller Sail model and a cheaper refinement, and speculation is the maximal move against it.
  This is the EPIC-entry inversion (above) at microarchitectural scale: spending the scarce currency (proof surface on the least-built arrow) to buy the free one (IPC).
- **It closes one of four blockers and leaves the timing half untouched.**
  Speculation was deleted for the transient leak, for timing determinism, for hidden state surviving a partition switch, and for the classical channels, and SecureBOOM addresses only the first.
  Worst-case timing: the design's bound collapses to a tree sum precisely because an overlap-free, non-speculative pipeline leaves the estimator no path interference to resolve (§11, §15), and out-of-order execution reintroduces exactly the history- and pipeline-state-dependent latency that makes WCET intractable and breaks the static cyclic executive (§7); UPEC certifies nothing about it.
  Admission test: the branch predictor and the speculative structures are hidden, history-indexed shared state that survives a partition switch (test 3), and out-of-order completion is data-dependent by design (test 2), so satisfying the profile would still demand a `fence.t`-class flush on every switch, forfeiting the out-of-order benefit and adding the flush obligation, whether or not the *secret* leak is fenced.
  Classical channels: SecureBOOM's *own* threat model excludes them (it explicitly places the instruction-cache footprint of square-and-multiply RSA out of scope), whereas the cacheless, in-order profile deletes the co-residency and cache-timing classes at the source (§15), so secure-OoO would reopen a channel class the design closed by construction and re-shut only its transient subset.
- **The confidentiality scope is weaker.**
  SecureBOOM declares architectural registers non-confidential and pushes "do not spill secrets into registers" onto the software developer, below the platform's binary-level constant-time bar; carrying constant-time over a speculative core would require a speculative-leakage contract (the hardware-software-contracts line, Guarnieri et al.) baked into the leakage-annotated Sail model and into every relational CT proof, replacing what the fixed-latency profile obtains structurally for straight-line code (§5, §15).

**The distilled atom is already banked, and it is the opposite trade.**
The design's answer to "recover ILP without re-admitting the leak" is not secure-OoO but **NaR / metadata speculation** (the belt and EPIC entries above): deferred-fault poison loads give the speculative *scheduling* benefit with no microarchitectural rollback and therefore no transient-execution class at all, so there is nothing to fence and nothing to prove secure.
That is the shape of an admissible ILP recovery here, alongside macro-op fusion, the one in-model performance win admitted precisely because it is architecturally transparent, adds no hidden state, opens no timing channel, and *tightens* WCET (§15).
Secure-OoO is the mirror image: add the mechanism, then spend scarce proof to fence it and still owe the timing and refinement costs; the enclave entry (below) reaches the same verdict from the isolation side, where the transient and shared-microarchitecture threats are *deleted, not defended*.

**Where it ranks.**
Off the abandon-substrate scale, evaluated as two things.
As a microarchitectural mitigation it imports nothing, being the security patch for a mechanism the profile does not contain.
As a verification method, UPEC is logged in the same slot as GLIFT / SecVerilog and riscv-formal (below): a bounded, non-Coq, information-flow property checker useful as bring-up evidence *were* speculation ever admitted, never the Coq close.

**Disposition:** no import.
Secure speculation lowers the cost of *keeping* out-of-order speculation and blocking its transient leak; the profile's bet is to *delete* speculation together with its WCET intractability, its hidden predictor state, its classical channels, and its share of the RTL ⊑ Sail proof, and re-admitting it would sacrifice all four to recover an IPC the NaR atom (above) recovers without any of them.
UPEC and its STT/DOLMA-style information-flow tracking are logged, with GLIFT / SecVerilog (below), as a bounded bring-up complement that enters no trust base.
Non-normative; no spec-body change.

---

## Non-speculative out-of-order and the invisible-speculation family: NS-OoO dataflow cores, InvisiSpec, delay-on-miss, DAE; out-of-order is separable from speculation, but the latency wall it hides is deleted and the dynamic scheduler it adds is the data-dependent timing the profile forbids

The proposal is the third leg of the speculation/out-of-order design space the belt/EPIC and SecureBOOM entries (above) open: where the belt recovers instruction-level parallelism by *avoiding* speculation (NaR metadata speculation, no rollback) and SecureBOOM *keeps* full speculation and proves the transient leak fenced, this line **keeps the out-of-order execution engine and deletes only the speculation**: dynamic (Tomasulo/reservation-station) scheduling that issues an instruction the moment its data operands are ready, but fetch strictly down the architecturally-correct path with **no control speculation** (stall at an unresolved branch rather than predict it).
It bundles the variants the popular framing raises: **non-speculative out-of-order / dataflow cores** (the pure form), the **invisible / undo / delay** speculation schemes (**InvisiSpec**, Yan et al., MICRO 2018; **delay-on-miss**, Sakalis et al., ISCA 2019; **CleanupSpec**, Saileshwar & Qureshi, MICRO 2019; and the **SafeBet** / speculative-data-oblivious line, Yu et al., ISCA 2020), and **decoupled access-execute** (DAE, J.E. Smith, ISCA 1982), plus the "deterministic time-based CPU" vendor pitch.
They are resolved individually against the §15 admission test, the same decomposition that logged the belt's spiller and EPIC's NaR while rejecting the rest.

**The steelman: one real and correct insight.**
Out-of-order *execution* (dynamic scheduling: execute when operands are ready) is genuinely separable from *speculation* (transient execution of instructions that may be squashed), and Spectre and Meltdown are properties of the latter, not the former: Spectre is wrong-path transient execution, Meltdown is transient forwarding of a permission-violating load's result to its dependents.
A core that schedules out of order but never fetches past an unresolved branch, and never forwards a bounds-failing load to its dependents (automatic on a purecap machine, where the bounds check *is* the dereference, §15), is **Spectre- and Meltdown-immune by construction while still hiding memory latency through memory-level parallelism**: overlapping independent long-latency loads in the shadow of a stalled one.
That the security-relevant axis is speculation and not out-of-order-ness is correct, and it is the one thing the framing that conflates the two gets right.

**Why it clears no bar this design has: it hides a wall the design already demolished, and pays for it in the scarce currency.**
- **The latency wall it exists to hide is deleted (the decisive, design-specific point).**
  Out-of-order-plus-speculation won the last thirty years as a *latency-hiding* technology for the widening CPU↔DRAM gap; memory-level parallelism is worth exactly the miss latency it overlaps.
  This machine has **flat, low-latency, deterministic on-die SRAM main memory and no cache hierarchy** (§15; the no-hardware-caches entry below), so there is no hundreds-of-cycle miss to shadow: the textbook "out-of-order recovers 2–3× over in-order" assumes a DRAM/cache hierarchy this platform does not have, so the large fraction of that benefit a non-speculative out-of-order core is credited with recovering inverts here, because in-order *already* captures most of the little that flat SRAM leaves on the table.
  The dominant thing NS-OoO buys is absent here by prior construction.
- **What memory-level parallelism remains needs the one speculation NS-OoO forbids.**
  Real out-of-order MLP is bought with *memory-dependence speculation* (store-sets: issue a load past unresolved stores it is predicted not to alias): speculation with a stateful, history-indexed predictor, the same hidden shared state the LR/SC reservation set and the dynamic branch predictor are *deleted* for (§15, admission test 3).
  A genuinely non-speculative core must instead wait for every prior store *address* to resolve before issuing a load, serializing exactly the load stream whose parallelism was the point; so NS-OoO's MLP is narrower than the pitch, and widening it re-admits a predictor the profile forbids.
- **The window collapses to the next unresolved branch.**
  Without control speculation the effective reorder window is bounded by the distance to the nearest branch whose condition is not yet computed: roughly five to seven instructions in control-heavy integer code.
  The control-speculation half of out-of-order's benefit is irrecoverable, so a non-speculative core recovers a large fraction of it only for long dependency-free windows (streaming, vector, FP) and far less for the branchy integer and control code the scalar cores run; and the V/M datapaths, which *do* have such windows, already hide their latency through vector length and the systolic array (§15), so NS-OoO would help precisely the cores where the branch wall bites hardest and least where latency-hiding is already solved.
- **It reintroduces the data-dependent timing the whole edifice forbids (admission test 2, and WCET).**
  A dynamic scheduler's issue cycle is a function of operand-ready time, hence of data (variable-latency producers, bank conflicts, reservation-station and issue-port occupancy): the data-dependent latency the fixed-latency profile, the `Zkt`/`Zvkt` contract, and the constant-time layer (§5, §15) exist to forbid.
  And it collapses the §11 WCET bound from a tree sum back to the path-interference problem IPET exists to solve, because reservation-station pressure, issue-port and writeback contention, and load/store-queue occupancy are exactly the pipeline-state-dependent latencies an overlap-free non-speculative core was chosen *not* to have (§5, §11): the same objection the SecureBOOM and asynchronous-logic entries make, here from the scheduler rather than the predictor or the gates, and the static cyclic executive (§7) breaks with it.
- **New hidden state to flush, and the least-built arrow inflated (admission test 3, and RTL ⊑ Sail).**
  The reorder buffer, reservation stations, load/store queue, and physical register file are new microarchitectural state surviving a partition switch, *enlarging* the `fence.t` flush set the cacheless, predictor-free profile worked to shrink (§15).
  And a register-renamed, dynamically-scheduled core is the canonical state-space-explosion case for RTL ⊑ Sail, the least-built arrow (§17, §18) with no off-the-shelf non-speculative application-class RISC-V core to start from (BOOM is speculative, Rocket in-order), so it is net-new RTL *and* net-new proof; the proof-aware design-space exploration (§15) weights proof simplicity as a first-class objective precisely to avoid this shape.
  This is the EPIC/SecureBOOM inversion again: spend the scarce currency (proof surface on the hardest arrow, a bigger flush obligation, a broken WCET model) to buy the free one (IPC), for a latency-hiding win the memory subsystem already delivered.

**The named variants, dispositioned individually.**
- **The invisible / undo / delay family (InvisiSpec, delay-on-miss, CleanupSpec, SafeBet, speculative-data-oblivious) shares the SecureBOOM verdict (above), verbatim.**
  These *keep* full speculation and add machinery to *hide* its traces (a speculative buffer redone at commit), *undo* them (cache rollback on squash), or *delay/scramble* the transmitter: so they are the opposite of "simple and deterministic" (strictly *more* complex than a plain out-of-order core), carry real measured overhead (InvisiSpec is ≈5–30% depending on threat model, not "normal out-of-order speed", and the taint schemes realized as actual BOOM microarchitecture cost more still: 22–35% IPC for STT and NDA on the highest-performance core, ShadowBinding, MICRO 2025), repeatedly leak through channels they did not model (port contention, the validation/redo traffic, the TLB), and, like SecureBOOM, close only the transient-leak blocker while leaving the WCET, hidden-state-flush, classical-channel, and RTL ⊑ Sail costs untouched.
  Logged in the SecureBOOM slot: bounded bring-up evidence for a mechanism the profile does not contain, never an import.
- **Decoupled access-execute (DAE) imports nothing the vector unit is not already.**
  DAE is a real latency-hiding structure but *not* a speculation defense and *not* inherently deterministic (a decoupled machine can still speculate); its dividend, running an access stream ahead to prefetch, is again the memory-latency hiding flat SRAM deletes, and where a datapath does want it, the **decoupled RVV vector unit is already a decoupled access-execute engine** (vector address generation running ahead of the arithmetic, §15).
  Nothing to import.
- **The "deterministic time-based CPU" is vendor marketing whose atom is banked.**
  The pitch is a scoreboard-with-a-time-counter doing *static* issue scheduling: unproven in application-class silicon, and the one funded attempt has failed on exactly that bar (Condor Computing's 8-wide time-scheduled Cuzco, presented at Hot Chips 2025, underperformed its spec, and the company was dissolved in early 2026 with the IP returned to Andes and no test silicon); its one real idea, moving the schedule to compile time where it is reproducible, is already the EPIC entry's distilled atom (**wider in-order superscalar + verified static scheduling on plain RV64**, above).
  "Edge-chasing / ghost-loop" dynamic loop optimization is a dynamic predictor with state (admission test 3); the static-loop case is already the profile's static prediction (§15).

**The distilled atom: already banked, three times over.**
The admissible ways to recover the in-order IPC tax *without* speculation are already logged and all live on plain RV64+CHERI with no dynamic-scheduling engine: **NaR / deferred-fault poison loads** (the belt and EPIC entries: speculative *scheduling* with no rollback and no transient class), **wider in-order superscalar + verified static scheduling** (the EPIC entry: the compiler packs the independent operations an in-order core issues), and **static-slot fine-grained (barrel) multithreading** (the FGMT entry below: fill a stalled thread's shadow with another partition's work, the pipeline-level TDM NoC).
These recover the same memory- and functional-unit-latency shadow NS-OoO chases, deterministically and at no new trust base beyond a per-thread-state Sail addition; NS-OoO adds a large data-dependent mechanism to buy a slice of that shadow the cacheless memory has already mostly filled.

**Where it ranks.**
Off the abandon-substrate scale entirely (NS-OoO and its cousins are microarchitecture options on RV64+CHERI, not ISA forks), it is the mirror image of the SecureBOOM entry: SecureBOOM keeps the speculation and fences the leak; NS-OoO keeps the out-of-order engine and deletes the speculation.
Both are dominated here for the same reason, spending scarce proof (a broken WCET model, a larger flush set, a state-space explosion on the least-built arrow) to buy an IPC the flat-SRAM, in-order profile has largely captured for free, and both sit strictly beneath the three non-speculative levers (NaR, static scheduling, barrel MT) that need no dynamic scheduler at all.

**Disposition:** rejected as a base direction; no import.
The proposal's one correct insight, that out-of-order execution is separable from speculation so a non-speculative out-of-order core is genuinely Spectre- and Meltdown-immune, is granted and is moot here twice over: the security win is redundant against a profile that already deleted speculation, and the performance win is largely redundant against a memory subsystem that already deleted the latency wall out-of-order exists to hide (§15), while the dynamic scheduler's data-dependent issue timing (admission test 2), its new partition-switch-surviving state (test 3), its collapse of the tree-sum WCET (§11), and its inflation of the least-built RTL ⊑ Sail arrow (§17, §18) all land on the scarce axis.
The invisible/undo/delay family is logged with SecureBOOM as bounded bring-up evidence that enters no trust base; DAE and the "deterministic time-based CPU" import nothing the decoupled vector unit and the already-banked static-scheduling atom do not.
The platform axiom decides it as ever (*trust is the scarce resource, engineering is free, delete rather than defend, performance is subordinated*): the admissible non-speculative levers recover the IPC without the engine.
Non-normative; the only spec-body touch is the §15 microarchitecture cross-reference to this entry.

---

## SEAM-V decoupled vector backend: rejected

SEAM-V decouples an RVV backend from its scalar core, feeds it from a backend-local execute-packet store, adds backend-visible context and request-bound prefetch, and resolves dependencies across packets dynamically.
The measured short-vector supply gain is real, but each mechanism lands on an excluded axis.
Task-level decoupling makes completion depend on queue occupancy and issue skew, breaking the tree-sum WCET; backend-local instruction supply is a second instruction-fetching computer and fails the no-foreign-computers rule; request-bound prefetch adds history-indexed hidden state; and cross-packet hazard management is a dynamic scoreboard with state-dependent latency.
The asynchronous backend also enlarges the least-built RTL-to-Sail refinement for throughput alone.

**Disposition:** reject SEAM-V task-level decoupling, backend-local instruction supply, request-bound prefetch, and dynamic cross-packet dependency tracking.
The static packet-packing lesson and Ara baseline are documented in [Inspirations & Prior Art](inspirations.md).
Non-normative; no spec-body change.

---

## Minimal-ISA extremes: OISC and transport-triggered architectures; parsimony past the point the substrate and the proof survive

The proposal pushes the profile's own parsimony instinct (deleting the C extension for unambiguous decode, curating `A` to `Zaamo`, folding scalar float onto the vector unit, §15) to its absolute limit: a **one-instruction-set computer** (OISC, a single instruction such as *subtract-and-branch-if-≤0*, from which all computation is synthesized) or a **transport-triggered architecture** (TTA / the MOVE machine: the only operation is a register-to-functional-unit-port move, and arithmetic is a *side effect* of moving operands to a unit's input ports).
The pitch is a decode surface and a formal model small enough to hold on a page: the smallest thing a Sail model and an RTL ⊑ Sail proof could describe.

**The steelman: one real card.**
A minimal ISA is a minimal Sail model, a minimal decoder, and the least surface for the least-built arrow (RTL ⊑ Sail, §18) to refine: exactly the scarce axis the platform spends engineering to shrink, and the same argument that deleted the C extension.

**Why it fails: the EPIC disqualifier, plus an inverted proof-shrink.**
- **It abandons RISC-V for a dead ecosystem: the EPIC/Wasm cost verbatim.**
  OISC and TTA are not RV64 extensions, so they pay the **substrate-cost disqualifier** in full (the Itanium/EPIC entry above), into an ecosystem with no CHERI, no verified compiler, and no RVV to inherit.
- **TTA re-couples the binary to the microarchitecture.**
  A transport-triggered schedule encodes the *specific* functional-unit ports and latencies it was compiled against, so a pipeline change forces a recompile: the VLIW binary-portability curse (the EPIC entry's second count), violating §15's *"one base ISA, one parameterized model; classes differ only in datapath"* property.
- **Minimal *instruction count* is not minimal *proof surface*: the shrink inverts.**
  An OISC moves complexity out of the decoder and into gigantic synthesized instruction *counts* and control flow; once capabilities, DMA, interrupts, and the timing contract are expressed, the Sail model is not smaller; and the verified compiler must now target a pathological ISA (an OISC has no register file to allocate, a TTA exposes the pipeline the compiler must schedule against by hand), *enlarging* the CHERI-CompCert proof rather than shrinking it, the same inversion the EPIC entry found ("VLIW deletes nothing here; it *adds* a mechanism").

**The distilled atom: already banked.**
ISA parsimony as a proof-shrink lever is the whole §15 curation posture: unambiguous 4-byte decode (no C extension), `Zaamo`-only atomics, no scalar FP, `Zifencei` dropped; extracting *real* Sail-model and decode savings **inside** RV64, where the CHERI / CompCert / Cerise substrate is kept.
The minimal-ISA entries add nothing but substrate abandonment on top of a parsimony the design already practices.

**Where it ranks.**
Beside EPIC on the "abandon RISC-V" scale and below the belt and EDGE: more radical in decode-minimalism than any of them, but into a *deader* ecosystem (OISC/TTA never shipped an application platform, let alone a verified one) and *inverting* the proof-shrink it promises, so it clears none of the bars the belt's spiller or EDGE's block-atomic commit clear.
The one point on this axis that *did* ship an application platform is Wirth's **RISC5** (fourteen instructions, sixteen registers, a few hundred lines of Verilog, carrying a compiler, an operating system, and a graphical environment), and it is weighed separately in the Oberon-system entry below, where it loses on the criterion this entry leaves implicit: the instruction set of record is chosen by whose semantics is already mechanized, not by whose instruction count is smaller.

**Disposition:** rejected as a substrate: OISC/TTA abandon RV64 and re-mint every artifact stated against its Sail model (the EPIC disqualifier), TTA re-couples binary to microarchitecture, and neither actually shrinks the proof surface once capabilities, DMA, interrupts, and timing are modeled; the genuine parsimony atom (minimal decode, curated extensions) is already banked **inside** RISC-V (§15).
The platform axiom decides it as ever: parsimony is spent where it shrinks the proof without forfeiting the substrate, not past the point the substrate and the proof survive.
Non-normative; no spec-body change.

---

## Three further ISA amendments: all declined under the frozen-profile gate

The profile freeze is the root of the toolchain, Sail model, CHERI-CompCert backend, TAL, and Cerise schedule, so a further instruction must retire a booked proof or code-size obligation rather than merely add throughput.
The standing gate requires a win on proof surface or resident code size, evidence from this profile's emitted mix, no new architectural or hidden state, custom opcode placement with a Sail clause, and a cost booked as a deletion.
Fusion cannot justify an amendment because the profile makes it combinational, architecturally transparent, and free of new state or admission cases; asynchronous device-interrupt prologues cannot justify one because device delivery is absent.

Three candidates fail:
- **Test-bit-and-branch** saves four bytes on an uncommon pattern whose cycle fusion and static prediction already recover, so it fails the scarce-quantity gate.
- **A bespoke base ISA** abandons the inherited Sail/CHERI/CompCert ecosystem and, critically, the independent Spike/QEMU/tests oracles that catch specification-versus-intent errors, for a small fixed-microarchitecture delta.
- **Bespoke capability semantics** forfeits the Cambridge monotonicity, provenance, and non-forgeability results and turns representation proof into a fresh algebra proof.

**Disposition:** decline all three amendments and keep the instruction class closed.
The adopted fixed-rate fetch format that separately cleared the gate is documented in [Inspirations & Prior Art](inspirations.md); it is not part of this rejected set.
Non-normative; no spec-body change.

---

## `Zcmt` table jumps: reject the JVT mechanism

`Zcmt` attacks repeated call targets with `cm.jt`/`cm.jalt` and a jump-vector table.
The mechanism is declined independently of the purecap `C.LY`/`C.SY` encoding collision: a JVT puts a runtime, address-derived memory read in the branch path; its base CSR adds architectural state and a context-switch and flush rule; and a capability machine needs a new authority rule for the table access.
The design has no reason to retain that runtime machinery when the image is already position-fixed at composition.

**Disposition:** reject `cm.jt`, `cm.jalt`, and the JVT mechanism at R-15-036q.
The composition-time code-density decisions that supersede it are recorded in [Inspirations & Prior Art](inspirations.md).
Non-normative; no spec-body change is made here.

---

## Self-timed datapath logic: rejected at the timing axiom

Delay-insensitive or bundled-data asynchronous logic offers average-case completion, lower clock-distribution power, and reduced clock-spectrum emission.
Its defining benefit is also the disqualifier: completion time depends on operands, as with an early-resolving carry chain or comparison, so it creates the data-dependent latency the constant-time contract forbids.
A clockless datapath has no fixed per-operation latency for the per-class/OPP tables, replacing the §11 timing model with a harder worst-case circuit-delay proof while providing average-case speed a non-work-conserving worst-case schedule cannot use.

**Disposition:** reject self-timed execution logic in the datapath under admission test 2 and the fixed-latency WCET requirement.
The system-level GALS clocking discipline that avoids this defect is documented in [Inspirations & Prior Art](inspirations.md).
Non-normative; no spec-body change.

---

## Static-slot fine-grained multithreading: the non-speculative throughput candidate the SMT rejection over-rejected

The profile deletes **simultaneous multithreading** (SMT) uniformly (§15) on admission-test-3 grounds: SMT threads share issue ports and functional units *dynamically*, so one thread's occupancy is hidden shared state surviving a partition switch that makes the other's timing data-dependent: the co-residency channel.
That rejection is correct, but it kills only *simultaneous* (dynamic-issue) multithreading, and it has been read too broadly.
**Fine-grained (barrel / temporal) multithreading** is a structurally different mechanism: N hardware threads with **replicated per-thread register files**, interleaved onto one pipeline by a **fixed, statically-scheduled round-robin**: thread *t* owns issue slot *t mod N* unconditionally, whether or not it has work.
This is the lineage of the CDC 6600 peripheral barrel, the Denelcor HEP and Tera MTA (Burton Smith), and (shipping, sold on determinism) **XMOS xCORE** (guaranteed-MIPS logical cores for hard-real-time I/O; its fourth generation re-skins the same architecture with a RISC-V ISA while keeping the cycle determinism, so the shipping instance of the lever is itself converging on this substrate).
It is separable from SMT exactly as EPIC's NaR was separable from the bundle, and the separated form clears the admission test the dynamic one fails.

**The steelman: it is the non-speculative throughput lever the belt entry went looking for.**
Interleaving hides load-use, functional-unit, and branch-resolution latency by filling the shadow of a stalled thread with *another partition's* independent work: recovering much of the in-order IPC tax **with no speculation, no dynamic prediction, and no rollback**: the "ILP without speculation" the belt chases through exposed scheduling and NaR, here obtained by temporal interleaving instead.

**Why the static-slot form passes where SMT fails.**
Run barrel MT through the five-part §15 admission test in its *fixed-schedule* form: (1) deterministic: a thread's timeline is a function of its own instruction stream and its fixed slot allotment, nothing else; (2) no data-dependent latency: the schedule being fixed, thread A's stalls **cannot** shift thread B's issue cycles (the inter-thread interference SMT reintroduces is exactly what a static round-robin removes, providing *stronger* temporal isolation than a single fast thread, not weaker); (3) no hidden shared state surviving a partition switch: per-thread register files are architectural and replicated, the slot assignment is a composition-time constant, and threads map to partitions so the interleave *is* the partition boundary; (4) Sail-expressible: thread ID and slot table are architectural state; (5) no autonomous behavior: the round-robin is a fixed counter, not an address-dependent engine.
It is the **pipeline-level analog of the TDM NoC and memory partitioning** (§15): time-division of one datapath among fixed tenants, which is precisely why T-CREST pairs barrel-predictable cores with a TDM NoC.
The **dynamic** variant (fill an idle slot with any ready thread, FlexPRET's *soft* threads, SMT's issue logic) reintroduces the data-dependent contention and stays rejected; only the fixed-slot form is under consideration.

**Where it ranks: the cheapest throughput lever, and it stays in RISC-V.**
It **abandons no substrate** (FlexPRET is RV32; a barrel front end is an RV64+CHERI datapath option, not a new ISA), so it is off the belt/EPIC/OISC "abandon RISC-V for ILP" scale entirely, and it ranks **above** all of them as the *first* non-speculative throughput lever to reach for: it joins the two stay-in-RISC-V atoms the EPIC entry distilled: NaR poison loads and wider in-order superscalar + verified static scheduling; as a **third**, and the most directly latency-hiding of the set, at zero substrate cost and no new proof base beyond a per-thread-state Sail addition.
Its natural home would be the scalar in-order cores that actually pay the IPC tax (the V/M datapaths already hide latency through vector length and the systolic array), while sub-slot radio turnaround remains fixed-function (§12, §15).

**Disposition (non-normative; gen-2 throughput candidate + prior-art grounding).**
**Static-slot fine-grained (barrel) multithreading is admissible**: it passes the five-part admission test as the pipeline-level sibling of the TDM NoC (fixed schedule, replicated per-thread state, no inter-thread timing dependence), and is **logged as the first-choice non-speculative throughput lever should the in-order IPC tax bind**: ahead of the belt and any ISA fork, beside the EPIC entry's NaR and wider-superscalar atoms, on plain RV64+CHERI.
**Dynamic-issue SMT (and FlexPRET-style soft-thread slot-filling) stays rejected** (§15): the data-dependent contention the static schedule removes.
The platform axiom decides it as ever (*engineering is free, performance is subordinated*): a throughput lever that buys back IPC (the free axis) without speculation and without leaving the substrate is a gen-2 candidate, not a base move, unless the vector/matrix-memory-latency-hiding case ever justifies banking it at base.
**Honest residual (§17):** barrel MT is the rare performance entry that *grows* the Sail model rather than shrinking it: per-thread register files, a slot-schedule table, and thread-ID architectural state join the model and the partition-switch/flush accounting; admissible only in the fixed-schedule form and only where a partition carries enough independent threads to fill its slots (else they idle, which the non-work-conserving §11 model already tolerates); it buys throughput, the freely-spent axis, so it is booked as a bounded, deferrable extrapolation like the belt, not a standing obligation.

---

## CHERI-Wasm as a hardware ISA: reject the execution substrate

The evaluated proposal was to make Wasm bytecode the hardware ISA, use CHERI as the module-linear-memory sandbox, or make Wasm the system deployment format.
Wasm has a strong Coq formalization and a capability-shaped linear memory, but neither closes this platform's actual obligations: it gives no intra-module temporal safety or CFI, its sandbox is coarser than byte-granular purecap CHERI, and its type-soundness theorem is not the binary functional-refinement, constant-time, and WCET story the platform requires.

As an ISA it also pays the full substrate cost: a variable-length, LEB128, structured stack machine forks the RISC-V Sail model, CHERI, the compiler backend, Cerise, Islaris, and every binary-level certificate.
A JIT adds hidden translation state and violates W^X; interpretation retains the decode/validation surface at unacceptable cost; Wasm threads bring a relaxed memory model into a Ztso design.

**Disposition:** reject Wasm as hardware ISA, CHERI sandbox target, and system execution substrate.
A contained application may still embed a private interpreter, which is ordinary software rather than an architectural import; the platform now makes that the declining case, offering one verified interpreter (R-14-013a) whose adoption takes Wasm's mechanized semantics as a *guest language* while every ground above still refuses it as substrate, so the rejection and the offer are the same judgment read at two layers.
The interface lineage actually used by the platform is documented in [Inspirations & Prior Art](inspirations.md).
Non-normative; no spec-body change.

---

## The guest-language slot: verified JavaScript, CakeML, and K-generated interpreters, declined for the one pinned Wasm guest semantics

The R-14-013a platform interpreter needed a guest language whose mechanized semantics and theorems could be curated rather than authored, and the candidates other than core Wasm fail that test in four different ways.

A **verified JavaScript engine** fails on scale: the standing mechanizations cover the core of one superseded edition without libraries, garbage collection, or realistic performance, the language's specification runs to hundreds of pages and grows yearly, its regex chapter alone sustained a dedicated multi-year mechanization effort, and its dynamism (effectful property access, proxies, `eval`, the last banned here anyway) resists exactly the small-step pinning the theorems need.
Even under this project's effort premise the artifact is a research program, not a curation, so web JavaScript stays contained per origin (R-14-008) and the declination is normative at R-14-013c.

**CakeML** is the one verified managed-language runtime with an RV64 backend and machine-code theorems, and is declined on three mismatches: its proofs live in a different prover, so its theorems could be consumed only as axioms against the one-prover discipline; its REPL and `Eval` path is runtime code generation the platform forbids, leaving only the install-time AOT half; and its surface language is one applications do not embed for untrusted content, so it would fill the slot without serving the slot's purpose.

**K-framework-generated interpreters** buy real-language coverage from one semantics, but the generating toolchain is unverified and its proof-object emission program incomplete, so adopting one is trusting a large translator, the shape the certifying-toolchain discipline (§13) exists to refuse: the checker must be small and the pedigree untrusted.

**MSWasm as the admitted guest dialect** was declined even though its handles are CHERI-shaped and its security invariants are mechanized: admitting it would put a second capability vocabulary beside the architectural one inside the guest boundary, for safety the embedding's CHERI-bounded memory plan already enforces from outside.
It is retained as design vocabulary where guest handles lower onto real capabilities.

**Verified install-time AOT of guest content** fails at the definition: guest content is dynamic and has no install point (R-14-008f), so the AOT route exists only for content shipped through §13 admission, where it is the ordinary native path rather than a Wasm story.

**Disposition:** the guest language is core Wasm under the R-14-013b pinned semantics, no threads, curated from the WasmCert lineage with SpecTec as tracked upstream; the four candidates above are declined on the grounds stated, and the JS declination is the one carried normatively (R-14-013c) because it bounds what the offer can ever claim to reach.
Non-normative; the normative change is §14's.

---

## ELF as the on-device executable and package format: declined

ELF was evaluated as the artifact the device would parse and load.
Most of its machinery serves facilities the platform excludes: dynamic linking and `ld.so`, PLT/GOT lazy binding, writable-to-executable promotion, runtime symbol resolution, and section tables for an on-device linker or debugger.
Even a narrow ELF profile leaves an attacker-facing, offset-linked grammar of program, section, string, relocation, and dynamic tables that would have to enter the verified decoder and loader TCB.
Purecap capability relocations make the mismatch sharper: they want an explicit authority-wiring relation, not legacy relocation records bolted onto a format designed for integer addresses.

Slim binaries such as Juice were also considered and rejected because a syntax-tree artifact requires an on-device code generator, runtime executable creation, and a compiler inside the device TCB.

**Disposition:** stock or profiled ELF is declined as an on-device admitted artifact and retained only as off-device build interchange; Juice-style mobile code is likewise declined.
The adopted image lineage is documented in [Inspirations & Prior Art](inspirations.md).
Non-normative; no spec-body change is made here.

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
  Hardware-tagged Lisp cells, Java typed references, and 432 object descriptors are all *tagged metadata checked in the datapath*: the SAFE/micro-policies genus the tagged-architecture entry (below) dispositions: CHERI **is** a fixed-policy tagged architecture, byte-granular and universal, strictly exceeding any HLLCA's per-object typing; and the one further tag policy the platform wanted (Write-before-Read) it declined to build as a second plane, taking it as a type attribute instead (the Mon CHÉRI entry below, §5/§15).
  Card (a) of the steelman is the concession, not the case for import: the design already took the one HLLCA atom that survives.
- **The language-ISA claim (1) is the Wasm/EPIC substrate-cost disqualifier, verbatim.**
  A Lisp/bytecode/graph-reduction ISA is a *distinct instruction set*, not an RV64+CHERI extension, so it pays the **substrate-cost disqualifier** in full (the Itanium/EPIC entry above); and the one-language execution target is the cross-ISA portability the **Goals declare a non-goal** (§2).
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

## Language-based isolation as the sole mechanism, and in-place live evolution: rejected

Singularity, Verve, Tock, Midori, and Theseus motivate deleting hardware protection and relying on a type-safe language plus a trusted compiler/runtime.
As a sole isolation mechanism this leaves one unsafe block, miscompilation, or unverified binary with unrestricted access to the shared address space, precisely the arbitrary-code case the hardware universal contract must bound.
The Singularity/Verve form also relies on a trusted runtime and, in Singularity's case, a garbage collector the platform excludes; Verve's Boogie/Z3 proof would widen the one-prover trust base.

Theseus-style in-place live evolution is separately declined because runtime replacement mutates executable code outside static composition, measured boot, and W^X.
It would create a fine-grained update and authority path where the design admits only measured, signed A/B generations.

**Disposition:** reject language safety as the sole isolation mechanism, the trusted runtime/GC that carries it, and runtime live evolution.
The source-safety, TAL, error-model, and state-spill lineage retained from these systems is documented in [Inspirations & Prior Art](inspirations.md).
Non-normative; no spec-body change.

---

## Oberon system mechanisms not imported: executable text, GC, dynamic linking, `AWAIT`, Juice, and RISC5

Six Oberon-family runtime and substrate mechanisms were evaluated and declined:
- **Executable text** resolves a global `Module.Command` name and lets the target parse surrounding text under ambient system authority, recreating name-resolution, text-to-action, injection, and confused-deputy classes.
- **The mark-and-sweep collector** adds a managed runtime and pause behavior incompatible with the fixed WCET model.
- **Load-time module linking and unloading** add on-device name resolution and executable mutation after the component and capability graph should already be fixed.
- **Active Oberon `AWAIT` and condition monitors** re-evaluate waiting predicates at monitor exit, a data-dependent runtime scheduler over a preemptive-priority model the cyclic executive excludes.
- **Juice slim binaries** require an on-device code generator, writable-to-executable promotion, and a compiler in the device TCB.
- **RISC5 and Lola-2** lack the RV64, CHERI, vector, atomics, compiler, and mechanized-semantics substrate; a small informal RTL is more proof work here than a larger existing formal model.

**Disposition:** import none of these six mechanisms.
The Oberon method, module-key lesson, quiescent-point rule, and Active Cells/Oberon-V lineage retained by the design are documented in [Inspirations & Prior Art](inspirations.md).
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
  DIFC labels track explicit and storage flows; the covert **timing** channels are closed here by construction (in-order, non-speculative, no caches, partitioned memory and NoC, §15) and by the constant-time layer (§5), not by labels: so a DIFC OS would still owe the timing-channel story the profile already discharges.
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
Each component maps onto a strictly stronger mechanism already mandated here: PMP zones → **CHERI + capability-checked DMA + islands** (byte-granular, unforgeable, formally modeled vs. a handful of coarse power-of-two regions); nanokernel → the **seL4-design capability microkernel** (re-proved in Coq, §5) with a completed refinement + non-interference proof (MultiZone advertises "formally verifiable," not a finished machine-checked proof); messenger → the **verified ring data plane** under Ztso; configurator → **static composition + signed generation + proof-checked admission**.
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
"More robust" is genuinely two-sided: PMP is more mature *today*, but the gap is closing from the other side (the first commercial CHERI silicon shipped in 2026: SCI Semiconductor's CHERIoT-Ibex ICENI parts, with Codasip's X730 CHERI-RISC-V core certified alongside), and CHERI is the stronger, more *uniform* guarantee once built (subsuming MMU-split, shadow stacks, and software W^X into one monotone mechanism), covering the same ground with fewer orthogonal parts.

**Disposition:** the M-mode/PMP-only design is **rejected as the base, not a stage the plan passes through**: the platform is purecap from first bring-up (§18) with no capability-degraded instantiation to descend to, and "trust is the scarce resource, engineering is free" resolves the base toward CHERI's smaller, deeper, byte-granular story.
Taking PMP-only as the *goal* would trade the platform's defining property: hardware that bounds arbitrary unverified code; for buildability the spec deliberately declines to optimize.

**PMP is dominated in both roles: and dropped entirely.**
The domination verdict above is specific to PMP as a *primary, fine-grained compartmentalization* mechanism, where CHERI + capability-checked DMA + islands strictly exceed it.
A tempting alternative *banks* PMP in a *secondary, coarse, sub-kernel backstop* role (immutable-text/W^X, per-core partition bound, crown-jewel secret fencing) on the ground that, being CHERI-disjoint, it would hedge a CHERI *logic* fault no in-band mechanism otherwise could.
**That backstop is dropped too**, and the drop-PMP entry below is where that is argued: with CHERI formally verified and application-class silicon already removing PMP on exactly this ground, the disjoint hedge is judged redundant Sail surface, and all three roles collapse onto mechanisms the design already carries.
So the full disposition is unqualified: nothing of MultiZone's *architecture* imports, the base does not descend to it, and PMP is not retained even as a backstop: CHERI is the sole in-band spatial mechanism, hedged by its own verification rather than by a coarse subset of itself.

---

## Historical capability-machine runtime machinery: banks, meters, keepers, and whole-machine persistence declined

The historical capability machines supply important lineage, but their distinct runtime mechanisms were evaluated separately from that ancestry.
KeyKOS space banks and meters dynamically delegate memory and CPU budgets; keepers receive control on a domain fault or budget exhaustion.
On this platform those objects would duplicate the static memory plan, cyclic schedule, and crash-only supervision tree while adding runtime state and authority paths.
An arbitrary keeper able to inspect, modify, or resume another compartment would reopen debugger, exception, and continuation authority the static design excludes.

Orthogonal persistence and the single-level store were also declined in their whole-machine form.
Restoring registers, stacks, in-flight calls, and a saved capability graph conflicts with measured boot, eager-zeroized fresh memory, crash-only reinitialization, and static composition; storage would become a second origin of authority able to resurrect a capability after revocation.
The capability-system lineage itself and the typed-data persistence property taken from it are documented in [Inspirations & Prior Art](inspirations.md).

**Disposition:** import no runtime bank, meter, keeper, process-resume, or capability-graph checkpoint machinery.
Non-normative; no spec-body change is made here.

---

## Object Memory Architecture: object-granular naming against byte-granular capabilities; the elegant synthesis is already the design, the deeper one is the MMU it deleted

Where the Historical capability machines entry (above) took the object *machines* as ancestry, this entry takes their shared *memory model*, idealized to its most elegant form, as an axis in its own right: an **Object Memory Architecture** (OMA) in which memory is not a flat array of bytes but a graph of **objects**, each with an unforgeable **object identifier (OID)**, an implicit boundary, an optional type, and object-granular access rights, so that a reference is an **(OID, offset)** pair naming an *identity* rather than a *location*.
The lineage: Intel's **iAPX 432** (access descriptors indexing an object table to reach an object segment); IBM's **System/38 → AS/400** (a single-level store whose 128-bit pointers carry a hardware **tag bit** ordinary stores cannot forge, the object model living behind the Machine Interface); **MONADS** (Rosenberg/Keedy: a persistent object store in one enormous address space, password capabilities); the **Rekursiv**; and the modern non-volatile-memory instance **Twizzler** (Bittman et al., USENIX ATC '20: 128-bit object IDs and cross-object pointers over persistent memory).
It decomposes, in this document's manner, into five separable claims: (1) **object-granular naming** (reference = (OID, offset)); (2) **identity-based temporal safety** (a dangling reference is a reference to a retired OID); (3) **hardware object typing**; (4) **single-level store / orthogonal persistence** (memory and storage unified, no serialize/load boundary); (5) **location independence** (objects relocate, compact, swap, or persist behind the OID indirection).

**The steelman: the most elegant OMA, four real cards.**
(a) **Safety is a consequence of *naming*, not a check bolted onto an address.**
You address *within* an object, running past the end is not expressible because the object is the unit of naming, and the OID is unforgeable, so spatial safety falls out of the reference scheme rather than out of a bounds comparison.
(b) **Temporal safety by *identity*, with no sweep: the strongest card.**
Freeing an object retires its OID, and any surviving reference simply fails its next validity check, so use-after-free is caught without CHERI's revocation *sweep*, the genuinely awkward part of capability temporal safety (Cornucopia-class; that the successor literature keeps attacking exactly this point, PoisonCap's dangling-capability poisoning of 2026 replacing the shadow-bitmap sweep outright, confirms the sweep is the card OMA is playing against).
(c) **One uniform model spanning register, memory, storage, and the authority graph.**
The single-level store deletes the serialize/load boundary and the memory/file distinction, and authority rides the object graph: the "everything is an object" dual of this platform's "everything is a byte plus a capability," a genuine conceptual economy.
(d) **It is spec-sympathetic in spirit.**
A single global space (the design is already single-address-space, §15), a location-independent identity (the design is already content-addressed, §10), and authority on the object graph (the capability graph) are all present here already, and the AS/400 tagged pointer is a spiritual CHERI ancestor, reaching "tag equals unforgeability" from the object side decades early.

**Why the most elegant OMA still does not win: five objections.**
- **The OID → location indirection is the MMU this design deleted, generalized to per-object.**
  A reference (OID, offset) must resolve to a location, and there are only two ways.
  A **hardware object table with a cache** (an object TLB) is a mapping structure with data-dependent hit/miss latency (admission test 2) and hidden state surviving a partition switch (admission test 3): the Sv39 walker / ALAT / PUMP-rule-cache shape the profile deletes, here made *finer than a page table* (per-object, so more entries and worse), and the iAPX 432's access-descriptor-to-object-table indirection is the object-model instance of the microcode-critical-path cost the Historical entry books (above), a central reason the 432 was "ruinous in performance," the exact structure the MMU-deletion rationale in [Inspirations & Prior Art](inspirations.md) rejects.
  Or the location is **inlined** into the reference, so the reference is (location, OID-for-validation): but that is a CHERI capability with an extra OID field, and the validation is a tag (CHERI's tag) or another lookup, so "identity, not address" collapses into "CHERI capability plus an OID that buys only persistence and relocation," which the design declines.
- **CHERI is byte-granular and sub-object; the object model is object-granular, hence coarser.**
  OMA's boundary is the object, so intra-object overflow (one field into the next) is uncaught unless every field becomes its own object, which explodes the table and the indirection; CHERI's `csetbounds` narrows to any byte range, delivering the object boundary *and* sub-object bounds *and* per-element gather/scatter bounds (§8) with no OID table, so on the actual memory-safety axis CHERI strictly exceeds the object model, the same "byte-granular and universal, exceeding X" verdict the Wasm-linear-memory, HiStar-container, and micro-policy entries reach.
- **The temporal card is a real trade, not a win, and this design's low allocation churn already blunts it.**
  That *OMA avoids the sweep* is right, but the sweep is not a hot-path cost: the design's dereference path already carries a deterministic per-capability-load **revocation check** (the load filter, fixed-latency, §8), so OMA's per-access validity check is not a *new* hot-path tax, and the honest difference is on the *free* path, where CHERI pays a budgeted background **sweep plus quarantine** (freed memory reused only after the sweep, the §11 model accounts for it) and OMA pays **generation storage plus a non-aliasing discipline** and reuses immediately.
  That trade is workload-dependent (allocation-churn-heavy favors OMA's no-sweep, pointer-chase-heavy favors CHERI's already-cheap dereference) and it lands on the performance axis the platform spends freely (§2); and decisively, this design's **static composition (§7), GC-free storage (§10), and crash-only explicit state (§16)** minimize allocation churn, so the sweep the OMA scheme targets is already small here (the sweep is awkward in a malloc-heavy C program, not in a low-churn static system), while the generation scheme is not free on the scarce axes either (below).
- **Single-level store, relocation, and GC are already declined or banned.**
  Orthogonal persistence is *already declined* (the Historical capability machines entry, above) for dissolving the crash-only state boundary (§12, §16), the eager-zeroize / Write-before-Read assumption that memory starts empty (§7, §5), and the explicit, provable crash-refinement of the verified storage stack (§10); transparent object *relocation* (compacting GC, swap) is an autonomous memory-touching engine (admission test 5, the ground the Sv39 walker and Itanium's RSE are deleted on, and §10 bans the GC outright), so OMA's two most distinctive advantages, persistence and relocation, land on axes the design deliberately refuses, not on the scarce one.
- **Object-as-ISA is the substrate-cost disqualifier, verbatim.**
  An object-addressed machine is a distinct ISA and memory model, not an RV64+CHERI extension, so it pays the **substrate-cost disqualifier** in full (the Itanium/EPIC entry above, as the Wasm and OISC entries do), spent to buy a naming model whose distinctive features the design declines.

**The synthesis, and why the elegant one is already here.**
The admissible synthesis of object identity ⋈ capability enforcement is *already the design*, reached from the capability side and moved off the runtime path.
Object **identity** is the content-addressed store (§10): objects named by hash, a location-independent unforgeable identity, resolved to a CHERI capability *once, at install and compose time* by the capability-wiring table of the content-addressed capability image (the executable-and-package-format entry above: source object, offset, bounds, permissions), not by a per-dereference hardware table, so the wiring table *is* an object graph materialized into capabilities.
Object **bounds** are CHERI capability bounds (byte-granular, sub-object); object **type** is the CHERI-TAL typing derivation carried to the binary (the HLLCA entry's verdict, above: semantic-gap closure belongs to the verified compiler, not the hardware) plus otype for sealing; object **persistence** is the explicit, verified content-addressed CoW storage stack (§10), not orthogonal; object **access control** is capabilities ⋈ the powerbox (§8).
So the design already *is* an object system: a graph of content-addressed, hash-named, capability-bounded, TAL-typed objects with authority riding the graph, and the one thing separating it from OMA is *where the object graph is resolved*: at composition and storage time, statically, verified, once, lowered to CHERI capabilities, rather than at run time, per dereference, in a hardware object table.
That is the platform's signature move (do it once, statically, verified, then delete the runtime mechanism), the same one it makes deleting the MMU, the dynamic predictor, and the on-device loader; the *deeper* synthesis (an OID indirection in the hardware) is inadmissible for reasons already on the record, being the object-table-with-a-cache the MMU-deletion rationale in [Inspirations & Prior Art](inspirations.md) rejects, generalized per-object, and dragging in the persistence, relocation, and GC the design declines.

**The distilled atom: identity temporal safety, already met or already a tag plane.**
Following the belt→spiller / EPIC→NaR / Mon-CHÉRI→Write-before-Read discipline, the one non-redundant OMA idea is *identity/generation-tagged temporal safety*, and it is either already met or already shaped as a fixed tag plane.
The property (freed ⇒ unreachable) is already the design's, discharged by budgeted revocation and the deterministic load filter (§8) beside CHERI-TAL linear/affine types (§5, §13); the *generation-tag* realization (a version stamped in the capability, compared against the object's current generation on access) is an *implementation option* for that same property, not a new capability, and its admissible form would be a fixed, address-indexed generation-tag plane checked in-line at fixed latency, never the OID *table*: though the Mon CHÉRI entry below now sets the prior test any such plane meets first, which is whether the property can be decided in the type system instead (there, it could; here, temporal safety already is, by the linear/affine discipline plus the load filter, which is why no generation plane is built either).
It is therefore a parameter for the §15 proof-aware design-space exploration (a way to spend the tag-storage budget on determinism-preserving temporal safety) weighed against sweep-based revocation, and note the *probabilistic* memory-tagging cousin (MTE) is already excluded (§15) as a statistic rather than a theorem, so a deterministic full-width generation tag is the admissible form should the sweep ever prove too costly.
On the proof axis the intuition holds but is already spent: identity-based temporal safety *is* simpler to state than global revocation (a local per-access invariant rather than a sweep-completeness-plus-quarantine argument), but the design banked that simplification one level higher as the **CHERI-TAL linear/affine types** (static ownership is compile-time identity tracking, the cheapest proof, discharging most use-after-free at type-check, revocation left only the runtime backstop for the residual), and the hardware-OID generation scheme does not extend it: it *moves* the hard argument (sweep-completeness becomes generation-non-aliasing / ABA-freedom), adds a generation-state clause to the one Iris-over-Sail metatheorem (§13) and its Sail surface, and leaves the already-mechanized revocation lineage (Cornucopia, Cerise) net-new to restate for generations.

**Where it ranks.**
With HLLCA and the Historical capability machines entry (above), off the EDGE ≻ belt ≻ EPIC ILP ranking: not an ILP play but a safety, naming, and persistence play, rejected on *motivation* and substrate cost one level above the performance argument.
Its safety atom is exceeded by CHERI, its identity-temporal atom is banked (or a design-space-exploration tag-plane option), its persistence and relocation atoms are declined or banned, and its uniformity is matched from the capability side, so nothing imports as a machine, exactly as for the capability-machine ancestry it idealizes.

**Disposition:** no import as an architecture: the object memory model's spatial safety is byte-granularly exceeded by CHERI (§1, §8) without the OID indirection; its identity-based temporal safety is already met by budgeted revocation ⋈ the load filter (§8) ⋈ CHERI-TAL linear/affine types (§5, §13) and admissible only as a transparent generation-tag plane, never the hardware object table (which is the MMU this design deleted, below, generalized per-object); and its single-level store, relocation, and GC are the orthogonal persistence the Historical capability machines entry (above) declines and the autonomous relocation / managed runtime the admission test and §10 ban.
The elegant synthesis (object identity ⋈ capability enforcement) is *already the design*: content-addressed objects (§10) resolved to CHERI capabilities at compose and storage time by the wiring table (the content-addressed capability image entry above), TAL-typed (HLLCA, above) and explicitly, verifiably persisted (§10), the object graph resolved statically and once rather than by a runtime hardware table.
The platform axiom decides it as ever: resolve the object model into capabilities ahead of time and delete the runtime indirection, rather than pay a per-dereference object-table tax to buy persistence and relocation the design refuses.
Non-normative; no spec-body change.

---

## Enclave architectures: Sanctum, MI6, Keystone; defending against the speculation and sharing this design already deleted

The proposal is hardware **enclaves**: a privileged security monitor carving isolated, attested execution environments out of a shared machine: MIT's **Sanctum** (SGX-class isolation with a small monitor; Costan/Lebedev/Devadas, USENIX Security '16), **MI6** (enclaves on a *speculative, out-of-order* core; Bourgeat et al., MICRO '19: from the same MIT group as Kôika), and **Keystone** (a RISC-V enclave framework built on **PMP**; EuroSys '20).
The pitch is strong isolation for mutually-distrusting workloads on shared silicon, with a small trusted monitor and remote attestation.

**Why it is already subsumed: the threats it fights are deleted, not defended.**
- **Enclaves exist to claw isolation back from mechanisms this platform removed.**
  MI6's hard problem is isolating enclaves on a *speculative, out-of-order, cache-sharing* core; the platform is **in-order, non-speculative**, with **no caches and partitioned memory and islands** (§15), so the transient-execution and shared-microarchitecture channels enclaves are engineered to close are absent by construction: the same reason the design needs no enclave-grade speculation fences.
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
Tyche (EPFL DCSL; Ghosn, Castes, Kalani, Qian, Kogias, Bugnion; EuroS&P 2026) is a recent security monitor of exactly this small-privileged-monitor shape that composes attestable isolation out of **capabilities**: nested *security domains* (enclaves, sandboxes, CVMs) over two monotonic capability-derivation trees with cascading revocation, a platform-independent **capability engine** (a few thousand lines of Rust with no `unsafe`) above a thin hardware **backend** (x86 EPT, RISC-V PMP), and region-transfer attributes: *clean* (zero-on-revoke), *hash* (measure-on-transfer), *vital* (revoke-the-receiver): the intents of which this platform already carries (eager-zeroize §15, reference-integrity-manifest attestation §9, revocation-driven teardown §8).
It independently reaches this design's own structure: the capability model split from the enforcement substrate, monotonic revocation, a root domain with no special privilege: so it *validates* those choices rather than proposing an alternative to them. Its revocation is CDT-shaped where this design's is epoch- and load-filter-shaped (the object-model entry below), which changes the mechanism carrying monotonic revocation, not the validation.
Its motivation, though, is the **foil**: it exists to *retrofit* composable isolation beneath an **untrusted commodity OS** on legacy hardware (Linux domains, KVM/Gramine/Keystone compatibility), it is **unverified** (a fuzzed monitor, not a proved one), it puts side channels and physical attacks out of scope, and its RISC-V enforcement *is* the **PMP** this design drops (drop-PMP, above).
Its cross-core capability-update protocol (IPI-driven, two-barrier atomic) is a concrete reference, but for a **shared-state** engine coherent across cores: the opposite of the share-nothing island model, so the distributed non-coherent revocation reference is [SemperOS](inspirations.md), not Tyche.

**Where it ranks.**
Off the abandon-substrate scale: a convergent / subsumed entry: the design is an *all-enclave machine* (every compartment is one) *without an enclave mechanism*, because it removed the shared-and-speculative substrate enclaves were invented to partition, and it verifies the monitor enclaves keep small-but-trusted.

**Disposition:** no import: hardware enclaves defend against transient-execution and shared-microarchitecture channels the in-order, non-speculative, cacheless, single-address-space profile deletes (§15), and their coarse PMP realization (Keystone) is the mechanism CHERI exceeds (drop-PMP, above); the attested isolated compartment and the small verified monitor are already the CHERI compartment ⋈ measured root (§9, §12, §14) and the verified kernel ⋈ RoT (§7, §9).
The MI6/Kôika formal-HDL lineage is shared as a *verification* vehicle (§18); the enclave product is not needed.
Non-normative; no spec-body change.

---

## External roaming hardware authenticators: the YubiKey and FIDO2 security-key class, declined for the verified on-die authenticator

The proposal moves the second authentication factor onto an **external roaming hardware security key**: a FIDO2/CTAP device of the YubiKey 5C Bio class, plugged into the USB-C port, holding origin-bound credentials and gating them with its own on-key fingerprint sensor.

**The steelman is real.**
A roaming key is phishing-resistant by construction (WebAuthn origin binding), hardware-binds its private keys, adds a genuine *possession* factor, gates with an on-key biometric, and rides an open, widely-audited standard.
It is the best commodity answer to credential theft, and a natural thing to reach for.

**Why it is declined, on this platform's own axioms.**
A security key is a **foreign computer** (§4): its own microcontroller running unverified vendor firmware, the category this design admits only for the zero-authority eUICC.
Admitting it as an authenticator puts an unverified device *in the authentication path*, and requires the USB stack to speak CTAP/CTAPHID (attacker-facing wire, one more Narcissus grammar, §5) to a device a malicious lookalike can impersonate (the BadUSB shape); the device-authentication floor and capability containment (§12) bound that surface but do not make it free, and it is spent on a function the platform already discharges.
The function is **already on-die and verified**: the RoT, the crypto core, and the credential and unlock service together are a hardware-bound, phishing-resistant, post-quantum (ML-DSA) authenticator whose private keys never leave the crypto core (§5, §9, §12), with an on-device biometric gate (the under-display fingerprint sensor, §15) and attestation over the sealing service.
The post-quantum choice is now also the declined ecosystem's own: CTAP 2.3 (February 2026) lists ML-DSA among the FIDO-recommended algorithms, so the on-die authenticator speaks the credential algebra the roaming-key standard itself is converging on, ahead of any shipping key.
This is the **TPM disposition one layer up** (the function is kept, on-die and verified; the standardized external device that also provides it is declined as a foreign trust base), and the drop-PMP maxim in miniature: *verify rather than hedge*, one authenticator, no unverified second root.

**The distilled atom is already banked.**
The useful capability (a hardware-bound, phishing-resistant credential and a possession factor) is the on-die **platform authenticator**: the WebAuthn platform-authenticator role realized over the sealing and attestation service (§12), so passkeys and origin-bound credentials are provided with no external device at all.
What is declined is specifically the *roaming* (external, cross-device) key, not the authenticator function.

**Honest cost.**
Declining roaming keys forgoes the one thing the platform authenticator cannot offer: **portability across foreign devices and ecosystems** (a user cannot bring an existing YubiKey, and a credential minted here does not roam to a machine that is not this platform), the same class of interop trade as the no-Linux and no-tunneling decisions.
The choice is the **most-secure** reading (zero external-authenticator support keeps the authentication attack surface minimal and the trust base purely on-die and verified), taken deliberately over the convenience of an existing key ecosystem.

**Disposition:** no import: external roaming hardware authenticators are declined; the verified on-die path is the sole authentication root (the §12 credential and unlock service names it the platform authenticator).

---

## DIVA and general hardware lockstep/TMR: rejected or deployment-deferred

**DIVA** keeps a fast complex core and validates its architectural results with a small checker at commit.
It was rejected because it checks what the core computed, not what its speculative, out-of-order microarchitecture leaked through predictors, caches, contention, and timing.
The platform instead verifies one simple non-speculative core for all inputs; a per-execution functional checker would retain the channel class the profile is designed to delete.

General dual-core lockstep and TMR address random-fault reliability rather than the security threat.
ECC already protects stored state, CHERI checks fail-stop corrupted capabilities, and the multikernel contains failures; the remaining transient datapath result and permanent-aging cases are deployment concerns.
Duplicating every core would grow logic and, for masking, require an explicit voter and fault-model proof.
Software instruction/task redundancy, ABFT, periodic SBST, and hardware DCLS/TMR remain graded G5 options where a safety case pays for detection, a tight FTTI, or availability through a fault.

**Disposition:** reject DIVA as a core-correctness strategy and do not carry general lockstep/TMR by default.
The one normative detector exception and its prior art are documented under COSMIC in [Inspirations & Prior Art](inspirations.md).

---

## Rejected profile simplifications: retained surface whose deletion fails the pure-win gate

These proposals are recorded here so they are not re-proposed as cost-free simplifications.
A deletion qualifies as a pure simplification only if it clears all five gates:

1. **Deletes specification or proof surface** measurably: Sail semantics, a proof obligation, a state-inventory entry, a `fence.t` flush-set member, or a hedge.
2. **Costs nothing in performance, or gains.** A deletion that trades cycles for surface is an accepted performance cost, not a pure simplification.
3. **Sheds no security property.** Every claimed theorem remains unchanged.
4. **Follows the profile's own grounds:** *delete rather than defend* (R-15-012), *verify rather than hedge* (R-15-013), or the no-consumer parsimony that cut `Zacas` (R-15-026) and `Zifencei` (R-15-047).
5. **Reduces, never relocates.** A cost that reappears as a software obligation, checker, or assumption has moved rather than disappeared.

| Proposal | Fails | Why |
|---|---|---|
| **Freeze `vtype` by dropping fractional LMUL and fixing tail/mask policy** | 2, 5 | Fractional LMUL is not merely compile-time convenience: mixed-width ML, DSP, crypto, and codec chains use it to keep widening results in smaller register groups. Removing it can increase live-register pressure, add moves or spills, and therefore cost hot-loop cycles. Fixing an agnostic policy can likewise require explicit preservation where undisturbed elements are needed; fixing an undisturbed policy can require preservation work where agnostic results suffice. Moving those costs into generated code relocates rather than deletes them. Enumerating configurations after measuring kernels may still be useful profile hygiene, but until the measured set proves no generated-code delta, restricting the set is not a pure win. |
| **Sequential consistency** *with the store buffer retained* (at any core count or width) | 2, 4 | Grounds (1)–(4) of R-15-018, whose invariance clause states the absence of any hart-count or issue-width term: single-copy memory (R-15-087) keeps the deviation from SC local to each hart's store buffer, so nothing scales with harts. Ground (3) is decisive and invariant: it trades a *structural* obligation (a FIFO cannot expose ordering weaker than TSO, bookable in the absence contract) for an *interlock-correctness* obligation (no load bypasses the drain, on any path, proven present and complete), which runs *delete rather than defend* backwards. Wider cores make it worse, not better. **Scope note:** every one of the four grounds presupposes the buffer is *kept* and loads are stalled behind it; ground (3)'s interlock has no referent when there is no queue to drain. SC reached by *deleting* the buffer is a different proposal and is treated in the entry immediately below, where it is likewise not adopted, but on an open measurement rather than on these grounds. |
| **Delete hardware integer DIV/REM**, do it in software | 2 | [performance-estimates.md](performance-estimates.md) already books −1% to −6% for the always-worst-case fixed-latency divider (R-15-080). Shift-subtract or Newton–Raphson in software is several times that latency; the deletion buys one datapath unit and one timing-contract row for a real cycle loss. |
| **Delete vector masking** | 2 | Tempting because R-15-085 mandates mask-*independent* timing, so masking buys no cycles, but if-converted vector code then needs explicit merges, which need masks to generate. The surface returns as instructions and the cycles go negative. |
| **Collapse the three VLENs to one** | 2 | VLEN is where the vector performance argument lives (R-15-113, R-15-115). Real surface win, real performance loss; this belongs in the multi-objective DSE trade the spec already specifies (§15, [implementation-plan.md](implementation-plan.md) §1), not in the pure-simplification set. |
| **Delete indexed gather/scatter and segment load/store** | 2 | Large surface with per-element capability checks (R-15-115), but segment load/store is the AoS-to-SoA path the radio and codec kernels on the V-class need most. Deleting it moves the cost into every kernel's inner loop. |
| **A hardware store-buffer bypass predictor**, or any dynamic ordering optimization | 3, 4 | Hidden state that survives a partition switch fails admission test 3 outright (R-15-011). The recovery gate below rejects the whole class. |

**Disposition:** rejected as pure simplifications. Each deletion either costs performance, relocates its surface into software, sheds a security property, or contradicts the profile's established deletion grounds. Non-normative; no spec-body change.

---

## Delete the store buffer: sequential consistency by absence, distinguished from the buffer-retained SC the table above rejects

The proposal is to remove the **store buffer** itself: the queue, its addressable entries, and the different-address load-bypass network, leaving stores in flight as **in-order pipeline stages** with no bypass. The machine is then sequentially consistent because no structure exists by which a load could pass a pending store, not because an interlock stalls one.

**It is a different proposal from R-15-018's, and the difference is the whole argument.** R-15-018 evaluates SC *on a machine that keeps the buffer*: ground (1) prices a load waiting until every prior store is globally visible, ground (2) names "an unconditional stall of every load behind the store buffer" as the only admissible realization, and ground (3), the decisive one, rejects the **drain-before-load interlock** that realization needs. All three are properties of the bypass network's presence. Delete the network and there is no drain, no interlock, and nothing for a load to wait behind: the load is already behind the store in one ordered request path. Ground (4) survives intact and is conceded below.

**The property is binary in the bypass, not graduated in the depth.** What makes this machine TSO is not that writes are in flight; it is that a load may pass a pending store *to a different address*. A depth-1 buffer that permits that still costs the entire prize: the Ztso model (R-15-004), `fence`'s `drain | nop` semantics (R-15-017), flush-set membership (R-15-213), the R-15-016 bring-up gate, and the whole of R-15-015b. There is no partial credit and no depth at which the surface is partly recovered, so the proposal is never *shrink the queue*.

**In the four-class state map the structure is reclassified, not vaporized.** Writes in flight remain; what goes is the queue's addressability and its different-address forwarding path. The residue is FIFO pipeline latching whose contents are a function of the issued stream and not of prior execution history, which is class 4 (**stream-determined pipeline state**, emptied by the fence's pipeline drain) rather than class 3 (**`fence.t`-flushed**), and which passes the same table-freeness rule (R-15-104) the static-path fetch buffer passes. The `fence.t`-flushed class then has **no members at all**, and R-15-106's completeness classification, the one obligation the refinement provably cannot discharge, becomes vacuous rather than merely small. This is R-15-105 (*deletion preferred to partitioning, even where partitioning would suffice*) applied to the last piece of microarchitectural state on the machine that never received it.

**Same-address forwarding is retained and is SC-legal.** Positional comparators against fixed pipeline stages are the shape of ordinary ALU register forwarding: stream-determined, historyless, table-free. A load taking the value of the immediately preceding program-order store is what SC *requires*; the relaxation TSO adds is the *different-address* case, and that is exactly what is deleted.

**What it deletes (gate 1).** The Ztso architectural model and its Sail surface; `fence`'s two semantics, which collapse to `nop` in every legal encoding with reserved `fm` still trapping under R-15-014; R-15-015's per-core discharge; R-15-015b entirely, with the device-store exclusion, the drain-first rule, and their case analysis; R-15-088; the R-15-016 bring-up gate; the sole member of the `fence.t` flush set and with it R-15-106's residual scope; and the restatement of every §12 ring proof under a relaxed model. **What it does not delete** is R-15-015a's fabric obligation, which is untouched, already mandated, always the harder half, and which afterwards *is* the memory-model obligation in full.

**Where the cycles actually go: three sources, one of them real.**

| Source | Disposition |
|---|---|
| Store **completion** latency | Not incurred. SC constrains order, not visibility-before-issue. One in-order request path per hart, single-copy locations making the bank arbiter the order point (R-15-087), and R-15-015a's per-hart order preservation together complete stores and loads in program order with writes still pipelined. This is the premise ground (1) prices and this proposal does not hold. |
| Store **issue** latency | **The only real cost.** With no queue the core stalls at the memory stage while a store waits for its TDM slot or its bank arbiter. This is the whole of what the buffer was buying. |
| Device-store **accept** | Unchanged. R-15-015b already drains, then accepts before retire, so a device store stalls the core today. Behaviour after deletion is identical, while the exclusion rule and its case analysis go, and the endpoint's latency lands in the issuing compartment's WCET *structurally* rather than by exception, which R-15-015b already names as the gain it wants. |

**The issue-latency cost is bought at composition, not at runtime.** Let **ρ** be the guaranteed per-hart memory-issue opportunities per cycle divided by that hart's static peak memory-op issue rate. At **ρ ≥ 1** a store never waits and the deletion costs zero cycles. The enabling fact is specific to this machine: **on-die SRAM has no pin budget.** Write queues exist because DRAM channels are scarce; here the fabric is wires on a die and the banks are on that same die, so per-hart non-blocking memory issue is a wire-count problem, which is the currency the engineering-free axiom exists to spend. The condition is therefore stated as an **admission side condition rather than a measurement**: §11 already emits the TDM NoC schedule (R-11-017) and already reads each island's memory ceiling off that schedule and the bank/macro/tier binding, so *a schedule not satisfying ρ ≥ 1 for every hart in every slot is rejected* is a side condition on an artifact the tool already produces. Gate 2 stops being an empirical hope and becomes interval arithmetic, which is where this design buys everything else.

**The residual is bank conflict inside a shared macro**, which slot provisioning does not cover because the contention point is the bank arbiter rather than the fabric. It is answered by static placement (R-08-015 already schedules placement) and bank interleaving, and it is *vacuous* for high-assurance islands, which own a whole macro or tier and have no co-tenant. So the residual falls only on low-sensitivity co-tenants of a shared macro: precisely the population §15 already books as carrying residual coupling narrowed by static arbitration. The cost lands where coupling is already accepted; SC and the empty flush set go to everyone.

**It inverts the admission-gate objection, and the gain must not be overstated.** R-15-018-2's closing objection is that SC uniformly inflates every store-followed-by-load path and so raises every bound feeding the §11 schedulability check, landing on a gate rather than a preference. At ρ ≥ 1 there is no inflation, because store issue never waits; and ρ ≥ 1 independently **tightens** every memory operation's WCET, loads included, since the bound no longer prices worst-case slot wait. That tightening is a consequence of the provisioning, not of the deletion: provisioning is what makes the deletion free. On the `fence.t` side the constant is already a first-class admission term through §11's switch-duty ratio σ = C_switch / T_poll, so removing its largest component is directly visible in the arithmetic, but at realistic switch rates the raw throughput effect is small. **The honest claim is performance-neutral with a WCET-bound tightening, not faster.**

**Ground (4) stands and is conceded.** SC does not delete the memory model: this remains a multi-hart platform over shared island SRAM, so an interleaving semantics is still stated over the per-hart sequential Sail and still proved of the RTL, and the Isla litmus set persists against a simpler oracle. What ground (4) understates is the rest of the ledger: the relaxed-edge count goes one to zero, `fence` goes to `nop`, R-15-015b vanishes, and the flush set empties. The saving is larger than "stating a relaxation" and still smaller than "deleting the model."

**The kill switch, stated so the DSE can fire it.** The falsifier is **sustained scalar store bursts exceeding one memory op per cycle against a bank that cannot absorb them.** The structural argument that this machine generates few is real but is an argument, not a measurement: bulk movement rides *vector* stores at VLEN bits per instruction and is array-bandwidth-bound rather than queue-depth-bound, `cbo.zero` is a bulk granule operation, and wide in-order issue with macro-op fusion means scalar store streams are not the bulk path. If a workload sustains such a burst against an island where ρ ≥ 1 is unaffordable, the deletion is not free *for that island*, and the honest disposition is per-class staging rather than a platform-wide claim. Half the arithmetic needs no RTL and is available now: the savings side is C_switch's drain term multiplied by the switch rate in the major frame, both static schedule properties.

| Gate | Standing |
|---|---|
| 1. Deletes surface | **Clears, and unusually widely:** an architectural memory model, an instruction's semantics, a bring-up gate, the sole flush-set member, and R-15-106's residual scope. |
| 2. Costs nothing, or gains | **Open, and the reason this is not adopted here.** Free at ρ ≥ 1, which is a composition-time condition rather than a hope, but the falsifier above is unmeasured until the microarchitectural DSE runs. |
| 3. Sheds no security property | **Clears.** SC is strictly stronger than TSO; no theorem weakens, and the fabric obligation is unchanged. |
| 4. Follows the profile's grounds | **Clears.** *Delete rather than defend* (R-15-012) in its primary form, and R-15-105's conversion of a correctness obligation into an absence obligation, moving work out of the least-built arrow (R-17-039). |
| 5. Reduces, never relocates | **Clears.** Nothing moves into software: the ring algorithms lose fences rather than gaining them, and the one relocation is into the TDM schedule, which §11 already emits. |

**Disposition:** **not adopted, and distinguished rather than rejected.** The normative position stands unchanged: **Ztso is the specified model (R-15-004) and the store buffer is retained**, and the table above continues to reject buffer-retained SC on grounds that remain correct about what they evaluated. What this entry changes is the standing of the *other* proposal, which had never been evaluated: it clears gates 1, 3, 4, and 5, and turns on a single measurable quantity. It is therefore booked as a **DSE question with a stated falsifier and a stated admission condition**, not as a pending change and not as a foreclosed one, and it is the second such question the memory model carries beside R-15-018's own §18 note. Should the DSE return ρ ≥ 1 as affordable on every class, the spec-body changes it would trigger are enumerated here so the scope is not rediscovered: §15's memory-model subsection (R-15-004, R-15-015, R-15-015a, R-15-015b, R-15-016, R-15-017, R-15-088), the four-class map's class 3 row (R-15-213, R-15-217) and the A-13 – A-15 dependency argument (R-15-215) in [absence-contract.md](absence-contract.md), the `fence` and memory-model rows of [isa-profile.md](isa-profile.md), and a new §11 obligation carrying the ρ ≥ 1 side condition on the emitted TDM schedule. Non-normative; no spec-body change is made by this entry.

---

## Dedicated fixed-function GPU and uniform graphics on every core: both declined

A fixed-function GPU would provide higher raster and texture throughput per watt, but a modern GPU is a separately booted computer: command processor, firmware, shader compiler, self-mastering DMA, driver, command validator, and data-dependent SIMT scheduler.
That is the foreign-computer and variable-timing class §§4, 11, and 15 exclude, and CHERI-per-lane remains unexplored.

The opposite proposal, widening every core so graphics can run wherever cycles are free, is also declined.
It over-provisions scalar and control classes with large vector register files and zeroization costs, and assumes dynamic cross-class migration that the statically pinned multikernel does not offer.

**Disposition:** no fixed-function GPU, GPU firmware/driver stack, SIMT scheduler, or uniform graphics datapath on every core.
The adopted graphics-compute lineage is documented in [Inspirations & Prior Art](inspirations.md).
The honest cost is the net-new engineering and lower peak throughput of a no-JIT software renderer.

---

## Vulkan and software GPU personalities: declined

Vulkan is the most explicit mainstream graphics API, but its central runtime operation is pipeline creation from shader IR.
Implementing that contract in software would reintroduce runtime code generation and the shader compiler W^X excludes; interpreting SPIR-V would avoid executable promotion but spend the graphics throughput budget while retaining the other surfaces.
Command buffers recreate an attacker-authored stream and validator even without GPU hardware, and descriptor sets, queues, heaps, ICDs, and extensions emulate a discrete device and memory model the machine does not have.

**Disposition:** expose no Vulkan, GL, Metal, wgpu, software ICD, command-buffer personality, or runtime shader compiler.
The certified-kernel interface used instead is documented in [Inspirations & Prior Art](inspirations.md).
The honest cost is a native backend per toolkit rather than one inherited compatibility layer.

---

## OLED aging compensation and an unavailable micro-LED base: declined

Emitter physics alone does not make a panel space-grade: radiation and environmental qualification are dominated by the backplane, driver silicon, alignment layers, polarizers, packaging, and link.
The decisive security distinction is correction state.
Shipping OLED mitigations derive per-pixel correction from accumulated drive and thermal history, keeping persistent mutable state in panel electronics outside the capability system; that state is both a foreign computer and a coarse integral of previously displayed content.

Micro-LED avoids the organic-aging loop, but it was not selected as the current mandatory panel because the required five-to-seventeen-inch, high-density supply does not exist at viable mass-transfer yield and repair economics.

**Disposition:** decline panel-side adaptive aging compensation and do not make present-day micro-LED procurement a base requirement.
The technology-neutral rule and current/future instantiation are documented in [Inspirations & Prior Art](inspirations.md).
Non-normative; no spec-body change is made here.

---

## Adaptive-Sync and per-frame variable refresh: declined

Variable refresh fixes tearing and cadence mismatch by making the frame period depend on when composition finishes.
The §11 schedule could reserve the fastest mode and tolerate slower frames as slack, so schedulability is not the binding objection.
The binding objection is observation: composition completes when the slowest surface is ready, so a present callback or external sink learns timing influenced by surfaces it has no capability to inspect.
It is the display instance of the reactive workload-to-timing loops the profile deletes elsewhere.

**Disposition:** no Adaptive-Sync or other per-frame variable-refresh mechanism.
The fixed-rate substitute and its lineage are documented in [Inspirations & Prior Art](inspirations.md).
The honest cost is residual judder for unknown or varying non-divisor content rates.

---

## Dedicated firmware-driven NPUs: declined

A dedicated NPU uses one or more control cores and mutable firmware to master a separate matrix engine.
Its throughput and model agility are real, but its trust structure is exactly the on-die foreign computer §4 excludes: a second core, firmware image, update path, DMA master, and block of architectural and verification surface.
Wrapping CHERI-unaware accelerator IP in a boundary checker would contain the same opaque engine rather than remove it.

**Disposition:** reject the separately booted, firmware-driven NPU and its control processor.
Model changes are compiled and certified off-device rather than installed as accelerator firmware.
The integrated tensor-core pattern actually used is documented in [Inspirations & Prior Art](inspirations.md).

---

## x86 ACE/Arm SME architectural state: not imported

x86 ACE and Arm SME were evaluated as models for the frozen matrix extension.
Dedicated architectural tile files and block-scale registers add large context and zeroization state, serialize low-precision operations around scale writes unless renamed, and enlarge the Sail and switch proofs.
The platforms' ISA encodings themselves are not importable into RV64.

**Disposition:** import neither ACE/SME tile state nor an architectural block-scale register.
Outer-product sourcing remains a proof-aware microarchitectural DSE question rather than a new ISA commitment.
The software de-quantization and scaling path adopted from this comparison is documented in [Inspirations & Prior Art](inspirations.md).

---

## Bespoke full-PQC and NTT instruction sets: declined

HORCRUX, PQCUARK, and related coprocessors add NTT butterflies, modular reduction, samplers, and algorithm-specific datapaths beside Keccak.
They target small vectorless embedded cores, whereas this application-class profile already has RVV: the lattice arithmetic is straight-line, statically scheduled, and constant-time on the vector unit.
Specialized NTT instructions would add Sail semantics, `Zvkt` timing clauses, and RTL refinement cases without deleting a difficult proof.

**Disposition:** reject the full PQC coprocessor and its NTT, modular-reduction, and sampler instructions.
The one primitive that crossed the hardware threshold and the software path retained for the rest are documented in [Inspirations & Prior Art](inspirations.md).

---

## Mon CHÉRI conditional capabilities and an initialization tag plane: rejected

Mon CHÉRI adds operation-specific bounds and conditional permissions to capabilities, with Write-before-Read as the flagship policy.
The binary mechanism is declined: it is opt-in, changes the capability encoding and instruction stream, steals cursor bits, assumes sequential writes, and needs a store-linearization compiler pass to avoid stale capability copies and false positives.
It would enlarge Sail, RTL refinement, CHERI-CompCert, and the TAL metatheory for non-monotonic permission regain.

A transparent address-indexed initialization plane was also evaluated and rejected.
Although deterministic and stock-binary-compatible, its marginal population is code admitted incorrectly by the certifier: eager zeroization already prevents disclosure, native tags prevent uninitialized capabilities, and every admitted component must establish initialization by proof or typing.
The plane would therefore hedge a verified primary in the same way the profile declines PMP, IOMMU, MTE, and shadow stacks.

**Disposition:** reject conditional-capability encodings, operation-bound instructions, store linearization, and a second initialization metadata plane.
The adopted Write-before-Read lineage is documented in [Inspirations & Prior Art](inspirations.md).

---

## Programmable tag-policy engines: PUMP and software-defined metadata processing rejected

SAFE, micro-policies, PUMP, and CoreGuard attach metadata to words and consult a software-defined policy through a hardware rule cache.
The rule cache is hidden history-dependent state surviving a partition switch, and misses trap to a monitor at a latency dependent on operand tags, which under IFC are themselves secret labels.
It therefore fails admission tests 2 and 3 and breaks the fixed WCET model.
Runtime-loadable policy also inverts the platform's frozen-with-the-proof discipline: expressiveness is purchased with a general trusted monitor and cache.

**Disposition:** reject the programmable rule cache, policy monitor, and field-loadable metadata semantics.
SAFE's Coq metatheory remains methodological evidence only; fixed CHERI tags and statically decided TAL attributes are documented in [Inspirations & Prior Art](inspirations.md).

---

## Physical bifurcation of the radio onto a second die: declined

A second attested copy of the die linked by ring-over-SerDes would separate radio power and thermal mass from the rest of the machine.
It would not separate the mask-set threat, because the proposal deliberately reuses the same die design, and it would add a package, link protocol, parser, CDC/metastability obligation, two-die attestation relation, power, latency, and another object for supply-chain inspection.
The remaining substrate and analog-emission separation is outside the remote threat model and is not cleanly closed by a nearby second die in any case.

**Disposition:** decline the second radio die and inter-die link.
The adopted top-rung on-die isolation is documented in [Inspirations & Prior Art](inspirations.md).

---

## Memory encryption and the memory integrity tree: declined outright, because memory cryptography protects an interface and this machine has none

Total memory encryption and a memory-wide Merkle counter-tree for integrity and anti-replay are the two mechanisms a conventional design puts on the memory path, and both are declined here, in every configuration, along with the on-die node cache that would amortize the tree's walk.
The entry is kept at length because the reasoning generalizes: this is the clearest case in the design of a mechanism that admits itself by *category* ("memory protection is good") rather than by the admission test everything else must pass.

**The reframing that settles it: memory cryptography protects an interface, not a memory.**
Every word decrypts on arrival at the controller before it can be computed on, so the plaintext is reachable to any adversary who reached the core, and the mechanism buys protection at exactly one physical hop.
A conventional design encrypts DRAM not because DRAM is untrusted but because the *bus* is exposed.
This design deleted the bus: main memory is bespoke SRAM on the same die as the cores (the SRAM entry above), and the packaging entry below declines the chiplet and bonded-stack realizations that would have reintroduced a die-to-die interface.
So there is no hop, and the mechanism has no customer.

**Each benefit usually claimed for it is already discharged.**
Shutdown zeroization: SRAM is volatile with near-zero remanence and the platform zeroizes anyway (§9).
Bus interposers: there is no bus.
Cold boot: the same volatility.
What remains is an adversary already inside the package and onto the die, which is **invasive physical attack, out of scope by name** (§3, §17) and out of scope for a reason that survives scrutiny: an attacker at that level reads and writes SRAM directly, and would equally reach the keys and root registers any controller-side construction depends on.
Encrypting against that adversary is structurally identical to PMP, the IOMMU, MTE, and the Harvard split, each declined on *verify rather than hedge* grounds; declining this one is consistency, not economy.

**The tree carried a soundness defect on top of the scope problem.**
Its node cache would hold *recently-used* tree nodes, which is ordinarily defended as "address- not history-indexed, so no data-cache timing channel."
That defence does not work: **a data cache is address-indexed too.**
Address-indexing describes the lookup; what makes a structure a channel is that its *contents* are a function of history, and "recently-used" is history, so its hit and miss distribution would depend on another partition's access addresses.
Three claims fail together under it: the flat-latency claim (WCET must then assume the full walk, log *N* SRAM accesses plus crypto, on every access), the "dominant WCET-pessimism term is gone" claim (the cache is deleted and its pessimism term reintroduced through the tree), and **admission test 3**, which such a buffer fails outright absent a per-island partitioning nothing specifies.

**The cost sits almost entirely in the tree, not the cipher.**
Encryption is a fixed pipeline latency: one more constant in the timing-annotated model.
A tree walk is log-depth with a hit-or-miss distribution, which is precisely the term §11 must otherwise bound pessimistically on **every** access, instruction fetch, framebuffer scanout, and bulk vector and matrix traffic included.
Declining both keeps the memory controller down to a granule read-modify-write stage and an ECC encode-and-check stage, two fixed terms and one memory-access latency constant, and keeps an entire encrypt-and-authenticate pipeline off the least-built arrow (the Kôika-authored RTL ⊑ Sail workstream, §18), where net-new hardware is most expensive.

**Capability-scoped encryption was weighed as the middle option and also declined, though its idea is kept.**
The No-PMP decision re-homes PMP's third role, **crown-jewel secret fencing**, onto the crypto core's hardware boundary and sealed capabilities (the drop-PMP entry above), and blanket memory encryption is a poor instrument for that role, taxing all of memory to protect key schedules and sealing roots.
**CHERI-Crypt** (Jackson, Jiang, and Oswald, *IACR TCHES* 2025(2); MIT-licensed, IACR Artifacts-Functional, [cap-tee/cheri-crypt](https://github.com/cap-tee/cheri-crypt)) supplies the better shape: an encryption engine for memory reached through **sealed CHERI capabilities**, on a CHERI-RISC-V core, encrypting compartments and secure regions rather than everything.
The shape is right and the design adopts its *lesson*, that a security mechanism belongs on the capability substrate rather than spread uniformly over memory.
The **mechanism** is nevertheless declined here, because it too is transparent to the capability check (the controller decrypts for anyone issuing an in-bounds access), so it adds nothing against on-die software compromise, which CHERI already confines; its only real customer is the same physical adversary at an interface this machine does not have.
Crown-jewel fencing therefore rests on **the crypto core's hardware boundary and the seal/switch primitives alone** (§7, with the sealing and attestation service of §12 as its userspace face), which is where the role belonged: the encryption was never the part doing the work.
CHERI-Crypt's numbers would not have transferred in any case (RV32 on FPGA: ~3.5× flip-flops and LUTs against a small soft core, −6 MHz on a soft core, and 626 cycles for a seal-and-invoke rather than a per-access latency), and its TEE/enclave **framing** is excluded by §15 by name.

**Disposition:** decline memory encryption, authentication, an integrity tree, and controller key material.
The memory controller's only pipeline terms are the granule read-modify-write and the ECC encode-and-check.
Integrity against the threat main memory on this die actually faces, the random bit flip, is the pervasive SECDED/DECTED ECC with bit-interleaving and scrubbing, uncorrectable events being fail-stop sentinel events; confidentiality at rest is SRAM volatility plus zeroization; crown-jewel confidentiality is the crypto core's boundary plus the seal/switch primitives (§7, §12); and data-at-rest on persistent media keeps its full AEAD and Merkle-root story (§10), because persistent media genuinely leave the die and genuinely survive power-down, which is exactly the asymmetry that justifies treating them differently.

**Honest residual (§17):** the design has **no defence-in-depth layer beneath the package boundary on the memory path**, so the invasive-attack scope line is load-bearing rather than conservative.
If that line is ever judged wrong, nothing sits behind it: there is no encryption to slow an attacker down and no freshness check to catch a replay.
This is the document's own posture (*verify rather than hedge*) applied to its own threat model, and it is booked as a residual rather than presented as a guarantee.

---

## SRAM chiplets and bonded die-stacking: declined

Separately manufactured SRAM chiplets and bonded memory dies would improve density, process specialization, yield, and economics.
They are declined because each additional die is an additional mask set, fab lot, supply-chain entity, and object whose correspondence to the verified design must be evidenced; the die-to-die interface also recreates the exposed hop that makes memory cryptography and link protocol machinery arguable.
Bonding does not change that trust structure merely because the second die is vertical.

The capacity advantage is real and the cost is explicit: without a separately optimized SRAM die, capacity depends on the less mature one-die process route and can collapse to the planar-tier budget if that route fails.

**Disposition:** no SRAM chiplet, bonded memory die, die-to-die memory link, or multi-die fallback.
The adopted one-die realization and its discrete manufacturability residual are documented in [Inspirations & Prior Art](inspirations.md).

---

## Dynamic/adaptive low-leakage SRAM techniques and active sub-threshold memory: declined

Workload- or temperature-tracking body bias, activity-driven power gating, and adaptive read/write assist add feedback from data and activity to power and timing.
That is a correlation-power and data-dependent-latency surface and the same reactive class the profile removes from DVFS, refresh, prediction, and caching.
Deep sub-threshold active SRAM is also declined because its latency reopens the gap the cacheless, non-speculative architecture relies on fast SRAM to close.

The bitcell topology that would carry these levers is a separate decision and is taken in the entry below, which owns the transistor-count question for the stability family and the security family alike.

**Disposition:** reject dynamic/adaptive leakage controls and sub-threshold operation for active working memory.
The admitted static circuit lineage is documented in [Inspirations & Prior Art](inspirations.md).

---

## SRAM bitcell transistor count: 6T stays normative, the stability family stays an implementation choice, and the security family is declined at the test masking was declined at

The proposal is to spend bitcell area on a higher-transistor-count cell, most often stated as 10T, to buy side-channel resistance and a decoupled read path, accepting lower capacity in exchange.
It is refused for main memory, and the literature is the reason rather than the capacity arithmetic alone: **the cells that buy side-channel resistance and the cells usually called 10T are different cells, and on the security axis the common 10T is the negative baseline rather than the improvement.**

**Three families share the transistor-count axis and none of them is ordered by it.**
The *stability and minimum-voltage* family decouples the read port from the storage node to make read static noise margin equal hold margin: the foundry 8T, the disturb-free 9T, Calhoun and Chandrakasan's subthreshold 10T with its four-transistor read port, and the Schmitt-trigger cells of the Kulkarni line.
The *security* family equalizes an access's energy or a cell's static current, and it is not the same set: the strongest dynamic-power result in the literature is a **7T** cell, fewer transistors than the 8T it improves on, while the strongest leakage-power result is a **12T**.
The *periphery* family changes no cell at all.
Transistor count is therefore an artifact of which margin a cell was drawn for, and reading it as a security ordering is the error the proposal rests on.

**On the dynamic-power channel the security cells target the write path, because the 6T read is already the balanced half.**
A 6T read is differential: both bitlines precharge high, exactly one discharges by the sense delta, and precharge restores both, so per-access bitline energy is comparatively data-balanced because one line of the pair always discharges.
The write is where 6T leaks, the cell's energy depending on whether the addressed cell flips, which is the Hamming-distance model DPA is built on.
The security literature is arranged accordingly: [Rožić, Dehaene, and Verbauwhede's 8T dual-rail-precharge cell](https://ieeexplore.ieee.org/document/6224331/) imports the dual-rail discipline of secure logic styles, and [Giterman, Keren, and Fish's 7T security-oriented bitcell](https://doi.org/10.1109/TCSII.2018.2886175) (*IEEE TCAS-II* 66(8), 2019, 28 nm) adds one transistor and a two-phase write to reach **over 1000× lower write-energy standard deviation between writing a one and writing a zero**, at 39–53% lower write energy and 19–38% lower write delay than the prior power-analysis-resistant cells.
The older *Power Analysis Resistant SRAM* line reports a 10× reduction in the data and address dependence of power at higher area and power, and an 11T cross-coupled-domino two-port cell reaches the same goal by a third route.
**The decoupled-read cell the proposal names is on the wrong side of this.** Its read buffer is single-ended, so the read bitline discharges for one polarity only and the fetched word's Hamming weight becomes a first-order term in read current, replacing the one comparatively balanced access the 6T array had. Buying that cell for side-channel reasons trades the balanced half away and leaves the unbalanced half untouched.

**On the static-power channel the inversion is measured, and the measurement is on a 10T.**
Leakage power analysis recovers stored data from static current without any access occurring, the word's leakage tracking the Hamming weight of what it holds (Alioto et al., *Leakage Power Analysis Attacks: A Novel Class of Attacks to Nanometer Cryptographic Circuits*), and the countermeasure cells are explicitly *symmetrical* ones: a leakage-power-attack-resilient symmetrical 8T, a [PMOS-reading 9T at 7 nm](https://doi.org/10.3390/electronics13132551), and a [Schmitt-trigger-based symmetric 12T at 40 nm](https://doi.org/10.1016/j.mejo.2023.105888).
That last one supplies the decisive number. It is built by adding two transistors to **the Schmitt-trigger 10T**, and it reports a leakage-distribution overlap between storing a zero and storing a one of **97.5% for the 12T against 0.09% for the 10T it extends**: the canonical stability-oriented 10T is very nearly perfectly separable under leakage power analysis, which is why a security cell had to be built on top of it.
The proposal would adopt, for side-channel reasons, the cell the side-channel literature uses as the thing to fix.

**The capacity price is the one the proposal already concedes, and it is larger than "10T versus 6T" suggests.**
Reported layouts put a single-decoupled-read 10T at about **1.67×** the 6T cell (0.047 µm² in that study), and a two-port 10T with two decoupled read ports at **3.18×**, with 8T variants between; the security cells add their own, a transmission-gate construction costing 1.88×.
Against the §15 budget (R-15-170: ~30–50 Mb/mm², a gigabyte at 160–270 mm² of array, a phone at 4–8 GB over 8–16 tiers), 1.67× means the same roster wants 13–27 tiers, or the phone falls to 2.5–5 GB.
In the pessimistic branch the design already books (R-15-173a: no array-grade complementary back-end device, capacity is the single planar tier at 1–2 GB) it falls to 0.6–1.2 GB, below the 1–4B-parameter inference class R-15-171 already treats as the phone floor.
Three second-order costs run the same way: more devices per bit is more leakage per bit, and R-15-189l makes leakage proportional to powered bitcell count; the compensating minimum-voltage lever is unbanked, because R-15-188 holds main memory at a fixed operating point and never scales it, while the RETAINED rail is set by hold margin, which is the same cross-coupled latch in every cell here; and single-ended sensing needs a larger swing than differential small-signal sensing, so holding array latency costs column segmentation and periphery area on top of the cell, which matters because flat SRAM latency is the premise the cacheless architecture rests on (R-15-164).

**The cheap answer exists, is silicon-proven, and is declined on the same ground as the expensive one.**
[Impedance randomization units placed in the periphery of a conventional 6T macro](https://ieeexplore.ieee.org/abstract/document/9453841) (*IEEE Access* 2021, 55 nm test chip) cost **1% area and under 5% latency and power**, and reduce measured leakage from 8 bits of mutual information after 100 traces to under about 1.5 bits after 160K traces.
That is one to two orders of magnitude better than a cell swap on every axis this design counts, and it is still refused here, at the test R-17-058a sets: **its deliverable is a measured reduction factor, not a statement anyone can verify.** Every figure in this entry is of that shape, a 1000× standard-deviation ratio, a 10× dependence reduction, a 97.5% overlap, a mutual-information decay curve. Masking enters the crypto core only together with machine-checked *d*-probing and composition theorems over a conferred probing-model statement, the axiom named and review-gated (R-05-004a, R-15-053a); the bitcell and the periphery unit offer the axiom with no theorem over it, and *attenuation no theorem stands on is evidence about difficulty, and difficulty is what this document declines to count everywhere else*, so neither gets in through a door masking paid a theorem to open.
The randomization unit carries a second objection of its own: it puts a randomized element on the most-shared resource in the machine and draws per-access randomness from the one entropy root, against a design whose memory path is a fixed-latency constant in the §11 model.

**What the decoupled read actually buys is reliability, and it is already bought.**
Removing read disturb separates two electrical paths; it is not an information-flow boundary and does not separate who may read from who may write, which here is CHERI permission bits checked at the fabric.
Read disturb and half-select are covered by SECDED with mandated physical bit-interleaving and scrubbing, DECTED on the tag plane, and asymmetric-Vt cell margin, with an uncorrectable event fail-stop (R-15-175, R-15-177, R-15-184's residual).
The one genuine composition is narrow and worth recording: because bit-interleaving forces column multiplexing, it forces half-select, and a column-write-controlled decoupled-read cell removes that disturb mode at its source rather than correcting it (a [2026 bit-interleaved macro](https://www.sciencedirect.com/science/article/abs/pii/S0167926026000738) combines exactly bit-interleaving, switching-power-rail write assist, and decoupled read). It improves a residual that is already covered, which is an implementation-grade reason and not a platform-grade one.
Note also that the p-type argument moves slightly the other way and does not carry: a decoupled read buffer is NMOS, so the pFET fraction per bit falls from 2/6 to 2/8 or 2/10, easing the thermal and device-quality margin of a back-end tier, but R-15-163's gate is binary and the latch still needs its two pFETs, so a lower fraction does not unlock the branch.

**Disposition:** **6T remains the normative main-memory bitcell.**
The stability and minimum-voltage family (7T, 8T, 9T, 10T decoupled-read, Schmitt-trigger, dual- and two-port) remains what it already was, a per-tier and per-structure implementation decision taken on density, stability, and porting grounds, and it is admitted where multiple ports are a *functional* requirement, which is the vector register files and the matrix scratchpads rather than main memory.
It is admitted on no security ground whatever, and this entry exists so that the next reading of "10T is better for side channels" meets the measurement that contradicts it.
The security-oriented family (7T power-analysis, 8T dual-rail-precharge, 11T domino, symmetrical 8T, PMOS-reading 9T, symmetric 12T) and the cheaper periphery randomization unit are both **declined as platform mechanisms**, under R-17-058a's existing test rather than a new one.
Re-open on the four conditions R-17-058a's test states, the same four the crypto core's masking meets (R-05-004a, R-15-053a): a probing- or leakage-model statement for the array authored as a crown-jewel specification beside the `Zkt`/`Zvkt` and probing ones, the array's data-independence theorem carried as a §5 obligation and verified on the artifact, the composition property shown to survive the macro rather than the cell, and any randomness booked against the entropy root and the §11 slot.
Until those exist, a capacity sacrifice would buy attenuation the document cannot state and would spend the roster's stated floor to do it.
Non-normative; no spec-body change, with one exception recorded next.

**Honest residual (§17), and it is not currently named anywhere.** R-17-058a scopes the analog channel to the crypto core *in operation*, and R-17-059 scopes the memory path to invasive attack. Leakage power analysis sits in neither: it reads an array's static current while nothing is being accessed, and power mechanism 5 holds crown-jewel arrays in **RETAINED** at a reduced rail for exactly the long, quiet, locked standby interval R-15-189b says the battery spends its life in, which is unbounded integration time against a stationary target on the one machine-wide resource. The reduced retention rail raises leakage's share of total current, and the admitted leakage levers (asymmetric-Vt storage core, gate-length biasing) shape the very quantity such an attack measures. This does not change the disposition above, the class remaining physical-scope and answered by no mechanism either way, but it is a distinct exposure window from the one §17 records and it wants its own residual entry rather than being read as covered by the crypto-core one.

---

## Transparent variable-rate memory compression and runtime deduplication: declined

Variable-rate compression makes resident footprint and decompression latency functions of data, so a composition-time capacity proof becomes an overcommit estimate and the flat memory WCET becomes operand-dependent.
A compressed pool is hidden history-dependent placement state; a background compactor is an autonomous memory-touching engine; and occupancy and timing expose a CRIME/BREACH/Safecracker-style ratio oracle across domains.
Runtime deduplication additionally creates a sharing and authority edge from content coincidence rather than delegation.

The mechanism also conflicts with the fixed ECC/tag granule: a variable-size rewrite needs relocation and variable-extent read-modify-write, while native CHERI tags either become a separate table or force capability-bearing data out of the compressor.

**Disposition:** no transparent main-memory compression, compressed cache or swap, runtime deduplication, compactor, or recompressor.
The fixed-rate representations used instead are documented in [Inspirations & Prior Art](inspirations.md).

---

## Static code overlays: a deterministic instruction scratchpad, deferred until a measured resident image fails the capacity budget

The proposal addresses the one capacity case the fixed-rate data rule above does not settle: an application whose code cannot remain resident even after §13 whole-image dead and duplication elimination (R-13-010a, R-13-010b, R-13-010c), size-directed outlining and tail merging, and the §15 fixed-rate dictionary encoding (R-15-036a). Composition partitions that application into statically scheduled phases and assigns each phase a fixed instruction-bank image. Before a phase begins, a dedicated loader fills the bank from the authenticated object store, hardware verifies the image hash and canonical encoded representation, execution receives read-execute authority but no store authority to the bank, and the bank is invalidated before reuse.

**It resembles a cache physically and pre-warming operationally, but is neither architecturally.** A cache fills on demand, chooses retention and replacement from runtime access history, and preserves a miss path to backing storage. This bank is a **statically managed instruction scratchpad**: the composition fixes every resident set and replacement point, the §11 schedule reserves the complete bounded fill before entry, and no instruction miss or fallback fill exists during the phase. Pre-warming makes cache hits likely; the overlay plan makes phase residency an admission invariant. The distinction preserves deterministic execution timing and avoids tags, replacement policy, and history-dependent cache state.

**The security shape is admissible.** The executable bank is never writable by ordinary software, its contents derive only from an authenticated generation, and canonical-encoding verification prevents a hash-valid byte string from acquiring a second instruction reading. Phase transitions are fixed by the composed control-flow and schedule artifacts rather than requested dynamically by the application. There is no demand paging, executable promotion, runtime linker, or general loader API, and no authority edge is created by which a compartment can choose arbitrary code to install. In those respects the proposal takes the useful physical shape of an instruction cache while declining the cache mechanism that §15 deletes.

**The proof and TCB cost is nevertheless substantial.** The loader holds bank-fill authority that no current runtime component needs; the composition proof gains a per-phase residency plan and must show that every reachable instruction of a phase is present before entry; the temporal proof gains a bounded authenticated-fill stage on every transition; the image argument must connect the stored object, hash, canonical dictionary encoding, bank contents, and executed instruction stream; control transfer must be proved unable to cross into a nonresident phase; and invalidation joins the `fence.t` argument so that no stale instruction or authority survives bank reuse. Double banking can overlap fill with execution, but adds another executable store and a bank-swap atomicity proof; single banking is smaller but places the entire fill on the phase boundary. Either form spends trusted mechanism and verification surface to recover SRAM capacity.

**Why it remains open rather than adopted.** The project axiom treats proof surface as scarce and engineering as free. Overlays spend the scarce quantity to solve a hard capacity failure, so they are justified only if the capacity failure exists after every static lever already admitted. That condition requires a measured composed roster, not an estimate of an uncomposed application and not a hypothetical large workload. The measurement must include the exact dead and duplication elimination result, the frozen dictionary's encoded bundle count, code and read-only data placement, and the SRAM allocation left after the accepted system roster. Until such a roster fails admission, adding the loader and its proof obligations would violate the organizing principle by enlarging the TCB without discharging a demonstrated requirement.

**Disposition (deferred behind a measured trigger):** do not add static code overlays to the normative architecture, requirements register, ISA profile, schedule, or implementation plan. Preserve them as the final resident-code capacity alternative. Re-open the decision only when an otherwise admitted, representative composed roster exceeds its executable SRAM budget after R-13-010a/b/c and R-15-036a have been applied and measured. At that point compare three explicit outcomes: reject or shrink the roster, provision more SRAM, or admit the smallest single-bank statically scheduled overlay mechanism whose loader, residency, canonical-image, control-transfer, timing, and invalidation obligations can be closed. No demand-filled instruction cache, paging path, or application-directed code loading is introduced under this disposition.

**Honest residual (§17):** deferral means the current architecture may reject an application whose resident image exceeds the fixed SRAM budget, even when its phases would fit separately; that is an accepted capacity limit, not an implementation omission. If the trigger is later met and overlays are adopted, deterministic timing survives only because every fill is statically scheduled and bounded, while the loader and executable-bank lifecycle become new crown-jewel proof surfaces that must be counted rather than described as cache pre-warming.

---

## Non-volatile main memory and unified SOT-MRAM storage: the idle-power case is real, but the useful substitution is physical, not semantic

The updated proposal is narrower and stronger than generic "use MRAM": replace the large SRAM arrays with encrypted, ECC-protected **2T-1MTJ spin-orbit-torque MRAM (SOT-MRAM)**; use c-axis-aligned crystalline In-Ga-Zn-O (**CAAC-IGZO**) transistors to move selectors into the back end of line; stack and bank the arrays; remove the external SSD; and treat 2T separation, CAAC-IGZO, ECC, and encryption as successive side-channel reductions.
It decomposes into five claims that must be decided separately: (1) magnetic cells remove SRAM retention leakage; (2) 2T SOT is a better active-memory cell than 1T spin-transfer-torque MRAM (STT-MRAM); (3) oxide-semiconductor selectors make dense monolithic tiers practical; (4) banking recovers the lost latency; and (5) one physical medium should erase the architectural memory/storage boundary.
MRAM is the strongest non-volatile main-memory candidate, so it carries the detailed analysis; FeRAM and ReRAM remain folded in below, because they share the non-volatility question while carrying different device-specific debts.

**The steelman: the idle-power win and the SOT device progress are both real.**
The magnetic state draws essentially no cell-retention power and needs no refresh, directly attacking the largest honest cost of the all-SRAM choice; only the decoders, sense amplifiers, ECC, encryption, fabric, and write drivers remain powered.
The 2T SOT topology also improves on 1T STT: the read current crosses the MTJ while the write current runs through the SOT channel, separating read and write optimization, sharply reducing read disturb, and keeping the high write current out of the tunnel barrier.
The silicon evidence is no longer merely a device promise. **"Demonstration of 128 Kb SOT-MRAM chip with 5 ns write and 15 ns read speed, high endurance over 10^10 and low ECC-on bit error rate"** (IEDM 2024, [DOI](https://doi.org/10.1109/IEDM50854.2024.10873510)) is a fabricated chip result; [Truth Memory's 8 Mb SOT-MRAM chip](https://www.mram-info.com/truth-memory-corporation-developed-worlds-first-8mb-sot-mram-chip-using-110-nm-process) (January 2026) is the array-scale mark, a 110 nm multi-bank part with redundancy and on-chip ECC on a wafer-level 200 mm flow compatible with mainstream CMOS back-end processing, reporting sub-nanosecond writes below 1 pJ/bit at write-error rates down to 10^-6, and now in pilot/early production of standalone parts (vendor press reports a first deployment in a drone flight controller, mid-2026); **"Unveiling the endurance limit of SOT-MRAM"** (Jiang et al., *Nano Research* 2026, [DOI](https://doi.org/10.26599/NR.2026.94908447)) fabricates and cycles a 2 Kb array and, after material and geometry optimization, reports endurance beyond 10^18 cycles at 125 °C.
The architecture-level upside also has a steelman: **"A Detailed Study of SOT-MRAM as an Alternative to DRAM Primary Memory"** (*IEEE Access* 2024, [DOI](https://doi.org/10.1109/ACCESS.2024.3352151)) projects a 74.05% power reduction, a 72.85% energy-delay-product reduction, and at most a 3.71% latency penalty for its evaluated full-main-memory systems.
That last result is simulation, not silicon, and its own abstract says public SOT-MRAM parameters were unavailable, so it is evidence that the cross-stack case can close under a plausible parameter set, not evidence that a manufacturable array has closed it.
CHERI tags and ECC remain compatible: an MRAM word can carry the native validity bit beside the data exactly as SRAM does, and ECC should cover the stored ciphertext and tag plane before authentication or decryption. Neither compatibility decides the substitution.

**2T SOT is not a one-transistor, DRAM-class cell.**
A conventional 2T-1MTJ SOT bit needs distinct read and write access devices plus difficult MTJ and SOT-channel routing; its density case is against SRAM, not against 3D NAND and not automatically against DRAM.
**"SOT-MRAM Bitcell Scaling with BEOL Read Selectors"** (Xiang et al., *IEEE Transactions on Electron Devices* 2025, [arXiv](https://arxiv.org/abs/2508.18250)) identifies that routing as the primary scaling limit. Its design-technology co-optimization projects 10-40% area reduction from BEOL selectors and eventual sub-N3 SRAM area, but only for LLC-specific **0.1-100 s retention targets**.
The same study uses the low-drive IGZO FET as the **read selector** and retains a silicon write transistor, whose available fins must supply the SOT switching current; the IGZO selector costs as much as 3-5 ns of read latency. It therefore supports a hybrid silicon-write/oxide-read cell, not two CAAC-IGZO access transistors and not a free latency reduction.
CAAC-IGZO's extremely low reported off current, around 10^-22 A/um, is valuable for a selector, but **"Charge Trapping and Emission Properties in CAAC-IGZO Transistor"** (*Materials* 2023, [DOI](https://doi.org/10.3390/ma16062282)) also records threshold-voltage drift under bias stress from charge traps and oxygen vacancies. Low static leakage is not equivalent to high write drive, fixed timing, or side-channel silence.

**Why the wholesale form is declined: it does not delete as much mechanism as it first appears to.**
The switch to SRAM was made on the *scarce* axis (trust and proof surface): it *deletes* the refresh, refresh-management, per-row-activation-counting, and reactive-back-off machinery, and the RowHammer charge-disturbance primitive with them, accepting lower capacity and higher idle leakage on the *free* (engineering) axis as the honest price (above).
SOT-MRAM matches the refresh and RowHammer deletion and additionally removes most array-retention power, a genuine simplification. It does not remove ECC, bank scheduling, fault containment, reset, or persistence machinery, and encrypting every retained working-memory line adds a fixed cipher stage the SRAM path deliberately lacks.

**Objection 1: banking recovers throughput, not the serial latency the cacheless core exposes.**
Layered independent banks can approach the sum of their bandwidths when the instruction stream presents enough independent requests; vectors, DMA, streaming, and multiple cores can exploit that, and the static memory plan already spreads concurrently-live objects across assigned banks for exactly this reason (§8, §15).
A dependent load, instruction fetch, or pointer chain still pays array access plus sensing plus ECC plus line cryptography plus fabric latency. The 128 Kb chip's 15 ns read is excellent for an emerging NVM and materially slower than the flat SRAM path this in-order, cacheless machine was designed around; no number of idle neighboring banks shortens that dependency.
Parallel writes also add their SOT currents, causing IR drop, supply noise, and localized heating. A deterministic implementation therefore needs a composition-fixed simultaneous-write limit per bank and tier, booked into WCET and bandwidth; an activity-driven limiter, write combiner, or adaptive pulse shaper would recreate the reactive hidden state the proposal hoped to remove.

**Objection 2: 2T, CAAC-IGZO, ECC, and encryption do not compose into side-channel absence.**
The 2T cell removes read disturb and decouples the two electrical paths; it does not hide the MTJ resistance being sensed, the polarity and magnitude of the SOT write, the selected address, or the bank and power-rail contention they create.
**"Comprehensive Study of Side-Channel Attack on Emerging Non-Volatile Memories"** (Khan and Ghosh, *JLPEA* 2021, [DOI](https://doi.org/10.3390/jlpea11040038)) validates on commercial NVM chips that observed read/write supply current can recover an AES key; **"Fault Injection Attacks on Emerging Non-Volatile Memory"** (Khan et al., HASP 2018, [DOI](https://doi.org/10.1145/3214292.3214302)) shows data-dependent writes can create exploitable voltage droop and polarity faults; and **"Security Evaluation of a Hybrid CMOS/MRAM Ascon Hardware Implementation"** (DATE 2023, [DOI](https://doi.org/10.23919/DATE56975.2023.10137126)) finds that MRAM hybridization does not significantly reduce the differential- or correlation-power-analysis feature against its CMOS reference.
Those results are not a direct fabricated CAAC-IGZO 2T SOT array attack, and that absence cuts against the security claim rather than for it: the reviewed literature contains no experimental result establishing that the proposed four-layer combination suppresses power or electromagnetic leakage.
ECC corrects or detects bounded faults; it conceals no current, timing, address, or access pattern. Encryption hides retained plaintext after key loss; its own cipher is a side-channel target and it leaves access patterns visible. Only fixed-latency implementation, static bank isolation, masking or a proved leakage discipline, and physical measurement can close those channels.

**Objection 3: magnetic-field fault injection and thermal attack are a new physical surface the enclosure does not cover.**
External-magnetic-field fault injection and denial of service have been demonstrated experimentally on commercial MRAM, and retention is temperature-dependent, so a thermal attack is a further vector.
The design's Faraday enclosure (§15) attenuates *time-varying* electromagnetic fields through induced eddy currents, but a *static or low-frequency magnetic* field passes through a conductive shell largely unattenuated (blocking it needs high-permeability ferromagnetic shielding, a different and heavier measure), so MRAM adds a physical-fault and denial-of-service surface the SRAM design does not have and the existing enclosure does not close: a new §17 residual.

**Objection 4: encryption can emulate confidentiality after power loss, but it neither restores volatility nor turns an SSD engine into a memory controller.**
A per-boot, non-persisted working-memory key can provide **cryptographic volatility**: every MRAM line remains ciphertext at the cell, reset or lock destroys the key, and reboot clears every CHERI tag before any line can become authority again. This is a real answer to plaintext remanence, not a contradiction in terms, and it preserves the idle-power reason to use MRAM even though the old working set becomes unrecoverable.
It is narrower than physical volatility. Ciphertext, addresses, equality and access history, ECC words, and magnetic domains remain; key compromise can recover retained data; and a stale native CHERI tag or capability graph must never survive merely because its bytes decrypt. The working region therefore needs a fresh epoch key and a mandatory tag-plane reset, while the persistent region must carry no live capability tags at all and must reconstitute authority only through the measured storage reader.
The SSD cryptographic *primitive* can be shared, but not its protocol. Sector encryption tolerates storage latency and large blocks; random-access main memory needs fixed-latency line tweaks and enough replicated throughput for every fetch, load, store, vector access, and DMA beat. If active splicing and replay are in scope, it also needs persistent counters, MACs, and integrity-tree roots.
**"Streamlining Integrity Tree Updates for Secure Persistent Non-Volatile Memory"** (Freij et al. 2020, [arXiv](https://arxiv.org/abs/2003.04693)) shows why those are storage state rather than free encryption metadata: data, counter, MAC, and Bonsai-Merkle-tree updates must persist atomically for crash recovery, and prior work substantially underestimated the tree-persistence cost.
The one-medium proposal must therefore choose between two meanings of "unified." A common fabricated medium is compatible with explicit volatile-semantic and persistent partitions. A **single-level store** that makes ordinary working memory durable dissolves the crash-only reset, eager initialization, capability-revocation, and explicit storage-refinement boundaries already rejected in the Historical capability-machine and Object Memory Architecture entries above.
[Twizzler](https://www.usenix.org/conference/atc20/presentation/bittman) supplies the steelman for the latter (*USENIX ATC* 2020: under 0.5 ns added persistent-pointer latency, operations up to 13x faster than Unix, and SQLite queries up to 4.2x faster than PMDK), but its result demonstrates the value of a different persistence model; it does not make persisted execution state or authority compatible with this one.

**The scale gap decides SSD removal separately from main-memory substitution.**
The strongest concrete chip result above is 8 Mb, and at a relaxed 110 nm node; 1 GiB is 2^10 times larger in bit capacity, and replacing a conventional hundreds-of-gigabytes SSD adds several more orders of magnitude before native CHERI tags, ECC, authentication tags, counters, spare rows, and yield repair.
The 2025 selector study projects SRAM-class *area* at short LLC retention, not storage-class retention or NAND-class density. The reviewed literature demonstrates [200 mm manufacturing integration](https://doi.org/10.1088/1674-4926/43/10/102501), [300 mm array integration](https://doi.org/10.1109/VLSITechnologyandCir46783.2024.10631340), and megabit-class arrays, with foundry engagement now at array-level research silicon but still no offered embedded option (TSMC's line has advanced from a [stated sub-2 ns cache exploration](https://research.tsmc.com/page/mram/5.html) to a [64-kb BEOL-compatible β-tungsten macro with embedded CMOS control and 1 ns switching](https://www.nature.com/articles/s41928-025-01434-x), *Nature Electronics* 2025, plus a field-free 8 kb array at IEDM 2025; the four foundry embedded-MRAM offerings remain STT), not the dozens or hundreds of independently addressed magnetic tiers that would make a 2T-per-bit medium compete with 3D NAND.
Monolithic stacking remains a credible direction because the MTJ and oxide selector are back-end-compatible, but every tier compounds routing, yield, thermal removal, and write-current delivery, while the 2026 endurance result identifies write heating itself as the failure driver. Removing the SSD is consequently a later and much harder capacity milestone than replacing the large SRAM arrays.

**A further reliability upside does not settle the system decision.**
The magnetic storage element is relatively immune to the charge-based single-event upset that flips an SRAM or DRAM cell (a particle strike does not overturn a magnetic domain the way it dumps charge in a capacitor or a latch), and this is the likely kernel of truth behind the *stronger attack resistance* premise.
But the peripheral CMOS around the array is still upset-susceptible, that immunity is traded for the magnetic-field fault surface objection 3 names, and the design already meets the single-event-upset threat with pervasive SECDED and DECTED ECC, scrubbing, fault containment, and a radiation-hardened silicon realization where the deployment warrants it (§15, §16, and the space-grade realization entry above), so it needs no upset-immune storage element to buy.
The real upside is already covered, and it arrives bundled with a worse new surface.

**The distilled atom is physical-medium substitution with semantic separation.**
The new evidence makes "reject MRAM" too coarse. The admissible atom is to replace the *large* SRAM cell arrays with statically banked 2T SOT-MRAM while preserving every architectural boundary the SRAM design used: no persistent execution state, no capability-graph checkpoint, eager reinitialization, explicit storage transactions, and fixed timing.
The same die may then contain a working region encrypted under a per-boot ephemeral key and a persistent region holding only ciphertext extents and storage metadata under long-lived volume keys. They may share qualified AES/GHASH datapaths and fabrication steps; they do not share keys, retention targets, CHERI-tag semantics, or commit protocols.
Tiny cycle-critical arrays, register files, FIFOs, reset state, and the immutable boot/root material remain flops, SRAM, ROM, OTP, or dedicated monotonic state as appropriate. "Only MRAM" is not a realizable security boundary, because the key and boot root needed to interpret encrypted MRAM must exist before that interpretation begins.

**The rest of the non-volatile class inherits the decisive strike: FeRAM and ReRAM.**
The reasoning above is not specific to the magnetic junction; it is about non-volatility on the working set, so the other main-memory-candidate non-volatile memories fail the same way, each carrying its own extra disqualifier.
Ferroelectric RAM, which stores a bit as the polarization of a ferroelectric capacitor, is *strictly weaker than MRAM here*: it carries the identical non-volatility remanence strike (objection 4), and it swaps the magnetic-fault surface for a *thermal* one (polarization is erased past the Curie temperature, a documented depolarization and fault-injection vector, with electric-field and imprint attacks alongside, so objection 3 recurs in a flavor the enclosure still does not cover).
And it adds two problems MRAM does not have: its density is the *worst* of the class (the ferroelectric capacitor scales poorly, so commercial FeRAM tops out in the megabit range, orders of magnitude below a usable main store, which disqualifies it as main memory before the security axis is even reached), and its read is *destructive* (sensing depolarizes the cell and forces an immediate restoring write, turning every read into a read-modify-write, with the wear and the read-coupled write-timing that implies).
Its one genuine edge over STT-MRAM and ReRAM, very high and low-power write endurance, is less decisive now that optimized SOT arrays demonstrate cache-class endurance; and it remains moot for the small persistent security state, whose write rate is already too low to wear even flash (the monotonic counters advance on signed updates, key rotation, or authentication attempts, never on a data commit, and the time floor persists rarely, §9, §10).
The **ferroelectric field-effect transistor (FeFET)** is that same ferroelectric physics moved into the transistor gate rather than a separate capacitor, and it is the form the *non-volatile SRAM* proposal takes: embedded in the 6T cell it adds non-volatility with no extra transistors, and because the ferroelectric is touched only on a store or restore, not on every access, it keeps the volatile cell's active speed and dodges FeRAM's destructive read, promising a *power-gate-to-zero* standby that would beat retentive gating on idle power; the line has first silicon (a 28 nm fabricated FeFET 6T nvSRAM, 2026), so it is research-stage rather than hypothetical.
It is declined for the strike that survives all of that: the state it preserves across power-off is exactly the remanence the switch to SRAM deleted (the non-volatility strike, objection 4, and the hybrid below), it inherits the ferroelectric thermal, Curie, and imprint fault surface (objection 3), and the idle-power edge it claims over retentive gating is bought *with* that remanence, whereas retentive gating keeps the state in the *volatile* latch at low leakage and so takes most of the same idle-power win without it (the low-leakage entry above).
Resistive RAM, which stores a bit as the resistance of a switchable metal-oxide filament, is the denser and more tempting of the two (density is *not* its disqualifier), but it carries the same non-volatility strike and the same axis inversion, its filament set and reset writes are asymmetric, variable, and partly stochastic (objection 2 returns as a data-dependent write timing and power channel), and its limited endurance can require the wear-remapping machinery optimized SOT-MRAM may avoid.
Decisively, the design's own anti-features already place it: binary ReRAM is admitted *only* as deterministic storage below the §10 integrity line, never as main memory, and the analog ReRAM crossbar (compute-in-memory) is rejected outright (§15), so ReRAM as a main store sits on the far side of a line the spec has already drawn.

**The admissible gen-2 shape and its trigger.**
The strongest form is neither a transparent SRAM/SOT cache hierarchy nor a single-level store. It is a **physically common, semantically partitioned substrate**: small volatile structures stay close to the core; large working banks become 2T SOT-MRAM with fixed-latency ECC and per-boot line encryption; persistent banks carry no live CHERI tags and remain behind the existing per-extent AEAD, CoW, and crash-recovery interface; retention and write-current classes differ by bank; CAAC-IGZO is considered first as a read selector while silicon supplies write current; and bank/tier arbitration plus simultaneous-write limits are fixed at composition.
That shape imports the idle-power and stacking atom without importing transparent persistence, dynamic tiering, wear remapping, or a persisted authority graph. It is a memory-technology substitution beneath the abstract machine, not a new memory model.

It remains deferred because the evidence is separated by five orders of array capacity and because every result that closes one corner loosens another. Re-open it only when one integrated demonstrator simultaneously establishes: (1) the composition-sized working-memory capacity with native CHERI tags, ECC, spares, and acceptable yield; (2) fixed read and write latency including line crypto and the longest retention class; (3) a static simultaneous-write envelope closing IR-drop, thermal, endurance, and WCET bounds; (4) measured power and electromagnetic leakage plus magnetic, voltage, and thermal fault behavior on the actual 2T SOT/selector stack; (5) tag clearing and ephemeral-key destruction across every reset and lock transition; and (6), before SSD removal separately, persistent capacity, decade-class retention, atomic crypto-metadata recovery, and multi-tier manufacturability.

**Disposition:** reject the wholesale **all-CAAC-IGZO, all-SOT-MRAM single-level store** as the base, and keep bespoke volatile SRAM normative (§15).
Defer **large-array 2T SOT-MRAM substitution with semantic separation** as a gen-2 proof-aware design-space candidate behind the six measured triggers above; it is no longer rejected on the obsolete claim that all MRAM necessarily needs wear leveling, but within the capacity class it ranks second. The oxide-semiconductor gain-cell candidate of the next entry reaches the same idle-power and stacking atom without non-volatility, a line cipher, or the magnetic fault surface, but its bounded power-off remanence still requires explicit reset-time tag invalidation and pre-admission sanitization.
FeRAM, ReRAM, and ferroelectric-FET non-volatile SRAM remain rejected as main memory for their separate device and remanence grounds; removing the SSD remains a later capacity decision, not a consequence of admitting SOT working memory.
Non-normative; no spec-body change.

---

## Oxide-semiconductor gain-cell (2T0C) working memory: eventually volatile, n-type-only, with a composition-scheduled refresh obligation; first-ranked dense-class candidate

The proposal closes a design space the entry above opens and does not finish.
Every capacity-class candidate weighed there is non-volatile, and each buys its idle-power win at the same three counters: the remanence strike (objection 4), a per-boot line cipher to emulate the volatility it surrendered, and a new physical fault surface the enclosure does not cover (objection 3); on the other flank, every dynamic leakage lever is declined as reactive machinery (the low-leakage entry above, R-15-189h).
Neither family occupies the remaining quadrant: an **eventually volatile, charge-based, back-end-stackable cell whose worst-corner retention is long enough for refresh to be a fixed, composition-scheduled sweep rather than a demand-driven controller**. Its reset semantics, however, cannot depend on waiting for that charge to decay.
That quadrant has an occupant, and the design has already vetted its device: the **two-transistor, zero-capacitor (2T0C) gain cell** in oxide-semiconductor (a-IGZO / CAAC-IGZO) transistors, the same device class the entry above admits as a read *selector*, here promoted to the cell itself.

**The device, and the evidence for it.**
A 2T0C cell stores the bit as charge on the read transistor's gate node, written through a write transistor and sensed through the read transistor: no capacitor, no shared storage node, and a **non-destructive read** on a path separate from the write.
The oxide channel makes the geometry work twice over: its off current, reported around 10^-22 A/µm and below 1 aA/cell in fabricated form, *is* the retention mechanism, and its low deposition temperature is precisely the back-end-of-line constraint sequential 3D imposes (§15).
The published trajectory: imec's [first functional 2T0C cell at >400 s retention](https://www.imec-int.com/en/press/imec-demonstrates-capacitor-less-igzo-based-dram-cell-400s-retention-time) (IEDM 2020), then [>10^3 s retention, >10^11 read/write cycles, and <10 ns writes](https://www.imec-int.com/en/articles/capacitor-less-igzo-based-dram-cell-excellent-retention-endurance-and-gate-length-scaling) (IEDM 2021), then [retention beyond 4.5 hours](https://www.imec-int.com/en/articles/disrupting-dram-roadmap-capacitor-less-igzo-dram-technology); a [dual-gate cell at ION = 1500 µA/µm](https://ieeexplore.ieee.org/document/10019488/) (IEDM 2022); a [stacked two-layer vertical channel-all-around bit-cell at 4F² effective area](https://www.researchgate.net/publication/378064875_First_Demonstration_of_Stacked_2T0C-DRAM_Bit-Cell_Constructed_by_Two-Layers_of_Vertical_Channel-All-Around_IGZO_FETs_Realizing_4F_2_Area_Cost) (IEDM 2023); an [8×8 monolithic multi-deck array](https://doi.org/10.1126/sciadv.adu4323) (*Science Advances* 2025); and, decisive for who funds the maturation, [Kioxia and Nanya's OCTRAM](https://www.kioxia.com/en-jp/rd/technology/topics/topics-77.html) (IEDM 2024), a 4F² DRAM on an IGZO vertical transistor at >15 µA/cell on current and <1 aA/cell off current, extended at [IEDM 2025 to 8-layer-stacked oxide-channel transistors](https://www.kioxia.com/en-jp/about/news/2025/20251212-1.html) formed by a NAND-like stack-and-replace flow (3D OCTRAM): the commodity DRAM roadmap itself moving onto the oxide channel (Samsung's 4F² vertical-channel working die targets 2028 production, and both major DRAM roadmaps name IGZO as the leakage-reduction channel), where every candidate in the entry above matures on a boutique one.

**Run against the strikes this document actually uses, it clears the ones the non-volatile class cannot.**
- **Eventual physical volatility is preserved, but reset semantics never wait for natural discharge.** A 2T0C gain cell stores charge rather than a non-volatile material state, so its contents eventually decay after power loss; at an hours-scale retention corner, however, a short power interruption can restore the machine while old data and old capability-validity bits remain physically readable. “Volatile” therefore names the medium's eventual endpoint, not the reset invariant. No epoch-key or line cipher is owed, but **immediate authority invalidation and pre-admission sanitization are owed**.

  On every cold boot, watchdog reset, deep-sleep wake, and OFF→ON transition involving a gain-cell domain, the RoT holds all application cores, DMA engines, and capability-bearing fabric initiators in reset. Before any requester can name the domain, the implementation establishes both of the following, in order:

  1. **Authority is gone:** every capability-validity tag associated with the domain is known clear, independently of the data cells' discharge state and independently of any restarted revocation epoch.
  2. **Residue is inaccessible:** the data plane is deterministically cleared, or its active discharge is confirmed complete, before the domain is admitted to measured execution or delegated by the static memory plan.

  Resetting the capability epoch alone does not satisfy the first condition: an ordinary tagged-memory capability need not carry that epoch, and a retained native tag could otherwise resurrect an old authority graph. Eventual charge decay does not satisfy the second condition: measured execution must never observe retained plaintext merely because power returned inside the remanence window.

  A gain-cell macro is admissible only with one of three reset constructions, selected and verified for the realized macro:

  - **Volatile SRAM tag sidecars:** gain cells retain the data plane, while one validity bit per 64-bit granule and its DECTED protection reside in a fast-decaying SRAM tag plane guaranteed clear on loss of the macro supply. The tag plane is read and committed atomically with the gain-cell data and is checked clear before the data plane is addressable. This is the preferred construction: retained stale bytes become inert integers as soon as their authority bits disappear, at the cost of the tag plane and its ECC rather than an authority-critical clear of the dense data array.
  - **Reset-time tag-plane clearing:** the RoT keeps every requester reset while a fixed-latency sweep clears and verifies every tag bit in the gain-cell domain. Data sanitization remains a separate admission step.
  - **Confirmed active discharge:** every bank carries a deterministic bleed path that discharges both data storage nodes and any native gain-cell tag storage; the RoT admits the bank only after a fail-stop completion indication. Timeout halts the transition and exposes no retry-dependent timing.

  In all three constructions, tag invalidation is the first security boundary and full sanitization is the later confidentiality boundary. A failed or incomplete tag clear, data clear, or discharge is a fail-stop reset failure; it never releases a partially sanitized bank.
- **Refresh and ECC scrub may share an engine and schedule, but they discharge independent obligations.** Conventional DRAM's tens-of-milliseconds retention forces an autonomous distributed refresh engine with activation-counting and reactive back-off; that machinery remains absent. At the gain cell's minutes-to-hours worst corner, one fixed, composition-sized, data-independent sweep engine may perform both maintenance functions, but the proof establishes two postconditions separately:

  - **Scrub postcondition:** every visited codeword is correct after read-correct-write, or the machine raises a fail-stop uncorrectable-ECC event.
  - **Refresh postcondition:** every data cell and every tag cell is successfully rewritten before its characterized worst-corner retention deadline, even when scrub finds no error.

  Data, tag validity, and their ECC commit atomically at the granule. A failed refresh write may not leave an old valid tag over data whose rewrite did not complete; the granule's tag is cleared or the domain fails stop. The cadence is a worst-thermal-corner build constant, never demand-triggered, counted from accesses, or current-sensed.

  Refresh-current shaping is part of the same static power contract. Bank phases are fixed and staggered by the composition-time schedule, with the simultaneous-refresh set admitted against voltage-droop, thermal-coupling, and power-signature limits. A temporally public sweep is not permission to refresh every bank at once.
- **No activate/precharge/restore cycle.** The gain-cell read is non-destructive through its own transistor, so fixed-latency random access is realizable and the DRAM timing objection does not transfer; and the classic RowHammer mechanism, repeated wordline activation coupling charge out of *neighboring storage capacitors*, has no direct analog on a gate-node cell read through a separate path. That is an argument rather than a measurement, stacked decks having disturb modes of their own, and the trigger list below demands the measurement.
- **n-type only: it unlocks the branch where the SRAM realization loses the vertical lever.** The 6T tier stack is hostage to array-grade *complementary* back-end devices, the latch's two pFETs being irreducible (the bitcell entry above; R-15-163's binary gate), which is why R-15-173a's pessimistic branch collapses capacity to the planar tier at 1-2 GB. A 2T0C cell contains no pFET at all. At ~4F² per deck against a 6T footprint tens of times larger, one oxide deck outweighs several hypothetical SRAM tiers before multi-deck stacking is even counted, directly against the R-15-170 budget and the R-15-171 floor.
- **The density claim is a cell/deck claim until a repaired macro proves otherwise.** Approximately 4F² describes the demonstrated bit-cell geometry, not achieved system-memory density. Sense amplifiers, word-line drivers, refresh and reset logic, tag columns and their DECTED protection, data ECC, spare rows, yield repair, vertical vias, and bank routing all consume area and may materially reduce the headline advantage. Capacity claims therefore use measured usable density from a megabit-class repaired macro carrying the complete tag, ECC, refresh, discharge, and routing overhead; “tens of times denser” is not an architectural input before that trigger closes.
- **The leakage claim needs no new mechanism.** Sub-aA off current takes the large arrays' standby draw toward periphery-only, and the whole R-15-189 gating apparatus (states, vectors, clears, discharge confirmation) carries over unchanged; it simply has less to gate.

**The objections are real, and they shape the admissible form rather than defeating it.**
- **Read latency is the weak axis, and as a universal substitution it fails R-15-164 exactly as MRAM does.** Low channel mobility and single-ended sensing put array reads in the ~10 ns class, the same order the entry above holds against the 15 ns MRAM read. The admissible form is therefore **not substitution but a second static latency class**: bespoke SRAM remains normative for the scalar working set and every cycle-critical array, and gain-cell decks carry bulk, framebuffers, images, model weights, vector and matrix extents, and code under static placement, assigned at composition by the same static memory plan that already assigns banks (R-08-012a) and entering §11 as two fixed constants. No cache, no migration, no tiering, no wake-on-access: the static-management shape the overlays entry above accepts and the "physically common, semantically partitioned" atom the entry above distills, with volatility kept.
- **Vth drift under bias stress**, the CAAC-IGZO charge-trapping caveat the entry above records, applies to the cell itself; a drifting read threshold is a sense- and retention-margin item qualification must bound.
- **Multi-bit is declined outright.** The literature's extra density multiplier is analog, data-dependent margins, the same ground the analog compute-in-memory crossbar is rejected on (§15). One bit per cell.
- **Temperature-dependent retention** is met by the worst-corner cadence, never by sensing (R-15-189h); the residual is that a thermal adversary narrows margin toward the fixed cadence, backstopped by the same fail-stop ECC discipline (R-15-177) and named rather than waved off.
- **Maturity is lab-scale.** The multi-deck array demonstration is 8×8 and the two-layer bit-cell is a bit-cell, so the capacity gap to a composition-sized working set is as wide as SOT-MRAM's recently was. What differs is the closer: the oxide access transistor is the DRAM industry's own scaling direction, so the device matures on commodity funding either way.
- **Side channels stay in SRAM's class on one axis and regress on another, and the regression must be named.** There is no magnetic-field or Curie-point surface, so the enclosure gap objection 3 opens against MRAM and FeRAM does not open here, and the leakage-power-analysis residual keeps the shape already booked for SRAM (the bitcell entry above) under R-17-058a's scoping unchanged. But the gain-cell read is single-ended, so it sits on the unbalanced side of the read-power ledger that entry draws: the fetched word's Hamming weight is a first-order read-current term, a regression against the 6T differential read, booked under the same physical-scope line that declines to count any such attenuation or exposure as a platform mechanism.

**Where it ranks: first in the capacity class, beside rather than against the SRAM it does not replace.**
Against the deferred SOT-MRAM shape it dominates on the axes this design counts: eventually physically volatile rather than cryptographically volatile (bounded power-off remanence, but no line cipher or epoch-key protocol), no new §17 magnetic fault surface, capacitive gate-node writes in place of SOT current pulses (no IR-drop and thermal write envelope, no write-heating endurance driver), and commodity-roadmap maturation.
It concedes the scheduled sweep, whose shape the platform's scrub machinery already owns, and an idle-power floor that is comparable rather than superior.
The fast class stays SRAM by construction.

**Disposition:** keep bespoke volatile SRAM normative (§15) as the sole fast class; log **oxide-semiconductor 2T0C gain-cell decks as the first-ranked gen-2 dense-class candidate**, ahead of the SOT-MRAM deferral above, admissible only as a second static latency class with composition-time placement and one bit per cell.
Re-open behind measured triggers of the same kind the entry above sets: (1) a megabit-class monolithic multi-deck repaired macro reporting **usable macro density**, with tag plane, data and tag ECC, sense periphery, refresh/reset logic, spares, routing, and yield repair included; (2) fixed read and write latency at the macro, sense path included, across the retention corner; (3) disturb characterization on the actual stacked array, including any stacking-borne analog of RowHammer; (4) Vth drift bounded under the composed bias profile over deployment life; (5) separate scrub-coverage and refresh-deadline proofs for the shared sweep engine, with bandwidth booked against the §11 slot classes and RETAINED accounting of R-15-189k; (6) a statically staggered refresh-current envelope closing voltage-droop, thermal-coupling, and global power-signature bounds; and (7) reset behavior across a short power interruption inside the measured remanence window, demonstrating immediate tag invalidation by one of the three admitted constructions and deterministic data sanitization or confirmed discharge before the domain is exposed.
Non-normative; no spec-body change.

**Honest residual (§17):** the hours-scale retention that makes refresh cheap is also an hours-scale power-off remanence window. Eventual decay makes the medium physically volatile, but no reset guarantee depends on that decay completing. Across a short power cycle, stale bytes may remain; they are required to lose authority immediately through verified tag invalidation and to remain unreachable until deterministic sanitization or confirmed discharge completes. Until that sequence is demonstrated on the realized macro, gain-cell memory is not admissible even as a gen-2 dense class.

---

## Gate-all-around on the acting logic tier and exotic successor devices: declined

Gate-all-around and CFET improve density but make vertically stacked device geometry harder to resolve from one backside image, increase self-heating, and arrive in the same process regime as backside power delivery.
On the tier containing the RoT, cores, capability fabric, and memory controller, that trades the scarce physical evidence against the fab residual for logic density the design does not need.
Backside power is independently disqualifying because opaque metal blocks IRIS's optical path; with the first backside-power node entering production (TSMC A16, late 2026) and the failure-analysis literature itself recording that backside metallization defeats near-infrared fault isolation, the refusal is a live divergence from the mainstream roadmap rather than an anticipatory one.

2D-material logic, tunnel FETs, and carbon-nanotube FETs remain research references: complementary materials, contacts, variability, and reliability are unresolved, while tunnel FETs also surrender the active-memory speed premise.

**Disposition:** decline GAA/CFET on the bottom acting logic tier, refuse backside power delivery, and do not base the design on 2D, tunnel-FET, or CNT logic.
The tier-graded use of dense devices is documented in [Inspirations & Prior Art](inspirations.md).

---

## Wide-bandgap logic substrates and substrate-based reconciliation with backside power: declined

No transparent substrate makes backside power compatible with optical inspection: the occluder is the opaque metal grid, not silicon, which is already transparent at the infrared wavelengths IRIS uses.
Silicon-carbide-on-insulator offers a wider optical window and strong radiation and temperature tolerance, but it has no mature dense complementary-CMOS process suitable for an application-class CHERI core.

**Disposition:** decline silicon-carbide-on-insulator as the logic substrate and reject the claim that any substrate choice reconciles a dense backside power network with backside inspection.
The SOI realization actually selected is documented in [Inspirations & Prior Art](inspirations.md).

---

## Logic-over-logic die stacking and an alternative inspection suite as an IRIS replacement: declined

Nano-CT, lock-in thermography, TDI, dark-field inspection, acoustic microscopy, virtual in-line metrology, and BIST were evaluated as a way to recover assurance after logic is buried in a 3D stack.
Only Nano-CT supplies structural evidence through the stack, and it trades resolution, field of view, and throughput; the others are interface, surface, behavioral, statistical, or readout techniques that a dormant malicious addition can evade.
Stacking separately fabricated logic also multiplies dies, mask sets, fab sources, and hidden interfaces while deleting the backside optical path.

**Disposition:** do not stack acting logic over logic and do not treat this defect/reliability suite as a substitute for IRIS on the logic tier.
Its bounded role on passive monolithic memory tiers is documented in [Inspirations & Prior Art](inspirations.md).

---

## Reversible and adiabatic computing: the recoverable energy is real and is not what "reversible" names, and the machine it would be recovered on is leakage-bound

The proposal deserves a fresh reading rather than a reflex, and it deserves it on this design's own terms: a machine that has already deleted speculation, caches, virtual memory, and simultaneous multithreading has spent so much of the conventional performance budget that one more unconventional substrate looks cheap, and the energy claim in the literature is not small.
It is refused, and the reason is not the side-channel objection the proposal expects to have to answer.
**The refusal turns on the proposal being four levers sold as one**, on the fact that the lever carrying the name is the one buying the least here, and on a collision with erasure that this design cannot absorb.

**The four levers, stated apart, because they have different physics, different costs, different retrofit paths, and different answers.**
(1) **Architectural reversibility**: a bijective *instruction set*, so a program runs backwards and no uncompute log is needed; this is what "reversible computing" names in the architecture literature, and it is the only lever that touches the ISA.
(2) **Gate-level reversibility**: local invertibility inside the logic, whether by a reversible cell family or by Bennett clocking's compute-then-decompute cascade; it is invisible above the RTL.
(3) **Adiabatic charge recovery**: driving nodes from a ramped or resonant power-clock rather than a step supply, so the *CV²*/2 charging energy is returned instead of dissipated; this is what recovers energy in every measured result.
(4) **Resonant clock distribution**: applying (3) to the clock network alone, leaving logic style, supply, and architecture untouched.
The coupling is between (2) and (3) and not where the name suggests: deep recovery *does* require gate-level reversibility, because an adiabatic gate that destructively overwrites its output dumps the stored charge non-adiabatically, which is why the fully adiabatic families are locally invertible and retract.
(1) is separable from all of it. Its function is to avoid the logging and decompute overhead of running an irreversible program on reversible hardware, which is an efficiency constant, not an enabling condition, and it is a precondition only for operating *below* the Landauer floor of *kT* ln 2 (about 2.9 zJ at 300 K).

**Landauer is not the binding constraint at any point this machine will occupy, so the lever named "reversible" buys the least.**
The floor is about 2.9 zJ per erased bit; a modern switch dissipates hundreds of *kT* at the transistor and far more once interconnect is counted, and [Limits to the Energy Efficiency of CMOS Microprocessors](https://arxiv.org/abs/2312.08595) puts shipping parts roughly 200 times off a first-principles CMOS ceiling that is itself set by interconnect capacitance and leakage rather than by Landauer.
Frank and Edwards' [Industry perspective: Limits of energy efficiency for conventional CMOS and the need for adiabatic reversible computing](https://doi.org/10.1063/5.0279617) (*APL Electronic Devices* 1(3), 030902, 2025) is the strongest recent statement of the case and it is honest about the same ordering: what stalls conventional CMOS is the potential-energy difference a reliable field-effect switch needs, and the answer offered is *adiabatic* operation, with reversibility as the discipline that keeps adiabatic operation coherent at scale rather than as the term that supplies the joules.
A design four to five orders of magnitude above the erasure floor does not need to stop erasing. It needs to stop dissipating what it charges, which is lever (3).

**Lever (3) buys energy with time, and this machine's energy is not dominated by the term that would be bought.**
Adiabatic dissipation scales as roughly *RC*/*T* per transition, so an order of magnitude of recovery costs an order of magnitude of transition time, and the recovery does not run away: leakage energy grows with the same *T*, so total energy admits an optimum period from d*E*/d*T* = 0 and rises again past it.
That optimum is where the whole case lands here, because **this design is leakage-bound by construction and by its own admission**: main memory is bespoke on-die SRAM whose retention leakage is named as the admitted price of the choice (R-15-189b, §15), the mitigations already taken are the *static* cell and circuit levers, and the dominant deployment state is a standby mode whose draw is retention rather than switching.
Adiabatic logic recovers dynamic switching energy in the *logic*, which is the minority term on a die that is mostly array, and it pays for that recovery in cycle time, which multiplies the leakage term that is the majority one.
The published measurements sit exactly where that argument predicts: [EE-SPFAL](https://doi.org/10.1109/TETC.2016.2645128) reports average energy saving falling from 76.5% at 100 kHz to 21.3% at 25 MHz against static CMOS, and its evaluation targets are RFID tags and smart cards.
The fully adiabatic families are explicit about the time price on the other axis too: [S2LAL](https://arxiv.org/abs/2009.00448), the first fully static and truly fully adiabatic CMOS family, needs 8 phases of a trapezoidal power-clock and a minimum initiation interval of 8 ticks against one tick of stage latency.

**The silicon evidence is a test chip, and the roadmap's factor rests on a component that does not exist yet.**
Vaire Computing's *Ice River* (22 nm, 2025) is the first net energy recovery demonstrated for an adiabatic system in a commercial foundry process, and what it demonstrates is an on-chip resonator driving a capacitor array at an energy-recovery factor of 1.77 and a shift register at 1.41, roughly 50% average recycling.
That is a real result and it is a resonator, a capacitor array, and a shift register, not a core; the widely quoted 4000-fold figure is a ten-to-fifteen-year projection contingent on integrated MEMS resonators reaching 99.97% recovery, a figure that remains unmeasured; a second tapeout shifted toward logic and competitive PPA carries no published measurement, and the company remains seed-stage.
By the standard this document applies to gate-all-around, tunnel FETs, and carbon-nanotube logic, adiabatic logic at application-core scale is in the same category: a research reference, not a substrate to base a design on.

**The side-channel question, answered in the direction the proposal hopes for, and it still discharges nothing.**
The literature is genuinely favorable and it should be said plainly: adiabatic charging reduces d*V*/d*t* and d*I*/d*t*, which lowers switching noise and radiated emission; [Investigating the DPA-Resistance Property of Charge Recovery Logics](https://eprint.iacr.org/2008/192) found 2N-2N2P charge-recovery logic improves DPA resistance while consuming less power than the standard CMOS circuit, the first countermeasure style to do both; and the purpose-built secure families ([Secure Adiabatic Logic](https://eprint.iacr.org/2008/123), [charge-sharing symmetric adiabatic logic](https://doi.org/10.1016/j.mejo.2013.04.003), EE-SPFAL) equalize per-cycle energy deliberately.
None of that reaches the position this design actually holds.
Every constant-time obligation here is stated against the ratified `Zkt`/`Zvkt` architectural leakage model, and instantaneous power draw and near-field emission are *outside* that model; what answers them is the crypto core's masked datapath with its theorems over the conferred probing-model statement (R-05-004a, R-15-053a, R-17-058a, §17), so there is no theorem for a logic style to improve: a quieter rail narrows nothing the masking theorems do not already carry and states nothing where they do not reach.
Worse, a DPA-resistance claim carried by a logic family is an assumption about the silicon with no statement verified over it, which is precisely what R-17-058a books as the masking construction's one open cost: adopting adiabatic logic *for security* would import a second such axiom while adding a bespoke cell library and no theorem, and a leakage claim verified against a physical model the die does not satisfy is the crown-jewel failure mode one layer down.
**And the resonant rail cuts against a guarantee this design does hold.** The power-clock is supply and clock at once, shared across everything it drives, and its recovery factor is a function of the total capacitance actually switched; that makes tank amplitude and phase an activity-dependent global observable, which is a new coupling term against island power isolation (R-15-189m, §15), whose current channel analysis is short precisely because a domain's power state is a function of the public mode index alone.
Per-island resonators restore the separation and multiply the inductors; the tank is also narrowband, which sits badly with a small set of pre-proved operating modes.

**Levers (1) and (2) collide with erasure, and erasure is load-bearing here rather than incidental.**
The overstated form of this objection should be set aside first: a reversible machine is not forbidden to erase. Real ones erase at chosen points and pay Landauer there, so "cannot destroy information" is false as stated.
**What is true is that the default inverts, and the default is what this design's proofs are written against.**
Under Bennett's compute-copy-uncompute, and under the gate-level decompute cascade that lever (2) needs, intermediate state persists until a specific inverse has run; erasure stops being the ambient condition and becomes an action someone must have taken.
So "this secret is gone" changes category, from a local property of a write to a property of the whole execution history: not *these bytes now hold zero*, but *no retained intermediate anywhere in the pipeline, the decompute cascade, or the log still determines it*.
This design spends a great deal on the property that just moved. Memory is zeroed at allocation and the typed assembly language rejects a program that could read before writing (§8); revocation makes freed memory unreachable (§8); the duress credential crypto-erases the sealing root (§9); SRAM was chosen partly because near-zero volatile remanence leaves nothing to recover after power-down (§15); and `Zicboz` exists to make eager zeroization nearly free.
Every one of those is a local claim today, checkable where it is written, and each would become a statement over execution histories on a reversible substrate.
That is the harm the "as long as it does not actively hurt" test is looking for, and it lands on the scarce axis rather than the free one: not more logic to build, but a rewrite of the obligations that are this project's actual product.
The one honest credit on the other side is that retained history is exactly what an auditor or a debugger wants, and it rhymes with the evidence discipline elsewhere; it is simply the wrong direction for confidentiality, which is the property these particular proofs carry.

**Lever (1) is a different ISA, and therefore a different proof chain, and the prior art says so by what it is built on.**
Every reversible processor that exists carries a bespoke reversible instruction set rather than an extension of a commodity one: MIT's [Pendulum](https://dspace.mit.edu/handle/1721.1/36039) and its PISA (0.5 um CMOS, 18 instructions including the direction-changing ones an irreversible set has no need of), and the [Bob architecture and BobISA](https://doi.org/10.1007/978-3-642-29517-1_3) with its locally invertible instruction set and fully reversible control and address logic, which is the line Janus compiles into.
**There is no reversible RISC-V, and the near misses are informative.** Notre Dame's adiabatic microprocessor line is the closest working hardware, and it is MIPS: a fabricated Mini-MIPS, then a [16-bit adiabatic reversible microprocessor](https://doi.org/10.2514/6.2022-4296) with a ten-instruction MIPS datapath in SkyWater 90 nm rad-hard FDSOI, needing twelve adiabatic ramping clocks and reaching 0.5 GHz at roughly an order of magnitude below its static-CMOS counterpart in energy.
That 0.5 GHz is worth noting against the assumption that adiabatic means slow; what it costs is twelve clock phases, a 16-bit datapath, and ten instructions.
Work published as a RISC-V reversible extension is a different and weaker thing: reversible *gate primitives* (Toffoli, Fredkin) instantiated inside an ALU, with neither a power-clock nor a bijective architectural state, which is the lever-(2) vocabulary applied without lever (3) and delivers neither.
This platform's ISA is a frozen RV64 profile carrying CHERI, the tag plane, the timing-annotated Sail model, the TAL, and every theorem stated over them (§5, §15, §18).
A reversible ISA is not a substrate swap beneath that; it replaces the artifact the whole chain is stated about, and no prior art suggests it could be reached as an RV64 extension rather than as a replacement.

**The toolchain and the physical constraints close what is left.**
The RTL of record was chosen for whose semantics is mechanized, and there is no mechanized semantics for multi-phase, non-restoring, charge-based logic; there is also no foundry standard-cell library, no timing signoff flow, and no synthesis path, which is why Vaire is building one from scratch.
The RTL ⊑ Sail refinement rests on a synchronous timing model with fixed per-operation latency (§11), and while an adiabatic datapath is clocked rather than self-timed and so does *not* fail at the timing axiom the way the self-timed entry above does, its per-stage latency is defined by a ramp on an analog rail whose worst case is a resonator property.
On the physical side, high-Q on-chip inductors are large and lossy, off-die resonators reintroduce a package-level analog component on a die whose trust boundary is the die, and neither sits comfortably with the SOI substrate, the refusal of backside power, and the IRIS optical path the process choices are pinned to (§15, §18).

**The future-proofing argument, which is the strongest form of the proposal, and the one place this entry returns a positive finding.**
The argument runs: efficiency will keep approaching the Landauer floor, reversibility will eventually be mandatory, this design is already breaking so much compatibility that the marginal breakage is small, and adopting from the outset is cheaper than retrofitting.
The first two premises are granted and the conclusion still does not follow, **because the levers have different retrofit paths and the expensive one is not the lever that must be committed early**.
Levers (2) and (3) are cell-library and process-tier choices, and this document already owns the doctrine that settles them: a radiation-hardened flip-flop "holds the same architectural state as its commercial equivalent, so the Sail model is unchanged and the **RTL ⊑ Sail** refinement still holds, adding no mechanism, no Sail surface, and no proof obligation" (R-15-157, §15).
An adiabatic realization of this same Sail model is admitted by that rule as written. **The specification is therefore already future-proof against the lever that carries the energy**, and stays so without any amendment: a gen-2 part can be adiabatic without the ISA, the TAL, the tag plane, or a single theorem moving.
What early commitment would actually buy is lever (1), and lever (1) buys only the avoidance of Bennett logging and decompute overhead, which matters when the erasure term dominates the energy budget: at four to five orders of magnitude above the floor it is under a hundredth of a percent of the total, and even Frank's 4000-fold target, contingent on MEMS resonators at 99.97% recovery in ten to fifteen years, does not reach the crossover.
**The option value is therefore asymmetric in the opposite direction from the one the argument assumes.** Deferring costs a gen-2 re-spin, which this document has an established idiom for (the belt architecture and the SOT-MRAM substitution are both deferred that way, above). Adopting now costs the frozen profile, CHERI, the Sail model, the TAL, CHERI-CompCert, and every theorem stated over them, which is not this project's overhead but its entire product.
The compatibility premise also misreads what has been spent: the deletions this design has made (speculation, caches, virtual memory, SMT) are all *subtractions* that leave the ISA a strict RV64 profile and the proof chain intact, which is exactly why they were affordable. A reversible ISA is not another subtraction of that kind, and treating a long list of removals as evidence that an incompatible replacement is cheap is the one inference the record does not support.

**What is separable, and it is lever (4).**
Resonant clock distribution changes no logic style, no supply discipline, no architectural state, no Sail surface, and no proof obligation: it is a tank circuit across the clock mesh, in the same category as the radiation-hardened cell that holds identical architectural state.
It has shipped in volume, which nothing else in this entry has: Cyclos' resonant clock mesh in AMD's 32 nm Piledriver core cut clock distribution power by up to 24% at peak and 5 to 10% on average, for up to 10% of total part power.
It is unusually well matched to this design, because a resonant tank wants a fixed frequency and this machine has no DVFS, no reactive frequency control, and a small set of pre-proved operating points (R-15-193, §15), and because the clock net switches every cycle regardless of data, so the lever is activity-independent and stays on the admitted side of the static-versus-reactive line the power discipline draws.
It is nonetheless *deferred* rather than adopted, behind three triggers: (a) a per-island tank that keeps the mode-index-only property of R-15-189m intact, with the cross-island coupling measured rather than argued; (b) a fixed-latency clock-tree characterization across the pre-proved modes that closes into the §11 tables, including tank startup and mode transition; and (c) inductor area and emission measured against the enclosure and emission-envelope budgets (§15) rather than assumed benign.

**Disposition:** reject **architectural reversibility**, lever (1), and with it any reversible instruction set, on the erasure default inverting into a whole-history obligation, on the absence of any prior art reaching a reversible ISA as an extension rather than a replacement, and on the Landauer floor sitting four to five orders of magnitude below where this machine operates, so the lever bearing the name supplies none of the energy and its only function, avoiding Bennett logging overhead, is worth under a hundredth of a percent at that distance.
Reject **gate-level reversibility and fully adiabatic charge recovery as the datapath circuit style**, levers (2) and (3), on maturity (a resonator test chip and a ten-instruction 16-bit research core, no application-class part), on the absence of a mechanized semantics and a signoff flow for the RTL of record, and on the leakage-bound arithmetic: an all-SRAM machine pays its energy in retention, and buying dynamic-switching recovery with cycle time multiplies the term that already dominates.
Their side-channel benefit is real and is declined as a *reason*, because the class it would improve is answered by the masked crypto core's theorems rather than by rail quietness (R-05-004a, R-17-058a), and because a logic-family leakage claim is the silicon axiom without the theorem masking pays for it with.
Defer **resonant clock distribution on the clock network alone**, lever (4), as the one separable atom, behind the three triggers above; it is the only part of this proposal that is production-proved, architecture-neutral, and activity-independent.
**Record that no amendment is owed for future-proofing:** R-15-157 already admits a substrate that holds identical architectural state without touching the Sail model or the refinement, so a gen-2 adiabatic realization of this ISA needs nothing added here, and the levers that *would* need an early commitment are the two rejected on their own merits.
Non-normative; no spec-body change.

---

## Ternary and multi-valued logic: a 1.585× encoding win priced quadratically in noise margin, on a machine whose scarce axes are fixed latency and static leakage

The proposal deserves the same fresh reading the adiabatic entry above receives, and for the same reason: a machine that has already deleted speculation, caches, virtual memory, and simultaneous multithreading has spent enough of the conventional budget that one more unconventional substrate looks cheap, and the encoding argument is arithmetically true rather than folklore.
It is refused, and the refusal turns on the same structural fact: **the proposal is four levers sold as one**, the two that carry the density are architecturally invisible and therefore already admitted without amendment, and the two that would need an early commitment supply none of it.

**The four levers, stated apart, because they have different physics, different costs, different retrofit paths, and different answers.**
(1) **Ternary *values* on a binary machine**: a `{−1, 0, +1}` data representation, most consequentially as a neural-network weight format; no hardware is implicated at all.
(2) **Multi-level *signaling***: three or more amplitudes on one conductor (PAM-3, PAM-4), a physical-layer encoding beneath the wire's logical contract.
(3) **Multi-level *storage***: a bitcell holding log₂3 bits, changing bits-per-cell without changing the byte interface the array presents.
(4) **Ternary *logic***: trits in the datapath, and at the maximal end a ternary ISA with balanced-ternary architectural words and trit-addressed memory.
The density claim rides entirely on (3) and (4). (1) and (2) are separable from both, and are already settled here.

**One arithmetic prices all four.**
log₂3 = 1.585, so a trit carries 58.5% more information than a bit and radix economy (cost ∝ *r*·log<sub>*r*</sub>*N*, minimized at *e* ≈ 2.718) does make three the optimal integer radix: the ternary literature cites this constantly and it is correct.
It is also inapplicable, because the theorem assumes cost is **linear** in the number of levels, and in CMOS the cost of a level is noise margin: splitting a rail into three roughly halves the per-level margin, and restoring the margin costs supply voltage against a *CV*² energy term.
**The price is quadratic and the gain is a fixed 1.585×**, which is the whole reason binary won, and it is a physics result rather than an inertia result.
The trade inverts only where *C* is dominated by a long, expensive, shared conductor the encoding lets you *not* duplicate: which is exactly why multi-level encoding shipped in a lossy serial channel (PAM-4 in PCIe 6.0 and 400G optics, bought with a known SNR penalty and mandatory FEC), in a NAND string, and in a weight file, and in not one logic gate anywhere.

**Maturity, by the standard this document already applies.**
The state of the art is [carbon-nanotube source-gating transistors](https://www.science.org/doi/10.1126/sciadv.adt1909) (*Science Advances*, 2025), which form a controllable p–n homojunction by extending the source into the channel and demonstrate ternary inverters, NMIN/NMAX gates, a ternary SRAM cell, and a small ternary neural network: the highest-performing ternary circuitry realized in low-dimensional materials, and tens of devices rather than an application-class part.
The most fab-compatible route is [tunnelling-based ternary MOS](https://www.nature.com/articles/s41928-019-0272-8) (*Nature Electronics*, 2019), which manufactures the middle plateau by band-to-band tunnelling in a conventional silicon process.
The most complete system study is [ART-9](https://arxiv.org/abs/2111.07584) (DATE 2022), a 9-trit balanced-ternary five-stage RISC core with 24 instructions, whose headline 3.06×10⁶ DMIPS/W comes from a simplified 32 nm CNTFET model *without parasitic capacitance*, whose FPGA validation emulates ternary in binary encoding, and which reaches 0.42 DMIPS/MHz against VexRiscv's 0.65: its real and defensible win is 17–54% code density against ARMv6-M and RV32I, not throughput.
By the standard the gate-all-around entry applies to 2D, tunnel-FET, and CNT logic, and the adiabatic entry applies to charge-recovery cores, **ternary logic at application-core scale is a research reference, not a substrate to base a design on**.

**Lever (1) is already banked, and it is the only one likely to matter.**
Ternary *weights* are the one place ternary is winning in production, and the win has nothing to do with a ternary transistor: [BitNet b1.58](https://github.com/microsoft/BitNet) encodes weights in `{−1, 0, +1}` at 1.58 bits per parameter and reports up to 6.17× speedup on x86 and 5.07× on ARM with 70–82.2% energy reduction against full precision, **entirely on binary silicon**, because the gain is the collapse of the multiplier into add, sign, and zero-skip.
This design already takes it without an amendment: arbitrary low-bit quantized formats are unpacked in software on the V-class VLEN=1024 unit into the int8 the 32×32 systolic array consumes, and MX-style block scales are applied there as ordinary per-element operations, so no architectural tile file or block-scale register joins the context, zeroization, or proof surface ([Inspirations & Prior Art](inspirations.md), §15).
A ternary weight format is therefore a §12 inference-server payload, a content-addressed store object (§10), and a `burn` de-quantization path ([userspace-porting.md](userspace-porting.md)): available today, at zero spec surface.
Its residual density claim, packing five trits into eight bits against 1.585 bits of entropy, is roughly 1.25× over naïve 2-bit packing and is a software encoding choice on the store object, not a hardware one.

**Lever (2) is admitted by R-15-157 already, and the channel that would make it pay does not exist here.**
Three amplitudes on a wire hold the same architectural state as two, so R-15-157's doctrine applies verbatim: a realization that holds identical architectural state leaves the Sail model unchanged and the **RTL ⊑ Sail** refinement intact, adding no mechanism, no Sail surface, and no proof obligation.
Nothing is owed, and nothing is gained either.
Multi-level signaling buys Nyquist frequency at the cost of SNR and mandatory forward error correction, and an FEC decoder is a variable-latency block against a TDM NoC whose per-hop latency is a constant in the §11 tables; and the long, lossy, expensive channels where halving the baud rate is worth that price barely exist on a machine that refuses logic-over-logic stacking, refuses chiplets, keeps main memory on-die, and draws its trust boundary at the die.
On-die wires are short, and this design's own answer to wire cost is the flat cacheless array rather than a denser code on the wire.

**Lever (3) is the sharpest future-proof argument in the proposal, and it lands squarely on the residual §17 does not name.**
The steelman first, at full strength.
R-15-173a books this design's largest single exposure: where complementary back-end devices do not reach array-grade quality, the vertical lever is *absent rather than reduced*, capacity is the single planar tier at order 1–2 GB, and the phone envelope is unreachable rather than late.
A cell holding log₂3 bits is a density lever aimed at precisely that exposure, and the recent ternary device demonstrations cluster on precisely the device line R-15-163 is waiting on: [reconfigurable binary/ternary asymmetric dual-gate IGZO](https://www.nature.com/articles/s41467-025-62116-y) (*Nature Communications*, 2025) and a [phase-composite ZnO ternary serial adder](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12038365/) (2025), both n-type oxide semiconductors, both back-end-survivable, both exactly the shape R-15-163a already recognizes when it notes that an n-type-only cell is not gated by the p-type result the SRAM tier waits on.
Grant every clause of that.
It still fails, on three counts, and the third is decisive.
- **It is a worse version of the lever it substitutes for, contingent on the same materials result.** A tier buys 2×; a ternary cell buys 1.585×. Where the p-type result lands, tiers are the cheaper multiple and R-15-173 runs as written; where it does not, 1.585× on 1–2 GB is 1.6–3.2 GB, which does not reach the R-15-171 phone floor and only makes the pessimistic branch less bad, at a cost the branch is least able to pay.
- **NAND is the measurement, and it is the only place industry deployed multi-level cells at scale.** Each additional bit per cell costs roughly an order of magnitude of program/erase endurance (SLC ~100k, TLC ~300–1000, QLC ~100–1000) and demands progressively heavier ECC with more decoding iterations, and it costs that under conditions this array does not have: microsecond access, adaptive read-retry, LDPC, wear leveling, and a dedicated controller ASIC to hide the analog mess. This array is a fixed-latency constant in the §11 model (R-15-164), carries SECDED with mandated physical bit-interleaving and scrubbing, DECTED on the tag plane, and fail-stop on an uncorrectable event (R-15-175, R-15-177, R-15-184). A raw-BER rise pushes ECC strength up, which inflates the fixed granule and the memory latency constant the cacheless architecture rests on, and the tag plane already carries the *stronger* code, so a ternary tag plane is worse still.
- **It widens the one exposure §17 does not currently name, by construction.** The 6T bitcell entry above records it: leakage power analysis reads static array current while nothing is being accessed, a word's leakage tracking the Hamming weight of what it holds, over the unbounded RETAINED standby interval R-15-189b says the battery spends its life in, on the one machine-wide resource, against a stationary target. A three-level cell replaces a two-symbol static-leakage alphabet with a three-symbol one whose middle level is, in every published construction, physically distinct *in kind* and not merely in magnitude: it is held by a divider or a partially-conducting path, so it draws a static current neither rail state draws. Where that entry finds a symmetric 12T needed to lift leakage-distribution overlap from **0.09% to 97.5%** over the Schmitt-trigger 10T it extends, a ternary cell moves the array in the direction that measurement runs away from; and R-15-189l makes leakage proportional to powered bitcell count, so the lever cuts the count by 1.585× while raising per-cell static current and making it data-dependent in three ways instead of two.

**Lever (4) splits in two, and both halves fail before the substrate cost is reached.**
- **A ternary *realization* of the binary RV64 profile is admitted in principle and buys nothing.** This is the non-obvious finding worth recording: R-15-157 does not forbid building a binary machine out of ternary gates, because the architectural state is identical. What defeats it is the timing model, not the ISA. In every published construction the intermediate level is reached through a weaker path than the rails (a resistive divider, a dual-conduction region, or a tunnelling current), so propagation delay to the middle level differs from delay to a rail and **per-operation latency becomes a function of operand value: admission test 2**. That is the self-timed-datapath entry's disqualifier reached by different physics, and it has the same resolution: clocking to the worst case restores the fixed latency by paying the ternary cost and taking the binary timing. The static path compounds it: the standard ternary inverter holds its middle level through a DC path from V<sub>DD</sub> to ground unless a second V<sub>DD</sub>/2 rail is routed to every cell, and both branches are bad here, the first making static current a function of the value on every node in the datapath (the leakage-analysis point again, now in the logic rather than the array), the second adding a second power distribution network with a regulator that must source *and* sink, against R-15-189m's island power isolation whose current-channel analysis is short precisely because a domain's power state is a function of the public mode index alone. And the binary↔ternary conversion tax at every interface is the interfacing problem [Dubrova](https://people.kth.se/~dubrova/PAPERS/NORCHIP99b.pdf) named as a core unsolved obstacle in 1999 and the [2024 critical review](https://www.sciencedirect.com/science/article/pii/S2590123024010168) still lists as the most considerable one.
- **A ternary *ISA* pays the substrate-cost disqualifier worse than any other entry that pays it.** The Itanium/EPIC count applies in full and then goes further: a fork of the Sail model, CHERI, CHERI-CompCert, Cerise, Islaris, and every binary-level certificate is the ordinary bill, but 9 trits is not a power of two, so alignment, page granules, the ECC and tag granule, capability field packing, and every bit-mask identity in the CHERI representation become re-derived arithmetic rather than re-typed constants. And the proof tooling is Boolean end to end: SAT, SMT, the model and equivalence checkers, riscv-formal, and the ATPG flow; the RTL of record was chosen on whose semantics is mechanized, and there is no mechanized semantics for a multi-valued datapath. Balanced ternary's genuine arithmetic elegance is real and is worth a few percent of datapath area against that bill: free negation by digit-wise inversion, truncation-as-rounding, sign in the leading nonzero trit, and the carry-free redundant representations Dubrova credits as MVL's one legitimate arithmetic advantage.

**Durability, answered in the two forms it actually takes.**
The devices with a wear mechanism (memristive, ferroelectric, floating-gate) are memory technologies in a logic costume: 10¹² programming cycles is about seventeen minutes of GHz toggling, which disqualifies them from a datapath outright and returns them to lever (3), where the NAND arithmetic above already governs.
The devices without one (CNT, silicon multi-V<sub>th</sub>, tunnel FET) do not wear, and their third state is nonetheless the fragile part, because it is **not a device property but a voltage window roughly half as wide as a binary margin**: BTI, hot-carrier injection, random telegraph noise, and thermal drift consume a far larger fraction of it, and the MVL literature is explicit that insensitivity to geometric scaling is what governs the stability of the intermediate state and therefore the feasibility of small-scale integration.
The window narrows as the device scales, which is backwards from the direction a density lever needs.
The gate-all-around entry above already declines 2D, tunnel-FET, and CNT logic on unresolved complementary materials, contacts, variability, and reliability; a ternary use of those devices asks *more* of precisely the parameter (threshold placement) each of them controls worst, since a CNTFET's threshold is set by tube diameter and diameter distribution is that process's least-controlled quantity.

**The security lever, answered in the direction the proposal hopes for, and it still discharges nothing.**
There is a real and decades-old line using a third value as a NULL or spacer rather than as data: dual-rail precharge logic, secure triple-track logic, and [delay-insensitive ternary CMOS](https://www.mdpi.com/2079-9268/5/3/183), where a return-to-spacer protocol makes per-cycle switching activity data-independent at half the wires and half the swing of binary dual-rail.
It is declined for R-17-058a's reason without modification, the same ground the adiabatic families and the security bitcells are declined on: the analog class is answered by the masked crypto core's theorems over the conferred probing-model statement (R-05-004a, R-15-053a, §17), and a DPA-resistance claim carried by a cell family is an axiom about the silicon with no statement verified over it, the axiom without the theorem.
**And it is not additive with the density case**: a spacer-based ternary wire carries one bit, not 1.585, because the third value has been spent to destroy information rather than to carry it.
The two halves of the proposal consume the same physical resource, and any presentation offering both is double-counting.
The direction the *net* runs is the other way: three levels give a power-analysis adversary a three-symbol alphabet with asymmetric transition energies, a data-dependent static component by construction, and value-dependent propagation delay; and halving the noise margin halves the perturbation a voltage-glitch or EM fault-injection attack must deliver, while adding the middle level as a third fault target with no binary analogue.

**The future-proofing argument, stated at its strongest, and the retrofit paths that answer it.**
The argument runs: geometric scaling is ending and encoding density becomes the binding lever; the ternary device line is arriving on exactly the oxide-semiconductor and stacked-complementary processes this design is already waiting on; ternary weight formats may become the dominant inference representation; and groundwork laid now is cheaper than a retrofit into a frozen profile.
All four premises are granted, and the conclusion still does not follow, for the structural reason the adiabatic entry gives: **the levers have different retrofit paths, and the two that carry the density are the two R-15-157 already admits without amendment.**
Lever (1) needs nothing built: it is a payload format on a path that exists today.
Levers (2) and (3) hold identical architectural state, a wire carrying three levels still presenting a bit and an array storing three levels still presenting a byte, so R-15-157 admits them as process and cell-library choices with the Sail model unchanged and the refinement intact, exactly as it admits a radiation-hardened flip-flop.
**The specification is therefore already future-proof against every lever that carries the density**, and stays so without an amendment; what those levers must additionally clear is not an ISA question but the fixed-latency, fixed-ECC-granule, and static-leakage obligations above, which are the obligations *any* candidate cell clears when it exists rather than in advance.
Only lever (4) would need an early commitment, and lever (4) is the one rejected on its own merits in both halves.
So the option value is asymmetric in the opposite direction from the one the argument assumes: deferring costs a gen-2 cell-library or process choice, which this document has an established idiom for; adopting now costs the frozen profile, CHERI, the Sail model, the TAL, CHERI-CompCert, and every theorem stated over them, which is not this project's overhead but its product.

**What is worth watching, stated as triggers rather than a plan.**
The one lever with a live claim on this design is (3), and only in the pessimistic branch of R-15-173a. Re-open it iff all three hold:
(a) the complementary back-end result fails and capacity is the single planar tier, so a 1.585× is worth its cost rather than a strictly worse substitute for a 2× tier;
(b) a candidate n-type oxide multi-level cell publishes a **retention-mode static-current distribution across its three states**, not a density figure, because the leakage-power-analysis residual is what it must clear and no ternary paper in the reviewed literature measures it;
(c) its raw bit-error rate closes into the existing SECDED/DECTED granule and the fixed §11 memory-latency constant without a variable-iteration decoder.
Condition (b) is the load-bearing one: absent it, a ternary array buys capacity by widening the single exposure §17 does not currently name.

**Where it ranks.**
Off the ILP scale entirely, because the motivation is encoding density rather than parallelism, and beside the **reversible and adiabatic** entry above rather than beside the belt: both are unconventional-substrate proposals whose strongest form is future-proofing, both decompose into levers with different retrofit paths, and both return the same positive finding, that the lever carrying the physics is architecturally invisible and needs no amendment while the lever needing early commitment supplies none of it.
Where they differ is the sharper way to say the verdict.
Adiabatic logic recovers dynamic energy on a machine that is leakage-bound, so it recovers the minority term.
**Ternary logic recovers density this machine buys more cheaply with a tier, and pays for it in leakage, which is the term that already dominates.**

**Disposition:** reject **ternary logic and any ternary instruction set**, lever (4), in both halves: the ternary realization of the binary profile on admission test 2 (value-dependent propagation delay to the intermediate level, the self-timed entry's disqualifier by different physics) and on the standard ternary inverter's static V<sub>DD</sub>-to-ground path making static current data-dependent across the datapath; the ternary ISA on the substrate-cost disqualifier (the Itanium/EPIC entry) compounded by a word length that is not a power of two and by Boolean-only proof tooling with no mechanized multi-valued semantics.
Reject **multi-level storage as a normative bitcell**, lever (3), on being a 1.585× substitute for the 2× tier lever contingent on the same materials result, on the NAND-measured endurance and ECC price against a fixed-latency array with a fixed SECDED/DECTED granule, and decisively on widening the leakage-power-analysis residual the 6T entry records as unnamed in §17; re-openable only on the three triggers above, of which the static-current distribution across states is load-bearing.
**Import nothing from lever (2)**: multi-level signaling is already admitted by R-15-157 as an architecturally-invisible realization choice, needs no amendment, and finds no channel on this die worth its SNR and FEC price.
**Record that lever (1) is already adopted**: ternary weight formats run today as a §12 inference-server payload unpacked in software on the V-class unit into the int8 the M-class array consumes, with no architectural tile file, block-scale register, or spec surface, and this is where the production ternary win actually is.
The third value's use as a NULL spacer for power-analysis resistance is declined at R-17-058a's test exactly as the adiabatic families and the security bitcells are, an attenuation with no theorem over a stated model, and is noted as non-additive with the density case in any event.
**Record that no amendment is owed for future-proofing:** R-15-157 already admits every density-carrying realization of this ISA without touching the Sail model or the refinement, so a gen-2 part may encode three levels on a wire or in a cell with nothing here moving, and the levers that *would* need an early commitment are the ones rejected on their own merits.
The platform axiom decides it as ever (*trust is the scarce resource, engineering is free, delete rather than defend, performance is subordinated*): a 1.585× bought with a halved noise margin, a value-dependent latency, and a data-dependent static current spends three scarce axes to buy the free one.
Non-normative; no spec-body change.

---

## Legacy emergency-only radio fallback: declined

A minimal 2G/3G/4G emergency receiver would improve emergency coverage where 5G standalone is absent.
It is declined because the demodulation and RF path, once present, is a bid-down target regardless of software intent: a rogue base station regains a generation to which it can try to force the device.
The security property here is physical absence of the legacy path, not a policy bit saying it is used only for emergency service.

**Disposition:** no legacy emergency-only receiver, legacy channel decoder, or legacy RF fallback.
The zero-authority emergency mode and its explicit coverage cost are documented in [Inspirations & Prior Art](inspirations.md).

---

## The session-security slot: authored protocol proofs, computational-model upstreams, and trusted external provers, declined for curated symbolic upstreams

R-12-043e pins each radio reference state machine to the machine-checked symbolic security analysis of its protocol, and three other ways of buying the session-security half were declined for it.

**Authoring original protocol-security proofs in the platform's own prover** fails the same test the guest-language candidates failed: it converts a curation into a research program.
The Tamarin and ProVerif analyses of 5G-AKA, the 802.11 handshakes, SAE, and Bluetooth pairing embody a decade of adversarial refinement, standards-body feedback, and published attacks that a fresh Coq formalization would re-derive from zero, in a prover whose automation was not built for unbounded-session Dolev-Yao reasoning; and since the imported statements enter no trust base (R-12-043f), the one-prover discipline, which governs what enters the trust base, is not violated by leaving them where they were checked.

**Computational-model upstreams** (CryptoVerif, Squirrel-class analyses) were declined as the pin on coverage: the symbolic lineage carries full-protocol models of all four reference machines against their current standards, and no computational analysis does.
The cost of the symbolic choice is stated rather than hidden, as the second part of the R-12-043f remainder: composition with the §5 scheme-level reductions is assumed rather than proved.
A computational analysis of any of the four protocols remains welcome as further producer-side evidence, narrowing that part without any change to the design.

**Consuming the analyses' statements as axioms** (admitting Tamarin or ProVerif into the trust base, the way an external theorem is imported as an axiom) was declined on the CakeML ground: theorems in a different prover are consumed as axioms or not at all, and here the axiom is unnecessary, because the platform's own claim is the R-12-043b conformance theorem and the analysis stands upstream of the specification rather than inside the proof.

**Extending the import to TLS 1.3 and WireGuard** was declined for now, and the boundary is the conferral rather than the literature: machine-checked symbolic analyses of both exist at full-protocol scale, but R-12-043c confers reference-model rows on the radio control planes alone, so those stacks have no crown-jewel state machine for an analyzed model to stand upstream of, and their composed session security stays booked whole at R-03-004.
The raise is named: conferring reference-model rows for the TLS and WireGuard client state machines, with the same refinement obligation, would extend the same narrowing at the same price.

**Disposition:** the four radio reference machines take curated symbolic upstreams under R-12-043e with the R-12-043f remainder booked; the three alternatives above are declined on the grounds stated.
Non-normative; the normative change is §12's.

---

## Kernel-in-gateware: the benefit needs the whole kernel, the safety only a frozen subset; the one separable primitive worth fusing is already CHERI

The proposal is to express the capability/endpoint/scheduler machine **directly in a formal-semantics HDL** (Kôika/Kami) rather than as Machine-mode software, so the Machine-mode software TCB on application cores could collapse toward zero. That does **not** make the gateware kernel another implementation of the CPU ISA. It introduces a second architectural state machine beside the CPU, with its own abstract state, transitions, endpoint semantics, scheduler semantics, capability-object semantics, and failure behavior.

The proof stack is therefore two refinements plus a composition theorem:

$$
\text{gateware kernel RTL} \sqsubseteq \text{abstract kernel machine}
$$

$$
\text{CPU RTL} \sqsubseteq \text{Sail ISA}
$$

followed by a verified interface/refinement theorem joining the abstract kernel machine to the Sail CPU, interrupt and timer delivery, capability/tag fabric, DMA boundary, and reset model. Ordinary RTL-to-Sail ISA refinement proves neither endpoint behavior nor scheduler and capability-object semantics. Fusion therefore does not fold the kernel proof into the existing **CPU RTL ⊑ Sail ISA** arrow; it adds a fresh hardware refinement and a hardware/kernel/ISA seam that must compose with that arrow.

Its strongest premise is nevertheless real and already in the spec: the kernel ABI is *"on the order of a dozen invocations… frozen with the proof"* (§7), and a per-core multikernel instance is share-nothing, sequential, event-driven, with **zero post-boot allocation** (§7): architecturally a synthesizable abstract machine. It is best read as the **terminus of the kernel-shrinking directions**: the **table-driven cyclic executive in place of MCS** (§7, §11) atop the **single-address-space CHERI isolation that deletes the VM subsystem** (the MMU-deletion entry above), the two base simplifications collapsing the kernel to exactly that frozen state machine; not as an ISA-refinement shortcut.

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
- **Pedigree does not transfer across the prover, the transcription, or the interface theorem.** seL4's battle-testing is a property of the **Isabelle** proof, the C implementation, and its deployed configurations; the design is greenfield in Coq (seL4 vs. CertiKOS, above).
  Fusing to Kôika creates a **new** RTL artifact and therefore a new Coq proof that the gateware refines a fresh abstract kernel machine, plus a new theorem composing that machine with the CPU's Sail semantics and the capability-bearing hardware interfaces. The existing **CPU RTL ⊑ Sail ISA** work remains necessary and does not subsume either obligation.
  The independent eyes were on the Isabelle artifact, not the gateware, so fusion inherits the *design* and re-proves *fresh* on the least-built hardware arrow while adding a new seam: strictly worse than the software re-proof, which at least rides the more-mature CompCert/VST path.
- **The radio/MTTR self-defeat softens under narrowing but survives.**
  Restricting to the most-scrutinized subset genuinely lowers P(functional defect): the crown-jewel doctrine (§5) working as designed.
  But the defect classes fusion forecloses response to are **uncorrelated with the functional proof**: **timing channels** (outside seL4's functional *and* non-interference proofs: time protection is a separate, still-maturing, hardware-dependent effort), hardware-model drift, assumption-boundary violations, and errata interactions.
  Scrutiny buys none of those down, and fusion concentrates its cost exactly there: on the **highest-privilege layer**, where the spec's own rule bites hardest: *"a fully fused radio could never patch its most-attacked surface"* (§12), so patch latency becomes fab latency.
  Lower P(defect) × maximal-severity-and-zero-remediation is still a bad tail trade.
- **What remains to accelerate cannot justify the added proof surface.**
  Static composition and the cyclic executive remove most dynamic RTOS work, but gateware could still shorten partition switches, endpoint lookup, bounded capability-table operations, notification delivery, revocation scanning, zeroization, and timer-boundary handling. Those are real performance and WCET-constant opportunities.
  They do not, however, collapse the TCB unless the whole capability/endpoint/scheduler machine moves with them. Partial fusion leaves the software kernel in place and adds a verified hardware/software seam; whole fusion freezes the least mature and least patchable parts.
  The defensible claim is therefore not that gateware buys nothing, but that its remaining gains buy performance or a smaller WCET constant: not enough TCB reduction to compensate for a new unpatchable hardware proof surface.

**The distilled atom: already banked, following the belt→spiller / EPIC→NaR discipline.**
The non-redundant idea is *a single genuinely-frozen, cleanly-separable primitive as a verified hardware block*, and it is **already present**: the highest-value such primitive: **spatial capability enforcement** (bounds, tags, monotonicity); is in gateware as **CHERI**, with its own Sail semantics and RTL ⊑ Sail obligation (§1, §18), reached **not** by fusing seL4 but by a hardware capability model.
A verified **Kôika scheduler/timer block** is admissible *in principle* (a cyclic-executive table lookup, a windowed timer) but is far too small to deliver the proposal's TCB-collapse and is orthogonal to the capability/endpoint machine it actually names.
So the separable primitive worth fusing is already fused; the rest is **control-plane sequencing best kept patchable, in software, in the same prover as everything else**.

**It is not a memory-capacity lever.** Even complete fusion removes only the small kernel image and limited per-core kernel state. The SRAM budget is dominated by applications, services, graphics, browser compartments, and model weights, so moving the kernel into gates does not materially change the capacity problem that motivates the dense-memory alternatives. Kernel-in-gateware may remain an interesting post-freeze TCB endpoint; it is irrelevant to the main-memory-density decision.

**Where it ranks.**
Unlike the belt, EPIC, and Wasm targets, kernel-in-gateware does **not** abandon the RISC-V substrate: it keeps the substrate and moves the *kernel* into it; so it is off that ranking.
It is the terminus of the kernel-shrink path (the adopted cyclic executive ⋈ the adopted single-address-space MMU-deletion, above, which subsumes the frozen-page-table step), coherent only **after** those simplifications land: as the base has them; **and** the seL4-in-Coq specification and proof are complete and frozen; a gen-2 direction contingent on spec-freeze, in the same "iff the binding constraint appears" slot as the belt, not a base move.

**Disposition:** the fusion of the **capability/endpoint/scheduler machine** is **rejected as a base direction**: the benefit needs the whole kernel while the proven-and-frozen safety covers only a subset (the scissor), the proven subset is not this platform's multikernel/purecap configuration, and the correct proof stack adds **gateware kernel RTL ⊑ abstract kernel machine** plus a verified interface theorem beside, not inside, **CPU RTL ⊑ Sail ISA**. The maturity lives in Isabelle and does not transfer to a fresh Coq → Kôika → RTL artifact on the least-built arrow, while fusion forecloses remediation of the timing/assumption/errata defect classes the functional proof never covered on the most-privileged layer. It receives no memory-capacity credit.
It is logged only as a **spec-freeze-contingent gen-2 direction** (terminus of the adopted cyclic-executive and MMU-deletion simplifications, above). Any partial block is judged as a performance/WCET accelerator and must independently justify the added hardware/software seam; it receives no presumed TCB reduction.
The one distilled atom: a verified hardware block for a genuinely-frozen separable primitive; is **already banked as CHERI** (§1); a verified **Kôika scheduler/timer** block is admissible in principle but too small to be the proposal, and stays non-normative.
The **RealFast RTU / Sierra** line is a functional reference that RTOS-in-gates is real and deterministic, **not** an admissible artifact: unverified VHDL, a dynamic-priority/semaphore shape the §15 admission test deletes, and an accelerator that keeps the software kernel rather than replacing it.
Non-normative; no spec-body change.

---

## Source correspondence checked off-device, leaving only the TAL checker on the install path: declined

The proposal is to move the CIC kernel wholly to the release side, so that on-device admission is the CHERI-TAL type-checker alone, on the observation that a correspondence proof binds bytes to a source closure which may itself be malicious.

The observation is correct and is already the stated scope of the split, not a defect in it: R-13-023 divides supply-chain defense into checked correspondence against a *corrupted* artifact and compose-time confinement against a *subverted-but-memory-safe upstream*, and neither half claims the other's coverage. What the observation does not reach is the conclusion, because the value of the check on the install path was never source virtue. It is the binding: the correspondence theorem is the only step at which *these* installed bytes are tied to the source closure the manifest names (R-13-003), and every other artifact in that manifest, the typing derivation, the tier certificate, the capability manifest, is stated about that closure. Checked only off-device, the binding reaches the device as a producer's assertion about an artifact admitted on a signature, so admission gates on pedigree rather than on evidence: exactly what R-05-008 forbids, what R-13-022 means by *no trusted-toolchain fallback*, and what R-13-026 spends when it admits a nondeterministic producer on correspondence rather than on reproducibility.

The saving is also the smaller half of the seam. R-13-027 already keeps compilation and proving off-device, and R-13-028 already puts the deep composed proofs at release time bound into the measured-boot root; what remains on-device is one artifact-local theorem per install. The stratification is by **proof scale**, and re-cutting it at the **device boundary** deletes the cheap half and pays for it with the binding.

**Disposition:** declined. The CIC kernel stays on the install path and the per-install source-correspondence check is mandatory on-device, with no release-time substitute (R-05-026, R-05-027, R-06-008, R-06-010, R-13-027). Non-normative; the normative position is unchanged and no spec-body change is made by this entry.

---

## CompCert-CT: constant-time by compiler preservation, declined for on-artifact verification

**CompCert-CT** (Barthe, Blazy, et al., POPL 2020) modifies CompCert to preserve a source-level constant-time property through compilation.
It is declined for three reasons.
It has no CHERI backend, so every preservation proof would have to be re-established across the priority-zero CHERI backend; its theorem buys an earlier statement rather than a stronger floor, since both preservation and binary proof ultimately depend on the same `Zkt`/`Zvkt` leakage model and RTL-to-Sail refinement; and it covers only binaries produced by that compiler, leaving direct-binary and other certifying-toolchain paths dependent on producer pedigree.
The line's frontier has moved past plain constant-time to *speculative* constant-time preservation (Barthe et al., POPL 2025, extended to the production Jasmin compiler in 2025, with the companion finding that preserving CT alone does not preserve SCT), which sharpens rather than weakens the verdict: the property it labors to carry through a speculating compiler-and-core stack is one this profile's deletion of speculation leaves without a customer, and the CHERI-backend and pedigree grounds are untouched.

**Disposition:** decline CompCert-CT and any compiler-pedigree-only constant-time admission route.
The artifact-level constant-time verification actually used, including its cost and residual, is documented in [Inspirations & Prior Art](inspirations.md).
Non-normative; no spec-body change.

---

## Whole-compiler translation validation as a replacement for CHERI-CompCert: deferred fallback

The seL4-style alternative is to compile the whole trusted base with stock CHERI-LLVM and prove each resulting binary refines its source, retiring or shrinking the priority-zero CHERI-CompCert backend.
The ingredients are plausible, especially at low optimization: a CHERI-RISC-V Sail model, Islaris-style decompilation into logic, and SMTCoq-style checked solver evidence.

It remains a fallback because per-build proof search is less reusable and more fragile than one compiler theorem, purecap aliasing and calling conventions require substantial new validation work, and program-specific refinement does not establish secure compilation's robust-preservation hyperproperty over every adversarial linked context.

**Disposition:** do not replace CHERI-CompCert wholesale with whole-program translation validation; retain that extension only as the named fallback if the backend proves intractable.
The translation-validation role already adopted for source correspondence and compiler residuals is documented in [Inspirations & Prior Art](inspirations.md).

---

## The hardware-description language: Hardcaml, Chisel, and the generator HDLs; the RTL of record is chosen by whose semantics is mechanized, not by whose ergonomics are better

The proposal is to author the hardware in a **host-language-embedded generator HDL** rather than in the Coq hardware DSL the design names.
**Hardcaml** (Jane Street: an OCaml library, open source via opam, in production in their low-latency trading systems, with the ZPrize MSM/NTT implementations as its public showpiece) is the strongest current instance, and the genus also holds **Chisel** (Scala), **SpinalHDL** (Scala), **Clash** (Haskell), and **Bluespec** itself.
Wirth's **Lola-2**, in which the RISC5 processor was restated after its Verilog, is the non-embedded member of the same question and is dispositioned with the rest of the Oberon line above: it is smaller and more regular than SystemVerilog, it has no mechanized circuit semantics in Coq, and it therefore fails the anchor test below for the same reason the generator HDLs do, with less industrial weight behind it than any of them.
All share one shape: a program in the host language *elaborates* to a netlist, and SystemVerilog is emitted for synthesis.
Three claims separate: the **generator and type-system productivity**, the **simulation and verification story**, and the **hardware-software integration** (drivers written in the same language as the RTL, with register maps generated from the driver code rather than transcribed).

**The steelman: it is on target in a way an HLS tool would not be.**
Hardcaml states plainly that it is a fully-featured HDL and not high-level synthesis, so it does not reintroduce the scheduling opacity that would put a compiler's arbitrary pipelining between the design and the fixed-latency timing contracts (§11, §15): every register and wire stays under the designer's control and the generated RTL is predictable, with synthesis results mapping back to the source.
Its functor system parameterizes a design over its implementations and datatypes, which is exactly the shape a frozen-parameter design wants when it sweeps a proof-aware design-space exploration (§15).
Its simulation runs inside the host runtime with the full software ecosystem available, so constrained-random testing (Quickcheck), inline waveform expect-tests, and driver code exercised against simulated hardware all come for free, and this is a *real* industrial artifact rather than a research prototype.

**The adjacent members, dispositioned here: the transpiled successor HDLs, and co-assurance HLS.**
**Veryl** (SystemVerilog's semantics under a modernized syntax: clock and reset types, clock-domain annotations, a package manager, deliberately readable emitted SystemVerilog) and **Spade** (a research prototype: Rust-shaped enums and `match`, so a decoder reads structurally near its Sail source, with pipeline latencies typed and compiler-checked) are standalone transpilers rather than embedded generators, and they move the authoring ergonomics of SystemVerilog-class RTL without moving its evidence class: neither has a mechanized circuit semantics in any prover, Veryl because its semantics is SystemVerilog's by design and Spade because its semantics lives only in its compiler, so both fail the anchor test below at the same clause as the generator HDLs and are admissible in the same untrusted-scaffolding slot, Spade's decode-as-`match` easing *manual* review of RTL against the Sail decode, which is review ergonomics, not evidence.
Hardin's **RAR** line (a Restricted Algorithmic Rust subset transpiled to Russinoff–O'Leary Restricted Algorithmic C, from which commercial Catapult HLS emits the RTL and the RAC-to-ACL2 translator emits the definitions proved, the Arm-FPU-verification RAC lineage) is the one member that arrives *with* mechanized proofs and fails twice anyway: the theorem is about the RAC source while the RTL is whatever the unverified HLS scheduler emits, compiler-trust with no check on the output where the FEV rung's commercial trust is checker-trust over the actual RTL (§15), reintroducing exactly the scheduling opacity the steelman credits Hardcaml with refusing (§11), and the proofs land in ACL2, a second prover with no bridge to Sail or the Coq spine, the trust-base widening the rule applied to aiT, Binsec/Rel, and SecVerilog refuses as a closing axiom (§5).
It lacks even the scaffolding slot: what HLS generates well is the algorithm-shaped block (queues, filters, crypto kernels), which this design imports as reference RTL rather than authors (§15, §18).

**Why it does not import.**
- **The RTL-of-record decision is a semantic-anchor decision, not an authoring-ergonomics one.**
  Kôika/Kami is named the closing vehicle for one reason: the refinement is tractable only against a source whose semantics is *already mechanized in the prover*, so the net-new blocks are authored there and their SystemVerilog is *generated*, which is why that generated SystemVerilog is not an anchor (§15).
  A Hardcaml design has no mechanized circuit semantics in Coq, so making it the source of record would admit a new circuit-semantics anchor that **duplicates one the budget already holds**, failing clauses (1) Coq-native or mechanically bridged and (2) no duplicate of an existing anchor, and retiring no interim under clause (3) (§5).
  The same verdict falls on Chisel, SpinalHDL, and Clash, and it is the verdict the design already reaches when it takes CHERI-CVA6, Ara, and Gemmini as *references* rather than as the trusted base.
- **Its verification story lands in the complement slot, which is already full.**
  Native simulation, constrained-random generation, expect-tested waveforms, and formal verification via SAT solvers and industry-standard toolkits are all **bounded or foreign-prover evidence**: precisely the rung the design already occupies with riscv-formal bounded model checking, Isla-derived obligations, and Sail-generated SystemVerilog under commercial formal-equivalence verification (§15).
  By the rule applied to aiT, Binsec/Rel, and SecVerilog (the entry below), such a tool is admissible as bring-up evidence and never the closing axiom, so adopting Hardcaml would add a fourth source of a kind of evidence the design already has three of, and would close nothing.
- **The OCaml adjacency is a coincidence, not a bridge.**
  Coq extracts to OCaml, which makes it tempting to read Hardcaml as somehow near the prover, but the two meet in the wrong direction: a verified OCaml program that *builds* a netlist gives a trustworthy **elaborator**, not a semantics for the circuit it emits, and the obligation is a statement about the circuit's behavior against the Sail model.
  Kôika runs the useful direction instead, being a rule semantics *in* Coq with a compilation to circuits proved *inside* the same kernel that checks the kernel and the compilers (§6).
- **The blocks that are actually authored here are the ones a generator HDL helps least.**
  What is written from scratch is the capability- and tag-carrying DMA fabric, the TDM NoC, and the fixed-function sequencers (§15, §17, §18): small, static, fixed-latency, and free of dynamic scheduling.
  Generator-HDL productivity pays most on the elaborate, heavily parameterized, dynamically scheduled structures this profile has deliberately deleted (caches, a coherence protocol, predictors, out-of-order issue), and the mass that remains lives in the imported cores, which are already SystemVerilog and Chisel and enter under the Sail-plus-FEV rung.
  Re-authoring those in *any* HDL is the re-expression hop the deferred Verilog-semantics rung exists to delete, not to redirect (§15).

**The distilled atoms are banked, each from the other side.**
The integration idea, one language for the hardware and its driver so the register map cannot drift, is held here by the **register-description language** from which the verified HAL's field accessors are generated and Coq-checked, with drivers reaching the device through a typed register interface so no driver open-codes a shift or a mask (§5, §12).
Simulation as a first-class artifact is held by the Sail C-backend golden model and the deterministic simulation testing built on it, where the *same* frozen model the silicon is proven to refine is the thing the tests run against, which is the gap a black-box simulator leaves open.
Generated-rather-than-hand-written RTL is already the shape of both live rungs, one generating from Kôika and one from Sail, and the Sail rung is demonstrated at full-processor scale: CHERIoT-Ibex carries an unbounded observational-correctness proof against its Sail specification through exactly this Sail-generated-SystemVerilog-plus-commercial-FEV shape (Oxford/Cambridge/lowRISC, 2025, upstreamed into the production CHERIoT-Ibex repository).
Functor-parameterized architectural sweeps are the proof-aware design-space exploration, whose utility function weights proof simplicity beside performance and area (§15).

**Where it could legitimately sit.**
As **untrusted scaffolding**: a generator or exploration front end feeding the design-space search, or a fast simulation cross-check, in the same slot PipelineGen and Sail-to-Kôika generation already occupy as scaffolding rather than the design of record.
Anything in that slot enters no trust base and is spent freely on the engineering axis, which is also why adopting it buys little the design lacks.

**Where it ranks.**
Off the abandon-substrate scale entirely: this is a tooling question, not an architecture, and it ranks with the verification complements (aiT, Binsec/Rel, riscv-formal, SecVerilog below) rather than with the entries that would change what the machine is.

**Disposition:** no import as the language of record.
The RTL of record stays Kôika/Kami for the net-new blocks, with imported cores entering as references under Sail-generated SystemVerilog plus commercial FEV (§15), because the choice turns on which HDL's semantics is mechanized in the one prover and not on which is pleasanter to write; Hardcaml and its genus are admissible only as untrusted generators or simulation cross-checks, which is the slot the existing scaffolding already fills.
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
  The nearest Rocq-native motion, a mechanized deductive system for hardware leakage-contract satisfaction (Correnson, Zeng, Hofmann, 2026), operates on abstract CPU models rather than RTL, so the slot assignment stands.
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
  zk-proving carries **≈10⁵–10⁶× execution overhead** (measured provers cluster near a million times native, sub-thousand-fold is reachable only through precompiles, and the "real-time" block-proving results of 2025–26 absorb the factor with GPU fleets rather than shrinking it); the platform spends performance freely, but not by six orders of magnitude, and the property bought: *a third party can check a run happened*; is not the platform's problem: the attested measured-boot root ⋈ reference integrity manifest (§9) already give a remote party a **reproduced-not-asserted** account of *what* is running, and FPCC gives the *static* guarantee it is correct **for all inputs**: strictly stronger, per input, than a per-execution transcript.
- **Per-execution proof is weaker than ahead-of-time proof for local security.**
  A zk-proof that *this* run was faithful to the ISA says nothing about whether the program is memory-safe, constant-time, or non-interfering *across* runs; the FPCC / CHERI-TAL stack (§13, below) proves those for **all** runs.
  And *"the machine executed the bytecode faithfully"* is exactly what **RTL ⊑ Sail** (§18) already establishes for the real silicon: once, structurally; without a per-run proof.

**The distilled atom: already banked.**
Proof-carrying *artifact* is the FPCC discipline (§5, §6); attested *what-is-running* is the measured root ⋈ reference manifest (§9).
The zk primitives themselves (a SNARK/STARK verifier) are ordinary contained crypto the platform could run as an *application* if a specific need ever arose: verifying an untrusted third party's *off-device* computation, say; an app-level tool, never a system execution substrate.
The ecosystem's own verification push (circuit-determinism proofs over most of the R0VM circuit set, a Lean soundness formalization for Jolt) aims at the prover's soundness, not at the memory-safety, constant-time, or WCET properties this platform's admission decides, so it moves no ground here.

**Where it ranks.**
Rejected on **motivation**, one level above cost: like Wasm-as-substrate, it trades for a property the Goals do not seek (third-party verifiability of a remote execution) that FPCC ⋈ attestation already exceed for the local threat model; off the ILP ranking entirely, since it is not an ILP play.

**Disposition:** rejected as an execution substrate, the FPCC discipline already banks proof-carrying artifacts *statically and per-input* (stronger than a per-execution transcript), attestation already gives a remote party a reproduced account of what runs (§9), and RTL ⊑ Sail already proves the machine executes the ISA faithfully (§18); a zk verifier is admissible only as an ordinary **application-level tool** for checking a specific untrusted third-party computation, never a system execution model, and its six-order overhead is the wrong trade on the one axis the platform spends.
Non-normative; no spec-body change.

---

## Homomorphic encryption and secure multiparty computation as compute substrates: the privacy-preserving sibling of zkVM, rejected on the same two grounds

The proposal makes the execution substrate a **privacy-preserving computation** model: **fully homomorphic encryption** (FHE; Gentry, STOC '09: compute directly on ciphertext, the data never decrypted, so the executing machine never sees plaintext) or **secure multiparty computation** (MPC; Yao garbled circuits, GMW, secret-sharing: split a computation across mutually-distrusting parties so none sees another's inputs).
It is the confidentiality sibling of the zkVM entry (above): where zkVM adds *verifiability* of a remote execution, FHE/MPC add *confidentiality against the executor*.

**The steelman.**
FHE gives **data-in-use confidentiality against the host itself**: the strongest possible data-confidentiality, and a property this platform's memory path does not attempt at all, carrying no cryptography whatever (§15, on the reasoning that any such mechanism decrypts on arrival at the controller to compute and therefore protects an interface rather than a memory); and it is a genuinely different security model: confidentiality by *cryptography* rather than by *isolation*.
Some FHE/MPC implementations are formalization-adjacent, so it is not off the verification map.

**Why it does not import as a substrate: the zkVM rejection, verbatim, on two grounds.**
- **Threat model.**
  FHE/MPC protect a computation *from the machine running it*: the outsourced/cloud model where the executor is the adversary.
  This platform **is** the trusted machine: a personal device whose CHERI, kernel, and crypto core the owner trusts and the design *verifies*, whose confidentiality boundary is the die itself ⋈ the crypto core's hardware boundary (keys never leave) ⋈ CHERI/IFC in-core (§8, §15), and whose whole point is that computing on plaintext on-core is safe.
  Protecting the computation from its own trusted CPU is a property **outside the threat model**: the same "buys a property the Goals do not seek" rejection the zkVM (third-party verifiability) and Wasm-as-substrate (portability) entries make.
- **Overhead.**
  FHE carries **≈10³–10⁴× slowdown on GPU/ASIC-accelerated deployments and up to 10⁶× on plain CPUs** (bootstrapping-dominated; the DPRIVE-line and ISSCC 2026 accelerator prototypes claim three-to-four-order speedups over CPU with no commercial availability); MPC carries round-complexity and communication blowup, and its parameter- and noise-management structure is data-dependent in ways that fight the fixed-latency WCET tables (§11).
  The platform spends performance freely, but not three-to-six orders of magnitude to buy a property it does not need, the identical cost argument the zkVM entry books.

**The distilled atom: already banked / app-level.**
Data confidentiality here is **the die as the trust boundary** (§15) ⋈ the **crypto core's hardware boundary** ⋈ **CHERI/IFC** in-core (§8) ⋈ **AEAD at rest** in storage (§10): confidentiality by isolation, matched to a threat model in which the CPU is trusted.
The FHE/MPC *primitives* fall to the zkVM verifier's sole admissible role, above: ordinary contained crypto, admissible **as an application** should a specific need arise (private set intersection, a sealed-bid or private-contact-discovery protocol with an untrusted **remote** party), never a system execution substrate.
The shipped deployments sit exactly there: Apple's production homomorphic PIR (Live Caller ID Lookup, over its open-sourced BFV stack) is an application-level protocol against an untrusted remote service, not an execution substrate, which is the role this entry admits.

**Where it ranks.**
Rejected on **motivation**, one level above cost: with zkVM and Wasm-as-substrate, it trades the substrate for a property (confidentiality against a distrusted executor) the Goals do not seek for the local threat model, where the die boundary ⋈ isolation ⋈ at-rest AEAD already give confidentiality against the threats that *are* in scope; off the ILP ranking (not an ILP play), and paired with the zkVM entry as the two cryptographic-computing models rejected on threat-model + overhead.

**Disposition:** rejected as an execution substrate, FHE/MPC protect a computation from a distrusted host, a threat model this trusted, verified personal device is not in (confidentiality here is the die boundary ⋈ the crypto-core boundary ⋈ CHERI/IFC ⋈ at-rest AEAD, §8/§10/§15, against the threats actually in scope), and their 10³–10⁶× overhead is the wrong trade on the one axis the platform spends; FHE/MPC primitives are admissible only as **application-level tools** for privacy-preserving interaction with an untrusted *remote* party, never a system execution model, the confidentiality sibling of the zkVM entry's verifiable-computation rejection.
Non-normative; no spec-body change.

---

## First-order-only source languages and whole-program defunctionalization: rejected

A first-order restriction would ban closures, function pointers, and dynamic dispatch to close the call graph and remove indirect branches.
It buys no hardware simplification here: dynamic predictors are already absent, and cross-compartment sentry entry is necessarily an indirect capability jump.
Defunctionalization also relocates rather than removes dispatch, turning a closure into a tag plus `apply`, which compiles to either an indirect jump table or a branch tree; without dynamic prediction the latter can be worse.
As a whole-program transform it also conflicts with per-compartment admission and would unnecessarily gut safe Rust's ordinary abstraction mechanisms.

**Disposition:** reject a first-order-only contained language and mandatory defunctionalization.
The finite-callee property used by memory and WCET analyses is documented in [Inspirations & Prior Art](inspirations.md).

---

## Rejected performance-recovery levers: the recovery gate, and the proposals that fail it

The design's performance-recovery levers are normative where they exist: static schedule synthesis (R-11-015b), bound-directed lowering (R-18-014c), the size-constrained link-step transforms (R-18-014e) and the optional measured-path modulo scheduling beside them (R-18-014f), the static memory plan and layout (R-08-012a, R-18-014b, §10), the interpreter levers (R-14-008a), and the §15 parameter search. Each is admissible on one architecture-wide fact, the §6 enabling theorem: *a compromised compiler or analyzer cannot mint a valid certificate for a property its output lacks*, so the optimizer is untrusted evidence-producing machinery and may be pursued to arbitrary aggressiveness without touching the trust base, any transformation whose result still type-checks (CHERI-TAL, §5) or proof-checks (CIC kernel, §6) being admissible however it was produced. The theorem's reach is narrower than "wrong answers cannot ship", and the difference matters: the checkers decide memory safety, the CT taint discipline, and the WCET typing, and **nothing on the device decides functional correctness of non-TCB code**, so a miscompilation that is memory-safe, constant-time, and WCET-typed is admitted and runs, and a transformation whose failure mode is a wrong-but-well-typed binary carries a producer-side validation obligation (translation validation, differential testing) as engineering hygiene, never as a trust argument.

A recovery proposal is a **pure win**, admissible at all, only if it clears all six:

1. **Recovers performance** on at least one loss row of [performance-estimates.md](performance-estimates.md), *intra-design* (the same instantiation, un-optimized vs. optimized). Collecting a hardware gain already booked there is backend completeness, not a recovery lever.
2. **No trust widening**, no new axiom, no TCB growth; the produced artifact is re-checked, so its *producer* stays untrusted.
3. **Sheds no security property**, every theorem the spec claims still holds, unchanged.
4. **Revives no deleted dynamic mechanism and opens no channel**, no speculation, OoO, dynamic prediction, SMT, JIT, DVFS/turbo, prefetch state, or reservation state sneaks back.
5. **Stays inside the proven-safe envelope**, passes the five-part §15 admission test and the §8 non-interference / §11 WCET obligations.
6. **Does not spend a different scarce resource.** No lever may loosen a WCET bound, worsen WCET *analyzability*, or grow the image against the §15 SRAM capacity budget: on a machine with no I-cache, no swap, no overcommit, and a composition-time capacity budget measured in square millimetres (§15), **code size is a hard admission quantity, not a preference**, and schedulability is a gate rather than a metric (§11). The clause did **not** loosen when the dictionary encoding (R-15-036a) turned the standing code-size penalty into a saving: that lever bought headroom against a fixed budget, not a change in the budget's character, and a lever that spends the headroom is spending the same scarce quantity it always was.

Untrusted-producer status is necessary and not sufficient: where a transformation's *mandatory* producer-side validation cannot be discharged by tools that already exist, supplying it means minting the very checker the §5 rule deleted (R-05-064, R-18-022), and the proposal is declined rather than shipped unvalidated (the superoptimization entry below).

The proposals below were evaluated as recovery levers and rejected, recorded so they are not re-proposed. Each fails at least one gate, whether by **shedding a property, reopening a channel, adding scarce-axis surface, lacking a scored recovery, or relying on a mechanism that cannot work as stated**. The entries that restore deliberately deleted mechanisms describe the **irreducible accepted security cost**, the part that survives after every admitted lever has run **and** the equivalent passes have run on the baseline; the remaining entries prevent invalid or non-pure proposals from returning:

- **Source-level fast-path porting**, writing application data structures onto the RVV / GEMM / crypto paths the profile accelerates. It is real work and it pays, but it is porting discipline rather than a recovery lever: it changes no mechanism, no schedule, and no theorem, so there is nothing for the spec to land. It is stated once, in [userspace-porting.md](userspace-porting.md).
- **Speculation / OoO, dynamic branch prediction, SMT**, hidden shared state that fails admission-test-3 (§15); the very channels the design deletes.
- **JIT / on-device codegen**, violates W^X (§14).
  The substitute is a faster pure interpreter, and it is normative: R-14-008a admits threaded dispatch, an off-device-selected superinstruction set whose bodies are AOT image code, and data-plane inline caches, under the size budget of R-14-008b and the §8 argument of R-14-008c. Web JS and Wasm are dynamic content, so no AOT shortcut exists *on the web delivery path*; the §13 install path is a different matter (R-14-008f).
- **DVFS / turbo, reactive clocking**, a data-dependent frequency channel; power states are static schedule artifacts (§7/§15).
- **Prefetch / non-temporal hints (`Zicbop`/`Zihintntl`), a return-address stack, LR/SC**, reintroduce µarch state that WCET must model and admission-test-3 forbids.
  The pure-win substitute for prefetch is static load hoisting by the mandatory scheduler and the optional modulo-scheduled form (R-18-014a, R-18-014f); note that the estimates score no-prefetch at ≈0%, so the substitute is collecting a cost that was never booked as a loss.
- **Slack donation / work-conserving scheduling / any reclaim of idle discretionary slots**, recorded here because §17 names it as the mechanism that will never be added: reclaiming an idle slot across a confidentiality boundary *is* the timing channel the non-work-conserving frame is buying. The pure-win substitutes are the schedule synthesis normative at R-11-015b, the bound-directed lowering normative at R-18-014c, and the composition-time granularity budget normative at R-14-007a, none of which reclaim anything.
- **A hardware reference-count or ownership primitive (a capability-copy-intercepting counter, hardware *linear* capabilities)**, recovers refcount traffic only by adding microarchitecture: a new mutable per-object counter or a non-duplication check in the pipeline is exactly the hidden shared state admission-test-3 (§15) forbids, and it breaks the no-new-µarch premise every admitted recovery lever rests on.
  There is no recovery substitute: temporal safety already rides the tag + revocation machinery and the linear/affine capability types (§8, §5, §13). Compiler work that merely realizes that required discipline is §13 hygiene, not a recovery lever until a scored instrumentation cost exists.
- **Mandating V/M-class pinning to delete the eager-zeroize obligation.** §7 offers either static pinning of a V/M-class core to a single domain (preferred) or eager zeroize at the switch, and making pinning *mandatory* is proposed as **negative** proof surface: a register file that never crosses a domain has no residue question to discharge. It fails on two independent grounds.
  **First, it does not delete the obligation.** The C-class is `RV64IMV`+CHERI at **VLEN=256** (§15 roster) and the C-class is *the slotted class*: kernel instances, servers, apps, and browser origins all live there. So the vector zeroize path survives in the spec, in the proof, and in the partition-switch budget no matter what the V/M cores do. Mandatory V/M pinning removes **instances** of the obligation, never the rule, and the proof-surface delta is therefore zero rather than negative.
  **Second, pinning is not free on the scarce axis (gate 6).** With four general V-class cores, mandating pinning caps at four the number of domains that may use the long-vector unit *at all*, which spends exactly the capacity the §17 population wall is about, and spends it against a row the estimates score at **−2% to −4%** whose top end the delete-the-save decision (R-07-014a) already took down by ~5× in state traffic and which `Zicboz` makes nearly a free write pass.
  The existing disposition is the correct one and is already load-bearing: R-11-011 and R-15-114 pin exactly where σ = C_switch / T_poll demands it and call pinning an **admission outcome, not a favour granted per device**. The lever adjacent to this is not a mandate but the core-count axis the §15 search weighs (R-15-108a), which buys *more* opportunities to pin without foreclosing time-shared vector use.
- **Collapsing a tag-table miss-and-walk WCET term.** There is none to collapse. R-15-203 carries CHERI tags as **native SRAM bits**, one validity tag per 64-bit granule, read and written in parallel with the data, with no reserved-memory tag table and no tag cache; the estimates score the row at ≈0% with **no latency term**, and the absence contract (A-11) books the tag cache as structurally absent. The all-SRAM direction such a lever would argue toward *is* the specified design, so this is a closed question recorded to stop it reopening as an open one.
- **Any structure that would rejoin the `fence.t` flush set: a victim buffer, a small I-cache, a return-address stack, a prefetcher.** Each buys real throughput, and each gives back the same thing: the design closed these by **deletion** rather than by flushing, §15 makes the singularity of the flush set (the store buffer alone) a crown-jewel clause, and R-15-100's absence contract is discharged *structurally against the RTL* precisely because there is nothing there to prove complete. Reintroducing any of them converts an absence obligation back into a flush-completeness obligation on the least-built arrow of the stack (§17, §18), which at this design's exchange rate is a bad trade regardless of the throughput. This is the general rule of which the RAS and prefetch bullets above are instances.
- **A static-callee-set-driven fetch redirect.** Tempting, because the CHERI-TAL typing derivation already carries the callee set, so the front end could in principle be steered by information the certificate has *already proved* rather than by learned history. But a redirect that **can** be wrong is a transient window and fails admission-test-3 exactly as a BTB does; only a variant that provably cannot mispredict is admissible, and that variant collapses to the singleton case, i.e. a direct call, which R-18-014a's direct-call sequence collapse and the retained static predictor already handle. The admissible residue is much narrower than the idea first appears and does not amount to a lever.
- **A software-written branch-target latch (prepare-to-branch, the `mtctr`/`bctr` shape).** The one cannot-mispredict variant the previous entry's collapse does *not* reach: an architectural target register written explicitly ahead of a paired indirect jump, read by the front end at decode of the jump, so the redirect is the jump's defined semantics rather than a guess. It would land on exactly the branches this machine predicts with nothing, the outlined-helper return (R-15-036o), the interpreter's threaded-dispatch jump (R-14-008a), and the indirect calls the singleton collapse cannot devirtualize (R-05-114a), and it is declined on the audit predicate and on yield, in that order.
  **It fails R-15-104's table search as literally written.** The latch is a state element in the fetch path whose write data depends on a prior execution, which is that predicate's definition of a prefetcher. The exemption it would plead, architectural, Sail-visible, zeroized at the switch, and so carrying nothing across a partition boundary, is sound in isolation, and granting it converts the audit from a table search back into a judgment call, which spends the structural-absence property the predicate exists to keep: the `fence.t`-flush-set entry's exchange rate again, real throughput paid for by softening a crown-jewel clause.
  **Its yield over what needs no ISA change is zero on this pipeline.** A dedicated latch earns its keep on machines whose decoupled front end cannot read a general register early, which is the front end this design does not have. On a short in-order pipe the same cycles come from a **resolve-point choice inside the §15 pipeline parameters**: `cjalr`'s target capability is read at the register-read stage, the redirect issuing from decode exactly as the static predictor's backward-taken redirect does when no older in-flight instruction writes that register, and decode stalling until the write completes when one does. No guess, so no transient window; no state element, so nothing for the R-15-104 table search to find; and the stall-or-redirect outcome depends only on the quantities the load-use interlock already depends on (the instruction stream and the profile's fixed instruction latencies), so it enters §11 as an ordinary per-site constant. The scheduling half is already mandated: hoisting the target materialization past the resolve distance is R-18-014a's existing latency-aware duty with the branch-target operand treated as the latency-critical use it is, and the interpreter's next-handler load is hoisted into the handler body as ordinary AOT code shape under R-14-008a. The return case needs no hoisting at all, the sentry being written at the call and architecturally final for the whole callee body, which is where the outlining measurement's cycle axis (R-15-036p) softens.
  What survives is therefore an RTL design fact against a constant the estimates already price as a range (the static-prediction row's fetch-to-resolve distance), which is implementation quality under gate 1, not a lever; the latch itself would have added a capability-width register to the switch-zeroize path, a second jump-target materialization for the sentry semantics and CJ-CERISE to cover, Sail clauses, and an R-18-034 rerun, all spent to duplicate cycles the resolve-point choice collects for free.
- **Compiler-liveness-based V/M switch minimization.** R-07-014a requires the switch to zeroize the vector RF, vector CSRs, and scratchpad and save nothing; the task already reaches a normal boundary with no live V/M value. Narrowing `VL` or releasing registers does not erase stale architectural storage and therefore cannot reduce the mandatory zeroize without adding a new hardware contract. `Zicboz` already makes the one remaining write pass nearly free.
- **Overlapping the partition switch's three phases.** The `fence.t` padded constant, the eager V/M zeroize, and the OPP relock are specified as an *additive* bound (R-15-220), and a mechanism running them concurrently, so that a switch costs the longest phase rather than the sum, is declined as a base-spec mechanism: on yield first, on the obligations it opens second.
  **The cap on the win is small, and two stronger moves already hold the same term.** The row is scored at −2% to −4% and only on switch-heavy work ([performance-estimates.md](performance-estimates.md)), and the relock term applies only where operating points differ, a handful of coarse points per class (R-15-188), so overlap collects a fraction of a fraction. Pinning **deletes** all three constants together for exactly the tenants whose switch rate demands it (R-11-011, R-15-114), and with the high-rate servers off the slot wheel the constant amortizes to a negligible fraction of the major frame for everyone else (R-11-013).
  **The dominant term's correct attack is deletion, not concealment.** The store-buffer entry above removes the drain outright rather than hiding it behind another phase, which is R-15-105's exchange rate applied to the same constant; overlap leaves every structure and every obligation standing and buys only a tighter sum.
  **The proof it demands is not free.** Phase independence would have to hold under every fault and power state, and an ordering argument would have to show that no successor instruction observes state the zeroize has not yet written, which R-15-215 currently gets for free from the switch writing that state before the successor's first instruction. New obligations, for a tightening the §11 arithmetic barely sees.
  It is nevertheless not foreclosed: overlap is semantics-free and only ever tightens a constant, so a composed schedule that turns out switch-bound after pinning and amortization can re-propose it as a pure amendment (§18) with the independence proof in hand and no architectural rework. It is not carried as an open question, and R-18-009's two remain the only two.
- **A scalar scratchpad pursued as a performance-recovery dimension.** §15 permits it as a general proof-aware DSE parameter, but also states that it adds a modeled region, partition-switch zeroize state, and RTL ⊑ Sail surface and is a poor fit for the irregular access that motivates it. That is a performance-for-proof trade, not a pure win; the normative no-scratchpad default stands.
- **Eliding software bounds checks onto CHERI's hardware bounds, in both the naive and the certified-precondition form.**
  The **naive** form fails gate 3 outright: eliding a check the capability does not actually subsume (a `Vec` bounded to *capacity*, an object above the compressed-bounds precision threshold) deletes the only spatial check on that access and sheds a security property.
  The **certified** form, in which the compiler proves the capability's bounds are exactly the checked region before eliding, is declined on yield and on failure mode rather than on principle.
  **The yield is close to nothing.** R-15-019 makes prediction backward-taken / forward-not-taken, and a Rust bounds check is a forward branch to a cold panic block, so it is *correctly predicted by construction*: none of the static-prediction (−10% to −25%) row is recoverable this way, that row being scored against the data-dependent branches where nothing static helps. The panic block is code, but §10's profile-free static layout (R-10-034) already places it cold, so it is not fetch-path bytes either. What remains is a compare and a branch's issue slots per indexed access, set against a CHERI purecap row that R-15-031b's fusion set already partly self-funds by collapsing the offset-then-dereference sequences that row is charged for, and that R-15-007e removes outright wherever the index is a runtime value.
  **The failure mode is silent, and admission cannot catch it.** If the `len`-versus-capacity precondition is violated, the resulting access is *in bounds of the capability*: CHERI-TAL types it memory-safe, the §13 certificate is valid, and the device admits a program that reads uninitialized in-compartment memory. That is the wrong-but-well-typed class the enabling theorem's reach clause describes, except that here the wrongness is a confidentiality-relevant read rather than a functional bug, so gate 3 would rest on a producer-side compiler analysis instead of on a checker, which is the arrangement §6 exists to prevent. The preconditions also anti-correlate with the payoff: compressed bounds round outward above the representable-precision threshold, so the analysis is least sound on exactly the large arrays whose hot indexed loops would pay most. **The 64+1-bit capability format widens that argument rather than weakening it** (R-15-007c): the threshold is byte-exactness to 256 bytes, so nearly every array worth eliding a check in falls above it, where a 128-bit format left a few kilobytes of exactly-bounded objects on the sound side. The lever was already declined on the silent-failure-mode ground, which stands alone; what the narrowed format changes is that the anti-correlation is now the common case rather than the large-object case. The panic-to-fault change is a third cost on its own (an unwinding, catchable event becomes fail-stop compartment death), and making it a per-call-site or per-compartment policy adds a configuration surface with a security-relevant default.
  **What survives needs nothing new.** Where the compiler already proves `i < len`, ordinary range analysis removes the check with no CHERI reasoning and no change of semantics, and that is backend completeness. The delta this lever would add over it is precisely the cases the compiler *cannot* prove and would hand to the hardware.
- **Producer-side superoptimization / equality-saturation / search-based (incl. ML and evolutionary) codegen for Tier-2 kernels.** Untrusted-producer status is the right frame for it and is not sufficient, because the validation such an item must mandate cannot be discharged.
  **The available validation does not cover what the transformation can break.** Alive2-class translation validation checks LLVM IR refinement under the LLVM memory model; it models neither capability provenance, tags, bounds monotonicity, nor the purecap ABI, and it models neither constant-timeness nor WCET. Closing that gap means a CHERI-aware verified equivalence checker, which is exactly the artifact R-05-064 / R-18-022 deleted and R-05-065 forbids re-minting. The proposal therefore terminates either in unvalidated search output entering Tier-2 or in the deleted checker.
  **The reliability exposure is real precisely because admission is silent on it.** Admission decides memory safety, the CT taint discipline, and WCET typing, never Tier-2 functional correctness, so a well-typed wrong kernel is admitted and runs, and search-derived code is the class most likely to produce one.
  **The target is also mismatched.** Superoptimization returns on scalar bit and integer sequences, where `Zba`/`Zbb`/`Zbs` already books +2% to +12%, while the rows that dominate the estimates are in-order latency and no-caches on the RVV kernels these tools do not address.
  **What stays admissible is search as offline *discovery*:** Souper- or egg-class search may propose peephole patterns a human then lands in the ordinary backend, under normal review and the existing test suites. That yields optimizations, not shipped binaries. Search over **schedules and instantiation parameters** is untouched by this entry for the opposite reason, and is normative (R-11-015b; the §15 parameter search): its output is a schedule or a parameter set, decided in full by the §11 schedulability check and the five-part §15 admission test, so none of it rests on unchecked functional correctness.
- **Restoring saved vector/matrix state across a partition switch.** The switch zeroizes and saves nothing (§7, R-07-014a); reintroducing a save to spare a slot-spanning computation its own state sink (R-07-014b) buys back availability convenience at the cost of a per-partition save area, a kernel save/restore path and its proof, and a resident copy of one domain's vector state between switches. The deletion argument is normative in §7 (R-07-014).
- **Adding memory encryption or a memory integrity tree back**, and any capability-scoped variant of either.
  These are not recovery levers at all here: the memory path carries no cryptography (§15), so there is nothing to tune, amortize, or partition.
  They are recorded so they are not re-proposed as a *security* addition either: each would add a controller-side latency term to every access, and the tree would additionally require a node cache whose contents are history-dependent, which fails admission-test-3 (§15) exactly as a data cache does.
  The full reasoning is this document's own entry above (*Memory encryption and the memory integrity tree*); the short form is that memory cryptography protects an interface and this machine has none.

---

## Conventional scheduler families: fixed priority and the reservation servers, declined because the literature that settled them measures no timing channel

The evaluated alternative is to adopt what the real-time literature recommends: fixed-priority scheduling under rate-monotonic assignment, or its reservation-based descendants (constant-bandwidth and sporadic servers, seL4's MCS scheduling contexts: the machinery R-07-035 deletes), in place of the §7 table-driven cyclic executive. The first question at any review of the schedule model is whether the whole design collapses into "the real-time literature settled this against cyclic executives in 1992, so adopt fixed priority or a reservation server"; it does not, and the reason is worth writing down once rather than re-deriving.

**The received conclusion is real and is about a different objective.** Locke's *Cyclic executives vs. fixed priority executives* (Real-Time Systems 4(1), 1992) concludes that fixed priority under rate-monotonic assignment generally dominates the cyclic executive, and the multi-core cyclic-executive line that followed still reports the two costs he named: strongly NP-hard schedule construction, and idle time when execution times vary. Both costs land here in full: construction is the R-11-015b search duty, and the idle time is the §17 population wall, whose division R-07-037b stops at the label boundary and no finer. **What that literature does not weigh is the timing channel**, because it is not measuring one.

**On the objective this platform states, the mechanism class is forced, and there is a proof of it.** Ge, Yarom, Chothia and Heiser (*Time Protection*, EuroSys 2019) separate two channels a shared scheduler exposes: **online time**, what a domain observes of its own uninterrupted execution, and **offline time**, the gap between its executions. Partitioning and flushing (the `fence.t` lineage the profile already adopts) closes the online half and leaves the offline half open. Only a schedule whose instants are independent of every domain's behaviour closes the offline half, which is exactly what R-07-032 and R-07-036 are. Gong and Kiyavash (IEEE/ACM Transactions on Networking, 2015) close the other direction information-theoretically: leakage is unavoidable within the deterministic *work-conserving* class, where work-conserving TDMA is privacy-optimal and still leaks. **Elimination requires surrendering work conservation**, so R-07-036 is a consequence rather than a preference (its acceptance clause records both halves), and R-17-006's refusal to add a donation mechanism later is the same statement seen from the cost side.

**The proof-cost half is measured, not asserted.** Connecting Prosa's mechanized response-time analysis to RT-CertiKOS (single-core, sequential, fixed-priority) took roughly 4,100 lines of Rocq for the connection alone, 1,900 of them interface translation (Liu et al., CAV 2019). seL4's MCS branch, the mechanism R-07-035 deletes, reached functional correctness on RISC-V in June 2026, roughly eight years after the mechanism was published, and its integrity and confidentiality proofs are outstanding still. An interval-arithmetic check over a harmonic task set (R-11-006) is close to the cheapest schedulability obligation on offer, and on an objective that treats trust as the scarce resource that is the whole argument.

**What is worth watching, stated as triggers rather than a plan.** Neither line carries an obligation; each aims at the argument above, so a movement reruns it rather than amending anything here.

- **The time-protection proof line.** Buckley, Sison, Wistoff, Millar, Murray, Klein and Heiser (FM 2023) machine-check time protection as a dynamic, observer-relative, intransitive nonleakage property, over a generic OS model rather than seL4 itself. Instantiating it onto seL4's proof stack is the active work as of 2025–26 (Sison, Isabelle Workshop 2026, with l4v-invariant and touched-address groundwork underneath; funded under Cyberagentur's PISTIS-V), and on the hardware side `fence.t.s` extends the flush primitive to out-of-order cores (Wistoff, Heiser and Benini; archival 2025). It is the nearest external work to §17's own obligation, and the residuals to expect inheriting are the ones the project itself states: the hardware–software contract is not fully formalized, the `fence.t` implementation is unverified, and seL4's information-flow proofs do not yet reach timing.
- **Any published work-conserving scheduler carrying an offline-time leakage proof.** This is the one result that would reopen this entry and with it the whole reservation-based family. None exists as of August 2026, and the current literature runs the other way: new scheduler side-channel attacks and leakage quantification on one side, and on the other mitigations that obtain privacy precisely by surrendering work conservation or adding pacing delay. Gong and Kiyavash argue the proof cannot exist for deterministic schedulers, but their model is a shared queueing server rather than a partitioned CPU, so the impossibility is narrower than a casual reading makes it: a gap now a decade old, neither closed nor exploited.

**Disposition:** fixed-priority, dynamic-priority, and reservation-server scheduling are declined for the time-triggered, non-work-conserving cyclic executive R-07-032, R-07-036, and R-07-038 state, R-07-035 deleting the strongest verified instance of the declined class; the inner-scheduling entry below bounds how far scheduling flexibility returns inside a confidentiality label; re-openable only on the offline-time-proof trigger above. The platform axiom decides it as ever (*trust is the scarce resource, performance is subordinated*): the declined family buys back idle time, the freely-spent axis, and pays in the timing channel and the proof mass, the scarce ones.
Non-normative; no spec-body change.

---

## The inner scheduling level: the preemptive and budgeted forms, declined for the same-label rotation

R-07-037b answers the question of where the slot boundary is drawn: the tenant of a discretionary slot is a confidentiality label, and same-label partitions may share one slot under a composition-fixed cooperative rotation over their syntactic poll sites, admitted by the R-11-006b interval arithmetic. The ground is that the timing channel's boundary is the label: compartments sharing a label are mutually distrusting for authority, which CHERI and the manifest enforce, and not for timing secrecy, a flow between them being permitted by the lattice by definition, so every instant the rotation produces is a function of one label's own state and R-07-036, written across confidentiality boundaries, is untouched. Two stronger forms of the same idea were evaluated and are declined here so they are not re-proposed as the natural next step.

- **The priority-preemptive inner level (ARINC 653 and its industrial line: PikeOS, VxWorks 653, the static-partitioning hypervisors).** Every separation kernel in the field pairs the partition window schedule with priority-preemptive processes inside each window, and that inner level is where the information-leakage flaws found by the Isabelle/HOL verification work on ARINC 653 actually lived, in the standard's own service definitions and again in VxWorks 653, XtratuM, and POK. Restoring it would also restore what its deletion bought structurally: a trap source beside the boundary timer (R-07-038, R-07-040) and the preemption term every WCET derivation currently loses rather than bounds (R-07-043). Declined outright; the admitted rotation makes no decisions, so the surface those flaws lived in does not exist to verify.
- **The budgeted inner level (a CBS-style server per member, admitted under Shin and Lee's periodic resource model).** The exact schedulability condition exists and is not the obstacle. A budget is a guarantee only if enforced, and runtime enforcement is an inner timer: a second asynchronous trap, the same structural cost as the preemptive form. On this platform the enforcement is also unnecessary: every member reaction carries a derived WCET (R-11-015) that the admitted, immutable binary cannot exceed on any input, so the guarantee a budget would enforce at runtime is had at admission by arithmetic over constants the artifact already carries (R-11-006b), with the boundary timer capping the group whole and the R-11-007 watchdog theorems as the detection backstop. The periodic-resource condition is therefore declined together with the server it would admit.
- **Intra-label slack reclamation as a mechanism (GRUB inside `SCHED_DEADLINE`; QNX adaptive partitioning).** There is no budget to reclaim: the rotation is work-conserving within the label by the member's own yield, an idle member's turn passing to its sibling with no accounting, no donation, and no state. Across labels, reclamation remains the channel §17 says will never be added (R-17-006), and this entry is not a route around the population wall: the wall counts labels, each browser origin is its own label (R-17-004, R-17-005), and nothing here moves those numbers.

The scoping fact that makes the admitted form consistent with the §7 impossibility argument: Gong and Kiyavash's result binds deterministic work-conserving scheduling across the boundary the observer sits on. A rotation whose every decision is a function of one label's state conserves work only inside that label, so it does not re-enter the class the result forecloses; the schedule's cross-label instants stay independent of every domain's behaviour, which is the property R-07-032 and R-07-036 exist to state.

**Disposition:** the cooperative same-label rotation is normative (R-07-037b, R-11-006b); the preemptive and budgeted inner levels and any intra-label budget-reclamation mechanism are declined and are not to be re-proposed as refinements of it.

---

## Linux BPF OOM hooks, Meta's oomd, and PSI: the policy separation is kept as a composition-time contract, every runtime mechanism is declined

The evaluated alternative is the capacity-exhaustion machinery general-purpose Linux converged on during the 7.x development cycle: a BPF hook ahead of the kernel OOM killer so a workload-specific policy can select a victim task or memory cgroup, or free memory by another mechanism, with the ordinary kernel killer retained as the final fallback; a PSI-triggered path so intervention can begin before terminal deadlock or livelock; and, in userspace, Meta's oomd consuming cgroup v2 and Pressure Stall Information through a detector/action plugin system that typically terminates a whole workload group early ([mm: BPF OOM](https://lwn.net/Articles/1019129/), [the v3 series summary](https://www.phoronix.com/news/Linux-OOM-BPF-2026), [oomd overview](https://facebookmicrosites.github.io/oomd/docs/overview.html), [Meta's design rationale](https://engineering.fb.com/2018/07/19/production-engineering/oomd/), [source](https://github.com/facebookincubator/oomd)). The motivating argument for the hook is sound on its own terms: victim selection depends on workload organization, userspace daemons are hard to keep reliable under exactly the pressure they exist to answer, and a policy that runs must then demonstrate that it made sufficient progress. The question the evaluation answers is how much of that machinery a machine with no online allocator has any use for.

**The condition the machinery answers does not exist here.** A Linux global OOM event is the collision of overcommit, demand paging, swap, reclaim, and a dynamically competing memory hierarchy, and R-08-045 makes the corresponding state unreachable: every byte is charged to the signed composition, aggregate insufficiency is a build-time rejection, and no runtime path requests unplanned storage from a global pool. What remains is narrower and more general: finite precomposed pools whose storage is statically reserved can still fill at runtime (R-08-046), which is a per-pool condition with an owner rather than a machine condition with a victim search. That reframing is what makes every mechanism below unnecessary while keeping most of what operating the mechanisms taught.

**Each mechanism, taken separately.**

- **The BPF policy hook** separates *when to intervene* from *what to do*, which is kept; the mechanism is runtime-loaded policy, sleepable hooks, dynamic iteration over a workload hierarchy, generic victim selection, and a second policy engine as fallback, all of which conflict with a finite admitted state space and a static proof posture. R-12-087 takes the separation as a finite composition-time mapping from enumerated detectors to enumerated actions, compiled into the synchronous Lustre control plane, with no loadable policy of any kind.
- **PSI** is the insight that progress degradation beats raw utilization as a trigger, and it has no consumer here: PSI measures wall-clock time lost to reclaim, refault, compaction, paging, and swap stalls, none of which exist on this machine. R-12-088 keeps the insight as typed forward-progress signals against declared protocol bounds (pool occupancy, oldest-waiter age, quarantine backlog, teardown completion age), each with a fixed cadence and an admitted reaction time, collected without scanning anything proportional to the machine.
- **oomd's plugin system and group-level kill** contribute three lessons: detector and action should be independently testable, the recovery unit should coincide with an ownership and restart boundary, and protected workloads need explicit policy rather than an inferred score. They land as the compiled detector/action table (R-12-087), the ownership-closed victim unit whose teardown closure the compositor proves (R-16-024), and composition-fixed criticality classes with reserved critical capacity (R-12-089). The daemon itself is declined: the sentinel and supervisors already hold reserved execution (R-16-023), so there is no separate process to keep alive despite pressure and no deployment or telemetry pipeline beside the platform's own.
- **The kernel killer as final fallback** is declined outright: behind each pool stands its own finite ladder ending in the owner's stop and the already-authorized watchdog reset (R-16-025, R-16-005), so no generic victim selector waits behind customized policy, and the patch series' demand that a policy demonstrate actual progress survives as the verified completion predicate with `reclaim_min` and `complete_by` rather than as a fallback trigger.
- **`oom_score_adj`, badness scoring, and the cgroup hierarchy walk** import nothing: scoring is replaced by the criticality classes, and the hierarchy walk by manifest-declared ownership groups; no detector searches the component graph and no action computes a victim score at runtime.

**What the import would have cost is the usual currency.** A loadable policy hook is unattestable policy in the signed composition's blind spot; a PSI subsystem is a statistic made normative in a document that admits none; a victim search is an unbounded scan on the recovery path, which R-16-023 requires to be pre-funded and independent of the exhausted pool; and a fallback killer behind the declared ladder is precisely the ambient supervisor decision the R-08-047 verdict exists to make unreachable.

**Disposition:** the BPF OOM hook, PSI, oomd, the cgroup-style dynamic hierarchy, badness scores, emergency reserves, global reclaim, and any global victim selection are declined in every part; the operational lessons (detection separated from action, workload-aware group-level policy, progress-based triggering, reliability of the responder under pressure, verified reclamation, hysteresis and rate accounting, a unified typed event pipeline) enter the normative body as the capacity-exhaustion contract of §§8, 12, 14, and 16 (R-08-045 through R-08-047, R-12-087 through R-12-090, R-14-014, R-14-015, R-16-023 through R-16-028), its composed availability cost booked at R-17-030u and its verification campaign at R-18-036. Non-normative; the spec-body change is that contract, not any import of the mechanisms.
