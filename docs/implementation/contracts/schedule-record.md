# Schedule record and symbolic admission

This is the U-05 statement slice of [the prerequisite map](../../assurance/unassigned-proof-map.md). [ScheduleRecord.v](../../../proofs/ScheduleRecord.v) extends [CyclicExecutive.v](../../../proofs/CyclicExecutive.v)'s existing `Composition` and `Frame` vocabulary with the three outputs required by R-11-017. R-11-006 supplies the interval-arithmetic admission boundary. The artifact is an executable Gallina statement over composition inputs. It supplies no measured timing values, machine refinement, or deployed composition.

## Inputs and outputs

`ModeSchedule` carries the existing per-core frames, a finite operating-point catalog, the visit declarations, a partition-to-point assignment, the NoC grants, the watchdog windows, and a target re-entry window. A visit identifies an existing core and slot by index. It does not copy its slot geometry. Every frame slot has exactly one visit; missing, duplicate and out-of-range visits fail admission. All cores have one positive major-frame period and a phase smaller than that period.

The three outputs are fields of this single record:

| Output | Representation and decision |
| --- | --- |
| OPP assignment | `opp_assignment` maps a frame's existing tenant to an index in `schedule_points`. Repeated visits of one tenant therefore select one point. The record carries a decidable equality with proof for the tenant type. Admission checks the selected point against every visit and compares its speed order with every point satisfying all visits of that same tenant. |
| TDM NoC table | `schedule_noc` identifies a visit, a fabric resource, an absolute offset, width and work bound per grant. A grant fits its owner's slot, fits the common period and covers its bound. Grants on one resource cannot overlap. The sum of granted work for a visit covers its declared demand. A missing owner or unserved demand is refused. |
| Watchdog windows | `schedule_watchdogs` carries exactly one window per declared visit. The window opens by the slot's start, covers its full padded width and closes by the visit's deadline. Missing, duplicate, out-of-range and prematurely closing windows are refused. |

The NoC declaration permits simultaneous grants on distinct resources. The resource identifiers and the demand terms are composition declarations. U-03 must bind those identifiers and grants to the arbiter model; this statement does not establish NoC delivery, route consistency or timing noninterference. Watchdog windows state scheduled observation intervals; detector failure domains and the implementation of monitoring remain separate obligations.

## Bounds and operating points

Each visit has one `WorkBound` for every point in the mode's catalog, including points of another class. Only points matching the visit's declared execution class can qualify. Each row declares its non-memory execution time and read/write counts in each of M0.14's two memory classes. `work_time` adds that execution time and each count multiplied by the corresponding point's declared memory latency. Fetch accesses belong in the read count of their assigned class. The table's derivation from code and the model belongs to the WCET workstream.

All durations use one common composition-selected spine-time unit. Bounds derived in another clock domain must be converted conservatively before constructing these inputs. `speed_order` is the catalog's declared order within an execution class, with lower values slower. Its correspondence to physical operating points, catalog completeness, and the qualification of both memory classes' latencies are external input obligations. The statement does not turn ordinal ranks into frequencies or treat a witness number as measured. The existing `Composition` boundary cost must safely bound switching at every candidate point in the catalog.

For a selected point, the calculated work bound must equal the existing slot's declared bound, and that bound plus the full boundary cost must fit the slot and its declared deadline. The old frame admission also runs, preserving its harmonic-period and non-overlap checks. Candidate points are compared against those same slot widths, deadlines and boundary cost. `admitted_visit_selects_slowest_partition_point` proves that an accepted selection is no faster than any candidate satisfying every visit of its tenant. A faster point needed by one visit remains admissible when another visit alone would fit a slower one.

## Modes, re-entry and the transition boundary

`ModeCatalog` contains a nonempty list of independently admitted complete schedules. `every_catalog_mode_is_admitted` gives the per-mode result. The target re-entry declaration carries an offset, a positive reserved width and a work bound. Admission checks that the work fits and that the interval is inside, and disjoint from all partition slots of, every target core's frame. It reuses Q23d's interval geometry without assigning link-leap semantics to a mode entry. An occupied or undersized re-entry window fails admission.

This is the target-side re-entry seam of U-05. R-11-018 additionally requires directed transition certificates, runtime guards, old-to-new service-chain bounds, bounded pending requests, dwell/service bounds, checkpoint and restore accounting, revocation and zeroization service, peak-memory bounds, recovery destinations, and invariance under arbitrary permitted sequences. Those certificates and the RoT-attested transition implementation are not constructed here. Endpoint admission and an idle target entry window do not authorize a mode change. The workflow combinations required by R-11-018a also remain outside this slice.

## Ensemble compatibility

`FourOutputSchedule` carries `ModeSchedule` as its first three outputs and Q23d's existing `LinkTable` values as a further field. `ensemble_projection` constructs Q23d's existing `MemberSchedule` directly from the first three outputs' frames, preserving every frame by construction. `fourth_output_preserves_frames` states this relation. The existing Q23d emission checker still owns link agreement, guards, leap scheduling and ensemble admission; carrying a link table in this wrapper does not discharge those checks.

## Acceptance evidence

### Research handoff for schedule synthesis

The following non-normative research inputs belong to U-05's future producer and
its join with U-03's resource model and code-derived WCET. The
[survey](../../background/open-math-conjectures.md#allocation-fragmentation-and-scheduling)
owns their status and sources. A usable proof first maps the selected workload to
the theorem's job or transfer model, then maps its schedule into `ModeSchedule`
while preserving the existing admission checks. No synthesis result supplies
physical bounds, transitions, a new deadline or the target implementation proof.

| Research input | Remaining bridge and discriminating examples |
| --- | --- |
| [Three identical processors](../../background/open-math-conjectures.md#three-identical-processors-with-unit-jobs-and-precedence) | Recognize exactly three identical processors and indivisible unit jobs before evaluating the subexponential result. Prove precedence and slot preservation. A varying-WCET job or a split requiring forbidden preemption rejects the reduction; the general polynomial-versus-NP-hard classification remains open. |
| [Unrelated-machine makespan](../../background/open-math-conjectures.md#unrelated-machine-makespan-approximation) | Derive finite compatible-core costs from admitted bounds, retaining dependencies, labels, communication and slot deadlines in the decoded schedule. A low-makespan assignment that misses a dependency or fabric grant is a negative witness. A general approximation or prediction-assisted result gives no full-platform ratio without this bridge. |
| [Pinwheel certificates/complexity](../../background/open-math-conjectures.md#pinwheel-scheduling-certificates-and-complexity) and [5/6 theorem/relaxed synthesis](../../background/open-math-conjectures.md#pinwheel-scheduling-the-56-theorem-and-relaxed-synthesis) | Include the whole service and overhead in each unit slot and prove every recurring window, including frame wrap. The published density theorem proposes candidates; density above 5/6 is not a refusal. An EPTAS schedule for relaxed periods must still meet the original periods before admission. Exercise a wraparound miss, overhead overrun and forbidden relaxation. Dense NP-completeness does not supply short certificates for general feasibility; a compact schedule representation still needs bounded expansion or a correspondence proof to this explicit record. |
| [List edge coloring](../../background/open-math-conjectures.md#list-edge-coloring-conjecture) and [Goldberg-Seymour](../../background/open-math-conjectures.md#goldberg-seymour-and-the-number-of-transfer-rounds) | Prove conflicts are exactly shared endpoints for unit transfers, with repeated transfers as parallel edges; bind colors and permitted lists to actual grants. The ordinary coloring theorem and constructive preprint offer a round bound and candidate algorithm, not a list-coloring theorem. Use solved bipartite or stated prime-order special cases only after recognition. Check endpoint conflicts, a forbidden listed slot, an extra routed-resource conflict and unequal durations before claiming the model fits. |

The survey's [real-period pinwheel artifact and dual covering result](../../background/open-math-conjectures.md#pinwheel-scheduling-the-56-theorem-and-relaxed-synthesis)
offer separate synthesis leads. The inspected Lean theorem covers exactly four
positive sorted real-period tasks; the manuscript's arbitrary multiplicities of
four distinct values require a separate aggregation/splitting proof. Preserve
the requirement of at least `ell` executions in every `ceil(ell*a_i)` slots for
all positive `ell`, and prove a bounded finite periodic realization before
encoding the infinite schedule as `ModeSchedule`. Matching mean rates or rounding
each period once is insufficient. Dual covering enforces minimum rest between
executions; a covering schedule that misses a replenishment deadline is a
negative witness, even when it satisfies the covering density threshold.

The [phase-service extraction boundary](../phase-service/prerequisite-contract.md#schedule-and-resource-extraction)
still requires all joint traffic alternatives, refresh and completion occupancy.
A matching-round schedule can pass endpoint coloring while failing that boundary;
this is a useful negative comparison for a proposed transfer reduction.

### Existing finite statement evidence

The closed witnesses inhabit every new record. Conversion proves an accepted three-output mode, a two-mode catalog, and a partition with two visits whose joint deadline constraints require the faster point. The refusal witnesses include a slot overrun, a fitting OPP that is not the slowest, an incomplete bound table, a wrong execution class, duplicate or uncovered visits, missing or early watchdogs, overlapping NoC grants, unserved NoC demand, occupied or overrun re-entry, and a catalog containing a rejected mode. `schedule_decidable` exposes the executable yes/no verdict over the supplied finite bounds.

The focused check compiles the new module and its dependency closure with the pinned Rocq toolchain, audits assumptions, and independently kernel-checks the compiled module in the assigned native lane. The integrated `python tools/run.py proofs` receipt supplies the corpus count and final evidence. Host metadata, generated requirement fingerprints and the implementation landing record are integrated with that receipt; no witness establishes a release timing floor.
