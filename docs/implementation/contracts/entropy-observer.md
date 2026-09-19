# Entropy-root observer contract

This is the S6 implementation contract for a model observer at `rot_draw` in
[rot.sail](../../../model/model/sys/rot.sail). It supplies the missing observation
boundary identified by the [replay record contract](replay-record.md).
It does not implement the M3.2 record writer, the M3.4 sealing primitive, or replay
injection. The existing architectural draw result and state transitions remain
the owner's.

## Callback and ordering

Every invocation of `rot_draw` calls `entropy_draw_callback` exactly once after
its outcome is known and before returning to its consumer. Its arguments are
`available : bool` and `value : bits(64)`. Success reports the conditioned word;
every refusal reports false and zero. Raw source samples never cross this hook.
The hook neither replaces a word nor changes the architectural result.

The Sail fallback is a no-op. The C++ backend routes the callback through
`PlatformInterface`, `ModelImpl`, and the registered `callbacks_if` observers,
using the same synchronous dispatch as existing memory and retirement callbacks.
An observer can associate the call with its current core, schedule point and
retirement origin, including calls before the first retirement. Invocation order
orders multiple draws at that point. A watchdog arm or accepted pet reaches the
same root callback as an MMIO draw; a rejected pet that never invokes the root
does not produce a callback.

The callback is a trusted harness boundary carrying secret material. Ordinary
commit and diagnostic log callbacks do not print it. A capture installs its own
observer, seals successful words immediately, and records the sealed value via
the bounded recorder. Refusal consumes no entropy event. Recorder or seal failure
must abort the capture; synchronous exceptions propagate to the harness. A
capture must use this root as its single entropy producer, disabling the older
MMIO-derived producer for that capture to avoid recording a bus draw twice.
An unattached observer allows ordinary model execution but supplies no capture
evidence. Replay authentication and substitution remain separate work.

## Acceptance predicate

The model typechecks and its generated C++ callback signatures compile. A
focused executable harness registers an observer and checks direct success,
latched refusal, watchdog arm and accepted pet, rejected pet, callback ordering,
and the absence of draw changes with a no-op observer. The callback sees no raw
sample, no ordinary trace contains the secret, and no instruction, CSR or decode
construct is added. Host adapter tests check sealing, refusal, order, and bounded
record exhaustion. These are observer acceptance tests, not operational replay
or a stochastic-source assessment.
