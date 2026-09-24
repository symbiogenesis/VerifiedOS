# Supervisor core

This directory owns M7.1b's bounded GC-free C core, authored against
[SupervisionTree.v](../proofs/SupervisionTree.v). It admits a finite manifest, checks
start order, computes detector/action, dwell, window, boot and backoff decisions,
and produces ordered start requests with grants filtered by the current revocation
snapshot. The [roster contract](../docs/implementation/contracts/boot-roster.md)
fixes its place as the kernel's first partition.

**This is a host-checked core, not an executable target roster member.** The accepted
M1.2f backend, M4.4 kernel adapter, authenticated manifest handoff, and M7.1a image and
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

The kernel adapter must complete teardown, zeroization and revocation of the stop
set, wait the declared delay, acquire a current epoch snapshot, regenerate the
plan, and consume starts in order. Immediately before each grant/start it calls
`request_current` while serialized with revocation; a changed epoch or changed
grant set is refused. Earlier successful starts must be acknowledged by the
adapter before the next request. An integer epoch equality is not a kernel
revocation-completion receipt. The core deliberately supplies no lifecycle,
window clock or counter-reset policy that the reference leaves unspecified.

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

The native build lane retains inputs, answers, generated Gallina and a report
binding source, generated comparison and binary hashes. Compiler and comparison
logs live in its directory under `/root/logs`. Source and compiler identities are
checked before and after the comparison. This is a finite host
comparison. It neither proves C refinement nor supplies assumption-audit or proof
gate evidence. Host behavioral tests run with `python tools/run.py test --only
test_supervisor`; Linux also compiles and runs the consumer-control harness.

The original C and Python files use `Apache-2.0`, and this document uses
`CC-BY-4.0`, under [COPYRIGHT.md](../COPYRIGHT.md).
