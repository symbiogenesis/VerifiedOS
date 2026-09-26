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

Use the [pinned lowering switch](README.md#pinned-environment) and M1.2f's accepted
contained compiler and source-bound model snapshot. All generated C, proof objects,
images, logs and receipts stay under the selected native lane. For example, from
the assigned Windows checkout:

```console
python tools/bedrock2-lowering/hello.py --stage /root/build/lane-<lane>/hello \
  --ccomp /root/build/lane-backend-accept-20260925/compiler-final/ccomp \
  --config /root/build/lane-compiler-accept-20260925/component-vector-integrated/compcert.ini \
  --simulator /root/build/lane-compiler-accept-20260925/model-snapshot/sail_riscv_sim \
  --model-receipt /root/build/lane-compiler-accept-20260925/model-snapshot/model-build.json \
  --check --controls
python tools/run.py model corpus gallina-hello
```

The second command uses the model installed in that checkout's lane. The first
accepts a separately retained snapshot only after matching its successful build
receipt, executable digest and complete current model-file population. It binds
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
