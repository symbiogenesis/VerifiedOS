// SPDX-License-Identifier: Apache-2.0
//
// The frozen 64+1-bit capability format, in SystemVerilog.
//
// This package is authored against `model/model/core/cap_format.sail` and
// `cap_common.sail`, which are the definition. It is not derived from the
// imported CHERI-CVA6 datapath's own capability package: that one implements the
// ISAv8/v9 128-bit lineage, and the delta between the two is enumerated in
// [docs/rtl-reparameterization-delta.md]. Where this file and the Sail model
// disagree the model wins and this file is defective.
//
// **What has been checked and what has not.** This package lints and elaborates
// under Verilator. Nothing here is verified: no equivalence against the model is
// claimed, and the instrument that would decide one is the capability-widened
// commit trace of the co-simulation gate, which is R2's and not this file's. A
// reader should treat every function below as a transcription owed a check.
//
// **What is carried and what is owed.** The packed form, the permission lattice,
// the object-type space, the encode and decode of a capability including the
// exponent's normalized case and the top mantissa's derived high bits, the null
// transform across the memory interface, and the bounds decode are here. The
// bounds *construction* (`setCapBounds`), the fast representability check, and
// the address and offset setters that rest on it are owed and are named in
// [rtl/README.md].

package vos_cheri_pkg;

  // ---------------------------------------------------------------------------
  // 1. Field widths. These are cap_format.sail's, and they spend 64 bits exactly:
  //    no reserved field, no software-defined permission field, no capability-mode
  //    flag, and no revocation colour appears, each needing a bit the table has
  //    already spent.
  // ---------------------------------------------------------------------------

  // The capability, excluding its validity tag. Also the tag plane's granule:
  // one tag per 64-bit granule.
  localparam int unsigned CapSize = 8;
  localparam int unsigned Log2CapSize = 3;
  localparam int unsigned CapWidth = 8 * CapSize;

  // The granule group four instructions share: the CBO block `cbo.zero`
  // allocates, whose tags `cloadtags` reports.
  localparam int unsigned Log2CapBlockSize = 6;
  localparam int unsigned CapsPerBlock = 2 ** (Log2CapBlockSize - Log2CapSize);

  // Five bits naming one of 32 enumerated permission sets, not one bit per
  // permission. The expansion is in section 3.
  localparam int unsigned CapPermsCodeWidth = 5;
  localparam int unsigned CapPermsWidth = 12;

  // Sixteen sealed-capability classes. Three are reserved by the architecture,
  // the unsealed codepoint and the two sentry edges; the other thirteen are
  // allocated at composition.
  localparam int unsigned CapOTypeWidth = 4;
  localparam int unsigned ReservedOTypes = 3;

  // A five-bit exponent, an eight-bit base mantissa, and a top mantissa stored
  // in six bits with its high two derived.
  localparam int unsigned CapMantissaWidth = 8;
  localparam int unsigned CapEWidth = 5;
  localparam int unsigned CapStoredTWidth = CapMantissaWidth - 2;

  // The address space is 36 bits, so the address field is 36 bits and no access
  // above 2^36 is representable. An effective address stays XLEN wide and reaches
  // memory only through a capability.
  localparam int unsigned CapAddrWidth = 36;
  localparam int unsigned CapLenWidth = CapAddrWidth + 1;
  localparam int unsigned Xlen = 64;

  // The maximum effective exponent, chosen so that the reset capability's top is
  // 2^CapAddrWidth.
  localparam int unsigned CapMaxE = CapLenWidth - CapMantissaWidth + 1;

  typedef logic [CapWidth-1:0]         cap_bits_t;
  typedef logic [CapAddrWidth-1:0]     cap_addr_t;
  typedef logic [CapLenWidth-1:0]      cap_len_t;
  typedef logic [CapOTypeWidth-1:0]    cap_otype_t;
  typedef logic [CapPermsCodeWidth-1:0] cap_perms_code_t;
  typedef logic [CapPermsWidth-1:0]    cap_perms_t;
  typedef logic [CapMantissaWidth-1:0] cap_mant_t;
  typedef logic [CapStoredTWidth-1:0]  cap_stored_t_t;
  typedef logic [CapEWidth-1:0]        cap_e_t;

  // ---------------------------------------------------------------------------
  // 2. The packed form and the decoded form.
  // ---------------------------------------------------------------------------

  // The address occupies the low 36 bits, which is what lets the merged register
  // file's integer reading and its capability reading agree over every value that
  // is an address.
  typedef struct packed {
    cap_perms_code_t perms;
    cap_otype_t      otype;
    cap_e_t          e_field;
    cap_mant_t       b;
    cap_stored_t_t   t;
    cap_addr_t       address;
  } enc_capability_t;

  // A partially decompressed capability. `e` is the *effective* exponent and
  // `normalized` is the case flag the exponent field carries with it; `t` is the
  // full mantissa, whose high two bits the encoding derives.
  typedef struct packed {
    logic            tag;
    cap_perms_code_t perms;
    logic            normalized;
    cap_e_t          e;
    cap_mant_t       b;
    cap_mant_t       t;
    cap_otype_t      otype;
    cap_addr_t       address;
  } capability_t;

  // ---------------------------------------------------------------------------
  // 3. Sealing.
  //
  // The sentry pair is the forward/backward-edge split, which is the platform's
  // coarse-grained CFI: a forward-edge sentry is a call target and a backward-edge
  // sentry is a return address, and `cjalr` admits each only in its own role.
  // ---------------------------------------------------------------------------

  localparam cap_otype_t OTypeUnsealed  = 4'b1111;
  localparam cap_otype_t OTypeSentryFwd = 4'b1110;
  localparam cap_otype_t OTypeSentryBwd = 4'b1101;
  localparam int unsigned CapMaxOType = (2 ** CapOTypeWidth) - 1 - ReservedOTypes;

  function automatic logic is_cap_sealed(capability_t cap);
    return cap.otype != OTypeUnsealed;
  endfunction

  // Tests whether the capability has a reserved otype, which includes both the
  // sealed sentry edges and the unsealed all-ones codepoint.
  function automatic logic has_reserved_otype(capability_t cap);
    return {1'b0, cap.otype} > (CapOTypeWidth + 1)'(CapMaxOType);
  endfunction

  function automatic logic is_sentry(capability_t cap);
    return (cap.otype == OTypeSentryFwd) || (cap.otype == OTypeSentryBwd);
  endfunction

  function automatic capability_t seal_cap(capability_t cap, cap_otype_t otyp);
    capability_t ret = cap;
    ret.otype = otyp;
    return ret;
  endfunction

  function automatic capability_t unseal_cap(capability_t cap);
    capability_t ret = cap;
    ret.otype = OTypeUnsealed;
    return ret;
  endfunction

  // ---------------------------------------------------------------------------
  // 4. Permissions.
  //
  // The five-bit field is not one flag per permission: the admitted sets are
  // enumerated at freeze time, the enumeration is total over all 32 codepoints,
  // and the residue is the bottom element, so the field has no illegal encoding
  // to reject and its decode is a total function. That totality stands in place
  // of the legal-permissions invariant a one-bit-per-permission field needs.
  //
  // Two combinations are excluded at the lattice rather than downstream of it: no
  // admitted set holds both Permit_Seal and Permit_Unseal, and none holds both
  // Permit_Store and Permit_Execute, which makes W+X unrepresentable rather than
  // merely underivable.
  // ---------------------------------------------------------------------------

  // Bit positions in the expanded bitmap, least significant first:
  //
  //   0 global                 4 store-capability       8  permit-execute
  //   1 permit-load            5 store-local-capability 9  permit-seal
  //   2 permit-store           6 load-global            10 permit-unseal
  //   3 load-capability        7 load-mutable           11 access-system-registers
  localparam int unsigned PermGlobal    = 0;
  localparam int unsigned PermLoad      = 1;
  localparam int unsigned PermStore     = 2;
  localparam int unsigned PermLoadCap   = 3;
  localparam int unsigned PermStoreCap  = 4;
  localparam int unsigned PermStoreLocal = 5;
  localparam int unsigned PermLoadGlobal = 6;
  localparam int unsigned PermLoadMutable = 7;
  localparam int unsigned PermExecute   = 8;
  localparam int unsigned PermSeal      = 9;
  localparam int unsigned PermUnseal    = 10;
  localparam int unsigned PermAsr       = 11;

  // The sixteen authority shapes, which bit 4 of the field crosses with
  // local/global to give the 32 codepoints. Local versus global is orthogonal to
  // the shape: it bounds where a capability may be stored, not what it authorises.
  localparam cap_perms_code_t PermsNone        = 5'b00000; // the bottom element
  localparam cap_perms_code_t PermsR           = 5'b00001;
  localparam cap_perms_code_t PermsRW          = 5'b00010;
  localparam cap_perms_code_t PermsRCap        = 5'b00011;
  localparam cap_perms_code_t PermsRCapLg      = 5'b00100;
  localparam cap_perms_code_t PermsRCapLmLg    = 5'b00101;
  localparam cap_perms_code_t PermsRwCap       = 5'b00110;
  localparam cap_perms_code_t PermsRwCapLg     = 5'b00111;
  localparam cap_perms_code_t PermsDataRoot    = 5'b01000;
  localparam cap_perms_code_t PermsStack       = 5'b01001;
  localparam cap_perms_code_t PermsX           = 5'b01010;
  localparam cap_perms_code_t PermsXCapLg      = 5'b01011;
  localparam cap_perms_code_t PermsCodeRoot    = 5'b01100;
  localparam cap_perms_code_t PermsCodeRootAsr = 5'b01101;
  localparam cap_perms_code_t PermsSeal        = 5'b01110;
  localparam cap_perms_code_t PermsUnseal      = 5'b01111;
  localparam cap_perms_code_t PermsGlobalBit   = 5'b10000;

  // The architectural permission set a codepoint names, as the expanded bitmap.
  // Total: every one of the 32 codepoints names a set. The shape occupies bits
  // 11 down to 1 and the global bit is bit 0, so the literals below read in the
  // order ASR US SE X LM LG SL SC LC W R.
  function automatic cap_perms_t perms_expand(cap_perms_code_t code);
    logic [10:0] shape;
    unique case (code[3:0])
      4'b0000: shape = 11'b000_0000_0000; // {}
      4'b0001: shape = 11'b000_0000_0001; // {R}
      4'b0010: shape = 11'b000_0000_0011; // {R,W}
      4'b0011: shape = 11'b000_0000_0101; // {R,LC}
      4'b0100: shape = 11'b000_0010_0101; // {R,LC,LG}
      4'b0101: shape = 11'b000_0110_0101; // {R,LC,LM,LG}
      4'b0110: shape = 11'b000_0000_1111; // {R,W,LC,SC}
      4'b0111: shape = 11'b000_0010_1111; // {R,W,LC,SC,LG}
      4'b1000: shape = 11'b000_0110_1111; // {R,W,LC,SC,LM,LG}
      4'b1001: shape = 11'b000_0111_1111; // {R,W,LC,SC,SL,LM,LG}
      4'b1010: shape = 11'b000_1000_0001; // {R,X}
      4'b1011: shape = 11'b000_1010_0101; // {R,X,LC,LG}
      4'b1100: shape = 11'b000_1110_0101; // {R,X,LC,LM,LG}
      4'b1101: shape = 11'b100_1110_0101; // {R,X,LC,LM,LG,ASR}
      4'b1110: shape = 11'b001_0000_0000; // {SE}
      4'b1111: shape = 11'b010_0000_0000; // {US}
      default: shape = 11'b000_0000_0000;
    endcase
    return {shape, code[4]};
  endfunction

  // The codepoint of the largest admitted permission set contained in `want`,
  // which is how a mask reaches a non-orthogonal field: the result is a subset of
  // the input, so `candperm` can only ever remove authority whatever mask it is
  // handed. Where two admitted sets of equal size both fit, the lower codepoint
  // wins; the order of the table above is part of the freeze.
  //
  // This is a 32-way search and it is the one place in the format path where the
  // frozen dialect is more logic than the imported one.
  function automatic cap_perms_code_t perms_narrow(cap_perms_t want);
    cap_perms_code_t best;
    int signed best_n;
    cap_perms_code_t code;
    cap_perms_t set;
    int signed n;
    best = PermsNone;
    best_n = -1;
    for (int unsigned i = 0; i < 32; i++) begin
      code = cap_perms_code_t'(i);
      set = perms_expand(code);
      n = int'($countones(set));
      if (((set & want) == set) && (n > best_n)) begin
        best = code;
        best_n = n;
      end
    end
    return best;
  endfunction

  function automatic cap_perms_t get_cap_perms(capability_t cap);
    return perms_expand(cap.perms);
  endfunction

  // The permission accessors. The struct carries the codepoint rather than a field
  // per permission, so the only reachable permission sets are the admitted ones and
  // no derivation can construct a set outside the enumeration. Each accessor indexes
  // the expanded bitmap at the position section 4 states, so the layout is written
  // once and read off here.
  function automatic logic cap_global(capability_t c);
    return get_cap_perms(c)[PermGlobal];
  endfunction
  function automatic logic cap_permit_load(capability_t c);
    return get_cap_perms(c)[PermLoad];
  endfunction
  function automatic logic cap_permit_store(capability_t c);
    return get_cap_perms(c)[PermStore];
  endfunction
  function automatic logic cap_load_cap(capability_t c);
    return get_cap_perms(c)[PermLoadCap];
  endfunction
  function automatic logic cap_store_cap(capability_t c);
    return get_cap_perms(c)[PermStoreCap];
  endfunction
  function automatic logic cap_store_local_cap(capability_t c);
    return get_cap_perms(c)[PermStoreLocal];
  endfunction
  function automatic logic cap_load_global(capability_t c);
    return get_cap_perms(c)[PermLoadGlobal];
  endfunction
  function automatic logic cap_load_mutable(capability_t c);
    return get_cap_perms(c)[PermLoadMutable];
  endfunction
  function automatic logic cap_permit_execute(capability_t c);
    return get_cap_perms(c)[PermExecute];
  endfunction
  function automatic logic cap_permit_seal(capability_t c);
    return get_cap_perms(c)[PermSeal];
  endfunction
  function automatic logic cap_permit_unseal(capability_t c);
    return get_cap_perms(c)[PermUnseal];
  endfunction
  function automatic logic cap_access_system_regs(capability_t c);
    return get_cap_perms(c)[PermAsr];
  endfunction

  function automatic capability_t set_cap_perms(capability_t cap, cap_perms_t want);
    capability_t ret = cap;
    ret.perms = perms_narrow(want);
    return ret;
  endfunction

  // ---------------------------------------------------------------------------
  // 5. Encode and decode.
  //
  // One packing decision is the dialect's rather than the imported lineage's, and
  // it carries the same information. Upstream spends a bit flagging whether the
  // exponent is stored internally, in bits stolen from the two mantissas; the
  // frozen format has an explicit five-bit exponent field with no bit to spare
  // beside it, so the flag rides the field itself, IEEE-754 fashion: a zero
  // exponent field is the denormal case (effective exponent zero, length mantissa
  // below its own half), and a field of k+1 is the normalized case at effective
  // exponent k. The effective exponent runs to CapMaxE, so k+1 runs to 31 and the
  // five bits are spent exactly.
  // ---------------------------------------------------------------------------

  function automatic enc_capability_t cap_bits_to_enc(cap_bits_t c);
    enc_capability_t ret;
    ret.perms   = c[63:59];
    ret.otype   = c[58:55];
    ret.e_field = c[54:50];
    ret.b       = c[49:42];
    ret.t       = c[41:36];
    ret.address = c[35:0];
    return ret;
  endfunction

  function automatic cap_bits_t enc_to_cap_bits(enc_capability_t cap);
    return {cap.perms, cap.otype, cap.e_field, cap.b, cap.t, cap.address};
  endfunction

  function automatic capability_t enc_to_capability(logic tag, enc_capability_t c);
    capability_t ret;
    logic        normalized;
    logic [1:0]  len_msbs;
    logic [1:0]  carry_out;
    logic [1:0]  t_top2;
    normalized = c.e_field != '0;
    len_msbs = normalized ? 2'b01 : 2'b00;
    // Reconstruct the top two bits of T from the top two bits of B, the length
    // MSBs implied by the case above, and the carry out of B + len that is
    // implied when T's low bits are below B's.
    carry_out = (c.t < c.b[CapStoredTWidth-1:0]) ? 2'b01 : 2'b00;
    t_top2 = c.b[CapMantissaWidth-1:CapMantissaWidth-2] + len_msbs + carry_out;
    ret.tag        = tag;
    ret.perms      = c.perms;
    ret.normalized = normalized;
    ret.e          = normalized ? (c.e_field - 5'd1) : '0;
    ret.b          = c.b;
    ret.t          = {t_top2, c.t};
    ret.otype      = c.otype;
    ret.address    = c.address;
    return ret;
  endfunction

  function automatic enc_capability_t capability_to_enc(capability_t cap);
    enc_capability_t ret;
    ret.perms   = cap.perms;
    ret.otype   = cap.otype;
    ret.e_field = cap.normalized ? (cap.e + 5'd1) : '0;
    ret.b       = cap.b;
    ret.t       = cap.t[CapStoredTWidth-1:0];
    ret.address = cap.address;
    return ret;
  endfunction

  function automatic cap_bits_t capability_to_bits(capability_t cap);
    return enc_to_cap_bits(capability_to_enc(cap));
  endfunction

  function automatic capability_t cap_bits_to_capability(logic tag, cap_bits_t c);
    return enc_to_capability(tag, cap_bits_to_enc(c));
  endfunction

  // ---------------------------------------------------------------------------
  // 6. The reset capabilities.
  //
  // The machine comes out of reset holding a split root set rather than one
  // almighty capability: no admitted permission set holds both store and execute,
  // so a single partition-bounded root is inexpressible and composition hands each
  // core an execute-side and a store-side authority instead. `RootCodeCap` is the
  // execute-side one, which is what PCC and the trap capabilities reset to;
  // `RootDataCap` is the store-side one, and it carries store-local because
  // narrowing can only remove, so a stack capability is derivable only from a root
  // that already holds it.
  // ---------------------------------------------------------------------------

  localparam cap_e_t   CapResetE = cap_e_t'(CapMaxE);
  localparam cap_mant_t CapResetT = {2'b01, {(CapMantissaWidth - 2){1'b0}}};

  localparam capability_t NullCap = '{
      tag:        1'b0,
      perms:      PermsNone,
      normalized: 1'b1,
      e:          CapResetE,
      b:          '0,
      t:          CapResetT,
      otype:      OTypeUnsealed,
      address:    '0
  };

  localparam capability_t RootCodeCap = '{
      tag:        1'b1,
      perms:      PermsCodeRootAsr | PermsGlobalBit,
      normalized: 1'b1,
      e:          CapResetE,
      b:          '0,
      t:          CapResetT,
      otype:      OTypeUnsealed,
      address:    '0
  };

  localparam capability_t RootDataCap = '{
      tag:        1'b1,
      perms:      PermsStack | PermsGlobalBit,
      normalized: 1'b1,
      e:          CapResetE,
      b:          '0,
      t:          CapResetT,
      otype:      OTypeUnsealed,
      address:    '0
  };

  // ---------------------------------------------------------------------------
  // 7. The memory interface.
  //
  // Capabilities are exclusive-ored with the bits of the null capability when
  // they cross the memory interface, so that an all-zeroes granule reads back as
  // canonical NULL even though NULL has bits set logically. The null capability's
  // address is zero, so the transform leaves the low 36 bits alone: an address
  // reads back as itself through it, which is what makes the merged file's integer
  // reading agree with its capability reading over every value that is an address.
  //
  // The transform runs in **both** directions. The imported datapath applies it on
  // the store path only, so the load path is where a curator most easily leaves it
  // out and the resulting NULL is not the one the zeroize discipline reads back.
  // ---------------------------------------------------------------------------

  localparam cap_bits_t NullCapBits = {
      PermsNone, OTypeUnsealed, 5'd31, {CapMantissaWidth{1'b0}},
      {CapStoredTWidth{1'b0}}, {CapAddrWidth{1'b0}}
  };

  function automatic cap_bits_t capability_to_mem_bits(capability_t cap);
    return capability_to_bits(cap) ^ NullCapBits;
  endfunction

  function automatic capability_t mem_bits_to_capability(logic tag, cap_bits_t b);
    return cap_bits_to_capability(tag, b ^ NullCapBits);
  endfunction

  // An integer at an address, carrying no authority. This is what an integer write
  // into the merged register file produces: the register's 64 data bits are the
  // integer, and the low 36 of them are the address field a capability reading
  // takes.
  function automatic capability_t int_to_cap(logic [Xlen-1:0] v);
    return mem_bits_to_capability(1'b0, v[CapWidth-1:0]);
  endfunction

  // An address above the implemented space is unrepresentable rather than
  // truncated into it: the result is untagged and faults at its next dereference.
  function automatic logic addr_in_range(logic [Xlen-1:0] addr);
    return addr[Xlen-1:CapAddrWidth] == '0;
  endfunction

  // ---------------------------------------------------------------------------
  // 8. The bounds decode.
  //
  // CHERI Concentrate's decode at the frozen widths. The representable limit is
  // derived from the top three mantissa bits and the comparisons are three bits
  // wide, which is the model's formulation; the imported datapath states the same
  // quantity over the whole mantissa, and the correspondence between the two is
  // part of what the representation-correctness proof owes.
  // ---------------------------------------------------------------------------

  // Wide enough to hold `(a_top + correction) << (CapMantissaWidth + E)` before
  // the truncation to CapLenWidth discards its overflow.
  localparam int unsigned BoundsWide = 96;

  // One of the two concatenations `(a_top + correction) @ mantissa @ zeros(E)`,
  // as a shift-and-or: the shifted correction term's low `CapMantissaWidth + E`
  // bits are zero, and the mantissa term occupies exactly that window, so the two
  // never overlap and the disjunction is the concatenation.
  function automatic cap_len_t bounds_term(cap_addr_t a_top, logic [1:0] corr,
                                           cap_mant_t mant, cap_e_t e);
    logic [BoundsWide-1:0] corrected;
    logic [BoundsWide-1:0] high_part;
    logic [BoundsWide-1:0] mant_part;
    logic [BoundsWide-1:0] whole;
    corrected = {{(BoundsWide - CapAddrWidth){1'b0}}, a_top}
              + {{(BoundsWide - 2){corr[1]}}, corr};
    high_part = corrected << (CapMantissaWidth + 32'(e));
    mant_part = {{(BoundsWide - CapMantissaWidth){1'b0}}, mant} << e;
    whole = high_part | mant_part;
    return whole[CapLenWidth-1:0];
  endfunction

  typedef struct packed {
    cap_len_t  top;
    cap_addr_t base;
  } cap_bounds_t;

  function automatic cap_bounds_t get_cap_bounds(capability_t c);
    cap_bounds_t ret;
    cap_e_t     e;
    logic [2:0] a3;
    logic [2:0] b3;
    logic [2:0] t3;
    logic [2:0] r3;
    logic       a_hi;
    logic       b_hi;
    logic       t_hi;
    logic [1:0] corr_base;
    logic [1:0] corr_top;
    cap_addr_t  a_top;
    cap_len_t   base_full;
    cap_len_t   top_full;
    logic [1:0] base2;
    logic [1:0] top2;
    logic [BoundsWide-1:0] shifted;

    e = (c.e > cap_e_t'(CapMaxE)) ? cap_e_t'(CapMaxE) : c.e;

    // The bits needed for the top correction and the representable limit.
    shifted = {{(BoundsWide - CapAddrWidth){1'b0}}, c.address} >> (32'(e) + CapMantissaWidth - 3);
    a3 = shifted[2:0];
    b3 = c.b[CapMantissaWidth-1:CapMantissaWidth-3];
    t3 = c.t[CapMantissaWidth-1:CapMantissaWidth-3];
    r3 = b3 - 3'b001; // wraps

    // Do address, base and top lie in the R-aligned region above the one holding R?
    a_hi = (a3 < r3);
    b_hi = (b3 < r3);
    t_hi = (t3 < r3);

    // Region corrections for top and base relative to a, each in {-1, 0, +1}.
    corr_base = {1'b0, b_hi} - {1'b0, a_hi};
    corr_top  = {1'b0, t_hi} - {1'b0, a_hi};

    shifted = {{(BoundsWide - CapAddrWidth){1'b0}}, c.address} >> (32'(e) + CapMantissaWidth);
    a_top = shifted[CapAddrWidth-1:0];

    base_full = bounds_term(a_top, corr_base, c.b, e);
    top_full  = bounds_term(a_top, corr_top,  c.t, e);

    // If base and top are more than an address space apart, invert the MSB of
    // top: that corrects the case where the representable space wraps.
    base2 = {1'b0, base_full[CapAddrWidth-1]};
    top2  = top_full[CapAddrWidth:CapAddrWidth-1];
    if ((e < cap_e_t'(CapMaxE - 1)) && ((top2 - base2) > 2'd1)) begin
      top_full[CapAddrWidth] = ~top_full[CapAddrWidth];
    end

    ret.base = base_full[CapAddrWidth-1:0];
    ret.top  = top_full;
    return ret;
  endfunction

  // The bounds check is stated over the effective address, which is wider than
  // the address field, so an out-of-range integer fails it rather than aliasing
  // into range: no path runs from an integer above 2^36 to an access.
  function automatic logic in_cap_bounds(capability_t cap, logic [Xlen-1:0] addr,
                                         logic [Xlen-1:0] size);
    cap_bounds_t bounds;
    logic [Xlen:0] a;
    logic [Xlen:0] top;
    logic [Xlen:0] base;
    bounds = get_cap_bounds(cap);
    a    = {1'b0, addr};
    base = {{(Xlen + 1 - CapAddrWidth){1'b0}}, bounds.base};
    top  = {{(Xlen + 1 - CapLenWidth){1'b0}}, bounds.top};
    return (a >= base) && ((a + {1'b0, size}) <= top);
  endfunction

  function automatic capability_t clear_tag_if(capability_t cap, logic cond);
    capability_t ret = cap;
    ret.tag = cap.tag & ~cond;
    return ret;
  endfunction

endpackage
