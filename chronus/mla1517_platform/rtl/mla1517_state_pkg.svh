package mla1517_state_pkg;
  // 64-byte hot transport descriptor: D1-D11, route token, and reserved slots.
  typedef struct packed {
    logic [63:0] d1_payload_nonce;
    logic [31:0] d2_lucas_scale;
    logic [31:0] d3_pisot_fold;
    logic [31:0] d4_fibonacci_exact;
    logic [31:0] d5_zeckendorf_code;
    logic [31:0] d6_binet_projection;
    logic [31:0] d7_prime_address;
    logic [31:0] d8_polyhedral_position;
    logic [31:0] d9_transform_eigenbasis;
    logic [31:0] d10_cassini_integrity;
    logic [31:0] d11_lineage_time;
    logic [31:0] route_control;
    logic [31:0] reserved0;
    logic [31:0] reserved1;
    logic [31:0] reserved2;
  } mla1517_hot_state_t;

  localparam int MLA1517_HOT_STATE_W = $bits(mla1517_hot_state_t);
endpackage