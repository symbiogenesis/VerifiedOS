// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Physical memory model.
//
// This assumes that the platform memory map has been defined, so that accesses
// to MMIO regions can be dispatched.
//
// The implementation below supports the reading and writing of memory
// metadata in addition to raw memory data.
//
// The external API for this module is composed of three central functions
//
//   mem_read_meta
//   mem_write_ea
//   mem_write_value_meta
//
// and some special cases which partially apply these functions:
//
//   mem_read         - strips metadata from reads
//   mem_write_value  - uses a default value for metadata
//
// The internal implementation performs a PMA check and then dispatches
// to MMIO regions or physical memory as per the platform memory map.
// There is no second protection check to sequence it against: CHERI is
// the sole memory-protection mechanism, so PMP is absent (R-15-075) and
// the accesses carry no privilege, there being one privilege mode
// (R-15-003).

// The reservation flag these once carried is gone with `Zalrsc`
// (R-15-025): the only reserved read and conditional write left on the
// machine are the two halves of an AMO, so atomicity is read off the
// access type rather than passed beside it.

private function read_kind_of_flags (aq : bool, rl : bool, access : MemoryAccessType(mem_payload)) -> read_kind =
  match (aq, rl, is_amo_access(access)) {
    (false, false, false) => Read_plain,
    (true, false, false)  => internal_error(__FILE__, __LINE__, "Non-atomic load with acquire semantics should be unreachable"),
    (true, true, false)   => internal_error(__FILE__, __LINE__, "Non-atomic load with acquire-release semantics should be unreachable"),
    (false, false, true)  => Read_RISCV_reserved,
    (true, false, true)   => Read_RISCV_reserved_acquire,
    (true, true, true)    => Read_RISCV_reserved_strong_acquire,
    // This is never called with rl=true and aq=false.
    (false, true, false)  => internal_error(__FILE__, __LINE__, "Non-atomic load with release semantics should be unreachable"),
    (false, true, true)   => internal_error(__FILE__, __LINE__, "Atomic load with release semantics should be unreachable"),
  }

function write_kind_of_flags (aq : bool, rl : bool, access : MemoryAccessType(mem_payload)) -> write_kind =
  match (aq, rl, is_amo_access(access)) {
    (false, false, false) => Write_plain,
    (false, true,  false) => internal_error(__FILE__, __LINE__, "Non-atomic store with release semantics should be unreachable"),
    (false, false, true)  => Write_RISCV_conditional,
    (false, true , true)  => Write_RISCV_conditional_release,
    (true,  true,  false) => internal_error(__FILE__, __LINE__, "Non-atomic store with acquire-release semantics should be unreachable"),
    (true,  true , true)  => Write_RISCV_conditional_strong_release,
    // This is never called with aq=true and rl=false.
    (true,  false, false) => internal_error(__FILE__, __LINE__, "Non-atomic store with acquire semantics should be unreachable"),
    (true,  false, true)  => internal_error(__FILE__, __LINE__, "Atomic store with acquire semantics should be unreachable"),
  }


// Information used to access physical memory.
//
// It specifies whether the access should be split, and if so, the MAG
// granule to use. In future, this could be extended to cover memory
// ordering properties.

struct Phys_Mem_Access_Info = {
  // Whether the access should be split.
  splittable : Splittability,
  // The granule size to use for any splitting.
  granule_size_exp : mag_size_exp,
}

private function pmaCheck forall 'n, 0 < 'n <= max_mem_access .
(
  paddr      : physaddr,
  width      : int('n),
  access     : MemoryAccessType(mem_payload),
)  -> result(Phys_Mem_Access_Info, ExceptionType) = {

  // With no page tables there is no PBMT override: a region's PMA is
  // whatever the platform configuration declares it to be.
  let attributes : PMA = match matching_pma_region(pma_regions, paddr, width) {
    None() =>
      return Err(accessFaultFromAccessType(access)),
    Some(struct { attributes, _ }) =>
      attributes,
  };

  // The spec is silent about the order in which PMA checks are done,
  // but access faults have higher priority than misaligned exceptions
  // so those are checked first. See the "Synchronous exception
  // priority in decreasing priority order." table in the ISA manual.

  let canAccess : bool = match access {
    InstructionFetch()     => attributes.executable,
    Load(_)                => attributes.readable,
    Store(_)               => attributes.writable,

    Atomic(op, _, _, _, _) => attributes.readable & attributes.writable & pma_allows_atomic_op(attributes.atomic_support, op, width),

    // "A cache-block zero instruction is permitted to access
    // the specified cache block whenever a store instruction
    // is permitted to access the corresponding physical
    // addresses and when the PMAs indicate that cache-block
    // zero instructions are a supported access type."
    CacheAccess(CB_zero())      => attributes.writable & attributes.supports_cbo_zero,
  };

  if not(canAccess) then {
    if get_config_print_pma()
    then print_log("PMA access check failed for a " ^ dec_str(width) ^ "-byte wide " ^ to_str(access) ^ " access to address " ^ hex_bits_str(bits_of(paddr)) ^ " with PMA {" ^ to_str(attributes) ^ "}");

    return Err(accessFaultFromAccessType(access));
  };

  // Check if we need to raise an exception for misalignment.

  match mag_pma_check(attributes, access, paddr, width) {
    Ok((splittable, granule_size_exp)) => Ok(struct { splittable, granule_size_exp }),

    Err(e) => {
      if get_config_print_pma()
      then print_log("MAG PMA check failed for a " ^ dec_str(width) ^ "-byte wide " ^ to_str(access) ^ " access to address " ^ hex_bits_str(bits_of(paddr)) ^ " with PMA {" ^ to_str(attributes) ^ "}");
      match e {
        AccessFault        => Err(accessFaultFromAccessType(access)),
        AlignmentException => Err(alignmentFaultFromAccessType(access)),
      }
    },
  }
}

// Check if access is permitted according to the PMAs.
// NOTE: this function is only used for unsplit accesses such
// as CBOs and an unpaired SC.
function phys_access_check forall 'n, 0 < 'n <= max_mem_access . (
  access : MemoryAccessType(mem_payload),
  paddr : physaddr,
  width : int('n),
) -> result(Phys_Mem_Access_Info, ExceptionType) =
  pmaCheck(paddr, width, access)

// dispatches to MMIO regions or physical memory regions depending on physical memory map
private function checked_mem_read forall 'n, 0 < 'n <= max_mem_access . (
  access : MemoryAccessType(mem_payload),
  paddr : physaddr,
  width : int('n),
  aq : bool,
  rl : bool,
  meta : bool,
) -> MemoryOpResult((bits(8 * 'n), mem_meta)) = {

  let access_info : Phys_Mem_Access_Info = match pmaCheck(paddr, width, access) {
    Ok(access_info) => access_info,
    Err(e)          => return Err(paddr, e),
  };

  // Split into `N` (single-copy-atomic) memory operations, each
  // of `split_width` width. If the access is aligned, then `N` = 1
  // and `split_width` == `width`.
  let ('N, 'split_width) = split_misaligned(paddr, width, access_info.granule_size_exp, access_info.splittable);

  let paddr_bits = bits_of(paddr);

  var data = zeros(8 * N * split_width);

  // The metadata a read returns is the conjunction of what its splits carry,
  // and MMIO carries none. An unsplit access is the case that matters, and
  // there the conjunction is that granule's validity tag exactly, which is what
  // a capability load reads (extensions/CHERI/cheri_mem.sail). A split access
  // spans more than one granule, so no single tag belongs to it and the
  // conjunction is the conservative answer: one cleared granule clears the
  // result, which is the same polarity as the write path's clearing of every
  // granule it covers (R-15-007r, R-15-203).
  var read_meta : mem_meta = meta;

  let (first, last, step) = misaligned_order(N);
  var i : range(0, 'N - 1) = first;
  var finished : bool = false;

  let rk = read_kind_of_flags(aq, rl, access);

  repeat {
    let offset = i;
    let paddr = Physaddr(paddr_bits + (offset * split_width));

    // Since splitting is within 4K boundaries and PMAs are
    // page-aligned, every split will be in a homogeneous region,
    // though the code looks otherwise.

    let split_data =
      if   within_mmio_readable(paddr, split_width)
      then {
        read_meta = false;
        match mmio_read(access, paddr, split_width) {
          Err(e) => return Err(e),
          Ok(mmio_data) => mmio_data,
        }
      } else {
        let (ram_data, ram_meta) = read_ram(rk, paddr, split_width, meta);
        read_meta = read_meta & ram_meta;
        ram_data
      };
    data[(8 * (offset + 1) * split_width - 1) .. 8 * offset * split_width] = split_data;

    if offset == last then {
      finished = true
    } else {
      i = offset + step
    }
  } until finished;

  Ok((data, read_meta))
}

// This lets the Rocq extraction know why the repeat loop above terminates
termination_measure checked_mem_read repeat N

// Atomic accesses can be done to MMIO regions, e.g. in kernel access to device registers.

val mem_read      : forall 'n, 0 < 'n <= max_mem_access . (MemoryAccessType(mem_payload), physaddr, int('n), bool, bool)       -> MemoryOpResult(bits(8 * 'n))
val mem_read_meta : forall 'n, 0 < 'n <= max_mem_access . (MemoryAccessType(mem_payload), physaddr, int('n), bool, bool, bool) -> MemoryOpResult((bits(8 * 'n), mem_meta))

// The most generic memory read operation
function mem_read_meta (access, paddr, width, aq, rl, meta) = {
  let result : MemoryOpResult((bits(8 * 'n), mem_meta)) = match (aq, rl) {
    (false, true) => throw(Error_not_implemented("load.rl")),
    (_, _)        => checked_mem_read(access, paddr, width, aq, rl, meta)
  };
  match result {
    Ok(value, tag) => mem_read_callback(to_str(access), bits_of(paddr), width, value, tag),
    Err(addr, e) => mem_exception_callback(bits_of(addr), exceptionType_bits(e)),
  };
  result
}

// Specialized mem_read_meta that drops the metadata
function mem_read (access, paddr, width, aq, rel) =
  MemoryOpResult_drop_meta(mem_read_meta(access, paddr, width, aq, rel, false))

// This function is always called before `mem_write_value`.
val mem_write_ea : forall 'n, 0 < 'n <= max_mem_access . (physaddr, int('n), MemoryAccessType(mem_payload), bool, bool) -> MemoryOpResult(unit)
function mem_write_ea(paddr, width, access, aq, rl) = {
  // This function should only succeed when `mem_write_value` would
  // succeed, and fail when `mem_write_value` would fail. This means
  // it should at least perform the same PMA checks, and includes
  // matching behavior for split accesses.
  //
  // However, there is a corner case that is not handled here: writes
  // to MMIO regions, where the failure of those writes can only be
  // determined currently by actually trying to perform those
  // writes. In such cases, `mem_write_ea` could still succeed when
  // the `mem_write_value` would fail. Since `mem_write_ea` is used
  // only for the concurrency model, this will be an issue when that
  // model is extended for MMIO, but until then, this should suffice
  // for concurrency of RAM accesses.

  let access_info : Phys_Mem_Access_Info = match pmaCheck(paddr, width, access) {
    Ok(access_info) => access_info,
    Err(e)          => return Err(paddr, e),
  };

  let ('N, 'split_width) = split_misaligned(paddr, width, access_info.granule_size_exp, access_info.splittable);

  let paddr_bits = bits_of(paddr);

  let (first, last, step) = misaligned_order(N);
  var i : range(0, 'N - 1) = first;
  var finished : bool = false;

  let wk = write_kind_of_flags(aq, rl, access);

  repeat {
    let offset = i;
    let paddr = Physaddr(paddr_bits + (offset * split_width));

    write_ram_ea(wk, paddr, split_width);

    if offset == last then {
      finished = true
    } else {
      i = offset + step
    }

  } until finished;

  Ok(())
}

// This lets the Rocq extraction know why the repeat loop above terminates
termination_measure mem_write_ea repeat N

// dispatches to MMIO regions or physical memory regions depending on physical memory map
function checked_mem_write forall 'n, 0 < 'n <= max_mem_access . (
  paddr : physaddr,
  width : int('n),
  data: bits(8 * 'n),
  access : MemoryAccessType(mem_payload),
  meta: mem_meta,
  aq : bool,
  rl : bool,
) -> MemoryOpResult(bool) = {

  let access_info : Phys_Mem_Access_Info = match pmaCheck(paddr, width, access) {
    Ok(access_info) => access_info,
    Err(e)          => return Err(paddr, e),
  };

  // Split into `N` (single-copy-atomic) memory operations, each
  // of `split_width` width. If the access is aligned, then `N` = 1
  // and `split_width` == `width`.
  let ('N, 'split_width) = split_misaligned(paddr, width, access_info.granule_size_exp, access_info.splittable);
  // TODO: handle any splits of metadata across the splits.

  let paddr_bits = bits_of(paddr);
  var write_success : bool = true;

  let (first, last, step) = misaligned_order(N);
  var i : range(0, 'N - 1) = first;
  var finished : bool = false;

  let wk = write_kind_of_flags(aq, rl, access);

  repeat {
    let offset = i;
    let paddr = Physaddr(paddr_bits + (offset * split_width));

    let write_value = data[(8 * (offset + 1) * split_width) - 1 .. 8 * offset * split_width];

    // See comment above in `checked_mem_read` about the
    // homogeneity of the split accesses.
    if   within_mmio_writable(paddr, split_width)
    then match mmio_write(paddr, split_width, write_value) {
      Ok(v)  => write_success = write_success & v,
      Err(e) => return Err(e),
    } else {
      // This assumes that the same metadata applies to every split.
      let v = write_ram(wk, paddr, split_width, write_value, meta);
      write_success = write_success & v
    };

    if offset == last then {
      finished = true
    } else {
      i = offset + step
    }
  } until finished;

  Ok(write_success)
}

// This lets the Rocq extraction know why the repeat loop above terminates
termination_measure checked_mem_write repeat N

// Atomic accesses can be done to MMIO regions, e.g. in kernel access to device registers.

// Memory write with an explicit metadata value.  Metadata writes are
// currently assumed to have the same alignment constraints as their
// data.
val mem_write_value_meta : forall 'n, 0 < 'n <= max_mem_access . (physaddr, int('n), bits(8 * 'n), MemoryAccessType(mem_payload), mem_meta, bool, bool) -> MemoryOpResult(bool)
function mem_write_value_meta (paddr, width, value, access, meta, aq, rl) = {
  let result = checked_mem_write(paddr, width, value, access, meta, aq, rl);
  match result {
    Ok(_) => mem_write_callback(to_str(access), bits_of(paddr), width, value, meta),
    Err(addr, e) => mem_exception_callback(bits_of(addr), exceptionType_bits(e)),
  };
  result
}

// Memory write with explicit MemoryAccessType and default metadata
val mem_write_value : forall 'n, 0 < 'n <= max_mem_access . (physaddr, int('n), bits(8 * 'n), MemoryAccessType(mem_payload), bool, bool) -> MemoryOpResult(bool)
function mem_write_value (paddr, width, value, access, aq, rl) = {
  mem_write_value_meta(paddr, width, value, access, default_meta, aq, rl)
}
