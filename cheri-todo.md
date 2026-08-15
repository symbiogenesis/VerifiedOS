# CHERI Profile TODO

*Non-normative. The work list distilled from [cheri-version-matrix.md](cheri-version-matrix.md), which is itself a reading of [requirements-register.md](requirements-register.md) and [isa-profile.md](isa-profile.md). Where this document and the register disagree, **the register wins and this document is defective**. Nothing here amends the frozen profile: this is the agenda the review gate (R-18-034) works through, not a set of decisions already taken.*

*Every item carries the matrix row it came from, the requirements that govern it, and the place in [isa-profile.md](isa-profile.md) where the change lands. Items are ordered by class, not by size: a one-line statement that closes a named hole outranks a design question that would take a quarter to settle.*

**Convention.** When an item lands normatively, delete the bullet and its row in the landing table. No departure notes, no strikethroughs — git history is the narrative.

---

## The classes

| Class | Meaning | Count |
| --- | --- | --- |
| **§0 The pin** | Why the list does not collapse into "pin the latest version, minus exclusions" — and the one clause that collapses six of it. | 1 |
| **§1 Defects** | The register requires something the profile does not carry, or the profile names a hole it can now close. The profile is defective until these land. | 4 |
| **§2 Corrections** | Claims the profile makes that were true when written and are now imprecise. The conclusions stand; the arguments need restating. | 4 |
| **§3 Statements** | Cheap clauses the profile should add because silence has stopped being neutral — a standards line has now made the opposite statement explicit. | 5 |
| **§4 Decisions** | Genuine open questions the freeze must answer. Grouped into clusters, because several are one question wearing different hats. | 19 in 9 clusters |
| **§5 Records** | Deliberate divergences and free confirmations, recorded so a later reader does not mistake either for drift. | 7 + 2 |
| **§6 Watch** | External lines with no obligation attached, tracked because they aim at questions §4 leaves open. | 4 |

*The matrix's own §11 summary tallies these differently, and lower. It counts by matrix **row**; this counts by **edit**. Three rows the matrix files as decisions (the `menvcfg` explicitness, the vector store's tag clearing, the zeroed-granule NULL) resolve to a clause the profile owes either way, so they sit in §3 here.*

---

## 0. Why this is a list and not a pin

*The first question at the review gate will be whether the whole list collapses into "pin the latest upstream version, minus the exclusions." It does not, and the reason is worth writing down once rather than re-deriving.*

**The pin already exists and has already done most of the collapsing.** R-15-007 makes the format a re-parameterization of `sail-cheri-riscv`, whose capability functions *are* the ISAv8/v9 CHERI-RISC-V ones, and R-15-007a inherits the monotonicity, provenance, and non-forgeability results from it. That is the matrix's ⚙️ class — carried whether or not the profile names it — and at roughly thirty rows it is the largest class in the document. **This list is by construction the residue the pin does not reach.**

**"The latest" can only mean ISAv9.** Pinning to RVY is not on the menu: R-15-007 and R-17-048a retire that re-pin outright, and a 36-bit address with 8/6-bit mantissas falls outside anything RVY will ratify. ISAv9 is already the pin.

### Why the residue survives a pin

- **The format is the deviation.** Anything touching the bit budget has no upstream answer to inherit, because upstream's answer assumes upstream's bits. The revocation colour needs a field in a format that spends all 64; RVY mandates 4 SDP bits the profile cannot represent; seal/unseal separability is a question only a *lattice* has to answer, and upstream has independent bits so it never had to; the reachable malformed-bounds set at 8/6 mantissas differs from RV64LYA's. **Pinning here imports requirements that are unsatisfiable, which is worse than silence.**
- **Upstream's realization uses a mechanism the profile deleted.** ISAv8 and RVY both realize the load barrier as per-page PTE bits. Inheriting the *statement* buys nothing with no MMU to hang it on — the profile owes the other realization, and no pin writes it.
- **"The latest" is three lineages that disagree.** The per-load tag check is architectural in CHERIoT and deliberately implementation-defined in RVY (`Svucrglct` dropped). Compressed permissions shipped in CHERIoT and were reverted in RVY. The sentry split is in CHERIoT and is a *future* CT value in RVY. Choosing which line wins per feature **is** the item-by-item work.
- **Some questions are created by this platform's deletions and have no upstream answer at all.** ISAv9 deleted `CClearRegs` because a merged file made it meaningless — but the switcher still clears registers on every cross-compartment call, on a machine with no `C` extension. The pin hands over upstream's deletion, which is the wrong answer here for a reason upstream never had. `CMOVN`/`CMOVZ` has the same shape: `Zicond` suffices upstream because upstream has a dynamic predictor.
- **Four items are prose corrections about the standards landscape** (§2). No pin restates an argument.

### What a tighter pin *would* collapse

- [ ] **Add a residual-semantics clause to R-15-007.** *R-15-007, R-15-007a · Lands:* §4.1 or §11
  Of the form: *where this profile is silent, ISAv9 semantics govern, and the deviation list is exhaustive.* Cheap, and the highest-leverage single edit on this list — it closes six items outright:

  | Item | Carried by the clause? |
  | --- | --- |
  | Tag-clearing vs. trapping (defect 4) | fully |
  | Merged register file (defect 5) | fully |
  | Zeroed granule decodes as NULL (§3) | fully |
  | Sentry unseal on `mret` (4F) | fully |
  | Unaligned-base cause encoding (4F) | fully |
  | `xtval` (defect 3) | **semantics only** — §5's table is closed, so the row must still be written |

### Where a blanket pin actively backfires

**On the refusals.** A default-inherit clause imports ISAv9's CHERI enable bit, which is precisely what R-15-049 deletes and R-15-052 refuses. The `menvcfg` statement and "no runtime CHERI disable" (§3) get *harder* to state under a pin, not easier — they are refusals of upstream features, and inheritance-by-default argues the other way.

**On the admission discipline, which is the deeper conflict.** Six decision items — `CRAM`/`CRRL`, `CSetBoundsExact` (4B), `CLoadTags`, `CClearTags` (4D), `CMOVN`/`CMOVZ` (4E), `CTestSubset` (4G) — are instructions that **already exist in ISAv8/v9**. A blanket pin decides every one of them at a stroke, in the *include* direction. That batch decision is genuinely available, and it is the strongest case for the pin. It is nonetheless declined:

> §5's CSR table is **closed**, §6 enumerates exclusions **by name**, and R-15-014 traps unallocated encodings. The profile is **closed-by-default with opt-in admission and a stated ground per instruction.** "Everything ISAv9 has, minus exclusions" is open-by-default, and imports six instructions' worth of silicon, encoding space, and Sail cases that nothing has priced against the emitted mix.

The conflict is architectural rather than stylistic: adopting it trades a curated profile for a subtractive one, and the *unallocated encodings trap* property is downstream of that choice. **The six stay individual, and each is admitted on a measured ground or declined on a stated one.**

---

## 1. Defects

*The register requires it and the profile does not carry it. These are not preferences.*

- [ ] **The revocation colour has no bits.**
  *Governing:* R-08-004, R-08-004a · *Lands:* §4.1 (capability format) · *Matrix:* §6
  R-08-004a stamps a colour at derivation and retires colours as a set, which is what buys subtree revocation with no derivation tree. §4.1's field table spends all 64 bits: 36 + 4 + 5 + 5 + 8 + 6 = 64, with the tag outside. **It cannot be both required and unrepresentable.** Exactly one of these must land:
  - the colour is *not* capability metadata, living instead in the filter's shadow structure keyed by address — in which case R-08-004a's explicit preference for **ancestry** keying over address keying must be re-argued, not quietly dropped; or
  - a field is found, which at this width means taking bits from the object type or a mantissa, and the cost lands on R-15-007c's exactness threshold or R-07-002b's otype set.

- [ ] **Close `mcause`/`mtval` with `xtval`.**
  *Governing:* §5.3, R-07-022, R-15-073 · *Lands:* §5.3 → §5.1 · *Matrix:* §1, §6, §7, §9.2 `Xtval2`
  §5.3 books this as an extraction defect: the trap path is specified in capability terms (`MTCC` installed, `MEPCC` saved, authority from `MTDC`) but no requirement names a cause register, a trap-value register, or the CHERI cause encoding. **ISAv8 settled it and ISAv9 and RVY both keep it:** capability exceptions report through the existing trap-value CSR, not a bespoke cause register. It is also the cheaper answer — reuse `mtval` rather than add a bank. RVY's `Xtval2` confirms the shape from the other side: one trap-value register is where CHERI exception detail belongs.
  Adopting it settles the profile's own named hole and **takes three §4 decision rows with it** — see cluster **4F**.

- [ ] **State the tag-clearing-versus-trapping discipline.**
  *Governing:* R-15-007, R-15-007e · *Lands:* §4.1 or §4 · *Matrix:* §7
  ISAv9 adopted Morello's rule: non-monotonic modification **clears the tag** rather than raising an exception. The profile inherits "instruction semantics unchanged" without saying which side it lands on, and the two are not equivalent here — trapping makes every failed derivation a control-flow event with a WCET term and a cause encoding; tag clearing makes it a silent data result that faults later at dereference. R-15-007e already reasons about `cincoffset` producing an out-of-representable-region result, **which only coheres on the tag-clearing side**. The profile is already committed; it should say so.

- [ ] **State the merged register file.**
  *Governing:* R-07-015, R-15-214 · *Lands:* §1 (Base) · *Matrix:* §7
  ISAv9 made the merged file normative for all CHERI architectures and the profile never states it. Not cosmetic: R-07-015 and R-15-214 make the partition-switch restore total over "every general-purpose register, **capability register**, and CSR a partition can name" — phrasing that reads as an enumeration over *two* files. On a merged file the restore set is **one file of 32 × (64+1) bits**, and that is the set the totality obligation quantifies over — which is in turn why the register files are not in the `fence.t` flush set. One row in §1.

---

## 2. Corrections

*True when written, imprecise now. In every case the conclusion stands and the argument needs restating — do not reopen the decision.*

- [ ] **"No re-pin target" for the capability indexed load/store overstates it.**
  *Governing:* R-15-007e, R-15-067d · *Lands:* §3 (custom and fork-and-frozen instructions) · *Matrix:* §9.2 `YSH1ADD`
  §3 records the capability indexed load/store as having **"none: bespoke with the dialect"** for a re-pin target. RVY places capability shift-and-add (`YSH1ADD`…`YSH4ADD`) in `Zba`, **an extension this profile adopts**. It is genuinely a different instruction — it materializes the intermediate capability, which is exactly what R-15-007f's admissibility argument turns on avoiding — but it covers the address-formation half, so "none exists" is too strong.

- [ ] **R-17-048a's cost estimate is now optimistic; restate it in two terms.**
  *Governing:* R-17-048a · *Lands:* §11 (freeze and re-pin obligations), and R-17-048a itself · *Matrix:* §9.2, last row
  R-17-048a books the retired re-pin as differential-testing oracles "degrading in proportion to the parameterization rather than all at once". That was measured against a CHERI-RISC-V sharing mnemonics, encodings, and CSR names with `sail-cheri-riscv`. Since then RVY has **renamed every instruction** to the `Y*` space, **relocated its whole encoding space into Custom-3**, moved sealing to a CT field, restructured the CSRs, and renamed the format to RV64LYA. So:
  - **algebraic** oracles (bounds encode/decode, monotonicity) still degrade in proportion — unchanged;
  - **instruction-level** oracles (Spike, QEMU, the CHERI test suites) now degrade closer to all at once.
  The conclusion stands. The estimate should carry both terms rather than one.

- [ ] **"Permanently bespoke" was a true dichotomy and is not one now.**
  *Governing:* R-15-007, R-17-048a · *Lands:* §11 · *Matrix:* §9.2, alternative encoding formats
  RVY separates the base ISA (`RV64Y`) from a **parameterized capability encoding format** (`RV64LYA`, parameterized by mantissa width, exponent width, max exponent), with an `_L<params>` naming scheme added at v0.9.6.1, and states that *"every RVY base ISA requires a capability encoding format to complete the specification."* The profile's 64+1-bit format is exactly a different parameterization of that slot. **This does not reopen R-15-007** — 36-bit addresses and 8/6-bit mantissas fall outside anything RVY will ratify — but the retirement argument should engage with the mechanism rather than with a fork/adopt binary the standard no longer presents.

- [ ] **Re-word R-15-007b's supporting evidence: RVY is not a convergence.**
  *Governing:* R-15-007b · *Lands:* R-15-007b's rationale · *Matrix:* §9.2 AP field, §11
  An earlier reading treated compressed non-orthogonal permissions as a two-line convergence. It is not. RV64LYA spends **8 bits one-bit-per-permission** plus a P-bit, reserving the illegal combinations (90 valid of 512), and the release history shows a compressed AP encoding was **attempted at v0.9.9 and reverted**. What survives is a note that future encoding formats *may* compress — an invitation, not a precedent. **CHERIoT's 6-bit encoding of 12 permissions is the sole shipped precedent**, and it is a good one. R-15-007b remains sound and is still the right choice at 64 bits; the rationale should lean on CHERIoT alone and record that RVY looked down this road and did not take it.

---

## 3. Statements to add

*Each is one or two clauses. Each is needed because a standards line has now made the opposite statement explicit, so silence has stopped being neutral.*

- [ ] **A zeroed granule decodes as untagged NULL.**
  *Governing:* R-15-182, R-15-060 · *Lands:* §4.1 · *Matrix:* §1
  Load-bearing here rather than merely conventional: `cbo.zero` writes zeroed data *and* cleared tags (R-15-182), and eager zeroize is the platform's Write-before-Read mechanism. "All-zeroes, untagged, decodes as NULL" is therefore a property the **format must state**, not one a reader should assume. One line.

- [ ] **No runtime CHERI disable.**
  *Governing:* R-15-052 · *Lands:* §1 or §6 (exclusions) · *Matrix:* §9.2 `misa.Y`
  RVY's `misa.Y` now resets to 1, and **clearing it disables CHERI entirely** — gated only by a check that `pc`, `xtvec`, and `xepc` hold root capabilities. R-15-052's read-only `misa` already refuses this, but on a machine whose entire protection story is CHERI, "no runtime ISA morphing" and "no runtime CHERI disable" are the same sentence and only one of them is written.

- [ ] **The load instruction must permit revocation-driven tag clearing.**
  *Governing:* R-08-005, R-15-007 · *Lands:* §4 · *Matrix:* §9.2 `Svyrg`
  RVY amended `LY`'s definition at v0.9.6.1 to allow exactly this. It is the architectural clause the profile's load filter needs and does not have — **the same one-line fix as defect 1, seen from the instruction side rather than the mechanism side**, and it should land in the same edit.

- [ ] **A vector store clears the capability tag of every granule it overwrites.**
  *Governing:* R-15-115 · *Lands:* §8 (core classes), beside the existing "vector data carries no tags" clause · *Matrix:* §9.2
  R-15-115 says vector data carries no tags; it does **not** say what a vector store does to the tag of the granule it overwrites. RVY answers: clear it. Without that clause, a vector store can be read as leaving a stale tag over overwritten data — **a forgery primitive**. One clause.

- [ ] **State that CHERI is unconditionally enabled and no enable bit exists.**
  *Governing:* §5.3, R-15-049 · *Lands:* §5.3 → §5.2 · *Matrix:* §7, §9.2
  ISAv9 and RVY both put a CHERI enable/disable bit in `menvcfg`/`senvcfg` (RVY moved its position twice during v0.9.9 review, so it is settled architecture rather than a placeholder). §5.3 indicates deleting `menvcfg` on R-15-049's ground — its bits gate a less-privileged mode that does not exist — and **that ground survives contact with the change**. But the conclusion now needs saying out loud, so a curator reading `menvcfg → deletion` does not silently delete the CHERI enable along with it. *Filed here rather than in §4 because the deletion ground is intact; only the explicitness is missing.*

---

## 4. Decisions the freeze must make

*Grouped, because several of these are one question wearing different hats and deciding them separately is how a format acquires an inconsistency.*

### 4A. The bit budget — decide as one, at the lattice enumeration

*The format has **zero** spare bits (36+4+5+5+8+6 = 64). Every row here spends the same currency, and defect 2's revocation colour competes for it too. This cluster cannot be decided piecewise.*

- [ ] **Software-defined permission bits.** *R-15-007b · §4.1 · Matrix §1, §9.2*
  The 5-bit lattice carries no SDP bits. **RVY mandates a 4-bit SDP field** for all encodings and gave it adjacent reserved space at v0.9.9; CHERIoT carries them. Ground for declining exists — a static task set, sealing over a fixed otype set — but **it is not stated**, and the lattice enumeration at freeze is where it must be settled.
- [ ] **Whether `Permit_Seal` and `Permit_Unseal` are separable.** *R-15-007b · §4.1 · Matrix §5*
  Not a free inheritance: the 5-bit lattice enumerates *which permission sets exist*, so separability is a decision the enumeration makes at freeze, and R-15-007b does not record it. Reducing unseal-only privilege is why upstream split them at 7.0-A1.
- [ ] **Malformed-capability integrity checks.** *R-15-007a · §4.1 · Matrix §9.2*
  RVY enforced integrity checks at v0.9.6.1 and split them into **mandatory and optional** sets at v0.9.9, alongside a "legal permissions invariant for tagged capabilities" at v0.9.2. Half is obviated here — there are no reserved bits to check, all 64 being spent — and half is not: **malformed bounds is a property of the bounds algorithm**, and at 8/6-bit mantissas the reachable malformed set differs from RV64LYA's. R-15-007a's representation-correctness proof is the natural home and should name it. The mandatory/optional split is itself instructive: RVY found some integrity checks must be architectural and some may be implementation choices, **which is the same question the profile faces on the load filter** (defect 1).

### 4B. Dynamic bounds narrowing — three answers to one question

*R-15-007c concedes that **dynamic subobject narrowing carries the representability case at runtime**, and at a 256-byte exactness threshold that rounding is coarse and frequent. Decide these together or not at all.*

- [ ] **`CRAM` / `CRRL`** — representable alignment mask and rounded length. *R-15-007c · Matrix §5, §6.* Mature at ISAv8. **RVY standardized `YAMASK` into the base ISA.**
- [ ] **`CSetBoundsExact`** and its exception code. *R-15-007c · Matrix §2.* Worth **more** here than upstream, not less: at an 8-bit base mantissa, "this narrowing was exact" is an assertion a dynamic subobject narrow actually needs.
- [ ] The alternative to both is a **software computation of the exponent** against `CRAM`-style rounding, whose cost lands on the same hot path. Price it before declining the instructions.

### 4C. Compartment-switch cost — the unpriced term

*At **partition** switch the profile is covered structurally: the restore is total over every register a partition can name (R-07-015, R-15-214), which is why the register files are not in the `fence.t` flush set. At **compartment** switch it is not — the switcher's software cost is unpriced in the profile, on a machine with no `C` extension and a hard code-size budget.*

- [ ] **Fast register-clearing instructions** (`CClearHi`/`CClearLo`/`CClearRegs`). *R-07-014, R-07-015, R-15-214 · Matrix §2.*
  The switcher clears registers on **every** cross-compartment call. ISAv9 deleted `Clear` only because the merged register file made the split-file variant meaningless — **not because the need went away**.
- [ ] **`mshwm`/`mshwmb` stack high-water-mark CSRs** (CHERIoT). *§5, R-07-014 · Matrix §10.*
  The mechanism exists so a switch zeroizes only the stack actually used. The profile zeroizes eagerly and pays for it, and **§5's CSR table is closed**, so these are absent *by construction rather than by decision*. If the compartment-switch zeroize cost is material at §11, this is the cheap lever; if it is not, the row should say so.
- [ ] **`CSetBounds` with a large immediate** (CHERIoT). *R-15-067d · Matrix §10.*
  A further code-size candidate of the same class, and it should be measured the same way R-15-067d measures the bitfield pair: **against actual generated output at the freeze, dropped if the delta is immaterial.** R-15-036n makes that one measurement rather than several, so this lands with the bitfield pair and the single-check multi-save or not at all.
- [ ] Weigh all three against **§3's two code-size admissions** and the dictionary encoding's headroom (R-15-036a). Watch `ZcheriSanitary` (§6) — it is the standards-track form of this exact question.

### 4D. Sweep support

- [ ] **`CLoadTags`.** *R-08-007, R-15-203 · Matrix §5, §6 (marked **yes** in both).*
  The §8 sweep is an incremental software task whose completion latency is "the domain's capability-bearing footprint over the per-frame sweep quantum" — i.e. **entirely a memory-traffic quantity**. `CLoadTags` reads a granule group's tags without reading the data, and with native SRAM tag bits read in parallel with data (R-15-203) it is close to free in silicon. **Mature since ISAv8, so the "experimental" objection is gone. Nothing in the profile carries it and no requirement declines it** — the strongest lean in this section.
- [ ] **`CClearTags`.** *R-15-182, R-08-007 · Matrix §6.*
  Partly covered already: `cbo.zero` allocates whole lines with zeroed data *and* cleared tags at one fixed latency (R-15-182). The residue is **tag-only clearing where data must survive** — a sweep-side want, not a zeroize-side one. Decide with `CLoadTags`.

### 4E. A capability conditional move

- [ ] **`CMOVN`/`CMOVZ`.** *R-15-054, R-15-019, R-15-023 · Matrix §4.*
  The one obviated-looking row that is not obviated. `Zicond` is adopted **precisely because** branchless select is doubly load-bearing under static-only prediction with a full mispredict penalty on every forward conditional — but `czero.eqz`/`czero.nez` selects an *integer*, and on a purecap machine the selected value is frequently a **capability**. Either a capability-aware conditional move exists, or every conditional pointer select pays a mispredict-equivalent penalty and **breaks the constant-time story R-15-054 was bought to protect**. The argument is stronger here than the one ISAv6 made upstream, because the fallback is a branch this profile has deliberately made expensive.

### 4F. The trap-path residue — rides the `xtval` fix

*All three close in the same edit as defect 3. §5's table is closed, so silence on each is a decision rather than an omission.*

- [ ] **Does a sentry installed in `MEPCC` unseal on `mret`?** *R-15-073, R-07-022 · Matrix §6.*
  ISAv8 made sentries auto-unseal when installed in the exception PC, not only when jumped to. The trap path installs `MTCC` and saves `MEPCC`; the profile does not answer this, and **it is on the domain-entry path**.
- [ ] **The unaligned-base CHERI exception code.** *R-15-084, §5.3 · Matrix §6.*
  The *behavior* is settled — misaligned data accesses trap (R-15-084) and fetch is bundle-aligned. What is unsettled is the **cause encoding**, which belongs with the `mcause` row.
- [ ] **`ErrorEPCC` — a trap taken inside the handler.** *R-07-022, §5.3 · Matrix §5.*
  Modeled on MIPS `ErrorEPC` and not carried into RISC-V, where the equivalent question is what happens to a fault inside a fault handler. Low cost; §5.3 is the right place to settle it.

### 4G. Argument validation at a domain boundary

- [ ] **`CTestSubset` / RVY `YSS`.** *R-07-031a · Matrix §5, §9.2.*
  Upstream's first consumer is a garbage collector, which this platform has not got. **Its second consumer is argument validation at a domain boundary, which this platform has**: the switcher checks delegated buffers on every cross-compartment call. RVY **promoted it out of the experimental appendix into the base ISA**, which weakens the "no consumer" reading considerably.

### 4H. Vector checking versus mask independence

- [ ] **State the composition of "only active elements are subject to CHERI checks" with R-15-085.** *R-15-115, R-15-085 · §8/§9 · Matrix §9.2.*
  R-15-085's mask-independence contract **forbids skipping cycles or memory accesses for masked-off elements**. RVY checks only active elements. The two are compatible — *check everything, fault only on active elements* — but one is a security contract and the other a timing one, and the composition should be **stated rather than left to a reader to reconcile**.

### 4I. Multi-rooted capability hierarchy

- [ ] **Disjoint RX / RW / sealing roots, so no W+X root exists** (CHERIoT). *R-14-002 · Matrix §10.*
  R-14-002 proves system-wide W^X as an invariant of the derivation forest, via a machine-checked absence of Store∧Execute **in the static initial capability distribution**. Disjoint roots would make the same property **structural — unforgeable by construction rather than true of one audited initial state** — and the profile already fixes the initial distribution at composition, so the cost is close to zero. Worth weighing precisely because **R-15-076 books the concentration of everything onto CHERI's own correctness**.

---

## 5. Records to add

### 5A. Deliberate divergences — so a later reader does not read them as drift

- [ ] **4-bit object type against RVY's 1-bit CT field.** *R-15-007, R-07-002b · Matrix §9.2.* A divergence in both directions, and the profile is not behind: RVY's base keeps one sealing bit where the profile keeps four otype bits.
- [ ] **The forward/backward sentry split is ahead of RVY's base, not adrift from it.** *R-15-071 · Matrix §9.2.* CHERIoT 1.0 added it for exactly the profile's reason; RVY lists it as a *future* CT value and has **reserved encoding room** — `YSENTRY`'s `rs1` is held for a future `YSEAL` taking an authorizing capability.
- [ ] **No software-defined permissions**, which RVY mandates and CHERIoT carries. *R-15-007b.* Record the ground once **4A** decides it.
- [ ] **`YBLD` is base functionality upstream and forbidden at the root here.** *R-05-136 · Matrix §4, §9.2.* No reconstruction of a capability from its bit pattern, ever; the upstream use cases (swap, VM migration, runtime linking) are each independently absent.
- [ ] **Pointer masking**, which RVY integrates for RVA23 compatibility and R-15-043 deletes. *R-15-043 · Matrix §9.2.* The divergence is **entirely a profile-compatibility artifact** — RVY must coexist with a ratified application profile; this platform curates its own.
- [ ] **The per-load tag check is architectural here and implementation-defined upstream.** *R-08-005 · Matrix §9.2 `Svucrglct`.* RVY **dropped** `Svucrglct` on the ground that software must assume the check might not happen, so naming it buys nothing. The profile cannot take that position: R-08-005 makes the check architectural and fixed-latency **because containment latency is a proof obligation and a §11 schedule term**. Same mechanism, opposite conclusion, and the profile's reason is specific to it.
- [ ] **Also record what §10 is actually refusing.** *R-15-078, R-15-079 · §10 · Matrix §9.2.* RVY spends real effort making a debugger work against capability state — CHERI mode on debug entry, `dpcc`, `drootcsel`, capability-width abstract commands. The profile's answer is orthogonal and stronger: the Debug Module is **lifecycle-fused in hardware**, clock and reset gated off in production. §10 states the fuse without stating that **the capability-debug surface is what the fuse is refusing** — worth one clause, so the profile does not read as merely *missing* the debug work.

### 5B. Free confirmations to collect

- [ ] **`Zcd`, `Zcmp`, and `Zcmt` are incompatible with any purecap RV64 CHERI machine.** *R-15-036, R-15-036a · §6 · Matrix §9.2.*
  Purecap needs the 16-bit load/store encoding space for `C.LY`/`C.SY`, so the **code-size half of the `Zc*` family — push/pop multiple and table jump — was never on offer**, standards-track or not. The profile's `C` exclusion therefore forgoes less than a naive reading suggests: two of the three code-size instruments were unavailable regardless. It also removes a hypothetical objection, since `Zcmt`'s jump-vector table is a target-membership structure that would sit awkwardly beside sentry CFI and R-15-072's typed callee set anyway.
- [ ] **`Zicfiss` is incompatible with CHERI** — its push/pop instructions would need modifying. *R-15-044 · §6 · Matrix §9.2.*
  RVY reaches R-15-044's conclusion **from the encoding side rather than the principle side**. Collect it: two independent grounds for one exclusion.

*Two convergences are already recorded correctly and need no work — **physical-address capabilities** (ISAv7 experimental appendix → ISAv9 model section, and this platform's entire address model) and the **64-bit Concentrate format** (the literal base of the frozen format). A third, compressed non-orthogonal permissions, is not a convergence: see correction 4.*

---

## 6. Watch

*No obligation attached. Tracked because each aims at a question §4 leaves open, or because a release would rerun the review gate.*

- [ ] **`ZcheriSanitary`** — cleaning capabilities on compartment switch. *Research, needs a PR.* **The one to watch.** It is the standards-track form of cluster **4C**: what must a compartment switch scrub, and can the ISA help?
- [ ] **`ZcheriTraceTag`** — data capability trace with tags. *Research, needs a PR.* Irrelevant in production (trace rides the lifecycle fuse, R-15-079) but relevant in the **development** lifecycle state, where §10 permits trace and R-15-077 points development measurement at it.
- [ ] **ISAv10.** `app-versions-10-0.tex` on `main` still reads `TBD`. Nothing to track yet; a published Cambridge release is an **amendment that reruns the review gate (R-18-034)**, not a drift.
- [ ] **RVY toward v1.0 ratification.** Stable at v0.9.9 with limited change expected. Not an obligation — R-15-007 and R-17-048a retire the re-pin — but `Zylevels1` was **postponed out of the v1.0 package** at v0.9.8, and the profile adopts it (R-15-074), so the standard is behind the profile on that row rather than ahead.

---

## Where the work lands

*Several findings collapse into one edit. This is the grouping to work in, not the order above.*

| Profile section | Items | Class |
| --- | --- | --- |
| §1 Base | merged register file; no runtime CHERI disable | defect, statement |
| §3 Custom instructions | `YSH1ADD` re-pin-target correction; opcode-space choice (see below) | correction |
| §4 CHERI feature set | revocation-driven tag clearing on load; tag-clearing-vs-trapping | defect, statement |
| §4.1 Capability format | revocation colour; zeroed-granule NULL; SDP bits; seal/unseal separability; malformed-bounds checks | defect ×2, cluster 4A |
| §5.1 / §5.3 CSR bank | `xtval` closure + sentry-on-`mret`, unaligned-base cause, `ErrorEPCC`; `menvcfg` explicitness; `mshwm`/`mshwmb` | defect, cluster 4F, statement, 4C |
| §6 Exclusions | `Zcd`/`Zcmp`/`Zcmt` and `Zicfiss` confirmations; divergence records | confirmations, 5A |
| §8 Core classes | vector store clears tags; active-element ⋈ mask-independence | statement, 4H |
| §10 Debug | what the fuse is refusing | 5A |
| §11 Freeze / re-pin | R-17-048a two-term estimate; parameterized-encoding-format argument; **residual-semantics clause** (or §4.1) | corrections 2, 3, **§0** |
| Register (not the profile) | R-15-007b rationale re-word; R-08-004a keying | correction 4, defect 2 |

**One item has no landing row and should get one at the freeze:** the profile places three bespoke instructions — the capability indexed load/store and `bfext`/`bfins` — in "custom opcode space". At v0.9.8 **RVY relocated its own instructions into what is Custom-3 for RVI and reserved Custom1–3 wholesale** when the base ISA is RVY. There is **no defect today**, since the profile is not RVY-based. But it forecloses the encoding-level rapprochement that correction 3 would otherwise leave open, so **the encoding should be chosen knowing the standards line has claimed the same real estate** (R-15-007e, R-15-067a, R-15-014; matrix §9.2).
