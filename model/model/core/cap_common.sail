// =======================================================================================
// Ported from the CHERI-RISC-V Sail model (CTSRD-CHERI/sail-cheri-riscv @ bb07488d,
// src/cheri_cap_common.sail and src/cheri_types.sail), which is subject to the BSD
// two-clause licence in model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The capability algebra: decode, encode, bounds, permissions, sealing, and the
// monotone derivations. This is CHERI Concentrate as upstream states it, ported
// to the Sail the curated tree is written in (0.20.2, no effect annotations,
// `--strict-var` and `--strict-bitvector`); the parameters it is instantiated at
// are in cap_format.sail.
//
// Two upstream constructs are not carried across, both dead at the source:
// `have_cheri_relocation` and its two guards are constant `false` upstream, so
// PCC and DDC relocation are folded out here rather than ported as unreachable
// branches (the profile has no DDC at all, R-15-002); and the effect annotations
// the old Sail carried have no counterpart in 0.20.

// Sealing is a property of the object type: all-ones is unsealed, and the top
// `reserved_otypes` codepoints are reserved rather than allocatable.
let reserved_otypes = 4
let otype_unsealed = -1
let otype_sentry   = -2 // sealed erstwhile or prospective PCC

let cap_max_otype = (pow2(cap_otype_width) - 1) - reserved_otypes

type cap_uperms_shift : Int = 15
let  cap_uperms_shift = sizeof(cap_uperms_shift)
type cap_perms_width : Int = cap_uperms_shift + cap_uperms_width
let  cap_perms_width = sizeof(cap_perms_width)

type CapAddrBits  = bits(cap_addr_width)
type CapAddrInt   = range(0, (2 ^ cap_addr_width) - 1)
type CapLenBits   = bits(cap_len_width)
type CapLen       = range(0, (2 ^ cap_len_width))
type CapPermsBits = bits(cap_perms_width)
type CapFlagsBits = bits(cap_flags_width)
type CapOTypeBits = bits(cap_otype_width)

// Reset E and T chosen to make top 2^cap_addr_width.
let cap_max_E   = cap_len_width - cap_mantissa_width + 1
let cap_reset_E : bits(cap_E_width) = to_bits(cap_max_E)
let cap_reset_T : bits(cap_mantissa_width) = 0b01 @ zeros(cap_mantissa_width - 2)

let otype_unsealed_bits : CapOTypeBits = ones()
let otype_sentry_bits   : CapOTypeBits = ones() - 1

/*! A partially decompressed capability. E, B, T and otype are not present in
 * all encodings and are populated by [encCapabilityToCapability].
 */
struct Capability = {
  tag                    : bool,
  uperms                 : bits(cap_uperms_width),
  permit_set_CID         : bool,
  access_system_regs     : bool,
  permit_unseal          : bool,
  permit_cinvoke         : bool,
  permit_seal            : bool,
  permit_store_local_cap : bool,
  permit_store_cap       : bool,
  permit_load_cap        : bool,
  permit_store           : bool,
  permit_load            : bool,
  permit_execute         : bool,
  global                 : bool,
  reserved               : bits(cap_reserved_width),
  flag_cap_mode          : bool,
  internal_E             : bool,
  E                      : bits(cap_E_width),
  B                      : bits(cap_mantissa_width),
  T                      : bits(cap_mantissa_width),
  otype                  : CapOTypeBits,
  address                : CapAddrBits,
}

let null_cap : Capability = struct {
  tag                    = false,
  uperms                 = zeros(),
  permit_set_CID         = false,
  access_system_regs     = false,
  permit_unseal          = false,
  permit_cinvoke         = false,
  permit_seal            = false,
  permit_store_local_cap = false,
  permit_store_cap       = false,
  permit_load_cap        = false,
  permit_store           = false,
  permit_load            = false,
  permit_execute         = false,
  global                 = false,
  reserved               = zeros(),
  flag_cap_mode          = false,
  internal_E             = true,
  E                      = cap_reset_E,
  B                      = zeros(),
  T                      = cap_reset_T,
  otype                  = otype_unsealed_bits,
  address                = zeros(),
}

let default_cap : Capability = struct {
  tag                    = true,
  uperms                 = ones(),
  permit_set_CID         = true,
  access_system_regs     = true,
  permit_unseal          = true,
  permit_cinvoke         = true,
  permit_seal            = true,
  permit_store_local_cap = true,
  permit_store_cap       = true,
  permit_load_cap        = true,
  permit_store           = true,
  permit_load            = true,
  permit_execute         = true,
  global                 = true,
  reserved               = zeros(),
  flag_cap_mode          = false,
  internal_E             = true,
  E                      = cap_reset_E,
  B                      = zeros(),
  T                      = cap_reset_T,
  otype                  = otype_unsealed_bits,
  address                = zeros(),
}

function getCapHardPerms(cap : Capability) -> bits(cap_hperms_width) =
   (bool_to_bit(cap.permit_set_CID)
  @ bool_to_bit(cap.access_system_regs)
  @ bool_to_bit(cap.permit_unseal)
  @ bool_to_bit(cap.permit_cinvoke)
  @ bool_to_bit(cap.permit_seal)
  @ bool_to_bit(cap.permit_store_local_cap)
  @ bool_to_bit(cap.permit_store_cap)
  @ bool_to_bit(cap.permit_load_cap)
  @ bool_to_bit(cap.permit_store)
  @ bool_to_bit(cap.permit_load)
  @ bool_to_bit(cap.permit_execute)
  @ bool_to_bit(cap.global))

function encCapabilityToCapability(t : bool, c : EncCapability) -> Capability = {
  let internal_E : bool = bit_to_bool(c.internal_E);
  var E : bits(cap_E_width) = zeros();
  var Bs : bits(cap_mantissa_width) = zeros();
  var T : bits(cap_mantissa_width - 2) = zeros();
  var lenMSBs : bits(2) = zeros();
  if internal_E then {
    E = c.T[internal_E_take_bits - 1 .. 0] @ c.B[internal_E_take_bits - 1 .. 0];
    // Exponent chosen so that the length MSBs are 0b01.
    lenMSBs = 0b01;
    T = c.T[cap_mantissa_width - 3 .. 3] @ zeros(internal_E_take_bits);
    Bs = c.B[cap_mantissa_width - 1 .. 3] @ zeros(internal_E_take_bits);
  } else {
    // Exponent zero.
    lenMSBs = 0b00;
    T = c.T;
    Bs = c.B;
  };
  // Reconstruct the top two bits of T from the top two bits of B, the length
  // MSBs implied by the format above, and the carry out of B + len that is
  // implied when T is below B.
  let carry_out : bits(2) = if T <_u Bs[cap_mantissa_width - 3 .. 0] then 0b01 else 0b00;
  let Ttop2 = Bs[cap_mantissa_width - 1 .. cap_mantissa_width - 2] + lenMSBs + carry_out;
  struct {
    tag                    = t,
    uperms                 = c.perms[cap_hperms_width + cap_uperms_width - 1 .. cap_hperms_width],
    permit_set_CID         = bit_to_bool(c.perms[11]),
    access_system_regs     = bit_to_bool(c.perms[10]),
    permit_unseal          = bit_to_bool(c.perms[9]),
    permit_cinvoke         = bit_to_bool(c.perms[8]),
    permit_seal            = bit_to_bool(c.perms[7]),
    permit_store_local_cap = bit_to_bool(c.perms[6]),
    permit_store_cap       = bit_to_bool(c.perms[5]),
    permit_load_cap        = bit_to_bool(c.perms[4]),
    permit_store           = bit_to_bool(c.perms[3]),
    permit_load            = bit_to_bool(c.perms[2]),
    permit_execute         = bit_to_bool(c.perms[1]),
    global                 = bit_to_bool(c.perms[0]),
    reserved               = c.reserved,
    flag_cap_mode          = bit_to_bool(c.flags[0]),
    internal_E             = internal_E,
    E                      = E,
    B                      = Bs,
    T                      = Ttop2 @ T,
    otype                  = c.otype,
    address                = c.address,
  }
}

function capBitsToCapability(t : bool, c : CapBits) -> Capability =
  encCapabilityToCapability(t, capBitsToEncCapability(c))

function capToEncCap(cap : Capability) -> EncCapability = {
  let t_hi : bits(cap_mantissa_width - 2 - internal_E_take_bits) =
    cap.T[cap_mantissa_width - 3 .. internal_E_take_bits];
  let b_hi : bits(cap_mantissa_width - internal_E_take_bits) =
    cap.B[cap_mantissa_width - 1 .. internal_E_take_bits];
  var t_lo : bits(internal_E_take_bits) = cap.T[internal_E_take_bits - 1 .. 0];
  var b_lo : bits(internal_E_take_bits) = cap.B[internal_E_take_bits - 1 .. 0];
  if cap.internal_E then {
    t_lo = cap.E[2 * internal_E_take_bits - 1 .. internal_E_take_bits];
    b_lo = cap.E[internal_E_take_bits - 1 .. 0];
  };
  struct {
    perms      = cap.uperms @ getCapHardPerms(cap),
    reserved   = cap.reserved,
    flags      = bool_to_bit(cap.flag_cap_mode),
    otype      = cap.otype,
    internal_E = bool_to_bit(cap.internal_E),
    T          = t_hi @ t_lo,
    B          = b_hi @ b_lo,
    address    = cap.address,
  }
}

// Capability struct to bits, without the tag.
function capToBits(cap : Capability) -> CapBits = encCapToBits(capToEncCap(cap))

// Capabilities are xored with the bits of the null capability when they cross
// the memory interface, so that an all-zeroes granule reads back as canonical
// NULL even though NULL has bits set logically (R-15-182 relies on this).
let null_cap_bits : CapBits = capToBits(null_cap)

function capToMemBits(cap : Capability) -> CapBits = capToBits(cap) ^ null_cap_bits

function memBitsToCapability(tag : bool, b : CapBits) -> Capability =
  capBitsToCapability(tag, b ^ null_cap_bits)

function getCapBoundsBits(c : Capability) -> (CapAddrBits, CapLenBits) = {
  let E = min(cap_max_E, unsigned(c.E));
  let a : CapAddrBits = c.address;
  // The bits needed for the top correction and the representable limit.
  let a3 = truncate(a >> (E + cap_mantissa_width - 3), 3);
  let B3 = truncateLSB(c.B, 3);
  let T3 = truncateLSB(c.T, 3);
  let R3 = B3 - 0b001; // wraps
  // Do address, base and top lie in the R-aligned region above the one holding R?
  let aHi = if a3 <_u R3 then 1 else 0;
  let bHi = if B3 <_u R3 then 1 else 0;
  let tHi = if T3 <_u R3 then 1 else 0;
  // Region corrections for top and base relative to a.
  let correction_base = bHi - aHi;
  let correction_top  = tHi - aHi;
  let a_top = a >> (E + cap_mantissa_width);
  let base : CapLenBits = truncate((a_top + correction_base) @ c.B @ zeros(E), cap_len_width);
  var top  : CapLenBits = truncate((a_top + correction_top)  @ c.T @ zeros(E), cap_len_width);
  // If base and top are more than an address space apart, invert the MSB of
  // top: that corrects the case where the representable space wraps.
  let base2 : bits(2) = 0b0 @ base[cap_addr_width - 1 .. cap_addr_width - 1];
  let top2  : bits(2) = top[cap_addr_width .. cap_addr_width - 1];
  if (E < (cap_max_E - 1)) & (unsigned(top2 - base2) > 1) then {
    top[cap_addr_width] = ~(top[cap_addr_width]);
  };
  (base[cap_addr_width - 1 .. 0], top)
}

function getCapBounds(cap : Capability) -> (CapAddrInt, CapLen) = {
  let (base, top) = getCapBoundsBits(cap);
  (unsigned(base), unsigned(top))
}

// The 'ideal' setCapBounds of the CHERI Concentrate paper.
function setCapBounds(cap : Capability, base : CapAddrBits, top : CapLenBits) -> (bool, Capability) = {
  let ext_base : CapLenBits = 0b0 @ base;
  let length = top - ext_base;
  // Choose an exponent that puts the most significant bit of the length second
  // from the top, as decoding assumes. The bottom MW bits are the ie = 0 case.
  let e = cap_max_E - count_leading_zeros(length[cap_addr_width .. cap_mantissa_width - 1]);
  // Use the internal exponent if e is non-zero, or if e is zero but the implied
  // bit of the length is not (the denormal versus normal case).
  let ie = (e != 0) | (length[cap_mantissa_width - 2] == 0b1);

  // The non-ie e == 0 case is exact, so the relevant bits extract directly.
  var Bbits : bits(cap_mantissa_width) = truncate(base, cap_mantissa_width);
  var Tbits : bits(cap_mantissa_width) = truncate(top, cap_mantissa_width);
  var lostSignificantTop : bool = false;
  var lostSignificantBase : bool = false;
  var incE : bool = false;

  if ie then {
    // Three bits of each of B and T are given up to the exponent.
    var B_ie : bits(cap_mantissa_width - 3) = truncate(base >> (e + 3), cap_mantissa_width - 3);
    var T_ie : bits(cap_mantissa_width - 3) = truncate(top >> (e + 3), cap_mantissa_width - 3);

    // Whether significant bits of base and top were lost, against a mask of the
    // bits that go (including the three taken for the exponent).
    let maskLo : CapLenBits = zero_extend(ones(e + 3));
    lostSignificantBase = unsigned(ext_base & maskLo) != 0;
    lostSignificantTop  = unsigned(top & maskLo) != 0;

    if lostSignificantTop then {
      // T must be incremented to stay above top with the lost bits. It may wrap,
      // but if that makes B < T then decoding compensates.
      T_ie = T_ie + 1;
    };

    // Has the length overflowed? e was chosen so that the top two bits of the
    // length would be 0b01, but incrementing T or losing bits of base can grow it.
    let len_ie = T_ie - B_ie;
    if len_ie[cap_mantissa_width - 4] == 0b1 then {
      // Length overflow: increment E and recompute T and B against it.
      incE = true;

      lostSignificantBase = lostSignificantBase | (B_ie[0] == 0b1);
      lostSignificantTop  = lostSignificantTop | (T_ie[0] == 0b1);

      B_ie = truncate(base >> (e + 4), cap_mantissa_width - 3);
      let incT : range(0, 1) = if lostSignificantTop then 1 else 0;
      T_ie = truncate(top >> (e + 4), cap_mantissa_width - 3) + incT;
    };

    Bbits = B_ie @ 0b000;
    Tbits = T_ie @ 0b000;
  };
  let newE : bits(cap_E_width) = to_bits(if incE then e + 1 else e);
  let newCap = { cap with address = base, E = newE, B = Bbits, T = Tbits, internal_E = ie };
  let exact = not(lostSignificantBase | lostSignificantTop);
  (exact, newCap)
}

function getCapPerms(cap : Capability) -> CapPermsBits = {
  let perms : bits(cap_uperms_shift) = zero_extend(getCapHardPerms(cap));
  cap.uperms @ perms
}

function setCapPerms(cap : Capability, perms : CapPermsBits) -> Capability =
  { cap with
    uperms                 = truncate(perms >> cap_uperms_shift, cap_uperms_width),
    // 14 .. 12 reserved: ignored.
    permit_set_CID         = bit_to_bool(perms[11]),
    access_system_regs     = bit_to_bool(perms[10]),
    permit_unseal          = bit_to_bool(perms[9]),
    permit_cinvoke         = bit_to_bool(perms[8]),
    permit_seal            = bit_to_bool(perms[7]),
    permit_store_local_cap = bit_to_bool(perms[6]),
    permit_store_cap       = bit_to_bool(perms[5]),
    permit_load_cap        = bit_to_bool(perms[4]),
    permit_store           = bit_to_bool(perms[3]),
    permit_load            = bit_to_bool(perms[2]),
    permit_execute         = bit_to_bool(perms[1]),
    global                 = bit_to_bool(perms[0]),
  }

/*! Gets the architecture specific capability flags for a given capability. */
function getCapFlags(cap : Capability) -> CapFlagsBits = bool_to_bit(cap.flag_cap_mode)

/*!
 * THIS`(cap, flags)` sets the architecture specific capability flags on `cap`
 * to `flags` and returns the result as a new capability.
 */
function setCapFlags(cap : Capability, flags : CapFlagsBits) -> Capability =
  { cap with flag_cap_mode = bit_to_bool(flags[0]) }

function isCapSealed(cap : Capability) -> bool = signed(cap.otype) != otype_unsealed

/*!
 * Tests whether the capability has a reserved otype (larger than [cap_max_otype]).
 * This includes both sealed (e.g. sentry) and unsealed (all ones) otypes.
 */
function hasReservedOType(cap : Capability) -> bool = unsigned(cap.otype) > cap_max_otype

function sealCap(cap : Capability, otyp : CapOTypeBits) -> Capability = { cap with otype = otyp }

function unsealCap(cap : Capability) -> Capability = { cap with otype = otype_unsealed_bits }

function getCapBaseBits(c : Capability) -> CapAddrBits = {
  let (base, _) = getCapBoundsBits(c);
  base
}

function getCapBase(c : Capability) -> CapAddrInt = unsigned(getCapBaseBits(c))

function getCapTopBits(c : Capability) -> CapLenBits = {
  let (_, top) = getCapBoundsBits(c);
  top
}

function getCapTop(c : Capability) -> CapLen = unsigned(getCapTopBits(c))

function getCapOffsetBits(c : Capability) -> CapAddrBits = {
  let base : CapAddrBits = getCapBaseBits(c);
  c.address - base
}

function getCapOffset(c : Capability) -> CapAddrInt = unsigned(getCapOffsetBits(c))

function getCapLength(c : Capability) -> CapLen = {
  let (base, top) = getCapBounds(c);
  // For valid capabilities top >= base, but the representation admits top < base
  // for some untagged ones, where the length is taken as a 65-bit quantity that
  // wraps.
  assert(not(c.tag) | top >= base);
  let len = top - base;
  if len >= 0 then len else len + pow2(cap_len_width)
}

function inCapBounds(cap : Capability, addr : CapAddrBits, size : CapLen) -> bool = {
  let (base, top) = getCapBounds(cap);
  let a = unsigned(addr);
  (a >= base) & ((a + size) <= top)
}

function getCapCursor(cap : Capability) -> CapAddrInt = unsigned(cap.address)

function int_to_cap(offset : CapAddrBits) -> Capability = { null_cap with address = offset }

function clearTagIf(cap : Capability, cond : bool) -> Capability =
  { cap with tag = cap.tag & not(cond) }

function clearTagIfSealed(cap : Capability) -> Capability = clearTagIf(cap, isCapSealed(cap))

function clearTag(cap : Capability) -> Capability = { cap with tag = false }

function capBoundsEqual(c1 : Capability, c2 : Capability) -> bool = {
  let (base1, top1) = getCapBounds(c1);
  let (base2, top2) = getCapBounds(c2);
  (base1 == base2) & (top1 == top2)
}

function setCapAddr(c : Capability, addr : CapAddrBits) -> (bool, Capability) = {
  let newCap = { c with address = addr };
  let representable = capBoundsEqual(c, newCap);
  (representable, newCap)
}

function setCapAddrChecked(c : Capability, addr : CapAddrBits) -> Capability = {
  let (representable, newCap) = setCapAddr(c, addr);
  clearTagIf(newCap, not(representable) | isCapSealed(c))
}

function fastRepCheck(c : Capability, i : CapAddrBits) -> bool = {
  let E = unsigned(c.E);
  if E >= cap_max_E - 2 then {
    true // the representable region is the whole address space
  } else {
    let i_top = signed(sail_arith_shiftright(i, E + cap_mantissa_width));
    let i_mid = truncate(i >> E, cap_mantissa_width);
    let a_mid = truncate(c.address >> E, cap_mantissa_width);
    let B3 = truncateLSB(c.B, 3);
    let R3 = B3 - 0b001;
    let R : bits(cap_mantissa_width) = R3 @ zeros(cap_mantissa_width - 3);
    let diff = R - a_mid;
    let diff1 = diff - 1;
    // i_top decides both whether the increment is in range (less than the size
    // of the representable region, 2^(E+MW)) and whether it is positive or
    // negative, so the cases of interest are i_top 0 and -1.
    if i_top == 0 then {
      i_mid <_u diff1
    } else if i_top == -1 then {
      (i_mid >=_u diff) & (R != a_mid)
    } else {
      false
    }
  }
}

function setCapOffset(c : Capability, offset : CapAddrBits) -> (bool, Capability) = {
  let base = getCapBaseBits(c);
  let newAddress = base + offset;
  let newCap = { c with address = newAddress };
  let representable = fastRepCheck(c, newAddress - c.address);
  (representable, newCap)
}

function setCapOffsetChecked(cap : Capability, offset : CapAddrBits) -> Capability = {
  let (representable, newCap) = setCapOffset(cap, offset);
  clearTagIf(newCap, not(representable) | isCapSealed(cap))
}

function incCapOffset(c : Capability, delta : CapAddrBits) -> (bool, Capability) = {
  let newAddress : CapAddrBits = c.address + delta;
  let newCap = { c with address = newAddress };
  let representable = fastRepCheck(c, delta);
  (representable, newCap)
}

function capToString(cap : Capability) -> string = {
  let len = getCapLength(cap);
  let len_str = bits_str(to_bits(cap_len_width + 3, len));
  // Print the architectural type, which is -1 for unsealed capabilities.
  let otype64 : CapAddrBits = if hasReservedOType(cap) then sign_extend(cap.otype) else zero_extend(cap.otype);
  " t:" ^ (if cap.tag then "1" else "0")
  ^ " s:" ^ (if isCapSealed(cap) then "1" else "0")
  ^ " perms:" ^ bits_str(0b0 @ getCapPerms(cap))
  ^ " type:" ^ bits_str(otype64)
  ^ " address:" ^ bits_str(cap.address)
  ^ " base:" ^ bits_str(getCapBaseBits(cap))
  ^ " length:" ^ len_str
}

function getRepresentableAlignmentMask(len : xlenbits) -> xlenbits = {
  let (_, c) = setCapBounds(default_cap, zeros(), 0b0 @ len);
  let e = min(unsigned(c.E), cap_max_E);
  let e2 = if c.internal_E then e + internal_E_take_bits else 0;
  ones(xlen - e2) @ zeros(e2)
}

function getRepresentableLength(len : xlenbits) -> xlenbits = {
  let m = getRepresentableAlignmentMask(len);
  (len + ~(m)) & m
}

/*!
 * The integer program counter of a capability. With PCC relocation folded out
 * (above) this is the address field.
 */
function cap_to_integer_pc(cap : Capability) -> xlenbits = cap.address

/*!
 * THIS`(cap, pc)` updates `cap` to reference the integer program counter `pc`,
 * clearing the tag if the result is unrepresentable or the input was sealed.
 */
function update_cap_with_integer_pc(cap : Capability, pc : xlenbits) -> Capability =
  setCapAddrChecked(cap, pc)
