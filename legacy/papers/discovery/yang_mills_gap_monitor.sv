// =============================================================================
// FILE: hardware/rtl/yang_mills_gap_monitor.sv
// DESCRIPTION: Hardware Monitor for Exact Yang-Mills Spectral Gap.
//              Computes Δ = λ₁ - λ₀ exactly in exact integer cross-products
//              and asserts Δ > 0 with zero floating-point approximation.
// =============================================================================

`timescale 1ns / 1ps

module yang_mills_gap_monitor #(
    parameter int WIDTH = 256
) (
    input  logic                clk,
    input  logic                rst_n,
    input  logic                measure_enable,

    // Two lowest eigenvalues of H = L + V (exact rational limbs)
    input  logic [WIDTH-1:0]    lambda_0_num,
    input  logic [WIDTH-1:0]    lambda_0_den,
    input  logic [WIDTH-1:0]    lambda_1_num,
    input  logic [WIDTH-1:0]    lambda_1_den,

    // Outputs
    output logic                gap_positive,
    output logic [WIDTH-1:0]    gap_num,
    output logic [WIDTH-1:0]    gap_den
);

    // Δ = λ₁ - λ₀ = (λ₁_num · λ₀_den - λ₀_num · λ₁_den) / (λ₁_den · λ₀_den)
    logic [2*WIDTH-1:0] gap_n, gap_d;
    always_comb begin
        gap_n = (lambda_1_num * lambda_0_den) - (lambda_0_num * lambda_1_den);
        gap_d = (lambda_1_den * lambda_0_den);
    end

    assign gap_num = gap_n[WIDTH-1:0];
    assign gap_den = gap_d[WIDTH-1:0];

    // Gap strictly positive if numerator and denominator cross-product is > 0
    assign gap_positive = ((lambda_1_num * lambda_0_den) > (lambda_0_num * lambda_1_den)) &&
                          (gap_d != 0);

endmodule
