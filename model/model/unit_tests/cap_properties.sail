// =======================================================================================
// Ported from the CHERI-RISC-V verification artifacts (CTSRD-CHERI/sail-cheri-riscv-verif @ 4da8fd10,
// cap_properties.sail), which are subject to the BSD two-clause licence in
// model/LICENCE.cheri-verif.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The capability-helper property suite, transcribed to the frozen 64+1-bit
// dialect. Upstream states twenty-four `$property` functions over the 128-bit
// helpers this model transplanted (core/cap_common.sail) and then narrowed
// (core/cap_format.sail); what is here is each of them restated at the frozen
// widths where it can be, the premise the narrowing moved named where one was,
// and the properties the narrowing owes that upstream never stated.
//
// Each is a universal statement: Sail's SMT target emits one SMT-LIB file per
// `$[property]` asserting the negation, and an `unsat` answer is the solver's
// verdict over the whole input space. That is a quantifier the `$[test]`
// harness in test_capability.sail does not have, and it is still evidence about
// the Sail functions and not R-15-007a's representation-correctness proof, which
// stays owed. `run.py model smt` runs them; they are behind the project file's
// `smt_properties` variable so that no build's ctest waits on a solver.
//
// The premises the narrowing moved, before anything is run:
//
//   (a) Widths: the address is 36 bits and not XLEN, the mantissa 8 and not 14,
//       the exponent field 5 and not 6, the object type 4 and not 18, and the
//       capability 8 bytes and not 16, so `cap_max_E` is 30 (R-15-007,
//       R-15-002a).
//   (b) The internal-exponent flag is gone. Upstream spends a bit saying whether
//       the exponent is stored in bits stolen from the mantissas; the frozen
//       format carries the case in the exponent field itself, a zero field being
//       the denormal case at effective exponent zero and a field of k + 1 the
//       normalized case at effective exponent k. Upstream's `internal_E`,
//       `internal_E_take_bits`, and the `ie_correct` and `bot_correct` clauses
//       of its `encodableCap` therefore have no referent, and `encodableCap` is
//       redefined below from `encCapabilityToCapability`.
//   (c) There is no reserved field, no flags field and no software-defined
//       permission field (R-15-007n), and `cbuildcap` is not in the profile, so
//       `propBuildCapValidEq` loses its flag and reserved terms and is a
//       property of the algebra alone.
//   (d) Permissions are a five-bit enumerated code with a twelve-bit expanded
//       bitmap (R-15-007b), so `setCapPerms(c, getCapPerms(c)) == c` holds
//       because every code is admitted, and the permission properties below are
//       stated over codes and over the expansion.
//   (e) Sealing: `cap_max_otype` is 12, three of the sixteen codepoints being
//       reserved (R-15-007, R-15-071), so `propSealEncodable`'s valid type is an
//       object type at or below 12.
//   (f) Five upstream properties are unstatable because `getRepresentableLength`
//       and `getRepresentableAlignmentMask` left with `cram` and `crrl`:
//       propRepresentableSetBoundsExact, propRepresentableBoundsMono,
//       propRepresentableLengthIdempotent, propRepresentableMaskLengthAbsorb
//       and propSpecifiedRequiredAlignment. The contract they stated moved to
//       the static memory plan (R-15-007k, R-08-011) and is not restated here.
//   (g) The byte-exact threshold is the narrowing's own 128 bytes (R-15-007c),
//       which is stronger than upstream's 2^(MW-2) = 64, so both are stated.
//   (h) `propSetLSBs`'s slice is bits(cap_mantissa_width - 3) = bits(5).
//   (i) The offset an instruction hands `setCapOffset` and `incCapOffset` is
//       XLEN wide here and address wide upstream, `addrInRange` being part of
//       the representability answer (R-15-002a), so the two offset properties
//       quantify over `xlenbits`.
//   (j) `setCapBounds` preserves encodability only inside the containment
//       domain R-15-007a states, a requested top at or below 2^36: above it the
//       chosen exponent can reach 31, which the struct holds and the five-bit
//       field does not, so `propSetBoundsEncodable` carries that domain where
//       upstream's premise was `reqBase <= reqTop` alone. That is read off
//       `setCapBounds`'s own exponent choice and no probe pins it; the
//       containment property below is the one whose domain a probe pins.
//
// Per upstream property, what this file does with it. *Carried* means the
// property's own statement is upstream's, with only the types, the widths and
// the named constants under it moved; *restated* means the statement itself
// changed, a premise or a conjunct being added, dropped or replaced;
// *unstatable* means its subject is not in this model.
//
//   propEncodableCorrect              carried, over the redefined encodableCap
//   propDecodeEncodable               carried
//   propDefaultCapEncodable           carried
//   propNullCapEncodable              carried
//   propSetBoundsEncodable            restated over (j)
//   propSealEncodable                 carried, over (e)
//   propUnsealEncodable               carried
//   propSetBoundsValid                carried
//   propSetBoundsInstrValid           carried
//   propBaseLeqTop                    carried
//   propBuildCapValidEq               restated over (c) and (d)
//   propSetBounds                     carried
//   propSetOffset                     carried, over (i)
//   propIncOffset                     carried, over (i)
//   propSetLSBs                       carried, over (h)
//   propSetBoundsSmallExact           carried, with the stronger (g) beside it
//   propRepresentableSetBoundsExact   unstatable, (f)
//   propPowerOfTwoRepresentable       restated, n bounded to range(0, 36) (a)
//   propZeroLenRepresentable          carried
//   propRepresentableBoundsMono       unstatable, (f)
//   propRepresentableLengthIdempotent unstatable, (f)
//   propRepresentableMaskLengthAbsorb unstatable, (f)
//   propSetCurrentBoundsExact         carried
//   propSpecifiedRequiredAlignment    unstatable, (f)
//
// Upstream's `-->` and `<-->` sugar is the prelude's `==>` here, and its `EXTZ`
// is a concatenation with a zero bit or `zero_extend`.
//
// Two premises below carry a probe that drops each, so that the implications
// guarded by them are not read as vacuous. A probe is not carried as a
// property, a property here being a thing the file expects to prove, and its
// answer is satisfiability rather than a proof. The bodies are written out so a
// reader restores one and runs `run.py model smt --property` on it. Nothing in
// the tree holds either answer: what the landing's own run got is in the Q3a
// note of docs/completion-log.md, with the revision and the solver it was taken
// at.
//
//   $[property]
//   function probeAllEncodable(c : Capability) -> bool =
//     memBitsToCapability(c.tag, capToMemBits(c)) == c
//
//   $[property]
//   function probeContainsNoDomain(c : Capability, reqBase : CapAddrBits,
//                                  reqTop : CapLenBits) -> bool = {
//     let (_, newCap) = setCapBounds(c, reqBase, reqTop);
//     let (newBase, newTop) = getCapBounds(newCap);
//     let outDomain = unsigned(reqBase) <= unsigned(reqTop)
//                     & unsigned(reqTop) > pow2(cap_addr_width);
//     outDomain ==> (newBase <= unsigned(reqBase) & unsigned(reqTop) <= newTop)
//   }
//
// The first is the claim that `encodableCap` is identically true, since by
// propEncodableCorrect the round trip is the identity exactly where the
// predicate holds; the second is the claim that the containment domain (j) is
// decoration. propDefaultCapEncodable, propNullCapEncodable and
// propRootDataCapEncodable pin the predicate from the other side, each proving
// it at a concrete capability. R-15-007a says the tag is what makes the region
// above 2^36 unreachable rather than a repair, and the tag is outside what
// these properties quantify over.

// *****************************************************************
// Encodability.
//
// The Capability record is not the in-memory form: it carries the effective
// exponent with its case flag, and the full top mantissa whose high two bits
// the encoding derives. A record is *encodable* when those derived values are
// what decoding would have computed, so that the round trip through memory is
// the identity. Every capability manipulation below is shown to preserve it.

function encodableCap(c : Capability) -> bool = {
  // The exponent field spends its five bits exactly: a normalized exponent is
  // stored as k + 1, so it reaches cap_max_E and no further, and a denormal one
  // is stored as zero and so is zero.
  let expOk : bool = if c.normalized then unsigned(c.E) <= cap_max_E else unsigned(c.E) == 0;
  // The top two bits of T are the top two bits of B plus the length's implied
  // top two bits plus the carry out of the low bits, as decoding derives them.
  let lenMSBs : bits(2) = if c.normalized then 0b01 else 0b00;
  let Tlow = c.T[cap_mantissa_width - 3 .. 0];
  let Blow = c.B[cap_mantissa_width - 3 .. 0];
  let carry_out : bits(2) = if Tlow <_u Blow then 0b01 else 0b00;
  let Ttop2 = c.B[cap_mantissa_width - 1 .. cap_mantissa_width - 2] + lenMSBs + carry_out;
  expOk & (c.T[cap_mantissa_width - 1 .. cap_mantissa_width - 2] == Ttop2)
}

// A Capability is encodable iff the round trip through the in-memory form is
// the identity.
$[property]
function propEncodableCorrect(c : Capability) -> bool =
  encodableCap(c) == (memBitsToCapability(c.tag, capToMemBits(c)) == c)

// The decoding of any bit pattern is encodable.
$[property]
function propDecodeEncodable(capBits : CapBits, tag : bool) -> bool =
  encodableCap(memBitsToCapability(tag, capBits))

// Decode is total over the 64 bits and the bit-side round trip is the identity
// on every pattern: every granule names a capability and stores back as itself,
// which is what an integer read of a register rests on (R-15-007a, R-15-007i).
$[property]
function propMemBitsRoundTrip(capBits : CapBits, tag : bool) -> bool =
  capToMemBits(memBitsToCapability(tag, capBits)) == capBits

// The reset capabilities are encodable. These are also the non-vacuity check
// on encodableCap: each is a concrete value the solver evaluates.
$[property]
function propDefaultCapEncodable() -> bool = encodableCap(default_cap)

$[property]
function propNullCapEncodable() -> bool = encodableCap(null_cap)

$[property]
function propRootDataCapEncodable() -> bool = encodableCap(root_data_cap)

// Setting bounds inside the containment domain preserves encodability (j).
$[property]
function propSetBoundsEncodable(c : Capability, reqBase : CapAddrBits, reqTop : CapLenBits) -> bool = {
  let (_, c2) = setCapBounds(c, reqBase, reqTop);
  let sensibleRequest = unsigned(reqBase) <= unsigned(reqTop) & unsigned(reqTop) <= pow2(cap_addr_width);
  (encodableCap(c) & sensibleRequest) ==> encodableCap(c2)
}

// Sealing with a valid object type preserves encodability (e).
$[property]
function propSealEncodable(c : Capability, otype : CapOTypeBits) -> bool = {
  let c2 = sealCap(c, otype);
  let validType = unsigned(otype) <= cap_max_otype;
  (encodableCap(c) & validType) ==> encodableCap(c2)
}

// Unsealing preserves encodability.
$[property]
function propUnsealEncodable(c : Capability) -> bool =
  encodableCap(c) ==> encodableCap(unsealCap(c))

// Other capability manipulations change neither the bounds nor the object
// type, and so preserve encodability trivially.

// *****************************************************************
// Valid bounds.
//
// Decoding normally ensures base <= top, but at the two highest exponents the
// most significant bits of B and T would land above the 36 and 37 bits the
// derived base and top have, and decoding assumes they are zero. validBounds
// names that assumption, read off getCapBoundsBits at the frozen widths: at
// cap_max_E the base is B's low six bits and the top T's low seven, and at
// cap_max_E - 1 the base is B's low seven. setCapBounds is shown never to
// produce a capability violating it when the requested top is at or below
// 2^36, the top of the reset capability, so for any encodable capability
// derived monotonically from the reset roots base <= top holds.

function validBounds(c : Capability) -> bool = {
  let Bmsb = c.B[cap_mantissa_width - 1];
  let Bmsb2 = c.B[cap_mantissa_width - 1 .. cap_mantissa_width - 2];
  let Tmsb = c.T[cap_mantissa_width - 1];
  if unsigned(c.E) > cap_max_E then false
  else if unsigned(c.E) == cap_max_E then Tmsb == bitzero & Bmsb2 == 0b00
  else if unsigned(c.E) == cap_max_E - 1 then Bmsb == bitzero
  else true
}

// The reset capability has valid bounds, which is validBounds' own non-vacuity
// check.
$[property]
function propDefaultCapValidBounds() -> bool = validBounds(default_cap) & validBounds(root_data_cap)

// setCapBounds produces valid bounds if base <= top <= 2^36.
$[property]
function propSetBoundsValid(c : Capability, reqBase : CapAddrBits, reqTop : CapLenBits) -> bool = {
  let (_, c2) = setCapBounds(c, reqBase, reqTop);
  let sensibleReq = unsigned(reqBase) <= unsigned(reqTop) & unsigned(reqTop) <= pow2(cap_addr_width);
  sensibleReq ==> validBounds(c2)
}

// In instructions, setCapBounds is used with the address as the base and a
// length added to it, which guarantees base <= top, so valid bounds follow from
// top <= 2^36 alone; that is what the instruction's check against the original
// top gives for every reachable capability.
$[property]
function propSetBoundsInstrValid(c : Capability, len : CapAddrBits) -> bool = {
  let newBase = c.address;
  let newTop : CapLenBits = (0b0 @ newBase) + (0b0 @ len);
  let (_, c2) = setCapBounds(c, newBase, newTop);
  let sensibleReq = unsigned(newTop) <= pow2(cap_addr_width);
  sensibleReq ==> validBounds(c2)
}

$[property]
function propBaseLeqTop(c : Capability) -> bool = {
  let (base, top) = getCapBounds(c);
  (encodableCap(c) & validBounds(c)) ==> (base <= top)
}

// For a capability with a valid bounds encoding, re-deriving it from an
// unsealed tagged authority by setting its bounds, its offset and its
// permissions recreates it exactly (c, d).
$[property]
function propBuildCapValidEq(c : Capability, auth : Capability) -> bool = {
  let (base, top) = getCapBoundsBits(c);
  let (_, c1) = setCapBounds(auth, base, top);
  let (_, c2) = setCapOffset(c1, getCapOffsetBits(c));
  let result = setCapPerms(c2, getCapPerms(c));
  let expected = { unsealCap(c) with tag = true };
  (encodableCap(c) & encodableCap(auth) & validBounds(c) & auth.tag & not(isCapSealed(auth)))
    ==> (result == expected)
}

// *****************************************************************
// Monotonicity and containment of setCapBounds.

// Monotonicity of setCapBounds, under the preconditions the bounds-setting
// instructions check (and assuming a reachable capability, one whose top is at
// or below 2^36).
$[property]
function propSetBounds(c : Capability, reqBase : CapAddrBits, reqTop : CapLenBits) -> bool = {
  let (origBase, origTop) = getCapBounds(c);
  let (exact, newCap) = setCapBounds(c, reqBase, reqTop);
  let (newBase, newTop) = getCapBounds(newCap);
  let reqBasei = unsigned(reqBase);
  let reqTopi = unsigned(reqTop);
  // exclude invalid bounds requests
  let baseBelowTop = reqBasei <= reqTopi;
  let reachableTop = reqTopi <= pow2(cap_addr_width);
  // exclude non-monotonic bounds requests
  let requestMonotonic = origBase <= reqBasei & reqTopi <= origTop;
  // the returned region includes the requested one
  let requestSatisfied = newBase <= reqBasei & reqTopi <= newTop;
  // the returned region does not exceed the original one
  let boundsMonotonic = origBase <= newBase & newTop <= origTop;
  // the exponent does not increase
  let expMonotonic = unsigned(newCap.E) <= unsigned(c.E);
  // exact is true iff the returned bounds are exactly the requested ones
  let exactCorrect = ((reqBasei == newBase) & (reqTopi == newTop)) == exact;
  (baseBelowTop ==> exactCorrect) &
  ((encodableCap(c) & baseBelowTop & reachableTop & requestMonotonic)
    ==> (requestSatisfied & boundsMonotonic & (validBounds(c) ==> expMonotonic)))
}

// The containment property with its domain, as R-15-007a states it: for a
// requested region whose top is at or below 2^36 the derived region contains
// it, whatever capability the bounds are set on. This is the edge case the
// register says the format's property harness owes.
$[property]
function propSetBoundsContains(c : Capability, reqBase : CapAddrBits, reqTop : CapLenBits) -> bool = {
  let (_, newCap) = setCapBounds(c, reqBase, reqTop);
  let (newBase, newTop) = getCapBounds(newCap);
  let inDomain = unsigned(reqBase) <= unsigned(reqTop) & unsigned(reqTop) <= pow2(cap_addr_width);
  inDomain ==> (newBase <= unsigned(reqBase) & unsigned(reqTop) <= newTop)
}

// Inside that domain setCapBounds never produces a malformed capability, one
// whose derived top is below its derived base (R-15-007a's malformed-set
// clause, over what the algebra can reach).
$[property]
function propSetBoundsWellFormed(c : Capability, reqBase : CapAddrBits, reqTop : CapLenBits) -> bool = {
  let (_, newCap) = setCapBounds(c, reqBase, reqTop);
  let (newBase, newTop) = getCapBounds(newCap);
  let inDomain = unsigned(reqBase) <= unsigned(reqTop) & unsigned(reqTop) <= pow2(cap_addr_width);
  inDomain ==> (newBase <= newTop)
}

// *****************************************************************
// Representability of address moves.

// fastRepCheck is sound: an increment it admits leaves the bounds where they
// were. setCapOffset and incCapOffset rest on this (R-15-007h).
$[property]
function propFastRepCheckSound(c : Capability, i : CapAddrBits) -> bool = {
  let moved = { c with address = c.address + i };
  fastRepCheck(c, i) ==> capBoundsEqual(c, moved)
}

// setCapOffset and incCapOffset do not change the bounds when the
// representability check succeeds (i).
$[property]
function propSetOffset(c : Capability, offset : xlenbits) -> bool = {
  let (origBase, origTop) = getCapBounds(c);
  let (representable, c2) = setCapOffset(c, offset);
  let (newBase, newTop) = getCapBounds(c2);
  representable ==> (newBase == origBase & newTop == origTop)
}

$[property]
function propIncOffset(c : Capability, delta : xlenbits) -> bool = {
  let (origBase, origTop) = getCapBounds(c);
  let (representable, c2) = incCapOffset(c, delta);
  let (newBase, newTop) = getCapBounds(c2);
  representable ==> (newBase == origBase & newTop == origTop)
}

// Modifying the low MW-3 bits of the address is always representable (h).
$[property]
function propSetLSBs(c : Capability, low : bits(cap_mantissa_width - 3)) -> bool = {
  let addr2 = [c.address with (cap_mantissa_width - 4) .. 0 = low];
  let c2 = { c with address = addr2 };
  let (origBase, origTop) = getCapBounds(c);
  let (newBase, newTop) = getCapBounds(c2);
  newBase == origBase & newTop == origTop
}

// *****************************************************************
// Exactness.

// Setting bounds to a length below 2^(MW-2) is always exact, at any base.
$[property]
function propSetBoundsSmallExact(c : Capability, len : CapAddrBits) -> bool = {
  let reqBase = c.address;
  let reqTop : CapLenBits = (0b0 @ reqBase) + (0b0 @ len);
  let (exact, c2) = setCapBounds(c, reqBase, reqTop);
  let (newBase, newTop) = getCapBoundsBits(c2);
  let lenSmall = unsigned(len) < pow2(cap_mantissa_width - 2);
  lenSmall ==> (exact & newBase == reqBase & newTop == reqTop)
}

// The narrowing's own threshold is stronger: byte-exact for every length below
// 128 at any base, the exponent being chosen so that the decoder knows the
// length mantissa's top two bits (g, R-15-007c). test_capability.sail checks the
// same claim at one base; this is every base.
$[property]
function propSetBoundsByteExact(c : Capability, len : CapAddrBits) -> bool = {
  let reqBase = c.address;
  let reqTop : CapLenBits = (0b0 @ reqBase) + (0b0 @ len);
  let (exact, c2) = setCapBounds(c, reqBase, reqTop);
  let (newBase, newTop) = getCapBoundsBits(c2);
  let lenSmall = unsigned(len) < pow2(cap_mantissa_width - 1);
  lenSmall ==> (exact & newBase == reqBase & newTop == reqTop)
}

// Naturally aligned bounds with a power-of-two length are always representable,
// up to and including the whole address space.
$[property]
function propPowerOfTwoRepresentable(c : Capability, n : range(0, cap_addr_width)) -> bool = {
  let one : CapLenBits = zero_extend(0b1);
  let len : CapLenBits = one << n;
  let alignmentMask = ~(len - 1);
  let base : CapAddrBits = c.address;
  let top : CapLenBits = (0b0 @ base) + len;
  let baseAligned = ((0b0 @ base) & alignmentMask) == (0b0 @ base);
  let (exact, c2) = setCapBounds(c, base, top);
  let (newBase, newTop) = getCapBoundsBits(c2);
  let boundsExact = exact & (c.address == newBase) & (top == newTop);
  baseAligned ==> boundsExact
}

// Zero-length bounds are representable at any base.
$[property]
function propZeroLenRepresentable(c : Capability) -> bool = {
  let (exact, c2) = setCapBounds(c, c.address, 0b0 @ c.address);
  let (newBase, newTop) = getCapBoundsBits(c2);
  exact & (newBase == c.address) & (newTop == 0b0 @ c.address)
}

// Setting the bounds of a capability to its current bounds does not change it,
// with one caveat: the instruction takes the address as the requested base, so
// the address is first moved to the base. The original bounds are assumed to
// have a canonical encoding, which rules out negative lengths.
$[property]
function propSetCurrentBoundsExact(c0 : Capability) -> bool = {
  // move the address to the base
  let (representable, c1) = setCapOffset(c0, zeros());
  // the length, in bit-vector arithmetic because getCapLength's integer modulo
  // is outside what the SMT backend implements
  let newLen2 : CapLenBits = {
    let (base1, top1) = getCapBoundsBits(c0);
    top1 - (0b0 @ base1)
  };
  // set the bounds to the current base and length
  let newBase2 = c1.address;
  let newTop2 : CapLenBits = (0b0 @ newBase2) + newLen2;
  let (exact, c2) = setCapBounds(c1, newBase2, newTop2);
  (encodableCap(c0) & validBounds(c0)) ==> (c1 == c2 & representable & exact)
}

// *****************************************************************
// The permission representation (R-15-007b).
//
// The field is an enumerated code and the architectural permission set is its
// expansion, so what is stated is the pair: the expansion is injective and the
// narrowing is its left inverse, the narrowing can only remove, the two lattice
// exclusions hold at every codepoint, and every strip the load path applies
// lands on a codepoint exactly.

// Every codepoint is recovered from its own expansion, so distinct codepoints
// name distinct sets and the enumeration wastes none of the 32.
$[property]
function propPermsNarrowInvertsExpand(code : CapPermsCode) -> bool =
  perms_narrow(perms_expand(code)) == code

// A mask can only remove: the narrowed set is contained in whatever was asked
// for (R-15-007b, R-15-007h).
$[property]
function propPermsNarrowContained(want : CapPermsBits) -> bool = {
  let got = perms_expand(perms_narrow(want));
  (got & want) == got
}

// The narrowing is the largest admitted subset: no admitted set contained in
// the request is larger than the one chosen.
$[property]
function propPermsNarrowLargest(want : CapPermsBits, other : CapPermsCode) -> bool = {
  let got = perms_expand(perms_narrow(want));
  let candidate = perms_expand(other);
  ((candidate & want) == candidate) ==> (perms_count(candidate) <= perms_count(got))
}

// No admitted set holds both Permit_Store and Permit_Execute (R-15-007l), and
// none holds both Permit_Seal and Permit_Unseal (R-15-007o).
$[property]
function propPermsLatticeExclusions(code : CapPermsCode) -> bool = {
  let set = perms_expand(code);
  not(bit_to_bool(set[2]) & bit_to_bool(set[8])) & not(bit_to_bool(set[9]) & bit_to_bool(set[10]))
}

// The load path's strips are exact (R-15-074): removing global, removing the
// three store permissions, or removing both from any admitted set lands on an
// admitted set rather than below one, so a read-only view of a structure yields
// exactly the read-only views of what it points at. The two masks are the ones
// `load_transitivity` applies as `keep_global` and `keep_mutable`
// (extensions/CHERI/cheri_mem.sail), restated here as literals: bit 0 of the
// expanded bitmap is the globality bit and bits 2, 4 and 5 are Permit_Store,
// Permit_Store_Capability and Permit_Store_Local, on the order `perms_expand`
// states (core/cap_common.sail). No rule holds the two sites together, so a
// change to the load path's masks leaves these three properties proving the
// strip that was. Nothing closes that here: what would close it is a checker
// pairing the mask literals at the two sites, and no rule under tools/vos
// names either identifier or either literal.
//
// One strip per property rather than three in one: each of these is a
// `perms_narrow` call, and `perms_narrow` is a thirty-two-way search whose
// term the SMT backend unrolls, so a property naming three of them costs more
// to emit than the three cost together.
$[property]
function propPermsStripGlobalExact(code : CapPermsCode) -> bool = {
  let stripped = perms_expand(code) & ~(0b0000_0000_0001);
  perms_expand(perms_narrow(stripped)) == stripped
}

$[property]
function propPermsStripStoreExact(code : CapPermsCode) -> bool = {
  let stripped = perms_expand(code) & ~(0b0000_0011_0100);
  perms_expand(perms_narrow(stripped)) == stripped
}

$[property]
function propPermsStripBothExact(code : CapPermsCode) -> bool = {
  let stripped = perms_expand(code) & ~(0b0000_0011_0101);
  perms_expand(perms_narrow(stripped)) == stripped
}

