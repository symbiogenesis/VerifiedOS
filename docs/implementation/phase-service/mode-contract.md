# Mode-transition extension for the phase-service model

This contract extends the finite phase-service model of the
[store-buffer comparison](../comparisons/store-buffer.md) from one periodic
table to a declared set of global modes and the transitions between them. The
zero-wait predicate ranges over startup, frame wrap and mode transitions, which
the v1 readers of the [prerequisite contract](prerequisite-contract.md) refuse
as a `modes` or `transitions` field, so only a `phase-schedule-v2` declaration
yields a receipt that covers a transition.
R-11-018 makes each global mode an independently admission-proved schedule and
gives every permitted directed transition a certificate fixing its guard, entry
phase and carry-in work; R-11-014d permits a mode change to re-phase and defers
its transition interval to R-11-018. No register entry fixes the instant of the
source schedule at which an edge may fire (a slot boundary, a major-frame
boundary or a declared point): R-11-018 fixes the entry phase and presupposes
the old schedule's last service without naming the instant that produces it,
and R-11-023 and R-11-024 fix a major-frame boundary for the population axis
that R-11-019 separates from this one. The gap is R-11-018's to close, by an
Accept clause stating that each edge certificate also fixes the exit instant of
the source schedule, as a named slot boundary, the major-frame boundary or a
composition-declared point of the source table. Until it closes, this contract
takes the transition points as declared input and records the gap as a finding
for that entry's owner. Nothing here authors the R-11-017 artifact or an edge
certificate.

## Input format

Schema `phase-schedule-v2` has exactly the fields `schema`, `name`,
`resources_sha256`, `modes`, `initial` and `transitions`. v1's singular `mode`
discriminator, required to equal `"periodic"`, has no v2 counterpart and is
unrelated to v2's `modes`; v2 refuses it as v1 refuses `modes` and
`transitions`. `phase-schedule-v1` stays accepted through its existing reader
unchanged, and neither schema accepts the other's fields. Every strictness rule
of the [schedule input](schedule-input.md) applies at every level: exact field
sets, duplicate keys and names refused, no floating-point or non-finite numbers,
no boolean where an integer is required, identifier syntax for names, and the
digest binding of the one shared `phase-resources-v1` file, which gives every
mode the same banks, paths, occupancies and refresh durations. The schema
records no power state, so a mode's {ON, RETAINED, OFF} vector over gating
domains (R-15-189f; the domain is the macro or tier and never the bank,
R-15-189e) is outside this model: a mode declares the requests and refresh its
own table states. Where a composition leaves a bank's gating domain RETAINED,
its refresh share still runs (R-15-247k) and that mode's table is expected to
declare it; where the domain is OFF, no refresh and no request is reachable
(R-15-189d). Nothing here checks that expectation, which stays owed.

`modes` maps each mode name to an object with exactly `phases`, a nonempty
phase array exactly as v1 states it, each mode free to have its own length.
`initial` is a nonempty array of distinct declared mode names. Each starts at
its phase zero with empty banks, no maintenance in progress and nothing in
flight, the state R-15-247h's reset hold leaves every requester in when the
slot counter starts; listing a mode as initial declares it a possible startup
mode. No field declares another initial state, so a non-empty initial state is
inexpressible here and stays owed rather than refused. `transitions` is an
array of objects with exactly `from`, `from_phase`, `to` and `to_phase`: the
switch may occur at the end of `from_phase` of mode `from`, and mode `to`
resumes at `to_phase`. Both indices are zero-based into their own table and
required; a target of zero is written, not defaulted. `from` may equal `to`,
declaring a re-phasing of one table, and a switch at the end of the source's
last phase is permitted and coincides with its wrap. An undeclared mode name,
an out-of-range index, a duplicate transition or initial mode, a transition
whose target state is the source's own continuation (a no-op), and a declared
mode no initial mode reaches through the transition graph are refused as
malformed input; a point the exploration never visits because an earlier
failure stopped it is not refused.

## Transition semantics

A transition is a nondeterministic choice held by the executive, not the model:
at every reachable visit of a declared point the exploration takes both the
continuation into the source's next phase and every declared switch from that
point. A switch carries the boundary state unchanged. Bank occupancy,
maintenance occupancy and requests in flight are exactly what the continuation
would carry; nothing is drained, reset or re-issued: the model treats a switch
as a change of boundary label with no fence and no queue, and R-15-247h's reset
hold on a discharge edge belongs to the transition interval this model does not
represent. The cycle `from_phase` runs in full under the source's grant,
alternatives and refresh; the boundary after it is the state (`to`,
`to_phase`); the first target cycle is `to_phase` under the target's grant,
alternatives and refresh. A source refresh still holding its bank at that
boundary is carried as maintenance occupancy into the target's cycles (as
maintenance in the completion state), and the target's refresh of that bank
meets it as `refresh-overlap`. A switch may land inside any occupancy or
refresh, and the model must then see the conflict: a switch into a phase whose
alternatives assume idle banks is `arrival-blocked` where the carried occupancy
conflicts, and a request in flight across the switch that finds its bank taken
is `path-blocked`. One hart's acceptance and completion order is checked across
the switch as within a mode. A switch grants nothing: the source's remaining
phases lend no slack to the target, the mode-switch analogue of R-07-036's
non-work-conserving rule, which the register states for partition boundaries.

## Reachable product and completion

The acceptance state is (mode, phase, bank occupancy, requests in flight) at
the boundary before a cycle. The cycle runs under that mode's grant,
alternatives and refresh exactly as `phase_service` does; its successor is
(mode, phase plus one modulo that mode's length) for the continuation and
(`to`, `to_phase`) for each declared switch from that point, with the same
occupancy and requests in flight. The exploration seeds every initial mode's
state in declared order and proceeds breadth-first; at each dequeued state it
takes the alternatives in declared order and, for each alternative, enqueues
that alternative's continuation successor and then its switch successors in
transition declaration order, merging identical states on first discovery. It
closes over the whole reachable product and otherwise stops at the first
failure met in dequeue order, which is at the earliest failing cycle since
startup; a failure is attributed to the mode whose cycle detected it. The
closure is the finite analogue of R-11-018's demand that arbitrary transition
sequences preserve the declared invariants; each mode's own table stays the
object R-11-006 admits. The [completion model](completion-model.md) runs over
the same product under the same switch rule, with quiescent drain taken at
every reachable boundary of every mode by stopping arrivals and replaying issued
operations to completion while the current mode's refresh continues. No
transition is taken during a drain: the drain models a boundary that stops
issue in the mode the machine is in, and a mode change with issue stopped is
the separately admitted transition R-11-014d defers to and R-11-018 owns, whose
carry-in work and completion deadline R-11-018's certificate owes and this
model does not supply. Permitting a switch during a drain could not lengthen a
finite drain, since paths and occupancies are shared by every mode and a
refresh never delays an operation but only blocks it, and a block at a switch
point is a refutation of the product at that point; the reported bound is the
same under either rule.

## Outputs and regression

Acceptance keeps `zero_wait`, `states`, `trace`, `failure`, `reason` and
`drain`, and completion keeps `ordered`, `quiescent_drain`, `drain_status`,
`drain_failure` and `drain_cycles`, all with their meanings. Each result gains
`trace_modes`, one `[mode_name, phase]` pair per trace step; `mode_states`, an
object mapping every declared mode name to its distinct state count, zero for
a mode a stopped exploration never entered; and `transitions_taken`, the
zero-based indices into `transitions`, in declaration order, of the declared
transitions whose switch successor the exploration generated at a reachable
visit before closure or the earliest failure, whether or not that successor was
already known. The `failure` and `drain_failure` states each gain a leading
mode name, and each `injection_excesses` record gains `mode`. Each product
checker keeps its base checker's state shape and reason vocabulary, the
ordering reason being `order-inverted` for acceptance and
`acceptance-order-inverted` or `completion-order-inverted` for completion,
extended only by the mode.

A v2 declaration with one mode, that mode initial and no transitions emits that
mode's table as the v1 `Contract` and must yield, under `--output-contract`,
byte-identical contract bytes to the v1 declaration of that table; its
acceptance and completion results must equal the v1 results on every v1 field,
the v2 failure state compared with its mode removed, and must carry
`trace_modes` pairing that one mode with each step's phase, `mode_states`
mapping that mode to `states`, `transitions_taken` empty and `mode` equal to
that mode on every `injection_excesses` record; a v1 declaration is unaffected.
The tests hold both, and hold the product checkers equal under that projection
to `phase_service.check` and `phase_completion.check` on every tracked fixture
under `closed/` and `refuted/` and every built-in scenario wrapped as one mode.
A declaration with more than one mode or any transition emits the mode
contract, the object with exactly `initial` (the declared list), `modes` (each
mode name mapped to its table in the v1 `Contract` shape) and `transitions`
(the declared objects in declared order), as sorted, compact JSON with one
final LF, which `phase-service --contract` keeps refusing by its `modes` field;
the receipt binds those bytes. The product checkers take that per-mode
`Contract` table, so any v1 fixture can be wrapped as one mode.

`target_comparison` stays `open`. In `open_because` the single reason
`initial states and mode transitions` is replaced by `non-empty initial states`
and by the mode terms this model does not supply: the mode-transition budget
and dwell (R-15-247g, R-15-189i), the executive's own switch work, the
edge-certificate correspondence and the recovery-state entry a failed edge
takes after teardown (R-11-018); `qualified memory and timing` narrows to
`qualified occupancy and timing (R-15-247m)`. Every other reason the evaluator
publishes, the actual schedule, instruction-stream and arbiter correspondence,
whole-image WCET and physical area/power evidence, architectural ordering and
visibility refinement, and qualified second-class service and timer-residency
bounds (R-15-247m, R-07-040), is unchanged, this extension closing none of
them. The evaluator publishes that list for every declaration, each reason
being true of a v1 join as well. On a v2 declaration with more than one mode
or any transition, `phase-evaluate`'s `scope` reads
`declared-mode-product-zero-wait-comparison` and `phase-schedule`'s reads
`declared-mode-product-periodic-schedule`; a single-mode v2 declaration and
every v1 declaration keep `declared-single-mode-zero-wait-comparison` and
`declared-single-mode-periodic-schedule`, and `phase-schedule`'s `open_because`
is unchanged for every schema.

## Cost join

R-11-009 charges R-07-040's padded boundary once per slot-boundary visit, and
that boundary constant is H, the complete timer-hold residency, plus
R-15-220a's switch budget (R-15-220's three platform terms plus the context
term). The register already prices several terms of a mode change into the
section 11 mode-transition budget: per-domain rail transition latency
(R-15-189i), the discharge and refresh dwell (R-15-247g, R-15-247f), one
re-verification constant per image-derived domain (R-15-190b) and one constant
per release point of the reset table (R-15-198a). R-11-018 gives a mode
transition its own guard, entry phase and carry-in work. What no entry states
is whether a mode change is also a visit of the partition-switch boundary, or
whether the mode-transition budget enters this comparison's arithmetic at all.
This extension adds no boundary visit for a mode change and leaves `switches`
in the [cost input](cost-input.md) as the declared slot-boundary count, its
schema unchanged; that question is the second finding for the register's
owner. `phase-evaluate` accepts a v2 declaration through the same dispatching
reader and joins the product verdicts as it joins single-mode ones, the
product's `quiescent_drain` being the maximum over every mode's boundaries and
so a bound for each mode while the cost input's slots remain mode-agnostic, and
names the mode-transition budget as a term this comparison does not carry.

## Acceptance cases

The implementing module is `tools/vos/phase_modes.py`: the v2 reader, reusing
the v1 reader's phase, request and refresh helpers, and the product acceptance
and completion checkers. It is a new module because receipts bind the bytes of
`phase_schedule.py`, `phase_service.py` and `phase_completion.py`, and the
regression obligation is held against their unchanged decisions. The
`phase-schedule` command decodes with the same strict decoder, reads `schema`
before any field-set check, dispatches on it, and reports an unsupported or
absent `schema` as malformed input at exit 2; it gains an opt-in `--completion`
for both schemas, and `phase-service --contract` is unchanged. Tests live in
`tools/tests/test_phase_modes.py` under `python tools/run.py test --only
phase_modes`; synthetic examples under `mode-examples/` bind one resource file.

Acceptance requires these checked cases: an undeclared transition mode
refused; a `from_phase` or `to_phase` out of range refused; an initial mode not
declared refused; a final-phase write of mode A surviving the switch and
blocking the first phase of mode B, `arrival-blocked` with the failure in B;
mode B's refresh starting on a bank still occupied by mode A's write,
`refresh-overlap` across the switch; a request issued in A over a nonzero path
and finding its bank taken after the switch, `path-blocked`; a hart's request
issued in mode A over a longer path and its next request issued in mode B's
entry phase over a shorter path, `order-inverted` with the failure in B, an
inversion between two requests both issued in A being detected at their
arrival and attributed to A's continuation, which the exploration dequeues
first; a closed companion
whose switch point moves to the phase after which the carried state cannot
conflict, closing with every declared transition taken; the single-mode
regression; a completion inversion whose two operations of one hart issue in
different modes; and completion drain over both modes with a blocked drain
whose `drain_failure` names the target mode. A companion closes by restricting
the switch point or the arrivals, never by draining state at the switch.

## Scope

The extension establishes closure of a declared finite product only. It does
not model the mode-change mechanism, its RoT sequencing or dwell (R-15-247g,
R-15-247h), the executive's own switch work, initial states other than empty,
the recovery-state entry a failed edge takes after teardown (R-11-018), or the
actual arbiter and fabric, and it establishes no correspondence to the
R-11-017 artifact, to R-11-018's edge certificates or to qualified occupancy
(R-15-247m); R-17-041's timing residuals remain. A closed multi-mode receipt is
declared-input evidence and turns the zero-wait branch into no positive result
on any island. Q22e stays open, and its available-evidence sentence names
actual mode changes, their instant, dwell and cost, rather than mode changes.
