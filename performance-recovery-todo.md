# Performance Recovery: Pure-Win TODO (non-normative)

> Companion to [performance-estimates.md](performance-estimates.md) and [verification-maximal-os.md](verification-maximal-os.md).
> Where the estimates doc *accounts for* the accepted price of the security choices, this doc enumerates only the **pure wins**, recovery levers that cost nothing on the scarce axis.
> A **pure win** here recovers performance while **shedding no security property, reviving no deleted mechanism, opening no channel, and adding no axiom or TCB surface**, admissible precisely because it is *static, ahead-of-time, off-device*, and its output is **re-checked at admission** (§6).
> "Engineering is free; trust is the scarce resource," so every item below may be pursued to arbitrary aggressiveness without touching the trust base.
> Checkboxes track workstream progress; nothing here is normative, and no item may relax the §15 admission test.
> **This list is deliberately confined to off-device software levers**, the untrusted-producer, re-checked-artifact architecture is what keeps them free of trust cost, so the one *in-model* (hardware) pure win, **decoder-stage macro-op fusion**, is booked in the specification itself (§2, §15) rather than here: fused and unfused executions reach identical architectural state, so it is carried by the existing RTL-against-Sail *functional* refinement at no proof cost, recovering scalar issue efficiency without any off-device artifact to re-check.
> **Baseline, and what "recovery" here does and does not mean.**
> Every figure below is measured **intra-design**, the same frozen instantiation *un-optimized vs. optimized*, and **not** as a narrowing of the gap to the conventional (speculative, OoO, JIT- and DVFS-capable) baseline of [performance-estimates.md](performance-estimates.md).
> The distinction is load-bearing because almost every lever here, autovectorization, software pipelining, PGO/BOLT, LTO, superoptimization, micro-architectural DSE, static schedule synthesis, is **universal engineering that a conventional toolchain and design flow run too**: hold the compiler and the design flow constant across both machines (*ceteris paribus*) and those levers appear on **both** sides and cancel, leaving the structural hardware/ISA taxes, in-order issue, static-only prediction, CHERI pointer width, the integrity tree, the non-work-conserving frame, **still fully paid**.
> So these items do **not** catch up to a chip that keeps the dangerous mechanisms, they only stop the secure design from running slower than it provably has to.
> The few genuinely *differential* levers, **CHERI bounds-check** and **temporal-safety elision** (they spend on-die hardware, capability bounds and tags + revocation, that the baseline lacks) and, weakly, **`Zicond` if-conversion** (worth more under static-only prediction), still merely **offset a self-imposed tax**, never overtaking the baseline.
> The irreducible inter-design gap is exactly the deleted dynamic mechanisms, booked as accepted costs in the estimates (§ *Out of scope*, below) and recovered nowhere here.

## The pure-win gate

An item earns a place on this list iff it clears all five:

1. **Recovers performance** on at least one row of [performance-estimates.md](performance-estimates.md), *intra-design* (the same instantiation, un-optimized vs. optimized), **not** by narrowing the inter-design gap to the conventional baseline (see **Baseline** above).
2. **No trust widening**, no new axiom, no TCB growth; the produced artifact is re-checked, so its *producer* stays untrusted.
3. **Sheds no security property**, every theorem the spec claims still holds, unchanged.
4. **Revives no deleted dynamic mechanism and opens no channel**, no speculation, OoO, dynamic prediction, SMT, JIT, DVFS/turbo, prefetch state, or reservation state sneaks back.
5. **Stays inside the proven-safe envelope**, passes the five-part §15 admission test and the §8 non-interference / §11 WCET obligations.

**The enabling theorem (§6).**
*"A compromised compiler or analyzer cannot mint a valid certificate for a property its output lacks"*, so the optimizer is untrusted evidence-producing machinery.
Aggressiveness is therefore **unbounded by trust**: any transformation whose result still type-checks (CHERI-TAL, §5) or proof-checks (CIC kernel, §6) is admissible however it was produced.
This single fact is what makes the whole list pure.

---

## 1. Off-device compiler optimization: untrusted optimizer, re-checked output

*All items extend the in-scope §18 certifying-compiler workstream; none add a workstream to the TCB.
The output carries the same memory-safety / constant-time / WCET certificates (§5, §13) it always did, the optimizer only makes the same-certified binary faster.
Ceteris paribus these are the passes **any** optimizing compiler runs, so a conventional toolchain banks them too: on this design they realize the secure binary's **own** achievable speed, they do not close the gap to a conventional chip.
The two CHERI-elision items are the exceptions, they lean on on-die hardware (capability bounds, tags + revocation) the baseline lacks, yet even they only offset the self-imposed CHERI taxes.*

- [ ] **Autovectorization / SLP onto RVV, the dominant lever.**
  Lift scalar inner loops onto the already-in-profile vector unit (VLEN 256 C-class / 4096 V-class, §15).
  Moving a loop onto RVV turns an in-order-scalar row into a vector-gain row, so *intra-design* it does not merely shave the general-scalar deficit, it converts it.
  Ceteris paribus, though, this is **not** a closing of the inter-design gap but the *key that realizes an already-booked hardware gain* (the RVV row of the estimates): a conventional autovectorizer targets *its* vector unit too, so only the wider VLEN, itself already counted, differs.
  *Keeps it pure:* secret-touching output still carries the binary-level constant-time certificate (§5/§13), which rejects any secret-dependent vectorization.
- [ ] **Software pipelining / modulo scheduling / static load hoisting.**
  The in-order core has no out-of-order window to hide load/FP latency behind, so the scheduler must do it offline, overlap iterations, hoist loads ahead of use.
  Recovers part of the in-order (−35% to −60%) and no-prefetch (−3% to −15%) rows.
  Ceteris paribus this only *narrows* the in-order tax and never closes it: the OoO baseline hides the same latency dynamically in hardware, and static scheduling wins mainly on regular loops, not the branchy code that dominates that row.
  *Keeps it pure:* static hoisting, **not** the excluded `Zicbop` prefetch hint, no new µarch state, no channel.
- [ ] **Aggressive if-conversion onto `Zicond`.**
  Convert unpredictable forward branches into branchless `czero.eqz/nez` selects.
  Already "doubly load-bearing" (§15), it dodges the static-predictor mispredict *and* closes the data-dependent-branch leak.
  Recovers part of the static-prediction (−10% to −30%) row.
  One of the few genuinely *differential* levers: it is worth more here than on the baseline (whose dynamic predictor would often have nailed the branch, and which can even be *hurt* by if-converting a well-predicted one), yet it still only narrows the static-prediction tax, never beating that predictor on the branches left un-converted.
- [ ] **Elide redundant software bounds checks onto CHERI's hardware bounds, the die already checks every access.**
  Teach the certifying Rust→RV64+CHERI toolchain (§18) to recognize that a panicking language-level bounds check (safe Rust's `a[i]`, a hardened-C length test) is *redundant against the capability that already bounds the object*, §5's "CHERI discharges spatial safety in hardware," §7's "CHERI bounds are the sole in-core spatial isolation", and drop the compare-and-forward-branch, letting the hardware bound fault instead.
  Under the platform's fail-stop posture the two outcomes coincide (an out-of-bounds access is a fault-stop either way), so for the panicking index/slice checks the elision is semantically transparent.
  Each check removed is one fewer instruction (in-order row), one fewer forward branch (static-prediction −10% to −30% row), and less code (no-C −2% to −12% row); together they partially *offset* the CHERI purecap pointer-width tax (−3% to −15% row), you pay the wide pointer but claw back the software-check.
  This is one of the few genuinely *differential* levers, it spends on-die capability bounds a conventional chip lacks, so that chip's compiler cannot copy the trick, yet even so it only *offsets a self-imposed tax*, never overtaking a baseline that never paid the CHERI width.
  Unclaimed today: current purecap Rust (Morello / CHERI-RISC-V) makes raw-pointer and `unsafe` code spatially safe yet still emits the safe-Rust check *on top of* the hardware bound.
  *Keeps it pure:* the bound is still enforced, by hardware already on the die, adding no µarch, so the output still type-checks memory-safe in the CHERI-TAL (§5/§6), the §13 certificate is undisturbed, the check is address- not secret-dependent (constant-time untouched), and fewer instructions only tighten WCET (§11).
- [ ] **Lower temporal-safety instrumentation onto the revocation and tags already on the die, not a software refcount, and *not* a hardware one.**
  The spatial elision has a temporal mirror, but the mechanism is *not* a counter: CHERI carries **no hardware reference-count primitive**, copying a capability is an un-intercepted move, so a hardware counter would be new microarchitecture (fails admission-test-3, §15, and the "no new µarch" premise this whole list rests on).
  What the die *does* run is the **tag + budgeted revocation sweep** (§8, "derivation-tree revoke + CHERI sweep," CHERIoT/Cornucopia lineage) and the **linear/affine capability types** the CHERI-TAL already carries as the temporal residual (§5, §13).
  So the lever is a compiler that discharges use-after-free with *those*, eliding software shadow-memory / heavy-atomic UAF guards, and, where a genuine count survives (CoW-extent refcounts §10, `Rc`/`Arc` sharing), uses CHERI's *precise* tags to license non-conservative or non-atomic counting rather than a `Zaamo` atomic on every clone-and-drop.
  That is CheriOS's "claim" (an object-granular refcount made sound by revocation) produced by an untrusted, re-checked compiler.
  Recovers the small atomic-RMW refcount traffic (the `Zaamo` / atomics −0% to −3% rows) and keeps the §13 temporal obligation structural rather than instrumented.
  Differential like the spatial elision (it spends on-die tags + revocation the baseline lacks), but tiny, and again only offsetting a self-imposed cost.
  *Keeps it pure:* leans only on mechanisms already in the design, adds no µarch and no channel, and is sound precisely because the §6 checker still re-checks the temporal-safety certificate on the output.
- [ ] **Deterministic PGO fall-through + BOLT-style post-link layout.**
  Lay hot paths out as fall-through to hit the backward-taken / forward-not-taken static rule, and pack hot code to fight the +25–30% code-size and fetch-bandwidth pressure from the deleted C extension.
  §10 and §15 already book this as "partial recovery"; make it a first-class, maximized pass.
  *Keeps it pure:* the profile is a **signed, reproducible build input** (§10), never runtime-learned predictor state.
- [ ] **LTO, aggressive inlining, loop unrolling, superblock formation.**
  Cut branch density (fewer static mispredicts), widen the scheduler's window for pipelining, and expose more loops to the vectorizer.
  Recovers part of the static-prediction and in-order rows; compounds the items above.
- [ ] **Superoptimization / equality-saturation / search-based (incl. ML and evolutionary) codegen for hot kernels.**
  Because the artifact is re-checked (§6), point unbounded offline search at the hottest routines: the whole modern SMT-backed stack enters *as untrusted, re-checked oracles*, **Souper**-class SMT superoptimization, **egg** / equality-saturation rewrite search, and **Alive2**-style translation validation gating each peephole, none touching the trust base, because the emitted binary still carries the CHERI-TAL and constant-time certificates the §6 checker re-validates.
  Ceteris paribus the *speed* here is universal (a conventional toolchain runs Souper / egg / Alive2 too); the design's distinctive claim is only that it can point **unbounded, untrusted** search at the problem without TCB growth, a *trust* win, not an inter-design speed differential.
  *This is the only admissible home for "evolutionary algorithms", on codegen, where a wrong answer simply fails the checker, never on the spec or the proofs.*

---

## 2. Off-device design-space search: admission tests as hard constraints

*Optimize the **instantiation**, never the specification.
Every candidate is frozen at composition time, Sail-modeled, and must clear the five-part §15 admission test plus §8 NI / §11 schedulability before it is admissible, the proof obligations are the feasibility oracle.
The spec stays invariant, so this widens no trust base.
This, not mutating the spec, is the correct reading of "run a search over the design."
Ceteris paribus this too is universal: DSE is ordinary chip-design practice (the conventional baseline is itself a DSE output) and static schedule synthesis only shrinks the design's **own** non-work-conserving idle, so neither narrows the inter-design gap, they merely keep the secure instantiation from being needlessly detuned.*

- [ ] **Static schedule synthesis.**
  Pack the cyclic-executive slots (§7) and the TDM-NoC arbitration schedule (§15) with an ILP / SMT / evolutionary optimizer, subject to the §11 interval-arithmetic schedulability check.
  Tighter packing recovers the non-work-conserving-scheduler idle (−10% to −35%) and TDM-NoC (−5% to −15%) rows.
  This shrinks the design's **self-imposed** idle only; it can never reach the baseline's work-conserving efficiency (that would need slack donation = a timing channel), so the row is narrowed, not closed.
  *Keeps it pure:* the frame stays **non-work-conserving**, no slack donation, no runtime scheduling decision, it is merely a better-packed static frame.
- [x] **Micro-architectural DSE over the frozen parameters.**
  Multi-objective (perf / area / power / WCET / proof simplicity) Pareto search over: VLEN per class, issue width and pipeline depth, scratchpad sizes, SRAM bank/macro/tier assignment, and on-die integrity-tree-node cache size (there are no hardware caches to size, main-spec §15).
  Partially recovers the memory-partition (−5% to −20%) and memory-integrity-tree (−5% to −30%) rows.
  Universal ceteris paribus: the conventional baseline is itself a DSE output, so this closes no inter-design gap, it only selects the best *admissible* secure configuration.
  *Keeps it pure:* each candidate is a static, Sail-modeled, admission-checked config; the one address-indexed structure that remains (the integrity-tree-node cache) is **partition-scoped and fence.t-flushed**, so admission-test-3 still holds (there is no data cache, main-spec §15).
  *Done, wired into [verification-maximal-os.md](verification-maximal-os.md) §15 (normative) and [implementation-plan.md](implementation-plan.md) §1; the §17 Sail ⋈ RTL residual names it the standing mitigation.*

---

## 3. Faster pure-interpreters: recover the JIT loss without runtime codegen

- [ ] **Faster pure-interpreters for the browser's JS and Wasm.**
  Under no-JIT (§14) the browser runs downloaded JS and Wasm *interpreted*, Boa/Nova for JS, wasmi for Wasm (both pure-Rust), because web content is dynamic and W^X (§14) forbids on-device codegen.
  Claw the overhead back with threaded / computed-goto dispatch, superinstructions, and **data-plane inline caches** (caches as *data*, never generated code).
  *Keeps it pure:* no runtime codegen, the W^X invariant (§14) holds by construction.
  This *narrows* the no-JIT gap but cannot close it, an interpreter, however tuned, does not match a JIT, so the −60% to −90% row is mitigated, not erased.
  *No off-device AOT shortcut exists:* web-delivered Wasm is dynamic content and installed apps compile straight to native RV64+CHERI, so Wasm is never an execution target (§14), a "Wasm AOT" lever would be a category error, so none is listed.

---

## 4. Application-level restructuring: software-only, no trust cost

- [ ] **Data-oriented restructuring onto the fast paths.**
  SoA layouts, batching, and replacing pointer-chasing with vectorizable / matrix-shaped structure move general-purpose work onto the RVV, systolic-GEMM, and table-free-crypto paths (§15) that already run at parity-to-many-×.
  The single-address-space (no MMU, §7) already helps pointer-chasing (+5% to +25%).
  Pure by construction, ordinary source-level engineering that changes no mechanism, and universal: a conventional chip benefits identically, so ceteris paribus it closes no inter-design gap, it only moves work onto the fast paths both machines share.

---

## What each lever recovers

Rows are named from [performance-estimates.md](performance-estimates.md) (figures live there, so this stays in sync).
The third column marks whether the lever is *universal* (a conventional toolchain or design flow runs it too, so it cancels *ceteris paribus* and its "recovery" is intra-design only) or genuinely *differential* (it spends on-die hardware the baseline lacks, though still only to offset a self-imposed tax).

| Pure-win lever | Rows it attacks | Ceteris-paribus status |
|---|---|---|
| Autovectorization / SLP | In-order issue; static prediction → converted to RVV vector gain | Universal pass; *realizes* the already-booked wide-VLEN gain (cancels vs. a vector-equipped baseline) |
| Software pipelining / static load hoisting | In-order issue; no prefetch / NT hints | Universal; narrows the in-order tax only (OoO baseline hides the same latency in hardware) |
| `Zicond` if-conversion | Static-only branch prediction | **Differential** (worth more under static-only prediction); narrows, never closes |
| CHERI bounds-check elision | In-order issue; static prediction; no C/compressed (fetch); offsets CHERI purecap width | **Differential** (on-die bounds the baseline lacks); offsets a self-imposed tax |
| CHERI temporal-safety elision | Atomic-RMW / `Zaamo` refcount traffic | **Differential** (on-die tags + revocation); offsets a self-imposed tax, tiny |
| Deterministic PGO + BOLT layout | Static branch prediction; no C/compressed (fetch) | Universal; the baseline runs BOLT too |
| LTO / inlining / unrolling | Static prediction + in-order (compounding) | Universal; cancels |
| Superoptimization / search codegen | In-order scalar; bit/integer paths | Universal on speed; the re-check story is a *trust* win, not a perf differential |
| Static schedule synthesis | Non-work-conserving scheduler; TDM NoC | Shrinks a self-imposed idle; never reaches work-conserving |
| Micro-architectural DSE | SRAM bank/macro; main-memory integrity tree | Universal; the baseline is itself a DSE output |
| Faster pure-interpreters (JS + Wasm) | No-JIT (browser JS and Wasm) | Substitute for the missing JIT; narrows, never closes |
| Data-oriented restructuring | General scalar → vector / matrix / crypto | Universal source technique; shared by both machines |

---

## Out of scope: explicitly *not* pure wins

Recorded so they are not re-proposed.
Each recovers performance only by **shedding a property or reopening a channel**, so it belongs in [performance-estimates.md](performance-estimates.md) as an accepted cost, never here.
These accepted costs *are* the irreducible inter-design gap, the residual no §1–§4 lever narrows, which is why "recovery" in this doc is always intra-design (see **Baseline**, top):

- **Speculation / OoO, dynamic branch prediction, SMT**, hidden shared state that fails admission-test-3 (§15); the very channels the design deletes.
- **JIT / on-device codegen**, violates W^X (§14).
  The pure-win substitute is a faster pure-interpreter (§3); web JS and Wasm are dynamic content, so no AOT shortcut exists.
- **DVFS / turbo, reactive clocking**, a data-dependent frequency channel; power states are static schedule artifacts (§7/§15).
- **Prefetch / non-temporal hints (`Zicbop`/`Zihintntl`), a return-address stack, LR/SC**, reintroduce µarch state that WCET must model and admission-test-3 forbids.
  The pure-win substitute for prefetch is static load hoisting (item 1).
- **A hardware reference-count or ownership primitive (a capability-copy-intercepting counter, hardware *linear* capabilities)**, recovers refcount traffic only by adding microarchitecture: a new mutable per-object counter or a non-duplication check in the pipeline is exactly the hidden shared state admission-test-3 (§15) forbids, and it breaks the "no new µarch" premise the list rests on.
  The pure-win substitute is eliding *software* temporal-safety instrumentation onto the tag + revocation machinery and the linear/affine capability *types* already present (§8, §5, §13), the compiler-elision item in §1, not a counter in silicon.
- **Dropping the main-memory integrity / anti-replay tree**, sheds the evil-maid / rollback defense (§3/§15).
  Its tax is only *mitigable* (on-die node caching, item 2), never removable.
