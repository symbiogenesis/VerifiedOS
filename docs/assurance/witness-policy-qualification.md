# Witness-policy qualification

This is [Q22b's](../implementation/implementation-checklist.md#q-assessment-actions)
qualified interface and bounded executable model for
[R-13-023c](../spec.md#r-13-023c). The
[supply-chain statement](../spec.md#r-13-023a) separates witnessed public commitment
from source correspondence, confinement and release selection. This document reads
that distinction together with the register's inclusion, history and fail-closed
requirements. It supplies no production witness service, cryptographic verifier or
machine-checked policy theorem. CJ-WITNESS remains open at the formal model and
theorem boundary assigned to M5.5; M6.2c owns the local evidence validator, and M5.4
consumes its decision in the update transactor.

## Fixed policy and threat model

A policy names a trust scope, an epoch, distinct witness identities and distinct
verification keys, a population size N, a threshold K, and a bound f. It admits
every size-K subset. N is positive, 1 <= K <= N, and 0 <= f < N. The Byzantine set
is fixed for the epoch and has at most f members. Its members may sign arbitrary
statements, equivocate and withhold. The log and network may equivocate, reorder,
replay and withhold. Fresh clients have authenticated policy/bootstrap inputs but
no earlier local checkpoint. Clients retain authenticated durable pins thereafter.

Honest witnesses authenticate their own state, check that a proposed checkpoint
extends it, and persist before releasing a signature. An honest identity cannot
be cloned into independent signers or restarted from an unauthenticated empty
state. Concurrent signing operations at one identity are serialized; the model's
atomic state operations assume that discipline. A mobile adversary that accumulates
more than f compromised identities in one epoch violates the declared fault model.
Later compromise that enables old-epoch signatures counts against that epoch's
bound for as long as those signatures remain acceptable; terminal state alone
supplies no key-erasure or forward-security guarantee.
Operational independence and different operator names establish none of these
conditions by themselves. Deployment must justify the fault bound, authentication,
durability, rollback detection, serialization and bootstrap authority assumptions.

Every pair of size-K quorums has at least 2K - N members in common. Requiring
`2K - N > f` leaves an honest member in that intersection. Conversely, if the
inequality fails, two quorums can intersect only in faulty witnesses, including
the empty intersection of two honest witnesses under 1-of-2. Those witnesses can
each extend their common initial checkpoint differently for fresh clients.
The policy refuses 1-of-2 even when every received signature authenticates.
Non-flat policies require their own intersection argument and are outside this
model. A larger accepted quorum contains a size-K quorum, so the minimal quorums
suffice for this flat-policy calculation.

Availability is a separate assumption: at least K enrolled witnesses must be
responsive and willing to sign the same consistent request, and the relevant
messages must arrive. If all Byzantine witnesses withhold and at most o additional
honest witnesses are unavailable, the sufficient count is `N - f - o >= K`.
An asynchronous or partitioned network supplies no response deadline. Fewer
responses stop installation; a threshold is never reduced to restore progress.
Unanimity can meet safety and remain unavailable after one withholding witness.

## Durable witness state and recovery

[The executable model](../../tools/vos/witness.py) represents a checkpoint as a
complete tuple of log identities. Exact prefix comparison stands for verified
consistency, and membership stands for verified inclusion. A signature carries the
complete policy, signer identity/key, checkpoint and optional terminal transition.
Its authentication flag is an ideal verifier's result, not cryptographic code.
Fixtures and their objects are trusted symbolic inputs; constructing a Python
object establishes no authenticity in a real deployment.

An honest witness separates the volatile proposal from its durable record. The
record carries the checkpoint, a monotonic serial and any terminal transition.
Preparation checks consistency. Commit atomically persists the entire successor
and updates the authenticated antirollback anchor. Release is enabled only when
the prepared record equals that committed state. The anchor is an explicit ideal
primitive outside the modeled failing storage, not another unprotected copy in
the same failure domain. A concrete witness deployment needs authenticated recovery
or identity retirement if no such continuity evidence survives.

A crash before commit loses the proposal and releases no signature. A crash after
commit may lose the reply but keeps the successor; retrying the same statement is
safe, while a conflicting successor is refused. Missing storage, a stale serial or
changed checkpoint/terminal state is quarantined by comparison with the trusted
anchor. Recovery authenticates the exact policy, identity, key and latest complete
record, including terminal status. An authentic old record is insufficient.
Recovery without the latest continuity evidence is refused; retiring the identity
then follows the policy transition or explicit rebootstrap rule below. The model
does not turn an undetected rollback into a detected one: the protected anchor's
existence and adequacy remain an external assumption.

## Epoch continuity and explicit replacement

An ordinary shared checkpoint is insufficient for a disjoint policy change.
Two independently safe populations can both sign that prefix and subsequently
sign different extensions. The executable counterexample constructs exactly those
valid certificates. The continuous transition interface therefore requires an old
terminal quorum, in addition to new-policy acceptance of the same anchor.

The terminal statement binds the entire old and new policies, their scope and
consecutive epoch numbers, and the exact anchor checkpoint. Each old signer checks
that the anchor extends its own durable history, then atomically persists both
that checkpoint and a permanent closure of its old-epoch signing authority before
releasing the seal. It may retransmit the identical seal; it refuses an ordinary
old-epoch signature, another destination, or another terminal checkpoint. Recovery
preserves this closure. Every old accepted quorum intersects this terminal quorum
at an honest identity, so an accepted old history is compatible with the anchor
and the remaining old signers cannot form a conflicting accepted quorum under the
stated fault bound. This is the argument to formalize, not a completed theorem.

The new quorum accepts the exact anchor under the complete destination policy.
Its later accepted quorums intersect that acceptance at an honest new witness.
A client checks both certificates and consistency from its own pin before changing
policy and pin together. Destination keys may be entirely disjoint: preservation
comes from closing the old epoch and initializing the new one through the bound
certificates, not from either policy's independent validity. Unavailable old
signers can prevent this transition, even if a new population is responsive.
Authentication of the policy path is required for fresh clients too; accepting an
arbitrary advertised replacement is no bootstrap procedure.

The alternative is an explicitly authenticated rebootstrap decision. It names the
old policy, full replacement policy, anchor and replacement trust assumptions, and
uses a fresh trust-scope identifier. The replacement anchor needs a valid new-policy
certificate. It may conflict with the old pin because the old population-wide
continuity claim is expressly surrendered; the returned client state records that
loss. An unauthenticated decision, empty replacement assumptions, changed binding,
or attempted reuse of any earlier trust scope on that client's path is refused.
Bootstrap authority must supply a fresh scope for the population, beyond the
client's local record of previously used names. The concrete authorization
and audit representation belong to M6.2c's admission interface. These witness
changes are independent of the holder's enrolled generation-key set and impose
no requirement for two generation keys.

## Local admission boundary

An accepted pack must bind inclusion of its exact base-image root and every
admitted package identity to an authenticated checkpoint. Package identity covers
the content-addressed source closure and manifest/interface hash that
[R-13-023b](../spec.md#r-13-023b) specifies; the generation root
and roster-specific emitted manifest are not substituted for that identity.
The model uses symbolic names for those values. It checks authenticated distinct
enrolled signatures, exact policy/epoch/checkpoint/transition binding, threshold,
the declared flat policy's safety predicate, inclusion and consistency with the
client's pin. Repeated, foreign or wrong-key signatures cannot contribute a quorum.

These predicates do not parse fixed-layout bytes, verify a hash or signature,
prove a Merkle path, enforce input/resource bounds, establish crash-atomic device
storage, or implement the update transaction. M6.2c owns that realization and
refinement against the accepted policy model, reusing the project's existing
primitive and parser foundations. It must refuse malformed, over-limit, forged,
stale, duplicate, absent and misbound evidence and expose the persistent pin and
transition result to M5.4. The abstract client keeps its running generation and
pin unchanged on every refusal. Crash consistency of the real pin/update join
remains an implementation obligation at those owners.

## Executable qualification and remaining proof

```console
python tools/run.py witness qualify
python tools/run.py witness qualify --json
python tools/run.py test --only witness
```

The qualification command enumerates every N from one through its declared bound,
every K and f in the domain above, every ordered pair of size-K quorums, and every
fault set of size at most f. Its comparison directly subtracts each enumerated
fault set from each intersection and compares the result with the inequality.
The maximum supported N is six, keeping this complete bounded check inexpensive.
Output computes the policy and assignment counts and identifies the exact model
source with SHA-256. It gives no result outside that declared domain.

[The behavioral cases](../../tools/tests/test_witness.py) include fresh 1-of-2
split views, safe but unavailable policies, signature/policy binding errors,
checkpoint and inclusion refusal, every crash cut around prepare/commit/release,
and every length-seven schedule over the two fork proposals, commit, release and
crash. Additional examples cover lost/rolled-back state, authenticated latest
recovery, terminal closure across recovery, disjoint shared-prefix failure,
bound terminal transitions and authenticated rebootstrap with a new scope.
The schedule bound is explicit; unbounded histories, arbitrary schedules and
real cryptographic inputs are not verified by these examples.

Two separately logged valid variants remain accepted for different clients under
one identical witnessed checkpoint. The example models their inclusion; their
correspondence and confinement evidence is an independent assumed admission input.
Nothing in witness policy decides which valid software a recipient ought to get.
The selective-delivery residual therefore remains with
[R-13-023a](../spec.md#r-13-023a), including unavailable source or
audit material and the absent release-selection/monitor construction.

M5.5 owns the reviewed Gallina policy/history model, general honest-intersection
and compatible-history theorems, crash/recovery and terminal-transition invariants,
explicit authentication/persistence/fault assumptions, constructive accepted and
rejected examples, and the repository's assumption and non-vacuity gates. M6.2c
owns the bounded local evidence validator and its refinement, followed by M5.4's
update-transactor join. Those priced checklist items exclude production operation
of external witnesses and creation of missing cryptographic or parser foundations;
a missing prerequisite is priced before incorporation. Bounded qualification
closes neither child and establishes no claim that a deployment satisfies the
external witness assumptions.
