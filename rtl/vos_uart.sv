// SPDX-License-Identifier: Apache-2.0
// Polled character wrapper: docs/hardware/platform-device-contracts.md.
module vos_uart (
  input logic clk_i, reset_i,
  input logic req_valid_i, req_write_i, req_ordinary_i,
  input logic [63:0] req_offset_i, req_data_i,
  input logic [4:0] req_bytes_i,
  output logic rsp_valid_o, rsp_error_o, rsp_tag_o,
  output logic [63:0] rsp_data_o,
  input logic rx_valid_i,
  input logic [7:0] rx_data_i,
  output logic rx_ready_o,
  output logic tx_valid_o,
  output logic [7:0] tx_data_o,
  input logic tx_ready_i
);
  import vos_device_regs_pkg::*;
  logic rx_full_q, tx_full_q;
  logic [7:0] rx_q, tx_q;
  logic read_byte, write_byte;
  assign rx_ready_o = !reset_i && !rx_full_q;
  assign tx_valid_o = !reset_i && tx_full_q;
  assign tx_data_o = tx_q;
  assign rsp_valid_o = req_valid_i && !reset_i;
  assign rsp_tag_o = 1'b0;
  always_comb begin
    rsp_error_o = 1'b1;
    rsp_data_o = '0;
    read_byte = 1'b0;
    write_byte = 1'b0;
    if (rsp_valid_o && req_ordinary_i && req_bytes_i == 4 && req_offset_i[1:0] == 0) begin
      case (req_offset_i)
        UART_STATUS: if (!req_write_i) begin
          rsp_error_o = 1'b0;
          rsp_data_o[UART_TXFULL_BIT] = tx_full_q;
          rsp_data_o[UART_RXFULL_BIT] = rx_full_q;
          rsp_data_o[UART_TXEMPTY_BIT] = !tx_full_q;
          rsp_data_o[UART_TXIDLE_BIT] = !tx_full_q;
          rsp_data_o[UART_RXIDLE_BIT] = !rx_valid_i;
          rsp_data_o[UART_RXEMPTY_BIT] = !rx_full_q;
        end
        UART_RDATA: if (!req_write_i && rx_full_q) begin
          rsp_error_o = 1'b0;
          rsp_data_o[7:0] = rx_q;
          read_byte = 1'b1;
        end
        UART_WDATA: if (req_write_i && !tx_full_q) begin
          rsp_error_o = 1'b0;
          write_byte = 1'b1;
        end
        default: ;
      endcase
    end
  end
  always_ff @(posedge clk_i) begin
    if (reset_i) begin
      rx_full_q <= 1'b0;
      tx_full_q <= 1'b0;
      rx_q <= '0;
      tx_q <= '0;
    end else begin
      if (rx_valid_i && rx_ready_o) begin rx_q <= rx_data_i; rx_full_q <= 1'b1; end
      if (read_byte) begin rx_q <= '0; rx_full_q <= 1'b0; end
      if (tx_valid_o && tx_ready_i) begin tx_q <= '0; tx_full_q <= 1'b0; end
      if (write_byte) begin tx_q <= req_data_i[7:0]; tx_full_q <= 1'b1; end
    end
  end
endmodule
