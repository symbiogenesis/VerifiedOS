# Modeled block-device contract candidate

This is M5.3's proposed composition interface for an executable storage image and
the corresponding R1c-ii device wrapper. It is a review input, not an implemented
device or a new architectural requirement. The [M5.3 acceptance predicate](../docs/implementation-checklist.md)
requires review of this interface before its implementation lane opens. Recovery
policy receives a separate review. Neither M5.3 nor R1c-ii lands with this document.

## Boundary and authority of the choices

The proposed slave presents logical blocks at the availability-service boundary of
R-10-021. It is a bounded emulator device for executing the storage stack. The
production path in R-12-025 is raw NAND, an ONFI PHY and fixed-function ECC with a
host-side FTL; R-12-026, R-12-027, R-12-029 and R-12-030 add device-code and scrub
obligations. A logical-block model implements none of those mechanisms. R1c-ii may
use this interface for a simulation wrapper only after that scope is accepted; a
production flash interface still needs its own reviewed commands and FTL binding.

| Choice or constraint | Owner and present disposition |
| --- | --- |
| Dense placement and attestation of an aperture; device memory cannot execute | R-15-002b and R-15-002d in the [register](../docs/requirements-register.md), with their [map rationale](../docs/spec.md#r-15-002b). Placement is already declared by `platform.blkdev` in the [composition](../model/config/verifiedos.json); it does not specify a device. |
| A modeled device for the two storage instances; shared semantics with the RTL lane | The M5.3 and R1c-ii checklist cells. These plan obligations authorize a proposal, but no register entry currently fixes this slave's command set. |
| PIO, one outstanding command, widths, encodings, geometry, service steps, completion and reset rules below | Proposed composition choices owned by this candidate. Device review accepts or revises them before implementation; they are not deductions from the address map. |
| Raw NAND, fixed-function code and host FTL on the production path | R-12-025 through R-12-030 and the [storage lower half](../docs/spec.md#r-12-025). Mapping this logical abstraction to that path remains owed; accepting the candidate does not authorize a firmware-bearing controller. |
| Storage can return corrupted or misplaced bytes; integrity is checked above it | R-10-021, R-10-001, R-10-022 and R-10-022a and their [read-path rationale](../docs/spec.md#r-10-022a). Device success never authenticates an extent or advances a trusted root. |
| Authority derives from the composed capability distribution | R-08-001 and R-08-034 and the [manifest rule](../docs/spec.md#r-08-034). The composed storage service owns the slave; a block number is data, not authority. |
| Multi-block commit and recovery | R-10-036 and R-16-003 own the obligation; [JournalIndex.v](../proofs/JournalIndex.v) leaves the recovery discipline and commit representation as parameters. This candidate selects neither. |

The [MMIO dispatch](../model/model/sys/platform.sail) currently does not claim the
declared block window. The [memory path](../model/model/sys/mem.sail) can therefore
send permitted accesses there to RAM. The model also disables MMIO dispatch under
`get_config_rvfi()`. Device acceptance requires an execution mode which actually
dispatches the device; RVFI-only runs with that bypass cannot supply the evidence.

## Composition input

The accepted composition supplies `base` and `size` from `platform.blkdev`, a
logical block length `B`, a block count `N`, and positive integer service bounds
`read_steps`, `write_steps` and `flush_steps`. The model records these inputs with
the image identity and input-event trace. No current configuration key is claimed
to supply the new quantities; their schema and attested representation are an
implementation deliverable after review.

`base` is aligned to eight bytes; `B` is positive, a multiple of eight and at most
`size - 0x100`; `N` is positive. `B`, `N` and every register result fit an unsigned
64-bit integer. The composition rejects any overflow in `base + size` or `N * B`,
any aperture outside the physical address space or its permitted IO region, and
any geometry exceeding the statically allocated model backing. These computations
use mathematical integers before narrowing. A fixture's block length does not
select the NAND page size or the main-memory CBO block size.

The backing medium is an explicitly supplied byte array of exactly `N * B`
bytes. There is no implicit blank disk, host file discovery or truncation to fit a
geometry. Missing backing and a mismatched length are startup refusals. A supplied
all-zero fixture is valid and identifiable as that fixture. Host paths are harness
inputs and are never guest-visible register data.

## Bus access and authority

Every declared byte of the aperture is claimed in both directions, including
reserved offsets and registers whose direction forbids the access. The claim
routes an access to a decision; it does not make the access succeed. Any access
overlapping the aperture but not wholly contained in it is refused before RAM
fallback. An access wholly outside it remains the map owner's decision. This does
not settle R1c-ii's policy for unrelated, unclaimed IO addresses.

The slave accepts aligned, ordinary eight-byte loads and stores only. The complete
access, including width and kind, is validated before any effect; narrower, wider,
misaligned, fetch, atomic and split accesses cannot become accepted sub-accesses.
Capability and PMA checks precede the slave. The existing write-dispatch signature
does not carry the access kind, so the implementation must preserve the decision
at the memory boundary or extend the internal interface; a check only in a handler
that never sees the kind is insufficient.

All successful reads return bytes with a cleared capability tag. Stored tags do
not enter the staging buffer or persistent medium; capability-shaped bytes remain
data. No register names a RAM pointer, DMA descriptor, interrupt destination or
domain selector. The slave initiates no fabric access and raises no interrupt.
The service polls at its admitted points. Sharing its raw control capability with
several independent clients would share staging and status; the composition gives
the control interface to one serialized service, and clients use that service's
bounded, separately authorized interface. The device does not establish
system/user-volume separation or authenticate a caller's block number.

An invalid bus access raises the existing load/store access fault for its kind,
with no device-state or medium change and no successful data response. A CHERI or
PMA fault or architectural alignment refusal may occur earlier and takes
precedence. Fetch refusal is already owned
by the non-executable device PMA. A malformed request at the RTL slave boundary
returns an error response; the core adapter maps it to the architectural fault.

## Register layout

Offsets are relative to `base`; register values and data-window doublewords use
little-endian byte order. `RO`, `WO` and `RW` describe direction; a forbidden
direction faults. Every offset not admitted by this table faults.

| Offset | Name | Access | Value or effect |
| --- | --- | --- | --- |
| `0x00` | `VERSION` | RO | `1`, identifying this proposed ABI. |
| `0x08` | `BLOCK_BYTES` | RO | `B`. |
| `0x10` | `BLOCK_COUNT` | RO | `N`. |
| `0x18` | `STATUS` | RO | `0=IDLE`, `1=BUSY`, `2=DONE`, `3=ERROR`; all other bits zero. |
| `0x20` | `RESULT` | RO | `0=OK`, `1=BAD_COMMAND`, `2=RANGE`, `3=INCOMPLETE`, `4=IO`; all other bits zero. Meaningful as an error code only in `ERROR`. |
| `0x28` | `BLOCK` | RW | Unsigned logical block number, writable only in `IDLE`. Any 64-bit value may be staged; command acceptance checks the range. |
| `0x30` | `COMMAND` | WO | `1=READ`, `2=WRITE`, `3=FLUSH`. Accepted only in `IDLE`; remaining encodings produce `BAD_COMMAND`. |
| `0x38` | `ACK` | WO | Exactly `1` retires `DONE` or `ERROR` to `IDLE`. All other values or states fault. |
| `0x100 + 8*i`, `0 <= i < B/8` | `DATA[i]` | RW | Staging doubleword. Writes allowed only in `IDLE`; reads allowed only in `DONE` following a successful `READ`. |

State holds `B` staging bytes and a written-doubleword bitmap, the staged block
number, and at most one pending command with its latched block, data and remaining
steps. `STATUS` and `RESULT` loads have no effect. Geometry registers and `BLOCK`
remain readable in every state; `BLOCK` shows the staged number and does not change
while a command is active. There is no read-to-clear bit, command queue or hidden
retry. Writes to `BLOCK` clear staging and its bitmap even when the value is
unchanged, making selection of a block a new preparation boundary.

## Command, completion and error transitions

At reset and after `ACK`, state is `IDLE`, `RESULT=OK`, `BLOCK=0`, staging is zero,
the bitmap is empty, and there is no pending command. Zeroing is observable only
through a subsequent authorized read transaction: an `IDLE` data-window load
faults. Rewriting a staging doubleword replaces it and marks that word written.

A `COMMAND` store in `IDLE` consumes that preparation. Validation precedence is
unknown opcode, then block range for `READ` or `WRITE`, then complete staging for
`WRITE`. The selected validation failure retires the MMIO store successfully and
publishes `ERROR` with the corresponding result, clears staging and its bitmap,
and changes no persistent byte. `FLUSH` ignores `BLOCK` and staging. There is no
partial command acceptance on a validation failure.

A valid command latches its inputs, sets `BUSY` and `RESULT=OK`, clears the
CPU-facing staging buffer and its bitmap, and schedules one backend operation.
`WRITE` retains its latched private payload. A control or data write while busy
faults without replacing the pending request. The command remains busy for its
composition-declared number of device steps. A device step is an external model
progress event, independent of status loads; the executor must deliver these
events even when software does not poll. The harness records their order relative
to bus accesses and reset. These steps are functional sequencing inputs, not a
measured NAND latency or an admitted WCET.

At the final step, exactly one terminal outcome occurs:

| Command | `DONE`, `RESULT=OK` | `ERROR`, `RESULT=IO` |
| --- | --- | --- |
| `READ` | Snapshot the selected persistent block into staging and allow repeated data reads, with no medium mutation. | Clear staging; no data read succeeds and no medium byte changes. |
| `WRITE` | The latched bytes are durable at the selected block before `DONE` is observable. Other blocks are unchanged. Data-window reads remain forbidden. | The selected block may contain a torn combination of old and new bits as defined below. Other blocks are unchanged absent a separately recorded media fault. No success is reported. |
| `FLUSH` | Complete a durability barrier over preceding successful writes. This candidate is write-through, so there is no acknowledged volatile write backlog. | Report the backend's barrier failure. Do not convert the failure into success or undo a preceding successful write. |

A terminal outcome remains latched until `ACK` or reset. Repeated reads never
re-execute a command. A new command while `DONE` or `ERROR` faults. Invalid `ACK`
faults without clearing a completion. No completion cookie is needed for the
single-outstanding protocol; reset must cancel the backend association so an old
response cannot be mistaken for a later command.

## Persistence, faults and reset

Successful command completion is a device result, not an L0 commit record or a
`Fresh`-region acknowledgement: R-10-013c reserves that acknowledgement until the
freshness epoch is sealed. A
write-through success is proposed to make the durable boundary explicit before
the storage lowering relies on it. The host adapter cannot equate a buffered host
write with that boundary: its success path must establish persistence in the
backing image used for restart, and an adapter that cannot do so reports `IO`.
The harness's modeled crash is an explicit input event; killing a host process
without that event is not evidence of the model's crash transition.

Reset and power loss use the same conservative volatile-state transition here.
They clear every control/staging/pending field, invalidate the old backend
response, and preserve the persistent medium except for a write in flight. A
pending write may leave any bitwise mixture of its previous block `old` and
latched block `new`: for a harness-supplied mask `m` of `8*B` bits, the resulting
block is `(old & ~m) | (new & m)`. Both endpoints and non-prefix tears are allowed;
no sector, word or multi-block atomicity is assumed. A reset during `READ` or
`FLUSH` changes no medium byte. A reset after a successful write preserves its
bytes even if software never read `STATUS` or never acknowledged the completion.

Reset wins over a final-step event at the same harness boundary: that operation
is in flight and may tear; a final step ordered earlier has already completed.
There is no completion after reset for the canceled command, including a delayed
host callback. The adapter must quiesce or fence off the canceled operation's
medium writes before accepting a new command; suppressing its status callback
alone does not establish this boundary. A fresh run opens the resulting
persistent image and begins with
reset volatile state. Startup must not recreate the original fixture over it.

The mask rule is a declared fault class, not an exhaustive NAND failure model.
Separate harness events can replace bytes at a named block, return another
block's intact bytes on `READ`, or fail a backend command. They are explicit
inputs recorded with the command and event boundary, not guest-writable fault
registers. A fault-free `READ` returns the addressed bytes; a misplaced-read event
can return intact wrong bytes with `DONE`, because the integrity layer must detect
that condition itself. This prevents a friendly device oracle from hiding the
R-10-021 obligation. No corruption event is silently interpreted as a trusted
root update, authenticated read or erased key.

The device does not parse a journal, recognize `rec_closes`, choose a root, skip a
torn record, stop at one, replay a transaction or clear durable regions. Feed the
same crashed image to either recovery parameter in `JournalIndex.v`: the device
answer is identical. Which recovered store is accepted still belongs to the
independent recovery-policy decision and the subsequent crash-refinement proof.

## Decisive acceptance cases

These are predicates for the future real Sail device and wrapper, not passing
test results. The harness derives addresses and iteration bounds from a valid
fixture with `N >= 2`; payloads distinguish every byte and both blocks. It compares
full medium and volatile state where a case says unchanged. Every architectural
case emits its observed verdict through the existing HTIF test path, while the
harness records injected events and the before/after image identity. A host-only
reference exercise establishes harness behavior and cannot close device execution.

| Case | Stimulus | Required observation |
| --- | --- | --- |
| P-init | Start with exact backing; read geometry and status. | Supplied `B`, `N`; `IDLE/OK`; no implicit write to backing. |
| P-read | Select block, submit `READ`, issue fewer than `read_steps` progress events, then the final event. | `BUSY` before the final event; exactly one `DONE`; full selected payload, repeatably readable, with tag clear. |
| P-write | Select the last valid block; fill every staging word in shuffled order, replacing one; submit `WRITE` and complete. | Latest staged bytes at that block; adjacent blocks unchanged; success durable before status observation. |
| P-ack | Acknowledge a terminal result; repeat a new command. | Clean preparation; no old bitmap, payload or completion reused. |
| P-flush | Successful write, acknowledge, set an out-of-range `BLOCK`, submit `FLUSH`, then restart. | Flush ignores block argument; write survives; no additional data operation occurs. |
| P-progress | Submit with no status polling; supply all declared device steps. | Completion occurs; polling frequency does not drive progress. |
| N-start | Missing, short or oversized backing; zero/overflowing geometry; insufficient fixed model backing. | Startup refusal before any guest instruction or implicit backing mutation. |
| N-access | Each invalid direction, reserved offset, width and alignment; overlapping aperture ends and overflowing address arithmetic. | Fault or earlier architectural refusal; no device or RAM mutation, no truncated access. Entirely outside addresses are excluded from this case. |
| N-kind | Fetch, atomic and split requests at valid register/data offsets. | Refusal before any constituent device side effect. |
| N-authority | Untagged, insufficiently bounded or wrong-permission capability at an otherwise valid access. | Architectural capability refusal before device state changes. Mere knowledge of `base` or a block number grants nothing. |
| N-command | Unknown opcode; `READ`/`WRITE` with `BLOCK=N` or the largest unsigned value; `WRITE` missing one staging word. Combine errors to exercise precedence. | Latched `BAD_COMMAND`, `RANGE` or `INCOMPLETE` respectively; bus store succeeds; no backend request or medium mutation. |
| N-staging | Prepare data, rewrite `BLOCK`, then submit `WRITE` without refilling. | `INCOMPLETE`; no earlier preparation leaks across selection. |
| N-state | Write command, block or data while busy; command at terminal state; data load outside successful-read `DONE`; invalid `ACK`. | Bus fault; original command/result and full medium unchanged. |
| N-io-read | Inject read failure after a previous successful read and acknowledgement. | `ERROR/IO`; data load faults, including at offsets that held the previous payload. |
| N-io-write | Inject write failure with zero, full and non-prefix tear masks. | `ERROR/IO` even for a full mask; selected bits match the mask and other blocks remain unchanged. |
| N-io-flush | Inject barrier failure after an acknowledged successful write. | `ERROR/IO`; earlier durable bytes remain. |
| C-idle | Reset from `IDLE`, a validation error and each terminal result. | Clean volatile state; persistent image preserved. |
| C-inflight | Reset before command acceptance, after acceptance, at each progress boundary, and concurrent with the final event, for every command. | No pre-acceptance effect; pending write follows supplied tear mask; pending read/flush leaves medium unchanged; reset wins the tie; no terminal result survives. |
| C-durable | Reset after write completion but before status load and before `ACK`; reopen saved image. | Completed bytes survive with clean device state. |
| C-late | Complete a new post-reset command, then deliver the canceled command's delayed response. | New command and medium unchanged by the stale response. |
| I-corrupt | Corrupt an extent or return intact bytes from the wrong block in the composed storage image. | Device can return `DONE` and wrong bytes; the real system-integrity/AEAD path refuses before returning object bytes. Device-local success alone fails this case. |
| I-recovery | Run both exhibited recovery disciplines on the same device-produced crashed medium. | Identical device bytes; report the policy-dependent stores separately. No preferred store or M5.3 crash-half success is inferred. |

The M5.3 target predicate additionally owes the one-index-body link map, differing
cross-domain digests under the real crypto implementation, and execution with
M4.4's kernel interface. The table contributes the device and corruption cases;
it supplies none of those other producer artifacts. R1c-ii's wrapper evidence
compares accepted bus accesses, refusals, payloads, terminal results and reset
outcomes against the same fixture and input trace, with an explicit mapping from
model progress events to simulated cycles. It is differential testing, not RTL
refinement evidence or a physical latency qualification.

## Review and implementation handoff

Device review must decide the proposed PIO abstraction, write-through durable
success, complete-access refusal and reset race ordering together. It must also
accept or replace the simulation-only use at the RTL boundary; the existing
[provenance record](../rtl/synthesis-provenance.md) says the selected upstream has
no block-device implementation. Choosing an upstream or authored wrapper and its
license/provenance disposition remains R1c-ii's act.

After review is recorded and the contract lands, the model owner supplies its
configuration schema, static backing, event/reset mechanism and full-aperture
dispatch, then takes the cases above on that device. The current composition
comments, attested device-tree representation and model bundle require a
coherent update at that implementation boundary. The integrator records the
partial M5.3 progress and remaining findings in the shared checklist; this
document grants no completed-item status, proof tier or recovery-policy ruling.
