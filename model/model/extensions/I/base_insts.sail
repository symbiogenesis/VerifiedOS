// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// *****************************************************************
// This file specifies the instructions in the base integer set.

// *****************************************************************
union clause instruction = UTYPE : (bits(20), regidx, uop)

mapping encdec_uop : uop <-> bits(7) = {
  LUI   <-> 0b0110111
}

mapping clause encdec = UTYPE(imm, rd, op)
  <-> imm @ encdec_reg(rd) @ encdec_uop(op)

$[split op]
function clause execute UTYPE(imm, rd, op) = {
  let off : xlenbits = sign_extend(imm @ 0x000);
  X(rd) = match op {
    LUI   => off
  };
  RETIRE_SUCCESS
}

mapping utype_mnemonic : uop <-> string = {
  LUI   <-> "lui"
}

mapping clause assembly = UTYPE(imm, rd, op)
  <-> utype_mnemonic(op) ^ spc() ^ reg_name(rd) ^ sep() ^ hex_bits_signed_20(imm)

// *****************************************************************

// Jump execution to a specified target address. This can fail
// due to the target not being 4-byte aligned, or due to extension checks.
// Callers must ensure that the target address is 2-byte aligned.
function jump_to(target : xlenbits) -> ExecutionResult = {
  // Extensions get the first checks on the prospective target address.
  match ext_control_check_pc(target) {
    Some(e) => return Ext_ControlAddr_Check_Failure(e),
    None()  => (),
  };

  // Perform standard alignment check.
  // Check target is at least 2-byte aligned (callers must ensure
  // this so it can be an assertion).
  assert(target[0] == 0b0);
  // There are no compressed instructions, so a target that is not
  // 4-byte aligned raises an alignment exception.
  if bit_to_bool(target[1])
  then return memory_exception(Virtaddr(target), E_Fetch_Addr_Align());

  set_next_pc(target);
  RETIRE_SUCCESS
}

// *****************************************************************
// The two jumps are absent here for the reason `auipc` is: on a purecap machine
// a jump-and-link writes a *capability* return address, sealed as a
// backward-edge sentry, and an indirect jump reads its target from a capability
// whose sentry it unseals, so both are capability instructions and their
// clauses are the capability surface's `cjal` and `cjalr`
// (extensions/CHERI/cheri_insts.sail, R-15-008, R-15-068, R-15-071). The
// encodings are unchanged; what is absent is a second, integer reading of them.
//
// Branches stay here: a branch writes no link and reads no register as an
// address, so its only capability obligation is the PCC bounds check
// `jump_to` already performs through `ext_control_check_pc`.

// *****************************************************************
union clause instruction = BTYPE : (bits(13), regidx, regidx, bop)

mapping encdec_bop : bop <-> bits(3) = {
  BEQ  <-> 0b000,
  BNE  <-> 0b001,
  BLT  <-> 0b100,
  BGE  <-> 0b101,
  BLTU <-> 0b110,
  BGEU <-> 0b111
}

mapping clause encdec = BTYPE(imm @ 0b0, rs2, rs1, op)
  <-> imm[11] @ imm[9..4] @ encdec_reg(rs2) @ encdec_reg(rs1) @ encdec_bop(op) @ imm[3..0] @ imm[10] @ 0b1100011

$[split op]
function clause execute BTYPE(imm, rs2, rs1, op) = {
  let taken : bool = match op {
    BEQ  => X(rs1) == X(rs2),
    BNE  => X(rs1) != X(rs2),
    BLT  => X(rs1) <_s X(rs2),
    BGE  => X(rs1) >=_s X(rs2),
    BLTU => X(rs1) <_u X(rs2),
    BGEU => X(rs1) >=_u X(rs2)
  };
  if taken
  then jump_to(PC + sign_extend(imm))
  else RETIRE_SUCCESS
}

mapping btype_mnemonic : bop <-> string = {
  BEQ  <-> "beq",
  BNE  <-> "bne",
  BLT  <-> "blt",
  BGE  <-> "bge",
  BLTU <-> "bltu",
  BGEU <-> "bgeu"
}

mapping clause assembly = BTYPE(imm, rs2, rs1, op)
  <-> btype_mnemonic(op) ^ spc() ^ reg_name(rs1) ^ sep() ^ reg_name(rs2) ^ sep() ^ hex_bits_signed_13(imm)

// *****************************************************************
union clause instruction = ITYPE : (bits(12), regidx, regidx, iop)

mapping encdec_iop : iop <-> bits(3) = {
  ADDI  <-> 0b000,
  SLTI  <-> 0b010,
  SLTIU <-> 0b011,
  ANDI  <-> 0b111,
  ORI   <-> 0b110,
  XORI  <-> 0b100
}

mapping clause encdec = ITYPE(imm, rs1, rd, op)
  <-> imm @ encdec_reg(rs1) @ encdec_iop(op) @ encdec_reg(rd) @ 0b0010011

$[split op]
function clause execute ITYPE(imm, rs1, rd, op) = {
  let immext : xlenbits = sign_extend(imm);
  X(rd) = match op {
    ADDI  => X(rs1) + immext,
    SLTI  => zero_extend(bool_to_bit(X(rs1) <_s immext)),
    SLTIU => zero_extend(bool_to_bit(X(rs1) <_u immext)),
    ANDI  => X(rs1) & immext,
    ORI   => X(rs1) | immext,
    XORI  => X(rs1) ^ immext
  };
  RETIRE_SUCCESS
}

mapping itype_mnemonic : iop <-> string = {
  ADDI  <-> "addi",
  SLTI  <-> "slti",
  SLTIU <-> "sltiu",
  XORI  <-> "xori",
  ORI   <-> "ori",
  ANDI  <-> "andi"
}

mapping clause assembly = ITYPE(imm, rs1, rd, op)
  <-> itype_mnemonic(op) ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1) ^ sep() ^ hex_bits_signed_12(imm)

// *****************************************************************
union clause instruction = SHIFTIOP : (bits(6), regidx, regidx, sop)

mapping encdec_sop : sop <-> bits(3) = {
  SLLI <-> 0b001,
  SRLI <-> 0b101,
  SRAI <-> 0b101
}

mapping clause encdec = SHIFTIOP(shamt, rs1, rd, SLLI)
  <-> 0b000000 @ shamt @ encdec_reg(rs1) @ 0b001 @ encdec_reg(rd) @ 0b0010011
mapping clause encdec = SHIFTIOP(shamt, rs1, rd, SRLI)
  <-> 0b000000 @ shamt @ encdec_reg(rs1) @ 0b101 @ encdec_reg(rd) @ 0b0010011
mapping clause encdec = SHIFTIOP(shamt, rs1, rd, SRAI)
  <-> 0b010000 @ shamt @ encdec_reg(rs1) @ 0b101 @ encdec_reg(rd) @ 0b0010011

$[split op]
function clause execute SHIFTIOP(shamt, rs1, rd, op) = {
  let shamt = shamt[log2_xlen - 1 .. 0];
  X(rd) = match op {
    SLLI => X(rs1) << shamt,
    SRLI => X(rs1) >> shamt,
    SRAI => shift_bits_right_arith(X(rs1), shamt),
  };
  RETIRE_SUCCESS
}

mapping shiftiop_mnemonic : sop <-> string = {
  SLLI <-> "slli",
  SRLI <-> "srli",
  SRAI <-> "srai"
}

mapping clause assembly = SHIFTIOP(shamt, rs1, rd, op)
  <-> shiftiop_mnemonic(op) ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1) ^ sep() ^ hex_bits_6(shamt)

// *****************************************************************
union clause instruction = RTYPE : (regidx, regidx, regidx, rop)

mapping clause encdec = RTYPE(rs2, rs1, rd, ADD)  <-> 0b0000000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b000 @ encdec_reg(rd) @ 0b0110011
mapping clause encdec = RTYPE(rs2, rs1, rd, SLT)  <-> 0b0000000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b010 @ encdec_reg(rd) @ 0b0110011
mapping clause encdec = RTYPE(rs2, rs1, rd, SLTU) <-> 0b0000000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b011 @ encdec_reg(rd) @ 0b0110011
mapping clause encdec = RTYPE(rs2, rs1, rd, AND)  <-> 0b0000000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b111 @ encdec_reg(rd) @ 0b0110011
mapping clause encdec = RTYPE(rs2, rs1, rd, OR)   <-> 0b0000000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b110 @ encdec_reg(rd) @ 0b0110011
mapping clause encdec = RTYPE(rs2, rs1, rd, XOR)  <-> 0b0000000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b100 @ encdec_reg(rd) @ 0b0110011
mapping clause encdec = RTYPE(rs2, rs1, rd, SLL)  <-> 0b0000000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b001 @ encdec_reg(rd) @ 0b0110011
mapping clause encdec = RTYPE(rs2, rs1, rd, SRL)  <-> 0b0000000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b101 @ encdec_reg(rd) @ 0b0110011
mapping clause encdec = RTYPE(rs2, rs1, rd, SUB)  <-> 0b0100000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b000 @ encdec_reg(rd) @ 0b0110011
mapping clause encdec = RTYPE(rs2, rs1, rd, SRA)  <-> 0b0100000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b101 @ encdec_reg(rd) @ 0b0110011

$[split op]
function clause execute RTYPE(rs2, rs1, rd, op) = {
  X(rd) = match op {
    ADD  => X(rs1) + X(rs2),
    SLT  => zero_extend(bool_to_bit(X(rs1) <_s X(rs2))),
    SLTU => zero_extend(bool_to_bit(X(rs1) <_u X(rs2))),
    AND  => X(rs1) & X(rs2),
    OR   => X(rs1) | X(rs2),
    XOR  => X(rs1) ^ X(rs2),
    SLL  => X(rs1) << X(rs2)[log2_xlen - 1 .. 0],
    SRL  => X(rs1) >> X(rs2)[log2_xlen - 1 .. 0],
    SUB  => X(rs1) - X(rs2),
    SRA  => shift_bits_right_arith(X(rs1), X(rs2)[log2_xlen - 1 .. 0]),
  };
  RETIRE_SUCCESS
}

mapping rtype_mnemonic : rop <-> string = {
  ADD  <-> "add",
  SLT  <-> "slt",
  SLTU <-> "sltu",
  AND  <-> "and",
  OR   <-> "or",
  XOR  <-> "xor",
  SLL  <-> "sll",
  SRL  <-> "srl",
  SUB  <-> "sub",
  SRA  <-> "sra"
}

mapping clause assembly = RTYPE(rs2, rs1, rd, op)
  <-> rtype_mnemonic(op) ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1) ^ sep() ^ reg_name(rs2)

// *****************************************************************
union clause instruction = LOAD : (bits(12), regidx, regidx, bool, word_width)

// unsigned loads are only present for widths strictly less than xlen,
// signed loads also present for widths equal to xlen
function valid_load_encdec(width : word_width, is_unsigned : bool) -> bool =
  (width < xlen_bytes) | (not(is_unsigned) & width <= xlen_bytes)

val extend_value : forall 'n, 0 < 'n <= xlen. (bool, bits('n)) -> xlenbits
function extend_value(is_unsigned, value) = if is_unsigned then zero_extend(value) else sign_extend(value)

$[wavedrom "offset[11:0] base _ width dest LOAD"]
mapping clause encdec = LOAD(imm, rs1, rd, is_unsigned, width)
  <-> imm @ encdec_reg(rs1) @ bool_bit(is_unsigned) @ width_enc(width) @ encdec_reg(rd) @ 0b0000011
  when valid_load_encdec(width, is_unsigned)

function clause execute LOAD(imm, rs1, rd, is_unsigned, width) = {
  let offset : xlenbits = sign_extend(imm);

  // This is checked during decoding.
  assert(width <= xlen_bytes);

  match data_read(rs1, offset, width, Load(Data), false, false) {
    Ok(data) => {
      X(rd) = extend_value(is_unsigned, data);
      RETIRE_SUCCESS
    },
    Err(e) => e,
  }
}

mapping maybe_u : bool <-> string = {
  true  <-> "u",
  false <-> ""
}

mapping clause assembly = LOAD(imm, rs1, rd, is_unsigned, width)
  <-> "l" ^ width_mnemonic(width) ^ maybe_u(is_unsigned) ^ spc() ^ reg_name(rd) ^ sep() ^ hex_bits_signed_12(imm) ^ "(" ^ reg_name(rs1) ^ ")"

// *****************************************************************
union clause instruction = STORE : (bits(12), regidx, regidx, word_width)

$[wavedrom "offset[11:5] src base _ width offset[4:0] STORE"]
mapping clause encdec = STORE(imm, rs2, rs1, width)
  <-> imm[11..5] @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b0 @ width_enc(width) @ imm[4..0] @ 0b0100011
  when width <= xlen_bytes

function clause execute STORE(imm, rs2, rs1, width) = {
  let offset : xlenbits = sign_extend(imm);

  // This is checked during decoding.
  assert(width <= xlen_bytes);

  // FIXME: the read of `rs2` should not be done before the
  // `mem_write_ea` of the effective address.
  // See https://github.com/riscv/sail-riscv/issues/1761.

  let data = X(rs2)[width * 8 - 1 .. 0];
  match data_write(rs1, offset, width, data, Store(Data), false, false) {
    Ok(_) => RETIRE_SUCCESS,
    Err(e) => e,
  }
}

mapping clause assembly = STORE(imm, rs2, rs1, width)
  <-> "s" ^ width_mnemonic(width) ^ spc() ^ reg_name(rs2) ^ sep() ^ hex_bits_signed_12(imm) ^ opt_spc() ^ "(" ^ opt_spc() ^ reg_name(rs1) ^ opt_spc() ^ ")"

// *****************************************************************
union clause instruction = ADDIW : (bits(12), regidx, regidx)

$[wavedrom "I-immediate[11:0] src ADDIW dest OP-IMM-32"]
mapping clause encdec = ADDIW(imm, rs1, rd)
  <-> imm @ encdec_reg(rs1) @ 0b000 @ encdec_reg(rd) @ 0b0011011

function clause execute ADDIW(imm, rs1, rd) = {
  let result = X(rs1) + sign_extend(imm);
  X(rd) = sign_extend(result[31..0]);
  RETIRE_SUCCESS
}

mapping clause assembly = ADDIW(imm, rs1, rd)
  <-> "addiw" ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1) ^ sep() ^ hex_bits_signed_12(imm)

// *****************************************************************
union clause instruction = RTYPEW : (regidx, regidx, regidx, ropw)

mapping clause encdec = RTYPEW(rs2, rs1, rd, ADDW)
  <-> 0b0000000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b000 @ encdec_reg(rd) @ 0b0111011
mapping clause encdec = RTYPEW(rs2, rs1, rd, SUBW)
  <-> 0b0100000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b000 @ encdec_reg(rd) @ 0b0111011
mapping clause encdec = RTYPEW(rs2, rs1, rd, SLLW)
  <-> 0b0000000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b001 @ encdec_reg(rd) @ 0b0111011
mapping clause encdec = RTYPEW(rs2, rs1, rd, SRLW)
  <-> 0b0000000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b101 @ encdec_reg(rd) @ 0b0111011
mapping clause encdec = RTYPEW(rs2, rs1, rd, SRAW)
  <-> 0b0100000 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b101 @ encdec_reg(rd) @ 0b0111011

$[split op]
function clause execute RTYPEW(rs2, rs1, rd, op) = {
  let rs1_val = X(rs1)[31..0];
  let rs2_val = X(rs2)[31..0];
  let result : bits(32) = match op {
    ADDW => rs1_val + rs2_val,
    SUBW => rs1_val - rs2_val,
    SLLW => rs1_val << rs2_val[4..0],
    SRLW => rs1_val >> rs2_val[4..0],
    SRAW => shift_bits_right_arith(rs1_val, rs2_val[4..0]),
  };
  X(rd) = sign_extend(result);
  RETIRE_SUCCESS
}

mapping rtypew_mnemonic : ropw <-> string = {
  ADDW <-> "addw",
  SUBW <-> "subw",
  SLLW <-> "sllw",
  SRLW <-> "srlw",
  SRAW <-> "sraw"
}

mapping clause assembly = RTYPEW(rs2, rs1, rd, op)
  <-> rtypew_mnemonic(op) ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1) ^ sep() ^ reg_name(rs2)

// *****************************************************************
union clause instruction = SHIFTIWOP : (bits(5), regidx, regidx, sopw)

mapping clause encdec = SHIFTIWOP(shamt, rs1, rd, SLLIW)
  <-> 0b0000000 @ shamt @ encdec_reg(rs1) @ 0b001 @ encdec_reg(rd) @ 0b0011011
mapping clause encdec = SHIFTIWOP(shamt, rs1, rd, SRLIW)
  <-> 0b0000000 @ shamt @ encdec_reg(rs1) @ 0b101 @ encdec_reg(rd) @ 0b0011011
mapping clause encdec = SHIFTIWOP(shamt, rs1, rd, SRAIW)
  <-> 0b0100000 @ shamt @ encdec_reg(rs1) @ 0b101 @ encdec_reg(rd) @ 0b0011011

$[split op]
function clause execute SHIFTIWOP(shamt, rs1, rd, op) = {
  let rs1_val = X(rs1)[31..0];
  let result : bits(32) = match op {
    SLLIW => rs1_val << shamt,
    SRLIW => rs1_val >> shamt,
    SRAIW => shift_bits_right_arith(rs1_val, shamt),
  };
  X(rd) = sign_extend(result);
  RETIRE_SUCCESS
}

mapping shiftiwop_mnemonic : sopw <-> string = {
  SLLIW <-> "slliw",
  SRLIW <-> "srliw",
  SRAIW <-> "sraiw"
}

mapping clause assembly = SHIFTIWOP(shamt, rs1, rd, op)
  <-> shiftiwop_mnemonic(op) ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1) ^ sep() ^ hex_bits_5(shamt)

// *****************************************************************
union clause instruction = FENCE_TSO : unit

mapping clause encdec = FENCE_TSO()
  <-> 0b1000 @ 0b0011 @ 0b0011 @ 0b00000 @ 0b000 @ 0b00000 @ 0b0001111

// `fence.tso` is a semantic no-op (R-15-017). Under RVWMO it orders everything
// but store to later-load, which is the one relaxation Ztso leaves, so on a
// machine whose memory model is already TSO it asks for nothing the machine does
// not already do. It keeps its own encoding rather than folding into `FENCE`
// because `fm` 1000 is its allocation and every other `fm` traps below.
function clause execute FENCE_TSO() = RETIRE_SUCCESS

mapping clause assembly = FENCE_TSO()
  <-> "fence.tso"

// *****************************************************************
union clause instruction = FENCE : (bits(4), bits(4), regidx, regidx)

// Note: FENCE_TSO is encoded as FENCE so it must come first.
//
// `fm` is not an operand, it is the literal 0b0000. Upstream decodes every `fm`
// into this clause and then ignores it, which is the base ISA's forward
// compatibility rule: an implementation is to treat a reserved configuration as
// `fm`=0000 rather than trap. This profile refuses that rule outright, all
// reserved, custom, and unused encodings trapping rather than silently executing
// (R-15-014), and R-15-017 says so for this instruction by name. So the field is
// matched rather than bound, and the reserved values reach no clause and become
// ILLEGAL. `rs1` and `rd` are the residual class that stays legal-and-ignored:
// they are reserved for finer-grained fences of a *future* extension, so a
// program that sets them is asking for a fence this machine is entitled to give
// it in full.
mapping clause encdec = FENCE(pred, succ, rs, rd)
  <-> 0b0000 @ pred : bits(4) @ succ : bits(4) @ encdec_reg(rs) @ 0b000 @ encdec_reg(rd) @ 0b0001111

// The two semantics R-15-017 leaves. A `fence` drains the store buffer iff its
// predecessor set contains a write (`PW` or `PO`) and its successor set contains
// a read (`PR` or `PI`); every other combination is a no-op. The sets are IORW,
// so the write half of a predecessor is bits O and W and the read half of a
// successor is bits I and R, and each is one mask rather than a position in the
// 256-case lattice.
//
// Reading I and O directly is what retires `is_fiom_active`. Upstream made the
// I-implies-R and O-implies-W direction conditional on the FIOM bit of
// `menvcfg`/`senvcfg`, both of which left with the mode they gated (core/
// sys_regs.sail, R-15-049a); the condition here is unconditional and strictly
// stronger than the bit ever made it, so nothing is lost by the register going.
function fence_drains(pred : bits(4), succ : bits(4)) -> bool =
  (pred & 0b0101) != zeros() & (succ & 0b1010) != zeros()

function clause execute FENCE(pred, succ, _rs, _rd) = {
  if fence_drains(pred, succ) then sail_barrier(Barrier_RISCV_drain);
  RETIRE_SUCCESS
}

mapping bit_maybe_r : bits(1) <-> string = {
  0b1 <-> "r",
  0b0 <-> ""
}

mapping bit_maybe_w : bits(1) <-> string = {
  0b1 <-> "w",
  0b0 <-> ""
}

mapping bit_maybe_i : bits(1) <-> string = {
  0b1 <-> "i",
  0b0 <-> ""
}

mapping bit_maybe_o : bits(1) <-> string = {
  0b1 <-> "o",
  0b0 <-> ""
}

mapping fence_bits : bits(4) <-> string = {
  // Fences with empty predecessor or successor sets are nops.
  // Clang/LLVM's assembly supports using `0` for these.
  // Binutils/GAS does not so you would have to use `.insn` to encode these.
  0b0000 <-> "0",
  i : bits(1) @ o : bits(1) @ r : bits(1) @ w : bits(1) <-> bit_maybe_i(i) ^ bit_maybe_o(o) ^ bit_maybe_r(r) ^ bit_maybe_w(w),
}

// Every legal encoding disassembles: a reserved `fm` is no longer one of them,
// so the class that had no assembly is now the `fence` carrying a non-zero `rs1`
// or `rd`, which stays legal and ignored.
// Unfortunately we need to split forwards and backwards because there's
// no way to write a zero regidx as a literal.
mapping clause assembly =
  forwards FENCE(pred, succ, rs, rd) => "fence" ^ spc() ^ fence_bits(pred) ^ sep() ^ fence_bits(succ)
    when rs == zreg & rd == zreg

// TODO: This hits a Sail compiler bug, https://github.com/rems-project/sail/issues/1577
// however we don't currently use the assembler direction of this mapping so
// it doesn't really matter.
// mapping clause assembly =
//   backwards "fence" ^ spc() ^ fence_bits(pred) ^ sep() ^ fence_bits(succ) => FENCE(pred, succ, zreg, zreg)

// *****************************************************************
union clause instruction = ECALL : unit

mapping clause encdec = ECALL()
  <-> 0b000000000000 @ 0b00000 @ 0b000 @ 0b00000 @ 0b1110011

function clause execute ECALL() = {
  let t : sync_exception = struct {
    trap    = E_M_EnvCall(),
    excinfo = None(),
    ext     = None(),
  };
  trap(t)
}

mapping clause assembly = ECALL() <-> "ecall"

// *****************************************************************
union clause instruction = MRET : unit

mapping clause encdec = MRET()
  <-> 0b0011000 @ 0b00010 @ 0b00000 @ 0b000 @ 0b00000 @ 0b1110011

// `mret` no longer transfers privilege: with one mode it restores the
// interrupt-enable stack and returns to `mepc`. `sret` is deleted with
// the mode there is no returning to (R-15-003).
function clause execute MRET() = {
  if   not(ext_check_xret_priv())
  then Ext_XRET_Priv_Failure()
  else {
    mstatus[MIE]  = mstatus[MPIE];
    mstatus[MPIE] = 0b1;

    long_csr_write_callback("mstatus", mstatus.bits);

    set_next_pc(prepare_xret_target());

    xret_callback(true);
    RETIRE_SUCCESS
  }
}

mapping clause assembly = MRET() <-> "mret"

// *****************************************************************
union clause instruction = EBREAK : unit

mapping clause encdec = EBREAK()
  <-> 0b000000000001 @ 0b00000 @ 0b000 @ 0b00000 @ 0b1110011

function clause execute EBREAK() =
  trap(make_sync_exception(E_Breakpoint(), PC))

mapping clause assembly = EBREAK() <-> "ebreak"

// *****************************************************************
union clause instruction = WFI : unit

mapping clause encdec = WFI()
  <-> 0b000100000101 @ 0b00000 @ 0b000 @ 0b00000 @ 0b1110011

// `mstatus.TW`, which made WFI illegal in a less-privileged mode after
// a bounded wait, is gone with that mode.
function clause execute WFI() = Enter_Wait(WAIT_WFI)

mapping clause assembly = WFI() <-> "wfi"

// `sfence.vma` is deleted: there is no address translation to fence
// and no TLB to flush (R-15-002, R-15-038).
