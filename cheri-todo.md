# CHERI Profile TODO

*Non-normative. The work list distilled from [cheri-version-matrix.md](cheri-version-matrix.md), which is itself a reading of [requirements-register.md](requirements-register.md) and [isa-profile.md](isa-profile.md). Where this document and the register disagree, **the register wins and this document is defective**. Nothing here amends the frozen profile: this is the agenda the review gate (R-18-034) works through, not a set of decisions already taken.*

*Every item carries the matrix row it came from, the requirements that govern it, and the place in [isa-profile.md](isa-profile.md) where the change lands. Items are ordered by class, not by size: a one-line statement that closes a named hole outranks a design question that would take a quarter to settle.*

**Convention.** When an item lands normatively, delete the bullet and its row in the landing table. No departure notes, no strikethroughs — git history is the narrative.

---

## The classes

| Class | Meaning | Count |
| --- | --- | --- |
| **§0 The pin** | Why the list does not collapse into "pin the latest version, minus exclusions". | 0 |
| **§1 Defects** | The register requires something the profile does not carry, or the profile names a hole it can now close. The profile is defective until these land. | 0 |
| **§2 Corrections** | Arguments the profile makes that a change upstream has made imprecise. The conclusions stand; the arguments need restating. | 0 |
| **§3 Statements** | Cheap clauses the profile should add because silence has stopped being neutral — a standards line has now made the opposite statement explicit. | 0 |
| **§4 Decisions** | Genuine open questions the freeze must answer. Grouped into clusters, because several are one question wearing different hats. | 6 in 5 clusters |
| **§5 Records** | Deliberate divergences and free confirmations, recorded so a later reader does not mistake either for drift. | 6 + 2 |
| **§6 Watch** | External lines with no obligation attached, tracked because they aim at questions §4 leaves open. | 4 |

*The matrix's own §11 summary tallies these differently, and lower. It counts by matrix **row**; this counts by **edit**.*

---

## 0. Why this is a list and not a pin

*The first question at the review gate will be whether the whole list collapses into "pin the latest upstream version, minus the exclusions." It does not, and the reason is worth writing down once rather than re-deriving.*

**The pin already exists and has already done most of the collapsing.** R-15-007 makes the format a re-parameterization of `sail-cheri-riscv`, whose capability functions *are* the ISAv8/v9 CHERI-RISC-V ones, and R-15-007a inherits the monotonicity, provenance, and non-forgeability results from it; R-15-007j states the pin's residual reach outright, so where the profile is silent on *behaviour*, ISAv9 governs. That is the matrix's ⚙️ class — carried whether or not the profile names it — and at roughly thirty rows it is the largest class in the document. **This list is by construction the residue the pin does not reach.**

**"The latest" can only mean ISAv9.** Pinning to RVY is not on the menu: R-15-007 and R-17-048a retire that re-pin outright, and a 36-bit address with 8/6-bit mantissas falls outside anything RVY will ratify. ISAv9 is already the pin.

### Why the residue survives a pin

- **The format is the deviation.** Anything touching the bit budget has no upstream answer to inherit, because upstream's answer assumes upstream's bits. The revocation colour needs a field in a format that spends all 64; RVY mandates 4 SDP bits the profile cannot represent; seal/unseal separability is a question only a *lattice* has to answer, and upstream has independent bits so it never had to; the reachable malformed-bounds set at 8/6 mantissas differs from RV64LYA's. **Pinning here imports requirements that are unsatisfiable, which is worse than silence.**
- **Upstream's realization uses a mechanism the profile deleted.** ISAv8 and RVY both realize the load barrier as per-page PTE bits. Inheriting the *statement* buys nothing with no MMU to hang it on — the profile owes the other realization, and no pin writes it.
- **"The latest" is three lineages that disagree.** The per-load tag check is architectural in CHERIoT and deliberately implementation-defined in RVY (`Svucrglct` dropped). Compressed permissions shipped in CHERIoT and were reverted in RVY. The sentry split is in CHERIoT and is a *future* CT value in RVY. Choosing which line wins per feature **is** the item-by-item work.
- **Some questions are created by this platform's deletions and have no upstream answer at all.** ISAv9 deleted `CClearRegs` because a merged file made it meaningless — but the switcher still clears registers on every cross-compartment call, on a machine with no `C` extension. The pin hands over upstream's deletion, which is the wrong answer here for a reason upstream never had. `CMOVN`/`CMOVZ` has the same shape: `Zicond` suffices upstream because upstream has a dynamic predictor.

### Where a blanket pin actively backfires

*What backfires is the **membership** half, which is exactly the half R-15-007j does not carry: it governs the behaviour of constructs the profile already carries and admits nothing. Both objections below are objections to widening it.*

**On the refusals.** A membership-inheriting clause imports ISAv9's CHERI enable bit, which the profile refuses by name in two places: no enable bit exists (§5.2) and no runtime CHERI disable exists (§1). Both are refusals of upstream features, and inheritance-by-default argues the other way, so widening the pin would put it at odds with clauses the profile carries.

**On the admission discipline, which is the deeper conflict.** Four decision items — `CLoadTags`, `CClearTags` (4A), `CMOVN`/`CMOVZ` (4B), `CTestSubset` (4D) — are instructions that **already exist in ISAv8/v9**. A blanket pin decides every one of them at a stroke, in the *include* direction. That batch decision is genuinely available, and it is the strongest case for the pin. It is nonetheless declined:

> §5's CSR table is **closed**, §6 enumerates exclusions **by name**, and R-15-014 traps unallocated encodings. The profile is **closed-by-default with opt-in admission and a stated ground per instruction.** "Everything ISAv9 has, minus exclusions" is open-by-default, and imports four instructions' worth of silicon, encoding space, and Sail cases that nothing has priced against the emitted mix.

The conflict is architectural rather than stylistic: adopting it trades a curated profile for a subtractive one, and the *unallocated encodings trap* property is downstream of that choice. **The four stay individual, and each is admitted on a measured ground or declined on a stated one.**

---

## 1. Defects

*The register requires it and the profile does not carry it. These are not preferences.*

---

## 2. Corrections

*An upstream change has made the argument imprecise. In every case the conclusion stands and the argument needs restating — do not reopen the decision.*

---

## 3. Statements to add

*Each is one or two clauses. Each is needed because a standards line has now made the opposite statement explicit, so silence has stopped being neutral.*

---

## 4. Decisions the freeze must make

*Grouped, because several of these are one question wearing different hats and deciding them separately is how a format acquires an inconsistency.*

*Which freeze, of the two R-15-014a names: an item conditioned on a measurement against generated output falls to the **final** freeze, and every other item here to the **provisional** one. No item below is so conditioned, so this section is day-one work in its entirety and not work that waits on a backend.*

### 4A. Sweep support

- [ ] **`CLoadTags`.** *R-08-007, R-15-203 · Matrix §5, §6 (marked **yes** in both).*
  The §8 sweep is an incremental software task whose completion latency is "the domain's capability-bearing footprint over the per-frame sweep quantum" — i.e. **entirely a memory-traffic quantity**. `CLoadTags` reads a granule group's tags without reading the data, and with native SRAM tag bits read in parallel with data (R-15-203) it is close to free in silicon. **Mature since ISAv8, so the "experimental" objection is gone. Nothing in the profile carries it and no requirement declines it** — the strongest lean in this section.
- [ ] **`CClearTags`.** *R-15-182, R-08-007 · Matrix §6.*
  Partly covered already: `cbo.zero` allocates whole lines with zeroed data *and* cleared tags at one fixed latency (R-15-182). The residue is **tag-only clearing where data must survive** — a sweep-side want, not a zeroize-side one. Decide with `CLoadTags`.

### 4B. A capability conditional move

- [ ] **`CMOVN`/`CMOVZ`.** *R-15-054, R-15-019, R-15-023 · Matrix §4.*
  The one obviated-looking row that is not obviated. `Zicond` is adopted **precisely because** branchless select is doubly load-bearing under static-only prediction with a full mispredict penalty on every forward conditional — but `czero.eqz`/`czero.nez` selects an *integer*, and on a purecap machine the selected value is frequently a **capability**. Either a capability-aware conditional move exists, or every conditional pointer select pays a mispredict-equivalent penalty and **breaks the constant-time story R-15-054 was bought to protect**. The argument is stronger here than the one ISAv6 made upstream, because the fallback is a branch this profile has deliberately made expensive.

### 4C. The trap-path residue

*R-15-073a fixes where a capability exception reports; this is what it leaves open. §5's table is closed, so silence is a decision rather than an omission.*

- [ ] **`ErrorEPCC` — a trap taken inside the handler.** *R-07-022, §5.3 · Matrix §5.*
  Modeled on MIPS `ErrorEPC` and not carried into RISC-V, where the equivalent question is what happens to a fault inside a fault handler. Low cost; §5.3 is the right place to settle it.

### 4D. Argument validation at a domain boundary

- [ ] **`CTestSubset` / RVY `YSS`.** *R-07-031a · Matrix §5, §9.2.*
  Upstream's first consumer is a garbage collector, which this platform has not got. **Its second consumer is argument validation at a domain boundary, which this platform has**: the switcher checks delegated buffers on every cross-compartment call. RVY **promoted it out of the experimental appendix into the base ISA**, which weakens the "no consumer" reading considerably.

### 4E. Vector checking versus mask independence

- [ ] **State the composition of "only active elements are subject to CHERI checks" with R-15-085.** *R-15-115, R-15-085 · §8/§9 · Matrix §9.2.*
  R-15-085's mask-independence contract **forbids skipping cycles or memory accesses for masked-off elements**. RVY checks only active elements. The two are compatible — *check everything, fault only on active elements* — but one is a security contract and the other a timing one, and the composition should be **stated rather than left to a reader to reconcile**.

---

## 5. Records to add

### 5A. Deliberate divergences — so a later reader does not read them as drift

- [ ] **4-bit object type against RVY's 1-bit CT field.** *R-15-007, R-07-002b · Matrix §9.2.* A divergence in both directions, and the profile is not behind: RVY's base keeps one sealing bit where the profile keeps four otype bits.
- [ ] **The forward/backward sentry split is ahead of RVY's base, not adrift from it.** *R-15-071 · Matrix §9.2.* CHERIoT 1.0 added it for exactly the profile's reason; RVY lists it as a *future* CT value and has **reserved encoding room** — `YSENTRY`'s `rs1` is held for a future `YSEAL` taking an authorizing capability.
- [ ] **`YBLD` is base functionality upstream and forbidden at the root here.** *R-05-136 · Matrix §4, §9.2.* No reconstruction of a capability from its bit pattern, ever; the upstream use cases (swap, VM migration, runtime linking) are each independently absent.
- [ ] **Pointer masking**, which RVY integrates for RVA23 compatibility and R-15-043 deletes. *R-15-043 · Matrix §9.2.* The divergence is **entirely a profile-compatibility artifact** — RVY must coexist with a ratified application profile; this platform curates its own.
- [ ] **The per-load tag check is architectural here and implementation-defined upstream.** *R-08-005 · Matrix §9.2 `Svucrglct`.* RVY **dropped** `Svucrglct` on the ground that software must assume the check might not happen, so naming it buys nothing. The profile cannot take that position: R-08-005 makes the check architectural and fixed-latency **because containment latency is a proof obligation and a §11 schedule term**. Same mechanism, opposite conclusion, and the profile's reason is specific to it.
- [ ] **Also record what §10 is actually refusing.** *R-15-078, R-15-079 · §10 · Matrix §9.2.* RVY spends real effort making a debugger work against capability state — CHERI mode on debug entry, `dpcc`, `drootcsel`, capability-width abstract commands. The profile's answer is orthogonal and stronger: the Debug Module is **lifecycle-fused in hardware**, clock and reset gated off in production. §10 states the fuse without stating that **the capability-debug surface is what the fuse is refusing** — worth one clause, so the profile does not read as merely *missing* the debug work.

### 5B. Free confirmations to collect

- [ ] **`Zcd`, `Zcmp`, and `Zcmt` are incompatible with any purecap RV64 CHERI machine.** *R-15-036, R-15-036a · §6 · Matrix §9.2.*
  Purecap needs the 16-bit load/store encoding space for `C.LY`/`C.SY`, so the **code-size half of the `Zc*` family — push/pop multiple and table jump — was never on offer**, standards-track or not. The profile's `C` exclusion therefore forgoes less than a naive reading suggests: two of the three code-size instruments were unavailable regardless. It also removes a hypothetical objection, since `Zcmt`'s jump-vector table is a target-membership structure that would sit awkwardly beside sentry CFI and R-15-072's typed callee set anyway.
- [ ] **`Zicfiss` is incompatible with CHERI** — its push/pop instructions would need modifying. *R-15-044 · §6 · Matrix §9.2.*
  RVY reaches R-15-044's conclusion **from the encoding side rather than the principle side**. Collect it: two independent grounds for one exclusion.

*Two convergences are already recorded correctly and need no work — **physical-address capabilities** (ISAv7 experimental appendix → ISAv9 model section, and this platform's entire address model) and the **64-bit Concentrate format** (the literal base of the frozen format). A third, compressed non-orthogonal permissions, is **not** a convergence — RVY attempted a compressed AP encoding at v0.9.9 and reverted — and R-15-007b's rationale now records CHERIoT's 6-bit encoding as the sole shipped precedent.*

---

## 6. Watch

*No obligation attached. Tracked because each aims at a question §4 leaves open, or because a release would rerun the review gate.*

- [ ] **`ZcheriSanitary`** — cleaning capabilities on compartment switch. *Research, needs a PR.* **The one to watch**, and the profile's **recorded re-pin target** for `cclear` (R-15-069b) rather than a question beside it: if it ratifies, the obligation opens on a frozen encoding, which is the one watch row here that would touch §3 rather than only rerun the gate.
- [ ] **`ZcheriTraceTag`** — data capability trace with tags. *Research, needs a PR.* Irrelevant in production (trace rides the lifecycle fuse, R-15-079) but relevant in the **development** lifecycle state, where §10 permits trace and R-15-077 points development measurement at it.
- [ ] **ISAv10.** `app-versions-10-0.tex` on `main` still reads `TBD`. Nothing to track yet; a published Cambridge release is an **amendment that reruns the review gate (R-18-034)**, not a drift.
- [ ] **RVY toward v1.0 ratification.** Stable at v0.9.9 with limited change expected. Not an obligation — R-15-007 and R-17-048a retire the re-pin — but `Zylevels1` was **postponed out of the v1.0 package** at v0.9.8, and the profile adopts it (R-15-074), so the standard is behind the profile on that row rather than ahead.

---

## Where the work lands

*Several findings collapse into one edit. This is the grouping to work in, not the order above.*

| Profile section | Items | Class |
| --- | --- | --- |
| §5.1 / §5.3 CSR bank | `ErrorEPCC` | 4C |
| §6 Exclusions | `Zcd`/`Zcmp`/`Zcmt` and `Zicfiss` confirmations; divergence records | confirmations, 5A |
| §8 Core classes | active-element ⋈ mask-independence | 4E |
| §10 Debug | what the fuse is refusing | 5A |

**One item has no landing row and should get one at the freeze:** the profile places four bespoke instructions — the capability indexed load/store, `bfext`/`bfins`, and `cclear` — in "custom opcode space". At v0.9.8 **RVY relocated its own instructions into what is Custom-3 for RVI and reserved Custom1–3 wholesale** when the base ISA is RVY. There is **no defect today**, since the profile is not RVY-based. But it forecloses the encoding-level rapprochement that §11's parameterized-encoding-format argument would otherwise leave open, so **the encoding should be chosen knowing the standards line has claimed the same real estate** (R-15-007e, R-15-067a, R-15-069a, R-15-014; matrix §9.2).
