# Fiat-Crypto emission contract

This document owns M3.4c-ii's derivation recipe, destination, licensing decision and acceptance predicate under R-05-060. The [implementation checklist](implementation-checklist.md) owns item completion; the [third-party ledger](../../THIRD-PARTY.md) owns incorporated upstream records.

## Destination and license decision

The selected generator is `mit-plv/fiat-crypto` at `e6946985c9165b3270eae457c0fae887cd7b7b76`, the exact `upstream/fiat-crypto` gitlink. Its own `COPYRIGHT` offers MIT, Apache-2.0 or BSD-1-Clause. This project elects Apache-2.0, as its existing ledger does. The selected revision's `LICENSE-APACHE` and `AUTHORS` were read before authoring this contract; generated output retains the upstream authors' notice and all notices emitted by the generator. The generator and its libraries are build-time inputs, not artifacts to distribute from this repository. Every nested dependency used to build it needs its own license receipt; no permission for a dependency is inferred from Fiat-Crypto's election.

Generated field routines belong under `tools/generated/fiat-crypto/` as C inclusion headers, with `// SPDX-License-Identifier: Apache-2.0` in the opening comment. The generator emits static/internal routines suitable for inclusion into a consuming translation unit. The `.h` suffix describes that interface and already has a K-52/K-53 comment-syntax ruling; it does not hide an unruled file kind. The provenance wrapper is an explicit reproducible transformation, not a claim that a wrapped header is byte-identical to raw stdout. No generated field arithmetic belongs in the modified Sail model, whose upstream bytes have their own BSD-2-Clause boundary and `-text -eol` rule. No checker exemption or license-map change is needed.

Each emitted header retains the raw generated body and prepends only the recorded SPDX, copyright, immutable source and command notice. A JSON manifest beside it carries the pin, nested revisions, invocation, generator identity, raw/wrapped hashes and verification results. A local original Python driver may reproduce/check the envelope; it must reject a different pin, missing generator, failed invocation or mismatching output. Generated code is not manually repaired. Raw stdout, stderr and toolchain/build logs remain under the assigned native lane; retained receipts identify them.

## Field and representation scope

The first recipe covers the two standard prime-field examples the selected upstream documents: `2^255 - 19` and `2^256 - 2^224 + 2^192 + 2^96 - 1`. These are explicit field-arithmetic artifacts, not a decision to admit any complete curve protocol or platform cipher suite. The selected 32-bit limb representation uses ordinary bounded-width C intermediates rather than requiring a new 128-bit primitive from the future purecap backend. Their host compilation is not a target refinement proof.

The intended generator commands are:

```
fiat_crypto unsaturated-solinas 25519 32 10 '2^255 - 19' carry_mul carry_square carry_scmul121666 carry add sub opp selectznz to_bytes from_bytes
fiat_crypto word-by-word-montgomery p256 32 '2^256 - 2^224 + 2^192 + 2^96 - 1'
```

The exact executable path, flags and all output transformations are frozen by the recorded successful recipe, rather than inferred from these examples. A second party must build or identify the generator at the recorded parent and nested revisions, run each invocation twice, and compare byte-for-byte raw and wrapped output hashes. A historical binary built at `5691ca0d` cannot witness generation at the current pin.

## Acceptance predicate

The generation half is accepted only when:

1. The parent and every used nested source revision, own license files and intended distribution are recorded. The fixed proof switch is unchanged.
2. The recorded pinned generator is actually executed successfully for each named field; the manifest identifies its executable and build environment. Existing pre-generated upstream C alone is insufficient.
3. Two runs of each exact command produce identical raw bytes; the deterministic envelope produces the checked-in header bytes. The manifest and tracked outputs agree by hash.
4. The headers compile as the declared inclusion interface. Bounded arithmetic/serialization tests agree with an independent integer reference at representative edges. These checks establish a local artifact, not whole-curve correctness, constant-time target execution, WCET or backend refinement.
5. K-52/K-53 and the scoped artifact check pass. Any source change invalidates the recorded result and requires regeneration. Licensing/provenance records are integrated by the owner before item completion is recorded.

If the current generator cannot be built or run, record the exact failed tuple and command. The destination and acceptance contract remain an authored checkpoint; no emission or reproducibility result may be fabricated from the historical build, upstream checked-in output or a successful package installation.
