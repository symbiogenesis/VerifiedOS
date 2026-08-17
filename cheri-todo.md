# CHERI Profile TODO

*Non-normative. The work list distilled from [cheri-version-matrix.md](cheri-version-matrix.md), which is itself a reading of [requirements-register.md](requirements-register.md) and [isa-profile.md](isa-profile.md). Where this document and the register disagree, **the register wins and this document is defective**. Nothing here amends the frozen profile: this is the agenda the review gate (R-18-034) works through, not a set of decisions already taken.*

*Every item carries the matrix row it came from, the requirements that govern it, and the place in [isa-profile.md](isa-profile.md) where the change lands. Items are ordered by class, not by size: a one-line statement that closes a named hole outranks a design question that would take a quarter to settle.*

**Convention.** When an item lands normatively, delete the bullet and its row in the landing table. No departure notes, no strikethroughs: git history is the narrative.

---

## The classes

| Class | Meaning | Count |
| --- | --- | --- |
| **§0 The pin** | Why the list does not collapse into "pin the latest version, minus exclusions". | 0 |
| **§1 Defects** | The register requires something the profile does not carry, or the profile names a hole it can now close. The profile is defective until these land. | 0 |
| **§2 Corrections** | Arguments the profile makes that a change upstream has made imprecise. The conclusions stand; the arguments need restating. | 0 |
| **§3 Statements** | Cheap clauses the profile should add because silence has stopped being neutral, a standards line having now made the opposite statement explicit. | 0 |
| **§4 Decisions** | Genuine open questions the freeze must answer. Grouped into clusters, because several are one question wearing different hats. | 0 |
| **§5 Confirmations** | Free confirmations, collected so a later reader does not mistake one for drift. | 0 |
| **§6 Watch** | External lines with no obligation attached, tracked because they bear on a decision the profile has taken. | 4 |

*The matrix's own §11 summary tallies these differently, and lower. It counts by matrix **row**; this counts by **edit**.*

---

## 0. Why this is a list and not a pin

*The first question at the review gate will be whether the whole list collapses into "pin the latest upstream version, minus the exclusions." It does not, and the reason is worth writing down once rather than re-deriving.*

**The pin already exists and has already done most of the collapsing.** R-15-007 makes the format a re-parameterization of `sail-cheri-riscv`, whose capability functions *are* the ISAv8/v9 CHERI-RISC-V ones, and R-15-007a inherits the monotonicity, provenance, and non-forgeability results from it; R-15-007j states the pin's residual reach outright, so where the profile is silent on *behaviour*, ISAv9 governs. That is the matrix's ⚙️ class, carried whether or not the profile names it, and at roughly thirty rows it is the largest class in the document. **This list is by construction the residue the pin does not reach.**

**"The latest" can only mean ISAv9.** Pinning to RVY is not on the menu: R-15-007 and R-17-048a retire that re-pin outright, and a 36-bit address with 8/6-bit mantissas falls outside anything RVY will ratify. ISAv9 is already the pin.

### Why the residue survives a pin

- **The format is the deviation.** Anything touching the bit budget has no upstream answer to inherit, because upstream's answer assumes upstream's bits. The revocation colour needs a field in a format that spends all 64; RVY mandates 4 SDP bits the profile cannot represent; seal/unseal separability is a question only a *lattice* has to answer, and upstream has independent bits so it never had to; the reachable malformed-bounds set at 8/6 mantissas differs from RV64LYA's. **Pinning here imports requirements that are unsatisfiable, which is worse than silence.**
- **Upstream's realization uses a mechanism the profile deleted.** ISAv8 and RVY both realize the load barrier as per-page PTE bits. Inheriting the *statement* buys nothing with no MMU to hang it on: the profile owes the other realization, and no pin writes it.
- **"The latest" is three lineages that disagree.** The per-load tag check is architectural in CHERIoT and deliberately implementation-defined in RVY (`Svucrglct` dropped). Compressed permissions shipped in CHERIoT and were reverted in RVY. The sentry split is in CHERIoT and is a *future* CT value in RVY. Choosing which line wins per feature **is** the item-by-item work.
- **Some questions are created by this platform's deletions and have no upstream answer at all.** ISAv9 deleted `CClearRegs` because a merged file made it meaningless, but the switcher still clears registers on every cross-compartment call, on a machine with no `C` extension. The pin hands over upstream's deletion, which is the wrong answer here for a reason upstream never had. `CMOVN`/`CMOVZ` has the same shape: `Zicond` suffices upstream because upstream has a dynamic predictor.

### Where a blanket pin actively backfires

*What backfires is the **membership** half, which is exactly the half R-15-007j does not carry: it governs the behaviour of constructs the profile already carries and admits nothing. Both objections below are objections to widening it.*

**On the refusals.** A membership-inheriting clause imports ISAv9's CHERI enable bit, which the profile refuses by name in two places: no enable bit exists (§5.2) and no runtime CHERI disable exists (§1). Both are refusals of upstream features, and inheritance-by-default argues the other way, so widening the pin would put it at odds with clauses the profile carries.

**On the admission discipline, which is the deeper conflict.** Several instructions the profile decides **already exist in ISAv8/v9**, and a blanket pin decides every one of them at a stroke, in the *include* direction: `CLoadTags`, `CClearTags`, `CTestSubset`, and the conditional capability move. That batch decision is genuinely available, and it is the strongest case for the pin. It is nonetheless declined:

> §5's CSR table is **closed**, §6 enumerates exclusions **by name**, and R-15-014 traps unallocated encodings. The profile is **closed-by-default with opt-in admission and a stated ground per instruction.** "Everything ISAv9 has, minus exclusions" is open-by-default, and imports silicon, encoding space, and Sail cases that nothing has priced against the emitted mix.

The conflict is architectural rather than stylistic: adopting it trades a curated profile for a subtractive one, and the *unallocated encodings trap* property is downstream of that choice. The decisions themselves are the discipline's evidence, and the pin gets two of the four wrong: `CLoadTags` is admitted on the sweep's own quantum and `CTestSubset` declined on where the domain boundary validates, the conditional move admitted on an idiom `Zicond` has no capability form of and `CClearTags` declined on a write path that already clears tags. **Each is admitted on a measured ground or declined on a stated one.**

---

## 1. Defects

*The register requires it and the profile does not carry it. These are not preferences.*

---

## 2. Corrections

*An upstream change has made the argument imprecise. In every case the conclusion stands and the argument needs restating; do not reopen the decision.*

---

## 3. Statements to add

*Each is one or two clauses. Each is needed because a standards line has now made the opposite statement explicit, so silence has stopped being neutral.*

---

## 4. Decisions the freeze must make

*Grouped, because several of these are one question wearing different hats and deciding them separately is how a format acquires an inconsistency. Which freeze, of the two R-15-014a names: an item conditioned on a measurement against generated output falls to the **final** freeze, and every other one to the **provisional** freeze, which is day-one work and not work that waits on a backend.*

---

## 5. Free confirmations to collect

*Two convergences are already recorded correctly and need no work: **physical-address capabilities** (ISAv7 experimental appendix → ISAv9 model section, and this platform's entire address model) and the **64-bit Concentrate format** (the literal base of the frozen format). A third, compressed non-orthogonal permissions, is **not** a convergence (RVY attempted a compressed AP encoding at v0.9.9 and reverted), and R-15-007b's rationale now records CHERIoT's 6-bit encoding as the sole shipped precedent.*

---

## 6. Watch

*No obligation attached. Tracked because each bears on a decision the profile has already taken, or because a release would rerun the review gate.*

- [ ] **`ZcheriSanitary`**: cleaning capabilities on compartment switch. *Research, needs a PR.* **The one to watch**, and the profile's **recorded re-pin target** for `cclear` (R-15-069b) rather than a question beside it: if it ratifies, the obligation opens on a frozen encoding, which is the one watch row here that would touch §3 rather than only rerun the gate.
- [ ] **`ZcheriTraceTag`**: data capability trace with tags. *Research, needs a PR.* Irrelevant in production (trace rides the lifecycle fuse, R-15-079) but relevant in the **development** lifecycle state, where §10 permits trace and R-15-077 points development measurement at it.
- [ ] **ISAv10.** `app-versions-10-0.tex` on `main` still reads `TBD`. Nothing to track yet; a published Cambridge release is an **amendment that reruns the review gate (R-18-034)**, not a drift.
- [ ] **RVY toward v1.0 ratification.** Stable at v0.9.9 with limited change expected. Not an obligation (R-15-007 and R-17-048a retire the re-pin), but `Zylevels1` was **postponed out of the v1.0 package** at v0.9.8, and the profile adopts it (R-15-074), so the standard is behind the profile on that row rather than ahead.

---

## Where the work lands

**One item has no landing row and should get one at the freeze:** the profile places four bespoke instructions (the capability indexed load/store, `bfext`/`bfins`, and `cclear`) in "custom opcode space". At v0.9.8 **RVY relocated its own instructions into what is Custom-3 for RVI and reserved Custom1–3 wholesale** when the base ISA is RVY. There is **no defect today**, since the profile is not RVY-based. But it forecloses the encoding-level rapprochement that §11's parameterized-encoding-format argument would otherwise leave open, so **the encoding should be chosen knowing the standards line has claimed the same real estate** (R-15-007e, R-15-067a, R-15-069a, R-15-014; matrix §9.2).
