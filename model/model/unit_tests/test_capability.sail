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
