# Supervisor core

This directory owns M7.1b's bounded GC-free C core, authored against
[SupervisionTree.v](../proofs/SupervisionTree.v). It admits a finite manifest, checks
start order, computes detector/action, dwell, window, boot and backoff decisions,
and executes ordered start requests through explicit kernel effect bindings,
with grants filtered by the current revocation snapshot. The
[roster contract](../docs/implementation/contracts/boot-roster.md)
fixes its place as the kernel's first partition.

**This is a host-checked core, not an executable target roster member.** The accepted
M1.2f backend, M4.4 kernel effect bindings, authenticated manifest handoff, and M7.1a image and
boot trace remain open. The code does not perform compartment entry, teardown,
zeroization, revocation or capability derivation. M6.1b retains the Lustre/Vélus
lowering and its control-plane obligations.

## Manifest source and implementation choices

[src/manifest.c](src/manifest.c) is the proposed M8a manifest source while M5.4's
object system is deferred: an immutable typed C object compiled into the supervisor
member of the signed, admitted generation. The image's producer must bind these
bytes to admission and measured boot. There is no runtime text parser or external
configuration lookup. The current object names local unit 0 as `crypto-core`, 1 as
`storage` and 2 as `copy-service`, orders them accordingly, and declares storage's
edge to the crypto core. Those IDs are local to the supervisor, not boot ranks.

The thresholds, schedule and whole-roster restart victim in that object are
bring-up choices, with no measured time unit or availability claim. Its restart
membership must be accepted as ownership-closed by the composition owner. Its
source is concrete; its authenticity, resource judgment and target binding remain
the composition join. These values are separate from the Gallina demo used by the
differential harness.

[include/vos_supervisor.h](include/vos_supervisor.h) fixes capacities of 16 units and
16 backoff entries for this build. These are implementation bounds, not normative
limits. No allocation, recursion or garbage collector is used. Manifest admission
refuses duplicate, missing, unknown and early starts, excess capacity, out-of-range
action codes, a clear threshold above assertion, and a backoff beyond its ceiling.
The equal-threshold case agrees with the statement's explicitly open band choice.

Detection receives only its own signal. A signal is the normalized detector quantity
that the Gallina definition compares with `>=`; translating raw pool occupancy or
ages to that quantity belongs to the supplying kernel adapter. `decide` takes an
already admitted immutable manifest, reads only the caller's declared counters, and
reports each predicate separately. It does not silently combine a fired detector,
dwell admission and boot admission into an action execution rule. In particular,
rate-limit escalation remains visible even when ordinary admission is false.

`plan` returns the initial bring-up order or the composition-declared restart
subset in that order, its stop set, and its declared backoff. `spec_regrant`'s
epoch-filtered arm is used: every requested grant is a manifest edge not retired
in the supplied current snapshot. This chooses the statement's implementation arm
and does not resolve its documented normative regrant gap. No private memory or
old capability slots enter the plan.

Epoch snapshots, requests and comparisons carry the full nonwrapping 64-bit
counter fixed by R-08-007a. The supervisor never increments that counter.

## Effect execution boundary

[src/effects.c](src/effects.c) implements the bounded orchestration in
[include/vos_supervisor_effects.h](include/vos_supervisor_effects.h). The caller
selects initial bring-up or an admitted restart and supplies trusted kernel
bindings. Manifest and callback admission happens before any effect; copies keep
callbacks from changing the selected manifest or callback table during the run.
The caller still owns the detector, dwell, window and boot policy judgment:
`execute` does not turn the independent `decide` predicates into an invented
action rule or reset their declared counters.

A restart first calls the binding that completes teardown and eager zeroization
of the composition's ownership-closed stop set and returns its actual
`vos_completion` record. The adapter applies the kernel's
[`vos_semantic_completion`](../kernel/src/context.c) predicate to that record.
Epoch advancement alone does not satisfy it. Only after completion does the
adapter wait the declared delay, acquire serialization and read a fresh snapshot,
regenerate the plan, and consume starts in manifest order. Initial bring-up starts
at acquisition and does not call teardown or backoff bindings.

The binding holds serialization against revocation and unit-lifecycle changes
from snapshot acquisition through the last acknowledged start. Immediately before
each grant/start the adapter calls `request_current` inside that interval; an
epoch mismatch or changed grant set is refused. Each successful start acknowledges
both the exact epoch-filtered grants and the unit's start before the next request.
Refusal cannot make new authority accessible for that unit. This interval is
part of the binding contract, not an inference from equal integer epochs.

Any failure stops the sequence, releases an acquired lock exactly once, and
reports the acknowledged start prefix and the refused unit. The adapter performs
no retry or rollback. The caller must use that report when selecting recovery;
repeating initial bring-up after a partial start is not a recovery policy.

These callbacks do not yet have target kernel implementations. Their completion
record is data from a trusted binding, not independently attested evidence. The
adapter does not itself perform compartment entry, capability derivation,
teardown, zeroization, revocation, or clock measurement. Those effects, ownership
closure, bounded callback completion and the serialized region must be realized
and checked at M4.4's join. Host test bindings establish sequencing and refusal
behavior only.

## Focused comparison

`python tools/run.py supervisor check` compiles the C harness with the native C
compiler, generates start-order weakenings and strangers, every detector around
its threshold, a finite product of declared counters around dwell/window/boot and
backoff boundaries, and every edge of the demo manifest. The C answers become
exact equality examples over the shipped Gallina definitions. The locked proof
switch compiles the reference and those examples in a fresh native lane directory.
Python supplies inputs and syntax, never reference verdicts. Fixed consumer controls
cover stale epochs, retired and invented authority, start and restart requests,
unchanged outputs on refusal, malformed manifests and boundary capacities; their
verdict is reported separately from Gallina agreement.

The same harness also generates effect executions across every supported roster
size, every nonempty suffix of a dependency chain, declared backoff boundaries,
and a refusal at every callback position beside successful controls. It checks
the effect trace, exact grant/start order, release of serialization, and the
reported prefix after refusal. Every revocation-completion bit pattern is
exercised, including epoch advancement without containment. Controls also cover
revocation during backoff, stale snapshots, full-width epochs, malformed callback
tables, and attempted manifest changes by a callback. These checks use host
bindings and the kernel's actual completion predicate; they supply no target
effect evidence or new Gallina theorem.

The native build lane retains inputs, answers, generated Gallina and a report
binding source, generated comparison and binary hashes, including the kernel
completion implementation and headers linked by the harness. Compiler and comparison
logs live in its directory under `/root/logs`. Source and compiler identities are
checked before and after the comparison. This is a finite host
comparison. It neither proves C refinement nor supplies assumption-audit or proof
gate evidence. Host behavioral tests run with `python tools/run.py test --only
test_supervisor`; Linux also compiles and runs the consumer-control harness.

The original C and Python files use `Apache-2.0`, and this document uses
`CC-BY-4.0`, under [COPYRIGHT.md](../COPYRIGHT.md).
