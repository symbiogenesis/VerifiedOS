// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// default exception model

type ext_exception = unit

// Is MRET permitted by extension?
function ext_check_xret_priv () : unit -> bool = true
// Called if above check fails
function ext_fail_xret_priv () : unit -> unit = ()

function handle_trap_extension(_pc : xlenbits, _u : option(unit)) -> unit = ()

// used for traps and ECALL
function prepare_trap_vector(cause : Mcause) -> xlenbits = {
  match tvec_addr(mtvec, cause) {
    Some(epc) => epc,
    None()    => internal_error(__FILE__, __LINE__, "Invalid tvec mode")
  }
}

// MRET handling involves three functions:
//
// get_mepc:            used to read the value of the mret target  (no control flow transfer)
// set_mepc:            used to write a value of the mret target   (no control flow transfer)
// prepare_xret_target: used to get the value for control transfer to the mret target

function get_mepc() -> xlenbits = align_pc(mepc)

function set_mepc(value : xlenbits) -> xlenbits = {
  let target = legalize_xepc(value);
  mepc = target;
  target
}

function prepare_xret_target() -> xlenbits = get_mepc()

// other trap-related CSRs

function get_mtvec() -> xlenbits =
  mtvec.bits

function set_mtvec(value : xlenbits) -> xlenbits = {
  mtvec = legalize_tvec(mtvec,
                        value,
                        plat_mtvec_direct_mode_supported,
                        plat_mtvec_direct_base_alignment_exp,
                        plat_mtvec_vectored_mode_supported,
                        plat_mtvec_vectored_base_alignment_exp);
  mtvec.bits
}

// Ensure that mtvec[Mode] contains a supported value on reset.
// This would matter if these fields are read-only for the DUT.
function reset_tvec() -> unit = {
  if plat_mtvec_direct_mode_supported then {
    mtvec[Mode] = trapVectorMode(TV_Direct)
  } else if plat_mtvec_vectored_mode_supported then {
    mtvec[Mode] = trapVectorMode(TV_Vector)
  };
}

mapping clause csr_name_map = 0x305  <-> "mtvec"
mapping clause csr_name_map = 0x341  <-> "mepc"

function clause is_CSR_accessible(0x305, _) = true // mtvec
function clause is_CSR_accessible(0x341, _) = true // mepc

function clause read_CSR(0x305) = get_mtvec()
function clause read_CSR(0x341) = get_mepc()

function clause write_CSR(0x305, value) = { Ok(set_mtvec(value)) }
function clause write_CSR(0x341, value) = { Ok(set_mepc(value)) }
