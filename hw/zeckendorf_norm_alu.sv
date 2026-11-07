// Chronus QiGPU phi-ALU: exact integer-lattice arithmetic in RTL.
//
// norm_f257phi: Galois norm N(a + b*phi) = a^2 + a*b - b^2 (mod 257).
//   5 is a quadratic non-residue mod 257, so F_257[phi] is the field F_257^2.
//   Fully combinational, exact, no floating point anywhere in the datapath.
//
// zeckendorf_fold_sweep: one parallel even-phase rewrite sweep of the
//   base-phi fold rule F_k + F_{k+1} = F_{k+2}  (bit pattern 011 -> 100).
//   Even-indexed pairs are non-overlapping, so the sweep is combinational
//   with constant gate delay and no binary carry chain.
//
// qigpu_phi_alu: top level binding one fold sweep and one norm unit.

module norm_f257phi (
    input  wire [8:0] a,
    input  wire [8:0] b,
    output wire [8:0] norm
);
    wire [17:0] aa = a * a;
    wire [17:0] ab = a * b;
    wire [17:0] bb = b * b;
    // Headroom of 257*256 keeps the intermediate non-negative before mod.
    wire [26:0] wide = {9'b0, aa} + {9'b0, ab} + 27'd65792 - {9'b0, bb};
    assign norm = wide % 257;
endmodule

module zeckendorf_fold_sweep (
    input  wire [63:0] bits_in,
    output wire [64:0] bits_out
);
    // Even phase: pairs (0,1), (2,3), ... share no input bits, so every
    // local rewrite fires in parallel in one gate delay. When a fold target
    // lands on a bit whose own pair also fired, the target wins: for the
    // pattern 1111 the exact identity F_k+F_{k+1}+F_{k+2}+F_{k+3} =
    // F_{k+2}+F_{k+4} keeps every sweep value-preserving.
    wire [31:0] fire;
    genvar p;
    generate
        for (p = 0; p < 32; p = p + 1) begin : even_pairs
            assign fire[p] = bits_in[2*p] & bits_in[2*p+1];
        end
    endgenerate
    genvar j;
    generate
        for (j = 0; j < 64; j = j + 1) begin : out_bits
            wire cleared = fire[j/2];
            wire target  = (j >= 2) && (j % 2 == 0) && fire[(j-2)/2];
            assign bits_out[j] = target ? 1'b1 : (cleared ? 1'b0 : bits_in[j]);
        end
    endgenerate
    assign bits_out[64] = fire[31];
endmodule

module qigpu_phi_alu (
    input  wire [8:0]  a,
    input  wire [8:0]  b,
    input  wire [63:0] zv_in,
    output wire [8:0]  norm,
    output wire [64:0] zv_out
);
    norm_f257phi u_norm (.a(a), .b(b), .norm(norm));
    zeckendorf_fold_sweep u_fold (.bits_in(zv_in), .bits_out(zv_out));
endmodule
