// SPDX-License-Identifier: Apache-2.0
//
// The SoC address map.
//
// **Generated, and not edited by hand.** Every figure below is read out of
// model/config/verifiedos.json, which is the artifact that fixes the placement
// of every aperture on this die (R-15-002b); this file is that map said in the
// language the SoC top is written in. Rule K-88 holds these bytes against what
// `python tools/run.py check --fix` writes, so an edit here is a finding rather
// than a change.
//
// Two things this package deliberately is not. It is not a device list: what a
// window's device does at these addresses is not stated by the composition and is
// not invented here. And it is not a permission decision: the three PMA bits per
// region are the composition's own, and what an access to an address no aperture
// claims should do is decided by no artifact in this repository and by nothing in
// this file (see vos_soc_decode.sv, which reports that case rather than resolving
// it).

package vos_soc_map_pkg;

  // R-15-002a: one physical address space, this wide. Every base and size
  // below is stated at 64 bits and lies inside it.
  localparam int unsigned VosPhysAddrBits = 36;

  // Where the attested devicetree is written (R-09-007). It shares the ROM
  // region with the boot ROM and the two are held apart at composition and
  // again where the blob is written, which is the only point its size is
  // known (model/model/postlude/validate_config.sail).
  localparam logic [63:0] VosDtbAddress = 64'h0000_0000_0000_1000;

  // The memory regions this composition declares, in its own order. A region
  // is where an access is decided before any aperture is consulted: the model
  // runs `pmaCheck` over exactly these attributes ahead of the fall-through
  // (model/model/sys/mem.sail), and an address outside every region is claimed
  // by nothing at all.
  localparam int unsigned VosRegionCount = 4;

  typedef struct packed {
    logic [63:0] base;
    logic [63:0] size;
    logic        io;          // IOMemory rather than MainMemory
    logic        executable;
    logic        readable;
    logic        writable;
  } vos_soc_region_t;

  localparam vos_soc_region_t VosRegions [VosRegionCount] = '{
    '{ base: 64'h0000_0000_0000_1000, size: 64'h0000_0000_0000_8000, io: 1'b1, executable: 1'b0, readable: 1'b1, writable: 1'b0 },
    '{ base: 64'h0000_0000_0200_0000, size: 64'h0000_0000_1000_0000, io: 1'b1, executable: 1'b0, readable: 1'b1, writable: 1'b1 },
    '{ base: 64'h0000_0000_8000_0000, size: 64'h0000_0000_8000_0000, io: 1'b0, executable: 1'b1, readable: 1'b1, writable: 1'b1 },
    '{ base: 64'h0000_0001_0000_0000, size: 64'h0000_0002_0000_0000, io: 1'b0, executable: 1'b1, readable: 1'b1, writable: 1'b1 }
  };

  // Every window the composition declares and gives an extent, in its own
  // order. Found by shape rather than by a list of names, so a window the
  // composition gains arrives here without an edit; what obliges each one to
  // sit where it sits is R-15-002b, and what obliges the devices to exist at
  // all is the implementation plan rather than the register.
  localparam int unsigned VosApertureCount = 10;

  typedef struct packed {
    logic [63:0] base;
    logic [63:0] size;
  } vos_soc_aperture_t;

  localparam vos_soc_aperture_t VosApertures [VosApertureCount] = '{
    '{ base: 64'h0000_0000_0200_0000, size: 64'h0000_0000_000c_0000 },
    '{ base: 64'h0000_0000_0210_0000, size: 64'h0000_0000_0000_1000 },
    '{ base: 64'h0000_0000_0230_0000, size: 64'h0000_0000_0000_1000 },
    '{ base: 64'h0000_0000_0240_0000, size: 64'h0000_0000_0000_1000 },
    '{ base: 64'h0000_0000_0250_0000, size: 64'h0000_0000_0000_1000 },
    '{ base: 64'h0000_0000_0260_0000, size: 64'h0000_0000_0000_1000 },
    '{ base: 64'h0000_0000_0270_0000, size: 64'h0000_0000_0000_1000 },
    '{ base: 64'h0000_0000_0000_5000, size: 64'h0000_0000_0000_4000 },
    '{ base: 64'h0000_0000_0280_0000, size: 64'h0000_0000_0000_1000 },
    '{ base: 64'h0000_0000_0290_0000, size: 64'h0000_0000_0000_1000 }
  };

  // The index each window sits at, so that a reader naming one window in
  // this package can find it in the composition under the same name.
  localparam int unsigned VosApClint = 0;
  localparam int unsigned VosApImsic = 1;
  localparam int unsigned VosApMemorySequencer = 2;
  localparam int unsigned VosApOtp = 3;
  localparam int unsigned VosApTrng = 4;
  localparam int unsigned VosApMonotonicCounters = 5;
  localparam int unsigned VosApWatchdog = 6;
  localparam int unsigned VosApBootRom = 7;
  localparam int unsigned VosApUart = 8;
  localparam int unsigned VosApBlkdev = 9;

  // The window whose extent the composition does not state. Its size is
  // `revocation_bitmap_bytes` in model/model/core/revocation.sail, a
  // function of the plane it covers rather than a configuration key, so
  // it is carried here as a base alone and is outside the table above.
  // Inventing an extent for it would be the unowned derived fact this
  // repository refuses, and a decoder over this package reaches it not
  // at all rather than wrongly.
  localparam int unsigned VosApertureCountUnsized = 1;
  localparam logic [63:0] VosApRevocationBase = 64'h0000_0000_0220_0000;

endpackage : vos_soc_map_pkg
