// SPDX-License-Identifier: Apache-2.0
//
// The SoC top's address decode, over the map the frozen composition writes.
//
// This is the map-facing half of the SoC top and nothing else. Given a physical
// address, an access width and an access kind, it answers three questions and
// deliberately refuses a fourth:
//
//   1. which declared memory region contains the whole access, if any;
//   2. whether that region's own PMA permits an access of this kind;
//   3. which declared MMIO aperture claims the address, if any;
//   4. and, where the access is inside an IO region that permits it and no aperture
//      claims it, it says so and stops.
//
// **The fourth is not decided here because no artifact in this repository decides
// it.** In the golden model an IO address no device claims falls through to the RAM
// path with `pmaCheck` already run ahead of it (model/model/sys/mem.sail), which is
// a fact about a composition whose doors have not arrived rather than an
// architectural statement: no register
// entry says what an unclaimed address inside a device region does, and the
// alternatives, a decode error and a silent read of zero, are observably different
// at the commit trace the co-simulation gate diffs. So both arms are exhibited and
// the top above chooses; a default written into this module would fix that choice by
// implication, which is the defect the split between the map and the top exists to
// avoid.
//
// **Nothing here is a device.** No register, no transmit path and no descriptor ring:
// an aperture index is the whole of what this hands upward, and what sits behind one
// is the imported reference the milestone brings in through its own gitlink.
//
// It is authored rather than generated, where vos_soc_map_pkg.sv beside it is
// generated: the map is a fact the composition owns and this is a reading of it.
// Nothing holds this module against the model's own `pmaCheck` today, and a
// cross-check that did would be this module's counterpart to what
// `run.py rtl crosscheck` already does for the capability format.

module vos_soc_decode
  import vos_soc_map_pkg::*;
#(
  // The access-width input's width. Five bits reaches sixteen bytes, which is one
  // capability-carrying granule pair and above anything the frozen profile's load
  // and store surface emits; it is a parameter rather than a literal so that a
  // caller with a wider burst is a parameter change and not an edit here.
  parameter int unsigned BytesWidth = 5
) (
  // The physical address, at the one width R-15-002a fixes.
  input  logic [VosPhysAddrBits-1:0]          addr_i,
  // How many bytes the access covers, from `addr_i` upward. Zero is no access and
  // decodes as a miss, so a caller that has not driven this gets a refusal rather
  // than a hit at address zero.
  input  logic [BytesWidth-1:0]               bytes_i,
  // The access kind, as the two independent facts a PMA is stated over. A fetch is
  // `fetch_i` alone, a load is neither, a store is `write_i` alone. A caller
  // asserting both asks for a region that is executable *and* writable, which no
  // region here is, so the malformed case refuses rather than admitting.
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

  // The access as the interval it is, widened to the width the map is stated at.
  // Computed over the full 64 bits rather than over `VosPhysAddrBits` so that an
  // access whose last byte crosses the top of the space compares as the address it
  // has rather than wrapping into a region that does not hold it.
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
        // One conjunct per asserted kind and the read bit for the kind that
        // asserts neither, so a fetch is decided by `executable` alone and never
        // additionally by `readable`, which is the model's own reading
        // (`pmaCheck` in model/model/sys/mem.sail) and not a stricter one here.
        permitted_o    = (~fetch_i | VosRegions[i].executable)
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

  // The one case this module reports and does not resolve. It is not a hypothetical:
  // the attested devicetree occupies the lower half of the ROM region, is claimed by
  // no aperture because it is a blob rather than a device, and lands here on every
  // composed die.
  assign unclaimed_io_o = region_hit_o & permitted_o & ~aperture_hit_o
                        & VosRegions[region_index_o].io;

endmodule : vos_soc_decode
