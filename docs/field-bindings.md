# The Field-Binding Map

*Normative as a **view** of [ApexTheorem.v](../proofs/ApexTheorem.v), the machine-checked statement R-18-031(a) makes the coverage checklist: every side-property some seam consumes or concludes is a Prop field of the statement's `Vocabulary` record, a proof workstream lands by instantiating its field, and a field nothing instantiates is an uncovered obligation with exactly one name. This document is that checklist laid out as a table, one row per Prop field, so that coverage and blast radius are read rather than reconstructed.*

> **Precedence.** The mechanical half of every row (the field list, its order, and the **Consumed by** column) is derived from the `.v`, which wins; `tools/check.ps1` recomputes it on every run and fails this document where it drifts. The semantic half (**Authored by**) is hand-authored and answers to [requirements-register.md](requirements-register.md), which wins over both this document and the statement's own comments. This document adds no obligation.

## How to read a row

- **Consumed by** lists every definition of the statement that touches the field: a seam lemma that takes it as premise or concludes it, the substrate or tower conjunction that carries it, the `Ax` ledger, or a record coercion. This is the blast-radius column: an edit that changes what a field *states* re-opens exactly the definitions listed, and nothing else, which is what entitles a workstream behind one field to refactor freely against a fixed statement. `tools/blast-radius.ps1` answers the same question as a query, with the seam-to-seam trail shown.
- **Authored by** names the artifact that gives the field its meaning: a crown-jewel inventory row (see [crown-jewels.md](crown-jewels.md)), a theorem target, or the register entry that states it. Proofs against a wrong authoring artifact match it rather than check it, so this column is review-gate subject matter, not a tool's.
- **Instantiated by** names the proof development that discharges the field, linked, or `none yet`. A row reading `none yet` is R-18-031(a)'s uncovered obligation, named. Today every row reads `none yet`: no proof workstream has landed, which is the honest position the [crown-jewel inventory](crown-jewels.md) counts from the specification side.

## The bindings

| Field | Consumed by | Authored by | Instantiated by |
| --- | --- | --- | --- |
| `spatial_safety` | `seam_attestation_capability_safety, substrate_invariants` | the Cerise universal contract, `CJ-CERISE` (R-05-159) | none yet |
| `temporal_safety` | `substrate_invariants` | revocation under the CHERI-TAL linear-capability discipline (R-05-159) | none yet |
| `wx_exclusivity` | `substrate_invariants` | the derivation-forest W^X invariant (R-05-159) | none yet |
| `write_before_read` | `substrate_invariants` | definite initialization over eager-zeroized memory (R-05-159) | none yet |
| `source_refines_spec` | `refinement_tower` | the tower's first rung (R-05-158); `CJ-KERNEL`, `CJ-COMPCERT` | none yet |
| `binary_refines_source_robustly` | `refinement_tower` | the tower's second rung (R-05-158); `CJ-COMPCERT`, `CJ-SECOMP` | none yet |
| `binary_against_sail` | `refinement_tower` | the tower's third rung (R-05-158); R-05-023's translation validation | none yet |
| `rtl_refines_sail` | `refinement_tower, seam_ct_rtl_sail` | the tower's fourth rung (R-05-158); `CJ-RTL-SAIL` | none yet |
| `explicit_flow_noninterference` | `seam_ni_timing` | the flow theorem over row 2's policy model (R-08-026) | none yet |
| `timing_isolation` | `seam_ni_timing, seam_wcet_isolation` | the isolation model's non-interference statement, rows 7 and 8 (R-08-027, R-15-211) | none yet |
| `partition_guarantee` | `seam_ni_timing` | the composed partition-level guarantee (R-08-027) | none yet |
| `wcet_bounds_sound` | `seam_wcet_isolation` | bounds read off typing derivations (R-05-102); magnitudes from row 15 | none yet |
| `composed_schedulability` | `seam_liveness_schedulability, seam_wcet_isolation` | the admission-proved schedule, row 11 (R-11-017) | none yet |
| `constant_time_typed` | `seam_ct_rtl_sail` | `CJ-CT-SOUND` over row 5's leakage model | none yet |
| `constant_time_on_die` | `seam_ct_rtl_sail` | the same claim transported to the RTL of record (R-17-042) | none yet |
| `cheri_tal_soundness` | `seam_cheri_tal_sail` | `CJ-TAL-SOUND` over rows 4 and 6 | none yet |
| `admission_type_check` | `seam_cheri_tal_sail` | the R-06-008 on-device checkers, rooted at R-06-014 | none yet |
| `admitted_binaries_safe` | `seam_cheri_tal_sail` | the fourth seam's conclusion (R-05-160) | none yet |
| `crypto_reductions` | `seam_crypto_hardness` | `CJ-REDUCTION` over row 14's functional specifications | none yet |
| `ae_ind_cca_int_ctxt` | `seam_ae_noninterference, seam_crypto_hardness` | the AE property at row 14's join (R-17-049, R-10-025) | none yet |
| `storage_noninterference` | `seam_ae_noninterference` | the filesystem data-noninterference claim (R-10-025) | none yet |
| `verifiable_encryption` | `seam_ae_noninterference` | R-10-025's composed claim | none yet |
| `kernel_liveness` | `seam_liveness_schedulability` | `CJ-KERNEL`'s progress half | none yet |
| `progress_guarantee` | `seam_liveness_schedulability` | the no-stall claim (R-05-161), observable per R-08-027a | none yet |
| `declassified_flows_authorized` | `seam_consent_declassification` | the seventh seam's conclusion, at T's own D (R-05-156, R-05-162) | none yet |
| `init_realizes_topology` | `seam_attestation_capability_safety` | the initialisation refinement (R-07-028) | none yet |
| `attestation_chain` | `seam_attestation_capability_safety` | the measured boot chain (R-05-161a) | none yet |
| `image_binding` | `seam_attestation_capability_safety` | the two-halved boot binding (R-05-161a) | none yet |
| `die_matches_rtl` | `ax_machine_carries_die_matches_rtl` | an element of Ax's machine class (R-05-162, R-05-162a) | none yet |
| `hardness_conjectures` | `ax_hardness_carries_conjectures, seam_crypto_hardness` | MLWE/MSIS and ECDLP/CDH (R-17-049) | none yet |
| `consent_correctness` | `ax_human_carries_consent, seam_consent_declassification` | the human class of Ax (R-17-013, R-17-013e) | none yet |
| `Ax_machine` | `Ax, ax_machine_carries_die_matches_rtl` | the machine class of the R-18-031(c) ledger (R-05-162a) | none yet |
| `Ax_hardness` | `Ax, ax_hardness_carries_conjectures` | the hardness class of the same ledger (R-05-162a) | none yet |
| `Ax_human` | `Ax, ax_human_carries_consent` | the human class of the same ledger (R-05-162a) | none yet |

## Standing obligations

- **The mechanical half is never edited by hand toward a wish.** A `Consumed by` cell disagreeing with the statement is repaired by re-deriving it from the `.v`, or the statement itself is wrong and that is an amendment to the statement, decided at the review gate.
- **An instantiation is a landing, not a claim.** A cell that moves off `none yet` links the proof development that discharges the field, and the linked artifact answers to `tools/proof-gate.sh` like everything shipped under [proofs](../proofs/).
- **A new field is a new row before it is anything else.** `check.ps1` fails the view that lags the record in either direction, so the checklist property (every obligation has exactly one name) survives amendment mechanically.
