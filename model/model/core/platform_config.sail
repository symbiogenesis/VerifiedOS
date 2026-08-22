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

// The machine-level interrupt file. An MSI is a *store* to it, so send
// authority is a write capability in the static topology rather than a
// side table (R-15-064); only the machine level exists and of that only
// the pending array (R-15-065, sys/platform.sail).
let plat_have_imsic : bool = config platform.imsic.supported
let plat_imsic_base : physaddrbits = to_bits_checked(config platform.imsic.base : int)
let plat_imsic_size : physaddrbits = to_bits_checked(config platform.imsic.size : int)

// The revocation sidecar (R-08-005a). The interval map and the window
// the kernel revocation path updates the bitmap through are
// attested-devicetree constants; the plane itself is core/revocation.sail,
// and the clear it decides is inside the capability load's own definition
// (extensions/CHERI/cheri_mem.sail, R-08-005b).
let plat_have_revocation : bool = config platform.revocation.supported
let plat_revocation_base : physaddrbits = to_bits_checked(config platform.revocation.base : int)
let plat_revocation_interval_base : physaddrbits = to_bits_checked(config platform.revocation.interval_base : int)
let plat_revocation_interval_size : physaddrbits = to_bits_checked(config platform.revocation.interval_size : int)

// The refresh and discharge sequencer (R-15-247h). `base` is the register
// slave's window, which is in the address map and answers no requester at all,
// the RoT being its only sequencer (sys/platform.sail); the cadence table
// beside it is the composition-fixed schedule that slave runs over the second
// latency class's banks (sys/memory_sequencer.sail, core/memory_class.sail).
let plat_have_memory_sequencer : bool = config platform.memory_sequencer.supported
let plat_memory_sequencer_base : physaddrbits = to_bits_checked(config platform.memory_sequencer.base : int)
let plat_memory_sequencer_size : physaddrbits = to_bits_checked(config platform.memory_sequencer.size : int)

// A phase's bank set and the interval between phases, in the widths the class
// record states its bank count and its latency constants in. A phase's set is a
// subset of that class's banks, so the width is the same one and the *real*
// bound is the validator's: which simultaneous-activation set a droop envelope
// admits is M0.17's to decide (R-15-247g, R-15-247p), and a set no envelope
// admits is a composition that has not been priced rather than a value a type
// can refuse.
type memory_sequencer_banks  = range(0, 65535)
type memory_sequencer_cycles = range(0, 4294967295)

let plat_memory_sequencer_refresh_banks_per_phase   : memory_sequencer_banks  = config platform.memory_sequencer.banks_per_refresh_phase
let plat_memory_sequencer_refresh_phase_cycles      : memory_sequencer_cycles = config platform.memory_sequencer.refresh_phase_cycles
let plat_memory_sequencer_discharge_banks_per_phase : memory_sequencer_banks  = config platform.memory_sequencer.banks_per_discharge_phase
let plat_memory_sequencer_discharge_phase_cycles    : memory_sequencer_cycles = config platform.memory_sequencer.discharge_phase_cycles

let plat_insns_per_tick : nat1 = config platform.instructions_per_tick

// The spine frequency (R-15-195). Two things read it: the generated devicetree
// publishes it and the timebase derived from it (postlude/device_tree.sail), and
// the sequencer's refresh deadline crosses a retention figure stated in
// microseconds into the cycles its cadence is stated in
// (sys/memory_sequencer.sail).
let plat_clock_frequency : nat = config platform.clock_frequency

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

// The odd-numbered-register reserved behaviour is gone with `Zacas`
// (R-15-026, R-15-027): the rule it needed a policy for was `AMOCAS.D/Q`
// naming an odd register for a pair operand, and no surviving instruction
// names a register pair at all, so there is no reserved behaviour left to
// have a policy about.

enum XtvecModeReservedBehavior = {
  Xtvec_Fatal,
  Xtvec_Ignore,
}


enum IllegalVtypeReservedBehavior = {
  IllegalVtype_SetVill,
  IllegalVtype_Illegal,
  IllegalVtype_Fatal,
}

let xtvec_mode_reserved_behavior : XtvecModeReservedBehavior = config base.reserved_behavior.xtvec_mode
let illegal_vtype_reserved_behavior : IllegalVtypeReservedBehavior = config extensions.V.reserved_behavior.illegal_vtype

// The dynamic-rounding-mode and accrued-flag policies went with `fcsr`
// (R-15-039, R-15-083), and the RV32 `Zdinx` register-pair rule with the
// in-integer-register floating point that had the pairs.
