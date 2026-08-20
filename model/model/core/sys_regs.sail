// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Machine-mode state definitions.
//
// There are no state projections here. Machine state was projected to
// lowered views (mstatus -> sstatus, mip -> sip) for reading from, and
// lifted back when written by, a less-privileged mode; with one
// privilege mode (R-15-003) every register has one view and every
// write is a machine-mode write.
//
// Several fields in machine state registers are WARL or WLRL,
// requiring that values written to the registers be legalized.  For each such
// register, there will be an associated 'legalize_' function.  These functions
// will need to be supplied externally, and will depend on the legal values
// supported by a platform/implementation (or misa).  The legalize_ functions
// generate a legal value from the current value and the written value.  In more
// complex cases, they will also implicitly read the current values of misa,
// mstatus, etc.

// current instruction bits, used for illegal instruction exceptions

register cur_inst : xlenbits

// Model-internal count of retired instructions. This is not `minstret`,
// which is deleted with the performance counters (R-15-077): it is
// harness state with no CSR address and no architectural reader,
// serving the RVFI trace's `order` field for the differential rig.

register retire_count : bits(64)


// M-mode registers

bitfield Misa : xlenbits = {
  MXL  : xlen - 1 .. xlen - 2,

  Z    : 25,
  Y    : 24,
  X    : 23,
  W    : 22,
  V    : 21,
  U    : 20,
  T    : 19,
  S    : 18,
  R    : 17,
  Q    : 16,
  P    : 15,
  O    : 14,
  N    : 13,
  M    : 12,
  L    : 11,
  K    : 10,
  J    : 9,
  I    : 8,
  H    : 7,
  G    : 6,
  F    : 5,
  E    : 4,
  D    : 3,
  C    : 2,
  B    : 1,
  A    : 0
}
register misa : Misa =
  [ Mk_Misa(zeros()) with
    // MXL is a read-only field that specifies the native XLEN, which is
    // RV64 and only RV64 (R-15-001, xlen.sail).
    MXL = 0b10,
  ]

// `misa` is read-only (R-15-052): the writability configuration knob
// and the legalization function it gated are both gone, and a write is
// ignored rather than legalized. There is no runtime ISA morphing, and
// therefore no runtime CHERI disable: the register's value is fixed at
// reset by `reset_misa()` from the extensions the hart supports, which
// on a frozen profile is a composition-time constant.

mapping clause csr_name_map = 0x301  <-> "misa"
function clause is_CSR_accessible(0x301, _) = true // misa
function clause read_CSR(0x301) = misa.bits
function clause write_CSR(0x301, _) = Ok(misa.bits)

// What is left of `mstatus` is the extension-context gate. Every other
// field it carried named a less-privileged mode or the machinery for
// entering one: the trap-and-virtualize bits (TSR, TW, TVM), the
// translation-permission bits (MXR, SUM), the modify-privilege
// retarget (MPRV), the effective-XLEN fields for the lower modes (SXL,
// UXL), the byte-endianness control for supervisor accesses (SBE), and
// the previous-mode and supervisor interrupt-enable stacks (MPP, SPP,
// SPIE, SIE). `FS` goes with scalar floating point (R-15-039): all
// floating point is vector, so `VS` is the machine's only extension-state
// gate and `FS` is not a field any code can name.
bitfield Mstatus : bits(64) = {
  SD   : xlen - 1,

  MBE  : 37,

  XS   : 16 .. 15,

  VS   : 10 .. 9,

  MPIE : 7,
  MIE  : 3,
}

private function legalize_mstatus(o : Mstatus, v : bits(64)) -> Mstatus = {
  // Populate all defined fields using the bits of v, stripping anything
  // that does not have a matching bitfield entry. The SD bits are handled
  // explicitly later depending on xlen.
  let v = Mk_Mstatus(v);

  let o = [o with
    // We don't currently support changing MBE.
    // MBE = v[MBE],

    // We don't have any extension context yet.
    XS = extStatus_map(Off),
    // Validate VS against its allowed set.
    VS = legalize_extStatus(plat_mstatus_legal_vs, v[VS]),

    MPIE = v[MPIE],
    MIE = v[MIE],
  ];

  // Set dirty bit to OR of other status bits.
  let dirty = extStatus_map(o[XS]) == Dirty |
              extStatus_map(o[VS]) == Dirty;

  [o with SD = bool_to_bit(dirty)]
}

register mstatus : Mstatus = Mk_Mstatus(zeros())

// `mstatush` is the RV32 high half of `mstatus` and goes with the RV32
// configuration itself (xlen.sail): at XLEN=64 the register is one CSR
// and 0x310 is an unallocated address, which traps under R-15-014.
mapping clause csr_name_map = 0x300  <-> "mstatus"

function clause is_CSR_accessible(0x300, _) = true // mstatus

function clause read_CSR(0x300) = mstatus.bits

function clause write_CSR(0x300, value) = { mstatus = legalize_mstatus(mstatus, value); Ok(mstatus.bits) }

// `mseccfg` is not defined: it exists only for Zkr or for a feature that
// requires it, and Zkr, Smepmp, Zicfilp and pointer masking are all absent.


// The environment-configuration registers are not defined. Every bit
// of `menvcfg` gated a less-privileged mode's access to an extension
// feature, and `senvcfg` is part of the S-mode bank, so both leave
// with the mode (R-15-049a, R-15-003). `Zicboz`'s `CBZE` was the one
// bit with a live feature behind it, and `cbo.zero` is unconditionally
// permitted rather than gated.

// I/O fences do not imply memory fences: the `FIOM` bit that made them
// do so lived in `menvcfg`/`senvcfg` and applied only below machine
// mode.
function is_fiom_active() -> bool = false

// registers for trap handling

bitfield Mtvec : xlenbits = {
  Base : xlen - 1 .. 2,
  Mode : 1 .. 0
}
register mtvec : Mtvec  // Trap Vector

// PUBLIC: invoked from set_{ms}tvec() [exceptions/sys_exceptions.sail]
function legalize_tvec(
  o : Mtvec,
  v : xlenbits,
  direct_supported : bool,
  direct_alignment_exp : tvec_alignment,
  vectored_supported : bool,
  vectored_alignment_exp : tvec_alignment
) -> Mtvec = {
  let v = Mk_Mtvec(v);
  // Legalize mode.
  let v : Mtvec = match trapVectorMode(v[Mode]) {
    TV_Direct => if direct_supported then v else [v with Mode = o[Mode]],
    TV_Vector => if vectored_supported then v else [v with Mode = o[Mode]],
    _         => match xtvec_mode_reserved_behavior {
      Xtvec_Fatal => reserved_behavior("Tried to write a reserved value (" ^ dec_str(unsigned(v[Mode])) ^ ") to the MODE field of xtvec."),
      Xtvec_Ignore => [v with Mode = o[Mode]],
    },
  };
  // Legalize alignment.
  let base_alignment : tvec_alignment = match trapVectorMode(v[Mode]) {
    TV_Direct   => direct_alignment_exp,
    TV_Vector   => vectored_alignment_exp,
    TV_Reserved => // This should never happen due to the check above.
                   internal_error(__FILE__, __LINE__, "Reserved mode in xtvec."),
  };
  // v[Base] doesn't contain the lowest 2 bits, and hence is at least 4-byte aligned.
  if base_alignment > 2
  then [v with Base = [v[Base] with (base_alignment - 3) .. 0 = zeros()]]
  else v;
}

bitfield Mcause : xlenbits = {
  IsInterrupt : xlen - 1,
  Cause       : xlen - 2 .. 0
}
register mcause : Mcause
mapping clause csr_name_map = 0x342  <-> "mcause"
function clause is_CSR_accessible(0x342, _) = true // mcause
function clause read_CSR(0x342) = mcause.bits
function clause write_CSR(0x342, value) = { mcause.bits = value; Ok(mcause.bits) }

// Interpreting the trap-vector address
function tvec_addr(m : Mtvec, c : Mcause) -> option(xlenbits) = {
  let base : xlenbits = m[Base] @ 0b00;
  match trapVectorMode(m[Mode]) {
    TV_Direct => Some(base),
    TV_Vector => if   c[IsInterrupt] == 0b1
                 then Some(base + (zero_extend(c[Cause]) << 2))
                 else Some(base),
    TV_Reserved => None()
  }
}

// Exception PC

register mepc : xlenbits

// With no compressed instructions the minimum PC alignment is four bytes,
// so the xepc legalization zeroes xepc[1:0].
// PUBLIC: invoked from set_xepc() [exceptions/sys_exceptions.sail]
function legalize_xepc(v : xlenbits) -> xlenbits = [v with 1..0 = zeros()]

// Align value to min supported PC alignment. This is used to
// legalize xepc reads.
function align_pc(addr : xlenbits) -> xlenbits = [addr with 1..0 = zeros()]

// auxiliary exception registers

register mtval    : xlenbits
register mscratch : xlenbits

mapping clause csr_name_map = 0x343  <-> "mtval"
mapping clause csr_name_map = 0x340  <-> "mscratch"

function clause is_CSR_accessible(0x343, _) = true // mtval
function clause is_CSR_accessible(0x340, _) = true // mscratch

function clause read_CSR(0x343) = mtval
function clause read_CSR(0x340) = mscratch

function clause write_CSR(0x343, value) = { mtval = value; Ok(mtval) }
function clause write_CSR(0x340, value) = { mscratch = value; Ok(mscratch) }

// The performance counters are deleted in every lifecycle state
// (R-15-077): `mcycle`, `minstret`, the `mhpmcounter`/`mhpmevent`
// banks, and `mcountinhibit` with them, so there is no counter to
// inhibit and no counter state to save. `mcounteren`/`scounteren`
// granted a less-privileged mode access to counters that no longer
// exist (R-15-003). What remains is `mtime`, which is memory-mapped
// rather than a CSR: the kernel programs the machine-timer compare
// through the fabric (R-15-063, R-15-066).

register mtime : bits(64)

// Machine information registers. Four of the five are hardwired zero,
// the reading RISC-V permits for all of them (R-15-052a): one Sail
// model frozen with the proof leaves no discovery question to ask, and
// no kernel path or admitted binary branches on an implementation
// identifier, so they are constants in the read clause rather than
// registers with configuration behind them.
//
// `mhartid` is the exception and the sole implementation identifier
// with a consumer (R-15-052b): one kernel binary runs unmodified on
// every core class and selects its per-hart state, the core's class,
// and the island binding from it at boot, so it keeps its register and
// its per-hart configured value.
register mhartid   : xlenbits = to_bits_checked(config platform.hartid : int)

mapping clause csr_name_map = 0xF11  <-> "mvendorid"
mapping clause csr_name_map = 0xF12  <-> "marchid"
mapping clause csr_name_map = 0xF13  <-> "mimpid"
mapping clause csr_name_map = 0xF14  <-> "mhartid"
mapping clause csr_name_map = 0xF15  <-> "mconfigptr"

function clause is_CSR_accessible(0xf11, _) = true // mvendorid
function clause is_CSR_accessible(0xf12, _) = true // marchdid
function clause is_CSR_accessible(0xf13, _) = true // mimpid
function clause is_CSR_accessible(0xf14, _) = true // mhartid
function clause is_CSR_accessible(0xf15, _) = mconfigptr_is_defined // mconfigptr

function clause read_CSR(0xF11) = zeros()
function clause read_CSR(0xF12) = zeros()
function clause read_CSR(0xF13) = zeros()
function clause read_CSR(0xF14) = mhartid
function clause read_CSR(0xF15) = zeros()

// The S-mode bank has no rows: `sstatus`, `stvec`, `sepc`, `scause`,
// `stval`, `sie`, `sip`, `sscratch`, `senvcfg` and `scounteren` are
// deleted with the ring there is no delegate for, and `satp` with the
// MMU, whose translation state the model no longer carries (R-15-003,
// R-15-002).

// The trigger module has no rows. `Sdtrig`'s `tselect` and `tdata1-3`
// are deleted in **every** lifecycle state rather than fused off with
// the Debug Module (R-15-079a): the CSRs are machine-mode-accessible
// and machine mode is the only mode here, so a fused trigger module
// would still leave a comparator any compartment holding
// access-system-registers permission could arm, firing on an address
// or data match and holding its arming across a partition switch,
// which is the shape admission test (3) rejects (R-15-010, R-15-012).
// Upstream's `tselect` read the ones-complement of what was written to
// advertise no trigger support; the four addresses now name no CSR at
// all, so they trap like any other unallocated address (R-15-014).

