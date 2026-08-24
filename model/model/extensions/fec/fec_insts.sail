// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// `ldpcdec` and `polardec`, the FEC decoders' instruction surface (R-15-119,
// R-15-119a, R-15-119b, R-15-119c).
//
// The codes the two are written over are [fec_codes.sail](fec_codes.sail); what
// is here is the operand form, the encoding, the authority the pass is checked
// against, and the pass itself. That division is the one R-15-119a forces: the
// code parameters are TS 38.212's and arrive from a composition, the surface is
// this profile's and is frozen once, and the second must be invariant over the
// first or the single freeze R-15-014 takes becomes one profile per builder.
//
// **It is bespoke surface and lives apart from the vendored extensions for the
// reason the Keccak fork does.** There is no standards-track channel-decoding
// instruction to re-pin to and none proposed, so the row's re-pin cell is `n/a`
// rather than a target (isa-profile.md §3), and the surface is authored here on
// the ground `extensions/platform/` and `extensions/keccak/` already sit on.
//
// **The operand form is two authorities and one descriptor, and the shape is
// forced by what a decoder is.** An R-type names three registers. A block decode
// needs the buffer it consumes, the buffer it produces, and a description of the
// block, and those are exactly three:
//
//   - `cs1` authorises the **soft-symbol buffer**, `nsoft` bytes of signed 8-bit
//     log-likelihood ratio, one per received coded bit, and is checked for load.
//   - `cd` authorises the **hard-bit buffer**, `ceil(nhard / 8)` bytes, and is
//     checked for store. It sits in the `rd` field and is read as a *source*,
//     which is what a three-register store has to do in this layout and is
//     exactly what `csd` and RVV's own stores do (extensions/CHERI/cheri_custom).
//   - `rs2` is the **block descriptor** packed into one register, which is the
//     shape `rcstep` already takes for the same reason: one register field, one
//     description, and no second instruction to carry the rest of it.
//
// Two buffers rather than one in place, and the reason is a lifetime rather than
// a convenience: a receiver's soft-symbol buffer and its decoded transport block
// are different objects held by different code for different spans, and an
// in-place form would force one authority over both and make a decoder's write
// reach every byte its read did.
//
// **There is no verdict register, and declining one is a decision rather than an
// oversight.** A decoder can report whether its own parity check closed; this one
// does not, on two grounds that point the same way. The transport block carries a
// CRC and software computes it, so a decoder-side syndrome flag is a redundant
// mechanism whose failure domain the CRC's own strictly contains, which is where
// *verify rather than hedge* declines a hedge (R-15-013). And such a flag is a
// function of the message schedule and the iteration bound the decoder ran, which
// R-15-119a puts on the microarchitectural side of the parameter split, so an
// architectural result computed from it would be a frozen-parameter value
// promoted to an instruction's output. What the surface returns is the block.
//
// **The descriptor's field layout** is fixed here and is invariant over every
// parameter either set supplies:
//
//   [15 .. 0]   `nsoft`  soft symbols consumed, one byte each
//   [31 .. 16]  `nhard`  hard bits produced
//   [47 .. 32]  `code`   the composition's own index into its declared code set
//   [63 .. 48]  reserved, and a non-zero value is an illegal instruction
//
// The index is the one thing the instruction says about a code, which is what
// keeps the encoding invariant: a base graph, a lifting size, a reliability
// sequence and a rate-matching schedule never reach an instruction field, and a
// builder who declares a different set of codes writes the same words.
//
// **The gate is the roster's `fec_units` and nothing else, and that is a third
// answer to the question `vmclear` and `vkeccak.vi` answer differently.** What
// decides which predicate an instruction takes is whose instruction it is *and*
// what state it touches. `vmclear` is the switcher's and must not be trappable by
// the partition it erases, so it gates on the static property alone;
// `vkeccak.vi` is the partition's own and reads and writes the architectural
// vector register file, so it folds in `mstatus.VS`. This one is the PHY server's
// own, so the first half of `vkeccak.vi`'s argument applies to it; and it touches
// **no extension context at all**, writing no vector register, no vector CSR and
// no unit state, its whole effect being memory reached through two explicit
// capability operands (R-15-118's coprocessor line, R-08-003). There is no
// context bit for a context gate to read, so the static half is the whole gate.
// It is the roster's rather than the class's because the decoders follow the
// statically pinned radio cores (R-12-038, R-15-114) and not the class table.
//
// **The encoding is custom-0 `funct3` 100 with the family in `funct7`, and the
// six rows in that opcode still spend one opcode between them.** `cclear` is 000,
// `vmclear` 001, `vkeccak.vi` 010 and the indexed access's width-coded pair 011
// and 111, so 100 is the first free point and the two decoders take it together
// rather than one each: the FEC unit is one attachment carrying two code
// families, so the family belongs in a sub-opcode field and not in a second
// `funct3`, which leaves 101 and 110 unspent where a row apiece would have left
// one. Custom-1 and custom-3 stay whole for the rows the freeze's single measured
// act admits (R-15-014a, R-15-067e), and spending either here would have been an
// opcode taken by a row that did not need it. `funct7` above the two allocated
// values reaches no clause and traps like every other unallocated encoding
// (R-15-014).
//
// **No row enters the extension registry**, for the reason the Keccak fork adds
// none: `hartSupports` builds the generated `riscv,isa` string and the
// `riscv,isa-extensions` array (postlude/device_tree.sail), and there is no
// standards-track extension name for this surface to claim. What the attested
// tree says about the unit is the roster's own `fec_units` flag and the class
// node's declared geometry, which say exactly what is true (R-09-007).
//
// **Where this model stops is correction, and it stops there for the reason
// `cbo.scrub` stops at the syndrome.** What the pass below computes is the hard
// decision, the sign of each log-likelihood ratio, which is what every declared
// decoder geometry agrees on before a single message passes. Belief propagation
// above it corrects a channel, and this model has none: memory returns the bits
// some program wrote, no codeword carries an error, and an iteration would have
// nothing to correct (the same absence extensions/platform/cbo_scrub.sail states
// for a correctable codeword). The iteration bound is declared beside the rest of
// the geometry and is zero in every configuration this tree ships, R-15-108's
// exploration not having selected one, so for every composition here the two
// coincide exactly rather than approximately.

// The class half of the composition's declaration, read where the composition
// declares it. `None()` is unreachable in any composition the validator admits,
// `check_core_roster` refusing one whose roster omits this hart, and is written
// as a zero-sized datapath rather than as an error for the reason every other
// total decode path is (R-15-014).
function fec_sized_block() -> int =
  match this_core_class() {
    Some(c) => core_class_datapath(c).fec_max_block,
    None()  => 0,
  }

// The hard decision of one soft symbol. A log-likelihood ratio is signed with
// positive meaning *zero is the likelier bit*, so the decision is the sign bit
// and nothing else, and the arithmetic is the same at every declared geometry.
function fec_hard_decision(llr : bits(8)) -> bits(1) = llr[7 .. 7]

mapping encdec_fec_family : FecFamily <-> bits(7) = {
  FecFamily_Ldpc  <-> 0b0000000,
  FecFamily_Polar <-> 0b0000001,
}

mapping fec_mnemonic : FecFamily <-> string = {
  FecFamily_Ldpc  <-> "ldpcdec",
  FecFamily_Polar <-> "polardec",
}

union clause instruction = FecDecode : (FecFamily, regidx, regidx, regidx)

mapping clause encdec = FecDecode(family, rs2, cs1, cd)
  <-> encdec_fec_family(family) @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b100 @ encdec_reg(cd) @ 0b0001011
  when this_core_has_fec_units()

mapping clause assembly = FecDecode(family, rs2, cs1, cd)
  <-> fec_mnemonic(family) ^ spc() ^ cap_reg_name(cd) ^ sep() ^ cap_reg_name(cs1) ^ sep() ^ reg_name(rs2)

// The pass, in one ascending traversal of the block.
//
// **The authority is checked once per byte and the check is the ordinary one.**
// A code block runs to tens of kilobytes, which is past the memory interface's
// widest access, so the pass is a walk rather than one wide access, exactly as
// `cloadtags` and `cbo.scrub` walk a block. Each step goes through `data_read` or
// `data_write`, which compose `ext_data_get_addr` over `cap_data_checks`
// (core/addr_checks.sail): there is no second copy of the check here, which is
// what R-08-003 asks for on this surface as it asks for it on the vector one.
//
// **A fault stops the pass where it happened**, leaving the bytes already written
// written, which is `cbo.scrub`'s disposition and for the same reason: the
// instruction is one architectural event over a range and not a transaction, and
// a rollback would be state this machine does not have.
//
// The output is packed **least-significant bit first**, hard bit *i* of soft
// symbol *8b + i* landing in bit *i* of output byte *b*. A final partial byte has
// its bits above `nhard` written **zero rather than preserved**, so the
// destination buffer is a total function of the source block, which is where the
// Keccak fork puts the 448 bits above its state for the same reason.
function clause execute FecDecode(family, rs2, cs1, cd) = {
  let desc = X(rs2);

  if desc[63 .. 48] != zeros() then return Illegal_Instruction();

  let nsoft = unsigned(desc[15 .. 0]);
  let nhard = unsigned(desc[31 .. 16]);
  let index = unsigned(desc[47 .. 32]);

  // The code the composition declares at that index, and the family the
  // instruction names. A machine whose composition declares no code has no index
  // that names one, which is every composition in this tree.
  let code : FecCode = match fec_code_at(fec_codes, index) {
    None()  => return Illegal_Instruction(),
    Some(c) => c,
  };
  if code.family != family then return Illegal_Instruction();

  // The geometry the datapath is sized for. A block longer than the unit was
  // built to lift is not a longer decode but a decode this machine cannot
  // perform, so it is refused rather than truncated or split (R-15-119).
  //
  // **A zero reads as *not selected* and not as a zero-length datapath**, which
  // is the reading the class table already states for every field beside
  // `frozen` (core/core_class.sail, R-15-108): a class whose exploration has not
  // run has selected no maximum, so it imposes none, and the refusal appears the
  // day a composition selects one rather than being a refusal of every block on
  // a machine nobody has sized yet.
  if nsoft == 0 then return Illegal_Instruction();
  if fec_sized_block() > 0 & nsoft > fec_sized_block() then return Illegal_Instruction();
  if nhard == 0 | nhard > nsoft then return Illegal_Instruction();

  var failure : option(ExecutionResult) = None();
  var acc : bits(8) = zeros();

  foreach (j from 0 to (nsoft - 1)) {
    match failure {
      Some(_) => (),
      None()  =>
        match data_read(cs1, to_bits_truncate(64, j), 1, Load(Data), false, false) {
          Err(e)  => failure = Some(e),
          Ok(llr) => {
            if j < nhard then {
              let bit : bits(8) = zero_extend(fec_hard_decision(llr));
              acc = acc | (bit << (j % 8));
              if (j % 8) == 7 | j == nhard - 1 then {
                match data_write(cd, to_bits_truncate(64, j / 8), 1, acc, Store(Data), false, false) {
                  Err(e) => failure = Some(e),
                  Ok(_)  => (),
                };
                acc = zeros()
              }
            }
          },
        },
    }
  };

  match failure {
    Some(e) => e,
    None()  => RETIRE_SUCCESS,
  }
}
