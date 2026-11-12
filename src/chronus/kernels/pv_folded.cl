// Exact F_257[phi] period-516 folded memory and lookup kernel.
// Integer-only arithmetic: ushort / uint / ulong lanes exclusively.
// Residue 256 requires 9 bits, so every field coefficient lane is ushort
// (uint16_t); an 8-bit lane would silently truncate the residue 256.

#define F257_MOD 257U
#define PISANO_PERIOD 516U
#define HALF_PERIOD 258U

// 16-byte coalesced folded state record. The unbounded scale trajectory
// s = 516 * q + r is separated into its exact 64-bit winding quotient and
// its canonical phase residual, so folding is bijective and lossless:
// unfold(fold(s)) == s bit-for-bit.
typedef struct __attribute__((packed, aligned(16))) {
    ulong  epoch_q;        // exact quotient q = s / 516 (zero truncation)
    ushort r_mod_516;      // canonical residual r = s % 516 in [0, 515]
    ushort coeff_a;        // F_257[phi] scalar component a in [0, 256]
    ushort coeff_b;        // F_257[phi] golden component b in [0, 256]
    ushort manifold_flags; // cyclotomic / Binet-Zeckendorf parity metadata
} FoldedState16;

// O(1) constant-cache lookup: returns (a, b) = phi^r in F_257[phi].
// The LUT is the host-generated 2,064-byte payload (516 x ushort2).
inline ushort2 pv_lut_lookup(
    __constant const ushort2* restrict phi_lut_516,
    uint r_mod_516
) {
    return phi_lut_516[r_mod_516];
}

// Exact bilinear multiplication in F_257[phi] with phi^2 = phi + 1:
// (a0 + b0*phi) * (a1 + b1*phi)
//   = (a0*a1 + b0*b1) + (a0*b1 + b0*a1 + b0*b1)*phi   (mod 257)
// 32-bit uint intermediates: the largest term, 256*256*3 = 196608,
// can never overflow a uint lane.
inline ushort2 f257_phi_mul(ushort2 x, ushort2 y) {
    uint a0 = (uint)x.s0, b0 = (uint)x.s1;
    uint a1 = (uint)y.s0, b1 = (uint)y.s1;
    uint bb = (b0 * b1) % F257_MOD;
    ushort res_a = (ushort)((a0 * a1 + bb) % F257_MOD);
    ushort res_b = (ushort)((a0 * b1 + b0 * a1 + bb) % F257_MOD);
    return (ushort2)(res_a, res_b);
}

// Advances each folded state by an arbitrary scale jump delta_s with zero
// loops: one integer div/mod updates (q, r), one constant-cache read
// refreshes (a, b). Host-side parity verification is fail-closed.
__kernel void step_folded_states(
    __constant const ushort2* restrict phi_lut_516, // 2,064-byte LUT buffer
    __global FoldedState16* restrict states,        // coalesced 16B records
    const ulong delta_s,                            // arbitrary scale jump
    const uint count
) {
    const uint gid = get_global_id(0);
    if (gid >= count) return;

    FoldedState16 st = states[gid];

    // Fold delta_s into quotient and residual without losing high-order bits.
    ulong dq = delta_s / PISANO_PERIOD;
    uint  dr = (uint)(delta_s % PISANO_PERIOD);

    uint next_r = (uint)st.r_mod_516 + dr;
    if (next_r >= PISANO_PERIOD) {
        next_r -= PISANO_PERIOD;
        dq += 1UL;
    }

    st.epoch_q   += dq;
    st.r_mod_516  = (ushort)next_r;

    // 1-cycle L1 constant-cache fetch for exact [a, b] in F_257[phi].
    ushort2 ab = pv_lut_lookup(phi_lut_516, next_r);
    st.coeff_a = ab.s0;
    st.coeff_b = ab.s1;

    states[gid] = st;
}
