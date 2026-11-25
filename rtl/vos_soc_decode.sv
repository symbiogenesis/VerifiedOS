// SPDX-License-Identifier: Apache-2.0
//
// Decode complete physical access intervals against the generated SoC map.
// Region and aperture hits report geometric containment independently. The
// permission output applies the matched region's PMA to the access kind.
// Consumers must check permission before routing a hit.
//
// For permitted IO with no aperture, the decoder asserts unclaimed_io_o.
// [The routing contract](../docs/hardware/platform-device-contracts.md#unclaimed-io-and-the-attested-device-tree)
// assigns that case to [the route module](vos_device_route.sv). SoC agreement
// still requires Sail fallback alignment and core-facing integration.

module vos_soc_decode
  import vos_soc_map_pkg::*;
#(
  // Width of the byte-count input. Five bits encodes counts from 0 to 31.
  parameter int unsigned BytesWidth = 5
) (
  // The physical address, at the one width R-15-002a fixes.
  input  logic [VosPhysAddrBits-1:0]          addr_i,
  // Number of bytes starting at addr_i. A zero count yields no hit.
  input  logic [BytesWidth-1:0]               bytes_i,
  // Fetch and store each assert their own bit. A load clears both.
  // Asserting both bits denies permission even when the interval hits a region.
  input  logic                                fetch_i,
  input  logic                                write_i,

  // Whether one declared region contains the whole access, and which.
  output logic                                region_hit_o,
  output logic [$clog2(VosRegionCount)-1:0]   region_index_o,
  // Whether that region's PMA permits this access. False wherever no region hits,
  // so a reader may take this as the whole verdict of the region layer.
  output logic                                permitted_o,
  // Whether one declared aperture contains the whole access, and which.
  output logic                                aperture_hit_o,
  output logic [$clog2(VosApertureCount)-1:0] aperture_index_o,
  // The case above that this module does not decide: permitted, inside a device
  // region, and claimed by no aperture.
  output logic                                unclaimed_io_o
);

  // Compare the half-open interval [access_lo, access_hi) at map width.
  // Widen before adding so a scalar access across the physical address limit
  // retains its out-of-range end for the containment checks.
  logic [63:0] access_lo;
  logic [63:0] access_hi;

  assign access_lo = {{(64 - VosPhysAddrBits) {1'b0}}, addr_i};
  assign access_hi = access_lo + {{(64 - BytesWidth) {1'b0}}, bytes_i};

  // A region hit is containment of the whole access and never of its first byte.
  // An access that begins inside a region and ends past it is claimed by neither,
  // which is the fail-closed reading: a straddling access has no single set of
  // attributes to be decided against.
  always_comb begin
    region_hit_o   = 1'b0;
    region_index_o = '0;
    permitted_o    = 1'b0;
    for (int unsigned i = 0; i < VosRegionCount; i++) begin
      if (bytes_i != '0
          && access_lo >= VosRegions[i].base
          && access_hi <= (VosRegions[i].base + VosRegions[i].size)) begin
        region_hit_o   = 1'b1;
        region_index_o = ($clog2(VosRegionCount))'(i);
        // Apply the access-kind permissions selected by
        // [pmaCheck](../model/model/sys/mem.sail#pmaCheck). A fetch uses the
        // executable bit alone. The leading term rejects the invalid encoding.
        permitted_o    = ~(fetch_i & write_i)
                       & (~fetch_i | VosRegions[i].executable)
                       & (~write_i | VosRegions[i].writable)
                       & (fetch_i | write_i | VosRegions[i].readable);
      end
    end
  end

  always_comb begin
    aperture_hit_o   = 1'b0;
    aperture_index_o = '0;
    for (int unsigned i = 0; i < VosApertureCount; i++) begin
      if (bytes_i != '0
          && access_lo >= VosApertures[i].base
          && access_hi <= (VosApertures[i].base + VosApertures[i].size)) begin
        aperture_hit_o   = 1'b1;
        aperture_index_o = ($clog2(VosApertureCount))'(i);
      end
    end
  end

  // The attested device-tree interval has no aperture. The route module
  // uses this flag together with the composed interval and access kind.
  assign unclaimed_io_o = region_hit_o & permitted_o & ~aperture_hit_o
                        & VosRegions[region_index_o].io;

endmodule : vos_soc_decode
