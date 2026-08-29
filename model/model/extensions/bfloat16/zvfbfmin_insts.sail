//=======================================================================================
//  This Sail RISC-V architecture model, comprising all files and
//  directories except where otherwise noted is subject the BSD
//  two-clause license in the LICENSE file.
//
//  SPDX-License-Identifier: BSD-2-Clause
//=======================================================================================

// The profile adopts `Zvfbfmin` beside `Zvfbfwma`, being that extension's own
// standards-track dependency: the widening bf16 multiply-accumulate is defined
// over an element type whose narrowing and widening conversions are the two
// clauses below, so adopting the second and not the first would state an
// incomplete extension set rather than a narrower one (R-15-067i). Neither
// clause takes a scalar operand, so neither pays the re-homing surcharge every
// other vector floating-point adoption here pays (R-15-040b) and neither
// diverges from upstream.
function clause currentlyEnabled(Ext_Zvfbfmin) = hartSupports(Ext_Zvfbfmin) & currentlyEnabled(Ext_Zve32f)

union clause instruction = VFNCVTBF16_F_F_W : (bits(1), vregidx, vregidx)

$[wavedrom "VFUNARY0 _ _ vfncvtbf16 OPFVV _ OP-V"]
mapping clause encdec = VFNCVTBF16_F_F_W(vm, vs2, vd)
  <-> 0b010010 @ vm @ encdec_vreg(vs2) @ 0b11101 @ 0b001 @ encdec_vreg(vd) @ 0b1010111
  when currentlyEnabled(Ext_Zvfbfmin) & get_sew() == 16

function clause execute (VFNCVTBF16_F_F_W(vm, vs2, vd)) = {
  let rm_3b    = fp_static_rm;
  let SEW      = get_sew();
  let LMUL_pow = get_lmul_pow();
  let num_elem = get_num_elem(LMUL_pow, SEW);

  let SEW_widen      = SEW * 2;
  let LMUL_pow_widen = LMUL_pow + 1;

  if illegal_fp_variable_width(vd, vm, SEW, SEW_widen, LMUL_pow_widen) |
     not(valid_reg_overlap(vs2, vd, LMUL_pow_widen, LMUL_pow)) |
     not(valid_vm_src_overlap(vm, vs2, SEW_widen))
  then return Illegal_Instruction();

  assert(SEW == 16);
  assert(LMUL_pow_widen <= 3);

  let 'n = num_elem;
  let 'm = SEW;
  let 'o = SEW_widen;

  let vm_val  : bits('n)             = read_vmask(num_elem, vm, zvreg);
  let vs2_val : vector('n, bits('o)) = read_vreg(num_elem, SEW_widen, LMUL_pow_widen, vs2);
  let vd_val  : vector('n, bits('m)) = read_vreg(num_elem, SEW, LMUL_pow, vd);

  let (initial_result, mask) : (vector('n, bits('m)), bits('n)) = init_masked_result(num_elem, SEW, LMUL_pow, vd_val, vm_val);
  var result = initial_result;

  foreach (i from 0 to (num_elem - 1)) {
    if mask[i] == 0b1 then {
      let (_, elem) = riscv_f32ToBF16(rm_3b, vs2_val[i]);
      result[i] = elem;
    }
  };

  write_vreg(num_elem, SEW, LMUL_pow, vd, result);
  RETIRE_SUCCESS
}

mapping clause assembly = VFNCVTBF16_F_F_W(vm, vs2, vd)
  <-> "vfncvtbf16.f.f.w" ^ spc() ^ vreg_name(vd) ^ sep() ^ vreg_name(vs2) ^ sep() ^ maybe_vmask(vm)

union clause instruction = VFWCVTBF16_F_F_V : (bits(1), vregidx, vregidx)

$[wavedrom "VFUNARY0 _ _ vfwcvtbf16 OPFVV _ OP-V"]
mapping clause encdec = VFWCVTBF16_F_F_V(vm, vs2, vd)
  <-> 0b010010 @ vm @ encdec_vreg(vs2) @ 0b01101 @ 0b001 @ encdec_vreg(vd) @ 0b1010111
  when currentlyEnabled(Ext_Zvfbfmin) & get_sew() == 16

function clause execute (VFWCVTBF16_F_F_V(vm, vs2, vd)) = {
  let rm_3b    = fp_static_rm;
  let SEW      = get_sew();
  let LMUL_pow = get_lmul_pow();
  let num_elem = get_num_elem(LMUL_pow, SEW);

  let SEW_widen      = SEW * 2;
  let LMUL_pow_widen = LMUL_pow + 1;

  if illegal_fp_variable_width(vd, vm, SEW, SEW_widen, LMUL_pow_widen) |
     not(valid_reg_overlap(vs2, vd, LMUL_pow, LMUL_pow_widen)) |
     not(valid_vm_src_overlap(vm, vs2, SEW))
  then return Illegal_Instruction();

  assert(SEW == 16);
  assert(LMUL_pow_widen <= 3);

  let 'n = num_elem;
  let 'm = SEW;
  let 'o = SEW_widen;

  let vm_val  : bits('n)             = read_vmask(num_elem, vm, zvreg);
  let vs2_val : vector('n, bits('m)) = read_vreg(num_elem, SEW, LMUL_pow, vs2);
  let vd_val  : vector('n, bits('o)) = read_vreg(num_elem, SEW_widen, LMUL_pow_widen, vd);

  let (initial_result, mask) : (vector('n, bits('o)), bits('n)) = init_masked_result(num_elem, SEW_widen, LMUL_pow_widen, vd_val, vm_val);
  var result = initial_result;

  foreach (i from 0 to (num_elem - 1)) {
    if mask[i] == 0b1 then {
      result[i] = bf16_to_f32_set_flags(vs2_val[i]);
    }
  };

  write_vreg(num_elem, SEW_widen, LMUL_pow_widen, vd, result);
  RETIRE_SUCCESS
}

mapping clause assembly = VFWCVTBF16_F_F_V(vm, vs2, vd)
  <-> "vfwcvtbf16.f.f.v" ^ spc() ^ vreg_name(vd) ^ sep() ^ vreg_name(vs2) ^ sep() ^ maybe_vmask(vm)
