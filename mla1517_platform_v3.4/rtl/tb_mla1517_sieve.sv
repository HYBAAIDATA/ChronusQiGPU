`timescale 1ns/1ps
module tb_mla1517_sieve;
  localparam int LANES = 32;
  localparam int MEMORY_NODES = 20;
  localparam int STATE_W = 512;

  logic [31:0] d5_lane [0:LANES-1];
  logic [31:0] d7_prime [0:LANES-1];
  logic [STATE_W-1:0] state_lane [0:LANES-1];
  logic [31:0] difficulty_mask = 32'h0000003f;
  logic [31:0] anchor_mask = 32'h00000040;
  logic [63:0] poly_mask = 64'd0;
  logic [63:0] poly_target = 64'd0;
  logic [LANES-1:0] vote;
  logic [4:0] rank [0:LANES-1];
  logic [STATE_W-1:0] state_mem [0:MEMORY_NODES-1];
  logic [MEMORY_NODES-1:0] valid_mem;

  mla1517_sieve_crossbar #(
    .LANES(LANES), .MEMORY_NODES(MEMORY_NODES),
    .D5_W(32), .STATE_W(STATE_W)
  ) dut (
    .d5_lane_i(d5_lane), .d7_prime_address_i(d7_prime),
    .state_lane_i(state_lane), .difficulty_mask_i(difficulty_mask),
    .anchor_mask_i(anchor_mask), .polyhedral_mask_i(poly_mask),
    .polyhedral_target_i(poly_target), .warp_vote_o(vote),
    .winner_rank_o(rank), .state_mem_o(state_mem),
    .valid_mem_o(valid_mem)
  );

  integer i;
  initial begin
    for (i = 0; i < LANES; i = i + 1) begin
      d5_lane[i] = 32'd0;
      d7_prime[i] = i;
      state_lane[i] = i;
    end
    d5_lane[4] = 32'h00000040;  // void + anchor: accepted
    d5_lane[5] = 32'h00000041;  // lower void violated: rejected
    d5_lane[7] = 32'h00000040;  // second accepted lane
    #1;
    if (!vote[4] || !vote[7] || vote[5]) $fatal(1, "sieve ballot failure");
    if (rank[4] != 0 || rank[7] != 1) $fatal(1, "prefix compaction failure");
    if (!valid_mem[4] || !valid_mem[7]) $fatal(1, "crossbar route failure");
    $display("MLA1517 sieve/crossbar smoke test PASS vote=%h", vote);
    $finish;
  end
endmodule