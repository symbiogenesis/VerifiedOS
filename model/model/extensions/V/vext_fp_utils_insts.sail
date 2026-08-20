// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// ******************************************************************************
// This file implements functions used by vector instructions.
// ******************************************************************************

// The rounding mode every vector floating-point instruction uses. Rounding is
// static here (R-15-083): the dynamic `frm` CSR went with scalar floating
// point (R-15-039) and RVV encodes no rounding-mode field, so round-to-nearest
// -ties-to-even is the mode, and the conversions that name round-toward-zero
// architecturally still pass their own mode to the softfloat interface.
let fp_static_rm : bits(3) = 0b000 // RNE

// Check for valid floating-point operation types: the element width. The
// rounding mode is not checked, there being no dynamic mode to be reserved.
function valid_fp_op(SEW : sew_bitsize) -> bool =
  // SEW=8 is valid for conversions between INT8 and FP16(vfncvt[.rtz].x[u].f.w, etc.)
  SEW >= 8 & SEW <= 64

// a. Normal check for floating-point instructions
function illegal_fp_normal(vd : vregidx, vm : bits(1), SEW : sew_bitsize) -> bool = {
  not(valid_vtype()) | not(valid_rd_mask(vd, vm)) | not(valid_fp_op(SEW))
}

// b. Masked check for floating-point instructions encoded with vm = 0
function illegal_fp_vd_masked(vd : vregidx, SEW : sew_bitsize) -> bool = {
  not(valid_vtype()) | vd == zvreg | not(valid_fp_op(SEW))
}

// c. Unmasked check for floating-point instructions encoded with vm = 1
function illegal_fp_vd_unmasked(SEW : sew_bitsize) -> bool = {
  not(valid_vtype()) | not(valid_fp_op(SEW))
}

// d. Variable width check for floating-point widening/narrowing instructions
function illegal_fp_variable_width(vd : vregidx, vm : bits(1), SEW : sew_bitsize, SEW_new : nat, LMUL_pow_new : int) -> bool = {
  not(valid_vtype()) | not(valid_rd_mask(vd, vm)) | not(valid_fp_op(SEW)) |
  not(valid_eew_emul(SEW_new, LMUL_pow_new))
}

// e. Normal check for floating-point reduction instructions
function illegal_fp_reduction(SEW : sew_bitsize) -> bool = {
  not(valid_vtype()) | not(valid_fp_op(SEW))
}

// f. Variable width check for floating-point widening reduction instructions
function illegal_fp_widening_reduction(SEW : sew_bitsize, EEW : nat) -> bool = {
  illegal_fp_reduction(SEW) | not(EEW >= 8 & EEW <= elen)
}

// Floating point classification. The per-width `f_is_*_{H,S,D}` definitions
// went with the scalar F/D instruction files (R-15-039); these are the same
// predicates over the Sail float library's width-generic ones.
val f_is_neg_inf : forall 'm, 'm in {16, 32, 64}. bits('m) -> bool
function f_is_neg_inf(xf) = float_is_negative(xf) & float_is_inf(xf)

val f_is_neg_norm : forall 'm, 'm in {16, 32, 64}. bits('m) -> bool
function f_is_neg_norm(xf) = float_is_negative(xf) & float_is_normal(xf)

val f_is_neg_subnorm : forall 'm, 'm in {16, 32, 64}. bits('m) -> bool
function f_is_neg_subnorm(xf) = float_is_negative(xf) & float_is_subnormal(xf)

val f_is_neg_zero : forall 'm, 'm in {16, 32, 64}. bits('m) -> bool
function f_is_neg_zero(xf) = float_is_negative(xf) & float_is_zero(xf)

val f_is_pos_zero : forall 'm, 'm in {16, 32, 64}. bits('m) -> bool
function f_is_pos_zero(xf) = float_is_positive(xf) & float_is_zero(xf)

val f_is_pos_subnorm : forall 'm, 'm in {16, 32, 64}. bits('m) -> bool
function f_is_pos_subnorm(xf) = float_is_positive(xf) & float_is_subnormal(xf)

val f_is_pos_norm : forall 'm, 'm in {16, 32, 64}. bits('m) -> bool
function f_is_pos_norm(xf) = float_is_positive(xf) & float_is_normal(xf)

val f_is_pos_inf : forall 'm, 'm in {16, 32, 64}. bits('m) -> bool
function f_is_pos_inf(xf) = float_is_positive(xf) & float_is_inf(xf)

val f_is_SNaN : forall 'm, 'm in {16, 32, 64}. bits('m) -> bool
function f_is_SNaN(xf) = float_is_snan(xf)

val f_is_QNaN : forall 'm, 'm in {16, 32, 64}. bits('m) -> bool
function f_is_QNaN(xf) = float_is_qnan(xf)

val f_is_NaN : forall 'm, 'm in {16, 32, 64}. bits('m) -> bool
function f_is_NaN(xf) = float_is_nan(xf)

// Scalar register shaping for floating point operations. The operand comes
// from the integer register file: with no `f0`-`f31` (R-15-039) a scalar
// floating-point value is a bit pattern in an integer register, which is what
// the soft-float-register calling convention R-15-040 books already assumes.
// The instructions that use this check `SEW <= xlen` in their illegal
// condition, so the low SEW bits are the whole operand.
val get_scalar_fp : forall 'n, 'n in {16, 32, 64}. (regidx, int('n)) -> bits('n)
function get_scalar_fp(rs1, SEW) = {
  assert(xlen >= SEW, "invalid vector floating-point operand width: XLEN < SEW");
  X(rs1)[SEW - 1 .. 0]
}

// Negate a floating point number: flip the sign bit, at any element width.
// The per-width `negate_{H,S,D}` went with the scalar F/D files (R-15-039).
val negate_fp : forall 'm, 'm in {16, 32, 64}. bits('m) -> bits('m)
function negate_fp(xf) = (0b1 @ zeros('m - 1)) ^ xf

// Floating point functions using softfloat interface
val fp_add: forall 'm, 'm in {16, 32, 64}. (bits(3), bits('m), bits('m)) -> bits('m)
function fp_add(rm_3b, op1, op2) = {
  let (_, result_val) : (bits_fflags, bits('m)) = match 'm {
    16  => riscv_f16Add(rm_3b, op1, op2),
    32  => riscv_f32Add(rm_3b, op1, op2),
    64  => riscv_f64Add(rm_3b, op1, op2)
  };
  result_val
}

val fp_sub: forall 'm, 'm in {16, 32, 64}. (bits(3), bits('m), bits('m)) -> bits('m)
function fp_sub(rm_3b, op1, op2) = {
  let (_, result_val) : (bits_fflags, bits('m)) = match 'm {
    16  => riscv_f16Sub(rm_3b, op1, op2),
    32  => riscv_f32Sub(rm_3b, op1, op2),
    64  => riscv_f64Sub(rm_3b, op1, op2)
  };
  result_val
}

val fp_min : forall 'm, 'm in {16, 32, 64}. (bits('m), bits('m)) -> bits('m)
function fp_min(op1, op2) = {
  let (_, op1_lt_op2) : (bits_fflags, bool) = match 'm {
    16  => riscv_f16Lt_quiet(op1, op2),
    32  => riscv_f32Lt_quiet(op1, op2),
    64  => riscv_f64Lt_quiet(op1, op2)
  };

  let result_val = if (f_is_NaN(op1) & f_is_NaN(op2)) then canonical_NaN('m)
                else if f_is_NaN(op1) then op2
                else if f_is_NaN(op2) then op1
                else if (f_is_neg_zero(op1) & f_is_pos_zero(op2)) then op1
                else if (f_is_neg_zero(op2) & f_is_pos_zero(op1)) then op2
                else if op1_lt_op2 then op1
                else op2;
  result_val
}

val fp_max : forall 'm, 'm in {16, 32, 64}. (bits('m), bits('m)) -> bits('m)
function fp_max(op1, op2) = {
  let (_, op1_lt_op2) : (bits_fflags, bool) = match 'm {
    16  => riscv_f16Lt_quiet(op1, op2),
    32  => riscv_f32Lt_quiet(op1, op2),
    64  => riscv_f64Lt_quiet(op1, op2)
  };

  let result_val = if (f_is_NaN(op1) & f_is_NaN(op2)) then canonical_NaN('m)
                else if f_is_NaN(op1) then op2
                else if f_is_NaN(op2) then op1
                else if (f_is_neg_zero(op1) & f_is_pos_zero(op2)) then op2
                else if (f_is_neg_zero(op2) & f_is_pos_zero(op1)) then op1
                else if op1_lt_op2 then op2
                else op1;
  result_val
}

val fp_eq : forall 'm, 'm in {16, 32, 64}. (bits('m), bits('m)) -> bool
function fp_eq(op1, op2) = {
  let (_, result_val) : (bits_fflags, bool) = match 'm {
    16  => riscv_f16Eq(op1, op2),
    32  => riscv_f32Eq(op1, op2),
    64  => riscv_f64Eq(op1, op2)
  };
  result_val
}

val fp_gt : forall 'm, 'm in {16, 32, 64}. (bits('m), bits('m)) -> bool
function fp_gt(op1, op2) = {
  let (invalid, temp_val) : (bits_fflags, bool) = match 'm {
    16  => riscv_f16Le(op1, op2),
    32  => riscv_f32Le(op1, op2),
    64  => riscv_f64Le(op1, op2)
  };
  // The invalid-operation flag decides the result here, so it is read where
  // the softfloat interface returns it rather than accrued: `fflags` is gone
  // with scalar floating point (R-15-039) and reaches no architectural state.
  let result_val = (if invalid == nvFlag() then false else not(temp_val));
  result_val
}

val fp_ge : forall 'm, 'm in {16, 32, 64}. (bits('m), bits('m)) -> bool
function fp_ge(op1, op2) = {
  let (invalid, temp_val) : (bits_fflags, bool) = match 'm {
    16  => riscv_f16Lt(op1, op2),
    32  => riscv_f32Lt(op1, op2),
    64  => riscv_f64Lt(op1, op2)
  };
  // As in fp_gt: read where returned, never accrued (R-15-039).
  let result_val = (if invalid == nvFlag() then false else not(temp_val));
  result_val
}

val fp_lt : forall 'm, 'm in {16, 32, 64}. (bits('m), bits('m)) -> bool
function fp_lt(op1, op2) = {
  let (_, result_val) : (bits_fflags, bool) = match 'm {
    16  => riscv_f16Lt(op1, op2),
    32  => riscv_f32Lt(op1, op2),
    64  => riscv_f64Lt(op1, op2)
  };
  result_val
}

val fp_le : forall 'm, 'm in {16, 32, 64}. (bits('m), bits('m)) -> bool
function fp_le(op1, op2) = {
  let (_, result_val) : (bits_fflags, bool) = match 'm {
    16  => riscv_f16Le(op1, op2),
    32  => riscv_f32Le(op1, op2),
    64  => riscv_f64Le(op1, op2)
  };
  result_val
}

val fp_mul : forall 'm, 'm in {16, 32, 64}. (bits(3), bits('m), bits('m)) -> bits('m)
function fp_mul(rm_3b, op1, op2) = {
  let (_, result_val) : (bits_fflags, bits('m)) = match 'm {
    16  => riscv_f16Mul(rm_3b, op1, op2),
    32  => riscv_f32Mul(rm_3b, op1, op2),
    64  => riscv_f64Mul(rm_3b, op1, op2)
  };
  result_val
}

val fp_div : forall 'm, 'm in {16, 32, 64}. (bits(3), bits('m), bits('m)) -> bits('m)
function fp_div(rm_3b, op1, op2) = {
  let (_, result_val) : (bits_fflags, bits('m)) = match 'm {
    16  => riscv_f16Div(rm_3b, op1, op2),
    32  => riscv_f32Div(rm_3b, op1, op2),
    64  => riscv_f64Div(rm_3b, op1, op2)
  };
  result_val
}

val fp_muladd : forall 'm, 'm in {16, 32, 64}. (bits(3), bits('m), bits('m), bits('m)) -> bits('m)
function fp_muladd(rm_3b, op1, op2, opadd) = {
  let (_, result_val) : (bits_fflags, bits('m)) = match 'm {
    16  => riscv_f16MulAdd(rm_3b, op1, op2, opadd),
    32  => riscv_f32MulAdd(rm_3b, op1, op2, opadd),
    64  => riscv_f64MulAdd(rm_3b, op1, op2, opadd)
  };
  result_val
}

val fp_nmuladd : forall 'm, 'm in {16, 32, 64}. (bits(3), bits('m), bits('m), bits('m)) -> bits('m)
function fp_nmuladd(rm_3b, op1, op2, opadd) = {
  let op1 = negate_fp(op1);
  let (_, result_val) : (bits_fflags, bits('m)) = match 'm {
    16  => riscv_f16MulAdd(rm_3b, op1, op2, opadd),
    32  => riscv_f32MulAdd(rm_3b, op1, op2, opadd),
    64  => riscv_f64MulAdd(rm_3b, op1, op2, opadd)
  };
  result_val
}

val fp_mulsub : forall 'm, 'm in {16, 32, 64}. (bits(3), bits('m), bits('m), bits('m)) -> bits('m)
function fp_mulsub(rm_3b, op1, op2, opsub) = {
  let opsub = negate_fp(opsub);
  let (_, result_val) : (bits_fflags, bits('m)) = match 'm {
    16  => riscv_f16MulAdd(rm_3b, op1, op2, opsub),
    32  => riscv_f32MulAdd(rm_3b, op1, op2, opsub),
    64  => riscv_f64MulAdd(rm_3b, op1, op2, opsub)
  };
  result_val
}

val fp_nmulsub : forall 'm, 'm in {16, 32, 64}. (bits(3), bits('m), bits('m), bits('m)) -> bits('m)
function fp_nmulsub(rm_3b, op1, op2, opsub) = {
  let opsub = negate_fp(opsub);
  let op1 = negate_fp(op1);
  let (_, result_val) : (bits_fflags, bits('m)) = match 'm {
    16  => riscv_f16MulAdd(rm_3b, op1, op2, opsub),
    32  => riscv_f32MulAdd(rm_3b, op1, op2, opsub),
    64  => riscv_f64MulAdd(rm_3b, op1, op2, opsub)
  };
  result_val
}

val fp_widen : forall 'm, 'm in {16, 32}. bits('m) -> bits('m * 2)
function fp_widen(nval) = {
  let rm_3b = fp_static_rm;
  let (_, wval) : (bits_fflags, bits('m * 2)) = match 'm {
    16 => riscv_f16ToF32(rm_3b, nval),
    32 => riscv_f32ToF64(rm_3b, nval)
  };
  wval
}

// Floating point functions without softfloat support
function riscv_f16ToI16(rm : bits_rm, v : bits_H) -> (bits_fflags, bits(16)) = {
  let (flag, sig32) = riscv_f16ToI32(rm, v);
  if signed(sig32) > signed(0b0 @ ones(15)) then (nvFlag(), 0b0 @ ones(15))
  else if signed(sig32) < signed(0b1 @ zeros(15)) then (nvFlag(), 0b1 @ zeros(15))
  else (flag, sig32[15 .. 0]);
}

function riscv_f16ToI8(rm : bits_rm, v : bits_H) -> (bits_fflags, bits(8)) = {
  let (flag, sig32) = riscv_f16ToI32(rm, v);
  if signed(sig32) > signed(0b0 @ ones(7)) then (nvFlag(), 0b0 @ ones(7))
  else if signed(sig32) < signed(0b1 @ zeros(7)) then (nvFlag(), 0b1 @ zeros(7))
  else (flag, sig32[7 .. 0]);
}

function riscv_f32ToI16(rm : bits_rm, v : bits_S) -> (bits_fflags, bits(16)) = {
  let (flag, sig32) = riscv_f32ToI32(rm, v);
  if signed(sig32) > signed(0b0 @ ones(15)) then (nvFlag(), 0b0 @ ones(15))
  else if signed(sig32) < signed(0b1 @ zeros(15)) then (nvFlag(), 0b1 @ zeros(15))
  else (flag, sig32[15 .. 0]);
}

function riscv_f16ToUi16(rm : bits_rm, v : bits_H) -> (bits_fflags, bits(16)) = {
  let (flag, sig32) = riscv_f16ToUi32(rm, v);
  if unsigned(sig32) > unsigned(ones(16)) then (nvFlag(), ones(16))
  else (flag, sig32[15 .. 0]);
}

function riscv_f16ToUi8(rm : bits_rm, v : bits_H) -> (bits_fflags, bits(8)) = {
  let (flag, sig32) = riscv_f16ToUi32(rm, v);
  if unsigned(sig32) > unsigned(ones(8)) then (nvFlag(), ones(8))
  else (flag, sig32[7 .. 0]);
}

function riscv_f32ToUi16(rm : bits_rm, v : bits_S) -> (bits_fflags, bits(16)) = {
  let (flag, sig32) = riscv_f32ToUi32(rm, v);
  if unsigned(sig32) > unsigned(ones(16)) then (nvFlag(), ones(16))
  else (flag, sig32[15 .. 0]);
}

val rsqrt7 : forall 'm, 'm in {16, 32, 64}. (bits('m), bool) -> bits_D
function rsqrt7 (v, sub) = {
  let (sig, exp, sign, e, s) : (bits(64), bits(64), bits(1), {5, 8, 11}, {10, 23, 52}) = match 'm {
    16 => (zero_extend(64, v[9 .. 0]), zero_extend(64, v[14 .. 10]), [v[15]], 5, 10),
    32 => (zero_extend(64, v[22 .. 0]), zero_extend(64, v[30 .. 23]), [v[31]], 8, 23),
    64 => (zero_extend(64, v[51 .. 0]), zero_extend(64, v[62 .. 52]), [v[63]], 11, 52)
  };
  let table : vector(128, int) = [
      52, 51, 50, 48, 47, 46, 44, 43,
      42, 41, 40, 39, 38, 36, 35, 34,
      33, 32, 31, 30, 30, 29, 28, 27,
      26, 25, 24, 23, 23, 22, 21, 20,
      19, 19, 18, 17, 16, 16, 15, 14,
      14, 13, 12, 12, 11, 10, 10, 9,
      9, 8, 7, 7, 6, 6, 5, 4,
      4, 3, 3, 2, 2, 1, 1, 0,
      127, 125, 123, 121, 119, 118, 116, 114,
      113, 111, 109, 108, 106, 105, 103, 102,
      100, 99, 97, 96, 95, 93, 92, 91,
      90, 88, 87, 86, 85, 84, 83, 82,
      80, 79, 78, 77, 76, 75, 74, 73,
      72, 71, 70, 70, 69, 68, 67, 66,
      65, 64, 63, 63, 62, 61, 60, 59,
      59, 58, 57, 56, 56, 55, 54, 53];

  let (normalized_exp, normalized_sig) =
      if sub then {
        let nr_leadingzeros = count_leading_zeros(sig[s - 1 .. 0]);
        assert(nr_leadingzeros >= 0);
        (to_bits_unsafe(64, (0 - nr_leadingzeros)), zero_extend(64, sig[(s - 1) .. 0] << (1 + nr_leadingzeros)))
      } else {
        (exp, sig)
      };

  let idx : nat = match 'm {
    16 => unsigned([normalized_exp[0]] @ normalized_sig[9 .. 4]),
    32 => unsigned([normalized_exp[0]] @ normalized_sig[22 .. 17]),
    64 => unsigned([normalized_exp[0]] @ normalized_sig[51 .. 46])
  };
  assert(idx >= 0 & idx < 128);
  let out_sig = to_bits_unsafe(s, table[(127 - idx)]) << (s - 7);
  let out_exp = to_bits_unsafe(e, quot_round_zero(3 * (2 ^ (e - 1) - 1) - 1 - signed(normalized_exp), 2));
  zero_extend(64, sign @ out_exp @ out_sig)
}

function riscv_f16Rsqrte7(_rm : bits_rm, v : bits_H) -> (bits_fflags, bits_H) = {
  // TODO: Replace magic numbers here with `canonical_NaN()` etc.
  match float_classify(v) {
    float_class_negative_inf       => (nvFlag(), 0x7e00),
    float_class_negative_normal    => (nvFlag(), 0x7e00),
    float_class_negative_subnormal => (nvFlag(), 0x7e00),
    float_class_snan               => (nvFlag(), 0x7e00),
    float_class_qnan               => (zeros(5), 0x7e00),
    float_class_negative_zero      => (dzFlag(), 0xfc00),
    float_class_positive_zero      => (dzFlag(), 0x7c00),
    float_class_positive_inf       => (zeros(5), 0x0000),
    float_class_positive_subnormal => (zeros(5), rsqrt7(v, true)[15 .. 0]),
    float_class_positive_normal    => (zeros(5), rsqrt7(v, false)[15 .. 0])
  }
}

function riscv_f32Rsqrte7(_rm : bits_rm, v : bits_S) -> (bits_fflags, bits_S) = {
  match float_classify(v) {
    float_class_negative_inf       => (nvFlag(), 0x7fc00000),
    float_class_negative_normal    => (nvFlag(), 0x7fc00000),
    float_class_negative_subnormal => (nvFlag(), 0x7fc00000),
    float_class_snan               => (nvFlag(), 0x7fc00000),
    float_class_qnan               => (zeros(5), 0x7fc00000),
    float_class_negative_zero      => (dzFlag(), 0xff800000),
    float_class_positive_zero      => (dzFlag(), 0x7f800000),
    float_class_positive_inf       => (zeros(5), 0x00000000),
    float_class_positive_subnormal => (zeros(5), rsqrt7(v, true)[31 .. 0]),
    float_class_positive_normal    => (zeros(5), rsqrt7(v, false)[31 .. 0])
  }
}

function riscv_f64Rsqrte7(_rm : bits_rm, v : bits_D) -> (bits_fflags, bits_D) = {
  match float_classify(v) {
    float_class_negative_inf       => (nvFlag(), 0x7ff8000000000000),
    float_class_negative_normal    => (nvFlag(), 0x7ff8000000000000),
    float_class_negative_subnormal => (nvFlag(), 0x7ff8000000000000),
    float_class_snan               => (nvFlag(), 0x7ff8000000000000),
    float_class_qnan               => (zeros(5), 0x7ff8000000000000),
    float_class_negative_zero      => (dzFlag(), 0xfff0000000000000),
    float_class_positive_zero      => (dzFlag(), 0x7ff0000000000000),
    float_class_positive_inf       => (zeros(5), zeros(64)),
    float_class_positive_subnormal => (zeros(5), rsqrt7(v, true)[63 .. 0]),
    float_class_positive_normal    => (zeros(5), rsqrt7(v, false)[63 .. 0])
  }
}

val recip7 : forall 'm, 'm in {16, 32, 64}. (bits('m), bits(3), bool) -> (bool, bits_D)
function recip7 (v, rm_3b, sub) = {
  let (sig, exp, sign, e, s) : (bits(64), bits(64), bits(1), {5, 8, 11}, {10, 23, 52}) = match 'm {
    16 => (zero_extend(64, v[9 .. 0]), zero_extend(64, v[14 .. 10]), [v[15]], 5, 10),
    32 => (zero_extend(64, v[22 .. 0]), zero_extend(64, v[30 .. 23]), [v[31]], 8, 23),
    64 => (zero_extend(64, v[51 .. 0]), zero_extend(64, v[62 .. 52]), [v[63]], 11, 52)
  };
  let table : vector(128, int) = [
      127, 125, 123, 121, 119, 117, 116, 114,
      112, 110, 109, 107, 105, 104, 102, 100,
      99, 97, 96, 94, 93, 91, 90, 88,
      87, 85, 84, 83, 81, 80, 79, 77,
      76, 75, 74, 72, 71, 70, 69, 68,
      66, 65, 64, 63, 62, 61, 60, 59,
      58, 57, 56, 55, 54, 53, 52, 51,
      50, 49, 48, 47, 46, 45, 44, 43,
      42, 41, 40, 40, 39, 38, 37, 36,
      35, 35, 34, 33, 32, 31, 31, 30,
      29, 28, 28, 27, 26, 25, 25, 24,
      23, 23, 22, 21, 21, 20, 19, 19,
      18, 17, 17, 16, 15, 15, 14, 14,
      13, 12, 12, 11, 11, 10, 9, 9,
      8, 8, 7, 7, 6, 5, 5, 4,
      4, 3, 3, 2, 2, 1, 1, 0];

  let nr_leadingzeros = count_leading_zeros(sig[s - 1 .. 0]);
  assert(nr_leadingzeros >= 0);
  let (normalized_exp, normalized_sig) =
      if sub then {
        (to_bits_unsafe(64, (0 - nr_leadingzeros)), zero_extend(64, sig[(s - 1) .. 0] << (1 + nr_leadingzeros)))
      } else {
        (exp, sig)
      };

  let idx : nat = match 'm {
    16 => unsigned(normalized_sig[9 .. 3]),
    32 => unsigned(normalized_sig[22 .. 16]),
    64 => unsigned(normalized_sig[51 .. 45])
  };
  assert(idx >= 0 & idx < 128);
  let mid_exp = to_bits_unsafe(e, 2 * (2 ^ (e - 1) - 1) - 1 - signed(normalized_exp));
  let mid_sig = to_bits_unsafe(s, table[(127 - idx)]) << (s - 7);

  let (out_exp, out_sig)=
      if mid_exp == zeros(e) then {
        (mid_exp, mid_sig >> 1 | 0b1 @ zeros(s - 1))
      } else if mid_exp == ones(e) then {
        (zeros(e), mid_sig >> 2 | 0b01 @ zeros(s - 2))
      } else (mid_exp, mid_sig);

  if sub & nr_leadingzeros > 1 then {
      if (rm_3b == 0b001 | rm_3b == 0b010 & sign == 0b0 | rm_3b == 0b011 & sign == 0b1) then {
        (true, zero_extend(64, sign @ ones(e - 1) @ 0b0 @ ones(s)))
      }
      else (true, zero_extend(64, sign @ ones(e) @ zeros(s)))
    } else (false, zero_extend(64, sign @ out_exp @ out_sig))
}

function riscv_f16Recip7(rm : bits_rm, v : bits_H) -> (bits_fflags, bits_H) = {
  let (round_abnormal_true, res_true) = recip7(v, rm, true);
  let (round_abnormal_false, res_false) = recip7(v, rm, false);
  match float_classify(v) {
    float_class_negative_inf       => (zeros(5), 0x8000),
    float_class_positive_inf       => (zeros(5), 0x0000),
    float_class_negative_zero      => (dzFlag(), 0xfc00),
    float_class_positive_zero      => (dzFlag(), 0x7c00),
    float_class_snan               => (nvFlag(), 0x7e00),
    float_class_qnan               => (zeros(5), 0x7e00),
    float_class_negative_subnormal => if round_abnormal_true then (nxFlag() | ofFlag(), res_true[15 .. 0]) else (zeros(5), res_true[15 .. 0]),
    float_class_positive_subnormal => if round_abnormal_true then (nxFlag() | ofFlag(), res_true[15 .. 0]) else (zeros(5), res_true[15 .. 0]),
    _                              => if round_abnormal_false then (nxFlag() | ofFlag(), res_false[15 .. 0]) else (zeros(5), res_false[15 .. 0])
  }
}

function riscv_f32Recip7(rm : bits_rm, v : bits_S) -> (bits_fflags, bits_S) = {
  let (round_abnormal_true, res_true) = recip7(v, rm, true);
  let (round_abnormal_false, res_false) = recip7(v, rm, false);
  match float_classify(v) {
    float_class_negative_inf       => (zeros(5), 0x80000000),
    float_class_positive_inf       => (zeros(5), 0x00000000),
    float_class_negative_zero      => (dzFlag(), 0xff800000),
    float_class_positive_zero      => (dzFlag(), 0x7f800000),
    float_class_snan               => (nvFlag(), 0x7fc00000),
    float_class_qnan               => (zeros(5), 0x7fc00000),
    float_class_negative_subnormal => if round_abnormal_true then (nxFlag() | ofFlag(), res_true[31 .. 0]) else (zeros(5), res_true[31 .. 0]),
    float_class_positive_subnormal => if round_abnormal_true then (nxFlag() | ofFlag(), res_true[31 .. 0]) else (zeros(5), res_true[31 .. 0]),
    _                              => if round_abnormal_false then (nxFlag() | ofFlag(), res_false[31 .. 0]) else (zeros(5), res_false[31 .. 0])
  }
}

function riscv_f64Recip7(rm : bits_rm, v : bits_D) ->  (bits_fflags, bits_D) = {
  let (round_abnormal_true, res_true) = recip7(v, rm, true);
  let (round_abnormal_false, res_false) = recip7(v, rm, false);
  match float_classify(v) {
    float_class_negative_inf       => (zeros(5), 0x8000000000000000),
    float_class_positive_inf       => (zeros(5), 0x0000000000000000),
    float_class_negative_zero      => (dzFlag(), 0xfff0000000000000),
    float_class_positive_zero      => (dzFlag(), 0x7ff0000000000000),
    float_class_snan               => (nvFlag(), 0x7ff8000000000000),
    float_class_qnan               => (zeros(5), 0x7ff8000000000000),
    float_class_negative_subnormal => if round_abnormal_true then (nxFlag() | ofFlag(), res_true[63 .. 0]) else (zeros(5), res_true[63 .. 0]),
    float_class_positive_subnormal => if round_abnormal_true then (nxFlag() | ofFlag(), res_true[63 .. 0]) else (zeros(5), res_true[63 .. 0]),
    _                              => if round_abnormal_false then (nxFlag() | ofFlag(), res_false[63 .. 0]) else (zeros(5), res_false[63 .. 0])
  }
}
