# Sail Rocq emission qualification

Q35o remains open. The canonical target omits unused `Real`, and its generation
identity binds the native plugins Sail selects. A private syntax candidate
preserves the minimal and canonical types' elaborated declarations; the
handwritten support and candidate types compile strictly without diagnostics.
The retained main-module compile against the earlier support stops at Q35p's
tag-write monad mismatch. The main has not been qualified against the
[memory-binding candidate](sail-memory-bindings.md).

## Retained evidence

Each bundle binds its executed commands, inputs, readings and diagnostics.

- [Handwritten support and canonical types](../implementation/retained-evidence/q35o-handwritten-types-20261023/manifest.json),
  SHA256 `e6d5db45c31b8983a137bfbd0bd04a9ea36a400a9128aecad9f66a6b97bf835d`:
  preserving import repair, native declarations and assumptions, fresh original-plugin
  generation, complete types comparison and strict compilation at
  `a5e4ba0e3e2ab477cdde2ae8a59dd47b82a9da90`.
- [Scoped canonical syntax](../implementation/retained-evidence/q35o-scope-20261023/manifest.json),
  SHA256 `30f9caabab5f9e92c949242b527a8702b4a6a19ec022ef821b7367465305b32c`:
  private patch, four notation controls, canonical generation identity, first strict
  diagnostic and installed-artifact restoration at base `59f8a9e9`.
- [Minimal syntax and identity](../implementation/retained-evidence/close3-q35o-20261013/manifest.json),
  SHA256 `c23303de03306ca8f985592f4967cf61db365ddb0168cebc16ccf8950a4c07dd`:
  source patch, frozen readings, generation receipt and notices at inputs `2f3500f6`.

## Canonical target and loader identity

The alternate module argument selects `SailStdpp.Base`,
`SailStdpp.ConcurrencyInterfaceTypes`, `SailStdpp.ConcurrencyInterface` and
`SailStdpp.ConcurrencyInterfaceBuiltins`. Both generated files omit
`SailStdpp.Real`. The receipt retains the unchanged frozen configuration,
133-source aggregate, 31 already classified emitted axioms and actual installed
plugin population. Complete generated canonical files remain native and untracked
under the [tracking decision](canonical-machine-term.md#7-tracking-decision).

Sail 0.20.3's `src/bin/sail.ml`, SHA256
`82cf0ee3369b235d58e3028ac1c4de916986b2377a6b192a7cee086962f12ec8`,
uses ordered `SAIL_PLUGIN_DIR` directories when present, otherwise Dune's plugin
sites. Presence of `SAIL_NO_PLUGINS` disables loading. Native enumeration loads
files whose `Filename.extension` equals `.cmxs`: installed OCaml 5.4.1 controls
exclude `.cmxs` and `..cmxs` but include `.hidden.cmxs`. Native and Python directory
selection orders agree for the observed installation.

Fresh identity refuses the independent `SAIL_DIR` and `DUNE_DIR_LOCATIONS`
selectors on the default-plugin route, requiring explicit absolute plugin
directories instead. The selected library directory must also be absolute.
Disabled, empty, relative, missing and duplicate backend selections refuse.
Before/after comparisons bind every selected plugin and directory order,
including plugins able to register another backend. They are input inventories,
not an atomic Dynlink trace; legacy receipts retain their original omissions.

Metadata subprocesses inherit the full environment and use unique absolute
temporary directories. Eleven focused `model_rocq` cases cover plugin mutations,
hidden filenames, order changes, overrides, refusals and cleanup; locked Windows
and Linux typechecking passes.

## Handwritten support and canonical types qualification

The model-owned `riscv_extras.v` explicitly imports `List` and `Lia` from
`Stdlib`. Its complete native inventory has identical types, universes,
transparent bodies and declaration metadata before and after the spelling
change. All owned declarations have closed native assumption queries, and the
candidate compiles strictly without diagnostics.

Fresh original-plugin generation and the scoped candidate bind identical frozen
configuration and complete Sail source identities. Their untouched
`rv64d_types.v` files compile at identical original settings with byte-identical
readings over every native declaration and transparent/inductive `Print` target.
The candidate also compiles strictly. A cross-flag comparison would be invalid:
`-disallow-sprop` suppresses automatically generated `_sind` declarations.

Private support reconstructs exactly from the authenticated paired release and
Q35g/Q35n patches without fuzz. The `Base` and canonical V1 dependency closures
compile strictly. Source/object inventories bind the actual dependencies and
unchanged installed objects and sentinels. The retained bounded replay reads the
complete baseline body output under an explicit larger cap; it drops no body.

## Immutable syntax trial and exact stop

The candidate derives from Sail 0.20.3's `src/sail_coq_backend/pretty_print_coq.ml`
at `3df54034910b31a1e00d948ee965b2e9603d68e0`. Its in-file BSD-2-Clause notice and
release `LICENSE` were read before incorporation. The patch adds explicit `Proof`
openings and rewrite-database declarations, emits Q35n's level-0
`sail_update (r with field := e)` syntax with unchanged expansions, and imports
`Defs` with the locked prover's `-(notations)` filter. Four outcome notations are
declared in `sail_concurrency_scope`; their expansions remain `Defs.bind`,
`Defs.bind0` and `Defs.pure_early_return_bind`, including `>>$`'s ignored argument.
No warning, primitive, Gallina statement, executable expansion, pin or acceptance
compiler changes.

The minimal concurrency probe adds an enum, record, variant and record update.
Both output modules compile strictly without diagnostics and repeat byte for byte.
At identical original settings, all 347 declarations (300 types, 47 main) and
283 transparent/inductive print targets retain identical elaborated readings.
Four strict controls establish the original expansions of `>>=`, `>>`, `>>$=`
and `>>$` by reflexivity with closed assumption queries. This qualifies the finite
canonical V1 probe; V2 and custom `concurrency_monad_params` remain unqualified.

The actual target emits through `run.py model rocq` with an absolute private
`SAIL_PLUGIN_DIR`. Its receipt binds the complete plugin population and unchanged
model inputs. The 241.7-second run records unavailable unrelated-backend options
and the actual solver; the preferred `/root/z3-5.3.1/bin` was absent. These
observations supply no locked-toolchain or hosted verdict.

Canonical types compile strictly. Against the earlier support, the untouched main
stops at `write_tag_bool` in `__WriteRAM_Meta`: it returns
`Prompt_monad.monad bool` where `M unit` is required. No output was post-edited.
This is the semantic boundary owned by Q35p.

The retained setup incident supplies no qualification evidence: an unfiltered
dependency sort compiled two installed `BinNums` files before refusing
`EqdepFacts`. The touched objects/globs were restored from that switch's original
duplicate destinations, and three new auxiliary files were preserved then removed.
The restoration receipt binds original identities. The corrected harness asserts
selected-source membership and lane containment and checks installed sentinels.

## Remaining acceptance

Q35p's semantic qualification and Q35q's [native census](sail-support-inventory.md)
are independent prerequisites. Q35o still owes complete canonical-main frozen
comparison and hosted immutable-plugin/source qualification. Q35b retains strict
whole-term compilation, exact assumption closure and compiled size; Q35n retains
cold production carriage. The handwritten proof-maintenance handoff requires
cold Guest CI under the existing proof workflow. Hosted execution and verdicts
remain user-managed under the [validation handoff](../../AGENTS.md#tool-execution-and-validation).
