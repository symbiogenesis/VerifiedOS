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
// **What has been checked and what has not.** The widths and the packed field
// positions below are held against the model on the host by rule K-79, which
// reads them out of `cap_format.sail` and `cap_common.sail` and holds every
// restatement of them against that. The *functions* are held by
// `tools/rtl.py crosscheck`, which compiles the model with a generator that calls
// the same functions, prints what they return, and requires this package to
// reproduce every line; the package lints clean and is executed there behind a
// testbench, and nothing in a design instantiates it yet.
//
// What a cross-check decides is agreement over the vectors it ran, which is a
// measurement and not a proof, and it is not the co-simulation gate either: the
// capability-widened commit trace of a running core is R2's instrument and this
// is a function-level cross-check ahead of it. Nothing below is verified.
//
// **What is carried.** The packed form, the permission lattice, the object-type
// space, the encode and decode of a capability including the exponent's
// normalized case and the top mantissa's derived high bits, the null transform
// across the memory interface, the bounds decode, the bounds construction
// `csetbounds` performs, the representable-limit comparison and the fast
// representability check, the address and offset setters that rest on it, the
// length, and the malformed predicate.
//
// **What is not.** No instruction, no datapath and no register file: this is the
// format and its algebra, and the unit that decodes an opcode into a call on it
// is R1's remaining curation. `CRAM`, `CRRL` and `CSetBoundsExact` are excluded
// at the architecture rather than owed here (R-15-007k, R-08-011), so no
// representable-alignment mask is computed and none is returned.

package vos_cheri_pkg;

  // ---------------------------------------------------------------------------
  // 1. Field widths. Each is the model's and not this file's: the packed fields'
  //    widths are cap_format.sail's, the permission bitmap's and the reserved
  //    object-type count are cap_common.sail's, and the register width is
  //    core/xlen.sail's. Rule K-79 reads them out of those three and holds every
  //    site below against them.
  //
  //    The six packed fields spend 64 bits exactly, which is why no reserved
  //    field, no software-defined permission field, no capability-mode flag and no
  //    revocation colour appears: each would need a bit the table has already
  //    spent. That sum is arithmetic rather than a claim, and K-79 recomputes it
  //    at this packing and at the model's.
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
  // permission. The expansion is in section 4.
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

  // Narrows to the largest admitted set contained in `want`. **The caller
  // intersects first**, and that is a precondition rather than a nicety: what
  // makes `candperm` unable to widen is `want` already being the capability's own
  // set masked, so a caller handing this an unrelated mask gets the largest
  // admitted set inside that mask and not a subset of what the input held. The
  // model states the same obligation at `setCapPerms` and has a caller that meets
  // it; here there is no caller yet, so this is the only place it can be written.
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
  // exponent k.
  //
  // The model's own account of that adds "the effective exponent runs to
  // cap_max_E, so k+1 runs to 31 and the five bits are spent exactly", and that
  // sentence is true of a requested top at or below 2^CapAddrWidth and not above
  // it: `set_cap_bounds` reaches an internal exponent of 31 there, which
  // `capability_to_enc` below writes as 31 + 1 in five bits, so the field reads
  // back as the denormal case and section 8's clamp catches it. It is not
  // restated as this file's claim for that reason. Which requested tops the
  // sentence covers is part of what R-15-007a owes and is not decided here.
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

  // Derived from the null capability rather than written out beside it, which is
  // what `cap_common.sail`'s `let null_cap_bits : CapBits = capToBits(null_cap)`
  // does: the exponent field this packs is the reset exponent plus one, so a
  // spelled-out literal would be a second statement of the reset bounds that an
  // edit to `CapResetE` could not reach.
  localparam cap_bits_t NullCapBits = capability_to_bits(NullCap);

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
  //
  // **`get_cap_bounds` is the model's `getCapBoundsBits` and not its
  // `getCapBounds`**, which is the one place a name in this file does not
  // transliterate its Sail counterpart. Sail has an unbounded integer type and
  // states the pair twice, once over bits and once over integers; SystemVerilog
  // has only the first, so there is one function here and it is the bits-valued
  // one. The same holds for `get_cap_top_bits` and `get_cap_offset_bits`.
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

  function automatic capability_t clear_tag(capability_t cap);
    capability_t ret = cap;
    ret.tag = 1'b0;
    return ret;
  endfunction

  function automatic capability_t clear_tag_if_sealed(capability_t cap);
    return clear_tag_if(cap, is_cap_sealed(cap));
  endfunction

  // ---------------------------------------------------------------------------
  // 9. The quantities read off the decoded bounds.
  //
  // Each is one line over section 8's decode and each is stated here rather than
  // open-coded at a caller, because the model states them and the caller that
  // recomputes one is the caller that will recompute it differently. The offset
  // is a modular quantity in the address space's own width, so it wraps at 2^36
  // and not at 2^64 (`cap_common.sail`, `getCapOffsetBits`).
  // ---------------------------------------------------------------------------

  // The address as an *effective* address, which is XLEN wide where the field is
  // 36 (R-15-002a): the widening is a reading of the field and never a path to an
  // access above 2^36, the bounds check in section 8 being stated over the wide
  // value.
  function automatic logic [Xlen-1:0] cap_addr_bits(capability_t c);
    return {{(Xlen - CapAddrWidth){1'b0}}, c.address};
  endfunction

  function automatic cap_addr_t get_cap_base(capability_t c);
    cap_bounds_t bounds = get_cap_bounds(c);
    return bounds.base;
  endfunction

  function automatic logic [Xlen-1:0] get_cap_base_bits(capability_t c);
    cap_bounds_t bounds = get_cap_bounds(c);
    return {{(Xlen - CapAddrWidth){1'b0}}, bounds.base};
  endfunction

  function automatic cap_len_t get_cap_top_bits(capability_t c);
    cap_bounds_t bounds = get_cap_bounds(c);
    return bounds.top;
  endfunction

  function automatic logic [Xlen-1:0] get_cap_offset_bits(capability_t c);
    cap_bounds_t bounds = get_cap_bounds(c);
    return {{(Xlen - CapAddrWidth){1'b0}}, (c.address - bounds.base)};
  endfunction

  function automatic cap_addr_t get_cap_cursor(capability_t c);
    return c.address;
  endfunction

  // The length, as the model states it: a **wrapping** quantity and not the
  // saturating one the imported datapath computes, whose own comment there calls
  // that saturation short of being correct (docs/rtl-reparameterization-delta.md
  // §2.1, line 493). For a tagged capability top is at or above base and this is
  // the plain difference; the representation admits top below base for some
  // untagged ones, and there the difference wraps at 2^cap_len_width, which is
  // what the 37-bit subtraction below does.
  function automatic cap_len_t get_cap_length(capability_t c);
    cap_bounds_t bounds = get_cap_bounds(c);
    return bounds.top - {1'b0, bounds.base};
  endfunction

  // The malformed predicate, and the whole of it: an encoding is malformed when
  // its own decode puts the top below the base. The imported datapath states this
  // as a case analysis on `exp == 0` and `exp == 1` over the ISAv8/v9 widths,
  // which has no reading at 8 and 6 bits; the frozen definition has no explicit
  // predicate at all and states the same fact as an assertion inside
  // `getCapLength` (`cap_common.sail`, `assert(not(c.tag) | top >= base)`), so
  // this is that assertion made computable rather than a behaviour invented here.
  //
  // Which encodings satisfy it is a property of the algorithm at these widths and
  // is R-15-007a's to characterize; `tools/rtl.py crosscheck` decides the two
  // implementations agree on it over the whole 19-bit bounds encoding, which is a
  // measurement and not that characterization.
  function automatic logic cap_bounds_malformed(capability_t c);
    cap_bounds_t bounds = get_cap_bounds(c);
    return bounds.top < {1'b0, bounds.base};
  endfunction

  function automatic logic cap_bounds_equal(capability_t c1, capability_t c2);
    cap_bounds_t a = get_cap_bounds(c1);
    cap_bounds_t b = get_cap_bounds(c2);
    return (a.base == b.base) && (a.top == b.top);
  endfunction

  // ---------------------------------------------------------------------------
  // 10. The bounds construction.
  //
  // `setCapBounds` of `cap_common.sail`, which is the CHERI Concentrate paper's
  // ideal narrowing at the frozen widths. It is authored against that statement
  // rather than re-parameterized from the imported `set_cap_reg_bounds`, for the
  // reason [docs/rtl-reparameterization-delta.md] §2.1 gives at that row: the
  // frozen format has no internal-exponent flag and steals no mantissa bits, so
  // the imported function's `int_exp`, `lmask_lo`, `lmask_lo_ovflw`,
  // `len_carry_in`, `len_max` and `len_max_less_1` family has nothing to compute
  // and its shape is not this one's.
  //
  // Three orderings inside it read like defects and are the definition's, so they
  // are reproduced and not repaired (the delta document's precedence note: where
  // this file and the model disagree the model wins).
  //
  //   * `norm` is decided from the exponent chosen *before* any increment and is
  //     never recomputed, so an incremented exponent can sit beside a denormal
  //     case flag.
  //   * Inside the increment branch the base's lost-significance flag reads bit 0
  //     of the mantissa as it stood *before* the recompute, the top's reads bit 0
  //     of the mantissa as it stands *after* the +1 above, and the recomputed top
  //     mantissa's own +1 reads the flag that line has just updated. Reorder any
  //     two and the exactness verdict is wrong on a subset of inputs that still
  //     elaborates and still decodes.
  //   * The exponent the increment produces can be CapMaxE + 1, which this
  //     function returns as it stands and which section 5's encode then writes as
  //     32 truncated into five bits, so the field reads back as the denormal case
  //     and section 8's clamp catches it on the way back. The truncation is the
  //     encoder's and not this function's, which matters to a reader looking for
  //     where the value goes. Whether the case is reachable at all is a question
  //     about the requested top's domain and is part of what R-15-007a owes;
  //     nothing here decides it.
  //
  // The result carries the exactness verdict beside the capability because the
  // caller needs both: `csetbounds` narrows whether or not the narrowing was
  // exact, the region only ever growing, and `CSetBoundsExact` is excluded at the
  // architecture (R-15-007k, R-08-011) so no third answer is returned.
  // ---------------------------------------------------------------------------

  // A derivation's two answers: whether it was exact or representable, and the
  // capability it produced. Four functions return this shape and the model
  // returns a pair at each of them.
  typedef struct packed {
    logic        ok;
    capability_t cap;
  } cap_result_t;

  // The leading-zero count the exponent choice is made from, over the slice
  // `length[cap_addr_width .. cap_mantissa_width - 1]`. That slice is CapMaxE
  // bits wide at these parameters, which is why the count and the exponent share
  // a range: an all-zero length answers CapMaxE and gives exponent zero.
  function automatic int unsigned count_leading_zeros_len(logic [CapMaxE-1:0] v);
    int unsigned n;
    n = CapMaxE;
    // Ascending, so the last index at which a bit is set is the most significant
    // one and its answer is the one left standing.
    for (int unsigned i = 0; i < CapMaxE; i++) begin
      if (v[i]) begin
        n = (CapMaxE - 1) - i;
      end
    end
    return n;
  endfunction

  function automatic cap_result_t set_cap_bounds(capability_t cap, cap_addr_t base,
                                                 cap_len_t top);
    cap_result_t ret;
    cap_len_t    ext_base;
    cap_len_t    length;
    cap_len_t    mask_lo;
    int unsigned e;
    logic        norm;
    cap_mant_t   b_bits;
    cap_mant_t   t_bits;
    cap_mant_t   len_mant;
    logic        lost_base;
    logic        lost_top;
    logic        inc_e;

    ext_base = {1'b0, base};
    length   = top - ext_base;

    // The exponent that puts the length's most significant bit second from the
    // top of the mantissa, which is what decoding assumes.
    e = CapMaxE - count_leading_zeros_len(length[CapLenWidth-1:CapMantissaWidth-1]);

    // The denormal case is an exponent of zero whose length does not reach the
    // mantissa's half, which is the one case decoding cannot infer 0b01 for.
    norm = (e != 0) || (length[CapMantissaWidth-2] == 1'b1);

    b_bits  = cap_mant_t'(base >> e);
    t_bits  = cap_mant_t'(top >> e);

    // The bits the shift drops, against which significance is decided.
    mask_lo   = ~({CapLenWidth{1'b1}} << e);
    lost_base = |(ext_base & mask_lo);
    lost_top  = |(top & mask_lo);
    inc_e     = 1'b0;

    // The top mantissa must be incremented to stay above the requested top with
    // the lost bits. It may wrap, and decoding compensates where that makes the
    // base mantissa exceed it.
    if (lost_top) begin
      t_bits = t_bits + 8'd1;
    end

    // Has the length overflowed? The exponent was chosen so that the length
    // mantissa's top two bits would be 0b01, and incrementing the top can grow it
    // past that.
    len_mant = t_bits - b_bits;
    if (len_mant[CapMantissaWidth-1] == 1'b1) begin
      inc_e     = 1'b1;
      lost_base = lost_base | b_bits[0];
      lost_top  = lost_top | t_bits[0];
      b_bits    = cap_mant_t'(base >> (e + 1));
      t_bits    = cap_mant_t'(top >> (e + 1)) + (lost_top ? 8'd1 : 8'd0);
    end

    ret.cap            = cap;
    ret.cap.address    = base;
    ret.cap.e          = cap_e_t'(inc_e ? (e + 1) : e);
    ret.cap.b          = b_bits;
    ret.cap.t          = t_bits;
    ret.cap.normalized = norm;
    ret.ok             = ~(lost_base | lost_top);
    return ret;
  endfunction

  // ---------------------------------------------------------------------------
  // 11. Representability, and the setters that rest on it.
  //
  // A derivation that moves the address outside the region the encoding can
  // represent yields an **untagged result and not a trap** (R-15-007h): the
  // failure is a data value that faults at its next dereference, so the check
  // below decides a tag and never an exception.
  //
  // Two checks, and they are not interchangeable. `setCapAddr` decides
  // representability by decoding the bounds on both sides and requiring them
  // equal, which is exact and costs two decodes. `fastRepCheck` decides the same
  // question about an *increment* from the representable limit alone, which is
  // the comparison the datapath can afford, and the offset setters take it. The
  // imported datapath's `is_offset_in_range` is not the counterpart of either: it
  // assigns its result and then overwrites it with zero unconditionally, which is
  // why the delta document books that row as a deletion rather than a rewrite.
  // ---------------------------------------------------------------------------

  // The fast representability check of `cap_common.sail`. `i` is the increment,
  // read as a signed quantity in the address field's own width.
  //
  // It reads the exponent raw, without the `min(cap_max_E, ...)` clamp the decode
  // in section 8 applies, and answers true outright at and above `cap_max_E - 2`
  // because there the representable region is the whole address space.
  function automatic logic fast_rep_check(capability_t c, cap_addr_t i);
    logic        ret;
    int unsigned e;
    cap_addr_t   i_top;
    cap_mant_t   i_mid;
    cap_mant_t   a_mid;
    logic [2:0]  b3;
    logic [2:0]  r3;
    cap_mant_t   r_full;
    cap_mant_t   diff;
    cap_mant_t   diff1;

    e = 32'(c.e);
    if (e >= (CapMaxE - 2)) begin
      ret = 1'b1;
    end else begin
      // The increment's own top decides both whether it is inside the
      // representable region, which is 2^(E+MW) wide, and its sign, so the only
      // cases of interest are an i_top of 0 and of -1.
      i_top  = cap_addr_t'($signed(i) >>> (e + CapMantissaWidth));
      i_mid  = cap_mant_t'(i >> e);
      a_mid  = cap_mant_t'(c.address >> e);
      b3     = c.b[CapMantissaWidth-1:CapMantissaWidth-3];
      r3     = b3 - 3'b001;
      r_full = {r3, {(CapMantissaWidth - 3){1'b0}}};
      diff   = r_full - a_mid;
      diff1  = diff - 8'd1;
      if (i_top == '0) begin
        ret = i_mid < diff1;
      end else if (&i_top) begin
        ret = (i_mid >= diff) && (r_full != a_mid);
      end else begin
        ret = 1'b0;
      end
    end
    return ret;
  endfunction

  function automatic cap_result_t set_cap_addr(capability_t c, logic [Xlen-1:0] addr);
    cap_result_t ret;
    ret.cap         = c;
    ret.cap.address = addr[CapAddrWidth-1:0];
    ret.ok          = addr_in_range(addr) & cap_bounds_equal(c, ret.cap);
    return ret;
  endfunction

  // The tag is cleared where the move is unrepresentable **or** the input was
  // sealed, a sealed capability's address being immovable.
  function automatic capability_t set_cap_addr_checked(capability_t c,
                                                       logic [Xlen-1:0] addr);
    cap_result_t moved = set_cap_addr(c, addr);
    return clear_tag_if(moved.cap, ~moved.ok | is_cap_sealed(c));
  endfunction

  // The offset is measured from the decoded base, and the range test is on the
  // *offset* rather than on the address it produces, which is the model's own
  // asymmetry and not a slip: an offset above 2^36 is refused before the wrapped
  // address it would give is ever examined.
  function automatic cap_result_t set_cap_offset(capability_t c,
                                                 logic [Xlen-1:0] offset);
    cap_result_t ret;
    cap_bounds_t bounds;
    cap_addr_t   new_address;
    bounds          = get_cap_bounds(c);
    new_address     = bounds.base + offset[CapAddrWidth-1:0];
    ret.cap         = c;
    ret.cap.address = new_address;
    ret.ok          = addr_in_range(offset)
                      & fast_rep_check(c, new_address - c.address);
    return ret;
  endfunction

  function automatic capability_t set_cap_offset_checked(capability_t c,
                                                         logic [Xlen-1:0] offset);
    cap_result_t moved = set_cap_offset(c, offset);
    return clear_tag_if(moved.cap, ~moved.ok | is_cap_sealed(c));
  endfunction

  // The increment form, which carries no range test at all: the delta is taken
  // modulo the address field's width and the representability check is the whole
  // of the answer.
  function automatic cap_result_t inc_cap_offset(capability_t c,
                                                 logic [Xlen-1:0] delta);
    cap_result_t ret;
    cap_addr_t   d;
    d               = delta[CapAddrWidth-1:0];
    ret.cap         = c;
    ret.cap.address = c.address + d;
    ret.ok          = fast_rep_check(c, d);
    return ret;
  endfunction

  // With PCC relocation folded out, the integer program counter of a capability
  // is its address field widened to an effective address (R-15-001c).
  function automatic logic [Xlen-1:0] cap_to_integer_pc(capability_t cap);
    return cap_addr_bits(cap);
  endfunction

  function automatic capability_t update_cap_with_integer_pc(capability_t cap,
                                                             logic [Xlen-1:0] pc);
    return set_cap_addr_checked(cap, pc);
  endfunction

endpackage
