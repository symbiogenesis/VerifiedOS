# The RTL correspondence boundary

*What a source-level circuit theorem reaches, and where the trusted seam sits between
that theorem and the bytes a synthesis tool reads. Q22d qualifies this boundary before
M10 claims the closing refinement.*

The [register](../requirements-register.md) owns the obligation. R-15-092's Accept
already fixes what an elected version records and already rules that generation and
byte reproducibility alone establish no correspondence; R-01-002a and R-01-002b own the
two tiers and rule that a tier is read off the artifacts admitted rather than asserted;
R-18-010 owns the rung ladder those artifacts sit on; R-15-091 keeps the Coq refinement
the closing vehicle and R-15-097 keeps the honest scope. This document adds no
obligation. It makes R-15-092's record fillable, fills it for the two blocks that exist
at this revision, and reports what the filling could not decide.

**It does not re-open the Kami election.** [The plan's
§11](../implementation/implementation-checklist.md#11-building-an-fpga-from-it-all)
and [THIRD-PARTY.md](../../THIRD-PARTY.md) keep Kami the default on licence ground and
state the per-block election test; nothing here disturbs either. It builds no HDL
verifier and attempts no RTL-to-Sail proof, which stay with the post-M10 refinement
owner.

## 1. Why the worked examples are not Kami blocks

Route (a) is not open. [The absence contract's
§8](../hardware/absence-contract.md#8-running-it-on-day-one) states it outright: for
Kôika and Kami blocks the six audit steps become one structural predicate over the Coq
term under R-15-102, and those blocks do not exist yet. The plan's §11 owes nothing on
that route before the co-simulation gate.

So the representative blocks are chosen from what exists, and both are authored or
generated SystemVerilog standing where a route-(a) theorem will stand. That reading is
not new here: [the provenance record's
§4a](../../rtl/synthesis-provenance.md#4a-the-tag-fabrics-route-recorded-so-it-is-not-derived-twice)
already took it for the tag fabric, ruling that R-15-092's *authored* is a statement
about the artifact of record rather than about every artifact that stands where it will
stand. What this document adds is the record such a standing artifact owes in the
meantime, so that the day a Kami block replaces it the two records are comparable rather
than differently shaped.

## 2. The record a block owes

One record per block, six fields, in this order. The first three say what is claimed and
the last three say over what.

| Field | What fills it | The wrong answer it is there to refuse |
| --- | --- | --- |
| Source semantics | The artifact whose meaning the block is correct against, named by path and by the revision it was read at | A language, a model family, or "the Sail model" with no file |
| Theorem endpoint | The named proof object and the two things it relates, or an `n/a` from the grammar below | A theorem name with no statement of what it does not reach |
| Emitter identity and revision | The program that writes the block's bytes and the revision of that program | "Generated", with no emitter named |
| Emitted bytes | What holds the block's bytes to that emitter's output, cited by the rule or record that holds them | A digest transcribed into this document, which is a derived fact with no owner |
| Synthesis input | The exact file set a synthesis or elaboration run reads, and its identity | The emitted bytes, where no run has read them |
| Tier reached | The tier under R-01-002a, named by the rungs of R-18-010 admitted for this block and the claims riding them | An adjective, or a tier raised on an intermediate rung |

**Three different things wear `n/a`, and the repair differs.** This is the grammar
[the provenance record's §1](../../rtl/synthesis-provenance.md#1-how-to-read-this)
already keeps for absences, met a second time on a different subject, and the reason to
keep it is the same: a field bound to nothing reads as discharged.

- **`n/a, by route`.** The block's route never has this field, so nothing is owed. A
  hand-authored SystemVerilog package has no emitter and no emitted bytes, and the seam
  it exposes is a transcription seam rather than an emission seam.
- **`n/a, not yet`.** The route has this field and no artifact fills it today. The row
  names who owes it. This is the only kind that is work.
- **`n/a, out of boundary`.** The field belongs to an artifact this record is not taken
  over. The row names that artifact.

A field carrying `n/a` with no kind and no ground is a finding, on R-15-092's own
reading: the record exists to keep an unchecked emission seam explicit, and an
unlabelled blank is exactly the seam going quiet.

## 3. Worked example A: the authored capability package

| Field | Value |
| --- | --- |
| Block | [`rtl/vos_cheri_pkg.sv`](../../rtl/vos_cheri_pkg.sv), the frozen capability format and its algebra |
| Source semantics | `model/model/core/cap_format.sail` and `model/model/core/cap_common.sail`, with `model/model/core/xlen.sail` fixing the register width the address field sits in. The five files the vector generator compiles against are declared in [the tool](../../tools/vos/cli/rtl.py); rule K-79 holds the package's declared parameters against the first three on the host |
| Theorem endpoint | `n/a, not yet`. No proof object relates this package to those files. Route (a) is the owner and the plan's §11 opens it after the co-simulation gate |
| Emitter identity and revision | `n/a, by route`. [The RTL tree's §2](../../rtl/README.md) lists this file authored, not generated. It was transcribed from the Sail source by hand |
| Emitted bytes | `n/a, by route`, on the same ground. There is no generator output to hold the tracked bytes against, which is why the transcription itself is the seam |
| Synthesis input | `n/a, not yet`. Nothing in the design instantiates the package and no elaboration of a core reaches it, as [the RTL tree's §3](../../rtl/README.md) records, so no synthesis input exists to identify. R1's curated datapath owes the first one |
| Tier reached | Evidence tier under R-01-002b, and below every rung of R-18-010. The rung list admitted for this block is empty: the crosscheck is neither rvfi, nor Sail-generated SystemVerilog under commercial FEV, nor an Isla obligation, nor a Coq refinement. The claim riding it is agreement with the model's own answers over the vectors that ran |

**What the evidence is.** `python tools/run.py rtl crosscheck` compiles the model with a
generator that calls its capability functions and prints what they return, builds this
package under Verilator behind [a harness](../../tools/cheri-equiv/) that replays those
lines, and compares the two texts. Two of its sweeps are exhaustive over their own
domain. That is a measurement of agreement, and R-15-092 already rules that a
measurement of this shape is not the checked correspondence a theorem-tier claim needs.

**Two things it is not, and the second is the seam.** It is not a proof, which the
register and the RTL tree both already say. It is also not independent of an authored
choice: the vectors are the model's own, but the harness is written in this repository
and decides which functions each vector kind drives. Five functions are named by no
vector, which [the RTL tree's §3](../../rtl/README.md) records by name. The coverage of
the slice is therefore an authored choice, and §5 below measures what that costs.

## 4. Worked example B: the generated address map

Example A has a correspondence instrument and no emitter. This block is the converse,
and it is the instance R-15-092's sentence about generation and byte reproducibility
names.

| Field | Value |
| --- | --- |
| Block | [`rtl/vos_soc_map_pkg.sv`](../../rtl/vos_soc_map_pkg.sv), the SoC address map |
| Source semantics | [The frozen profile's composition](../../model/config/verifiedos.json), which R-15-002b makes the artifact that fixes every base, size and permission |
| Theorem endpoint | `n/a, not yet`, and no owner is assigned. The map's meaning is its agreement with the model's `pmaCheck` in `model/model/sys/mem.sail`, and no artifact states that relation |
| Emitter identity and revision | [`tools/vos/socmap.py`](../../tools/vos/socmap.py), at this checkout's revision. It is tracked here rather than pinned upstream, so its identity is the tracked source and it carries no external revision |
| Emitted bytes | Held by rule K-88 as byte identity against what that emitter writes from the composition, decided on the host at every landing. Cited rather than transcribed: a digest copied into this document would be a derived fact with no owner |
| Synthesis input | `n/a, not yet`. The SoC top does not exist and neither half of it is authored, which [the RTL tree's §4](../../rtl/README.md) books with its two reasons |
| Tier reached | Evidence tier under R-01-002b, below every rung of R-18-010, and below example A on R-01-002b's own two-list test: the rung list is likewise empty, and the claim riding it is weaker, being byte identity with a generator's output rather than agreement with the model's answers |

**What K-88 decides and what it does not.** It decides that these bytes are what the
emitter writes from the composition, which makes the map a faithful transcription of its
source of record. It decides nothing about whether the addresses that composition fixes
are the addresses the model's own memory check reads, and nothing about whether the
decode authored over the map answers as `pmaCheck` answers: [the RTL tree's
§4](../../rtl/README.md) records that nothing holds the decode against the model. So the
emitter here is checked in exactly the sense R-15-092 rules insufficient, and this row is
that ruling with an instance under it rather than as a general caution.

## 5. The perturbation experiment

The acceptance test is that a changed emitted mux, reset or tag path is either rejected
by an independently checked correspondence slice or exposes a precisely recorded seam.
Four perturbations of example A were posed against `rtl/vos_cheri_pkg.sv`.

**Predicate and conditions.** Each trial copied the tracked package and the harness into
a scratch directory on the guest filesystem under this lane's build root, applied one
single-line edit to the copy, and replayed the lane's own `vectors.txt` through the
tool's own Verilator invocation. No tracked file was modified. A differing line is a line
of the model's own `vectors.txt` that the replay does not reproduce, counted as the left
side of `diff vectors.txt replay.txt`. Figures were taken on 2026-09-14 at revision
`9e2b56ab` in lane `q22d-rtlbound-20260914` under Verilator 5.052, the pin. The baseline
run is green and its population, 658,659 vectors over thirteen kinds across 658,662
lines, is the tool's own figure and is not restated here as a new measurement. A control
copy with no edit reproduced it at zero differing lines.

| Trial | The edit | Differing lines | Where | Verdict |
| --- | --- | --- | --- | --- |
| Mux | The two arms of the carry-out ternary in `enc_to_capability` swapped | 545,921 | `dec` 540,672, `ib` 3,249, `ac` 2,000 | Rejected |
| Reset | `CapResetE` decremented by one | 4,000 | `it` 2,000, `mb` 2,000 | Rejected |
| Tag, reached term | `clear_tag_if` made to ignore its condition | 9,645 | `so` 7,633, `sa` 2,012 | Rejected |
| Tag, exported wrapper | `clear_tag` made a no-op | 0 | n/a | **Not rejected** |

**The reset substitution is recorded rather than assumed.** This package declares no
sequential logic, so it has no reset signal. What it has is the reset capabilities as
localparams, and `CapResetE` is the field a reset-path defect would move, so that is the
limb the trial perturbs. The rejection is carried by the two kinds that exercise the
reset capabilities and by no other kind.

**The fourth trial is the item's point, and it is narrower than it first reads.** The tag
path is not unheld: `clear_tag_if` carries the tag-clearing term the package's reached
functions use, and moving it is rejected on 9,645 lines. What is unheld is `clear_tag`,
the one-line exported wrapper. No vector drives it, no other function in the package
calls it, and neither the adapter nor the harness references it, so a package that never
clears a tag on that entry point reproduces the model line for line. The seam is
therefore not "tag paths are not covered" but the exact statement: **the harness's
function selection is an authored choice, and an exported entry point outside that
selection is held by nothing.** Its residue is the five functions [the RTL tree's
§3](../../rtl/README.md) already names, and this trial measures what that residue costs
at one of them.

**Source-level correctness alone does not pass, and the fourth trial is the witness.**
The model's own `clear_tag` is correct and unperturbed in every trial. That fact reaches
nothing about the SystemVerilog, because no vector drives the SystemVerilog function it
would correspond to. A correspondence claim resting on the source side alone would report
this package as agreeing where it does not.

**Lint is not a correspondence check, and this is what that means concretely.** All four
perturbed packages lint clean under the same flags `python tools/run.py rtl lint` uses,
exit zero with no warning a package can answer, including the two the crosscheck rejects
on half a million lines. A green lint decides that a source compiles and that no warning
class fires; it reads no model, replays no vector, and can decide no agreement. Nothing
in the tree claims otherwise; it is recorded here because a reader auditing this boundary
will meet the lint gate first.

**The instrument has no source override.** `run.py rtl crosscheck` reads the format
package from the checkout unconditionally, so there is no supported way to ask it about a
perturbed source, and each trial above replicated its Verilator invocation by hand. That
absence is reported and not repaired: Q22d prices boundary qualification and a bounded
experiment, not a tool mode.

## 6. The candidate DSLs

Each row's emitter and correspondence reading is the pinned upstream evidence recorded in
[the hardware proof-reuse records](proof-reuse/hardware.md) and dispositioned in [the
alternatives entry on hardware-description
languages](../background/architectural-alternatives.md); this table is the tier that
evidence implies for a block authored today and carries no second copy of the readings.

| Candidate | Emitter | Checked correspondence result covering that emitter | Tier a block authored in it reaches today |
| --- | --- | --- | --- |
| Kami (HW-07, MIT, pin `3f9c603a`) | Bluespec extraction, described separately from the proofs in the upstream README | None. `fetchDecode_refines_fetchNDecode` and the FIFO and cache refinements relate Kami terms, and HW-07 records that a theorem over Kami semantics does not cover Verilog emission or synthesis | Evidence tier, with the extraction and the Bluespec compiler as named trusted tools. The theorem reaches the Kami term and stops there |
| Kôika (HW-08, LGPL-2.1, pin `8921e304`) | A verified compiler to circuits, followed by an unverified RTL-emission layer | Partial, and the part it covers is the wrong end. `compiler_correct` relates a scheduled rule cycle to the compiled register-output circuits; the emission layer below it is unverified by the project's own overview | Evidence tier. The circuit theorem is stronger than Kami's on the compiler leg and reaches the same stopping point at the emitted RTL |
| Cava, Silver Oak shaped (HW-09, Apache-2.0, pin `cccfdb4e`) | A Cava-to-SystemVerilog compiler, which Silver Oak's own README excludes from what it verifies | None, and the exclusion is the project's own statement rather than an inference | Evidence tier. No gitlink is pinned here and [THIRD-PARTY.md](../../THIRD-PARTY.md) reads no Cava terms, so a block authored in it would owe a licence reading at the milestone that incorporated it |

**The three rows agree on the finding and that is the point.** No candidate's circuit
theorem covers its own emitter, so on this boundary the election is not decided by
emission evidence, and the licence ground the plan's §11 states is untouched by anything
here. What each row changes is the size of the seam a block leaves, not whether it leaves
one, and the record of §2 is what keeps that size written down.

## 7. What this document could not decide

- **Nothing in the register requires this record.** R-15-092's Accept states its fields
  for an elected version and no entry makes the record a required artifact the way
  R-15-100a makes the absence contract required. Making it one is a register act, either
  a new entry or an amendment to R-15-092's Accept, and it belongs to the register's
  owner rather than to this document.
- **The register states no tier below evidence tier.** R-01-002a admits two tiers and
  R-01-002b decides between them by two lists, the rungs admitted and the claims riding
  them. So the acceptance predicate's *lower evidence tier* is read here as a shorter
  rung list and a weaker claim, which is what §3 and §4 record, rather than as a third
  tier this document would be inventing. If a sub-tier is wanted, that is a register act.
- **R-18-010's rungs are stated per core.** Both worked examples are packages rather than
  cores, and no rung of that ladder admits a package, which is why both rung lists are
  empty rather than short. Extending the ladder to non-core blocks, or ruling that it
  deliberately does not reach them, is the register's to decide.
- **No theorem endpoint is owed to the address map by any artifact.** §4's second row
  names the relation and no owner. Assigning one is the plan's act, not this document's.
