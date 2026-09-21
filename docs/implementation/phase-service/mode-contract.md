# Mode-transition extension for the phase-service model

This contract extends the finite phase-service model of the
[store-buffer comparison](../comparisons/store-buffer.md) from one periodic
table to a declared set of global modes and the transitions between them. The
zero-wait predicate ranges over startup, frame wrap and mode transitions, and
every instrument of the [prerequisite contract](prerequisite-contract.md)
refuses a `modes` or `transitions` field, so no receipt covers a transition.
R-11-018 makes each global mode an independently admission-proved schedule and
gives every permitted directed transition a certificate fixing its guard, entry
phase and carry-in work; R-11-014d lets a mode change re-phase under a
separately checked transition interval. No register entry fixes the instant of
the source schedule at which an edge may fire (a slot boundary, a major-frame
boundary or a declared point), so this contract takes the transition points as
declared input and records that gap as a finding for the register's owner.
Nothing here authors the R-11-017 artifact or an edge certificate.

## Input format

Schema `phase-schedule-v2` has exactly the fields `schema`, `name`,
`resources_sha256`, `modes`, `initial` and `transitions`. `phase-schedule-v1`
stays accepted through its existing reader unchanged, and neither schema accepts
the other's fields. Every strictness rule of the
[schedule input](schedule-input.md) applies at every level: exact field sets,
duplicate keys and names refused, no floating-point or non-finite numbers, no
boolean where an integer is required, identifier syntax for names, and the
digest binding of the one shared `phase-resources-v1` file, which gives every
mode the same banks, paths, occupancies and refresh durations. A mode leaving a
bank OFF or RETAINED (R-15-189f, R-15-247k) declares no request to it; its
refresh share still runs where that mode's table says so.

`modes` maps each mode name to an object with exactly `phases`, a nonempty
phase array exactly as v1 states it, each mode free to have its own length.
`initial` is a nonempty array of distinct declared mode names; each starts at
its phase zero with empty banks and nothing in flight, and no field declares
another initial state, so a non-empty one is refused and named as owed.
`transitions` is an array of objects with exactly `from`, `from_phase`, `to`
and `to_phase`: the switch may occur at the end of `from_phase` of mode `from`,
and mode `to` resumes at `to_phase`. Both indices are zero-based into their own
table and required; a target of zero is written, not defaulted. An undeclared
mode name, an out-of-range index, a duplicate transition or initial mode, and a
declared mode no initial mode reaches through the transition graph are refused.
`from` may equal `to`, declaring a re-phasing of one table.

## Transition semantics

A transition is a nondeterministic choice held by the executive, not the model:
at every reachable visit of a declared point the exploration takes both the
continuation into the source's next phase and every declared switch from that
point. A switch carries the boundary state unchanged. Bank occupancy,
maintenance occupancy and requests in flight are exactly what the continuation
would carry; nothing is drained, reset or re-issued, because a switch is not a
fence and this model has no queue. The target's refresh declaration governs
from the resume phase. A refresh the source started and that still holds its
bank is carried as occupancy, and the target's refresh of that bank meets it as
`refresh-overlap`. A switch may land inside any occupancy or refresh, and the
model must then see the conflict: a switch into a phase whose alternatives
assume idle banks is `arrival-blocked` where the carried occupancy conflicts,
and a request in flight across the switch that finds its bank taken is
`path-blocked`. One hart's acceptance and completion order is checked across
the switch as within a mode. A switch grants nothing; the source's remaining
phases lend no slack to the target (R-07-036).

## Reachable product and completion

The acceptance state is (mode, phase, bank occupancy, requests in flight). The
exploration starts from every initial mode in declared order, takes
alternatives in declared order and the continuation before switches in
declaration order, merges identical states, closes over the whole reachable
product and otherwise stops at the earliest failing cycle in that order. The
closure is the finite analogue of R-11-018's demand that arbitrary transition
sequences preserve the declared invariants; each mode's own table stays the
object R-11-006 admits. The [completion model](completion-model.md) runs over
the same product under the same switch rule, with quiescent drain taken at
every reachable boundary of every mode by stopping arrivals and replaying issued
operations to completion while the current mode's refresh continues. No
transition is taken during a drain: the drain models a boundary that stops
issue in the mode the machine is in, and a mode change with issue stopped is
the transition interval R-11-014d checks separately, whose carry-in work and
completion deadline R-11-018's certificate owes and this model does not supply.

## Outputs and regression

Acceptance keeps `zero_wait`, `states`, `trace`, `failure`, `reason` and
`drain`, and completion keeps `ordered`, `quiescent_drain`, `drain_status`,
`drain_failure` and `drain_cycles`, all with their meanings. Each result gains
`trace_modes`, one `[mode, phase]` per trace step, `mode_states`, the distinct
state count per mode, and `transitions_taken`, the declared transitions taken
before closure or the earliest failure, in declaration order. Every failure
state names its mode, and each `injection_excesses` record gains `mode`. A v2
declaration with one mode, that mode initial and no transitions must yield the
same result fields, the same verdict and, under `--output-contract`,
byte-identical contract bytes as the v1 declaration of that table; a v1
declaration is unaffected. The tests hold both, and hold the product checkers
equal to `phase_service.check` and `phase_completion.check` field by field on
every tracked fixture under `closed/` and `refuted/` and every built-in
scenario wrapped as one mode. A declaration with more than one mode or any
transition emits the mode contract as sorted, compact JSON with one final LF,
which `phase-service --contract` keeps refusing by its `modes` field; the
receipt binds those bytes. `target_comparison` stays `open`, and `open_because`
names the mode-change cost and dwell (R-15-247g), the executive's own switch
work, the actual arbiter, backpressure, non-empty initial states, qualified
occupancy (R-15-247m) and the instruction-stream and certificate correspondence.

## Cost join

R-11-009 charges R-07-040's padded boundary once per slot-boundary visit, and
R-15-220a's switch budget is what that boundary contains. R-11-018 gives a mode
transition its own guard, entry phase and carry-in work, and R-11-014d its own
transition interval; no entry states that a mode change is a visit of the
partition-switch boundary. This extension adds no boundary visit for a mode
change and leaves `switches` in the [cost input](cost-input.md) as the declared
slot-boundary count, its schema unchanged. Whether a mode change coincides with
a slot boundary, and how its interval is priced, is a second finding for the
integrator. `phase-evaluate` accepts a v2 declaration through the same reader,
joins the product verdicts as it joins single-mode ones, and names the
transition interval as an unpriced term.

## Acceptance cases

The implementing module is `tools/vos/phase_modes.py`: the v2 reader, reusing
the v1 reader's phase, request and refresh helpers, and the product acceptance
and completion checkers. It is a new module because receipts bind the bytes of
`phase_schedule.py`, `phase_service.py` and `phase_completion.py`, and the
regression obligation is held against their unchanged decisions. The
`phase-schedule` command dispatches on the `schema` value read with the same
strict decoder and gains an opt-in `--completion` for both schemas;
`phase-service --contract` is unchanged. Tests live in
`tools/tests/test_phase_modes.py` under `python tools/run.py test --only
phase_modes`; synthetic examples under `mode-examples/` bind one resource file.

Acceptance requires these checked cases: an undeclared transition mode
refused; a `from_phase` or `to_phase` out of range refused; an initial mode not
declared refused; a final-phase write of mode A surviving the switch and
blocking the first phase of mode B, `arrival-blocked` with the failure in B;
mode B's refresh starting on a bank still occupied by mode A's write,
`refresh-overlap` across the switch; a request issued in A over a nonzero path
and finding its bank taken after the switch, `path-blocked`; a closed companion
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
or the actual arbiter and fabric, and it establishes no correspondence to the
R-11-017 artifact, to R-11-018's edge certificates or to qualified occupancy
(R-15-247m); R-17-041's timing residuals remain. A closed multi-mode receipt is
declared-input evidence and turns the zero-wait branch into no positive result
on any island. Q22e stays open.
