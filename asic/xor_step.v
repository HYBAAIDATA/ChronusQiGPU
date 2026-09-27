// ASIC1 synthesis sketch — not a tape-out.
module xor_step (
  input  wire [7:0] state,
  input  wire [7:0] delta,
  output wire [7:0] next
);
  assign next = state ^ delta;
endmodule
