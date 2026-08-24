// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The core classes (R-15-113) and the roster `mhartid` indexes (R-15-052b).
//
// There is exactly one Sail model, parameterized by core class, and exactly one
// capability encoding (R-15-005). Heterogeneity lives in the datapath and never
// in the trust structure: every class shares the base ISA, the purecap
// capability model, the kernel binary, and this model, differing only in
// execution resources (R-04-009, R-15-111). One shared scalar front end runs
// under all of them, which is what makes kernel-path WCET a single analysis
// (R-15-112).
//
// **What is here is the class table and the roster; what a class *is* to the
// machine is its datapath, and the datapath is fixed at composition.** There is
// no dynamic migration between classes and no mechanism to drag VLEN-scale
// register state across the die (R-07-013), so a hart's class is decided once,
// by the composition, exactly as a region's latency class is
// (core/memory_class.sail).
//
// **No instruction reads any of this and none ever will.** The class is not
// architectural state and there is no CSR that reports it: one kernel binary
// runs unmodified on every class and selects its per-hart state, the core's
// class, and the island binding from `mhartid` against the attested devicetree
// (R-15-052b, R-09-007, postlude/device_tree.sail). So the decode surface is
// unchanged by this file, which is what the absence contract's A-17 is an
// auditor's search for, and the one class-visible obligation the kernel carries
// is gating vector and matrix state at partition setup through `mstatus.VS`
// (R-07-012), which is a CSR this model already has.
//
// **Counts are composition parameters, not architecture** (R-15-113), so no
// count is declared: the roster enumerates harts and a class's count is the
// number of its entries (`core_class_count` below). A declared count beside an
// enumeration is the same fact twice, and the one that drifts is the one nobody
// renders.
//
// **The values are the composition's and this file holds none of them.** VLEN
// per class, core count per class, issue width, pipeline depth, and scratchpad
// size are R-15-108's frozen microarchitectural parameters, chosen by a
// design-space exploration that has not run; R-15-113's figures are a reference
// instantiation of them. So the validator holds the *shape* a composition may
// declare and never the numbers, which is the register M0.14 established for the
// memory classes and for the same reason (postlude/validate_config.sail).

enum CoreClass = {
  CoreClass_C,    // control and application
  CoreClass_V,    // long vector
  CoreClass_M,    // matrix and AI
  CoreClass_S,    // scalar sentinel
  CoreClass_RoT,  // the platform's only management processor
}

mapping core_class_str : CoreClass <-> string = {
  CoreClass_C   <-> "c",
  CoreClass_V   <-> "v",
  CoreClass_M   <-> "m",
  CoreClass_S   <-> "s",
  CoreClass_RoT <-> "rot",
}
overload to_str = {core_class_str}

// The declared widths. Each bound says what a field is allowed to be rather than
// what it is.
//
// `core_class_vlen_exp` and `core_class_elen_exp` are **value**-level and reach
// zero, where core/vlen.sail's `vlen_exp` is **type**-level and constrained to
// `3 <= vlen_exp <= 16`. The two are not the same declaration and could not be:
// a Sail type-level configuration sizes the vector register file, so one build
// realizes one VLEN, and zero is not a vector geometry at all but the vectorless
// classes' declaration that they have none (R-15-113, R-15-041). What binds them
// is a refusal rather than a derivation, and it is stated where every other
// shape refusal is: a composition whose roster puts this hart on a class whose
// declared geometry is not the geometry this model was built at is refused
// (postlude/validate_config.sail).
type core_class_vlen_exp   = range(0, 16)
type core_class_elen_exp   = range(0, 16)
type core_class_lanes      = range(0, 255)
type core_class_matrix_dim = range(0, 255)
type core_class_scratchpad = range(0, 4294967295)
type core_class_issue      = range(0, 15)
type core_class_depth      = range(0, 63)

// The FEC decoders' realization geometry, which is **this machine's own** and
// not the channel codes' (R-15-119a). Each bound is a width and none of them is
// a value: what a composition may declare, never what it declares.
type core_class_fec_lanes  = range(0, 255)
type core_class_fec_block  = range(0, 65535)
type core_class_fec_iters  = range(0, 255)
type core_class_fec_list   = range(0, 255)

// The roster's own widths. `core_hartid` is the value space R-15-052b makes a
// composition-time constant, and `core_island` names the clock and power island
// a core is bound to, the third thing the kernel reads out of `mhartid`.
type core_hartid = range(0, 65535)
type core_island = range(0, 255)

// **The record is symmetric and the machine is not**, which is R-15-113's
// asymmetry rather than a composition's to choose, and the validator is where it
// is held. A vectorless class declares zero for every vector and matrix field,
// and a class with no systolic array declares zero for both matrix dimensions
// and for the scratchpad the array streams through. They are declared zero
// rather than omitted under the model's existing zero-is-absent idiom
// (`misaligned_atomicity_granule_size_exp`, sys/pma.sail), and anything else is
// refused.
//
//   - `vlen_exp` / `elen_exp`. Zero on the S class and the RoT, which are
//     scalar-only: no vector permutation instruction is reachable there, which
//     is why the RoT hashes SHA-3/SHAKE in plain 64-bit integer with `Zbb`
//     rotations rather than wanting a hardware round unit (R-15-041, R-15-042,
//     R-09-005a).
//   - `lanes`. The V class's decoupled long-vector unit is eight lanes in the
//     reference instantiation; a class with no long-vector unit declares zero.
//     Lane count is a datapath figure that no architectural result depends on,
//     which is why it is declared here and read by nothing.
//   - `matrix_int8_dim` / `matrix_bf16_dim`. The systolic array's two geometries
//     (R-15-113). The array consumes int8 and bf16 only: de-quantization and
//     microscaling block-scale application are software on the same class's
//     vector unit, so no block-scale register enters the frozen matrix ISA
//     (R-15-117), and nothing here is a place for one.
//   - `scratchpad_bytes`. The software-managed scratchpad the array streams
//     through, explicit capability-governed plain memory rather than a cache
//     (R-15-165, R-15-167). Scalar cores carry no local memory tier, so a scalar
//     class declares zero (R-15-168). Where it *is* in the address space is a
//     region class the address map declares and this table does not repeat
//     (sys/pma.sail), the two being held against each other by the validator so
//     that a size here and a range there cannot describe two scratchpads.
//   - `issue_width` / `pipeline_depth`. R-15-108's frozen parameters, and
//     R-15-108a's single Pareto axis with core count: each added C-class core
//     and each unit of issue width spend the same fixed, non-stackable area. The
//     model has no pipeline, so nothing reads either; they are declared because
//     a frozen parameter with nowhere to be written is a parameter the freeze
//     records in prose alone.
//   - `keccak_unit`. The frozen Keccak-f[1600] permutation is a single vector
//     instruction, so it is placed on the vector-bearing cores and not on the
//     vectorless sentinel or RoT (R-15-056, R-15-059). It is a class property
//     because the unit is a datapath attachment, and the validator refuses it on
//     a class that declares no vector geometry.
//   - `fec_parallelism`, `fec_max_block`, `fec_iterations` and `fec_polar_list`.
//     The FEC decoders' realization geometry, which R-15-119a sorts onto **this
//     machine's** side of the parameter split and R-15-108's exploration selects
//     like every other geometry it selects. The decoder parallelism, the maximum
//     lifted block length the datapath is sized for in soft symbols, the
//     deterministic iteration bound R-15-119 requires, and the successive-
//     cancellation list width are here; the LDPC base graph and lifting size and
//     the polar reliability sequence and rate-matching schedule are TS 38.212's
//     and are declared where the codes are (extensions/fec/fec_codes.sail).
//     Only the second of the four has a consumer, the refusal of a block longer
//     than the datapath is sized for; the other three are declared for the
//     reason `issue_width` and `pipeline_depth` are, a frozen parameter with
//     nowhere to be written being a parameter the freeze records in prose alone.
//     **The unit count is not among them and is not missing**: a class's FEC unit
//     count is the number of its roster entries carrying `fec_units`, exactly as
//     its core count is the number of its entries (R-15-113), and a declared
//     count beside an enumeration is the same fact written twice.
//   - `replicated`. The S class is one architectural core realized as a
//     detection-only lockstepped pair, and **the core-class table carries
//     replication for that row alone** (R-16-008d, R-16-008e). The comparator
//     holds no architectural state and changes no committed result, so this is a
//     composition fact and not a second core in the roster.
//
// `frozen` is a property of the **configuration** and not of the machine, and it
// is here for the reason `qualified` is in the memory-class record: a zero in
// this table has two readings and only an attestation separates them. In a row
// whose `frozen` is false a zero is *not selected*, R-15-108's exploration being
// the thing that selects it and not having run; in a row whose `frozen` is true
// a zero is *absent*, which is what the S class's vector geometry and the C
// class's matrix geometry are. R-15-113's figures are a reference instantiation
// rather than a freeze, and a table carrying them with nothing distinguishing
// them from selected values is how a placeholder becomes an architectural input.
// It is false in every configuration this tree ships, it is emitted into the
// generated devicetree beside the numbers it qualifies, and no property asserts
// its value: a test fixing it would be a test about the calendar.
struct CoreClassDatapath = {
  frozen           : bool,
  vlen_exp         : core_class_vlen_exp,
  elen_exp         : core_class_elen_exp,
  lanes            : core_class_lanes,
  matrix_int8_dim  : core_class_matrix_dim,
  matrix_bf16_dim  : core_class_matrix_dim,
  scratchpad_bytes : core_class_scratchpad,
  issue_width      : core_class_issue,
  pipeline_depth   : core_class_depth,
  keccak_unit      : bool,
  fec_parallelism  : core_class_fec_lanes,
  fec_max_block    : core_class_fec_block,
  fec_iterations   : core_class_fec_iters,
  fec_polar_list   : core_class_fec_list,
  replicated       : bool,
}

// One roster entry is one hart. `class` and `island` are the two things
// R-15-052b names beside the per-hart state, so they are what the roster carries
// and the whole of it.
//
//   - `pinned`. Pinning is an admission outcome and not a favour granted per
//     device: membership is decided by the R-11-011 switch-duty rule, where a
//     device server whose deadline-driven poll cadence would spend an
//     inadmissible fraction of a core on partition switching takes a core of its
//     class instead of a slot (R-15-114). The radio-pinned V pair and the S
//     sentinel are the current members. It is per **entry** rather than per
//     class because that is how the rule decides it, one core at a time.
//   - `fec_units`. The LDPC and polar decoders are attached to the radio V cores
//     under the coprocessor line: fixed-geometry arithmetic with deterministic
//     iteration bounds and core-issued capability-operand movement, no DMA
//     mastership and no firmware (R-15-119, R-12-038). They are per entry for
//     the same reason pinning is: they follow the pinned pair rather than the
//     class, and the scaling axis is core count and never a firmware processor
//     (R-15-134).
struct CoreRosterEntry = {
  hartid    : core_hartid,
  class     : CoreClass,
  island    : core_island,
  pinned    : bool,
  fec_units : bool,
}

let plat_core_class_c   : CoreClassDatapath = config platform.core_classes.c
let plat_core_class_v   : CoreClassDatapath = config platform.core_classes.v
let plat_core_class_m   : CoreClassDatapath = config platform.core_classes.m
let plat_core_class_s   : CoreClassDatapath = config platform.core_classes.s
let plat_core_class_rot : CoreClassDatapath = config platform.core_classes.rot

function core_class_datapath(c : CoreClass) -> CoreClassDatapath =
  match c {
    CoreClass_C   => plat_core_class_c,
    CoreClass_V   => plat_core_class_v,
    CoreClass_M   => plat_core_class_m,
    CoreClass_S   => plat_core_class_s,
    CoreClass_RoT => plat_core_class_rot,
  }

// The table's own enumeration order, as an index and its inverse. Two consumers
// want it and want it to agree: the validator walks every row, and the generated
// devicetree writes the roster as a flat cell array whose class column is this
// index, because a devicetree property carries cells or a string and not both
// (postlude/device_tree.sail). The tree emits the index beside each class node's
// name rather than leaving a reader to reconstruct the mapping from a comment,
// so what decodes the roster travels with it.
type core_class_index = range(0, 4)

function core_class_to_index(c : CoreClass) -> core_class_index =
  match c {
    CoreClass_C   => 0,
    CoreClass_V   => 1,
    CoreClass_M   => 2,
    CoreClass_S   => 3,
    CoreClass_RoT => 4,
  }

function core_class_of_index(i : core_class_index) -> CoreClass =
  match i {
    0 => CoreClass_C,
    1 => CoreClass_V,
    2 => CoreClass_M,
    3 => CoreClass_S,
    _ => CoreClass_RoT,
  }

// A class is vector-bearing iff it declares a vector geometry. This is the one
// derived predicate the table needs and it is stated once: the Keccak placement
// (R-15-059), the `vmclear` trap on a vectorless class (R-07-014c, R-15-069d),
// and the scalar-crypto retention for vectorless cores (R-15-042) are three
// consumers of one question, and a second spelling of it is how they would come
// to disagree.
function core_class_is_vector_bearing(c : CoreClass) -> bool =
  core_class_datapath(c).vlen_exp > 0

// **The matrix extension is fork-and-frozen and its re-pin obligation is
// standing, so it is recorded where the model declares the unit rather than left
// to a document.** R-15-009 carries full Sail semantics for the bespoke
// extension only *until a ratified RISC-V matrix extension of the AME/IME
// lineage supersedes it*, at which point it re-pins; that is the one obligation
// this model holds that no build, no gate, and no proof will ever discharge,
// because what closes it is an event at another standards body. Three things
// follow and each is a fact about this file rather than a plan.
//
// The obligation is on the **encoding and not on the semantics**: a re-pin
// substitutes a ratified instruction surface for a bespoke one over the same
// array, so what it must not do is widen what was frozen, which is the same
// discipline the Keccak fork takes in freezing both round counts ahead of its
// own re-pin (R-15-056a, R-15-057a). The geometries above are therefore the
// unit's whole architectural declaration and the re-pin does not touch them.
//
// The obligation is **conditional on an admission that is taken**: R-15-116
// admits the extension only against an order-of-magnitude sustained dense-GEMM
// margin over the same GEMM expressed as RVV on this class's own VLEN=1024
// unit, and the register records dense int8/bf16 inference clearing that bar
// and the extension kept. So the unit is admitted and it is the *instruction
// surface* that is unwritten, which is R-15-007j's question and not this
// requirement's: nothing enters the profile by inheritance, the frozen profile
// books the matrix extension as a unit and names no instruction for it, and an
// instruction the enumeration does not name is absent (isa-profile.md §3).
//
// And the unit **holds no state for the obligation to be about**. R-15-118's
// coprocessor line makes every byte it moves core-issued against an explicit
// capability operand, with no DMA mastership, no translation context, and no
// firmware, so what a partition can dirty is the scratchpad above and nothing
// else; that is why the partition switch's inventory names the scratchpad and
// stops (extensions/platform/vmclear.sail, R-07-014c).
function core_class_has_matrix(c : CoreClass) -> bool = {
  let d = core_class_datapath(c);
  d.matrix_int8_dim > 0 | d.matrix_bf16_dim > 0
}

// A class declares an FEC geometry iff it declares any of its four fields, and
// this is the one derived predicate that half of the table needs. It is stated
// once for the reason `core_class_is_vector_bearing` is: the validator's
// whole-or-nothing refusal and the vectorless refusal are two consumers of one
// question (R-15-119a).
function core_class_has_fec(c : CoreClass) -> bool = {
  let d = core_class_datapath(c);
  d.fec_parallelism > 0 | d.fec_max_block > 0 | d.fec_iterations > 0 | d.fec_polar_list > 0
}

// The composed roster. `platform.hartid` is an index into it rather than a value
// beside it, which is what makes R-15-052b's reachable value space a
// composition-time constant: a hart identity outside the roster is not a value
// this machine can present, because the validator refuses the composition that
// would present it.
let plat_hartid : core_hartid = config platform.hartid

register core_roster : list(CoreRosterEntry) = config platform.core_roster

function core_roster_lookup(roster : list(CoreRosterEntry), h : core_hartid) -> option(CoreRosterEntry) =
  match roster {
    [||]           => None(),
    entry :: rest  => if entry.hartid == h then Some(entry) else core_roster_lookup(rest, h),
  }

// The entry for the hart this model was built as. It is an `option` because the
// lookup is total over rosters and not because a valid composition may omit it:
// `check_core_roster` refuses one that does, so every path below that reads a
// class reads the class of a hart the roster names.
function this_core_entry() -> option(CoreRosterEntry) = core_roster_lookup(core_roster, plat_hartid)

function this_core_class() -> option(CoreClass) =
  match this_core_entry() {
    None()      => None(),
    Some(entry) => Some(entry.class),
  }

// A class's core count is the number of its roster entries, never a declared
// figure beside them (R-15-113). The S class's lockstep partner is not among
// them: it is one architectural core presenting one identity, and the
// replication is a field of the class rather than a second hart (R-16-008d).
function core_class_count(roster : list(CoreRosterEntry), c : CoreClass) -> nat =
  match roster {
    [||]          => 0,
    entry :: rest => (if entry.class == c then 1 else 0) + core_class_count(rest, c),
  }

function core_roster_size(roster : list(CoreRosterEntry)) -> nat =
  match roster {
    [||]          => 0,
    _ :: rest     => 1 + core_roster_size(rest),
  }

// The FEC unit count, derived from the roster and declared nowhere, which is
// R-15-113's rule for a count applied to the one geometry R-15-119a names that
// is an enumeration rather than a width. The decoders follow the statically
// pinned radio cores rather than the class (R-12-038), so the count is over
// entries and the geometry above is over classes.
function fec_unit_count(roster : list(CoreRosterEntry)) -> nat =
  match roster {
    [||]          => 0,
    entry :: rest => (if entry.fec_units then 1 else 0) + fec_unit_count(rest),
  }

// Whether this hart carries the decoders. It is the whole of the FEC decode
// surface's gate (extensions/fec/fec_insts.sail) and it is a **static** property
// of the composed hart, which is what makes it the roster's and not the class's.
function this_core_has_fec_units() -> bool =
  match this_core_entry() {
    Some(entry) => entry.fec_units,
    None()      => false,
  }
