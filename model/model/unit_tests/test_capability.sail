// Properties of the capability encoding (core/cap_format.sail) and of the
// algebra over it (core/cap_common.sail).
//
// These are the transplant's standing regression rather than its proof. The
// representation-correctness obligation R-15-007a books (encode/decode round
// trip, field extraction, derivation of base and top, decode total over the
// bounds encoding) is a proof over statements of this shape, and until it is
// discharged these are what a re-parameterization of the field widths is
// checked against: M0.6f changes cap_format.sail and this file must still
// pass, or the change moved the algebra and not only the parameters.

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

// Encoding and decoding round-trip on the two capabilities the model resets
// from, tag included.
$[test]
function test_encode_decode_round_trips() -> unit = {
  assert(capBitsToCapability(false, capToBits(null_cap)) == null_cap);
  assert(capBitsToCapability(true, capToBits(default_cap)) == default_cap);
}

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
  let base : CapAddrBits = 0x0000000080000000;
  let top : CapLenBits = (0b0 @ base) + 4096;
  let (exact, c) = setCapBounds(default_cap, base, top);
  assert(exact);
  let (b, t) = getCapBounds(c);
  assert(b == unsigned(base));
  assert(t == unsigned(top));
}

// Below the mantissa threshold the bounds are byte-exact, which is what makes
// a narrow to a small object representable rather than rounded outward
// (R-15-007c). At these field widths the threshold is far above five bytes.
$[test]
function test_small_bounds_are_byte_exact() -> unit = {
  let base : CapAddrBits = 0x0000000080000003;
  let top : CapLenBits = (0b0 @ base) + 5;
  let (exact, c) = setCapBounds(default_cap, base, top);
  assert(exact);
  let (b, t) = getCapBounds(c);
  assert(b == unsigned(base));
  assert(t == unsigned(top));
  assert(getCapLength(c) == 5);
}

// Moving the address outside the representable region yields an untagged
// result rather than a trap: a failed derivation is a data result that faults
// at its next dereference (R-15-007h). A move that stays inside keeps the tag.
$[test]
function test_unrepresentable_address_clears_the_tag() -> unit = {
  let base : CapAddrBits = 0x0000000080000000;
  let (_, c) = setCapBounds(default_cap, base, (0b0 @ base) + 4096);
  assert(c.tag);
  let moved = setCapAddrChecked(c, zeros());
  assert(not(moved.tag));
  let near = setCapAddrChecked(c, base + 8);
  assert(near.tag);
  assert(capBoundsEqual(near, c));
}

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

// The register file is one file read two ways: `C(r)` is the capability and
// `X(r)` is its address field (R-15-007i). Writing an integer over a register
// destroys the authority it held rather than reinterpreting it.
$[test]
function test_integer_write_clears_the_authority() -> unit = {
  C(Regno(1)) = default_cap;
  assert(C(Regno(1)).tag);
  X(Regno(1)) = 0x0000000012345678;
  assert(not(C(Regno(1)).tag));
  assert(C(Regno(1)).address == 0x0000000012345678);
  assert(X(Regno(1)) == 0x0000000012345678);
}

// The two readings are of one register, so a capability write is visible to an
// integer read at its address field.
$[test]
function test_the_two_readings_are_one_register() -> unit = {
  let (_, c) = setCapBounds(default_cap, 0x0000000080000000, 0b0 @ 0x0000000080001000);
  C(Regno(5)) = c;
  assert(X(Regno(5)) == c.address);
  assert(C(Regno(5)) == c);
}

// The zero register reads as the null capability whatever is written to it.
$[test]
function test_zero_register_reads_null() -> unit = {
  C(Regno(0)) = default_cap;
  assert(C(Regno(0)) == null_cap);
  assert(X(Regno(0)) == zeros());
}

// The tag plane is keyed by granule, not by byte, and a data write clears the
// tag of every granule it covers, which is what makes tag clearing a property
// of the write path (R-15-007r, R-15-115a). The granule is the capability size
// while the format is ISAv9's; M0.6f narrows both together (R-15-203).
$[test]
function test_tag_plane_is_granule_keyed() -> unit = {
  let a : physaddrbits = 0x0000000080000000;
  __WriteRAM_Meta(a, cap_size, true);
  assert(__ReadRAM_Meta(a, cap_size));
  // An address inside the same granule reads the same bit.
  assert(__ReadRAM_Meta(a + 8, 8));
  // The neighbouring granule is untouched.
  assert(not(__ReadRAM_Meta(a + cap_size, cap_size)));
  // A data write clears every granule it covers, one or many.
  __WriteRAM_Meta(a + cap_size, cap_size, true);
  assert(__ReadRAM_Meta(a + cap_size, cap_size));
  __WriteRAM_Meta(a, 4 * cap_size, false);
  assert(not(__ReadRAM_Meta(a, cap_size)));
  assert(not(__ReadRAM_Meta(a + cap_size, cap_size)));
}

// A trap saves the interrupted authority and installs the handler's: MEPCC
// comes to hold PCC with the faulting address, and the handler executes under
// MTCC (R-15-073, R-07-022).
$[test]
function test_a_trap_saves_and_installs_capabilities() -> unit = {
  let (_, handler) = setCapBounds(default_cap, 0x0000000080000000, 0b0 @ 0x0000000080001000);
  MTCC = setCapAddrChecked(handler, 0x0000000080000000);
  PCC = default_cap;
  let pc : xlenbits = 0x0000000000001000;
  let target = trap_handler(Exception(E_M_EnvCall()), pc, None(), None());
  assert(target == 0x0000000080000000);
  assert(nextPCC == MTCC);
  assert(MEPCC.tag);
  assert(MEPCC.address == pc);
  assert(capBoundsEqual(MEPCC, default_cap));
  assert(get_mepc() == pc);
}

// `mret` unseals a sentry into the executing PCC, which is what makes a return
// capability a control-flow target and nothing else (R-15-008, R-15-071).
$[test]
function test_mret_unseals_a_sentry() -> unit = {
  MEPCC = sealCap(setCapAddrChecked(default_cap, 0x0000000080000100), otype_sentry_bits);
  assert(isCapSealed(MEPCC));
  let target = prepare_xret_target();
  assert(target == 0x0000000080000100);
  assert(not(isCapSealed(nextPCC)));
  assert(nextPCC.tag);
}

// Every fetch is checked against PCC: its bounds on every granule, its tag,
// seal state and execute permission on the first.
$[test]
function test_fetch_is_checked_against_pcc() -> unit = {
  let (_, c) = setCapBounds(default_cap, 0x0000000080000000, 0b0 @ 0x0000000080001000);
  PCC = setCapAddrChecked(c, 0x0000000080000000);
  assert(ext_fetch_check_pc(0x0000000080000000, 0x0000000080000000) == None());
  assert(ext_fetch_check_pc(0x0000000080000000, 0x0000000080000ffc) == None());
  assert(ext_fetch_check_pc(0x0000000080001000, 0x0000000080001000) == Some(CapEx_LengthViolation));
  PCC = clearTag(PCC);
  assert(ext_fetch_check_pc(0x0000000080000000, 0x0000000080000000) == Some(CapEx_TagViolation));
  PCC = default_cap;
}

// A data access is authorised by the capability in the base register it names,
// and by nothing else: there is no default data capability to fall back on
// (R-15-001c).
$[test]
function test_a_store_needs_store_permission() -> unit = {
  // The capability-mode arm is the one the profile keeps; the integer-mode arm
  // beside it goes with DDC in M0.6f (core/addr_checks.sail).
  PCC = setCapFlags(default_cap, 0b1);
  let (_, c) = setCapBounds(default_cap, 0x0000000080000000, 0b0 @ 0x0000000080001000);
  let c = setCapAddrChecked(c, 0x0000000080000000);
  C(encdec_reg(0b00010)) = { c with permit_store = false };
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
  PCC = default_cap;
}

// A derivation that would widen bounds or add permissions is not expressible
// through the setters: `setCapPerms` takes the permission bits it is given, so
// monotonicity is the caller's obligation, but clearing is total and its
// result is what the lattice reading of the field will be stated over
// (R-15-007b). What is checked here is that the two directions agree.
$[test]
function test_permissions_round_trip() -> unit = {
  let perms = getCapPerms(default_cap);
  assert(setCapPerms(default_cap, perms) == default_cap);
  let stripped = setCapPerms(default_cap, zeros());
  assert(getCapPerms(stripped) == zeros());
  assert(not(stripped.permit_store));
  assert(not(stripped.permit_execute));
  assert(capBoundsEqual(stripped, default_cap));
}
