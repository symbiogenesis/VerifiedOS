// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Basic type and function definitions used pervasively in the model.

type half = bits(16)
type word = bits(32)

// Bit-vector of an uncompressed instruction.
type instbits = bits(32)

// PMA regions are required to be aligned to, and a multiple of, 2^12
// bytes, so a PMA property cannot change within an access that stays
// inside one such block. This is the only role the page size retained
// once the MMU was deleted (R-15-002): it names a PMA granule, not a
// translation unit.
type pma_granule_bits : Int = 12
let  pma_granule_bits = sizeof(pma_granule_bits)

// RV32E and RV64E Base Integer Instruction Sets. If this enabled then
// the model will only support E (16 integer registers). It is allowed
// to have a design where `misa[I]` is writable to turn E on and off,
// but this model does not support that.
type base_E_enabled : Bool = config base.E
let base_E_enabled = constraint(base_E_enabled)

// register identifiers

type regidx_bit_width = if base_E_enabled then 4 else 5
let regidx_bit_width = sizeof(regidx_bit_width)

newtype regidx = Regidx : bits(regidx_bit_width)  // uncompressed register identifiers
newtype cregidx = Cregidx : bits(3) // identifiers in RVC instructions
type csreg = bits(12)  // CSR addressing

function regidx_offset(Regidx(r) : regidx, o : bits(regidx_bit_width)) -> regidx = Regidx(r + o)
function regidx_offset_range(Regidx(r) : regidx, o : range(0, 31)) -> regidx = Regidx(r + o)
function regidx_bits(Regidx(b) : regidx) -> bits(regidx_bit_width) = b
overload operator + = { regidx_offset, regidx_offset_range }
// register file indexing

newtype regno = Regno : range(0, 2 ^ regidx_bit_width - 1)

// mapping RVC register indices into normal indices
function creg2reg_idx(Cregidx(i) : cregidx) -> regidx = Regidx(zero_extend(0b1 @ i))

// some architecture and ABI relevant register identifiers
let zreg : regidx = Regidx(zero_extend(0b00)) // x0, zero register
let ra   : regidx = Regidx(zero_extend(0b01)) // x1, return address
let sp   : regidx = Regidx(zero_extend(0b10)) // x2, stack pointer
let t0   : regidx = Regidx(zero_extend(0b101)) // x5, alternate link register

// base architecture definitions

enum Architecture = {RV32, RV64, RV128}
type arch_xlen = bits(2)

mapping architecture_bits : Architecture <-> arch_xlen = {
  RV32  <-> 0b01,
  RV64  <-> 0b10,
  RV128 <-> 0b11,
  backwards 0b00 => internal_error(__FILE__, __LINE__, "architecture(0b00) is invalid")
}

// There is one privilege mode. Supervisor and User are deleted with
// the ring they would delegate to, and the virtual modes with the
// hypervisor (R-15-003, R-15-006), so no privilege type, no
// `cur_privilege` register, and no privilege-encoding field remains:
// the machine is always in Machine mode and nothing observes that as
// a value.

// memory access types

union cacheop = {
  CB_zero     : unit,
}

// The two bool parameters of `Atomic` are the `aq` and `rl`
// instruction annotations respectively. The load-reserved and
// store-conditional classes are gone with `Zalrsc` (R-15-025), which
// takes the reservation register with them: the only atomic access
// left on the machine is the indivisible read-modify-write of an AMO.
union MemoryAccessType ('a : Type) = {
  Load             : 'a,
  Store            : 'a,
  Atomic           : (amoop, bool, bool, 'a, 'a),
  InstructionFetch : unit,
  CacheAccess      : cacheop
}

// Some useful predicates on the kind of memory access
function is_load_store forall ('a : Type) . (access : MemoryAccessType('a)) -> bool =
  match access {
    Load(_)             => true,
    Store(_)            => true,
    Atomic(_)           => true,
    InstructionFetch(_) => false,
    CacheAccess(_)      => true,
  }

// CSR access types
enum CSRAccessType = { CSRRead, CSRWrite, CSRReadWrite }

type is_mem_width('w) = 'w in {1, 2, 4, 8}
// used for misalignment calculations
type max_mem_width_bytes_exp : Nat = 3
type max_mem_width_bytes : Nat = 2 ^ max_mem_width_bytes_exp

// architectural interrupt definitions

// Only the machine-level interrupts remain: the supervisor and
// virtual-supervisor classes go with their modes (R-15-003, R-15-006)
// and the local counter-overflow interrupt with the performance
// counters (R-15-077).
enum InterruptType = {
  I_M_Software,
  I_M_Timer,
  I_M_External,
}

mapping interruptType_bits : InterruptType <-> exc_code = {
  I_M_Software   <-> 0b000011, // 3
  I_M_Timer      <-> 0b000111, // 7
  I_M_External   <-> 0b001011, // 11
}

function interruptType_to_str(i : InterruptType) -> string =
  match (i) {
    I_M_Software  => "machine-software-interrupt",
    I_M_Timer     => "machine-timer-interrupt",
    I_M_External  => "machine-external-interrupt",
  }

overload to_str = {interruptType_to_str}

// architectural exception definitions

enum breakpoint_cause = {Brk_Software, Brk_Hardware}

// The page-fault classes go with the MMU (R-15-002), the guest-page
// and virtual-instruction classes with the hypervisor (R-15-006), the
// U/S/VS environment calls with their modes (R-15-003), and the
// software-check fault with `Zicfilp`'s landing pads (R-15-044). The
// reserved codepoints held places for exceptions `medeleg` could name
// and nothing else, so they leave with the delegation register.
union ExceptionType = {
  E_Fetch_Addr_Align   : unit,
  E_Fetch_Access_Fault : unit,
  E_Illegal_Instr      : unit,
  E_Breakpoint         : breakpoint_cause,
  E_Load_Addr_Align    : unit,
  E_Load_Access_Fault  : unit,
  E_SAMO_Addr_Align    : unit,
  E_SAMO_Access_Fault  : unit,
  E_M_EnvCall          : unit,

  // extensions
  E_Extension          : ext_exc_type
}

mapping exceptionType_bits : ExceptionType <-> exc_code = {
  E_Fetch_Addr_Align()   <-> 0b000000, // 0
  E_Fetch_Access_Fault() <-> 0b000001, // 1
  E_Illegal_Instr()      <-> 0b000010, // 2
  E_Load_Addr_Align()    <-> 0b000100, // 4
  E_Load_Access_Fault()  <-> 0b000101, // 5
  E_SAMO_Addr_Align()    <-> 0b000110, // 6
  E_SAMO_Access_Fault()  <-> 0b000111, // 7
  E_M_EnvCall()          <-> 0b001011, // 11

  // breakpoints
  E_Breakpoint(Brk_Software) <-> 0b000011, // 3
  E_Breakpoint(Brk_Hardware) <-> 0b000011, // 3

  // extensions
  E_Extension(e)         <-> ext_exc_type_bits(e)
}

function exceptionType_to_str(e : ExceptionType) -> string =
  match (e) {
    E_Fetch_Addr_Align()   => "misaligned-fetch",
    E_Fetch_Access_Fault() => "fetch-access-fault",
    E_Illegal_Instr()      => "illegal-instruction",
    E_Load_Addr_Align()    => "misaligned-load",
    E_Load_Access_Fault()  => "load-access-fault",
    E_SAMO_Addr_Align()    => "misaligned-store/amo",
    E_SAMO_Access_Fault()  => "store/amo-access-fault",
    E_M_EnvCall()          => "m-call",

    // breakpoints
    E_Breakpoint(Brk_Software) => "software-breakpoint",
    E_Breakpoint(Brk_Hardware) => "hardware-breakpoint",

    // extensions
    E_Extension(e)         => ext_exc_type_to_str(e)
  }

overload to_str = {exceptionType_to_str}

// An architectural trap can be caused by either an interrupt or an exception

union TrapCause = {
  Interrupt : InterruptType,
  Exception : ExceptionType,
}

mapping trapCause_bits : TrapCause <-> exc_code = {
  Interrupt(i) <-> interruptType_bits(i),
  Exception(e) <-> exceptionType_bits(e),
}

function trapCause_is_interrupt(t : TrapCause) -> bool = match t {
  Interrupt(_) => true,
  Exception(_) => false,
}

function trapCause_to_str(t : TrapCause) -> string = match t {
  Interrupt(i) => "int#" ^ interruptType_to_str(i),
  Exception(e) => "exc#" ^ exceptionType_to_str(e),
}

overload to_str = {trapCause_to_str}

// trap modes

type tv_mode = bits(2)
enum TrapVectorMode = {TV_Direct, TV_Vector, TV_Reserved}

mapping trapVectorMode : tv_mode <-> TrapVectorMode = {
  0b00 <-> TV_Direct,
  0b01 <-> TV_Vector,
  0b10 <-> TV_Reserved,
  0b11 <-> TV_Reserved,
}

// extension context status

type ext_status = bits(2)
enum ExtStatus = {Off, Initial, Clean, Dirty}

mapping extStatus_map : ExtStatus <-> ext_status = {
  Off     <-> 0b00,
  Initial <-> 0b01,
  Clean   <-> 0b10,
  Dirty   <-> 0b11
}

function legalize_extStatus(policy : ExtContextPolicy, status : ext_status) -> ext_status = {
  match policy {
    ExtContext_Off       => extStatus_map(Off),

    // This emulates the following implementation choice from the spec:
    //
    // "On other implementations, dirtiness might not be tracked at
    // all, in which case the valid FS states are Off and Dirty, and
    // an attempt to set FS to Initial or Clean causes it to be set to
    // Dirty."
    //
    // and analogously for VS.
    ExtContext_TwoState  => if extStatus_map(status) == Off then status else extStatus_map(Dirty),

    ExtContext_FourState => status,
  }
}

// CSR access control bits (from CSR addresses)

type csrRW = bits(2)  // read/write

// Wait state reasons

enum WaitReason = {WAIT_WFI}
mapping wait_name : WaitReason <-> string = {
  WAIT_WFI     <-> "WAIT-WFI",
}

overload to_str = {wait_name}

// Width of access for most instructions (load/store, etc.).
type word_width = {1, 2, 4, 8}
// Some instructions allow 128-bit accesses.
type word_width_wide = {1, 2, 4, 8, 16}

// Get the bit encoding of word_width.
mapping width_enc : word_width <-> bits(2) = {
  1 <-> 0b00,
  2 <-> 0b01,
  4 <-> 0b10,
  8 <-> 0b11,
}

mapping width_mnemonic : word_width <-> string = {
  1 <-> "b",
  2 <-> "h",
  4 <-> "w",
  8 <-> "d",
}

// Get the bit encoding of word_width.
mapping width_enc_wide : word_width_wide <-> bits(3) = {
  1  <-> 0b000,
  2  <-> 0b001,
  4  <-> 0b010,
  8  <-> 0b011,
  16 <-> 0b100,
}

mapping width_mnemonic_wide : word_width_wide <-> string = {
  1  <-> "b",
  2  <-> "h",
  4  <-> "w",
  8  <-> "d",
  16 <-> "q",
}
