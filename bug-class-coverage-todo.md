# Bug-Class Coverage: TODO (non-normative)

> Companion to the **Bug classes removed by construction** inventory in [README.md](README.md), to [verification-maximal-os.md](verification-maximal-os.md), and to [requirements-register.md](requirements-register.md).
> Where the README inventory states what the construction *already* removes, this doc holds the critiques of that inventory: the classes it should carry and does not, and the classes it should name as open and does not.
> Nothing here is normative and nothing here relaxes an obligation.
> An item leaves this list when it lands as a numbered requirement in the register with an acceptance criterion and a trace, and appears in the inventory as a row or in §17 as a residual. Removing an item from the list without one of those is the failure mode this doc exists to prevent.
> Item numbers are stable. Resolved items are deleted rather than checked off, and survivors are **not** renumbered, so gaps in the sequence are the record of what closed (the [critique.md](critique.md) convention).

## What earns a row

The inventory's rows are the strongest claims in the repository, so a proposed row is admitted only if it clears all five:

1. **It names a boundary and a property, not an attack.** "Rowhammer" is a name for an instance; "a memory array must not permit a write at one address to disturb a bit at another" is a property of a boundary. A row stated as an attack name can only ever be lengthened, never completed, and the [coverage matrix](coverage-matrix.md) is where the completable form of the claim lives.
2. **The construction is stated in this design's own mechanisms**, citing the sections that carry it, not in the general vocabulary of hardening.
3. **It carries a discharge mode**, and the mode is honest about what is *checked* versus what is *believed*. The vocabulary is six modes wide, and the last two are the ones a row reaches for when it would otherwise overclaim: *detected* where the fault occurs and its consequence is bounded, *transferred* where the obligation is met by a named party other than the platform.
4. **It cites the requirement that makes it true.** A row with no requirement behind it is a claim about the prose, and the register's conferral discipline exists precisely because three overlapping sources of the same fact will disagree.
5. **If it cannot be discharged, it is a §17 residual, not an omission.** The inventory's closing paragraph already carries an exclusion list; the failure mode is a class that appears in neither.

---

## The honest frontier

These are open. Some are open in a way the inventory already admits and states poorly; some are open and unmentioned.

- [ ] **10. Power and electromagnetic analog leakage.**
  Absent entirely, and honestly so: §3 scopes invasive physical attack out, §15 admits the Faraday enclosure as attenuation that no theorem rests on, and §17 books emanation as narrowed but not closed. Nothing in the construction is a countermeasure for differential power analysis or electromagnetic analysis against the crypto core, and the constant-time discipline addresses *timing*, not power.
  The only construction-grade answer is **masking with a machine-checked proof in a probing model**, which is a real and mature line of work and is entirely unrepresented here. It is expensive on both axes (randomness per operation, area, and a proof over a leakage model that is itself an assumption), so the decision is a genuine one rather than an oversight to correct.
  The minimum honest step is to state the position: that the crypto core carries no masking, that side-channel resistance against a probing adversary is not claimed, and what would change that. The maximum step is the masked implementation with its probing-model theorem, which would be a new crown jewel and a new leakage assumption.
  **Lands as:** a §17 residual stated in its own right rather than inside the physical-attack clause; optionally a §5 obligation if masking is ever adopted. **Mode:** residual.

- [ ] **11. Fault injection, and the two detector positions the design has not taken.**
  Voltage and clock glitching, laser injection, and electromagnetic fault injection are not eliminable, and the design says so. But they are *detectable* by construction, and the design already carries most of the detectors: pervasive error-correcting codes with correction on every array, the CHERI validity tags, the fail-stop sentinel, the watchdog, the crash-only restart, and the multikernel blast-radius containment (§7, §15, §16). §15 even states the doctrine in one line: *detect, correct, or contain, never shield*.
  The gap is no longer the vocabulary: *detected* now names the mode, and the detection rows beside it (upsets, the entropy root, the wedged partition) are the shape the fault-injection row would take. What the row still lacks is its construction. A row whose honest answer is "an injected fault is caught and the partition restarts" has to say which mechanism catches *which* injection, and for the sequences where a single skipped instruction is catastrophic the design says nothing at all.
  The remaining construction work is small and specific: a stated position on control-flow signatures for those sequences (the boot chain, the credential comparison, the lifecycle transition), and a stated position on whether the sentinel core runs in lockstep, which the design has evaluated and deferred rather than decided in the inventory's terms. Until both exist the row would be a mode with nothing under it.
  **Lands as:** an inventory row beside the other detection rows, plus the §16 statements it would cite. **Mode:** detected.

- [ ] **13. Silicon supply chain: the mask analogue of reproducible builds.**
  Partly answered and stated as partly answered, which is right: §17 carries the fab residual, names open RTL and multi-sourcing as partial mitigations, and adds post-fabrication infrared inspection as evidence rather than proof.
  What has no analogue is the software side's strongest instrument. Every binary is bound to its exact source closure by a checked theorem, and the base image is bit-for-bit reproducible; nothing states the corresponding property for the artifact that becomes silicon. The deterministic-synthesis question (that a given RTL and toolchain produce a bit-identical layout, so that an independent party can regenerate and compare), the hashing and attestation of the mask set that the boot ROM already assumes is attested (§9 cites "the attested mask set"), and the correspondence between the layout that was reviewed and the layout that was taped out, are all unstated.
  The honest ceiling is unchanged: none of this reaches a fab that deviates from the mask set, which is what the inspection evidence exists for. But the *design-to-mask* half is the same shape as source-to-binary and is currently missing while its analogue is load-bearing.
  **Lands as:** §17 refinement plus §18 obligations on the tapeout path. **Mode:** proved for the design-to-mask correspondence; the mask-to-die half stays evidence.

---

## What would retire this list

Item 13 is a statement the design owes about a position it has already taken.
Items 10 and 11 are the ones that change what the inventory *claims*: 10 by admitting a class is not addressed, and 11 by deciding the two §16 positions its row would have to cite.
The structural change is already made: the [coverage matrix](coverage-matrix.md) is the coverage argument, so every item still on this list is now either a cell whose construction is thinner than its row reads or a residual whose booking is thinner than it should be, and a class nobody has thought of is a computed finding rather than a critique someone had to notice.
