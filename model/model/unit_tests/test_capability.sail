// Properties of the capability encoding (core/cap_format.sail) and of the
// algebra over it (core/cap_common.sail).
//
// These are the format's standing regression rather than its proof. The
// representation-correctness obligation R-15-007a books (encode/decode round
// trip, field extraction, derivation of base and top, decode total over the
// bounds encoding) is a proof over statements of this shape, and until it is
// discharged these are what the frozen field widths are checked against.
//
// They are also, for now, the whole of the machine's own regression corpus.
// `riscv-tests` addresses memory with an integer base register throughout,
// which on a purecap machine is an untagged capability that faults at its
// first load, so the suite stopped being a corpus this machine can run when the
// default data capability went (model/test/CMakeLists.txt, R-15-001c). The
// purecap programs that replace it are M0.12's.

// *****************************************************************
// The encoding.

// An all-zeroes granule decodes as untagged NULL, and NULL stores back as all
// zeroes. Eager zeroize and `cbo.zero` both rely on reading that back
// (R-15-182, R-15-060).
$[test]
function test_null_capability_is_the_all_zeroes_granule() -> unit = {
  assert(capToMemBits(null_cap) == zeros());
  let decoded = memBitsToCapability(false, zeros());
  assert(not(decoded.tag));
  assert(decoded == null_cap);
}

// The format spends 64 bits and one tag bit, and the granule it is stored in is
// the tag plane's (R-15-007, R-15-203).
$[test]
function test_the_format_spends_sixty_four_bits() -> unit = {
  assert(cap_size * 8 == 64);
  assert(cap_perms_code_width + cap_otype_width + cap_E_width
         + cap_mantissa_width + (cap_mantissa_width - 2) + cap_addr_width == 64);
  assert(cap_addr_width == 36);
}

// Encoding and decoding round-trip on the capabilities the model resets from,
// tag included, and on an arbitrary bit pattern: decode is total over the
// encoding, so every 64-bit granule names a capability and the pair is a
// bijection (R-15-007a). Totality is what an integer read of a register rests
// on, the register's 64 data bits being the integer (core/reg_type.sail).
$[test]
function test_encode_decode_round_trips() -> unit = {
  assert(capBitsToCapability(false, capToBits(null_cap)) == null_cap);
  assert(capBitsToCapability(true, capToBits(default_cap)) == default_cap);
  assert(capBitsToCapability(true, capToBits(root_data_cap)) == root_data_cap);
  foreach (i from 0 to 63) {
    let pattern : CapBits = 0x9e3779b97f4a7c15 ^ (ones() >> i);
    assert(capToBits(capBitsToCapability(false, pattern)) == pattern);
  }
}

// *****************************************************************
// Permissions: an enumerated lattice, not one bit per permission.

// The enumeration is total over all 32 codepoints, which is what stands in
// place of a legal-permissions invariant: a total encoding has no codepoint to
// reject (R-15-007b, R-15-007a).
$[test]
function test_the_permission_enumeration_is_total() -> unit = {
  // Distinct codepoints name distinct sets, so the encoding wastes none of the
  // 32 and `perms_narrow` has one answer.
  foreach (i from 0 to 31) {
    foreach (j from 0 to 31) {
      let ci : CapPermsCode = to_bits_truncate(cap_perms_code_width, i);
      let cj : CapPermsCode = to_bits_truncate(cap_perms_code_width, j);
      assert((i == j) | (perms_expand(ci) != perms_expand(cj)));
    }
  };
  // The bottom element is the all-zeroes codepoint, which is what makes the
  // null capability's permission field zero.
  assert(perms_expand(perms_none) == zeros());
}

// Two combinations are excluded at the lattice rather than downstream of it, so
// each is a finite check over 32 codepoints rather than a property of one
// audited distribution (R-15-007l, R-15-007o).
$[test]
function test_the_lattice_excludes_two_combinations() -> unit = {
  foreach (i from 0 to 31) {
    let set = perms_expand(to_bits_truncate(cap_perms_code_width, i));
    // No admitted set holds both store and execute, so W+X is unrepresentable
    // rather than merely underivable.
    assert(not(bit_to_bool(set[2]) & bit_to_bool(set[8])));
    // No admitted set holds both seal and unseal, so minting a delegation and
    // redeeming one are never the same lattice element.
    assert(not(bit_to_bool(set[9]) & bit_to_bool(set[10])));
  }
}

// A mask can only remove: the result is an admitted set contained in the
// intersection, whatever mask is handed to it, and an all-ones mask is the
// identity (R-15-007b).
$[test]
function test_permission_narrowing_is_monotone() -> unit = {
  foreach (i from 0 to 31) {
    let code : CapPermsCode = to_bits_truncate(cap_perms_code_width, i);
    let set = perms_expand(code);
    assert(perms_narrow(set) == code);
    foreach (b from 0 to (cap_perms_width - 1)) {
      let masked = set & ~(zero_extend(0b1) << b);
      let got = perms_expand(perms_narrow(masked));
      assert((got & masked) == got);
    }
  }
}

// The reset roots are a **pair**, because the lattice makes one almighty root
// inexpressible: the execute side carries no store permission and the store
// side no execute permission (R-15-007l, R-15-007p).
$[test]
function test_the_root_set_is_split() -> unit = {
  assert(cap_permit_execute(default_cap));
  assert(not(cap_permit_store(default_cap)));
  assert(cap_access_system_regs(default_cap));
  assert(cap_permit_store(root_data_cap));
  assert(not(cap_permit_execute(root_data_cap)));
  // The store side carries store-local, since `candperm` can only remove and a
  // stack capability is derived from it.
  assert(cap_store_local_cap(root_data_cap));
  assert(cap_global(default_cap) & cap_global(root_data_cap));
  assert(not(cap_global(null_cap)));
}

// *****************************************************************
// Bounds.

// The reset capability spans the whole address space.
$[test]
function test_default_capability_spans_the_address_space() -> unit = {
  let (base, top) = getCapBounds(default_cap);
  assert(base == 0);
  assert(top == pow2(cap_addr_width));
  assert(getCapLength(default_cap) == pow2(cap_addr_width));
}

// A narrowing to an aligned region is exact, and the bounds read back as they
// were set.
$[test]
function test_set_bounds_is_exact_on_an_aligned_region() -> unit = {
  let base : CapAddrBits = 0x080000000;
  let top : CapLenBits = (0b0 @ base) + 4096;
  let (exact, c) = setCapBounds(root_data_cap, base, top);
  assert(exact);
  let (b, t) = getCapBounds(c);
  assert(b == unsigned(base));
  assert(t == unsigned(top));
}

// Below the mantissa threshold the bounds are byte-exact at any base, which is
// the precision the narrowing spends mantissa width to buy (R-15-007c).
//
// The threshold the frozen widths deliver is **128 bytes**, and it is a
// property of the encoding rather than of the mantissa alone: the exponent is
// chosen so that the length mantissa's top two bits are known to the decoder,
// which is what lets the top mantissa be stored in six bits and derived into
// eight, so an exponent of zero reaches half the mantissa's span and not all of
// it. Above the threshold the quantum is one part in 64 to one part in 128 of
// the length, on each side.
$[test]
function test_small_bounds_are_byte_exact() -> unit = {
  let base : CapAddrBits = 0x080000003;
  let top : CapLenBits = (0b0 @ base) + 5;
  let (exact, c) = setCapBounds(root_data_cap, base, top);
  assert(exact);
  let (b, t) = getCapBounds(c);
  assert(b == unsigned(base));
  assert(t == unsigned(top));
  assert(getCapLength(c) == 5);

  // Byte-exact at an arbitrary, deliberately unaligned base.
  foreach (len from 1 to 127) {
    let (ex, d) = setCapBounds(root_data_cap, 0x080000103, (0b0 @ 0x080000103) + len);
    assert(ex);
    assert(getCapLength(d) == len);
  };

  // Above it the narrow is still exact where the base and the length are
  // aligned to the quantum, which is the case the static memory plan is
  // obliged to arrange for every capability the profile's code derives
  // (R-15-007k, R-08-011).
  foreach (k from 7 to 20) {
    let len = pow2(k);
    let aligned : CapAddrBits = to_bits_truncate(cap_addr_width, 2 * len);
    let (ex, d) = setCapBounds(root_data_cap, aligned, (0b0 @ aligned) + len);
    assert(ex);
    assert(getCapLength(d) == len);
  };

  // And an unaligned narrow above the threshold rounds outward rather than
  // failing: the result is a *larger* region, never a smaller one, so the
  // derivation stays monotone (R-15-007c, R-15-007h).
  let odd : CapAddrBits = 0x080000103;
  let want = unsigned(odd);
  let (inexact, wide) = setCapBounds(root_data_cap, odd, (0b0 @ odd) + 1000);
  assert(not(inexact));
  let (wb, wt) = getCapBounds(wide);
  assert(wb <= want);
  assert(wt >= want + 1000);
  // The padding is bounded at one part in 64 of the length on each side.
  assert(want - wb <= 1000 / 64);
  assert(wt - (want + 1000) <= 1000 / 64);
}

// Moving the address outside the representable region yields an untagged
// result rather than a trap: a failed derivation is a data result that faults
// at its next dereference (R-15-007h). A move that stays inside keeps the tag.
$[test]
function test_unrepresentable_address_clears_the_tag() -> unit = {
  let base : CapAddrBits = 0x080000000;
  let (_, c) = setCapBounds(root_data_cap, base, (0b0 @ base) + 4096);
  assert(c.tag);
  let moved = setCapAddrChecked(c, zeros());
  assert(not(moved.tag));
  let near = setCapAddrChecked(c, zero_extend(base) + 8);
  assert(near.tag);
  assert(capBoundsEqual(near, c));
}

// An address above the implemented space is unrepresentable on the same terms,
// so no path runs from an out-of-range integer to an access (R-15-002a).
$[test]
function test_an_out_of_range_address_is_unrepresentable() -> unit = {
  let beyond : xlenbits = 0x0000001000000000; // 2^36
  let moved = setCapAddrChecked(default_cap, beyond);
  assert(not(moved.tag));
  assert(not(inCapBounds(default_cap, beyond, 4)));
  assert(inCapBounds(default_cap, 0x0000000fffffffff, 1));
}

// *****************************************************************
// Sealing.

// Sealing changes the object type and nothing else, and unsealing undoes it.
$[test]
function test_sealing_changes_only_the_object_type() -> unit = {
  assert(not(isCapSealed(default_cap)));
  let otype : CapOTypeBits = to_bits(3);
  let sealed = sealCap(default_cap, otype);
  assert(isCapSealed(sealed));
  assert(capBoundsEqual(sealed, default_cap));
  assert(getCapPerms(sealed) == getCapPerms(default_cap));
  assert(unsealCap(sealed) == default_cap);
}

// The four-bit object type names sixteen classes: thirteen the composition
// allocates and three the architecture reserves, the unsealed codepoint and the
// two sentry edges (R-15-007, R-15-071).
$[test]
function test_the_object_type_space_is_frozen() -> unit = {
  assert(cap_max_otype == 12);
  assert(hasReservedOType(sealCap(default_cap, otype_unsealed_bits)));
  assert(hasReservedOType(sealCap(default_cap, otype_sentry_fwd_bits)));
  assert(hasReservedOType(sealCap(default_cap, otype_sentry_bwd_bits)));
  assert(not(hasReservedOType(sealCap(default_cap, to_bits(12)))));
  assert(isSentry(sealCap(default_cap, otype_sentry_fwd_bits)));
  assert(isSentry(sealCap(default_cap, otype_sentry_bwd_bits)));
  assert(not(isSentry(sealCap(default_cap, to_bits(12)))));
  assert(otype_sentry_fwd_bits != otype_sentry_bwd_bits);
}

// *****************************************************************
// The merged register file.

// The register file is one file read two ways: `C(r)` is the capability and
// `X(r)` is its 64 data bits (R-15-007i). Writing an integer over a register
// destroys the authority it held rather than reinterpreting it, and the two
// readings agree over every value that is an address, the address field being
// the low 36 bits of the integer (R-15-002a).
$[test]
function test_integer_write_clears_the_authority() -> unit = {
  C(Regno(1)) = default_cap;
  assert(C(Regno(1)).tag);
  X(Regno(1)) = 0x0000000012345678;
  assert(not(C(Regno(1)).tag));
  assert(C(Regno(1)).address == 0x012345678);
  assert(X(Regno(1)) == 0x0000000012345678);
  // An integer wider than the address space round-trips as an integer and
  // carries no authority, which is what keeps XLEN arithmetic intact.
  X(Regno(1)) = 0xfedcba9876543210;
  assert(X(Regno(1)) == 0xfedcba9876543210);
  assert(not(C(Regno(1)).tag));
}

// The two readings are of one register, so a capability write is visible to an
// integer read.
$[test]
function test_the_two_readings_are_one_register() -> unit = {
  let (_, c) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  C(Regno(5)) = c;
  assert(X(Regno(5))[cap_addr_width - 1 .. 0] == c.address);
  assert(C(Regno(5)) == c);
  // And the integer reading is the whole register: writing it back is the
  // identity, tag excepted.
  X(Regno(5)) = X(Regno(5));
  assert(C(Regno(5)) == clearTag(c));
}

// The zero register reads as the null capability whatever is written to it, and
// as integer zero.
$[test]
function test_zero_register_reads_null() -> unit = {
  C(Regno(0)) = default_cap;
  assert(C(Regno(0)) == null_cap);
  assert(X(Regno(0)) == zeros());
}

// The tag plane is keyed by granule, not by byte, and a data write clears the
// tag of every granule it covers, which is what makes tag clearing a property
// of the write path (R-15-007r, R-15-115a). The granule is the capability size,
// which the frozen format puts at 64 bits (R-15-203).
$[test]
function test_tag_plane_is_granule_keyed() -> unit = {
  let a : physaddrbits = 0x0000000080000000;
  assert(cap_size == 8);
  __WriteRAM_Meta(a, cap_size, true);
  assert(__ReadRAM_Meta(a, cap_size));
  // An address inside the same granule reads the same bit.
  assert(__ReadRAM_Meta(a + 4, 4));
  // The neighbouring granule is untouched.
  assert(not(__ReadRAM_Meta(a + cap_size, cap_size)));
  // A data write clears every granule it covers, one or many.
  __WriteRAM_Meta(a + cap_size, cap_size, true);
  assert(__ReadRAM_Meta(a + cap_size, cap_size));
  __WriteRAM_Meta(a, 4 * cap_size, false);
  assert(not(__ReadRAM_Meta(a, cap_size)));
  assert(not(__ReadRAM_Meta(a + cap_size, cap_size)));
}

// *****************************************************************
// Traps and checks.

// A trap saves the interrupted authority and installs the handler's: MEPCC
// comes to hold PCC with the faulting address, and the handler executes under
// MTCC (R-15-073, R-07-022).
$[test]
function test_a_trap_saves_and_installs_capabilities() -> unit = {
  let (_, handler) = setCapBounds(default_cap, 0x080000000, 0b0 @ 0x080001000);
  MTCC = setCapAddrChecked(handler, 0x0000000080000000);
  PCC = default_cap;
  let pc : xlenbits = 0x0000000000001000;
  let target = trap_handler(Exception(E_M_EnvCall()), pc, None(), None());
  assert(target == 0x0000000080000000);
  assert(nextPCC == MTCC);
  assert(MEPCC.tag);
  assert(MEPCC.address == 0x000001000);
  assert(capBoundsEqual(MEPCC, default_cap));
  assert(get_mepc() == pc);
}

// `mret` unseals a sentry into the executing PCC, which is what makes a return
// capability a control-flow target and nothing else (R-15-008, R-15-071).
$[test]
function test_mret_unseals_a_sentry() -> unit = {
  MEPCC = sealCap(setCapAddrChecked(default_cap, 0x0000000080000100), otype_sentry_bwd_bits);
  assert(isCapSealed(MEPCC));
  let target = prepare_xret_target();
  assert(target == 0x0000000080000100);
  assert(not(isCapSealed(nextPCC)));
  assert(nextPCC.tag);
}

// Every fetch is checked against PCC: its bounds on every granule, its tag,
// seal state and execute permission on the first.
//
// The last two assertions are the granule-width property: the second granule of
// the last instruction inside PCC's bounds is checked against the two bytes it
// reads, so an instruction wholly inside the bounds fetches, while a check that
// asked for a whole instruction there would refuse it (core/addr_checks.sail).
$[test]
function test_fetch_is_checked_against_pcc() -> unit = {
  let (_, c) = setCapBounds(default_cap, 0x080000000, 0b0 @ 0x080001000);
  PCC = setCapAddrChecked(c, 0x0000000080000000);
  assert(ext_fetch_check_pc(0x0000000080000000, 0x0000000080000000, min_instruction_bytes) == None());
  assert(ext_fetch_check_pc(0x0000000080000000, 0x0000000080000ffc, min_instruction_bytes) == None());
  assert(ext_fetch_check_pc(0x0000000080001000, 0x0000000080001000, min_instruction_bytes) == Some(CapEx_LengthViolation));
  assert(ext_fetch_check_pc(0x0000000080000ffc, 0x0000000080000ffe, 2) == None());
  assert(ext_fetch_check_pc(0x0000000080000ffc, 0x0000000080000ffe, min_instruction_bytes) == Some(CapEx_LengthViolation));
  PCC = clearTag(PCC);
  assert(ext_fetch_check_pc(0x0000000080000000, 0x0000000080000000, min_instruction_bytes) == Some(CapEx_TagViolation));
  PCC = default_cap;
}

// A data access is authorised by the capability in the base register it names,
// and by nothing else: there is no default data capability to fall back on and
// no mode in which the base register is an integer (R-15-001c).
$[test]
function test_a_store_needs_store_permission() -> unit = {
  let (_, c) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  let c = setCapAddrChecked(c, 0x0000000080000000);
  C(encdec_reg(0b00010)) = { c with perms = perms_r | perms_global_bit };
  match ext_data_get_addr(encdec_reg(0b00010), zeros(), Store(Data), 8) {
    Ext_DataAddr_Error((capEx, idx)) => {
      assert(capEx == CapEx_PermitStoreViolation);
      assert(idx == 0b000010);
    },
    Ext_DataAddr_OK(_) => assert(false, "a store without permit-store must fault"),
  };
  match ext_data_get_addr(encdec_reg(0b00010), zeros(), Load(Data), 8) {
    Ext_DataAddr_OK(va) => assert(bits_of(va) == 0x0000000080000000),
    Ext_DataAddr_Error(_) => assert(false, "an in-bounds load must be permitted"),
  };
  // An untagged base register is a fault at the access rather than at the
  // write that produced it (R-15-007h).
  C(encdec_reg(0b00010)) = int_to_cap(0x0000000080000000);
  match ext_data_get_addr(encdec_reg(0b00010), zeros(), Load(Data), 8) {
    Ext_DataAddr_Error((capEx, _)) => assert(capEx == CapEx_TagViolation),
    Ext_DataAddr_OK(_) => assert(false, "an untagged base register must fault"),
  };
}

// The permission setter is the lattice's, so a derivation lands on a codepoint
// or below one and never outside the enumeration (R-15-007b).
$[test]
function test_permissions_round_trip() -> unit = {
  let perms = getCapPerms(root_data_cap);
  assert(setCapPerms(root_data_cap, perms) == root_data_cap);
  let stripped = setCapPerms(root_data_cap, zeros());
  assert(getCapPerms(stripped) == zeros());
  assert(not(cap_permit_store(stripped)));
  assert(not(cap_permit_execute(stripped)));
  assert(capBoundsEqual(stripped, root_data_cap));
}
