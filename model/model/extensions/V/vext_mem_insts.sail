// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// ******************************************************************************
// This file implements part of the vector extension.
// Chapter 7: Vector Loads and Stores
// ******************************************************************************

mapping vlewidth_bitsnumberstr : vlewidth <-> string = {
  VLE8      <-> "8",
  VLE16     <-> "16",
  VLE32     <-> "32",
  VLE64     <-> "64"
}

mapping encdec_vlewidth : vlewidth <-> bits(3) = {
  VLE8      <-> 0b000,
  VLE16     <-> 0b101,
  VLE32     <-> 0b110,
  VLE64     <-> 0b111
}

mapping vlewidth_pow : vlewidth <-> {3, 4, 5, 6} = {
  VLE8      <-> 3,
  VLE16     <-> 4,
  VLE32     <-> 5,
  VLE64     <-> 6
}

mapping encdec_indexed_mop : indexed_mop <-> bits(2) = {
  INDEXED_UNORDERED <-> 0b01,
  INDEXED_ORDERED   <-> 0b11,
}

mapping indexed_mop_mnemonic : indexed_mop <-> string = {
  INDEXED_UNORDERED <-> "u",
  INDEXED_ORDERED   <-> "o",
}

// ******************* Vector Load Unit-Stride Normal & Segment (mop=0b00, lumop=0b00000) *********************
union clause instruction = VLSEGTYPE : (nfields, bits(1), regidx, vlewidth, vregidx)

mapping clause encdec = VLSEGTYPE(nf, vm, rs1, width, vd)
  <-> encdec_nfields(nf) @ 0b0 @ 0b00 @ vm @ 0b00000 @ encdec_reg(rs1) @ encdec_vlewidth(width) @ encdec_vreg(vd) @ 0b0000111
  when (currentlyEnabled(Ext_Zve32x) & vlewidth_pow(width) <= 5)
     | (currentlyEnabled(Ext_Zve64x) & vlewidth_pow(width) <= 6)

function clause execute VLSEGTYPE(nf, vm, rs1, width, vd) = {
  let EEW_pow = vlewidth_pow(width);
  let load_width_bytes = 2 ^ (EEW_pow - 3);
  let EEW = 2 ^ EEW_pow;
  let SEW_pow = get_sew_pow();
  let LMUL_pow = get_lmul_pow();
  let EMUL_pow = EEW_pow - SEW_pow + LMUL_pow;

  assert(-3 <= EMUL_pow & EMUL_pow <= 3);

  let num_elem = get_num_elem(EMUL_pow, EEW); // # of element of each register group
  assert(num_elem > 0);

  if illegal_load(vd, vm, nf, EEW, EMUL_pow) | not(valid_reg_group(vd, EMUL_pow))
  then return Illegal_Instruction();

  let EMUL_reg = 2 ^ max(EMUL_pow, 0);
  let vm_val = read_vmask(num_elem, vm, zvreg);
  let vd_seg = read_vreg_seg(num_elem, load_width_bytes * 8, EMUL_pow, nf, vd);

  let 'm = nf * load_width_bytes * 8;
  let 'n = num_elem;
  let (result, mask) : (vector('n, bits('m)), bits('n)) = init_masked_result(num_elem, 'm, EMUL_pow, vd_seg, vm_val);
  let inactive : bits('n) = vector_body_inactive(num_elem, EMUL_pow, vm_val);

  foreach (i from 0 to (num_elem - 1)) {
    if mask[i] == 0b1 then { // active segments
      foreach (j from 0 to (nf - 1)) {
        let elem_offset = (i * nf + j) * load_width_bytes;
        match data_read(rs1, to_bits_unsafe(xlen, elem_offset), load_width_bytes, Load(Vector), false, false) {
          Ok(elem) => write_single_element(load_width_bytes * 8, i, vregidx_offset(vd, to_bits_unsafe(5, j * EMUL_reg)), elem),
          Err(e)   => return e,
        }
      }
    } else { // masked-off or tail segments
      // A masked-off element's capability check is performed with it and
      // discarded; a tail element is not an element at all (vext_mem_checks.sail,
      // R-15-115b, R-15-085).
      if inactive[i] == 0b1 then {
        foreach (j from 0 to (nf - 1)) {
          let elem_offset = (i * nf + j) * load_width_bytes;
          vector_masked_element_check(rs1, to_bits_unsafe(xlen, elem_offset), load_width_bytes, Load(Vector))
        }
      };
      foreach (j from 0 to (nf - 1)) {
        let skipped_elem = (result[i] >> (j * load_width_bytes * 8))[(load_width_bytes * 8 - 1) .. 0];
        write_single_element(load_width_bytes * 8, i, vregidx_offset(vd, to_bits_unsafe(5, j * EMUL_reg)), skipped_elem)
      }
    }
  };

  RETIRE_SUCCESS
}

mapping clause assembly = VLSEGTYPE(nf, vm, rs1, width, vd)
  <-> "vl" ^ nfields_string(nf) ^ "e" ^ vlewidth_bitsnumberstr(width) ^ ".v" ^ spc() ^ vreg_name(vd) ^ sep() ^ "(" ^ reg_name(rs1) ^ ")" ^ maybe_vmask(vm)

// ******************* Vector Store Unit-Stride Normal & Segment (mop=0b00, sumop=0b00000) ********************
union clause instruction = VSSEGTYPE : (nfields, bits(1), regidx, vlewidth, vregidx)

mapping clause encdec = VSSEGTYPE(nf, vm, rs1, width, vs3)
  <-> encdec_nfields(nf) @ 0b0 @ 0b00 @ vm @ 0b00000 @ encdec_reg(rs1) @ encdec_vlewidth(width) @ encdec_vreg(vs3) @ 0b0100111
  when (currentlyEnabled(Ext_Zve32x) & vlewidth_pow(width) <= 5)
     | (currentlyEnabled(Ext_Zve64x) & vlewidth_pow(width) <= 6)

function clause execute VSSEGTYPE(nf, vm, rs1, width, vs3) = {
  let EEW_pow = vlewidth_pow(width);
  let load_width_bytes = 2 ^ (EEW_pow - 3);
  let EEW = 2 ^ EEW_pow;
  let SEW_pow = get_sew_pow();
  let LMUL_pow = get_lmul_pow();
  let EMUL_pow = EEW_pow - SEW_pow + LMUL_pow;

  assert(-3 <= EMUL_pow & EMUL_pow <= 3);

  let num_elem = get_num_elem(EMUL_pow, EEW);
  assert(num_elem > 0);

  if illegal_store(vs3, nf, EEW, EMUL_pow) |
     not(valid_reg_group(vs3, EMUL_pow)) |
     not(valid_vm_src_overlap(vm, vs3, EEW))
  then return Illegal_Instruction();

  let EMUL_reg = 2 ^ max(EMUL_pow, 0);
  let vm_val = read_vmask(num_elem, vm, zvreg);
  let vs3_seg = read_vreg_seg(num_elem, load_width_bytes * 8, EMUL_pow, nf, vs3);

  let 'n = num_elem;
  let mask : bits('n) = init_masked_source(num_elem, EMUL_pow, vm_val);
  let inactive : bits('n) = vector_body_inactive(num_elem, EMUL_pow, vm_val);

  foreach (i from 0 to (num_elem - 1)) {
    if mask[i] == 0b1 then { // active segments
      foreach (j from 0 to (nf - 1)) {
        let elem_offset = (i * nf + j) * load_width_bytes;
        let vs = vregidx_offset(vs3, to_bits_unsafe(5, j * EMUL_reg));
        let data = read_single_element(load_width_bytes * 8, i, vs);
        // The tag clear R-15-115a states is this write, and not a step beside
        // it: `data_write` carries `default_meta` down to `__WriteRAM_Meta`,
        // which clears every granule the element covers, partial-granule writes
        // included (core/mem_metadata.sail, R-15-007r).
        match data_write(rs1, to_bits_unsafe(xlen, elem_offset), load_width_bytes, data, Store(Vector), false, false) {
          Ok(true)  => (),
          Ok(false) => internal_error(__FILE__, __LINE__, "store got false from data_write"),
          Err(e)    => return e,
        }
      }
    } else if inactive[i] == 0b1 then { // masked-off segments
      // Checked and discarded, and no address presented: a masked-off store
      // that reached memory would write it (vext_mem_checks.sail, R-15-115b).
      foreach (j from 0 to (nf - 1)) {
        let elem_offset = (i * nf + j) * load_width_bytes;
        vector_masked_element_check(rs1, to_bits_unsafe(xlen, elem_offset), load_width_bytes, Store(Vector))
      }
    }
  };

  RETIRE_SUCCESS
}

mapping clause assembly = VSSEGTYPE(nf, vm, rs1, width, vs3)
  <-> "vs" ^ nfields_string(nf) ^ "e" ^ vlewidth_bitsnumberstr(width) ^ ".v" ^ spc() ^ vreg_name(vs3) ^ sep() ^ "(" ^ reg_name(rs1) ^ ")" ^ maybe_vmask(vm)

// ***************************** Vector Load Constant-Stride Normal & Segment (mop=0b10) ******************************
union clause instruction = VLSSEGTYPE : (nfields, bits(1), regidx, regidx, vlewidth, vregidx)

mapping clause encdec = VLSSEGTYPE(nf, vm, rs2, rs1, width, vd)
  <-> encdec_nfields(nf) @ 0b0 @ 0b10 @ vm @ encdec_reg(rs2) @ encdec_reg(rs1) @ encdec_vlewidth(width) @ encdec_vreg(vd) @ 0b0000111
  when (currentlyEnabled(Ext_Zve32x) & vlewidth_pow(width) <= 5)
     | (currentlyEnabled(Ext_Zve64x) & vlewidth_pow(width) <= 6)

function clause execute VLSSEGTYPE(nf, vm, rs2, rs1, width, vd) = {
  let EEW_pow = vlewidth_pow(width);
  let load_width_bytes = 2 ^ (EEW_pow - 3);
  let EEW = 2 ^ EEW_pow;
  let SEW_pow = get_sew_pow();
  let LMUL_pow = get_lmul_pow();
  let EMUL_pow = EEW_pow - SEW_pow + LMUL_pow;

  assert(-3 <= EMUL_pow & EMUL_pow <= 3);

  let num_elem = get_num_elem(EMUL_pow, EEW);
  assert(num_elem > 0);

  if illegal_load(vd, vm, nf, EEW, EMUL_pow) | not(valid_reg_group(vd, EMUL_pow))
  then return Illegal_Instruction();

  let EMUL_reg = 2 ^ max(EMUL_pow, 0);
  let vm_val  = read_vmask(num_elem, vm, zvreg);
  let vd_seg  = read_vreg_seg(num_elem, load_width_bytes * 8, EMUL_pow, nf, vd);
  let rs2_val = unsigned(get_scalar(rs2, xlen));

  let 'm = nf * load_width_bytes * 8;
  let 'n = num_elem;
  let (result, mask) : (vector('n, bits('m)), bits('n)) = init_masked_result(num_elem, nf * load_width_bytes * 8, EMUL_pow, vd_seg, vm_val);
  let inactive : bits('n) = vector_body_inactive(num_elem, EMUL_pow, vm_val);

  foreach (i from 0 to (num_elem - 1)) {
    if mask[i] == 0b1 then { // active segments
      foreach (j from 0 to (nf - 1)) {
        let elem_offset = i * rs2_val + j * load_width_bytes;
        match data_read(rs1, to_bits_unsafe(xlen, elem_offset), load_width_bytes, Load(Vector), false, false) {
          Ok(elem) => write_single_element(load_width_bytes * 8, i, vregidx_offset(vd, to_bits_unsafe(5, j * EMUL_reg)), elem),
          Err(e)   => return e,
        }
      }
    } else { // masked-off or tail segments
      // The runtime stride puts this access off the data-independent-timing
      // list (R-15-085a), which is what makes the mask-independence of its
      // element sequence a statement worth making rather than an implication of
      // the stride (vext_mem_checks.sail, R-15-115b).
      if inactive[i] == 0b1 then {
        foreach (j from 0 to (nf - 1)) {
          let elem_offset = i * rs2_val + j * load_width_bytes;
          vector_masked_element_check(rs1, to_bits_unsafe(xlen, elem_offset), load_width_bytes, Load(Vector))
        }
      };
      foreach (j from 0 to (nf - 1)) {
        let skipped_elem = (result[i] >> (j * load_width_bytes * 8))[(load_width_bytes * 8 - 1) .. 0];
        write_single_element(load_width_bytes * 8, i, vregidx_offset(vd, to_bits_unsafe(5, j * EMUL_reg)), skipped_elem)
      }
    }
  };

  RETIRE_SUCCESS
}

mapping clause assembly = VLSSEGTYPE(nf, vm, rs2, rs1, width, vd)
  <-> "vls" ^ nfields_string(nf) ^ "e" ^ vlewidth_bitsnumberstr(width) ^ ".v" ^ spc() ^ vreg_name(vd) ^ sep() ^ "(" ^ reg_name(rs1) ^ ")" ^ sep() ^ reg_name(rs2) ^ maybe_vmask(vm)

// **************************** Vector Store Constant-Stride Normal & Segment (mop=0b10) ******************************
union clause instruction = VSSSEGTYPE : (nfields, bits(1), regidx, regidx, vlewidth, vregidx)

mapping clause encdec = VSSSEGTYPE(nf, vm, rs2, rs1, width, vs3)
  <-> encdec_nfields(nf) @ 0b0 @ 0b10 @ vm @ encdec_reg(rs2) @ encdec_reg(rs1) @ encdec_vlewidth(width) @ encdec_vreg(vs3) @ 0b0100111
  when (currentlyEnabled(Ext_Zve32x) & vlewidth_pow(width) <= 5)
     | (currentlyEnabled(Ext_Zve64x) & vlewidth_pow(width) <= 6)

function clause execute VSSSEGTYPE(nf, vm, rs2, rs1, width, vs3) = {
  let EEW_pow = vlewidth_pow(width);
  let EEW = 2 ^ EEW_pow;
  let load_width_bytes = 2 ^ (EEW_pow - 3);
  let SEW_pow = get_sew_pow();
  let LMUL_pow = get_lmul_pow();
  let EMUL_pow = EEW_pow - SEW_pow + LMUL_pow;

  assert(-3 <= EMUL_pow & EMUL_pow <= 3);

  let num_elem = get_num_elem(EMUL_pow, EEW);
  assert(num_elem > 0);

  if illegal_store(vs3, nf, EEW, EMUL_pow) |
     not(valid_reg_group(vs3, EMUL_pow)) |
     not(valid_vm_src_overlap(vm, vs3, EEW))
  then return Illegal_Instruction();

  let EMUL_reg = 2 ^ max(EMUL_pow, 0);
  let vm_val = read_vmask(num_elem, vm, zvreg);
  let vs3_seg = read_vreg_seg(num_elem, load_width_bytes * 8, EMUL_pow, nf, vs3);
  let rs2_val = unsigned(get_scalar(rs2, xlen));

  let 'n = num_elem;
  let mask : bits('n) = init_masked_source(num_elem, EMUL_pow, vm_val);
  let inactive : bits('n) = vector_body_inactive(num_elem, EMUL_pow, vm_val);

  foreach (i from 0 to (num_elem - 1)) {
    if mask[i] == 0b1 then { // active segments
      foreach (j from 0 to (nf - 1)) {
        let elem_offset = i * rs2_val + j * load_width_bytes;
        let vs = vregidx_offset(vs3, to_bits_unsafe(5, j * EMUL_reg));
        let data = read_single_element(load_width_bytes * 8, i, vs);
        match data_write(rs1, to_bits_unsafe(xlen, elem_offset), load_width_bytes, data, Store(Vector), false, false) {
          Ok(true)  => (),
          Ok(false) => internal_error(__FILE__, __LINE__, "store got false from data_write"),
          Err(e)    => return e,
        }
      }
    } else if inactive[i] == 0b1 then { // masked-off segments
      foreach (j from 0 to (nf - 1)) {
        let elem_offset = i * rs2_val + j * load_width_bytes;
        vector_masked_element_check(rs1, to_bits_unsafe(xlen, elem_offset), load_width_bytes, Store(Vector))
      }
    }
  };

  RETIRE_SUCCESS
}

mapping clause assembly = VSSSEGTYPE(nf, vm, rs2, rs1, width, vs3)
  <-> "vss" ^ nfields_string(nf) ^ "e" ^ vlewidth_bitsnumberstr(width) ^ ".v" ^ spc() ^ vreg_name(vs3) ^ sep() ^ "(" ^ reg_name(rs1) ^ ")" ^ sep() ^ reg_name(rs2) ^ maybe_vmask(vm)

// ************************ Vector Load Indexed (Ordered and Unordered) Normal & Segment (mop=0b01 or mop=0b11) *******
// Note: Zve64* extensions do not support EEW=64 for index values when XLEN=32.
union clause instruction = VLXSEGTYPE : (nfields, bits(1), vregidx, regidx, vlewidth, vregidx, indexed_mop)

mapping clause encdec = VLXSEGTYPE(nf, vm, vs2, rs1, width, vd, mop)
  <-> encdec_nfields(nf) @ 0b0 @ encdec_indexed_mop(mop) @ vm @ encdec_vreg(vs2) @ encdec_reg(rs1) @ encdec_vlewidth(width) @ encdec_vreg(vd) @ 0b0000111
   when currentlyEnabled(Ext_Zve32x) & vlewidth_pow(width) <= max_index_eew_exp

// `mop` selects between the ordered and unordered variants of these instructions.  This function currently
// only implements the ordered variant, hence `mop` is ignored.
function clause execute VLXSEGTYPE(nf, vm, vs2, rs1, width, vd, _mop) = {
  let EEW_index_pow = vlewidth_pow(width);
  let EEW_index = 2 ^ EEW_index_pow;
  let EEW_index_bytes = 2 ^ (EEW_index_pow - 3);
  let EEW_data_pow = get_sew_pow();
  let EEW_data_bytes = get_sew_bytes();
  let EMUL_data_pow = get_lmul_pow();
  let EMUL_index_pow = EEW_index_pow - EEW_data_pow + EMUL_data_pow;
  let num_elem = get_num_elem(EMUL_data_pow, EEW_data_bytes * 8);
  assert(num_elem > 0);

  let index_dst_overlap : bool =
    if nf == 1
    then not(valid_reg_overlap(vs2, vd, EMUL_index_pow, EMUL_data_pow))          // non-segment indexed load
    else not(valid_disjoint_reg_groups_segmented(vs2, vd, EMUL_index_pow, EMUL_data_pow, nf)); // segment indexed load

  if illegal_indexed_load(vd, vm, nf, 2 ^ EEW_index_pow, EMUL_index_pow, EMUL_data_pow) |
     index_dst_overlap |
     not(valid_vm_src_overlap(vm, vs2, EEW_index))
  then return Illegal_Instruction();

  let EMUL_data_reg = if EMUL_data_pow <= 0 then 1 else 2 ^ EMUL_data_pow;
  let vm_val = read_vmask(num_elem, vm, zvreg);
  let vd_seg = read_vreg_seg(num_elem, EEW_data_bytes * 8, EMUL_data_pow, nf, vd);
  let vs2_val = read_vreg(num_elem, EEW_index_bytes * 8, EMUL_index_pow, vs2);

  let 'm = nf * EEW_data_bytes * 8;
  let 'n = num_elem;
  let (result, mask) : (vector('n, bits('m)), bits('n)) =
    init_masked_result(num_elem, nf * EEW_data_bytes * 8, EMUL_data_pow, vd_seg, vm_val);
  let inactive : bits('n) = vector_body_inactive(num_elem, EMUL_data_pow, vm_val);

  // As mentioned above, currently mop = 1 (unordered) or 3 (ordered) do the same operations.
  foreach (i from 0 to (num_elem - 1)) {
    if mask[i] == 0b1 then { // active segments
      foreach (j from 0 to (nf - 1)) {
        let elem_offset : int = unsigned(vs2_val[i]) + j * EEW_data_bytes;
        match data_read(rs1, to_bits_unsafe(xlen, elem_offset), EEW_data_bytes, Load(Vector), false, false) {
          Ok(elem) => write_single_element(EEW_data_bytes * 8, i, vregidx_offset(vd, to_bits_unsafe(5, j * EMUL_data_reg)), elem),
          Err(e)   => return e,
        }
      }
    } else { // masked-off or tail segments
      // This is the form R-08-003 names by itself: the element address is a
      // runtime index, so the check is owed per element and cannot be hoisted
      // to the base. A masked-off element's index is whatever the register
      // holds, so its check is the one most likely to fail, and failing is what
      // it is allowed to do here (vext_mem_checks.sail, R-15-115b, R-15-085a).
      if inactive[i] == 0b1 then {
        foreach (j from 0 to (nf - 1)) {
          let elem_offset : int = unsigned(vs2_val[i]) + j * EEW_data_bytes;
          vector_masked_element_check(rs1, to_bits_unsafe(xlen, elem_offset), EEW_data_bytes, Load(Vector))
        }
      };
      foreach (j from 0 to (nf - 1)) {
        let skipped_elem = (result[i] >> (j * EEW_data_bytes * 8))[(EEW_data_bytes * 8 - 1) .. 0];
        write_single_element(EEW_data_bytes * 8, i, vregidx_offset(vd, to_bits_unsafe(5, j * EMUL_data_reg)), skipped_elem)
      }
    }
  };

  RETIRE_SUCCESS
}

mapping clause assembly = VLXSEGTYPE(nf, vm, vs2, rs1, width, vd, mop)
  <-> "vl" ^ indexed_mop_mnemonic(mop) ^ "x" ^ nfields_string(nf) ^ "ei" ^ vlewidth_bitsnumberstr(width) ^ ".v" ^ spc() ^ vreg_name(vd) ^ sep() ^ "(" ^ reg_name(rs1) ^ ")" ^ sep() ^ vreg_name(vs2) ^ maybe_vmask(vm)

// *********************** Vector Store Indexed (Ordered and Unordered) Normal & Segment (mop=0b01 or mop=0b11) *******
// Note: Zve64* extensions do not support EEW=64 for index values when XLEN=32.
union clause instruction = VSXSEGTYPE : (nfields, bits(1), vregidx, regidx, vlewidth, vregidx, indexed_mop)

mapping clause encdec = VSXSEGTYPE(nf, vm, vs2, rs1, width, vs3, mop)
  <-> encdec_nfields(nf) @ 0b0 @ encdec_indexed_mop(mop) @ vm @ encdec_vreg(vs2) @ encdec_reg(rs1) @ encdec_vlewidth(width) @ encdec_vreg(vs3) @ 0b0100111
  when (currentlyEnabled(Ext_Zve32x) & vlewidth_pow(width) <= max_index_eew_exp)

// `mop` selects between the ordered and unordered variants of these instructions.  This function currently
// only implements the ordered variant, hence `mop` is ignored.
function clause execute VSXSEGTYPE(nf, vm, vs2, rs1, width, vs3, _mop) = {
  let EEW_index_pow = vlewidth_pow(width);
  let EEW_index = 2 ^ EEW_index_pow;
  let EEW_index_bytes = 2 ^ (EEW_index_pow - 3);
  let EEW_data_pow = get_sew_pow();
  let EEW_data = 2 ^ EEW_data_pow;
  let EEW_data_bytes = get_sew_bytes();
  let EMUL_data_pow = get_lmul_pow();
  let EMUL_index_pow = EEW_index_pow - EEW_data_pow + EMUL_data_pow;
  let num_elem = get_num_elem(EMUL_data_pow, EEW_data_bytes * 8); // number of data and indices are the same

  assert(num_elem > 0);

  if illegal_indexed_store(vs3, nf, 2 ^ EEW_index_pow, EMUL_index_pow, EMUL_data_pow) |
     not(valid_src_overlap(vs2, EEW_index, EMUL_index_pow, vs3, EEW_data, EMUL_data_pow)) |
     not(valid_vm_src_overlap(vm, vs2, EEW_index)) |
     not(valid_vm_src_overlap(vm, vs3, EEW_data))
  then return Illegal_Instruction();

  let EMUL_data_reg = if EMUL_data_pow <= 0 then 1 else 2 ^ EMUL_data_pow;
  let vm_val = read_vmask(num_elem, vm, zvreg);
  let vs3_seg = read_vreg_seg(num_elem, EEW_data_bytes * 8, EMUL_data_pow, nf, vs3);
  let vs2_val = read_vreg(num_elem, EEW_index_bytes * 8, EMUL_index_pow, vs2);

  let 'n = num_elem;
  let mask : bits('n) = init_masked_source(num_elem, EMUL_data_pow, vm_val);
  let inactive : bits('n) = vector_body_inactive(num_elem, EMUL_data_pow, vm_val);

  // As mentioned above, currently mop = 1 (unordered) or 3 (ordered) do the same operations.
  foreach (i from 0 to (num_elem - 1)) {
    if mask[i] == 0b1 then { // active segments
      foreach (j from 0 to (nf - 1)) {
        let elem_offset : int = unsigned(vs2_val[i]) + j * EEW_data_bytes;
        let vs = vregidx_offset(vs3, to_bits_unsafe(5, j * EMUL_data_reg));
        let data = read_single_element(EEW_data_bytes * 8, i, vs);
        match data_write(rs1, to_bits_unsafe(xlen, elem_offset), EEW_data_bytes, data, Store(Vector), false, false) {
          Ok(true)  => (),
          Ok(false) => internal_error(__FILE__, __LINE__, "store got false from data_write"),
          Err(e)    => return e,
        }
      }
    } else if inactive[i] == 0b1 then { // masked-off segments
      foreach (j from 0 to (nf - 1)) {
        let elem_offset : int = unsigned(vs2_val[i]) + j * EEW_data_bytes;
        vector_masked_element_check(rs1, to_bits_unsafe(xlen, elem_offset), EEW_data_bytes, Store(Vector))
      }
    }
  };

  RETIRE_SUCCESS
}

mapping clause assembly = VSXSEGTYPE(nf, vm, vs2, rs1, width, vs3, mop)
  <-> "vs" ^ indexed_mop_mnemonic(mop) ^ "x" ^ nfields_string(nf) ^ "ei" ^ vlewidth_bitsnumberstr(width) ^ ".v" ^ spc() ^ vreg_name(vs3) ^ sep() ^ "(" ^ reg_name(rs1) ^ ")" ^ sep() ^ vreg_name(vs2) ^ maybe_vmask(vm)

// **************** Vector Load Unit-Stride Whole Register (vm=0b1, mop=0b00, lumop=0b01000) ******************
union clause instruction = VLRETYPE : (nfields_pow2, regidx, vlewidth, vregidx)

mapping clause encdec = VLRETYPE(nf, rs1, width, vd)
  <-> encdec_nfields_pow2(nf) @ 0b0 @ 0b00 @ 0b1 @ 0b01000 @ encdec_reg(rs1) @ encdec_vlewidth(width) @ encdec_vreg(vd) @ 0b0000111
  when (currentlyEnabled(Ext_Zve32x) & vlewidth_pow(width) <= 5)
     | (currentlyEnabled(Ext_Zve64x) & vlewidth_pow(width) <= 6)

function clause execute VLRETYPE(nf, rs1, width, vd) = {
  let EEW_pow = vlewidth_pow(width);
  let load_width_bytes = 2 ^ (EEW_pow - 3);
  let EEW = 2 ^ EEW_pow;
  let elem_per_reg = vlen / EEW;
  assert(elem_per_reg >= 0);

  if not(valid_whole_register(vd, nf)) then return Illegal_Instruction();

  // The whole-register transfer starts at element zero: with `vstart` deleted
  // (R-15-039a) there is no partially-transferred register to align back to,
  // so the field loop below is the whole instruction.
  //
  // `vm` is the literal one in the encoding, so every element is active and
  // this clause owes no discarded check: R-15-115b's obligation is over a mask
  // this form does not have (vext_mem_checks.sail). The per-element capability
  // check still lands, once per element, in `data_read` (R-08-003).
  var cur_elem : int = 0;

  foreach (j from 0 to (nf - 1)) {
    foreach (i from 0 to (elem_per_reg - 1)) {
      let elem_offset = cur_elem * load_width_bytes;
      match data_read(rs1, to_bits_unsafe(xlen, elem_offset), load_width_bytes, Load(Vector), false, false) {
        Ok(elem) => write_single_element(load_width_bytes * 8, i, vregidx_offset(vd, to_bits_unsafe(5, j)), elem),
        Err(e)   => return e,
      };
      cur_elem = cur_elem + 1
    }
  };

  RETIRE_SUCCESS
}

mapping clause assembly = VLRETYPE(nf, rs1, width, vd)
  <-> "vl" ^ nfields_pow2_string(nf) ^ "re" ^ vlewidth_bitsnumberstr(width) ^ ".v" ^ spc() ^ vreg_name(vd) ^ sep() ^ "(" ^ reg_name(rs1) ^ ")"

// **************** Vector Store Unit-Stride Whole Register (vm=0b1, mop=0b00, sumop=0b01000) *****************
union clause instruction = VSRETYPE : (nfields_pow2, regidx, vregidx)

mapping clause encdec = VSRETYPE(nf, rs1, vs3)
  <-> encdec_nfields_pow2(nf) @ 0b0 @ 0b00 @ 0b1 @ 0b01000 @ encdec_reg(rs1) @ 0b000 @ encdec_vreg(vs3) @ 0b0100111
  when currentlyEnabled(Ext_Zve32x)

function clause execute VSRETYPE(nf, rs1, vs3) = {
  let load_width_bytes = 1;
  let EEW = 8;
  let elem_per_reg = vlen / EEW;
  assert(elem_per_reg >= 0);

  if not(valid_whole_register(vs3, nf)) then return Illegal_Instruction();

  // As in VLRETYPE: element zero is the only start (R-15-039a).
  var cur_elem : int = 0;

  foreach (j from 0 to (nf - 1)) {
    let vs3_val = read_vreg(elem_per_reg, load_width_bytes * 8, 0, vregidx_offset(vs3, to_bits_unsafe(5, j)));
    foreach (i from 0 to (elem_per_reg - 1)) {
      let elem_offset = cur_elem * load_width_bytes;
      match data_write(rs1, to_bits_unsafe(xlen, elem_offset), load_width_bytes, vs3_val[i], Store(Vector), false, false) {
        Ok(true)  => (),
        Ok(false) => internal_error(__FILE__, __LINE__, "store got false from data_write"),
        Err(e)    => return e,
      };
      cur_elem = cur_elem + 1
    }
  };

  RETIRE_SUCCESS
}

mapping clause assembly = VSRETYPE(nf, rs1, vs3)
  <-> "vs" ^ nfields_pow2_string(nf) ^ "r.v" ^ spc() ^ vreg_name(vs3) ^ sep() ^ "(" ^ reg_name(rs1) ^ ")"

// ************* Vector Mask Load/Store Unit-Stride (nf=0b000, mop=0b00, lumop or sumop=0b01011) **************
union clause instruction = VMTYPE : (regidx, vregidx, vmlsop)

mapping encdec_lsop : vmlsop <-> bits(7) = {
  VLM      <-> 0b0000111,
  VSM      <-> 0b0100111
}

mapping clause encdec = VMTYPE(rs1, vd_or_vs3, op)
  <-> 0b000 @ 0b0 @ 0b00 @ 0b1 @ 0b01011 @ encdec_reg(rs1) @ 0b000 @ encdec_vreg(vd_or_vs3) @ encdec_lsop(op)
  when currentlyEnabled(Ext_Zve32x)

// The mask load and store carry `vm` as the literal one too, so their inactive
// elements are the ones past `evl = ceil(vl/8)` and are tail rather than
// masked-off: no discarded check is owed here either, `vl` being an
// architectural register a partition reads back (vext_mem_checks.sail,
// R-15-115b).
function clause execute VMTYPE(rs1, vd_or_vs3, op) = {
  let EEW = 8;
  let EMUL_pow = 0;
  let vl_val = unsigned(vl);
  let evl : int = if vl_val % 8 == 0 then vl_val / 8 else vl_val / 8 + 1; // the effective vector length is evl=ceil(vl/8)
  let num_elem = get_num_elem(EMUL_pow, EEW);

  if illegal_vd_unmasked() then return Illegal_Instruction();

  assert(evl >= 0);
  let 'n = num_elem;
  let vd_or_vs3_val : vector('n, bits(8)) = read_vreg(num_elem, 8, 0, vd_or_vs3);

  foreach (i from 0 to (num_elem - 1)) {
    if i < evl then { // active elements
      if op == VLM then { // load
        match data_read(rs1, to_bits_unsafe(xlen, i), 1, Load(Vector), false, false) {
          Ok(elem) => write_single_element(8, i, vd_or_vs3, elem),
          Err(e)   => return e,
        }
      } else if op == VSM then { // store
        match data_write(rs1, to_bits_unsafe(xlen, i), 1, vd_or_vs3_val[i], Store(Vector), false, false) {
          Ok(true)  => (),
          Ok(false) => internal_error(__FILE__, __LINE__, "store got false from data_write"),
          Err(e)    => return e,
        }
      }
    } else { // tail elements for mask load, always with agnostic policy
      if op == VLM then {
        write_single_element(8, i, vd_or_vs3, vd_or_vs3_val[i])
        // TODO: configuration support for agnostic behavior
      }
    }
  };

  RETIRE_SUCCESS
}

mapping vmtype_mnemonic : vmlsop <-> string = {
  VLM      <-> "vlm.v",
  VSM      <-> "vsm.v"
}

mapping clause assembly = VMTYPE(rs1, vd_or_vs3, op)
  <-> vmtype_mnemonic(op) ^ spc() ^ vreg_name(vd_or_vs3) ^ sep() ^ "(" ^ reg_name(rs1) ^ ")"
