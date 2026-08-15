# Bespoke ISA Deviation: Amendment TODO (non-normative)

> Companion to [isa-profile.md](isa-profile.md) and [performance-recovery-todo.md](performance-recovery-todo.md), and the **mirror image** of the latter.
> The recovery TODO is confined by construction to levers that touch no theorem, spend no trust, and require no amendment: "engineering is free; trust is the scarce resource." This list records the opposite class, the levers that are worth having **only** by amending the frozen profile, and it exists because that class was being reasoned about informally and priced wrong in both directions.
> An amendment to the profile reruns the review gate (R-18-034) and moves the schedule root (R-18-003a). Nothing here is normative, nothing here relaxes the five-part §15 admission test, and an item that lands in the register leaves this list.
> **The premise of the list is that RISC-V conformance is already spent, not that it is cheap.** [isa-profile.md](isa-profile.md) forks standard RVV twice (scalar-FP-free at R-15-040, `vstart`-free at R-15-040a), deletes the C extension, mandates Ztso in place of RVWMO, freezes a bespoke matrix extension and a bespoke Keccak instruction, and runs M-mode-only purecap with CHERI as the sole protection mechanism. No profile-conforming binary runs here and nothing built here runs elsewhere. What conformance still buys is enumerated in §3 below, and it is not zero; it is just much smaller than the word suggests.

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

## 4. Banked: the narrowed capability format

**Take it as re-parameterized CHERI Concentrate, not as a bespoke format.** Same bounds algorithm, same capability algebra, different field widths. That distinction is the whole of why this is affordable: the Cambridge monotonicity, provenance, and non-forgeability results are statements about the algebra and not the bit layout, so preserving the algebra exactly and changing only the representation leaves those results reusable and owes a **representation-correctness proof** (encode/decode round-trip, field-extraction lemmas, bounds derivation) rather than a re-proof. The Sail work becomes a re-parameterization of `sail-cheri-riscv`'s capability functions rather than a rewrite, which keeps most of the differential-testing surface intact.

This is the only item on the list that pays primarily on **proof surface**, and it is the one to take even if nothing else is taken.

### What the platform's own constraints hand you

| Constraint | Governing | What it releases |
| --- | --- | --- |
| Single physical address space, no MMU, `satp` Bare | R-15-002 | No virtual-address space to span and **no VA-expansion pressure ever**; the 64-bit address field exists in CHERI-RISC-V to be future-proof against a growth axis this machine does not have |
| All-die SRAM, 1–2 GB roster | §15 | Physical address space bounded by fabricable silicon rather than by architecture |
| Static task set, composition-time authority graph | §13, R-15-005 | The complete permission lattice and the full set of sealed-capability classes are known at freeze time, so orthogonal permission bits are generality that has no consumer |
| One capability encoding, no hybrid, no CHERIoT second format | R-15-005, R-15-001 | The narrowing applies uniformly, RoT included; nothing forks |

### The prize is bounds precision, and it is proof surface rather than area

CHERI Concentrate's mantissas are small because they compress bounds over 2⁶⁴. The **same or larger mantissas over a 2³⁴–2³⁶ space give exact bounds across most of the allocation size range**, with imprecision confined to large objects. Three consequences, in descending order of value:

- **Representable-region-versus-requested-region reasoning leaves the common case** in the allocator (§12's allocation discipline), in CHERI-TAL, and in the `CJ-TAL-SOUND` obligation. This is a genuine reduction in proof surface, not a performance claim.
- **The recovery TODO's bounds-check-elision entry loses one of its two disqualifying arguments.** That entry declines the certified form partly because "compressed bounds round outward above the representable-precision threshold, so the analysis is least sound on exactly the large arrays whose hot indexed loops would pay most." Better precision does not by itself revive the lever (the silent-failure-mode argument stands on its own and is the stronger half), but it removes the anti-correlation, and the entry should be re-read rather than assumed unchanged.
- **Allocator alignment constraints collapse** for sub-threshold objects, which is capacity on a budget measured in square millimetres.

### The secondary wins

- **The capability register file halves.** Directly against R-07-014a's partition-switch zeroize obligation and, through the store buffer, against R-15-088's `fence.t` padded constant.
- **Capability spills halve.** Code size (gate 6) and image capacity, on a machine where a purecap ABI makes capability spills the common spill.

### What it costs, stated as deletions

- **R-15-007's re-pin obligation to the ratified RVY base is abandoned outright.** This is the headline cost and belongs in §17 as a retired obligation, not in the §6 exclusion table. It is a larger scope-honesty change than any instruction on this list, because it converts the CHERI dialect from *forked pending ratification* into *permanently bespoke*.
- **The tag granule moves 128 → 64 bits.** R-15-203 carries tags as native SRAM bits, one validity tag per 128-bit granule, read and written in parallel with the data, with no tag table and no tag cache. Halving the granule doubles tag-plane density (0.78% → 1.56% of array). Capability-dense structures halve in size, so the net is plausibly favourable and is **directly computable against the roster** rather than arguable, but it is not free and it touches row 9's bank/macro/tier binding map and the DECTED tag-code area.
- **Row 6 acquires the capability encoding as authored rather than curated work**, on the arrow R-17-039 calls the least-built layer. This is smaller than it first appears, since row 6 is already a fork on five independent axes, but it lands where the schedule is thinnest.

### The parameter has a cliff, and the cliff is the actual decision

The format width is not a smooth trade. A worked reference point: CHERIoT reaches 64-bit capabilities on a 32-bit address space with roughly 9-bit base and top mantissas, a 4-bit exponent, 6 bits of encoded (non-orthogonal) permissions, and 3 bits of object type. Scaling that to a 34–36 bit address consumes nearly all of the remaining budget.

So:

- **34–36 address bits** (16–64 GB) lands at **64+1** and delivers the halved register file, the halved spills, and the precision win together.
- **40 address bits** (1 TB) either costs the precision that is the main prize, or pushes the format to 96+1 or 128+1, at which point the register-file and spill wins evaporate and only the precision win survives.

**The commitment is permanent**, a later format break invalidating every stored capability in the immutable image, so it deserves the margin question asked explicitly rather than defaulted. The argument that makes 34–36 bits safe here, and that would **not** hold for a DRAM design, is that the address space is bounded by on-die SRAM: the roster is 1–2 GB, and SRAM density does not put 64 GB on a die within any horizon this design plans for. That is a far stronger guarantee than "we do not expect to need more."

**Two follow-on obligations if this is taken:**

- **The physical address map must be dense.** A narrow space cannot absorb MMIO apertures scattered at wide power-of-two offsets. This becomes a constraint on the attested devicetree and on row 9's binding map, and it should be stated there rather than discovered at composition.
- **The permission encoding becomes non-orthogonal**, so the permission lattice must be authored as an enumerated set with its join/meet, and monotonicity restated over it. This is a small, bounded proof obligation and it is the one place the *algebra* changes rather than only the representation, so it is the part that does not inherit.

---

## 5. Banked: a capability indexed load/store

Shape: `cld rd, cs1[rs2 << imm]` and the store form. Bounds and permission check on base + scaled index, **with no intermediate capability materialized**.

### Why it clears gate 1

R-15-031b names `cincoffset`+load/store as the offset-then-dereference pair covering **"every indexed dereference here"**, and records that base-plus-index `add`+load does not exist separately because a purecap load takes no integer base. Fusion already recovers the cycle. What fusion cannot recover is **bytes**: a fused pair still occupies 8 bytes of image and of fetch bandwidth.

That makes this the **largest single code-size lever available**, because it applies to the highest-frequency pair the profile emits, on a machine with no I-cache, an accepted 33–43% no-C penalty (R-15-036), and code size as a hard admission quantity.

### Why it is less capability semantics, not more

This is the non-obvious part and it is what distinguishes this item from an ordinary custom instruction. The fused pair materializes an **intermediate capability** whose representability must be reasoned about: `cincoffset` may produce a capability outside the representable region, which is a case CHERI-TAL, Cerise, and the Sail model each carry. A single indexed access never materializes it. The representability question **leaves that path** rather than being discharged on it.

It also composes with §4: better bounds precision and the absence of an intermediate both cut at the same reasoning.

### Cost

One Sail clause and its semantics; one instruction-selection rule in the backend; one case each in `CJ-TAL-SOUND` and `CJ-CERISE`; one entry in the timing-annotated model. No new architectural state, no flush-set member, no admission-test case. Custom opcode space is available and uncontended, the profile having no C extension to compete with for 32-bit encoding space.

**Open:** whether the shift-amount immediate is worth its encoding bits, or whether an unscaled index suffices given that element strides are known at composition. Decide against the emitted mix, per gate 2.

---

## 6. Conditional: multi-bit bitfield extract and insert

`Zbs` is adopted (R-15-067) and provides **single-bit** `bext`/`bset`/`bclr`. RISC-V has no general bitfield extract or insert, so a multi-bit field access lowers to a shift-and-mask pair, and an insert to a longer sequence.

**The justification is specific to this platform's mix and is unusually strong on paper.** Row 10 of [crown-jewels.md](crown-jewels.md) is the wire-format inventory: ASN.1 **UPER** (bit-aligned, not byte-aligned) RRC grammars, the IEI/TLV 5G-NAS grammar, the 802.11 MLME element grammars, plus the image, media, font, archive, and document formats. Narcissus-generated decoders over bit-aligned grammars are bitfield extraction in a loop, and machine-generated code is shaped **entirely** by what the backend can lower to, so the multiplier here is larger than for hand-written code.

**Why it is conditional rather than banked.** The cycle half is partly available to fusion already (`slli`+`srli`, `srli`+`andi` are short dependent-ALU chains, the third class in R-15-031's frozen set). The size half is real, and the dependent chains in bit-packed decode are longer than adjacent-pair fusion collapses well, but the magnitude is a claim about emitted code that has not been measured.

**Admission condition:** re-derive from actual Narcissus output on at least the UPER RRC and IEI/TLV descriptors, and land it only if the image-size delta is material against the §15 capacity budget. This is gate 2 held strictly, and it is the general form of what should be required of every item on this list.

---

## 7. Declined

Recorded so they are not re-proposed. Each fails a specific gate rather than being merely unattractive.

- **Test-bit-and-branch (`TBZ`/`TBNZ`-class).** Fails gate 1. `bext`+`bnez` falls in R-15-031b's compare-and-branch class, so the cycle is already taken; branch **count** is unchanged, so none of the static-prediction loss row (−10% to −30%) is addressed. And the recovery TODO's own reasoning about Rust bounds checks applies directly: under R-15-019's backward-taken/forward-not-taken rule, a test-bit branch to a cold path is **correctly predicted by construction**. What remains is 4 bytes on a pattern that is not among the profile's highest-frequency pairs, which does not justify an amendment to the schedule root.

- **A bespoke base ISA, for orthogonality or encoding elegance.** Fails gate 1 and gate 5 together. The perf-attributable delta at fixed microarchitecture is single-digit to low-double-digit and is mostly capturable by the items above; the proof-surface delta is confined to the ISA-model, decoder, and refinement slice, which is a minority of the total burden dominated by the certifying compiler, the TAL, and the OS logic. Against that, the deletions are severe and land on the least-built arrow: `sail-riscv` ⋈ `sail-cheri-riscv` as an inherited and externally-maintained model, a CompCert backend (1–2 person-years for a *non-capability* target before CHERI), differential testing against Spike, QEMU, `riscv-tests`, and `arch-test`, and the CHERIoT-Ibex FEV work as a methodology reference for R-18-010's second rung. **Differential testing is the load-bearing loss**, and specifically so for this project: proofs catch spec-versus-implementation divergence and do not catch spec-versus-intent divergence, which is R-17-016's residual and the first-ranked risk in [critique.md](critique.md) gap 16. Independent implementations are the only instrument that reports on the layer the proofs sit on top of. **The general rule this instance establishes:** conformance is worth what its *oracles* are worth, not what its badge is worth, and the oracles degrade **proportionally** to the number of amendments rather than all at once, which is exactly why a short bounded list is affordable where a clean sheet is not.

- **Bespoke capability *semantics* (as opposed to representation).** Fails gate 5's spirit and the §4 argument. Changing the algebra rather than the encoding forfeits the Cambridge security results and converts a representation-correctness proof into a re-proof of monotonicity, provenance, and non-forgeability from scratch, on the arrow with the least slack. §4's non-orthogonal permission lattice is the **one** admitted algebra change, it is bounded, and it should stay the only one.

- **Reviving the C extension, or a restricted `VerifiedOS-C` profile, as a code-size answer to the items above.** Out of scope for this list and recorded here only to keep the two questions apart. R-15-036 excludes C for unique 4-byte-aligned decode, and the items above are chosen precisely because they reduce code size **without** reopening variable-length fetch, mid-instruction reinterpretation, or the fetch-alignment machinery. Whether C returns is a separate decision against a separate set of obligations, and an amendment taken here neither strengthens nor weakens it.

---

## 8. Summary

| Item | Wins on | Gate 1 axis | Cost headline | Disposition |
| --- | --- | --- | --- | --- |
| Narrowed capability format (re-parameterized Concentrate, 64+1) | Bounds precision; halved capability RF and spills; zeroize and `fence.t` budget | **Proof surface** and code size | R-15-007's RVY re-pin obligation retired; tag granule 128→64 | **Bank** |
| Capability indexed load/store | 4 bytes on every indexed dereference; no intermediate capability materialized | **Code size** | One Sail clause; one case each in `CJ-TAL-SOUND`, `CJ-CERISE` | **Bank** |
| Multi-bit bitfield extract/insert | Bit-aligned wire-format decode (UPER, IEI/TLV, MLME) | **Code size** | Two Sail clauses | **Conditional** on measured Narcissus output |
| Test-bit-and-branch | 4 bytes on a low-frequency pattern | Fails gate 1 | n/a | **Declined** |
| Bespoke base ISA | Encoding elegance | Fails gates 1 and 5 | Loses Sail model, CompCert backend, differential oracles, FEV reference | **Declined** |
| Bespoke capability semantics | n/a | Fails gate 5 | Forfeits the Cambridge security results | **Declined** |

## 9. What moves if the banked items land

Recorded because an amendment to a derived view is defective unless the register moves first (R-05-152), and because the blast radius is the thing most likely to be underestimated.

**Narrowed capability format:**
- R-15-007 (128-bit purecap encoding; RVY re-pin): **rewritten**, with the retired re-pin booked in §17
- R-15-203 (tag granule): granule and density restated; row 9's binding map and the DECTED tag-code area re-derived
- R-07-014a, R-15-088: budgets re-derived, both favourably
- Crown-jewel rows 4 and 6: row 4 re-frozen, row 6's capability semantics move from curated to authored
- §12 allocation discipline: alignment constraints re-derived
- [performance-recovery-todo.md](performance-recovery-todo.md), bounds-check-elision entry: one of two disqualifying arguments weakened; re-read, do not assume unchanged
- The attested devicetree: new density constraint on the physical address map

**Capability indexed load/store:**
- [isa-profile.md](isa-profile.md) §3: new row, custom opcode space, no standards-track re-pin target
- R-15-031b: the offset-then-dereference pair narrows to the cases the new instruction does not cover; the pair is **not** deleted, since fusion costs nothing to keep and the sequence remains legal
- Row 15 (`CJ-WCET` latency magnitudes): one entry
- `CJ-TAL-SOUND`, `CJ-CERISE`, `CJ-COMPCERT`: one case each

**Both:** R-18-034's review-gate rerun, and a re-freeze of row 4.
