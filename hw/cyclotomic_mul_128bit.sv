// =============================================================================
// CHRONUS QUANTUM iGPU: 128-BIT CYCLOTOMIC MULTIPLIER (T_CYCLO_MUL)
// =============================================================================
// Module: cyclotomic_mul_128bit
// Architecture: Exact Algebraic Ring Z[zeta_5] = Z[x] / (x^4 + x^3 + x^2 + x + 1)
// Function: 1-Cycle exact polynomial convolution and quotient reduction.
//
// Input Format:
//   Two 128-bit words (A, B), each packing four 32-bit signed coefficients:
//   A = {a3[31:0], a2[31:0], a1[31:0], a0[31:0]}  <=> a0 + a1*zeta + a2*zeta^2 + a3*zeta^3
//   B = {b3[31:0], b2[31:0], b1[31:0], b0[31:0]}  <=> b0 + b1*zeta + b2*zeta^2 + b3*zeta^3
//
// Output Format:
//   One 128-bit product C = A (x) B mod Phi_5(x):
//   C = {c3[31:0], c2[31:0], c1[31:0], c0[31:0]}
//
// Mathematical Invariant (Zero Floating-Point Truncation):
//   Because x^5 = 1, x^6 = x, and x^4 = -x^3 - x^2 - x - 1:
//     c0 = p0 - p4 + p5
//     c1 = p1 - p4 + p6
//     c2 = p2 - p4
//     c3 = p3 - p4
//   where p_k = sum_{i+j=k} a_i * b_j.
// =============================================================================

`timescale 1ns / 1ps

module cyclotomic_mul_128bit (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  enable,
    input  wire signed [127:0]   a_in,
    input  wire signed [127:0]   b_in,
    output reg  signed [127:0]   c_out,
    output reg                   valid_out
);

    // Unpack 32-bit signed coefficients
    wire signed [31:0] a0 = a_in[31:0];
    wire signed [31:0] a1 = a_in[63:32];
    wire signed [31:0] a2 = a_in[95:64];
    wire signed [31:0] a3 = a_in[127:96];

    wire signed [31:0] b0 = b_in[31:0];
    wire signed [31:0] b1 = b_in[63:32];
    wire signed [31:0] b2 = b_in[95:64];
    wire signed [31:0] b3 = b_in[127:96];

    // 16 parallel 32x32 signed cross-products (64-bit precision)
    wire signed [63:0] m00 = a0 * b0;
    wire signed [63:0] m01 = a0 * b1;
    wire signed [63:0] m02 = a0 * b2;
    wire signed [63:0] m03 = a0 * b3;

    wire signed [63:0] m10 = a1 * b0;
    wire signed [63:0] m11 = a1 * b1;
    wire signed [63:0] m12 = a1 * b2;
    wire signed [63:0] m13 = a1 * b3;

    wire signed [63:0] m20 = a2 * b0;
    wire signed [63:0] m21 = a2 * b1;
    wire signed [63:0] m22 = a2 * b2;
    wire signed [63:0] m23 = a2 * b3;

    wire signed [63:0] m30 = a3 * b0;
    wire signed [63:0] m31 = a3 * b1;
    wire signed [63:0] m32 = a3 * b2;
    wire signed [63:0] m33 = a3 * b3;

    // Polynomial convolution coefficients P_0 .. P_6
    wire signed [63:0] p0 = m00;
    wire signed [63:0] p1 = m01 + m10;
    wire signed [63:0] p2 = m02 + m11 + m20;
    wire signed [63:0] p3 = m03 + m12 + m21 + m30;
    wire signed [63:0] p4 = m13 + m22 + m31;
    wire signed [63:0] p5 = m23 + m32;
    wire signed [63:0] p6 = m33;

    // Exact mod Phi_5(x) Quotient Reduction
    // x^4 = -x^3 - x^2 - x - 1
    // x^5 = 1
    // x^6 = x
    wire signed [63:0] red_c0 = p0 - p4 + p5;
    wire signed [63:0] red_c1 = p1 - p4 + p6;
    wire signed [63:0] red_c2 = p2 - p4;
    wire signed [63:0] red_c3 = p3 - p4;

    // Synchronous registered output (1-cycle execution)
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            c_out     <= 128'sd0;
            valid_out <= 1'b0;
        end else if (enable) begin
            c_out <= {red_c3[31:0], red_c2[31:0], red_c1[31:0], red_c0[31:0]};
            valid_out <= 1'b1;
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule

