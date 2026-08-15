# Code Size: Import TODO (non-normative)

> Companion to [isa-profile.md](isa-profile.md) §1.1 and [cheri-version-matrix.md](cheri-version-matrix.md) §9.2.
> Where the version matrix reads the CHERI lineages against the frozen profile, this doc reads the **RISC-V Code Size Reduction group** ([riscvarchive/riscv-code-size-reduction](https://github.com/riscvarchive/riscv-code-size-reduction), archived; `Zc` merged into the Unprivileged Specification) against R-15-036a's dictionary encoding.
> Nothing here amends the frozen profile. Every row is a reading of [requirements-register.md](requirements-register.md), and where the two disagree the register wins and this document is defective.
> This list records **open** items only: an item that lands normatively leaves the list, and its row leaves the summary table with it.

## Why the family is worth a second reading

[cheri-version-matrix.md](cheri-version-matrix.md) §9.2 already collects the free confirmation: `Zcd`, `Zcmp`, and `Zcmt` are **unavailable on any purecap RV64 machine**, because purecap needs the 16-bit load/store encoding space for `C.LY`/`C.SY`. That is correct and stands.

It is also an argument about **the `C` encoding space**, and this profile has no `C`. R-15-036a substitutes a dictionary format with its own 16-bit slot namespace, and §3 of the profile has already admitted **two bespoke instructions on code-size grounds** — the capability indexed load/store (R-15-007e) and `bfext`/`bfins` (R-15-067a). The encoding-space collision therefore answers *"not on offer"* and not *"not worth having"*. The Zc mechanisms have to be re-judged against the dictionary, which is what this document does.

**Code size is a hard admission quantity here**, not a preference: no I-cache, no swap, no overcommit, and a composition-time SRAM capacity budget measured in square millimetres (clause 6 of [performance-recovery-todo.md](performance-recovery-todo.md)'s pure-win gate). The dictionary bought headroom against that budget; it did not change the budget's character.

## The three redundancy classes

The group's decade of work sorts into three classes of redundancy. The dictionary collects exactly one of them, completely.

| Class | Zc instrument | Status under R-15-036a |
| --- | --- | --- |
| **Per-instruction** — a small set of opcode+operand patterns dominates the histogram | `Zca`, `Zcb` | **Subsumed, and strictly better.** A dictionary index *is* a 16-bit encoding of an existing instruction, selected by measurement rather than by committee, allocating no opcode and creating no decode ambiguity |
| **Sequence** — recurring multi-instruction idioms, dominantly prologue/epilogue | `Zcmp` | **Not collected.** The dictionary is a total `Fin N → Instr` (R-15-036c); its codomain is one instruction, so it cannot name a sequence at any hit rate |
| **Cross-reference** — call targets and address materialization | `Zcmt` | **Not collected, and adversarial to the dictionary**, a PC-relative displacement being a distinct entry per site (R-15-036k). Its insight is imported at R-15-036l; its mechanism is rejected at item 2 |

The first row is the load-bearing one and it is a **free confirmation the profile should collect**, of the same class as the matrix's two: `Zcb`'s entire premise is that a handful of already-existing instructions dominates emitted code. That is R-15-036h's premise, reached independently, measured on a real corpus, and shipped. R-15-036h currently rests the density claim on an unattributed hit rate; a citation costs one clause.

## What earns a row

An item belongs here iff it clears all four:

1. **It attacks a redundancy class the dictionary does not collect**, or it corrects a claim the profile makes about density.
2. **It clears the five-part §15 admission test** — or its failure to is the finding.
3. **It adds no architectural state, no `fence.t` flush-set member, no admission-test case, and no structure the absence contract must newly police**, the bar R-15-067c sets for the two code-size instructions already admitted.
4. **It is decided by measurement, not by argument** — R-15-067d's discipline, which is also the group's own stated principle: *"if you can't measure it you can't improve it."*

---

## 1. [DECIDE] A `Zcmp`-shaped multi-save, in single-check form only

- [ ] **The residual is real, and the dictionary has already collected half of it.**

  Prologues are stereotyped, so the dictionary hits on them at near unity — each `csc cs_i, off(csp)` at a recurring (register, offset) pair is one entry, reused at every call site in the image. `Zcmp`'s marginal win over the dictionary is therefore **(k−1)·16 bits, not (k−1)·32**: half its value against RVC, which is the figure the group measured it at.

  Against that halved win, stock `cm.push`/`cm.pop` are multi-access compound instructions with a **restartable mid-sequence trap model**. That is architectural state, and it fails gate 3 outright — it is also a direct hit on R-15-036b's *no decoder state* and would put a sequencer where the profile has a stateless decoder.

  One platform accident cuts the other way and is worth recording: asynchronous interrupt delivery is deleted (R-15-070 collapses the three CHERIoT sentry types to one on exactly this ground), so the hardest part of specifying compound multi-access instructions in stock RISC-V does not arise here. What remains is the capability check, which can still fault mid-sequence.

  **The one admissible form is all-or-nothing with a single up-front bounds check** against `[csp − adj, csp)` instead of *k* checks. That is structurally the same admission argument R-15-007f makes for the indexed load/store — *less* capability semantics rather than more, one check where the sequence does N — and it is the argument that has already cleared this bar once. The stack is a distinguished statically-known capability here (R-15-074: only the stack carries `store-local`), and the whole consumer is the CHERI-CompCert backend (R-18-014a), so there is one emitter to teach.

  **Owed:** carry it as a **measurement-conditional candidate in R-15-067d's style** — re-derived at the freeze from actual generated output, dropped on an immaterial delta rather than carried on the argument. Expectation is that it dies: the win is halved, and it competes for the same bespoke-encoding budget as the matrix's `CSetBounds`-with-large-immediate row and as R-15-036l's absolute call and global-address forms, which the matrix now carries `AUICGP` against. Decide the four together.

## 2. [NO] `Zcmt` table jump — reject the mechanism, keep the insight

- [ ] **Record the rejection, since the profile currently rejects it only by accident of encoding space.**

  A table jump puts a **runtime memory read in the branch path** with an address derived from a table, on a machine whose forward-edge CFI is sentry-based (R-15-008) and which is explicit that a sentry deliberately does *not* decide target membership (R-15-072). The JVT is a CSR: new architectural state, a `fence.t` flush-set member (R-15-062), and a context-switch line item. The table read is also an address-derived access in the fetch path, adjacent to the address-timing channel R-15-085a fences off.

  The strongest evidence is already in this repo: [cheri-version-matrix.md](cheri-version-matrix.md) §9.1 records that at v0.7.1–v0.8.3 **`Zcmt` checking was moved to PCC bounds in legacy mode** — the standards line had to invent a bespoke authority rule for the JVT fetch the moment capabilities arrived. That is the mechanism failing to compose with CHERI upstream, independently.

  The insight survives and is booked at R-15-036l: *index the target, do not displace to it*. On this platform it reduces to *use composition-time absolute targets*, which needs no table.

## 3. [YES] The measurement instrument, which the profile owes four times over

- [ ] **Name a corpus, a tool, and a threshold.**

  The group's durable output beyond the specification is a method: a benchmark corpus, an ELF-diffing analysis script, published per-extension deltas, and a standing refusal to admit an instruction without one.

  The profile has **four open measurement obligations** and no instrument for any of them:

  | Obligation | What must be measured | Against what |
  | --- | --- | --- |
  | R-15-036h, R-15-036k | dictionary hit rate *p* **stratified by operand class**, and the realized dictionary itself | the composed image, after §13's merge (R-15-036i) |
  | R-15-036l | whether the call and global-address forms are PC-relative or composition-time absolute | generated output at the freeze, in R-15-067d's style |
  | R-15-067d | whether `bfext`/`bfins` carry, in which form | generated Narcissus UPER/TLV codecs and generated MMIO accessors |
  | R-15-007g | the indexed load/store scale immediate | the emitted mix, under R-15-031a's discipline |

  All four say *"measured"*; none names a corpus, a tool, a threshold, or who runs it. [tools/](tools/) holds only `check.ps1`. One instrument discharges the shape of all four, and R-18-003b(i) makes the profile freeze and its Sail curation the **first day-one deliverable**, which is where this instrument is needed rather than after.

  R-15-036k raises the bar on the first row rather than adding a row: an instrument that reports one aggregate *p* cannot discharge it, so the corpus must carry operand-class provenance from the emitter and not be recovered by disassembly after the fact.

  Note the ordering constraint this shares with R-15-036i: a dictionary selected against an unmerged image is selected against the wrong histogram, and a `bfext` delta measured against hand-written rather than generated code is measured against the wrong corpus. The corpus definition is part of the obligation, not a detail of running it.

---

## What the list says

**One decision.** A single-check multi-save is the only `Zcmp`-shaped construct that clears R-15-067c's bar, its win is halved by the dictionary, and it should be measured beside `bfext`/`bfins`, the matrix's `CSetBounds`-with-large-immediate row, and R-15-036l's absolute call and global-address forms rather than argued on its own.

**One rejection worth writing down**, because the profile currently gets the right answer on `Zcmt` for a reason (encoding-space collision with `C.LY`/`C.SY`) that does not apply to a machine with no `C`.

**One free confirmation.** `Zcb` is the dictionary's premise, reached independently and measured on a real corpus, and R-15-036h should cite it.

**And one instrument**, which is the cheapest item here and unblocks four obligations that currently name a measurement without naming a way to take it.

## Sources

- [`riscvarchive/riscv-code-size-reduction`](https://github.com/riscvarchive/riscv-code-size-reduction) — archived; the `Zc` specification is merged into the RISC-V Unprivileged Specification
- Zc specification: `Zca` (C minus floating-point load/store), `Zcb` (byte/halfword load/store, sign/zero extension, `c.mul`, `c.not`), `Zcf`/`Zcd` (compressed FP load/store), `Zcmp` (`cm.push`/`cm.pop`/`cm.popret`/`cm.popretz` plus `cm.mva01s`/`cm.mvsa01`), `Zcmt` (`cm.jt`/`cm.jalt` through the JVT CSR), `Zce` (the microcontroller bundle)
- The group's stated method: *"if you can't measure it you can't improve it"* — a benchmark corpus, an ELF-size analysis script, and published per-extension deltas
