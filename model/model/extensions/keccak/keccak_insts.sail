// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// `vkeccak.vi`, the frozen Keccak unit as one vector instruction (R-15-056,
// R-15-057, R-15-057a, R-15-059, R-15-059a).
//
// The permutation itself is [keccak_p1600.sail](keccak_p1600.sail); what is
// here is the element group it reads and writes, the class it is placed on, the
// round-count immediate, and the encoding the re-pin exchanges. That division
// is what R-15-057a's re-pin is over: the semantics do not move at ratification
// and the encoding does.
//
// **It is bespoke surface and lives apart from the vendored vector crypto for
// that reason.** `extensions/vector_crypto/` carries the ratified `Zvkned`,
// `Zvknh[ab]`, `Zvkg`, `Zvbb` and `Zvbc` this profile adopts (R-15-055), each
// with an upstream clause standing behind it. This has none: RVG-84 has not
// ratified, so the fork is authored here and diffed against the draft at each
// PQC Task Group milestone, exactly as `extensions/platform/` holds the three
// instructions belonging to no standard extension.
//
// **The element group is 2048 bits of 32 SEW=64 elements, and the state is the
// low 25 of them** (R-15-057a). Element *i* is lane *i* of the FIPS 202 state
// under the standard's own lane order, so the 200 bytes a sponge implementation
// already holds load straight in with a unit-stride vector load and no shuffle.
// The seven elements above the state are **written zero rather than preserved**,
// which is a decision this fork records rather than one R-15-057a fixes: the
// group is 448 bits wider than the permutation, and preserving them would carry
// whatever the destination held across a crypto instruction, where zeroing makes
// the destination group a total function of the source state. It lands where
// R-15-182 and R-15-060 already put an all-zeroes granule, and it is the first
// of the two re-pin deltas booked at the foot of this file.
//
// **The gate is the class and the context, and both are needed for opposite
// reasons.** R-15-059 places the unit on the vector-bearing cores and not on the
// vectorless S-class sentinel or the RoT, which is a *static* property of the
// hart: `keccak_unit_present` below reads it out of the class table
// (core/core_class.sail) rather than out of a second declaration, so there is
// nothing for the two to disagree about. `currentlyEnabled(Ext_Zve64x)` is
// beside it and folds in `mstatus.VS`, which `vmclear` deliberately does not do
// (extensions/platform/vmclear.sail): that instruction is the *switcher's* and
// must not be trappable by the partition it exists to erase, where this one is
// the **partition's own** and reads and writes the architectural vector register
// file exactly as `vsha2ms.vv` does. Gating this one on the class alone would
// let a partition that has turned its own vector unit off write the vector
// register file, which is the extension-context gate deleted rather than
// honoured (R-07-012, R-15-049).
//
// **What decides the geometry is the check and not the mandate.** R-15-057a
// records the re-pin target as depending on `Zve64x` and mandating `Zvl128b`.
// The dependency is held above; the mandate is not written as a conjunct,
// because it could never fire: an element group of 2048 bits needs
// LMUL × VLEN >= 2048 and LMUL tops out at 8, so the effective floor is
// VLEN = 256 and `zvk_check_encdec(2048, 32)` below is strictly stronger than
// `Zvl128b` at every geometry. A conjunct no configuration can fail is a dead
// arm, and the disagreement between the two figures is booked as the second
// re-pin delta rather than resolved here. VLEN = 256 is also the C class's own
// geometry, which is what R-15-059a states its figures at (R-15-113).
//
// **The encoding is custom-0 `funct3` 010, and the six custom-opcode rows
// still spend one opcode between them.** It sits beside `cclear`'s 000,
// `vmclear`'s 001, the two FEC decoders sharing 100 and the indexed access's
// width-coded 011 and 111 (extensions/CHERI/cheri_custom.sail,
// extensions/platform/vmclear.sail, extensions/fec/fec_insts.sail), so
// custom-1 and custom-3 stay whole for the rows the freeze's single measured act
// admits (R-15-014a, R-15-067e). A fork takes custom space rather than an
// unallocated point in the standard OP-V opcode deliberately: the vector major
// opcode is space the standard allocates, and moving into it is the **re-pin**
// rather than something a fork may do first, so a reader checking this encoding
// against the RISC-V opcode map finds an instruction in the space reserved for
// exactly this and a stock disassembler prints nothing rather than the wrong
// thing (the ground M0.6h took for `cbo.scrub`). `funct7` is reserved and zero,
// so a non-zero field decodes to nothing and traps (R-15-014).
//
// **No row enters the extension registry and none should.** `hartSupports` is
// what the generated `riscv,isa` string and `riscv,isa-extensions` array are
// built from (postlude/device_tree.sail), and an `Ext_Zvknhk` row would have an
// **attested** devicetree name a standards-track extension this machine does not
// implement, RVG-84 not having ratified. What the tree already says about the
// unit is `verifiedos,keccak-unit` on the class node, which M0.8a put there and
// which is a vendor property saying exactly what is true (R-09-007, R-15-007j).

// The class half of the gate. It is a static property of the hart read out of
// the composed roster: R-15-052b makes the reachable identity space a
// composition-time constant and `check_core_roster` refuses a composition whose
// roster omits the hart, so the `None()` arm is unreachable in any composition
// the validator admits and is written as `false` rather than as an error for the
// reason every other total decode path is (R-15-014).
function keccak_unit_present() -> bool =
  match this_core_class() {
    Some(c) => core_class_datapath(c).keccak_unit,
    None()  => false,
  }

// The round-count immediate. R-15-057a selects the round count by immediate with
// unassigned values illegal, and this fork spells the two admitted values as the
// round counts themselves rather than as an index into them, so `vkeccak.vi vd,
// vs2, 24` reads as what it does and a reader checks it against FIPS 202 without
// a second table. Every other value of the five-bit field reaches no decode
// clause and therefore traps exactly as any unallocated encoding does
// (R-15-014); nothing below is written to reject one.
function keccak_valid_rounds(rnd : bits(5)) -> bool =
  rnd == 0b01100 | rnd == 0b11000

val keccak_rounds : bits(5) -> {'r, 'r in {12, 24}. int('r)}
function keccak_rounds(rnd) = if rnd == 0b01100 then 12 else 24

union clause instruction = VKECCAK_VI : (bits(5), vregidx, vregidx)

// EGW 2048 and EGS 32 are written as the literals R-15-057a states rather than
// bound to a name: `zvk_check_encdec` takes them at the type level, so a name
// would have to carry the bound the check needs and would hide the two figures
// a reader is here to check against the register.
// `valid_vtype()` is in the guard and is **not** inherited from the vendored
// vector crypto beside it, none of whose rows carry it. This instruction reads
// its element width out of `vtype`, so it depends on `vtype`, and the rule the
// model already spells out is that a vector instruction depending on `vtype`
// with `vill` set is illegal (`valid_vtype` in
// extensions/V/vext_utils_insts.sail). What makes it load-bearing here rather
// than pedantic is what sets `vill`: it is the state `vmclear` leaves behind,
// *no configuration* being spelled as `vill` precisely so that a successor
// partition cannot inherit a usable one it never selected
// (extensions/platform/vmclear.sail, R-15-069d). An instruction ignoring it
// would run at a SEW the partition never chose, on the first instruction after
// a switch.
mapping clause encdec = VKECCAK_VI(rnd, vs2, vd)
  <-> 0b0000000 @ rnd @ encdec_vreg(vs2) @ 0b010 @ encdec_vreg(vd) @ 0b0001011
  when keccak_unit_present() & currentlyEnabled(Ext_Zve64x) & keccak_valid_rounds(rnd)
       & valid_vtype() & get_sew() == 64 & zvk_check_encdec(2048, 32)

mapping clause assembly = VKECCAK_VI(rnd, vs2, vd)
  <-> "vkeccak.vi" ^ spc() ^ vreg_name(vd) ^ sep() ^ vreg_name(vs2) ^ sep() ^ dec_bits_5(rnd)

// The destination and the source are separate register groups and full overlap
// is the expected idiom rather than a case: a sponge permutes in place, so
// `vkeccak.vi v0, v0, 24` is what software writes, and the whole group is read
// into `state` before any element of it is written. Partial overlap is not a
// case either, at any geometry this instruction decodes at: an element group of
// 2048 bits is one register group, `valid_reg_group` requires both operands to
// be aligned to it, and two aligned groups of one size are equal or disjoint.
//
// The masked-off and tail elements are neither read nor written. This is an
// element-group instruction, so `vl` counts elements and the group count is
// `vl / 32`; elements above `vl` are the tail and are left alone, which is what
// every other element-group instruction in this model does
// (extensions/vector_crypto/zvknhab_insts.sail) and what keeps the instruction
// unmasked and its latency a function of the group count alone (R-15-053).
function clause execute VKECCAK_VI(rnd, vs2, vd) = {
  let SEW      = get_sew();
  let LMUL_pow = get_lmul_pow();

  if not(valid_reg_group(vs2, LMUL_pow)) | not(valid_reg_group(vd, LMUL_pow))
  then return Illegal_Instruction();

  assert(SEW == 64);

  let eg_len = unsigned(vl) / 32;

  foreach (i from 0 to (eg_len - 1)) {
    var state : keccak_state = vector_init(zeros());
    foreach (j from 0 to 24) {
      state[j] = read_single_element(SEW, i * 32 + j, vs2)
    };

    let permuted = keccak_p1600(state, keccak_rounds(rnd));

    foreach (j from 0 to 24) {
      write_single_element(SEW, i * 32 + j, vd, permuted[j])
    };
    // The 448 bits the element group carries above the 1600-bit state, written
    // zero so the destination group is a total function of the source state.
    foreach (j from 25 to 31) {
      write_single_element(SEW, i * 32 + j, vd, zeros())
    }
  };

  RETIRE_SUCCESS
}

// **Two re-pin deltas are booked here rather than discovered at ratification**
// (R-15-057, R-15-057a). The frozen fork's semantics are diffed against RVG-84's
// shape at each PQC Task Group milestone, and these are the two places this fork
// states something the register's record of that shape does not:
//
//   1. **The disposition of the 448 bits above the state.** EGW is 2048 and the
//      permutation is 1600, and R-15-057a does not say what the remaining seven
//      SEW=64 elements of the destination group hold. This fork writes them
//      zero. A ratified instruction that preserves them instead is an encoding
//      *and* a semantic difference and would be caught by the harness's
//      element-group property rather than by a reading of the draft.
//   2. **The vector-length mandate.** R-15-057a records `Zvl128b`, and an
//      element group of 2048 bits is unreachable below VLEN = 256 because LMUL
//      tops out at 8. Either the draft's mandate is `Zvl256b` and the register's
//      record of it is short, or the draft admits a geometry at which its own
//      instruction cannot decode. The model is correct either way, the geometry
//      check being the operative condition; what is owed is a reading of the
//      draft, and it is a register question rather than a model one.
