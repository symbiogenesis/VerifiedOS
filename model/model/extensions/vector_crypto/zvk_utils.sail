// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

function zvk_valid_reg_overlap(rs : vregidx, rd : vregidx, emul_pow : int) -> bool = {
  let reg_group_size = if emul_pow > 0 then 2 ^ emul_pow else 1;
  let rs_int = unsigned(vregidx_bits(rs));
  let rd_int = unsigned(vregidx_bits(rd));
  (rs_int + reg_group_size <= rd_int) | (rd_int + reg_group_size <= rs_int)
}

function zvk_check_encdec(EGW : nat, EGS : nat1) -> bool = {
  let LMUL_pow = get_lmul_pow();
  let LMUL_times_VLEN = if LMUL_pow < 0 then vlen / (2 ^ abs_int(LMUL_pow)) else (2 ^ LMUL_pow) * vlen;
  let VLMAX = LMUL_times_VLEN / get_sew();
  // An out-of-bounds vstart (>= VLMAX) is reserved, whether it traps is configurable.
  let vstart_in_bounds : bool = match vstart_reserved_behavior {
    Vstart_Illegal => unsigned(vstart) < VLMAX,
    Vstart_Ignore  => true,
  };
  (unsigned(vl) % EGS == 0) & (unsigned(vstart) % EGS == 0) & LMUL_times_VLEN >= EGW & vstart_in_bounds
}

// Utility functions for Zvknh[ab]
// ----------------------------------------------------------------------

enum zvk_vsha2_funct6 = {ZVK_VSHA2CH_VV, ZVK_VSHA2CL_VV}

function zvknhab_check_encdec(vs2 : vregidx, vs1 : vregidx, vd: vregidx) -> bool = {
  let SEW      = get_sew();
  let LMUL_pow = get_lmul_pow();
  zvk_check_encdec(SEW, 4) & zvk_valid_reg_overlap(vs1, vd, LMUL_pow) & zvk_valid_reg_overlap(vs2, vd, LMUL_pow);
}

val zvk_sig0 : forall 'n, 'n in {32, 64} . (bits('n), int('n)) -> bits('n)
function zvk_sig0(x, SEW) = {
  match SEW {
    32 => ((x >>> 7) ^ (x >>> 18) ^ (x >> 3)),
    64 => ((x >>> 1) ^ (x >>>  8) ^ (x >> 7)),
  }
}

val zvk_sig1 : forall 'n, 'n in {32, 64} . (bits('n), int('n)) -> bits('n)
function zvk_sig1(x, SEW) = {
  match SEW {
    32 => ((x >>> 17) ^ (x >>> 19) ^ (x >> 10)),
    64 => ((x >>> 19) ^ (x >>> 61) ^ (x >>  6)),
  }
}

val zvk_sum0 : forall 'n, 'n in {32, 64} . (bits('n), int('n)) -> bits('n)
function zvk_sum0(x, SEW) = {
  match SEW {
    32 => ((x >>>  2) ^ (x >>> 13) ^ (x >>> 22)),
    64 => ((x >>> 28) ^ (x >>> 34) ^ (x >>> 39)),
  }
}

val zvk_sum1 : forall 'n, 'n in {32, 64} . (bits('n), int('n)) -> bits('n)
function zvk_sum1(x, SEW) = {
  match SEW {
    32 => ((x >>>  6) ^ (x >>> 11) ^ (x >>> 25)),
    64 => ((x >>> 14) ^ (x >>> 18) ^ (x >>> 41)),
  }
}

val zvk_ch : forall 'n, 'n >= 0. (bits('n), bits('n), bits('n)) -> bits('n)
function zvk_ch(x, y, z) = (x & y) ^ (~(x) & z)

val zvk_maj : forall 'n, 'n >= 0. (bits('n), bits('n), bits('n)) -> bits('n)
function zvk_maj(x, y, z) = (x & y) ^ (x & z) ^ (y & z)

// Utility functions for Zvkned
// ----------------------------------------------------------------------

enum zvk_vaesdf_funct6 = {ZVK_VAESDF_VV, ZVK_VAESDF_VS}
enum zvk_vaesdm_funct6 = {ZVK_VAESDM_VV, ZVK_VAESDM_VS}
enum zvk_vaesef_funct6 = {ZVK_VAESEF_VV, ZVK_VAESEF_VS}
enum zvk_vaesem_funct6 = {ZVK_VAESEM_VV, ZVK_VAESEM_VS}
