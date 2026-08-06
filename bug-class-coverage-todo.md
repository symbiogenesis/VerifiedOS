# Bug-Class Coverage: TODO (non-normative)

> Companion to the **Bug classes removed by construction** inventory in [README.md](README.md), to [verification-maximal-os.md](verification-maximal-os.md), and to [requirements-register.md](requirements-register.md).
> Where the README inventory states what the construction *already* removes, this doc holds the critiques of that inventory: the classes it should carry and does not, the classes it should name as open and does not, and the two defects in its *shape*.
> Nothing here is normative and nothing here relaxes an obligation.
> An item leaves this list when it lands as a numbered requirement in the register with an acceptance criterion and a trace, and appears in the inventory as a row or in §17 as a residual. Removing an item from the list without one of those is the failure mode this doc exists to prevent.
> Item numbers are stable. Resolved items are deleted rather than checked off, and survivors are **not** renumbered, so gaps in the sequence are the record of what closed (the [critique.md](critique.md) convention).

## What earns a row

The inventory's rows are the strongest claims in the repository, so a proposed row is admitted only if it clears all five:

1. **It names a boundary and a property, not an attack.** "Rowhammer" is a name for an instance; "a memory array must not permit a write at one address to disturb a bit at another" is a property of a boundary. A row stated as an attack name can only ever be lengthened, never completed (item 14).
2. **The construction is stated in this design's own mechanisms**, citing the sections that carry it, not in the general vocabulary of hardening.
3. **It carries a discharge mode**, and the mode is honest about what is *checked* versus what is *believed* (items 15 and 16 propose the two modes the current vocabulary lacks).
4. **It cites the requirement that makes it true.** A row with no requirement behind it is a claim about the prose, and the register's conferral discipline exists precisely because three overlapping sources of the same fact will disagree.
5. **If it cannot be discharged, it is a §17 residual, not an omission.** The inventory's closing paragraph already carries an exclusion list; the failure mode is a class that appears in neither.

---

## Eliminable with modest added construction

These are classes the design has the machinery to remove and does not currently claim. Each is a small construction over mechanisms that already exist, not a new subsystem.

- [ ] **1. Nonce and initialization-vector reuse.**
  The per-extent AEAD nonce is specified as random and per-extent (§10), the DRBG is verified and single-rooted (§15, §16), and the checkpoint exclusion list already names nonces as state that must never be restored (§10). What is missing is the property that makes the class *unexpressible* rather than merely well-implemented: a nonce is a **use-once value**, and use-once is a type this system already has.
  The construction is the linear or affine grade the CHERI-TAL carries for capabilities, applied to a different object: a nonce-typed value is consumed by the operation that seals under it and cannot be duplicated, stored, or reached twice, so a reuse is a type error at admission rather than a review item at the call site.
  This is also the shape that survives the two hard cases (a restored checkpoint and a re-derived key), because the linear obligation forces the fresh draw rather than trusting the exclusion list to be read.
  **Lands as:** a §5 attribute admitted under the standing attribute test (R-05-132: finite domain, no duplicate axis, local syntax-directed rule) plus §6 checker-table coverage. **Mode:** admission-rejected.

- [ ] **2. Secret residue on release, and residue in registers and spill slots.**
  Allocation zeroizes eagerly (§7) and the partition switch zeroizes vector and matrix state (§7), which together close *disclosure to the next tenant*. Neither obligates **scrubbing on release**, so a secret's lifetime ends when its holder stops caring rather than when the secret is erased, and the residue that survives is exactly the residue in the places the switch does not clear: scalar registers not covered by the switch discipline, compiler-introduced spill slots, and the caller frames of a compartment that returns rather than restarts.
  The construction is the affine dual of item 1: a secret-typed value carries a **must-be-consumed-by-erasure** obligation, discharged by the erasing operation and checked on the final binary, which reaches the spill slots precisely because the check is on the binary and not the source. The `Zicboz` cost argument the eager-zeroize discipline already makes (§15) applies unchanged.
  Note the interaction with the crash-only posture: restart erases a compartment's whole footprint, so the obligation binds the paths that *return* while holding secrets, which is the smaller and the more dangerous set.
  **Lands as:** the same §5 attribute family as item 1, with the §13 tier table naming which tiers must carry it. **Mode:** admission-rejected, with eager zeroize as the absent-by-construction half already claimed.

- [ ] **3. Entropy-source failure and random-number-generator subversion.**
  The inventory has no row for the case where every cryptographic proof holds and the seed is predictable, and that case is not covered by anything else in the construction: the security reductions are conditional on uniform keys, the constant-time discipline says nothing about the values, and the single-root rule (§15, `Zkr` excluded so that exactly one entropy root exists) *concentrates* the risk rather than discharging it.
  What is missing is a statement of what the root owes: continuous on-line health tests with a defined failure action (fail-stop, not degrade), a conditioning and post-processing chain whose properties are stated rather than assumed, a seeding and reseeding discipline the DRBG's own correctness proof is stated against, and the boot-time position that a failed health test blocks key derivation rather than proceeding.
  The subversion half is the harder one and is where the design's existing instrument applies: the RDRAND cautionary history the profile already cites is an argument for **not trusting a raw source**, so the honest construction is a conditioned root whose output no single hardware failure can silently fix, with the failure detectable rather than the source trusted.
  **Lands as:** §15 hardware obligations on the TRNG plus a §5 or §6 statement of the DRBG's precondition, with the residual (a source that fails in a way the health tests do not see) booked in §17. **Mode:** detected (item 15) for the failure case, residual for the subversion case.

- [ ] **4. Parser differentials and encoding ambiguity.**
  This one needs a correction before it needs work. Narcissus buys more than memory safety: the format descriptor yields a **proved encode and decode pair** (§5), so the round trip is not in question. What is genuinely absent is the *other* direction and the *other* party.
  Two properties are separable and neither is currently claimed. **Canonicity**: that a value has exactly one admissible encoding, so a decode of a re-encode is the identity and a malleable second encoding of the same value cannot exist. **Agreement**: that two independent implementations of the same format accept the same language, which is what a parser differential actually is, and which a single verified parser cannot establish by itself.
  Canonicity is the one worth pursuing because it is provable from the descriptor rather than tested: it makes signature-over-encoding, content addressing, and cache identity (§10, §12) sound against a peer that re-encodes, and it is exactly the property whose absence produces the signature-confusion and hash-substitution families.
  Agreement stays evidence rather than theorem, and the design already knows the shape: the differential oracles named for the radio and network grammars (§5) are the instrument, and they enter no trust base.
  **Lands as:** a canonicity obligation on the §5 format-descriptor discipline, cited by the §13 image reader and the §10 content address. **Mode:** proved for canonicity; the agreement half stays evidence and belongs in §17.

- [ ] **5. Protocol state-machine flaws and downgrade.**
  Partly claimed and partly not. The design already states the radio-generation floor as matter rather than policy (§15) and the no-null-cipher, mutual-authentication-required, no-silent-downgrade posture as a verified property of the L2/L3 servers rather than a toggle (§12), and §17 books protocol-level composition as above the proof frontier.
  The gap is between those two statements: a protocol state machine is a Lustre control plane (§5, §12), which is the right vehicle, but no requirement says the machine **refines a formal model of the standard's own state machine**, and without that the verified property is a property of the implementation the design happens to have written.
  The construction that fits the design's grain is a single admissible configuration with nothing to negotiate (one ciphersuite, no version negotiation, no capability-driven fallback) plus refinement of the sequencer against a formal 802.11 or WPA3 or 5G-AKA state machine. The first half deletes the class the way the generation floor deletes the legacy-attach class; the second half is what makes the remaining half a theorem.
  **Lands as:** §12 refinement obligations on the named control planes, with the crown-jewel specification for each protocol's model. **Mode:** proved, with the composition residual unchanged in §17.

- [ ] **6. Lifecycle and debug-surface escape.**
  The design inherits the strongest available answer and does not claim it. Debug and trace sit behind RoT lifecycle state and are fused off in production (§15), the lifecycle state and anti-rollback counters live in on-die OTP (§9), and the boot ROM is metal-mask immutable (§9). That is an OpenTitan-lineage one-way fuse state machine, which is a *construction*, not a mitigation.
  What is not stated is the property: that the lifecycle is **monotone**, that no state transition re-enables a debug or test surface once production is entered, that raw-flash and test modes have no re-entry path, and that the transition is attested into the measured chain rather than merely performed.
  The class this removes is large and famous (test-mode re-entry, unlocked JTAG, factory-mode escape, engineering-key acceptance), and it is a class of *escape* rather than of exploitation, which is why it is worth a row of its own rather than a clause in the boot section.
  **Lands as:** §9 lifecycle requirements with the monotonicity property stated, cited from the §15 debug-gating entry. **Mode:** hardware-enforced, with the fuse state as the enforcing element.

- [ ] **7. Dimension, unit, and clock-domain confusion.**
  Nearly free at the type level and unclaimed. The design already separates the two clocks that matter (the free-running monotonic `mtime` the scheduler uses, and the disciplined wall-clock view the time service computes, §12, §15) and already knows that a cold boot has no absolute time (§9). Nothing prevents a value from one domain being used where the other is meant, and nothing prevents the ordinary unit confusions (cycles against microseconds, bytes against elements, a slot index against a slot width).
  The construction is a **phantom dimension attribute** on the TAL's existing attribute machinery, checked syntactically and erased before code generation, so it costs a rule and no runtime.
  It is worth doing here specifically because the WCET budgets, the frame arithmetic, and the deadline obligations (§11) are the places where a unit confusion is not a bug but an unsound admission, and because the monotonic-versus-wall-clock distinction is load-bearing for freshness (§9, §17).
  **Lands as:** a §5 attribute under R-05-132, consumed by the §11 admission arithmetic. **Mode:** admission-rejected.

---

## The honest frontier

These are open. Some are open in a way the inventory already admits and states poorly; some are open and unmentioned. None is closed by an item above.

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

- [ ] **12. Proof-trusted-computing-base hygiene.**
  Two checks are buildable today, cost nothing on the scarce axis, and are named nowhere.
  **Assumption gating.** A Coq development can compile green while resting on an admitted lemma, and the closing theorems here are the whole argument. The check is mechanical: for every shipped theorem, enumerate its axioms and assumptions and fail the build if the set is not exactly the declared one. The design already has the declared set, since §5's semantic-anchor budget and §6's axiom list state what is *supposed* to be assumed; the check is the one that makes the list true rather than aspirational.
  **Vacuity and coverage.** A theorem can be true and empty, whether by an unsatisfiable premise, a specification that permits everything, or a quantifier that ranges over nothing. The register's own review gate exists because "a proof against a wrong spec verifies perfectly", and a vacuous theorem is the degenerate case of exactly that.
  Both are checks over the proof artifacts, so they join `tools/check.ps1` in spirit but not in file: they belong to the build of the proofs rather than the consistency of the documents.
  **Lands as:** §5 or §6 obligations on the proof workstream, with §18 naming them as day-one deliverables (they gate on nothing, which is the §18 test for that class). **Mode:** proved, as a precondition on every other use of that mode.

- [ ] **13. Silicon supply chain: the mask analogue of reproducible builds.**
  Partly answered and stated as partly answered, which is right: §17 carries the fab residual, names open RTL and multi-sourcing as partial mitigations, and adds post-fabrication infrared inspection as evidence rather than proof.
  What has no analogue is the software side's strongest instrument. Every binary is bound to its exact source closure by a checked theorem, and the base image is bit-for-bit reproducible; nothing states the corresponding property for the artifact that becomes silicon. The deterministic-synthesis question (that a given RTL and toolchain produce a bit-identical layout, so that an independent party can regenerate and compare), the hashing and attestation of the mask set that the boot ROM already assumes is attested (§9 cites "the attested mask set"), and the correspondence between the layout that was reviewed and the layout that was taped out, are all unstated.
  The honest ceiling is unchanged: none of this reaches a fab that deviates from the mask set, which is what the inspection evidence exists for. But the *design-to-mask* half is the same shape as source-to-binary and is currently missing while its analogue is load-bearing.
  **Lands as:** §17 refinement plus §18 obligations on the tapeout path. **Mode:** proved for the design-to-mask correspondence; the mask-to-die half stays evidence.

---

## The structural defect

- [ ] **14. The taxonomy is shaped like a vulnerability archive, and that shape can never be argued complete.**
  Every row enumerates a historically named archetype. That form has a real virtue (a reader recognizes what is being claimed) and one fatal property: it can only be **lengthened**, never **completed**, and its coverage argument is therefore always "here is a long list" rather than "here is every case".
  A completeness claim needs a different shape, and the design already owns the materials for it. The shape is **interfaces by properties, top down**: for each boundary in the system, enumerate the properties that boundary must hold, then show each is discharged or listed as residual.
  The boundaries are already named across the specification: the ISA and its microarchitectural absences (§15), the binary-admission interface (§13), the inter-process interface definition language and its rings (§12), the device edge with its capability-checked direct memory access and its register-slave analog front ends (§12, §15), storage at rest (§10), the radio and network wire (§12), the human consent path (§6, §8), time and freshness (§9), and the supply chain from source through binary to mask (§13, §17).
  The properties per boundary are equally already named: confidentiality, integrity, authority, freshness, availability and progress, timing and leakage, and identity or uniqueness.
  Each cell is then discharged by requirement, or it is a residual, and an empty cell is a finding rather than an oversight. **This is derivable from the register**, because every requirement already carries a trace, so the matrix is computed rather than authored, and it is checkable in exactly the way the three existing derived views are: a cell with no requirement and no residual fails.
  The result is a **coverage argument** instead of a list, and it retires the inventory's weakest sentence, which is the implicit one that says the list is long enough.
  **Lands as:** a fourth derived view, generated and checked by `tools/check.ps1` alongside the existing three, with the README inventory retained as the reader-facing summary it is good at being. **Mode:** not applicable; this is the shape the modes are reported in.

---

## Two smaller structural notes

- [ ] **15. The discharge vocabulary is missing at least two real modes.**
  The inventory uses absent, hardware-enforced, admission-rejected, and proved. Two mechanisms the design leans on heavily fit none of them.
  **Detected and corrected.** Error-correcting codes are the clearest case: the mandate is pervasive and graded, correction is on every array, uncorrectable events are fail-stop, and the whole single-event-upset posture is *detect, correct, or contain* (§15). None of that is absence, none of it is a hardware access check, none of it is refused at admission, and none of it is a theorem about the fault. The same is true of the memory integrity tree, of storage scrubbing, of the watchdog, and of the fail-stop sentinel. Adding the mode is the precondition for items 3 and 11 having anywhere to land.
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

Items 1, 2, 6, and 7 are small constructions over existing machinery and could land as requirements without new mechanism.
Items 4 and 5 are real proof obligations of ordinary size.
Items 3, 9, 12, 13, 15, and 16 are statements the design owes about positions it has already taken.
Items 8, 10, 11, and 14 are the ones that change what the inventory *claims*: 8 by admitting its theorem has not started, 10 by admitting a class is not addressed, 11 by acquiring a mode it lacks, and 14 by changing the shape of the argument from a list to a covering.
Only item 14 retires the others structurally, because a matrix of boundaries against properties makes every remaining item either a filled cell or a named residual, and makes a *missing* item a computed finding rather than a critique someone had to notice.
