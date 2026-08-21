// =======================================================================================
// Ported from the CHERI-RISC-V Sail model (CTSRD-CHERI/sail-cheri-riscv @ bb07488d,
// src/cheri_insts.sail, src/cheri_insts_begin.sail, src/cheri_insts_end.sail and
// src/cheri_scr_map.sail), which is subject to the BSD two-clause licence in
// model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The capability instruction surface, at the frozen dialect's parameterization.
//
// Membership is by enumeration and never by inheritance (R-15-007j): an ISAv9
// instruction the profile does not name is absent. What that removes here falls
// into five groups, each named with the mechanism it went with rather than with
// a preference:
//
//   - **Hybrid mode.** The capability-mode flag, the second decode it selected,
//     the explicit-authority data and capability load and store forms, and the
//     two mode-independent jumps all exist because there are two modes. With
//     one mode `auipc`, `jal` and `jalr` *are* the capability forms and a load
//     or store takes the authority in its base register, so each of those is a
//     duplicate encoding rather than an instruction (R-15-001, R-15-001c).
//     `cclear` goes with them: its low bit names DDC, and its two-quadrant,
//     sixteen-register shape is the split file's, where the profile's own
//     masked clear runs over the merged one and arrives with the other bespoke
//     rows (R-15-069a, R-15-069b).
//   - **Capability reconstruction.** `cbuildcap`, `ccopytype`, `ccseal` and
//     `csethigh` each take fields off one capability and produce a tagged one
//     under an authority. The profile forbids reconstruction at the root,
//     admitting only the monotone derivations applied to a capability already
//     held (R-05-136, R-15-002, R-15-006). `cgethigh` goes with `csethigh`,
//     the pair being a property of a capability wider than a register.
//   - **Runtime bounds rounding.** `cram`, `crrl` and `csetboundsexact` answer
//     a runtime allocator, and allocation here is composition-time: the static
//     memory plan lays every narrowable object out at its representable
//     alignment, so an inexact narrow is a defect in the plan rather than a
//     runtime event (R-15-007k).
//   - **The subset test.** `ctestsubset`'s two upstream consumers are a
//     collector and a domain boundary's argument validation, and neither exists
//     here; its permission half is a bitwise containment test that the
//     enumerated permission lattice has no reading of (R-15-007m).
//   - **The call gate.** `cinvoke` is the two-capability domain entry that
//     capability jump-and-link replaces: the sentry unseal-and-seal semantics
//     of `cjalr` *are* the hardware root of domain entry, so there is no
//     separate call gate to carry (R-15-068, R-15-069).
//
// Three further ISAv9 groups were already inapplicable before this batch, each
// because the machine no longer has what they act on: `FPClear` clears a scalar
// floating-point file the profile deletes (R-15-039), `LoadRes*`/`StoreCond*`
// need a reservation `Zalrsc` took with it (R-15-025), and `AMOSwapCap` names a
// capability-width atomic where `A` is narrowed to byte through doubleword
// (R-15-024). `ccleartag` joins them here: tag clearing is a property of the
// write path rather than an instruction (R-15-007r).
//
// The capability layer is ungated, as the format and algebra in `core` are: the
// machine is purecap-only, so an `Xcheri` extension gate would be a
// configuration key with one admitted value (R-15-001, R-15-005).

// One bit of Boolean in a register. `cgettag`, `cgetsealed` and `cseqx` all
// answer with a register, and a register is XLEN wide.
function bool_to_xlenbits(b : bool) -> xlenbits = if b then zero_extend(0b1) else zeros()

// The return capability a capability call writes: the next instruction's PCC,
// sealed as a **backward-edge** sentry, so it is usable as a control-flow target
// exactly once, at a jump that writes no link of its own, and nowhere else
// (R-15-008, R-15-068, R-15-071).
function link_capability() -> Capability = {
  let (representable, linkCap) = setCapAddr(PCC, get_next_pc());
  assert(representable, "Link capability should always be representable");
  assert(not(isCapSealed(linkCap)), "Link capability should always be unsealed");
  sealCap(linkCap, otype_sentry_bwd_bits)
}

// *****************************************************************
// Control transfers.
//
// These three take the base encodings of `auipc`, `jal` and `jalr`, which is
// what one mode means: there is no integer form of a control transfer to
// distinguish them from, so the base clauses are absent from
// `extensions/I/base_insts.sail` rather than shadowed here.

union clause instruction = AUIPCC : (bits(20), regidx)

mapping clause encdec = AUIPCC(imm, cd)
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

// See `mapping clause encdec = JAL` upstream for why the immediate is spelled out.
mapping clause encdec = CJAL(imm_19 @ imm_7_0 @ imm_8 @ imm_18_13 @ imm_12_9 @ 0b0, cd)
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

mapping clause encdec = CJALR(imm, cs1, cd)
  <-> imm @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1100111

function clause execute CJALR(imm, cs1, cd) = {
  let cs1_val = C(cs1);
  let idx = capreg_idx_of_regidx(cs1);
  let off : xlenbits = sign_extend(imm);
  // Bit zero is cleared as it is for `jalr` upstream.
  let newPC = [capAddrBits(cs1_val) + off with 0 = 0b0];

  // A sentry is unsealed by the jump itself, which is what makes domain entry a
  // hardware property with no separate call gate (R-15-068). **Which** sentry
  // is admitted is what the forward/backward split decides: a jump that writes
  // a link is a call and may enter only a forward-edge sentry, while a return
  // address is sealed as the backward edge and is reachable only by a jump that
  // writes no link, so a return capability may target only a return site and a
  // call may not enter one (R-15-071).
  let admitted_entry : bool =
    if cd != zreg then cs1_val.otype == otype_sentry_fwd_bits
    else isSentry(cs1_val);

  if not(cs1_val.tag) then
    Ext_ControlAddr_Check_Failure((CapEx_TagViolation, idx))
  // Any other sealed type, any sentry entered in the wrong role, and any
  // non-zero displacement onto a sentry, is a seal violation.
  else if isCapSealed(cs1_val) & (not(admitted_entry) | (imm != zeros())) then
    Ext_ControlAddr_Check_Failure((CapEx_SealViolation, idx))
  else if not(cap_permit_execute(cs1_val)) then
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
// Inspection: the fields of a capability, read into an integer register.

union clause instruction = CGetPerm   : (regidx, regidx)
union clause instruction = CGetType   : (regidx, regidx)
union clause instruction = CGetBase   : (regidx, regidx)
union clause instruction = CGetLen    : (regidx, regidx)
union clause instruction = CGetTag    : (regidx, regidx)
union clause instruction = CGetSealed : (regidx, regidx)
union clause instruction = CGetOffset : (regidx, regidx)
union clause instruction = CGetAddr   : (regidx, regidx)
union clause instruction = CGetTop    : (regidx, regidx)

// The permissions answer in the **expanded** bitmap rather than in the encoded
// field, which is what lets `candperm`'s mask be an ordinary bitwise operand
// over a non-orthogonal encoding (core/cap_common.sail, R-15-007b).
function clause execute CGetPerm(rd, cs1) = {
  X(rd) = zero_extend(getCapPerms(C(cs1)));
  RETIRE_SUCCESS
}

function clause execute CGetType(rd, cs1) = {
  let capVal = C(cs1);
  // A reserved object type is reported as the negative architectural value it
  // stands for, which is what makes an unsealed capability read as -1, a
  // forward-edge sentry -2, and a backward-edge sentry -3.
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
  X(rd) = capAddrBits(C(cs1));
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

// Length and top are at most 2^36, so both fit an XLEN-wide answer with no
// saturation: the address space is narrower than a register (R-15-002a).
function clause execute CGetLen(rd, cs1) = {
  X(rd) = to_bits_truncate(xlen, getCapLength(C(cs1)));
  RETIRE_SUCCESS
}

function clause execute CGetTop(rd, cs1) = {
  X(rd) = to_bits_truncate(xlen, getCapTop(C(cs1)));
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
mapping clause assembly = CGetTop(rd, cs1)    <-> "cgettop"    ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1)

mapping clause encdec = CGetPerm(rd, cs1)   <-> 0b1111111 @ 0b00000 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetType(rd, cs1)   <-> 0b1111111 @ 0b00001 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetBase(rd, cs1)   <-> 0b1111111 @ 0b00010 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetLen(rd, cs1)    <-> 0b1111111 @ 0b00011 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetTag(rd, cs1)    <-> 0b1111111 @ 0b00100 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetSealed(rd, cs1) <-> 0b1111111 @ 0b00101 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetOffset(rd, cs1) <-> 0b1111111 @ 0b00110 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetAddr(rd, cs1)   <-> 0b1111111 @ 0b01111 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CGetTop(rd, cs1)    <-> 0b1111111 @ 0b11000 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011

// *****************************************************************
// The monotone derivations. Every one of them **clears the tag** where the
// result would exceed its input rather than trapping, so a failed derivation is
// a data result that faults at its next dereference and carries no cause code
// and no control-flow term in a timing bound (R-15-007h).

union clause instruction = CMove      : (regidx, regidx)
union clause instruction = CSealEntry : (regidx, regidx)

function clause execute CMove(cd, cs1) = {
  C(cd) = C(cs1);
  RETIRE_SUCCESS
}

// `csealentry` mints the **forward** edge: a call target. The backward edge is
// minted only by the call itself, which is what keeps a return address out of
// software's gift (R-15-071).
function clause execute CSealEntry(cd, cs1) = {
  C(cd) = sealCap(clearTagIfSealed(C(cs1)), otype_sentry_fwd_bits);
  RETIRE_SUCCESS
}

mapping clause encdec = CMove(cd, cs1)      <-> 0b1111111 @ 0b01010 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSealEntry(cd, cs1) <-> 0b1111111 @ 0b10001 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011

mapping clause assembly = CMove(cd, cs1)      <-> "cmove"      ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1)
mapping clause assembly = CSealEntry(cd, cs1) <-> "csealentry" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1)

// *****************************************************************
// The conditional capability move, in both polarities (R-15-054a).
//
// This is the capability half of the branchless select, and it is a *merge*
// rather than a zero-then-OR because the recombining `or` has no capability
// form: an integer select can zero one arm and OR the two together, and doing
// that to a capability would be reconstruction from a bit pattern, which the
// profile forbids at the root (R-05-136, R-15-054). So the destination is
// written whole, tag included, on the taken arm and left untouched on the
// other, which is what a select over authority has to mean.
//
// Its latency is independent of the operand values *and* of which arm is taken,
// so it joins the `Zkt`/`Zvkt` list with one entry in the timing-annotated
// model; that is a hardware contract the architectural write cannot show, and
// it is carried as an annotation rather than by writing the destination twice
// (M0.9, R-15-053).
//
// The encoding is the dialect's own rather than custom opcode space, so it
// contends with nothing the freeze's measured act weighs (R-15-014a). The two
// `funct7` values are the first pair above ISAv9's highest three-operand
// allocation, which is where a bespoke row belongs: membership is by
// enumeration and never by inheritance, so a reader checking this against
// ISAv9 finds free space rather than a re-used opcode (R-15-007j).

// The two polarities are two clauses rather than one clause over a polarity
// enumeration, because the `instruction` union is scattered and declared before
// this file: a type of its own would have to live in a types file ahead of that
// declaration, which is a file and a group for one bit of information.
function conditional_cap_move(cd : regidx, cs1 : regidx, taken : bool) -> ExecutionResult = {
  if taken then C(cd) = C(cs1);
  RETIRE_SUCCESS
}

union clause instruction = CMOVZ : (regidx, regidx, regidx)
union clause instruction = CMOVN : (regidx, regidx, regidx)

mapping clause encdec = CMOVZ(cd, cs1, rs2)
  <-> 0b0100010 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CMOVN(cd, cs1, rs2)
  <-> 0b0100011 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011

function clause execute CMOVZ(cd, cs1, rs2) = conditional_cap_move(cd, cs1, X(rs2) == zeros())
function clause execute CMOVN(cd, cs1, rs2) = conditional_cap_move(cd, cs1, X(rs2) != zeros())

mapping clause assembly = CMOVZ(cd, cs1, rs2)
  <-> "cmovz" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CMOVN(cd, cs1, rs2)
  <-> "cmovn" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)

// *****************************************************************
// Three-operand derivations.

union clause instruction = CAndPerm  : (regidx, regidx, regidx)
union clause instruction = CIncOffset : (regidx, regidx, regidx)
union clause instruction = CSetOffset : (regidx, regidx, regidx)
union clause instruction = CSetAddr   : (regidx, regidx, regidx)
union clause instruction = CSetBounds : (regidx, regidx, regidx)
union clause instruction = CIncOffsetImmediate : (regidx, regidx, bits(12))
union clause instruction = CSetBoundsImmediate : (regidx, regidx, bits(12))

// The mask is over the expanded bitmap and the result is the largest admitted
// permission set inside the intersection, so `candperm` can only ever remove
// authority however the mask is chosen (R-15-007b).
function clause execute CAndPerm(cd, cs1, rs2) = {
  let cs1_val = C(cs1);
  let mask = truncate(X(rs2), cap_perms_width);
  C(cd) = setCapPerms(clearTagIfSealed(cs1_val), getCapPerms(cs1_val) & mask);
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

// The narrowing the two `csetbounds` forms share: base becomes the input's
// address and length the requested one. Every narrowing the profile's code
// emits is exactly representable by construction of the static memory plan, so
// the exactness the third upstream form reported has no consumer and no
// instruction here computes it (R-15-007k).
function narrow_bounds(cs1_val : Capability, length : CapAddrBits) -> (bool, Capability) = {
  let newBase = cs1_val.address;
  let newTop : CapLenBits = zero_extend(newBase) + zero_extend(length);
  let inBounds = inCapBounds(cs1_val, zero_extend(newBase), unsigned(length));
  let (_, newCap) = setCapBounds(clearTagIfSealed(cs1_val), newBase, newTop);
  (inBounds, newCap)
}

function clause execute CSetBounds(cd, cs1, rs2) = {
  let (inBounds, newCap) = narrow_bounds(C(cs1), truncate(X(rs2), cap_addr_width));
  C(cd) = clearTagIf(newCap, not(inBounds));
  RETIRE_SUCCESS
}

function clause execute CSetBoundsImmediate(cd, cs1, uimm) = {
  let (inBounds, newCap) = narrow_bounds(C(cs1), zero_extend(uimm));
  C(cd) = clearTagIf(newCap, not(inBounds));
  RETIRE_SUCCESS
}

mapping clause encdec = CSetBounds(cd, cs1, rs2)      <-> 0b0001000 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CAndPerm(cd, cs1, rs2)        <-> 0b0001101 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSetOffset(cd, cs1, rs2)      <-> 0b0001111 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSetAddr(cd, cs1, rs2)        <-> 0b0010000 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CIncOffset(cd, cs1, rs2)      <-> 0b0010001 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011

mapping clause encdec = CIncOffsetImmediate(cd, cs1, imm) <-> imm @ encdec_reg(cs1) @ 0b001 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSetBoundsImmediate(cd, cs1, imm) <-> imm @ encdec_reg(cs1) @ 0b010 @ encdec_reg(cd) @ 0b1011011

mapping clause assembly = CAndPerm(cd, cs1, rs2)   <-> "candperm"   ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CSetOffset(cd, cs1, rs2) <-> "csetoffset" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CSetAddr(cd, cs1, rs2)   <-> "csetaddr"   ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CIncOffset(cd, cs1, rs2) <-> "cincoffset" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CSetBounds(cd, cs1, rs2) <-> "csetbounds" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)

mapping clause assembly = CIncOffsetImmediate(cd, cs1, imm) <-> "cincoffsetimm" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ hex_bits_12(imm)
mapping clause assembly = CSetBoundsImmediate(cd, cs1, imm) <-> "csetboundsimm" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ hex_bits_12(imm)

// *****************************************************************
// Comparison and pointer arithmetic between two capabilities. The zero register
// reads as the null capability, which is what upstream's "`c0` means DDC" arm
// becomes on a machine with no default data capability (core/reg_type.sail).

union clause instruction = CToPtr   : (regidx, regidx, regidx)
union clause instruction = CFromPtr : (regidx, regidx, regidx)
union clause instruction = CSub     : (regidx, regidx, regidx)
union clause instruction = CSEQX    : (regidx, regidx, regidx)

function clause execute CToPtr(rd, cs1, cs2) = {
  let cs1_val = C(cs1);
  X(rd) = if   not(cs1_val.tag)
          then zeros()
          else capAddrBits(cs1_val) - getCapBaseBits(C(cs2));
  RETIRE_SUCCESS
}

function clause execute CFromPtr(cd, cs1, rs2) = {
  let rs2_val = X(rs2);
  if rs2_val == zeros() then {
    C(cd) = null_cap;
    RETIRE_SUCCESS
  } else {
    let (representable, newCap) = setCapOffset(clearTagIfSealed(C(cs1)), rs2_val);
    C(cd) = clearTagIf(newCap, not(representable));
    RETIRE_SUCCESS
  }
}

function clause execute CSub(rd, cs1, cs2) = {
  X(rd) = capAddrBits(C(cs1)) - capAddrBits(C(cs2));
  RETIRE_SUCCESS
}

function clause execute CSEQX(rd, cs1, cs2) = {
  X(rd) = bool_to_xlenbits(C(cs1) == C(cs2));
  RETIRE_SUCCESS
}

mapping clause encdec = CToPtr(rd, cs1, cs2)      <-> 0b0010010 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CFromPtr(cd, cs1, rs2)    <-> 0b0010011 @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CSub(rd, cs1, cs2)        <-> 0b0010100 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011
mapping clause encdec = CSEQX(rd, cs1, cs2)       <-> 0b0100001 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011

mapping clause assembly = CToPtr(rd, cs1, cs2)      <-> "ctoptr"      ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)
mapping clause assembly = CFromPtr(cd, cs1, rs2)    <-> "cfromptr"    ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)
mapping clause assembly = CSub(rd, cs1, cs2)        <-> "csub"        ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)
mapping clause assembly = CSEQX(rd, cs1, cs2)       <-> "cseqx"       ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)

// *****************************************************************
// Sealing.
//
// The two authorities are never the same lattice element: no admitted
// permission set holds both `Permit_Seal` and `Permit_Unseal`, so the authority
// to mint a delegation and the authority to redeem one are separated at the
// encoding rather than by an audit of the distribution (R-15-007o).

union clause instruction = CSeal   : (regidx, regidx, regidx)
union clause instruction = CUnseal : (regidx, regidx, regidx)

function clause execute CSeal(cd, cs1, cs2) = {
  let cs1_val = C(cs1);
  let cs2_val = C(cs2);
  let cs2_cursor = getCapCursor(cs2_val);
  let (cs2_base, cs2_top) = getCapBounds(cs2_val);

  let permitted = cs2_val.tag
                & not(isCapSealed(cs2_val))
                & cap_permit_seal(cs2_val)
                & (cs2_cursor >= cs2_base)
                & (cs2_cursor < cs2_top)
                & (cs2_cursor <= cap_max_otype);

  let newCap = sealCap(clearTagIfSealed(cs1_val), to_bits_truncate(cap_otype_width, cs2_cursor));
  C(cd) = clearTagIf(newCap, not(permitted));
  RETIRE_SUCCESS
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
                & cap_permit_unseal(cs2_val)
                & (cs2_cursor >= cs2_base)
                & (cs2_cursor < cs2_top);

  // Unsealing through a local authority yields a local capability: global is
  // the meet of the two rather than the sealed capability's own (R-15-074).
  let unsealed = unsealCap(cs1_val);
  let newCap = if cap_global(cs2_val) then unsealed
               else setCapPerms(unsealed, getCapPerms(unsealed) & ~(0b0000_0000_0001));
  C(cd) = clearTagIf(newCap, not(permitted));
  RETIRE_SUCCESS
}

mapping clause encdec = CSeal(cd, cs1, cs2)   <-> 0b0001011 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011
mapping clause encdec = CUnseal(cd, cs1, cs2) <-> 0b0001100 @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b000 @ encdec_reg(cd) @ 0b1011011

mapping clause assembly = CSeal(cd, cs1, cs2)   <-> "cseal"   ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)
mapping clause assembly = CUnseal(cd, cs1, cs2) <-> "cunseal" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ cap_reg_name(cs2)

// *****************************************************************
// The special capability registers. The bank and its numbering are in
// core/cap_regs.sail; what is here is the access rule and the two legalizations.
//
// Access is the capability, not a ring: everything but PCC needs the
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
    0b11100 => (true, false, true),  // MTCC
    0b11101 => (true, false, true),  // MTDC
    0b11111 => (true, false, true),  // MEPCC
    _       => (false, true, true),
  };
  let writing = cs1 != zreg;

  if not(exists) | (read_only & writing) then
    Illegal_Instruction()
  else if needASR & not(cap_access_system_regs(PCC)) then
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
      0b11100 => MTCC,
      0b11101 => MTDC,
      0b11111 => legalize_epcc(MEPCC),
      _       => { assert(false, "unreachable"); null_cap },
    };
    if writing then {
      match scr {
        0b11100 => MTCC = legalize_tcc(MTCC, cs1_val),
        0b11101 => MTDC = cs1_val,
        0b11111 => MEPCC = cs1_val,
        _       => assert(false, "unreachable"),
      };
      // A write to a special capability register is reported by the
      // capability-widened commit trace, which is where `wC` leaves the
      // register file's own writes too (M0.12, core/cap_regs.sail). The value
      // reported is the register's, not the operand's: MTCC's address is
      // legalized on the way in.
      match scr {
        0b11100 => scr_write_callback(scr, MTCC),
        0b11101 => scr_write_callback(scr, MTDC),
        0b11111 => scr_write_callback(scr, MEPCC),
        _       => (),
      }
    };
    RETIRE_SUCCESS
  }
}

mapping clause assembly = CSpecialRW(cd, scr, cs1)
  <-> "cspecialrw" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ scr_name_map(scr) ^ sep() ^ cap_reg_name(cs1)

// *****************************************************************
// Capability loads and stores.
//
// One mode leaves one form of each: the authority is the capability in the base
// register the instruction names, which is what the four explicit-authority
// forms beside them existed to override.

union clause instruction = LoadCapImm  : (regidx, regidx, bits(12))
union clause instruction = StoreCapImm : (regidx, regidx, bits(12))

function clause execute LoadCapImm(cd, cs1, imm) = {
  let (auth, addr, auth_idx) = cap_mode_auth(cs1, sign_extend(imm));
  cap_load(cd, auth, auth_idx, addr)
}

function clause execute StoreCapImm(cs2, cs1, imm) = {
  let (auth, addr, auth_idx) = cap_mode_auth(cs1, sign_extend(imm));
  cap_store(cs2, auth, auth_idx, addr)
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
mapping clause encdec = LoadCapImm(cd, cs1, imm)
  <-> imm @ encdec_reg(cs1) @ 0b010 @ encdec_reg(cd) @ 0b0001111
  when cd != zreg

mapping clause encdec = StoreCapImm(cs2, cs1, imm)
  <-> imm[11 .. 5] @ encdec_reg(cs2) @ encdec_reg(cs1) @ 0b100 @ imm[4 .. 0] @ 0b0100011

mapping clause assembly = LoadCapImm(cd, cs1, imm)
  <-> "lc" ^ spc() ^ cap_reg_name(cd) ^ sep() ^ hex_bits_signed_12(imm) ^ opt_spc() ^ "(" ^ opt_spc() ^ cap_reg_name(cs1) ^ opt_spc() ^ ")"
mapping clause assembly = StoreCapImm(cs2, cs1, imm)
  <-> "sc" ^ spc() ^ cap_reg_name(cs2) ^ sep() ^ hex_bits_signed_12(imm) ^ opt_spc() ^ "(" ^ opt_spc() ^ cap_reg_name(cs1) ^ opt_spc() ^ ")"

// *****************************************************************
union clause instruction = CLoadTags : (regidx, regidx)

// The tag-group load: the validity tags of a naturally aligned group of
// granules returned in an integer register without loading the granules. Two
// parameters upstream leaves implementation-defined are fixed by the profile:
// the group is the CBO block `cbo.zero` allocates rather than a cache line, and
// the tags are reported **as stored** rather than as the revocation filter would
// return them, that filter having no base to index by (R-15-007q, R-08-007).
// The group itself is `caps_per_block` in core/cap_format.sail, beside the
// granule it is a multiple of: four instructions read that one parameter, so it
// belongs to the machine rather than to the first of them to need it.

// The authority a tag-plane block operation owes, shared by the two of them.
// Both read the tag of every granule in the group, so both require exactly what
// a **tag-preserving capability load** over the group requires and neither
// requires more: `creclaim` writes no data and can only destroy authority, so
// its clear is not a store (R-15-007q, R-15-007s).
//
// Unlike a capability load, both *fault* where the authority lacks
// load-capability permission rather than answering with cleared tags: an answer
// of all-zeroes would be indistinguishable from an empty group, and the sweep
// that read it would silently miss every capability in it.
function cap_block_checks(auth : Capability, idx : capreg_idx, addr : xlenbits)
         -> option(ExecutionResult) = {
  let vaddr = Virtaddr(addr);
  let block = caps_per_block * cap_size;
  assert(plat_cache_block_size_exp == sizeof(log2_cap_block_size),
         "the tag group is the CBO block, so the two must be configured alike");

  if not(auth.tag) then
    Some(Ext_DataAddr_Check_Failure((CapEx_TagViolation, idx)))
  else if isCapSealed(auth) then
    Some(Ext_DataAddr_Check_Failure((CapEx_SealViolation, idx)))
  else if not(cap_permit_load(auth)) then
    Some(Ext_DataAddr_Check_Failure((CapEx_PermitLoadViolation, idx)))
  else if not(cap_load_cap(auth)) then
    Some(Ext_DataAddr_Check_Failure((CapEx_PermitLoadCapViolation, idx)))
  else if not(inCapBounds(auth, addr, block)) then
    Some(Ext_DataAddr_Check_Failure((CapEx_LengthViolation, idx)))
  else if not(is_aligned_addr(vaddr, block)) then
    Some(memory_exception(vaddr, E_Load_Addr_Align()))
  else
    None()
}

function clause execute CLoadTags(rd, cs1) = {
  let cs1_val = C(cs1);
  let idx = capreg_idx_of_regidx(cs1);
  let addr = capAddrBits(cs1_val);
  let vaddr = Virtaddr(addr);

  match cap_block_checks(cs1_val, idx, addr) {
    Some(failure) => failure,
    None()        => {
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
    },
  }
}

mapping clause encdec = CLoadTags(rd, cs1)
  <-> 0b1111111 @ 0b10010 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011

mapping clause assembly = CLoadTags(rd, cs1)
  <-> "cloadtags" ^ spc() ^ reg_name(rd) ^ sep() ^ "(" ^ opt_spc() ^ cap_reg_name(cs1) ^ opt_spc() ^ ")"

// *****************************************************************
union clause instruction = CReclaim : (regidx, regidx)

// The block revocation reclaim: the §8 sweep's inner loop as one instruction
// (R-15-007s, R-08-007b).
//
// Over one granule group it applies the per-granule conditional clear the sweep
// exists to apply — each stored capability whose **base** falls under a set
// revocation bit has its validity tag cleared in place — and returns the
// group's tags as they stand after the pass. A granule whose bit is clear is
// untouched bit for bit, and no data is written by either case.
//
// **It is the conditional form, which is why R-15-007r is undisturbed.** That
// entry excludes a *bulk* tag clear: an instruction clearing a group's tags
// while leaving its data standing is a way to destroy authority wholesale with
// no predicate deciding it. This one has the predicate, and the predicate is
// the same one the load already applies (R-08-005b, core/revocation.sail), so
// what it can do to a granule is exactly what the next capability load of that
// granule would have done to the value it delivered.
//
// **What it buys is the pass time and not a security bound.** Containment is
// the epoch flip (R-08-006); the sweep's pass time is the quarantine interval
// (R-08-007a), so one instruction per group in place of a capability load per
// tagged granule shortens the pass by roughly the group width and the
// quarantine pool and the §11 background slot budget shrink with it. Its
// latency is independent of the tags found, the bits set, and the clears
// performed, every granule taking its cycle, so no implementation ends early on
// a group it finds empty and the sweep is one entry per group in the
// timing-annotated model (M0.9, R-15-053).
//
// The walk stays software: the instruction ends at its group boundary and the
// next group is the sweep task's next instruction, so nothing autonomous is
// added and R-08-009's refusal of a hardware sweep engine is undisturbed.
//
// The clear reaches memory through the ordinary store path, so a granule in a
// region the PMA refuses writes cannot be cleared. That is not the capability
// check arriving twice under two names: the authority this instruction requires
// is a *load's*, because it mints nothing and can only destroy, while the PMA is
// a fact about the medium, and an array that cannot be written cannot have a tag
// cleared in it whoever asks.
//
// The encoding is the dialect's own beside `cloadtags`, at the first sub-opcode
// of this two-operand group that ISAv9 never allocated, so it contends for no
// custom opcode space and a reader checking it against ISAv9 finds free space
// rather than a re-used opcode (R-15-007j, R-15-014a).
function clause execute CReclaim(rd, cs1) = {
  let cs1_val = C(cs1);
  let idx = capreg_idx_of_regidx(cs1);
  let addr = capAddrBits(cs1_val);
  let vaddr = Virtaddr(addr);

  match cap_block_checks(cs1_val, idx, addr) {
    Some(failure) => failure,
    None()        => {
      let base = physical_address(vaddr);
      var tags : bits(caps_per_block) = zeros();
      var failure : option(ExceptionType) = None();

      foreach (i from 0 to (caps_per_block - 1)) {
        match failure {
          Some(_) => (),
          None()  => {
            let granule = Physaddr(bits_of(base) + (i * cap_size));
            // The granule is read as **bits and a tag** rather than as a
            // decoded capability, and written back as the bits it was. The
            // decode below is used for the one field the predicate needs and
            // its result reaches no register and no memory, which is the whole
            // of *without materializing the value*: the surviving granules are
            // bit-for-bit untouched, and a cleared one differs from what was
            // there in its tag alone.
            match mem_read_meta(Load(Data), granule, cap_size, false, false, true) {
              Err(_, e) => failure = Some(e),
              Ok(v, tag) => {
                let revoked = tag & revocation_revoked(
                  zero_extend(getCapBaseBits(memBitsToCapability(tag, v))));
                if revoked then {
                  match mem_write_value_meta(granule, cap_size, v, Store(Data), false, false, false) {
                    Err(_, e) => failure = Some(e),
                    Ok(true)  => (),
                    Ok(false) => internal_error(__FILE__, __LINE__, "creclaim got false from mem_write_value_meta"),
                  }
                };
                tags = [tags with i = bool_to_bit(tag & not(revoked))]
              },
            }
          },
        }
      };

      match failure {
        Some(e) => memory_exception(vaddr, e),
        None()  => { X(rd) = zero_extend(tags); RETIRE_SUCCESS },
      }
    },
  }
}

mapping clause encdec = CReclaim(rd, cs1)
  <-> 0b1111111 @ 0b10011 @ encdec_reg(cs1) @ 0b000 @ encdec_reg(rd) @ 0b1011011

mapping clause assembly = CReclaim(rd, cs1)
  <-> "creclaim" ^ spc() ^ reg_name(rd) ^ sep() ^ "(" ^ opt_spc() ^ cap_reg_name(cs1) ^ opt_spc() ^ ")"
