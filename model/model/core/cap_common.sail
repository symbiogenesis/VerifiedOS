// =======================================================================================
// Ported from the CHERI-RISC-V Sail model (CTSRD-CHERI/sail-cheri-riscv @ bb07488d,
// src/cheri_cap_common.sail and src/cheri_types.sail), which is subject to the BSD
// two-clause licence in model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The capability algebra: decode, encode, bounds, permissions, sealing, and the
// monotone derivations. This is CHERI Concentrate as upstream states it,
// re-parameterized to the frozen 64+1-bit dialect: the bounds algorithm and the
// derivation semantics are unchanged and the field widths in cap_format.sail
// are what moved, which is why the narrowing owes a representation-correctness
// proof rather than a re-proof of CHERI (R-15-007, R-15-007a).
//
// Three upstream constructs are absent, each because the machine no longer has
// what it acts on. There is no default data capability to relocate, so the
// PCC and DDC relocation guards (constant `false` upstream) are not carried
// (R-15-001c). There is no capability-mode flag, the machine having one mode
// (R-15-001). And there are no software-defined permission bits, the field
// being an enumerated lattice with every codepoint architecturally interpreted
// (R-15-007n).
//
// One packing decision is the dialect's rather than upstream's, and it carries
// the same information. Upstream spends a bit flagging whether the exponent is
// stored *internally*, in bits stolen from the two mantissas; the frozen format
// has an explicit five-bit exponent field with no bit to spare beside it, so
// the flag rides the field itself, IEEE-754 fashion: a zero exponent field is
// the denormal case (effective exponent zero, length mantissa below its own
// half), and a field of *k* + 1 is the normalized case at effective exponent
// *k*. The effective exponent runs to `cap_max_E` = 30, so *k* + 1 runs to 31
// and the five bits are spent exactly.

// *****************************************************************
// Sealing.
//
// The four-bit object type names sixteen classes. Three are reserved by the
// architecture, the unsealed codepoint and the two sentry edges; the other
// thirteen are allocated at composition, with no runtime type allocation
// (R-15-007, R-07-002b).
//
// The sentry pair is the forward/backward-edge split, which is the platform's
// coarse-grained CFI: a forward-edge sentry is a call target and a backward-edge
// sentry is a return address, and `cjalr` admits each only in its own role, so a
// return capability may target only a return site (R-15-008, R-15-071).
// CHERIoT's interrupt-state variants are not among them: with asynchronous
// interrupt delivery deleted the three collapse to the plain sealed entry
// (R-15-070).
let reserved_otypes = 3
let otype_unsealed    = -1
let otype_sentry_fwd  = -2
let otype_sentry_bwd  = -3

let cap_max_otype = (pow2(cap_otype_width) - 1) - reserved_otypes

type CapAddrBits   = bits(cap_addr_width)
type CapAddrInt    = range(0, (2 ^ cap_addr_width) - 1)
type CapLenBits    = bits(cap_len_width)
type CapLen        = range(0, (2 ^ cap_len_width))
type CapOTypeBits  = bits(cap_otype_width)
type CapPermsCode  = bits(cap_perms_code_width)

let otype_unsealed_bits   : CapOTypeBits = 0b1111
let otype_sentry_fwd_bits : CapOTypeBits = 0b1110
let otype_sentry_bwd_bits : CapOTypeBits = 0b1101

// *****************************************************************
// Permissions.
//
// The five-bit field is **not** one flag per permission: the admitted sets are
// enumerated at freeze time, the enumeration is total over all 32 codepoints,
// and the residue is the bottom element, so the field has no illegal encoding
// to reject and its decode is a total function. That totality stands in place
// of the legal-permissions invariant a one-bit-per-permission field needs
// (R-15-007b, R-15-007a).
//
// Two combinations are excluded at the lattice rather than downstream of it, so
// each is a finite check over the table below rather than a property of one
// audited distribution: no admitted set holds both `Permit_Seal` and
// `Permit_Unseal` (R-15-007o), and no admitted set holds both `Permit_Store`
// and `Permit_Execute`, which makes W+X unrepresentable rather than merely
// underivable (R-15-007l).
//
// What software sees is the *expanded* bitmap: `cgetperm` answers in it and
// `candperm` masks with it. The field is the encoding and the bitmap is the
// architectural permission set, which is what lets a mask be an ordinary
// bitwise operand over a non-orthogonal field.
type cap_perms_width : Int = 12
let  cap_perms_width = sizeof(cap_perms_width)
type CapPermsBits = bits(cap_perms_width)

// Bit positions in the expanded bitmap, least significant first:
//
//   0 global                 4 store-capability      8  permit-execute
//   1 permit-load            5 store-local-capability 9  permit-seal
//   2 permit-store           6 load-global           10 permit-unseal
//   3 load-capability        7 load-mutable          11 access-system-registers
//
// The accessors below index these positions literally, so the layout is stated
// once here and read off there.

// The sixteen authority shapes, which bit 4 of the field crosses with
// local/global to give the 32 codepoints. Local versus global is orthogonal to
// the shape: it bounds where a capability may be *stored*, not what it
// authorises (R-15-074).
//
// The shapes are named here because a composed distribution names them: every
// capability the initial distribution hands out is one of these, and a curator
// reading the table should be able to find the root set of R-15-007p in it.
let perms_none          : CapPermsCode = 0b00000 // the bottom element
let perms_r             : CapPermsCode = 0b00001 // read data
let perms_rw            : CapPermsCode = 0b00010 // read and write data
let perms_r_cap         : CapPermsCode = 0b00011 // read capabilities, stripped
let perms_r_cap_lg      : CapPermsCode = 0b00100 // read capabilities, globality kept
let perms_r_cap_lm_lg   : CapPermsCode = 0b00101 // read capabilities, fully transitive
let perms_rw_cap        : CapPermsCode = 0b00110 // read and write capabilities, stripped
let perms_rw_cap_lg     : CapPermsCode = 0b00111
let perms_data_root     : CapPermsCode = 0b01000 // the store-side root's shape
let perms_stack         : CapPermsCode = 0b01001 // the one shape carrying store-local
let perms_x             : CapPermsCode = 0b01010 // execute, no capability loads
let perms_x_cap_lg      : CapPermsCode = 0b01011
let perms_code_root     : CapPermsCode = 0b01100 // the execute-side root's shape
let perms_code_root_asr : CapPermsCode = 0b01101 // and the privileged one
let perms_seal          : CapPermsCode = 0b01110 // mint a delegation
let perms_unseal        : CapPermsCode = 0b01111 // redeem one
let perms_global_bit    : CapPermsCode = 0b10000

/*!
 * THIS`(code)` is the architectural permission set the codepoint names, as the
 * expanded bitmap. It is total: every one of the 32 codepoints names a set.
 */
function perms_expand(code : CapPermsCode) -> CapPermsBits = {
  // Bit order, most significant first: ASR US SE X LM LG SL SC LC W R.
  let shape : bits(11) = match code[3 .. 0] {
    0b0000 => 0b000_0000_0000, // {}
    0b0001 => 0b000_0000_0001, // {R}
    0b0010 => 0b000_0000_0011, // {R,W}
    0b0011 => 0b000_0000_0101, // {R,LC}
    0b0100 => 0b000_0010_0101, // {R,LC,LG}
    0b0101 => 0b000_0110_0101, // {R,LC,LM,LG}
    0b0110 => 0b000_0000_1111, // {R,W,LC,SC}
    0b0111 => 0b000_0010_1111, // {R,W,LC,SC,LG}
    0b1000 => 0b000_0110_1111, // {R,W,LC,SC,LM,LG}
    0b1001 => 0b000_0111_1111, // {R,W,LC,SC,SL,LM,LG}
    0b1010 => 0b000_1000_0001, // {R,X}
    0b1011 => 0b000_1010_0101, // {R,X,LC,LG}
    0b1100 => 0b000_1110_0101, // {R,X,LC,LM,LG}
    0b1101 => 0b100_1110_0101, // {R,X,LC,LM,LG,ASR}
    0b1110 => 0b001_0000_0000, // {SE}
    0b1111 => 0b010_0000_0000, // {US}
  };
  shape @ code[4 .. 4]
}

function perms_count(p : CapPermsBits) -> int = {
  var n : int = 0;
  foreach (i from 0 to (cap_perms_width - 1)) {
    if bit_to_bool(p[i]) then n = n + 1
  };
  n
}

/*!
 * THIS`(want)` is the codepoint of the largest admitted permission set
 * contained in `want`, which is how a mask reaches a non-orthogonal field: the
 * result is a subset of the input, so `candperm` can only ever remove
 * authority whatever mask it is handed (R-15-007b, R-15-007h). Where two
 * admitted sets of equal size both fit, the lower codepoint wins; the order of
 * the table above is part of the freeze.
 */
function perms_narrow(want : CapPermsBits) -> CapPermsCode = {
  var best : CapPermsCode = perms_none;
  var best_n : int = -1;
  foreach (i from 0 to 31) {
    let code : CapPermsCode = to_bits_truncate(cap_perms_code_width, i);
    let set = perms_expand(code);
    let n = perms_count(set);
    if ((set & want) == set) & (n > best_n) then {
      best = code;
      best_n = n;
    }
  };
  best
}

// *****************************************************************

/*! A partially decompressed capability. `E` is the *effective* exponent and
 * `normalized` is the case flag the exponent field carries with it (above);
 * `T` is the full mantissa, whose high two bits the encoding derives.
 */
struct Capability = {
  tag        : bool,
  perms      : CapPermsCode,
  normalized : bool,
  E          : bits(cap_E_width),
  B          : bits(cap_mantissa_width),
  T          : bits(cap_mantissa_width),
  otype      : CapOTypeBits,
  address    : CapAddrBits,
}

// Reset E and T chosen to make top 2^cap_addr_width.
let cap_max_E   = cap_len_width - cap_mantissa_width + 1
let cap_reset_E : bits(cap_E_width) = to_bits(cap_max_E)
let cap_reset_T : bits(cap_mantissa_width) = 0b01 @ zeros(cap_mantissa_width - 2)

let null_cap : Capability = struct {
  tag        = false,
  perms      = perms_none,
  normalized = true,
  E          = cap_reset_E,
  B          = zeros(),
  T          = cap_reset_T,
  otype      = otype_unsealed_bits,
  address    = zeros(),
}

// The machine comes out of reset holding a **split** root set rather than one
// almighty capability: no admitted permission set holds both store and execute,
// so a single partition-bounded root is inexpressible and composition hands each
// core an execute-side and a store-side authority instead (R-15-007l,
// R-15-007p). `default_cap` is the execute-side one, which is what PCC and the
// trap capabilities reset to; `root_data_cap` is the store-side one, and it
// carries `store-local` because `candperm` can only remove, so a stack
// capability is derivable only from a root that already holds it.
let default_cap : Capability = struct {
  tag        = true,
  perms      = perms_code_root_asr | perms_global_bit,
  normalized = true,
  E          = cap_reset_E,
  B          = zeros(),
  T          = cap_reset_T,
  otype      = otype_unsealed_bits,
  address    = zeros(),
}

let root_data_cap : Capability = { default_cap with perms = perms_stack | perms_global_bit }

// The permission accessors. The struct carries the codepoint rather than a
// field per permission, so the only reachable permission sets are the admitted
// ones and no derivation can construct a set outside the enumeration
// (R-15-007b).
function getCapPerms(cap : Capability) -> CapPermsBits = perms_expand(cap.perms)

function cap_global(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[0])
function cap_permit_load(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[1])
function cap_permit_store(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[2])
function cap_load_cap(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[3])
function cap_store_cap(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[4])
function cap_store_local_cap(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[5])
function cap_load_global(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[6])
function cap_load_mutable(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[7])
function cap_permit_execute(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[8])
function cap_permit_seal(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[9])
function cap_permit_unseal(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[10])
function cap_access_system_regs(cap : Capability) -> bool = bit_to_bool(getCapPerms(cap)[11])

/*!
 * THIS`(cap, want)` narrows `cap`'s permissions to the largest admitted set
 * contained in `want`. It cannot widen: a mask naming a permission the input
 * does not hold has no effect, because the caller intersects first.
 */
function setCapPerms(cap : Capability, want : CapPermsBits) -> Capability =
  { cap with perms = perms_narrow(want) }

function encCapabilityToCapability(t : bool, c : EncCapability) -> Capability = {
  let ef = unsigned(c.E);
  // A zero exponent field is the denormal case: effective exponent zero and a
  // length mantissa below its own half, so the length's top two bits are 0b00.
  // Any other value is the normalized case at effective exponent ef - 1, where
  // the exponent was chosen to make those two bits 0b01.
  let normalized : bool = ef != 0;
  let E : bits(cap_E_width) = if normalized then to_bits_truncate(cap_E_width, ef - 1) else zeros();
  let lenMSBs : bits(2) = if normalized then 0b01 else 0b00;
  let Bs : bits(cap_mantissa_width) = c.B;
  // Reconstruct the top two bits of T from the top two bits of B, the length
  // MSBs implied by the case above, and the carry out of B + len that is
  // implied when T's low bits are below B's.
  let carry_out : bits(2) = if c.T <_u Bs[cap_mantissa_width - 3 .. 0] then 0b01 else 0b00;
  let Ttop2 = Bs[cap_mantissa_width - 1 .. cap_mantissa_width - 2] + lenMSBs + carry_out;
  struct {
    tag        = t,
    perms      = c.perms,
    normalized = normalized,
    E          = E,
    B          = Bs,
    T          = Ttop2 @ c.T,
    otype      = c.otype,
    address    = c.address,
  }
}

function capBitsToCapability(t : bool, c : CapBits) -> Capability =
  encCapabilityToCapability(t, capBitsToEncCapability(c))

function capToEncCap(cap : Capability) -> EncCapability = struct {
  perms   = cap.perms,
  otype   = cap.otype,
  E       = if cap.normalized then to_bits_truncate(cap_E_width, unsigned(cap.E) + 1) else zeros(),
  B       = cap.B,
  T       = cap.T[cap_mantissa_width - 3 .. 0],
  address = cap.address,
}

// Capability struct to bits, without the tag.
function capToBits(cap : Capability) -> CapBits = encCapToBits(capToEncCap(cap))

// Capabilities are xored with the bits of the null capability when they cross
// the memory interface, so that an all-zeroes granule reads back as canonical
// NULL even though NULL has bits set logically (R-15-182 relies on this). The
// null capability's address is zero, so the transform leaves the low 36 bits
// alone: an address reads back as itself through it, which is what makes the
// merged file's integer reading agree with its capability reading over every
// value that is an address (core/reg_type.sail).
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
  // from the top, as decoding assumes.
  let e = cap_max_E - count_leading_zeros(length[cap_addr_width .. cap_mantissa_width - 1]);
  // The denormal case is an exponent of zero whose length does not reach the
  // mantissa's half, which is the one case decoding cannot infer 0b01 for.
  let norm = (e != 0) | (length[cap_mantissa_width - 2] == 0b1);

  var Bbits : bits(cap_mantissa_width) = truncate(base >> e, cap_mantissa_width);
  var Tbits : bits(cap_mantissa_width) = truncate(top >> e, cap_mantissa_width);
  // Whether significant bits of base and top were lost, against a mask of the
  // bits the shift drops.
  let maskLo : CapLenBits = ~(ones(cap_len_width) << e);
  var lostSignificantBase : bool = unsigned(ext_base & maskLo) != 0;
  var lostSignificantTop  : bool = unsigned(top & maskLo) != 0;
  var incE : bool = false;

  if lostSignificantTop then {
    // T must be incremented to stay above top with the lost bits. It may wrap,
    // but if that makes B < T then decoding compensates.
    Tbits = Tbits + 1;
  };

  // Has the length overflowed? e was chosen so that the top two bits of the
  // length mantissa would be 0b01, and incrementing T can grow it past that.
  let len_mant = Tbits - Bbits;
  if len_mant[cap_mantissa_width - 1] == 0b1 then {
    incE = true;
    lostSignificantBase = lostSignificantBase | (Bbits[0] == 0b1);
    lostSignificantTop  = lostSignificantTop | (Tbits[0] == 0b1);
    Bbits = truncate(base >> (e + 1), cap_mantissa_width);
    let incT : range(0, 1) = if lostSignificantTop then 1 else 0;
    Tbits = truncate(top >> (e + 1), cap_mantissa_width) + incT;
  };

  let newE : bits(cap_E_width) = to_bits(if incE then e + 1 else e);
  let newCap = { cap with address = base, E = newE, B = Bbits, T = Tbits, normalized = norm };
  let exact = not(lostSignificantBase | lostSignificantTop);
  (exact, newCap)
}

function isCapSealed(cap : Capability) -> bool = cap.otype != otype_unsealed_bits

/*!
 * Tests whether the capability has a reserved otype (larger than [cap_max_otype]).
 * This includes both sealed (the two sentry edges) and unsealed (all ones) otypes.
 */
function hasReservedOType(cap : Capability) -> bool = unsigned(cap.otype) > cap_max_otype

/*! A sentry of either edge: a call target or a return address (R-15-071). */
function isSentry(cap : Capability) -> bool =
  (cap.otype == otype_sentry_fwd_bits) | (cap.otype == otype_sentry_bwd_bits)

function sealCap(cap : Capability, otyp : CapOTypeBits) -> Capability = { cap with otype = otyp }

function unsealCap(cap : Capability) -> Capability = { cap with otype = otype_unsealed_bits }

// The bounds and the address as an *effective* address, which is XLEN wide
// where the field is 36 (R-15-002a): an address reaches memory only through a
// capability, so the widening is a reading of the field and never a path to an
// access above 2^36.
function capAddrBits(c : Capability) -> xlenbits = zero_extend(c.address)

function getCapBaseBits(c : Capability) -> xlenbits = {
  let (base, _) = getCapBoundsBits(c);
  zero_extend(base)
}

function getCapBase(c : Capability) -> CapAddrInt = {
  let (base, _) = getCapBoundsBits(c);
  unsigned(base)
}

function getCapTopBits(c : Capability) -> CapLenBits = {
  let (_, top) = getCapBoundsBits(c);
  top
}

function getCapTop(c : Capability) -> CapLen = unsigned(getCapTopBits(c))

// The offset is a modular quantity in the address space's own width, so it
// wraps at 2^36 rather than at 2^64.
function getCapOffsetBits(c : Capability) -> xlenbits = {
  let (base, _) = getCapBoundsBits(c);
  zero_extend(c.address - base)
}

function getCapOffset(c : Capability) -> CapAddrInt = unsigned(getCapOffsetBits(c)[cap_addr_width - 1 .. 0])

function getCapLength(c : Capability) -> CapLen = {
  let (base, top) = getCapBounds(c);
  // For valid capabilities top >= base, but the representation admits top < base
  // for some untagged ones, where the length is taken as a wrapping quantity.
  assert(not(c.tag) | top >= base);
  let len = top - base;
  if len >= 0 then len else len + pow2(cap_len_width)
}

// The bounds check is stated over the *effective* address, which is wider than
// the address field, so an out-of-range integer fails it rather than aliasing
// into range: no path runs from an integer above 2^36 to an access (R-15-002a).
function inCapBounds(cap : Capability, addr : xlenbits, size : CapLen) -> bool = {
  let (base, top) = getCapBounds(cap);
  let a = unsigned(addr);
  (a >= base) & ((a + size) <= top)
}

function getCapCursor(cap : Capability) -> CapAddrInt = unsigned(cap.address)

function clearTagIf(cap : Capability, cond : bool) -> Capability =
  { cap with tag = cap.tag & not(cond) }

function clearTagIfSealed(cap : Capability) -> Capability = clearTagIf(cap, isCapSealed(cap))

function clearTag(cap : Capability) -> Capability = { cap with tag = false }

function capBoundsEqual(c1 : Capability, c2 : Capability) -> bool = {
  let (base1, top1) = getCapBounds(c1);
  let (base2, top2) = getCapBounds(c2);
  (base1 == base2) & (top1 == top2)
}

// An address above the implemented space is unrepresentable rather than
// truncated into it, which is the same disposition an unrepresentable bounds
// move takes: the result is untagged and faults at its next dereference
// (R-15-007h).
function addrInRange(addr : xlenbits) -> bool = addr[xlen - 1 .. cap_addr_width] == zeros()

function setCapAddr(c : Capability, addr : xlenbits) -> (bool, Capability) = {
  let newCap = { c with address = truncate(addr, cap_addr_width) };
  let representable = addrInRange(addr) & capBoundsEqual(c, newCap);
  (representable, newCap)
}

function setCapAddrChecked(c : Capability, addr : xlenbits) -> Capability = {
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

function setCapOffset(c : Capability, offset : xlenbits) -> (bool, Capability) = {
  let (base, _) = getCapBoundsBits(c);
  let newAddress = base + truncate(offset, cap_addr_width);
  let newCap = { c with address = newAddress };
  let representable = addrInRange(offset) & fastRepCheck(c, newAddress - c.address);
  (representable, newCap)
}

function setCapOffsetChecked(cap : Capability, offset : xlenbits) -> Capability = {
  let (representable, newCap) = setCapOffset(cap, offset);
  clearTagIf(newCap, not(representable) | isCapSealed(cap))
}

function incCapOffset(c : Capability, delta : xlenbits) -> (bool, Capability) = {
  let d : CapAddrBits = truncate(delta, cap_addr_width);
  let newAddress : CapAddrBits = c.address + d;
  let newCap = { c with address = newAddress };
  let representable = fastRepCheck(c, d);
  (representable, newCap)
}

function capToString(cap : Capability) -> string = {
  let len = getCapLength(cap);
  let len_str = bits_str(to_bits(cap_len_width + 3, len));
  // Print the architectural type, which is -1 for unsealed capabilities.
  let otype_str : xlenbits = if hasReservedOType(cap) then sign_extend(cap.otype) else zero_extend(cap.otype);
  " t:" ^ (if cap.tag then "1" else "0")
  ^ " s:" ^ (if isCapSealed(cap) then "1" else "0")
  ^ " perms:" ^ bits_str(getCapPerms(cap))
  ^ " type:" ^ bits_str(otype_str)
  ^ " address:" ^ bits_str(cap.address)
  ^ " base:" ^ bits_str(getCapBaseBits(cap))
  ^ " length:" ^ len_str
}

/*!
 * An integer at an address, carrying no authority. This is what an integer
 * write into the merged register file produces: the register's 64 data bits are
 * the integer, and the low 36 of them are the address field a capability
 * reading takes (R-15-007i, R-15-002a, core/reg_type.sail).
 */
function int_to_cap(v : xlenbits) -> Capability = memBitsToCapability(false, v)

/*!
 * The integer program counter of a capability. With PCC relocation folded out
 * (above) this is the address field, widened to an effective address.
 */
function cap_to_integer_pc(cap : Capability) -> xlenbits = capAddrBits(cap)

/*!
 * THIS`(cap, pc)` updates `cap` to reference the integer program counter `pc`,
 * clearing the tag if the result is unrepresentable or the input was sealed.
 */
function update_cap_with_integer_pc(cap : Capability, pc : xlenbits) -> Capability =
  setCapAddrChecked(cap, pc)
