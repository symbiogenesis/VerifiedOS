// SPDX-License-Identifier: Apache-2.0
// Frozen transport and store-lane helpers, owned by cap_format.sail.
package vos_scalar_width_pkg;
  import vos_cheri_pkg::*;
  localparam int unsigned MemoryBits = CapWidth;
  localparam int unsigned RegisterBits = $bits(capability_t);
  localparam int unsigned PccBits = RegisterBits;
  localparam int unsigned ByteLaneBits = $clog2(CapSize);

  function automatic logic [MemoryBits-1:0] align_store(
      logic [3:0] address, logic [MemoryBits-1:0] data);
    int unsigned shift_bits = int'(address[ByteLaneBits-1:0]) * 8;
    return (data << shift_bits) | (data >> (MemoryBits - shift_bits));
  endfunction

  // The merged register file's integer view (`regval_from_reg` and
  // `regval_into_reg`, reg_type.sail). A register holds the decoded capability,
  // so its integer reading is the memory form and not a slice of the record:
  // the low 36 bits of both are the address, and the upper 28 differ. An
  // integer write decodes the integer's bits untagged. Reading back returns the
  // integer: the packed form's decode copies every field or, for the exponent,
  // keeps the case flag that re-encodes it, and the null transform cancels. The
  // width check exercises that over a finite set of integers.
  function automatic logic [MemoryBits-1:0] reg_to_int(capability_t r);
    return capability_to_mem_bits(r);
  endfunction

  function automatic capability_t int_to_reg(logic [MemoryBits-1:0] x);
    return int_to_cap(x);
  endfunction
endpackage
