`timescale 1ns/1ps
module tb_mla1517;
  localparam int STATE_W = 512;
  logic clk = 1'b0;
  logic rst = 1'b1;
  always #5 clk = ~clk;

  logic valid_i;
  logic [31:0] warp_step_i;
  logic [4:0] lane_id_i;
  logic valid_z;
  logic [31:0] nonce_z;
  logic [31:0] d5_z;
  logic [193:0] d6_z;

  mla1517_zcore #(
    .ROM_ADDR_W(8),
    .D5_ROM("rtl/rom/zcore_d5_zeckendorf.mem"),
    .D6_ROM("rtl/rom/zcore_d6_binet_q.mem")
  ) zcore (
    .clk(clk), .rst(rst), .valid_i(valid_i),
    .warp_step_i(warp_step_i), .lane_id_i(lane_id_i),
    .valid_o(valid_z), .nonce_o(nonce_z),
    .d5_zeckendorf_o(d5_z), .d6_binet_projection_o(d6_z)
  );

  logic cassini_valid;
  logic [STATE_W-1:0] cassini_state;
  logic signed [129:0] determinant;
  mla1517_cassini_dsp #(.F_W(64), .STATE_W(STATE_W)) cassini (
    .clk(clk), .rst(rst), .valid_i(valid_i),
    .f_prev_i(64'sd3), .f_n_i(64'sd5), .f_next_i(64'sd8),
    .state_i('0), .valid_o(), .cassini_valid_o(cassini_valid),
    .state_o(cassini_state), .determinant_o(determinant)
  );

  initial begin
    valid_i = 1'b0;
    warp_step_i = 0;
    lane_id_i = 5'd4;
    repeat (2) @(posedge clk);
    rst = 1'b0;
    valid_i = 1'b1;
    warp_step_i = 32'd3;
    @(posedge clk);
    #1;
    if (!valid_z || nonce_z != 32'd100) $fatal(1, "Z-Core nonce/valid failure");
    if (!cassini_valid || determinant != -1) $fatal(1, "Cassini DSP failure");
    $display("MLA1517 RTL smoke test PASS nonce=%0d cassini=%0d", nonce_z, determinant);
    // The reference ROM ends at nonce 255; out-of-range requests must not wrap.
    warp_step_i = 32'd8;
    @(posedge clk);
    #1;
    if (valid_z) $fatal(1, "Z-Core out-of-range guard failure");
    $finish;
  end
endmodule