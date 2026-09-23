// SPDX-License-Identifier: Apache-2.0
//
// The co-simulation harness's frame writer: one line per retirement, in the frame
// `tools/vos/rtltrace.py` decodes (version 1), written by the Verilator harness that
// drives the curated scalar core.
//
// This is a checking harness and not something this repository synthesizes, so it
// lives beside the tool that runs it, on the precedent `tools/cheri-equiv/` sets for
// the capability cross-check. Its contract is
// docs/assurance/rtl-cosimulation-harness.md; what it writes is decided there and in
// `rtltrace.py`, and this file is one producer of it.
//
// **What it converts and what it passes through.** The destination write arrives in
// the register form the datapath computes in, `cva6_cheri_pkg::cap_reg_t`, and leaves
// as the two halves of its memory encoding through `cap_reg_to_cap_mem`, the one
// implementation of that algebra the RTL has, so the frame's `rd_tag`/`rd_wdata` are
// the bits a store of the register writes (commit-trace schema v1). Every other field
// is written as the port states it: a harness that repaired what the port reports
// would hide the defect the comparison exists to find. Two fields follow the frame's
// own rules rather than repairing anything. A retirement naming x0 writes zero data
// and no tag, which is RVFI's rule, and it matters here because the register form of
// an all-zero input does not encode to zero. And `cause` is written only where the
// retirement trapped, the imported port assigning the commit stage's exception
// cause on every cycle, valid or not.
//
// **A retirement is `valid` or `trap`, and ports retire in port order within a
// cycle.** The imported `cva6_rvfi.sv` at the pin raises `valid` on a synchronous
// exception only for the environment calls and the capability cause, so a harness
// sampling `valid` alone would drop every other trap. `order` is this writer's own
// count; the harness contract says why that makes the decoder's order check a check
// on this writer rather than on the core.
//
// Nothing here is verified against the core, which does not elaborate yet.
// `tools/run.py testrig framesim` builds this module behind its testbench and holds
// the frame it writes to the decoder.

module vos_rvfi_frame #(
    parameter int unsigned NRET = 1,
    parameter string PATH = "rtl.frame"
) (
    input logic                                clk_i,
    input logic                                rst_ni,
    input logic                                finish_i,
    input logic [NRET-1:0]                     valid_i,
    input logic [NRET-1:0]                     trap_i,
    input logic [NRET-1:0][63:0]               cause_i,
    input logic [NRET-1:0][63:0]               pc_rdata_i,
    input logic [NRET-1:0][63:0]               pc_wdata_i,
    input logic [NRET-1:0][31:0]               insn_i,
    input logic [NRET-1:0][4:0]                rd_addr_i,
    input cva6_cheri_pkg::cap_reg_t [NRET-1:0] rd_wdata_i,
    input logic [NRET-1:0][63:0]               mem_addr_i,
    input logic [NRET-1:0][7:0]                mem_rmask_i,
    input logic [NRET-1:0][7:0]                mem_wmask_i,
    input logic [NRET-1:0]                     mem_rtag_i,
    input logic [NRET-1:0]                     mem_wtag_i,
    input logic [NRET-1:0][63:0]               mem_rdata_i,
    input logic [NRET-1:0][63:0]               mem_wdata_i
);
  import cva6_cheri_pkg::*;

  int fd;
  logic [63:0] order;
  logic closed;
  string path;

  // `+frame=PATH` names the file at run time, so one build writes as many frames as
  // its harness runs programs; the parameter is the default.
  initial begin
    path = PATH;
    void'($value$plusargs("frame=%s", path));
    fd = $fopen(path, "w");
    if (fd == 0) $fatal(1, "cannot open the frame %s", path);
    $fwrite(fd, "vos-rtl-rvfi 1\n");
  end

  // The harness holds reset for at least one clock before the first retirement, which
  // is when the count starts; nothing is written while reset is asserted.
  always_ff @(posedge clk_i) begin
    if (!rst_ni) begin
      order  <= '0;
      closed <= 1'b0;
    end else if (!closed) begin
      // The count within one cycle is local, so a second port's line carries the
      // order after the first's, and the register takes the cycle's total once.
      automatic logic [63:0] next = order;
      for (int i = 0; i < int'(NRET); i++) begin
        if (valid_i[i] || trap_i[i]) begin
          automatic capw_t       mem   = cap_reg_to_cap_mem(rd_wdata_i[i]);
          automatic logic        x0    = rd_addr_i[i] == 5'd0;
          automatic logic        rdtag = x0 ? 1'b0 : mem[CTLEN-1];
          automatic logic [63:0] rd    = x0 ? 64'd0 : mem[63:0];
          automatic logic [63:0] cause = trap_i[i] ? cause_i[i] : 64'd0;
          // `%h` prints a vector at its own width with leading zeros, so each field
          // lands at the width the frame fixes for it.
          $fwrite(fd, "P %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",
                  next, pc_rdata_i[i], pc_wdata_i[i], insn_i[i], trap_i[i], cause,
                  rd_addr_i[i], rdtag, rd, mem_addr_i[i], mem_rmask_i[i],
                  mem_wmask_i[i], mem_rtag_i[i], mem_wtag_i[i], mem_rdata_i[i],
                  mem_wdata_i[i]);
          next = next + 64'd1;
        end
      end
      order <= next;
      if (finish_i) begin
        $fwrite(fd, "E %0d\n", next);
        $fclose(fd);
        closed <= 1'b1;
      end
    end
  end
endmodule
