// SPDX-License-Identifier: Apache-2.0
module vos_scalar_width_tb;
  import vos_cheri_pkg::*;
  import vos_scalar_width_pkg::*;
  logic [MemoryBits-1:0] data_word;
  logic [MemoryBits-1:0] expected_word;
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
    $display("scalar width: memory=%0d register=%0d PCC=%0d; all store bits/lanes PASS",
             MemoryBits, RegisterBits, PccBits);
    $finish;
  end
endmodule
