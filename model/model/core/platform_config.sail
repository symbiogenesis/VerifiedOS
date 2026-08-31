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

// The Root of Trust's four peripherals (R-09-001, sys/rot.sail): the OTP fuse
// bank holding the lifecycle state (R-09-003, R-09-032), the entropy root
// (R-15-241), the monotonic counter file (R-10-013), and the windowed watchdog
// (R-15-240). Each is a register slave whose window is in the address map of
// every composition, because the die has one RoT whichever of its cores an
// emulator composes (R-15-194, R-15-113); which requester the window *answers*
// is the composed hart's class and not a key, the roster already saying which
// core this run is (R-15-052b, sys/rot.sail).
//
// **Only the windows are here.** The lifecycle reset state, the declared noise
// source count, the start-up sample budget, the emulation seed and the two
// watchdog bounds are read in sys/rot.sail instead, beside the enumerations and
// widths that bound them, which is where core/core_class.sail reads the class
// table for the same reason: a bound written here and a type written there is
// one fact in two files.
let plat_have_otp : bool = config platform.otp.supported
let plat_otp_base : physaddrbits = to_bits_checked(config platform.otp.base : int)
let plat_otp_size : physaddrbits = to_bits_checked(config platform.otp.size : int)

let plat_have_trng : bool = config platform.trng.supported
let plat_trng_base : physaddrbits = to_bits_checked(config platform.trng.base : int)
let plat_trng_size : physaddrbits = to_bits_checked(config platform.trng.size : int)

let plat_have_monotonic : bool = config platform.monotonic_counters.supported
let plat_monotonic_base : physaddrbits = to_bits_checked(config platform.monotonic_counters.base : int)
let plat_monotonic_size : physaddrbits = to_bits_checked(config platform.monotonic_counters.size : int)

let plat_have_watchdog : bool = config platform.watchdog.supported
let plat_watchdog_base : physaddrbits = to_bits_checked(config platform.watchdog.base : int)
let plat_watchdog_size : physaddrbits = to_bits_checked(config platform.watchdog.size : int)

// The three devices beside the core (R-15-002b): the SoC boot ROM, the serial
// port, and the block device. What obliges each to exist is the implementation
// plan's R1; what obliges its placement to be declared is R-15-002b, which puts
// every MMIO aperture inside the 36-bit space and makes the placement a stated
// constraint on the attested devicetree.
//
// **These three are placements and nothing else, and the asymmetry with the
// eight above is deliberate.** Each of those has a slave in sys/platform.sail
// that either answers or refuses; none of these has one, because no register
// entry gives a serial port or a block device a register interface and the
// devices themselves are route-(c) references arriving with the SoC top written
// over this map. So the only readers of these six values are the attested
// devicetree, which carries the placement R-15-002b requires it to state, and
// the validator, which refuses a composition that places one wrong
// (postlude/device_tree.sail, postlude/validate_config.sail).
//
// The cost of that is stated rather than absorbed, and the enclosing region's
// PMA decides how much of it there is: an IO address no device claims falls
// through to the RAM path (sys/mem.sail), but `pmaCheck` runs ahead of that
// fall-through, so what is silent is only what the region already permits. The
// serial port and the block device sit in a readable and writable IO region, so
// a load and a store inside either are the RAM path's until the top lands. The
// boot ROM's region is readable and neither writable nor executable, so a load
// there reads zero while a store or an instruction fetch is an access fault the
// region raises today; the fetch is the one access an SoC boot ROM exists for,
// and that region's `executable` is R1c-ii's to decide with the attested tree
// sharing the region. Either way this is the opposite disposition from the
// memory sequencer's window and the RoT's four, and the reason is that their
// refusal is permanent where these are doors whose device has not arrived.
let plat_have_boot_rom : bool = config platform.boot_rom.supported
let plat_boot_rom_base : physaddrbits = to_bits_checked(config platform.boot_rom.base : int)
let plat_boot_rom_size : physaddrbits = to_bits_checked(config platform.boot_rom.size : int)

let plat_have_uart : bool = config platform.uart.supported
let plat_uart_base : physaddrbits = to_bits_checked(config platform.uart.base : int)
let plat_uart_size : physaddrbits = to_bits_checked(config platform.uart.size : int)

let plat_have_blkdev : bool = config platform.blkdev.supported
let plat_blkdev_base : physaddrbits = to_bits_checked(config platform.blkdev.base : int)
let plat_blkdev_size : physaddrbits = to_bits_checked(config platform.blkdev.size : int)

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
