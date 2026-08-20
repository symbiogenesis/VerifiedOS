// =======================================================================================
// Ported from the CHERI-RISC-V Sail model (CTSRD-CHERI/sail-cheri-riscv @ bb07488d,
// src/cheri_insts.sail, src/cheri_insts_begin.sail, src/cheri_insts_end.sail and
// src/cheri_scr_map.sail), which is subject to the BSD two-clause licence in
// model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The capability instruction surface.
//
// This is ISAv9's, at ISAv9's parameterization, which is the batch's shape
// rather than a delay: the M0.4 oracle (`cheri_riscv_sim_RV64`, built from the
// same upstream at the same pin) is the differential reference for the
// transplant, and it is a reference only over instructions both models decode
// (core/cap_format.sail). M0.6f narrows the surface to the frozen profile at
// the same time as it narrows the format.
//
// Three ISAv9 groups are **not** carried across, each because the machine no
// longer has what they act on rather than because the profile excludes them:
//
//   - `FPClear` clears the scalar floating-point registers, and the whole
//     scalar floating-point file is deleted (R-15-039, c4).
//   - `LoadRes*`, `StoreCond*`, and the sub-word `lr`/`sc` decodings ISAv9 adds
//     to the base need a reservation, and `Zalrsc` is deleted with the
//     reservation register (R-15-025, c3).
//   - `AMOSwapCap` is a capability-width atomic swap, and `A` is narrowed to
//     `Zaamo` + `Zabha` at byte, halfword, word, and doubleword (R-15-024), so
//     the width it names is not one the adopted atomic surface carries.
//
// The capability layer is ungated, as the format and algebra in `core` are: the
// machine is purecap-only, so an `Xcheri` extension gate would be a
// configuration key with one admitted value (R-15-001, R-15-005).

// One bit of Boolean in a register. `cgettag`, `cgetsealed`, `cseqx`, and
// `ctestsubset` all answer with a register, and a register is XLEN wide.
function bool_to_xlenbits(b : bool) -> xlenbits = if b then zero_extend(0b1) else zeros()

// `cgetlen` and `cgettop` also answer in a register, and length and top are
// CLEN+1-bit quantities, so both saturate at the largest value an address-wide
// result can carry.
let cap_max_addr : CapLen = (2 ^ cap_addr_width) - 1

// The return capability a capability call writes: the next instruction's PCC,
// sealed as a backward-edge sentry so it is usable as a control-flow target
// exactly once and nowhere else (R-15-008, R-15-068, R-15-071).
function link_capability() -> Capability = {
  let (representable, linkCap) = setCapAddr(PCC, get_next_pc());
  assert(representable, "Link capability should always be representable");
  assert(not(isCapSealed(linkCap)), "Link capability should always be unsealed");
  sealCap(linkCap, otype_sentry_bits)
}

// *****************************************************************
// Capability-mode control transfers.
//
// These three replace `auipc`, `jal`, and `jalr` when PCC is in capability
// mode, and they are the only instructions that decode differently rather than
// through the address hook, which is why they need a second decode mapping
// (postlude/decode_ext.sail).

union clause instruction = AUIPCC : (bits(20), regidx)

mapping clause encdec_capmode = AUIPCC(imm, cd)
  <-> imm @ encdec_reg(cd) @ 0b0010111

function clause execute AUIPCC(imm, cd) = {
  let off : xlenbits = sign_extend(imm @ 0x000);
  let (representable, newCap) = setCapAddr(PCC, get_arch_pc() + off);
  C(cd) = clearTagIf(newCap, not(representable));
  RETIRE_SUCCESS
}

mapping clause assembly = AUIPCC(imm, cd)
  <-> "auipcc" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ hex_bits_20(imm)

// *****************************************************************
union clause instruction = CJAL : (bits(21), regidx)

// See `mapping clause encdec = JAL` for why the immediate is spelled out.
mapping clause encdec_capmode = CJAL(imm_19 @ imm_7_0 @ imm_8 @ imm_18_13 @ imm_12_9 @ 0b0, cd)
  <-> imm_19 : bits(1) @ imm_18_13 : bits(6) @ imm_12_9 : bits(4) @ imm_8 : bits(1) @ imm_7_0 : bits(8) @ encdec_reg(cd) @ 0b1101111

function clause execute CJAL(imm, cd) = {
  let off : xlenbits = sign_extend(imm);
  let newPC = get_arch_pc() + off;
  if not(inCapBounds(PCC, newPC, min_instruction_bytes)) then
    Ext_ControlAddr_Check_Failure((CapEx_LengthViolation, PCC_IDX))
  else if bit_to_bool(newPC[1]) then
    memory_exception(Virtaddr(newPC), E_Fetch_Addr_Align())
  else {
    C(cd) = link_capability();
    set_next_pc(newPC);
    RETIRE_SUCCESS
  }
}

mapping clause assembly = CJAL(imm, cd)
  <-> "cjal" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ hex_bits_21(imm)

// *****************************************************************
union clause instruction = CJALR : (bits(12), regidx, regidx)

mapping clause encdec_capmode = CJALR(imm, cs1, cd)
  <-> imm @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1100111

function clause execute CJALR(imm, cs1, cd) = {
  let cs1_val = C(cs1);
  let idx = capreg_idx_of_regidx(cs1);
  let off : xlenbits = sign_extend(imm);
  // Bit zero is cleared as it is for `jalr`.
  let newPC = [cs1_val.address + off with 0 = 0b0];

  if not(cs1_val.tag) then
    Ext_ControlAddr_Check_Failure((CapEx_TagViolation, idx))
  // A forward-edge sentry is unsealed by the jump itself, which is what makes
  // domain entry a hardware property with no separate call gate (R-15-068).
  // Any other sealed type, and any non-zero displacement onto a sentry, is a
  // seal violation.
  else if isCapSealed(cs1_val) & ((cs1_val.otype != otype_sentry_bits) | (imm != zeros())) then
    Ext_ControlAddr_Check_Failure((CapEx_SealViolation, idx))
  else if not(cs1_val.permit_execute) then
    Ext_ControlAddr_Check_Failure((CapEx_PermitExecuteViolation, idx))
  else if bit_to_bool(newPC[1]) then
    memory_exception(Virtaddr(newPC), E_Fetch_Addr_Align())
  else if not(inCapBounds(cs1_val, newPC, min_instruction_bytes)) then
    Ext_ControlAddr_Check_Failure((CapEx_LengthViolation, idx))
  else {
    C(cd) = link_capability();
    set_next_pc(newPC);
    nextPCC = unsealCap(cs1_val);
    RETIRE_SUCCESS
  }
}

mapping clause assembly = CJALR(imm, cs1, cd)
  <-> "cjalr" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ hex_bits_signed_12(imm)

// *****************************************************************
// The two-register jumps, which are the mode-independent forms of the pair
// above: each is the capability-mode instruction with a zero displacement, so
// each redirects rather than repeating its checks.

union clause instruction = JALR_CAP : (regidx, regidx)

mapping clause encdec = JALR_CAP(cd, cs1)
  <-> 0b1111111 @ 0b01100 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011

function clause execute JALR_CAP(cd, cs1) = ExecuteAs(CJALR(zeros(), cs1, cd))

mapping clause assembly = JALR_CAP(cd, cs1)
  <-> "jalr.cap" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1)

// *****************************************************************
union clause instruction = JALR_PCC : (regidx, regidx)

mapping clause encdec = JALR_PCC(rd, rs1)
  <-> 0b1111111 @ 0b10100 @ encdec_reg(rs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011

function clause execute JALR_PCC(rd, rs1) = ExecuteAs(JALR(zeros(), rs1, rd))

mapping clause assembly = JALR_PCC(rd, rs1)
  <-> "jalr.pcc" ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1)

// *****************************************************************
union clause instruction = CInvoke : (regidx, regidx)

mapping clause encdec = CInvoke(cs1, cs2)
  <-> 0b1111110 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ 0b00001 @ 0b1011011

function clause execute CInvoke(cs1, cs2) = {
  let cs1_val = C(cs1);
  let cs2_val = C(cs2);
  let idx1 = capreg_idx_of_regidx(cs1);
  let idx2 = capreg_idx_of_regidx(cs2);
  let newPC = [cs1_val.address with 0 = 0b0];

  if not(cs1_val.tag) then
    Ext_ControlAddr_Check_Failure((CapEx_TagViolation, idx1))
  else if not(cs2_val.tag) then
    Ext_ControlAddr_Check_Failure((CapEx_TagViolation, idx2))
  else if hasReservedOType(cs1_val) then
    Ext_ControlAddr_Check_Failure((CapEx_SealViolation, idx1))
  else if hasReservedOType(cs2_val) then
    Ext_ControlAddr_Check_Failure((CapEx_SealViolation, idx2))
  else if cs1_val.otype != cs2_val.otype then
    Ext_ControlAddr_Check_Failure((CapEx_TypeViolation, idx1))
  else if not(cs1_val.permit_cinvoke) then
    Ext_ControlAddr_Check_Failure((CapEx_PermitCInvokeViolation, idx1))
  else if not(cs2_val.permit_cinvoke) then
    Ext_ControlAddr_Check_Failure((CapEx_PermitCInvokeViolation, idx2))
  else if not(cs1_val.permit_execute) then
    Ext_ControlAddr_Check_Failure((CapEx_PermitExecuteViolation, idx1))
  else if cs2_val.permit_execute then
    Ext_ControlAddr_Check_Failure((CapEx_PermitExecuteViolation, idx2))
  else if bit_to_bool(newPC[1]) then
    memory_exception(Virtaddr(newPC), E_Fetch_Addr_Align())
  else if not(inCapBounds(cs1_val, newPC, min_instruction_bytes)) then
    Ext_ControlAddr_Check_Failure((CapEx_LengthViolation, idx1))
  else {
    // The callee's data capability lands in the last register of the file,
    // which the ABI reserves for it.
    C(Regidx(ones())) = unsealCap(cs2_val);
    set_next_pc(newPC);
    nextPCC = unsealCap(cs1_val);
    RETIRE_SUCCESS
  }
}

mapping clause assembly = CInvoke(cs1, cs2)
  <-> "cinvoke" ^ spc() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)

// *****************************************************************
// Inspection: the fields of a capability, read into an integer register.

union clause instruction = CGetPerm   : (regidx, regidx)
union clause instruction = CGetType   : (regidx, regidx)
union clause instruction = CGetBase   : (regidx, regidx)
union clause instruction = CGetLen    : (regidx, regidx)
union clause instruction = CGetTag    : (regidx, regidx)
union clause instruction = CGetSealed : (regidx, regidx)
union clause instruction = CGetOffset : (regidx, regidx)
union clause instruction = CGetAddr   : (regidx, regidx)
union clause instruction = CGetFlags  : (regidx, regidx)
union clause instruction = CGetHigh   : (regidx, regidx)
union clause instruction = CGetTop    : (regidx, regidx)

function clause execute CGetPerm(rd, cs1) = {
  X(rd) = zero_extend(getCapPerms(C(cs1)));
  RETIRE_SUCCESS
}

function clause execute CGetFlags(rd, cs1) = {
  X(rd) = zero_extend(getCapFlags(C(cs1)));
  RETIRE_SUCCESS
}

function clause execute CGetType(rd, cs1) = {
  let capVal = C(cs1);
  // A reserved object type is reported as the negative architectural value it
  // stands for, which is what makes an unsealed capability read as -1.
  X(rd) = if   hasReservedOType(capVal)
          then sign_extend(capVal.otype)
          else zero_extend(capVal.otype);
  RETIRE_SUCCESS
}

function clause execute CGetBase(rd, cs1) = {
  X(rd) = getCapBaseBits(C(cs1));
  RETIRE_SUCCESS
}

function clause execute CGetOffset(rd, cs1) = {
  X(rd) = getCapOffsetBits(C(cs1));
  RETIRE_SUCCESS
}

function clause execute CGetAddr(rd, cs1) = {
  X(rd) = C(cs1).address;
  RETIRE_SUCCESS
}

function clause execute CGetTag(rd, cs1) = {
  X(rd) = bool_to_xlenbits(C(cs1).tag);
  RETIRE_SUCCESS
}

function clause execute CGetSealed(rd, cs1) = {
  X(rd) = bool_to_xlenbits(isCapSealed(C(cs1)));
  RETIRE_SUCCESS
}

function clause execute CGetLen(rd, cs1) = {
  let len = getCapLength(C(cs1));
  X(rd) = to_bits_truncate(xlen, if len > cap_max_addr then cap_max_addr else len);
  RETIRE_SUCCESS
}

function clause execute CGetTop(rd, cs1) = {
  let top = getCapTop(C(cs1));
  X(rd) = to_bits_truncate(xlen, if top > cap_max_addr then cap_max_addr else top);
  RETIRE_SUCCESS
}

// The bits `cgethigh` returns and `csethigh` consumes are the **in-memory**
// form, so the pair agrees with storing a capability and reloading its halves
// (core/cap_common.sail, `capToMemBits`). The pair is a property of a capability
// wider than a register: at the frozen 64+1-bit format there is no high half to
// name, so both go with the re-parameterization (M0.6f, R-15-007).
function clause execute CGetHigh(rd, cs1) = {
  X(rd) = capToMemBits(C(cs1))[xlen * 2 - 1 .. xlen];
  RETIRE_SUCCESS
}

mapping clause assembly = CGetPerm(rd, cs1)   <-> "cgetperm"   ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CGetType(rd, cs1)   <-> "cgettype"   ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CGetBase(rd, cs1)   <-> "cgetbase"   ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CGetLen(rd, cs1)    <-> "cgetlen"    ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CGetTag(rd, cs1)    <-> "cgettag"    ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CGetSealed(rd, cs1) <-> "cgetsealed" ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CGetOffset(rd, cs1) <-> "cgetoffset" ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CGetAddr(rd, cs1)   <-> "cgetaddr"   ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CGetFlags(rd, cs1)  <-> "cgetflags"  ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CGetHigh(rd, cs1)   <-> "cgethigh"   ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CGetTop(rd, cs1)    <-> "cgettop"    ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)

mapping clause encdec = CGetPerm(rd, cs1)   <-> 0b1111111 @ 0b00000 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetType(rd, cs1)   <-> 0b1111111 @ 0b00001 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetBase(rd, cs1)   <-> 0b1111111 @ 0b00010 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetLen(rd, cs1)    <-> 0b1111111 @ 0b00011 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetTag(rd, cs1)    <-> 0b1111111 @ 0b00100 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetSealed(rd, cs1) <-> 0b1111111 @ 0b00101 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetOffset(rd, cs1) <-> 0b1111111 @ 0b00110 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetFlags(rd, cs1)  <-> 0b1111111 @ 0b00111 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetAddr(rd, cs1)   <-> 0b1111111 @ 0b01111 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetHigh(rd, cs1)   <-> 0b1111111 @ 0b10111 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetTop(rd, cs1)    <-> 0b1111111 @ 0b11000 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011

// *****************************************************************
// The monotone derivations. Every one of them **clears the tag** where the
// result would exceed its input rather than trapping, so a failed derivation is
// a data result that faults at its next dereference and carries no cause code
// and no control-flow term in a timing bound (R-15-007h).

union clause instruction = CMove    : (regidx, regidx)
union clause instruction = CClearTag : (regidx, regidx)
union clause instruction = CSealEntry : (regidx, regidx)

function clause execute CMove(cd, cs1) = {
  C(cd) = C(cs1);
  RETIRE_SUCCESS
}

function clause execute CClearTag(cd, cs1) = {
  C(cd) = clearTag(C(cs1));
  RETIRE_SUCCESS
}

function clause execute CSealEntry(cd, cs1) = {
  C(cd) = sealCap(clearTagIfSealed(C(cs1)), otype_sentry_bits);
  RETIRE_SUCCESS
}

mapping clause encdec = CMove(cd, cs1)      <-> 0b1111111 @ 0b01010 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CClearTag(cd, cs1)  <-> 0b1111111 @ 0b01011 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSealEntry(cd, cs1) <-> 0b1111111 @ 0b10001 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011

mapping clause assembly = CMove(cd, cs1)      <-> "cmove"      ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CClearTag(cd, cs1)  <-> "ccleartag"  ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CSealEntry(cd, cs1) <-> "csealentry" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1)

// *****************************************************************
union clause instruction = CRRL : (regidx, regidx)
union clause instruction = CRAM : (regidx, regidx)

// Both answer a runtime allocator, and allocation here is composition-time, so
// both go with the runtime bounds-rounding group the profile excludes
// (R-15-007k, M0.6f).
function clause execute CRRL(rd, rs1) = {
  X(rd) = getRepresentableLength(X(rs1));
  RETIRE_SUCCESS
}

function clause execute CRAM(rd, rs1) = {
  X(rd) = getRepresentableAlignmentMask(X(rs1));
  RETIRE_SUCCESS
}

mapping clause encdec = CRRL(rd, rs1) <-> 0b1111111 @ 0b01000 @ encdec_reg(rs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CRAM(rd, rs1) <-> 0b1111111 @ 0b01001 @ encdec_reg(rs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011

mapping clause assembly = CRRL(rd, rs1) <-> "crrl" ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1)
mapping clause assembly = CRAM(rd, rs1) <-> "cram" ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1)

// *****************************************************************
union clause instruction = CClear : (bits(2), bits(8))

// Sixteen registers cleared to NULL by mask, in two halves. The 0th bit of the
// low half names DDC rather than `c0`, `c0` having nothing to clear. The
// profile's own masked clear is `cclear h, mask` over the merged file, which
// arrives with the other bespoke rows (R-15-069a, M0.6g).
function clause execute CClear(q, m) = {
  let q_u = unsigned(q);
  foreach (i from 0 to 7) {
    if bit_to_bool(m[i]) then {
      if q_u == 0 & i == 0 then DDC = null_cap
      else C(Regidx(to_bits_truncate(regidx_bit_width, 8 * q_u + i))) = null_cap
    }
  };
  RETIRE_SUCCESS
}

mapping clause encdec = CClear(q, m)
  <-> 0b1111111 @ 0b01110 @ q @ m[7 .. 5] @ 0b000 @ m[4 .. 0] @ 0b1011011

mapping clause assembly = CClear(q, m)
  <-> "cclear" ^ spc() ^ hex_bits_2(q) ^ sep() ^ hex_bits_8(m)

// *****************************************************************
// Three-operand derivations.

union clause instruction = CAndPerm  : (regidx, regidx, regidx)
union clause instruction = CSetFlags : (regidx, regidx, regidx)
union clause instruction = CSetHigh  : (regidx, regidx, regidx)
union clause instruction = CIncOffset : (regidx, regidx, regidx)
union clause instruction = CSetOffset : (regidx, regidx, regidx)
union clause instruction = CSetAddr   : (regidx, regidx, regidx)
union clause instruction = CSetBounds : (regidx, regidx, regidx)
union clause instruction = CSetBoundsExact : (regidx, regidx, regidx)
union clause instruction = CIncOffsetImmediate : (regidx, regidx, bits(12))
union clause instruction = CSetBoundsImmediate : (regidx, regidx, bits(12))

function clause execute CAndPerm(cd, cs1, rs2) = {
  let cs1_val = C(cs1);
  let mask = truncate(X(rs2), cap_perms_width);
  C(cd) = setCapPerms(clearTagIfSealed(cs1_val), getCapPerms(cs1_val) & mask);
  RETIRE_SUCCESS
}

function clause execute CSetFlags(cd, cs1, rs2) = {
  let flags = truncate(X(rs2), cap_flags_width);
  C(cd) = setCapFlags(clearTagIfSealed(C(cs1)), flags);
  RETIRE_SUCCESS
}

// The high half is replaced in the **in-memory** form and the result is always
// untagged, which is what keeps this from being capability reconstruction: it
// can only ever produce data (R-05-136).
function clause execute CSetHigh(cd, cs1, rs2) = {
  let capLow : xlenbits = capToMemBits(C(cs1))[xlen - 1 .. 0];
  C(cd) = memBitsToCapability(false, X(rs2) @ capLow);
  RETIRE_SUCCESS
}

function clause execute CIncOffset(cd, cs1, rs2) = {
  let (representable, newCap) = incCapOffset(clearTagIfSealed(C(cs1)), X(rs2));
  C(cd) = clearTagIf(newCap, not(representable));
  RETIRE_SUCCESS
}

function clause execute CIncOffsetImmediate(cd, cs1, imm) = {
  let delta : xlenbits = sign_extend(imm);
  let (representable, newCap) = incCapOffset(clearTagIfSealed(C(cs1)), delta);
  C(cd) = clearTagIf(newCap, not(representable));
  RETIRE_SUCCESS
}

function clause execute CSetOffset(cd, cs1, rs2) = {
  let (representable, newCap) = setCapOffset(clearTagIfSealed(C(cs1)), X(rs2));
  C(cd) = clearTagIf(newCap, not(representable));
  RETIRE_SUCCESS
}

function clause execute CSetAddr(cd, cs1, rs2) = {
  let (representable, newCap) = setCapAddr(clearTagIfSealed(C(cs1)), X(rs2));
  C(cd) = clearTagIf(newCap, not(representable));
  RETIRE_SUCCESS
}

// The narrowing shared by the three `csetbounds` forms: base becomes the input's
// address and length the requested one, rounded outward where the format cannot
// hold it exactly. `exact` is what separates the plain form from the exact one.
function narrow_bounds(cs1_val : Capability, length : CapAddrBits) -> (bool, bool, Capability) = {
  let newBase = cs1_val.address;
  let newTop : CapLenBits = zero_extend(newBase) + zero_extend(length);
  let inBounds = inCapBounds(cs1_val, newBase, unsigned(length));
  let (exact, newCap) = setCapBounds(clearTagIfSealed(cs1_val), newBase, newTop);
  (inBounds, exact, newCap)
}

function clause execute CSetBounds(cd, cs1, rs2) = {
  let (inBounds, _, newCap) = narrow_bounds(C(cs1), X(rs2));
  C(cd) = clearTagIf(newCap, not(inBounds));
  RETIRE_SUCCESS
}

function clause execute CSetBoundsImmediate(cd, cs1, uimm) = {
  let (inBounds, _, newCap) = narrow_bounds(C(cs1), zero_extend(uimm));
  C(cd) = clearTagIf(newCap, not(inBounds));
  RETIRE_SUCCESS
}

// The exact form's consumer is a runtime allocator, so it goes with `CRAM` and
// `CRRL`: here every emitted narrowing is exactly representable by construction
// of the static memory plan, and an inexact one is a defect in the plan rather
// than a runtime event (R-15-007k).
function clause execute CSetBoundsExact(cd, cs1, rs2) = {
  let (inBounds, exact, newCap) = narrow_bounds(C(cs1), X(rs2));
  C(cd) = clearTagIf(newCap, not(inBounds & exact));
  RETIRE_SUCCESS
}

mapping clause encdec = CSetBounds(cd, cs1, rs2)      <-> 0b0001000 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSetBoundsExact(cd, cs1, rs2) <-> 0b0001001 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CAndPerm(cd, cs1, rs2)        <-> 0b0001101 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSetFlags(cd, cs1, rs2)       <-> 0b0001110 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSetOffset(cd, cs1, rs2)      <-> 0b0001111 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSetAddr(cd, cs1, rs2)        <-> 0b0010000 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CIncOffset(cd, cs1, rs2)      <-> 0b0010001 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSetHigh(cd, cs1, rs2)        <-> 0b0010110 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011

mapping clause encdec = CIncOffsetImmediate(cd, cs1, imm) <-> imm @ encdec_reg(cs1) @ 0b001 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSetBoundsImmediate(cd, cs1, imm) <-> imm @ encdec_reg(cs1) @ 0b010 @ encdec_reg(cd) @ 0b1011011

mapping clause assembly = CAndPerm(cd, cs1, rs2)   <-> "candperm"   ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CSetFlags(cd, cs1, rs2)  <-> "csetflags"  ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CSetHigh(cd, cs1, rs2)   <-> "csethigh"   ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CSetOffset(cd, cs1, rs2) <-> "csetoffset" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CSetAddr(cd, cs1, rs2)   <-> "csetaddr"   ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CIncOffset(cd, cs1, rs2) <-> "cincoffset" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CSetBounds(cd, cs1, rs2) <-> "csetbounds" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CSetBoundsExact(cd, cs1, rs2) <-> "csetboundsexact" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)

mapping clause assembly = CIncOffsetImmediate(cd, cs1, imm) <-> "cincoffsetimm" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ hex_bits_12(imm)
mapping clause assembly = CSetBoundsImmediate(cd, cs1, imm) <-> "csetboundsimm" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ hex_bits_12(imm)

// *****************************************************************
// Comparison and pointer arithmetic between two capabilities.

union clause instruction = CToPtr   : (regidx, regidx, regidx)
union clause instruction = CFromPtr : (regidx, regidx, regidx)
union clause instruction = CSub     : (regidx, regidx, regidx)
union clause instruction = CSEQX    : (regidx, regidx, regidx)
union clause instruction = CTestSubset : (regidx, regidx, regidx)

function clause execute CToPtr(rd, cs1, cs2) = {
  let cs2_val = if cs2 == zreg then DDC else C(cs2);
  let cs1_val = C(cs1);
  X(rd) = if   not(cs1_val.tag)
          then zeros()
          else cs1_val.address - getCapBaseBits(cs2_val);
  RETIRE_SUCCESS
}

function clause execute CFromPtr(cd, cs1, rs2) = {
  let cs1_val = if cs1 == zreg then DDC else C(cs1);
  let rs2_val = X(rs2);
  if rs2_val == zeros() then {
    C(cd) = null_cap;
    RETIRE_SUCCESS
  } else {
    let (representable, newCap) = setCapOffset(clearTagIfSealed(cs1_val), rs2_val);
    C(cd) = clearTagIf(newCap, not(representable));
    RETIRE_SUCCESS
  }
}

function clause execute CSub(rd, cs1, cs2) = {
  X(rd) = C(cs1).address - C(cs2).address;
  RETIRE_SUCCESS
}

function clause execute CSEQX(rd, cs1, cs2) = {
  X(rd) = bool_to_xlenbits(C(cs1) == C(cs2));
  RETIRE_SUCCESS
}

// The subset test's two upstream consumers are a collector and a domain
// boundary's argument validation, and neither exists here, so it goes with the
// re-parameterization: its permission half is a bitwise containment test that
// the enumerated permission lattice has no reading of (R-15-007m, M0.6f).
function clause execute CTestSubset(rd, cs1, cs2) = {
  let cs1_val = if cs1 == zreg then DDC else C(cs1);
  let cs2_val = C(cs2);
  let (cs1_base, cs1_top) = getCapBounds(cs1_val);
  let (cs2_base, cs2_top) = getCapBounds(cs2_val);
  let cs1_perms = getCapPerms(cs1_val);
  let cs2_perms = getCapPerms(cs2_val);

  let subset = (cs1_val.tag == cs2_val.tag)
             & (cs2_base >= cs1_base)
             & (cs2_top <= cs1_top)
             & ((cs2_perms & cs1_perms) == cs2_perms);
  X(rd) = bool_to_xlenbits(subset);
  RETIRE_SUCCESS
}

mapping clause encdec = CToPtr(rd, cs1, cs2)      <-> 0b0010010 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CFromPtr(cd, cs1, rs2)    <-> 0b0010011 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSub(rd, cs1, cs2)        <-> 0b0010100 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CTestSubset(rd, cs1, cs2) <-> 0b0100000 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CSEQX(rd, cs1, cs2)       <-> 0b0100001 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011

mapping clause assembly = CToPtr(rd, cs1, cs2)      <-> "ctoptr"      ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)
mapping clause assembly = CFromPtr(cd, cs1, rs2)    <-> "cfromptr"    ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CSub(rd, cs1, cs2)        <-> "csub"        ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)
mapping clause assembly = CTestSubset(rd, cs1, cs2) <-> "ctestsubset" ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)
mapping clause assembly = CSEQX(rd, cs1, cs2)       <-> "cseqx"       ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)

// *****************************************************************
// Sealing.

union clause instruction = CSeal     : (regidx, regidx, regidx)
union clause instruction = CCSeal    : (regidx, regidx, regidx)
union clause instruction = CUnseal   : (regidx, regidx, regidx)
union clause instruction = CBuildCap : (regidx, regidx, regidx)
union clause instruction = CCopyType : (regidx, regidx, regidx)

function clause execute CSeal(cd, cs1, cs2) = {
  let cs1_val = C(cs1);
  let cs2_val = C(cs2);
  let cs2_cursor = getCapCursor(cs2_val);
  let (cs2_base, cs2_top) = getCapBounds(cs2_val);

  let permitted = cs2_val.tag
                & not(isCapSealed(cs2_val))
                & cs2_val.permit_seal
                & (cs2_cursor >= cs2_base)
                & (cs2_cursor < cs2_top)
                & (cs2_cursor <= cap_max_otype);

  let newCap = sealCap(clearTagIfSealed(cs1_val), to_bits_truncate(cap_otype_width, cs2_cursor));
  C(cd) = clearTagIf(newCap, not(permitted));
  RETIRE_SUCCESS
}

// The conditional seal exists to make a swapped-out capability's rederivation
// branchless, and there is no swap and no paging here, so it goes with
// `CBuildCap` and `CCopyType` in the reconstruction group (R-05-136, M0.6f).
function clause execute CCSeal(cd, cs1, cs2) = {
  let cs1_val = C(cs1);
  let cs2_val = C(cs2);
  let cs2_cursor = getCapCursor(cs2_val);
  let (cs2_base, cs2_top) = getCapBounds(cs2_val);

  let passthrough = not(cs2_val.tag)
                  | isCapSealed(cs1_val)
                  | (cs2_cursor < cs2_base)
                  | (cs2_cursor >= cs2_top)
                  | (signed(cs2_val.address) == otype_unsealed);
  if passthrough then {
    C(cd) = cs1_val;
    RETIRE_SUCCESS
  } else {
    let permitted = not(isCapSealed(cs2_val))
                  & cs2_val.permit_seal
                  & (cs2_cursor <= cap_max_otype);
    let newCap = sealCap(cs1_val, to_bits_truncate(cap_otype_width, cs2_cursor));
    C(cd) = clearTagIf(newCap, not(permitted));
    RETIRE_SUCCESS
  }
}

function clause execute CUnseal(cd, cs1, cs2) = {
  let cs1_val = C(cs1);
  let cs2_val = C(cs2);
  let cs2_cursor = getCapCursor(cs2_val);
  let (cs2_base, cs2_top) = getCapBounds(cs2_val);

  let permitted = cs2_val.tag
                & isCapSealed(cs1_val)
                & not(isCapSealed(cs2_val))
                & not(hasReservedOType(cs1_val))
                & (cs2_cursor == unsigned(cs1_val.otype))
                & cs2_val.permit_unseal
                & (cs2_cursor >= cs2_base)
                & (cs2_cursor < cs2_top);

  // Unsealing through a local authority yields a local capability: global is
  // the meet of the two rather than the sealed capability's own (R-15-074).
  let newCap = { unsealCap(cs1_val) with global = cs1_val.global & cs2_val.global };
  C(cd) = clearTagIf(newCap, not(permitted));
  RETIRE_SUCCESS
}

// `cbuildcap` and `ccopytype` are the reconstruction pair: each takes fields off
// an untagged or differently-typed capability and produces a tagged one under an
// authority. The profile forbids reconstruction at the root, admitting only the
// monotone derivations applied to a capability already held, so both go with
// `ccseal` (R-05-136, R-15-002, R-15-006, M0.6f).
function clause execute CBuildCap(cd, cs1, cs2) = {
  let authorityCap = if cs1 == zreg then DDC else C(cs1);
  let requestedCap' = { C(cs2) with tag = true };
  let requestedSentry = requestedCap'.otype == otype_sentry_bits;
  let requestedCap = if requestedSentry then requestedCap' else unsealCap(requestedCap');

  let (authorityBase, authorityTop) = getCapBounds(authorityCap);
  let (requestedBase, requestedTop) = getCapBounds(requestedCap);
  let authorityPerms = getCapPerms(authorityCap);
  let requestedPerms = getCapPerms(requestedCap);
  let requestedFlags = getCapFlags(requestedCap);

  let subset = (requestedBase >= authorityBase)
             & (requestedTop <= authorityTop)
             // The requested capability may be untagged, so its length may be
             // negative; this rejects that.
             & (requestedBase <= requestedTop)
             & ((requestedPerms & authorityPerms) == requestedPerms);

  let (exact, cd1) = setCapBounds(clearTagIfSealed(authorityCap),
                                  to_bits_truncate(cap_addr_width, requestedBase),
                                  to_bits_truncate(cap_len_width, requestedTop));
  // The representability check is not relevant here: the fast check is stated
  // over an increment and this is a fresh offset.
  let (_, cd2) = setCapOffset(cd1, getCapOffsetBits(requestedCap));
  let cd3 = setCapPerms(cd2, requestedPerms);
  let cd4 = setCapFlags(cd3, requestedFlags);
  let cd5 = if requestedSentry then sealCap(cd4, otype_sentry_bits) else cd4;
  // True exactly when the requested encoding was derivable: bounds within the
  // address space, no reserved bits set, and an authority that was tagged and
  // unsealed.
  let derivable = cd5 == requestedCap;
  assert(not(derivable) | exact, "CBuildCap: setCapBounds was not exact");

  C(cd) = if subset & derivable then cd5 else clearTag(requestedCap);
  RETIRE_SUCCESS
}

function clause execute CCopyType(cd, cs1, cs2) = {
  let cs2_val = C(cs2);
  let reserved = hasReservedOType(cs2_val);
  let otype : xlenbits = if reserved then sign_extend(cs2_val.otype) else zero_extend(cs2_val.otype);
  let (representable, newCap) = setCapAddr(clearTagIfSealed(C(cs1)), otype);
  C(cd) = clearTagIf(newCap, reserved | not(representable));
  RETIRE_SUCCESS
}

mapping clause encdec = CSeal(cd, cs1, cs2)     <-> 0b0001011 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CUnseal(cd, cs1, cs2)   <-> 0b0001100 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CBuildCap(cd, cs1, cs2) <-> 0b0011101 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CCopyType(cd, cs1, cs2) <-> 0b0011110 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CCSeal(cd, cs1, cs2)    <-> 0b0011111 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011

mapping clause assembly = CSeal(cd, cs1, cs2)     <-> "cseal"     ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)
mapping clause assembly = CUnseal(cd, cs1, cs2)   <-> "cunseal"   ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)
mapping clause assembly = CBuildCap(cd, cs1, cs2) <-> "cbuildcap" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)
mapping clause assembly = CCopyType(cd, cs1, cs2) <-> "ccopytype" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)
mapping clause assembly = CCSeal(cd, cs1, cs2)    <-> "ccseal"    ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)

// *****************************************************************
// The special capability registers. The bank and its numbering are in
// core/cap_regs.sail; what is here is the access rule and the two legalizations.
//
// Access is the capability, not a ring: everything but PCC and DDC needs the
// access-system-registers permission on the executing PCC (R-15-003).

// A capability written to MTCC has its address legalized the way a write to the
// integer `mtvec` view does (exceptions/sys_exceptions.sail).
function legalize_tcc(o : Capability, v : Capability) -> Capability = {
  let legalized = legalize_tvec(Mk_Mtvec(cap_to_integer_pc(o)),
                                cap_to_integer_pc(v),
                                plat_mtvec_direct_mode_supported,
                                plat_mtvec_direct_base_alignment_exp,
                                plat_mtvec_vectored_mode_supported,
                                plat_mtvec_vectored_base_alignment_exp);
  update_cap_with_integer_pc(v, legalized.bits)
}

// MEPCC is legalized on the way out rather than on the way in, and the identity
// case is left alone so that reading a sentry does not attempt to move its
// address.
function legalize_epcc(v : Capability) -> Capability = {
  let int_val = cap_to_integer_pc(v);
  let legalized = legalize_xepc(int_val);
  if legalized == int_val then v else update_cap_with_integer_pc(v, legalized)
}

union clause instruction = CSpecialRW : (regidx, screg, regidx)

mapping clause encdec = CSpecialRW(cd, scr, cs1)
  <-> 0b0000001 @ scr @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011

function clause execute CSpecialRW(cd, scr, cs1) = {
  let (exists, read_only, needASR) : (bool, bool, bool) = match scr {
    0b00000 => (true, true,  false), // PCC
    0b00001 => (true, false, false), // DDC
    0b11100 => (true, false, true),  // MTCC
    0b11101 => (true, false, true),  // MTDC
    0b11111 => (true, false, true),  // MEPCC
    _       => (false, true, true),
  };
  let writing = cs1 != zreg;

  if not(exists) | (read_only & writing) then
    Illegal_Instruction()
  else if needASR & not(PCC.access_system_regs) then
    // The register a capability fault names is the special register itself,
    // which sits above the merged file's indices (core/cap_causes.sail).
    Ext_DataAddr_Check_Failure((CapEx_AccessSystemRegsViolation, 0b1 @ scr))
  else {
    let cs1_val = C(cs1);
    C(cd) = match scr {
      0b00000 => {
        let (representable, pcc) = setCapAddr(PCC, get_arch_pc());
        assert(representable, "PCC at the architectural PC should always be representable");
        pcc
      },
      0b00001 => DDC,
      0b11100 => MTCC,
      0b11101 => MTDC,
      0b11111 => legalize_epcc(MEPCC),
      _       => { assert(false, "unreachable"); null_cap },
    };
    if writing then {
      match scr {
        0b00001 => DDC = cs1_val,
        0b11100 => MTCC = legalize_tcc(MTCC, cs1_val),
        0b11101 => MTDC = cs1_val,
        0b11111 => MEPCC = cs1_val,
        _       => assert(false, "unreachable"),
      }
      // A write to a special capability register is reported by the
      // capability-widened commit trace rather than by a print of its own
      // (M0.12), which is where `wC` leaves the register file's own writes too.
    };
    RETIRE_SUCCESS
  }
}

mapping clause assembly = CSpecialRW(cd, scr, cs1)
  <-> "cspecialrw" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ scr_name_map(scr) ^ sep() ^ cap_reg_name(cs1)

// *****************************************************************
// Explicit-authority data loads and stores.
//
// These name the authority in the opcode rather than taking the one the mode
// selects, which is what lets integer-mode code dereference a capability and
// capability-mode code dereference DDC. Both halves go with hybrid mode
// (R-15-001c, M0.6f); on a purecap machine the mode-selected form is the only
// one there is.

union clause instruction = LoadDataDDC  : (regidx, regidx, bool, word_width)
union clause instruction = LoadDataCap  : (regidx, regidx, bool, word_width)
union clause instruction = StoreDataDDC : (regidx, regidx, word_width)
union clause instruction = StoreDataCap : (regidx, regidx, word_width)

function explicit_load(rd : regidx, auth : Capability, auth_idx : capreg_idx, addr : xlenbits,
                       is_unsigned : bool, width : word_width) -> ExecutionResult = {
  let access = Load(Data);
  match cap_data_checks(auth, auth_idx, addr, access, width) {
    Some(e) => return Ext_DataAddr_Check_Failure(e),
    None()  => (),
  };
  match data_read_addr(Virtaddr(addr), width, access, false, false) {
    Ok(data) => { X(rd) = extend_value(is_unsigned, data); RETIRE_SUCCESS },
    Err(e)   => e,
  }
}

function explicit_store(rs2 : regidx, auth : Capability, auth_idx : capreg_idx, addr : xlenbits,
                        width : word_width) -> ExecutionResult = {
  let access = Store(Data);
  match cap_data_checks(auth, auth_idx, addr, access, width) {
    Some(e) => return Ext_DataAddr_Check_Failure(e),
    None()  => (),
  };
  let data = X(rs2)[width * 8 - 1 .. 0];
  match data_write_addr(Virtaddr(addr), width, data, access, false, false) {
    Ok(_)  => RETIRE_SUCCESS,
    Err(e) => e,
  }
}

function clause execute LoadDataDDC(rd, rs1, is_unsigned, width) =
  explicit_load(rd, DDC, DDC_IDX, DDC.address + X(rs1), is_unsigned, width)

function clause execute LoadDataCap(rd, cs1, is_unsigned, width) = {
  let cs1_val = C(cs1);
  explicit_load(rd, cs1_val, capreg_idx_of_regidx(cs1), cs1_val.address, is_unsigned, width)
}

function clause execute StoreDataDDC(rs2, rs1, width) =
  explicit_store(rs2, DDC, DDC_IDX, DDC.address + X(rs1), width)

function clause execute StoreDataCap(rs2, cs1, width) = {
  let cs1_val = C(cs1);
  explicit_store(rs2, cs1_val, capreg_idx_of_regidx(cs1), cs1_val.address, width)
}

mapping clause encdec = LoadDataDDC(rd, rs1, is_unsigned, width)
  <-> 0b1111101 @ 0b00 @ bool_bit(is_unsigned) @ width_enc(width) @ encdec_reg(rs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
  when valid_load_encdec(width, is_unsigned)

mapping clause encdec = LoadDataCap(rd, cs1, is_unsigned, width)
  <-> 0b1111101 @ 0b01 @ bool_bit(is_unsigned) @ width_enc(width) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
  when valid_load_encdec(width, is_unsigned)

mapping clause encdec = StoreDataDDC(rs2, rs1, width)
  <-> 0b1111100 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b000 @ 0b000 @ width_enc(width) @ 0b1011011
  when width <= xlen_bytes

mapping clause encdec = StoreDataCap(rs2, cs1, width)
  <-> 0b1111100 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ 0b010 @ width_enc(width) @ 0b1011011
  when width <= xlen_bytes

mapping clause assembly = LoadDataDDC(rd, rs1, u, w)
  <-> "l" ^ width_mnemonic(w) ^ maybe_u(u) ^ ".ddc" ^ spc() ^ reg_name(rd) ^ sep() ^ "(" ^ opt_spc() ^ reg_name(rs1) ^ opt_spc() ^ ")"
mapping clause assembly = LoadDataCap(rd, cs1, u, w)
  <-> "l" ^ width_mnemonic(w) ^ maybe_u(u) ^ ".cap" ^ spc() ^ reg_name(rd) ^ sep() ^ "(" ^ opt_spc() ^ cap_reg_name(cs1) ^ opt_spc() ^ ")"
mapping clause assembly = StoreDataDDC(rs2, rs1, w)
  <-> "s" ^ width_mnemonic(w) ^ ".ddc" ^ spc() ^ reg_name(rs2) ^ sep() ^ "(" ^ opt_spc() ^ reg_name(rs1) ^ opt_spc() ^ ")"
mapping clause assembly = StoreDataCap(rs2, cs1, w)
  <-> "s" ^ width_mnemonic(w) ^ ".cap" ^ spc() ^ reg_name(rs2) ^ sep() ^ "(" ^ opt_spc() ^ cap_reg_name(cs1) ^ opt_spc() ^ ")"

// *****************************************************************
// Capability loads and stores.
//
// The immediate forms are the ones a compiler emits: they take the authority the
// mode selects, so they are the purecap machine's `lc` and `sc`. The four
// explicit-authority forms beside them go with hybrid mode.

union clause instruction = LoadCapImm  : (regidx, regidx, bits(12))
union clause instruction = StoreCapImm : (regidx, regidx, bits(12))
union clause instruction = LoadCapDDC  : (regidx, regidx)
union clause instruction = LoadCapCap  : (regidx, regidx)
union clause instruction = StoreCapDDC : (regidx, regidx)
union clause instruction = StoreCapCap : (regidx, regidx)

function clause execute LoadCapImm(cd, rs1_cs1, imm) = {
  let (auth, addr, auth_idx) = cap_mode_auth(rs1_cs1, sign_extend(imm));
  cap_load(cd, auth, auth_idx, addr)
}

function clause execute StoreCapImm(cs2, rs1_cs1, imm) = {
  let (auth, addr, auth_idx) = cap_mode_auth(rs1_cs1, sign_extend(imm));
  cap_store(cs2, auth, auth_idx, addr)
}

function clause execute LoadCapDDC(cd, rs1) =
  cap_load(cd, DDC, DDC_IDX, DDC.address + X(rs1))

function clause execute LoadCapCap(cd, cs1) = {
  let cs1_val = C(cs1);
  cap_load(cd, cs1_val, capreg_idx_of_regidx(cs1), cs1_val.address)
}

function clause execute StoreCapDDC(cs2, rs1) =
  cap_store(cs2, DDC, DDC_IDX, DDC.address + X(rs1))

function clause execute StoreCapCap(cs2, cs1) = {
  let cs1_val = C(cs1);
  cap_store(cs2, cs1_val, capreg_idx_of_regidx(cs1), cs1_val.address)
}

// `sc` takes STORE funct3 100, which is vacant: the store widths the base
// encodes are three bits whose top is zero.
//
// `lc` takes MISC-MEM funct3 010, which is **not** vacant here, and the clash is
// a finding rather than a choice. ISAv9 puts the capability load there and the
// cache-block operations are also there, distinguished only by a zero
// destination and a small immediate; upstream never meets the two because it
// does not implement `Zicboz`, and the profile adopts it (R-15-060). The
// destination separates them: a capability load into the null register discards
// the value it loaded, so the encoding is useless as a load and is left to the
// cache-block block entire. The frozen dialect re-encodes this anyway
// (R-15-007), so what is owed at the freeze is a decision and not a repair.
mapping clause encdec = LoadCapImm(cd, rs1, imm)
  <-> imm @ encdec_reg(rs1) @ 0b010 @ encdec_reg(cd) @ 0b0001111
  when cd != zreg

mapping clause encdec = StoreCapImm(cs2, rs1, imm)
  <-> imm[11 .. 5] @ encdec_reg(cs2) @ encdec_reg(rs1) @ 0b100 @ imm[4 .. 0] @ 0b0100011

mapping clause encdec = LoadCapDDC(cd, rs1)
  <-> 0b1111101 @ 0b10111 @ encdec_reg(rs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = LoadCapCap(cd, cs1)
  <-> 0b1111101 @ 0b11111 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = StoreCapDDC(cs2, rs1)
  <-> 0b1111100 @ encdec_reg(cs2) @ encdec_reg(rs1) @ 0b000 @ 0b00100 @ 0b1011011
mapping clause encdec = StoreCapCap(cs2, cs1)
  <-> 0b1111100 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ 0b01100 @ 0b1011011

mapping clause assembly = LoadCapImm(cd, rs1, imm)
  <-> "lc" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ hex_bits_signed_12(imm) ^ opt_spc() ^ "(" ^ opt_spc() ^ reg_name(rs1) ^ opt_spc() ^ ")"
mapping clause assembly = StoreCapImm(cs2, rs1, imm)
  <-> "sc" ^ spc() ^ cap_reg_name(cs2) ^ sep() ^ hex_bits_signed_12(imm) ^ opt_spc() ^ "(" ^ opt_spc() ^ reg_name(rs1) ^ opt_spc() ^ ")"
mapping clause assembly = LoadCapDDC(cd, rs1)
  <-> "lc.ddc" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ "(" ^ opt_spc() ^ reg_name(rs1) ^ opt_spc() ^ ")"
mapping clause assembly = LoadCapCap(cd, cs1)
  <-> "lc.cap" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ "(" ^ opt_spc() ^ cap_reg_name(cs1) ^ opt_spc() ^ ")"
mapping clause assembly = StoreCapDDC(cs2, rs1)
  <-> "sc.ddc" ^ spc() ^ cap_reg_name(cs2) ^ sep() ^ "(" ^ opt_spc() ^ reg_name(rs1) ^ opt_spc() ^ ")"
mapping clause assembly = StoreCapCap(cs2, cs1)
  <-> "sc.cap" ^ spc() ^ cap_reg_name(cs2) ^ sep() ^ "(" ^ opt_spc() ^ cap_reg_name(cs1) ^ opt_spc() ^ ")"

// *****************************************************************
union clause instruction = CLoadTags : (regidx, regidx)

// The tag-group load: the validity tags of a naturally aligned group of
// granules returned in an integer register without loading the granules. Two
// parameters upstream leaves implementation-defined are fixed by the profile:
// the group is the CBO block `cbo.zero` allocates rather than a cache line, and
// the tags are reported **as stored** rather than as the revocation filter would
// return them, that filter having no base to index by (R-15-007q, R-08-007).
type log2_cap_block_size : Int = 6
type caps_per_block : Int = 2 ^ (log2_cap_block_size - log2_cap_size)
let  caps_per_block = sizeof(caps_per_block)

// Unlike a capability load, this one *faults* where the authority lacks
// load-capability permission rather than answering with cleared tags: an
// answer of all-zeroes would be indistinguishable from an empty group, and the
// sweep that reads it would silently miss every capability in it.
function clause execute CLoadTags(rd, cs1) = {
  let cs1_val = C(cs1);
  let idx = capreg_idx_of_regidx(cs1);
  let addr = cs1_val.address;
  let vaddr = Virtaddr(addr);
  assert(plat_cache_block_size_exp == sizeof(log2_cap_block_size),
         "cloadtags group is the CBO block, so the two must be configured alike");

  if not(cs1_val.tag) then
    Ext_DataAddr_Check_Failure((CapEx_TagViolation, idx))
  else if isCapSealed(cs1_val) then
    Ext_DataAddr_Check_Failure((CapEx_SealViolation, idx))
  else if not(cs1_val.permit_load) then
    Ext_DataAddr_Check_Failure((CapEx_PermitLoadViolation, idx))
  else if not(cs1_val.permit_load_cap) then
    Ext_DataAddr_Check_Failure((CapEx_PermitLoadCapViolation, idx))
  else if not(inCapBounds(cs1_val, addr, caps_per_block * cap_size)) then
    Ext_DataAddr_Check_Failure((CapEx_LengthViolation, idx))
  else if not(is_aligned_addr(vaddr, caps_per_block * cap_size)) then
    memory_exception(vaddr, E_Load_Addr_Align())
  else {
    let base = physical_address(vaddr);
    var tags : bits(caps_per_block) = zeros();
    var failure : option(ExceptionType) = None();

    foreach (i from 0 to (caps_per_block - 1)) {
      match failure {
        Some(_) => (),
        None()  => match mem_read_cap(Physaddr(bits_of(base) + (i * cap_size)), false, false) {
          Err(_, e) => failure = Some(e),
          Ok(v)     => tags = [tags with i = bool_to_bit(v.tag)],
        },
      }
    };

    match failure {
      Some(e) => memory_exception(vaddr, e),
      None()  => { X(rd) = zero_extend(tags); RETIRE_SUCCESS },
    }
  }
}

mapping clause encdec = CLoadTags(rd, cs1)
  <-> 0b1111111 @ 0b10010 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011

mapping clause assembly = CLoadTags(rd, cs1)
  <-> "cloadtags" ^ spc() ^ reg_name(rd) ^ sep() ^ "(" ^ opt_spc() ^ cap_reg_name(cs1) ^ opt_spc() ^ ")"
