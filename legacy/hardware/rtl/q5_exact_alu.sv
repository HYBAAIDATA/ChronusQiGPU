// ============================================================================
// File: q5_exact_alu.sv
// Project: HYBA/PYTHIA Q5 ASIC
// Subsystem: Pipeline-Amputated Zero-FPU Rational Field ALU
// Description: Implements exact arithmetic in Q[√5] = {a + b√5 | a, b in Q}.
//              Zero IEEE-754 FPUs. Zero floating-point rounding units.
// ============================================================================

\`timescale 1ns/1ps
import q5_types_pkg::*;

module q5_exact_alu (
    input  logic                   clk,
    input  logic                   rst_n,
    input  q5_opcode_e             opcode,
    input  logic                   op_start,
    input  q5_exact_amp_t          op_a,
    input  q5_exact_amp_t          op_b,
    input  logic signed [63:0]     lucas_n,
    input  logic signed [63:0]     lucas_n_plus_1,
    
    output q5_exact_amp_t          result,
    output logic                   op_done,
    output logic                   circuit_breaker_tripped,
    output logic [31:0]            fault_code
);

    // Intermediate multi-precision registers (512-bit wide for cross-products)
    logic signed [511:0] cross_a_num;
    logic signed [511:0] cross_b_num;
    logic        [511:0] common_den;
    
    // Lucas-Pisot cross-multiplier verification wires
    logic signed [511:0] lhs_scale_check;
    logic signed [511:0] rhs_scale_check;
    logic                scale_match;

    // SVA Signals
    logic scaling_active;
    assign scaling_active = (opcode == OP_LUCAS_PISOT_MUL) && op_start;

    // Direct rational arithmetic combinational datapath
    always_comb begin
        cross_a_num = op_a.a.num * $signed({1'b0, op_b.a.den});
        cross_b_num = op_b.a.num * $signed({1'b0, op_a.a.den});
        common_den  = op_a.a.den * op_b.a.den;

        lhs_scale_check = result.a.num * lucas_n_plus_1;
        rhs_scale_check = op_a.a.num * lucas_n;
        scale_match     = (lhs_scale_check == rhs_scale_check);
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result.a.num            <= '0;
            result.a.den            <= 256'd1;
            result.a.valid          <= 1'b0;
            result.b.num            <= '0;
            result.b.den            <= 256'd1;
            result.b.valid          <= 1'b0;
            op_done                 <= 1'b0;
            circuit_breaker_tripped <= 1'b0;
            fault_code              <= '0;
        end else if (op_start) begin
            case (opcode)
                OP_ORACLE_PHASE_INV: begin
                    // Exact phase inversion: q -> -q (flip numerator signs)
                    result.a.num   <= -op_a.a.num;
                    result.a.den   <= op_a.a.den;
                    result.a.valid <= 1'b1;
                    result.b.num   <= -op_a.b.num;
                    result.b.den   <= op_a.b.den;
                    result.b.valid <= 1'b1;
                    op_done        <= 1'b1;
                end

                OP_LUCAS_PISOT_MUL: begin
                    // Scaling by L_n / L_{n+1}
                    result.a.num   <= op_a.a.num * lucas_n;
                    result.a.den   <= op_a.a.den * lucas_n_plus_1[31:0];
                    result.a.valid <= 1'b1;
                    result.b.num   <= op_a.b.num * lucas_n;
                    result.b.den   <= op_a.b.den * lucas_n_plus_1[31:0];
                    result.b.valid <= 1'b1;
                    op_done        <= 1'b1;
                end

                default: begin
                    op_done <= 1'b0;
                end
            endcase
        end else begin
            op_done <= 1'b0;
        end
    end

    // ------------------------------------------------------------------------
    // MANDATE 3: FORMAL SYSTEMVERILOG ASSERTION (Lucas-Pisot Cross-Multiplication)
    // ------------------------------------------------------------------------
    property p_lucas_pisot_scale;
        @(posedge clk) disable iff (!rst_n || !scaling_active)
        (lhs_scale_check == rhs_scale_check);
    endproperty

    assert_lucas_scale: assert property(p_lucas_pisot_scale)
        else begin
            $fatal(1, "[HW FAULT] Lucas-Pisot Rational Collapse: LHS=%0d != RHS=%0d", lhs_scale_check, rhs_scale_check);
        end

endmodule
