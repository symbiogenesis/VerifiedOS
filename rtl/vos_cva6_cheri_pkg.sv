// SPDX-License-Identifier: Apache-2.0
//
// The imported datapath's capability package, re-pointed at the frozen format.
//
// This file declares `cva6_cheri_pkg`, which is the name the imported CHERI-CVA6
// datapath reaches its capability format through, by qualified reference across
// `core/` and by wildcard import in `cheri_unit.sv` and `csr_regfile.sv`. It is
// the first row of `tools/vos/cli/rtl.py`'s `SUBSTITUTIONS`: `run.py rtl` places
// it where the imported manifest names `core/include/cva6_cheri_pkg.sv`, so the
// datapath compiles against this package and the imported one stays behind its
// gitlink. Nothing is copied out of it.
//
// **What is the imported tree's and what is not.** The package name and the API
// identifiers below (`cap_reg_t`, `set_cap_reg_bounds`, `cap_reg_to_cap_mem` and
// the rest) are those of `core/include/cva6_cheri_pkg.sv` at `36a1dc5c`, a file
// governed by Solderpad v0.51 at its tree's root, which permits the licensee to
// elect Apache-2.0 and is the election THIRD-PARTY.md records for the whole
// datapath. Every *body* here is written against `vos_cheri_pkg` and the Sail
// model, on the precedent `vos_c_class_config_pkg.sv` takes: what is authored is
// the wrapper and not the record it fills. Where a name here and the model
// disagree the model wins and this file is defective.
//
// **The register form is the model's `capability_t` verbatim**, permissions as
// the five-bit code with `perms_expand` on read and narrowing on every write, so
// `cap_reg_t` is a typedef of it and no third format exists between the datapath
// and the model. Its width is the sum of the decoded form's fields, which the
// imported `build_config_pkg.sv` reads as `PCLEN = $bits(cap_reg_t)`; the
// figure is measured at the elaboration and stated there rather than here.
//
// **Every deletion row of docs/rtl-reparameterization-delta.md §2.1 is a member
// this package does not have.** No software-defined permission field, no reserved
// field, no exponent half, no guest cause, no `int_mode` flag, no `EF` format bit,
// no compressed-bounds union, no implied or embedded packing, no
// `legalize_arch_perms`, no `is_offset_in_range`, no `bot3z` or `add_b1000`, no
// representable-alignment mask, and no single `SENTRY_CAP`. A datapath site that
// reads one of them does not compile against this package, and that failure is
// the measurement the first seam takes: each such site is a row of the delta's
// §2.2 or §2.3 and the compile names it by file and line.
//
// **What is carried from the model that the format package left behind.** The
// capability cause set of `model/model/core/cap_causes.sail`: the eleven ISAv9
// cause codes in a five-bit field, the six-bit register index a fault reports with
// `PCC` outside the merged file's index space, and the `mtval` payload
// `zero_extend(regnum @ code)`; and the one `mcause` code a capability violation
// raises, `EXC_CHERI`, from `model/model/core/types_ext.sail`. Those values are
// restated here as digits and no checker rule reads them: rule K-79 holds the
// format's widths and packings and says nothing about the cause table, so the
// eleven codes, the two widths, `PCC_IDX` and `CAP_EXCEPTION` are transcriptions
// held by nothing but a reading of the two Sail files beside them.
//
// **Two wrappers change what their imported namesakes did, on the model's
// ground.** `set_cap_reg_addr` was the unchecked address set and is the checked
// one here, because the model has no unchecked `setCapAddr` and the frozen one
// additionally clears the tag above 2^36 (delta §2.1, lines 506 to 525).
// `cap_mem_to_cap_reg` applies the null exclusive-or on the load side, which the
// imported tree applied on the store side only (delta §2.5, item 1).
//
// Nothing here is verified. The package lints alone against `vos_cheri_pkg`, and
// what the datapath does with it is what an elaboration reports.
//
// The file is named as this repository's and the package as the imported API's,
// which is the one mismatch Verilator's DECLFILENAME reads; it is the point of
// the file rather than a slip, so the warning is answered here and nowhere else.

/* verilator lint_off DECLFILENAME */
package cva6_cheri_pkg;
/* verilator lint_on DECLFILENAME */

  import vos_cheri_pkg::*;
  export vos_cheri_pkg::*;

  // ---------------------------------------------------------------------------
  // 1. Widths. Each follows the format package's parameter, which is the site
  //    rule K-79 holds against the model; none is a digit of this file's own
  //    (delta §2.1, the width and literal rows at lines 25 to 38).
  // ---------------------------------------------------------------------------

  localparam int unsigned XLEN = Xlen;
  // `CLEN = 2 * XLEN` collapses onto `XLEN`: a capability and an integer occupy
  // one register and one memory word.
  localparam int unsigned CLEN = Xlen;
  localparam int unsigned CTLEN = Xlen + 1;
  localparam int unsigned CAP_ADDR_WIDTH = CapAddrWidth;
  localparam int unsigned CAP_M_WIDTH = CapMantissaWidth;
  localparam int unsigned CAP_E_WIDTH = CapEWidth;
  localparam int unsigned CAP_OTYPE_WIDTH = CapOTypeWidth;
  // The reset exponent is the maximal one, so every comparison against it
  // inverts sense relative to the imported tree, where it was zero.
  localparam int unsigned CAP_RESET_EXP = CapMaxE;
  localparam int unsigned CAP_MAX_EXP = CapMaxE;
  localparam cap_mant_t CAP_RESET_TOP = CapResetT;

  // ---------------------------------------------------------------------------
  // 2. Types. The register form is the model's decoded capability and the memory
  //    form is the tag beside the model's packed bits; the address types are the
  //    36-bit field and the 37-bit length the format package declares.
  // ---------------------------------------------------------------------------

  typedef logic bool_t;
  typedef capability_t cap_reg_t;
  typedef struct packed {
    bool_t     tag;
    cap_bits_t bits;
  } cap_mem_t;
  typedef logic [CTLEN-1:0] capw_t;
  typedef cap_addr_t addrw_t;
  typedef cap_len_t addrwe_t;
  typedef cap_otype_t otypew_t;
  typedef cap_e_t ew_t;
  typedef cap_mant_t mw_t;
  typedef cap_stored_t_t cmw_t;

  // The bounds construction's two answers, the capability and whether the
  // narrowing was exact. The imported shape carried a representable-alignment
  // mask beside them, and it is not here: `CRAM`, `CRRL` and `CSetBoundsExact`
  // are excluded at the architecture (R-15-007k, R-08-011).
  typedef struct packed {
    cap_reg_t cap;
    bool_t    exact;
  } cap_reg_set_bounds_ret_t;

  // ---------------------------------------------------------------------------
  // 3. Object types. The polarity inverts, unsealed being all ones, and the one
  //    sentry becomes a pair the branch unit must distinguish by edge (R-15-071):
  //    a forward-edge sentry is a call target and a backward-edge one a return
  //    address. There is deliberately no single `SENTRY_CAP`, because an alias
  //    would let a site that cannot tell the edges apart compile.
  // ---------------------------------------------------------------------------

  localparam otypew_t UNSEALED_CAP = OTypeUnsealed;
  localparam otypew_t SENTRY_FWD_CAP = OTypeSentryFwd;
  localparam otypew_t SENTRY_BWD_CAP = OTypeSentryBwd;

  // ---------------------------------------------------------------------------
  // 4. The reset capabilities. One root becomes two: no admitted permission set
  //    holds both store and execute, so a single almighty `REG_ROOT_CAP` is
  //    inexpressible (R-15-007l, R-15-007p) and composition hands each core an
  //    execute-side and a store-side authority. The memory-form null is all
  //    zeroes by construction, the null transform being what makes an all-zeroes
  //    granule read back as canonical NULL.
  // ---------------------------------------------------------------------------

  localparam cap_reg_t REG_ROOT_CODE_CAP = RootCodeCap;
  localparam cap_reg_t REG_ROOT_DATA_CAP = RootDataCap;
  localparam cap_reg_t REG_NULL_CAP = NullCap;
  localparam cap_mem_t MEM_NULL_CAP = '{tag: 1'b0, bits: capability_to_mem_bits(NullCap)};
  localparam bool_t MemNullCapIsZero = (MEM_NULL_CAP == '0);

  // ---------------------------------------------------------------------------
  // 5. The capability cause set and the `mtval` payload (cap_causes.sail).
  //
  //    The codes keep ISAv9's numbering and the enumeration carries the causes
  //    this machine can raise and no others, so the field has gaps: 0b00100 to
  //    0b10000 and 0b10111 name no cause. An enumeration written contiguously
  //    would be a different encoding. A fault reports the register that raised
  //    it in the six bits above the code, and `PCC`, which has no index in the
  //    merged file, reports as the one value outside the file's index space.
  // ---------------------------------------------------------------------------

  localparam int unsigned CapExCodeWidth = 5;
  localparam int unsigned CapRegIdxWidth = 6;

  typedef logic [CapExCodeWidth-1:0] cap_ex_code_t;
  typedef logic [CapRegIdxWidth-1:0] capreg_idx_t;

  typedef enum logic [CapExCodeWidth-1:0] {
    CapEx_None                         = 5'b00000,
    CapEx_LengthViolation              = 5'b00001,
    CapEx_TagViolation                 = 5'b00010,
    CapEx_SealViolation                = 5'b00011,
    CapEx_PermitExecuteViolation       = 5'b10001,
    CapEx_PermitLoadViolation          = 5'b10010,
    CapEx_PermitStoreViolation         = 5'b10011,
    CapEx_PermitLoadCapViolation       = 5'b10100,
    CapEx_PermitStoreCapViolation      = 5'b10101,
    CapEx_PermitStoreLocalCapViolation = 5'b10110,
    CapEx_AccessSystemRegsViolation    = 5'b11000
  } cap_ex_t;

  function automatic cap_ex_code_t CapExCode(cap_ex_t ex);
    return cap_ex_code_t'(ex);
  endfunction

  localparam capreg_idx_t PCC_IDX = 6'b100000;

  // The index a fault reports for a general-purpose register: the file's own
  // index, one bit narrower than the fault index, zero-extended.
  function automatic capreg_idx_t capreg_idx_of_regidx(logic [CapRegIdxWidth-2:0] r);
    return {1'b0, r};
  endfunction

  // The `mtval` layout: the violation type in the low five bits and the register
  // above it, zero-extended into the register by the consumer.
  typedef struct packed {
    capreg_idx_t  regnum;
    cap_ex_code_t code;
  } cap_tval_t;

  function automatic logic [XLEN-1:0] capex_tval(cap_ex_t ex, capreg_idx_t regnum);
    cap_tval_t t;
    t.regnum = regnum;
    t.code   = CapExCode(ex);
    return {{(XLEN - $bits(cap_tval_t)){1'b0}}, t};
  endfunction

  // The one `mcause` code a capability violation raises: `EXC_CHERI`, which
  // `types_ext.sail` maps to `0b011100`. A restated digit with no holder; the
  // imported tree's guest cause beside it goes with the hypervisor extension.
  localparam logic [XLEN-1:0] CAP_EXCEPTION = 28;

  // ---------------------------------------------------------------------------
  // 6. The register interface, each a call on the format package.
  // ---------------------------------------------------------------------------

  function automatic bool_t is_cap_reg_valid(cap_reg_t cap);
    return cap.tag;
  endfunction

  function automatic cap_reg_t set_cap_reg_valid(cap_reg_t cap, bool_t tag);
    cap_reg_t ret = cap;
    ret.tag = tag;
    return ret;
  endfunction

  function automatic cap_reg_t seal(cap_reg_t cap, otypew_t otype);
    return seal_cap(cap, otype);
  endfunction

  function automatic cap_reg_t unseal(cap_reg_t cap);
    return unseal_cap(cap);
  endfunction

  function automatic cap_reg_t set_cap_reg_otype(cap_reg_t cap, otypew_t otype);
    return seal_cap(cap, otype);
  endfunction

  // The bounds are valid where the decode does not put the top below the base,
  // which is the whole of the frozen malformed predicate; the imported case
  // analysis on the exponent has no reading at these widths (delta §2.1, lines
  // 427 to 430).
  function automatic bool_t are_cap_reg_bounds_valid(cap_reg_t cap);
    return ~cap_bounds_malformed(cap);
  endfunction

  // The root bounds are the ones at the reset exponent, which is the maximal
  // one here rather than zero (delta §2.1, line 447).
  function automatic bool_t are_cap_reg_bounds_root(cap_reg_t cap);
    return are_cap_reg_bounds_valid(cap) && (cap.e == CapResetE);
  endfunction

  // The decoded bounds are read off the capability alone: the representable
  // limit the imported tree carried as a separate meta-data record is derived
  // inside the decode from the top three mantissa bits (delta §2.1, lines 196 to
  // 203), so no `cap_meta_data_t` exists to pass.
  function automatic logic [XLEN-1:0] get_cap_reg_base(cap_reg_t cap);
    return get_cap_base_bits(cap);
  endfunction

  function automatic addrwe_t get_cap_reg_top(cap_reg_t cap);
    return get_cap_top_bits(cap);
  endfunction

  // A wrapping quantity, as the model states it, and not the saturating one the
  // imported tree computed (delta §2.1, line 493).
  function automatic addrwe_t get_cap_reg_length(cap_reg_t cap);
    return get_cap_length(cap);
  endfunction

  // Both address setters are the checked one: the result is untagged where the
  // move is unrepresentable, where the input was sealed, or where the address
  // lies above the implemented space.
  function automatic cap_reg_t set_cap_reg_address(cap_reg_t cap, logic [XLEN-1:0] address);
    return set_cap_addr_checked(cap, address);
  endfunction

  function automatic cap_reg_t set_cap_reg_addr(cap_reg_t cap, logic [XLEN-1:0] address);
    return set_cap_addr_checked(cap, address);
  endfunction

  // The imported interface states the bounds as a base and a length and the
  // model states them as a base and a top; the top is the sum, in the length's
  // own width.
  function automatic cap_reg_set_bounds_ret_t set_cap_reg_bounds(cap_reg_t cap, addrw_t base,
                                                                 addrwe_t lengthfull);
    cap_result_t r = set_cap_bounds(cap, base, lengthfull + {1'b0, base});
    return '{cap: r.cap, exact: r.ok};
  endfunction

  // ---------------------------------------------------------------------------
  // 7. The memory interface. The null exclusive-or runs in both directions, so
  //    the load side gains it here (delta §2.5, item 1).
  // ---------------------------------------------------------------------------

  function automatic capw_t cap_reg_to_cap_mem(cap_reg_t cap);
    return {cap.tag, capability_to_mem_bits(cap)};
  endfunction

  function automatic cap_reg_t cap_mem_to_cap_reg(cap_mem_t cap);
    return mem_bits_to_capability(cap.tag, cap.bits);
  endfunction

  function automatic bool_t is_cap_mem_valid(capw_t cap);
    return cap[CTLEN-1];
  endfunction

  function automatic capw_t set_cap_mem_valid(capw_t cap, bool_t tag);
    capw_t ret = cap;
    ret[CTLEN-1] = tag;
    return ret;
  endfunction

endpackage
