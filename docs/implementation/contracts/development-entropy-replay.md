# Development entropy capture and replay checkpoint

This contract opens a bounded S6 work package over the actual generated Sail
entropy root. It consumes the [observer contract](entropy-observer.md),
[record body](replay-record.md) and [development envelope](host-replay-envelope.md).
The implementation checklist owns S6's completion. This call-level checkpoint
leaves its production sources, sealing, DRBG discipline, complete machine capture
and CT-scoped replay acceptance open.

## Delegated scope decision

The execution decision is to use the third worker for this bounded runtime
checkpoint. S6's production public-source services and cryptographic joins are
absent, so complete replay cannot be accepted from the available artifacts.
The checkpoint instead checks real generated Sail call paths and their refusal
boundaries under the existing S6 ownership; it supplies executable evidence beyond
the host structural fixtures while preserving the complete acceptance predicate.
The integrator owns Q40's independent header reproduction in another dedicated
worktree, so that verification does not consume this implementation lane. S6
retains its open status and receives no independent completion credit for this
work package.

## Trusted development hooks

Two additive hooks belong to the trusted development harness. Sail's ordinary
fallbacks do nothing and return the original value respectively:

- `entropy_draw_begin_callback : unit -> unit` runs after the root's initial
  refusal guards and before its first source sample. Capture reserves the maximum
  bounded event/body capacity here. A capacity refusal throws before conditioning
  advances the source; failures after this point abort finalization without a
  state-rollback claim.
- `entropy_draw_value_callback : bits(64) -> bits(64)` returns the effective
  successful word before the consumer receives it. Capture returns the original
  word. Replay supplies independently generated fresh development entropy after
  admitting the matching request. Failure is never turned into success and no
  last-known-good word supplies a refused draw.

The existing synchronous observer continues to see the original conditioned
outcome exactly once. Capture and replay controllers are mutually exclusive;
replay cannot run the capture observer or the old MMIO-derived entropy producer.
No instruction, CSR, architectural access door or production mode is added.
An unattached controller preserves ordinary root and watchdog behavior.

Original words reach only the trusted synchronous commitment callback. A keyed
development commitment supplies opaque bytes to the bounded recorder. Original
words, seeds and keys never enter files, ordinary traces or an archive retained
for replay. The development envelope authenticates exact body, origin and input
bytes against independently supplied bindings and keys. It supplies no RoT seal,
image-signature verification, export authorization or declassification facility.
Ordinary replay substitutes its own entropy, as R-16-017 requires, and never
recovers captured words.

## Development artifact binding

For this checkpoint, the expected base-image root is the SHA-256 of the exact
native executable, and the expected composition is the SHA-256 of the exact
configuration bytes passed to it. These development identities do not claim a
production signed-image root. The controller verifies both artifacts against the
independently supplied expectations before capture or replay launches, and checks
them again before capture finalization or successful replay completion. A mismatch
aborts the recorder or cursor and prevents success; a preflight mismatch releases
no fresh replay word.

These checks bind the authenticated envelope to the artifacts actually exercised.
The development lane is trusted and exclusive: no concurrent writer may replace
the executable or configuration during a run. Before-and-after hashing detects
persisting drift; it does not establish race-free executable pinning against an
adversarial writer. Production artifact authentication remains in S6's open scope.

## Acceptance fixed before implementation

Focused executable tests exercise the generated Sail definitions through their
actual direct, MMIO and internal watchdog arm/accepted-pet paths. They must check:

- Each successful root call is captured once, including internal watchdog draws;
  root refusal and a rejected pet produce no event. Existing observer order and
  unattached-controller outcomes remain unchanged.
- Event and body capacity refusals occur before source advancement. A declined
  commitment, interrupted protocol or later callback failure prevents every
  finalization path, including direct access to the underlying recorder.
- Before replay releases any substitute word, envelope authentication and the
  independent root, composition, origin, exact input bytes, interface profile and
  event count checks all pass. Each actual request matches its recorded point and
  endpoint; removed, mismatched, exhausted and trailing events refuse the run.
- Replay uses fresh independently supplied 64-bit words. The receipt names the
  finite public call-level observations compared and excludes nonce/token values.
  Unsupported draw-dependent branches or faults are reported outside that
  comparison. These observations establish no instruction-level replay, general
  noninterference, CT theorem or production fault-reproduction claim.
- Controls refuse a wrong key or tag, wrong expected root/origin, absent input,
  declined commitment, unrecorded watchdog request, and any request for a
  production or actual-draw declassification mode. Neither successful receipts
  nor failure diagnostics disclose original draws or keys.

Use a focused generated-C++ executable harness and focused host replay tests,
with source, tool and receipt identities retained in the assigned native lane.
Typecheck and compile the changed model and callbacks; preserve unrelated model
bytes and generate its bundle through the owner. Complete Host CI and dispatch
every Guest CI lane on the settled revision. Full gate suites remain hosted.

These are runtime checkpoint checks. S6 stays open until the existing replay
contract's complete operational predicate holds, including its absent public
source services, production cryptography, actual machine capture and proof scope.

## Focused execution

The controller is [replay_runtime.py](../../../tools/vos/replay_runtime.py).
From the assigned checkout, emit the model with `python tools/run.py model emit`.
In its assigned native build lane, build only the `entropy_capture` and
`entropy_observer` CMake targets. Run the unchanged observer, then the guest's
`python3 tools/run.py test --only replay_runtime --slow --jobs 1` for actual
capture, replay and refusal controls. The ordinary host replay selection checks
the controller and structural formats without executing the native campaign.

The controller starts the capture executable with private anonymous pipes.
Never redirect `entropy_capture` output to a file: its transient capture frames
carry original conditioned words. The endpoint refuses file and terminal input
or output. Retained evidence contains only public verdicts and source/tool
identities, with no original draws, keys or envelope archives.
