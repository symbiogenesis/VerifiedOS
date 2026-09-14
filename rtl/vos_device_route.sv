// SPDX-License-Identifier: Apache-2.0
// Device-facing route only. No core, loader or device is instantiated here.
module vos_device_route
  import vos_soc_map_pkg::*;
(
  input logic [VosPhysAddrBits-1:0] addr_i,
  input logic [4:0] bytes_i,
  input logic write_i, fetch_i, ordinary_i,
  output logic aperture_o, dtb_o, memory_o, error_o,
  output logic [$clog2(VosApertureCount)-1:0] aperture_index_o
);
  logic region_hit, permitted, aperture_hit, unclaimed_io;
  logic [$clog2(VosRegionCount)-1:0] region_index;
  logic [63:0] lo, hi;
  vos_soc_decode decode(.addr_i, .bytes_i, .fetch_i, .write_i,
    .region_hit_o(region_hit), .region_index_o(region_index), .permitted_o(permitted),
    .aperture_hit_o(aperture_hit), .aperture_index_o, .unclaimed_io_o(unclaimed_io));
  assign lo = 64'(addr_i);
  assign hi = lo + 64'(bytes_i);
  assign aperture_o = permitted && aperture_hit && ordinary_i;
  assign dtb_o = unclaimed_io && ordinary_i && !write_i && !fetch_i
               && lo >= VosDtbAddress && hi <= VosApertures[VosApBootRom].base;
  assign memory_o = region_hit && permitted && !VosRegions[region_index].io;
  assign error_o = !(aperture_o || dtb_o || memory_o);
endmodule
