// Chronus QiGPU PV scaling array: Lucas/Pisot-Vijayaraghavan scaling in silicon.
//
// Scaling by phi is the companion matrix step (a, b) -> (b, a + b): one
// integer addition per lane per scale step, no multiplier, no carry
// propagation beyond a single 64-bit add. Thirty-two lanes scale in
// parallel; after k steps each lane holds (a, b) * phi^k exactly.
//
// Anchors verified in the testbench:
//   (0, 1) after k steps -> (F_{k-1}, F_k)          (Fibonacci ladder)
//   (2, 1) after k steps -> (L_{k-1}, L_k)          (Lucas ladder)
//   composition: k1 steps then k2 steps == k1+k2 steps

module pv_scale_step (
    input  wire signed [63:0] a_in,
    input  wire signed [63:0] b_in,
    output wire signed [63:0] a_out,
    output wire signed [63:0] b_out
);
    assign a_out = b_in;
    assign b_out = a_in + b_in;  // (a + b*phi) * phi = b + (a+b)*phi
endmodule

module qigpu_pv_scale_32lane (
    input  wire                    clk,
    input  wire                    load,
    input  wire                    step,
    input  wire signed [32*64-1:0] a_array,
    input  wire signed [32*64-1:0] b_array,
    output wire signed [32*64-1:0] a_scaled,
    output wire signed [32*64-1:0] b_scaled
);
    genvar lane;
    generate
        for (lane = 0; lane < 32; lane = lane + 1) begin : lanes
            reg signed [63:0] a_reg, b_reg;
            wire signed [63:0] a_next, b_next;
            pv_scale_step unit (.a_in(a_reg), .b_in(b_reg),
                                .a_out(a_next), .b_out(b_next));
            always @(posedge clk) begin
                if (load) begin
                    a_reg <= a_array[lane*64 +: 64];
                    b_reg <= b_array[lane*64 +: 64];
                end else if (step) begin
                    a_reg <= a_next;
                    b_reg <= b_next;
                end
            end
            assign a_scaled[lane*64 +: 64] = a_reg;
            assign b_scaled[lane*64 +: 64] = b_reg;
        end
    endgenerate
endmodule
