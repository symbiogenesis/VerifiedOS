# Generated manifest target preparation

M7.1b's contained target driver can consume the production manifest through
`python tools/run.py supervisor target --generated-manifest`, with the command's
existing explicit compiler, compiler configuration, simulator and model-build
receipt arguments. The ordinary target mode and the accepted scalar join keep
their existing handwritten comparison policy.

The generated mode revalidates the published C and JSON projections against the
typed composition input and all declared bindings. It copies their exact bytes
into its native lane, compiles a wrapper that includes the actual generated C
object and the trusted consumer, and rechecks both projections, snapshots and
wrapper after compilation and execution. It does not replace a stale projection.
The contained supervisor receives the initialized manifest through its existing
read-only capability, alongside its read-only acknowledgment and writable request
regions.

The trace account compares every manifest byte against an independently
computed layout for the `uint32_t` fields in
[vos_supervisor.h](../../supervisor/include/vos_supervisor.h). The finite component
account requires the production manifest's exact three units, order, authority
edges and restart set; a different roster refuses this account. The prepared
controls preserve full-width current epochs, stale requests, incomplete
retirement, incomplete publication and phase cuts, and add an attempted store
through the manifest capability. They retain images and trace identities when
a qualified target run becomes available.

The supervisor reaction account uses the checked generated manifest's actual
backoff-table length. It charges each of the three possible manifest validations
for both its detector loop and every admitted backoff entry, and refuses an
account that reaches the declared fixed-slot limit. The scalar comparison mode
retains its one-entry account.

The production policy's first backoff is one logical step, which expires before
the next declared fixed slot. Its prepared run supplies an empty publication
before ordinary start to compare empty and occupied padded releases. Faults before
and after publication supply their own empty reaction. The waiting-phase fault
control remains covered only by the separate long-delay comparison policy; the
generated mode does not claim that case.

## Native evidence

The focused `test_lifecycle_target` native case compiles the actual generated
wrapper with the native C compiler and executes its manifest-copy function. It
compares every emitted byte with the independent layout account. A second,
successfully compiled object changes the generated initial backoff from one to
two; its emitted bytes disagree, so the live mutation is detected. Compilation
failure does not count as detection.

The native receipt records the compiler path, executable SHA-256 and reported
version, both projection identities, both executable identities and the emitted
layout digests at
`/root/build/lane-close3-20261013-kernel/supervisor-manifest-native/report.json`.
It explicitly carries `target_execution: false`, `production_admission: false`
and open milestone acceptance. Temporary probe sources and executables are
removed after the native control.

Focused controls also verify exact projection identity retention, independent
field offsets, rejection of a different roster, C/JSON/wrapper changes during
compilation, and rejection of invalid locked compiler provenance before any
target compilation. These supply preparation and native consumer evidence.

## Target refusal and remaining acceptance

The attempted generated target run used the retained compiler at
`/root/build/lane-backend-accept-20260925/compiler-final/ccomp`. The unchanged
provenance reader refused it with the exact diagnostic:

> contained compiler toolchain does not bind the recorded lock

The target driver records this refusal at its `compiler-provenance` stage in
`/root/build/lane-close3-20261013-kernel/supervisor-manifest-target/report.json`.
No target compilation or simulator execution followed. The compiler lock and
provenance requirements remain unchanged; the model receipt was not assessed
after this earlier refusal.

Actual generated-manifest target execution remains owed. Final M7.1b acceptance
also requires the Q39-qualified locked compiler for the shared final capture,
authenticated manifest admission and boot handoff, and observed start/fault order
through the full real roster under
[the boot-roster contract](contracts/boot-roster.md). Native object layout
agreement and the existing bounded scalar comparison do not discharge those joins.

This document uses `CC-BY-4.0` under [COPYRIGHT.md](../../COPYRIGHT.md).
