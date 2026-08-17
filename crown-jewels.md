# The Crown-Jewel Inventory

*Normative as a **view**. This document is the artifact **R-17-016a** mandates and R-05-046, R-05-076, R-08-028, R-12-043c, R-15-221, R-17-012, and R-17-016 depend on: the enumerated inventory of crown-jewel specifications. It is **derived from** [requirements-register.md](requirements-register.md), which remains the audited artifact per R-05-152.*

> **Precedence.** Where this document and the register disagree, **the register wins and this document is defective.** Every row cites the requirements that govern it. This document adds no obligation of its own.

## Why this document exists

Eight acceptance criteria decide membership in *the crown-jewel inventory*: R-05-046 ("the descriptor set is enumerated in the crown-jewel inventory"), R-05-076 ("each primitive's functional specification is in the crown-jewel inventory"), R-08-028, R-12-043c ("the inventory carries one row per reference model"), R-15-221, R-17-012 ("both appear in the crown-jewel inventory"), R-17-016, and R-05-151 (every requirement traces "to the crown-jewel spec it constrains"). This document is the inventory all eight quantify over; without it none of them is decidable.

Membership is **conferred, never declared in bulk**: a specification is a crown jewel because some requirement says a proof against it cannot check it, so no single entry can hold the list and R-17-016 does not try to. What stays distributed is the conferral; what is collected here is the set.

Two adjacent artifacts are sometimes mistaken for this one, and neither is an inventory:

1. the register's **`CJ-` trace-target table**, 21 entries, all used, internally consistent, but a *legend of trace targets* rather than an enumeration of specifications (below);
2. the **conferring requirements**, the entries whose own text asserts crown-jewel status, scattered across §5, §8, §10, §11, §12, §15, and §17. There are twenty-five such entries; each confers the status on one specification or speaks about the set, and not one of them states the membership.

Those requirements *are* the membership, and this table is the only place they are collected. The agreement runs both ways and is mechanical: `tools/check.ps1` reports a conferring requirement this document fails to carry, a row no conferring requirement stands behind, and a row citing an identifier the register does not hold.

## Why it matters for implementation

A crown jewel is a **specification that must be authored**, not a proof to be discharged. R-17-016's residual is that *proofs match the spec, never intent*, so a wrong crown jewel yields a correct proof of the wrong property, and no amount of proof effort detects it. That makes this inventory two things at once:

- **the review gate's subject.** R-05-150 gates release on independent specification review, and the crown jewels are what that review reads. R-18-032 calls the composition statement *"the review artifact the crown-jewel gate most needs"*: that gate needs a defined scope, which is this.
- **the specification work list.** Every row is an artifact someone writes before the corresponding proof workstream can begin. The **Status** column is therefore the honest count of how much of the specification half exists.

## The inventory

**Status** is `authored` where the artifact exists in this repository, `partial` where it exists but is incomplete or not yet in its final vehicle, and `not authored` otherwise. Status is a claim about *this repository*, not about the literature. In the **Constrained by** column, the requirement whose conferral the row collects is set in bold; the rest constrain the specification without conferring the status.

| # | Crown-jewel specification | `CJ-` target | Constrained by | Status |
| --- | --- | --- | --- | --- |
| 1 | **The apex theorem T**, the statement itself, with all four elements: the quantifier over adversary sets *C*, the value-and-timing-and-architectural observation, the *modulo D* clause, and the *relative to Ax* clause | `CJ-T` | **R-05-156**, R-05-157, R-17-065 | **authored**: [ApexTheorem.v](proofs/ApexTheorem.v), with the nine seam-lemma statements; its interface vocabularies are parameters, bound as the rows carrying them are authored |
| 2 | **The security policy model**, including the delimited-release bound and the robust-declassification statement | `CJ-NI` | **R-08-028**, **R-17-012** | not authored |
| 3 | **The IDL wire-format mapping**, the profile's mapping, the contract the IDL's types only document | `CJ-IDL` | **R-12-013** | not authored |
| 4 | **The frozen ISA-profile definition** | `CJ-SAIL` | R-15-001, **R-15-001a**, R-15-014 | **authored**: [isa-profile.md](isa-profile.md) |
| 5 | **The `Zkt`/`Zvkt` leakage-model statement**, the single leakage model constant-time verification is stated against | `CJ-LEAK` | **R-15-053**, R-05-070 | partial: enumerated in the profile (§2); the instruction list itself rides the ratified `Zkt`/`Zvkt` definition |
| 6 | **The frozen profile's Sail semantics**: the Ztso and static-prediction fetch statements, the frozen matrix-extension semantics, the **re-parameterized capability encoding** with its representation-correctness proof and enumerated permission lattice, and the native tag-bit layout, one model rather than three | `CJ-SAIL`, `CJ-RTL-SAIL` | **R-15-005**, R-15-004, R-15-016, R-15-019, R-15-086, R-15-095, R-15-009, R-15-116, R-15-117, R-15-118, R-15-175, R-15-035, R-15-007, R-15-007a, R-15-007b, R-15-007e, R-15-007f, R-15-067a, R-15-067c | partial: each is stated in prose by the profile (§1, §2, §3, §4.1, §6, §7); no Sail-model statement of any of them is authored, and the capability encoding, the indexed load/store, and the bitfield extract/insert are original authorship rather than curation of the upstream model |
| 7 | **The `fence.t` flush-set statement**, now over one structure rather than two | `CJ-ISOL` | R-15-213, R-15-215, R-15-217, **R-15-221** | partial: the four-class map is carried in [absence-contract.md](absence-contract.md) §6; the Sail statement is not authored |
| 8 | **The NoC/island isolation model**, whose non-interference statement is what temporal isolation is decided against, including the memory controller's per-island arbitration carrying TDM-NoC-class non-interference in the Sail model | `CJ-ISOL` | **R-15-211**, R-15-222, R-15-223, R-15-228 | not authored |
| 9 | **The bank/macro/tier→island binding map**, landing in the attested static devicetree | `CJ-ISOL`, `CJ-DEVTREE` | **R-15-228**, R-15-211 | not authored |
| 10 | **The wire-format inventory and its Narcissus descriptors**, every attacker-facing format with its descriptor, each descriptor a member per R-05-046: the ASN.1 UPER/aligned-PER RRC grammars and the 802.11 MLME element grammars, the IEI/TLV 5G-NAS grammar (**hand-transcribed**, and carrying differential-oracle coverage as its retirement mechanism, per R-05-050), the USB grammars, the image, media, font, archive, and document formats, and the pack and manifest descriptors | `CJ-FORMAT` | R-05-042, **R-05-046**, R-05-050, R-12-024f, R-13-009, R-18-029 | not authored |
| 11 | **The OPP / mode schedule statements**, R-11-017's one artifact with three outputs: the OPP assignment, the TDM NoC schedule, and the watchdog windows, one admission-proved instance per global mode | `CJ-WCET`, `CJ-ISOL` | **R-11-017**, R-11-018, R-17-005 | not authored |
| 12 | **The reset/power sequence table**, fixed, composition-time, dependency-ordered, in the attested devicetree | `CJ-DEVTREE` | **R-15-198** | not authored |
| 13 | **The calibration-manifest schema** | `CJ-DEVTREE` | **R-15-127**, R-17-062 | not authored |
| 14 | **Each primitive's abstract functional specification**, the join point of the three-layer crypto proof, where layer-1/2 refinement and the layer-3 game meet | `CJ-CRYPTO-SPEC` | **R-05-076**, R-05-059, **R-10-025**, **R-17-049** | not authored |
| 15 | **The timing-annotated Sail model's latency magnitudes** | `CJ-WCET` | **R-17-041**, R-15-095, R-18-024 | not authored |
| 16 | **The Lustre program and the control/data boundary** | `CJ-VELUS` | **R-17-044**, R-05-052, R-12-002 | not authored |
| 17 | **The static whole-program slot plan** and its live-range colouring | `CJ-MEMPLAN` | **R-08-011**, R-08-018, R-15-060 | not authored |
| 18 | **The verified HAL's hardware contracts** and DMA/descriptor postconditions | `CJ-HAL` | **R-05-082**, R-05-083, R-05-138, R-18-018 | not authored |
| 19 | **The NR RRC reference state machine** | `CJ-VELUS` | R-12-043b, **R-12-043c** | not authored |
| 20 | **The 5G NAS reference state machine**, including 5G-AKA | `CJ-VELUS` | R-12-043b, **R-12-043c** | not authored |
| 21 | **The 802.11 MLME reference state machine**, including the WPA3/SAE handshake | `CJ-VELUS` | R-12-043b, **R-12-043c** | not authored |
| 22 | **The BT L2CAP/GATT pairing reference state machine** | `CJ-VELUS` | R-12-043b, **R-12-043c** | not authored |

Two rules decide how finely conferral is cut, and they cut in opposite directions. **A row is one specification, never one clause of one** (R-17-016a: *one row per crown-jewel specification*), so where a single artifact carries several statements it is one row: row 6 is the frozen profile's Sail model, not three rows for the three statements it will make, and row 8 is the isolation model, not a row per mechanism inside it, because R-15-211 makes non-interference *"decided against the isolation model's non-interference statement rather than against the list of mechanisms above it"* and a row per mechanism would reinstate that list. **But where a requirement confers per member, the members are rows**, which is why rows 19–22 are four and not one: R-12-043c confers *per protocol rather than per stack* and its acceptance criterion requires the inventory to carry **one row per reference model**, since it is a particular standard's state machine a particular sequencer is proved to refine. Row 10 sits between the two: R-05-046 confers on each descriptor individually, but the descriptor set is not knowable until R-05-042's inventory exists, so the row carries the enumeration obligation and names the member classes, and the per-descriptor enumeration lands in it as that artifact is authored. Row 14 shares that shape: R-05-076 confers on each primitive's functional specification, and the per-primitive enumeration lands with the crypto inventory R-05-059 requires.

## The theorem targets

The remaining seven `CJ-` targets name **theorems, not specifications**, things proven rather than authored. They are not crown jewels in R-17-016's sense (a specification whose *correctness is unverifiable*, so that a proof matching it may still miss intent); a theorem's correctness is exactly what its proof establishes. They are listed here so that all 21 targets are accounted for, and because each one's premise includes a specification above, which is the seam structure R-18-031(a)'s machine-checked statement has to align.

| `CJ-` target | Theorem | Proven against |
| --- | --- | --- |
| `CJ-COMPCERT` | CHERI-CompCert correctness | CompCert C semantics ⋈ the frozen ISA profile (row 4) |
| `CJ-SECOMP` | Robust preservation of compartment isolation by the verified compiler | the policy model (row 2) |
| `CJ-KERNEL` | Kernel functional refinement: seL4's endpoint model and non-interference statement re-proved in Coq, the rest of the object model deleted (R-07-001) | the kernel's abstract specification ⋈ the slot plan (row 17) |
| `CJ-CERISE` | The Cerise universal contract | the ISA profile and its Sail semantics (rows 4, 6) |
| `CJ-TAL-SOUND` | CHERI-TAL soundness: well-typed ⇒ safe over the Sail model | the ISA profile and its Sail semantics (rows 4, 6) |
| `CJ-CT-SOUND` | Constant-time type soundness over the leakage model | the `Zkt`/`Zvkt` statement (row 5) |
| `CJ-REDUCTION` | The IND-CCA / EUF-CMA reductions | each primitive's functional specification (row 14) |

The split is the reason the inventory and the trace legend cannot be the same artifact. **A theorem with no specification to be proven against is not a deliverable**, so every row in this table depends on a row in the one above, and seventeen of those twenty-two are not authored.

## What the `CJ-` table is, and is not

The register's `CJ-` table is **healthy and should not be conflated with this inventory**: 21 targets, every one used by at least one `Trace:` line, none orphaned. But it is a *trace legend* (a controlled vocabulary letting each requirement name the specification it constrains) and its granularity is deliberately coarser than the inventory's. `CJ-FORMAT` is one target covering every Narcissus descriptor; `CJ-CRYPTO-SPEC` is one target covering every primitive's functional specification. R-05-046 and R-05-076 require the *members* to be enumerated, which a trace legend cannot do without one target per member.

So the two artifacts answer different questions and both are needed:

| Artifact | Question it answers | Granularity |
| --- | --- | --- |
| `CJ-` table (in the register) | *which crown jewel does this requirement constrain?* | 21 coarse targets |
| This inventory | *what are the crown jewels, and does each one exist yet?* | 22 specifications, per-member where a requirement demands it |

## Standing obligations

- **The list is closed by amendment** (R-17-016). A requirement asserting crown-jewel status for a specification absent from this table is a review-gate finding, not a silent addition; that is what closure can mean where membership is conferred entry by entry, and `tools/check.ps1` reports the violation in both directions rather than leaving it to a reader's roll-call.
- **Every crown jewel is subject to independent review** under R-05-150 (R-05-046, R-08-028, R-15-221).
- **Every crown jewel has a `CJ-` trace target** used by the sections that constrain it (R-17-016). The Constrained-by column is that check made visible.
- **Status is maintained, not asserted once.** The inventory is revved with the register (R-18-034), and a status that moves from `not authored` without an artifact link is a finding.

## Reading the status column

Two of twenty-two are authored outright (row 4, the frozen ISA profile, and row 1, the apex theorem's machine-checked statement), and three more are partial: rows 5, 6, and 7, each carried in part by a day-one deliverable of R-18-003b. Seventeen are not authored.

That ratio is the specification half of R-01-003's honest position: the as-specified assurance is very high because these twenty-two are *named, constrained, and traced*; the as-existing assurance is low because seventeen of them are not yet written, and the seven theorem targets above cannot start until their premises are. The inventory does not change the ratio: it makes it countable, which is what R-18-032 means by turning *"a dozen things are proven"* into *"the conjunction claims exactly this, and rests on exactly that."*

**The column is a burn-down with a stated direction, not a census.** The obligation count rises with every hardening, each one adding a row, and falls only when an artifact is authored, so the ratio is read for its direction over the git history rather than as a snapshot: `tools/check.ps1` recomputes the classes at each edition, and the [implementation plan](implementation-plan.md)'s milestones are the retirement mechanism, each flipping the rows whose artifacts it lands (M0's curated Sail model alone bears on rows 6, 7, and 15). A run of milestones that flips no row is the column reporting that the specification half is not being discharged, which is what the inventory exists to make visible.
