# Third-Party Components

*Everything in this repository that somebody else wrote, and the terms it arrives under. The distinction that organizes the page is redistribution: a vendored tree is carried here as bytes and its license binds this repository, while a submodule is carried as a URL and a commit hash and binds only whoever fetches it. [COPYRIGHT.md](COPYRIGHT.md) carries the map for the original content.*

## Vendored, and therefore redistributed here

Each component keeps its own license file in place, unmodified, beside the code it governs.

| Component | Upstream | License | Notice |
| --- | --- | --- | --- |
| The curated Sail model, `model/` | `riscv/sail-riscv`, vendored at `8f91355e` | BSD-2-Clause | [model/LICENCE](model/LICENCE) |
| The transplanted capability semantics | `CTSRD-CHERI/sail-cheri-riscv` | BSD-2-Clause | [model/LICENCE.cheri](model/LICENCE.cheri) |
| CLI11 | University of Cincinnati, Henry Schreiner | BSD-3-Clause | `model/dependencies/CLI11/LICENSE` |
| ELFIO | Serge Lamikhov-Center | MIT | `model/dependencies/elfio/LICENSE.txt` |
| Asio | Christopher M. Kohlhoff | BSL-1.0 | `model/dependencies/asio/LICENSE_1_0.txt` |
| jsoncons | Daniel Parker | BSL-1.0 | `model/dependencies/jsoncons/LICENSE` |
| Berkeley SoftFloat 3e | The Regents of the University of California, John R. Hauser | BSD-3-Clause | `model/dependencies/softfloat/berkeley-softfloat-3/COPYING.txt` |
| RISC-V encoding header | RISC-V International | BSD-3-Clause | In-file tag, `model/test/first_party/src/common/encoding.h` |
| nanoprintf | Charles Nicholson | 0BSD or Unlicense, at the user's choice | In-file text at the foot of `model/test/first_party/src/common/nanoprintf.h` |

The last two sit outside the upstream carve-out and are worth stating plainly. [model/LICENCE](model/LICENCE) places every file under BSD-2-Clause *except* the third-party dependencies in the `dependencies` directory, and these two are third-party code that does not live there: they are vendored into the first-party test harness and carry their own headers. The headers govern. Nothing here depends on resolving the tension, because every candidate reading is permissive and attribution-only.

Every one of these is permissive and attribution-only. No copyleft term and no field-of-use restriction is carried anywhere in the tracked tree, which is why the licenses in [COPYRIGHT.md](COPYRIGHT.md) are available to choose at all.

The curated model is a modified derivative rather than a copy: batches under the plan's hardware-reference milestone delete most of the upstream surface and transplant the capability layer into what remains. The upstream notice governs it whole, and [COPYRIGHT.md](COPYRIGHT.md) records that modifications made here are offered back on the same terms.

## Pinned as submodules, and not redistributed here

These are gitlink entries. This repository carries a URL and a commit hash for each and none of the code, so their terms bind a clone that fetches them rather than this tree.

| Submodule | Upstream | Pin | Standing |
| --- | --- | --- | --- |
| `upstream/sail-riscv` | `riscv/sail-riscv` | `6266b40c` | The edition the curation is reconciled against. Same BSD-2-Clause terms as the vendored tree. |
| `upstream/sail-cheri-riscv` | `CTSRD-CHERI/sail-cheri-riscv` | `bb07488d` | The capability-semantics oracle. Same BSD-2-Clause terms. |
| `upstream/SECOMP` | `secure-compilation/CompCert` | `5c20b839` | A CompCert fork, and the one pin whose terms are not permissive. Read at the pin and decomposed below. |

## The two that decide something

Neither is tracked here yet. Both are read at the pin rather than inferred, and both are booked in the [implementation plan](docs/implementation-checklist.md) as decisions at the milestone that would spend them.

**The compiler.** `upstream/SECOMP`'s `LICENSE` at the pinned commit puts the CompCert verified compiler under the **INRIA Non-Commercial License Agreement**, whose grant is "revocable, nonexclusive, nontransferable, royalty-free" and runs "solely for educational, research, or evaluation purposes". A named subset is dual-licensed LGPL-2.1-or-later: `lib/`, `common/`, twelve `cfrontend/` files, `backend/Cminor.v` with `backend/PrintCminor.ml`, `cparser/`, `export/`, four per-architecture files, `extraction/extraction.v`, and the build files. `flocq/` and `MenhirLib/` are LGPL-3.0-or-later, `runtime/` is BSD-3-Clause, and commercial use requires a separate AbsInt Software Usage Agreement.

The decomposition is what matters, and it is worse than the headline: **the verified backend passes and the RISC-V backend are not on the dual-licensed list**, nor is SECOMP's own `cheririscV/` capability backend, which is exactly the material the compiler milestone would take. The permissive and LGPL arms cover the parts that milestone does not need.

**The kernel specification.** The seL4 proof repository tags every file, and the tags split on directory: `spec/` and `proof/` are **GPL-2.0-only**, while `lib/` and `tools/` are BSD-2-Clause. The executable-spec objects a translation milestone would take are on the GPL-2.0-only side, and a translation is a derivative work of its source whatever the target language. Apache states that its own license is incompatible with GPL version 2, so a kernel derived from those objects could not be Apache-2.0. The syscall note in seL4's license does not reach this: it exempts user-level code that merely calls the kernel, not code derived from the kernel's specification.

**And one that does not.** A QEMU fork inherits QEMU's GPL-2.0 terms, but the fast emulator is a development instrument that no shipped image links or embeds, so it stays in its own repository and nothing propagates. It is a containment rule rather than a fork.
