# Bounded resident reservation proof increment

[ResidentReads.v](../../proofs/ResidentReads.v) supplies Q44's first executable
reservation reference and closed proofs under the
[resident-object contract](contracts/resident-object-reads.md). It models one
charged immutable backing, two independent holder slots and one outstanding
request per holder. This is a reference increment; Q44 remains open.

Admission checks the exact owner, domain, object, version and root identity,
current rights, generation, bounded window, expiry and finite token capacity;
it captures the current boot epoch.
`admission_installs_exact_window` proves those checks install the stated window.
`begin_stores_bounded_request` proves accepted requests fit that window and take
the next nonwrapping private sequence. `admitted_completion_within_window` joins
those transitions to the exact retained slice, using the window property that
admission establishes. It does not claim confinement for an arbitrarily forged
pending request in an arbitrary state.

Completion checks the current reservation, authority, identity, boot/generation
and expiry again, and invokes an abstract verifier on the actual backing and its
bound root before returning bytes. Failed authorization or verification returns
no payload. The model assumes no verifier soundness or hash injectivity.
The fixture verifier has independently stated expected bytes and root values;
it implements no cryptographic primitive.

The common-state frame and write-journal theorems cover begin, completion,
synchronous reads and repeated reads with fixed reservations. The journal
includes every declared abstract store, including repeated-value stores;
`no_common` rejects a common increment followed by a restoring decrement.
These theorems concern the reference's abstract stored cells. They do not
establish complete concrete caller/service write observation.

Both system-image and user-data witnesses admit two holders, serve their exact
independent windows repeatedly, accept an empty boundary read and retain two
simultaneous transfers. Refusals distinguish wrong domain/version/root/window,
revoked or expired in-flight authority, generation change and stale completion
against a successor request. An omitted-verifier construction serves incorrect
bytes beside the refusing control. The independent retention observation covers
reservations and accepted transfers; same-identity mutation or zeroization fails
it even when only an in-flight transfer remains. Completion preserves this
observation. Generic begin/admission retention preservation is not claimed.

A refused begin preserves an accepted pending request. Unmatched completion
preserves all state and emits no store; completion and modeled retirement
preserve private sequence counters. Retirement cancels reservations and transfers
without a holder acknowledgment. When its modeled barrier is unavailable, it
keeps the original bytes in closed, charged backing. The barrier input supplies
no containment, sweep, zeroization or physical reuse evidence, and this source
proves no retirement cost bound.

## Focused feedback

[Focused resident reservation proof evidence](retained-evidence/q44-resident-reservation-20261014/manifest.json), SHA256 `de0e639612ed7a6b7b4f1f40a637a98462756b9efcbd9943460b884d8949fd0f`.

The retained report binds the exact generated-header source and compiled object.
The selected-source check used the locked Rocq 9.3.0 switch and the proof gate's
strict flags. Compilation passed in 2.71 seconds; native inventory and assumption
queries passed in 1.91 seconds, with every enumerated symbol closed under the
global context. Recursive kernel rechecking of this module and its installed
library closure passed in 13.62 seconds, with no admitted root or covered sealed
field. The selected-source non-vacuity check reported no unbuilt record; closed
`witness_<Record>` definitions accompany every carrier record.

The native work directory was
`/root/build/lane-checklist-20261014-supervisor/resident-proof-focused`.
The focused driver staged only this module and used the existing
`gallina.vector_prover`/`compile_one`, selected-source `_check_source` and
`_recheck_joint`/`_worker_fault` helpers. No full proof suite ran locally.
The bounded journal retains eight candidate attempts within the twelve-attempt,
thirty-minute active-repair budget. Two attempts timed out on unrestricted
symbolic simplification of a lifetime witness; introducing its let-bound names
and computing closed cases resolved that proof without changing its statement.
Each candidate command resolved the same locked `rocq c` binary and strict flags
as the final report, followed by `-q -Q proofs "" -Q harness ""` and
`proofs/ResidentReads.v`. Attempts six through eight additionally used `-time`
to locate the slow sentence. The first five had a sixty-second limit, the sixth
a twelve-second diagnostic limit and the last two a twenty-five-second limit.
Final generated-header compilation, assumption inspection and kernel feedback
are separately recorded. These observations are local feedback, with fresh
hosted proof acceptance deferred to the integrator's cold Guest CI handoff.

## Remaining qualification

No theorem here refines the Python service, scalar retirement, concrete storage,
cryptographic authentication or a target artifact. Replacement, renewal, crash,
re-admission across backing reuse, complete writer observation and the full
resource/retirement accounting remain open. Private read/authentication counters
and external clock bounds have no general exhaustion theorem in this increment;
its finite-counter proofs concern admission tokens and request sequences.
The compiled production defect controls, both real storage instances and the
existing completion/sweep/zeroization barrier remain Q44/M5.3d joins. No complete
requirement discharge or whole-Q44 acceptance follows from this reference.

This document uses `CC-BY-4.0` under [COPYRIGHT.md](../../COPYRIGHT.md).
