# Third-Party Components

This document records third-party components, their licenses, and how VerifiedOS uses or distributes them. [COPYRIGHT.md](COPYRIGHT.md) covers content authored by this project. The upstream license texts govern each component; this record summarizes their application here.

## How to read this page

Components are grouped by their relationship to this repository:

- **Vendored:** source code is tracked and redistributed here, with its license and notices.
- **Fetched:** build declarations track a URL and integrity hash; the upstream supplies the source at configure time.
- **Submodule:** a gitlink records an upstream URL and commit. Source is obtained separately when the submodule is initialized.
- **Used, not conveyed:** a locally installed library or tool supports the build but is not distributed here.
- **Read ahead of a milestone:** a candidate is reviewed before incorporation. Any existing pin is identified separately.

**No tracked file is governed by reciprocal or non-commercial terms.** Such terms do apply to some external tools, libraries, potential build outputs, and candidates described below. Distribution obligations and restrictions on use are assessed separately.

Review the upstream's own licensing statements, including license files, source headers, manifests, packaging metadata, and README notices. A missing license file or an inconclusive hosting-service classification does not establish that no terms are stated. Record any missing redistribution notice separately from the stated grant.

Contents: [Vendored](#vendored-and-redistributed-here) · [Fetched](#fetched-at-build-time) · [Submodules](#pinned-as-submodules) · [Build dependencies](#used-by-the-build-not-conveyed) · [Milestone reviews](#read-ahead-of-a-later-milestone).

## Vendored, and redistributed here

Each component retains its upstream license file, unmodified, beside the governed code.

| Component | Version or pin | Upstream | License | License text |
| --- | --- | --- | --- | --- |
| Curated Sail model, `model/` | `8f91355e` | `riscv/sail-riscv` | `BSD-2-Clause` | [model/LICENCE](model/LICENCE) |
| Transplanted capability semantics | n/a | `CTSRD-CHERI/sail-cheri-riscv` | `BSD-2-Clause` | [model/LICENCE.cheri](model/LICENCE.cheri) |
| Transcribed capability-helper properties, `model/model/unit_tests/cap_properties.sail` | `4da8fd10` | `CTSRD-CHERI/sail-cheri-riscv-verif` | `BSD-2-Clause` | [model/LICENCE.cheri-verif](model/LICENCE.cheri-verif) |
| ELFIO | 3.12 | Serge Lamikhov-Center | `MIT` | `model/dependencies/elfio/LICENSE.txt` |
| Berkeley SoftFloat | 3e | The Regents of the University of California, John R. Hauser | `BSD-3-Clause` | `model/dependencies/softfloat/berkeley-softfloat-3/COPYING.txt` |

These licenses are permissive. Redistribution must retain the applicable notices, conditions, and disclaimers; BSD-3-Clause also restricts endorsement using the holders' or contributors' names. None requires source disclosure or restricts a field of use.

The curated model is a modified derivative: curation removes upstream features and incorporates capability semantics. Its upstream notices remain applicable, and project modifications use the same terms, as recorded in [COPYRIGHT.md](COPYRIGHT.md).

[model/LICENCE](model/LICENCE) governs the curated tree under BSD-2-Clause and excludes third-party code in `dependencies/`, where ELFIO and SoftFloat retain their own licenses. The capability-helper properties are transcribed for Sail 0.20.2 and the frozen capability widths because the upstream file does not load unchanged. Their separate notice preserves the upstream holders and funding acknowledgements. K-80 checks the tracked license paths in the table.

## Fetched at build time

The repository retains each component's license and `CMakeLists.txt` under `model/dependencies/`. `FetchContent` obtains the governed source from the upstream using a URL and verified archive hash; that source is not tracked here.

| Component | Version | Upstream | Integrity hash | License | License text |
| --- | --- | --- | --- | --- | --- |
| CLI11 | 2.7.2 | University of Cincinnati, Henry Schreiner | `SHA256` | `BSD-3-Clause` | `model/dependencies/CLI11/LICENSE` |
| Asio | 1.38.2 | Christopher M. Kohlhoff | `SHA3_256` | `BSL-1.0` | `model/dependencies/asio/LICENSE_1_0.txt` |
| jsoncons | 1.9.0 | Daniel Parker | `SHA3_256` | `BSL-1.0` | `model/dependencies/jsoncons/LICENSE` |

Hashes identify the downloaded bytes; the licenses govern their use. Dependency updates maintain these pins locally and verify them through a fresh model build. Upstream reconciliation preserves a newer local dependency pin. Asio uses its official GitHub tag archive because the SourceForge endpoint does not reliably return archive bytes.

[model/test/CMakeLists.txt](model/test/CMakeLists.txt) declares the downloadable test release. The `sail-riscv-tests` wrapper is Apache-2.0 and the `riscv-tests` sources are BSD-3-Clause; their license instruments are unchanged in the recorded release. The profile-refusal sweep downloads the corpus into the build lane and selects the declared release even if older caches exist. No test binary is tracked or distributed here.

## Pinned as submodules

The Git index contains a gitlink for each component below, with no source files beneath it. Initializing a submodule obtains its code from the upstream under that component's terms.

Dependency updates resolve the development branches in [.gitmodules](.gitmodules) to fixed commits and review the licenses at changed pins. Nested submodules retain the revisions selected by their parent upstream. Historical measurements identify the editions actually built.

The **Use** column records repository activity:

- **consumed:** a command under [tools/run.py](tools/run.py) opens the submodule's files.
- **read:** a person uses the pinned source to author the artifact identified in the Standing column; no tool opens the tree.
- **pinned to read later:** the pin reserves an edition for a future milestone.
- **pinned for a struck milestone:** the [implementation plan](docs/implementation/implementation-checklist.md) has struck the consuming milestone; the reference is retained for possible reinstatement.

The consumed rows cover all direct tool access. No proof under [proofs/](proofs/) or build under [model/](model/) directly accesses these pins. Update the Use cell when a tool begins doing so. Commands that require an uninitialized submodule report it by name.

| Submodule | Upstream | Pin | License | Standing | Use |
| --- | --- | --- | --- | --- | --- |
| `upstream/sail-riscv` | `riscv/sail-riscv` | `3243f939` | `BSD-2-Clause` | Comparison reference for the curated model. The completion log identifies the last semantic reconciliation; this pin does not replace the curated ISA. | read |
| `upstream/sail-cheri-riscv` | `CTSRD-CHERI/sail-cheri-riscv` | `bb07488d` | `BSD-2-Clause` | Capability-semantics oracle built by `run.py model oracle`. | consumed |
| `upstream/SECOMP` | `secure-compilation/SECOMP` | `5c20b839` | INRIA Non-Commercial License Agreement, over a dual-licensed subset | CompCert fork measured in a separate, unpublished local repository. No build here invokes it. | read |
| `upstream/llvm-project` | `llvm/llvm-project` | `90cebef1`, on `main` | `Apache-2.0 WITH LLVM-exception` | LLVM MC and `lld`, the untrusted assembler and linker to be adapted to the frozen dialect. | pinned to read later |
| `upstream/mocha` | `lowRISC/mocha` | `b5973217`, on `main` | `Apache-2.0` for lowRISC content; vendored subtrees have the terms below | Bring-up SoC used to author the device and tag-fabric descriptions in [the RTL delta](docs/hardware/rtl-reparameterization-delta.md) and [provenance record](rtl/synthesis-provenance.md). | read |
| `upstream/cva6-cheri` | `lowRISC/cva6-cheri` | `36a1dc5c` | `SHL-0.51` at the root; file-specific `Apache-2.0 WITH SHL-2.0` and `Apache-2.0 WITH SHL-2.1` | C-class scalar datapath adapted to the 64+1-bit profile. `run.py rtl elaborate` builds the baseline and curated configurations. | consumed |
| `upstream/axi-cheri-tagcontroller` | `Capabilities-Limited/axi_cheri_tagcontroller` | `24c6e2d8` | `SHL-0.51` | Tag-fabric survey reference. The flat-store design in the RTL delta uses CVA6-CHERI's older nested pin, identified in the provenance record. | read |
| `upstream/opentitan` | `lowRISC/opentitan` | `629146ef` | `Apache-2.0` | RoT peripheral reference. `run.py rtl elaborate` reads three primitive packages under `hw/ip` omitted by the imported core's manifest. Mocha retains its own older vendor lock. | consumed |
| `upstream/ibex` | `lowRISC/ibex` | `405c6d1d` | `Apache-2.0` | RoT functional reference. | pinned to read later |
| `upstream/cheriot-ibex` | `microsoft/cheriot-ibex` | `930feb29` | `Apache-2.0` | Conformance-methodology reference. The profile does not adopt its RV32 capability encoding. | pinned to read later |
| `upstream/cheri-compressed-cap` | `CTSRD-CHERI/cheri-compressed-cap` | `78a34ba5` | `BSD-2-Clause`; `test/FuzzedDataProvider.h` is `Apache-2.0 WITH LLVM-exception` | Library narrowed to the frozen 64+1-bit fields in the unpublished emulator repository. No build or check here uses it. | pinned for a struck milestone |
| `upstream/qemu` | `CTSRD-CHERI/qemu` | `d0bb921c`, on `qemu-cheri` | `GPL-2.0`, with the [file-specific terms](#development-tools-contained-by-use) below | Base of the unpublished fast-emulator fork; its `VERSION` is 7.0.0. Nothing here runs or vendors the fork. | pinned for a struck milestone |
| `upstream/rupicola` | `mit-plv/rupicola` | `5d37f856` | `MIT` | Relational-compilation toolkit for the GC-free lowering review, with Bedrock2 as a nested submodule. The lowering switch uses released opam packages. | pinned to read later |
| `upstream/katamaran` | `katamaran-project/katamaran` | `e8bfad6a` | `BSD-2-Clause` | Deferred separation-logic verifier using its own deep embedding rather than Sail. | pinned to read later |
| `upstream/sail-katamaran-backend` | `katamaran-project/sail-backend` | `c9b1cd02` | `BSD-2-Clause`, stated in packaging; see below | Translation backend for the Katamaran route. | pinned to read later |
| `upstream/cerise` | `logsem/cerise` | `9eb72e67` | `BSD-3-Clause`; `extra/` is `BSD-2-Clause` | Capability-machine contract and sentry-reasoning reference for the kernel milestone. | pinned to read later |
| `upstream/cerisier` | `logsem/cerisier` | `57ed584a` | `BSD-3-Clause`; `extra/` is `BSD-2-Clause` | Extension of that contract to local attestation. | pinned to read later |
| `upstream/sail-cheri-riscv-verif` | `CTSRD-CHERI/sail-cheri-riscv-verif` | `4da8fd10` | `BSD-2-Clause` | Source of [the transcribed property suite](model/model/unit_tests/cap_properties.sail), checked by `run.py model smt` at the frozen widths. No tool opens this pin; Isla is not installed. | read |
| `upstream/TestRIG` | `CTSRD-CHERI/TestRIG` | `70717956` | `BSD-2-Clause` | `LICENSE` reviewed at the pin. Its `RVFI-DII.md` informs [the local protocol codec](tools/vos/rvfi.py). The upstream engine is TestRIG's own submodule; no build here uses this pin. | read |
| `upstream/fiat-crypto` | `mit-plv/fiat-crypto` | `e6946985` | `MIT OR Apache-2.0 OR BSD-1-Clause`; this project elects `Apache-2.0` under `COPYRIGHT` | Required classical field-arithmetic generator. No recorded generation run or tracked emission satisfies the mandate yet. | pinned to read later |
| `upstream/hacl-star` | `hacl-star/hacl-star` | `504c2987` | `Apache-2.0` | Planned behavioral comparator from the F*/Low* lineage. No differential run, build, copying, or extraction occurs here. | pinned to read later |
| `upstream/libjade` | `formosa-crypto/libjade` | `755c7eaa` | `CC0-1.0 OR Apache-2.0` | Planned independent comparator from the Jasmin/EasyCrypt lineage, with the same usage limits. | pinned to read later |

### RTL license scope

The recorded RTL reviews date to 2026-08-23, except Mocha's `v0.1.1` review on 2026-08-31 and the header review below. The [Solderpad review](#the-rtl-substrate) covers the hardware-license family.

**Mocha.** The root has no `LICENSE`. Its `REUSE.toml` assigns `Apache-2.0` to `path = ["*", "doc/**"]` for lowRISC Contributors (COSMIC project); `LICENSES/` supplies the applicable texts. The separate `hw/vendor/REUSE.toml` assigns:

- CHERI-CVA6: `SHL-0.51 OR Apache-2.0 OR BSD-3-Clause`.
- Tag controller and PULP AXI, AXI-LLC, register-interface, debug, and atomics blocks: `SHL-0.51`.
- High-performance data cache: `Apache-2.0 WITH SHL-2.1`.
- Ethernet block: `MIT`.
- Vendored OpenTitan and its patches: `Apache-2.0`, credited to lowRISC Contributors.

The OpenTitan subtree, `hw/vendor/lowrisc_ip/`, supplies platform devices. Its `ip/` directory includes `rom_ctrl`, `uart`, `entropy_src`, `i2c`, `kmac`, `lc_ctrl`, the `prim` families, `rv_core_pkg`, `rv_timer`, `spi_device`, `spi_host`, and `tlul`. Its `ip_templates/` includes `alert_handler`, `clkmgr`, `gpio`, `pwrmgr`, `rstmgr`, and `rv_plic`.

The manifest does not annotate `hw/vendor/lint/` or `hw/vendor/sonata_system/`. Their waiver and DPI simulation files instead carry lowRISC copyright notices and `SPDX-License-Identifier: Apache-2.0` in each file. This review was recorded on 2026-09-03 at `ef1370c1`.

**CHERI-CVA6.** The root Solderpad v0.51 license governs files without a separate tag. Tagged files use `SHL-0.51`, `Apache-2.0 WITH SHL-2.0`, or `Apache-2.0 WITH SHL-2.1`. Each instrument permits an Apache-2.0 election, covering the complete datapath.

### Compiler and emulator references

**LLVM.** `LICENSE.TXT` states `Apache-2.0 WITH LLVM-exception`. The exception waives Apache sections 4(a), 4(b), and 4(d) for covered portions embedded in object form through compilation. The submodule remains uninitialized pending its milestone; `git submodule update --init upstream/llvm-project` obtains it.

**SECOMP.** [CompCert and SECOMP](#compcert-and-secomp) records the license decomposition. The older GitHub path, `secure-compilation/CompCert`, redirects to SECOMP and identifies the same project cited by the PriSC'23 abstract.

**Emulator references.** Both pins support a struck milestone and remain unused here. QEMU's `LICENSE` at `d0bb921c` supplies the decomposition under [development tools](#development-tools-contained-by-use).

The `cheri-compressed-cap` root notice contains the placeholder `Copyright (c) 2018 (holder)`; its developed-by text attributes the work to SRI International and the University of Cambridge Computer Laboratory. Retain that notice as supplied. Library headers state BSD-2-Clause, untagged files use the root terms, and `test/FuzzedDataProvider.h` uses `Apache-2.0 WITH LLVM-exception`. The narrowing does not use that fuzz-harness file.

### Proof and lowering references

The following reviews were recorded on 2026-08-29 at the pinned editions.

**Rupicola and Bedrock2.** Each root `LICENSE` is MIT and identifies its authors through `AUTHORS`: Rupicola, copyright 2019; Bedrock2, copyright 2017-2021. Bedrock2 is Rupicola's nested submodule. These terms permit the independent rebuilding contemplated by the lowering route.

**Katamaran and its Sail backend.** Katamaran's `LICENSE` is BSD-2-Clause, copyright 2019 Dominique Devriese, Georgy Lukyanov, Sander Huyghebaert, and Steven Keuchel, developed at the Vrije Universiteit Brussel Software Languages Lab.

The Sail backend states its terms in `default.nix`, `nanosail.nix`, and `monads.nix`. Each sets `meta.license = licenses.bsd2` for a package built from the repository; together they cover `sail_katamaran_backend`, `nanosail`, and `monads`. There is no standalone license or notice file. `dune-project` names Marius Goyet and Frederic Vogels but omits a license stanza, so generated opam files omit it too. The recorded review accepts the packaging grant as BSD-2-Clause and requires a redistribution notice using that authorship information if vendored. `sail.opam.locked` describes the separate Sail dependency and supplies no evidence for the backend's terms.

**Cerise and Cerisier.** Each root `LICENSE` states BSD-3-Clause except for `extra/`. That directory contains coqdoc theming under its own BSD-2-Clause `extra/LICENSE`, copyright 2016 Tobias Tebbi. The proof developments remain under BSD-3-Clause.

**Capability-helper properties.** The BSD-2-Clause notice credits Thomas Bauereiss, Robert Norton-Wright, Jessica Clarke, Prashanth Mundkur, and Alexander Richardson, copyright 2019-2021, with development at SRI International and the University of Cambridge Computer Laboratory. The upstream `smt` target asks a solver whether each property's negation is satisfiable; `check_properties` uses Isla. Locally, `run.py model smt` checks the [transcribed suite](model/model/unit_tests/cap_properties.sail). The separate [capability unit tests](model/model/unit_tests/test_capability.sail) provide regression checks at selected values. Isla is not installed, and no tool reads the upstream pin directly.

**Cryptography references.** Reviews on 2026-08-31 locate Fiat-Crypto's election in `COPYRIGHT`, libjade's SPDX expression in `LICENSE` with texts under `LICENSES/`, and HACL*'s Apache text in `LICENSE`. Their use and unresolved questions appear under [cryptography upstreams](#the-cryptography-upstreams).

## Used by the build, not conveyed

### GMP, linked into the golden emulator

GMP is offered as `LGPL-3.0-or-later OR GPL-2.0-or-later`. The Sail C runtime uses it for arbitrary-precision arithmetic, making `sail_riscv_sim` a Combined Work under the LGPL. The emulator is built locally for verification; no binary is distributed here.

Distributing that executable would require the applicable notices, license text, and a means for recipients to use a modified GMP. The build provides these acquisition paths:

- `model/CMakeLists.txt` uses `find_package(GMP)` by default. [The model command](tools/vos/cli/model.py) explicitly passes `-DDOWNLOAD_GMP=FALSE`, and [the Sail rig](tools/vos/sailrig.py) links `-lgmp`.
- `DOWNLOAD_GMP=ON` fetches a source tarball using a tracked SHA256 and links the resulting static `libgmp.a`. The vendored `build_simulator.sh` defaults to this path; repository tooling does not invoke it.

Both linking forms require review before binary distribution. A replaceable system library supports substitution directly; static linking requires a relinkable application form. This distribution question remains relevant to the [implementation plan](docs/implementation/implementation-checklist.md)'s reproducible bootstrap.

### The Fiat-Crypto generator's own build

Generator dependencies and generated output have separate licensing records. The historical build uses `mit-plv/fiat-crypto` at `5691ca0d`, recursively cloned outside this checkout, with `make SKIP_BEDROCK2=1 standalone-ocaml` in the `rocq-9.1.1` switch. These measurements do not describe the newer survey pin. Nested revisions are determined by that historical parent commit.

The dependency review on 2026-09-06 records:

- **rewriter:** `COPYRIGHT` offers `MIT OR Apache-2.0 OR BSD-1-Clause`, with texts in `LICENSE-MIT`, `LICENSE-APACHE`, and `LICENSE-BSD-1`; 147 compiled `.vo` objects.
- **coqprime:** `LICENSE` states LGPL version 2.1; 23 compiled objects.
- **coqutil:** `rupicola/bedrock2/deps/coqutil/LICENSE` is MIT, copyright 2018-2019 the coqutil authors; 132 compiled objects.
- **Rupicola and Bedrock2:** MIT source trees were present but not compiled under `SKIP_BEDROCK2=1`; the recorded source counts were 66 and 151 `.v` files, respectively.
- **etc/coq-scripts:** MIT, copyright 2014 Jason Gross. It compiles nothing; `etc/ensure_stack_limit.sh` runs during extraction linking.

The record treats generated C as output of the generator, without applying coqprime's license solely because the generator uses that library. Whether coqprime code survives extraction into the standalone OCaml binary remains unresolved. Review extraction before distributing such a binary; it is currently built outside the checkout and is neither tracked nor distributed here.

### Development tools, contained by use

**Rocq Stdlib.** [MemoryPlan.v](proofs/MemoryPlan.v) references separately installed `PeanoNat.Nat` theorems. The reviewed V9.2.0 edition is `8dd155bc10529814202f8f4c643e5ae6c2c88fa6`. Its [LICENSE](https://github.com/rocq-prover/stdlib/blob/8dd155bc10529814202f8f4c643e5ae6c2c88fa6/LICENSE) and [PeanoNat header](https://github.com/rocq-prover/stdlib/blob/8dd155bc10529814202f8f4c643e5ae6c2c88fa6/theories/Arith/PeanoNat.v) state LGPL version 2.1 and credit the Rocq Development Team, INRIA, CNRS, contributors, and Evgeny Makarov. The proof-switch lock fixes the installed version. Project adapters copy no upstream proof scripts, and neither Stdlib nor compiled proof objects are distributed here. Distribution of the library or a combined artifact would require review of the LGPL source, notice, and modification or relinking obligations. [The reuse record](docs/assurance/proof-reuse/foundations.md#f01-rocq-stdlib-arithmetic-integrated-by-reference) identifies theorem references and transitive assumptions.

Tools used to observe, execute, or accelerate a build do not automatically license its output. Non-commercial restrictions also govern use, even where nothing is distributed.

| Tool | License | Standing |
| --- | --- | --- |
| CHERI-QEMU fork | `GPL-2.0`, with file-specific terms below | Unpublished fast emulator for a struck milestone. Nothing here runs, embeds, links, or distributes it. |
| Verilator | `LGPL-3.0-only OR Artistic-2.0`, at the recipient's option | Elaborates and simulates RTL, pinned at **5.052**. |
| Node.js | `MIT`, with dependency notices in the upstream `LICENSE` | Runs the host-side Wasm oracle. [The runtime helper](tools/wasm-oracle/node.sh) pins its release, verifies the official archive hash, and installs it under a versioned project prefix. |
| pre-commit | `MIT` | Optional model hooks. [tools/pyproject.toml](tools/pyproject.toml) pins the runner; [tools/uv.lock](tools/uv.lock) records dependencies. |
| QuickChick | `MIT` | Gallina input generator, version **2.2.0**, in a dedicated switch. |
| Rupicola, Bedrock2, and the Bedrock2 compiler | `MIT` | Gallina lowering: Rupicola **0.0.11**, Bedrock2 and its compiler **0.0.9**. [tools/bedrock2-lowering/](tools/bedrock2-lowering/) tracks the local sources, driver, output digest, and size; emitted C remains external. |
| coqutil | `MIT` | Bedrock2 dependency, version **0.0.7**. |
| riscv-coq | `BSD-3-Clause` | Bedrock2 compiler's target ISA specification, version **0.0.6**. |
| CompCert, in the oracle's switch | INRIA Non-Commercial License Agreement, with [licensed subsets](#compcert-and-secomp) | CertiRocq dependency, version **3.18**. No tool here invokes this switch's compiler. |
| `ccache` | `GPL-3.0-or-later` | Build accelerator. |
| llama.cpp and `llama-bench` | `MIT`, with dependency terms below | External benchmark for [the inference-demand report](docs/performance/inference-demand.md), commit `427291b5`, build tag **b10816**. No gitlink, distributed artifact, or admitted runtime. |

**Verilator is pinned to a reviewed release.** The pin is **5.052**, installed by `run.py rtl install` from a release archive verified against a recorded SHA-256. It uses a versioned project prefix and leaves the distribution executable installed. The RTL tools reject other versions. Inventory measurements use this release's JSON output and expanded instance counts; earlier XML counts are not interchangeable. This repository distributes neither Verilator nor a binary built from it, and the recorded review does not apply its license to the inspected RTL or reported netlist.

**QuickChick.** Its MIT `LICENSE` credits Maxime Dénès, Catalin Hritcu, Leonidas Lampropoulos, and Zoe Paraskevopoulou, copyright 2014. `coq-quickchick.2.2.0` retains Rocq 9.1.1 because `coq-simple-io` requires Coq below 9.2. [The opam snapshots](tools/opam/README.md) fix its dependency closure, imported by [the QuickChick command](tools/vos/cli/quickchick.py) during provisioning.

**Lowering stack.** Rupicola, Bedrock2, its compiler, and coqutil use MIT at their respective `LICENSE` files. `coq-riscv.0.0.6` uses BSD-3-Clause in `LICENSE.txt`, copyright 2017-2018 MIT, where MIT names the institution. [The lowering snapshot](tools/opam/rupicola.lock) fixes OCaml 5.4.1, Rocq 9.2.0, and the compatibility packages. No `run.py` command invokes this stack. [regenerate.py](tools/bedrock2-lowering/regenerate.py) is run manually; [DIGESTS.md](tools/bedrock2-lowering/DIGESTS.md) records its output digest and size. Emitted C includes Bedrock2's load-and-store preamble and stays outside the repository.

**CompCert in the oracle switch.** CertiRocq's released metadata requires `coq-compcert >= 3.17`; the current resolution installs 3.18 from the official `AbsInt/CompCert` archive, including `ccomp`, `clightgen`, and Rocq libraries. The reviewed 3.18 `LICENSE` is byte-identical to 3.17. Proof and QuickChick switches contain no CompCert.

Opam supplies the download URL and archive hash; this repository records package versions only. No compiler source, `.wasm`, `.vo`, or vector output from that switch is tracked. The recorded use is a research and evaluation oracle; commercial use requires the separate agreement identified below.

No repository tool invokes the oracle switch's `ccomp` or `clightgen`. The `ccomp` path supplied manually to the lowering driver instead identifies the separate SECOMP compiler measured by the implementation plan. CertiRocq imports CompCert's dual-licensed `lib/`, `common/`, `export/`, selected `cfrontend/` files, and architecture `Archi.v`; its Wasm backend uses `lib/`, `common/`, and `Archi.v`. These offer `LGPL-2.1-or-later`. The installed backends, driver, and binaries outside that subset remain unused here.

**QEMU and the capability library.** QEMU's root `LICENSE` releases the emulator under GPL version 2. Untagged source permits version 2 or later; contributions to `bsd-user/`, `linux-user/`, `hw/vfio/`, and `hw/xen/xen_pt*` are version 2 only. The Tiny Code Generator is mostly BSD or MIT, with other terms on some parts. Any reinstated emulator route must retain its separate distribution policy.

The narrowed `cheri-compressed-cap` library remains separable from the QEMU integration. It is derived from the library's own upstream under BSD-2-Clause and currently resides beside the fork in the unpublished repository. No local tool builds or checks it. Its current location is a development choice; the recorded license permits later incorporation independently of QEMU.

#### Inference benchmark dependencies

The llama.cpp review on 2026-09-05 covers commit `427291b5b34cd914a31b3fd3b61a68f6184f4b9f`, build tag `b10816`, reporting `0.4.0-dev`. The `v0.4.0` release is the distinct commit `5266f24da75dc449bd56cbed7addb9c8e4a6a73e`. The root MIT license credits the ggml authors, copyright 2023-2026, and also governs `ggml/`.

The dependency review records these separate notices:

- `vendor/cpp-httplib/LICENSE`: MIT, yhirose, 2017.
- `vendor/nlohmann/json.hpp` and `licenses/LICENSE-jsonhpp`: MIT, Niels Lohmann, 2013-2025.
- `vendor/stb/stb_image.h`: MIT or public domain, Sean Barrett, 2017, stated at the file's end.
- `vendor/miniaudio/miniaudio.h`, v0.11.25: public domain or MIT No Attribution, David Reid, 2026, stated at the file's end.
- `vendor/sheredom/subprocess.h`: Unlicense, in the header.
- `vendor/hash/sha1/`: public domain in the header; `sha256/`: public domain, Igor Pavlov, in the header and `LICENSE`.
- `vendor/hash/xxhash/`: BSD-2-Clause, Yann Collet, 2012-2023, in the header and `LICENSE`; `rotate-bits/LICENSE.md`: MIT, William Casarin, 2021. The `hash.cpp` wrapper uses the root terms.
- `gguf-py/LICENSE`: MIT, Georgi Gerganov, 2023.
- `tools/ui/src/lib/vendors/`: `nerdamer-prime` is MIT, together-science, 2023; `decimal.js` is MIT, Michael Mclaughlin, 2025; `big-integer` is Unlicense.

The measured build uses the CPU backend with `GGML_NATIVE=ON`, `GGML_CPU_KLEIDIAI=OFF`, and `LLAMA_CURL=OFF`. No Arm kernel dependency is fetched, and absent OpenSSL disables cpp-httplib HTTPS. Targets are `llama-bench`, `llama-completion`, `llama-perplexity`, `llama-cli`, and `llama-gguf`, plus their libraries. The build also produces `libllama-server-impl.so`, which is not invoked. No server executable, web front end, or `gguf-py` is built or run. All source and outputs remain in the external `/root/build/` lane.

**Model weights.** `Qwen/Qwen3-4B-GGUF` at Hugging Face revision `bc640142c66e1fdd12af0bd68f40445458f3869b` uses Apache-2.0, copyright 2025 Alibaba Cloud. The 2026-09-05 review records `license: apache-2.0` in the README and a 11,544-byte `LICENSE`, SHA-256 `5de36594c10839788a8c589443a8ef9d8b8d17c65a1b5807206ae037fc36c6bd`. Official GGUF files are downloaded into the build lane and verified against the upstream tree's SHA-256 values. None is tracked or distributed. The selection review records no official GGUF for `HuggingFaceTB/SmolLM3-3B`, Qwen Research terms for `Qwen/Qwen2.5-3B-Instruct-GGUF`, and gated access for Llama 3.2.

## Read ahead of a later milestone

These reviews support future incorporation decisions in the [implementation plan](docs/implementation/implementation-checklist.md). No candidate source is vendored or fetched here. Existing RTL and cryptography references are identified in [the submodule table](#pinned-as-submodules). Review the applicable terms at the milestone that would incorporate a component.

### The RTL substrate

The scalar datapath, tag controller, bring-up SoC, and RoT references are already pinned. Vector and matrix candidates remain under advance review:

| Component | Upstream | License | Read from |
| --- | --- | --- | --- |
| Ara, V-class vector unit | `pulp-platform/ara` | `SHL-0.51`, Solderpad Hardware License v0.51 | Root `LICENSE` |
| Gemmini, M-class matrix unit | `ucb-bar/gemmini` | `BSD-3-Clause`, The Regents of the University of California | Root `LICENSE` |

The scalar review applies to `lowRISC/cva6-cheri`, whose file-specific terms are recorded above. The base `openhwgroup/cva6` project has no separate incorporation route here.

Solderpad v0.51 permits use, modification, sublicensing, and distribution, subject to license retention, modification notices, source attribution, and applicable NOTICE content. Its text expressly permits an Apache-2.0 election. Later Solderpad forms in the CHERI-CVA6 tree also permit that election.

The reviewed RTL licenses contain no reciprocal, field-of-use, or source-disclosure requirement. No CERN Open Hardware license variant is part of this plan.

### 3GPP TS 38.212 and TS 38.331

TS 38.212 supplies the LDPC base graphs and lifting sizes needed by the FEC design. TS 38.331 supplies the RRC procedures used by radio reference state machines. The provisional freeze requires the geometry review without a build prerequisite.

**Recorded terms.** Copyright belongs jointly to the 3GPP Organizational Partners: ARIB, ATIS, CCSA, ETSI, TSDSI, TTA, and TTC. The published ETSI notice restricts reproduction and utilization without written authorization. 3GPP permits in-house copies for standard development or product design; other reproduction uses require permission through its copyright process. Free download access does not itself authorize public redistribution.

**Decision: publish without normative tables.** No normative 3GPP table is tracked. FEC interfaces are authored with base-graph, lifting-size, and list-size parameters; radio state machines are authored against TS 38.331 procedures. Builders obtain the numeric inputs from their own authorized copies at composition. The register names those parameters without reproducing their values.

Whether a transcription of numeric base-graph data alone is protectable remains unresolved. The current publication policy avoids relying on an answer. Written permission could permit tracking the tables later.

**Limitation.** This tree alone cannot compose an FEC-bearing image. Each builder must obtain and review the standards, so that component's reproducible-build account depends on external material. The table-free approach supports the proof of concept; permission remains an option for the first release.

Standard-essential patent licensing is a separate product obligation under the Organizational Partners' IPR policies and FRAND terms. This copyright review does not resolve it.

### The cryptography upstreams

The cryptography milestone distinguishes generated arithmetic, authored specifications, validation vectors, and independent comparators. Initial licensing reviews were recorded on 2026-08-31; later measurements identify their dates below.

| Component | Standing taken | What it is |
| --- | --- | --- |
| Fiat-Crypto | [Pinned as a submodule](#pinned-as-submodules). Historical generator-build review at `5691ca0d`; no tracked emission or recorded generation run yet satisfies the mandate. | Required classical field arithmetic, admitted by a recorded derivation. |
| VST's `sha/` and `hmacdrbg/` | Reviewed, not acquired. The directories use BSD-2-Clause through `LICENSE` and `LICENSE-OPAM`; the project authors its own specifications. | SHA-256 and HMAC-DRBG-SHA-256 specifications, refinement proofs, and an FCF security proof. |
| FIPS 202 and NIST ACVP known-answer vectors | Reviewed at publication sources. No ACVP fetch declaration or corpus is tracked; existing vector literals are documented below. | Validation inputs for authored primitives. |
| Behavioral oracles | HACL* at `504c2987` and libjade at `755c7eaa`, [pinned as submodules](#pinned-as-submodules). No copying, extraction, or differential run here. | Comparators from independent verification lineages. |

#### Fiat-Crypto

The register requires each field-arithmetic implementation to trace to a Fiat-Crypto derivation. A generation record must identify the pinned input and emitted artifact; a pin or unexplained output alone does not satisfy that requirement. The generator has been built, but no qualifying generation run or tracked emission exists.

`COPYRIGHT` offers `MIT OR Apache-2.0 OR BSD-1-Clause`, with full texts in `LICENSE-MIT`, `LICENSE-APACHE`, and `LICENSE-BSD-1`; there is no root `LICENSE`. This project elects Apache-2.0, including its express patent grant. The other upstream options remain available for a later use. [The generator-build record](#the-fiat-crypto-generators-own-build) covers its dependencies separately.

#### VST

The review at `f384d2db` identifies BSD-2-Clause coverage for the VST opam distribution and test suite, including `sha/`, `hmacdrbg/`, and `hmacfcf/`. `LICENSE-OPAM` credits Andrew W. Appel et alia, copyright 2007-2022. Hub submodules such as FCF, Interaction Trees, and Paco retain their own licenses and are outside that distribution. The repository also contains `compcert/` and `compcert_new/`; the latter includes files outside CompCert's dual-licensed subset.

The package route has two practical limits:

- It still installs CompCert. At the reviewed source commit, `coq-vst.opam` requires `coq-compcert >= 3.15` and `< 3.17~`, incompatible with the current oracle resolution.
- It does not install the selected cryptographic developments. The `vst` target builds `msl veric floyd simpleconc`; installation selects `veric`, `floyd`, and `progs`. The `sha`, `hmacdrbg`, and `hmacfcf` developments belong to `make test3` and are not installed.

**Decision: author the specifications.** [Sha256.v](proofs/Sha256.v) and [HmacDrbg.v](proofs/HmacDrbg.v) follow FIPS 180-4, FIPS 198-1, and SP 800-90A, as [Keccak.v](proofs/Keccak.v) follows FIPS 202. No VST material is installed, pinned, copied, or quoted here.

The decision records independent compatibility and proof-assumption findings:

- On 2026-09-06, `opam install coq-vst --dry-run --show-actions` in `rocq-9.1.1` selected `coq-vst` 3.1beta, whose Coq range is `>= 8.19` and `< 8.21~`. It proposed removing Rocq core/runtime 9.1.1, Stdlib 9.2.0, Sail stdpp 0.20.2, and stdpp/bitvector 1.13.0, and installing Coq core/stdlib 8.20.1 with CompCert 3.18. A separate compatible switch avoids replacing the prover but retains CompCert's usage terms.
- VST's `msl/Axioms.v` declares dependent functional extensionality and propositional extensionality and re-exports `Stdlib.Logic.FunctionalExtensionality`. CompCert `v3.16`'s `lib/Axioms.v` declares proof irrelevance. Both files were reviewed on 2026-09-06. [The proof gate](tools/vos/cli/proofs.py), under R-05-164, currently accepts no undeclared assumptions; developments depending on these axioms fail it.

Authored specifications do not replace VST's refinement proof to C or the `hmacfcf/` security reduction required by R-05-077a. Both remain outstanding.

#### Validation vectors and quoted literals

**NIST ACVP.** `usnistgov/ACVP-Server` at `975de31e` states its terms in `README.md`, with no standalone license file. Its notice permits use, copying, modification, and distribution, subject to retaining the full notice, identifying the date and nature of changes, and acknowledging NIST. It states no field-of-use or non-commercial restriction.

The corpus is under `gen-val/json-files/`; a reviewed set is approximately 110 MB. No build fetches it yet. The consuming milestone must supply a pinned URL, integrity hash, and retained notice before adding it to [the fetched inventory](#fetched-at-build-time).

**FIPS 202.** [Keccak.v](proofs/Keccak.v) records known answers and intermediate values from `XKCP/XKCP` at `eb5244d6`, reviewed on 2026-08-31 under `tests/TestVectors/`. [The XKCP review](#xkcp) below records the scope question for those literals. The NIST genKAT harness's authorship does not establish terms for its output.

[The Sail Keccak unit tests](model/model/unit_tests/test_keccak.sail) use an independent FIPS 202 implementation cross-checked against standard-library SHA-3, plus the Keccak team's published all-zero permutation answer. They do not copy the pinned XKCP files.

**Classical validation archives.** [Sha256.v](proofs/Sha256.v), [HmacDrbg.v](proofs/HmacDrbg.v), and [RomVerifier.v](proofs/RomVerifier.v) identify the sources of their quoted answers and parameters. The 2026-09-05 acquisition record covers:

- `shabytetestvectors.zip`: `SHA256ShortMsg.rsp` and `SHA256LongMsg.rsp`, CAVS 11.0, generated 2011-03-15.
- `hmactestvectors.zip`: `HMAC.rsp`, CAVS 11.0, generated 2011-02-28.
- `drbgtestvectors.zip`: `HMAC_DRBG.rsp` in `drbgvectors_no_reseed`, `drbgvectors_pr_false`, and `drbgvectors_pr_true`, CAVS 14.3, generated 2013-04-02.
- NIST's `SHA256.pdf` example and FIPS 205, `NIST.FIPS.205.pdf`.

The archives are published beneath `csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/` in `shs/`, `mac/`, and `drbg/`; the SHA-256 example is under the Cryptographic Standards and Guidelines examples directory. FIPS 205 is published at `nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.205.pdf`.

The review of `nist.gov/oism/copyrights` on 2026-09-06 identifies separate software, data, and information notices. The software notice includes retention, modification, and attribution conditions and states that NIST employee software is not copyright-protected in the United States. The data notice supplies a warranty disclaimer; the information notice requests byline credit. Which applies to CAVS-generated `.rsp` files remains unresolved. The source files identify each archive, its CAVS header, and NIST; quoted answers are unmodified. No archive, document, or `.rsp` file is tracked.

RFC 4231's HMAC-SHA-256 cases have separate provenance: `rfc-editor.org/rfc/rfc4231.txt`, reviewed on 2026-09-05, copyright 2005 The Internet Society, subject to BCP 78. NIST's notices do not govern those cases.

#### Behavioral oracles

HACL* uses unmodified Apache-2.0 terms and the F*/Low* verification lineage. Libjade states `CC0-1.0 OR Apache-2.0` in `LICENSE`, with texts under `LICENSES/`, and uses Jasmin/EasyCrypt. Their pins reserve reproducible comparator editions. No command builds them or computes a differential result, and no artifact is copied, vendored, or extracted from either.

The comparator role does not supply a proof assumption or enter the trust base. A later import of a HACL* post-quantum primitive is a separate act governed by R-05-061 and M3.4b. R-05-022 identifies that interim F*/Z3 dependence alongside EasyCrypt's Why3/SMT and Cranelift/Crocus's SMT; R-05-022a requires progress toward the named destination as consumers grow. The aiT and Binsec/Rel exceptions do not extend to HACL*. R-05-109 and R-05-073 distinguish a comparator from an artifact on which a proof depends. Libjade has no corresponding interim entry.

The plan's exclusion of a Jasmin ML-KEM candidate for unstated licensing does not identify the licensed libjade tree. The candidate's identity remains unresolved by this review. That exclusion and the NTT deposit's assessment require review of all first-party licensing statements, including packaging, before treating the absence of a license file as decisive.

#### XKCP

XKCP is not acquired as a comparator. Its `LICENSE` at `eb5244d6` assigns different terms to different material:

- Most source and header files: CC0.
- `lib/common/brg_endian.h`: Gladman BSD notice.
- AVX2 and AVX512 Keccak assembly: CRYPTOGAMS, BSD-3-Clause or GPL.
- AArch64 assembly: Apache-2.0, ISC, or MIT.
- `Standalone/CompactFIPS202/C/genKAT.c` and unit-test genKAT sources: NIST BSD-3-Clause.
- `tests/Benchmarks/timing.h`: Apache-2.0, Google copyright.

Only published answers from `tests/TestVectors/` are quoted in [Keccak.v](proofs/Keccak.v). The directory is not named in the exceptions, but the default CC0 sentence expressly covers source and header files. Its application to vector text files remains unresolved. No license is inferred from the nearby harness or the separate ACVP repository, and the current record assigns no additional notice obligation to these literals.

### The interface-definition start-froms

The [typed IDL profile](docs/languages/idl-profile.md) uses these references for the interface layer in register section 12. Reviews were recorded on 2026-08-31. Neither source, fetch declaration, nor gitlink is tracked.

| Component | Upstream | License | Read from |
| --- | --- | --- | --- |
| WIT, type-layer syntax reference | `WebAssembly/component-model` | `Apache-2.0` | Root `LICENSE` pointer and `LICENSE-APACHE` |
| FIDL and Zircon channel, wire-layer reference | `fuchsia.googlesource.com/fuchsia` | `BSD-2-Clause` | Root `LICENSE` |

The Component Model's root `LICENSE` assigns Apache-2.0 unless a subdirectory states otherwise. The review finds no such exception. `LICENSE-APACHE` is the standard text with an unfilled copyright appendix; the hosting service's `NOASSERTION` classification does not alter it. The terms cover `design/mvp/WIT.md`.

Fuchsia's root license is BSD-2-Clause, copyright 2019 The Fuchsia Authors, with no endorsement clause. The review confirms the same text through the raw and rendered file views.

Both licenses are permissive. The profile adopts constructor names and meanings from WIT but copies no upstream text, grammar, or generated artifact. Wire-layer decisions are technical:

- WIT's Canonical ABI assumes Core WebAssembly linear memory. R-05-085 excludes Wasm as a system execution target, and local authority is represented by session-table indices.
- FIDL's bytes-plus-out-of-band-handles model informs profile sections 2, 3.3, and 4. Its unverified C++ codecs are not adopted; local marshalling uses generated Narcissus copy-once verified parsers.

The wire mapping is authored locally. Neither reference has a recorded commit; the profile therefore identifies a dated reading rather than a reproducible source pin. The Component Model provides no release or document version to substitute.

### Non-permissive upstreams, and the calls taken on them

No source from these components is tracked here. The [implementation plan](docs/implementation/implementation-checklist.md) records the following incorporation decisions:

| Upstream | Milestone | Terms | The call |
| --- | --- | --- | --- |
| CompCert through `upstream/SECOMP` | M1.1a, compiler | INRIA Non-Commercial License Agreement, with dual-licensed subsets and reciprocal distribution conditions | **Contained:** external build-time producer, not distributed here. |
| Vélus, `INRIA/velus` | M6.0a, control-plane compiler | Inria Non-Commercial License Agreement for Vélus, with reciprocal distribution conditions | **Contained:** external build-time producer, not distributed here. |
| seL4 `spec/` and `proof/` | M4.1a, kernel specification | `GPL-2.0-only`; `lib/` and `tools/` are `BSD-2-Clause` | **Declined:** Gallina objects are authored from the design. |

CompCert and Vélus have separate grants despite their agreements' similar form. Keeping a producer external addresses distribution; it does not remove restrictions on use.

#### CompCert and SECOMP

The pinned `upstream/SECOMP/LICENSE` places the verified compiler under the INRIA Non-Commercial License Agreement. The grant is revocable, nonexclusive, nontransferable, and royalty-free, limited to educational, research, or evaluation purposes. Commercial use requires a separate AbsInt Software Usage Agreement.

The license assigns these additional terms:

- **LGPL-2.1-or-later option:** `lib/`, `common/`, specified `cfrontend/` files, `backend/Cminor.v`, `backend/PrintCminor.ml`, `cparser/`, `export/`, specified architecture files, `extraction/extraction.v`, and build files. The license enumerates the covered files.
- **LGPL-3.0-or-later:** `flocq/` and `MenhirLib/`.
- **BSD-3-Clause:** `runtime/`.

Section 4 requires distribution of the software or derivatives under the same terms without granting additional rights. This repository distributes none of that software.

The verified backend passes, RISC-V backend, and SECOMP `cheririscV/` backend are outside the dual-licensed subset. M1.1b's subsequent route uses the RISC-V backend; `cheririscV/` remains a reading reference. Commercial rights to SECOMP's own contribution may require an agreement with its rightsholders separately from rights to CompCert.

VST also contains CompCert material. Its `compcert/` tree provides dual-licensed Clight material, while `compcert_new/` contains files without that option. Using opam avoids incorporating those directories into this repository, but still installs CompCert and requires review of its usage terms, as documented [above](#vst).

#### Vélus

`INRIA/velus/LICENSE` is the Inria Non-Commercial License Agreement for the Vélus verified Lustre compiler. Vélus also includes a modified CompCert as its own submodule. The recorded clauses are:

- **Section 2:** revocable, nonexclusive, nontransferable, royalty-free worldwide use for educational, research, or evaluation purposes; derivative works are limited to academic, non-commercial research. The definition includes modifications, enhancements, and works derived from or based on the software.
- **Section 3:** use connected with commercial gain for the user or others is excluded. This restriction applies to each use, regardless of the project's general purpose.
- **Section 4:** distributed software and derivatives must retain the same terms; additional rights cannot be granted.
- **Section 7:** noncompliance immediately terminates the license without notice and requires discontinuing use and returning or destroying copies.

CompCert agreements do not extend to Vélus. Any commercial route must address both grants separately. If the project instead authors the control-plane compiler, the plan's existing Gallina state-machine reference model provides a starting point.

#### seL4

The seL4 proof repository assigns `GPL-2.0-only` to `spec/` and `proof/`, and `BSD-2-Clause` to `lib/` and `tools/`. The executable-specification objects considered for translation are in the GPL-covered directories. Translating them into Gallina would not remove their derivative-work obligations.

The recorded decision declines that route because GPL-2.0-only material cannot be redistributed under the project's Apache-2.0 terms. The seL4 syscall exception concerns user code invoking the kernel; it does not cover code derived from the kernel specification. The project therefore authors its Gallina kernel objects from the design.

### The Coq hardware DSLs

The later RTL route considers **Kami (MIT)** and **Kôika (LGPL-2.1)**. Authoring Coq modules that import an LGPL hardware library raises a licensing question for the design itself, beyond the external-tool cases above.

Kôika's repository supplies the LGPL-2.1 text without per-file notices resolving `LGPL-2.1-only` versus `LGPL-2.1-or-later`. That scope remains unresolved. The [implementation plan](docs/implementation/implementation-checklist.md) records the required preference review when this route opens after the co-simulation gate.

### Start-froms read and declined

The 2026-08-29 review records these references without adding gitlinks:

**StkTokens.** The register adopts its linear and affine stack discipline as a design reference. The POPL 2019 technical report supplies proofs and detail but no published Coq mechanization to pin. `logsem/cerise-stack` concerns uninitialized-capability revocation and is not a named milestone input. No artifact is copied.

**CHERI Alliance Sail.** `CHERI-Alliance/sail-cheri-riscv` was archived in April 2025; its README directs readers to the organization's `sail-riscv` branch. The archived `LICENCE` is BSD-2-Clause, copyright 2017-2023 the CHERI-RISC-V Sail authors, Google, and Microsoft. [The version matrix](docs/hardware/cheri-version-matrix.md) treats this line as external evidence for a conditional RVY review. The required `make riscv_coq_build` target and property-repository reference are already documented by the pinned oracle, so this route requires no additional pin.

**Rocq-native NTT.** The February 2026 Zenodo deposit supplies a README and an archive containing a patch and source directory for commit `af03839247c545987c20e99342ab2bbfcd517863` of `mit-plv/fiat-crypto`. The deposit, README, and record state no license. Its author's personal fork has older NTT branches under Fiat-Crypto's `MIT OR Apache-2.0 OR BSD-1-Clause` election, but their relationship to the published artifact and the grant's scope over contributed files remain unresolved. The project reads the artifact without pinning, copying, vendoring, or extracting it. The broader review of first-party licensing statements remains due as recorded [above](#behavioral-oracles).
