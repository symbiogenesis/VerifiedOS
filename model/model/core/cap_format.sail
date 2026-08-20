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
// that M0.6f's re-parameterization to the frozen 64+1-bit dialect (isa-profile
// §4.1) is a change to this file and to the field extraction below it, and not
// to the algebra in cap_common.sail. Until that batch lands these are ISAv9's
// 128-bit widths, deliberately: the M0.4 oracle (`cheri_riscv_sim_RV64`, built
// from the same upstream at the same pin) is the differential reference for the
// transplant, and it can only be one if the two models agree on the format.
//
// The capability layer is core surface rather than an extension because the
// machine is purecap-only (R-15-001, R-15-003): there is no hybrid mode to gate,
// the capability *is* the register type (reg_type.sail), and an extension gate
// would be a configuration key with one admitted value. The extension directory
// carries the CHERI instruction surface; the format and its algebra live here.

// Width of a capability in bytes, excluding the validity tag.
type cap_size : Int = 16
let  cap_size = sizeof(cap_size)
type log2_cap_size : Int = 4
let  log2_cap_size = sizeof(log2_cap_size)
type CapBits = bits(8 * cap_size)

// Architectural permissions carried as one bit each.
type cap_hperms_width : Int = 12
let  cap_hperms_width = sizeof(cap_hperms_width)
// Software-defined permissions. Excluded by the frozen profile (R-15-007n);
// they go with the re-parameterization rather than ahead of it.
type cap_uperms_width : Int = 4
let  cap_uperms_width = sizeof(cap_uperms_width)
type cap_otype_width : Int = 18
let  cap_otype_width = sizeof(cap_otype_width)
type cap_reserved_width : Int = 2
let  cap_reserved_width = sizeof(cap_reserved_width)
// The capability-mode flag. Hybrid mode is excluded (R-15-001); the field is
// carried here for oracle agreement and deleted with the dialect in M0.6f.
type cap_flags_width : Int = 1
let  cap_flags_width = sizeof(cap_flags_width)
type cap_mantissa_width : Int = 14
let  cap_mantissa_width = sizeof(cap_mantissa_width)
type cap_E_width : Int = 6
let  cap_E_width = sizeof(cap_E_width)
type cap_addr_width : Int = xlen
let  cap_addr_width = sizeof(cap_addr_width)
type cap_len_width : Int = cap_addr_width + 1
let  cap_len_width = sizeof(cap_len_width)

// Bits of B and T given up to the internal exponent.
type internal_E_take_bits : Int = 3
let  internal_E_take_bits = sizeof(internal_E_take_bits)

// The packed form: everything but the tag, which is out of band.
struct EncCapability = {
  perms      : bits(cap_uperms_width + cap_hperms_width),
  otype      : bits(cap_otype_width),
  reserved   : bits(cap_reserved_width),
  flags      : bits(cap_flags_width),
  internal_E : bits(1),
  T          : bits(cap_mantissa_width - 2),
  B          : bits(cap_mantissa_width),
  address    : bits(cap_addr_width),
}

function capBitsToEncCapability(c : CapBits) -> EncCapability = struct {
  perms      = c[127 .. 112],
  reserved   = c[111 .. 110],
  flags      = c[109 .. 109],
  otype      = c[108 .. 91],
  internal_E = c[90 .. 90],
  T          = c[89 .. 78],
  B          = c[77 .. 64],
  address    = c[63 .. 0],
}

function encCapToBits(cap : EncCapability) -> CapBits =
  cap.perms @
  cap.reserved @
  cap.flags @
  cap.otype @
  cap.internal_E @
  cap.T @
  cap.B @
  cap.address
