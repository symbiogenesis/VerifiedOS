// SPDX-License-Identifier: Apache-2.0
module vos_scalar_width_tb;
  import vos_cheri_pkg::*;
  import vos_scalar_width_pkg::*;
  logic [MemoryBits-1:0] data_word;
  logic [MemoryBits-1:0] expected_word;
  logic [MemoryBits-1:0] lfsr;
  capability_t type_root;
  int unsigned integers;

  // The merged file's integer view is a round trip over every integer and an
  // untagged write, and over an address it is the address (reg_type.sail).
  task automatic check_integer(logic [MemoryBits-1:0] v);
    capability_t r = int_to_reg(v);
    if (reg_to_int(r) !== v) $fatal(1, "integer view round trip at %h", v);
    if (r.tag !== 1'b0) $fatal(1, "an integer write carries no tag at %h", v);
    if (v[MemoryBits-1:CapAddrWidth] == '0 && cap_addr_bits(r) !== v)
      $fatal(1, "an address reads back as itself at %h", v);
    integers++;
  endtask

  // A reset root is tagged, unsealed, global, and survives the memory form.
  task automatic check_root(capability_t c, string name);
    if (!c.tag || is_cap_sealed(c) || !cap_global(c))
      $fatal(1, "%s: a reset root is tagged, unsealed and global", name);
    if (mem_bits_to_capability(1'b1, capability_to_mem_bits(c)) !== c)
      $fatal(1, "%s: the memory form round-trips", name);
  endtask

  initial begin
    if (MemoryBits != Xlen || MemoryBits != CapSize * 8)
      $fatal(1, "memory and integer widths must agree");
    if (RegisterBits != $bits(cva6_cheri_pkg::cap_reg_t) || PccBits != RegisterBits)
      $fatal(1, "register and PCC widths must derive from the frozen record");
    if ($bits(cva6_cheri_pkg::cap_mem_t) != MemoryBits + 1)
      $fatal(1, "memory carries exactly one validity tag");
    for (int lane = 0; lane < 16; lane++) begin
      for (int bit_index = 0; bit_index < MemoryBits; bit_index++) begin
        data_word = '0;
        expected_word = '0;
        data_word[bit_index] = 1'b1;
        expected_word[(bit_index + (lane % CapSize) * 8) % MemoryBits] = 1'b1;
        if (align_store(4'(lane), data_word) !== expected_word)
          $fatal(1, "store rotation lane %0d bit %0d", lane, bit_index);
      end
    end

    integers = 0;
    check_integer('0);
    check_integer('1);
    check_integer({(MemoryBits / 2){2'b01}});
    check_integer({(MemoryBits / 2){2'b10}});
    for (int bit_index = 0; bit_index < MemoryBits; bit_index++) begin
      check_integer(MemoryBits'(1) << bit_index);
      check_integer(~(MemoryBits'(1) << bit_index));
      check_integer((MemoryBits'(1) << bit_index) - 1);
    end
    lfsr = 64'hACE1_2468_BDF1_3579;
    for (int n = 0; n < 65536; n++) begin
      check_integer(lfsr);
      lfsr = {lfsr[62:0], lfsr[63] ^ lfsr[62] ^ lfsr[60] ^ lfsr[59]};
    end

    check_root(RootCodeCap, "code root");
    check_root(RootDataCap, "data root");
    check_root(RootSealCap, "seal root");
    check_root(RootUnsealCap, "unseal root");
    if (!cap_permit_execute(RootCodeCap) || cap_permit_store(RootCodeCap))
      $fatal(1, "the code root executes and does not store");
    if (!cap_permit_store(RootDataCap) || cap_permit_execute(RootDataCap))
      $fatal(1, "the data root stores and does not execute");
    for (int k = 0; k < 2; k++) begin
      type_root = (k == 0) ? RootSealCap : RootUnsealCap;
      if (cap_permit_load(type_root) || cap_permit_store(type_root)
          || cap_permit_execute(type_root))
        $fatal(1, "an object-type root is memory-inert");
      if (cap_permit_seal(type_root) == cap_permit_unseal(type_root))
        $fatal(1, "an object-type root holds exactly one of seal and unseal");
      if (get_cap_base_bits(type_root) != '0
          || get_cap_top_bits(type_root) != cap_len_t'(CapMaxOType) + cap_len_t'(1)
          || cap_addr_bits(type_root) != '0)
        $fatal(1, "an object-type root spans the nonreserved types with its cursor at zero");
    end
    if (!cap_permit_seal(RootSealCap) || !cap_permit_unseal(RootUnsealCap))
      $fatal(1, "the seal root seals and the unseal root unseals");
    // The model's own unit test pins the two object-type roots' memory forms
    // (model/model/unit_tests/test_capability.sail), so a defect that kept the
    // properties above while moving a bit is refused here.
    if (capability_to_mem_bits(RootSealCap) !== 64'hf07c00d000000000
        || capability_to_mem_bits(RootUnsealCap) !== 64'hf87c00d000000000)
      $fatal(1, "the object-type roots' memory forms are the model's pinned ones");

    $display("scalar width: memory=%0d register=%0d PCC=%0d; all store bits/lanes PASS",
             MemoryBits, RegisterBits, PccBits);
    $display("integer view: %0d integers round-trip PASS; four reset roots PASS", integers);
    $finish;
  end
endmodule
