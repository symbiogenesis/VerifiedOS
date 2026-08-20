// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// The capability-width accessors below follow the CHERI-RISC-V Sail model
// (CTSRD-CHERI/sail-cheri-riscv @ bb07488d, src/cheri_mem.sail and
// src/cheri_insts.sail), which is subject to the BSD two-clause licence in
// model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Capability-width memory access.
//
// A capability is `cap_size` bytes of data plus one validity tag, and the tag is
// the metadata every physical access already carries (core/mem_metadata.sail),
// so these ride `mem_read_meta` and `mem_write_value_meta` rather than a second
// memory interface.
//
// Upstream separates `Read(Cap)` from `Read(Data)` in the access type. That
// distinction is the page-table walker's: on the read side it carries the page
// table entry's load-capability protocol, and on the write side it selects the
// capability-dirty case, and both go with the walker (R-15-002, R-15-038). No
// consumer of the access type survives here, so a capability access is an
// ordinary `Load(Data)` or `Store(Data)` at `cap_size` and the tag travels
// beside it as metadata rather than as a payload class.

val mem_read_cap : (physaddr, bool, bool) -> MemoryOpResult(Capability)
function mem_read_cap(addr, aq, rl) =
  match mem_read_meta(Load(Data), addr, cap_size, aq, rl, true) {
    Ok(v, tag) => Ok(memBitsToCapability(tag, v)),
    Err(a, e)  => Err(a, e),
  }

val mem_write_ea_cap : (physaddr, bool, bool) -> MemoryOpResult(unit)
function mem_write_ea_cap(addr, aq, rl) = mem_write_ea(addr, cap_size, Store(Data), aq, rl)

val mem_write_cap : (physaddr, Capability, bool, bool) -> MemoryOpResult(bool)
function mem_write_cap(addr, cap, aq, rl) =
  mem_write_value_meta(addr, cap_size, capToMemBits(cap), Store(Data), cap.tag, aq, rl)

// The checks a capability-width access owes, in the order a data access owes its
// own. Two are the capability plane's and appear on the store side only: storing
// a tagged capability needs store-capability, and storing a non-global one needs
// store-local beside it (R-15-074). The load side has no counterpart, a load
// without load-capability permission being defined to deliver its value untagged
// rather than to fault, which is the shape the revocation filter's result takes
// too (R-08-005b).
function cap_access_checks(
  auth     : Capability,
  auth_idx : capreg_idx,
  addr     : xlenbits,
  stored   : option(Capability),
) -> option(ext_data_addr_error) = {
  let (is_store, stored_tag, stored_global) : (bool, bool, bool) = match stored {
    None()  => (false, false, true),
    Some(c) => (true, c.tag, c.global),
  };
  if not(auth.tag) then
    Some((CapEx_TagViolation, auth_idx))
  else if isCapSealed(auth) then
    Some((CapEx_SealViolation, auth_idx))
  else if not(is_store) & not(auth.permit_load) then
    Some((CapEx_PermitLoadViolation, auth_idx))
  else if is_store & not(auth.permit_store) then
    Some((CapEx_PermitStoreViolation, auth_idx))
  else if is_store & stored_tag & not(auth.permit_store_cap) then
    Some((CapEx_PermitStoreCapViolation, auth_idx))
  else if is_store & stored_tag & not(stored_global) & not(auth.permit_store_local_cap) then
    Some((CapEx_PermitStoreLocalCapViolation, auth_idx))
  else if not(inCapBounds(auth, addr, cap_size)) then
    Some((CapEx_LengthViolation, auth_idx))
  else
    None()
}

// A capability access is *always* naturally aligned, whatever the platform's
// misaligned policy admits for data: a capability that straddled a granule
// boundary would have no tag of its own (core/mem_metadata.sail, R-15-203).

function cap_load(cd : regidx, auth : Capability, auth_idx : capreg_idx, addr : xlenbits) -> ExecutionResult = {
  match cap_access_checks(auth, auth_idx, addr, None()) {
    Some(e) => return Ext_DataAddr_Check_Failure(e),
    None()  => (),
  };
  let vaddr = Virtaddr(addr);
  if not(is_aligned_addr(vaddr, cap_size)) then
    return memory_exception(vaddr, E_Load_Addr_Align());

  match mem_read_cap(physical_address(vaddr), false, false) {
    Err(_, e) => memory_exception(vaddr, e),
    Ok(v)     => {
      C(cd) = clearTagIf(v, not(auth.permit_load_cap));
      RETIRE_SUCCESS
    },
  }
}

function cap_store(cs2 : regidx, auth : Capability, auth_idx : capreg_idx, addr : xlenbits) -> ExecutionResult = {
  let value = C(cs2);
  match cap_access_checks(auth, auth_idx, addr, Some(value)) {
    Some(e) => return Ext_DataAddr_Check_Failure(e),
    None()  => (),
  };
  let vaddr = Virtaddr(addr);
  if not(is_aligned_addr(vaddr, cap_size)) then
    return memory_exception(vaddr, E_SAMO_Addr_Align());

  let paddr = physical_address(vaddr);
  match mem_write_ea_cap(paddr, false, false) {
    Err(_, e) => memory_exception(vaddr, e),
    Ok(())    => match mem_write_cap(paddr, value, false, false) {
      Err(_, e) => memory_exception(vaddr, e),
      Ok(true)  => RETIRE_SUCCESS,
      Ok(false) => internal_error(__FILE__, __LINE__, "capability store got false from mem_write_cap"),
    },
  }
}
