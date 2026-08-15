# Code Size: Import TODO (non-normative)

> Companion to [isa-profile.md](isa-profile.md) §1.1 and [cheri-version-matrix.md](cheri-version-matrix.md) §9.2.
> Where the version matrix reads the CHERI lineages against the frozen profile, this doc reads the **RISC-V Code Size Reduction group** ([riscvarchive/riscv-code-size-reduction](https://github.com/riscvarchive/riscv-code-size-reduction), archived; `Zc` merged into the Unprivileged Specification) against R-15-036a's dictionary encoding.
> Nothing here amends the frozen profile. Every row is a reading of [requirements-register.md](requirements-register.md), and where the two disagree the register wins and this document is defective.
> This list records **open** items only: an item that lands normatively leaves the list, and its row leaves the summary table with it.

## Why the family is worth a second reading

[cheri-version-matrix.md](cheri-version-matrix.md) §9.2 already collects the free confirmation: `Zcd`, `Zcmp`, and `Zcmt` are **unavailable on any purecap RV64 machine**, because purecap needs the 16-bit load/store encoding space for `C.LY`/`C.SY`. That is correct and stands.

It is also an argument about **the `C` encoding space**, and this profile has no `C`. R-15-036a substitutes a dictionary format with its own 16-bit slot namespace, and §3 of the profile has already admitted **two bespoke instructions on code-size grounds** — the capability indexed load/store (R-15-007e) and `bfext`/`bfins` (R-15-067a). The encoding-space collision therefore answers *"not on offer"* and not *"not worth having"*. The Zc mechanisms have to be re-judged against the dictionary, which is what this document does.

**Code size is a hard admission quantity here**, not a preference: no I-cache, no swap, no overcommit, and a composition-time SRAM capacity budget measured in square millimetres (clause 6 of [performance-recovery-todo.md](performance-recovery-todo.md)'s pure-win gate). The dictionary bought headroom against that budget; it did not change the budget's character.

## The redundancy classes

The group's decade of work sorts into classes of redundancy. The dictionary collects one of them completely.

| Class | Zc instrument | Status under R-15-036a |
| --- | --- | --- |
| **Per-instruction** — a small set of opcode+operand patterns dominates the histogram | `Zca`, `Zcb` | **Subsumed, and strictly better.** A dictionary index *is* a 16-bit encoding of an existing instruction, selected by measurement rather than by committee, allocating no opcode and creating no decode ambiguity |
| **Cross-reference** — call targets and address materialization | `Zcmt` | **Not collected, and adversarial to the dictionary**, a PC-relative displacement being a distinct entry per site (R-15-036k). Its insight is imported at R-15-036l; its mechanism is rejected at item 2 |

The first row is the load-bearing one and it is a **free confirmation the profile should collect**, of the same class as the matrix's two: `Zcb`'s entire premise is that a handful of already-existing instructions dominates emitted code. That is R-15-036h's premise, reached independently, measured on a real corpus, and shipped. R-15-036h currently rests the density claim on an unattributed hit rate; a citation costs one clause.

## What earns a row

An item belongs here iff it clears all four:

1. **It attacks a redundancy class the dictionary does not collect**, or it corrects a claim the profile makes about density.
2. **It clears the five-part §15 admission test** — or its failure to is the finding.
3. **It adds no architectural state, no `fence.t` flush-set member, no admission-test case, and no structure the absence contract must newly police**, the bar R-15-067c sets for the two code-size instructions already admitted.
4. **It is decided by measurement, not by argument** — R-15-067d's discipline, which is also the group's own stated principle: *"if you can't measure it you can't improve it."*

---

## 1. [DECIDE] Outlining and tail merging — the sequence class has a software instrument, and the profile does not name it

- [ ] **The residual R-15-036n carries is also reachable from the compiler, and nothing in the register says who takes it.**

  A dictionary index names one instruction (R-15-036c), so a recurring *sequence* is outside its codomain at any hit rate. R-15-036n now carries the ISA answer for the stereotyped save/restore case, measurement-conditional. The general answer to the same class is a compiler pass: **outline** a recurring region into a called helper, **tail-merge** shared epilogues, and the sequence collapses into the per-instruction class the dictionary already collects completely. Neither transform appears anywhere in [requirements-register.md](requirements-register.md) or [verification-maximal-os.md](verification-maximal-os.md), and both are ordinary `-Oz` technology — LLVM's machine outliner and identical code folding — shipped for a decade against exactly this budget.

  It earns a row on gate 1, which is about the redundancy class and not about provenance; it is not a `Zc` instrument. Gates 2 and 3 do not clear so much as **fail to arise**: there is no instruction to admit, no opcode consumed, no architectural state, no `fence.t` flush-set member, no decoder state, and nothing new for the absence contract to police. The consumer is the CHERI-CompCert backend (R-18-014a) — the same single emitter R-15-036l and R-15-036n already teach — and the pass owes the secure-compilation obligation every backend pass owes (R-05-024) rather than a new kind of one. This is the profile's standing move, *take the property and decline the mechanism*, made on code size where §5 already made it on CFI for `Zicfilp` landing pads and the typed callee set.

  **The sharp consequence is that R-15-036n's corpus is not well-defined without this decision.** Outlining removes instances of precisely the stereotyped prologues the multi-save covers, so the two are substitutive in R-15-036i's exact sense — *partly substitutive, measured composed and never multiplied, and ordered first*. R-15-036i books that relation for the §10/§13 duplication-removal levers; outlining is such a lever, it is not on that list, and it sits upstream of the one measurement item 3 is meant to take. A multi-save delta re-derived from a backend that does not outline is measured against the wrong corpus, which is R-15-036i's ordering error in a new place and the same error item 3's last paragraph already warns about for `bfext`.

  **The win is also coupled to R-15-036l, tightly enough that the two cannot be measured apart.** For a region of *n* instructions outlined from *m* sites, all site-invariant hits at one slot: the region costs *nm* slots inline, against *n* + *m* + 1 outlined if the call is composition-time absolute and therefore one shared dictionary entry, or *n* + 2*m* + 1 if it stays PC-relative, every site being a distinct displacement and so a site-varying miss at two slots (R-15-036k). Break-even moves materially: a two-instruction region pays from four sites under an absolute call and **never pays** under a PC-relative one, and a three-instruction region needs five sites instead of three. R-15-036j's padding term pushes the same way, escapes stranding slots. Two riders: the profitable regions are those needing no frame of their own, or the helper re-incurs the save sequence this is meant to collect, and outlining must stay **intra-compartment** — a whole-image pass would fight the per-compartment admission model exactly as [architectural-alternatives.md](architectural-alternatives.md) records defunctionalization doing.

  **The cost is cycles, and here cycles are capacity, not throughput.** Each outlined region trades inline instructions for a call and return on the dynamic path, so this fails clause 6 of [performance-recovery-todo.md](performance-recovery-todo.md)'s pure-win gate on the cycle axis — which is why it is `[DECIDE]` and not `[YES]`. Under the static cyclic executive a partition's capacity *is* its slot width (R-07-032, R-07-037), so WCET inflation does not degrade smoothly: it widens a slot or it does not fit. Note the trade runs opposite to R-15-036n's, which spends architecture to buy cycles where this spends cycles to buy architecture.

  **Owed:** a decision recorded either way, and a **two-axis** measurement rather than the one-axis one the other candidates take — bytes removed *and* WCET added, since a lever that fails the pure-win gate cannot be settled on the byte column alone. It belongs in the same act as R-15-036l and R-15-036n and must be **ordered before both**, per R-15-036i. Expectation, unlike R-15-036n's, is that it carries: it costs no encoding budget, competes with nothing in §3, and its instrument is a backend pass rather than an ISA amendment.

## 2. [NO] `Zcmt` table jump — reject the mechanism, keep the insight

- [ ] **Record the rejection, since the profile currently rejects it only by accident of encoding space.**

  A table jump puts a **runtime memory read in the branch path** with an address derived from a table, on a machine whose forward-edge CFI is sentry-based (R-15-008) and which is explicit that a sentry deliberately does *not* decide target membership (R-15-072). The JVT is a CSR: new architectural state, a `fence.t` flush-set member (R-15-062), and a context-switch line item. The table read is also an address-derived access in the fetch path, adjacent to the address-timing channel R-15-085a fences off.

  The strongest evidence is already in this repo: [cheri-version-matrix.md](cheri-version-matrix.md) §9.1 records that at v0.7.1–v0.8.3 **`Zcmt` checking was moved to PCC bounds in legacy mode** — the standards line had to invent a bespoke authority rule for the JVT fetch the moment capabilities arrived. That is the mechanism failing to compose with CHERI upstream, independently.

  The insight survives and is booked at R-15-036l: *index the target, do not displace to it*. On this platform it reduces to *use composition-time absolute targets*, which needs no table.

## 3. [YES] The measurement instrument, which the profile owes five times over

- [ ] **Name a corpus, a tool, and a threshold.**

  The group's durable output beyond the specification is a method: a benchmark corpus, an ELF-diffing analysis script, published per-extension deltas, and a standing refusal to admit an instruction without one.

  The profile has **five open measurement obligations** and no instrument for any of them:

  | Obligation | What must be measured | Against what |
  | --- | --- | --- |
  | R-15-036h, R-15-036k | dictionary hit rate *p* **stratified by operand class**, and the realized dictionary itself | the composed image, after §13's merge (R-15-036i) |
  | R-15-036l | whether the call and global-address forms are PC-relative or composition-time absolute | generated output at the freeze, in R-15-067d's style |
  | R-15-036n | whether the single-check multi-register stack save and restore is carried at all | generated prologues and epilogues at the freeze, in the same act as R-15-036l and R-15-067d |
  | R-15-067d | whether `bfext`/`bfins` carry, in which form | generated Narcissus UPER/TLV codecs and generated MMIO accessors |
  | R-15-007g | the indexed load/store scale immediate | the emitted mix, under R-15-031a's discipline |

  All five say *"measured"*; none names a corpus, a tool, a threshold, or who runs it. [tools/](tools/) holds only `check.ps1`. One instrument discharges the shape of all five, and R-18-003b(i) makes the profile freeze and its Sail curation the **first day-one deliverable**, which is where this instrument is needed rather than after.

  R-15-036k raises the bar on the first row rather than adding a row: an instrument that reports one aggregate *p* cannot discharge it, so the corpus must carry operand-class provenance from the emitter and not be recovered by disassembly after the fact.

  Note the ordering constraint this shares with R-15-036i: a dictionary selected against an unmerged image is selected against the wrong histogram, and a `bfext` delta measured against hand-written rather than generated code is measured against the wrong corpus. Item 1 adds a third instance and the only one that is not yet decided — whether the corpus comes from a backend that outlines — which must be settled before the instrument is pointed at R-15-036n. The corpus definition is part of the obligation, not a detail of running it.

---

## What the list says

**One decision, and it is upstream of the others.** The sequence class has a software instrument the register never names, it is substitutive with R-15-036n rather than additive, and it is the one open question that changes what the corpus *is* — so it is settled first or the measurement below is taken against the wrong output.

**One rejection worth writing down**, because the profile currently gets the right answer on `Zcmt` for a reason (encoding-space collision with `C.LY`/`C.SY`) that does not apply to a machine with no `C`.

**One free confirmation.** `Zcb` is the dictionary's premise, reached independently and measured on a real corpus, and R-15-036h should cite it.

**And one instrument**, which is the cheapest item here and unblocks five obligations that currently name a measurement without naming a way to take it.

## Sources

- [`riscvarchive/riscv-code-size-reduction`](https://github.com/riscvarchive/riscv-code-size-reduction) — archived; the `Zc` specification is merged into the RISC-V Unprivileged Specification
- Zc specification: `Zca` (C minus floating-point load/store), `Zcb` (byte/halfword load/store, sign/zero extension, `c.mul`, `c.not`), `Zcf`/`Zcd` (compressed FP load/store), `Zcmp` (`cm.push`/`cm.pop`/`cm.popret`/`cm.popretz` plus `cm.mva01s`/`cm.mvsa01`), `Zcmt` (`cm.jt`/`cm.jalt` through the JVT CSR), `Zce` (the microcontroller bundle)
- The group's stated method: *"if you can't measure it you can't improve it"* — a benchmark corpus, an ELF-size analysis script, and published per-extension deltas
