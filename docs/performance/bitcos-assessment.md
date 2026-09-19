# BITCOS on the VerifiedOS inference path

Status: research assessment and proposed comparison for Q4b, not an admitted
format, implemented target kernel or measured speedup. The existing
[ternary demand record](ternary-static-demand.md) owns the measured baseline.
The [prompt-processing contract](prompt-processing-term.md) owns the coordinated
quality, demonstration-set and register act needed to select a ternary release
member. This assessment adds no ISA instruction or hardware block.

The [Bonsai 2 and post-training review](bonsai2-assessment.md) adds a g128,
rotated hybrid-attention candidate for a larger resource budget. Its tensor
census, activation transforms and state costs are separate from Q12's g64
baseline. Any reasoning-efficient derivative is finalized and quality-tested
before choosing its BITCOS layout.

## What the paper establishes

[Georganas, Heinecke and Dubey, BITCOS v1](https://arxiv.org/html/2609.16338v1)
describe lossless packing of existing ternary weights: a presence bitmap and
signs stored only for nonzeros. Symbol cost is `2 - z` bits per weight at zero
fraction `z`. Their x86 kernels use BMI2 `pdep`; AVX-512 selects scaled values
with masks, while the AVX2 path builds int8 operands for VNNI. Xe2 replaces bit
deposit with a four-weight lookup table and feeds DPAS. The reported end-to-end
maxima are 1.18 times on CPUs and 1.27 times on GPUs; the Lunar Lake CPU loses
because unpacking dominates. Table I reports Bonsai-4B at 37.71 percent zeros.
The evaluated Bonsai Q2_0 scale groups have 128 weights.

The encoding does not quantize an arbitrary model into a good ternary model.
An exact repack preserves its existing symbols and scales; changing activation
precision, scale groups or accumulation order is a separate numerical change.
Those changes cannot inherit the repack's losslessness claim.

There is no information-theoretic contradiction in going below `log2(3)`:
that is the maximum entropy of a ternary symbol, reached at equal probabilities.
For equally likely positive and negative nonzeros, entropy is
`h2(z) + (1 - z)` and BITCOS's excess is `1 - h2(z)`, where `h2` is binary
entropy. Unequal sign probabilities leave further redundancy. Small size and
minimum decode cost are different optimization objectives.

## Compare against this repository's actual baseline

Q12 measured a **g64** Q2_0 file. Preserve that file's group boundaries and
scale bits; substituting the paper's g128 overhead would claim a saving from
an unmeasured representation change. Read tensor types, element counts and
weight-read terms from [the static record](inference-demand/static-Q2_0_g64.json)
and rate, context, KV and grant terms from
[the budget](inference-demand/ternary-budget.json). Keep normalization tensors,
the tied output head and the embedding lookup in the accounting. A model-family
name does not establish equality with the paper's checkpoint or zero histogram.

For a comparison preserving one 16-bit scale per group of `g` weights, define
`o_f` as format `f`'s additional bits per weight, including directories,
alignment, tails and guard storage. Then the candidate storage costs are:

```text
two_bit     = 2       + 16/g + o_two
five_trit   = t       + 16/g + o_five
bitcos      = 2 - z   + 16/g + o_bitcos
```

Here `t` comes from the actual packing geometry, not its name. For example,
packing each complete 64-weight group into 13 symbol bytes gives `t = 104/64`;
tightly packing complete groups of five gives `t = 8/5` before tails. These
are comparison designs with unchanged scales, not assertions about a different
GGUF loader's TQ1_0 definition.

BITCOS beats five-trit storage only when
`z > 2 - t + o_bitcos - o_five`, and beats two-bit storage only when
`z > o_bitcos - o_two`. This exposes the particularly small margin over
five-trit at the paper's Bonsai-4B density. Per-vector offset records or generous
alignment can consume that margin. No format wins universally after overhead.

For a conditional sensitivity calculation, let `N` be the eligible Q2_0
elements read per token, including the additional embedding row, and let `H`
be the candidate's extra logical bytes read per token. Repacking with unchanged
scales saves `N*z/8 - H` bytes relative to two-bit symbols. Subtract that from
the budget's weight-read term and recompute its existing
`rate * (weight_reads + KV_at_context)` expression. Apply no saving to KV.
The paper's density is an input to a scenario until a census of the exact
Q12 artifact establishes it; it is not a new measured record.

Logical byte savings are not fabric savings on this cacheless design. A
sign window read afresh at each decode step can repeatedly fetch the same
aligned words. Count issued accesses, bank service, scratch reads and writes,
and transfer granularity separately from encoded file length. Credit reuse
only where an explicit register or scratch buffer retains those words.

## First candidate: use the existing RVV operations

Start with a lossless BITCOS-to-int8 expansion on the M-class's specified
VLEN=1024 RVV unit. Decode a block of at most 128 weights with SEW=8 and
LMUL=1. This is a candidate tile size, not a new profile constant. It keeps
every exclusive prefix rank inside an unsigned byte and allows a g64 block
boundary to remain explicit in subsequent arithmetic.

For presence bits `P[i]`, aligned compact sign bits `S[j]` and negative sign
encoded as one, the reference relation is:

```text
r[i] = sum(P[j] for j < i)
w[i] = 0                         if P[i] == 0
w[i] = 1 - 2*S[r[i]]             otherwise
next_sign_cursor = sign_cursor + sum(P)
```

Construct a byte vector of compact `+1`/`-1` values from the sign mask, form
exclusive ranks with `viota.m`, and gather those bytes into present lanes of
a zeroed destination. [RVV 1.0's permutation semantics](https://docs.riscv.org/reference/isa/v20260120/unpriv/v-st-ext.html)
provide this expansion using iota and masked register gather. Gather here reads
registers, not weight-dependent memory addresses.

The following is a register-only lowering sketch. Memory ingress, cursor
alignment, capability operands, scheduling and contraction are still owed.
`v1` holds presence, and `v0` initially holds the aligned compact sign mask.
Set `vl` to the block length and use `e8,m1,ta,mu` before these operations;
mask-undisturbed policy preserves zeros in absent lanes.

```asm
vmv.v.i     v2, 1
vmerge.vim  v2, v2, -1, v0
viota.m     v3, v1
vcpop.m     t0, v1
vmmv.m     v0, v1
vmv.v.i     v4, 0
vrgather.vv v4, v2, v3, v0.t
```

The register groups do not overlap. A present lane's rank is below the
population count, so it selects a valid compact sign. An absent lane retains
zero. The all-zero block reads no sign semantically; a fixed physical window
still needs valid backing. Tail lanes are not output and must not be contracted
as if initialized. `t0` advances the cursor once per block. Splitting a wider
vector into these blocks avoids both byte-rank overflow and byte-gather index
limits; wider ranks are an independently measured alternative.

The curated Sail already defines these mask and gather operations in
[the mask instructions](../../model/model/extensions/V/vext_mask_insts.sail)
and [the arithmetic instructions](../../model/model/extensions/V/vext_arith_insts.sail).
That establishes an existing semantic route, not its target throughput.
Prefix scans and gathers may be expensive on an in-order implementation.
Count mask ingress, vector configuration changes and source/destination
register pressure when measuring; the short sketch is not the kernel's full
instruction count.

For sign ingress, keep an aligned sliding word window in registers or bounded
scratch. At most three aligned 64-bit words cover 128 sign bits starting at
any bit offset. Special-case a zero shift without a shift-by-64 expression,
and retain overlapping words across blocks. Either validate a charged guard
region inside the same capability or use bounded final-window loads; reading
past an allocation because a vector tail is masked is not valid. The
[misaligned-access rule](../spec.md#r-15-084) traps rather than splitting a load,
so Intel's unaligned sign-load sequence cannot be copied directly.

For batch-one generation, compare RVV widening integer contraction against
any admitted dot-product lowering. Accumulate each original scale group in
int32 with an explicit overflow bound and apply its scale before combining
groups. Reuse the same activation representation in every arm. If the baseline
uses floating activations, an int8 activation arm is a separate quality-tested
candidate. For prompt processing or batching, also compare reuse of one
expanded tile across several activation rows. Charge tile storage, staging,
reloads and zeroization. Select the matrix route only when its instruction
surface and [matrix-margin obligations](../implementation/contracts/matrix-margin-contract.md)
are satisfied; a specified array geometry does not supply an executable opcode.

## Alternatives worth measuring

| Candidate | Reason to include it | Cost that can defeat it |
| --- | --- | --- |
| Two-bit and five-trit RVV kernels | Required baselines with identical symbols, scales and arithmetic | Extra stream bytes or radix decoding |
| Prefix-rank BITCOS | Existing operations and a simple functional relation | Scan, gather, sign-window ingress and issue occupancy |
| Register lookup BITCOS | Replace a long prefix path with small local lookups | Cursor formation, table registers and operand rearrangement |
| Bounded pre-expansion | Amortize decode over prompt rows or a batch | Scratch capacity, extra memory movement and reloads |
| Register-only bit deposit | Directly reconstruct a sparse sign bitmap | New semantics, timing and RTL cost, plus byte expansion still required |

A concrete lookup alternative maps four presence bits and the next four
compact sign bits to one byte containing four two-bit codes. Its 256 entries
fit in a 256-byte RVV register group, LMUL=2 at this VLEN, instead of a
memory-resident scaled-value table. Advance each nibble's sign cursor by its
presence population count, not by four, then unpack the resulting codes to
the contraction's operand order. This mapping is a proposed local design.
It needs its own comparison against the prefix route, including the work to
form keys and ranks; a smaller table is not evidence of a faster kernel.

Neither adopted `Zbs` single-bit operations nor the bespoke contiguous
`bfins` instruction is arbitrary-mask parallel bit deposit. See the
[ISA profile](../hardware/isa-profile.md). A new deposit instruction is an
off-model research arm only if existing RVV lowering demonstrably limits the
complete inference path. Require exact register semantics, fixed latency,
area/energy evidence, no hidden state and the ordinary
[ISA admission tests](../spec.md#r-15-010) before any profile change. Do not add
an autonomous decompressor, a sparse memory walker or a per-format scale CSR.

## Select a layout with the real schedule

Pack at model preparation, not once per token. Use bounded independently
addressable panels so workers can start without scanning all earlier weights.
Preserve scale ownership when permuting tensor dimensions. Compare panel sizes
large enough to amortize one sign offset and descriptor against smaller panels
that expose independent work and limit scratch. Keep bitmap and sign streams
separate; every padding byte and directory entry belongs in the capacity and
traffic ledger. Validate dimensions, products, offsets, popcounts, final cursor,
canonical padding, scale representation and buffer bounds before use.

Choose among formats per tensor or panel using a reviewed, finite candidate
set and charge the format tags and dispatch. Prefer simpler format granularity
when finer selection cannot repay those costs. The representation and kernel
identifier belong to the model descriptor; the server's allowed formats,
worker set, grant and worst-case ceiling stay fixed at composition. A prepared
model remains data. Model opening can validate a permitted descriptor, but
cannot change the worker schedule or install generated executable code.

Optimize admitted token time subject to resident capacity, grant, quality and
energy constraints. Report the Pareto choices if those objectives disagree.
For each equal-work block, `max(T_memory, T_unpack+compute)` is only an
optimistic overlap bound. Use the actual in-order schedule, including shared
issue and vector resources, transfers and dependencies, to establish achievable
time; absent overlap evidence, retain the serialized cost. Interleave a bounded
number of independent panels to shorten cursor stalls only when the register
and schedule ledger permits it. Intel's out-of-order cycles and cache reuse
cannot supply these terms.

Do not assume sparsity skips MACs: these candidates reconstruct dense operands.
Any sparse compute arm pays for indices, activation access and load imbalance.
Likewise no credit is taken for masked-off memory accesses returning their
cycles under the [mask timing contract](../spec.md#r-15-115b).
The [inference confidentiality scope](../spec.md#r-12-085) permits data-dependent
work confined to the server's slots and banks; it supplies no constant-time
claim about these kernels. This assessment neither widens that interface to
secret-labeled data nor erases its physical leakage residual.

## Evidence required for selection

Q4b owns this comparison within its target-verdict work; M6.6 owns descriptor
and executable-server integration, M6.8 owns the fixed grant, and Q1 owns
quality and useful prompt limits. Keep the existing measured Q12 record intact.
Before scoring candidates, fix the model digest, tensor census, arithmetic,
workload cases, candidate set and ranking rule. The comparison is complete only
when the following evidence exists:

1. Census the exact Q12 weight artifact by tensor and scale group, checking its
   original license record before use. Record zero counts and all representation
   costs from bytes, with a generator and drift check for any retained derived
   report. The paper's density alone cannot select a layout.
2. Round-trip every eligible tensor with identical symbols, original scale bits
   and indexing. Refuse invalid codes, truncated signs, inconsistent counts,
   overflowed offsets and unsupported scale forms. Exercise every short ternary
   vector, all sign-word offsets, all-zero/all-nonzero blocks, tails and panel
   boundaries against an independent scalar relation. These are functional
   checks, not a proof of the target kernel or parser.
3. Compare emitted target kernels with that relation, then compare complete
   contractions including signed-int8 extrema, group boundaries, overflow and
   rounding. Freeze acceptable numerical and quality differences before any
   activation or accumulation change. Keep host oracle and target evidence
   separate.
4. Measure each candidate's full in-slot cost on the same core configuration,
   extension set and memory grants. Retain memory transactions, decode/compute
   cycles, issue occupancy, scratch peaks and energy over the same work. Include
   batch-one short and declared-context decode, prompt processing, tile tails
   and concurrency; include initialization and admission-time repacking in their
   proper budgets rather than hiding them in warm-up.
5. Select only a feasible candidate that beats the strongest feasible baseline
   under the predetermined objective after uncertainty and overhead. Record
   losses as well as wins. An optimum claim is restricted to the enumerated
   candidates and that cost model. Missing target latency or energy inputs leave
   selection open; they are not zero costs. Any release-format choice still
   takes the joint act in the prompt-processing contract.

The immediate design recommendation is to evaluate the existing-RVV prefix
route and register-lookup alternative against two-bit and five-trit baselines,
with exact model statistics and aligned buffered sign reads. A hardware change
is justified only by the resulting target bottleneck evidence.
