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
endpackage
