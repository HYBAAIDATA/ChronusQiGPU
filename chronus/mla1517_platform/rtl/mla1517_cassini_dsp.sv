`timescale 1ns/1ps
module mla1517_cassini_dsp #(
  parameter int F_W = 64,
  parameter int STATE_W = 512
) (
  input  logic                   clk,
  input  logic                   rst,
  input  logic                   valid_i,
  input  logic signed [F_W-1:0]  f_prev_i,
  input  logic signed [F_W-1:0]  f_n_i,
  input  logic signed [F_W-1:0]  f_next_i,
  input  logic [STATE_W-1:0]     state_i,
  output logic                   valid_o,
  output logic                   cassini_valid_o,
  output logic [STATE_W-1:0]     state_o,
  output logic signed [2*F_W:0]  determinant_o
);
  // These two products are intended to infer two FPGA DSP48/equivalent
  // multiplier paths. The subtract and result register form one clock stage.
  (* use_dsp = "yes" *) logic signed [(2*F_W)-1:0] product_a;
  (* use_dsp = "yes" *) logic signed [(2*F_W)-1:0] product_b;
  logic signed [(2*F_W):0] determinant_comb;

  always_comb begin
    product_a = f_prev_i * f_next_i;
    product_b = f_n_i * f_n_i;
    determinant_comb = $signed({product_a[2*F_W-1], product_a}) -
                       $signed({product_b[2*F_W-1], product_b});
  end

  // One registered DSP stage from valid_i to cassini_valid_o.
  always_ff @(posedge clk) begin
    if (rst) begin
      valid_o <= 1'b0;
      cassini_valid_o <= 1'b0;
      determinant_o <= '0;
      state_o <= '0;
    end else begin
      valid_o <= valid_i;
      determinant_o <= determinant_comb;
      state_o <= state_i;
      cassini_valid_o <= valid_i &&
                         ((determinant_comb == 1) ||
                          (determinant_comb == -1));
    end
  end
endmodule