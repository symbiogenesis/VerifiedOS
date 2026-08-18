# Hardware Acceleration Determinations

Status: decision record, 2026-08-18, **wired into the normative corpus** (see the closing section for the requirement IDs created and amended). The project is greenfield: every candidate is determined now, on design-time grounds, from rationale already carried in `spec.md`, `requirements-register.md`, and `isa-profile.md`, with the non-normative analyses in `architectural-alternatives.md`, `performance-estimates.md`, and `critique.md` as evidence. Where the checklist asked for a measured baseline, the determination instead states the structural argument that decides the item without one, and names the residual a later result could overturn.

Five levers decide everything below, and they are the corpus's own:

1. **The five-part admission test** (R-15-010, R-15-011): deterministic Sail-expressible semantics; data-independent timing; no hidden state surviving a partition switch outside the four-class map; no authority path outside capabilities; no autonomous behaviour.
2. **Verify rather than hedge** (R-15-013): hardware that duplicates a verified software guarantee is declined; only a genuinely disjoint failure domain admits a second mechanism.
3. **Bound, not mean** (R-15-069b, R-15-069c): an accelerator is credited only for what it removes from the worst-case bound. A mean-case saving, spent rather than padded, is a cross-domain timing channel.
4. **Deletion preferred** (R-15-105): every removal converts a correctness obligation on the least-built arrow (RTL against Sail) into a structural absence check. Anything added back must delete more proof/WCET surface than it adds.
5. **The Sail-oracle asymmetry.** Instructions inherited from the official `sail-riscv` and `sail-cheri-riscv` models (`cbo.zero`, `cloadtags`, the CHERI core) arrive with upstream semantics and instruction-level oracles. Everything admitted below is **net-new Sail surface with no upstream oracle**, which is why every admission is confined to the one shape this architecture rewards: core-issued, bounded, fixed-latency, destructive or verify-and-correct, with a trivial software oracle for differential testing.

## Summary of determinations

| # | Candidate | Determination |
| --- | --- | --- |
| P0 | All seven existing primitives | **Keep** (confirmed; one open DSE note on `fence.t`) |
| P1-1 | V/M all-state clear | **Admit** (`vmclear`, R-15-069d) |
| P1-2 | Fixed-list stack save/restore | **Reject: struck** (R-15-036n rewritten as the strike) |
| P1-3 | Partition-switch phase overlap | **Reject** (additive three-term bound stays) |
| P1-4 | Wider/revised `cloadtags` | **Reject decoupling** (width stays welded to the CBO block) |
| P1-5 | Core-issued block reclamation | **Admit** (`creclaim`, R-15-007s) |
| P1-6 | Core-issued block scrub | **Admit** (`cbo.scrub`, R-15-177a; specification repair, not acceleration) |
| P1-7 | Static instruction scratchpad | **Reject for slotted cores; DSE parameter for pinned cores** |
| P1-8 | Fixed-function datapath additions | **No blanket admission; existing roster and framework govern** |
| P2-1 | Whole partition-switch engine | **Reject** (confirm default) |
| P2-2 | Hardware endpoint lookup | **Reject** (confirm; already a MUST NOT) |
| P2-3 | Hardware grant-table operation | **Reject** (confirm default) |
| P2-4 | Autonomous scrub/revocation walker | **Reject** (confirm; superseded by P1-5 and P1-6) |
| P2-5 | Executable-overlay loader | **Exclude; deferral trigger unchanged** |
| n/a | All explicit non-candidates | **Confirmed excluded** (each traced to a normative MUST NOT) |

Net effect on the profile: **three instructions in** (all in the destructive or verify-and-correct class), **one candidate retired early** (R-15-036n), everything else confirmed exactly as the corpus already disposes it.

## Priority 0: retain, all seven

These are architectural mechanisms with standing requirement IDs, not optional features, and nothing in this evaluation disturbs any of them. Confirmations, with the one live caveat:

1. **CHERI enforcement and sealed transfer**: keep. The sentry is the whole domain-entry mechanism (R-15-068, R-15-069), target membership deliberately stays in software as the typed callee set (R-15-072), and fixed-latency check semantics are already timing contracts (isa-profile §9). The known residual is single-mechanism concentration (R-17-037), hedged only by CHERI's own verification; that is the design's stated bet, not a defect this checklist can fix.
2. **Revocation load filter**: keep. Bank-side sidecar riding the data/tag access at one fixed latency regardless of bit state (R-08-005, R-08-005a); the deliberate divergence from RVY's optional check is load-bearing (containment latency is a §11 schedule term). In-flight DMA epoch observation is already a booked obligation (R-15-208), not a gap.
3. **`cbo.zero`, `cclear`, domain clear**: keep and extend (see P1-1). Zeroization is the one operation that is unconditional, destructive, and universal, which is what lets it *replace* history-sensitive machinery (the initialization-tag plane, R-15-035) rather than hedge it.
4. **`fence.t`**: keep. The flush set is one structure by construction (R-15-213), the padded constant completes never-early (R-15-218, R-15-219), and device stores stay out of the buffer (R-15-015b). **Standing note:** the one admissible path to retiring `fence.t`'s drain term is the store-buffer-deletion DSE (`architectural-alternatives.md`, "Delete the store buffer"): SC by absence, which would empty the flushed class entirely. That question is gated on a physical quantity no design-time argument can decide; it stays open exactly as logged, and it is the correct attack on the switch's dominant term (see P1-3).
5. **Slot-boundary timer**: keep; the hardware-scheduler rejection is confirmed and rests on a measured impossibility result (Gong and Kiyavash, via R-07-036), not preference. The sole reopening trigger stays: a published work-conserving scheduler with an offline-time leakage proof, which does not exist.
6. **IMSIC pending array**: keep. Interrupt-send as a capability-authorized store (R-15-064), pending-bit-only surface (R-15-065), full-FIFO worst case priced under R-11-010 ring sizing. Nothing to add and nothing left to remove.
7. **Capability-checked DMA and fixed streaming engines**: keep. The two admissible shapes (core-issued mover; delegated bounded-window streamer, R-15-206) and the tag-carrying fabric obligation (R-15-209) stand as specified.

## Priority 1 determinations

### P1-1. V/M all-state clear: ADMIT (`vmclear`)

One core-issued architectural instruction per V/M-bearing class that clears the vector register file, vector CSRs, matrix state, and architecturally defined scratchpad, unconditionally, mask-independently, at one fixed per-class latency.

**Grounds.** The obligation it accelerates is unconditional and normative (R-07-014, R-07-014a: the switch zeroizes and never saves), so the saving is off the *bound*, not the mean, which is precisely the currency `cclear` was admitted on (R-15-069b: "the clear being unconditional"). It passes all five admission tests on the `cclear` template: it can only destroy authority, so monotonicity is trivial rather than argued; it adds no CSR, no flush-set member, no admission-test case. Opcode space is uncontended (R-15-069a: no C extension competing for 32-bit encodings). `architectural-alternatives.md`'s rejection of compiler-liveness minimization already identified "a new hardware contract" as the only remaining route to shrinking this term; this is that contract, taken in the only admissible form.

**On the reset-wire comparison** (the checklist's last box): the architectural instruction is the right *specification*; direct reset wires are the right *implementation*. The zeroize must be visible to the switch proof and the timing-annotated model as a named operation with a padded completion constant; raw reset wires have no architectural completion event for the proof to cite. Specify the instruction; realize it with the wires.

**Conditions carried into the requirement:** unconditional, mask-independent, fixed per-class latency on the R-15-053 constant-time list; no progress CSR, high-water mark, or lazy-state tracking (R-15-069c and R-07-014 both foreclose these independently); V/M and scratchpad state remains class (a) of the four-class map (R-15-217). Software oracle: a loop of `cbo.zero` and `cclear`, trivial.

**Wired as:** R-07-014c (§7 statement), R-15-069d and R-15-069e (§15 instruction and grounds), plus an isa-profile §3 row and §9 timing contract.

### P1-2. Fixed-list stack save/restore: REJECT (R-15-036n struck)

**Grounds.** The corpus already expected this outcome ("the expected outcome is that it is dropped," the prior R-15-036n Accept) and already forbade the only path that could admit it without measurement (an immaterial measured delta drops it rather than carrying it on the argument alone). Since no measurement will be taken, the admission condition is unreachable by decision, and the default disposition executes. The structural facts stand regardless: the win is halved before it starts (dictionary encoding already makes each stereotyped save one 32-bit slot, so a *k*-register save is worth *k* − 1 slots, not *k* − 1 instructions); the software residual is normative and substitutive (outlining plus tail merging, R-15-036o); and the candidate contended for the same custom opcode space and the same freeze measurement as three other forms.

**What survives:** R-15-036m (the `Zcmp` exclusion, on the restartable-sequencer form) is untouched and remains the stronger, structural rejection. R-15-036o and R-15-036p (outlining, measurement ordering) remain, since the freeze's dictionary-selection corpus statistics are gathered anyway. R-15-036n itself now records the strike and preserves the all-or-nothing single-check shape as the only form a future amendment (R-18-034) may propose.

**Wired as:** R-15-036n rewritten from candidate to strike; the R-15-014a final-freeze delta list, R-15-036o, R-15-036p, R-15-067e, the isa-profile freeze table, and the performance-estimates dictionary row all updated to match.

### P1-3. Partition-switch phase overlap: REJECT (as a base-spec mechanism)

**Grounds.** The additive three-term switch bound (R-15-220) stays. Three reasons, in descending weight:

1. **The benefit is capped and the cap is small.** The whole switch row is scored at a few percent on switch-heavy work; OPP relock applies only where operating points differ (a handful of coarse OPPs per class, R-15-188), so overlap's win is a fraction of a fraction. The design already carries two stronger moves against the same term: pinning *deletes* all three constants for exactly the tenants whose switch rate matters (R-11-011, R-15-114), and frame amortization makes the constant negligible for everyone else (R-11-013).
2. **The correct attack on the dominant term is deletion, not overlap.** The store-buffer DSE (see P0 item 4) would remove the `fence.t` drain term outright, which is the design's revealed preference ("delete rather than defend") applied to the same constant.
3. **The proof it demands is not free.** Independence under every fault and power state, plus a no-exposure-before-zeroize ordering argument against R-15-215's "before the successor's first instruction" clause: new obligations bought for a bound-tightening the schedule arithmetic barely sees.

**Residual honestly stated:** overlap is semantics-free; it only ever tightens a constant. If a composed schedule someday turns out switch-bound after pinning and amortization, this is re-proposable as a pure amendment with the independence proof in hand, with no architectural rework. It is *not* carried as an open question; the two R-18-009 open questions stay the only two.

### P1-4. Wider or revised `cloadtags`: REJECT the decoupling; keep the weld

**Grounds.** There is no independent `cloadtags` width to tune. R-15-007q fixes the group to the CBO block `cbo.zero` allocates, "which makes the sweep's inspect unit and its reclaim unit one unit," precisely so the sweep's inner loop is one timing-model entry instead of a variable loop bound (R-15-014). Any width change is therefore a change to the **CBO block size**, which is a physical macro-geometry parameter already on the frozen-parameter DSE list; it gets chosen there, once, for `cbo.zero`, `cloadtags`, and the P1-5 `creclaim` simultaneously. Decoupling the widths would also drag `cloadtags` back into the measured-freeze pool it was deliberately decided outside of (R-15-014a).

Reported tags stay *stored*, never filtered (already normative: the instruction reads no capability to take a base from); all-clear and all-tagged latency identity stays a §9 timing contract. No spec action beyond the weld's reaffirmation.

### P1-5. Core-issued block reclamation: ADMIT (`creclaim`)

One instruction over one named, capability-authorized CBO block: for every granule, apply the per-granule conditional clear the load filter already defines (R-08-005b's revoked case, in place, without materializing the value in a register), and return the group's tags as they stand after the pass. It writes no data, moves no granule, touches no granule whose revocation bit is clear, and stops at its group boundary.

**Grounds.** This is net-new, not something previously deleted, and the corpus's own relief ladder points at it. R-15-007r rejected the *group-wide unconditional* tag clear because the sweep needs "a per-granule conditional clear that a group-wide unconditional one cannot express at all"; this is that conditional form. R-08-009 rejected the *autonomous* form (TBRE); this is the core-issued form that rejection explicitly preserved ("it touches memory only where an instruction says so, which is the property test 5 protects"). The checklist's own Priority-2 guidance names "increase block-operation width" as the sanctioned first relief. And the semantics are the composition of two clauses the Sail model already carries, the load's defined revoked case and `cloadtags`' group read, which is what keeps the clause small enough to review directly.

The benefit is a *derived constant with a permanent capacity price*, not a mean-case speedup: the sweep is the machine's only reclamation mechanism (revocation colour declined, TBRE declined), its pass time **is** the quarantine interval (R-08-007a), and the quarantine pool plus the per-core background sweep slots are composition-sized SRAM and core capacity paid forever. The software inner loop is issue-bound, not bandwidth-bound (native tags share the array row; the corpus states `cloadtags`' yield is an issue saving), so fusing the whole block's conditional clears into one instruction cuts the pass time by roughly the group width, and the quarantine constant and pool shrink with it. On a machine that admits capacity at composition time, that is admission headroom bought once, at design time.

**Conditions carried into the requirement:** fixed latency independent of tag and revocation density (every granule takes its cycle whether touched or not, on the R-15-053 list); explicit result (the surviving tags); **no autonomous continuation to the next block**, address progression staying in the admitted sweep task (R-08-007); authorization is the lattice element a tag-preserving capability load requires. Software oracle: `cloadtags` plus a capability load per tagged granule (the load's own semantics clear the revoked tag), which exists today.

**Wired as:** R-15-007s (§15 dialect instruction) and R-08-007b (§8 consumer), plus an isa-profile §3 row and §9 timing contract.

### P1-6. Core-issued block scrub: ADMIT (`cbo.scrub`, specification repair)

One synchronous fixed-block verify-and-correct instruction: read one named block through the existing ECC check, rewrite correctably erroneous codewords corrected via the memory controller's existing RMW stage (the merge-less case of R-15-181), fail-stop on uncorrectable data-plane or tag-plane errors, report correction telemetry, same latency corrected or clean.

**Grounds.** This admission closes a genuine inconsistency the evaluation surfaced: R-15-177 *mandates* background scrubbing and the power architecture names "the background scrubber," yet no scrub engine appeared in the memory-controller inventory (R-15-202), the four-class state map, or the absence contract, while an autonomous scrub walker is default-rejected (admission test 5). As previously specified, the mandated scrubber was either an unadmitted autonomous walker or a software task with no defined primitive. The core-issued block scrub is the resolution: address progression moves into an admitted software schedule (mirroring the revocation sweep's shape, R-08-007: incremental, preemptible, own background slot class, kernel-held scrub capability), and the datapath is a strict reuse of the verified RMW/ECC stage rather than new semantics. Under the checklist's own net test this *deletes* proof surface: an unspecified autonomous engine leaves the design; one small instruction enters.

It also gives the already-normative power-mode-exit sweep (R-15-189k: full verify-and-correct on the exit path of an over-held RETAINED domain) its primitive, priced like the OFF-to-ON clear.

**Conditions carried into the requirement:** cadence a composition-time constant, never error-rate-triggered (R-15-189k Accept); corrected and uncorrected same-cycle (already normative, R-15-179); fail-stop on uncorrectable (already normative); telemetry with no data-dependent timing; whole-granule writes only (R-15-181). Software oracle: ordinary loads through the ECC check.

**Wired as:** R-15-177a (§15 memory subsystem), with R-15-177's Accept and the power-architecture ON-state prose amended to name the scheduled task as the scrubber, plus an isa-profile §3 row and §9 timing contract.

### P1-7. Static instruction scratchpad: REJECT for slotted cores; DSE parameter for pinned cores

**Grounds for the slotted-core rejection (design-time, no measurement needed).** On a slotted C-class core the scratchpad must either be statically partitioned among the rung's tenants, dividing its capacity by up to 32 (R-11-019 rungs) until each share is too small to hold a working set, or be refilled at the partition switch, adding a code-fill term of hundreds of kilobytes at memory bandwidth to a switch whose entire budget is a few microseconds (spec §11). Either horn contradicts the switch model the rest of the design is built on; this is the same residency-and-fill problem that got the overlay loader deferred (`architectural-alternatives.md`, static code overlays), arriving through the front door. The standing scalar-scratchpad argument (R-15-173-2: a purely-performance structure that adds a modeled region, switch zeroize state, and RTL surface) seals it.

**Grounds for keeping the pinned-core option.** For a pinned, single-tenant core the structure is clean: filled once at composition, class (b) partition-owned state, no switch interaction, contents a function of explicit placement (passes R-15-165 and R-15-166 by construction; R-18-009 already said it "passes the admission test"). Whether it *pays* is a function of macro port counts and bank arbitration, a physical parameter the pre-silicon DSE (R-15-108) resolves anyway, with scratchpad sizes already on its frozen-parameter list. That is not a deferred measurement; it is where the decision natively lives.

**Wired as:** R-18-009 narrowed to the pinned single-tenant form, with the slotted-core rejection and its fill-or-partition argument recorded in the requirement so it is not re-opened as a routine optimization. The V/M-class data scratchpads (R-15-167) are untouched; they are architecturally intrinsic, not this candidate.

### P1-8. Fixed-function datapath additions: no blanket determination; the existing framework governs

The corpus already contains both the complete admission framework and a settled roster, and this evaluation confirms both without addition. Admitted and retained: vector crypto suites plus the frozen Keccak permutation (R-15-055 through R-15-059a), LDPC/polar FEC (R-15-119), the matrix unit at its order-of-magnitude sustained-GEMM bar (R-15-116), the PHY sub-slot turnaround sequencer (R-15-122, R-15-123), the 1000BASE-T PCS with per-link-epoch frozen coefficients (R-15-137, R-15-138), fixed sensor AFE and conditioning (R-15-140 through R-15-142), the IEEE-1588 NIC timestamp unit (R-12-036), and the RoT/fixed-sequencer split of power sequencing (R-15-194, R-12-066). Confirmed declines stand: scalar crypto rounds, turbo and convolutional decoders, 10GBASE-T, adaptive LMS, OLED aging loops, codec blocks, GPU command processors.

Any *future* unit is evaluated individually against the existing gauntlet: the five tests, geometry-not-grammar (R-15-238 against R-15-119), the coprocessor line (R-15-118: core-issued capability operands, no DMA mastership, no translation context, no firmware; "an accelerator that needs any of those is a device"), the seam-register walk (R-17-018), the R-15-116-style order-of-magnitude margin over the general-purpose datapath, and verify-rather-than-hedge. The checklist's generic entry adds nothing to that and is closed.

## Priority 2: defaults confirmed, all five

1. **Whole partition-switch engine: reject.** The isolation content of the switch is discharged by the kernel's total restore (R-07-015, R-07-016), which hardware cannot improve, only duplicate, the exact shape verify-rather-than-hedge declines. Partial fusion adds a verified hardware/software seam with "no presumed TCB reduction" (`architectural-alternatives.md`, kernel-in-gateware, objection 5). Where switch cadence binds, the design's answer is pinning, already normative.
2. **Hardware endpoint lookup: reject.** Stronger than a default: R-07-002b is a MUST NOT with an auditable acceptance criterion ("no index-to-capability lookup appears in the ABI or the proof"). There is no name to translate; a lookup engine would have to manufacture the namespace the kernel deleted. Singleton-call collapse (R-05-114a) and composition-assigned ring indexing (R-12-006) already close the dynamic cases in software.
3. **Hardware grant-table operation: reject.** The hot path is *already hardware*: the bank-side load filter kills every stored copy of a retired slot's capability at fixed latency. What remains in software is mint, unseal, and yield, which R-08-004d makes a capability dereference, not a name resolution; there is no walk to accelerate. An engine that allocated or selected slots would collide with R-08-045 through R-08-047. The narrow bounded-operation door the checklist leaves open stays theoretically open (the R-15-069b template), but nothing on the machine needs it, and no such operation is admitted.
4. **Autonomous memory scrub or revocation walker: reject.** R-08-009 (TBRE and STKZ declined) and admission test 5 stand, and the pressure this item existed to relieve is now absorbed by the admitted core-issued block operations (P1-5, P1-6) plus, at the composition's discretion, a dedicated low-end core or transition-time sweeps (R-15-189k). The single narrow carve-out stays exactly where the corpus put it: a fixed, composition-sized, data-independent refresh-plus-scrub sweep engine only if gen-2 gain-cell memory is ever adopted (`architectural-alternatives.md`, the 2T0C entry), with two separately proved postconditions; conditioned on the memory-technology decision, not open now.
5. **Executable-overlay loader: exclude; trigger unchanged.** The deferral is epistemic and its trigger is a *build-time* fact, not a lab measurement: re-open only when an otherwise admitted, representative composed roster exceeds its executable SRAM budget after R-13-010a/b/c dead-code and duplication elimination and R-15-036a dictionary encoding, facts the composition pipeline produces as a matter of course. Until that event the loader's residency, canonical-image, control-transfer, and invalidation proofs are not bought. For the initial architecture: excluded.

## Explicit non-candidates: all confirmed

Every line item traces to a normative prohibition, and nothing in this evaluation weakens any of them: hardware scheduler and donation (R-07-032 through R-07-037, Gong and Kiyavash), endpoint/object TLB and CSpace walkers (R-07-002b, A-14), autonomous walkers of every species (R-15-010 test 5, R-08-009), descriptor-following ring engines (R-04-010, R-12-006), runtime allocators and placement engines (R-08-045 through R-08-047, R-07-002a), programmable parsers and firmware cores (R-04-010, the §12 exclusion table; the eUICC containment shape is the sole tolerated exception and the template for any future one), interrupt delivery logic beyond the pending array (R-15-065, R-07-038 through R-07-041), high-water and lazy-clearing state (R-15-069c, R-07-014), caches, victim buffers, RAS, predictors, and prefetchers (R-15-100 through R-15-105, A-01 through A-16, the table-freeness rule R-15-104), and generic checkpoint, hibernation, and overlay engines (R-10-035 through R-10-037, A-01).

The one internal tension found among these lines, "no autonomous scrub walker" against the mandated-but-unowned "background scrubber," is resolved by the P1-6 admission, in the prohibition's favor.

## How this record was wired into the corpus

All actions below are landed; this section is the map from determination to requirement.

1. **`vmclear`**: new R-07-014c (spec §7), R-15-069d and R-15-069e (spec §15, register §15.9); R-07-014's Accept and R-15-220's zeroize term now name the instruction; isa-profile carries the §3 bespoke row and the §9 timing contract.
2. **`creclaim`**: new R-15-007s (spec §15 CHERI dialect, register §15.1) and R-08-007b (spec and register §8); isa-profile carries the §3 row and §9 contract.
3. **`cbo.scrub`**: new R-15-177a (spec §15 memory subsystem, register §15.22); R-15-177's Accept and the power architecture's ON-state line now name the scheduled scrub task; isa-profile carries the §3 row and §9 contract.
4. **R-15-036n struck**: rewritten from freeze candidate to recorded strike preserving the admissible shape; R-15-014a's delta list, R-15-036o, R-15-036p, R-15-067e, the isa-profile freeze table and prose, and the performance-estimates dictionary row updated to match.
5. **R-18-009 narrowed** to the pinned single-tenant scratchpad form, with the slotted-core rejection recorded.
6. **Implementation checklist**: new item M0.6h adds the three instructions to the curated Sail model; M0.6g notes the multi-save strike.
7. No change to any Priority-0 primitive, any Priority-2 default, or any non-candidate line. The store-buffer-deletion DSE remains the one open question touching a Priority-0 item, exactly as already logged.
