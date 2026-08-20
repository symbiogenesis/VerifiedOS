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
    // MXL is a read-only field that specifies the native XLEN.
    MXL = architecture_bits(if xlen == 32 then RV32 else RV64),
  ]

// whether misa is R/W
let sys_enable_writable_misa : bool = config base.writable_misa

private function legalize_misa(m : Misa, v : xlenbits) -> Misa = {
  let v = Mk_Misa(v);
  // Suppress updates to MISA if MISA is not writable.
  if   not(sys_enable_writable_misa)
  then m
  else [m with
    A = if hartSupports(Ext_A) then v[A] else 0b0,
    B = if hartSupports(Ext_B) then v[B] else 0b0,
    // Compressed instructions are not implemented, so misa.C is read-only zero.
    C = 0b0,
    D = if hartSupports(Ext_D) & v[F] == 0b1 then v[D] else 0b0,
    F = if hartSupports(Ext_F) then v[F] else 0b0,
    H = 0b0,
    // Writable I is not currently supported.
    I = bool_to_bit(not(base_E_enabled)),
    E = bool_to_bit(base_E_enabled),
    M = if hartSupports(Ext_M) then v[M] else 0b0,
    // Q = if hartSupports(Ext_Q) then v[Q] else 0b0, TODO: Not supported yet
    // There is no supervisor or user mode to advertise.
    S = 0b0,
    U = 0b0,
    V = if hartSupports(Ext_V) & v[F] == 0b1 & v[D] == 0b1 then v[V] else 0b0,
    // X = ... TODO: If custom extensions are present this should be 1
  ]
}

mapping clause csr_name_map = 0x301  <-> "misa"
function clause is_CSR_accessible(0x301, _) = true // misa
function clause read_CSR(0x301) = misa.bits
function clause write_CSR(0x301, value) = { misa = legalize_misa(misa, value); Ok(misa.bits) }

// What is left of `mstatus` is the extension-context gate. Every other
// field it carried named a less-privileged mode or the machinery for
// entering one: the trap-and-virtualize bits (TSR, TW, TVM), the
// translation-permission bits (MXR, SUM), the modify-privilege
// retarget (MPRV), the effective-XLEN fields for the lower modes (SXL,
// UXL), the byte-endianness control for supervisor accesses (SBE), and
// the previous-mode and supervisor interrupt-enable stacks (MPP, SPP,
// SPIE, SIE). `FS` stays for now: scalar F/D is still modeled and is
// cut with the vector fork.
bitfield Mstatus : bits(64) = {
  SD   : xlen - 1,

  MBE  : 37,

  XS   : 16 .. 15,
  FS   : 14 .. 13,

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
    // Validate FS and VS against their allowed set.
    FS = legalize_extStatus(plat_mstatus_legal_fs, v[FS]),
    VS = legalize_extStatus(plat_mstatus_legal_vs, v[VS]),

    MPIE = v[MPIE],
    MIE = v[MIE],
  ];

  // Set dirty bit to OR of other status bits.
  let dirty = extStatus_map(o[FS]) == Dirty |
              extStatus_map(o[XS]) == Dirty |
              extStatus_map(o[VS]) == Dirty;

  [o with SD = bool_to_bit(dirty)]
}

register mstatus : Mstatus = Mk_Mstatus(zeros())

mapping clause csr_name_map = 0x300  <-> "mstatus"
mapping clause csr_name_map = 0x310  <-> "mstatush"

function clause is_CSR_accessible(0x300, _) = true // mstatus
function clause is_CSR_accessible(0x310, _) = mstatush_is_defined & xlen == 32 // mstatush

function clause read_CSR(0x300) = mstatus.bits[xlen - 1 .. 0]
function clause read_CSR(0x310 if xlen == 32) = mstatus.bits[63 .. 32]

function clause write_CSR((0x300, value) if xlen == 64) = { mstatus = legalize_mstatus(mstatus, value); Ok(mstatus.bits) }
function clause write_CSR((0x300, value) if xlen == 32) = { mstatus = legalize_mstatus(mstatus, mstatus.bits[63 .. 32] @ value); Ok(mstatus.bits[31 .. 0]) }
function clause write_CSR((0x310, value) if xlen == 32) = { mstatus = legalize_mstatus(mstatus, value @ mstatus.bits[31 .. 0]); Ok(mstatus.bits[63 .. 32]) }

// architecture and extension checks
//
// With one privilege mode there is one effective XLEN, `misa.MXL`.

function architecture() -> Architecture =
  if xlen == 32 then RV32 else architecture_bits(misa[MXL])

function in32BitMode() -> bool = {
  architecture() == RV32
}

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

// machine information registers
register mvendorid : bits(32) = to_bits_checked(config platform.vendorid : int)
register mimpid    : xlenbits = to_bits_checked(config platform.impid : int)
register marchid   : xlenbits = to_bits_checked(config platform.archid : int)
register mhartid   : xlenbits = to_bits_checked(config platform.hartid : int)

register mconfigptr : xlenbits = zeros()

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

function clause read_CSR(0xF11) = zero_extend(mvendorid)
function clause read_CSR(0xF12) = marchid
function clause read_CSR(0xF13) = mimpid
function clause read_CSR(0xF14) = mhartid
function clause read_CSR(0xF15) = mconfigptr

// The S-mode bank has no rows: `sstatus`, `stvec`, `sepc`, `scause`,
// `stval`, `sie`, `sip`, `sscratch`, `senvcfg` and `scounteren` are
// deleted with the ring there is no delegate for, and `satp` with the
// MMU, whose translation state the model no longer carries (R-15-003,
// R-15-002).

// disabled trigger/debug module
register tselect : xlenbits

mapping clause csr_name_map = 0x7a0  <-> "tselect"
mapping clause csr_name_map = 0x7a1  <-> "tdata1"
mapping clause csr_name_map = 0x7a2  <-> "tdata2"
mapping clause csr_name_map = 0x7a3  <-> "tdata3"

function clause is_CSR_accessible(0x7a0, _) = true
function clause read_CSR(0x7a0) = ~(tselect)  // this indicates we don't have any trigger support
function clause write_CSR(0x7a0, value) = { tselect = value; Ok(tselect) }

