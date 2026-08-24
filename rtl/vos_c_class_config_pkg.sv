// SPDX-License-Identifier: Apache-2.0
//
// The curated C-class synthesis configuration.
//
// This package fills in the `config_pkg::cva6_user_cfg_t` record the imported
// CHERI-CVA6 core declares, at the values the profile and the absence contract
// require. Every field the provenance record names is written as a literal at
// the field rather than through a named parameter above it, so that the record
// and this package agree by reading rather than by indirection: rule K-76 holds
// the two against each other, and a value reached through a chain of localparams
// would put a hop between the claim and the setting.
//
// The record shape is the imported tree's, declared in its `config_pkg.sv` under
// Solderpad v2.0, which permits the licensee to elect Apache-2.0 and is the
// election this repository takes. What is authored here is the configuration and
// not the record it fills, and nothing imported is copied into this tree.
//
// This package elaborates. It is not verified: what it says about the netlist is
// what an elaborator reports, and whether the resulting core refines the Sail
// model is the co-simulation gate's to decide and not this file's to claim.

package cva6_config_pkg;

  localparam config_pkg::cva6_user_cfg_t cva6_cfg = '{
      XLEN: unsigned'(64),
      VLEN: unsigned'(64),
      FpgaEn: bit'(0),
      FpgaAlteraEn: bit'(0),
      TechnoCut: bit'(0),
      SuperscalarEn: bit'(0),
      ALUBypass: bit'(1),
      NrCommitPorts: unsigned'(1),
      AxiAddrWidth: unsigned'(64),
      AxiDataWidth: unsigned'(64),
      AxiIdWidth: unsigned'(4),
      AxiUserWidth: unsigned'(1),
      MemTidWidth: unsigned'(2),
      NrLoadBufEntries: unsigned'(2),

      // A-15: the scalar floating-point register file and every extended float
      // width with it. The rounding mode goes with them, being dynamic state.
      RVF: bit'(0),
      RVD: bit'(0),
      XF16: bit'(0),
      XF16ALT: bit'(0),
      XF8: bit'(0),
      XFVec: bit'(0),

      // A-13: the reservation register, which goes with the extension that has one.
      RVA: bit'(0),

      RVB: bit'(1),
      ZKN: bit'(0),

      // Not C-class: the vector and hypervisor extensions and the coprocessor.
      RVV: bit'(0),
      RVH: bit'(0),
      CvxifEn: bit'(0),
      CoproType: config_pkg::COPRO_NONE,

      // The compressed extension and its three companions.
      RVC: bit'(0),
      RVZCB: bit'(0),
      RVZCMT: bit'(0),
      RVZCMP: bit'(0),

      RVZiCond: bit'(1),

      // The cycle and performance counters the profile deletes.
      RVZicntr: bit'(0),
      RVZihpm: bit'(0),
      PerfCounterEn: bit'(0),

      // Purecap only: one mode, so the hybrid decode has nothing to select.
      RVZcheripurecap: bit'(1),
      RVZcherihybrid: bit'(0),

      NrScoreboardEntries: unsigned'(8),

      // A-14: the MMU, its walker, both TLBs and the shared one, and the two
      // rings whose existence is what a walker would serve.
      MmuPresent: bit'(0),
      RVS: bit'(0),
      RVU: bit'(0),
      InstrTlbEntries: int'(0),
      DataTlbEntries: int'(0),
      UseSharedTlb: bit'(0),
      SharedTlbDepth: int'(0),

      // The one asynchronous trap this machine has is the slot-boundary timer.
      SoftwareInterruptEn: bit'(0),

      HaltAddress: 64'h800,
      ExceptionAddress: 64'h808,

      // A-06, A-05 and A-04: every predictor array, and so every mutable
      // predictor state element on the fetch path.
      RASDepth: unsigned'(0),
      BTBEntries: unsigned'(0),
      BPType: config_pkg::BHT,
      BHTEntries: unsigned'(0),
      BHTHist: unsigned'(3),

      DmBaseAddress: 64'h0,
      TvalEn: bit'(1),
      DirectVecOnly: bit'(0),

      // PMP, whose authority path is the one capabilities replace.
      NrPMPEntries: unsigned'(0),
      PMPCfgRstVal: {64{64'h0}},
      PMPAddrRstVal: {64{64'h0}},
      PMPEntryReadOnly: 64'd0,
      PMPNapotEn: bit'(0),

      NOCType: config_pkg::NOC_TYPE_AXI4_ATOP,
      NrNonIdempotentRules: unsigned'(2),
      NonIdempotentAddrBase: 1024'({64'h0, 64'h2_0000}),
      NonIdempotentLength: 1024'({64'h1_0000, 64'h8000_0000 - 64'h2_0000}),
      NrExecuteRegionRules: unsigned'(3),
      ExecuteRegionAddrBase: 1024'({64'h8000_0000, 64'h1_0000, 64'h0}),
      ExecuteRegionLength: 1024'({64'h40000000, 64'h10000, 64'h1000}),
      NrCachedRegionRules: unsigned'(2),
      CachedRegionAddrBase: 1024'({64'h8000_0000, 64'h1_0000}),
      CachedRegionLength: 1024'({64'h40000000, 64'h1_0000}),
      MaxOutstandingStores: unsigned'(7),

      // The debug module is not imported and the trigger module is deleted in
      // every lifecycle state rather than fused off in one.
      DebugEn: bit'(0),
      SDTRIG: bit'(0),
      Mcontrol6: bit'(0),
      Icount: bit'(0),
      Etrigger: bit'(0),
      Itrigger: bit'(0),

      AxiBurstWriteEn: bit'(1),

      // A-09 and A-10 have no field here. The caches elaborate at every
      // configuration this record admits, so their sizes are stated as the
      // imported tree's defaults and their deletion is authoring work.
      IcacheByteSize: unsigned'(16384),
      IcacheSetAssoc: unsigned'(4),
      IcacheLineWidth: unsigned'(128),
      DCacheType: config_pkg::WT,
      DcacheByteSize: unsigned'(32768),
      DcacheSetAssoc: unsigned'(8),
      DcacheLineWidth: unsigned'(256),
      DcacheFlushOnFence: unsigned'(1),
      DcacheInvalidateOnFlush: unsigned'(0),

      DataUserEn: unsigned'(1),
      WtDcacheWbufDepth: int'(8),
      FetchUserWidth: unsigned'(64),
      FetchUserEn: unsigned'(0),
      NrLoadPipeRegs: int'(1),
      NrStorePipeRegs: int'(0),
      DcacheIdWidth: int'(1),

      // A-16: one tag plane and not two, stated rather than defaulted.
      CheriCapTagWidth: int'(1),

      RVFI_DII: int'(0)
  };

  // Four names the imported tree reads out of this package directly rather than
  // through the record above, so a configuration that declares only the record
  // does not elaborate. Each is **derived from** the field that already states
  // it, so the value is written once and this block cannot come to disagree with
  // the record it re-exports. `CVA6ConfigRvfiTrace` is the one with no field
  // behind it: it gates a tracer the imported tree instantiates outside the
  // record's reach, and nothing here wants that tracer.
  localparam CVA6ConfigXlen = cva6_cfg.XLEN;
  localparam CVA6ConfigDataUserWidth = cva6_cfg.CheriCapTagWidth;
  localparam CVA6ConfigRVZcheripurecap = cva6_cfg.RVZcheripurecap;
  localparam CVA6ConfigRvfiTrace = 0;

endpackage
