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

---

**Radical Simplifications, dispositioned**

**Scalar "VerifiedOS Core" first.** · *Open, no decision recorded.* This is finding 1's sequencing argument applied to the artifact rather than to the proof. It collides with R-15-007d's *the width is permanent*: every capability in the immutable image and every sealed blob is stored in the frozen format, so a later width change invalidates stored authority wholesale rather than costing a recompile. *Add the narrowed format only after a measured failure* is therefore unavailable for that one item, whatever its merit for the matrix unit, FEC, cellular, and dictionary encoding.

**Decide the product fork explicitly.** · *Open, and it is finding 2 restated as a decision rather than as a gap.* R-15-162 declines chiplets and bonded die-stacking outright, and R-15-163 makes the monolithic vertical lever conditional on a low-temperature p-type device result that laboratory work has reached and array-grade manufacturing has not. Accepting authenticated external or bonded memory reopens R-15-162, which is a deliberate refusal carrying a stated ground, so this is not a free choice between two equally open options.

---

**What remains concretely closeable:** nothing on this list. Findings 1 and 2 are product and sequencing decisions, and finding 3 waits on an unauthored artifact.

Wrong responses to a failed verdict, runtime-value-dependent overflow, analog power and EM leakage, human consent, protocol-standard flaws, and fail-closed denial remain honestly recorded as residuals rather than overlooked bugs.
