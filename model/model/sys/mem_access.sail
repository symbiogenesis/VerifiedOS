// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The data-side memory accessors instruction definitions call. (The
// instruction side is `postlude/fetch.sail`.)
//
// These accessors compute an effective address, apply the global
// misalignment policy, and return a Retire_Failure on error. There is
// no address translation between them and physical memory: `satp` is
// Bare and the page-table walker is deleted with the MMU (R-15-002,
// R-15-038), so an effective address *is* a physical address and the
// page-boundary split the translating model performed has nothing to
// split on. That is why these are `data_*` rather than upstream's
// `vmem_*`: there is no virtual memory for them to be the front of.
//
// All addresses are provided in integer source register arguments.
//
// The Misaligned Atomicity Granule requires that misaligned loads,
// stores, and AMOs that do not cross a PMA granule boundary are
// atomic. Misaligned accesses that pass the global misaligned checks
// (as configured by `memory.misaligned`) are passed down intact to
// `mem.sail`, where PMA checks are done.

function plat_misaligned_exception(access : MemoryAccessType(mem_payload)) -> option(misaligned_exception) = {
  if is_amo_access(access) then plat_misaligned_access.amo
  else if is_vector_access(access) then plat_misaligned_access.vector
  else plat_misaligned_access.load_store
}

// Memory exceptions from `mem.sail` are reported in terms of
// `physaddr`, while the utilities here report them in terms of the
// corresponding `virtaddr`.

private function offset_virtaddr_by(
  Virtaddr(base_vaddr) : virtaddr,
  Physaddr(base_paddr) : physaddr,
  Physaddr(exc_paddr)  : physaddr,
) -> virtaddr = {
  // Physical addresses may have a different size.
  let offset = (exc_paddr - base_paddr)[xlen - 1 .. 0];
  Virtaddr(base_vaddr + offset)
}

// External API

// With pointer masking deleted there is nothing to transform: the effective
// address is the address the instruction computed.
function transform_effective_address(vaddr : virtaddr, _access : MemoryAccessType(mem_payload)) -> virtaddr = vaddr

val data_read_addr : forall 'width, is_mem_width('width).
  (virtaddr, int('width), MemoryAccessType(mem_payload), bool, bool)
  -> result(bits(8 * 'width), ExecutionResult)

function data_read_addr(vaddr, width, access, aq, rl) = {
  if not(is_aligned_addr(vaddr, width)) then {
    match plat_misaligned_exception(access) {
      Some(AccessFault)        => return Err(memory_exception(vaddr, E_Load_Access_Fault())),
      Some(AlignmentException) => return Err(memory_exception(vaddr, E_Load_Addr_Align())),
      // Even if the CPU does support misaligned accesses, it might be
      // that the PMA doesn't support misaligned accesses so you can
      // still get a fault below.
      None()                   => (),
    };
  };

  let paddr = physical_address(vaddr);

  match mem_read(access, paddr, width, aq, rl) {
    Err(exc_paddr, e) => {
      let exc_vaddr = offset_virtaddr_by(vaddr, paddr, exc_paddr);
      Err(memory_exception(exc_vaddr, e))
    },

    Ok(v) => Ok(v),
  }
}

val data_write_addr : forall 'width, is_mem_width('width).
  (virtaddr, int('width), bits(8 * 'width), MemoryAccessType(mem_payload), bool, bool)
  -> result(bool, ExecutionResult)

function data_write_addr(vaddr, width, data, access, aq, rl) = {
  // See comments in data_read_addr for an explanation of this check.
  if not(is_aligned_addr(vaddr, width)) then {
    match plat_misaligned_exception(access) {
      Some(AccessFault)        => return Err(memory_exception(vaddr, E_SAMO_Access_Fault())),
      Some(AlignmentException) => return Err(memory_exception(vaddr, E_SAMO_Addr_Align())),
      None()                   => (),
    };
  };

  // NOTE: The `mem_write_value` call here goes down to the physical
  // memory layer, where it may get split to handle misalignment.
  // This may result in mismatches with the `mem_write_ea` call: one
  // `mem_write_ea` call with a wider width may be called for multiple
  // lower level value writes of smaller widths.  This needs to be
  // handled along with https://github.com/riscv/sail-riscv/issues/1761.

  let paddr = physical_address(vaddr);

  match mem_write_ea(paddr, width, access, aq, rl) {
    Err(exc_paddr, e) => {
      let exc_vaddr = offset_virtaddr_by(vaddr, paddr, exc_paddr);
      Err(memory_exception(exc_vaddr, e))
    },

    Ok(()) => match mem_write_value(paddr, width, data, access, aq, rl) {
      Err(exc_paddr, e) => {
        let exc_vaddr = offset_virtaddr_by(vaddr, paddr, exc_paddr);
        Err(memory_exception(exc_vaddr, e))
      },

      Ok(s) => Ok(s),
    },
  }
}

// Compute effective address with extension checks.
function get_transformed_data_addr(base : regidx, offset : xlenbits, acc : MemoryAccessType(mem_payload), width : mem_access_width)
         -> Ext_DataAddr_Check(ext_data_addr_error) = {
  match ext_data_get_addr(base, offset, acc, width) {
    Ext_DataAddr_Error(e) => Ext_DataAddr_Error(e),
    Ext_DataAddr_OK(vaddr) => {
      let vaddr = transform_effective_address(vaddr, acc);
      Ext_DataAddr_OK(vaddr)
    }
  }
}

val data_read : forall 'width, is_mem_width('width).
  (regidx, xlenbits, int('width), MemoryAccessType(mem_payload), bool, bool)
  -> result(bits(8 * 'width), ExecutionResult)

function data_read(rs, offset, width, access, aq, rl) = {
  // Get the address, X(rs1) + offset.
  // Extensions might perform additional checks on address validity.
  let vaddr : virtaddr = match get_transformed_data_addr(rs, offset, access, width) {
    Ext_DataAddr_OK(vaddr) => vaddr,
    Ext_DataAddr_Error(e)  => return Err(Ext_DataAddr_Check_Failure(e)),
  };

  data_read_addr(vaddr, width, access, aq, rl)
}

val data_write : forall 'width, is_mem_width('width).
  (regidx, xlenbits, int('width), bits(8 * 'width), MemoryAccessType(mem_payload), bool, bool)
  -> result(bool, ExecutionResult)

function data_write(rs_addr, offset, width, data, access, aq, rl) = {
  // Get the address, X(rs_addr) + offset.
  // Extensions might perform additional checks on address validity.
  let vaddr : virtaddr = match get_transformed_data_addr(rs_addr, offset, access, width) {
    Ext_DataAddr_OK(vaddr) => vaddr,
    Ext_DataAddr_Error(e)  => return Err(Ext_DataAddr_Check_Failure(e)),
  };

  data_write_addr(vaddr, width, data, access, aq, rl)
}
