// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// The capability checks below follow the CHERI-RISC-V Sail model
// (CTSRD-CHERI/sail-cheri-riscv @ bb07488d, src/cheri_addr_checks.sail), which is
// subject to the BSD two-clause licence in model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Every address the hart uses is checked against a capability: the fetch and
// control addresses against PCC, and a data address against the capability in
// the base register the access names. There is no unchecked path, because
// there is no default data capability to take one (R-15-001c).
//
// The checks are here; the traps they raise are in the postlude
// (cap_traps.sail), where the exception machinery they call has been defined.

// fetch address checks

type ext_fetch_addr_error = CapEx

// Since fetch is done in granules, the check function gets two arguments:
// start_pc: the PC at the start of the current fetch sequence
// pc:       the PC for the current granule
//
// returns:  an optional fetch error.
function ext_fetch_check_pc(start_pc : xlenbits, pc : xlenbits) -> option(ext_fetch_addr_error) = {
  if start_pc == pc then {
    // The permission checks are owed once per fetch sequence, on its first
    // granule; the bounds check is owed on every granule.
    if not(PCC.tag) then Some(CapEx_TagViolation)
    else if isCapSealed(PCC) then Some(CapEx_SealViolation)
    else if not(PCC.permit_execute) then Some(CapEx_PermitExecuteViolation)
    else if not(inCapBounds(PCC, pc, min_instruction_bytes)) then Some(CapEx_LengthViolation)
    else None()
  } else {
    if not(inCapBounds(PCC, pc, min_instruction_bytes)) then Some(CapEx_LengthViolation)
    else None()
  }
}

// control address checks

type ext_control_addr_error = (CapEx, capreg_idx)

// This function returns an optional exception for the address to use
// as the target for the control transfer. The control address is
// derived from the PC register, e.g. in JAL.
//
// NOTE: the input value does *not* have bit[0] set to 0, to enable
// more accurate bounds checking.

function ext_control_check_pc(pc : xlenbits) -> option(ext_control_addr_error) =
  if not(inCapBounds(PCC, pc, min_instruction_bytes))
  then Some((CapEx_LengthViolation, PCC_IDX))
  else None()

// data address checks

type ext_data_addr_error = (CapEx, capreg_idx)

// The authorising capability of a data access, and the address it authorises.
// In capability mode it is the capability in the base register the instruction
// names, and the address is that capability's address plus the offset; in
// integer mode the base register is an integer and the authority is DDC. The
// second arm is hybrid mode, which the profile deletes along with DDC itself
// (R-15-001c): on a purecap machine every access takes the first arm, and an
// integer in a base register is an untagged capability that faults here rather
// than reaching memory (R-15-001, R-15-007h).
function ext_data_get_addr(base : regidx, offset : xlenbits, access : MemoryAccessType(mem_payload), width : mem_access_width)
         -> Ext_DataAddr_Check(ext_data_addr_error) = {
  let (auth, newAddr, auth_idx) : (Capability, xlenbits, capreg_idx) =
    if PCC.flag_cap_mode then {
      let auth = C(base);
      (auth, auth.address + offset, capreg_idx_of_regidx(base))
    } else {
      (DDC, X(base) + offset, DDC_IDX)
    };

  let (need_load_perm, need_store_perm) : (bool, bool) = match access {
    Load(_)             => (true, false),
    Store(_)            => (false, true),
    Atomic(_)           => (true, true),
    // `cbo.zero` writes the block it names, so it is a store for permission
    // (R-15-060).
    CacheAccess(_)      => (false, true),
    InstructionFetch()  => internal_error(__FILE__, __LINE__, "ext_data_get_addr for InstructionFetch"),
  };

  if not(auth.tag) then
    Ext_DataAddr_Error((CapEx_TagViolation, auth_idx))
  else if isCapSealed(auth) then
    Ext_DataAddr_Error((CapEx_SealViolation, auth_idx))
  else if need_load_perm & not(auth.permit_load) then
    Ext_DataAddr_Error((CapEx_PermitLoadViolation, auth_idx))
  else if need_store_perm & not(auth.permit_store) then
    Ext_DataAddr_Error((CapEx_PermitStoreViolation, auth_idx))
  else if not(inCapBounds(auth, newAddr, width)) then
    Ext_DataAddr_Error((CapEx_LengthViolation, auth_idx))
  else
    Ext_DataAddr_OK(Virtaddr(newAddr))
}
