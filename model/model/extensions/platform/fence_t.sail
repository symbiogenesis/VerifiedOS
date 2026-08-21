// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// `fence.t`, the temporal-isolation fence (R-15-062).
//
// It is adopted as a **fork-and-frozen platform-custom instruction with full
// Sail semantics, specified rather than invoked**: what a curator finds here is
// an enumerated flush set and not a gesture at one. There is no standards track
// to re-pin to.
//
// **The flush set is a single structure: the store buffer, drained rather than
// merely fenced, so no store issued by the old partition can land or become
// visible after the switch** (R-15-213). Everything a `fence.t` on another
// machine would have to name is absent or accounted for elsewhere, and each of
// those is a deletion rather than an exemption:
//
//   - The **register files**, integer and vector alike, are covered by the
//     partition switch's *total restore* over every register a partition can
//     name, which is the obligation that replaces flush-set membership for them
//     (R-07-015, R-07-016, R-15-214).
//   - The **vector CSRs** are zeroized and not saved, so no vector CSR
//     context-switches and none joins this set (R-07-014a); `frm` and the
//     accrued flags are not here to join it either, scalar floating point being
//     deleted and rounding static (R-15-083).
//   - The **predictor structures** are deleted rather than flushed, which is
//     strictly stronger: nothing joins the set and no residual completeness
//     obligation exists for them (R-15-019, R-15-020). That deletion is
//     discharged structurally, by rows A-04 through A-06 of the
//     microarchitectural absence contract, and not by RTL refinement against
//     this model (R-15-021): Sail carries architectural state, so no model can
//     state *there is no branch predictor*, and searching this tree for one is
//     the wrong search. What the model can carry is the consequence, and it
//     does: prediction being a fixed function of the encoding and the
//     displacement sign, there is no predictor state to declare here and none
//     is declared (R-15-019, R-15-022, R-15-086, R-15-098).
//   - The **caches** do not exist to be flushed or partitioned, and the tag
//     table and tag cache went with them (R-15-061).
//   - The **SRAM banks, macros and tiers, the TDM NoC slots, and the per-
//     partition interrupt-file state** are *partitioned* rather than
//     time-shared, so `fence.t` does not touch them; in-flight DMA is likewise
//     not its concern, device windows being torn down by their own path
//     (R-15-216).
//
// So the whole of what this instruction does in an architectural model is drain
// the buffer, and this model has no buffer to drain: it is in-order and
// single-copy, so every store is already visible where the fence would make it
// so. The barrier below is the *same* barrier a draining `fence` emits, and it
// is one member of `barrier_kind` rather than two spellings, which is what makes
// the flush set and the drain visibly one structure (R-15-017, R-15-213). The
// difference is the condition, not the effect: a `fence` drains on its
// predecessor and successor sets and this instruction drains unconditionally.
// The barrier is that statement rather than a stand-in for one, and
// the *completeness* of the classification above is discharged by the
// microarchitectural absence contract rather than by the refinement, since
// completeness is the claim that no unenumerated state exists, which the model
// cannot see (R-15-106, R-17-019).
//
// **Its cost is a padded per-class constant and the fence completes at that
// bound, never early** (R-15-218). That is a property of the timing-annotated
// model rather than of any architectural state, so it is carried as an
// annotation (M0.9) and checked by measurement; a fence that finished early
// would make partition-switch latency a function of the outgoing partition's
// store traffic, with the incoming partition as observer, which is the channel
// the padding exists to close. It is also why the store-buffer drain is *one*
// term in the partition-switch budget rather than a second one beside it
// (R-15-088, R-15-220).
//
// The encoding is MISC-MEM `funct3` 100, which is vacant here: `fence` is 000,
// the cache-block operations and the capability load share 010, and `fence.i`
// went with `Zifencei` (R-15-047). Every other field is zero, so an encoding
// with a non-zero `rs1`, `rd`, or immediate decodes to nothing and traps rather
// than being ignored for forward compatibility the way `fence`'s reserved
// fields are: this instruction has no future extension to reserve them for
// (R-15-014).

union clause instruction = FENCE_T : unit

mapping clause encdec = FENCE_T()
  <-> 0b000000000000 @ 0b00000 @ 0b100 @ 0b00000 @ 0b0001111

function clause execute FENCE_T() = {
  sail_barrier(Barrier_RISCV_drain);
  RETIRE_SUCCESS
}

mapping clause assembly = FENCE_T() <-> "fence.t"
