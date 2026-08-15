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

## 1. [NO] `Zcmt` table jump — reject the mechanism, keep the insight

- [ ] **Record the rejection, since the profile currently rejects it only by accident of encoding space.**

  A table jump puts a **runtime memory read in the branch path** with an address derived from a table, on a machine whose forward-edge CFI is sentry-based (R-15-008) and which is explicit that a sentry deliberately does *not* decide target membership (R-15-072). The JVT is a CSR: new architectural state, a `fence.t` flush-set member (R-15-062), and a context-switch line item. The table read is also an address-derived access in the fetch path, adjacent to the address-timing channel R-15-085a fences off.

  The strongest evidence is already in this repo: [cheri-version-matrix.md](cheri-version-matrix.md) §9.1 records that at v0.7.1–v0.8.3 **`Zcmt` checking was moved to PCC bounds in legacy mode** — the standards line had to invent a bespoke authority rule for the JVT fetch the moment capabilities arrived. That is the mechanism failing to compose with CHERI upstream, independently.

  The insight survives and is booked at R-15-036l: *index the target, do not displace to it*. On this platform it reduces to *use composition-time absolute targets*, which needs no table.

## 2. [YES] The measurement instrument, which the profile owes six times over

- [ ] **Name a corpus, a tool, and a threshold.**

  The group's durable output beyond the specification is a method: a benchmark corpus, an ELF-diffing analysis script, published per-extension deltas, and a standing refusal to admit an instruction without one.

  The profile has **six open measurement obligations** and no instrument for any of them:

  | Obligation | What must be measured | Against what |
  | --- | --- | --- |
  | R-15-036h, R-15-036k | dictionary hit rate *p* **stratified by operand class**, and the realized dictionary itself | the composed image, after §13's merge (R-15-036i) |
  | R-15-036p | bytes removed **and worst-case cycles added** by outlining and tail merging, per admitted region class | the composed image, before every row below it (R-15-036o) |
  | R-15-036l | whether the call and global-address forms are PC-relative or composition-time absolute | generated output at the freeze, in R-15-067d's style |
  | R-15-036n | whether the single-check multi-register stack save and restore is carried at all | generated prologues and epilogues at the freeze, in the same act as R-15-036l and R-15-067d |
  | R-15-067d | whether `bfext`/`bfins` carry, in which form | generated Narcissus UPER/TLV codecs and generated MMIO accessors |
  | R-15-007g | the indexed load/store scale immediate | the emitted mix, under R-15-031a's discipline |

  All six say *"measured"*; none names a corpus, a tool, a threshold, or who runs it. [tools/](tools/) holds only `check.ps1`. One instrument discharges the shape of all six, and R-18-003b(i) makes the profile freeze and its Sail curation the **first day-one deliverable**, which is where this instrument is needed rather than after.

  R-15-036k raises the bar on the first row rather than adding a row: an instrument that reports one aggregate *p* cannot discharge it, so the corpus must carry operand-class provenance from the emitter and not be recovered by disassembly after the fact.

  **R-15-036p raises it on a second axis, and this is the one structural demand the list makes of the instrument.** Every other row is answered by a byte count; that one is not, because outlining fails the pure-win gate on cycles, so the instrument must emit a bytes-and-cycles pair per region class and take its WCET column from §11's model rather than from a stopwatch. An instrument built for bytes alone cannot discharge it and would report the lever as a clean win.

  Note the ordering constraint this shares with R-15-036i: a dictionary selected against an unmerged image is selected against the wrong histogram, a `bfext` delta measured against hand-written rather than generated code is measured against the wrong corpus, and R-15-036p's row runs before R-15-036l's and R-15-036n's or their corpus is the output of a backend that does not outline. The corpus definition is part of the obligation, not a detail of running it.

---

## What the list says

**One rejection worth writing down**, because the profile currently gets the right answer on `Zcmt` for a reason (encoding-space collision with `C.LY`/`C.SY`) that does not apply to a machine with no `C`.

**One free confirmation.** `Zcb` is the dictionary's premise, reached independently and measured on a real corpus, and R-15-036h should cite it.

**And one instrument**, which is the cheapest item here and unblocks six obligations that currently name a measurement without naming a way to take it, one of which needs a cycles column and not only a byte one.

## Sources

- [`riscvarchive/riscv-code-size-reduction`](https://github.com/riscvarchive/riscv-code-size-reduction) — archived; the `Zc` specification is merged into the RISC-V Unprivileged Specification
- Zc specification: `Zca` (C minus floating-point load/store), `Zcb` (byte/halfword load/store, sign/zero extension, `c.mul`, `c.not`), `Zcf`/`Zcd` (compressed FP load/store), `Zcmp` (`cm.push`/`cm.pop`/`cm.popret`/`cm.popretz` plus `cm.mva01s`/`cm.mvsa01`), `Zcmt` (`cm.jt`/`cm.jalt` through the JVT CSR), `Zce` (the microcontroller bundle)
- The group's stated method: *"if you can't measure it you can't improve it"* — a benchmark corpus, an ELF-size analysis script, and published per-extension deltas
