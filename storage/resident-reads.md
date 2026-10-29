# Bounded C resident adapter

[Q44's landed contract](../docs/implementation/contracts/resident-object-reads.md)
owns acceptance. [The C adapter](src/resident_reads.c) adds executable reservation,
request and completion operations over one service-owned immutable backing and
two independent holders. It copies publication bytes, binds exact owner, domain,
object, version, root, boot, token and window, and keeps each holder's request
sequence across retirement and crash. Exhaustion refuses before wrapping. This
first shape refuses another publication while its backing is retained; it does
not yet implement CoW predecessors, individual close or reservation renewal.

Matching completion checks current rights and expiry, calls the verifier on an
isolated snapshot of the whole actual backing, then checks that the owner and
pending request stayed unchanged before publishing exact window bytes. Empty
reads still invoke verification. Wrong identities, a stale completion, changed
system generation, revocation, failed authentication and output aliases into the
owner refuse without publishing payload. The root is an opaque identity supplied
by the caller: the adapter implements no cryptographic authentication or generation
admission. The native fixture's independent expected bytes and roots supply its
verifier seam.

The stored inventory has three parts. `common` contains backing, identity,
reservations, grants, admission/version/token limits and the generation/boot;
`pending` and `sequence` are holder-private; caller outputs are reply storage.
After initialization, every explicit adapter store to those regions calls the
observer, including same-value stores. Initialization and bounded stack snapshots
are outside the repeated-read owner-state projection. The native observer derives
classification from the actual destination address and rejects a mismatched label.
With fixed admissions, successful begin/completion calls store only holder-private
state and replies, with both holders serving independently expected bytes.

The observer is a trusted read-only harness hook. Verifier implementation work and
arbitrary external writes through its opaque argument are outside that hook's
coverage. A fixture callback that changes common state receives no payload because
the completion snapshot check detects persistent drift; this is no rollback or
complete callback-write observation. The verifier's immutable-argument contract
also applies to its isolated identity and payload snapshots: casting away `const`
is outside the interface. Neither these explicit-store observations nor
an unchanged common snapshot establishes a complete caller-to-owner target trace.

Retirement closes admission and cancels the complete finite holder/request set
before touching backing. It never waits for holder cooperation. Without its
trusted barrier input it leaves closed, occupied, unchanged backing in quarantine
and refuses replacement. With that input it zeroes and releases backing. The
barrier is an explicit test seam; this source does not establish actual kernel
containment, sweep, zeroization completion or physical reuse. Crash invalidates
reservations and grants while retaining monotonic request counters; retained bytes
never recreate an old reservation.

`python tools/run.py test --only test_resident_reads_c --jobs 1` compiles the native
fixture and every defect before executing it. The pristine fixture exercises both
root kinds, independent holders, finite repeated/empty reads, current rights,
identity/window checks, callback drift, quarantine, retirement, reuse, crash and
counter exhaustion. Executed defects add a common increment/decrement, replacement
touch or hidden reacquisition, omit domain/authentication/sequence checks, exceed
the counter bound or zero retained bytes early. A compilation failure is reported
as stillborn and supplies no kill evidence.

The same fixture includes the real [node-image producer](src/node_image.c) and
decoder under their committed interface. For both root kinds, it independently
constructs the expected canonical leaf bytes, publishes the actual encoder output,
serves two independent entry/full-image windows and decodes the returned whole
image. This concrete byte witness retains the fixture-verifier seam and supplies
no equivalence to cryptographic storage authentication.

The actual storage/crypto owner, accepted scalar
completion interface, Gallina/Python correspondence, target artifact and complete
concrete writer/resource qualification remain open. This is a C implementation
checkpoint and compiled-control campaign, not Q44 or M5.3d completion. Complete
hosted model/proof acceptance follows the repository validation handoff; behavior
counts here supply no benchmark or throughput claim.

This document uses `CC-BY-4.0` under [COPYRIGHT.md](../COPYRIGHT.md).
