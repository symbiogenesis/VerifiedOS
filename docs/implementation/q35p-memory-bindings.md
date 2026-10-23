# Canonical memory and tag binding qualification

Q35p remains open. The [tag-outcome contract](contracts/canonical-tag-outcomes.md)
now has a bounded support construction and an actual emitted-caller bridge.
The [bounded tag outcome construction](retained-evidence/q35p-tag-outcomes-20261023/manifest.json),
SHA256 `975fb21ac24e0e45c07ac5704e16ebe3a6fcdd229837090178173eb80fb74ba2`,
binds its immutable semantic patch, authored laws and controls, actual emitted
reproducer, native readings, exact compiler arguments, inputs and available logs.
The construction is a focused checkpoint; the remaining acceptance joins below
still decide closure.

## Representation and native bindings

The candidate applies after Q35g's axiom-removal patch and Q35n's strict syntax
patch to coq-sail 0.20.3, revision
`e7b914cddc032e3676eebd87a808229828013e9c`.
Its source archive and exact BSD-2-Clause notice match the qualification recipe.
The reconstructed baseline support sources match the
[prior frozen inputs](retained-evidence/close3-q35p-20261013/inputs.json).
The [baseline binding evidence](retained-evidence/close3-q35p-20261013/manifest.json),
SHA256 `db26237bdbde7915efa9f3d4ce29b3b95c595dc1008842fb34ce9f713a4f3510`,
binds the emulator/state readings and original missing-outcome diagnostic.
The new patch changes only V1 `ConcurrencyInterface.v` and
`ConcurrencyInterfaceBuiltins.v`: `TagRead` carries the raw
`mword 64` granule key and returns `bool`;
`TagWrite` carries that key and bit and returns `unit`.
`map_extra_iMon` and `try_catch` explicitly forward both events.

The actual Q35o plugin, authenticated against its retained emission receipt,
emitted the unchanged minimal Sail reproducer. Its types and main strictly
compile against the candidate support with the unchanged locked prover and
flags. The native reading resolves all seven primitive bindings:

| Sail primitive | Actual emitted reading |
| --- | --- |
| `read_mem#` | `read_mem_ : ... -> M (mword (8 * n))`; existing `internal_error` refusal |
| `read_mem_ifetch#` | `read_mem_ifetch_ : ... -> M (mword (8 * n))`; existing refusal |
| `read_mem_exclusive#` | `read_mem_exclusive_ : ... -> M (mword (8 * n))`; existing refusal |
| `write_mem#` | `write_mem_ : ... -> M bool`; existing refusal |
| `write_mem_exclusive#` | `write_mem_exclusive_ : ... -> M bool`; existing refusal |
| `__read_tag` | The emitted caller resolves native `Defs.read_tag_bool : mword 64 -> Defs.monad E bool` |
| `__write_tag` | The emitted loop resolves native `Defs.write_tag_bool : mword 64 -> bool -> Defs.monad E unit` |

## Executable interpretation and checked scope

The authored `TagOutcomeLaws.v` interprets tags through executable finite-map
lookup and insertion at `bv_unsigned key`. An absent key reads `false`;
a write returns `tt` and changes only its exact key. Other outcomes remain
residual requests with their payloads, responses and continuations preserved.
The laws derive primitive agreement for arbitrary initial maps and continuations,
neighbor framing, exception/early-return forwarding and the composed
read/write/read/clear sequence. The law functor takes the exact emitted
`Interface` implementation; it assumes no desired handler-agreement law.

`CallerBridge.v` proves the actual emitted metadata loop's ascending event
sequence and executable map-state interpretation for arbitrary endpoints,
initial maps and continuations. Its endpoint expression uses the emitted
fixed-width address addition. Concrete controls cover an aligned capability
write, partial and multi-granule clears, distinct raw keys, zero, the largest
unsigned key and the existing empty loop at wraparound.

The physical caller lemmas instantiate `Write_plain` and `Read_plain`.
For every raw data-write response, the existing `Ok` branch, including
`Ok (Some false)`, runs metadata and returns `true`; `Err ()` returns
`false` without metadata. Read controls observe requested metadata before the
data request, the unrequested default, and returned metadata after zero-data
success responses. The read-refusal controls classify the resulting event shape;
they do not establish exact refusal-payload equivalence. Native printed
definitions separately retain the existing refusal bodies.

Distinguishing `Fail` controls reject a changed write result type, discarded
write, unconstrained read, aliased or changed neighbor, omitted/reordered/added
clear, tag-as-exception and dummy data write. The selected support closure,
authored laws, actual emitted reproducer and caller controls strictly compile.
Every assumption query instantiated against the actual emitted architecture and
interface reports a closed global context; the focused kernel check exits zero.
Final native source identities match before and after acceptance, and installed
dependency sentinels remain unchanged.

## Bound and remaining acceptance

The checkpoint used its unchanged start of 2026-10-23 06:51:12.259 UTC and froze
at the twelfth candidate check after 993.014 active seconds, including candidate
waits. A concrete wraparound `vm_compute` control was stopped for excessive
eager allocation, then checked through lazy kernel conversion. The exact failed
caller diagnostics and final accepted evidence are retained. Some earlier raw
scratch logs were overwritten by repeated labels; the checkpoint marks their
original bytes unavailable and retains their recorded command, exit and digest.
Those digests supply no retained-byte or complete attempt-history claim.

The remaining joins are complete tag-free whole-computation conservativity;
the all-existing-support native frozen comparison and exhaustive declaration
census; physical-caller coverage beyond the plain request kinds and arbitrary
read-data preservation; paired full-model non-Rocq regeneration; Q35b's strict
whole-term compile, closure and compiled size; and Q35n/Q35q's cold production
carriage. This construction updates no shared switch or lock and supplies no
hosted acceptance. The integrator must complete Host CI and dispatch every
Guest CI lane with `cold: true`, recording a pending guest verdict honestly
and finishing without waiting for it.
