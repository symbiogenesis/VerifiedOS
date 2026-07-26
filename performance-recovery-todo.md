# Performance Recovery: Pure-Win TODO (non-normative)

> Companion to [performance-estimates.md](performance-estimates.md) and [verification-maximal-os.md](verification-maximal-os.md).
> Where the estimates doc *accounts for* the accepted price of the security choices, this doc enumerates only the **pure wins**: recovery levers that cost nothing on the scarce axis.
> A **pure win** recovers performance while **shedding no security property, reviving no deleted mechanism, opening no channel, and adding no axiom or TCB surface**, admissible precisely because it is *static, ahead-of-time, off-device*, and its output is **re-checked at admission** (§6).
> "Engineering is free; trust is the scarce resource," so every item may be pursued to arbitrary aggressiveness without touching the trust base.
> Checkboxes track progress; nothing here is normative, and no item may relax the §15 admission test.
> **The list is confined to off-device software and composition-time levers**, because the untrusted-producer, re-checked-artifact architecture is what keeps them free of trust cost. The one *in-model* (hardware) pure win, **decoder-stage macro-op fusion**, is booked in the spec instead (§2, §15): fused and unfused executions reach identical architectural state, so the existing RTL-against-Sail *functional* refinement carries it at no proof cost. The spec calls this list fusion's "off-device complement" (§15), and the complement is real work: the decoder fuses only *adjacent* pairs from a frozen set, so the gain exists only if the compiler emits them and the scheduler does not split them (§1A).
>
> **What "recovery" here means, and where the earlier "it all cancels" reading was wrong.**
> Figures are measured **intra-design** (the same frozen instantiation *un-optimized vs. optimized*) against the rows of [performance-estimates.md](performance-estimates.md).
> An earlier revision of this doc claimed that almost every lever is "universal engineering a conventional toolchain runs too, so *ceteris paribus* it appears on both sides and **cancels**."
> **That inference is invalid, and correcting it is the main structural change here.** A pass cancels only if it yields the *same delta* on both machines; running it on both sides is not sufficient.
> The deltas are not the same, and the asymmetry is systematic: the **marginal return** of static scheduling, code and data layout, and devirtualization is *low* against an out-of-order core with a TAGE-class predictor, whose hardware recovers dynamically from whatever the compiler got wrong, and *high* here, where **the compiler is the only latency-hiding mechanism, the only placement mechanism, and the only branch-prediction-recovery mechanism that exists.**
> Wherever the deltas differ, running the pass on both sides **does** narrow the inter-design gap, by the difference.
> What never narrows is the residual *after* every pass has run on both machines: the deleted dynamic mechanisms, booked as accepted costs in the estimates (§ *Out of scope*, below) and recovered nowhere here.
> These items do **not** catch up to a chip that keeps the dangerous mechanisms; they stop the secure design from running slower than it provably has to, and several of them do close real distance while doing it.
>
> **The three classes below replace the old universal/differential binary**, which conflated "the baseline also runs this pass" with "the pass is worth the same on both", and separately mis-scored the levers that realize a *gain* row as if they recovered a *loss* row.

## The three classes

Every item is tagged with one, and the tag is the honest statement of what it buys:

- **[R] Realizes.** The lever is the software key to a hardware gain the estimates **already book** as a positive row (RVV, macro-op fusion, `Zicond`). It recovers no loss row and must not be scored against one; without it the booked gain is simply not collected.
- **[D] Differential.** The lever exploits structure the conventional baseline **does not have** (a compose-time-frozen component graph, capability bounds and tags on die, a WCET-bounded frame, a partitioned SRAM map). Its marginal return is strictly higher here, so it narrows the inter-design gap by that difference. Several still only *offset a self-imposed tax* and never overtake the baseline; the item says which.
- **[U] Universal, higher margin.** An ordinary optimizing-compiler pass the baseline runs too, but whose marginal return is larger here because no dynamic mechanism papers over its absence. It narrows the gap by the difference in marginal return, which is smaller than a [D] lever's and is not zero.

## The pure-win gate

An item earns a place on this list iff it clears all six:

1. **Recovers performance** on at least one row of [performance-estimates.md](performance-estimates.md), *intra-design* (the same instantiation, un-optimized vs. optimized). An item that realizes a booked **gain** row is tagged **[R]** and may not additionally claim a loss row: that is double-counting, and the previous revision did it for `Zicond`.
2. **No trust widening**, no new axiom, no TCB growth; the produced artifact is re-checked, so its *producer* stays untrusted.
3. **Sheds no security property**, every theorem the spec claims still holds, unchanged.
4. **Revives no deleted dynamic mechanism and opens no channel**, no speculation, OoO, dynamic prediction, SMT, JIT, DVFS/turbo, prefetch state, or reservation state sneaks back.
5. **Stays inside the proven-safe envelope**, passes the five-part §15 admission test and the §8 non-interference / §11 WCET obligations.
6. **Does not spend a different scarce resource.** No lever may loosen a WCET bound, worsen WCET *analyzability*, or grow the image against the §15 SRAM capacity budget. This clause is new, and it is not ceremonial: on a machine with no I-cache, a +25–30% code-size penalty from the deleted C extension, and a composition-time capacity budget measured in square millimetres (§15), **code size is a hard admission quantity, not a preference**, and schedulability is a gate rather than a metric (§11). Items that trade against clause 6 are marked and arbitrated under **Tensions**, below.

**The enabling theorem (§6).**
*"A compromised compiler or analyzer cannot mint a valid certificate for a property its output lacks"*, so the optimizer is untrusted evidence-producing machinery.
Aggressiveness is therefore **unbounded by trust**: any transformation whose result still type-checks (CHERI-TAL, §5) or proof-checks (CIC kernel, §6) is admissible however it was produced.
This single fact is what makes the whole list pure.
**Its exact reach is narrower than "wrong answers cannot ship", and the difference matters:** the checkers decide memory safety, the CT taint discipline, and the WCET typing; **nothing on the device decides functional correctness of non-TCB code.** A miscompilation that is memory-safe, constant-time, and WCET-typed is admitted and runs. Purity is therefore a statement about the *trust base*, not about *correctness*, and levers whose failure mode is a wrong-but-well-typed binary carry a **producer-side validation obligation** (translation validation, differential testing) as engineering hygiene, never as a trust argument.

---

## 1. Off-device compiler optimization: untrusted optimizer, re-checked output

*All items extend the in-scope §18 certifying-compiler workstream; none add a workstream to the TCB.
The output carries the same memory-safety / constant-time / WCET certificates (§5, §13); the optimizer only makes the same-certified binary faster.
Nothing here contradicts the §5 rule that deleted the CryptOpt toolchain (R-05-064, R-18-022): that rule bans minting a **net-new verified artifact** whose only yield is speed, and every tool below is untrusted producer-side machinery that mints nothing.*

### 1A. Differential and realizing levers, ordered by expected value

- [ ] **[D] Whole-image partial evaluation against the composition graph.**
  The component graph, capability manifests, IFC labels, static grants, devicetree, cyclic-executive schedule, and browser origin pool are **build-time constants** (§7 static composition, §8, §14): the machine admits no compartment, endpoint, or grant minted at runtime.
  So specialize the entire image against them: **devirtualize every cross-compartment call to its single static callee**, specialize the seal/switch trampoline per graph *edge* rather than compiling one generic switcher, monomorphize the kernel per core class (§15 core-class table), constant-fold manifest and authority lookups into immediates, and resolve Rust `dyn` dispatch wherever the graph fixes the callee set.
  **This is the largest genuinely differential software lever available**, and its size comes from a hardware fact rather than a compiler one: with no BTB and no return-address stack, indirect branches and call/return dispatch pay **full pipeline-latency mispredict-equivalent penalties** (§15, the accepted-costs paragraph under static-only prediction). Every indirect call the graph lets the compiler turn into a direct one removes a penalty the baseline's predictor would have absorbed for free, so the pass is worth a rounding error there and a great deal here.
  A conventional OS cannot copy it: dynamic linking, `dlopen`, runtime plugin registration, and mutable capability tables are exactly what keeps its call graph open.
  Attacks the in-order (−35% to −60%), static-prediction (−10% to −30%), cross-core-coordination (−2% to −15%), and context-switch (−2% to −10%) rows.
  *Keeps it pure:* it specializes against the graph the §8 non-interference theorem is already stated over, mints no authority and no edge (specializing a call cannot create one the graph lacks), and the output re-type-checks in the CHERI-TAL like any other binary. Note under gate 6: per-edge trampoline specialization multiplies code, so it is **size-budgeted** (Tensions, below).
- [ ] **[D] Static data placement: bank-, macro-, and tier-aware layout.**
  **The lever the spec points here for and this list previously did not contain.** §15 says scalar cores get no scratchpad because "that irregular latency is recovered off-device by static layout, the performance-recovery levers", and the estimates' no-cache row says the same ("partly recovered off-device by static layout"): both cite a lever that was missing from this document, leaving the **no-hardware-caches (−10% to −50%)** row, the second-largest single loss in the design, entirely unattacked.
  The lever is hot/cold field splitting, structure splitting and merging, affinity-driven co-location of objects touched together, and explicit assignment of hot working sets to the island's least-contended SRAM banks and macros, all frozen into the signed image.
  Strictly differential, and for the sharpest possible reason: on the baseline the cache performs placement dynamically and the compiler's marginal contribution is small, while **here layout is the only placement mechanism in the machine.** The same fact that makes the loss row large makes the lever's marginal return large.
  Attacks the no-cache (−10% to −50%) and SRAM bank/macro partitioning (−5% to −20%) rows, and compounds with the no-MMU gain (+5% to +25%) on pointer-chasing.
  *Keeps it pure:* placement is data, fixed in the image, a function of the program and not of execution history, so it is the exact opposite of the reactive feedback loop §15 deletes; bank assignment stays inside the island's own partition, so no cross-island bandwidth is borrowed and §8 is untouched; flat SRAM latency means placement cannot introduce a data-dependent timing term.
- [ ] **[D] WCET-directed compilation: compile for the worst case, not the average.**
  On a non-work-conserving frame a task's cost *is* its slot width, and slot widths come from WCET, so **reducing a WCET bound buys schedulable frame capacity, which is throughput.** Path balancing, static loop bounds in place of data-dependent ones, hoisting variable-trip-count control flow out of bounded regions, and choosing the lowering with the tighter bound over the one with the better average all pay here.
  **Maximally differential: this lever is worth nothing at all on the baseline**, whose work-conserving scheduler bills actual time and to which a tighter worst case is invisible. It is also the only software-side attack on the non-work-conserving row, which this list previously attacked only from the schedule-synthesis side (§2).
  Attacks the non-work-conserving-scheduler (−10% to −35%) row and, by tightening the bounds the §11 interval-arithmetic check consumes, raises the population rung a given task set admits at (§11, §17).
  *Keeps it pure:* it strengthens the §11 obligation rather than relaxing it, and it is the one lever that improves gate 6 instead of trading against it.
- [ ] **[D] Capability-width-aware data representation.**
  The purecap tax is paid in *pointer width*, so spend the compiler on width, not only on checks: prefer one base capability plus 32/64-bit indices over arrays of capabilities, minimize capability liveness across calls so spills land in 64-bit slots rather than 128-bit ones, pack capability-dense structures so a granule carries more payload per tag, and prefer offset arithmetic to derived-capability construction where the bound is unchanged.
  Differential, and it attacks the CHERI row **directly** rather than by clawing back software checks the way the elision item below does, which plausibly makes it the larger of the two.
  Attacks the CHERI purecap 128-bit capability (−2% to −12%) row and, through reduced footprint, the memory-bound rows.
  *Keeps it pure:* fewer capabilities in flight is strictly less authority in flight; every retained capability keeps its exact bounds and tag, so §5 spatial safety and the §13 certificate are untouched; index arithmetic is address- not secret-dependent, leaving constant-time undisturbed.
- [ ] **[D] Switch-cost minimization: shrink the live V/M state at yield points.**
  The `fence.t` + eager V/M zeroize at a partition switch (§7, §15) costs in proportion to the architectural state that is live, so have the compiler narrow `VL`, release vector and matrix registers, and sink long-lived vector values to memory *before* a scheduled yield point, which the static frame makes statically known.
  Differential: the baseline has no eager-zeroize obligation to minimize, and no compile-time-known switch points to minimize it at.
  Attacks the `fence.t` + eager zeroize (−2% to −10%) row; compounds with `Zicboz` (+0% to +3%), already booked.
  *Keeps it pure:* it reduces the *amount* of state to zeroize, never the obligation to zeroize what remains; the switch still eagerly zeroizes everything live, so the §8 argument is unchanged.
- [ ] **[D] Ring-window and message layout for the multikernel.**
  Share-nothing per-core kernels exchange messages through shared-SRAM ring windows under `Ztso` fences (§7, §15) across a TDM NoC with static slots. So align ring buffers to the 16-byte tag granule (which §12's allocation discipline already makes free), size and batch transfers so a logical exchange lands **inside one TDM slot** rather than straddling two, and amortize IPI round-trips by batching at the source.
  Differential: a coherent baseline has no slot cadence to align to and no granule write path to respect; the compiler and the composition tooling here both know the schedule.
  Attacks the cross-core-coordination (−2% to −15%), TDM-NoC (−5% to −15%), and no-coherence (−5% to −20%) rows.
  *Keeps it pure:* it changes the *shape* of traffic inside a compartment's own statically granted slots and windows, never the slot allocation, the arbitration, or who may address what.
- [ ] **[R] Autovectorization / SLP onto RVV, the dominant realizing lever.**
  Lift scalar inner loops onto the already-in-profile vector unit (VLEN 256 C-class / 4096 V-class, §15).
  Moving a loop onto RVV converts an in-order-scalar row into a vector-gain row.
  Scored as **[R]**: it is the key that collects an already-booked hardware gain (the RVV row, +100% to +1500%), not a recovery of a loss row, and a conventional autovectorizer targets its own vector unit too, so only the wider VLEN, already counted, differs.
  *Keeps it pure:* secret-touching output still carries the binary-level constant-time certificate (§5/§13), which rejects any secret-dependent vectorization.
- [ ] **[R] Fusion-idiom-aware instruction selection and scheduling.**
  §15 admits decoder-stage macro-op fusion over a **frozen set of adjacent pairs** (`lui`+`addi`, `auipc`+`addi`/load, `slli`+`add` indexed addressing, compare-and-branch, short dependent-ALU chains) and books it as a **+3% to +10%** gain, and §15 explicitly names this list its off-device complement.
  The complement is two obligations the doc previously left unstated: **emit** the fusable idioms in preference to equivalent non-fusable encodings, and **forbid the scheduler from separating a fused pair** (see Tensions: aggressive scheduling and software pipelining destroy the adjacency fusion requires, so the booked gain can be lost while chasing the in-order row).
  Scored **[R]**: it collects a booked gain; it recovers no loss row.
  *Keeps it pure:* fusion is architecturally transparent (fused and unfused executions reach identical architectural state), so no certificate, WCET table entry, or CT statement is re-derived; the compiler is merely emitting one encoding rather than another.
- [ ] **[R] If-conversion onto `Zicond`, scoped honestly.**
  Convert unpredictable forward branches into branchless `czero.eqz/nez` selects.
  **Correction to the previous revision:** `Zicond` is booked in the estimates as a **gain row (+0% to +4%)**, so claiming it *also* recovers part of the static-prediction (−10% to −30%) loss row counted it twice. It is **[R]**, the same status as autovectorization: the compiler collects a booked gain.
  Two further scope limits the earlier text omitted. Applicability is narrow: `czero` if-converts **register-to-register arms only**, because this machine speculates nothing, so any arm containing a load, a store, or a trapping operation cannot be if-converted at all. And the security half is **not a performance lever**: eliminating a secret-dependent branch is *mandatory* under the CT taint discipline (§5), not optional recovery, so the performance credit is confined to non-secret unpredictable branches.
  Still worth more here than on the baseline in marginal terms, since a dynamic predictor would have nailed many of these branches and can even be *hurt* by if-converting a well-predicted one.
- [ ] **[D] Elide software bounds checks onto CHERI's hardware bounds, under a certified precondition.**
  Teach the certifying Rust→RV64+CHERI toolchain (§18) to drop a panicking language-level bounds check where the capability that will be dereferenced **already bounds exactly the region the check tests**, letting the hardware bound fault instead. Unclaimed today: current purecap Rust (Morello / CHERI-RISC-V) makes raw-pointer and `unsafe` code spatially safe yet still emits the safe-Rust check *on top of* the hardware bound.
  **The previous revision stated this unconditionally and was unsound.** Three preconditions are load-bearing, and elision without certifying them removes the only check that exists:
  1. **`len` is not the capability bound.** A `Vec`'s capability is bounded to *capacity*; a fixed array inside a struct may carry the struct's bounds. Eliding `v[i]` for `len ≤ i < capacity` silently admits a read of in-bounds uninitialized memory that hardware will not fault.
  2. **CHERI bounds are compressed and round outward.** Above the representable-precision threshold the enforced region is strictly larger than the object, so elision admits the small overflow the software check would have caught.
  3. **A panic is not a trap.** A Rust bounds panic is a defined, unwinding, catchable event a compartment may legitimately rely on (a codec compartment returning an error); a capability fault is fail-stop compartment death. The outcomes are both *safe* but they are **not equivalent**, so "semantically transparent" was wrong: this is an availability-semantics change, admissible under the crash-only posture (G5) but to be chosen deliberately, per call site or per compartment policy, never silently.
  So the admissible form is: **elide only where the compiler certifies the capability's bounds are exactly the checked region** (exact-bounded subslices, `len == capacity`, fixed-size arrays given exact sub-object bounds), and only where fault-stop is an acceptable substitute for unwind.
  Each check so removed is one fewer instruction (in-order row), one fewer forward branch (static-prediction −10% to −30% row), and less code (no-C −2% to −12% row), together partially offsetting the CHERI purecap (**−2% to −12%**, corrected from a mis-cited "−3% to −15%") row.
  Differential, spending on-die capability bounds a conventional compiler cannot copy, yet only *offsetting a self-imposed tax*, never overtaking a baseline that never paid the CHERI width.
  *Keeps it pure:* under the precondition the bound is still enforced, by hardware already on the die, adding no µarch; the output still type-checks memory-safe in the CHERI-TAL (§5/§6), the §13 certificate is undisturbed, the check is address- not secret-dependent, and fewer instructions only tighten WCET (§11).
- [ ] **[D] Lower temporal-safety instrumentation onto the revocation and tags already on the die, not a software refcount, and *not* a hardware one.**
  The spatial elision has a temporal mirror, but the mechanism is *not* a counter: CHERI carries **no hardware reference-count primitive**, copying a capability is an un-intercepted move, so a hardware counter would be new microarchitecture (fails admission-test-3, §15, and the "no new µarch" premise this whole list rests on).
  What the die *does* run is the **tag + budgeted revocation sweep** (§8, "derivation-tree revoke + CHERI sweep," CHERIoT/Cornucopia lineage, with the deterministic per-load revocation filter) and the **linear/affine capability types** the CHERI-TAL already carries as the temporal residual (§5, §13).
  So the lever is a compiler that discharges use-after-free with *those*, eliding software shadow-memory and heavy-atomic UAF guards, and, where a genuine count survives (CoW-extent refcounts §10, `Rc`/`Arc` sharing), uses CHERI's *precise* tags to license non-conservative or non-atomic counting rather than a `Zaamo` atomic on every clone-and-drop.
  That is CheriOS's "claim" (an object-granular refcount made sound by revocation) produced by an untrusted, re-checked compiler.
  **Row correction, and a demotion.** The previous revision claimed this "recovers the `Zaamo` / atomics −0% to −3% rows". It does not: that row is the cost of the **absent CAS**, and `Zaamo` itself is scored as a *gain*, so eliding refcount atomics recovers neither and the item did not clear gate 1 as written. The honest statement is that it recovers **an unbooked micro-cost** (instrumentation and atomic traffic the estimates never scored) and keeps the §13 temporal obligation structural rather than instrumented. Its size is further reduced by the share-nothing multikernel (§7): with no cross-core shared mutable memory, cross-core `Arc` traffic barely exists to elide.
  Kept for the structural argument, not the percentage; **if the estimates never grow a row for instrumentation cost, this item is a §13 hygiene item rather than a performance lever.**
  *Keeps it pure:* leans only on mechanisms already in the design, adds no µarch and no channel, and is sound precisely because the §6 checker still re-checks the temporal-safety certificate on the output.

### 1B. Universal passes whose marginal return is higher here

- [ ] **[U] Software pipelining / modulo scheduling / static load hoisting.**
  The in-order core has no out-of-order window to hide load or FP latency behind, so the scheduler must do it offline: overlap iterations, hoist loads ahead of use.
  **Row correction:** the previous revision credited this with recovering a "no-prefetch (−3% to −15%)" row. **No such row exists.** The estimates score no-prefetch at **≈0%** and state that the remaining load-use latency "is hidden instead by static instruction scheduling", explicitly warning that charging it here would **double-count** against the no-cache row. This lever's real targets are the in-order (−35% to −60%) and no-hardware-caches (−10% to −50%) rows.
  Higher margin than on the baseline, whose OoO window hides the same latency dynamically, so the compiler's marginal contribution there is small; the gap narrows by that difference, though static scheduling still wins mainly on regular loops rather than the branchy code that dominates the in-order row.
  *Keeps it pure:* static hoisting, **not** the excluded `Zicbop` prefetch hint, no new µarch state, no channel. Trades against fusion adjacency under **Tensions**.
- [ ] **[U] Deterministic PGO fall-through + BOLT-style post-link layout.**
  Lay hot paths out as fall-through to hit the backward-taken / forward-not-taken static rule, and pack hot code to fight the +25–30% code-size and fetch-bandwidth pressure from the deleted C extension.
  §10 and §15 already book this as "partial recovery"; make it a first-class, maximized pass.
  Higher margin: against a TAGE-class predictor, layout mistakes are recovered in hardware and BOLT's yield is modest; here the static rule *is* the predictor, so layout is the whole of it.
  *Keeps it pure:* the profile is a **signed, reproducible build input** (§10, R-10-034), never runtime-learned predictor state.
- [ ] **[U] LTO, aggressive inlining, loop unrolling, superblock formation.**
  Cut branch density (fewer static mispredicts), widen the scheduler's window for pipelining, and expose more loops to the vectorizer.
  Recovers part of the static-prediction and in-order rows; compounds with everything above.
  **Explicitly gate-6-constrained**, and this is the one item on the list most likely to violate it: inlining and unrolling buy speed with code size, on a machine with no I-cache, a +25–30% no-C size penalty, and a hard SRAM capacity budget. See **Tensions**.
- [ ] **[U] Superoptimization / equality-saturation / search-based (incl. ML and evolutionary) codegen for hot kernels.**
  Because the artifact is re-checked (§6), point unbounded offline search at the hottest routines: the whole modern SMT-backed stack enters *as untrusted, re-checked oracles*, **Souper**-class SMT superoptimization, **egg** / equality-saturation rewrite search, and **Alive2**-style translation validation gating each peephole, none touching the trust base, because the emitted binary still carries the CHERI-TAL and constant-time certificates the §6 checker re-validates.
  The design's distinctive claim is that it can point **unbounded, untrusted** search at the problem without TCB growth: a *trust* win. The speed itself is universal.
  *This is the only admissible home for "evolutionary algorithms", on codegen, never on the spec or the proofs.*
  **Correction, and the reason Alive2 is mandatory rather than decorative.** The previous revision said "a wrong answer simply fails the checker". **That is false for the case that matters.** The checkers decide memory safety, CT taint, and WCET typing; **no per-install checker decides functional correctness of Tier-2 application code**, so a search bug ships a memory-safe, constant-time, WCET-typed, *functionally wrong* application, silently. Producer-side translation validation and differential testing are therefore a **required** part of this item, as engineering hygiene: they are what keeps the output correct, while the §6 re-check is what keeps the *trust base* small. Do not conflate the two.
  **Scope limit (the CryptOpt line, main-spec §5, R-05-064 / R-06-026 / R-18-022):** this item is pure only where the *existing* checkers re-validate everything the search could break, i.e. code whose obligations are the CHERI-TAL derivation and the CT taint-typing.
  It does **not** extend to TCB code carrying a **functional-refinement** obligation (the kernel, the crypto core's field arithmetic, storage L0), because no per-install checker re-validates "this binary refines its Gallina spec": admitting searched assembly there would require minting a net-new verified equivalence checker, which is exactly the artifact §5 deletes for buying speed alone.
  So TCB hot paths are sped by *compiling better verified C*, never by admitting searched assembly, and the gate-2 phrase "the produced artifact is re-checked" must be read as *re-checked for every property it carries*, not merely for the type-level ones.

---

## 2. Off-device design-space search: admission tests as hard constraints

*Optimize the **instantiation**, never the specification.
Every candidate is frozen at composition time, Sail-modeled, and must clear the five-part §15 admission test plus §8 NI / §11 schedulability, the proof obligations serving as the feasibility oracle.
The spec stays invariant, so this widens no trust base, and is the correct reading of "run a search over the design."
DSE is ordinary chip-design practice and the conventional baseline is itself a DSE output, so the class here is **[U]**: it keeps the secure instantiation from being needlessly detuned rather than closing distance.*

- [ ] **[U] Static schedule synthesis.**
  Pack the cyclic-executive slots (§7) and the TDM-NoC arbitration schedule (§15) with an ILP / SMT / evolutionary optimizer, subject to the §11 interval-arithmetic schedulability check.
  Tighter packing recovers the non-work-conserving-scheduler idle (−10% to −35%) and TDM-NoC (−5% to −15%) rows.
  Compounds directly with **WCET-directed compilation** (§1A): the synthesizer's input *is* the WCET table, so every bound the compiler tightens is frame capacity this pass can then allocate. Treat the two as one loop.
  This shrinks the design's **self-imposed** idle only; it can never reach the baseline's work-conserving efficiency (that would need slack donation = a timing channel), so the row is narrowed, not closed.
  *Keeps it pure:* the frame stays **non-work-conserving**, no slack donation, no runtime scheduling decision, it is merely a better-packed static frame.
- [x] **[U] Micro-architectural DSE over the frozen parameters.**
  Multi-objective (perf / area / power / WCET / proof simplicity) Pareto search over: VLEN per class, issue width and pipeline depth, scratchpad sizes, SRAM bank/macro/tier assignment, and the TDM-NoC schedule (there are no hardware caches to size, main-spec §15).
  Partially recovers the memory-partition (−5% to −20%) row.
  Universal: the conventional baseline is itself a DSE output, so this selects the best *admissible* secure configuration rather than closing distance.
  **One parameter deserves naming, because it is the only hardware lever aimed at the biggest unlevered row.** §15 defaults scalar cores to *no* local memory tier but admits **a scalar scratchpad as a design-space-exploration parameter** "where a class's access is predictable and high-reuse enough for static staging to pay". That is a live search dimension against the no-hardware-caches (−10% to −50%) row, and it is not free on the scarce axis (a modeled region, partition-switch save-and-zeroize state, and RTL ⊑ Sail surface), which is precisely why it belongs to the multi-objective search with proof simplicity as a first-class term rather than to a hand decision. It is also, per §15, a *poor* bet for the irregular pointer-chasing that motivates it, so the search should expect it to pay only for the predictable-access classes.
  *Keeps it pure:* each candidate is a static, Sail-modeled, admission-checked config, and **no history-indexed dynamic structure exists to size**, the design carrying no data cache and no memory-integrity structure (main-spec §15).
  *Done, wired into [verification-maximal-os.md](verification-maximal-os.md) §15 (normative) and [implementation-plan.md](implementation-plan.md) §1; the §17 Sail ⋈ RTL residual names it the standing mitigation. The scalar-scratchpad dimension above is the open sub-item.*

---

## 3. Faster pure-interpreters: recover the JIT loss without runtime codegen

- [ ] **[U] Faster pure-interpreters for the browser's JS and Wasm.**
  Under no-JIT (§14) the browser runs downloaded JS and Wasm *interpreted*, Boa/Nova-lineage for JS, wasmi for Wasm (both pure-Rust, §12/§14 and [userspace-porting.md](userspace-porting.md)), because web content is dynamic and W^X (§14) forbids on-device codegen.
  Claw the overhead back with threaded / computed-goto dispatch, **offline-selected superinstructions** (the selection computed off-device from a corpus and shipped as a table, i.e. data in the signed image, never generated code), and **data-plane inline caches**.
  *Keeps it pure:* no runtime codegen, the W^X invariant (§14) holds by construction.
  **The inline-cache argument must be written down rather than asserted.** An inline cache *is* history-dependent state, which is the class §15 deletes in hardware, so its admissibility rests on three facts and not on the "it's only data" slogan: it lives inside a single origin compartment's own memory (§14 per-origin compartments), so it crosses no confidentiality boundary and §8 is untouched; it is ordinary compartment-private data under CHERI bounds, not microarchitecture, so no admission test applies to it; and it introduces timing variance *within* a discretionary slot whose width is fixed by the §11 rung, so it cannot move time between compartments. What it does forfeit is intra-compartment timing determinism, which the browser does not have and is not promised.
  This *narrows* the no-JIT gap but cannot close it, an interpreter, however tuned, does not match a JIT, so the −60% to −90% row is mitigated, not erased.
  **On AOT, corrected to what is actually true:** the earlier flat claim that "no off-device AOT shortcut exists" is right about the *web delivery path* and slightly overstated as a general statement. Web-delivered JS and Wasm are dynamic content and Wasm is never a system execution target (§14), so there is no AOT route for them; but AOT is available to anything that leaves that path for the §13 install path, and two consequences follow that this list should name: the browser's **own** chrome, built-in libraries, and privileged JS are not downloaded content and must be compiled natively rather than interpreted, and a web application that ships as an installed, admitted app (§13, §14's source-level on-ramp) is an ordinary native Tier-2 citizen paying none of the −60% to −90%. The product lever is to make that path attractive; the platform lever does not exist.

---

## 4. Application- and composition-level restructuring: software-only, no trust cost

- [ ] **[U] Data-oriented restructuring onto the fast paths.**
  SoA layouts, batching, and replacing pointer-chasing with vectorizable / matrix-shaped structure move general-purpose work onto the RVV, systolic-GEMM, and table-free-crypto paths (§15) that already run at parity-to-many-×.
  The single-address-space (no MMU, §7) already helps pointer-chasing (+5% to +25%).
  Ordinary source-level engineering that changes no mechanism; a conventional chip benefits identically, so this moves work onto the fast paths both machines share rather than closing distance. Its marginal return is nonetheless higher here for the same reason as static placement: there is no cache to rescue a bad access pattern.
- [ ] **[D] Compartment-granularity budgeting at composition time.**
  The design's largest *user-facing* performance cost is not in the big table at all: it is §17's **population wall**, where a non-work-conserving frame **divides rather than shares**, discretionary capacity collapses as roughly 1/n, a background origin at the 32-rung holds on the order of one percent of one core, and twenty idle background compartments burn twenty slots that no mechanism will ever reclaim (§17 states plainly that none will be added, because that mechanism *is* the channel the design is buying). Nothing on this list previously touched it.
  The only pure lever against it is the divisor: **choose compartment granularity deliberately at composition time**, keep the discretionary population small, prefer one compartment doing batched work to several waiting ones, and design apps so deep sets are *retained state* rather than live compartments, which is the shape §14 and §17 already describe.
  Differential in the strongest sense (the baseline's work-conserving scheduler makes the divisor free) though it is a *shape* lever rather than a percentage: it does not recover a row, it decides where the machine sits against the wall.
  **State the tension rather than hide it:** this pulls directly against §14's *required* intra-app library compartmentalization for attacker-facing parsers, and that requirement wins. The lever applies to discretionary granularity that is chosen for tidiness, never to a boundary §14 mandates.
  *Keeps it pure:* it is a compose-time authority-partitioning choice, changing no mechanism, no schedule mechanism, and no theorem; fewer compartments is less isolation, so it is bounded by §14's floor and is a budgeting discipline, not a licence to flatten.

---

## Tensions between levers

The list is not internally free: three pairs pull against each other, and the previous revision listed both halves of each without arbitrating.

- **Instruction scheduling vs. macro-op fusion.** Software pipelining and aggressive scheduling reorder instructions; the decoder fuses only **adjacent** pairs from a frozen set (§15). A scheduler ignorant of the fusion table will split fused pairs and give back part of the booked +3% to +10% while chasing the in-order row. **Arbitration:** the fusion table is a scheduler input, and pairs are atomic to the scheduler unless breaking one measurably wins on the same block.
- **Inlining and unrolling vs. code size.** Speed bought with size lands on a machine with no I-cache, a +25–30% no-C penalty, and a hard SRAM capacity budget (§15), so it can regress the very fetch-bandwidth pressure PGO/BOLT layout exists to relieve, and it consumes budget the §15 roster is fit to explicitly. **Arbitration:** gate 6. Size is a constrained objective in the optimizer, not a free variable, and profile-directed selectivity (inline and unroll on measured hot paths only) is the standing form.
- **Per-edge specialization vs. code size.** Whole-image partial evaluation multiplies trampolines and monomorphized kernel copies. Same arbitration: budgeted, profile-directed, and measured against the §15 capacity arithmetic rather than applied uniformly.

---

## What each lever recovers

Rows are named from [performance-estimates.md](performance-estimates.md) (figures live there, so this stays in sync).
The third column gives the class from **The three classes**, above: **[R]** realizes a booked gain row, **[D]** exploits structure the baseline lacks and so narrows the gap by its higher marginal return, **[U]** is a universal pass whose marginal return is nonetheless higher here.

| Pure-win lever | Rows it attacks | Class and marginal-return note |
|---|---|---|
| Whole-image partial evaluation | In-order issue; static prediction; cross-core coordination; context switch | **[D]** Compose-time-frozen call graph; indirect-branch removal is worth a rounding error against a BTB+RAS and a full pipeline penalty here |
| Static data placement (bank / macro / tier) | **No hardware caches (−10% to −50%)**; SRAM bank/macro partitioning | **[D]** Layout is the *only* placement mechanism in the machine; the lever §15 and the estimates both cite |
| WCET-directed compilation | Non-work-conserving scheduler; §11 population rung | **[D]** Worth *nothing* on a work-conserving baseline; buys schedulable frame capacity |
| Capability-width-aware representation | CHERI purecap 128-bit capabilities (−2% to −12%) | **[D]** Attacks the width tax directly; baseline has no such tax to shed |
| Switch-cost minimization (live V/M state) | `fence.t` + eager V/M zeroize (−2% to −10%) | **[D]** Baseline has no eager-zeroize obligation and no compile-time-known switch points |
| Ring-window / message layout | Cross-core coordination; TDM NoC; no coherence | **[D]** Aligns to a slot cadence and granule write path the baseline does not have |
| Autovectorization / SLP | → RVV vector gain row (+100% to +1500%) | **[R]** Collects a booked gain; claims no loss row |
| Fusion-idiom-aware iselect / scheduling | → macro-op fusion gain row (+3% to +10%) | **[R]** Collects a booked gain; the off-device complement §15 names |
| `Zicond` if-conversion | → `Zicond` gain row (+0% to +4%) | **[R]** *Corrected:* previously double-counted against the static-prediction loss row. Register-arm-only; the CT half is mandatory, not recovery |
| CHERI bounds-check elision | In-order; static prediction; no C/compressed; offsets CHERI purecap (−2% to −12%) | **[D]** Only under a certified exact-bounds precondition (`len` ≠ capacity, compressed-bounds rounding, panic ≠ trap) |
| CHERI temporal-safety elision | *No booked row*: unscored instrumentation + refcount atomic traffic | **[D]** *Corrected:* the −0% to −3% row is missing-CAS, not refcount cost. Structural §13 hygiene; tiny, and smaller still under share-nothing |
| Software pipelining / static load hoisting | In-order issue; no hardware caches | **[U]** *Corrected:* the "no-prefetch −3% to −15%" row does not exist (scored ≈0%; charging it double-counts). Higher margin: no OoO window to hide latency |
| Deterministic PGO + BOLT layout | Static branch prediction; no C/compressed (fetch) | **[U]** Higher margin: the static rule *is* the predictor, so layout is the whole of it |
| LTO / inlining / unrolling | Static prediction + in-order (compounding) | **[U]** Gate-6 constrained; trades against code size (Tensions) |
| Superoptimization / search codegen | In-order scalar; bit/integer paths | **[U]** Speed is universal; the untrusted-search story is a *trust* win. Producer-side TV is required, not optional |
| Static schedule synthesis | Non-work-conserving scheduler; TDM NoC | **[U]** Shrinks a self-imposed idle; never reaches work-conserving. Loops with WCET-directed compilation |
| Micro-architectural DSE | SRAM bank/macro; TDM-NoC schedule; *scalar scratchpad (open)* | **[U]** Baseline is itself a DSE output; the scratchpad dimension is the one aimed at the no-cache row |
| Faster pure-interpreters (JS + Wasm) | No-JIT (browser JS and Wasm) | **[U]** Substitute for the missing JIT; narrows, never closes. Inline caches need the §8 argument stated, not assumed |
| Data-oriented restructuring | General scalar → vector / matrix / crypto | **[U]** Shared source technique; higher margin only because no cache rescues a bad pattern |
| Compartment-granularity budgeting | §17 population wall (unrowed; the largest user-facing cost) | **[D]** A *shape* lever, not a percentage; bounded below by §14's mandatory compartmentalization |

---

## Out of scope: explicitly *not* pure wins

Recorded so they are not re-proposed.
Each recovers performance only by **shedding a property or reopening a channel**, so it belongs in [performance-estimates.md](performance-estimates.md) as an accepted cost, never here.
These accepted costs *are* the irreducible residual, the part that survives after every lever above has been run **and** the equivalent passes have been run on the baseline:

- **Speculation / OoO, dynamic branch prediction, SMT**, hidden shared state that fails admission-test-3 (§15); the very channels the design deletes.
- **JIT / on-device codegen**, violates W^X (§14).
  The pure-win substitute is a faster pure-interpreter (§3); web JS and Wasm are dynamic content, so no AOT shortcut exists *on the web delivery path* (the install path is a different matter, §3).
- **DVFS / turbo, reactive clocking**, a data-dependent frequency channel; power states are static schedule artifacts (§7/§15).
- **Prefetch / non-temporal hints (`Zicbop`/`Zihintntl`), a return-address stack, LR/SC**, reintroduce µarch state that WCET must model and admission-test-3 forbids.
  The pure-win substitute for prefetch is static load hoisting (§1B); note that the estimates score no-prefetch at ≈0%, so the substitute is collecting a cost that was never booked as a loss.
- **Slack donation / work-conserving scheduling / any reclaim of idle discretionary slots**, recorded here because §17 names it as the mechanism that will never be added: reclaiming an idle slot across a confidentiality boundary *is* the timing channel the non-work-conserving frame is buying. The pure-win substitutes are schedule synthesis (§2), WCET-directed compilation (§1A), and compartment-granularity budgeting (§4), none of which reclaim anything.
- **A hardware reference-count or ownership primitive (a capability-copy-intercepting counter, hardware *linear* capabilities)**, recovers refcount traffic only by adding microarchitecture: a new mutable per-object counter or a non-duplication check in the pipeline is exactly the hidden shared state admission-test-3 (§15) forbids, and it breaks the "no new µarch" premise the list rests on.
  The pure-win substitute is eliding *software* temporal-safety instrumentation onto the tag + revocation machinery and the linear/affine capability *types* already present (§8, §5, §13), the compiler-elision item in §1A, not a counter in silicon.
- **Bounds-check elision without the exact-bounds precondition**, recorded here because an earlier revision of this document admitted it as pure and it is not: eliding a check the capability does not actually subsume (a `Vec` bounded to capacity, an object above the compressed-bounds precision threshold) deletes the only spatial check on that access and **sheds a security property**, failing gate 3. The certified-precondition form in §1A is the pure one.
- **Adding memory encryption or a memory integrity tree back**, and any capability-scoped variant of either.
  These are not on this list because they are not levers at all here: the memory path carries no cryptography (§15), so there is nothing to tune, amortize, or partition.
  They are recorded in this section so they are not re-proposed as a *security* addition either: each would add a controller-side latency term to every access, and the tree would additionally require a node cache whose contents are history-dependent, which fails admission-test-3 (§15) exactly as a data cache does.
  The reasoning is in [architectural-alternatives.md](architectural-alternatives.md); the short form is that memory cryptography protects an interface and this machine has none.
