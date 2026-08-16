**Findings, dispositioned**

*References here are symbolic: requirement IDs, crown-jewel rows, and section headings, never line numbers. This follows the register's own **traces are bookmarks, not line numbers** rule, and it is not a stylistic preference: a line number is a derived fact restated in a second artifact with nothing checking it, and it goes stale on the next edit to the artifact it cites.*

**Convention.** When a finding closes, delete it and renumber, and retarget every cross-reference that pointed at it. No departure notes, no strikethroughs, no closed section: git history is the narrative, and what stands here is the open agenda. The same rule governs a simplification that is adopted or declined outright, and a partly adopted one keeps only the part still in question.

---

**1. The ISA freeze has a circular prerequisite.** · **Open. The recommendation is sound and no decision is recorded.**

R-18-003a makes the profile freeze the root of the schedule with no build prerequisite. Yet R-15-067d makes the bitfield pair's carriage conditional on a measurement against generated output, and the dictionary's realized size and entry selection are measured against the emitted mix (`isa-profile.md` §1.1, *Density is a model, not a quotation*). Those inputs do not exist before the compiler and a composed image do.

The proposed two-stage form (a provisional standard baseline, then one measured final freeze) is consistent with how the profile already talks about itself: `cheri-todo.md` §4 is explicitly *decisions the freeze must make*, and several are already marked as re-derived from actual output at freeze time. What is missing is a requirement naming the two stages and which artifacts gate the second.

**2. The proof target is behind the architecture.** · **Open, and structural.**

`crown-jewels.md` records 1 of 22 authored, 3 partial, 18 not authored, and its own *Reading the status column* section states the consequence. R-18-003b enumerates five day-one deliverables that gate on nothing, and the machine-checked statement of theorem `T` with its seam interfaces is among them.

The concern that further refinement risks optimizing for a proof whose interfaces later do not compose is the sharpest item in this document, and nothing in the current schedule answers it. It is a sequencing decision, not a defect to be edited into a requirement.

**3. "Mobile/laptop class" is conditional and unfalsifiable.** · **Open, and the repository already says so.**

`critique.md`'s *The first release has no stated minimum viable capability, so deletion is unfalsifiable* makes the same argument from the inside, and `performance-estimates.md`'s headline total carries the numbers: roughly 30-55% of a conventional core on general interactive code, worse on browser workloads, with the accelerated paths at parity or far above. The vertical capacity lever is conditional on a materials result rather than graded by effort (R-15-163), and the first release carries the radio roster whole (R-18-004).

The recommendation stands: either name this a fixed-capacity secure appliance, or state a measurable mobile acceptance criterion. Both are product decisions and neither is recorded.

**4. The cache deletion depends on an unauthored physical premise.** · **Open.**

Uniform flat SRAM access latency is what replaces DRAM's row-buffer variance and turns the worst-case memory-access term into a flat constant (R-15-163, R-15-164). The magnitudes are `crown-jewels.md` row 15, *the timing-annotated Sail model's latency magnitudes*, status **not authored** (R-17-041, R-15-095, R-18-024). The observation that *deterministic* does not imply *fast* is correct, and the suggested static hierarchy with fixed per-region latency classes is the obvious fallback if the magnitudes come back poorly.

Worth noting for whoever authors row 15: the static memory plan already emits a per-mode occupancy map over banks, macros, and tiers (R-08-012a, R-08-012e), so most of the placement machinery a fixed-latency-class hierarchy would need already exists. What does not exist is any requirement making the classes architecturally visible.

**5. Package installation conflicts with build-time composition.** · **Open.**

R-04-008 fixes every compartment at composition and R-07-025 fixes the component graph and capability distribution at build time, while R-12-024b compiles a handler and translator graph from installed packages and R-13-001 gives each package a capability manifest. The finding's two candidate readings (atomic next-boot recomposition, or binding into pre-proved empty slots) are the right pair, and the lifecycle specifies neither.

**6. Two README closures are stronger than the normative design.** · **Open, both halves, and both are conceded in the specification's own residuals.**

Integer overflow: §17's residual (6), *totalized arithmetic is per-install decidable only where the bounds are closed*, states the split directly, an overflow obligation over closed numerals being decided per-install while one depending on a runtime value descends to a release-time proof term that does not reach the installed-app population. The tier obligations are R-13-011 and R-13-012.

Failed verdicts: §17's relevance residual states that the must-examine rule makes dropping a verdict structurally impossible and does not constrain the response. Both are honest residuals in the design document and are overstated in the README, which is a README defect rather than a design one.

**7. Mutable user-data rollback is not merely availability for every app.** · **Open, and the proposal is well-shaped.**

R-10-013 spends the RoT monotonic counter only on the low-rate security-critical platform state it can keep fresh, and the four-layer stack below it is wholly non-TCB with a small verified reader carrying integrity (R-10-009). The consequence the finding draws is right: stale payment state, revocation lists, one-time operations, and application counters have security consequences under authenticated rollback, not merely availability ones.

The suggested shape (a small quota-controlled app-facing freshness service and a `Fresh` durable-state type, with bulk storage explicitly rollbackable) fits the existing structure, because R-10-013's argument is about *counter bandwidth* and a quota is exactly the mechanism that respects it.

---

**Radical Simplifications, dispositioned**

**Scalar "VerifiedOS Core" first.** · *Open, no decision recorded.* This is finding 2's sequencing argument applied to the artifact rather than to the proof. It collides with R-15-007d's *the width is permanent*: every capability in the immutable image and every sealed blob is stored in the frozen format, so a later width change invalidates stored authority wholesale rather than costing a recompile. *Add the narrowed format only after a measured failure* is therefore unavailable for that one item, whatever its merit for the matrix unit, FEC, cellular, and dictionary encoding.

**Extend the per-session index model to all revocable cross-domain authority.** · **Partly adopted; the remainder declined on a stated ground.**

The adopted half is the authority model's current shape: cross-domain authority that must be independently revocable goes through a kernel-owned grant table rather than being handed across as a bare capability (R-08-004a), with its costs booked in R-08-004c. Three differences from the proposal as written, with reasons:

- *Handles are sealed capabilities bounded to their slot, not indices into a table.* An index plus generation is capability-address translation, which R-07-002b deletes by name and whose l4v lookup refinement is one of the two largest remaining proof blocks after the VM layer. A capability whose **bounds** name the slot is dereferenced, not resolved, so that refinement does not return.
- *There is no generation counter.* It was considered and does not work, for the same structural reason a revocation colour does not: a generation discriminates only if the handle carries it, and the format has no field to carry it in (R-08-004b). Carried out of band, as an integer the delegate presents at invocation, it stops being capability authority and becomes a **bearer token**, and a stale holder who kept a handle to a re-minted slot need only present the successor of the generation it last saw. R-08-007a records the ground; reuse is gated on a sweep pass instead, which is an availability cost to the retiring principal rather than a security one to anybody.
- *The per-load filter, sweep, and quarantine are kept.* The proposal's *for the common case* is where its cost hides. R-05-159 states temporal safety as revocation joined with the CHERI-TAL linear-capability discipline, a conjunction; keeping raw capabilities local-or-linear deletes the first conjunct and asks linearity to carry the whole load over code it does not cover, namely residual C, the `unsafe` Rust the verified HAL is built from (R-08-003 exists to backstop exactly that), and Tier-2 apps whose obligations finding 6 shows are already thinner than advertised. Separately, `coverage-matrix.md` boundary `B-04` books fabric epoch-honoring for a transfer already in flight as a residual on R-08-006 and R-15-208; an architectural per-load check extends to a capability-carrying fabric, and a kernel-side table does not.

The failure mode is asymmetric: if any non-common case survives, the system carries the filter **and** the table, which is worse than either alone.

**TAL checker only on-device; source-correspondence off-device.** · *Open, no decision recorded.* The observation that a source-correspondence proof binds bytes to source that may itself be malicious is correct, and it is already the stratification's stated scope (R-13-023, R-13-028, and R-17-038's split by proof scale). What the proposal changes is which side of the release/install line the CIC kernel sits on, which is a live trade rather than a defect.

**Filesystem in contained safe Rust first.** · *Open, no decision recorded.* R-10-009 already makes the four-layer stack wholly non-TCB with a small verified reader carrying integrity, so this is a scheduling claim about the four fresh proof programs rather than an architectural one, and it disturbs no stated obligation.

**Decide the product fork explicitly.** · *Open, and it is finding 3 restated as a decision rather than as a gap.* R-15-162 declines chiplets and bonded die-stacking outright, and R-15-163 makes the monolithic vertical lever conditional on an unsolved low-temperature p-type device result. Accepting authenticated external or bonded memory reopens R-15-162, which is a deliberate refusal carrying a stated ground, so this is not a free choice between two equally open options.

---

**What remains concretely closeable:** wrong responses to failed verdicts, runtime-dependent Tier-2 overflow, rollback of security-sensitive app state, and non-atomic package recomposition.

Analog power and EM leakage, human consent, protocol-standard flaws, and fail-closed denial remain honestly recorded as residuals rather than overlooked bugs.
