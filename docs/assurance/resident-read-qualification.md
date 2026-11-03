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

## Retained proof evidence

[Focused reservation proof evidence](../implementation/retained-evidence/q44-resident-reservation-20261014/manifest.json),
SHA256 `de0e639612ed7a6b7b4f1f40a637a98462756b9efcbd9943460b884d8949fd0f`,
binds the generated-header source, compiled object, exact commands and bounded
candidate journal. At locked Rocq 9.3.0 with the proof gate's strict flags,
selected-source compilation, native inventory and assumption queries passed;
every enumerated symbol had a closed global context. Recursive kernel rechecking
of the module and installed library closure passed without an admitted root or
covered sealed field. Selected-source non-vacuity found no unbuilt record;
closed `witness_<Record>` definitions accompany every carrier record.

The retained run used eight of twelve permitted attempts within a thirty-minute
active-repair budget. Its focused results supply local feedback; fresh hosted
proof acceptance remains deferred to user-managed cold Guest CI.

## Remaining qualification

Q44 still owes Python/scalar/storage correspondence, verifier soundness,
replacement, renewal, crash and re-admission across backing reuse, complete writer
observation, and full resource/retirement accounting. Finite-counter proofs cover
admission tokens and request sequences; private read/authentication counters and
external clock bounds have no general exhaustion theorem here. Compiled production
defect controls, both real storage instances and the completion/sweep/zeroization
barrier remain Q44/M5.3d joins. This reference discharges no complete requirement.

This document uses `CC-BY-4.0` under [COPYRIGHT.md](../../COPYRIGHT.md).
