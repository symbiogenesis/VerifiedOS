# Sail memory and tag binding qualification

Q35p remains open. The [tag-outcome contract](../implementation/contracts/canonical-tag-outcomes.md)
has a bounded support construction and an actual emitted-caller bridge. Strict
compilation and focused native checks pass; complete semantic, support and
canonical-consumer acceptance remains owed.

## Retained evidence

- [Native V1 conservativity and physical-caller checkpoint](../implementation/retained-evidence/holdfast-q35p-worker-proofs-20261125/manifest.json),
  SHA256 `8e0eb97c3f34a8a0e56bbcf5f1a9cf1856a5c429b7916f9e0fdb806b2edd088c`.
  Frozen source identities, minimal emission repeats and focused proof readings.
- [Fresh sequential emulator repeat](../implementation/retained-evidence/q35p-holdfast-emulator-repeat-20261125/manifest.json),
  SHA256 `866a62b9da6f484ce28ebae0cc4f5bc6d788078dd4ab2898daaeda5a7490bcec`.
  Exact run commands, frozen identities and comparisons against the prior pair.
- [Paired emulator emission and determinism controls](../implementation/retained-evidence/q35p-holdfast-emulator-20261125/manifest.json),
  SHA256 `319b746cef4fb0b77ab08190a052f02ce95e1d3eba23be501ab9157d81baeac1`.
  Build commands, source and tool identities, and exact output comparisons for
  the default, stock-repeat and sequential runs.
- [Bounded tag outcomes](../implementation/retained-evidence/q35p-tag-outcomes-20261023/manifest.json),
  SHA256 `975fb21ac24e0e45c07ac5704e16ebe3a6fcdd229837090178173eb80fb74ba2`:
  immutable semantic patch, authored laws/controls, emitted reproducer, native
  readings, compiler arguments, inputs and available logs.
- [Baseline bindings](../implementation/retained-evidence/close3-q35p-20261013/manifest.json),
  SHA256 `db26237bdbde7915efa9f3d4ce29b3b95c595dc1008842fb34ce9f713a4f3510`:
  emulator/state readings and original diagnostic, with
  [frozen inputs](../implementation/retained-evidence/close3-q35p-20261013/inputs.json).
- [Reusable native candidate](../implementation/retained-evidence/reuse-wire-tags-20261023/manifest.json),
  SHA256 `3fe661163dd4ac2c9781d2229e2a8a546306bfe87359bbecffa1f0d762aaac0d`:
  separate patch, support, unchanged minimal emission, readings, assumptions, scoped
  kernel check and installed-path inventories at `a5e4ba0e3e2ab477cdde2ae8a59dd47b82a9da90`.
- [Executed reusable drivers](../implementation/retained-evidence/reuse-wire-tags-drivers-20261023/manifest.json),
  SHA256 `04b6f1e55fc37ca623105f559be23a23c6af723a271e0adfbd49074d1680dfb6`:
  original per-attempt Python commands.

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

## Conservativity and physical callers

[TagConservativity.v](../../tools/sail-tag-outcomes/TagConservativity.v) proves
that, for a V1 computation whose every continuation is tag-free, the tag
interpreter and the legacy replay with the same old-event handler preserve
return values, frame updates and ordered typed events at every fuel bound.
Tags stay unchanged on success. The equality also preserves an old-event
refusal or fuel exhaustion. The proof classifies every old constructor in the
extended V1 algebra. The complete frozen native comparison with the separately
compiled pre-extension support remains due.

[PhysicalCallerBridge.v](../../tools/sail-tag-outcomes/PhysicalCallerBridge.v)
checks each access kind in the emitted minimal `read_ram` and `write_ram`.
It preserves the requested tag read before the data request, the supplied tag
bit in the result and every response data bit through the emitted width cast.
All three successful write responses call the emitted metadata loop. The write
refusal returns `false` without that loop. The data-read refusal emits
`GenericFail "exit"`, and unused access kinds retain their typed `internal_error`
and continuation.

The locked Rocq 9.3.0 compiled both proof objects under the strict flags. All
15 assumption queries against the actual emitted interface had closed global
contexts. The two scoped kernel checks passed with dependencies admitted. The
source reconstruction matched all 29 selected private support sources.
Two fresh minimal emissions matched both retained Rocq source files byte for
byte when invoked with the relative `bindings.sail` name. The absolute-path
control changed the embedded refusal locations, which the replay now preserves
by passing the relative name in each emission directory.

## Paired emulator emission

The all-module emulator generator ran with both the stock Sail plugin population
and the population containing the patched Rocq plugin. The source manifest, Sail,
Z3 and the other plugins matched. Both runs emitted the same configuration schema
bytes. The paired C++ source and header differed, including generated label names
and register member declarations. A repeat using the stock plugin population and
the same generator flags also differed in both C++ files. Each run used its own
output and SMT cache paths. With Sail's `--dsequential` debug flag, the stock and
patched plugin populations emitted byte-identical C++ sources, headers and
schemas. A fresh repeat of each sequential run used its own empty SMT cache
and output directory. The two new runs agreed on all three files and each
reproduced the corresponding prior output byte for byte.

Sail 0.20.3's `--dsequential` selects ordered `List.map` for the internal
compiler scheduler used by deferred C++ compilation work. The repeated result
passes the [emulator isolation check](../implementation/contracts/canonical-tag-outcomes.md#emulator-isolation-check)
for the frozen inputs. The default runs record variation in the ordinary
development emitter. [Pinned Sail option](https://github.com/rems-project/sail/blob/3df54034910b31a1e00d948ee965b2e9603d68e0/src/bin/sail.ml#L416) ·
[Scheduler](https://github.com/rems-project/sail/blob/3df54034910b31a1e00d948ee965b2e9603d68e0/src/lib/parmap.par.ml#L138) ·
[Deferred compilation](https://github.com/rems-project/sail/blob/3df54034910b31a1e00d948ee965b2e9603d68e0/src/lib/jib_compile.ml#L3042).

## Bound and remaining acceptance

The original checkpoint began at 2026-10-23 06:51:12.259 UTC and exhausted twelve
checks after 993.014 active seconds, including waits. An eager wraparound
`vm_compute` was stopped for allocation; lazy conversion closed the unchanged
statement. Both constructions retain final readings and diagnostics. Some earlier
scratch logs were overwritten: recorded commands, exits and digests do not recover
their bytes or establish complete attempt history.

The [canonical candidate replay](sail-rocq-emission.md#canonical-candidate-replay)
establishes strict whole-term compilation, recursive kernel context and compiled
size with private support. Q35p still owes the complete frozen comparison of
support and the recursive closure on the qualified support. Repeat the sequential
emulator isolation check if the qualification inputs differ from the retained
pair. Q35q owns the hosted support declaration census and all twelve corruption
controls, and Q35o still owes hosted qualification of the immutable emitter.
Q35n owns cold production carriage, and Q35b owes replay and closure with
qualified support.
The [validation handoff](../../AGENTS.md#tool-execution-and-validation)
leaves Host CI and cold Guest CI publication, execution and verdicts to the user.
