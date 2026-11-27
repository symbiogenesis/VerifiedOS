# Sail memory and tag binding qualification

Q35p remains open. The [tag-outcome contract](../implementation/contracts/canonical-tag-outcomes.md)
has a bounded support construction and an actual emitted-caller bridge. Strict
compilation and focused native checks pass; complete semantic, support and
canonical-consumer acceptance remains owed.

## Retained evidence

- [Canonical hart-0 TagConservativity recursive kernel and native assumption closure](../implementation/retained-evidence/q35p-canonical-conservativity-20261127/manifest.json),
  SHA256 `86e7bf2fda88a47512833ec879df55663d843fc09a37330706b4ef20e234c9e2`.
  Strict compilation of `TagInterpreter.v`, `TagConservativity.v`,
  `CanonicalPhysicalCallerBridge.v`, and `CanonicalTagConservativity.v` against
  the canonical hart-0 term (`rv64d_types`, `rv64d`, `riscv_extras`), native
  `Print Assumptions` audit across all `1,038` enumerated declarations (`122` in
  `CanonicalTagPlaneInst`, `145` in `CanonicalOldOutcomesInst`, `307` in
  `CanonicalPhysicalCallerBridge`, and `464` in `CanonicalTagConservativity`,
  all closed under the global context), full recursive `rocqchk -silent -o`
  (`-norec` absent) on both `CanonicalPhysicalCallerBridge` and
  `CanonicalTagConservativity` matching the exact `31` classified floating-point
  axioms, bound inputs, installed-prefix comparison, and replay commands.
- [Recursive kernel and native assumption closure](../implementation/retained-evidence/q35p-recursive-closure-20261126/manifest.json),
  SHA256 `b47e2e2147e339567e28a762510af6de4f3eb640c2091b3a697254121f156ba1`.
  Native `Print Assumptions` audit across all four authored Q35p modules (`811`
  closed declarations) and four-partition recursive `rocqchk -silent -o`
  context summaries (`-norec` absent), bound inputs, installed-prefix
  comparison, and replay commands.
- [Complete 29-module Sail support comparison](../implementation/retained-evidence/q35p-support-comparison-20261126/manifest.json),
  SHA256 `904db7c5abd0fbeb80812ad2e7655be28dc5437bfb3e43194d97ab8b5df21d84`.
  Full 29-module source diff, compiled objects, normalized top-level elaborated
  readings (1,868 declarations each), installed-prefix inventories and replay
  commands.
- [Canonical caller replay manifest](../implementation/retained-evidence/q35p-canonical-callers-20261125/manifest.json),
  SHA256 `e1a92981e480aadecdd6baebb1fd4f98d836c2bb3b89039c6599cc36cff1a4d7`.
  Canonical hart-0 `CanonicalPhysicalCallerBridge.v` source, caller equivalence
  readings, and input identities.
- [Native V1 conservativity and physical-caller checkpoint](../implementation/retained-evidence/holdfast-q35p-worker-proofs-20261125/manifest.json),
  SHA256 `8e0eb97c3f34a8a0e56bbcf5f1a9cf1856a5c429b7916f9e0fdb806b2edd088c`.
  Frozen source identities, minimal emission repeats and focused proof readings.
- [Refreshed sequential emulator isolation](../implementation/retained-evidence/q35p-holdfast-emulator-refresh-20261125/manifest.json),
  SHA256 `eb6ef7fec1e686543a1b759dabe20c2d087a6830a1387d7cc8035dcc2c1806b6`.
  Bound source change, paired run commands and exact output comparisons.
- [Baseline bindings](../implementation/retained-evidence/close3-q35p-20261013/manifest.json),
  SHA256 `db26237bdbde7915efa9f3d4ce29b3b95c595dc1008842fb34ce9f713a4f3510`:
  emulator/state readings and original diagnostic, with
  [frozen inputs](../implementation/retained-evidence/close3-q35p-20261013/inputs.json).
- [Reusable native candidate](../implementation/retained-evidence/reuse-wire-tags-20261023/manifest.json),
  SHA256 `3fe661163dd4ac2c9781d2229e2a8a546306bfe87359bbecffa1f0d762aaac0d`:
  patch, support, unchanged minimal emission, readings, assumptions, scoped
  kernel check and installed-path inventories at `a5e4ba0e3e2ab477cdde2ae8a59dd47b82a9da90`.

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

[TagInterpreter.v](../../tools/sail-tag-outcomes/TagInterpreter.v) gives a fuelled
finite-map interpretation with a fixed other-outcome handler and generic frame,
interpreting tags by executable lookup/insertion at `bv_unsigned key`.
Primitive bridges quantify over arbitrary maps, keys, frames and continuations,
establishing neighbor framing, exception/early-return forwarding, and primitive
agreement for the exact emitted `Interface` implementation.

[TagControls.v](../../tools/sail-tag-outcomes/TagControls.v) and
[PhysicalCallerBridge.v](../../tools/sail-tag-outcomes/PhysicalCallerBridge.v)
check the actual emitted metadata loop and `read_ram`/`write_ram` callers:
aligned, partial and multi-granule writes, distinct raw keys, zero, the largest
unsigned key, and the empty loop at wraparound; requested/unrequested tag reads,
tag/data order, all three `Ok` forms and `Err ()`, ascending clears, forwarding,
and `GenericFail "exit"` / `internal_error` refusals. Distinguishing `Fail`
controls reject changed write type, discarded writes, unconstrained reads,
aliased/changed neighbors, omitted/reordered/added clears, tag-as-exception, and
dummy data writes. These finite controls establish no universal physical-caller
theorem.

## Reusable candidate and independent controls

The [reusable V1 candidate](../../tools/sail-tag-outcomes/README.md)
packages an isolated construction and replay recipe. The November input set binds
the retained Sail and Z3 binaries, complete selected plugin population and private
stdpp source and object bytes. The packaged replay strictly compiled the 29 selected
support modules on each side, both emitted modules and the four authored modules.
Both emissions reproduced the retained sources exactly. The before/after
installed-prefix inventories agreed. The [frozen V1 instance comparison](#frozen-v1-instance-comparison) reads the
affected interface and builtins on both compiled sides.

All 811 enumerated declarations across the four authored modules in the packaged
replay have closed native assumption queries, and full recursive `rocqchk -silent -o`
passes across all four partitions below. Minimal Rocq outputs repeat byte for
byte, as do two C regenerations' `.c`/`.h` files; this is not paired full-model
regeneration. Before/after inventories rescan all installed proof `bin`/`lib`
paths, unchanged, and Sail paths agree during the query/C-generation interval.
The candidate preserves BSD-2-Clause notices and leaves the production recipe,
shared switch, model and emitter unchanged.

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

## Frozen V1 instance comparison

The locked Rocq compiled the same emitted minimal architecture against each
side of the packaged replay. With an empty search blacklist, the native query
enumerated the declarations visible inside its `Interface` and `Defs` instances.
The framed reader compared their types (`Check`), declaration metadata
(`About`), and the printed bodies of transparent constants and inductives.
The retained record includes both normalized readings, the query driver, compile
commands and unchanged input identities. [Frozen V1 instance comparison](../implementation/retained-evidence/q35p-v1-instance-readings-20261125/manifest.json),
SHA256 `8453b57f4da174533d2b247c0c7d632ba9d0fa0033638b25cb874a0e875e166f`.

The candidate adds the two tag constructors and their two builtin bindings.
Every previous name still resolves. The native readings identify
`outcome_ind`, `outcome_rec` and `outcome_rect` as the generated principles
that change. The printed bodies of `outcome`, `map_extra_iMon` and `try_catch`
also change, with matching `Check` and `About` readings.

The additional change to `pure_iTrace_aux` meets the
[tag-outcome comparison criterion](../implementation/contracts/canonical-tag-outcomes.md#source-scope-and-acceptance).
Its source rejects `Choose` and recurses over every other event. Its `Check`
and `About` readings agree. Its printed body adds exactly the `TagRead` and
`TagWrite` cases, each recurring on the trace tail. Every previous case agrees.
The `pure_iTrace` wrapper, the `iTrace_match` relation and the `iMon_equiv`
definition that uses them have identical native readings on both sides. The
complete 29-module support comparison and recursive closure are retained below.

## Complete 29-module support comparison

The replay driver strictly compiled all 29 selected `SailStdpp` modules on both
the baseline and candidate support builds over the retained November inputs.
Across all 29 `.v` sources, only `ConcurrencyInterface.v` and
`ConcurrencyInterfaceBuiltins.v` differ; all other 27 `.v` files are byte-identical.

Native elaborated readings across all 29 `SailStdpp.<Mod>` modules (`Search`
with an empty blacklist, `Check`, `About`, and `Print` for transparent constants
and inductives, with fresh query-local universes normalized) record 1,868
top-level declarations on both baseline and candidate, with identical normalized
readings (`support-baseline.json.gz` and `support-candidate.json.gz`, decoded
SHA-256 `fbf69516126e69fb4abdd4a41766b8f7383644de06093de305180d6e0c601183`).
Six modules have zero top-level declarations on both sides (`Base`,
`ConcurrencyInterfaceBuiltins`, `ConcurrencyInterfaceBuiltinsV2`, `Impl_base`,
`Inhabited`, and `MachineWordInterface`), `ConcurrencyInterface` matches across
all 4 top-level declarations (`empOutcome`, `empOutcome_rec`, `empOutcome_ind`,
`empOutcome_rect`), and zero declarations are added, removed, or changed across
all 29 modules. Both installed opam prefixes (`verifiedos-rocq-9.3.0-ocaml-5.4.1`
and `verifiedos-sail-0.20.3-ocaml-5.4.1`) recorded zero changes before and after.
`candidate.json` binds `frozen_support_manifest` to the
[complete 29-module Sail support comparison](../implementation/retained-evidence/q35p-support-comparison-20261126/manifest.json),
SHA256 `904db7c5abd0fbeb80812ad2e7655be28dc5437bfb3e43194d97ab8b5df21d84`, and
re-running the replay driver verified both the 29-module support readings and
the instantiated V1 readings (`167` baseline vs `171` candidate).

## Recursive kernel and native assumption closure

The replay driver also runs a native `Print Assumptions` audit under the strict
flags across all four authored Q35p modules, instantiating the two functor-only
modules against the emitted minimal architecture and interface
(`TagPlaneInst := TagInterpreter.TagPlane bindings_types.Arch bindings_types.Interface`
and `OldOutcomesInst := TagConservativity.OldOutcomes bindings_types.Arch bindings_types.Interface`).
All `811` enumerated declarations (`122` in `TagPlaneInst`, `237` in
`TagControls`, `145` in `OldOutcomesInst`, and `307` in `PhysicalCallerBridge`)
report `Closed under the global context` (`assumptions.json`, SHA-256
`f6aa149e98b71c5cdb1513fe312acecbbf93e2d0af40e2239cf3760aa4e276e2`).

Full recursive `rocqchk -silent -o` (with `-norec` absent) checks four exact
partitions over the compiled candidate closure (`kernel-check.json`, SHA-256
`e21c22a248fede46440406e8472d11143dc533fee54419138d8b2c03f28506f7`):

- `authored_and_emitted` (`bindings_types`, `bindings`, `TagInterpreter`,
  `TagControls`, `TagConservativity`, `PhysicalCallerBridge`): `0` axioms.
- `support_axiom_free` (`27` `SailStdpp` candidate modules excluding `Real` and
  `Values_lemmas`): `0` axioms.
- `support_values_lemmas_control` (`SailStdpp.Values_lemmas`): exact `3`
  upstream `Stdlib.Program`/`Program.Wf` axioms
  (`Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq`,
  `Stdlib.Logic.FunctionalExtensionality.functional_extensionality_dep`,
  `Stdlib.Logic.ProofIrrelevance.proof_irrelevance`), arising from
  `From Stdlib Require Program Program.Wf.` in upstream `src/Values_lemmas.v`.
  `Values_lemmas` is outside the canonical term's import closure and these
  three axioms are never admitted into the project allowlist.
- `support_real_control` (`SailStdpp.Real`): exact `4` axioms matching
  [sail-support-qualification.json](../../tools/opam/sail-support-qualification.json)
  (`Stdlib.Logic.FunctionalExtensionality.functional_extensionality_dep`,
  `Stdlib.Reals.ClassicalDedekindReals.sig_not_dec`,
  `Stdlib.Reals.ClassicalDedekindReals.sig_forall_dec`,
  `Stdlib.Logic.Classical_Prop.classic`).

`candidate.json` binds `frozen_closure_manifest` to
[Recursive kernel and native assumption closure](../implementation/retained-evidence/q35p-recursive-closure-20261126/manifest.json),
SHA256 `b47e2e2147e339567e28a762510af6de4f3eb640c2091b3a697254121f156ba1`, and
re-running the replay driver verified unchanged installed prefixes and matching
normalized invariants across both `assumptions.json` and `kernel-check.json`.

## Canonical caller replay

Strict Rocq readings compare the minimal reproducer with the canonical hart 0
term on the same private support. The selected bindings and callers agree token
for token after mapping the recorded refusal source paths and line numbers. The
canonical bridge uses the exact canonical locations in its refusal statements.
It compiles under the locked flags, its six lemma contexts are closed, and its
scoped kernel check passes with dependencies admitted. The comparison, input
identities and proof results are bound by the [canonical caller replay manifest](../implementation/retained-evidence/q35p-canonical-callers-20261125/manifest.json),
SHA256 `e1a92981e480aadecdd6baebb1fd4f98d836c2bb3b89039c6599cc36cff1a4d7`.

[The canonical closure driver](../../tools/sail-tag-outcomes/canonical_closure.py)
extends that scoped check to full recursive kernel and native assumption closure
against the compiled canonical hart-0 term (`rv64d_types.vo`, `rv64d.vo`,
`riscv_extras.vo`), all 29 compiled `SailStdpp` candidate objects, and the
matching private `stdpp` tree. After verifying input source/object digests and
snapshotting the installed Rocq prefix before and after, it strictly compiles
all four authored modules (`TagInterpreter.v`, `TagConservativity.v`,
`CanonicalPhysicalCallerBridge.v`, and [CanonicalTagConservativity.v](../../tools/sail-tag-outcomes/CanonicalTagConservativity.v)).
`CanonicalTagConservativity` instantiates
`CanonicalOldOutcomes := TagConservativity.OldOutcomes rv64d_types.Arch rv64d_types.Interface`,
bridges `CanonicalPhysicalCallerBridge.T.run` to `CanonicalOldOutcomes.run_old`,
and proves caller-level tag-preservation and conservativity lemmas over
`rv64d.read_ram` and `rv64d.write_ram`: `read_ram kind (Physaddr addr) width false`
equals `finish_read addr width kind default_meta`, is `tag_free`, steps via
`MemRead` without emitting `TagRead`, and preserves `tags` unchanged; `write_ram`
under a `MemWrite` refusal (`Err tt`) returns `false` without invoking
`__WriteRAM_Meta` and preserves `tags` unchanged; and negative controls exclude
`read_ram kind (Physaddr addr) width true`, `__ReadRAM_Meta`, and
`__WriteRAM_Meta (zeros 64) 1 meta` from `CanonicalOldOutcomes.tag_free`.

The driver audits all `1,038` enumerated declarations under native `Print Assumptions`
(`122` in `CanonicalTagPlaneInst`, `145` in `CanonicalOldOutcomesInst`, `307` in
`CanonicalPhysicalCallerBridge`, and `464` in `CanonicalTagConservativity`, all
`Closed under the global context`) and runs full recursive `rocqchk -silent -o`
(`-norec` absent) on both `CanonicalPhysicalCallerBridge` (`26.088` seconds) and
`CanonicalTagConservativity` (`24.429` seconds, `50.517` seconds total), both
exiting `0` with only the exact `31` classified floating-point axioms in
[the canonical machine term](canonical-machine-term.md#the-31-the-emission-declares)
(`0` `Stdlib.Reals`, `0` `Program.Wf`/`Values_lemmas`, `0` new tag, conservativity,
or bridge axioms) and zero installed-prefix changes. `candidate.json` binds
`frozen_canonical_conservativity_manifest` to
[Canonical hart-0 TagConservativity recursive kernel and native assumption closure](../implementation/retained-evidence/q35p-canonical-conservativity-20261127/manifest.json),
SHA256 `86e7bf2fda88a47512833ec879df55663d843fc09a37330706b4ef20e234c9e2`.

## Paired emulator emission

The stock Sail plugin population and the population containing the patched Rocq
plugin emitted byte-identical all-module C++ source, header and configuration
schema with `--dsequential`. Each run used a fresh output directory and empty SMT
cache. The selected source inventory incorporates the vector floating-point
rounding-mode comment change at `99659edd`. The Sail and Z3 binaries, libraries,
other plugins, configuration and generator flags match the earlier pair, and
all three refreshed output hashes match their earlier counterparts. The pair
passes the [emulator isolation check](../implementation/contracts/canonical-tag-outcomes.md#emulator-isolation-check)
for the refreshed inputs.

Sail 0.20.3's `--dsequential` selects ordered `List.map` for the internal
compiler scheduler used by deferred C++ compilation work. On the earlier inputs,
repeating each sequential run reproduced all three files byte for byte. The
default-scheduler runs agreed on the schema and varied in both C++ files across
plugin populations and between stock repeats. [Pinned Sail option](https://github.com/rems-project/sail/blob/3df54034910b31a1e00d948ee965b2e9603d68e0/src/bin/sail.ml#L416) ·
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
size with private support. Q35p's isolated 29-module support comparison, V1
instance readings, native `Print Assumptions` audit, and four-partition
recursive `rocqchk -silent -o` closure checkpoint are retained against the
November inputs, and the canonical hart-0 closure replay extends native
`Print Assumptions` (`1,038` closed declarations in
`q35p-canonical-conservativity-20261127`)
and un-admitted recursive `rocqchk -silent -o` (`31` classified floating-point
axioms, `F-480`) to `TagInterpreter`, `TagConservativity`,
`CanonicalPhysicalCallerBridge`, and `CanonicalTagConservativity`. Q35p remains open for the
Q35q hosted support declaration census, the Q35o hosted emitter verdict, Q35n
cold production carriage, Q35b whole-term replay and closure with qualified
support, F-480 disposition of the `31` floating-point axioms, and repeating the
sequential emulator isolation check if qualification inputs differ from the
retained pair.
The [validation handoff](../../AGENTS.md#tool-execution-and-validation)
leaves Host CI and cold Guest CI publication, execution and verdicts to the user.
