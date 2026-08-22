// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The timing annotations (isa-profile.md §9, R-15-095, R-15-096).
//
// The obligations this platform states against the microarchitecture split in two
// by whether a model of architectural state can express them at all (R-15-089).
// The **absence** obligations, no speculation, no out-of-order issue, no dynamic
// predictor, no prefetcher, no cache, no frequency control, are invisible here
// and ride the [absence contract](../../../docs/absence-contract.md) instead
// (R-15-098, R-15-021). The **refinement** obligations, the `Zkt`/`Zvkt`
// data-independent-timing contract, the Ztso store-buffer ordering, static-only
// fetch timing, and the fixed-latency divide, vector-FPU and AMO contracts, are
// properties of modeled state, and this file is where they stop being prose.
//
// **What is stated here is the shape and not the magnitudes.** R-17-041 makes
// the latency magnitudes a crown-jewel specification and nothing measures one
// yet: `Zicntr` and `Zihpm` are implemented in no lifecycle state, so no counter
// exists to read a cycle from, and development measurement rides the
// lifecycle-gated Debug Module trace on real RTL (R-15-077). The freeze
// contract's report is barred from carrying a host-timing column for the same
// reason. So `qualified` is carried beside the numbers exactly as it is beside
// the memory classes' (core/memory_class.sail), it is false in every
// configuration this tree ships, and crown-jewel row 15 stays unauthored: the
// row is the magnitudes, and this is the table they will be written into.
//
// **The latency is a function of the operation and of nothing else, and that is
// the contract rather than a convenience.** `timing_cycles` takes a
// `TimingClass` and takes no operand, no register, no address, and no prior
// state, so there is nowhere for a value to enter it. That is what
// data-independent latency looks like in a model that executes no cycles: a
// future consumer wanting an operand shows up as a changed signature rather than
// as changed arithmetic, which is the same device the mode sequencer uses to
// hold R-15-247r by what its functions take (sys/memory_sequencer.sail).
//
// **The scalar table is one table because the front end is one front end**
// (R-15-112). Scalar front ends are one shared microarchitecture across every
// class, which is what makes kernel-path WCET a single analysis, so a per-class
// scalar latency would be a second front end stated by arithmetic. The vector
// rows are this build's, one build realizing one VLEN (core/vlen.sail). Two
// entries *are* per class and are declared separately below, because one kernel
// binary budgets a partition switch on every class it may run on (R-07-012).
//
// **What is not here is named rather than omitted.** No entry maps an
// instruction to its class: a total map over the decode surface is what makes
// the annotation complete, and it is also what flips R-17-041's row to
// `authored` and enters R-05-150's review at the flip, so it is the successor to
// this file rather than part of it. Two further rows wait on acts that have not
// happened: the fused pairs R-15-034 requires the model to list are selected
// against an emitted adjacency histogram the freeze has not run (R-15-031a), and
// `rcstep` is not in the model yet, its carriage being decided on cycles per
// frame by that same act (R-15-067h, R-15-238c).

// One row per operation class the register states a latency contract over. The
// members are the profile's §9 rows, grouped where the register groups them and
// split where it names an instruction on its own.
//
//   - `Timing_Divide` is separate from `Timing_Integer` because R-15-080 makes
//     it so: integer divide and remainder complete at a fixed worst case always,
//     and an early-out-on-small-operands divider is forbidden. Grouping it with
//     the ALU would state the contract by omission.
//   - `Timing_Branch` carries R-15-086's resolution latency, a fixed function of
//     the static rule, which is what leaves fetch timing dependent on
//     architectural state alone. The mispredict-equivalent penalty R-15-023
//     prices is inside it rather than beside it, there being no predictor whose
//     state could make it conditional.
//   - `Timing_CapLoad` includes the R-08-005 revocation filter. The bank-side
//     bitmap lookup rides the load and may add neither a second memory
//     transaction nor a retry, and revocation changes only the returned tag, so
//     a covered base and an uncovered one are one latency and not two
//     (R-08-005a, R-17-023). A second member for the revoked case would be that
//     contract negated.
//   - `Timing_LoadTags`, `Timing_Reclaim`, `Timing_BlockZero` and
//     `Timing_BlockScrub` are the four block instructions, each at one fixed
//     per-block latency independent of what it finds: of the tags returned
//     (R-15-007q), of the tags found and the bits set and the clears performed
//     (R-15-007s), and of whether anything was corrected (R-15-177a, R-15-179).
//     They share the welded block size (R-15-007q), so the four are one
//     parameter's four consumers here as they are everywhere else
//     (docs/block-geometry-constraint.md).
//   - `Timing_CapSelect` is the conditional capability move at one latency
//     independent of the operand values **and of which arm is taken**
//     (R-15-054a), which the architectural write cannot show and which is
//     precisely why it is an annotation. `Timing_CapClear` is `cclear` at one
//     latency independent of the mask's population (R-15-069b).
//   - `Timing_VectorFloat` covers every operand class including subnormals,
//     there being no subnormal slow path and no second floating-point datapath
//     to state the contract twice for (R-15-081, R-15-039).
//     `Timing_VectorDivide` is `vfdiv` and `vfsqrt`, which are either
//     fixed-latency or off the constant-time list on a discharged proof that no
//     secret-labeled operand reaches them, never on self-declaration (R-15-082,
//     R-15-011).
//   - The two vector memory rows are R-15-085a's split. Unit-stride, segment and
//     whole-register accesses are on the data-independent-timing list, their
//     bank sequence following from the element width and a granule-aligned base;
//     indexed and runtime-strided accesses are off it, and enter this table at
//     the **fully-conflicted** bound, every element resolving to one bank, so an
//     operation whose observed latency varies still contributes one sound
//     latency to the analysis (R-15-085b). The pessimism is paid in the schedule
//     rather than in the leakage model, and the schedule is non-work-conserving,
//     so the unspent remainder is burned inside the issuing partition's own slot.
enum TimingClass = {
  Timing_Integer,
  Timing_Multiply,
  Timing_Divide,
  Timing_Branch,
  Timing_Csr,
  Timing_Load,
  Timing_Store,
  Timing_Atomic,
  Timing_CapInspect,
  Timing_CapDerive,
  Timing_CapSelect,
  Timing_CapClear,
  Timing_CapLoad,
  Timing_CapStore,
  Timing_LoadTags,
  Timing_Reclaim,
  Timing_BlockZero,
  Timing_BlockScrub,
  Timing_VectorInteger,
  Timing_VectorFloat,
  Timing_VectorDivide,
  Timing_VectorMemUnit,
  Timing_VectorMemIndexed,
}

mapping timing_class_str : TimingClass <-> string = {
  Timing_Integer          <-> "integer",
  Timing_Multiply         <-> "multiply",
  Timing_Divide           <-> "divide",
  Timing_Branch           <-> "branch",
  Timing_Csr              <-> "csr",
  Timing_Load             <-> "load",
  Timing_Store            <-> "store",
  Timing_Atomic           <-> "atomic",
  Timing_CapInspect       <-> "cap-inspect",
  Timing_CapDerive        <-> "cap-derive",
  Timing_CapSelect        <-> "cap-select",
  Timing_CapClear         <-> "cap-clear",
  Timing_CapLoad          <-> "cap-load",
  Timing_CapStore         <-> "cap-store",
  Timing_LoadTags         <-> "load-tags",
  Timing_Reclaim          <-> "reclaim",
  Timing_BlockZero        <-> "block-zero",
  Timing_BlockScrub       <-> "block-scrub",
  Timing_VectorInteger    <-> "vector-integer",
  Timing_VectorFloat      <-> "vector-float",
  Timing_VectorDivide     <-> "vector-divide",
  Timing_VectorMemUnit    <-> "vector-mem-unit",
  Timing_VectorMemIndexed <-> "vector-mem-indexed",
}
overload to_str = {timing_class_str}

// Cycles, because a latency enters §11 as a schedule term against the same clock
// every other term is stated in, which is the reason core/memory_class.sail
// states its access constants in cycles too. The bound is wide enough for the
// fully-conflicted vector access at the widest VLEN this profile admits and for
// a whole-unit clear beside it.
type timing_cycles_t = range(0, 4294967295)

// The operation table for the class this model is built as. Every field is a
// latency and none is a count: what a WCET derivation sums is a per-instruction
// latency table projected from this (R-18-024, R-11-015), so a field here that
// meant something else would be summed as if it did not.
struct TimingConstants = {
  qualified            : bool,
  integer              : timing_cycles_t,
  multiply             : timing_cycles_t,
  divide               : timing_cycles_t,
  branch               : timing_cycles_t,
  csr                  : timing_cycles_t,
  load                 : timing_cycles_t,
  store                : timing_cycles_t,
  atomic               : timing_cycles_t,
  cap_inspect          : timing_cycles_t,
  cap_derive           : timing_cycles_t,
  cap_select           : timing_cycles_t,
  cap_clear            : timing_cycles_t,
  cap_load             : timing_cycles_t,
  cap_store            : timing_cycles_t,
  load_tags            : timing_cycles_t,
  reclaim              : timing_cycles_t,
  block_zero           : timing_cycles_t,
  block_scrub          : timing_cycles_t,
  vector_integer       : timing_cycles_t,
  vector_float         : timing_cycles_t,
  vector_divide        : timing_cycles_t,
  vector_mem_unit      : timing_cycles_t,
  vector_mem_indexed   : timing_cycles_t,
}

// The two per-class constants, and they are per class for a reason the scalar
// table's rows are not. A partition switch costs three terms and no fourth
// (R-15-220): the `fence.t` padded constant, the eager vector and matrix
// zeroize, and the operating-point relock. One kernel binary runs unmodified on
// every class (R-07-012) and has to budget that switch on each of them, so both
// constants are stated per class and read out of the attested devicetree rather
// than derived from whichever class the reading core happens to be.
//
//   - `vmclear_cycles`. R-15-069e admits the instruction on the bound: one
//     unconditional mask-independent pass over the vector register file, the
//     vector CSRs, the matrix unit's architectural state, and the class's
//     scratchpad, at one fixed per-class latency, replacing a loop whose
//     per-class trip count the kernel proof and the WCET table would otherwise
//     both carry (R-07-014c).
//   - `fence_t_cycles`. R-15-218 pads it: the fence completes at its bound and
//     never early, because a fence that finished early would make switch latency
//     a function of the outgoing partition's store traffic with the incoming
//     partition as the observer. That padding is also why the store-buffer drain
//     is one term in the budget rather than a second beside it (R-15-088).
struct CoreClassTiming = {
  vmclear_cycles : timing_cycles_t,
  fence_t_cycles : timing_cycles_t,
}

let plat_timing : TimingConstants = config timing.operations

let plat_timing_class_c   : CoreClassTiming = config timing.switch.c
let plat_timing_class_v   : CoreClassTiming = config timing.switch.v
let plat_timing_class_m   : CoreClassTiming = config timing.switch.m
let plat_timing_class_s   : CoreClassTiming = config timing.switch.s
let plat_timing_class_rot : CoreClassTiming = config timing.switch.rot

// The one reader of the operation table, and it takes a class and nothing else.
// Everything above about data independence is held by this signature rather than
// by a rule about it: there is no parameter for an operand to arrive through.
function timing_cycles(t : TimingClass) -> timing_cycles_t = {
  let k = plat_timing;
  match t {
    Timing_Integer          => k.integer,
    Timing_Multiply         => k.multiply,
    Timing_Divide           => k.divide,
    Timing_Branch           => k.branch,
    Timing_Csr              => k.csr,
    Timing_Load             => k.load,
    Timing_Store            => k.store,
    Timing_Atomic           => k.atomic,
    Timing_CapInspect       => k.cap_inspect,
    Timing_CapDerive        => k.cap_derive,
    Timing_CapSelect        => k.cap_select,
    Timing_CapClear         => k.cap_clear,
    Timing_CapLoad          => k.cap_load,
    Timing_CapStore         => k.cap_store,
    Timing_LoadTags         => k.load_tags,
    Timing_Reclaim          => k.reclaim,
    Timing_BlockZero        => k.block_zero,
    Timing_BlockScrub       => k.block_scrub,
    Timing_VectorInteger    => k.vector_integer,
    Timing_VectorFloat      => k.vector_float,
    Timing_VectorDivide     => k.vector_divide,
    Timing_VectorMemUnit    => k.vector_mem_unit,
    Timing_VectorMemIndexed => k.vector_mem_indexed,
  }
}

function core_class_timing(c : CoreClass) -> CoreClassTiming =
  match c {
    CoreClass_C   => plat_timing_class_c,
    CoreClass_V   => plat_timing_class_v,
    CoreClass_M   => plat_timing_class_m,
    CoreClass_S   => plat_timing_class_s,
    CoreClass_RoT => plat_timing_class_rot,
  }

// The partition-switch term this model can state, which is two of R-15-220's
// three. The third is the operating-point relock, a property of the rail and the
// mode schedule rather than of anything the machine executes (R-11-017), so it
// is not a row this file may carry: stating it here would put a figure the OPP
// artifact owns into a table nothing holds against it.
// The sum is a `nat` and not a `timing_cycles_t`, which is the type saying what
// it is: the field width bounds what a composition may *declare*, and a total
// over two declarations is a quantity nobody declares.
function partition_switch_cycles(c : CoreClass) -> nat = {
  let k = core_class_timing(c);
  k.vmclear_cycles + k.fence_t_cycles
}

// A memory access is priced against the latency class its region is placed on
// and against nothing here (R-15-247, R-15-247j, core/memory_class.sail). The
// two tables meet at this one function rather than by one restating the other's
// constants: `Timing_Load` is the pipeline's own term and the class constant is
// the array's, and what §11 charges a second-class placement is the difference
// of two array constants, which the static memory plan computes (M1.9).
function timing_access_cycles(t : TimingClass, c : MemoryClass) -> nat =
  timing_cycles(t) + memory_class_constants(c).read_cycles
