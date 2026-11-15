// =============================================================================
//  AL HARAS T-ISA COPROCESSOR: UNVERIFIED RTL SKETCH (SYSTEMVERILOG)
// =============================================================================
//  Status: design sketch only. This file has not been simulated, linted,
//  synthesised or timed in this repository's CI (the rtl-synthesis job covers
//  hw/*.sv only) and has not run on any FPGA or ASIC. No device target, clock
//  frequency or resource figure has been established.
//
//  Reference model: src/chronus/security/al_haras/hardware_t_isa.py. Its
//  RTL_SEMANTICS table records, per funct7, whether this RTL computes the same
//  function as the model. tests/test_al_haras_hardware_zk_formal_exact.py
//  evaluates the T_CYCLO_MUL expressions below against the exact Z[zeta_5]
//  product.
//
//  Timing by construction: one registered stage. A command accepted on a clock
//  edge produces resp_valid on the next edge. This is a structural property of
//  the sketch, not a measured latency.
//
//  What each funct7 does here:
//    0x01 T_CYCLO_ADD      coefficient-wise add, 32-bit wrap            (= model)
//    0x02 T_CYCLO_MUL      product mod Phi_5(x), 32-bit wrap            (= model)
//    0x03 T_SHEAF_INSPECT  exception 4'hE iff rs1 != rs2               (= model)
//    0x04 T_DSW_HEAL       register move rd <= rs2; no parity storage and
//                          no error correction    (model: Reed-Solomon scrub)
//    0x05 T_STARK_EVAL     returns the constant 1; evaluates nothing
//                                                 (model: F_257 identity check)
//    0x06 T_RICCI_INSPECT  exception 4'hC iff a0 < 0 (a sign test)      (= model)
//    0x07 T_HODGE_PROJ     rd <= (a0, a1, 0, 0)                         (= model)
//    0x08 T_ANOSOV_PURGE   cat map on the two low bytes of a0 only, results
//                          truncated to 8 bits        (model: all coefficients)
//    other funct7          illegal-instruction exception 4'h2
//
//  Known gaps (not addressed in this sketch):
//    * No load path: the RoCC rs1/rs2 operand values are not ports, so the
//      register file is only written with ALU results, and it is not reset.
//    * cmd_opcode and cmd_funct3 are not decoded.
//    * cmd_ready stays 1, so a response the host has not yet accepted
//      (resp_valid && !resp_ready) is overwritten by the next command.
//    * No memory interface: the egress gate of the Python model has no
//      counterpart here.
//  Corrected in this revision: the T_CYCLO_MUL reduction (the previous
//  expressions did not compute the product mod Phi_5(x)), and the sheaf trap,
//  which tested a 64-bit sum of squares that wraps to zero when every 32-bit
//  difference equals -2^31.
// =============================================================================

`timescale 1ns / 1ps

module t_isa_coprocessor #(
    parameter DATA_WIDTH       = 128, // 4 x 32-bit signed coefficients in Z[zeta_5]
    parameter REG_ADDR_WIDTH   = 5,   // 32 architectural cyclotomic registers
    parameter PRIME_MODULUS    = 257  // F_257 (used by the cat map below)
)(
    input  logic                     clk,
    input  logic                     rst_n,

    // RISC-V RoCC Command Interface
    input  logic                     cmd_valid,
    output logic                     cmd_ready,
    input  logic [6:0]               cmd_opcode,    // Custom-0: 7'b0001011 (0x0B); not decoded
    input  logic [2:0]               cmd_funct3,    // not decoded
    input  logic [6:0]               cmd_funct7,    // operation select
    input  logic [REG_ADDR_WIDTH-1:0] cmd_rs1,
    input  logic [REG_ADDR_WIDTH-1:0] cmd_rs2,
    input  logic [REG_ADDR_WIDTH-1:0] cmd_rd,

    // RISC-V RoCC Response Interface
    output logic                     resp_valid,
    input  logic                     resp_ready,
    output logic [DATA_WIDTH-1:0]    resp_data,
    output logic [REG_ADDR_WIDTH-1:0] resp_rd,
    output logic                     resp_exception,
    output logic [3:0]               resp_exc_code  // 4'hE sheaf trap, 4'hC sign trap, 4'h2 illegal
);

    // -------------------------------------------------------------------------
    // T-ISA funct7 encoding (Custom-0 opcode = 7'b0001011)
    // -------------------------------------------------------------------------
    localparam [6:0] OPC_CYCLO_ADD    = 7'b0000001;
    localparam [6:0] OPC_CYCLO_MUL    = 7'b0000010;
    localparam [6:0] OPC_SHEAF_INSP   = 7'b0000011;
    localparam [6:0] OPC_DSW_HEAL     = 7'b0000100;
    localparam [6:0] OPC_STARK_EVAL   = 7'b0000101;
    localparam [6:0] OPC_RICCI_INSP   = 7'b0000110;
    localparam [6:0] OPC_HODGE_PROJ   = 7'b0000111;
    localparam [6:0] OPC_ANOSOV_PURGE = 7'b0001000;

    // -------------------------------------------------------------------------
    // Register file: 32 x 128-bit, each (c0, c1, c2, c3) in Z[zeta_5]
    // -------------------------------------------------------------------------
    logic [DATA_WIDTH-1:0] regfile [0:(1<<REG_ADDR_WIDTH)-1];

    // Read ports
    wire [DATA_WIDTH-1:0] rs1_data = (cmd_rs1 == 0) ? {DATA_WIDTH{1'b0}} : regfile[cmd_rs1];
    wire [DATA_WIDTH-1:0] rs2_data = (cmd_rs2 == 0) ? {DATA_WIDTH{1'b0}} : regfile[cmd_rs2];

    // Coefficient unpacking (4 x 32-bit signed ints)
    wire signed [31:0] a0 = rs1_data[31:0];
    wire signed [31:0] a1 = rs1_data[63:32];
    wire signed [31:0] a2 = rs1_data[95:64];
    wire signed [31:0] a3 = rs1_data[127:96];

    wire signed [31:0] b0 = rs2_data[31:0];
    wire signed [31:0] b1 = rs2_data[63:32];
    wire signed [31:0] b2 = rs2_data[95:64];
    wire signed [31:0] b3 = rs2_data[127:96];

    // -------------------------------------------------------------------------
    // Unit 1: cyclotomic addition (c = a + b), 32-bit wrap per coefficient
    // -------------------------------------------------------------------------
    wire [DATA_WIDTH-1:0] cyclo_add_res = {
        (a3 + b3),
        (a2 + b2),
        (a1 + b1),
        (a0 + b0)
    };

    // -------------------------------------------------------------------------
    // Unit 2: multiplication in Z[x]/(Phi_5(x)), Phi_5(x) = x^4 + x^3 + x^2 + x + 1
    // With d_k = sum_{i+j=k} a_i*b_j and x^4 = -(1 + x + x^2 + x^3), x^5 = 1, x^6 = x:
    //   c0 = d0 - d4 + d5,  c1 = d1 - d4 + d6,  c2 = d2 - d4,  c3 = d3 - d4
    // Products are formed at 64 bits; each stored coefficient keeps the low 32
    // bits (two's-complement wrap).
    // -------------------------------------------------------------------------
    wire signed [63:0] p0 = (a0*b0) - (a1*b3) - (a2*b2) - (a3*b1) + (a2*b3) + (a3*b2);
    wire signed [63:0] p1 = (a0*b1) + (a1*b0) - (a1*b3) - (a2*b2) - (a3*b1) + (a3*b3);
    wire signed [63:0] p2 = (a0*b2) + (a1*b1) + (a2*b0) - (a1*b3) - (a2*b2) - (a3*b1);
    wire signed [63:0] p3 = (a0*b3) + (a1*b2) + (a2*b1) + (a3*b0) - (a1*b3) - (a2*b2) - (a3*b1);

    wire [DATA_WIDTH-1:0] cyclo_mul_res = {
        p3[31:0],
        p2[31:0],
        p1[31:0],
        p0[31:0]
    };

    // -------------------------------------------------------------------------
    // Unit 3: sheaf edge check. For the constant sheaf on the edge rs1 -> rs2 the
    // coboundary is rs2 - rs1, which is zero iff the two registers are equal, so
    // the trap tests equality directly. The response carries ||rs1 - rs2||^2
    // mod 2^64 for information only: that sum can wrap to zero, so it is not
    // used for the decision.
    // -------------------------------------------------------------------------
    wire signed [31:0] d0 = a0 - b0;
    wire signed [31:0] d1 = a1 - b1;
    wire signed [31:0] d2 = a2 - b2;
    wire signed [31:0] d3 = a3 - b3;

    wire [63:0] sheaf_residual_norm_sq = (d0*d0) + (d1*d1) + (d2*d2) + (d3*d3);
    wire sheaf_obstruction_detected = (rs1_data != rs2_data);

    // -------------------------------------------------------------------------
    // Unit 4: T_DSW_HEAL is only a register move here (rd <= rs2). This RTL
    // stores no parity and detects or corrects nothing; the Reed-Solomon scrub
    // exists only in the Python model.
    // -------------------------------------------------------------------------
    wire [DATA_WIDTH-1:0] dsw_move_data = rs2_data;

    // -------------------------------------------------------------------------
    // Unit 5: sign test of a0 (traps when a0 < 0). The notes call this a
    // Ricci-curvature indicator; no curvature is computed.
    // -------------------------------------------------------------------------
    wire ricci_anomaly_detected = (a0 < 32'sd0);

    // -------------------------------------------------------------------------
    // Unit 6: coordinate projection keeping (a0, a1) and zeroing (a2, a3).
    // -------------------------------------------------------------------------
    wire [DATA_WIDTH-1:0] hodge_projected_data = {32'd0, 32'd0, a1, a0};

    // -------------------------------------------------------------------------
    // Unit 7: Arnold cat map (2x + y, x + y) mod 257 on the two low bytes of a0
    // (x = bits [7:0], y = bits [15:8]). Results keep 8 bits, so a value of 256
    // is stored as 0. The map is a permutation, not an erasure.
    // -------------------------------------------------------------------------
    wire [15:0] cat_map_x = (16'd2 * rs1_data[7:0] + rs1_data[15:8]) % 16'd257;
    wire [15:0] cat_map_y = (rs1_data[7:0] + rs1_data[15:8]) % 16'd257;
    wire [DATA_WIDTH-1:0] anosov_purged_data = {96'd0, 8'd0, cat_map_y[7:0], 8'd0, cat_map_x[7:0]};

    // -------------------------------------------------------------------------
    // Control: single registered stage
    // -------------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cmd_ready      <= 1'b1;
            resp_valid     <= 1'b0;
            resp_data      <= '0;
            resp_rd        <= '0;
            resp_exception <= 1'b0;
            resp_exc_code  <= 4'h0;
        end else begin
            if (cmd_valid && cmd_ready) begin
                resp_valid <= 1'b1;
                resp_rd    <= cmd_rd;

                case (cmd_funct7)
                    OPC_CYCLO_ADD: begin
                        resp_data      <= cyclo_add_res;
                        resp_exception <= 1'b0;
                        if (cmd_rd != 0) regfile[cmd_rd] <= cyclo_add_res;
                    end

                    OPC_CYCLO_MUL: begin
                        resp_data      <= cyclo_mul_res;
                        resp_exception <= 1'b0;
                        if (cmd_rd != 0) regfile[cmd_rd] <= cyclo_mul_res;
                    end

                    OPC_SHEAF_INSP: begin
                        resp_data      <= {64'd0, sheaf_residual_norm_sq};
                        if (sheaf_obstruction_detected) begin
                            // Sheaf trap (fault code 4'hE)
                            resp_exception <= 1'b1;
                            resp_exc_code  <= 4'hE;
                        end else begin
                            resp_exception <= 1'b0;
                            resp_exc_code  <= 4'h0;
                        end
                    end

                    OPC_DSW_HEAL: begin
                        // Register move only (see Unit 4)
                        resp_data      <= dsw_move_data;
                        resp_exception <= 1'b0;
                        resp_exc_code  <= 4'h0;
                        if (cmd_rd != 0) regfile[cmd_rd] <= dsw_move_data;
                    end

                    OPC_STARK_EVAL: begin
                        // Placeholder: constant 1, nothing is evaluated
                        resp_data      <= {96'd0, 32'h00000001};
                        resp_exception <= 1'b0;
                        resp_exc_code  <= 4'h0;
                    end

                    OPC_RICCI_INSP: begin
                        resp_data      <= {96'd0, (ricci_anomaly_detected ? 32'hFFFFFFFF : 32'h00000001)};
                        if (ricci_anomaly_detected) begin
                            // Sign trap (fault code 4'hC)
                            resp_exception <= 1'b1;
                            resp_exc_code  <= 4'hC;
                        end else begin
                            resp_exception <= 1'b0;
                            resp_exc_code  <= 4'h0;
                        end
                        if (cmd_rd != 0) regfile[cmd_rd] <= {96'd0, (ricci_anomaly_detected ? 32'h00000000 : 32'h00000001)};
                    end

                    OPC_HODGE_PROJ: begin
                        // Coordinate projection (see Unit 6)
                        resp_data      <= hodge_projected_data;
                        resp_exception <= 1'b0;
                        resp_exc_code  <= 4'h0;
                        if (cmd_rd != 0) regfile[cmd_rd] <= hodge_projected_data;
                    end

                    OPC_ANOSOV_PURGE: begin
                        // Cat map on the low bytes of a0 (see Unit 7)
                        resp_data      <= anosov_purged_data;
                        resp_exception <= 1'b0;
                        resp_exc_code  <= 4'h0;
                        if (cmd_rd != 0) regfile[cmd_rd] <= anosov_purged_data;
                    end

                    default: begin
                        resp_data      <= '0;
                        resp_exception <= 1'b1;
                        resp_exc_code  <= 4'h2; // Illegal instruction
                    end
                endcase
            end else if (resp_valid && resp_ready) begin
                resp_valid     <= 1'b0;
                resp_exception <= 1'b0;
            end
        end
    end

endmodule
