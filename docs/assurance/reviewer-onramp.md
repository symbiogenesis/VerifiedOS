# The Reviewer's Onramp

*Non-normative guidance for an independent reviewer familiar with formal methods and new to this repository. The [requirements register](../requirements-register.md) governs; this guide states no obligation and supplies no review evidence (R-05-150a).*

## 1. What is being reviewed, and what is not

The gate audits **the register**, entry by entry (R-05-150, R-05-152). Review records cite requirement IDs.

- [spec.md](../spec.md) supplies rationale and worked arguments. Use it to understand an obligation; decide the obligation against its register entry.
- Derived views such as the [coverage matrix](coverage-matrix.md), [crown jewels](crown-jewels.md) and [absence contract](../hardware/absence-contract.md) add no obligations. A disagreement belongs to the requirement from which the view derives (R-15-001a).
- Executable Sail semantics alone establish neither a property of those semantics nor hardware refinement. Consult the [crown-jewel status](crown-jewels.md) and [implementation checklist](../implementation/implementation-checklist.md) for the corresponding artifacts.
- Complete extraction is a claim to review: look for normative obligations omitted from the register, not only defects in existing entries (R-05-151).

## 2. How to read one entry

Start with the register's [entry format and reading rules](../requirements-register.md#how-to-read-this), which define modalities, acceptance criteria, conferrals and traces. Apply them by asking:

1. Does each acceptance criterion decide the obligation? All criteria must hold. `IS` entries classify or define; review their correctness rather than asking whether they are implemented.
2. Does the entry contain the facts needed for that decision? Opening the prose for an explanation is normal; needing an unstated fact from it is a finding. A clause that contributes nothing should be deleted or made testable, regardless of the entry's length.
3. Does the obligation need a `· Fail-closed:` or `· RoT-fresh:` declaration? These lines confer membership in the fail-closed seam register and freshness enumeration. The checker catches disagreement between declarations and collected sets; the reviewer must still detect missing declarations on both sides.
4. Does the named crown-jewel specification match the obligation? The trace's prose bookmark derives from the requirement ID. The checker resolves that reference; deciding whether the linked text supports the entry remains a reading task.

## 3. Conventions that can look like errors

The [register preamble](../requirements-register.md#how-to-read-this) owns the permanent-ID, prose-order and derived-fact conventions. Read it before treating a numerical gap, letter suffix, struck entry or reference to another entry's set as a defect. The [critique](../background/critique.md) considers what frequent insertions imply for review stability.

Counts and collected sets belong to their defining artifacts. Use the checker to detect stale derived figures; review the source of a figure instead of recounting its copies. A missing generator or an incorrectly chosen source still needs a finding.

Resolve section references by reading their targets. K-13 establishes only that some document has the numbered heading; it cannot decide which document the sentence intended.

## 4. The co-read ledger, and what blessing means

The ledger records that a register entry and its cited prose were read together. Editing either side makes the pair stale, and K-61 reports the reading owed. The [`coread` command](../../tools/README.md#running-them) shows the pair and records a blessing.

**Blessing records a judgment; `--fix` cannot supply it.** As a reviewer, inspect the two texts for agreement rather than treating a recorded reading as proof that they agree. A green checker establishes that no reading is stale under this mechanism, not that the recorded judgments were correct. Reviewers need not bless entries themselves.

## 5. What the machinery cannot decide, and where you come in

The checker checks references, membership and arithmetic. It cannot decide whether an obligation is the right one. Read the [critique](../background/critique.md) for existing concerns, including criteria that check only the presence of a claim, enumerations whose completeness is assumed, and proofs against an inadequate specification. State where your assessment differs or what additional defect you find.

## 6. Review tools and validation evidence

The [command guide](../../tools/README.md#one-entry-point-and-the-commands-under-it) describes `coread` for paired readings, `view` for browsing the register with its prose, `rtl provenance` for absence bindings and `oracle list` for differential coverage. The [rule registry](../../tools/check-rules.md) states what each checker result means.

Use the [check schedule](../../tools/README.md#check-scheduling-during-fan-out) for validation and handoff, and the [CI contract](../../tools/ci/README.md) to interpret hosted evidence. Those documents own the workflow and its acceptance limits.

## 7. Where a finding goes

The [findings register](findings-register.md) indexes project findings against their plan owners. State a review finding against a requirement ID, identifying the defect:

1. **The obligation is wrong:** state the correction.
2. **The criterion does not decide the obligation:** state what it incorrectly admits or refuses.
3. **An obligation is uncaptured:** identify the normative prose with no register entry; this is an extraction defect (R-05-153).

A prose or derived-view defect must be connected to the affected obligation. An artifact recorded as unbuilt in the [crown-jewel status](crown-jewels.md) is not by itself a new specification defect; explain what is wrong with its stated obligation or acceptance criterion.
