# Sail memory and tag binding qualification

Q35p remains open. The [tag-outcome contract](../implementation/contracts/canonical-tag-outcomes.md)
has a bounded support construction and an actual emitted-caller bridge. Strict
compilation and focused native checks pass; complete semantic, support and
canonical-consumer acceptance remains owed.

## Retained evidence

| Bundle | Scope and SHA256 |
| --- | --- |
| [Bounded tag outcomes](../implementation/retained-evidence/q35p-tag-outcomes-20261023/manifest.json) | Immutable semantic patch, authored laws/controls, emitted reproducer, native readings, compiler arguments, inputs and available logs. `975fb21ac24e0e45c07ac5704e16ebe3a6fcdd229837090178173eb80fb74ba2`. |
| [Baseline bindings](../implementation/retained-evidence/close3-q35p-20261013/manifest.json) | Emulator/state readings and original missing-outcome diagnostic, with [frozen inputs](../implementation/retained-evidence/close3-q35p-20261013/inputs.json). `db26237bdbde7915efa9f3d4ce29b3b95c595dc1008842fb34ce9f713a4f3510`. |
| [Reusable native candidate](../implementation/retained-evidence/reuse-wire-tags-20261023/manifest.json) | Separate semantic patch, support, unchanged minimal emission, readings, assumptions, scoped kernel check and installed-path inventories at `a5e4ba0e3e2ab477cdde2ae8a59dd47b82a9da90`. `3fe661163dd4ac2c9781d2229e2a8a546306bfe87359bbecffa1f0d762aaac0d`. |
| [Executed reusable drivers](../implementation/retained-evidence/reuse-wire-tags-drivers-20261023/manifest.json) | Original per-attempt Python commands. `04b6f1e55fc37ca623105f559be23a23c6af723a271e0adfbd49074d1680dfb6`. |

<a id="actual-semantic-boundary"></a>

## Representation and native bindings

The candidate applies after Q35g's axiom-removal and Q35n's strict-syntax patches
to coq-sail 0.20.3 at `e7b914cddc032e3676eebd87a808229828013e9c`. Its archive and
BSD-2-Clause notice match the qualification recipe; reconstructed baseline sources
match the frozen inputs. Only V1 `ConcurrencyInterface.v` and
`ConcurrencyInterfaceBuiltins.v` change: `TagRead` takes a raw `mword 64` granule
key and returns `bool`; `TagWrite` takes that key and a bit and returns `unit`.
`map_extra_iMon` and `try_catch` forward both events explicitly.

The authenticated Q35o plugin emits the unchanged minimal Sail reproducer. Its
types and main compile strictly against the candidate at the locked prover and
flags. Native readings resolve all seven primitives:

| Sail primitive | Actual emitted reading |
| --- | --- |
| `read_mem#` | `read_mem_ : ... -> M (mword (8 * n))`; existing `internal_error` refusal |
| `read_mem_ifetch#` | `read_mem_ifetch_ : ... -> M (mword (8 * n))`; existing refusal |
| `read_mem_exclusive#` | `read_mem_exclusive_ : ... -> M (mword (8 * n))`; existing refusal |
| `write_mem#` | `write_mem_ : ... -> M bool`; existing refusal |
| `write_mem_exclusive#` | `write_mem_exclusive_ : ... -> M bool`; existing refusal |
| `__read_tag` | `Defs.read_tag_bool : mword 64 -> Defs.monad E bool` |
| `__write_tag` | `Defs.write_tag_bool : mword 64 -> bool -> Defs.monad E unit` |

## Executable interpretation and checked scope

`TagOutcomeLaws.v` interprets tags by executable finite-map lookup/insertion at
`bv_unsigned key`. An absent key reads `false`; writing returns `tt` and changes
only that key. Other outcomes retain their payloads, responses and continuations
as residual requests. Laws establish primitive agreement for arbitrary maps and
continuations, neighbor framing, exception/early-return forwarding and the composed
read/write/read/clear sequence. The functor takes the exact emitted `Interface`
implementation and assumes no desired handler-agreement law.

`CallerBridge.v` proves the actual metadata loop's ascending event sequence and
map interpretation for arbitrary endpoints, initial maps and continuations,
including the emitted fixed-width endpoint addition. Controls cover aligned,
partial and multi-granule writes, distinct raw keys, zero, the largest unsigned
key and the existing empty loop at wraparound.

Physical lemmas instantiate `Write_plain` and `Read_plain`. Every `Ok` data-write
response, including `Ok (Some false)`, runs metadata and returns `true`; `Err ()`
returns `false` without metadata. Read controls observe requested metadata before
data, the unrequested default and returned metadata after zero-data success.
Read refusals establish event shape, not exact refusal-payload equivalence;
printed definitions separately retain the refusal bodies.

Distinguishing `Fail` controls reject changed write type, discarded writes,
unconstrained reads, aliased/changed neighbors, omitted/reordered/added clears,
tag-as-exception and dummy data writes. Selected support, laws, emitted modules
and controls compile strictly. Queries instantiated against the emitted
architecture/interface have closed global contexts; the focused kernel check
exits zero. Final source identities and installed dependency sentinels agree.

## Reusable candidate and independent controls

The separate [reusable V1 candidate](../../tools/sail-tag-outcomes/README.md)
packages an isolated construction and replay recipe. Focused host controls, Ruff
and Linux/Windows typing pass; `test_sail_tag_outcomes` includes its host controls.
The native bundle binds the executed construction, not a clean replay of the
subsequently packaged runner.

[TagInterpreter.v](../../tools/sail-tag-outcomes/TagInterpreter.v) gives a fuelled
finite-map interpretation with a fixed other-outcome handler and generic frame.
Primitive bridges quantify over arbitrary maps, keys, frames and continuations.
[TagControls.v](../../tools/sail-tag-outcomes/TagControls.v) observes actual callers'
complete data environment and frame: requested/unrequested reads, tag/data order,
all three `Ok` forms and `Err ()`, ascending clears, wraparound, forwarding and
refusals. These finite controls establish no universal physical-caller theorem.

All 33 queried new proofs have closed global contexts. `rocqchk -norec` passes
on the two authored objects while admitting dependencies; that supplies no
dependency-axiom closure. Minimal Rocq outputs repeat byte for byte, as do two C
regenerations' `.c`/`.h` files; this is not paired full-model regeneration.

Before/after inventories rescan all 10,904 installed proof `bin`/`lib` paths,
including additions/deletions, unchanged. All 16,140 Sail paths agree during the
later query/C-generation interval; initial minimal Rocq emission precedes it.
No shared installation is rebuilt or repaired. The reusable checkpoint ends at
twelve checks within a conservative 1,001-second wall interval.

The two patches share constructor types, binding bodies and forwarding, with
different comments and placement. Each reading, assumption and kernel verdict
belongs to its elaborated candidate; source similarity transfers no verdict.
Both preserve BSD-2-Clause notices and leave the production recipe, shared switch,
model and emitter unchanged.

## Bound and remaining acceptance

The original checkpoint began at 2026-10-23 06:51:12.259 UTC and exhausted twelve
checks after 993.014 active seconds, including waits. An eager wraparound
`vm_compute` was stopped for allocation; lazy conversion closed the unchanged
statement. Both constructions retain final readings and diagnostics. Some earlier
scratch logs were overwritten: recorded commands, exits and digests do not recover
their bytes or establish complete attempt history.

Remaining joins are tag-free whole-computation conservativity; complete support
frozen comparison and declaration census; physical-caller coverage beyond plain
requests and arbitrary read-data preservation; paired full-model non-Rocq
regeneration; Q35b's strict whole-term compile, closure and size; and Q35n/Q35q's
cold production carriage. No shared switch or lock changes, or hosted acceptance,
follow from these checkpoints. The [validation handoff](../../AGENTS.md#tool-execution-and-validation)
leaves Host CI and cold Guest CI publication, execution and verdicts to the user.
