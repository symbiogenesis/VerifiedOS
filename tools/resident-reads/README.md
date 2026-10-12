# Finite resident-read reference

[Q44's contract](../../docs/implementation/contracts/resident-object-reads.md)
owns the obligations. This checkpoint implements a finite Python host reference
in [resident_reads.py](../vos/resident_reads.py), with independently expected
payload/refusal cases in [test_resident_reads.py](../tests/test_resident_reads.py).
Q44 remains open.

`python tools/run.py resident-reads --json` runs both system-image and user-data
fixtures with two independent holders, fixed admissions and several read counts.
The report binds its exact sources, configuration, stored-cell classification,
successful reads, returned bytes and modeled writes. These are behavior counts;
the command measures neither throughput nor latency. Focused checks use
`python tools/run.py test --only test_resident_reads --jobs 2`.

## Declared service shape

One storage owner serves one domain and one logical object. Each immutable
resident has an exact owner/domain/object/version/root identity. A holder's
reservation additionally binds boot epoch, unique finite token, backing slot and
exact byte window. Read admission and completion both check current grant and
identity; completion hashes actual retained bytes before publishing payload.
The independently authored fixture provides the trusted SHA-256 root. This is an
integrity seam, with no signatures, key custody, generation admission or storage
Merkle-tree implementation. A changed system-image generation refuses old reads;
replacing user data preserves a still-authorized predecessor's bytes and identity.

`Bounds` owns the finite composition. Backing bytes include current, predecessors
and quarantined residents. Metadata has one reservation per declared holder;
each holder has one outstanding transfer/request SPSC slot. Read length, retained
predecessors, expiration, renewal count, tokens, read sequences, version numbers,
clock and boot/generation epochs have finite limits with explicit refusal.
The reference never wraps identifiers or silently pins another backing range.
Publication charges every existing resident against the new version's predecessor
limit, including closed quarantine after the current version has stopped. Exhausted
predecessor capacity refuses publication without consuming a version; completing a
retirement can discharge that capacity and allow a later admission.

Retirement closes admission, cancels accepted private transfers, removes held
reservations, performs a modeled barrier, zeroizes and releases backing. Its
bound is independent of holder acknowledgment. When the barrier is unavailable,
it refuses after cancellation and retains closed backing inside the charged
quarantine. The backing safety oracle checks the exact resident identity for every
live reservation and accepted transfer. Repopulating a prematurely freed slot with
replacement bytes cannot satisfy that oracle merely because the slot is occupied;
the same-slot reuse control fails beside a valid retained-predecessor control.
Crash clears volatile reservations, grants and replies; retained data
does not recreate old authority. The scalar producer's existing fresh-replacement
observations cannot authorize this model's physical reuse. Correspondence to
[M4.4b-i's accepted observations](../../kernel/README.md#bounded-scalar-effects-and-fault-restart),
including actual holder inventory, containment, sweep and reusable backing, is open.

## Stored writes and observation boundary

Every modeled stored cell is declared before execution; `_put` refuses an unknown
cell and records every store, including stores that restore the previous value.
Initialization closes the declaration path and exposes a read-only classification
inventory. Later declarations cannot reset a stored cell without observation,
introduce an unknown writer or relabel a common writer. Executed refusal controls
exercise declaration, classification mutation and public inventory replacement
beside a common-counter defect that still returns independently expected bytes.
This protects those inventory interfaces; direct manipulation of private Python
internals remains an explicit harness seam rather than a tamper-resistance claim.
Common cells contain backing/catalog, reservations, grants, roots and identifiers.
Per-holder pending transfer, sequence, successful-read and authentication counts
are session-private. Request and response publication are per-holder SPSC cells.
Every admitted read/completion writes only those private and SPSC cells. Explicit
admission, renewal, close, replacement, revocation, clock, generation and retirement
operations have separately named stores outside that read class. SHA-256 evaluation
and byte copying have read work even when common metadata writes are zero.

The external observer's event list and Python runtime allocations are harness
work, outside this modeled service-state projection. Counts cover the declared
abstract stores, not Python machine instructions or every concrete target writer.
The target must separately bind its complete caller-to-owner trace to this
classification; relabeling a common counter as statistics is insufficient.

The executed Python controls add common increment/decrement, replacement touch
and hidden reacquisition while still returning the correct bytes. Their traffic
predicate fails. Other executed controls omit domain/root/authentication checks,
rebind an old handle, free backing with accepted transfers, wrap tokens or exceed
the holder-independent retirement bound. Every control has a passing counterpart
and its independently checked refusal, payload, uniqueness or lifetime oracle.
These controls execute as Python constructions; they are not compiled target
mutants and provide no compiled-control acceptance evidence.

The locked reference theorem/assumption audit, scalar producer correspondence,
concrete storage authentication and system-image/user-data target joins, compiled
defect controls, complete target write observation and target resource/WCET
qualification remain open. This checkpoint supplies no universal preservation or
reuse proof and does not complete M5.3d or Q44.
