// The FEC decoders' instruction surface: the two authorities a decode pass is
// checked against, the descriptor the surface refuses, the packing it writes,
// and the invariance of the encoding over the codes a composition declares
// (R-08-003, R-15-119, R-15-119a, R-15-119b, extensions/fec/fec_insts.sail).
//
// **No configuration in this tree declares a code or an FEC geometry**, so the
// first property below is that fact and the rest install what they need and
// restore what they found. That is the shape the scratchpad properties already
// take and it is forced twice over here: the channel-code parameters are TS
// 38.212's and a tracked configuration carrying one would be the reproduction the
// table-free arm declines (R-15-119a), and the decoder geometry beside them is
// one of R-15-108's frozen parameters whose exploration has not run.
//
// **What is asserted is the pass and never a corrected block.** The clause under
// test computes the hard decision, the sign of each log-likelihood ratio, which
// is where this model stops for want of a channel: memory returns the bits some
// program wrote, no codeword carries an error, and belief propagation above the
// hard decision would have nothing to correct. That is the same absence
// `cbo.scrub` states for a correctable codeword, and a property asserting a
// corrected word here would be a property about a harness rather than about this
// machine (extensions/platform/cbo_scrub.sail, R-15-177a).

// One declared code of each family, installed by the properties that need one.
// Every field is a *selector*, a small ordinal naming which of the standard's
// tables a code uses, and no field is a value TS 38.212 fixes: these are 1 and 2
// because a property needs two distinguishable codes and for no other reason.
let test_fec_ldpc_code : FecCode = struct {
  family               = FecFamily_Ldpc,
  base_graph           = 1,
  lifting_size         = 2,
  reliability_sequence = 0,
  rate_matching        = 0,
}

let test_fec_polar_code : FecCode = struct {
  family               = FecFamily_Polar,
  base_graph           = 0,
  lifting_size         = 0,
  reliability_sequence = 1,
  rate_matching        = 2,
}

// The descriptor `rs2` carries, assembled from its four fields so that a reader
// checks the layout here rather than counting bits in a literal
// (extensions/fec/fec_insts.sail).
function test_fec_descriptor(nsoft : bits(16), nhard : bits(16), code : bits(16)) -> bits(64) =
  0x0000 @ code @ nhard @ nsoft

// A roster entry written here rather than composed, for the count property below.
function test_fec_roster_entry(h : core_hartid, units : bool) -> CoreRosterEntry = struct {
  hartid    = h,
  class     = CoreClass_V,
  island    = 2,
  pinned    = true,
  fec_units = units,
}

// The composed hart's roster entry with the decoders attached, and its removal.
// `core_roster` is a register and this is why: the gate is a static property of
// the composition and there is no other way to exercise a surface no shipped
// composition carries. The entry is prepended, so the lookup finds it and the
// original stays beneath it; the removal drops that head rather than assigning a
// value saved beforehand, so what a property restores is read from the register
// it is restoring and not from a binding taken before the change.
function test_fec_attach_units() -> unit =
  match this_core_entry() {
    None()      => (),
    Some(entry) =>
      core_roster = struct {
        hartid    = entry.hartid,
        class     = entry.class,
        island    = entry.island,
        pinned    = true,
        fec_units = true,
      } :: core_roster,
  }

function test_fec_detach_units() -> unit =
  match core_roster {
    [||]      => (),
    _ :: rest => core_roster = rest,
  }

// The two buffers every property below uses, in first-class RAM: sixteen soft
// symbols at the base of one authority and two hard bytes under a second. They
// are separate authorities because the surface names two, which is the whole of
// what makes a decoder's write unable to reach the block its read covered.
let test_fec_soft_base : bits(64) = 0x0000000080000000
let test_fec_hard_base : bits(64) = 0x0000000080000100

// The soft block: sixteen signed log-likelihood ratios whose signs are the
// answer. Symbols 0 through 7 alternate positive and negative, so the first hard
// byte is 0xAA under least-significant-bit-first packing; symbols 8 through 14
// are positive and 15 is negative, so the second is 0x80.
function test_fec_write_soft_block() -> unit = {
  match mem_write_value(Physaddr(test_fec_soft_base), 8, 0x8140C000FF01807F, Store(Data), false, false) {
    Ok(_)     => (),
    Err(_, _) => assert(false, "writing the soft block must succeed"),
  };
  match mem_write_value(Physaddr(test_fec_soft_base + 0x0000000000000008), 8, 0xFF00000000000000, Store(Data), false, false) {
    Ok(_)     => (),
    Err(_, _) => assert(false, "writing the soft block must succeed"),
  }
}

function test_fec_hard_bytes() -> bits(16) =
  match mem_read_meta(Load(Data), Physaddr(test_fec_hard_base), 2, false, false, false) {
    Ok((value, _)) => value,
    Err(_, _)      => { assert(false, "reading the hard block must succeed"); zeros() },
  }

// *****************************************************************
// The shipped state, stated rather than assumed.

// Both halves matter and they are the two sides of R-15-119a's parameter split.
// No composition here declares a channel code, which is the table-free arm made
// a fact about the tree rather than a claim about it; and no class row declares
// an FEC geometry, which is R-15-108's exploration not having run, exactly as it
// has not run for the scratchpad size or the issue width beside it.
$[test]
function test_no_configuration_here_declares_a_code_or_an_fec_geometry() -> unit = {
  assert(fec_code_count(fec_codes) == 0);

  foreach (i from 0 to 4) {
    let c = core_class_of_index(i);
    let d = core_class_datapath(c);
    assert(not(core_class_has_fec(c)));
    assert(d.fec_parallelism == 0 & d.fec_max_block == 0);
    assert(d.fec_iterations == 0 & d.fec_polar_list == 0);
  };

  // And the composed hart carries no decoder, so the surface does not decode on
  // it at all. The gate is the roster's and not the class's, the decoders
  // following the statically pinned radio cores (R-12-038, R-15-114).
  assert(not(this_core_has_fec_units()));
}

// *****************************************************************
// The pass writes the hard decision, packed least-significant bit first.

// What the clause computes is one ascending traversal of the block: every soft
// symbol read under `cs1`, the first `nhard` of their signs packed into bytes,
// and each byte written under `cd`. The two capabilities are separate, so the
// assertion that the hard bytes changed and the soft block did not is an
// assertion about the surface's shape and not only about its arithmetic.
$[test]
function test_the_fec_pass_writes_the_hard_decision() -> unit = {
  assert(fec_code_count(fec_codes) == 0, "the shipped composition declares no code");
  fec_codes = [|test_fec_ldpc_code|];

  let (_, soft_region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080000010);
  let (_, hard_region) = setCapBounds(root_data_cap, 0x080000100, 0b0 @ 0x080000102);
  C(encdec_reg(0b00010)) = setCapAddrChecked(soft_region, test_fec_soft_base);
  C(encdec_reg(0b00011)) = setCapAddrChecked(hard_region, test_fec_hard_base);

  test_fec_write_soft_block();
  X(encdec_reg(0b00101)) = test_fec_descriptor(0x0010, 0x0010, 0x0000);

  match execute(FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "a decode inside both authorities must retire"),
  };

  // Little-endian, so the low byte of the halfword is the first output byte.
  assert(test_fec_hard_bytes() == 0x80AA, "the hard decision is the sign of each soft symbol, packed LSB first");

  // The soft block is untouched: `cd` is the only authority the pass writes
  // through and it covers the hard buffer alone.
  match mem_read_meta(Load(Data), Physaddr(test_fec_soft_base), 8, false, false, false) {
    Ok((value, _)) => assert(value == 0x8140C000FF01807F, "the decode reads the soft block and writes nowhere in it"),
    Err(_, _)      => assert(false, "reading the soft block back must succeed"),
  };

  // A final partial byte has its bits above `nhard` written **zero rather than
  // preserved**, so the destination is a total function of the source block. The
  // buffer is filled with ones first, or a clause that skipped the partial byte
  // and one that zero-filled it would be indistinguishable.
  match mem_write_value(Physaddr(test_fec_hard_base), 2, 0xFFFF, Store(Data), false, false) {
    Ok(_)     => (),
    Err(_, _) => assert(false, "priming the hard block must succeed"),
  };
  X(encdec_reg(0b00101)) = test_fec_descriptor(0x0010, 0x000C, 0x0000);
  match execute(FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "a twelve-bit block must retire"),
  };
  assert(test_fec_hard_bytes() == 0x00AA, "the bits above the block are written zero and not left standing");

  fec_codes = [||];
}

// *****************************************************************
// The two authorities, and each fault names its own register.

// R-08-003 puts the check on the capability operand of the issuing context, and
// what makes this surface's version of it two checks rather than one is that the
// block it consumes and the block it produces are different objects. The same
// descriptor through the same instruction faults on the soft side or on the hard
// side according to which authority is short, and the violation names the
// register the failing access took its authority from (R-15-073a).
$[test]
function test_the_fec_pass_is_checked_against_both_authorities() -> unit = {
  assert(fec_code_count(fec_codes) == 0, "the shipped composition declares no code");
  fec_codes = [|test_fec_ldpc_code|];

  let (_, hard_region) = setCapBounds(root_data_cap, 0x080000100, 0b0 @ 0x080000102);
  C(encdec_reg(0b00011)) = setCapAddrChecked(hard_region, test_fec_hard_base);
  X(encdec_reg(0b00101)) = test_fec_descriptor(0x0010, 0x0010, 0x0000);

  // Eight soft bytes of authority under a sixteen-symbol block: the ninth read
  // reaches past the soft buffer.
  let (_, short_soft) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080000008);
  C(encdec_reg(0b00010)) = setCapAddrChecked(short_soft, test_fec_soft_base);
  match execute(FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Ext_DataAddr_Check_Failure((capEx, idx)) => {
      assert(capEx == CapEx_LengthViolation);
      assert(idx == capreg_idx_of_regidx(encdec_reg(0b00010)));
    },
    _ => assert(false, "a soft symbol past the consuming authority must fault"),
  };

  // And the other side, with the soft authority whole: one byte of hard buffer
  // under a sixteen-bit block, so the second output byte reaches past it.
  let (_, soft_region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080000010);
  let (_, short_hard)  = setCapBounds(root_data_cap, 0x080000100, 0b0 @ 0x080000101);
  C(encdec_reg(0b00010)) = setCapAddrChecked(soft_region, test_fec_soft_base);
  C(encdec_reg(0b00011)) = setCapAddrChecked(short_hard, test_fec_hard_base);
  match execute(FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Ext_DataAddr_Check_Failure((capEx, idx)) => {
      assert(capEx == CapEx_LengthViolation);
      assert(idx == capreg_idx_of_regidx(encdec_reg(0b00011)));
    },
    _ => assert(false, "a hard byte past the producing authority must fault"),
  };

  // An untagged authority is an integer in a base register, which faults here
  // rather than reaching memory: there is no default data capability and no
  // unchecked path (R-15-001c).
  C(encdec_reg(0b00010)) = setCapAddrChecked(soft_region, test_fec_soft_base);
  C(encdec_reg(0b00011)) = null_cap;
  match execute(FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Ext_DataAddr_Check_Failure((capEx, idx)) => {
      assert(capEx == CapEx_TagViolation);
      assert(idx == capreg_idx_of_regidx(encdec_reg(0b00011)));
    },
    _ => assert(false, "an untagged producing authority must fault"),
  };

  fec_codes = [||];
}

// *****************************************************************
// The descriptor's refusals.

// The descriptor is a register operand, so its wrong values are refused at
// execute rather than by reaching no decode clause, which is where an unallocated
// `funct7` is refused instead (R-15-014). Every arm below is a shape the surface
// cannot mean, and each is refused rather than truncated, saturated, or clamped.
$[test]
function test_the_fec_descriptor_is_refused_where_it_is_wrong() -> unit = {
  assert(fec_code_count(fec_codes) == 0, "the shipped composition declares no code");
  fec_codes = [|test_fec_ldpc_code, test_fec_polar_code|];

  let (_, soft_region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080000010);
  let (_, hard_region) = setCapBounds(root_data_cap, 0x080000100, 0b0 @ 0x080000102);
  C(encdec_reg(0b00010)) = setCapAddrChecked(soft_region, test_fec_soft_base);
  C(encdec_reg(0b00011)) = setCapAddrChecked(hard_region, test_fec_hard_base);
  test_fec_write_soft_block();

  // A reserved field is reserved: a non-zero value there is an encoding this
  // surface does not carry, and admitting it would spend the field silently.
  X(encdec_reg(0b00101)) = 0x0001 @ 0x0000 @ 0x0010 @ 0x0010;
  match execute(FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Illegal_Instruction() => (),
    _ => assert(false, "a non-zero reserved descriptor field must be refused"),
  };

  // An index naming no declared code. Two codes are declared, so 2 is the first
  // index that names none.
  X(encdec_reg(0b00101)) = test_fec_descriptor(0x0010, 0x0010, 0x0002);
  match execute(FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Illegal_Instruction() => (),
    _ => assert(false, "an index naming no declared code must be refused"),
  };

  // The family the instruction names against the family the code is of. Code 1
  // is the polar row, so `ldpcdec` may not decode it and `polardec` may.
  X(encdec_reg(0b00101)) = test_fec_descriptor(0x0010, 0x0010, 0x0001);
  match execute(FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Illegal_Instruction() => (),
    _ => assert(false, "an LDPC instruction over a polar code must be refused"),
  };
  match execute(FecDecode(FecFamily_Polar, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _ => assert(false, "a polar instruction over a polar code must retire"),
  };

  // A block of no symbols and a block producing no bits are both decodes of
  // nothing, and a block producing more bits than it consumed symbols is not a
  // decode at all.
  X(encdec_reg(0b00101)) = test_fec_descriptor(0x0000, 0x0010, 0x0000);
  match execute(FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Illegal_Instruction() => (),
    _ => assert(false, "a block of no soft symbols must be refused"),
  };
  X(encdec_reg(0b00101)) = test_fec_descriptor(0x0010, 0x0000, 0x0000);
  match execute(FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Illegal_Instruction() => (),
    _ => assert(false, "a block producing no hard bits must be refused"),
  };
  X(encdec_reg(0b00101)) = test_fec_descriptor(0x0010, 0x0011, 0x0000);
  match execute(FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Illegal_Instruction() => (),
    _ => assert(false, "a block producing more bits than it consumed symbols must be refused"),
  };

  fec_codes = [||];
}

// *****************************************************************
// The encoding is invariant over the codes a composition declares.

// This is R-15-119b's own criterion, made a property. A builder supplies the
// channel-code parameters from a copy of TS 38.212 this repository does not carry
// (R-15-119a), and if a parameter could reach an instruction field then two
// builders would freeze two profiles and the single freeze R-15-014 takes would
// be one per composition. What the descriptor carries is an *index* into the
// declared set, so the same operands assemble to the same word under any
// declaration, and the two families differ in the sub-opcode field alone.
$[test]
function test_the_fec_encoding_is_invariant_over_the_declared_codes() -> unit = {
  assert(fec_code_count(fec_codes) == 0, "the shipped composition declares no code");
  test_fec_attach_units();

  let ldpc = FecDecode(FecFamily_Ldpc, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011));
  let polar = FecDecode(FecFamily_Polar, encdec_reg(0b00101), encdec_reg(0b00010), encdec_reg(0b00011));

  fec_codes = [|test_fec_ldpc_code|];
  let one = encdec(ldpc);
  fec_codes = [|test_fec_polar_code, test_fec_ldpc_code, test_fec_polar_code|];
  let many = encdec(ldpc);
  fec_codes = [||];
  let none = encdec(ldpc);
  assert(one == many & many == none, "the word does not depend on what codes a composition declares");

  // The family is the sub-opcode and nothing else moves with it, which is what
  // puts both decoders in one `funct3` and leaves two of the three free points in
  // custom-0 unspent (R-15-119b).
  let word = encdec(polar);
  assert(word[24 .. 0] == one[24 .. 0], "the two families share every field below `funct7`");
  assert(word[31 .. 25] != one[31 .. 25], "and are separated by `funct7` alone");
  assert(one[6 .. 0] == 0b0001011 & one[14 .. 12] == 0b100, "custom-0, `funct3` 100");

  fec_codes = [||];
  test_fec_detach_units();
}

// *****************************************************************
// The gate is the roster's and it is the whole gate.

// `vmclear` gates on a static property because it is the switcher's and must not
// be trappable by the partition it erases; `vkeccak.vi` folds in `mstatus.VS`
// because it is the partition's own and writes the architectural vector register
// file. This one is the partition's own **and touches no extension context at
// all**, its whole effect being memory reached through two explicit capability
// operands (R-15-118), so there is no context bit for a context gate to read and
// the static half is the whole gate.
$[test]
function test_the_fec_gate_is_the_composed_roster_entry() -> unit = {
  assert(not(this_core_has_fec_units()), "no composition in this tree attaches the decoders to the composed hart");

  test_fec_attach_units();
  assert(this_core_has_fec_units(), "an entry carrying the units is what makes the surface decode");

  test_fec_detach_units();
  assert(not(this_core_has_fec_units()), "and the gate follows the roster back");
}

// **The unit count is the roster's own and is declared nowhere beside it**,
// which is R-15-113's rule for a count applied to the one item of R-15-119a's
// machine-side list that is an enumeration rather than a width. It is asserted
// over a roster written here rather than over the composed one, because what is
// claimed is that the count is *derived* and a composition's own figure would be
// evidence about that composition instead.
$[test]
function test_the_fec_unit_count_is_derived_from_the_roster() -> unit = {
  assert(fec_unit_count([||]) == 0);
  assert(fec_unit_count([|test_fec_roster_entry(0, false)|]) == 0);

  // And it is a different question from the core count over the same roster: a
  // class's cores and its decoders are counted from the same enumeration and are
  // not the same number (R-15-113, R-12-038).
  let roster = [|test_fec_roster_entry(0, true), test_fec_roster_entry(1, false),
                 test_fec_roster_entry(2, true)|];
  assert(core_class_count(roster, CoreClass_V) == 3);
  assert(fec_unit_count(roster) == 2);
}
