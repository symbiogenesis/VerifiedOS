# Fiat-Crypto emission contract

This document owns M3.4c-ii's derivation recipe, destination, licensing decision and acceptance predicate under R-05-060. The [implementation checklist](implementation-checklist.md) owns item completion; the [third-party ledger](../../THIRD-PARTY.md) owns incorporated upstream records.

## Destination and license decision

The selected generator is `mit-plv/fiat-crypto` at `1e721c6f18c43b90922e7bc57fd64848e5cff2be`, the exact `upstream/fiat-crypto` gitlink. Its own `COPYRIGHT` offers MIT, Apache-2.0 or BSD-1-Clause. This project elects Apache-2.0, as its existing ledger does. The selected revision's `LICENSE-APACHE` and `AUTHORS` were read before incorporating its output; generated output retains the upstream authors' notice and all notices emitted by the generator. The generator and its libraries are build-time inputs, not artifacts to distribute from this repository. Every nested dependency used to build it needs its own license receipt; no permission for a dependency is inferred from Fiat-Crypto's election.

Generated field routines belong under `tools/generated/fiat-crypto/` as C inclusion headers, with `// SPDX-License-Identifier: Apache-2.0` in the opening comment. The generator emits static/internal routines suitable for inclusion into a consuming translation unit. The `.h` suffix describes that interface and already has a K-52/K-53 comment-syntax ruling; it does not hide an unruled file kind. The provenance wrapper is an explicit reproducible transformation, not a claim that a wrapped header is byte-identical to raw stdout. No generated field arithmetic belongs in the modified Sail model, whose upstream bytes have their own BSD-2-Clause boundary and `-text -eol` rule. No checker exemption or license-map change is needed.

Each emitted header retains the raw generated body and surrounds it with the recorded SPDX, copyright, immutable-source notice and C inclusion guard. The generator body carries its exact command. A JSON manifest beside it carries the pin, nested revisions and source-archive hashes, invocation, generator identity and raw/wrapped hashes; the companion vector receipt records verification results. A local original Python driver may reproduce/check the envelope; it must reject a different pin, missing generator, failed invocation or mismatching output. Generated code is not manually repaired. Raw stdout, stderr and toolchain/build logs remain under the assigned native lane; retained receipts identify them.

## Field and representation scope

The first recipe covers the two standard prime-field examples the selected upstream documents: `2^255 - 19` and `2^256 - 2^224 + 2^192 + 2^96 - 1`. These are explicit field-arithmetic artifacts, not a decision to admit any complete curve protocol or platform cipher suite. The selected 32-bit limb representation uses ordinary bounded-width C intermediates rather than requiring a new 128-bit primitive from the future purecap backend. Their host compilation is not a target refinement proof.

The intended generator commands are:

```
fiat_crypto unsaturated-solinas 25519 32 10 '2^255 - 19' carry_mul carry_square carry_scmul121666 carry add sub opp selectznz to_bytes from_bytes --static
fiat_crypto word-by-word-montgomery p256 32 '2^256 - 2^224 + 2^192 + 2^96 - 1' --static
```

The exact executable path, flags and all output transformations are frozen by the recorded successful recipe, rather than inferred from these examples. A second party must build or identify the generator at the recorded parent and nested revisions, run each invocation twice, and compare byte-for-byte raw and wrapped output hashes. A binary built at another source revision cannot witness generation at the selected pin.

## Research handoff for future field and code parameters

The survey's [finite-field factorization frontier](../background/open-math-conjectures.md#deterministic-polynomial-factorization-over-finite-fields) and [GRH entry](../background/open-math-conjectures.md#generalized-riemann-hypothesis-for-dirichlet-l-functions) are inputs to future parameter-generation proposals, not missing premises of the recorded M3.4c-ii emission. No present recipe bottleneck is identified by either result. This research guidance changes neither the chosen moduli nor the acceptance predicate below.

For a future field or code construction, make the finite representation explicit: a prime `p`, and, for an extension, an irreducible defining polynomial over `F_p`. Supply checked finite primality/irreducibility evidence and prove any factorization output reconstructs the input with the claimed multiplicities and irreducible factors. A reducible defining polynomial, a composite modulus or an omitted repeated factor is a useful negative witness. The March 2026 structured factorization progress for Reed-Solomon decoding only applies after proving its particular input structure. The survey records the later prime-field polynomial-time claim and its unverified companion analytic input; applying it to an explicitly represented extension field requires a reduction and bit-cost account. The [decoder proof handoff](../assurance/proof-reuse/hardware.md#research-handoff-for-future-code-and-decoder-proofs) owns the subsequent code-specific bridge.

GRH can inform the cost of some offline witness searches, but a search hypothesis need not enter a consumer theorem whose selected constants carry direct finite certificates. Separate search termination/cost from certificate soundness and charge bit operations, representation size and preprocessing to the actual producer. GRH alone does not settle unrestricted polynomial factorization, and neither result proves integer-factoring hardness or this suite's security. Any new emitted arithmetic still owes representation, target refinement and timing joins under its own reviewed scope.

## Acceptance predicate

The generation half is accepted only when:

1. The parent and every used nested source revision, own license files and intended distribution are recorded. The fixed proof switch is unchanged.
2. The recorded pinned generator is actually executed successfully for each named field; the manifest identifies its executable and build environment. Existing pre-generated upstream C alone is insufficient.
3. Two runs of each exact command produce identical raw bytes; the deterministic envelope produces the checked-in header bytes. The manifest and tracked outputs agree by hash.
4. The headers compile as the declared inclusion interface. Bounded arithmetic/serialization tests agree with an independent integer reference at representative edges. These checks establish a local artifact, not whole-curve correctness, constant-time target execution, WCET or backend refinement.
5. K-52/K-53 and the scoped artifact check pass. Any source change invalidates the recorded result and requires regeneration. Licensing/provenance records are integrated by the owner before item completion is recorded.

If the current generator cannot be built or run, record the exact failed tuple and command. The destination and acceptance contract remain an authored checkpoint; no emission or reproducibility result may be fabricated from the historical build, upstream checked-in output or a successful package installation.

## Current 2026-10-19 emission and replay

The selected parent `1e721c6f18c43b90922e7bc57fd64848e5cff2be` was archived
with its unchanged exact nested revisions and built in a fresh native tree.
The [build receipt](retained-evidence/dependencies-20261019/fiat/build.json)
records a successful locked Rocq 9.3.0 / OCaml 5.4.1 build in 1,130.5 seconds.
The [before and after export hashes](retained-evidence/dependencies-20261019/fiat/switch-exports.json)
match the unchanged proof lock. The generator executable has SHA-256
`eb983672439aa0ca1375f0760af5097ac09ceb0f4182062dcbe93a7de3c24389`.

Before building, restore the parent repository's Git index at that exact
revision in the unpacked tree. Upstream's `make_tactics.sh` enumerates tracked
Gallina imports with `git ls-files`; an archive without that index silently
loses imports. This build verifies all 4,092 archived regular files against
the post-build source bytes. The emitter requires the matching parent HEAD
and index and rejects any changed archived file before emission or replay.
The focused control reproduces a truncated generated import list and refuses it.

The [emission](retained-evidence/dependencies-20261019/fiat/emission.json)
and [replay](retained-evidence/dependencies-20261019/fiat/replay.json) each run
both recipes twice and reproduce the tracked headers. The current
[manifest](../../tools/generated/fiat-crypto/manifest.json) owns the raw and
wrapped hashes, exact archives, executable, recipes and emitter identity.
The [independent integer comparison](retained-evidence/dependencies-20261019/fiat/vectors.json)
passes all 6,786 operation results within its stated canonical-input scope.
It makes no divstep, target-refinement or timing claim.

The [independent source and build review](retained-evidence/dependencies-20261019/fiat/independent-review.json),
SHA-256 `ee01195bd9147dbb5bfe9eab9bbab3c6f46fa0770332d57154ba3ab4fec8f965`,
verifies the indexed source, all eleven archives and 4,092 source files, actual
build log, executable and unchanged proof-switch exports. Its fresh isolated
[second emission](retained-evidence/dependencies-20261019/fiat/independent-emission.json),
SHA-256 `f20b97d0c8a9ed30f459051fb363107fe4e3a8be3d0adfe5a6822ab8035cf0a8`,
executes each recipe twice and reproduces both wrapped headers. This identifies
the reviewed generator; it is not a second generator rebuild.

The [license receipt](retained-evidence/dependencies-20261019/fiat/licenses.json)
binds the parent and nested inputs to their own license instruments and verifies
every retained instrument digest against the actual build tree. No dependency
source, library, proof object or generator executable is incorporated.

## Reproduction procedure

Initialize the exact parent and nested gitlinks in an isolated source checkout. Archive each repository separately with `git -C <repository> -c core.autocrlf=false -c core.eol=lf archive --format=tar HEAD`, and unpack it at its recorded relative path into a fresh native build tree. Both overrides are required because host checkouts may have CRLF scripts. From the unpacked Fiat root, the successful command is:

```
opam exec --switch=verifiedos-rocq-9.3.0-ocaml-5.4.1 -- make -j2 SKIP_BEDROCK2=1 'COQC=/root/.opam/verifiedos-rocq-9.3.0-ocaml-5.4.1/bin/rocq c' standalone-unified-ocaml
```

The explicit `COQC` applies to recursive builds too. The manifest names the actual executable and the full build recipe; the environment binds the measured prover and OCaml versions to the current proof lock and both export hashes. The host inspector refuses missing or changed identities, a changed lock, unequal exports and a build recipe that does not use that compiler explicitly. A build receipt records an observed build rather than attesting that an arbitrary executable came from a claimed archive.

The selected [license receipt](retained-evidence/dependencies-20261019/fiat/licenses.json)
records the exact parent and nested instruments. Fiat-Crypto and Rewriter offer
MIT / Apache-2.0 / BSD-1-Clause, with Apache-2.0 elected. Coqprime's own instrument
is LGPL-2.1; Coqutil, Rupicola, Bedrock2, Kami and the coq-scripts copies carry MIT
terms; riscv-coq carries BSD-3-Clause. The generator, archives, libraries and proof
objects are external build inputs. Only the two generated field headers are
incorporated; no nested input's terms are inferred from another grant.

For a preserved or rebuilt generator, run these in the guest, replacing `<checkout>` and `<native>` with the assigned checkout and its native `/root/build` lane. Create the emission/replay directories before using them:

```
python3 <checkout>/tools/fiat_crypto_emit.py --emit --generator <native>/fiat-a/source/src/ExtractionOCaml/fiat_crypto --work-dir <native>/fiat-emit --source-receipt <native>/fiat-a/archives/manifest.json --build-receipt <native>/fiat-a/build-receipt.json
python3 <checkout>/tools/fiat_crypto_emit.py --check --generator <native>/fiat-a/source/src/ExtractionOCaml/fiat_crypto --work-dir <native>/fiat-check --source-receipt <native>/fiat-a/archives/manifest.json
python3 <checkout>/tools/fiat_crypto_vectors.py --work-dir <native>/fiat-vectors
```

The source receipt is a JSON array of `path`, full `revision` and sibling tar `archive` basename, in the tracked manifest's order; the driver hashes each archive itself. A fresh `--emit` requires a successful build receipt naming this source pin, executable and digest, the exact reviewed build command and the measured unchanged locked environment. A rebuilt executable with a different digest is refused by `--check` until its build provenance is reviewed. Generator binaries need not themselves be reproducible across build environments. Each run retains stdout and stderr under the caller's own native work directory.

The [vector receipt](retained-evidence/dependencies-20261019/fiat/vectors.json) records GCC 15.2.0 compiling the inclusion interface with `-std=c11 -O2 -Wall -Wextra -Werror -Wno-unused-function -shared -fPIC`. Each field passes 377 canonical-input pairs: the cross-product of 11 edges plus 256 reproducible pseudorandom pairs. Multiplication, squaring, addition, subtraction, negation, both selections, byte round trip and scalar-121666 multiplication or Montgomery one produce 3,393 checked results per field, 6,786 total, against Python integer arithmetic. P256's `divstep`, `divstep_precomp`, `msat` and `nonzero` routines remain outside that campaign; no target timing, constant-time execution, complete curve protocol or compiler-refinement claim follows.

The focused host tests reject altered/missing headers, an incomplete output set, the wrong parent pin, changed source archives, a non-sibling archive path, changed owner bytes, a missing generator path, the wrong prover or OCaml identity, a stale proof lock or export hash and a different build recipe. K-88 checks the host-readable record and hashes without running Fiat; native replay executes the recorded generator twice per recipe. The third-party ledger owns the incorporated source and license records. The retained JSON files contain original observations and identities, with no upstream source, compiled proof library or generator executable.
