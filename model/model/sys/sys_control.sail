// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Machine-mode functionality. There is no second mode: traps are
// taken by the Machine-mode kernel and delegation has no delegate
// (R-15-003).

// CSR access control

function csrAccess(csr : csreg) -> csrRW = csr[11..10]

// Check that the CSR access isn't a write to a read-only CSR.
function check_CSR_access(csr : csreg, access_type : CSRAccessType) -> bool =
  not((access_type == CSRWrite | access_type == CSRReadWrite) & (csrAccess(csr) == 0b11))

// The privilege half of this check is gone with the modes that could
// fail it: every CSR the profile keeps is machine-level, and machine
// mode is the only mode, so what is left to reject is a write to a
// read-only CSR and an address that names no CSR at all.
function check_CSR(csr : csreg, access_type : CSRAccessType) -> bool =
    check_CSR_access(csr, access_type)
  & is_CSR_accessible(csr, access_type)

// The priority order over simultaneous machine-mode interrupts is
// gone with the interrupts it ordered: `MTI` is the only one left
// (R-15-066a), so there is nothing to arbitrate.
function findPendingInterrupt(ip : xlenbits) -> option(InterruptType) = {
  let ip = Mk_Minterrupts(ip);
  if   ip[MTI] == 0b1 then Some(I_M_Timer)
  else                     None()
}

// Return the pending, enabled set of interrupts.
//
// This is used when the hart is in the Active state.
function getPendingSet() -> option(xlenbits) = {
  let pending = mip.bits & mie.bits;

  if   mstatus[MIE] == 0b1 & pending != zeros()
  then Some(pending)
  else None()
}

// Check if a locally enabled interrupt is pending.
//
// This does not examine the global enable bit `mstatus.MIE`; it does
// honor the local interrupt enable in `mie`, which after the narrowing
// is `MTIE` alone (R-15-066a). The privileged spec states the rule
// over the global bits and `mideleg` together, and both halves of that
// exemption survive as one: what a wait instruction ignores is
// `mstatus.MIE`, there being no delegation register left to ignore.
//
// This is used when the hart is in the Waiting state, caused by
// instructions such as WFI and WRS.{NTO,STO}.
//
// https://riscv.github.io/riscv-isa-manual/snapshot/privileged/#wfi
function shouldWakeForInterrupt() -> bool = {
  (mip.bits & mie.bits) != zeros()
}

// Examine the current interrupt state and return an interrupt to be
// handled, if any.
function dispatchInterrupt() -> option(InterruptType) = {
  match getPendingSet() {
    None()   => None(),
    Some(ip) => findPendingInterrupt(ip),
  }
}

// trap value

function tval(excinfo : option(xlenbits)) -> xlenbits = {
  match (excinfo) {
    Some(e) => e,
    None()  => zeros()
  }
}

function track_trap(is_interrupt : bool, cause : exc_code) -> unit = {
  long_csr_write_callback("mstatus", "mstatush", mstatus.bits);
  csr_write_callback("mcause", mcause.bits);
  csr_write_callback("mtval", mtval);
  csr_write_callback("mepc", mepc);

  trap_callback(is_interrupt, cause);
}

// handle exceptional ctl flow by updating nextPC
function trap_handler(c : TrapCause, pc : xlenbits, info : option(xlenbits), ext : option(ext_exception))
                     -> xlenbits = {
  let is_interrupt = trapCause_is_interrupt(c);
  let cause        = trapCause_bits(c);

  if   get_config_print_exception() | get_config_print_interrupt()
  then print_log("handling " ^ to_str(c) ^ " with tval " ^ bits_str(tval(info)));

  mcause[IsInterrupt] = bool_to_bit(is_interrupt);
  mcause[Cause]       = zero_extend(cause);

  mstatus[MPIE] = mstatus[MIE];
  mstatus[MIE]  = 0b0;
  mtval         = tval(info);
  mepc          = pc;

  handle_trap_extension(pc, ext);

  track_trap(is_interrupt, cause);

  prepare_trap_vector(mcause)
}

function exception_handler(exc : sync_exception, pc : xlenbits) -> xlenbits = {
  if   get_config_print_exception()
  then print_log("trapping to handle " ^ to_str(exc.trap));
  trap_handler(Exception(exc.trap), pc, exc.excinfo, exc.ext)
}
// Compute the value to write to mtval on a trap.
function xtval_exception_value(e : ExceptionType, excinfo : xlenbits) -> option(xlenbits) = {
  if match e {
    E_Illegal_Instr() => illegal_instruction_writes_xtval,
    E_Breakpoint() => breakpoint_writes_xtval,
    E_Load_Addr_Align() => misaligned_load_writes_xtval,
    E_Load_Access_Fault() => load_access_fault_writes_xtval,
    E_SAMO_Addr_Align() => misaligned_samo_writes_xtval,
    E_SAMO_Access_Fault() => samo_access_fault_writes_xtval,
    E_Fetch_Addr_Align() => misaligned_fetch_writes_xtval,
    E_Fetch_Access_Fault() => fetch_access_fault_writes_xtval,
    E_M_EnvCall()  => false,
    E_Extension(_) => true,
  } then Some(excinfo) else None()
}

function make_sync_exception(e : ExceptionType, xtval : xlenbits) -> sync_exception =
  struct { trap    = e,
           excinfo = xtval_exception_value(e, xtval),
           ext     = None() }

function handle_exception(xtval : xlenbits, e : ExceptionType) -> unit =
  set_next_pc(exception_handler(make_sync_exception(e, xtval), PC))

function handle_interrupt(i : InterruptType) -> unit =
  set_next_pc(trap_handler(Interrupt(i), PC, None(), None()))

// Reset misa to enable the maximal set of supported extensions.
function reset_misa() -> unit = {
  misa[A]   = bool_to_bit(hartSupports(Ext_A));   // atomics
  misa[C]   = 0b0;                                // no compressed instructions
  misa[B]   = bool_to_bit(hartSupports(Ext_B));   // Bit-manipulation
  misa[M]   = bool_to_bit(hartSupports(Ext_M));   // integer multiply/divide
  misa[U]   = 0b0;                                // no user mode
  misa[S]   = 0b0;                                // no supervisor mode
  misa[V]   = bool_to_bit(hartSupports(Ext_V));   // vector extension

  // Base integer ISA (disabled if we only support the 16-register E base).
  misa[E] = bool_to_bit(base_E_enabled);
  misa[I] = ~(misa[E]);

  if   hartSupports(Ext_F) & hartSupports(Ext_Zfinx)
  then internal_error(__FILE__, __LINE__, "F and Zfinx cannot both be enabled!");

  // We currently support both F and D
  misa[F]   = bool_to_bit(hartSupports(Ext_F));      // single-precision
  misa[D]   = if   flen >= 64
              then bool_to_bit(hartSupports(Ext_D))  // double-precision
              else 0b0;
  csr_write_callback("misa", misa.bits);
}

// Address to reset PC to on reset.
register pc_reset_address : xlenbits = zeros()
// This is called externally to set the PC reset address to the ELF entry point.
// bits(64) is used because it's easier to deal with in C.
function set_pc_reset_address(addr : bits(64)) -> unit = pc_reset_address = trunc(addr)

// This function is called on reset, so it should only perform the reset actions
// described in the "Reset" section of the privileged architecture specification.
function reset_sys() -> unit = {

  // "The mstatus field MIE is reset to 0." (MPRV is gone with the
  // less-privileged mode whose accesses it retargeted.)
  mstatus[MIE] = 0b0;

  // Though `mtvec` is unspecified on reset, its mode should hold
  // a supported value when read.
  reset_tvec();

  // "If little-endian memory accesses are supported, the mstatus/mstatush field
  // MBE is reset to 0."
  // TODO: The handling of mstatush is a bit awkward currently, but the model
  // currently only supports little endian so MBE is always 0.
  // See https://github.com/riscv/sail-riscv/issues/639
  // mstatus[MBE] = 0b0;

  long_csr_write_callback("mstatus", "mstatush", mstatus.bits);

  // "The misa register is reset to enable the maximal set of supported extensions"
  reset_misa();

  // "The pc is set to an implementation-defined reset vector."
  PC = pc_reset_address;
  nextPC = pc_reset_address;

  // "The mcause register is set to a value indicating the cause of the reset."
  // "The mcause values after reset have implementation-specific interpretation,
  // but the value 0 should be returned on implementations that do not
  // distinguish different reset conditions."
  mcause.bits = zeros();
  csr_write_callback("mcause", mcause.bits);

  // TODO: Probably need to remove these vector resets too but it needs
  // refactoring anyway. See https://github.com/riscv/sail-riscv/issues/566 etc.
  // If they are kept then callbacks need to be added.

  // initialize vector csrs
  vstart           = zeros();
  vl               = zeros();
  vcsr[vxrm]       = 0b00;
  vcsr[vxsat]      = 0b0;
  vtype[vill]      = 0b1;
  vtype[reserved]  = zeros();
  vtype[vma]       = 0b0;
  vtype[vta]       = 0b0;
  vtype[vsew]      = 0b000;
  vtype[vlmul]     = 0b000;
}

// memory access exceptions, defined here for use by the platform model.

type MemoryOpResult('a : Type) = result('a, (physaddr, ExceptionType))

val MemoryOpResult_add_meta : forall ('t : Type). (MemoryOpResult('t), mem_meta) -> MemoryOpResult(('t, mem_meta))
function MemoryOpResult_add_meta(r, m) = match r {
  Ok(v)  => Ok(v, m),
  Err(e) => Err(e)
}

val MemoryOpResult_drop_meta : forall ('t : Type). MemoryOpResult(('t, mem_meta)) -> MemoryOpResult('t)
function MemoryOpResult_drop_meta(r) = match r {
  Ok(v, _m)  => Ok(v),
  Err(e) => Err(e)
}
