// The frozen Keccak fork, against FIPS 202 and the NIST ACVP vectors
// (R-15-058, extensions/keccak/keccak_p1600.sail,
// extensions/keccak/keccak_insts.sail).
//
// R-15-058 makes the fixed-permutation invariant a **fresh** statement, there
// being no Coq-native Keccak proof to import, and disciplines it against FIPS
// 202 and the ACVP vectors as a differential oracle. What that is here is these
// properties: the permutation is exercised against published answers rather
// than against a second implementation of itself, so a transcription error in
// the round constants, the rotation offsets, the lane order, or the round range
// is a failure and not a difference of opinion between two things this
// repository wrote.
//
// **The oracle enters no trust base** (R-15-058). A known-answer vector is a
// constant in a test; nothing above it depends on the vector being right, and
// what it buys is that the constant and the model were produced by different
// routes. The vectors below were produced by an independent FIPS 202
// implementation cross-checked against the standard library's own SHA-3 on
// eleven digests spanning all four SHA-3 widths and both SHAKE functions, and
// the 24-round all-zero answer is the Keccak team's own published value for the
// permutation.
//
// The properties split the way the two files do. The first three are about the
// **permutation**, are stated at no geometry at all, and are the ones a reader
// checks against the standard. The last two are about the **instruction**: that
// the element group is wired to the permutation without a reordering, and that
// the encoding is closed.

// Every table below is written in the standard's lane order and read through
// `keccak_state_of_literal`, a Sail vector literal being `dec`-ordered so that
// its first element is its highest index (extensions/keccak/keccak_p1600.sail).
// Writing the vectors in index order instead would put them in a shape nobody
// can check against a published one, which is the whole of what a known-answer
// test buys.

// The state after Keccak-*f*[1600], which is Keccak-*p*[1600,24], applied once
// to the all-zero state. This is the standard published vector for the
// permutation and the one a fresh implementation is checked against first.
let keccak_kat_zero_24 : keccak_state = [
  0xF1258F7940E1DDE7, 0x84D5CCF933C0478A, 0xD598261EA65AA9EE, 0xBD1547306F80494D,
  0x8B284E056253D057, 0xFF97A42D7F8E6FD4, 0x90FEE5A0A44647C4, 0x8C5BDA0CD6192E76,
  0xAD30A6F71B19059C, 0x30935AB7D08FFC64, 0xEB5AA93F2317D635, 0xA9A6E6260D712103,
  0x81A57C16DBCF555F, 0x43B831CD0347C826, 0x01F22F1A11A5569F, 0x05E5635A21D9AE61,
  0x64BEFEF28CC970F2, 0x613670957BC46611, 0xB87C5A554FD00ECB, 0x8C3EE88A1CCF32C8,
  0x940C7922AE3A2614, 0x1841F924A2C509E4, 0x16F53526E70465C2, 0x75F644E97F30A13B,
  0xEAF1FF7B5CECA249,
]

// The same permutation applied twice, which is the second half of the published
// pair. A single application can be matched by an implementation that has the
// round range right and the round *order* wrong in a way the first vector does
// not separate, so the pair is carried rather than the first alone.
let keccak_kat_zero_24_twice : keccak_state = [
  0x2D5C954DF96ECB3C, 0x6A332CD07057B56D, 0x093D8D1270D76B6C, 0x8A20D9B25569D094,
  0x4F9C4F99E5E7F156, 0xF957B9A2DA65FB38, 0x85773DAE1275AF0D, 0xFAF4F247C3D810F7,
  0x1F1B9EE6F79A8759, 0xE4FECC0FEE98B425, 0x68CE61B6B9CE68A1, 0xDEEA66C4BA8F974F,
  0x33C43D836EAFB1F5, 0xE00654042719DBD9, 0x7CF8A9F009831265, 0xFD5449A6BF174743,
  0x97DDAD33D8994B40, 0x48EAD5FC5D0BE774, 0xE3B8C8EE55B7B03C, 0x91A0226E649E42E9,
  0x900E3129E7BADD7B, 0x202A9EC5FAA3CCE8, 0x5B3402464E1C3DB6, 0x609F4E62A44C1059,
  0x20D06CD26A8FBF5C,
]

// Keccak-*p*[1600,12] applied once to the all-zero state, which is the TurboSHAKE
// and KangarooTwelve permutation (R-15-056a). This is the vector that separates
// *the last twelve rounds* from *the first twelve rounds*: both are twelve
// rounds of the same round function and only one of them is the standard's.
let keccak_kat_zero_12 : keccak_state = [
  0x8E5E5438B9A78617, 0xD9CD6A50F259D01E, 0x87B8E7C652A91F35, 0x1093E067CDE4E0C5,
  0xB033AB90F2D95A45, 0xE0A72F72A8DD1A45, 0xC53780AA14672F9C, 0x3EDD47F50051071D,
  0xB3A31D310C178ACC, 0x79B586A59257AAA0, 0xBC4A7C3DB3B1F99B, 0x68874063E68A6793,
  0x5C6C03332E0E2566, 0x9CAA1202B9F030DA, 0x5F3B9A782BCF7A9F, 0xE536C1E061AE7923,
  0x6DE9B618B73C87EC, 0x2ABED1F170918AC2, 0x6AABBD53DAED24B7, 0xBFC1416A2C2EE15A,
  0xC6CFE036B90952AF, 0x45503617DC7060D7, 0x625611B2C29F7AE4, 0xD43671DB2C30647A,
  0xCFFD0D76222CA01C,
]

// A computed state against a published one, the published one read out of its
// literal's order into the lane order the state is computed in.
function keccak_matches_kat(a : keccak_state, literal : keccak_state) -> bool = {
  let b = keccak_state_of_literal(literal);
  var equal : bool = true;
  foreach (i from 0 to 24) {
    if a[i] != b[i] then equal = false
  };
  equal
}

function keccak_states_equal(a : keccak_state, b : keccak_state) -> bool = {
  var equal : bool = true;
  foreach (i from 0 to 24) {
    if a[i] != b[i] then equal = false
  };
  equal
}

// *****************************************************************
// The permutation, against FIPS 202.

// Both round counts against the published answers for the all-zero state, and
// the 24-round one twice. Nothing here names a vector register, a VLEN, or an
// instruction: R-15-058's invariant is about the permutation, and a statement
// about a function holds at every geometry the instruction is issued at.
$[test]
function test_keccak_permutation_matches_fips202() -> unit = {
  let zero : keccak_state = vector_init(zeros());

  let once = keccak_p1600(zero, 24);
  assert(keccak_matches_kat(once, keccak_kat_zero_24),
         "Keccak-f[1600] of the all-zero state must be the published vector");

  assert(keccak_matches_kat(keccak_p1600(once, 24), keccak_kat_zero_24_twice),
         "Keccak-f[1600] applied twice to the all-zero state must be the published vector");

  assert(keccak_matches_kat(keccak_p1600(zero, 12), keccak_kat_zero_12),
         "Keccak-p[1600,12] of the all-zero state must be the published vector");

  // The two round counts are two permutations and not one scaled: a model that
  // ran twelve rounds for both, or twenty-four for both, would pass a test that
  // only checked that each answer is stable.
  assert(not(keccak_states_equal(keccak_p1600(zero, 12), keccak_p1600(zero, 24))),
         "the two frozen round counts must be different permutations");

  // And the short form is a **suffix** of the long one rather than a prefix,
  // which is the one thing about R-15-056a a round-count argument cannot show:
  // twelve rounds of the last twelve constants applied to a state that has
  // already had the first twelve is the whole permutation.
  var head : keccak_state = zero;
  foreach (i from 0 to 11) {
    head = keccak_round(head, keccak_rc(i))
  };
  assert(keccak_matches_kat(keccak_p1600(head, 12), keccak_kat_zero_24),
         "the 12-round form must be the last twelve rounds of the 24-round one");
}

// One NIST ACVP message, carried through the permutation the way a sponge
// carries it: the SHA-3-256 rate is 136 bytes, so the empty message's padded
// block is the domain-separation byte 0x06 at byte 0 and the 0x80 at byte 135,
// which is lane 0 and lane 16 in the standard's lane order. The first four
// lanes of the result, read little-endian, are the ACVP known answer.
//
// This is the property that would catch a **lane-order** error, which the
// all-zero vectors above cannot: a state that is zero everywhere is invariant
// under any permutation of its lanes, so the first message with two distinct
// non-zero lanes is the first one that fixes where lane 16 is.
$[test]
function test_keccak_absorbs_an_acvp_message() -> unit = {
  var block : keccak_state = vector_init(zeros());
  block[0]  = 0x0000000000000006;
  block[16] = 0x8000000000000000;

  let out = keccak_p1600(block, 24);

  // a7ffc6f8 bf1ed766 51c14756 a061d662 f580ff4d e43b49fa 82d80a4b 80f8434a
  assert(out[0] == 0x66D71EBFF8C6FFA7, "SHA3-256 of the empty message, bytes 0 to 7");
  assert(out[1] == 0x62D661A05647C151, "SHA3-256 of the empty message, bytes 8 to 15");
  assert(out[2] == 0xFA493BE44DFF80F5, "SHA3-256 of the empty message, bytes 16 to 23");
  assert(out[3] == 0x4A43F8804B0AD882, "SHA3-256 of the empty message, bytes 24 to 31");
}

// The two tables, against their own shapes. A transcription error inside either
// is caught by the vectors above; what is caught here is an error that makes the
// table not a table of its kind at all, which is the failure a vector would
// report as an unreadable difference rather than as a cause.
$[test]
function test_keccak_tables_are_well_formed() -> unit = {
  // Both ends of the round-constant table, pinned. A Sail vector literal is
  // `dec`-ordered, so reading it without the accessor runs the permutation's
  // rounds backwards, which is a defect the known-answer vectors report as an
  // unreadable difference and this reports as its cause
  // (extensions/keccak/keccak_p1600.sail).
  assert(keccak_rc(0) == 0x0000000000000001, "the first round constant");
  assert(keccak_rc(23) == 0x8000000080008008, "the last round constant");
  // The 12-round form starts at round 12 of the same table (R-15-056a).
  assert(keccak_rc(12) == 0x000000008000808B, "the first constant of the short form");

  // *rho* rotates each of the twenty-five lanes by a distinct offset modulo 64,
  // lane (0, 0) alone by zero. The offsets are the triangular numbers modulo 64
  // and are therefore distinct, so a repeated offset is a transcription error.
  var seen : vector(64, bool) = vector_init(false);
  foreach (x from 0 to 4) {
    foreach (y from 0 to 4) {
      let r = keccak_rho(x, y);
      assert(not(seen[r]), "the rho offsets must be distinct");
      seen[r] = true
    }
  };
  assert(keccak_rho(0, 0) == 0, "rho leaves lane (0, 0) unrotated");

  // *pi* is a permutation of the twenty-five lanes, so every destination is
  // reached exactly once. A `mod 5` transcribed wrongly makes it a function that
  // drops a lane and duplicates another, which is the failure this catches.
  var reached : vector(25, bool) = vector_init(false);
  foreach (x from 0 to 4) {
    foreach (y from 0 to 4) {
      let d = y + 5 * keccak_mod5(2 * x + 3 * y);
      assert(not(reached[d]), "pi must be a permutation of the lanes");
      reached[d] = true
    }
  };

  // The two column steps are inverse to each other and neither is the identity.
  foreach (x from 0 to 4) {
    assert(keccak_prev5(keccak_next5(x)) == x, "the column steps must be inverse");
    assert(keccak_next5(x) != x, "the column step must not be the identity")
  }
}

// *****************************************************************
// The instruction.

// The `vlmul` encoding that makes the 2048-bit element group exactly one
// register group at this build's VLEN, or `None()` where no LMUL reaches it.
// LMUL tops out at 8, so nothing below VLEN=256 does (R-15-057a).
function keccak_test_vlmul() -> option(bits(3)) =
  if vlen_exp < 8 then None()
  else Some(match vlen_exp {
    8  => 0b011,  // VLEN=256,   LMUL=8
    9  => 0b010,  // VLEN=512,   LMUL=4
    10 => 0b001,  // VLEN=1024,  LMUL=2
    11 => 0b000,  // VLEN=2048,  LMUL=1
    12 => 0b111,  // VLEN=4096,  LMUL=1/2
    13 => 0b110,  // VLEN=8192,  LMUL=1/4
    _  => 0b101,  // VLEN>=16384, LMUL=1/8
  })

// `vkeccak.vi v0, v0, 24`, whose fields are `funct7` 0, `rs2` the round-count
// immediate 24, `rs1` the source group, `funct3` 010, `rd` the destination
// group, and custom-0.
let keccak_word_24        : bits(32) = 0x0180200B  // vkeccak.vi v0, v0, 24
let keccak_word_12        : bits(32) = 0x00C0200B  // vkeccak.vi v0, v0, 12
let keccak_word_v8_v0_24  : bits(32) = 0x0180240B  // vkeccak.vi v8, v0, 24
let keccak_word_rounds_23 : bits(32) = 0x0170200B  // an unassigned round count
let keccak_word_funct7    : bits(32) = 0x0380200B  // a non-zero reserved funct7

// Put this build's vector unit into the one configuration the instruction
// decodes at: SEW=64, the LMUL that makes the element group one register group,
// and `vl` at the group's 32 elements.
function keccak_test_configure(vlmul : bits(3)) -> unit = {
  mstatus[VS]     = extStatus_map(Dirty);
  vtype[vill]     = 0b0;
  vtype[reserved] = zeros();
  vtype[vma]      = 0b0;
  vtype[vta]      = 0b0;
  vtype[vsew]     = 0b011;
  vtype[vlmul]    = vlmul;
  vl              = to_bits(sizeof(xlen), 32);
}

// The element group carries the state in the standard's own lane order, so the
// instruction is the permutation and a vector register group and nothing
// between them. The all-zero group is what reset leaves, so what this asserts is
// the whole path: decode, the group read, the permutation, the group write, and
// the disposition of the 448 bits above the state.
$[test]
function test_keccak_instruction_carries_the_element_group() -> unit = {
  match keccak_test_vlmul() {
    // Below VLEN=256 no LMUL reaches an element group of 2048 bits, so the
    // encoding is unallocated and traps, which is the property at that geometry
    // rather than an absence of one (R-15-014, R-15-057a).
    None() => {
      match ext_decode(keccak_word_24) {
        ILLEGAL(_) => (),
        _          => assert(false, "vkeccak.vi must not decode below VLEN=256"),
      }
    },
    Some(vlmul) => {
      keccak_test_configure(vlmul);

      match ext_decode(keccak_word_24) {
        VKECCAK_VI(rnd, vs2, vd) => {
          assert(rnd == 0b11000, "the round-count immediate is the rs2 field");
          assert(vregidx_bits(vs2) == 0b00000 & vregidx_bits(vd) == 0b00000,
                 "vkeccak.vi v0, v0, 24 names v0 twice");
        },
        _ => assert(false, "custom-0 funct3 010 must decode as vkeccak.vi"),
      };

      // In place over the group reset leaves zero, twice, against both halves of
      // the published pair. Doing it twice is also what shows the destination is
      // read back as the source: a clause that wrote the permutation somewhere
      // else would pass the first check and fail the second.
      init_vregs();
      let kat24 = keccak_state_of_literal(keccak_kat_zero_24);
      match execute(VKECCAK_VI(0b11000, Vregidx(0b00000), Vregidx(0b00000))) {
        Retire_Success() => (),
        _                => assert(false, "vkeccak.vi must retire"),
      };
      foreach (j from 0 to 24) {
        assert(read_single_element(64, j, Vregidx(0b00000)) == kat24[j],
               "the element group must hold the permuted state in lane order")
      };
      // The 448 bits above the 1600-bit state are written zero rather than
      // preserved, so the destination group is a total function of the source
      // state (extensions/keccak/keccak_insts.sail).
      foreach (j from 25 to 31) {
        assert(read_single_element(64, j, Vregidx(0b00000)) == zeros(),
               "the element group above the state must be written zero")
      };

      match execute(VKECCAK_VI(0b11000, Vregidx(0b00000), Vregidx(0b00000))) {
        Retire_Success() => (),
        _                => assert(false, "vkeccak.vi must retire"),
      };
      let kat24twice = keccak_state_of_literal(keccak_kat_zero_24_twice);
      foreach (j from 0 to 24) {
        assert(read_single_element(64, j, Vregidx(0b00000)) == kat24twice[j],
               "the instruction must permute the group it wrote")
      };

      // The short round count, from a fresh zero group, and a distinct
      // destination group so that the source is checked to survive.
      init_vregs();
      match execute(VKECCAK_VI(0b01100, Vregidx(0b00000), Vregidx(0b01000))) {
        Retire_Success() => (),
        _                => assert(false, "vkeccak.vi at 12 rounds must retire"),
      };
      let kat12 = keccak_state_of_literal(keccak_kat_zero_12);
      foreach (j from 0 to 24) {
        assert(read_single_element(64, j, Vregidx(0b01000)) == kat12[j],
               "the 12-round form must write the TurboSHAKE permutation");
        assert(read_single_element(64, j, Vregidx(0b00000)) == zeros(),
               "a distinct source group must survive unchanged")
      };

      // An unaligned register group is not a group: at LMUL=8 the only starts
      // are v0, v8, v16 and v24, and an instruction naming any other one is
      // illegal rather than realigned.
      if vlen_exp == 8 then {
        match execute(VKECCAK_VI(0b11000, Vregidx(0b00001), Vregidx(0b00000))) {
          Illegal_Instruction() => (),
          _ => assert(false, "an unaligned source group must be illegal at LMUL=8"),
        }
      };
    },
  }
}

// The encoding is closed in both of the directions R-15-057a and R-15-014 close
// it: an unassigned round count and a non-zero reserved field each reach no
// decode clause and therefore trap, rather than being rounded to an admitted
// value or ignored.
$[test]
function test_keccak_encoding_is_closed() -> unit = {
  match keccak_test_vlmul() {
    None()      => (),
    Some(vlmul) => {
      keccak_test_configure(vlmul);

      match ext_decode(keccak_word_12) {
        VKECCAK_VI(rnd, _, _) => assert(rnd == 0b01100, "12 is an admitted round count"),
        _                     => assert(false, "vkeccak.vi at 12 rounds must decode"),
      };
      match ext_decode(keccak_word_v8_v0_24) {
        VKECCAK_VI(_, vs2, vd) =>
          assert(vregidx_bits(vs2) == 0b00000 & vregidx_bits(vd) == 0b01000,
                 "the source and destination groups are separate fields"),
        _ => assert(false, "vkeccak.vi with a distinct destination must decode"),
      };

      match ext_decode(keccak_word_rounds_23) {
        ILLEGAL(_) => (),
        _          => assert(false, "an unassigned round count must be illegal"),
      };
      match ext_decode(keccak_word_funct7) {
        ILLEGAL(_) => (),
        _          => assert(false, "a non-zero reserved funct7 must be illegal"),
      };

      // The context gate is folded in, which is where this instruction parts
      // company with `vmclear`: that one is the switcher's and must not be
      // trappable by the partition it erases, and this one is the partition's
      // own and reads and writes the architectural vector register file
      // (extensions/keccak/keccak_insts.sail, extensions/platform/vmclear.sail).
      mstatus[VS] = extStatus_map(Off);
      match ext_decode(keccak_word_24) {
        ILLEGAL(_) => (),
        _          => assert(false, "vkeccak.vi must trap with the vector context off"),
      };
      mstatus[VS] = extStatus_map(Dirty);

      // And `vill` is *no configuration*, not a configuration this instruction
      // may read a SEW out of (extensions/platform/vmclear.sail).
      vtype[vill] = 0b1;
      match ext_decode(keccak_word_24) {
        ILLEGAL(_) => (),
        _          => assert(false, "vkeccak.vi must trap with no vector configuration"),
      };
    },
  }
}

// R-15-059a's register-pressure figure, held as a property rather than declared
// as a number. At the C class's VLEN=256 the 2048-bit element group is LMUL=8,
// so a source group and a destination group are eight architectural vector
// registers each and a two-group permutation names sixteen of the thirty-two;
// the figure is not extrapolated from the V class's VLEN=4096, where the same
// element group is LMUL=1/2 and one register holds it.
$[test]
function test_keccak_element_group_is_lmul8_at_the_c_class() -> unit = {
  match keccak_test_vlmul() {
    None()      => (),
    Some(vlmul) => {
      keccak_test_configure(vlmul);
      let LMUL_pow = get_lmul_pow();
      let group_registers = if LMUL_pow > 0 then 2 ^ LMUL_pow else 1;

      // Whatever the geometry, the element group is 2048 bits.
      let group_bits = if LMUL_pow < 0 then vlen / (2 ^ abs_int(LMUL_pow))
                       else (2 ^ LMUL_pow) * vlen;
      assert(group_bits >= 2048, "the element group must reach 2048 bits");

      if vlen_exp == 8 then {
        assert(LMUL_pow == 3, "the C class's element group is LMUL=8");
        assert(group_registers == 8, "one permutation names eight of thirty-two registers");
        assert(group_bits == 2048, "at VLEN=256 the group is the element group exactly");
      }
    },
  }
}
