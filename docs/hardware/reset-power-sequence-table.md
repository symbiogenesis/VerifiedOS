# The Reset/Power Sequence Table and Second-Class Discharge Rider

> Crown-jewel specification for inventory rows 12 and 26 ([the crown-jewel inventory](../assurance/crown-jewels.md)): the fixed, composition-time, dependency-ordered reset/power sequence table (`R-15-198`, `R-15-198a`, `R-15-228h`, `R-15-228i`) and its integral second-class discharge and admission rider (`R-15-247d`, `R-15-247e`, `R-15-247f`, `R-15-247q`, `R-15-247t`, `R-15-190b`), together with its symbolic chain-latency composition contract (`R-09-006b`).
> Where this specification and [the requirements register](../requirements-register.md) disagree, the register governs and this specification is defective.

## 1. Scope and Artifact Ownership

Row 12 (`R-15-198`, `R-15-228h`, `R-15-228i`) and Row 26 (`R-15-247d`, `R-15-198`, `R-15-247e`, `R-15-247f`, `R-15-247q`) share one composition-time sequencing artifact because the second-class discharge and admission ordering rides the reset/power sequence table rather than standing beside it. Keeping both rows explicit prevents folding R-15-247d's security ordering into generic dependency edges.

| Artifact | Role | Governing obligations |
| --- | --- | --- |
| [reset-table.schema.json](../../interfaces/reset-table.schema.json) | Strict JSON Schema (`additionalProperties: false`, non-coerced integers) for composition tables | R-15-198, R-15-198a, R-15-247d, R-15-247t, R-15-190b, R-09-006b |
| [reset_table.py](../../tools/vos/reset_table.py) | Host validator combining schema checks, duplicate-key rejection, and all semantic predicates | R-15-198, R-15-198a, R-15-228h, R-15-228i, R-15-247d, R-15-247t, R-15-190b, R-09-006b |
| [test_reset_table.py](../../tools/tests/test_reset_table.py) | Positive and single-defect negative control suite covering every obligation | R-05-165, R-05-166 |
| [ResetTable.v](../../proofs/ResetTable.v) | Gallina model of cold walk, release points, staging, entropy order, suffix riders, socket transitions, and symbolic latency sums | R-15-198, R-15-198a, R-15-228h, R-15-228i, R-15-247d, R-09-006b |
| [DischargeSequence.v](../../proofs/DischargeSequence.v) | Gallina model of single-pass discharge, retained in-place re-entry, and loader-filled OFF-image extents | R-15-247d, R-15-247e, R-15-247f, R-15-247q, R-15-190a, R-15-190b |
| [MemoryPlan.v](../../proofs/MemoryPlan.v) | Gallina model of power vector, domain-to-island map, and R-15-247t provenance/kind derivation | R-15-247t, R-15-189f, R-15-228 |

## 2. Composition Structure (Row 12)

A composition reset/power sequence table fixes at composition time:

1. **Modes, islands, and power vector.** Each mode (`cold`, `normal`, `standby`, `lock`, `sleep`, `recovery`) declares per-island residency (`island_resident`) and per-domain power state (`ON`, `RETAINED`, `OFF`) in `power_vector`, matching [MemoryPlan.v](../../proofs/MemoryPlan.v#PowerVector).
2. **Domain bindings and R-15-247t retention labels.** Every second-class domain binds to one island, declares its physical arena `[lo, lo + len)` and held regions, and carries `retention_label` (`image_derived` or `session_derived`) matching its `arena_label` and derived from its held regions (`named_session_kind`, `from_image`, and `cap_store_granted`). A `session_derived` domain is `ON` when its owning island is resident and `OFF` otherwise; `RETAINED` is forbidden for `session_derived` domains in every mode.
3. **Fixed release points and staging (`R-15-198a`).** On the cold path and at every declared entry suffix, each `island_release(i)` follows `domain_ready(d)` and `domain_complete(d)` for every domain `d` bound to island `i` and for no other island. Every bound island is released on the cold path. Shell and ahead-ordered islands (`ahead_islands`) release ahead of any composed `inference_island` and ahead of that inference island's `image_derived` fill completions.
4. **Concurrent start-up entropy health tests (`R-09-006a`, `R-15-198a`).** `entropy_tests_begin` stands immediately after `rot_rail_up`, runs across `clock_spine_lock` and `memory_controller_up`, and extends `entropy_verdict_extended` before any `draws_entropy` or `island_release`.
5. **Hardware ready gating (`R-15-198`).** Every table step names its hardware ready indication (`ready_signal`) and its watchdog timeout symbol (`watchdog_bound_sym`); the RoT firmware executes the table as the sole sequencer.

## 3. The R-15-247d Discharge and Admission Rider (Row 26)

Every reset, wake, mode-exit, and OFF-to-ON transition involving a second-class domain carries the four-stage `R-15-247d` rider integrally on every suffix entry in `suffix_entries`:

| Stage | Rider step | Obligation |
| --- | --- | --- |
| 0 | `requesters_held` | Every application core, DMA engine, and fabric initiator that can address the domain is held in reset (`R-15-247h`). |
| 1 | `tag_discharge_confirmed` | Tag plane authority invalidation is confirmed by single-pass discharge + fixed worst-corner dwell + single fail-stop read (`R-15-247d`, `R-15-247e`, `R-15-247f`), or by reading every tag clear in place on a verified `R-15-190b` retained re-entry. |
| 2 | `requester_addressable` | Requesters may address the domain only after Stage 1 completes. |
| 3 | `data_sanitization_confirmed` | Data plane sanitization is confirmed (satisfied by the atomic single-pass write discharge on exit/OFF transitions, or by verified retained image content on `R-15-190b` re-entry) only after Stage 2 and before Stage 4. |
| 4 | `measured_execution` | Measured execution / memory-plan delegation begins only after Stage 3 completes. |

Both [ResetTable.v](../../proofs/ResetTable.v) (`suffix_entry_ok`, `every_admitted_suffix_preserves_rider`) and [reset_table.py](../../tools/vos/reset_table.py) reject any suffix that omits tag discharge confirmation, omits data sanitization confirmation, releases addressability before tag confirmation, reorders sanitization ahead of addressability, or enters execution before sanitization confirmation.

## 4. Suffix Re-Entry, Retained vs. OFF-Image Extents, and Socket Transitions

1. **Retained vs. loader-filled OFF-image extents (`R-15-190b`).** On chain re-execution (`unlock_wake`, `standby_exit`, `install_switch`, or cold/explicit reboot), any `image_derived` domain held `RETAINED` re-enters by `image_pass` -> `image_verdict` before `requester_addressable`, rewriting no byte and running no discharge when the verdict passes, and falling back to full discharge + refill on failure. Conversely, any `image_derived` domain that is `OFF` on chain execution (represented in `off_image_extents`, whether `executable` or `data`) must be discharged/sanitized (`domain_complete`), populated by the RoT loader (`loader_fill`), and verified (`extent_verified`) before execution release (`island_release` / `measured_execution`). [DischargeSequence.v](../../proofs/DischargeSequence.v) proves this via `off_image_extent_requires_loader_fill_before_exec`, `retained_and_off_image_reentry_composition`, and `unfilled_off_image_release_refused`.
2. **Optional inference socket power and isolation transitions (`R-15-228h`, `R-15-228i`).** Consistent with [the immutable module contract](immutable-module-contract.md), `socket_power` suffixes require `socket_isolated` before `socket_reset` under host RoT table control with no firmware board management, and `socket_isolation` suffixes require `epoch_invalidated` before `socket_isolated` with no autonomous `socket_reset` recovery after isolation.

## 5. Symbolic Chain-Latency Summation (`R-09-006b`)

Each release point (`wake_to_interactive`, `cold_boot_to_interactive`, and optional `inference_ready`) declares symbolic latency terms and non-negative cycle totals in `latency_table`:

- **Per-domain term:** `rail_discharge_dwell + (reverify_latency if retained else refill_latency)`.
- **Per-release-point sum:** sum of its bound domains' terms plus `entropy_budget`, `sig_verify`, and `restore`.
- **Checks:** every declared domain is accounted for without omission, non-zero dwell/reverify/refill/signature-verify terms are present, `stated_total_cycles` equals the exact sum, and `stated_total_cycles <= ceiling_cycles`.

All numerical fields in `latency_table` remain symbolic composition constants until hardware qualification populates physical values; ceilings `DP-6` (1.0 s wake-to-interactive) and `DP-7` (10 s cold-boot-to-interactive) in [the product-gate contract](../implementation/contracts/product-gate.md) remain `proposed`.

## 6. Open Boundaries Preserved for Register Acts and `Q33-ii`

This specification and its schema/validator discharge composition structure and ordering without closing open register ambiguities or physical measurements:

- **Open register acts (`F-444` through `F-448` in [the findings register](../assurance/findings-register.md)):** `F-444` (explicit region-kind partitioning beyond named examples), `F-445` (bank-shared session-domain island ownership), `F-446` (whether RoT-sequenced re-entry re-runs start-up entropy tests), `F-447` (walk vs. dependency graph for cross-island release independence), and `F-448` (concurrent entropy-test overlap with image fills vs. positional verdict-before-draw ordering) remain open register acts.
- **Open downstream integration (`Q33-ii` in [PLAN.md](../../PLAN.md)):** devicetree blob emission from validated JSON tables, M3.5 RoT/M-mode firmware enforcement, M7.1 image integration, and emulator/silicon cycle-count measurements for dwell, hashing, NAND, and TRNG budgets remain open to `Q33-ii` and physical qualification.
