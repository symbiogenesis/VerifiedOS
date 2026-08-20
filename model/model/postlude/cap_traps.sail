// =======================================================================================
// Ported from the CHERI-RISC-V Sail model (CTSRD-CHERI/sail-cheri-riscv @ bb07488d,
// src/cheri_addr_checks.sail), which is subject to the BSD two-clause licence in
// model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The traps the capability checks raise.
//
// These sit in the postlude rather than beside the checks in `core` because
// they call the exception machinery, which is defined in `sys`: a check is a
// question about a capability, and raising a trap is the machine's answer to
// it (core/addr_checks.sail, R-15-073a).

function handle_cheri_cap_exception(capEx : CapEx, regnum : capreg_idx) -> unit = {
  if get_config_print_exception() then
    print_log("CHERI " ^ string_of_capex(capEx) ^ " Reg=" ^ bits_str(regnum));
  let t : sync_exception = struct {
    trap    = E_Extension(EXC_CHERI),
    excinfo = Some(capex_tval(capEx, regnum)),
    ext     = None(),
  };
  set_next_pc(exception_handler(t, PC))
}

/*!
 * Raises a capability exception naming PCC, which has no index in the merged
 * file because it is not in it.
 */
function handle_cheri_pcc_exception(capEx : CapEx) -> unit =
  handle_cheri_cap_exception(capEx, PCC_IDX)

function ext_handle_fetch_check_error(err : ext_fetch_addr_error) -> unit =
  handle_cheri_pcc_exception(err)

function ext_handle_control_check_error(err : ext_control_addr_error) -> unit = {
  let (capEx, regnum) = err;
  handle_cheri_cap_exception(capEx, regnum)
}

function ext_handle_data_check_error(err : ext_data_addr_error) -> unit = {
  let (capEx, regnum) = err;
  handle_cheri_cap_exception(capEx, regnum)
}

// A CSR access without the access-system-registers permission, and an `mret`
// without it, are the same violation: the permission is the privilege
// mechanism, so its absence is what a privilege fault looks like here
// (R-15-003, core/ext_regs.sail).
function ext_check_CSR_fail() -> unit =
  handle_cheri_pcc_exception(CapEx_AccessSystemRegsViolation)

function ext_fail_xret_priv() -> unit =
  handle_cheri_pcc_exception(CapEx_AccessSystemRegsViolation)
