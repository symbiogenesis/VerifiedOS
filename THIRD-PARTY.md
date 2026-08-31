# Third-Party Components

*Every component in this repository that somebody else wrote, and the terms it arrives under. [COPYRIGHT.md](COPYRIGHT.md) carries the same map for this repository's own content.*

## How to read this page

Nearly every obligation in these licenses is conditioned on **conveyance**, so components are grouped by what this repository does with each one.

- **Vendored.** The code is tracked here, so this repository redistributes it and discharges its notice obligations on this page. This is the only group that is redistribution by this repository.
- **Fetched.** A URL and an integrity hash are tracked; the code is not. The upstream conveys the source at configure time.
- **Submodule.** A URL and a commit hash are tracked; the code is not. The upstream conveys the source to whoever initializes the gitlink.
- **Used, not conveyed.** Libraries and tools a build links, runs, or accelerates without this repository shipping them.
- **Read ahead of a milestone.** Nothing is tracked at all. A later milestone would incorporate the upstream, and reading its terms early is free and commits nothing.

**No file tracked in this repository is governed by a reciprocal or a non-commercial term.** The reciprocal and non-commercial terms that appear on this page attach to build outputs and to upstreams not yet incorporated, and each is stated where it appears.

Contents: [Vendored](#vendored-and-redistributed-here) · [Fetched](#fetched-at-build-time) · [Submodules](#pinned-as-submodules) · [Used by the build](#used-by-the-build-not-conveyed) · [Read ahead](#read-ahead-of-a-later-milestone).

## Vendored, and redistributed here

Each component keeps its own license file in place, unmodified, beside the code it governs.

| Component | Version or pin | Upstream | License | License text |
| --- | --- | --- | --- | --- |
| The curated Sail model, `model/` | `8f91355e` | `riscv/sail-riscv` | `BSD-2-Clause` | [model/LICENCE](model/LICENCE) |
| The transplanted capability semantics | n/a | `CTSRD-CHERI/sail-cheri-riscv` | `BSD-2-Clause` | [model/LICENCE.cheri](model/LICENCE.cheri) |
| ELFIO | 3.12 | Serge Lamikhov-Center | `MIT` | `model/dependencies/elfio/LICENSE.txt` |
| Berkeley SoftFloat | 3e | The Regents of the University of California, John R. Hauser | `BSD-3-Clause` | `model/dependencies/softfloat/berkeley-softfloat-3/COPYING.txt` |

Every license in that table is permissive and non-reciprocal. Each conditions redistribution on nothing more than retention of a copyright notice and a warranty disclaimer. None carries a reciprocal obligation, a field-of-use restriction, or a source-disclosure condition, which is why the licenses in [COPYRIGHT.md](COPYRIGHT.md) are available to choose at all.

**The curated model is a modified derivative rather than a copy.** Batches under the plan's hardware-reference milestone delete most of the upstream surface and transplant the capability layer into what remains. The upstream notice governs the result whole, and [COPYRIGHT.md](COPYRIGHT.md) records that modifications made here are offered back on the same terms.

**No row above falls outside [model/LICENCE](model/LICENCE)'s own scheme.** It places every file under BSD-2-Clause *except* the third-party dependencies in the `dependencies` directory, the first two rows are the curated tree that licence governs directly, and the other two are third-party code living exactly in the directory it carves out, each beside the licence file naming its terms. Nothing here states its terms in a source-file header instead of a licence file, which is why the License-text column locates a tracked path in every row and why K-80 can hold it.

## Fetched at build time

Each of these keeps a license file and a `CMakeLists.txt` under `model/dependencies/` and none of the governed code. Each is a `FetchContent` declaration naming an upstream URL and an integrity hash, so the source is conveyed by its own upstream at configure time and at no point by this repository.

| Component | Version | Upstream | Integrity hash | License | License text |
| --- | --- | --- | --- | --- | --- |
| CLI11 | 2.6.2 | University of Cincinnati, Henry Schreiner | `SHA256` | `BSD-3-Clause` | `model/dependencies/CLI11/LICENSE` |
| Asio | 1.36.0 | Christopher M. Kohlhoff | `SHA3_256` | `BSL-1.0` | `model/dependencies/asio/LICENSE_1_0.txt` |
| jsoncons | 1.8.1 | Daniel Parker | `SHA3_256` | `BSL-1.0` | `model/dependencies/jsoncons/LICENSE` |

The hash is an integrity control and not a license mechanism: it fixes *which* bytes arrive, and the terms above govern them once they do. The license files are retained here so that the terms are legible before a build is configured rather than after.

Versions are the curated tree's to follow rather than this repository's to choose. Each is upstream `sail-riscv`'s dependency, arriving through the curation, so a local bump is divergence that every later reconciliation has to carry; drift here is read as a signal about reconciliation cadence rather than as a repair owed.

## Pinned as submodules

These are gitlink entries. This repository carries a URL and a commit hash for each and none of the code, so their terms bind a clone that fetches them rather than this tree.

| Submodule | Upstream | Pin | License | Standing |
| --- | --- | --- | --- | --- |
| `upstream/sail-riscv` | `riscv/sail-riscv` | `ac2a5855` | `BSD-2-Clause` | The edition the curation is reconciled against. |
| `upstream/sail-cheri-riscv` | `CTSRD-CHERI/sail-cheri-riscv` | `bb07488d` | `BSD-2-Clause` | The capability-semantics oracle. |
| `upstream/SECOMP` | `secure-compilation/SECOMP` | `5c20b839` | INRIA Non-Commercial License Agreement, over a dual-licensed subset | A CompCert fork, and the one pin whose terms are not permissive. |
| `upstream/llvm-project` | `llvm/llvm-project` | `ca7933e4`, tagged `llvmorg-22.1.8` | `Apache-2.0 WITH LLVM-exception` | The untrusted assembler and linker the compiler milestone re-homes to the frozen dialect: LLVM's MC layer and `lld`. |
| `upstream/mocha` | `lowRISC/mocha` | `ef1370c1`, named by tag `v0.1.1` | `Apache-2.0` for lowRISC's own content; each vendored subtree carries its own terms, below | The bring-up SoC, and the integration the scalar-RTL milestone reads its device list and its tag-carrying fabric from. |
| `upstream/cva6-cheri` | `lowRISC/cva6-cheri` | `36a1dc5c` | `SHL-0.51` at the root, with `Apache-2.0 WITH SHL-2.0` and `Apache-2.0 WITH SHL-2.1` on files that carry their own tag | The CHERI-CVA6 datapath itself: the C-class scalar front end the profile re-parameterizes to the 64+1-bit dialect. |
| `upstream/axi-cheri-tagcontroller` | `Capabilities-Limited/axi_cheri_tagcontroller` | `173646d5` | `SHL-0.51` | The functional reference for the tag-carrying fabric: tags on the bus user bits, held in a memory block of their own. |
| `upstream/opentitan` | `lowRISC/opentitan` | `bf4a2b24` | `Apache-2.0` | The RoT peripherals, at the revision the bring-up SoC vendors rather than at the upstream's own tip. |
| `upstream/ibex` | `lowRISC/ibex` | `8b8ee086` | `Apache-2.0` | The RoT functional reference. |
| `upstream/cheriot-ibex` | `microsoft/cheriot-ibex` | `930feb29` | `Apache-2.0` | The CHERI-on-Ibex reference, whose separate RV32 capability encoding this profile declines while taking its conformance methodology. |
| `upstream/cheri-compressed-cap` | `CTSRD-CHERI/cheri-compressed-cap` | `78a34ba5` | `BSD-2-Clause` at the root and on every library header; one `test/` file is `Apache-2.0 WITH LLVM-exception` | The compressed-capability library the fast-emulator milestone narrows to the frozen 64+1-bit fields. |
| `upstream/qemu` | `CTSRD-CHERI/qemu` | `d0bb921c`, the tip of its own default branch `qemu-cheri` | `GPL-2.0`, decomposed under [development tools](#development-tools-contained-by-use) | The edition the fast emulator's fork is cut from, carrying `VERSION` 7.0.0. The fork is a separate repository and none of it is vendored here; the gitlink fixes which tree that fork answers to. |
| `upstream/rupicola` | `mit-plv/rupicola` | `b5894db6` | `MIT` | The relational-compilation toolkit the GC-free lowering route is re-priced against, carrying Bedrock2 as a submodule of its own. |
| `upstream/katamaran` | `katamaran-project/katamaran` | `50d2c62c` | `BSD-2-Clause` | The separation-logic verifier the deferred program logic discharges its per-instruction obligations with, over its own deep embedding rather than over Sail. |
| `upstream/sail-katamaran-backend` | `katamaran-project/sail-backend` | `c9b1cd02` | none: the repository states no terms anywhere | The translation that route owes, automated. The one pin on this page with no grant of any kind, read below. |
| `upstream/cerise` | `logsem/cerise` | `9eb72e67` | `BSD-3-Clause`, with `extra/` carved out and covered below | The universal contract for a capability machine, and the sentry reasoning the kernel milestone cites the lineage of. |
| `upstream/cerisier` | `logsem/cerisier` | `57ed584a` | `BSD-3-Clause`, on the same carve-out | That contract extended to local attestation, which is the measured-boot half of the same citation. |
| `upstream/sail-cheri-riscv-verif` | `CTSRD-CHERI/sail-cheri-riscv-verif` | `4da8fd10` | `BSD-2-Clause` | The capability-helper properties of the transplanted semantics, checked over the whole input space by an SMT solver rather than at chosen values. |
| `upstream/TestRIG` | `CTSRD-CHERI/TestRIG` | `70717956` | `BSD-2-Clause` | The RVFI-DII protocol's own specification and the harness around it, read at `LICENSE` at the pin. The engine it drives is a submodule of *its* tree and not a gitlink here; nothing in this repository builds from this pin. |

**The RTL pins' terms are each read from the file at the pin, and every one is permissive.** Six of the seven are dated 2026-08-23 and the bring-up SoC's, taken at `v0.1.1`, is dated 2026-08-31. Three of them are hardware licenses, a family read in full under [the RTL substrate](#the-rtl-substrate) below. Two of the seven readings do not resolve at a single file, and both are recorded here rather than smoothed over.

**Mocha declares its terms in a manifest rather than in a license file, and the manifest governs its own content only.** There is no `LICENSE` at the repository root. `REUSE.toml` at the pin annotates `path = ["*", "doc/**"]` as `Apache-2.0` for *lowRISC Contributors (COSMIC project)*, and `LICENSES/` carries the full text of that and of six further instruments the tree needs. The tree those six serve is `hw/vendor/`, whose own `REUSE.toml` annotates the vendored subtrees separately: the CHERI-CVA6 core as `SHL-0.51 OR Apache-2.0 OR BSD-3-Clause`, the tag controller and the PULP AXI, AXI-LLC, register-interface, debug and atomics blocks as `SHL-0.51`, the high-performance data cache as `Apache-2.0 WITH SHL-2.1`, and the Ethernet block as `MIT`. So *Mocha is Apache-2.0* is true of what lowRISC wrote and false of a third of what the repository ships, and a reading that stopped at the announcement would have carried the wrong instrument onto four of the blocks the scalar milestone actually wants.

**The CHERI-CVA6 tree carries three instruments and no file falls outside them.** `LICENSE` at the root is Solderpad v0.51 and governs the files that carry no tag of their own, which is most of `core/`. Of the tagged files, thirty-five carry `Apache-2.0 WITH SHL-2.0` and twelve carry `Apache-2.0 WITH SHL-2.1`, both being Solderpad's later wraparound form, and two carry `SHL-0.51` explicitly. All three permit the licensee to elect Apache-2.0: v0.51 in its preamble, and v2.0 and v2.1 in their opening paragraph, which reads *"You may, at your option, choose to treat any Work released under this license as released under the Apache License."* The election is available at every file in the tree, so the whole datapath can be taken under the license this repository's own content already carries.

**LLVM's terms were read from `LICENSE.TXT` at the pin.** They are permissive, with no copyleft term and no non-commercial restriction, and the exception waives the notice conditions of Apache §4(a), (b) and (d) for portions embedded in object form by compilation, which is the case a compiler's runtime pieces raise. The gitlink is deliberately unpopulated, that milestone not having started; `git submodule update --init upstream/llvm-project` fetches it when it does.

**SECOMP's terms are decomposed under [CompCert and SECOMP](#compcert-and-secomp)**, beside the other upstreams whose terms are not permissive. The project is renamed on GitHub and the older `secure-compilation/CompCert` path redirects here, so the PriSC'23 abstract's link and this row name one repository.

**The two emulator pins were read at the pin, and one of the two readings is finer than the page previously carried.** QEMU's `LICENSE` at `d0bb921c` is word for word the decomposition [below](#development-tools-contained-by-use) already states, so that read now stands against an edition rather than against a project. `cheri-compressed-cap`'s root file is `BSD-2-Clause` and two details of it are carried rather than smoothed. Its copyright line is the literal placeholder `Copyright (c) 2018 (holder)`, never filled in, so the attribution to SRI International and the University of Cambridge Computer Laboratory rests on the notice's own developed-by sentences and not on a holder field; nothing in the grant turns on that, every condition of `BSD-2-Clause` attaching to the notice text that is present. And the root file is not the whole tree: every library header carries its own `BSD-2-Clause` tag, forty-three files under `test/` and the build carry no tag at all and fall to the root, and one of those, `test/FuzzedDataProvider.h`, is LLVM's under `Apache-2.0 WITH LLVM-exception`. The single non-`BSD-2-Clause` file is in the fuzz harness, which is not material the narrowing takes, so the decomposition changes nothing about the disposition and is recorded because *the project is BSD-2-Clause* is the shape of claim this page has already had to correct once.

**The six start-from pins were read at the file at each pin, on 2026-08-29, and one of them has no file to read.** They are the upstreams the [implementation plan](docs/implementation-checklist.md)'s opening reading disposes: the lowering route the compiler milestone is re-priced against, the program logic the deferred verification section owes, the capability-machine contract the kernel milestone cites the lineage of, and the properties of the capability helpers the curated model transplanted. Each is a gitlink and no file beneath any of them is tracked here, so pinning them commits this repository to nothing beyond fixing the edition each reading was taken at.

**Rupicola is `MIT`, and so is the Bedrock2 it emits into.** The `LICENSE` at the pin is the ordinary instrument under "Copyright (c) 2019 the rupicola authors (see the AUTHORS file)", granting permission "to deal in the Software without restriction" against retention of the notice. Bedrock2 is not a row above because it is Rupicola's own submodule rather than this repository's, and its `LICENSE` is the same instrument under "Copyright (c) 2017-2021 the bedrock2 authors (see the AUTHORS file)". Neither carries a reciprocal term, which is what the lowering route's claim that a component built this way is third-party-rebuildable stands on, and it is the one route on the plan that partially repairs a containment forfeit rather than spending one.

**Katamaran is `BSD-2-Clause` and the tool that feeds it states no terms at all.** The verifier's `LICENSE` at the pin is the two-clause instrument under "Copyright (c) 2019 Dominique Devriese, Georgy Lukyanov, Sander Huyghebaert, Steven Keuchel", developed at the Vrije Universiteit Brussel Software Languages Lab. **`katamaran-project/sail-backend` is the finding of this reading.** Its root carries a README, a Makefile, nix and dune files and three opam files, and no `LICENSE`, `LICENCE`, `COPYING` or `COPYRIGHT`; the forge reports its licence as null; and neither the backend's opam file, which describes itself as the Sail to microSail translation, nor the intermediate-representation package's beside it carries a `license:` field. So the one tool that automates the translation the register books as owed is published with no grant of any kind, from a project whose verifier half is permissive. It may be pinned and read; it may not be copied, vendored, or extracted from, and whether what it *emits* may be carried is a question no file in it answers. That is the disposition the cryptography milestone already reached for a Jasmin artifact, met here on a tool rather than on a library, and the pin records the edition rather than admitting the tool.

**Cerise and Cerisier state one licence with one carve-out, and the carve-out resolves.** Each `LICENSE` opens "All files in this development, excluding those in extra/, are distributed under the terms of the 3-clause BSD license", so the file names a directory it declines to govern and says nothing about what does. `extra/` holds the coqdoc theming rather than any proof, and its own `extra/LICENSE` is `BSD-2-Clause` under "Copyright (c) 2016 Tobias Tebbi". Both trees are therefore permissive whole, the third clause adding only that the copyright holder's and contributors' names may not "be used to endorse or promote products derived from this software without specific prior written permission", which is a naming restriction rather than a condition on the work.

**The capability-helper properties are `BSD-2-Clause`, and what they buy is a quantifier.** `sail-cheri-riscv-verif`'s `LICENSE` at the pin is the two-clause instrument under "Copyright (c) 2019-2021 Thomas Bauereiss, Robert Norton-Wright, Jessica Clarke, Prashanth Mundkur, Alexander Richardson", developed by SRI International and the University of Cambridge Computer Laboratory. Its `smt` target emits one SMT-LIB file per property and asks the solver whether the negation is satisfiable, and its `check_properties` target puts the same questions through Isla. That is what separates it from the curated model's own `$[test]` functions, which assert at chosen values and which [the capability unit tests](model/model/unit_tests/test_capability.sail) already say are the format's standing regression rather than its proof.

## Used by the build, not conveyed

### GMP, linked into the golden emulator

`model/CMakeLists.txt` calls `find_package(GMP)`, and GMP is offered as `LGPL-3.0-or-later OR GPL-2.0-or-later`. The Sail C runtime links it for arbitrary-precision arithmetic, which makes a built `sail_riscv_sim` a Combined Work in the LGPL's sense. It is the one reciprocal term that attaches to a build output without reaching a tracked file, so the claim at the top of this page is accurate as to the tree and is not the whole account.

No condition of that license is presently triggered, because every one of them attaches to *conveying* the Combined Work and this repository conveys no binary: the golden-model emulator is built locally as a verification instrument. Conveying one to a third party would engage the Combined Work conditions, of which the substantive one is the recipient's right to relink the executable against a modified GMP, alongside notice and a copy of the license. That is a condition on the shipping act, recorded here because the reproducible-bootstrap story in the [implementation plan](docs/implementation-checklist.md) contemplates exactly that act.

### Development tools, contained by use

Reciprocity under these licenses runs to derivative and combined works rather than to whatever a program is used to produce. Each tool below observes, accelerates, or executes a build without entering the work the build emits, so its terms reach nothing this repository conveys.

| Tool | License | Standing |
| --- | --- | --- |
| The CHERI-QEMU fork, the fast emulator | `GPL-2.0`, with the particulars below | A development instrument, maintained in a separate repository. No conveyed image links against it or embeds it. |
| Verilator | `LGPL-3.0 OR Artistic-2.0`, at the recipient's option | Elaborates and simulates RTL, pinned at **5.032**. |
| QuickChick | `MIT` | Generates the inputs the Gallina front is exercised on, at **2.2.0** in a switch of its own. |
| `ccache` | `GPL-3.0-or-later` | Accelerates a build. |

**Verilator is pinned and its terms reach nothing it elaborates.** The pin is **5.032**, the version Ubuntu 26.04 packages, which is what keeps the RTL lane reproducible without a source build; a version other than the pin is a finding rather than a warning, as it is for the two type checkers and the prover. The bring-up SoC this lane's imported sources come from pins **5.040** through nix, and that difference is recorded rather than chased, nothing here running the reference's own flow. Reciprocity under the LGPL runs to derivative and combined works, and an elaborator's output is neither: a netlist Verilator reports on is the input's, not Verilator's, and no conveyed artifact links against it. The Artistic arm is available at the recipient's option in any case, and this repository conveys no Verilator and no binary built from one.

**QuickChick's terms are read at its own `LICENSE` and its switch is its own.** The file says *The MIT License (aka Expat License)*, copyright 2014 Maxime Dénès, Catalin Hritcu, Leonidas Lampropoulos and Zoe Paraskevopoulou; permissive on every arm, so nothing it generates and nothing it is linked into carries a reciprocal term. It is installed as `coq-quickchick.2.2.0` in a switch named for the prover it is built against, and the switch is separate for a reason worth recording rather than by preference: adding it to the CertiCoq oracle's switch downgrades dune and recompiles fifty-nine packages including `rocq-certirocq` itself, and the proof gate's switch carries `rocq-core` and nothing else on purpose, an assumption reachable through an import being an assumption inside the R-05-163 gate's reach. The obvious spelling of the install is also the wrong one, `opam install coq-quickchick` into a clean switch resolving **Coq 8.16.1** rather than the Rocq 9.1.1 this tree pins; the prover is asked for by name instead. [tools/run.py quickchick](tools/vos/cli/quickchick.py) states all three routes and their prices.

**QEMU's own `LICENSE` is more particular than `GPL-2.0-only`, and the particulars leave the disposition where it was.** The emulator as a whole is released under GPL version 2. A source file carrying no licensing information of its own is version 2 or, at the recipient's option, any later version; contributions to `bsd-user/`, `linux-user/`, `hw/vfio/` and `hw/xen/xen_pt*` are taken under version 2 and no later version; and the Tiny Code Generator is mostly BSD or MIT with parts under other terms. So the fork is copyleft whichever arm a given file falls under, which is all the containment rule turns on, and the narrower version-2-only term bites only on a fork that keeps the user-mode trees, which a machine type modelling one bare-metal board has no use for.

**The capability library that fork exists to narrow is not copyleft at all.** `CTSRD-CHERI/cheri-compressed-cap` is `BSD-2-Clause`, from SRI International and the University of Cambridge Computer Laboratory, and the fast-emulator milestone names it as exactly the library it narrows to the frozen 64+1-bit fields. Permissive terms mean the compressed-capability work is **separable from the fork**: an instantiation of that library at this profile's field widths is not a derivative work of QEMU, so it may sit wherever it is most useful, this repository included, and only the QEMU integration around it need stay contained. **That instantiation now exists and it sits beside the fork rather than here**, which is a placement rather than an obligation: the library and the decode surface that will use it are read and changed together, and its copy of upstream is taken from the library's own repository rather than from the fork's vendored subtree, so nothing about its provenance depends on where it lives. What the read settles is that the containment rule is a property of the emulator and not of the capability format, and moving the library here later needs no licence question reopened.

## Read ahead of a later milestone

None of these is vendored, fetched, or pinned: this repository carries no URL, no hash, and no file of any of them. Each is here because a milestone of the [implementation plan](docs/implementation-checklist.md) names it, and the plan's rule is that a milestone which would move an upstream from pinned to incorporated states its terms where it is booked. Reading is free and commits nothing, which is why it happens early rather than at the milestone.

### The RTL substrate

The scalar half of that substrate is pinned rather than read ahead: [the submodule table](#pinned-as-submodules) carries the CHERI-CVA6 datapath, the tag controller, the bring-up SoC and the three RoT references, each with its terms taken from the file at its own pin. What is left here is the vector and matrix half, which no milestone before the datapath's touches.

| Component | Upstream | License | Read from |
| --- | --- | --- | --- |
| Ara, the V-class vector unit | `pulp-platform/ara` | `SHL-0.51`, Solderpad Hardware License v0.51 | `LICENSE` at the repository root |
| Gemmini, the M-class matrix unit | `ucb-bar/gemmini` | `BSD-3-Clause`, The Regents of the University of California | `LICENSE` at the repository root |

**A fork's terms are the fork's, which is why the base core is not a row.** The datapath the scalar milestone takes is `lowRISC/cva6-cheri`, not `openhwgroup/cva6`, and it does not carry one instrument: three appear at three different files in its own tree, and which governs a given file is a property of that file rather than of the project. Reading the base and attributing the result to the fork would be exactly the inference from lineage this plan refuses, so the fork is read at the fork and the base is left unread, having no route of its own.

**Solderpad is Apache-2.0 wearing a hardware hat, and it says so in its own text rather than by resemblance.** Version 0.51 grants "a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable license under the Rights to reproduce, prepare Derivative Works of, publicly display, publicly perform, sublicense, and distribute the Work", and conditions redistribution on the Apache notice obligations and nothing beyond them: a copy of the license to recipients, prominent notices on modified files, retention of the attribution notices in source form, and the NOTICE file's contents where one exists. It then settles the question outright: "As this license is not currently OSI or FSF approved, the Licensor permits any Work licensed under this License, at the option of the Licensee, to be treated as licensed under the Apache License Version 2.0." The licensee may therefore elect the license this repository's own content is already offered under.

No RTL row on this page carries a reciprocal obligation, a field-of-use restriction, or a source-disclosure condition, whether it is read here or pinned above, and the CERN Open Hardware family, whose permissive, weakly-reciprocal and strongly-reciprocal variants differ materially in exactly those respects, appears nowhere on this plan.

### 3GPP TS 38.212 and TS 38.331

These are the one instrument on this page that is not software, and the one whose terms bear on an act this plan already schedules rather than on a tree it might one day vendor. The FEC decoders' geometry needs TS 38.212's LDPC base graphs and lifting sizes, and the radio reference state machines need TS 38.331's RRC procedures. The register owes the first at the provisional freeze, and the plan states that act carries no build prerequisite, so this read is owed **now** rather than at some later milestone.

**The terms.** Copyright in a 3GPP Technical Specification vests jointly in the Organizational Partners (ARIB, ATIS, CCSA, ETSI, TSDSI, TTA and TTC), and the published ETSI edition carries the standing restriction that no part may be reproduced or utilized in any form or by any means without written authorization. 3GPP's own answer states the carve-out that matters: other than for in-house copies for the purpose of further development of the 3GPP standard or for product design purposes, no part of a TS or TR may be reproduced without seeking permission, with a copyright form for uses such as company training, conference presentations, journal articles and textbooks.

**Two distinctions decide what that means here.**

- *Obtaining is not a license to reproduce.* The specifications are freely downloadable from 3GPP's and ETSI's portals, and downloading one grants nothing beyond the in-house carve-out.
- *Implementing is not reproducing.* A decoder built to the standard is product design, which the carve-out reaches, while a base-graph table transcribed into a Coq or Sail source *in a public repository* is reproduction of a normative table inside a conveyed artifact, which it does not. This repository is public, so those two acts come apart at exactly the point this plan would put them.

**What the read does not settle**: whether a transcription carrying the *numbers* of a base graph without the specification's surrounding text is reproduction of a protectable work. The ETSI notice is broad, the 3GPP carve-out is narrower than the use this plan would make of it, and the answer belongs to counsel and to the copyright form rather than to a document here.

**The call is to publish table-free**, which is the arm that does not need the unsettled question answered. No normative 3GPP table is a tracked file. The FEC decoders' surface is authored parameterized over a base graph, a lifting size and a list size, and the radio reference state machines are authored against TS 38.331's procedures, with the numbers supplied at composition from a copy the builder obtains under their own in-house carve-out. Designing against the standard is what the carve-out already permits, so the arm blocks no engineering and defers nothing; what it declines is reproduction inside an artifact this repository conveys, which is the only act the carve-out fails to reach. It follows that **the register names such a parameter without stating its value**, which is the shape a frozen-but-unvalued parameter already takes here for the per-class bank count and the welded block size, the difference being only that the value is owed to a builder's copy rather than to a measurement.

**What the call forfeits is self-containment**, and the forfeit is recorded here rather than absorbed: this tree alone does not compose an FEC-bearing image, the reproducible-build account is narrower for that component than for any other, and each builder takes the 3GPP read themselves instead of inheriting one taken here. **The permission arm stays open and composes with this one.** Seeking 3GPP's copyright form would make the tables trackable and retire the forfeit, nothing in the table-free arm forecloses it, and a shipped product meets this ecosystem again at the FRAND instrument regardless. That is why table-free is what a proof-of-concept spends while what the first release is remains an open product question.

**Patents are a separate instrument and not a copyright question at all.** Patents essential to 5G NR are declared under the Organizational Partners' IPR policies and licensed on fair, reasonable and non-discriminatory terms. That instrument attaches to shipping a product rather than to publishing a specification or a model, and no reading of the copyright position substitutes for it.

### The cryptography upstreams

Nothing here is tracked, fetched, or pinned yet. The [implementation plan](docs/implementation-checklist.md)'s cryptography milestone would incorporate all four, and its calls are taken ahead of that act so the milestone opens against a decided standing rather than against an open question. Only one of the four is not permissive, and it is not permissive because it states no terms at all.

| Component | Standing taken | What it is |
| --- | --- | --- |
| Fiat-Crypto | Pinned as a submodule, run as a build-time generator, its emission tracked beside the commit it was derived at | The classical field arithmetic, which the register mandates by name and admits by derivation |
| VST's `sha/` and `hmacdrbg/` | Acquired through the VST opam distribution, which its own `LICENSE` places under `BSD-2-Clause` | SHA-256 and HMAC-DRBG-SHA-256, each carrying a Gallina specification and a refinement proof, the second an FCF security proof besides |
| The FIPS and ACVP known-answer vectors | Fetched at build time, a URL and an integrity hash tracked and no file | The oracle every authored primitive is validated against |
| The behavioural oracles | Pinned as submodules, read and never copied, vendored, or extracted from | A second implementation per authored primitive, taken in pairs of independent verification lineage |

**Fiat-Crypto is generated rather than vendored, and the register is what decides that.** The mandate's acceptance is that every field-arithmetic implementation *traces to a Fiat-Crypto derivation*, so a recorded generator run against a pinned commit satisfies it while a bare tracked output does not, having nothing in the checkout that names the derivation. Vendoring the tree would satisfy it too and is declined on the standing rule that pinning is free and vendoring is a commitment.

**Its election is Apache-2.0, and the reading that fixes the arms is owed at the pin rather than taken here.** The project offers three arms at the taker's option, and the sentence stating that in this document is a characterization written while disposing an unlicensed deposit that patches Fiat-Crypto, not a reading of Fiat-Crypto's own licence file. That is the inference from lineage this page forbids, so the arm is recorded and the reading is taken at the milestone that pins it. Apache-2.0 matches the licence this repository's own content already carries and adds an express patent grant on the one primitive class where patents historically bite; the permissive arms keep Apache's notice and patent-termination provisions out of the tree and stay available if a later act wants them.

**The VST route is chosen to avoid a term rather than to fix an edition.** The repository carries `compcert/` and `compcert_new/` in tree, and the second is the one VST's own direction says not to use without satisfying the CompCert licence, so pinning it would re-raise the non-commercial term decomposed under [CompCert and SECOMP](#compcert-and-secomp). The opam distribution is the acquisition route that does not convey it, the Coq sources are what this design reasons in, and the C beside them is OpenSSL- and mbedTLS-derived and is not taken. What the route forfeits is the exactness of a commit: a version constraint fixes the edition more loosely than a pin does.

**The vectors are fetched because they are large and because a floating corpus is worse than a large one.** They carry no usage restriction and two notice conditions, and one set alone is about 110 MB, so they take the shape [fetched at build time](#fetched-at-build-time) already uses here: a tracked URL and integrity hash, with the upstream conveying the bytes. That also makes a vector revision reproducible rather than silently floating under a milestone's acceptance evidence, which is what a corpus obtained by hand would be.

**One oracle states no terms at all, and it is pinned for its edition and read for nothing else.** The most prominent Jasmin ML-KEM artifact carries no licence file, so it may be pinned and read and may not be copied, vendored, or extracted from. That is the disposition [`katamaran-project/sail-backend`](#pinned-as-submodules) already carries, met on a library rather than on a tool, and it is why pinning an oracle is worth the row: what an acceptance figure was compared against is a property of an edition, and an unpinned oracle cannot state one.

### Non-permissive upstreams, and the calls taken on them

None is tracked here yet. Each was read at its pin or its own license file rather than inferred from lineage, and each is booked in the [implementation plan](docs/implementation-checklist.md) as a decision taken at the milestone that would incorporate it.

| Upstream | Milestone | Terms | The call |
| --- | --- | --- | --- |
| CompCert, through `upstream/SECOMP` | M1.1a, the compiler | INRIA Non-Commercial License Agreement, over a dual-licensed subset | **Contained.** It stays a build-time producer this repository does not convey. |
| Vélus, `INRIA/velus` | M6.0a, the control-plane compiler | Inria Non-Commercial License Agreement for Vélus, carrying a reciprocal distribution clause | **Contained**, on the same ground. |
| seL4's `spec/` and `proof/` | M4.1a, the kernel specification | `GPL-2.0-only`; `lib/` and `tools/` are `BSD-2-Clause` | **Not taken.** The Gallina objects are authored from the design rather than translated. |

CompCert and Vélus are the same form of instrument from the same licensor and are nonetheless **separate grants**: identical in form, and obtained apart. Neither containment call moves a row above, which is why neither appears in the vendored table and why the claim at the top of this page still holds. The kernel specification resolves differently because its term is the one that would have reached the shipped image: containment is reversible and a derivation is not.

#### CompCert and SECOMP

`upstream/SECOMP`'s `LICENSE` at the pinned commit puts the CompCert verified compiler under the **INRIA Non-Commercial License Agreement**, whose grant is "revocable, nonexclusive, nontransferable, royalty-free" and runs "solely for educational, research, or evaluation purposes". A named subset is dual-licensed `LGPL-2.1-or-later`: `lib/`, `common/`, twelve `cfrontend/` files, `backend/Cminor.v` with `backend/PrintCminor.ml`, `cparser/`, `export/`, four per-architecture files, `extraction/extraction.v`, and the build files. `flocq/` and `MenhirLib/` are `LGPL-3.0-or-later`, `runtime/` is `BSD-3-Clause`, and commercial use requires a separate AbsInt Software Usage Agreement.

**The decomposition is worse than the headline.** The verified backend passes and the RISC-V backend are not on the dual-licensed list, nor is SECOMP's own `cheririscV/` capability backend, which is exactly the material the compiler milestone would take. The permissive and LGPL arms cover the parts that milestone does not need.

**A commercial arm probably requires two grants from two rightsholders.** The AbsInt Software Usage Agreement conveys rights in CompCert, while `cheririscV/` is SECOMP's own contribution, in which AbsInt has no standing to grant anything.

**The same term is reachable through VST.** VST is `BSD-2-Clause` in the components this design reasons in, its `LICENSE` placing "all parts of the VST opam distribution ... (including msl, sepcomp, veric, floyd, concurrency)" and the test suite under that license, and it carries two CompCert trees beside them. Of these, `compcert/` is "dual licensed with a proprietary license and an open-source license" and contains Clight, which is what a sequential refinement requires; `compcert_new/` "contains some files that are not dual-licensed", and VST's own direction is that "you should not use compcert_new unless you satisfy the terms of the CompCert license". The condition is therefore specific rather than general, and it attaches to VST's concurrency path. The opam distribution is the acquisition route that does not convey it.

#### Vélus

`INRIA/velus`'s `LICENSE` is the **Inria Non-Commercial License Agreement for the Vélus verified Lustre compiler**, and Vélus incorporates a modified CompCert as a submodule of its own. The operative clauses, each quoted from the instrument rather than characterized:

- **§2, Grant.** A "revocable, nonexclusive, nontransferable, royalty-free and worldwide license ... to use the Software solely for educational, research, or evaluation purposes", entitling the licensee "to create Derivative Works solely for academic, non-commercial research endeavors". The Agreement defines that term broadly: "A 'Derivative Work' is a work that is a modification of, enhancement to, derived from, or based upon the Software".
- **§3, Limitations on Use.** "The License is limited to noncommercial use ... Any other use is commercial use. You may not use the Software in connection with any activities which purpose is to procure a commercial gain to you or others." Noncommercial use is thus a property of each act of use, not a standing characterization of the licensee or of the project.
- **§4, Limitations on Distribution.** "If you distribute the Software or any derivative works of the Software, you will distribute them under the same terms and conditions as in this License, and you will not grant other rights to the Software or derivative works that are different from those provided by this License." This is a reciprocal term, and the CompCert agreement carries no counterpart to it: a fork of Vélus may be published, and may be published only on these terms.
- **§7, Term of License.** The License "will terminate immediately without notice by the Provider if you fail to comply with the terms and conditions of this Agreement", whereupon the licensee "shall immediately discontinue all use" and return or destroy all copies.

The licensor and the form of the instrument are the compiler's; **the grant is not**. Inria licenses Vélus under its own agreement, so terms negotiated for CompCert, whether with Inria or with AbsInt, do not extend to it, and the two are priced as separate calls. What differs in the other direction is the cost of declining: the [implementation plan](docs/implementation-checklist.md)'s init system already keeps a Gallina reference model of the same state machine as its host-side oracle, so the arm that authors rather than imports begins from an existing artifact.

#### seL4

The seL4 proof repository tags every file, and the tags split on directory: `spec/` and `proof/` are `GPL-2.0-only`, while `lib/` and `tools/` are `BSD-2-Clause`. The executable-spec objects a translation milestone would take are on the `GPL-2.0-only` side, and translation is among the enumerated forms a derivative work takes, so the target language does not bear on the question.

**The incompatibility is structural rather than a matter of preference.** GPL-2.0 conditions redistribution on imposing "no further restrictions" on the recipient's exercise of the rights it grants, and Apache-2.0 imposes conditions, its patent-termination and notice provisions among them, that constitute such restrictions; the Apache Software Foundation and the Free Software Foundation both state the incompatibility in that direction. A kernel that is a derivative work of those objects therefore could not be offered under Apache-2.0, and would carry `GPL-2.0-only` instead. The syscall exception in seL4's licensing does not reach the question: it addresses user-level code that invokes the kernel through its system-call interface, not code derived from the kernel's specification.

### The Coq hardware DSLs

The plan's closing RTL route names two Coq hardware DSLs together wherever it names either, and their terms differ: **Kami is `MIT`** and **Kôika is `LGPL-2.1`**. Two things follow.

- Authoring a block means writing Coq modules that import the chosen library, which is the configuration in which an LGPL library's reciprocity is least settled, and this route is the one place on the plan where such a term could attach to *authored design* rather than to an instrument of the kind contained above.
- **Kôika's repository does not disambiguate `LGPL-2.1-only` from `LGPL-2.1-or-later`**, carrying the bare license text with no per-file notices electing a version, and the two differ materially in onward compatibility. That is a defect in the upstream rather than something this page can settle.

Nothing is owed before this route opens, well after the co-simulation gate. What is owed is the preference, so that the election is made on what each library buys rather than on which name appears first in a sentence, and the [implementation plan](docs/implementation-checklist.md) records it.

### Start-froms read and declined

Three of the start-froms the plan's opening reading disposes take no gitlink, on the rule that pinning is free where it fixes an edition somebody reads and is clutter where it does not. Each was read on 2026-08-29 at whatever its own terms are stated in, and the ground for declining is stated with the reading rather than left to be re-derived.

**StkTokens is a discipline and not an artifact.** The register cites it for the linear and affine stack discipline the program logic instantiates, and the technical report accompanying the POPL 2019 paper offers proofs and details rather than a mechanization; no Coq development of it is published under a repository this page could pin. What is published in Coq beside it is `logsem/cerise-stack`, which is the uninitialized-capability revocation work rather than StkTokens and which no milestone here names. Taking a discipline from a paper carries nothing, which is the distinction the kernel-specification call already turns on: ideas carry nothing and artifacts carry whatever they carry.

**The CHERI Alliance Sail line is external evidence, and what the plan wanted from it is already pinned.** `CHERI-Alliance/sail-cheri-riscv` was archived in April 2025 and its own README directs a reader to that organization's `sail-riscv` fork, where the CHERI work is a branch rather than a release; [the version matrix](docs/cheri-version-matrix.md) already places that line among the rows the profile's retired re-pin obligation is read against rather than among its start-froms. Terms decide nothing either way: the archived tree's `LICENCE` is `BSD-2-Clause` under "Copyright (c) 2017-2023" naming the CHERI-RISC-V Sail authors together with Google and Microsoft, the same instrument the pinned oracle carries. **The Rocq build target is not that line's to supply.** `make riscv_coq_build` is documented in the README of the pinned oracle itself, which also names the properties repository now pinned above, so both halves the plan attributed to the Alliance line are reachable at editions this page already carries and the third pin the plan implied is not owed.

**The Rocq-native NTT is published with no licence.** The artifact is a Zenodo deposit of February 2026 carrying a README and a source archive, and it is neither a fork nor a branch: it is a patch and a source directory to be applied over commit `af03839247c545987c20e99342ab2bbfcd517863` of `mit-plv/fiat-crypto`. The deposit states no licence, its README states none, and the record itself carries none, so the disposition is the cryptography milestone's own for a Jasmin artifact, read and never copied, vendored, or extracted from. A repository does exist, which the survey reading did not have: the author's personal fork of Fiat-Crypto carries two NTT branches under that project's root election of `MIT OR Apache-2.0 OR BSD-1-Clause`. It changes nothing here. Those branches predate the published artifact by more than a year, and whether a project-wide election reaches files a contributor added on a personal fork is a question that file does not answer and this page may not settle. The plan's disposition stands and its ground is replaced: the artifact is read rather than pinned because it has no terms, not because it has no repository.
