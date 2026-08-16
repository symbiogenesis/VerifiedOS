**Findings, dispositioned**

*References here are symbolic: requirement IDs, crown-jewel rows, and section headings, never line numbers. This follows the register's own **traces are bookmarks, not line numbers** rule, and it is not a stylistic preference: a line number is a derived fact restated in a second artifact with nothing checking it, and it goes stale on the next edit to the artifact it cites.*

**Convention.** When a finding closes, delete it and renumber, and retarget every cross-reference that pointed at it. No departure notes, no strikethroughs, no closed section: git history is the narrative, and what stands here is the open agenda. The same rule governs a simplification that is adopted or declined outright, and a partly adopted one keeps only the part still in question.

---

**1. The proof target is behind the architecture.** · **Open, and structural.**

`crown-jewels.md` records 1 of 22 authored, 3 partial, 18 not authored, and its own *Reading the status column* section states the consequence. R-18-003b enumerates five day-one deliverables that gate on nothing, and the machine-checked statement of theorem `T` with its seam interfaces is among them.

The concern that further refinement risks optimizing for a proof whose interfaces later do not compose is the sharpest item in this document, and nothing in the current schedule answers it. It is a sequencing decision, not a defect to be edited into a requirement.

**2. "Mobile/laptop class" is conditional and unfalsifiable.** · **Open, and the repository already says so.**

`critique.md`'s *The first release has no stated minimum viable capability, so deletion is unfalsifiable* makes the same argument from the inside, and `performance-estimates.md`'s headline total carries the numbers: roughly 30-55% of a conventional core on general interactive code, worse on browser workloads, with the accelerated paths at parity or far above. The vertical capacity lever is conditional on a materials result rather than graded by effort (R-15-163), and the first release carries the radio roster whole (R-18-004).

The recommendation stands: either name this a fixed-capacity secure appliance, or state a measurable mobile acceptance criterion. Both are product decisions and neither is recorded.

**3. The cache deletion depends on an unauthored physical premise.** · **Open.**

Uniform flat SRAM access latency is what replaces DRAM's row-buffer variance and turns the worst-case memory-access term into a flat constant (R-15-163, R-15-164). The magnitudes are `crown-jewels.md` row 15, *the timing-annotated Sail model's latency magnitudes*, status **not authored** (R-17-041, R-15-095, R-18-024). The observation that *deterministic* does not imply *fast* is correct, and the suggested static hierarchy with fixed per-region latency classes is the obvious fallback if the magnitudes come back poorly.

Worth noting for whoever authors row 15: the static memory plan already emits a per-mode occupancy map over banks, macros, and tiers (R-08-012a, R-08-012e), so most of the placement machinery a fixed-latency-class hierarchy would need already exists. What does not exist is any requirement making the classes architecturally visible.

**4. Package installation conflicts with build-time composition.** · **Open.**

R-04-008 fixes every compartment at composition and R-07-025 fixes the component graph and capability distribution at build time, while R-12-024b compiles a handler and translator graph from installed packages and R-13-001 gives each package a capability manifest. The finding's two candidate readings (atomic next-boot recomposition, or binding into pre-proved empty slots) are the right pair, and the lifecycle specifies neither.

**5. Two README closures are stronger than the normative design.** · **Open, both halves, and both are conceded in the specification's own residuals.**

Integer overflow: §17's residual (6), *totalized arithmetic is per-install decidable only where the bounds are closed*, states the split directly, an overflow obligation over closed numerals being decided per-install while one depending on a runtime value descends to a release-time proof term that does not reach the installed-app population. The tier obligations are R-13-011 and R-13-012.

Failed verdicts: §17's relevance residual states that the must-examine rule makes dropping a verdict structurally impossible and does not constrain the response. Both are honest residuals in the design document and are overstated in the README, which is a README defect rather than a design one.

**6. Mutable user-data rollback is not merely availability for every app.** · **Open, and the proposal is well-shaped.**

R-10-013 spends the RoT monotonic counter only on the low-rate security-critical platform state it can keep fresh, and the four-layer stack below it is wholly non-TCB with a small verified reader carrying integrity (R-10-009). The consequence the finding draws is right: stale payment state, revocation lists, one-time operations, and application counters have security consequences under authenticated rollback, not merely availability ones.

The suggested shape (a small quota-controlled app-facing freshness service and a `Fresh` durable-state type, with bulk storage explicitly rollbackable) fits the existing structure, because R-10-013's argument is about *counter bandwidth* and a quota is exactly the mechanism that respects it.

---

**Radical Simplifications, dispositioned**

**Scalar "VerifiedOS Core" first.** · *Open, no decision recorded.* This is finding 1's sequencing argument applied to the artifact rather than to the proof. It collides with R-15-007d's *the width is permanent*: every capability in the immutable image and every sealed blob is stored in the frozen format, so a later width change invalidates stored authority wholesale rather than costing a recompile. *Add the narrowed format only after a measured failure* is therefore unavailable for that one item, whatever its merit for the matrix unit, FEC, cellular, and dictionary encoding.

**Decide the product fork explicitly.** · *Open, and it is finding 2 restated as a decision rather than as a gap.* R-15-162 declines chiplets and bonded die-stacking outright, and R-15-163 makes the monolithic vertical lever conditional on an unsolved low-temperature p-type device result. Accepting authenticated external or bonded memory reopens R-15-162, which is a deliberate refusal carrying a stated ground, so this is not a free choice between two equally open options.

---

**What remains concretely closeable:** wrong responses to failed verdicts, runtime-dependent Tier-2 overflow, rollback of security-sensitive app state, and non-atomic package recomposition.

Analog power and EM leakage, human consent, protocol-standard flaws, and fail-closed denial remain honestly recorded as residuals rather than overlooked bugs.
