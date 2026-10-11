# Fiat-Crypto emission contract

This document owns M3.4c-ii's derivation recipe, destination, licensing decision and acceptance predicate under R-05-060. The [implementation checklist](implementation-checklist.md) owns item completion; the [third-party ledger](../../THIRD-PARTY.md) owns incorporated upstream records.

## Destination and license decision

The selected generator is `mit-plv/fiat-crypto` at `f3ecb2cf1f771de34771e967193ee7f0ee0b0acf`, the exact `upstream/fiat-crypto` gitlink. Its own `COPYRIGHT` offers MIT, Apache-2.0 or BSD-1-Clause. This project elects Apache-2.0, as its existing ledger does. The selected revision's `LICENSE-APACHE` and `AUTHORS` were read before incorporating its output; generated output retains the upstream authors' notice and all notices emitted by the generator. The generator and its libraries are build-time inputs, not artifacts to distribute from this repository. Every nested dependency used to build it needs its own license receipt; no permission for a dependency is inferred from Fiat-Crypto's election.

Generated field routines belong under `tools/generated/fiat-crypto/` as C inclusion headers, with `// SPDX-License-Identifier: Apache-2.0` in the opening comment. The generator emits static/internal routines suitable for inclusion into a consuming translation unit. The `.h` suffix describes that interface and already has a K-52/K-53 comment-syntax ruling; it does not hide an unruled file kind. The provenance wrapper is an explicit reproducible transformation, not a claim that a wrapped header is byte-identical to raw stdout. No generated field arithmetic belongs in the modified Sail model, whose upstream bytes have their own BSD-2-Clause boundary and `-text -eol` rule. No checker exemption or license-map change is needed.

Each emitted header retains the raw generated body and surrounds it with the recorded SPDX, copyright, immutable-source notice and C inclusion guard. The generator body carries its exact command. A JSON manifest beside it carries the pin, nested revisions and source-archive hashes, invocation, generator identity and raw/wrapped hashes; the companion vector receipt records verification results. A local original Python driver may reproduce/check the envelope; it must reject a different pin, missing generator, failed invocation or mismatching output. Generated code is not manually repaired. Raw stdout, stderr and toolchain/build logs remain under the assigned native lane; retained receipts identify them.

## Field and representation scope

The first recipe covers the two standard prime-field examples the selected upstream documents: `2^255 - 19` and `2^256 - 2^224 + 2^192 + 2^96 - 1`. These are explicit field-arithmetic artifacts, not a decision to admit any complete curve protocol or platform cipher suite. The selected 32-bit limb representation uses ordinary bounded-width C intermediates rather than requiring a new 128-bit primitive from the future purecap backend. Their host compilation is not a target refinement proof.

The intended generator commands are:

```
fiat_crypto unsaturated-solinas 25519 32 10 '2^255 - 19' carry_mul carry_square carry_scmul121666 carry add sub opp selectznz to_bytes from_bytes --static
fiat_crypto word-by-word-montgomery p256 32 '2^256 - 2^224 + 2^192 + 2^96 - 1' --static
```

The exact executable path, flags and all output transformations are frozen by the recorded successful recipe, rather than inferred from these examples. A second party must build or identify the generator at the recorded parent and nested revisions, run each invocation twice, and compare byte-for-byte raw and wrapped output hashes. A historical binary built at `5691ca0d` cannot witness generation at the current pin.

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

## Recorded emission and replay

Option A's entry tip, `f3ecb2cf1f771de34771e967193ee7f0ee0b0acf`, builds from fresh Git archives with the locked Rocq 9.3.0 compiler and OCaml 5.4.1. The [build receipt](retained-evidence/fiat-q40-20261010/build-receipt.json) records the successful command, compiler output, executable identity, source pin and observed proof-object counts. The cold build exited 0 in 931.98 s. Nothing was installed into the proof switch. Its [before and after exports](retained-evidence/fiat-q40-20261010/switch-exports.json) are byte-identical to each other and to [rocq.lock](../../tools/opam/rocq.lock), SHA-256 `3e70338fb77832f9e09ee8780cd10524e002420b1ca9aa5f56a15777765e1b32`. Option B is unnecessary because A succeeded.

The [manifest](../../tools/generated/fiat-crypto/manifest.json) binds the parent, every nested archive, exact recipes, current emitter, executable and build environment. The generator executable has SHA-256 `3f34a8230b5112c33889d6b8d01adb2724bf474888197ed2523519bab3572812`. Two executions of each recipe produced identical raw bytes. A subsequent `--check` ran each recipe twice again in a separate native work directory and reproduced the tracked header bytes with its source-archive comparison holding. The raw hashes equal the prior emission's recorded hashes; only the wrapper's source-pin notice changes in the headers. The [emission receipt](retained-evidence/fiat-q40-20261010/emission.json) identifies each actual invocation and its raw stdout/stderr files and hashes.

| Header | Raw SHA-256 | Wrapped SHA-256 |
| --- | --- | --- |
| `25519_32.h` | `0600b8d461d3bf94199efced49097c7682623ed27a4c146d7dde103859338ef0` | `b200b3ce50fd2020fe1d8e8dd7f2b258e08ad3bc2a1b2bcef7d72ab07afa96f6` |
| `p256_32.h` | `1cce0302f067c020553c06eae6547430bd6f1ff8d9198cd1258de2c8888ea0ca` | `0b865a4c6be783e00827a3aaaa79619153053cfa5f0f6a985f479c85bd46ed54` |

Initialize the exact parent and nested gitlinks in an isolated source checkout. Archive each repository separately with `git -C <repository> -c core.autocrlf=false -c core.eol=lf archive --format=tar HEAD`, and unpack it at its recorded relative path into a fresh native build tree. Both overrides are required because host checkouts may have CRLF scripts. From the unpacked Fiat root, the successful command is:

```
opam exec --switch=verifiedos-rocq-9.3.0-ocaml-5.4.1 -- make -j2 SKIP_BEDROCK2=1 'COQC=/root/.opam/verifiedos-rocq-9.3.0-ocaml-5.4.1/bin/rocq c' standalone-unified-ocaml
```

The explicit `COQC` applies to recursive builds too. The manifest names the actual executable and the full build recipe; the environment binds the measured prover and OCaml versions to the current proof lock and both export hashes. The host inspector refuses missing or changed identities, a changed lock, unequal exports and a build recipe that does not use that compiler explicitly. A build receipt records an observed build rather than attesting that an arbitrary executable came from a claimed archive.

The [license receipt](retained-evidence/fiat-q40-20261010/licenses.json) names each actual own file read on 2026-10-10 at the manifest's exact revisions and hashes its LF archive bytes. The generator, source archives, libraries and proof objects are external build inputs; only the two Fiat-generated field headers are incorporated.

| Nested input | Own license reading and use |
| --- | --- |
| `coqprime` | `LICENSE`: LGPL-2.1; 23 native proof objects built. No Coqprime source or binary is copied into the headers or distributed here. |
| `rewriter` | `COPYRIGHT`, `LICENSE-APACHE`, `AUTHORS`: MIT / Apache-2.0 / BSD-1-Clause election, Apache-2.0 selected; 147 native proof objects. |
| `rupicola/bedrock2/deps/coqutil` | `LICENSE` offers MIT and `AUTHORS` identifies its authors; 125 native proof objects. The containing Rupicola and Bedrock2 revisions' own `LICENSE` files offer MIT and their `AUTHORS` files were also read; no objects outside Coqutil were built under those trees. |
| `etc/coq-scripts` and its Rewriter/Coqutil copies | Each exact revision's own `LICENSE` is MIT, copyright 2014 Jason Gross. |
| `rupicola/bedrock2/deps/kami` | Its changed revision's own `LICENSE` is MIT, copyright CSAIL, Massachusetts Institute of Technology. It contributes no native proof object under `SKIP_BEDROCK2=1`. |
| `rupicola/bedrock2/deps/riscv-coq` | Its changed revision's own `LICENSE.txt` is BSD-3-Clause, copyright MIT. It contributes no native proof object under this target. |

Fiat's own `COPYRIGHT`, `LICENSE-APACHE` and `AUTHORS` were also read at the new parent, with Apache-2.0 elected and all emitted notices retained. No license for one nested input is inferred from another's grant.

For a preserved or rebuilt generator, run these in the guest, replacing `<checkout>` and `<native>` with the assigned checkout and its native `/root/build` lane. Create the emission/replay directories before using them:

```
python3 <checkout>/tools/fiat_crypto_emit.py --emit --generator <native>/fiat-a/source/src/ExtractionOCaml/fiat_crypto --work-dir <native>/fiat-emit --source-receipt <native>/fiat-a/archives/manifest.json --build-receipt <native>/fiat-a/build-receipt.json
python3 <checkout>/tools/fiat_crypto_emit.py --check --generator <native>/fiat-a/source/src/ExtractionOCaml/fiat_crypto --work-dir <native>/fiat-check --source-receipt <native>/fiat-a/archives/manifest.json
python3 <checkout>/tools/fiat_crypto_vectors.py --work-dir <native>/fiat-vectors
```

The source receipt is a JSON array of `path`, full `revision` and sibling tar `archive` basename, in the tracked manifest's order; the driver hashes each archive itself. A fresh `--emit` requires a successful build receipt naming this source pin, executable and digest, the exact reviewed build command and the measured unchanged locked environment. A rebuilt executable with a different digest is refused by `--check` until its build provenance is reviewed. Generator binaries need not themselves be reproducible across build environments. Each run retains stdout and stderr under the caller's own native work directory.

The [vector receipt](retained-evidence/fiat-q40-20261010/vectors.json) records GCC 15.2.0 compiling the inclusion interface with `-std=c11 -O2 -Wall -Wextra -Werror -Wno-unused-function -shared -fPIC`. Each field passes 377 canonical-input pairs: the cross-product of 11 edges plus 256 reproducible pseudorandom pairs. Multiplication, squaring, addition, subtraction, negation, both selections, byte round trip and scalar-121666 multiplication or Montgomery one produce 3,393 checked results per field, 6,786 total, against Python integer arithmetic. This equals the prior recorded campaign's count. P256's `divstep`, `divstep_precomp`, `msat` and `nonzero` routines remain outside that campaign; no target timing, constant-time execution, complete curve protocol or compiler-refinement claim follows.

The focused host tests reject altered/missing headers, an incomplete output set, the wrong parent pin, changed source archives, a non-sibling archive path, changed owner bytes, a missing generator path, the wrong prover or OCaml identity, a stale proof lock or export hash and a different build recipe. K-88 checks the host-readable record and hashes without running Fiat; native replay executes the recorded generator twice per recipe. The third-party ledger owns the incorporated source and license records. The retained JSON files contain original observations and identities, with no upstream source, compiled proof library or generator executable.

The [independent replay receipt](retained-evidence/fiat-q40-20261010/independent-replay.json),
SHA-256 `39fb3074b3b530356b85b1d4063effff95c7f6be83fd1ef61ff1acb0753170b2`,
records a second dedicated checkout at `82457550eb0d011290fc96583122a8769e0171a2`.
It identifies the same generator by digest, runs each recipe twice in
`/root/build/lane-checklist-20261010-d/fiat-independent`, and reproduces every
header byte with the source-archive comparison holding. The worker's subsequent
receipt-path amendment changes no generator, driver, recipe or header input.
This is an independent second emission, not an independent generator rebuild.
