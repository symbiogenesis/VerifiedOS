# Static-memory service transformations

This experiment advances the lifetime/representation and bytes-versus-work items
in the [research backlog](../background/static-memory-research.md). It emits and
executes a bounded frame service in a small interpreter instruction set. It checks
the resulting placements with the [existing model](static-memory-baseline.md),
compares outputs with an independent value specification, and reports physical
reservations and executed operation counts. It supplies no target compilation,
WCET, energy measurement or product admission evidence. Both research items remain
open under their full acceptance conditions.

## Replay and identity

From the repository root:

```console
python tools/run.py static-memory transform --json
python tools/run.py test --only static_memory_transform
```

The command calls
[`transformation_report`](../../tools/vos/static_memory_transform.py), whose report
includes the source revision, working-tree source hashes, generated input digest,
program digests, settings, all reservations, disjoint event ledgers, equivalence
findings and modeled Pareto candidates. The command's enclosing receipt binds its
other source identities. The report computes every result from generated programs;
this document does not maintain a second result table. `emit_program`, `layout`,
`execute` and `equivalence_findings` expose each stage for focused replay and
mutation. No dependency or target-language path is added.

The default comparison specializes the service to public exact frame lengths in
the report's settings. A separate specialization accepts exactly its configured
length, up to the generator's fixed maximum; it refuses a wrong length before
constructing backing. This is a family of statically bounded services, with the
same length and value contract across variants in each comparison. It is not a
runtime choice of a smaller arena based on private input.

## Service and equivalence argument

The service accepts an exclusively owned, disposable byte frame. For input `x`,
its contiguous result is:

```text
t[i] = (3*x[i] + 1) mod 256
c = (sum_i t[i]) mod 256
y[i] = t[i] XOR c
```

Ingress supplies the frame before computation. Egress consumes the complete
contiguous result, after which service backing is erased. The reported arena
belongs to this service. The ingress source and egress consumer's backing lie
outside that boundary and require their own composition charges; egress traffic
and the service's complete result buffer remain in this experiment. Host Python
objects do not measure target physical allocations.

The independent reference uses multiplication, a complete list and a whole-list
sum. Emitted map instructions use shift/add/mask. For byte `b`,
`((b << 1) + b + 1) & 255 = (3*b + 1) mod 256`; thus each map instruction implements
the reference element function. Modular addition is associative, so reducing
disjoint consecutive chunks gives the same `c` as reducing the whole list. The
generator's chunk starts partition the configured index interval with no duplicate
or missing index. Padding is outside the narrowed useful extent.

Cached variants preserve every mapped element until its output use.
Rematerialized variants preserve their input until the second application of the
same pure map; neither changes the checksum before the output pass. The in-place
variant replaces input element `i` only after reading it, accumulates the checksum
over that mapped value, and begins the XOR pass only after the complete reduction.
Later map iterations read distinct input indices. All variants therefore emit
`y[i]` in index order under this abstract interface. This is an elementary
algorithm argument, accompanied by bounded executable comparisons and mechanized
over its list functions below; it is not a machine-checked compiler refinement
theorem.

The report exhausts its declared small alphabet at its declared small lengths and
also executes deterministic generated full-size frames. Its input digest and
execution count are computed. The tests additionally exercise partial chunks,
mutate XOR into a copy, omit the control scrub, introduce an early retirement and
an out-of-bounds view, and corrupt placement into overlap. A value test alone would miss the latter
failures, so authority/index checks and the separate placement checker reject
them independently.

### Mechanized equivalence

[StaticMemoryService.v](../../proofs/StaticMemoryService.v) states the argument
above as Rocq theorems over list functions and proves them outright, with every
constant closed under the global context at the proof gate `run.py proofs` runs.
It carries the reference, the shift/add/mask map proved equal to the
multiply/mod map for every natural and re-decided by computation over the byte
domain, six functional models covering the seven rows of the variant table
below, and result equality with the reference on every input list. The two
retained-cache rows share one model, since they differ in retirement and not in
data flow. Early release, chunked cache and tiled recomputation each have a
model mirroring their own schedule, and the three coincide as functions up to a
reassociation of maps: that is the whole functional content of a stage copy
being a pure move and of a recomputed pure map returning what was stored, and
the models say nothing about what either costs. The chunk models take an
arbitrary list of `(start, count)` chunks under the hypothesis that the chunks
partition the index interval. The hypothesis is proved sufficient and shown not
to be necessary: one chunk reaching past the end of the list still returns the
reference, because a slice truncates there. The generator's chunk list,
including its clamp of the tile to the frame length, is proved to satisfy the
hypothesis for every positive tile, and a chunk list that drops the last indices
or repeats the first ones in their place is shown to fail it and to return a
different list on a concrete frame, differing in value and not only in length.
The in-place model is a sequential state machine over a memory function that
overwrites element `i` only after reading it, accumulates the checksum over the
mapped value, and starts its XOR pass only after the reduction completes. A
concrete frame has its outputs computed by `vm_compute` on every model, and a
variant whose XOR pass is replaced by a copy is refuted on it, mirroring the
tests' mutant. The proof cites R-08-019e, without claiming it, for the
recompute-rather-than-store lever the rematerialized variants exercise, since
that lever acts on the artifact only when recomputation returns the same
result; the certificate that prices the trade in space and time is untouched,
so no pricing or admission entry is cited, and whether the entry governs the
artifact is the review gate's reading.

The gap is explicit. The Rocq functions are not the interpreter: `execute`'s
instruction semantics, the emitted schedules, resource reservation and
retirement, authority and index checks, zeroization, the persistent checksum
byte, staging copies and any DMA staging are outside every theorem, and no
refinement from an emitted program to its functional model is stated. The chunk
models place a chunk's outputs by chunk order where the schedule writes them at
their start offsets, which agree only under the partition hypothesis.
Equivalence of the generator's programs to these functional models therefore
remains the executable-test claim `equivalence_findings` makes over the
report's frames, and the costs the report compares are not modeled by the
proof at all. The proof confers no landing credit and accepts no requirement;
the [requirements register](../requirements-register.md) remains authoritative
and both research items stay open under their full acceptance conditions.

## Variants and the assumption each changes

| Variant | Transformation and costs retained |
| --- | --- |
| `lexical-cache` | Retains input, mapped frame and result until the outer region exits. Each allocation carries its descriptor and padding. |
| `phased-cache` | Retires and erases input after the mapped frame and checksum exist. Its backing may be reused for the result after the scrub finishes. No payload operation changes. |
| `early-input-release` | Ingress materializes a bounded set of input chunks. Each chunk is retired after its last map use while later input chunks remain owned. Every chunk descriptor and partial-tail padding is charged. |
| `chunked-cache` | Retains mapped values in fixed bounded chunks. A bounded stage and a full contiguous sink carry the output; every stage copy, descriptor and padding byte is charged. |
| `tiled-rematerialized` | Uses a reusable fixed tile in both passes, preserving input for recomputation. The complete result, tile and input coexist in the output pass. |
| `fused-rematerialized` | Fuses map/reduction and map/XOR into separate passes without a mapped array. It repeats map arithmetic and preserves input until the second pass completes. |
| `in-place-phased` | Replaces the exclusively owned input with its mapped values and then its final output. This depends on the disposable-input interface; it is invalid for an immutable borrowed frame. |

These are a finite set of candidates, not an optimizer over all equivalent
programs. In particular, different instruction fusions and algebraic
transformations may improve them further. The same owner, configured length,
input values and output contract are used for each row. Changes to an immutable
input promise or a scatter/gather output promise would be separate experiments.

No external aliases, retained capabilities or asynchronous device transfers are
admitted by this synchronous interface. Buffer identities have bounded index
views and the interpreter rejects accesses outside an active view. Its offsets
and lengths model narrowing; they do not establish that the target compressed
capability can express those bounds. A device API that requires contiguous
transfers motivates the charged chunk stage, but the program executes synchronous
copies, not actual DMA. There is no device-completion timing claim. A target port
owes the [Q22 barrier](../assurance/revocation-qualification.md), capability
representability, alias/loan elimination and completion evidence before it can
reuse any extent on this schedule.

## Physical ledger and work model

The emitted schedule has fixed reserve, data operation and retirement instructions.
Every reserve/retirement is known before input values are supplied. The offline
planner assigns each identity its immutable offset with deterministic first fit;
the independent placement checker then checks bounds, alignment and all
simultaneous reservations. The program performs no runtime address search.

Each resource contains its useful byte extent, alignment/tail padding and a
literal descriptor reserve. The descriptor model contains a capability-sized
base/extent representation and scalar bookkeeping; its size is an experimental
setting, not an ABI assertion. A fixed control reserve is also charged. The actual
compiled stack, root storage and capability metadata remain unknown. No claim
equates the control reserve with a compiled function's stack bound.

The per-event ledger partitions the complete reserved span into input, mapped
values, output, staging, descriptors, padding, retained bytes, zeroizing bytes,
control reserve and idle bytes. A retired or zeroizing resource is charged as its
whole physical extent; its descriptor and padding are not counted again. The
ledger reports charged peak separately from layout span, so an earlier release
cannot be mistaken for improved packing. Byte-by-byte tests independently check
occupancy and conservation against the reservation intervals.

Every newly bound resource is zeroed over its full data, padding and descriptor
extent, then receives a descriptor binding write. Retirement scrubs that whole
extent before a later identity may occupy it. Explicit control-entry and
control-exit instructions scrub the control reserve, with their actual writes
charged when executed. The persistent checksum occupies a byte in that reserve;
each reduction and XOR reads its stored value and each reduction writes it back.
The omitted-control-exit mutant returns the right result while retaining a
nonzero checksum byte and failing the erasure witness. The interpreter checks that
service backing is all zero and all modeled authority is released after return.
This check does not establish erasure of Python locals or host allocations.
Scrub instructions cost their actual modeled byte writes;
counting one abstract scrub instruction never makes it a one-cycle operation.

Data and checksum reads/writes, descriptor reads on every modeled data access, descriptor
binding writes, ingress/egress traffic, stage copies and all zeroization writes
are counted by execution. Arithmetic counts include shift, add, mask and XOR,
with separate map-evaluation and bounds-check counts. Transient scalar arithmetic
resides in abstract temporaries; compiled spills, instruction fetch and bank traffic are
unmodeled. The memory-traffic figure is a declared interpreter cost model, not a
target bus trace. The descriptor-lookup setting is particularly consequential:
a target compiler may keep authority in registers and eliminate those reads.

The emitted program contains no input-value branch or data-dependent loop bound.
Its addresses, instruction sequence and resource extents are fixed for the public
length. Each executed cost counter therefore has one value for every frame of
that length in this model. The generated comparisons test that invariance across
different values; the reason it holds is the straight-line instruction semantics,
not the coverage of the sample. Instruction ordinals are lifecycle ordering
events, never elapsed-time deadlines. Emitted instruction counts expose abstract
unrolling growth while target code-size and instruction-selection costs stay
explicitly unknown.

## Findings and open disposition

The report's `modeled_pareto_frontier` compares reserved span, arithmetic operations
and modeled memory traffic only among its generated candidates. It cannot choose
a target winner without prices for those dimensions. In the default settings,
phase release reduces reservation compared with lexical retention while keeping
the payload operations. The early-input-release and chunked-cache candidates lose
to contiguous phases because their descriptors and staging consume the apparent
benefit. Tiled recomputation also loses when its input, tile and result must coexist.
These negative results refute a gain claim for these particular candidates under
these cost assumptions; they do not refute segmentation on a different service.

The disposable-input interface admits the stronger in-place transformation. Its
memory/arithmetic advantage and fused rematerialization's modeled traffic advantage
leave an explicit tradeoff in the default candidate set. None of these findings
establishes a better placement algorithm: reported charged peaks and spans show
whether a gain comes from changed reservation lifetimes or eliminated resources.
Descriptor pricing and possible additional fusion require further ablations.

Q5 can consume the exported reservation cases and independently checked plans.
Q8 still owes emitted target code, execution/bandwidth bounds and power evidence;
Q22 owns the target reuse join. A composition-level comparison additionally needs
the real roster, memory classes, vectorization behavior, DMA completion, source
and receiver charges, original deadlines and admitted image. The report leaves
those quantities unknown and grants neither research checkbox completion nor
implementation landing credit.
