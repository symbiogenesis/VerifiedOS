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

## Scalar retirement adapter

[The scalar adapter](src/resident_scalar.c) specializes the accepted
[kernel producer](../kernel/include/vos_effects.h) to the finite resident
holder/window shape. Its [private attempt record](include/vos_resident_scalar.h)
binds the current kernel epoch, the exact composition-declared closed victim
set and every configured holder slot, including slots with pending transfers.
An uncovered slot or stale initial epoch refuses before effects. Declared
kernel clearing regions must be disjoint from the retained owner and attempt.
These pointer checks do not establish the composition's complete machine
holder/base inventory or authentic capability bounds.

Prepare closes admission and cancels every reservation and transfer using the
existing resident owner, then obtains the actual kernel's one-use publication
ticket. A producer refusal leaves occupied bytes unchanged in closed quarantine
and never waits for holder acknowledgment. Finish checks the unchanged closed
owner and current epoch, consumes the actual publication ticket, invokes
`vos_kernel_retire`, and requires its semantic completion and exact successor
epoch. Attempt failure is sticky, including a partial teardown that advanced
the kernel epoch without complete architectural observations. Late transfers,
changed resident identity and replayed finish calls cannot advance the attempt.
The adapter has no read entry, so repeated reads introduce no attempt stores.

Even successful semantic completion leaves backing occupied and unchanged in
quarantine. It does not clear the old revocation masks, replenish roots or
authorize `vos_resident_retire`'s reuse seam. Post-barrier sweep, complete
sanitization and reuse evidence remain with their machine owners under the
[retirement qualification order](../docs/implementation/contracts/workflow-formal.md#concrete-retirement-adapters-and-qualification-order).
Actual bitmap publication/readback, resident-register scrub, exclusive dispatch
and complete composition ownership remain the scalar producer's trusted target
prerequisites; this source adapter manufactures none of them.

`python tools/run.py test --only test_resident_scalar --jobs 1` registers the
native campaign for Linux, including Host CI's Ubuntu runner. It links the real
kernel, supervisor, resident, storage-publication and crypto-core sources,
exercises both root kinds (`system-integrity` and `user-data`) over committed
CoW B+ tree roots verified through `vos_storage_verify_resident` with
independent pending readers and a failed holder, and checks actual clearing of
declared private bytes and saved capability slots. The existing architectural
observation seam is mocked. Refusals cover corrupted checkpoint MACs, incomplete
holder coverage, stale epochs, aliasing clearing regions, active copy work, an
open victim set, missing publication or scrub, owner drift and late completion.
Compiled defects omit coverage, epoch binding, cancellation or semantic
completion, change the retained binding, or release backing on semantic
completion; each must fail its intended oracle after compiling. This
source-level campaign supplies no target correspondence, complete writer trace
or safe-reuse proof.

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

## Authenticated storage and crypto verifier join

[The storage publication producer](src/storage_publish.c) and
[crypto-core compartment](src/crypto_core.c) supply the real cryptographic
verifier callback `vos_storage_verify_resident` for `vos_resident_complete`
under [its public header](include/vos_storage_publish.h). Given an open
`vos_storage_store` (`system-integrity` at `VOS_RESIDENT_ROOT_SIGNED` or
`user-data` at `VOS_RESIDENT_ROOT_COMMITTED`), `vos_storage_bind_resident_identity`
computes the domain-separated `vos_crypto_core_keyed_digest` (R-10-016) over the
object bytes and encodes the deterministic B+ tree authenticator entry
`resident_tree_value(root, version)`. During every `vos_resident_complete` call,
`vos_storage_verify_resident` checks the store's domain and root kind, verifies
the checkpoint MAC and any sealed `Fresh` epoch floor (R-10-013e), recomputes
the domain-separated object digest over the isolated backing snapshot, and looks
up `identity->object` in the store's authenticated CoW B+ tree (R-10-001,
R-10-003, R-10-006a, R-10-006b). Any tampered backing byte, wrong domain,
uncommitted object or rolled-back store state refuses before `vos_resident_complete`
copies a byte to the caller, while repeated reads across independent holders
record zero writes to `VOS_RESIDENT_COMMON`.

`vos_storage_admit_resident` authenticates the identity, bytes and tree membership
once into a receipt held privately by the serialized owner.
`vos_storage_verify_admitted_resident` reuses that membership while the exact
checkpoint, domain, key epoch and resident identity remain unchanged. It checks
key availability and the current Fresh seal and hashes the actual mutable host
backing on each completion. A checkpoint change requires new admission; a locked
key, advanced Fresh seal, changed backing, identity or length refuses. Neither
receipt nor common resident state is written during repeated reads. Corruption of
external arena blocks after admission does not invalidate already authenticated
resident bytes; a new storage lookup still detects that corruption. The
[persistent-image join](host/storage_blkdev_join.cpp) uses the receipt callback.

The [receipt campaign](host/resident_receipt.c), registered by
`python tools/run.py test --only storage_resident_receipt`, exercises both root
kinds, independent reader windows, unchanged owner/receipt state, admission
refusal, backing/checkpoint/identity substitution, lock and Fresh-epoch
invalidation. This host adapter retains byte authentication. Eliminating that
hash requires the protected immutable backing and lifetime evidence in the
[resident contract](../docs/implementation/contracts/resident-object-reads.md).

`python tools/run.py test --only storage_publish` exercises
`vos_storage_verify_resident` across both storage instances and kills a compiled
mutant that skips the authenticated B+ tree lookup. Gallina/Python
correspondence, purecap/Sail target execution and complete concrete
writer/resource qualification remain open. This is a C implementation checkpoint
and compiled-control campaign, not Q44 or M5.3d completion. Complete hosted
model/proof acceptance follows the repository validation handoff; behavior
counts here supply no benchmark or throughput claim.

This document uses `CC-BY-4.0` under [COPYRIGHT.md](../COPYRIGHT.md).
