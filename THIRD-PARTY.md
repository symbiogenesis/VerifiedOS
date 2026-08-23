# Third-Party Components

*Everything in this repository that somebody else wrote, and the terms it arrives under. The distinction that organizes the page is **conveyance**, because that is the act on which substantially every obligation in these licenses is conditioned, and it sorts into three kinds: a **vendored** tree is conveyed by this repository, so its terms bind every recipient of a copy of this repository and its notice obligations are discharged here; a **fetched** dependency is named by URL and integrity hash and is conveyed by its own upstream at configure time; and a **submodule** is named by URL and commit hash and is likewise conveyed by its own upstream, to whoever initializes it. Only the first is redistribution by this repository. [COPYRIGHT.md](COPYRIGHT.md) carries the map for the original content.*

## Vendored, and therefore redistributed here

Each component keeps its own license file in place, unmodified, beside the code it governs.

| Component | Upstream | License | Notice |
| --- | --- | --- | --- |
| The curated Sail model, `model/` | `riscv/sail-riscv`, vendored at `8f91355e` | BSD-2-Clause | [model/LICENCE](model/LICENCE) |
| The transplanted capability semantics | `CTSRD-CHERI/sail-cheri-riscv` | BSD-2-Clause | [model/LICENCE.cheri](model/LICENCE.cheri) |
| ELFIO 3.12 | Serge Lamikhov-Center | MIT | `model/dependencies/elfio/LICENSE.txt` |
| Berkeley SoftFloat 3e | The Regents of the University of California, John R. Hauser | BSD-3-Clause | `model/dependencies/softfloat/berkeley-softfloat-3/COPYING.txt` |
| RISC-V encoding header | RISC-V International | BSD-3-Clause | In-file tag, `model/test/first_party/src/common/encoding.h` |
| nanoprintf v0.8.0 | Charles Nicholson | `0BSD OR Unlicense`, at the recipient's option | In-file text at the foot of `model/test/first_party/src/common/nanoprintf.h` |

## Fetched at build time, and therefore not redistributed here

These three keep a license file and a `CMakeLists.txt` under `model/dependencies/` and none of the governed code. Each is a `FetchContent` declaration naming an upstream URL and an integrity hash, so the source is conveyed by its own upstream at configure time and at no point by this repository. They therefore sit on the submodule side of the distinction above rather than the vendored side. The hash is an integrity control and not a license mechanism: it fixes *which* bytes arrive, and the terms below govern them once they do. The license files are retained here so that the terms are legible before a build is configured rather than after.

| Component | Upstream | Pin | License | Notice |
| --- | --- | --- | --- | --- |
| CLI11 | University of Cincinnati, Henry Schreiner | 2.6.2, `SHA256` | BSD-3-Clause | `model/dependencies/CLI11/LICENSE` |
| Asio | Christopher M. Kohlhoff | 1.36.0, `SHA3_256` | BSL-1.0 | `model/dependencies/asio/LICENSE_1_0.txt` |
| jsoncons | Daniel Parker | 1.8.1, `SHA3_256` | BSL-1.0 | `model/dependencies/jsoncons/LICENSE` |

Their versions are the curated tree's to follow rather than to choose. Each is upstream `sail-riscv`'s dependency, arriving through the curation, so a local bump is divergence that every later reconciliation has to carry; drift here is read as a signal about reconciliation cadence rather than as a repair owed.

The last two vendored rows sit outside the upstream carve-out and are worth stating plainly. [model/LICENCE](model/LICENCE) places every file under BSD-2-Clause *except* the third-party dependencies in the `dependencies` directory, and these two are third-party code that does not live there: they are vendored into the first-party test harness and carry their own headers. The headers govern. Nothing here depends on resolving the tension, because every candidate reading is permissive and non-reciprocal.

The curated model is a modified derivative rather than a copy: batches under the plan's hardware-reference milestone delete most of the upstream surface and transplant the capability layer into what remains. The upstream notice governs it whole, and [COPYRIGHT.md](COPYRIGHT.md) records that modifications made here are offered back on the same terms.

Every license named above is permissive and non-reciprocal. Each conditions redistribution on nothing more than retention of a copyright notice and a warranty disclaimer, and `0BSD` and the Unlicense impose not even that. None carries a reciprocal obligation, a field-of-use restriction, or a source-disclosure condition, which is why the licenses in [COPYRIGHT.md](COPYRIGHT.md) are available to choose at all.

## Carried by the build, not by the tree

One reciprocal term attaches to the built emulator without reaching any tracked file, so the paragraph above is accurate as to the tree and is not the whole account. `model/CMakeLists.txt` calls `find_package(GMP)`, and GMP is offered as `LGPL-3.0-or-later OR GPL-2.0-or-later`; the Sail C runtime links it for arbitrary-precision arithmetic, which makes a built `sail_riscv_sim` a Combined Work in the LGPL's sense.

No condition of that license is presently triggered, because every one of them attaches to *conveying* the Combined Work and this repository conveys no binary: the golden-model emulator is built locally as a verification instrument. Conveying one to a third party would engage the LGPL's Combined Work conditions, of which the substantive one is the recipient's right to relink the executable against a modified GMP, alongside notice and a copy of the license. That is a condition on the shipping act rather than a defect in the tree, and it is recorded here because the reproducible-bootstrap story in the [implementation plan](docs/implementation-checklist.md) contemplates exactly that act. Until then the disposition is the containment rule the fast emulator carries, and for the same reason.

## Pinned as submodules, and not redistributed here

These are gitlink entries. This repository carries a URL and a commit hash for each and none of the code, so their terms bind a clone that fetches them rather than this tree.

| Submodule | Upstream | Pin | Standing |
| --- | --- | --- | --- |
| `upstream/sail-riscv` | `riscv/sail-riscv` | `ac2a5855` | The edition the curation is reconciled against. Same BSD-2-Clause terms as the vendored tree. |
| `upstream/sail-cheri-riscv` | `CTSRD-CHERI/sail-cheri-riscv` | `bb07488d` | The capability-semantics oracle. Same BSD-2-Clause terms. |
| `upstream/SECOMP` | `secure-compilation/SECOMP` | `5c20b839` | A CompCert fork, and the one pin whose terms are not permissive. The project is renamed on GitHub and the older `secure-compilation/CompCert` path redirects here, so the PriSC'23 abstract's link and this row name one repository. Read at the pin and decomposed below. |

## The three that decide something

None is tracked here yet. Each was read at its pin rather than inferred from lineage, and each is booked in the [implementation plan](docs/implementation-checklist.md) as a decision taken at the milestone that would incorporate it. Two of the three are the same instrument from the same licensor and are nonetheless **separate grants**, which is the fact most easily missed: they are identical in form and must be obtained apart.

**The three calls are taken and none of them moves a row above.** The compiler (M1.1a) and the control-plane compiler (M6.0a) are **contained**: each stays a build-time producer that this repository does not convey, which is why neither appears in the vendored table and why the sentence closing this document still holds. The kernel specification (M4.1a) is **not taken at all**, its Gallina objects being authored from the design rather than translated from `spec/` and `proof/`, because that is the one of the three whose term would have reached the shipped image. Containment is reversible and a derivation is not, which is the whole of why the third resolves differently from the first two.

**The compiler.** `upstream/SECOMP`'s `LICENSE` at the pinned commit puts the CompCert verified compiler under the **INRIA Non-Commercial License Agreement**, whose grant is "revocable, nonexclusive, nontransferable, royalty-free" and runs "solely for educational, research, or evaluation purposes". A named subset is dual-licensed LGPL-2.1-or-later: `lib/`, `common/`, twelve `cfrontend/` files, `backend/Cminor.v` with `backend/PrintCminor.ml`, `cparser/`, `export/`, four per-architecture files, `extraction/extraction.v`, and the build files. `flocq/` and `MenhirLib/` are LGPL-3.0-or-later, `runtime/` is BSD-3-Clause, and commercial use requires a separate AbsInt Software Usage Agreement.

The decomposition is what matters, and it is worse than the headline: **the verified backend passes and the RISC-V backend are not on the dual-licensed list**, nor is SECOMP's own `cheririscV/` capability backend, which is exactly the material the compiler milestone would take. The permissive and LGPL arms cover the parts that milestone does not need.

Two consequences of that term reach past the milestone that spends it. The first is that **the commercial arm probably requires two grants from two rightsholders**: the AbsInt Software Usage Agreement conveys rights in CompCert, while `cheririscV/` is SECOMP's own contribution, in which AbsInt has no standing to grant anything.

The second is that the same term is reachable through a second dependency. **VST** is BSD-2-Clause in the components this design reasons in, its `LICENSE` placing "all parts of the VST opam distribution ... (including msl, sepcomp, veric, floyd, concurrency)" and the test suite under that license, and it carries two CompCert trees beside them. Of these, `compcert/` is "dual licensed with a proprietary license and an open-source license" and contains Clight, which is what a sequential refinement requires; `compcert_new/` "contains some files that are not dual-licensed", and VST's own direction is that "you should not use compcert_new unless you satisfy the terms of the CompCert license". The condition is therefore specific rather than general, and it attaches to VST's concurrency path. The opam distribution is the acquisition route that does not convey it.

**The control-plane compiler.** `INRIA/velus`'s `LICENSE` is the **Inria Non-Commercial License Agreement for the Vélus verified Lustre compiler**, and Vélus incorporates a modified CompCert as a submodule of its own. Four clauses are operative, each quoted from the instrument rather than characterized:

- **§2, Grant.** A "revocable, nonexclusive, nontransferable, royalty-free and worldwide license ... to use the Software solely for educational, research, or evaluation purposes", entitling the licensee "to create Derivative Works solely for academic, non-commercial research endeavors". The Agreement defines that term broadly: "A 'Derivative Work' is a work that is a modification of, enhancement to, derived from, or based upon the Software".
- **§3, Limitations on Use.** "The License is limited to noncommercial use ... Any other use is commercial use. You may not use the Software in connection with any activities which purpose is to procure a commercial gain to you or others." Noncommercial use is thus a property of each act of use, not a standing characterization of the licensee or of the project.
- **§4, Limitations on Distribution.** "If you distribute the Software or any derivative works of the Software, you will distribute them under the same terms and conditions as in this License, and you will not grant other rights to the Software or derivative works that are different from those provided by this License." This is a reciprocal term, and the CompCert agreement carries no counterpart to it: a fork of Vélus may be published, and may be published only on these terms.
- **§7, Term of License.** The License "will terminate immediately without notice by the Provider if you fail to comply with the terms and conditions of this Agreement", whereupon the licensee "shall immediately discontinue all use" and return or destroy all copies.

The licensor and the form of the instrument are the compiler's; **the grant is not**. Inria licenses Vélus under its own agreement, so terms negotiated for CompCert, whether with Inria or with AbsInt, do not extend to it, and the two are priced as separate calls. What differs in the other direction is the cost of declining: the [implementation plan](docs/implementation-checklist.md)'s init system already keeps a Gallina reference model of the same state machine as its host-side oracle, so the arm that authors rather than imports begins from an existing artifact.

**The kernel specification.** The seL4 proof repository tags every file, and the tags split on directory: `spec/` and `proof/` are **GPL-2.0-only**, while `lib/` and `tools/` are BSD-2-Clause. The executable-spec objects a translation milestone would take are on the GPL-2.0-only side, and translation is among the enumerated forms a derivative work takes, so the target language does not bear on the question.

The incompatibility is structural rather than a matter of preference. GPL-2.0 conditions redistribution on imposing "no further restrictions" on the recipient's exercise of the rights it grants, and Apache-2.0 imposes conditions, its patent-termination and notice provisions among them, that constitute such restrictions; the Apache Software Foundation and the Free Software Foundation both state the incompatibility in that direction. A kernel that is a derivative work of those objects therefore could not be offered under Apache-2.0, and would carry GPL-2.0-only instead. The syscall exception in seL4's licensing does not reach the question: it addresses user-level code that invokes the kernel through its system-call interface, not code derived from the kernel's specification.

**And one that does not.** A fork of QEMU is a derivative work of a `GPL-2.0-only` work and is governed accordingly, but the fast emulator is a development instrument that no conveyed image links against or embeds, so it is maintained in a separate repository and its terms reach nothing here. That is a containment rule, and it holds because reciprocity under the GPL runs to derivative and combined works rather than to whatever a program is used to produce. Verilator, offered as `LGPL-3.0 OR Artistic-2.0` at the recipient's option, and `ccache`, `GPL-3.0-or-later`, are contained on the same ground: each observes or accelerates a build without entering the work the build emits.

**And one pair that is not the single choice it reads as.** The plan's closing RTL route names two Coq hardware DSLs together wherever it names either, and their terms differ: **Kami is `MIT`** and **Kôika is LGPL-2.1**. Two things follow. The first is that authoring a block means writing Coq modules that import the chosen library, which is the configuration in which an LGPL library's reciprocity is least settled, and this route is the one place on the plan where such a term could attach to *authored design* rather than to an instrument of the kind contained above. The second is a defect in the upstream that a careful reader should not paper over: **Kôika's repository does not disambiguate `LGPL-2.1-only` from `LGPL-2.1-or-later`**, carrying the bare license text with no per-file notices electing a version, and the two differ materially in onward compatibility. Nothing is owed before this route opens, well after the co-simulation gate. What is owed is the preference, so that the election is made on what each library buys rather than on which name appears first in a sentence, and the [implementation plan](docs/implementation-checklist.md) now records it.
