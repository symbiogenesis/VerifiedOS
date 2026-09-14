// SPDX-License-Identifier: Apache-2.0
module vos_devices_tb;
  import vos_device_regs_pkg::*;
  import vos_soc_map_pkg::*;
  logic clk = 0, reset = 1;
  logic bv = 0, bw = 0, bo = 1, step = 0, backend_error = 0;
  logic [63:0] ba = 0, bd = 0, br;
  logic [4:0] bn = 8;
  logic brv, bre, brt, commit, tear;
  logic [1:0] command;
  logic [63:0] block_number;
  logic [511:0] payload, backend_read, mask = '0;
  logic [511:0] media_image[2], original0, expected;
  logic uv = 0, uw = 0, uo = 1, urv, ure, urt;
  logic [63:0] ua = 0, ud = 0, ur;
  logic [4:0] un = 4;
  logic rxv = 0, rxready, txv, txready = 0;
  logic [7:0] rxdata = 0, txdata;
  logic [VosPhysAddrBits-1:0] address = 0;
  logic [4:0] bytes_count = 8;
  logic route_write = 0, route_fetch = 0, route_ordinary = 1;
  logic ap, dtb, memory_hit, route_error;
  logic [$clog2(VosApertureCount)-1:0] ap_index;
  int checks = 0;

  vos_block_device blockdev(.clk_i(clk), .reset_i(reset), .req_valid_i(bv), .req_write_i(bw),
    .req_ordinary_i(bo), .req_offset_i(ba), .req_data_i(bd), .req_bytes_i(bn),
    .rsp_valid_o(brv), .rsp_error_o(bre), .rsp_tag_o(brt), .rsp_data_o(br),
    .step_i(step), .backend_error_i(backend_error), .backend_read_i(backend_read),
    .backend_commit_o(commit), .backend_tear_o(tear), .backend_command_o(command),
    .backend_block_o(block_number), .backend_payload_o(payload));
  vos_uart uartdev(.clk_i(clk), .reset_i(reset), .req_valid_i(uv), .req_write_i(uw),
    .req_ordinary_i(uo), .req_offset_i(ua), .req_data_i(ud), .req_bytes_i(un),
    .rsp_valid_o(urv), .rsp_error_o(ure), .rsp_tag_o(urt), .rsp_data_o(ur),
    .rx_valid_i(rxv), .rx_data_i(rxdata), .rx_ready_o(rxready),
    .tx_valid_o(txv), .tx_data_o(txdata), .tx_ready_i(txready));
  vos_device_route route(.addr_i(address), .bytes_i(bytes_count), .write_i(route_write),
    .fetch_i(route_fetch), .ordinary_i(route_ordinary), .aperture_o(ap), .dtb_o(dtb),
    .memory_o(memory_hit), .error_o(route_error), .aperture_index_o(ap_index));

  assign backend_read = block_number < 2 ? media_image[int'(block_number)] : '0;
  // This is the explicit synchronous media_image boundary, not host persistence.
  always @(posedge clk) begin
    if (tear) media_image[int'(block_number)] <= (media_image[int'(block_number)] & ~mask) | (payload & mask);
    else if (commit && command == 2) media_image[int'(block_number)] <= payload;
  end
  task automatic check(input logic ok, input string why);
    checks++;
    if (ok !== 1'b1) $fatal(1, "%s", why);
  endtask
  task automatic tick;
    #1; clk = 1; #1; clk = 0; #1;
  endtask
  task automatic bus(input logic wr, input logic [63:0] offset, input logic [63:0] data,
                     input logic err, input logic [63:0] wanted = 0);
    bv = 1; bw = wr; ba = offset; bd = data; #1;
    check(brv && bre == err && !brt, "block response/error/tag");
    if (!wr && !err) check(br == wanted, "block read data");
    if (err) check(br == 0, "block error data is zero");
    tick(); bv = 0; #1;
  endtask
  task automatic ubus(input logic wr, input logic [63:0] offset, input logic [63:0] data,
                      input logic err, input logic [63:0] wanted = 0);
    uv = 1; uw = wr; ua = offset; ud = data; #1;
    check(urv && ure == err && !urt, "UART response/error/tag");
    if (!wr && !err) check(ur == wanted, "UART read data");
    if (err) check(ur == 0, "UART error data is zero");
    tick(); uv = 0; #1;
  endtask
  task automatic advance;
    step = 1; tick(); step = 0; #1;
  endtask
  task automatic prepare(input logic [63:0] target, input logic [511:0] contents);
    bus(1, BLK_BLOCK, target, 0);
    for (int i = 7; i >= 0; i--) bus(1, BLK_DATA + 64'(i*8), contents[i*64 +: 64], 0);
  endtask
  task automatic ack;
    bus(1, BLK_ACK, 1, 0);
  endtask
  initial begin
    for (int i = 0; i < 64; i++) begin
      media_image[0][i*8 +: 8] = 8'(i);
      media_image[1][i*8 +: 8] = 8'(64+i);
    end
    original0 = media_image[0];
    tick(); reset = 0; #1;
    bus(0, BLK_VERSION, 0, 0, 1);
    bus(0, BLK_BLOCK_BYTES, 0, 0, 64);
    bus(0, BLK_BLOCK_COUNT, 0, 0, 2);
    bus(0, BLK_STATUS, 0, 0, 0);
    bus(0, BLK_DATA, 0, 1);
    bus(0, BLK_COMMAND, 0, 1);
    bus(0, BLK_ACK, 0, 1);
    for (int n = 0; n < 17; n++) if (n != 8) begin
      bn = 5'(n); bus(1, BLK_BLOCK, 1, 1);
    end
    bn = 8;
    bus(1, BLK_BLOCK + 1, 1, 1);
    bus(1, 4092, 1, 1);
    bus(1, '1, 1, 1);
    bus(1, 64'h80, 1, 1);
    bo = 0; bus(1, BLK_COMMAND, 1, 1); bo = 1;
    for (int i = 0; i < 8; i++) expected[i*64 +: 64] = 64'h123456789abcdef0 ^ 64'(i);
    prepare(1, expected);
    expected[3*64 +: 64] = 64'hfedcba9876543210;
    bus(1, BLK_DATA + 24, expected[3*64 +: 64], 0);
    bus(1, BLK_COMMAND, 2, 0);
    bus(0, BLK_STATUS, 0, 0, 1);
    bus(0, BLK_STATUS, 0, 0, 1);
    bus(1, BLK_BLOCK, 0, 1);
    bus(1, BLK_DATA, 0, 1);
    advance(); bus(0, BLK_STATUS, 0, 0, 1);
    check(media_image[0] == original0 && media_image[1] != expected, "no prefinal write");
    advance(); bus(0, BLK_STATUS, 0, 0, 2);
    check(media_image[1] == expected && media_image[0] == original0, "last-block exact write, adjacent unchanged");
    bus(0, BLK_DATA, 0, 1);
    bus(1, BLK_COMMAND, 1, 1);
    bus(1, BLK_ACK, 0, 1); ack();
    bus(1, BLK_BLOCK, '1, 0); bus(1, BLK_COMMAND, 3, 0); advance(); ack();
    reset = 1; tick(); reset = 0;
    check(media_image[1] == expected, "write and flush survive reset");
    bus(1, BLK_BLOCK, 1, 0); bus(1, BLK_COMMAND, 1, 0); advance(); advance();
    for (int i = 0; i < 8; i++) bus(0, BLK_DATA + 64'(8*i), 0, 0, expected[i*64 +: 64]);
    bus(0, BLK_DATA, 0, 0, expected[63:0]); ack();
    bus(1, BLK_BLOCK, '1, 0); bus(1, BLK_COMMAND, 99, 0); bus(0, BLK_RESULT, 0, 0, 1); ack();
    bus(1, BLK_BLOCK, 2, 0); bus(1, BLK_COMMAND, 2, 0); bus(0, BLK_RESULT, 0, 0, 2); ack();
    prepare(0, ~original0); bus(1, BLK_BLOCK, 0, 0);
    bus(1, BLK_COMMAND, 2, 0); bus(0, BLK_RESULT, 0, 0, 3); ack();
    bus(1, BLK_COMMAND, 1, 0); backend_error = 1; advance(); advance(); backend_error = 0;
    bus(0, BLK_RESULT, 0, 0, 4); bus(0, BLK_DATA, 0, 1); ack();
    bus(1, BLK_COMMAND, 3, 0); backend_error = 1; advance(); backend_error = 0;
    bus(0, BLK_RESULT, 0, 0, 4); ack();
    check(media_image[0] == original0, "failed read/flush leave media_image unchanged");
    for (int tear_case = 0; tear_case < 3; tear_case++) begin
      logic [511:0] before_write;
      before_write = media_image[0];
      mask = tear_case == 0 ? '0 : (tear_case == 1 ? '1 : {64{8'haa}});
      prepare(0, ~before_write); bus(1, BLK_COMMAND, 2, 0);
      backend_error = 1; advance(); advance(); backend_error = 0;
      check(media_image[0] == ((before_write & ~mask) | (~before_write & mask)), "write-error mask");
      check(media_image[1] == expected, "write error preserves adjacent block");
      bus(0, BLK_RESULT, 0, 0, 4); ack();
    end
    original0 = media_image[0]; mask = {64{8'h55}};
    prepare(0, ~original0); bus(1, BLK_COMMAND, 2, 0); advance();
    reset = 1; step = 1; #1; check(tear && !commit, "reset wins final-step tie");
    tick(); reset = 0; step = 0; #1;
    check(media_image[0] == ((original0 & ~mask) | (~original0 & mask)), "reset tear uses current media_image");
    original0 = media_image[0]; advance(); advance();
    check(media_image[0] == original0, "stale progress after reset has no effect");
    bus(0, BLK_STATUS, 0, 0, 0); bus(0, BLK_BLOCK, 0, 0, 0); bus(0, BLK_DATA, 0, 1);

    ubus(0, UART_STATUS, 0, 0, 64'h3c);
    ubus(0, UART_RDATA, 0, 1);
    rxdata = 8'h93; rxv = 1; tick(); rxv = 0; #1;
    check(!rxready, "RX backpressure while full");
    ubus(0, UART_RDATA, 0, 0, 64'h93); ubus(0, UART_RDATA, 0, 1);
    ubus(1, UART_WDATA, 64'h11223344556677a5, 0);
    check(txv && txdata == 8'ha5, "TX low byte stable under backpressure");
    ubus(1, UART_WDATA, 0, 1);
    txready = 1; tick(); txready = 0; #1; check(!txv, "TX consumed once");
    ubus(1, UART_STATUS, 0, 1); ubus(1, UART_RDATA, 0, 1); ubus(0, UART_WDATA, 0, 1);
    un = 8; ubus(1, UART_WDATA, 0, 1); un = 4;
    uo = 0; ubus(1, UART_WDATA, 0, 1); uo = 1;
    ubus(1, UART_WDATA + 1, 0, 1); ubus(0, 0, 0, 1);
    ubus(1, UART_WDATA, 1, 0); reset = 1; tick(); reset = 0; #1;
    check(!txv && rxready, "UART reset clears both queues");

    address = VosPhysAddrBits'(VosDtbAddress); #1; check(dtb && !route_error && !ap, "DTB read route");
    route_write = 1; #1; check(route_error, "DTB write refusal"); route_write = 0;
    route_fetch = 1; #1; check(route_error, "DTB fetch refusal"); route_fetch = 0;
    address = VosPhysAddrBits'(VosApertures[VosApBootRom].base - 4); #1;
    check(route_error, "DTB boundary crossing refusal");
    address = VosPhysAddrBits'(VosApertures[VosApUart].base); bytes_count = 4; #1;
    check(ap && int'(ap_index) == VosApUart && !route_error, "UART aperture route");
    address = VosPhysAddrBits'(VosApertures[VosApClint].base + VosApertures[VosApClint].size); #1;
    check(route_error, "unclaimed IO decode error");
    bytes_count = 0; #1; check(route_error, "zero-width route refusal");
    $display("device wrappers: %0d assertions PASS", checks);
    $finish;
  end
endmodule
