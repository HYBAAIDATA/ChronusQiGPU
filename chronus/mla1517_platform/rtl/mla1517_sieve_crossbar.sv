`timescale 1ns/1ps
module mla1517_sieve_crossbar #(
  parameter int LANES = 32,
  parameter int MEMORY_NODES = 20,
  parameter int D5_W = 32,
  parameter int STATE_W = 512
) (
  input  logic [D5_W-1:0]  d5_lane_i [0:LANES-1],
  input  logic [31:0]      d7_prime_address_i [0:LANES-1],
  input  logic [STATE_W-1:0] state_lane_i [0:LANES-1],
  input  logic [D5_W-1:0]  difficulty_mask_i,
  input  logic [D5_W-1:0]  anchor_mask_i,
  input  logic [63:0]      polyhedral_mask_i,
  input  logic [63:0]      polyhedral_target_i,
  output logic [LANES-1:0] warp_vote_o,
  output logic [4:0]       winner_rank_o [0:LANES-1],
  output logic [STATE_W-1:0] state_mem_o [0:MEMORY_NODES-1],
  output logic [MEMORY_NODES-1:0] valid_mem_o
);
  integer lane;
  integer node;
  logic [LANES-1:0] prefix_mask;
  logic [D5_W-1:0] d5_state;

  // Combinational single-cycle sieve, ballot, compaction, and crossbar.
  always_comb begin
    warp_vote_o = '0;
    winner_rank_o = '{default:'0};
    state_mem_o = '{default:'0};
    valid_mem_o = '0;
    prefix_mask = '0;

    for (lane = 0; lane < LANES; lane = lane + 1) begin
      d5_state = d5_lane_i[lane];
      if (((d5_state & difficulty_mask_i) == '0) &&
          ((d5_state & anchor_mask_i) != '0) &&
          ((d7_prime_address_i[lane] & polyhedral_mask_i) ==
           polyhedral_target_i)) begin
        warp_vote_o[lane] = 1'b1;
        winner_rank_o[lane] = $countones(warp_vote_o & ((1 << lane) - 1));
      end
    end

    // Deterministic 32-to-1 selection per Aethel destination.
    // Lowest lane wins if several lanes target the same node in one cycle.
    for (lane = 0; lane < LANES; lane = lane + 1) begin
      if (warp_vote_o[lane]) begin
        node = d7_prime_address_i[lane] % MEMORY_NODES;
        if (!valid_mem_o[node]) begin
          valid_mem_o[node] = 1'b1;
          state_mem_o[node] = state_lane_i[lane];
        end
      end
    end
  end
endmodule