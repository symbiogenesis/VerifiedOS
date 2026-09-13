# An emitted-instruction census for two frame-service variants

This host artifact answers one reachable part of the *bytes-versus-work* item in
the [static-memory research agenda](../background/static-memory-research.md):
what the frame service's pure value kernel costs in emitted instructions when
two of its variants are lowered through a real compilation route rather than
counted in an interpreter. It is research, not normative. The
[requirements register](../requirements-register.md) remains authoritative, and
nothing here confers landing credit or accepts a requirement. The item stays
open under its full acceptance conditions.

## What is measured, and by which commands

The census runs over the existing [Bedrock2 lowering loop](../../tools/bedrock2-lowering/README.md),
whose route is Gallina to bedrock2 by Rupicola's relational compilation, bedrock2
to C by bedrock2's printer, and C to assembly by the contained CompCert of the
compiler milestone's lane. Two derivations of one kernel are added to that
directory and put through the same driver:

```console
python tools/bedrock2-lowering/regenerate.py --stage <guest stage> \
    --source tools/bedrock2-lowering/FrameKernelRetained.v \
    --function frame_kernel_retained --ccomp /root/build/secomp-m12/ccomp
python tools/bedrock2-lowering/regenerate.py --stage <guest stage> \
    --source tools/bedrock2-lowering/FrameKernelInPlace.v \
    --function frame_kernel_inplace --ccomp /root/build/secomp-m12/ccomp
python tools/bedrock2-lowering/regenerate.py --stage <guest stage> \
    --source tools/bedrock2-lowering/FrameKernelInPlace.v \
    --function frame_kernel_inplace --check
```

Every figure the run reports lives in
[DIGESTS.md](../../tools/bedrock2-lowering/DIGESTS.md), which records the digest,
size and line count of each emitted C file and the plain-RV64 census of each
assembly file, and in that directory's
[measurements table](../../tools/bedrock2-lowering/README.md#measurements). This
document keeps no second copy of any of them. `--check` recomputes the digests
and exits nonzero on drift, which is what makes the emitted C reproducible
rather than merely present.

The kernel is [the transformation experiment's](static-memory-transformations.md)
own value contract: each input byte is mapped by an affine function modulo 256,
the mapped values are reduced to a checksum modulo 256, and each mapped value is
combined with that checksum. The two derivations differ in exactly one place.
[FrameKernelRetained.v](../../tools/bedrock2-lowering/FrameKernelRetained.v)
reads the input buffer and writes the mapped values into a second buffer, which
is the shape a borrowed input forces and the assumption the `lexical-cache` row
of the transformation experiment keeps.
[FrameKernelInPlace.v](../../tools/bedrock2-lowering/FrameKernelInPlace.v)
overwrites each element after it has been read and runs its second pass over the
same buffer, which is the `in-place-phased` row and is legal only because that
experiment's service owns its input exclusively.

Each derivation closes at `Qed` with `Print Assumptions` reporting
`Closed under the global context`, and neither file contains an `Admitted`. What
that theorem states is the relation between the Gallina function and the
bedrock2 function, and no more: the printer from bedrock2 to C carries no
theorem, as the lowering loop's own boundary table records. Each file also
carries three `Example` commands checking its loop against a plain list-level
reference on concrete frames. Those are bounded executable agreement, closed by
computation; no lemma in either file relates the loop to that reference at every
input, and none is claimed.

## What is not measured

**An image size is not reachable by any path in this tree**, and the census is
not a proxy for one. No tool here consumes a C compiler's output into an image:
[vos/asm.py](../../tools/vos/asm.py) reads this repository's own assembly
dialect and [vos/image.py](../../tools/vos/image.py) is not the composer that
M1.2f joins. The *code-size growth* the research item asks for therefore remains
unanswered, and an assembly instruction count is not a substitute for it.

**The target is wrong, by construction.** The contained `ccomp` reaches the
stock RISC-V backend and emits plain RV64 with the capability arms stubbed.
[R-18-002](../requirements-register.md) forbids a plain-RV64 compilation target
anywhere on this platform, so every figure in this census is a proxy taken on a
target the platform does not admit. The `-dcapasm` stub count that the loop also
records is the size of the gap to the backend M1.2b through M1.2f author, not a
property of either kernel.

**No capability code is produced or measured.** Every address in the emitted C
is integer arithmetic on the buffer parameter, passed through bedrock2's own
load and store primitives, because bedrock2's memory is a map from words to
bytes and its load takes a word. Provenance, bounds and tags are absent from the
emitted text, and the separation that says the two buffers of the retained
variant do not overlap lives in the Gallina specification and stops at the
bedrock2 function.

**The service's own charges are outside the kernel.** There is no descriptor, no
staging buffer, no reservation, no retirement, no zeroization and no allocator
in either derivation; both buffers belong to the caller. The byte ledger that
the transformation experiment reports is therefore not comparable with anything
here, and this census neither confirms nor refutes it.

**No deadline, worst-case execution time, bandwidth or power figure is taken.**
An instruction count is not a cycle count on any machine, and nothing here
executes on a target model. The timings the loop records are wall-clock prover
times on a shared host and decide nothing.

## What the census shows

The two variants emit the same program. Their C differs at the function
prototype and at the address expressions of the first loop's store and of the
second loop's two accesses, and at no other line; their assembly differs by the
second pointer's prologue spill and by nothing in either loop body. The retained
variant is the one that emits more, and the whole of what it emits more is that
spill: the second buffer's addressing costs no extra instruction inside the
loop, because the store's address is recomputed from its base at every iteration
in both variants and the printer knows nothing about the in-place variant's
aliasing. The two `-dcapasm` terms carry the same stubbed arms, so neither
variant is nearer a capability target than the other.

The two variants' live-array counts do differ, and they differ as the
transformation experiment models them: the retained kernel keeps two buffers
live across both loops and the in-place kernel keeps one. On this route that
difference is a storage difference only. **This is a measured outcome of one
kernel at one size on one route, and it is not a general result.** A fused
variant, a different element type, a vectorizing backend or a compiler that
proves non-aliasing could each move it.

**One new conjecture, labelled as such.** The reading above suggests that the
in-place transformation's advantage is a reservation advantage rather than a
work advantage, and that a capability backend would not convert the live-array
difference into an instruction difference, because the difference never reaches
the loop body. Nothing here proves that. It is a conjecture about a backend
that does not yet exist, and the evidence against it would be an emitted-code
comparison on that backend.

The census is also *per program and not per length*. Both derivations take the
length as a runtime argument and emit two counted loops, so no figure in their
rows moves with the frame size. The transformation experiment's schedule is
unrolled at a public length and its abstract instruction count grows with that
length. The two counts are therefore not two measurements of one quantity, and
reading one as a check on the other is a mistake this document exists partly to
prevent.

Nothing in this census is transferred from a publication. Every figure is a
measured outcome of the commands above on this machine; the two compiled
correctness statements are machine-checked in the pinned switch; the paragraph
above is the only conjecture; and no percentage, benchmark or result from any
external paper is carried into it.

## Licence facts for the route

These are the terms [THIRD-PARTY.md](../../THIRD-PARTY.md) records, read at the
route rather than restated from lineage.

| Component | Terms | How this repository stands to it |
| --- | --- | --- |
| Rupicola, Bedrock2 and the Bedrock2 compiler | MIT | Released packages in a dedicated opam switch; the emitted C is not tracked, because bedrock2's printer prepends its own preamble, which is bedrock2's text under bedrock2's terms |
| coqutil | MIT | Bedrock2 dependency in the same switch |
| CompCert through SECOMP | INRIA Non-Commercial License Agreement, with dual-licensed subsets and reciprocal distribution conditions | A contained external build-time producer that is not distributed here; the grant is limited to educational, research or evaluation use, and commercial use requires a separate agreement |

The RISC-V backend and SECOMP's own `cheririscV/` backend are outside CompCert's
dual-licensed subset, so the containment is what keeps this census free of a
distribution obligation. It does not remove the restriction on use.

## Effort and brittleness this route already records

The lowering loop measures its own maintenance cost on the descriptor check, and
that measurement is asymmetric. A constant the generated owner moves reaches the
emitted C through one regeneration and no edit to the component, and the digest
drift is exactly the tests that constant feeds. A hypothesis the specification
moves stops the derivation: `compile` reports `Compilation incomplete` at every
site the old hypothesis discharged and `Qed` refuses, nothing is emitted, and
closing it again is work on the side-condition tactic rather than a
regeneration. The frame-kernel pair adds one datum in the same direction. Both
derivations needed one compilation hint that Rupicola 0.0.11 does not ship,
relating the byte a map or fold step produces to the word the array store
expects, and that hint is stated in each file beside the `Derive` it decides.
Neither the array-write nor the bounded-loop combinator was missing: both come
from the shipped `Loops` and `Arrays` libraries, and the shipped memcpy and
accumulator examples are the precedent both kernels follow.

## What the frontier item still owes

| Owed | Where it is owned |
| --- | --- |
| Worst-case execution time and traffic on a target the register admits | M1.2b through M1.2f, the backend and its acceptance loop |
| An image size, and with it the code-size growth the item names | M1.4′'s assembler and image composer, joined at M1.2f |
| Capability-bearing emitted code, with bounds and provenance in the text | The same backend; no printer edit reaches it, as the lowering loop's boundary table shows |
| Zeroization, descriptor and staging costs in emitted code | A compiled service rather than a pure kernel; the transformation experiment's charges are modeled, not compiled |
| Deadlines, memory classes, power and the admitted image | Q5b and Q8 with M7.1's actual roster |
| A general equivalence between the variants, rather than bounded agreement | A proof relating each loop to the list reference, which neither file carries |

Until those land, the item's candidates close nothing. This census narrows one
question and leaves that judgement where it was.
