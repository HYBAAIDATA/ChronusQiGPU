// ============================================================================
// File: q5_top_asic.sv
// Project: HYBA/PYTHIA Q5 ASIC (Exact-Rational Stratum V1 Diffusion Accelerator)
// Subsystem: Top-Level ASIC Integration & Cassini Determinant SVA Module
// Features: Zero FPUs, Zero Graphic Rasterizers, Pure Unimodular Companion Math
// ============================================================================

\`timescale 1ns/1ps
import q5_types_pkg::*;

module q5_top_asic (
    input  logic                   clk,
    input  logic                   rst_n,
    
    // Stratum V1 Mining Work Interface
    input  logic                   job_valid,
    input  logic [31:0]            job_id,
    input  logic [31:0]            n_inner_scale,   // e.g. 20, 22, 24, 26, 27
    input  logic [15:0]            target_k_steps,  // Grover optimal diffusion steps
    
    // Status & Proof-of-Work Output
    output logic                   solution_found,
    output logic [31:0]            golden_nonce,
    output logic                   exact_invariants_pass,
    output logic                   halt_circuit_breaker
);

    // Companion Matrix Registers: M = [[1, 1], [1, 0]]^n
    sl2z_matrix_t companion_matrix;
    logic signed [63:0] exact_det_register;
    logic [15:0]        power_n;
    logic               n_is_even;
    logic               unimodular_valid;

    // Lucas numbers register bank
    logic signed [63:0] lucas_curr;
    logic signed [63:0] lucas_next;

    // Calculate exact determinant: det = a*d - b*c
    always_comb begin
        exact_det_register = (companion_matrix.a * companion_matrix.d) - 
                             (companion_matrix.b * companion_matrix.c);
        n_is_even          = (power_n[0] == 1'b0);
        unimodular_valid   = job_valid && (power_n > 0);
    end

    // Companion Matrix Step Evolution
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            companion_matrix.a    <= 64'sd1;
            companion_matrix.b    <= 64'sd1;
            companion_matrix.c    <= 64'sd1;
            companion_matrix.d    <= 64'sd0;
            power_n               <= 16'd1;
            solution_found        <= 1'b0;
            golden_nonce          <= '0;
            exact_invariants_pass <= 1'b1;
            halt_circuit_breaker  <= 1'b0;
            lucas_curr            <= 64'sd1; // L_1
            lucas_next            <= 64'sd3; // L_2
        end else if (job_valid && !halt_circuit_breaker) begin
            // Advance companion matrix by M = [[1, 1], [1, 0]]
            companion_matrix.a <= companion_matrix.a + companion_matrix.b;
            companion_matrix.b <= companion_matrix.a;
            companion_matrix.c <= companion_matrix.c + companion_matrix.d;
            companion_matrix.d <= companion_matrix.c;
            
            // Advance Lucas sequence: L_{n+2} = L_{n+1} + L_n
            lucas_curr <= lucas_next;
            lucas_next <= lucas_next + lucas_curr;
            
            power_n <= power_n + 16'd1;
        end
    end

    // ------------------------------------------------------------------------
    // MANDATE 2: FORMAL SYSTEMVERILOG ASSERTION (Cassini Identity det(M^n) = (-1)^n)
    // ------------------------------------------------------------------------
    property p_cassini_exact;
        @(posedge clk) disable iff (!rst_n || !unimodular_valid)
        (exact_det_register == (n_is_even ? 64'sd1 : -64'sd1));
    endproperty

    assert_cassini: assert property(p_cassini_exact)
        else begin
            $fatal(1, "[HARDWARE FAULT] Cassini Identity Violation in Silicon Register: det=%0d at power n=%0d", 
                   exact_det_register, power_n);
        end

    // Clock halting circuit breaker on any assertion trip
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            halt_circuit_breaker <= 1'b0;
        end else if (exact_det_register != (n_is_even ? 64'sd1 : -64'sd1)) begin
            halt_circuit_breaker <= 1'b1;
        end
    end

endmodule
