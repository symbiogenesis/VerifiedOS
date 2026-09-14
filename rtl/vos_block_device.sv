// SPDX-License-Identifier: Apache-2.0
// PIO control wrapper for interfaces/block-device-contract.md.
// The synchronous backend owns medium bytes, tear masks and host persistence.
module vos_block_device #(
  parameter int unsigned BlockBytes = 64,
  parameter int unsigned BlockCount = 2,
  parameter int unsigned ApertureBytes = 4096,
  parameter int unsigned ReadSteps = 2,
  parameter int unsigned WriteSteps = 2,
  parameter int unsigned FlushSteps = 1
) (
  input logic clk_i, reset_i,
  input logic req_valid_i, req_write_i, req_ordinary_i,
  input logic [63:0] req_offset_i, req_data_i,
  input logic [4:0] req_bytes_i,
  output logic rsp_valid_o, rsp_error_o, rsp_tag_o,
  output logic [63:0] rsp_data_o,
  input logic step_i, backend_error_i,
  input logic [BlockBytes*8-1:0] backend_read_i,
  output logic backend_commit_o, backend_tear_o,
  output logic [1:0] backend_command_o,
  output logic [63:0] backend_block_o,
  output logic [BlockBytes*8-1:0] backend_payload_o
);
  import vos_device_regs_pkg::*;
  localparam int unsigned Words = BlockBytes / 8;
  localparam logic [1:0] Idle = 0, Busy = 1, Done = 2, Error = 3;
  localparam logic [1:0] Read = 1, Write = 2, Flush = 3;
  logic [1:0] status_q, command_q;
  logic [2:0] result_q;
  logic [63:0] block_q, pending_block_q;
  logic [BlockBytes*8-1:0] staging_q, payload_q;
  logic [Words-1:0] written_q;
  int unsigned remaining_q;
  logic accepted, data_window, final_step;
  int unsigned word_index;

  initial begin
    if (BlockBytes == 0 || BlockBytes % 8 != 0 || BlockBytes > BLK_MAX_BLOCK_BYTES
        || BlockCount == 0 || 64'(BlockCount) * BlockBytes > 64'(BLK_MAX_BYTES)
        || 64'(ApertureBytes) < BLK_DATA || 64'(BlockBytes) > 64'(ApertureBytes) - BLK_DATA
        || ReadSteps == 0 || WriteSteps == 0 || FlushSteps == 0)
      $fatal(1, "block geometry/service parameters violate the bounded contract");
  end
  assign rsp_valid_o = req_valid_i && !reset_i;
  assign rsp_tag_o = 1'b0;
  assign accepted = rsp_valid_o && !rsp_error_o;
  assign data_window = req_offset_i >= BLK_DATA && req_offset_i < BLK_DATA + 64'(BlockBytes);
  assign word_index = int'((req_offset_i - BLK_DATA) >> 3);
  assign final_step = status_q == Busy && step_i && remaining_q == 1;
  assign backend_commit_o = !reset_i && final_step && !backend_error_i;
  assign backend_tear_o = status_q == Busy && command_q == Write
                         && (reset_i || (final_step && backend_error_i));
  assign backend_command_o = command_q;
  assign backend_block_o = pending_block_q;
  assign backend_payload_o = payload_q;

  always_comb begin
    rsp_error_o = 1'b1;
    rsp_data_o = '0;
    if (rsp_valid_o && !step_i && req_ordinary_i && req_bytes_i == 8
        && req_offset_i[2:0] == 0 && req_offset_i <= 64'(ApertureBytes) - 8) begin
      if (req_write_i) begin
        case (req_offset_i)
          BLK_BLOCK, BLK_COMMAND: rsp_error_o = status_q != Idle;
          BLK_ACK: rsp_error_o = !((status_q == Done || status_q == Error) && req_data_i == 1);
          default: if (data_window) rsp_error_o = status_q != Idle;
        endcase
      end else begin
        case (req_offset_i)
          BLK_VERSION: begin rsp_error_o = 0; rsp_data_o = 1; end
          BLK_BLOCK_BYTES: begin rsp_error_o = 0; rsp_data_o = 64'(BlockBytes); end
          BLK_BLOCK_COUNT: begin rsp_error_o = 0; rsp_data_o = 64'(BlockCount); end
          BLK_STATUS: begin rsp_error_o = 0; rsp_data_o = 64'(status_q); end
          BLK_RESULT: begin rsp_error_o = 0; rsp_data_o = 64'(result_q); end
          BLK_BLOCK: begin rsp_error_o = 0; rsp_data_o = block_q; end
          default: if (data_window && status_q == Done && command_q == Read) begin
            rsp_error_o = 0;
            rsp_data_o = staging_q[word_index*64 +: 64];
          end
        endcase
      end
    end
  end

  task automatic clear_volatile;
    status_q <= Idle;
    result_q <= 0;
    block_q <= 0;
    pending_block_q <= 0;
    staging_q <= '0;
    payload_q <= '0;
    written_q <= '0;
    command_q <= 0;
    remaining_q <= 0;
  endtask

  always_ff @(posedge clk_i) begin
    if (reset_i) clear_volatile();
    else begin
      if (status_q == Busy && step_i) begin
        if (remaining_q > 1) remaining_q <= remaining_q - 1;
        else begin
          remaining_q <= 0;
          status_q <= backend_error_i ? Error : Done;
          result_q <= backend_error_i ? 3'd4 : 3'd0;
          if (!backend_error_i && command_q == Read) staging_q <= backend_read_i;
          else staging_q <= '0;
          payload_q <= '0;
        end
      end
      if (accepted && req_write_i) begin
        case (req_offset_i)
          BLK_ACK: clear_volatile();
          BLK_BLOCK: begin block_q <= req_data_i; staging_q <= '0; written_q <= '0; end
          BLK_COMMAND: begin
            staging_q <= '0;
            written_q <= '0;
            result_q <= 0;
            if (req_data_i < 1 || req_data_i > 3) begin status_q <= Error; result_q <= 1; end
            else if (req_data_i != 3 && block_q >= 64'(BlockCount)) begin status_q <= Error; result_q <= 2; end
            else if (req_data_i == 2 && !(&written_q)) begin status_q <= Error; result_q <= 3; end
            else begin
              status_q <= Busy;
              command_q <= req_data_i[1:0];
              pending_block_q <= block_q;
              payload_q <= req_data_i == 2 ? staging_q : '0;
              case (req_data_i[1:0])
                Read: remaining_q <= ReadSteps;
                Write: remaining_q <= WriteSteps;
                Flush: remaining_q <= FlushSteps;
                default: remaining_q <= 0;
              endcase
            end
          end
          default: if (data_window) begin
            staging_q[word_index*64 +: 64] <= req_data_i;
            written_q[word_index] <= 1'b1;
          end
        endcase
      end
    end
  end
endmodule
