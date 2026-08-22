// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

function clause currentlyEnabled(Ext_A) = hartSupports(Ext_A) & misa[A] == 0b1 // TODO: Move currentlyEnabled(Ext_A) to a more central file
function clause currentlyEnabled(Ext_Zaamo) = hartSupports(Ext_Zaamo) | currentlyEnabled(Ext_A)
function clause currentlyEnabled(Ext_Zabha) = hartSupports(Ext_Zabha) & currentlyEnabled(Ext_Zaamo)

function clause currentlyEnabled(Ext_Ziccamoa) = hartSupports(Ext_Ziccamoa)

// Zaamo defines AMOs for 32-bit and 64-bit.
// Zabha defines AMOs for 8-bit and 16-bit.
//
// Those two are the whole of the atomic surface (R-15-024). The
// compare-and-swap `Zacas` added is gone (R-15-026, R-15-027), and with it
// the only operand wider than XLEN, so the register-pair operands, the
// even-numbered-register rule and the reserved behaviour that rule needed a
// policy for are all absences here rather than configuration.
//
// The operation is no longer an operand of this question. It was one while
// `AMOCAS` was decoded here, because that one operation answered to a
// different extension and admitted a different width; every operation that is
// left is a `Zaamo` one at a `Zaamo` width, so what remains to check is the
// width alone.
private function amo_encoding_valid(width : word_width) -> bool =
  currentlyEnabled(Ext_Zaamo)
  &
  // Check the size.
  (if width < 4 then currentlyEnabled(Ext_Zabha) else width <= xlen_bytes)

// *****************************************************************

union clause instruction = AMO : (amoop, bool, bool, regidx, regidx, word_width, regidx)

mapping encdec_amoop : amoop <-> bits(5) = {
  AMOSWAP <-> 0b00001,
  AMOADD  <-> 0b00000,
  AMOXOR  <-> 0b00100,
  AMOAND  <-> 0b01100,
  AMOOR   <-> 0b01000,
  AMOMIN  <-> 0b10000,
  AMOMAX  <-> 0b10100,
  AMOMINU <-> 0b11000,
  AMOMAXU <-> 0b11100,
}

mapping clause encdec = AMO(op, aq, rl, rs2, rs1, size, rd)
  <-> encdec_amoop(op) @ bool_bit(aq) @ bool_bit(rl) @ encdec_reg(rs2) @ encdec_reg(rs1) @ width_enc_amo(size) @ encdec_reg(rd) @ 0b0101111
  when amo_encoding_valid(size)

$[split op]
function clause execute AMO(op, aq, rl, rs2, rs1, width, rd) = {
  let 'width = width;

  // This is checked during decoding.
  assert(width <= xlen_bytes);

  let access = Atomic(op, aq, rl, Data, Data);

  // Get the address, X(rs1) (no offset).
  // Some extensions perform additional checks on address validity.
  let vaddr : virtaddr = match get_transformed_data_addr(rs1, zeros(), access, width) {
    Ext_DataAddr_Error(e)  => return Ext_DataAddr_Check_Failure(e),
    Ext_DataAddr_OK(vaddr) => vaddr,
  };

  if not(is_aligned_addr(vaddr, width)) then {
    // Check if the model is configured to raise an exception based on
    // the misaligned effective address.
    match plat_misaligned_exception(access) {
      Some(AccessFault)        => return memory_exception(vaddr, E_SAMO_Access_Fault()),
      Some(AlignmentException) => return memory_exception(vaddr, E_SAMO_Addr_Align()),
      // No exception yet, but we may still get one from the PMA check.
      None()                   => (),
    };
  };

  let addr = physical_address(vaddr);

  let loaded : bits('width * 8) = match mem_write_ea(addr, width, access, aq & rl, rl) {
    Err(exc_addr, e) => {
      // AMOs should not get split.
      assert(exc_addr == addr);
      return memory_exception(vaddr, e)
    },
    Ok(_)  => match mem_read(access, addr, width, aq, aq & rl) {
      Err(exc_addr, e) => {
        // AMOs should not get split.
        assert(exc_addr == addr);
        return memory_exception(vaddr, e)
      },
      Ok(loaded) => loaded,
    },
  };

  // Sequence the read of `rs2` after the call to `mem_write_ea` with the effective address.
  // See https://github.com/riscv/sail-riscv/issues/1761.

  let rs2_val : bits('width * 8) = trunc(X(rs2));

  let result : bits('width * 8) = match op {
    AMOSWAP => rs2_val,
    AMOADD  => rs2_val + loaded,
    AMOXOR  => rs2_val ^ loaded,
    AMOAND  => rs2_val & loaded,
    AMOOR   => rs2_val | loaded,
    AMOMIN  => if rs2_val <_s loaded then rs2_val else loaded,
    AMOMAX  => if rs2_val >_s loaded then rs2_val else loaded,
    AMOMINU => if rs2_val <_u loaded then rs2_val else loaded,
    AMOMAXU => if rs2_val >_u loaded then rs2_val else loaded,
  };

  // Every operation writes its value back: the one that did not was the
  // compare-and-swap that compared unequal, and it is gone with `Zacas`.
  match mem_write_value(addr, width, sign_extend(result), access, aq & rl, rl) {
    Ok(true)  => {
      X(rd) = sign_extend(loaded);
      RETIRE_SUCCESS
    },
    Ok(false) => internal_error(__FILE__, __LINE__, "AMO got false from mem_write_value"),
    Err(exc_addr, e) => {
      // AMOs should not get split.
      assert(exc_addr == addr);
      memory_exception(vaddr, e)
    }
  }
}

mapping clause assembly = AMO(op, aq, rl, rs2, rs1, width, rd)
  <-> amo_mnemonic(op) ^ "." ^ width_mnemonic(width) ^ maybe_aqrl(aq, rl) ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs2) ^ sep() ^ "(" ^ reg_name(rs1) ^ ")"
