// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Platform-specific configuration parameters.

// Trap vector mode.
let plat_mtvec_direct_mode_supported : bool = config base.mtvec.direct.supported
let plat_mtvec_vectored_mode_supported : bool = config base.mtvec.vectored.supported

// Trap vector alignment.
type tvec_alignment = range(2, 24)
let plat_mtvec_direct_base_alignment_exp   : tvec_alignment = config base.mtvec.direct.base_alignment
let plat_mtvec_vectored_base_alignment_exp : tvec_alignment = config base.mtvec.vectored.base_alignment

// Cache block size is 2^cache_block_size_exp. Max is `max_mem_access` (4096)
// because this model performs `cbo.zero` with a single write.
let plat_cache_block_size_exp : range(0, 12) = config platform.cache_block_size_exp

// The exceptions that a misaligned access could generate.
enum misaligned_exception = { AccessFault, AlignmentException }
mapping misaligned_exception_str : misaligned_exception <-> string = {
  AccessFault        <-> "AccessFault",
  AlignmentException <-> "AlignmentException",
}
overload to_str = {misaligned_exception_str}

function optional_misaligned_exception_str(opt_e : option(misaligned_exception)) -> string =
  match opt_e {
    None()  => "NoFault",
    Some(e) => misaligned_exception_str(e),
  }
overload to_str = {optional_misaligned_exception_str}

function misaligned_exception_is_access_fault(e : option(misaligned_exception)) -> bool =
  match e {
    Some(AccessFault) => true,
    _                 => false,
  }

// Some misaligned accesses could proceed or generate exceptions.
// When used in the global configuration, `None` indicates that the
// handling is deferred to the underlying PMA (if any). The LR/SC row
// is gone with `Zalrsc` (R-15-025).
struct GlobalMisalignedExceptions = {
  load_store : option(misaligned_exception),
  vector     : option(misaligned_exception),
  amo        : option(misaligned_exception),
}

// The global handling of misaligned accesses.
let plat_misaligned_access : GlobalMisalignedExceptions = config memory.misaligned.exceptions

// Legal values for VS.  This is an enumeration to avoid lists. `FS` is gone
// with scalar floating point (R-15-039), so `VS` is the only user.
enum ExtContextPolicy = {
  ExtContext_Off,        // The extension is always off.
  ExtContext_TwoState,   // Legal values are Off and Dirty.
  ExtContext_FourState,  // Legal values are Off, Initial, Clean and Dirty.
}

let plat_mstatus_legal_vs : ExtContextPolicy = config base.mstatus.vs_legal_states

// Location of clock-interface, which should match with the spec in the DTB
let plat_have_clint : bool = config platform.clint.supported
let plat_clint_base : physaddrbits = to_bits_checked(config platform.clint.base : int)
let plat_clint_size : physaddrbits = to_bits_checked(config platform.clint.size : int)

// The Simple Interrupt Generator is gone with the two interrupt inputs
// it drove: with `mip`'s external- and software-interrupt fields
// hardwired zero (R-15-066a) the device had nothing left to signal.

let plat_insns_per_tick : nat1 = config platform.instructions_per_tick

// Maximum increment in the time CSR to wait for wait instructions.  This is not
// used within the model but instead configures the external C++ harness.
let max_wait_time : nat = config platform.max_time_to_wait

// which exceptions write information into `xtval`
let illegal_instruction_writes_xtval : bool = config base.xtval_nonzero.illegal_instruction
let breakpoint_writes_xtval : bool = config base.xtval_nonzero.breakpoint
let misaligned_load_writes_xtval : bool = config base.xtval_nonzero.load_address_misaligned
let load_access_fault_writes_xtval : bool = config base.xtval_nonzero.load_access_fault
let misaligned_samo_writes_xtval : bool = config base.xtval_nonzero.samo_address_misaligned
let samo_access_fault_writes_xtval : bool = config base.xtval_nonzero.samo_access_fault
let misaligned_fetch_writes_xtval : bool = config base.xtval_nonzero.fetch_address_misaligned
let fetch_access_fault_writes_xtval : bool = config base.xtval_nonzero.fetch_access_fault

// Define the policy for handling reserved behaviors.

enum AmocasOddRegisterReservedBehavior = {
  AMOCAS_Fatal,
  AMOCAS_Illegal,
}


enum XtvecModeReservedBehavior = {
  Xtvec_Fatal,
  Xtvec_Ignore,
}


enum IllegalVtypeReservedBehavior = {
  IllegalVtype_SetVill,
  IllegalVtype_Illegal,
  IllegalVtype_Fatal,
}

let amocas_odd_register_reserved_behavior : AmocasOddRegisterReservedBehavior = config base.reserved_behavior.amocas_odd_register
let xtvec_mode_reserved_behavior : XtvecModeReservedBehavior = config base.reserved_behavior.xtvec_mode
let illegal_vtype_reserved_behavior : IllegalVtypeReservedBehavior = config extensions.V.reserved_behavior.illegal_vtype

// The dynamic-rounding-mode and accrued-flag policies went with `fcsr`
// (R-15-039, R-15-083), and the RV32 `Zdinx` register-pair rule with the
// in-integer-register floating point that had the pairs.
