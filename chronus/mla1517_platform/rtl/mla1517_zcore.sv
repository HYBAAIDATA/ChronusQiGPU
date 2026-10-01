`timescale 1ns/1ps
module mla1517_zcore #(
  parameter int NONCE_W = 32,
  parameter int ROM_ADDR_W = 8,
  parameter int ROM_DEPTH = (1 << ROM_ADDR_W),
  parameter int D5_W = 32,
  parameter int D6_W = 194,
  parameter string D5_ROM = "rtl/rom/zcore_d5_zeckendorf.mem",
  parameter string D6_ROM = "rtl/rom/zcore_d6_binet_q.mem"
) (
  input  logic                 clk,
  input  logic                 rst,
  input  logic                 valid_i,
  input  logic [31:0]          warp_step_i,
  input  logic [4:0]           lane_id_i,
  output logic                 valid_o,
  output logic [NONCE_W-1:0]   nonce_o,
  output logic [D5_W-1:0]      d5_zeckendorf_o,
  output logic [D6_W-1:0]      d6_binet_projection_o
);
  logic [D5_W-1:0] d5_rom [0:(1 << ROM_ADDR_W)-1];
  logic [D6_W-1:0] d6_rom [0:(1 << ROM_ADDR_W)-1];
  logic [NONCE_W-1:0] nonce_comb;
  logic [ROM_ADDR_W-1:0] rom_addr;
  logic nonce_in_range;

  initial begin
    $readmemh(D5_ROM, d5_rom);
    $readmemh(D6_ROM, d6_rom);
  end

  always_comb begin
    nonce_comb = (warp_step_i << 5) + lane_id_i;
    rom_addr = nonce_comb[ROM_ADDR_W-1:0];
    nonce_in_range = (nonce_comb < ROM_DEPTH);
  end

  // One synchronous BRAM-style stage: lane/step -> registered D5/D6.
  always_ff @(posedge clk) begin
    if (rst) begin
      valid_o <= 1'b0;
      nonce_o <= '0;
      d5_zeckendorf_o <= '0;
      d6_binet_projection_o <= '0;
    end else begin
      // Never silently wrap a nonce into a smaller ROM image.
      valid_o <= valid_i && nonce_in_range;
      nonce_o <= nonce_comb;
      if (valid_i && nonce_in_range) begin
        d5_zeckendorf_o <= d5_rom[rom_addr];
        d6_binet_projection_o <= d6_rom[rom_addr];
      end else begin
        d5_zeckendorf_o <= '0;
        d6_binet_projection_o <= '0;
      end
    end
  end
endmodule