# Purecap Gallina hello-world

[HelloWorld.v](HelloWorld.v) defines the greeting's character function in Gallina,
derives Bedrock2 through Rupicola, and prints C. The derived functional relation
ends at Bedrock2. The printed C function is retained verbatim, with its unused
Bedrock2 preamble excluded, and joined to the authored [C harness](hello_harness.c).
The contained compiler's accepted typed route emits only those two client functions.
No compiler source, runtime, external helper or library code is included in the
[generated corpus member](../../corpus/gallina-hello.s).

The harness stores pointers into a dedicated image-data array, reads each pointer
back, and uses it to read and write its value. The corpus wrapper checks every
greeting character and prints the actual values through HTIF. It clears `gp` on
success. The native trace check requires every image-data pointer slot to have
an aligned tagged store and an intact tagged reload; automatic call-frame saves
cannot satisfy this check. Overlapping writes invalidate pending stored values.

## Reproduction

Use the [pinned lowering switch](README.md#pinned-environment), Q39's locked
contained compiler and a current source-bound model simulator. All generated C, proof objects,
images, logs and receipts stay under the selected native lane. For example, from
the assigned Windows checkout:

```console
python tools/bedrock2-lowering/hello.py --stage /root/build/lane-<lane>/hello \
  --ccomp /root/build/fanout-retained/0acbb4e6d7d797594b4f/checklist-20261010-c/lane/q39/final-build-1/compiler/ccomp \
  --config /root/build/fanout-retained/0acbb4e6d7d797594b4f/checklist-20261010-c/lane/q39/final-build-1/compiler/compcert.ini \
  --simulator /root/build/fanout-retained/0acbb4e6d7d797594b4f/checklist-20261010-c/lane/q39/simulator-dependency-2/build/c_emulator/sail_riscv_sim \
  --model-receipt /root/build/fanout-retained/0acbb4e6d7d797594b4f/checklist-20261010-c/lane/q39/simulator-dependency-2/simulator-build.json \
  --check --controls
```

The retained path is finalized by the `checklist-20261010` fanout journal; native
execution receipts keep their original lane paths. The selected compiler digest is
`3dae6ac7bd5a074053130fdcaaab84c42030bdc24be9fff6a4b244db272252f8`.
Its successful clean-build receipt and source manifest bind the released
[contained toolchain lock](../opam/contained-compiler.lock), actual prover,
OCaml and Menhir versions and executable hashes.

The recipe accepts a separately retained simulator only after matching its
successful build receipt, executable digest and complete current model-file population.
A complete model receipt requires successful configure, build and bundled `ctest`
stages. Q39's distinct focused receipt requires successful configure and the explicit
simulator target build, exact source and producer identities, and profile validation;
it records bundled tests as not run and full model acceptance as pending. General
target readers retain their complete-build contracts. To produce another current
focused dependency in the assigned checkout's lane:

```console
python tools/run.py model simulator --out /root/build/lane-<lane>/q39/simulator-dependency
```

The recipe binds
the original source closure, lowering lock, installed prover and complete Rocq
library trees, compiler, preprocessed C, compiler configuration, model receipt,
assembly, image and trace. Source and producer identities are checked again before
publishing `result.json`. `--check` compares regenerated assembly byte-for-byte with
the tracked member. `--export` intentionally replaces that member after a reviewed
input change; its new trace measurements also require a corpus manifest update.

Run the same command from a second isolated checkout with another native stage,
then compare `assembly_sha256` and `image_sha256` in the two receipts. Repeating
within one checkout establishes no independent-lane reproduction.

`--controls` assembles and executes three altered clients: an incorrect first
character, an integer store that strips a client pointer's tag, and a deleted
client pointer store. Each must execute and fail its declared check or trap.
These are detected compiling mutants; they are not compilation refusals.
`python tools/run.py test --only hello_world` exercises stale, damaged, untagged,
malformed and frame-only trace controls and refusal of runtime-dependent C extraction.

The receipt is finite execution evidence. It proves no C-printer correctness,
compiler simulation, source-to-binary refinement, secure compilation or hardware
refinement. M1.2f owns the accepted backend/component campaign; this image reuses
that prerequisite without repeating or broadening it.
