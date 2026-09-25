# Fiat-Crypto emission contract

This document owns M3.4c-ii's derivation recipe, destination, licensing decision and acceptance predicate under R-05-060. The [implementation checklist](implementation-checklist.md) owns item completion; the [third-party ledger](../../THIRD-PARTY.md) owns incorporated upstream records.

## Destination and license decision

The selected generator is `mit-plv/fiat-crypto` at `e6946985c9165b3270eae457c0fae887cd7b7b76`, the exact `upstream/fiat-crypto` gitlink. Its own `COPYRIGHT` offers MIT, Apache-2.0 or BSD-1-Clause. This project elects Apache-2.0, as its existing ledger does. The selected revision's `LICENSE-APACHE` and `AUTHORS` were read before authoring this contract; generated output retains the upstream authors' notice and all notices emitted by the generator. The generator and its libraries are build-time inputs, not artifacts to distribute from this repository. Every nested dependency used to build it needs its own license receipt; no permission for a dependency is inferred from Fiat-Crypto's election.

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

For a future field or code construction, make the finite representation explicit: a prime `p`, and, for an extension, an irreducible defining polynomial over `F_p`. Supply checked finite primality/irreducibility evidence and prove any factorization output reconstructs the input with the claimed multiplicities and irreducible factors. A reducible defining polynomial, a composite modulus or an omitted repeated factor is a useful negative witness. The March 2026 structured factorization progress for Reed-Solomon decoding only applies after proving its particular input structure; general deterministic `poly(d,log q)` factorization remains open. The [decoder proof handoff](../assurance/proof-reuse/hardware.md#research-handoff-for-future-code-and-decoder-proofs) owns the subsequent code-specific bridge.

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

The selected generator was built and executed for both recipes. The destination and acceptance decision was committed before this work. The tracked [manifest](../../tools/generated/fiat-crypto/manifest.json) binds the parent, all nested source archives, generator executable, build command and both raw and wrapped outputs. The generator executable has SHA-256 `0c165961c4fb496a843b5dfd411e9356c835897e0944aff48891ebacb1f8ee3a`. Two executions of each recipe produced identical raw bytes; the tracked headers reproduce through the original [emission driver](../../tools/fiat_crypto_emit.py).

| Header | Wrapped SHA-256 |
| --- | --- |
| `25519_32.h` | `65d3a1a45457f912872c3977d7ee0e53363050a62f14a1b4c425fffc7c50b6c6` |
| `p256_32.h` | `f332877f11b8569e950616bccb75aaa5dd2fc81e8e976669196f0e3ba5116ab8` |

Initialize the exact gitlink and its nested gitlinks in an isolated checkout. Archive each source repository separately with `git -C <repository> -c core.autocrlf=false -c core.eol=lf archive --format=tar HEAD`, and unpack them at their recorded relative paths into the native lane's build tree. Both configuration overrides matter: the host's global EOL setting otherwise produced CRLF in generator scripts. No source change was needed. The successful native build, from the unpacked Fiat root, was:

```
opam exec --switch=verifiedos-rocq-9.2.0-ocaml-5.4.1 -- make -j2 SKIP_BEDROCK2=1 'COQC=/root/.opam/verifiedos-rocq-9.2.0-ocaml-5.4.1/bin/rocq c' standalone-unified-ocaml
```

The explicit `COQC` also applies to recursive Coqprime builds. An initial recursive build used the ambient 8.20 compiler and was correctly refused when its objects reached Rocq 9.2; the affected native build objects were removed and rebuilt with the explicit compiler. The successful resumed build took 681.59 s after the earlier partial build. This is an external build, not an installation into the proof switch. Its before/after package exports are byte-identical.

The build consumed Fiat, Rewriter, Coqprime and Coqutil proofs and the nested build scripts. The following own license files were read at the manifest's revisions. These libraries and generator binaries remain external build inputs; only the two Fiat-generated field headers are incorporated.

| Nested input | Own license reading and use |
| --- | --- |
| `coqprime` | `LICENSE`: LGPL-2.1; 23 native proof objects built for generation. No Coqprime source or binary is copied into the headers or distributed here. |
| `rewriter` | `COPYRIGHT`, `LICENSE-APACHE`, `AUTHORS`: MIT / Apache-2.0 / BSD-1-Clause choice, Apache-2.0 elected; 147 native proof objects. |
| `rupicola/bedrock2/deps/coqutil` | `LICENSE`: MIT; 132 native proof objects. The containing Rupicola and Bedrock2 revisions' own LICENSE files are also MIT. No Rupicola or Bedrock2 proof objects outside Coqutil were built by this target. |
| `etc/coq-scripts` and its Rewriter/Coqutil copies | Each selected revision's own LICENSE is MIT, copyright 2014 Jason Gross. The manifest distinguishes the two script revisions. |
| Nested Kami and riscv-coq | Present at their recorded source pins because recursive gitlinks were archived; neither contributed a native proof object under `SKIP_BEDROCK2=1`. No incorporation or license election for them is claimed. |

For a preserved or rebuilt generator, run the following from the guest, replacing the explicit lane paths with the new assigned native lane and its source checkout:

```
python3 <checkout>/tools/fiat_crypto_emit.py --check --generator <native>/fiat-git-bytes/src/ExtractionOCaml/fiat_crypto --work-dir <native> --source-receipt <checkout>/out/fiat-archives/manifest.json
python3 <checkout>/tools/fiat_crypto_vectors.py --work-dir <native>/fiat-vectors
```

The source receipt is a JSON array of `path`, full `revision` and sibling tar `archive` basename, in the tracked manifest's order; the driver hashes those archives itself. The archived recovery receipt and `archive-fiat.py` preserve the exact archive operation. The optional source-receipt argument adds archive identity checking; without it, `--check` still checks the generator hash, recipes and every header byte after running each recipe twice. A different rebuilt executable is refused until its build provenance is reviewed; generator binaries need not themselves be reproducible across build environments. To record an approved fresh emission, `--emit` additionally requires `--build-receipt` containing the successful command and exit status. This receipt records an observed build, not a proof that an arbitrary executable came from a claimed source archive.

The native C harness compiled the inclusion headers with GCC 15.2.0 (`-std=c11 -O2 -Wall -Wextra -Werror -Wno-unused-function -shared -fPIC`). Each field passed 377 canonical-input pairs: the cross-product of 11 edges plus 256 reproducible pseudorandom pairs. Multiplication, squaring, addition, subtraction, negation, both selections, byte round trip and scalar-121666 multiplication or Montgomery one produced 3,393 checked results per field, 6,786 total, against Python integer arithmetic. P256's emitted `divstep`, `divstep_precomp`, `msat` and `nonzero` routines were not exercised by these vectors. No target timing, constant-time execution, complete curve protocol or compiler-refinement claim follows.

The focused host tests reject altered/missing headers, an incomplete output set, the wrong parent pin, changed source archives and a non-sibling archive path. The retained build, generation, vector and environment receipts live in the recovery lane's `out/qualification-evidence/` with their own hash manifest; native build logs remain under `/root/build/lane-recover-qualification-20260914`. K-88 binds the indexed Fiat pin, nonempty source identities, emitter source, exact recipes/output set and raw/wrapped hashes; malformed or stale records are findings without automatic repair. It checks host-readable provenance, not a binary build attestation. The third-party ledger records the incorporation. An independent integration lane identified the same generator by SHA-256, ran both recipes twice in its own native work directory and reproduced all header bytes. This is a second emission, not an independent generator rebuild. The scoped host tests also refuse missing or changed owner records, generator/build identity and stale driver bytes.
