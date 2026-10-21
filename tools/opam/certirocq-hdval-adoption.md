# CertiRocq bootstrap header backport

This contract adopts the header-boundary fix merged in
[CertiRocq PR 167](https://github.com/CertiRocq/certirocq/pull/167) for the
[Wasm oracle](../wasm-oracle/README.md). Commit the contract before building
the candidate. The qualified production snapshot remains the owner until the
acceptance below passes.

## Selected inputs and boundary

Keep CertiRocq release `v0.9.1+9.1`, source revision
`49cd1c23b74678d36f7f37412a5c1ce6d00f41d2`, and every package version in
[certirocq.lock](certirocq.lock), including Rocq 9.1.1 and OCaml 4.14.4.
Backport only the four bootstrap C-file changes in upstream commit
`971c1eb1b5f0adecfc280872bd5b71b0d7f33a0f`, merged as
`8e3a943a8b5ea7c9b2d098818fda8d6dfd5b2939`.
The immutable [commit patch](https://github.com/CertiRocq/certirocq/commit/971c1eb1b5f0adecfc280872bd5b71b0d7f33a0f.patch)
has SHA-256 `f350152fd710608b912e9584ae6ef2a005fb8f7d2fc8b7b1e4b15911c9de109b`.
It inserts a comment and `#undef Hd_val` before OCaml headers in each of
the two native bootstraps' wrapper and print translation units. No Gallina,
OCaml, Wasm backend, collector or standalone runtime source may change.
Reject an unexpected patch target, fuzzy application, changed package version
or other source difference.

The selected release archive keeps its recorded SHA-512
`9ef925f78e399c6d8a6bf8f78023157786eccc59ea4673c06a09317cb391310e95d29b8d47e0524d99b09753c7436fcf05954ec74c247dff959fc7193ea87d5f`.
The release and merge's root MIT instrument was read, as were the four target
files, which state no separate terms. Its SHA-256 is
`136a03804522ebaa80a74f76798083823ad4d81016d03d60c60f7cb90cb38aaf`.
The source archive's other file-specific terms remain applicable under
[the third-party record](../../THIRD-PARTY.md#development-tools-contained-by-use).
All source, compilation and oracle execution remain local; no upstream source,
compiled library or generated executable is distributed by this adoption.

An OCaml upgrade is separate work: the existing `ocaml-compiler-libs` release
excludes OCaml 5.2 and later. The stopped
[Rocq 9.3 trial](certirocq-compatibility.md#native-trial-verdict) is also separate.
Neither is resumed by adopting this C-header fix.

## Qualification and adoption

Use private native roots and build directories, preserving existing switches
and their exports. Bind source archives, package metadata and the patch by
digest. Build the complete selected package closure and both native
bootstraps with the package's original settings. Do not execute upstream full
test suites or benchmarks locally.

Compile the unchanged `demo.v`, `EndpointIPC.v` and `ipc_oracle.v` consumers.
Require the demo and original 84 IPC checks to answer true in the existing
kernel/Wasm forms, and the mask-boundary negative to answer false with a
nonzero runner exit. Recursively kernel-check the consumer roots and compare
each constant's exact assumptions against the qualified baseline; an
unexplained difference refuses adoption. Record the source boundary and all
command outcomes. Header compatibility controls may compile the four bridge
files against other already-installed OCaml headers without selecting those
compilers for production.

Export an actual successful switch with its explicit OCaml compiler invariant
and portable, frozen package metadata carrying the checksummed release and
upstream patch. Import it into another empty private root, repeat the consumer,
kernel and assumption checks, and require a byte-identical re-export.
Reissue the [complete-vector comparison](../wasm-oracle/README.md#the-purecap-counterpart-ipc_oraclec-m12f)
against the qualified contained compiler and source-bound emulator: all 84
positions, both mask mutants, both crossed comparisons and every
single-position corruption control. Keep raw outcomes and identities.

Only successful acceptance permits updating the snapshot, oracle owner,
native/container recipes, third-party record and upstream tracker together.
Declared-environment recognition must distinguish the backported package's
source/patch provenance from an unpatched package with the same version.
The backport retires when a released source includes the fix and passes the
same consumer acceptance. Stop on an unexpected source, version, statement,
assumption or behavior change and retain the refusal instead of publishing a
replacement snapshot.

Host CI must pass for the settled `main` revision and every Guest CI lane must
be dispatched without waiting for its verdict. The local-only
[instrument constraint](../ci/README.md#instrument-switch-route) remains in
force; neither hosted workflow supplies this oracle's acceptance evidence.
