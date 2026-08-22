// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Implementation of Physical Memory Attributes. These describe
// how memory accesses to different regions of memory behave.
// Very little is specified about PMAs, and there is no standard
// interface to query or control them. This implementation only
// provides static PMAs (dynamic PMAs are possible) and there
// is no way to query them (this information would normally be
// available in Device Tree, ACPI, or just "known").
//
// Since they are mostly implementation-defined, we try to
// provide a range of useful options that are likely to cover
// most implementations.

// Set of atomic instructions supported by memory.
// Each value is a superset of the previous ones.
//
// Four levels rather than seven, because the three above them graded a region
// by the *operand width* of the compare-and-swap it could carry, 4, 8 and 16
// bytes, and `Zacas` is gone (R-15-026, R-15-027). What is left still says
// everything a region has to say about the atomics this machine admits: the
// profile takes `Zaamo` and `Zabha` (R-15-024), which are one class of
// read-modify-write at four widths, so a region either carries none of them,
// the swap, the logical ones, or all of them, and `AMOArithmetic` is the top
// because there is nothing above it left to name. Width is not a level here
// and must not become one: `Zabha`'s byte and halfword forms are the same
// operation narrower, admitted by the extension in `amo_encoding_valid` and
// never by the region.
enum AtomicSupport = {
  AMONone,
  AMOSwap,
  AMOLogical,
  AMOArithmetic,
}

function pma_atomicity_support_gt(x : AtomicSupport, y : AtomicSupport) -> bool = num_of_AtomicSupport(x) > num_of_AtomicSupport(y)
function pma_atomicity_support_lt(x : AtomicSupport, y : AtomicSupport) -> bool = num_of_AtomicSupport(x) < num_of_AtomicSupport(y)
function pma_atomicity_support_ge(x : AtomicSupport, y : AtomicSupport) -> bool = num_of_AtomicSupport(x) >= num_of_AtomicSupport(y)
function pma_atomicity_support_le(x : AtomicSupport, y : AtomicSupport) -> bool = num_of_AtomicSupport(x) <= num_of_AtomicSupport(y)

overload operator > = {pma_atomicity_support_gt}
overload operator < = {pma_atomicity_support_lt}
overload operator >= = {pma_atomicity_support_ge}
overload operator <= = {pma_atomicity_support_le}

mapping atomic_support_str : AtomicSupport <-> string = {
  AMONone       <-> "AMONone",
  AMOSwap       <-> "AMOSwap",
  AMOLogical    <-> "AMOLogical",
  AMOArithmetic <-> "AMOArithmetic",
}
overload to_str = {atomic_support_str}

// The width the compare-and-swap arms discriminated on is gone with them, and
// the parameter that carried it with the width: what a region admits is a set
// of operations and never a size.
function pma_allows_atomic_op(pma : AtomicSupport, op : amoop) -> bool =
  match pma {
    AMONone       => false,
    AMOSwap       => op == AMOSWAP,
    AMOLogical    => op == AMOSWAP | op == AMOAND | op == AMOOR | op == AMOXOR,
    AMOArithmetic => true,
  }

enum MemoryRegionType = { MainMemory, IOMemory }
mapping memory_region_type_str : MemoryRegionType <-> string = {
  MainMemory <-> "main memory",
  IOMemory   <-> "IO memory",
}
overload to_str = {memory_region_type_str}

// PMA misalignment handling.
struct PMAMisalignedExceptions = {
  load_store : option(misaligned_exception),
  vector     : option(misaligned_exception),
  amo        : misaligned_exception,
}

// Physical Memory Attributes for a region.
struct PMA = {
  mem_type         : MemoryRegionType,
  // These have no effect on the model currently.
  cacheable        : bool,
  coherent         : bool,
  // If false then attempting to access this PMA during instruction fetch
  // will cause a fetch access fault.
  executable       : bool,
  // If false when reading/writing for data access then this will cause
  // an access fault.
  readable         : bool,
  writable         : bool,
  read_idempotent  : bool,
  write_idempotent : bool,
  // Misaligned handling for various accesses.
  misaligned_exceptions : PMAMisalignedExceptions,
  atomic_support   : AtomicSupport,
  // Flags whether this memory supports CBO.zero. Note that main memory regions must
  // have this set.
  supports_cbo_zero : bool,
  // The size of the optional misaligned atomicity granule is 2^misaligned_atomicity_granule_exp.
  // The value of 0 is used to indicate the attribute is absent.
  misaligned_atomicity_granule_size_exp : mag_size_exp,
  // The same as above but for vector accesses.
  vector_misaligned_atomicity_granule_size_exp : mag_size_exp,
  // Which of the two static latency classes this region is placed on
  // (core/memory_class.sail, R-15-247). It is `None` for IO memory and
  // `Some` for main memory, and the validator holds both directions: the
  // classes are two media, so a device endpoint is on neither and an array
  // is on exactly one. Placement is the static memory plan's composition-time
  // act, so this is a declaration and never a runtime property; nothing
  // reads it on any access path.
  memory_class : option(MemoryClass),
  // The datapath whose **software-managed scratchpad** this region is, or
  // `None` for every ordinary region (core/core_class.sail, R-15-165,
  // R-15-167).
  //
  // **A scratchpad is a region class and not a structure**, which is the whole
  // of what the model can carry about one. R-15-167 makes it capability-governed
  // plain memory at a fixed address range: no fill, no eviction, no valid or tag
  // array, and no lookup that is not the ordinary address decode, so it is
  // *declared* here beside every other property the composition fixes about an
  // address range rather than modeled as a second memory. R-15-165's test is
  // what that buys: the contents are a function of an explicit software
  // placement and never of access history, and it is history-dependence and not
  // address-indexing that carries the channel.
  //
  // **It is on neither main-memory latency class, and that is a placement fact
  // rather than an omission.** R-15-247's two classes are two media of *main*
  // memory; a scratchpad is the local tier above them, which R-15-168 says
  // scalar cores do not have at all. So `memory_class` is `None` here where it
  // is `Some` on every other array, and the validator holds the pair in both
  // directions rather than leaving a scratchpad to read as an unplaced array
  // (postlude/validate_config.sail).
  //
  // **Whose it is, is carried rather than derived.** R-15-165 places scratchpads
  // on the V- and M-class datapaths and R-15-113 sizes each class's in the class
  // table, so a region naming its class is what lets the two be held against
  // each other: a declared range whose size is not the class's declared
  // `scratchpad_bytes` is a composition describing two different scratchpads,
  // and neither artifact alone can see it.
  //
  // **Nothing on any access path reads it**, for the reason `memory_class`
  // states next door: the region is ordinary capability-governed memory, and
  // R-08-003's checks reach it unchanged, so a load or store that consulted this
  // field would be a machine deciding at run time what the memory plan decided
  // at composition. Its readers are the validator, the generated devicetree, the
  // `vmclear` pass R-07-014c defines over it, and the model's own properties.
  scratchpad : option(CoreClass),
  // TODO: Memory Ordering PMA
}

// Provide the misaligned treatment for a misaligned access.
function pma_misaligned_exception(pma : PMA, access : MemoryAccessType(mem_payload)) -> option(misaligned_exception) = {
  let exceptions = pma.misaligned_exceptions;
  match access {
    Load(Data)             => exceptions.load_store,
    Store(Data)            => exceptions.load_store,
    Load(Vector)           => exceptions.vector,
    Store(Vector)          => exceptions.vector,
    Atomic(_)              => Some(exceptions.amo),

    // These access types should not be misaligned at the PMA level.
    InstructionFetch()        => internal_error(__FILE__, __LINE__, "PMA: Invalid misaligned instruction fetch."),
    CacheAccess(_)            => internal_error(__FILE__, __LINE__, "PMA: Invalid misaligned cache-access."),
  }
}

private function is_mag_applicable_access(access : MemoryAccessType(mem_payload), width : nat) -> bool =
  // Note below that most of the accesses to which the MAG does not
  // apply cannot be misaligned at the PMA level.
  match access {
    // Loads/stores need to be XLEN bits or less.
    Load(Data)                          => width <= xlen_bytes,
    Store(Data)                         => width <= xlen_bytes,
    // Vector accesses use a separate MAG PMA; currently, this doesn't
    // condition the accesses on width like the scalar MAG does above.
    Load(Vector)                        => true,
    Store(Vector)                       => true,
    // AMOs
    Atomic(_)                           => true,

    // Other not applicable.
    InstructionFetch()                  => false,
    CacheAccess(_)                      => false,
  }

function mag_of_pma(pma : PMA, is_vector : bool) -> option(range(1, 12)) = {
  let mag = if is_vector
            then pma.vector_misaligned_atomicity_granule_size_exp
            else pma.misaligned_atomicity_granule_size_exp;
  // 0 implies no MAG present
  if  mag == 0 then None() else Some(mag)
}

// Check whether an access location is within a misaligned atomicity granule, if present.
function within_pma_mag forall 'n, 0 < 'n <= max_mem_access. (pma : PMA, Physaddr(addr) : physaddr, width : int('n), is_vector : bool) -> bool =
  match mag_of_pma(pma, is_vector) {
    None()    => false,
    // PMAs are restricted to page boundaries, so we can use the lowest xlen bits of the address.
    Some(mag) => allowed_misaligned(addr[xlen - 1 .. 0], width, mag),
  }

// This function implements the check for the MAG PMA.
function mag_pma_check forall 'n, 0 < 'n <= max_mem_access.
(
  pma     : PMA,
  access  : MemoryAccessType(mem_payload),
  paddr   : physaddr,
  width   : int('n)
) -> result((Splittability, mag_size_exp), misaligned_exception) = {

  let is_mag_applicable = is_mag_applicable_access(access, width);

  // If the access is aligned, it cannot be split, irrespective of the
  // MAG PMA.  If it is misaligned and the MAG PMA is applicable, it
  // cannot be split if the access is within the MAG granule.
  if is_aligned_addr(paddr, width) |
     (is_mag_applicable & within_pma_mag(pma, paddr, width, is_vector_access(access)))
  then return Ok((CannotSplit, 0));

  // If we get here, the misaligned access cannot be done in a single
  // (i.e. unsplit) memory operation.  Either the access can be split,
  // or an exception needs to be raised.  If the MAG is not applicable
  // to the misaligned access, e.g. for wide (> XLEN bits) F/D/Q
  // loads/stores, the access is handled according to the misaligned
  // exception for the PMA.
  match pma_misaligned_exception(pma, access) {
    Some(e) => Err(e),

    // If there is no misaligned exception, then the misaligned access
    // may proceed without atomicity.
    None() =>  match (is_mag_applicable, mag_of_pma(pma, is_vector_access(access))) {
      (true, Some(mag)) => Ok((CanSplit, mag)),
      // If the MAG is not applicable, or no MAG is specified, use the global setting.
      (_,    _        ) => Ok((CanSplit, sys_misaligned_allowed_within_exp)),
    }
  }
}

// A region of memory and its Physical Memory Attributes.
struct PMA_Region = {
  // TODO: These should be physaddrbits, but currently that doesn't work due to a compiler bug:
  // https://github.com/rems-project/sail/issues/1392
  base       : bits(64),
  size       : bits(64),
  attributes : PMA,
  // If set to `false` this will be excluded from the generated device tree.
  // This doesn't affect Sail's execution at all; it's just a convenience
  // for generating a device tree that matches the PMAs.
  include_in_device_tree : bool,
}

// Get the first PMA region that fully contains a given [base, base+size) range.
function matching_pma_region_bits_range(regions : list(PMA_Region), base : bits(64), size : bits(64)) -> option(PMA_Region) = {
  match regions {
    [||] => None(),
    region :: rest => {
      if range_subset(base, size, region.base, region.size)
      then Some(region)
      else matching_pma_region_bits_range(rest, base, size)
    }
  }
}

// Get the first PMA region that matches a given address range.
// Delegate to matching_pma_region_bits_range to avoid duplicating the range logic.
function matching_pma_region(regions : list(PMA_Region), addr : physaddr, width : mem_access_width) -> option(PMA_Region) = {
  matching_pma_region_bits_range(regions, zero_extend(bits_of(addr)), to_bits(width))
}

function pma_misaligned_to_str(m : PMAMisalignedExceptions) -> string =
  "misaligned-load-store:" ^ optional_misaligned_exception_str(m.load_store) ^
  " misaligned-amo:" ^ misaligned_exception_str(m.amo) ^
  " misaligned-vector:" ^ optional_misaligned_exception_str(m.vector)

overload to_str = {pma_misaligned_to_str}

function pma_attributes_to_str(attr : PMA) -> string =
  (match attr.mem_type { MainMemory => " main-memory", IOMemory => " io-memory", }) ^
  (if attr.cacheable then " cacheable" else "") ^
  (if attr.coherent then " coherent" else "") ^
  (if attr.executable then " executable" else "") ^
  (if attr.readable then " readable" else "") ^
  (if attr.writable then " writable" else "") ^
  (if attr.read_idempotent then " read-idempotent" else "") ^
  (if attr.write_idempotent then " write-idempotent" else "") ^
  " " ^ to_str(attr.misaligned_exceptions) ^
  " " ^ to_str(attr.atomic_support) ^
  (if attr.supports_cbo_zero then " supports-cbo-zero" else "") ^
  " misaligned_atomicity_granule_size_exp=" ^ dec_str(attr.misaligned_atomicity_granule_size_exp) ^
  " vector_misaligned_atomicity_granule_size_exp=" ^ dec_str(attr.vector_misaligned_atomicity_granule_size_exp) ^
  (match attr.memory_class {
     None()  => "",
     Some(c) => " memory-class=" ^ memory_class_str(c),
   }) ^
  (match attr.scratchpad {
     None()  => "",
     Some(c) => " scratchpad=" ^ core_class_str(c),
   }) ^
  " "

function pma_region_to_str(region : PMA_Region) -> string =
  "base: " ^ bits_str(region.base) ^ " size: " ^ bits_str(region.size)
    ^ pma_attributes_to_str(region.attributes)

overload to_str = {pma_attributes_to_str, pma_region_to_str}

// The list of PMA regions. These must be sorted and cannot overlap.
register pma_regions : list(PMA_Region) = config memory.regions

// The class an address is placed on, or `None` where it is not main memory
// (core/memory_class.sail, R-15-247).
//
// **This is a query about the composition and not a step of any access.** No
// load, store, fetch, atomic, or cache-block operation calls it, and none may:
// the class is two latency constants under one placement discipline, so an
// access consulting it would be a machine deciding at run time what the memory
// plan decided at composition, which is the hierarchy R-15-247 exists to refuse.
// Its callers are the generated devicetree, the validator, and the model's own
// properties, all of which ask about the plan rather than about an access.
function memory_class_at(addr : physaddr) -> option(MemoryClass) =
  match matching_pma_region(pma_regions, addr, 1) {
    None()       => None(),
    Some(region) => region.attributes.memory_class,
  }

// The datapath whose scratchpad an address falls in, or `None` where it falls in
// no scratchpad (R-15-165, R-15-167). It asks the same kind of question
// `memory_class_at` asks and carries the same prohibition: it is about the
// composition's placement and never a step of an access.
function scratchpad_class_at(addr : physaddr) -> option(CoreClass) =
  match matching_pma_region(pma_regions, addr, 1) {
    None()       => None(),
    Some(region) => region.attributes.scratchpad,
  }

// The region a class's scratchpad is, walked from the class rather than from an
// address, which is the direction the validator, the devicetree, and the
// `vmclear` pass all want it in: each of them starts from a core class and asks
// where its scratchpad is, and none of them holds an address to start from.
//
// `option` because most classes have none. R-15-168 gives the scalar classes no
// local memory tier at all, and a class whose exploration has not selected a
// size declares zero and gets no region, which is the state every configuration
// this tree ships is in (R-15-108).
function scratchpad_region_of(regions : list(PMA_Region), c : CoreClass) -> option(PMA_Region) =
  match regions {
    [||] => None(),
    region :: rest =>
      if region.attributes.scratchpad == Some(c)
      then Some(region)
      else scratchpad_region_of(rest, c),
  }

// The declared extent of a class's scratchpad, in bytes, read off the region
// that is it rather than off the class table that sizes it. The two are held
// against each other by the validator, so this is the same number by the time
// the machine runs; it is read from here and not from there because what a pass
// over the scratchpad needs is the *placement*, and a size with no base is not
// one.
function scratchpad_extent_of(c : CoreClass) -> (bits(64), bits(64)) =
  match scratchpad_region_of(pma_regions, c) {
    None()       => (zeros(), zeros()),
    Some(region) => (region.base, region.size),
  }
