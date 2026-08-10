# Bug-Class Coverage: TODO (non-normative)

> Companion to the **Bug classes removed by construction** inventory in [README.md](README.md), to [verification-maximal-os.md](verification-maximal-os.md), and to [requirements-register.md](requirements-register.md).
> Where the README inventory states what the construction *already* removes, this doc holds the critiques of that inventory: the classes it should carry and does not, the classes it should name as open and does not, and the two defects in its *shape*.
> Nothing here is normative and nothing here relaxes an obligation.
> An item leaves this list when it lands as a numbered requirement in the register with an acceptance criterion and a trace, and appears in the inventory as a row or in §17 as a residual. Removing an item from the list without one of those is the failure mode this doc exists to prevent.
> Item numbers are stable. Resolved items are deleted rather than checked off, and survivors are **not** renumbered, so gaps in the sequence are the record of what closed (the [critique.md](critique.md) convention).

## What earns a row

The inventory's rows are the strongest claims in the repository, so a proposed row is admitted only if it clears all five:

1. **It names a boundary and a property, not an attack.** "Rowhammer" is a name for an instance; "a memory array must not permit a write at one address to disturb a bit at another" is a property of a boundary. A row stated as an attack name can only ever be lengthened, never completed, and the [coverage matrix](coverage-matrix.md) is where the completable form of the claim lives.
2. **The construction is stated in this design's own mechanisms**, citing the sections that carry it, not in the general vocabulary of hardening.
3. **It carries a discharge mode**, and the mode is honest about what is *checked* versus what is *believed* (items 15 and 16 propose the two modes the current vocabulary lacks).
4. **It cites the requirement that makes it true.** A row with no requirement behind it is a claim about the prose, and the register's conferral discipline exists precisely because three overlapping sources of the same fact will disagree.
5. **If it cannot be discharged, it is a §17 residual, not an omission.** The inventory's closing paragraph already carries an exclusion list; the failure mode is a class that appears in neither.

---

## The honest frontier

These are open. Some are open in a way the inventory already admits and states poorly; some are open and unmentioned.

- [ ] **8. Spatial contention channels, and the theorem that would close them.**
  The inventory carries this row and the construction it names is the right one: static time-division multiplexing of fabric access, disjoint bank and macro binding per island, a whole macro or tier for a high-assurance island, and `fence.t` at the partition switch for the residual case where two low-sensitivity islands share a macro. That is the spatial analogue of the temporal partitioning, exactly as it should be.
  The open part is not the construction, it is that the row's mode says **proved** and the isolation model it would be proved against is unauthored, which is the dominant fact the critique's first gap states about the whole design. Bank-conflict and interconnect-arbitration channels survive the deletion of caches; what removes them is the static schedule, and what would *establish* that removal is the Sail-level non-interference statement for the memory path and the fabric.
  So the work here is not a new mechanism. It is: state the model, state the two-island shared-macro residual explicitly rather than in a subordinate clause, and stop the row from reading as discharged while its theorem has not started.
  **Lands as:** sharpening the existing row's honesty plus the crown-jewel specification it depends on. **Mode:** currently absent-or-proved; should read absent for the disjoint case and residual for the shared-macro case until the model exists.

- [ ] **9. Vector gather and scatter, and variable-latency arithmetic.**
  The general constant-time clause covers this in principle and an explicit profile entry would cover it in fact. Two specifics deserve naming rather than inheriting a general clause.
  **Secret-dependent addresses still leak without any cache.** Indexed vector access is checked per element (§15) but its *timing* over a banked SRAM is a function of the address pattern, because bank conflicts serialize. With no cache in the machine this is the surviving address-timing channel, and it is precisely the one a reader assumes the cacheless design deleted.
  **Subnormal and divide latency on the vector FPU.** The profile already mandates fixed latency across operand classes including subnormals and carves out `FDIV`/`FSQRT` with the argument that crypto needs neither, which is the correct discharge. The gather and scatter case has no equivalent sentence.
  The admissible resolution matches the existing carve-out discipline: either an operand-pattern-independent timing contract for indexed access, or an explicit ISA-profile exclusion of secret-indexed gather and scatter with the information-flow obligation that discharges it (the standing rule that a bare self-exclusion is not a pass).
  **Lands as:** a §15 timing-contract entry beside the FPU one, with the `Zvkt` list naming it. **Mode:** hardware-enforced or admission-rejected, per the carve-out pattern.

- [ ] **10. Power and electromagnetic analog leakage.**
  Absent entirely, and honestly so: §3 scopes invasive physical attack out, §15 admits the Faraday enclosure as attenuation that no theorem rests on, and §17 books emanation as narrowed but not closed. Nothing in the construction is a countermeasure for differential power analysis or electromagnetic analysis against the crypto core, and the constant-time discipline addresses *timing*, not power.
  The only construction-grade answer is **masking with a machine-checked proof in a probing model**, which is a real and mature line of work and is entirely unrepresented here. It is expensive on both axes (randomness per operation, area, and a proof over a leakage model that is itself an assumption), so the decision is a genuine one rather than an oversight to correct.
  The minimum honest step is to state the position: that the crypto core carries no masking, that side-channel resistance against a probing adversary is not claimed, and what would change that. The maximum step is the masked implementation with its probing-model theorem, which would be a new crown jewel and a new leakage assumption.
  **Lands as:** a §17 residual stated in its own right rather than inside the physical-attack clause; optionally a §5 obligation if masking is ever adopted. **Mode:** residual.

- [ ] **11. Fault injection, and the discharge mode it has nowhere to go.**
  Voltage and clock glitching, laser injection, and electromagnetic fault injection are not eliminable, and the design says so. But they are *detectable* by construction, and the design already carries most of the detectors: pervasive error-correcting codes with correction on every array, the CHERI validity tags, the fail-stop sentinel, the watchdog, the crash-only restart, and the multikernel blast-radius containment (§7, §15, §16). §15 even states the doctrine in one line: *detect, correct, or contain, never shield*.
  The gap is that the inventory has no mode for any of that. A row whose honest answer is "an injected fault is caught and the partition restarts" cannot be written today, so the class is simply missing from a matrix that claims to enumerate what the construction removes. This is the concrete case that motivates item 15.
  The remaining construction work is small and specific: a stated position on control-flow signatures for the sequences where a skipped instruction is catastrophic (the boot chain, the credential comparison, the lifecycle transition), and a stated position on whether the sentinel core runs in lockstep, which the design has evaluated and deferred rather than decided in the inventory's terms.
  **Lands as:** an inventory row once the mode exists, plus the §16 statements it would cite. **Mode:** detected (item 15).

- [ ] **13. Silicon supply chain: the mask analogue of reproducible builds.**
  Partly answered and stated as partly answered, which is right: §17 carries the fab residual, names open RTL and multi-sourcing as partial mitigations, and adds post-fabrication infrared inspection as evidence rather than proof.
  What has no analogue is the software side's strongest instrument. Every binary is bound to its exact source closure by a checked theorem, and the base image is bit-for-bit reproducible; nothing states the corresponding property for the artifact that becomes silicon. The deterministic-synthesis question (that a given RTL and toolchain produce a bit-identical layout, so that an independent party can regenerate and compare), the hashing and attestation of the mask set that the boot ROM already assumes is attested (§9 cites "the attested mask set"), and the correspondence between the layout that was reviewed and the layout that was taped out, are all unstated.
  The honest ceiling is unchanged: none of this reaches a fab that deviates from the mask set, which is what the inspection evidence exists for. But the *design-to-mask* half is the same shape as source-to-binary and is currently missing while its analogue is load-bearing.
  **Lands as:** §17 refinement plus §18 obligations on the tapeout path. **Mode:** proved for the design-to-mask correspondence; the mask-to-die half stays evidence.

---

## Two smaller structural notes

- [ ] **15. The discharge vocabulary is missing at least two real modes.**
  The inventory uses absent, hardware-enforced, admission-rejected, and proved. Two mechanisms the design leans on heavily fit none of them.
  **Detected and corrected.** Error-correcting codes are the clearest case: the mandate is pervasive and graded, correction is on every array, uncorrectable events are fail-stop, and the whole single-event-upset posture is *detect, correct, or contain* (§15). None of that is absence, none of it is a hardware access check, none of it is refused at admission, and none of it is a theorem about the fault. The same is true of the memory integrity tree, of storage scrubbing, of the watchdog, and of the fail-stop sentinel. Adding the mode is the precondition for item 11 having anywhere to land, and for the entropy root's health tests reading as the discharge they are rather than as a residual's consolation.
  **Transferred.** Some obligations are genuinely discharged by someone other than the platform: the compartment author (an app that ships its own string-parsing engine, which the inventory's closing paragraph already concedes), the deployment (the graded reliability and radiation-hardening axes), and the human (consent comprehension, which §17 books as outside every theorem). Today these appear as prose caveats after the tables, which reads as a footnote to a claim rather than as a claim about where the obligation went. Naming the mode makes the transfer a stated part of the argument and makes it countable.
  **Lands as:** two mode names in the README legend plus per-row use. **Mode:** not applicable.

- [ ] **16. The inventory is integrity-shaped, and confidentiality is under-represented.**
  Counting by row, the overwhelming majority of the claims are about integrity and authority. Confidentiality gets essentially one row (secret-dependent branches, addresses, and variable-latency operations) despite non-interference being the named property of §8 and a named §17 residual.
  Three confidentiality classes have no entry at all and each is a real class with a real construction position in this design.
  **Over-broad declassification.** The powerbox is the sole runtime declassifier and the design's answer is robust delimited declassification (§8), which is a strong construction and appears nowhere in the inventory. The class it removes (an over-broad grant, a grant an attacker can drive, a grant that carries more than the object it named) is exactly what a reader of a security inventory would look for.
  **Termination and progress channels.** A static cyclic executive with non-work-conserving slots and admitted worst-case bounds is an unusually strong answer here, because a computation's *observable* progress is a function of the schedule rather than of the secret. That is close to an absence claim and it is not made.
  **Exception and fault-path flows.** Fail-stop is the design's standard response, and a fault that is a function of a secret is an information flow whether or not the machine survives it. The design's position (that a fault restarts a partition, and that fault classes are reported to the sentinel) has a confidentiality consequence that is currently unstated.
  **Lands as:** three inventory rows plus, where the position is not yet stated, the §8 and §16 requirements they would cite. **Mode:** per row; the declassification row is proved, the progress row is closer to absent, the fault-path row may be residual.

---

## What would retire this list

Items 9, 13, 15, and 16 are statements the design owes about positions it has already taken.
Items 8, 10, and 11 are the ones that change what the inventory *claims*: 8 by admitting its theorem has not started, 10 by admitting a class is not addressed, and 11 by acquiring a mode it lacks.
The structural change is already made: the [coverage matrix](coverage-matrix.md) is the coverage argument, so every item still on this list is now either a cell whose construction is thinner than its row reads or a residual whose booking is thinner than it should be, and a class nobody has thought of is a computed finding rather than a critique someone had to notice.
