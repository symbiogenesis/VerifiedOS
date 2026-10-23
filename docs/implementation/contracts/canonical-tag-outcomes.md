# Canonical tag outcomes

This is Q35p's owner contract for the missing representation identified by the
[memory-binding qualification](../q35p-memory-bindings.md). Implementation begins
after the integrator lands this contract. It commissions a representation of the
model's existing tag effects in the canonical V1 outcome interface. It commissions
no new ISA behavior, tag plane, admission assumption or proof-switch update.

R-05-019b requires Sail's emitted definitions to remain the common machine term.
R-15-203 fixes the validity plane and its granule, and R-15-115a requires clearing
every granule a vector data store overwrites. The authoritative operations are
[the metadata owner](../../../model/model/core/mem_metadata.sail) and
[the physical memory owner](../../../model/model/core/phys_mem_interface.sail).
The existing emulator runtime's
[exact-key operations](../retained-evidence/close3-q35p-20261013/runtime-tags.txt)
and the paired support's
[state operations](../retained-evidence/close3-q35p-20261013/state-tags.txt)
provide the reference effects, rather than a new per-consumer ISA transcription.

## Representation and interpretation

Extend `src-stdpp/ConcurrencyInterface.v` in the exact paired support candidate
with `TagRead (key : mword 64) : outcome bool` and
`TagWrite (key : mword 64) (value : bool) : outcome unit`. The key is the raw
64-bit argument supplied to `__read_tag` or `__write_tag`. It is already a granule
index: the outcome performs no shift, multiplication, truncation, address
translation or access to data bytes. A separate type alias may document that
meaning without changing its representation.

In `src-stdpp/ConcurrencyInterfaceBuiltins.v`, define `Defs.read_tag_bool` and
`Defs.write_tag_bool` in `Defs.monad E`, yielding the corresponding `Next` outcome
followed by `Ret`. The read returns `bool`; the write returns `unit`. These names
must be the native resolved bindings of the unchanged emitted metadata calls.
There is no conversion from the prompt or sequential monad and no coercion that
discards a write effect. The five Q35f emulator-memory refusal definitions stay
as emitted; the canonical term continues to reach data through its existing
`sail_mem_read` and `sail_mem_write` outcomes.

The reference tag state is a finite map from unsigned raw 64-bit keys to booleans.
For every initial map and key, a legal `TagRead` event returns the map's value,
or `false` if absent, and leaves all state unchanged. A legal `TagWrite` event
updates exactly that key, returns `tt`, and leaves data, registers, output and all
other tags unchanged. These are total functional effects with no new success
boolean, abort, exception, allocation-failure result or nondeterministic read.
The runtime's host resource exhaustion is not a new architectural result.

The outcome algebra alone permits arbitrary event responses; its generic
`iTrace_match` supplies no tag-state legality theorem. The delivery must define
and check the legality/interpretation above, and connect it to the exact emitted
bindings. Merely constructing `Next TagRead` and compiling it does not establish
emulator agreement. A proof over the new events must use this same interpretation
and expose any additional physical or concurrency obligation at its existing
owner.

Existing outcomes retain their types, payloads and interpretation. The changes to
`Interface.map_extra_iMon` and `Defs.try_catch` add explicit forwarding branches
for both tag outcomes, preserving the key, written bit, response and continuation.
`ExtraOutcome` continues to carry the existing model exception or early-return
payload. The change must not encode tags as exceptions, as a zero-length or
value-free data request, or as a dummy data write. Generic bind, fmap, traces and
their event order remain unchanged apart from the extended outcome type.

## Agreement and boundary cases

State and prove the bridge for every initial finite tag map, each raw key and
bit, and arbitrary continuations, preserving return values, tag state, framed
state, ordered data requests and every existing refusal. The theorem must derive
the tag effects from executable map operations and the actual new bindings; it
must not assume the desired agreement as a handler law or record field. For old
outcomes, use the same fixed data/environment interpretation on both sides;
the bridge assumes no new fact about that interpretation's correctness.

The metadata caller bridge uses the emitted `addr_to_tag_addr`,
`__ReadRAM_Meta` and `__WriteRAM_Meta` definitions, including fixed-width address
addition, endpoint calculation and the ascending loop. Preserve the current
behavior at wraparound; a new mathematical interval extending beyond the address
width is a different definition. The physical-memory bridge preserves that a
metadata read, when requested, precedes the data read, while `read_meta = false`
returns `default_meta` without a tag event.

The write bridge preserves the exact branch in `write_ram`: after
`sail_mem_write` returns `Ok _`, run the metadata loop and return `true`; after
`Err ()`, return `false` without a tag write. The existing branch treats
`Ok None`, `Ok (Some true)` and `Ok (Some false)` alike. The
[library's retained caller](../retained-evidence/close3-q35p-20261013/emulator-write-callers.txt)
labels the inner boolean as exclusive/CAS success and wraps it in `Ok`.
Accordingly, "successful data write" in this binding contract means reaching
the existing `Ok` branch, not a newly introduced inner-boolean check. Whether a
reachable exclusive failure should have another architectural effect is a
separate source/requirement decision; this contract changes neither its reachability
nor its effect.

Construct inhabited positive instances and distinguishing rejected instances for
the following checks:

- Read an absent key, write `true`, read it, clear it, then read `false`; use
  distinct keys that would alias under an erroneous extra granule shift, and
  include zero and the largest unsigned 64-bit key.
- Update a tag with every other tag, data byte, register and output framed;
  reject a changed neighbor, discarded write, changed return type, dummy data
  event and an unconstrained read response.
- Exercise the actual metadata callers on an aligned capability write, a
  partial-granule data write and a multi-granule data write, observing the exact
  ascending key sequence and all affected clears; preserve the existing
  fixed-width boundary behavior.
- Exercise the actual `write_ram` continuation after each `Ok` variant and after
  `Err ()`; reject omitted, reordered or added tag events. Exercise requested and
  unrequested metadata reads, with successful and refused data reads.
- Carry tag effects through `try_catch`, early return and `map_extra_iMon`;
  distinguish a real exception from a tag event and preserve each of the five
  emulator-memory refusal bodies.

## Source scope and acceptance

The selected upstream is coq-sail 0.20.3, revision
`e7b914cddc032e3676eebd87a808229828013e9c`, whose archive is bound by
[the source recipe](../../../tools/opam/sail-support-qualification.json).
The 2026-10-23 source reading verified that archive's SHA-256
`1a0e226608ac84add6cd1f61a11637ea9db5e00e1551b2070945310078c9e031`
and read its actual BSD-2-Clause `LICENSE` before designing an amendment.
The source reading identified `map_extra_iMon` and `try_catch` as the V1
constructor-exhaustive consumers that need new branches. `InterfaceT` and
`InterfaceWithArch` include `Interface`; they acquire its extended declarations
through that include. The separate V2 interface and its builtins remain outside
this amendment. Before acceptance, repeat the dependency reading over the actual
patched source and compile its complete selected closure, rather than treating
this source observation as a permanent census.

Deliver one immutable semantic support patch over Q35n's qualified candidate,
with its source and license identity, the bridge and native positive/refusal
controls, and the actual seven emitted binding readings. Prefer support-only
resolution of the existing primitive names. If that cannot be qualified, stop
and return the exact unresolved binding before changing Sail declarations or
the emitter. Any necessary further target-only binding change needs its own
reviewed owner act before implementation.

Strict compile the minimal emitted reproducer at the unchanged locked prover
and flags. Compare the new native elaborated readings against the frozen inputs:
only the two new outcomes/bindings, forwarding branches and their explicitly
reviewed proof/dependency additions may differ. Existing declarations' meanings,
model refusals, dependency axioms and compiler acceptance policy must remain
unchanged. Audit all new proofs' exact assumptions and kernel-check the accepted
objects under the existing acceptance rules. Record the complete inputs and
resolved native names. Unchanged Sail bytes must give byte-identical non-Rocq
outputs in paired regeneration; a single baseline emission is insufficient.

Q35p then joins Q35o's actual-plugin syntax and deterministic-emission checks,
Q35b's strict whole-term compile, exact closure and compiled size, and Q35n/Q35q's
unchanged support census and cold production-carriage qualification. Acceptance
of this contract or an isolated primitive bridge closes none of those predicates.
The integrator completes Host CI and dispatches every Guest CI lane with
`cold: true` for accepted proof changes, recording pending Guest CI honestly and
finishing without waiting for it. Full gates and benchmarks run only on GitHub
Actions; focused local compilation and controls retain their separate purpose.

## Bound and remaining estimate

Use a new reviewed Sail/proof checkpoint after this owner act lands. Stop at
twelve candidate checks or thirty active minutes, or the first unexpected
semantic incompatibility, whichever comes first. Preserve the exact diagnostic
and return a further scoped owner act; do not weaken this bridge or expand its
effect surface to pass compilation.

The remaining phase basis is source extension and old-event forwarding 1–3 h;
executable interpretation and emitted-caller agreement 2–6 h; native
distinguishing controls and source/output
identities 2–4 h; independent review and consumer handoff 1–3 h. This replaces the
previous adapter phase basis. Q35b's whole-term acceptance, Q35n/Q35q's source
carriage/census, unattended hosted runtime and a further unsupported semantic
boundary remain outside these phases. The implementation checklist owns the
estimate cell.
