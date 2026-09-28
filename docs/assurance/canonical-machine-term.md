# The canonical machine term

*Q35b's record in [the implementation plan](../implementation/implementation-checklist.md#q-assessment-actions), which owns [the proof map's](unassigned-proof-map.md#7-the-next-slices) U-21. R-05-019b makes the Rocq definitions Sail's own backend emits from the frozen model the one term that the Iris-over-Sail logic and the RTL refinement quantify over, and R-05-019c keeps that emission downstream of the reviewed model. This record states how the term is emitted, what identifies it, which undeclared axioms it and its support library carry and how each can leave, its emitted size, and whether it is tracked. The compile at the locked prover, the exact assumption closure and the compiled size wait on the Sail support library's return to the proof switch, which [the opam guide](../../tools/opam/README.md) owns; [what stays owed](#8-what-stays-owed-and-the-blocking-input) records that blocking input. Every reading below was taken on 2026-09-28 at base revision `41fc2086850670eacae03c0f972c1233689ba9ba` in the lane `q35b-impl-20260928`, and [`/root/build/lane-q35b-impl-20260928/q35b/receipt.json`](../implementation/retained-evidence/root/build/lane-q35b-impl-20260928/q35b/receipt.json), SHA-256 `cfc2431322f1dfe7d3bdd80616500c77c9413e5281de1ba2b56f43ca276f71bb`, retains the native figures.*

## 1. How the term is emitted

The model's CMake target `generated_rocq_rv64d` in [model/model/CMakeLists.txt](../../model/model/CMakeLists.txt) runs Sail once from `model/model` and writes `rv64d.v` and `rv64d_types.v` under the build tree's `rocq/` directory. The lane emitted it in two guest steps, which are the reproducible command sequence:

1. Configure the lane's model tree with the configure line `run.py model build` and `run.py model emit` share (`_configure` in [the model command](../../tools/vos/cli/model.py)), seeding its memo cache and test data as they do. `python tools/run.py model emit` performs this step on a tree that has no `build.ninja`, and emits the C++ model besides.
2. Run `cmake --build <tree> -j 1 --target generated_rocq_rv64d`, where `<tree>` is the lane's build tree, `/root/build/lane-<lane>/verifiedos-model`.

The Sail command the target runs, as its build log records it with the tree written `<tree>`:

```console
sail --strict-var --strict-bitvector --strict-exponentials --require-version 0.20.2 \
  --memo-z3-path <tree>/model/sail_smt_cache --drocq-undef-axioms --rocq \
  --rocq-lib riscv_extras --rocq-output-dir <tree>/rocq -o rv64d \
  --config <tree>/config/rv64d_v256_e64.json --all-modules riscv.sail_project
```

`--drocq-undef-axioms` makes Sail emit an `Axiom` for each function the model declares and does not define for the Rocq target. Sail 0.20.2's help lists the option as `--rocq-undef-axioms`; this spelling is accepted and took effect, the emission carrying 85 `Axiom` declarations. `--rocq-lib riscv_extras` adds `Require Import riscv_extras.` to the output, so [the model's Rocq support file](../../model/handwritten_support/riscv_extras.v) is an input to the compile and not to the emission. `--config` fixes the model's configuration into the term; [the configuration section](#4-the-configuration-the-target-emits-at) records which file the target names.

No tool command wraps the two steps with an identity receipt. One is proposed with the axiom removals rather than added here, because today it would either emit at the target's configuration, which F-478 records as wrong, or restate the target's flags in a second place.

## 2. Generation identity

| Input or output | Identity | Predicate |
| --- | --- | --- |
| Sail | `Sail 0.20.2 (sail @ opam-v2.5.0 0.20.2)`; `bin/sail` SHA-256 `c3040b2464bccf4167ca21f9d74211bd087537c296ce27a302d941b9bc9b44b8`; Rocq backend plugin `share/libsail/plugins/sail_plugin_coq.cmxs` SHA-256 `148606b5345e542de96f86b71f4a419dd635e816c4b605332087f3c6788a7ef9` | the switch `verifiedos-sail-0.20.2-ocaml-5.4.1`, imported from [sail.lock](../../tools/opam/sail.lock) |
| Solver | Z3 5.1.0, SHA-256 `f12647df960955e4484afcba8cd0ffa02a9fd5d73dd2429a07578600ab299969` | the pinned prefix `/root/z3-5.1.0`, which the tools put ahead of the distribution's solver |
| Flags | the command in [section 1](#1-how-the-term-is-emitted) | the target as the base revision configures it |
| Model sources | 132 files, aggregate SHA-256 `bf3c276056ae34e10f36b80fc1a1498d254dbe404edbaf477179bab9d2a094cf` | the list `sail riscv.sail_project --all-modules --list-files-separated ';'` prints from `model/model`, which the model's CMake reads at configure; the SHA-256 of each file's bytes; the aggregate is the SHA-256 of the lines `<sha256>  <path>` sorted by repository path, each ending in a newline; the receipt lists every file |
| Sail library | 39 files, each equal to the MD5 [the tracked model bundle](../../tools/generated/sail_riscv_model.json) records for it | the bundle's library keys resolved under the Sail switch's `share/sail/` |
| Configuration | `<tree>/config/rv64d_v256_e64.json`, SHA-256 `76a9dcf3e4c58ad3d1861ebaded90bed341c5b84edb9860b69169addd6af48aa`, generated from [config.json.in](../../model/config/config.json.in), SHA-256 `a2cd42ce3655e844c628ad1ebdb6c07160ce1b6cefc6c8ab9209edae5b005cb8` | CMake's `configure_file` in [the configuration directory](../../model/config/CMakeLists.txt) |
| Project file and target | `riscv.sail_project` SHA-256 `2b3b4a35761bb387d3ac42347d85766642ab15c7ec5b3b860fceda3ebd29c1b7`; `model/model/CMakeLists.txt` SHA-256 `98607320dbed5a7efbd07d401945476c6886c7aed6237166a0b6a033c1ac6077` | bytes at the base revision |
| Output `rv64d.v` | SHA-256 `050e3616559c8287c4f166545f723fe413f2357e3f5849beece01a714bb6b793`, 3,785,951 bytes, 71,947 lines | lines counted as newline characters |
| Output `rv64d_types.v` | SHA-256 `0314c47ed739add290a11f48b9a18849fc783514e9a5ee79347c1db72a832c80`, 506,944 bytes, 12,951 lines | as above |

The explicit source list is used rather than the tracked bundle's owner hashes because the bundle's MD5 map records 121 of the 132 files the emission reads. The other eleven, `extensions/B/zbc_insts.sail`, `extensions/K/zbkx_insts.sail`, `extensions/Zicboz/zicboz_insts.sail`, `extensions/bfloat16/zvfbfmin_insts.sail`, `extensions/bfloat16/zvfbfwma_insts.sail`, `extensions/platform/cbo_scrub.sail`, `extensions/platform/fence_t.sail`, `extensions/vector_crypto/zvbb_insts.sail`, `extensions/vector_crypto/zvbc_insts.sail`, `extensions/vector_crypto/zvkg_insts.sail` and `postlude/csr_end.sail` under `model/model/`, appear in the bundle only as source locations. The 121 recorded files and the 39 library files all equal their recorded MD5 at the base revision (F-482).

## 3. The digest moves with the model

| Emission | Source state | `rv64d.v` SHA-256 | `rv64d_types.v` SHA-256 | Axioms | Wall time | Peak resident |
| --- | --- | --- | --- | --- | --- | --- |
| 1, the target | base revision | `050e3616559c8287c4f166545f723fe413f2357e3f5849beece01a714bb6b793` | `0314c47ed739add290a11f48b9a18849fc783514e9a5ee79347c1db72a832c80` | 85 | 4 min 0 s | 1,121,940 kB |
| 2, the target again | base revision | `050e3616559c8287c4f166545f723fe413f2357e3f5849beece01a714bb6b793` | `0314c47ed739add290a11f48b9a18849fc783514e9a5ee79347c1db72a832c80` | 85 | 3 min 4 s | 1,117,348 kB |
| 3, seeded edit | `model/model/extensions/M/mext_insts.sail` line 59, a division by zero yielding -2 where the model yields -1 | `0754e59d0f7a1e72c6e26a3b301094dfc71bc3fd3e6a5bb54c1762d58f5a7097` | `0314c47ed739add290a11f48b9a18849fc783514e9a5ee79347c1db72a832c80` | 85 | 3 min 1 s | 1,138,516 kB |
| 4, extern keys | `model/model/prelude/prelude.sail` lines 43 to 47, the four `rocq:` extern keys spelled `coq:` | `03f870cf295bd018b55af59b114da48eee8ca6a5392fb35c59a3578e25d3e1c0` | `0314c47ed739add290a11f48b9a18849fc783514e9a5ee79347c1db72a832c80` | 81 | 2 min 59 s | 1,137,316 kB |
| 5, frozen profile | base revision; the target's command run directly with `--config` naming `model/config/verifiedos.json` | `60a280fb40d54f2343668a6f5f89bc174409bc19c229ac5d692acf5166b17384` | `d63859dfac552509553857de4e3c59b645e9d8cee630c5184a33fba97b39eb46` | 85 | 6 min 5 s | 1,121,608 kB |

*Axioms* counts the lines of `rv64d.v` that open with `Axiom`. Wall time and peak resident are GNU `time`'s elapsed time and maximum resident set size of the build command for emissions 1 to 4 and of the Sail process for emission 5, one run each on a 12-core, 21 GB guest that two other lanes shared.

- **Emission is deterministic in a lane.** Emission 2 repeats emission 1 byte for byte. Neither file contains an absolute path, but `rv64d.v` embeds model-relative source locations in its assertion messages, on 754 lines containing `.sail:` followed by a digit, so a line moved in a source moves the digest without a semantic change.
- **A seeded model edit moves the digest.** The edit in emission 3 changes exactly one line of `rv64d.v`, line 62588, from `Z.opp (1)` to `Z.opp (2)`, and leaves `rv64d_types.v` unmoved. Each temporary edit was restored with `git checkout`; afterwards `git status --short -- model` printed nothing, `git ls-files --eol` read `i/lf w/lf attr/-text` for the file as before, and its SHA-256 equalled the base revision's. Neither edit is committed.

## 4. The configuration the target emits at

The target's `--config` names the configuration CMake generates from `config.json.in`, not the frozen profile, [verifiedos.json](../../model/config/verifiedos.json), that the tools hand the emulator. Flattened by [the tools' configuration reader](../../tools/vos/config.py), each has 254 leaves, and 19 differ: `base.mtvec.vectored.supported`; the `supported` switch of `A`, `Zaamo`, `Zama16b`, `Zbc`, `Zic64b`, `Ziccamoa`, `Ziccif`, `Zicclsm`, `Zvfbfmin`, `Zvfbfwma`, `Zvfh`, `Zvfhmin` and `Zvknha`; the three `memory.misaligned.exceptions` leaves; `memory.physaddr_bits`; and `memory.regions`. The term carries each difference. Emission 1 defines `physaddr_bits` as 56 where emission 5 defines 36, answers `currentlyEnabled` the other way for those 13 extensions, and sets the three misaligned-access exception settings to `None` where emission 5 sets `Some (AlignmentException)`. The two emissions declare the same 85 axioms by name.

The target's term therefore describes a machine other than the frozen profile (F-478). This record takes emission 5's configuration as the term consumers read, the target's own command at the frozen profile, until the target binds the profile; the repair is one line of the model's CMake and is proposed with the axiom removals.

## 5. Undeclared axioms and how each can leave

This section lists every undeclared axiom and parameter that a source reading, and the probe below, places in the term's closure. It is not the closure as the gate reads it: the gate reads the kernel checker's whole-environment summary after compilation, as [the tool guide](../../tools/README.md#current-evidence-and-generated-documentation) states, and that compile is owed. R-05-164's declared set is empty, so the gate refuses every name below today.

Three classes, following the plan's cell:

- **Model:** removable by a change inside `model/`, either a Rocq binding to an existing Rocq definition or to one added to the model's Rocq support file, or a Sail definition, deletion or Rocq-target guard that the backend emits from. This reads the cell's *definition in the model's Rocq support library* as including the model sources the backend emits that library's callers from, and is stated so that the review can refuse the reading.
- **Support library:** removable only by a change in `rocq-sail-stdpp`, or in the Sail library the locked emitter reads, both upstream artifacts at the locked pair.
- **Irremovable:** no definition at the pinned toolchain fixes the meaning, so the axiom stays unless the review gate admits it under R-05-164 or commissions a semantics that defines it.

### The 85 the emission declares

Paths are under `model/model/` unless stated; *references* counts whole-word occurrences in `rv64d.v` other than the declaration.

| Axioms | Declared at | References | Class | How it leaves |
| --- | --- | --- | --- | --- |
| `quot_positive_round_zero`, `quot_round_zero`, `rem_positive_round_zero`, `rem_round_zero` | `prelude/prelude.sail` lines 43, 44, 46 and 47 | 58, 7, 36 and 6 | Model | Each carries a `rocq:` extern key, which Sail 0.20.2's Rocq backend does not read; it reads `coq:`. Emission 4 spells the four keys `coq:`, and the four axioms leave, the term calling `Z.quot` and `Z.rem` (F-479). |
| `read_mem_`, `read_mem_ifetch_`, `read_mem_exclusive_`, `write_mem_`, `write_mem_exclusive_` | the Sail library's `concurrency_interface/emulator_memory.sail`, reached through `$include <concurrency_interface.sail>` at `core/phys_mem_interface.sail` line 16; for any target but Isla, C, C++, OCaml and SystemVerilog the library declares them without a body | none | Model | A Rocq-target guard in the model around the library's emulator-memory declarations; the term reaches memory through the concurrency interface's `sail_mem_read` and `sail_mem_write` instead. A Sail library change would also remove them. |
| `__TraceMemoryWrite`, `__TraceMemoryRead` | `core/phys_mem_interface.sail` lines 149 and 150, with no extern binding and no body | none | Model | Deleting the two declarations, which nothing calls, or defining them as no-ops. |
| `vtr_mnemonic_backwards`, `vtr_mnemonic_backwards_matches` | `extensions/V/vext_vset_insts.sail` line 45, a mapping whose forwards direction alone is defined | none | Model | Defining the backwards, assembly-parsing direction in the model; it carries no execution semantics. |
| `blkdev_host_trace_enabled`, `blkdev_host_input`, `blkdev_host_persist`, `plat_term_write`, `plat_term_read` | `sys/block_device.sail` lines 39, 40 and 139 and `sys/platform.sail` lines 583 and 584, each bound for C++ and the terminal pair also for Lem | 7, 7, 3, 1 and 0 | Model | Rocq-target bodies in the model: trace disabled and no effect for the two trace hooks, the host's persistence answer as the monad's own nondeterministic choice, which the backend emits for Sail's `undefined`, no effect for the terminal write and a chosen byte for the read. Which host behaviour the term observes is a modeling decision (F-485). |
| `riscv_f16Lt`, `riscv_f16Lt_quiet`, `riscv_f16Le`, `riscv_f16Le_quiet`, `riscv_f16Eq`, `riscv_f32Lt`, `riscv_f32Lt_quiet`, `riscv_f32Le`, `riscv_f32Le_quiet`, `riscv_f32Eq`, `riscv_f64Lt`, `riscv_f64Lt_quiet`, `riscv_f64Le`, `riscv_f64Le_quiet`, `riscv_f64Eq` | `core/softfloat_interface.sail`, each bound for C++ to Berkeley SoftFloat 3e and for Lem, and for no other target | 1 or 2 each, none for the three `Le_quiet` | Model, conditionally | Sail's float library at 0.20.2, whose interface the model's prelude already includes, defines `float_is_lt`, `float_is_lt_quiet`, `float_is_le`, `float_is_le_quiet` and `float_is_eq` over bit vectors with exception flags. Routing the comparisons through them needs an adapter, because the library's flag constants put invalid at bit 0 and inexact at bit 4 where the model's `nvFlag` and `nxFlag` put them at bits 4 and 0, and a checked agreement with SoftFloat 3e, which the emulator links, over the vector compare instructions. |
| `riscv_f16Add`, `riscv_f16Sub`, `riscv_f16Mul`, `riscv_f16Div`, `riscv_f32Add`, `riscv_f32Sub`, `riscv_f32Mul`, `riscv_f32Div`, `riscv_f64Add`, `riscv_f64Sub`, `riscv_f64Mul`, `riscv_f64Div`, `riscv_f16MulAdd`, `riscv_f32MulAdd`, `riscv_f64MulAdd`, `riscv_f16Sqrt`, `riscv_f32Sqrt`, `riscv_f64Sqrt`, `riscv_f16roundToInt`, `riscv_f32roundToInt`, `riscv_f64roundToInt` | `core/softfloat_interface.sail`, bound as above | none to 4 each | Irremovable | No definition exists at the pinned toolchain: the model and `rocq-sail-stdpp` define none, and Sail's float library at 0.20.2 defines one arithmetic entry point, `float_add`, which reads its rounding mode from the library's register `fp_rounding_global` where these operations take the mode as an argument. They stay unless the review gate admits them under R-05-164 or commissions an IEEE 754 semantics, authored in the model's Sail or admitted as a library, with its agreement with SoftFloat 3e shown (F-480). |
| `riscv_f16ToI32`, `riscv_f16ToUi32`, `riscv_i32ToF16`, `riscv_ui32ToF16`, `riscv_f16ToI64`, `riscv_f16ToUi64`, `riscv_i64ToF16`, `riscv_ui64ToF16`, `riscv_f32ToI32`, `riscv_f32ToUi32`, `riscv_i32ToF32`, `riscv_ui32ToF32`, `riscv_f32ToI64`, `riscv_f32ToUi64`, `riscv_i64ToF32`, `riscv_ui64ToF32`, `riscv_f64ToI32`, `riscv_f64ToUi32`, `riscv_i32ToF64`, `riscv_ui32ToF64`, `riscv_f64ToI64`, `riscv_f64ToUi64`, `riscv_i64ToF64`, `riscv_ui64ToF64`, `riscv_f16ToF32`, `riscv_f16ToF64`, `riscv_f32ToF64`, `riscv_f32ToF16`, `riscv_f64ToF16`, `riscv_f64ToF32`, `riscv_f32ToBF16` | `core/softfloat_interface.sail`, bound as above | none to 4 each | Irremovable | As for the arithmetic row: Sail's float library at 0.20.2 defines no conversion (F-480). |

The counts close: 4, 5, 2, 2 and 5 in the class Model outright, 15 in it conditionally and 52 irremovable, which is 85. The frozen profile sets the vector extension's support level to `Full`, which admits the vector floating-point instructions that call them, so the 67 floating-point axioms are load-bearing for those instructions. For a proof about integer code, such as Q35d's two functions, they matter because the gate refuses a loaded axiom whether or not a proof uses it.

### The five the support library loads

| Axiom | Loaded by | Class | How it leaves |
| --- | --- | --- | --- |
| `Stdlib.Logic.FunctionalExtensionality.functional_extensionality_dep`, `Stdlib.Reals.ClassicalDedekindReals.sig_not_dec`, `Stdlib.Reals.ClassicalDedekindReals.sig_forall_dec` | Stdlib's `Rbase`, and its `ROrderedType`, which the support library's `Values`, `State_monad`, `Instances` and `Real` require | Support library | Neither emitted file performs a real-number operation, by a source reading of both. A support library without the Reals requires, and without its concurrency interface's real-valued choice, removes them, together with the term's own `Require Import SailStdpp.Real`, which Sail emits (F-481). |
| `Stdlib.Logic.Classical_Prop.classic` | Stdlib's `Reals`, which the support library's `Real` requires | Support library | As above (F-481). |
| `Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq` | Stdlib's `Eqdep`, which the support library's `Values` requires | Support library | Using `Eqdep_dec`'s lemmas over the library's decidable index types in place of `Eqdep` (F-481). |

**The Stdlib figures are measured; the rest of this part is a source reading.** A probe file requiring exactly the Stdlib and stdpp modules that the term, `riscv_extras.v`, the support-library modules the term loads and stdpp's `bitvector.definitions` require, read from their sources, was compiled by the proof switch's `rocq` and checked by its `rocqchk -silent -o`, the gate's checker flags, in a scratch directory under the lane, with no switch changed. The context summary names exactly these five axioms and no type-in-type, unsafe fixpoint or assumed-positivity entry. Loading everything but Stdlib's Reals modules and `Eqdep` names none; `Rbase` and `ROrderedType` each name the first three, `Reals` adds `classic`, and `Eqdep` names `eq_rect_eq`.

`rocq-sail-stdpp` 0.20.2's source, fetched with `opam source` into the lane and installed nowhere, declares no global assumption in the modules the term loads: `SailStdpp.Base` with its requires, `Real`, `GenericValue` and the three concurrency-interface modules the term imports. Its `Parameter` and `Axiom` commands sit inside module types, `MachineWordInterface` and the concurrency interface's `Arch`, which `rv64d_types.v` instantiates with definitions; every `Context` sits inside a section; and no module is opaquely sealed. The modules the term does not load include `Values_lemmas`, which alone requires Stdlib's `Program`. The three source files of `rocq-stdpp-bitvector` 1.13.0 declare no assumption. The emitted files contain no `Admitted`, `admit`, `Parameter` or `Variable`, and `rv64d_types.v` no `Axiom`.

The gate's reading of an installed library can name more than a recursive check does: a worker that admits an installed library names each field of its opaquely sealed modules as an axiom, and Stdlib has such modules. Which names the gate covers, and whether the list above is the whole closure, is decided at the compile.

## 6. Emitted size

| File | Bytes | Lines | Commands opening a line |
| --- | --- | --- | --- |
| `rv64d.v` | 3,785,951 | 71,947 | 3,385 `Definition`, 23 `Fixpoint`, 85 `Axiom`, 239 `Hint` |
| `rv64d_types.v` | 506,944 | 12,951 | 952 `Definition`, 133 `Inductive`, 20 `Record`, 544 `Instance`, 586 `Lemma`, 148 `Notation`, 97 `Hint`, 3 `Module` |

The figures are emission 1's at the base revision. A command is counted where it is a line's first token after an optional attribute. Emission 5's files are 3,786,165 and 506,944 bytes with the same line counts. Emission costs one Sail process of 3 to 6 minutes and about 1.1 GB peak resident, the times varying with the other lanes' load. The compiled size, compile time and compile memory are owed with the compile.

## 7. Tracking decision

**The term is not tracked in this repository at this revision.** It is regenerated from the pinned toolchain, and a consumer cites the identity in [section 2](#2-generation-identity), or its own regenerated digest beside that identity's inputs.

- **Reproducibility.** Two emissions in one lane agree byte for byte, and every input is pinned: the Sail switch by its lock, the solver by its prefix and the sources by revision. Agreement across lanes or on a hosted runner is not yet measured; the first consumer that regenerates elsewhere compares its digest with this record's.
- **Staleness.** Every model edit moves the term, a moved source line included. A tracked copy would need a generated-artifact row with a guest-lane check like the bundle's, which is not this item's to add; untracked, the identity pins what a consumer read.
- **The gate.** The term cannot enter `proofs/` while it carries the axioms above and the support library is absent from the proof switch, and a copy tracked elsewhere gives no consumer a checked object.
- **Licence.** The output is generated from the model, a modified BSD-2-Clause derivative of sail-riscv and sail-cheri-riscv, and from the BSD-2-Clause Sail library, and each file carries only the line `(*Generated by Sail from rv64d.*)` with no notice. Outside `model/`, [the licensing map](../../COPYRIGHT.md), decided by path, would place it under Apache-2.0 as a non-Markdown file, so tracking it needs a map row and the retained BSD-2-Clause notice that `model/` carries.
- **Size and consumers.** The two files total 4,292,895 bytes, below the tracked model bundle, so size alone decides nothing. Q35c reads the term's definitions and Q35d reduces over it; each can regenerate in its lane and cite the identity.

The decision is revisited when the term compiles at the locked prover with the guide's library, the target binds the frozen profile and the removals land; tracking then comes with a generated-artifact row and a licensing-map row, owned by whoever tracks it.

## 8. What stays owed, and the blocking input

- **The blocking input.** The proof switch carries no Sail support library, by the opam guide's decision, and the guide returns `rocq-sail-stdpp` to it once a release admits Rocq 9.3, taking the release paired with the locked Sail. Read on 2026-09-28 without `opam update`: the guest's local package metadata lists `rocq-sail-stdpp` 0.20.2 alone; the Rocq released repository's history adds 0.20.3 on 2026-09-24; both releases require `rocq-core` at least 9.0 and below 9.3 and conflict with every Sail but their own version, so 0.20.3 pairs with Sail 0.20.3, which is not locked; and the opam repository's `rocq-core` versions end at 9.2.0. No release admits Rocq 9.3, so the wait outlasts the emission (F-483).
- **Owed with the compile:** the term's compile at the locked prover with the guide's library; the exact assumption closure as the gate reads it, compared by name with [section 5](#5-undeclared-axioms-and-how-each-can-leave); and the compiled size, compile time and peak memory.
- **Read at the compile.** `rv64d_types.v` has 586 lines opening with `Lemma` and 23 opening with `Proof`. The opam guide records that Rocq 9.3 reports a proof opened without `Proof` as `missing-proof-command` by default, and the gate's settings make a default-enabled warning an error, so a compile at 9.3 under those settings reads these proofs (F-484).
- **The term's top-level loop is bounded.** A `$iftarget rocq` block in [the step file](../../model/model/postlude/step.sail) gives the model's top-level `loop` the termination measure 100 so that it can be emitted, so the term's `loop` runs at most that bound where the emulator's does not. A consumer states its properties over `step` and `try_step`, or over the bounded loop by name.

## 9. Findings

- **F-478** owed-act: the model's `generated_rocq_rv64d` target emits the term at the configuration generated from `config.json.in` rather than at the frozen profile, 19 configuration leaves differing, so its term describes another machine. Open: the proposed removal cell binds the target to the profile; consumers read emission 5's configuration meanwhile.
- **F-479** upstream-defect: the curated prelude's four integer quotient and remainder declarations carry `rocq:` extern keys that Sail 0.20.2's Rocq backend does not read, so each is emitted as an axiom. Open: the proposed removal cell spells them `coq:`, which emission 4 measured removing all four.
- **F-480** owed-act: 52 floating-point operations, the arithmetic, fused multiply-add, square root, rounding and conversions the model binds to SoftFloat 3e, have no definition at the pinned toolchain and are irremovable without a new IEEE 754 semantics. Open: a review-gate act under R-05-164, admitting them by name or commissioning a semantics with its agreement to SoftFloat 3e shown.
- **F-481** upstream-defect: `rocq-sail-stdpp` 0.20.2 requires Stdlib's Reals and `Eqdep` in the modules the term loads, which loads five Stdlib axioms that neither emitted file uses, outside R-05-164's empty declared set. Open: a support-library change taken when the opam guide returns the library, or else a review-gate act under R-05-164.
- **F-482** owed-act: the tracked model bundle's MD5 map records 121 of the 132 source files the model's project lists, so the host half of K-88 and the Sail context tool, which read that map, cannot see an edit to the other eleven; the guest half's byte comparison can, since the bundle embeds their clause text. Open: K-88's owner states the residue or closes it.
- **F-483** measurement: no `rocq-sail-stdpp` release admits Rocq 9.3, 0.20.3 having joined 0.20.2 on 2026-09-24 with the same `rocq-core` bound and a pairing with the unlocked Sail 0.20.3, and the opam repository carries no `rocq-core` 9.3.0. Standing: the compile, closure and compiled size wait on the opam guide's act.
- **F-484** owed-act: the emitted types file opens most of its lemmas without `Proof`, which Rocq 9.3 reports by default and the gate's settings would make errors. Open: the compile owed here reads it at whichever prover the opam guide's act selects.
- **F-485** owed-act: five host-interface hooks are uninterpreted monadic axioms in the term, and removing them needs a decision on how the term models the host: its persistence answer as a nondeterministic choice, the trace hooks as no effect, and whether console output is observed. Open: the proposed removal cell takes the decision, and Q35c's breakdown reads what the logic observes.
