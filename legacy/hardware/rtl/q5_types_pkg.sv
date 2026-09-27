// ============================================================================
// File: q5_types_pkg.sv
// Project: HYBA/PYTHIA Q5 ASIC (Exact-Rational Q[√5] Diffusion Processor)
// Standard: IEEE 1800-2017 SystemVerilog
// ============================================================================

package q5_types_pkg;

  // Maximum bitwidths for exact multi-word rational arithmetic
  localparam int MAX_NUM_WIDTH = 256;
  localparam int MAX_DEN_WIDTH = 256;
  localparam int NUM_GLOBAL_FACES = 32;
  localparam int HBM3E_CHANNELS = 16;
  localparam int HBM3E_BANKS_PER_CH = 32;
  localparam int FIB_BASIS_DEPTH = 32;

  // Exact Rational Fraction Type: p / q with explicit sign bit
  typedef struct packed {
    logic signed [MAX_NUM_WIDTH-1:0] num;
    logic        [MAX_DEN_WIDTH-1:0] den; // Always strictly positive in canonical form
    logic                            valid;
  } q_rational_t;

  // Exact Q[√5] Quadratic Field Amplitude: a + b * √5 where a, b in Q
  typedef struct packed {
    q_rational_t a; // Rational component
    q_rational_t b; // √5 irrational coefficient
  } q5_exact_amp_t;

  // 2x2 Unimodular SL(2, Z) Matrix: [[a, b], [c, d]] where det = a*d - b*c in {+1, -1}
  typedef struct packed {
    logic signed [63:0] a;
    logic signed [63:0] b;
    logic signed [63:0] c;
    logic signed [63:0] d;
  } sl2z_matrix_t;

  // Zeckendorf canonical address representation
  typedef struct packed {
    logic [FIB_BASIS_DEPTH-1:0] fib_bits; // Strictly no adjacent 1s
    logic [4:0]                 face_id;  // 0 to 31
    logic [3:0]                 channel;  // HBM3e channel 0..15
    logic [4:0]                 bank;     // HBM3e bank 0..31
  } zeck_addr_t;

  // Execution state opcode
  typedef enum logic [3:0] {
    OP_IDLE             = 4'b0000,
    OP_ORACLE_PHASE_INV = 4'b0001, // |m> -> -|m>
    OP_MEAN_DIFFUSE     = 4'b0010, // 2*|ψ><ψ| - I
    OP_LUCAS_PISOT_MUL  = 4'b0011, // L_n / L_{n+1} scaling
    OP_CASSINI_STEP     = 4'b0100, // M^{n+1} companion advance
    OP_REDUCE_GCD       = 4'b0101, // Exact integer reduction
    OP_HALT_FAULT       = 4'b1111
  } q5_opcode_e;

endpackage: q5_types_pkg
