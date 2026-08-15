# Bespoke ISA Deviation: Amendment TODO (non-normative)

> Companion to [isa-profile.md](isa-profile.md) and [performance-recovery-todo.md](performance-recovery-todo.md), and the **mirror image** of the latter.
> The recovery TODO is confined by construction to levers that touch no theorem, spend no trust, and require no amendment: "engineering is free; trust is the scarce resource." This list records the opposite class, the levers that are worth having **only** by amending the frozen profile, and it exists because that class was being reasoned about informally and priced wrong in both directions.
> An amendment to the profile reruns the review gate (R-18-034) and moves the schedule root (R-18-003a). Nothing here is normative, nothing here relaxes the five-part §15 admission test, and an item that lands in the register leaves this list.
> **The premise of the list is that RISC-V conformance is already spent, not that it is cheap.** [isa-profile.md](isa-profile.md) forks standard RVV twice (scalar-FP-free at R-15-040, `vstart`-free at R-15-040a), deletes the C extension, mandates Ztso in place of RVWMO, freezes a bespoke matrix extension, a bespoke Keccak instruction, a bespoke capability indexed load/store (R-15-007e), and a bespoke bitfield extract/insert (R-15-067a), runs a re-parameterized 64+1-bit capability format whose RVY re-pin is retired (R-15-007, R-17-048a), and runs M-mode-only purecap with CHERI as the sole protection mechanism. No profile-conforming binary runs here and nothing built here runs elsewhere. What conformance still buys is enumerated in §4 below, and it is not zero; it is just much smaller than the word suggests.

## 1. The amendment window, and why it is the forcing function

Row 4 of [crown-jewels.md](crown-jewels.md) is **the only authored crown jewel**. Row 6 (the profile's Sail semantics) is partial. `CJ-COMPCERT`, `CJ-CERISE`, and `CJ-TAL-SOUND` are each premised on row 4 and **none has started**.

R-18-003a makes the profile freeze the **root of the schedule**: the toolchain, the Sail model, and the CHERI-CompCert backend all target it, so it precedes all three. R-18-003b(i) makes the freeze and its Sail curation the first day-one deliverable.

The consequence is that the cost of amending the profile is at its **permanent minimum right now**, and rises monotonically and steeply from here:

| When | What an amendment costs |
| --- | --- |
| Today | one derived view, one register edit, one review-gate rerun (R-18-034) |
| After the Sail curation | the above, plus re-curation of row 6 |
| After the CompCert backend | the above, plus an Asm-semantics and instruction-selection change on `CJ-COMPCERT` |
| After CHERI-TAL and Cerise | the above, plus reopened cases in `CJ-TAL-SOUND` and `CJ-CERISE`, the two theorems with the longest lead times |

So **anything that is ever going into this profile goes in now or never.** "Never" is a legitimate and defensible answer; what is not defensible is arriving at it by not deciding, because the default resolves silently against amendment as soon as the day-one deliverables land.

## 2. Two facts that do most of the ranking

Both correct a plausible line of argument that does not survive contact with the profile.

**Fusion is priced at zero, so no amendment may be justified by deleting a fusion pair.** The tempting argument (a custom instruction replaces a fused pair, and fused pairs carry observational-equivalence obligations, fusion-window invariants across interrupt arrival, and an RTL cross-check, so the instruction is the smaller proof surface) is **wrong here**. R-15-032/R-15-033 make fusion combinational on static encoding and architecturally transparent; R-15-031c records that widening the set adds no admission-test case, no flush-set member, and no obligation beyond R-15-034's listing, and *tightens* every bound it touches. Fusion pairs cost nothing to keep and nothing to add. A custom instruction therefore never wins on cycles that fusion already recovers.

**There is no interrupt prologue to optimize.** R-15-070 *excludes* CHERIoT's interrupt-state sentries, on the ground that asynchronous interrupt delivery is deleted and the three sentry types collapse to one plain sealed entry. The slot-boundary timer is the core's only asynchronous trap ([isa-profile.md](isa-profile.md) §5.3), and the partition switch zeroizes rather than saves (R-07-014a). The general RISC-V critique of software interrupt stacking, and the CHERI aggravation of it by capability register width, both have **no referent on this machine**. Any amendment argued from interrupt cost is arguing about a mechanism that is not here.

## 3. The admission gate

An item earns a place on this list iff it clears all five. The gate is deliberately narrower than the recovery TODO's, because every item here spends the scarce resource rather than avoiding it.

1. **It wins on a booked scarce quantity, not on cycles.** Fusion takes the cycles for free (§2), so a cycle argument is either already collected or unfalsifiable. The two quantities that count are **proof surface** and **code size**, the latter being an admission quantity rather than a preference: gate 6 of the recovery TODO, against no I-cache, the 33–43% no-C penalty accepted at R-15-036, and a composition-time SRAM capacity budget.
2. **It is re-derivable from this profile's emitted mix**, not from the general RISC-V literature. This is R-15-031a's discipline applied one layer up: the fusion set was selected against what a purecap-only, no-C, no-scalar-FP target actually emits, and an amendment answers to the same standard.
3. **It adds no new architectural state**, no flush-set member (R-15-213/215/217/221), no admission-test case (R-15-012), and no mutable microarchitectural structure the absence contract would have to newly police.
4. **It lives in custom opcode space** where it is an instruction, so it can never collide with a future ratified extension, and it carries a Sail clause with a recorded re-pin obligation where a standards track exists, per the §3 discipline of [isa-profile.md](isa-profile.md).
5. **Its cost is booked as a deletion, not slid in as an optimization.** Where an amendment retires a standing obligation (a re-pin target, a differential oracle, an inherited model), that retirement is the headline and belongs in §17, not in an exclusion table row.

**Gate 1 has a corollary worth stating, because it is the trap this list exists to avoid.** [critique.md](critique.md) gap 10 charges that the first release has no stated minimum viable capability, so *delete-rather-than-defend* is unfalsifiable: every deletion is scored on the axis it improves and the axis that would push back has no artifact. A performance-motivated **addition** admitted under the same condition is the identical defect running the other way, and strictly worse, because a deletion at least reduces proof surface while an addition does not. Until a minimum viable capability exists, an amendment justified by throughput cannot be evaluated at all, which is why gate 1 confines the list to the two axes that *do* have artifacts to be scored against.

---

## 4. Declined

Recorded so they are not re-proposed. Each fails a specific gate rather than being merely unattractive.

- **Test-bit-and-branch (`TBZ`/`TBNZ`-class).** Fails gate 1. `bext`+`bnez` falls in R-15-031b's compare-and-branch class, so the cycle is already taken; branch **count** is unchanged, so none of the static-prediction loss row (−10% to −30%) is addressed. And the recovery TODO's own reasoning about Rust bounds checks applies directly: under R-15-019's backward-taken/forward-not-taken rule, a test-bit branch to a cold path is **correctly predicted by construction**. What remains is 4 bytes on a pattern that is not among the profile's highest-frequency pairs, which does not justify an amendment to the schedule root.

- **A bespoke base ISA, for orthogonality or encoding elegance.** Fails gate 1 and gate 5 together. The perf-attributable delta at fixed microarchitecture is single-digit to low-double-digit and is mostly capturable by targeted amendments of the shape this list admits; the proof-surface delta is confined to the ISA-model, decoder, and refinement slice, which is a minority of the total burden dominated by the certifying compiler, the TAL, and the OS logic. Against that, the deletions are severe and land on the least-built arrow: `sail-riscv` ⋈ `sail-cheri-riscv` as an inherited and externally-maintained model, a CompCert backend (1–2 person-years for a *non-capability* target before CHERI), differential testing against Spike, QEMU, `riscv-tests`, and `arch-test`, and the CHERIoT-Ibex FEV work as a methodology reference for R-18-010's second rung. **Differential testing is the load-bearing loss**, and specifically so for this project: proofs catch spec-versus-implementation divergence and do not catch spec-versus-intent divergence, which is R-17-016's residual and the first-ranked risk in [critique.md](critique.md) gap 16. Independent implementations are the only instrument that reports on the layer the proofs sit on top of. **The general rule this instance establishes:** conformance is worth what its *oracles* are worth, not what its badge is worth, and the oracles degrade **proportionally** to the number of amendments rather than all at once, which is exactly why a short bounded list is affordable where a clean sheet is not.

- **Bespoke capability *semantics* (as opposed to representation).** Fails gate 5's spirit, and the narrowed format now in the register is the standing instance of the distinction. Changing the algebra rather than the encoding forfeits the Cambridge security results and converts R-15-007a's representation-correctness proof into a re-proof of monotonicity, provenance, and non-forgeability from scratch, on the arrow with the least slack. R-15-007b's non-orthogonal permission lattice is the **one** admitted algebra change, it is bounded, and it should stay the only one.

- **Reviving the C extension, or a restricted `VerifiedOS-C` profile, as a code-size answer to the amendments this list admits.** Out of scope for this list and recorded here only to keep the two questions apart. R-15-036 excludes C for unique 4-byte-aligned decode, and the amendments here are chosen precisely because they reduce code size **without** reopening variable-length fetch, mid-instruction reinterpretation, or the fetch-alignment machinery. Whether C returns is a separate decision against a separate set of obligations, and an amendment taken here neither strengthens nor weakens it.

---

## 5. Summary

| Item | Wins on | Gate 1 axis | Cost headline | Disposition |
| --- | --- | --- | --- | --- |
| Test-bit-and-branch | 4 bytes on a low-frequency pattern | Fails gate 1 | n/a | **Declined** |
| Bespoke base ISA | Encoding elegance | Fails gates 1 and 5 | Loses Sail model, CompCert backend, differential oracles, FEV reference | **Declined** |
| Bespoke capability semantics | n/a | Fails gate 5 | Forfeits the Cambridge security results | **Declined** |

## 6. What an item that lands has to move

Recorded because an amendment to a derived view is defective unless the register moves first (R-05-152), and because the blast radius is the thing most likely to be underestimated. Any item leaving this list moves, at minimum: the register entry and its acceptance criterion; the normative prose and its bookmark; [isa-profile.md](isa-profile.md) §3 and every other row of that view the amendment narrows; R-18-014a, where the backend owes the selection rule; one entry in the timing-annotated model behind row 15 (`CJ-WCET`); and one case each in `CJ-TAL-SOUND`, `CJ-CERISE`, and `CJ-COMPCERT`.

**And with it:** R-18-034's review-gate rerun, and a re-freeze of row 4.
