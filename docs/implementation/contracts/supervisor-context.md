# Supervisor lifecycle context slots

This contract fixes the transport between R-12-073's contained supervisor and
R-12-074's trusted lifecycle effects. It is an implementation of the request
surface admitted by those entries and R-07-031b. It adds neither an invocation
number nor an object, table, thread, queue or scheduled worker. M7.1b owns the
nonblocking supervisor adapter, M4.4b-i the boundary consumer and trusted effects,
and M7.1a their actual target join. The existing synchronous
[effects interface](../../../supervisor/include/vos_supervisor_effects.h) remains
a kernel-internal orchestration and comparison seam, not an ordinary compartment
call into privileged C.

## Placement and publication

Composition reserves a finite sequence of scalar slots inside the supervisor's
already placed partition context. Its request slots are writable only by the
supervisor and kernel; its acknowledgment and snapshot slots are writable only
by the kernel and readable by the supervisor. The capabilities exposed to the
supervisor cover exactly those respective regions with the stated permissions.
They exclude the saved context, grant roots, handler stack, other contexts and
all kernel-private lifecycle state. They contain scalar values, never supplied
kernel pointers, executable callbacks or transferred capabilities.

The kernel reads these slots only at the timer boundary ending the supervisor's
own assigned slot, with the supervisor stopped. It consumes at most one published
request. The supervisor clears the publication sequence before changing a
request, fills its scalar slots, orders those stores, and writes the nonzero
sequence last. Publication is the final act of the completed reaction; only its
fixed poll-site return follows it. A timer cut before publication supplies no
request and does not resume a partial reaction. A synchronous fault invalidates
the publication before any boundary consumption.

Sequences are nonwrapping 64-bit integers. A request is fresh only when its
sequence is the kernel's last acknowledged sequence plus one; zero, repetition,
a gap or exhaustion refuses without performing an effect. The kernel publishes
all acknowledgment fields before their sequence. The supervisor consumes an
acknowledgment only for its outstanding sequence. No phase retains a borrowed
stack capability, live kernel lock or continuation across a boundary.

## Closed operations and validation

The operation set is `retire` and `start`. Every request carries its sequence,
operation, full 64-bit expected epoch, ownership-closed member mask and a bounded
ordered batch of unit/grant-mask pairs. Unused slots are zero. A `retire` request
has an empty batch; a `start` request carries exactly the manifest order for its
named set. Composition fixes the slot count from the existing supervisor unit
bound. The layout generator owns offsets and widths; no C struct overlay is a
wire decoder.

The boundary consumer validates the complete scalar input before effects. It
checks the sequence, operation, widths, padding, current epoch, exact manifest
restart set, batch bound and order, and each exact current-epoch grant mask.
The supervisor supplies no allocation, authority source, arbitrary victim or
successor. A stale snapshot, invented or retired grant, widened member set or
malformed batch refuses before starting a unit. Initial bring-up is permitted
once; later starts require the kernel's completed retirement for that same set.

Retirement stops the exact admitted set and must satisfy the existing semantic
completion predicate over actual bitmap publication, epoch advancement, resident
roots, saved contexts, loans and device boundaries. Its eager clearing covers
every owned stack, staging span, ring, saved capability and live protected frame.
An incomplete result leaves the set unavailable and cannot authorize a start.
Fresh authority is installed only through R-12-074's checked re-instantiation of
the manifest. Reusing an address or clearing a revocation bit without the required
sweep and zeroization is not a re-grant; a new epoch number alone is insufficient.

Backoff is a deadline measured from acknowledged completion with the admitted
clock. Its attempts and delay are checked against kernel-retained lifecycle
state and the manifest. Waiting consists of later complete supervisor reactions
in its existing slots. The boundary consumer neither spins to await the deadline
nor runs the supervisor on another partition's behalf. It refuses an early start.

For an accepted start batch the kernel holds its existing dispatch exclusion
from current snapshot acquisition through the final start acknowledgment. Each
start receives exactly the checked manifest roots for the current generation;
a failed start publishes the acknowledged prefix and performs no later start.
The acknowledgment names its sequence, status, full epoch, completed prefix and
current snapshot. A refusal does not pretend that an earlier acknowledged prefix
was rolled back. The supervisor handles that result in its next complete reaction.

## Timing, faults and acceptance

The composition declares a finite upper bound for the entire boundary consumer,
including validation, bounded clearing and effect execution. That work must fit
R-07-040's admitted padded boundary constant for this composition. Both the empty
and occupied request paths release the successor at the same fixed instant. A
composition without this bound is refused. Requests change no table slot, width,
tenant, grant to another label or successor-selection rule. This handler is part
of the existing boundary path, not a third background task under R-07-020.

The nonblocking adapter preserves the existing manifest, start/restart plans,
backoff and generated lifecycle fixtures. It has explicit publish, await-ack,
backoff and refused states; a pending acknowledgment is not a successful callback.
Faults between phases restart from the kernel's last acknowledged sequence and
current snapshot, never from a saved partial callback continuation.

Acceptance requires actual non-ASR supervisor publication and kernel boundary
consumption on the target. Generated plan comparisons cover accepted and refused
lifecycle cases. Target controls additionally cover partial publication, replay,
sequence exhaustion, stale epoch, incomplete retirement, early backoff, wrong
batch order, failed-start prefix and faults between phases. Trace checks establish
the request-region permissions, absence of an extra syscall, bounded handler,
fixed successor release and fresh entry after a cut. The first payload/notification
and fault/restart join remains the
[scalar integration checkpoint](boot-roster.md#2a-scalar-integration-and-producer-joins).
Host callbacks, a writable acknowledgment region, a fabricated completion bit or
an ASR-enabled supervisor fail this contract.
