// =======================================================================================
// Ported from the CHERI-RISC-V Sail model (CTSRD-CHERI/sail-cheri-riscv @ bb07488d,
// src/cheri_prelude_128.sail), which is subject to the BSD two-clause licence in
// model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The capability encoding: field widths and the packed in-memory form.
//
// This file carries the *parameters* of CHERI Concentrate and nothing else, so
// that the algebra in cap_common.sail is a re-parameterization of the upstream
// functions rather than a rewrite (R-15-007, R-15-007a). The widths are the
// frozen dialect's ([isa-profile.md](../../../docs/isa-profile.md) §4.1) and
// they spend the 64 bits exactly, which is why no reserved field, no
// software-defined permission field, no capability-mode flag, and no revocation
// colour appears below: each would need a bit the table has already spent
// (R-15-007n, R-15-001c, R-08-004b).
//
// The capability layer is core surface rather than an extension because the
// machine is purecap-only (R-15-001, R-15-003): there is no hybrid mode to gate,
// the capability *is* the register type (reg_type.sail), and an extension gate
// would be a configuration key with one admitted value. The extension directory
// carries the CHERI instruction surface; the format and its algebra live here.

// Width of a capability in bytes, excluding the validity tag. This is also the
// tag plane's granule: one tag per 64-bit SRAM granule (R-15-203,
// core/mem_metadata.sail).
type cap_size : Int = 8
let  cap_size = sizeof(cap_size)
type log2_cap_size : Int = 3
let  log2_cap_size = sizeof(log2_cap_size)
type CapBits = bits(8 * cap_size)

// The permission *field*: five bits naming one of 32 enumerated permission
// sets, not one bit per permission. The enumeration and its expansion are in
// cap_common.sail; what is here is the width it occupies (R-15-007b).
type cap_perms_code_width : Int = 5
let  cap_perms_code_width = sizeof(cap_perms_code_width)

// Sixteen sealed-capability classes, known at freeze time (R-15-007). Three of
// the sixteen are reserved by the architecture (unsealed and the two sentry
// edges, cap_common.sail); the other thirteen are composition-allocatable.
type cap_otype_width : Int = 4
let  cap_otype_width = sizeof(cap_otype_width)

// Bounds: a five-bit exponent, an eight-bit base mantissa, and a top mantissa
// stored in six bits with its high two derived, as CHERI Concentrate derives
// them (R-15-007, R-15-007c).
type cap_mantissa_width : Int = 8
let  cap_mantissa_width = sizeof(cap_mantissa_width)
type cap_E_width : Int = 5
let  cap_E_width = sizeof(cap_E_width)

// The address space is 36 bits (R-15-002a), so the address field is 36 bits and
// no access above 2^36 is representable. An *effective* address stays XLEN wide
// and reaches memory only through a capability, so an out-of-range integer
// fails the bounds check rather than aliasing into it (cap_common.sail,
// `inCapBounds`).
type cap_addr_width : Int = 36
let  cap_addr_width = sizeof(cap_addr_width)
type cap_len_width : Int = cap_addr_width + 1
let  cap_len_width = sizeof(cap_len_width)

// The packed form: everything but the tag, which is out of band.
//
// The address occupies the low 36 bits, which is what lets the merged register
// file's integer reading and its capability reading agree over every value that
// is an address: an integer read is the register's 64 data bits, and the low 36
// of them are the address field (R-15-007i, R-15-002a, core/reg_type.sail).
struct EncCapability = {
  perms   : bits(cap_perms_code_width),
  otype   : bits(cap_otype_width),
  E       : bits(cap_E_width),
  B       : bits(cap_mantissa_width),
  T       : bits(cap_mantissa_width - 2),
  address : bits(cap_addr_width),
}

function capBitsToEncCapability(c : CapBits) -> EncCapability = struct {
  perms   = c[63 .. 59],
  otype   = c[58 .. 55],
  E       = c[54 .. 50],
  B       = c[49 .. 42],
  T       = c[41 .. 36],
  address = c[35 .. 0],
}

function encCapToBits(cap : EncCapability) -> CapBits =
  cap.perms @
  cap.otype @
  cap.E @
  cap.B @
  cap.T @
  cap.address
