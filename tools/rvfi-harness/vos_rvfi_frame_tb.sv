// SPDX-License-Identifier: Apache-2.0
//
// Drives `vos_rvfi_frame` from a stimulus file, one retirement per line, so the frame
// it writes can be held to the decoder in `tools/vos/rtltrace.py`.
//
// The stimulus is what `tools/run.py testrig framesim` writes: each line is one
// 512-bit word, `stim_t` below, with the destination given in its memory form. The
// bench turns that into the register form through `cap_mem_to_cap_reg`, which is
// the form the datapath's port carries, and the writer turns it back through
// `cap_reg_to_cap_mem`; a frame that comes back with the bits it was given is the
// round trip through the authored format package over every value the stimulus
// holds. A line naming x0 drives the all-zero register form, which is what the
// imported port presents there, and the writer must still write zero. A line with
// neither `valid` nor `trap` is an idle cycle and must write nothing.
//
// This is a fixture driver and not the core: what it establishes is the writer's
// protocol and the conversion's round trip, never the datapath's behaviour.

module vos_rvfi_frame_tb;
  import cva6_cheri_pkg::*;

  typedef struct packed {
    logic [5:0]  pad;
    logic        valid;
    logic        trap;
    logic [63:0] cause;
    logic [63:0] pc_rdata;
    logic [63:0] pc_wdata;
    logic [31:0] insn;
    logic [4:0]  rd_addr;
    logic        rd_tag;
    logic [63:0] rd_bits;
    logic [63:0] mem_addr;
    logic [7:0]  mem_rmask;
    logic [7:0]  mem_wmask;
    logic        mem_rtag;
    logic        mem_wtag;
    logic [63:0] mem_rdata;
    logic [63:0] mem_wdata;
  } stim_t;

  localparam int MaxLines = 16384;

  stim_t    stim [MaxLines];
  stim_t    cur;
  cap_reg_t rd_reg;
  string    path;
  int       count;
  logic     clk = 1'b0;
  logic     rst_n = 1'b0;
  logic     finish = 1'b0;

  always_comb begin
    rd_reg = (cur.rd_addr == 5'd0) ? cap_reg_t'('0)
                                   : cap_mem_to_cap_reg('{tag: cur.rd_tag, bits: cur.rd_bits});
  end

  vos_rvfi_frame #(.NRET(1)) writer (
      .clk_i      (clk),
      .rst_ni     (rst_n),
      .finish_i   (finish),
      .valid_i    (cur.valid),
      .trap_i     (cur.trap),
      .cause_i    (cur.cause),
      .pc_rdata_i (cur.pc_rdata),
      .pc_wdata_i (cur.pc_wdata),
      .insn_i     (cur.insn),
      .rd_addr_i  (cur.rd_addr),
      .rd_wdata_i (rd_reg),
      .mem_addr_i (cur.mem_addr),
      .mem_rmask_i(cur.mem_rmask),
      .mem_wmask_i(cur.mem_wmask),
      .mem_rtag_i (cur.mem_rtag),
      .mem_wtag_i (cur.mem_wtag),
      .mem_rdata_i(cur.mem_rdata),
      .mem_wdata_i(cur.mem_wdata)
  );

  task automatic tick();
    #1 clk = 1'b1;
    #1 clk = 1'b0;
  endtask

  initial begin
    if (!$value$plusargs("stimulus=%s", path)) $fatal(1, "no +stimulus= file named");
    if (!$value$plusargs("count=%d", count)) $fatal(1, "no +count= given");
    if (count < 0 || count > MaxLines) $fatal(1, "count %0d is outside 0..%0d", count, MaxLines);
    if (count > 0) $readmemh(path, stim, 0, count - 1);
    cur = '0;
    tick();
    rst_n = 1'b1;
    for (int i = 0; i < count; i++) begin
      cur = stim[i];
      tick();
    end
    cur = '0;
    finish = 1'b1;
    tick();
    $display("framesim: %0d stimulus line(s) driven", count);
    $finish;
  end
endmodule
