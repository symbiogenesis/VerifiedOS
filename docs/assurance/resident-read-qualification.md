# Resident read reference qualification

[ResidentReads.v](../../proofs/ResidentReads.v) supplies Q44's bounded executable
reservation reference under the
[resident-object contract](../implementation/contracts/resident-object-reads.md).
It models one charged immutable backing, two independent holder slots and one
outstanding request per holder. Q44 remains open: this reference does not yet
refine the Python service, scalar retirement, storage or a target artifact.

## Proven scope

Admission checks owner, domain, object, version, root identity, current rights,
generation, bounded window, expiry and finite token capacity, then captures the
boot epoch. `admission_installs_exact_window` establishes the admitted window;
`begin_stores_bounded_request` confines a request and assigns its next nonwrapping
private sequence. `admitted_completion_within_window` joins those transitions to
the exact retained slice. It requires the admitted window property and does not
cover a forged pending request in an arbitrary state.

Completion rechecks the reservation, authority, identity, boot/generation and
expiry, then invokes an abstract verifier on the backing and bound root before
returning bytes. Authorization or verification failure returns no payload. The
model assumes neither verifier soundness nor hash injectivity; the fixture uses
independently stated expected bytes and roots without implementing cryptography.

Common-state frame and write-journal theorems cover begin, completion, synchronous
reads and repeated reads with fixed reservations. The journal includes repeated
stores of the same value; `no_common` rejects a common increment followed by a
restoring decrement. These are the reference's abstract cells, with complete
concrete caller/service write observation still owed.

Both system-image and user-data witnesses admit two holders, repeatedly serve
their independent windows, accept an empty boundary read and retain simultaneous
transfers. Refusals distinguish wrong domain/version/root/window, revoked or
expired in-flight authority, generation change and stale completion against a
successor request. An omitted-verifier control serves incorrect bytes beside a
refusing control. The retention observation covers reservations and accepted
transfers, rejecting same-identity mutation or zeroization even when only a
transfer remains. Completion preserves it; generic begin/admission preservation
is not proved.

A refused begin preserves an accepted pending request. Unmatched completion
preserves all state and emits no store; completion and retirement preserve private
sequence counters. Retirement cancels reservations and transfers without holder
acknowledgment. If its modeled barrier is unavailable, it retains the bytes in
closed, charged backing. That abstract barrier supplies no containment, sweep,
zeroization, physical reuse or retirement-cost evidence.

Explicit reservation close, renewal, crash, and fresh-token readmission extend
this lifecycle model:

- `close_reservation` releases one holder slot (even if expired, revoked, or
  generation-changed) and clears that slot's pending request and response via
  `clear_pending`, preserving backing, `next_token`, authority, clock, boot and
  generation epochs, all sequence counters, and the peer slot's reservation and
  session (`close_preserves_backing_and_peer`, `close_invalidates_handle`,
  `close_refusal_preserves_state`).
- `readmit_after_close_allocates_fresh_token` proves that closing a handle
  whose token is at most `next_token` and readmitting the same slot yields a
  strictly larger token (`token h < token h'`), keeping the closed handle
  distinct from the new handle and refused by both `close_reservation` and `live`.
- `renew_reservation` extends a live reservation's expiry to
  `clock + retention_bound` within `counter_bound` when doing so strictly
  increases `expires`, preserving `reserved_handle`, backing, `next_token`, peer
  reservations, and all sessions including pending transfers
  (`renew_preserves_sessions_and_peer`, `renew_refusal_preserves_state`).
- `crash` advances `current_boot`, clears all reservations and pending
  requests, marks occupied backing non-accepting without releasing it, and
  preserves every holder's sequence counter, causing subsequent `live`,
  `complete`, `begin_read`, and `admit` checks to refuse
  (`crash_invalidates_all_and_preserves_sequences`).
- Executable witnesses (`close_preserves_peer_and_allows_readmit_witness`,
  `renew_extends_pending_transfer_witness`, and
  `crash_retains_backing_and_sequences_witness`) exercise these transitions and
  refusals for both `SystemImage` and `UserData`.

## Retained proof evidence

[Focused reservation proof evidence](../implementation/retained-evidence/q44-resident-reservation-20261014/manifest.json),
SHA256 `de0e639612ed7a6b7b4f1f40a637a98462756b9efcbd9943460b884d8949fd0f`,
binds the generated-header source, compiled object, exact commands and bounded
candidate journal for the initial reservation proof increment. At locked Rocq 9.3.0 with the proof gate's strict flags,
selected-source compilation, native inventory and assumption queries passed;
every enumerated symbol had a closed global context. Recursive kernel rechecking
of the module and installed library closure passed without an admitted root or
covered sealed field. Selected-source non-vacuity found no unbuilt record;
closed `witness_<Record>` definitions accompany every carrier record.

The retained run used eight of twelve permitted attempts within a thirty-minute
active-repair budget. Its focused results supply local feedback; the close,
renewal, crash, and fresh-token readmission extension was likewise verified
locally under locked Rocq 9.3.0 strict compilation, `Print Assumptions`, and
`rocqchk`. Fresh hosted proof acceptance remains deferred to user-managed cold
Guest CI.

## Remaining qualification

Q44 still owes two-slot predecessor replacement across backing reuse in Gallina,
Python/C/scalar/storage correspondence, verifier soundness, complete writer
observation, and full resource/retirement accounting. Finite-counter proofs cover
admission tokens and request sequences; private read/authentication counters and
external clock bounds have no general exhaustion theorem here. Compiled production
defect controls, both real storage instances, the completion/sweep/zeroization
barrier (Q44/M5.3d joins), and cold hosted Guest CI proof acceptance remain open.
This reference discharges no complete requirement.

This document uses `CC-BY-4.0` under [COPYRIGHT.md](../../COPYRIGHT.md).
