// kernels/unified_punch_kernel.cl
// LUCAS WIRING: classical punch kernels only — no quantum claims here.
// MUST NOT import from any sibling algorithm.
// Substrate route: mining
//
// Unified punch kernel: the classical half of the unified punch layer.
// Each work-item executes ONE punch, selected by punch_ids[gid].
// All buffers are pre-sized by the host:
//   input_float   : count * DIM
//   input_ulong   : count
//   input_int     : count
//   input_double  : count
//   output_float  : count * DIM
//   output_ulong  : count * DIM * DIM
//   output_int    : count
//   output_long   : count
//   output_double : count
//
// Requires fp64 (cl_khr_fp64) for the double-precision punches
// (pisot_schedule, diophantine_check).

#ifdef cl_khr_fp64
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
#endif

#define DIM 11
#define PHI 1.6180339887498949
#define PSI -0.6180339887498949
#define SQRT5 2.2360679774997898
#define LUCAS_15 1364
#define PRIME_COUNT 25
#define SLOTS_PER_PRIME 1024

// Program-scope constant tables. (Function-scope __constant is rejected by
// some compilers, e.g. Intel's — keep these at file scope.)
__constant ulong FIB_TABLE[94] = {
    0UL, 1UL, 1UL, 2UL, 3UL, 5UL, 8UL, 13UL, 21UL, 34UL, 55UL, 89UL,
    144UL, 233UL, 377UL, 610UL, 987UL, 1597UL, 2584UL, 4181UL,
    6765UL, 10946UL, 17711UL, 28657UL, 46368UL, 75025UL, 121393UL,
    196418UL, 317811UL, 514229UL, 832040UL, 1346269UL, 2178309UL,
    3524578UL, 5702887UL, 9227465UL, 14930352UL, 24157817UL,
    39088169UL, 63245986UL, 102334155UL, 165580141UL, 267914296UL,
    433494437UL, 701408733UL, 1134903170UL, 1836311903UL,
    2971215073UL, 4807526976UL, 7778742049UL, 12586269025UL,
    20365011074UL, 32951280099UL, 53316291173UL, 86267571272UL,
    139583862445UL, 225851433717UL, 365435296162UL, 591286729879UL,
    956722026041UL, 1548008755920UL, 2504730781961UL,
    4052739537881UL, 6557470319842UL, 10610209857723UL,
    17167680177565UL,
    27777890035288UL, 44945570212853UL, 72723460248141UL,
    117669030460994UL, 190392490709135UL, 308061521170129UL,
    498454011879264UL, 806515533049393UL, 1304969544928657UL,
    2111485077978050UL, 3416454622906707UL, 5527939700884757UL,
    8944394323791464UL, 14472334024676221UL, 23416728348467685UL,
    37889062373143906UL, 61305790721611591UL, 99194853094755497UL,
    160500643816367088UL, 259695496911122585UL, 420196140727489673UL,
    679891637638612258UL, 1100087778366101931UL, 1779979416004714189UL,
    2880067194370816120UL, 4660046610375530309UL, 7540113804746346429UL,
    12200160415121876738UL
};

__constant uint PRIME_TABLE[PRIME_COUNT] = {
    2u, 3u, 5u, 7u, 11u, 13u, 17u, 19u, 23u, 29u, 31u, 37u, 41u,
    43u, 47u, 53u, 59u, 61u, 67u, 71u, 73u, 79u, 83u, 89u, 97u
};

__constant float MILLENNIUM_BOUNDS[7] = {
    0.001f, 15.0f, 0.5f, 2.0f, 1.0f, 1.0f, 1.0f
};

// Weight w_j = PHI^{-(j+1)} used by the folded-manifold punches.
inline float phi_weight(int j) {
    return pown((float)PHI, -(j + 1));
}

// 0x01 — Cassini power via fast doubling. Returns F_n / L_n folded into a
// DIM x DIM tridiagonal block, mod 2^64 (matches the CPU path's masking).
inline void cassini_power(__global const ulong* n_values,
                          __global ulong* Qn_flat, uint gid) {
    ulong n = n_values[gid];
    ulong a = 0, b = 1;
    for (int bit = 63; bit >= 0; bit--) {
        ulong d = a * (2 * b - a);
        ulong e = a * a + b * b;
        if ((n >> bit) & 1) { a = e; b = d + e; }
        else { a = d; b = e; }
    }
    __global ulong* out = Qn_flat + (ulong)gid * DIM * DIM;
    for (int i = 0; i < DIM; i++) {
        for (int j = 0; j < DIM; j++) {
            ulong val = 0;
            if (i == j) val = a;
            else if (j == i + 1) val = b;
            else if (i == j + 1) val = b - a;
            out[i * DIM + j] = val;
        }
    }
}

// 0x02 — Zeckendorf encoding. Bit j of the mask is set iff FIB[j+2] is used.
// Only FIB[2..65] are encodable in a 64-bit mask (bit index <= 63).
inline void zeckendorf_encode(__global const ulong* values,
                              __global ulong* mask_out, uint gid) {
    ulong n = values[gid];
    ulong mask_lo = 0;
    ulong mask_hi = 0;
    for (int i = 93; i >= 2; i--) {
        if (FIB_TABLE[i] <= n) {
            int bit = i - 2;
            if (bit < 64) mask_lo |= (1UL << bit);
            else          mask_hi |= (1UL << (bit - 64));
            n -= FIB_TABLE[i];
        }
    }
    // Own-block write: every punch writes inside [gid*DIM*DIM, (gid+1)*DIM*DIM)
    // so no two work-items ever share an output address. Slot 0 holds mask
    // bits 0-63, slot 1 holds bits 64-91 (masks over full uint64 inputs can
    // exceed 64 bits).
    mask_out[(ulong)gid * DIM * DIM] = mask_lo;
    mask_out[(ulong)gid * DIM * DIM + 1] = mask_hi;
}

// 0x1C: Zeckendorf decode — inverse of 0x02. Consumes TWO in_ulong slots per
// work-item, indexed by the work-item's offset inside its own punch block
// (gid % count) so it stays in bounds inside the unified all-punch batch:
// in[2i] = mask bits 0-63, in[2i+1] = mask bits 64-127.
inline void zeckendorf_decode(__global const ulong* masks_in,
                              __global ulong* out, uint gid, uint npp) {
    ulong i = (ulong)(gid % npp);
    ulong lo = masks_in[i * 2];
    ulong hi = masks_in[i * 2 + 1];
    ulong n = 0;
    for (int i = 2; i <= 65; i++) {
        if (lo & (1UL << (i - 2))) n += FIB_TABLE[i];
    }
    for (int i = 66; i <= 93; i++) {
        if (hi & (1UL << (i - 2 - 64))) n += FIB_TABLE[i];
    }
    out[(ulong)gid * DIM * DIM] = n;
}

// 0x03 — Pisot schedule: n = ceil(log eps / log phi_inv), phi_inv^n.
inline void pisot_schedule(__global const double* epsilon,
                           __global uint* n_iterations,
                           __global double* phi_pow_n, uint gid) {
    double eps = fmax(epsilon[gid], (double)1e-300);
    double phi = (sqrt(5.0) - 1.0) / 2.0;
    double n_real = ceil(log(eps) / log(phi));
    uint n = (uint)fmin(n_real, (double)1024.0);
    n_iterations[gid] = n;
    phi_pow_n[gid] = pow(phi, (double)n);
}

// 0x04 — Diophantine check against the Hurwitz bound for phi.
// q is drawn from the SAME input array at a wrapped neighbour index so all
// reads stay in bounds.
inline void diophantine_check(__global const ulong* values,
                              __global int* is_valid,
                              uint gid, uint count) {
    ulong p = values[gid];
    ulong q = values[(gid + 1) % count];
    if (q == 0) { is_valid[gid] = 0; return; }
    double phi = (sqrt(5.0) - 1.0) / 2.0;
    double approx = (double)p / (double)q;
    double bound = 1.0 / (sqrt(5.0) * (double)q * (double)q);
    is_valid[gid] = (fabs(phi - approx) >= bound - 1e-15) ? 1 : 0;
}

// 0x05 — Golden-angle point distribution (own-slice write).
inline void golden_angle_distribute(__global float* output_float, uint gid) {
    float ga = 2.39996322972865332f;
    float theta = (float)gid * ga;
    output_float[gid * DIM + 0] = cos(theta);
    output_float[gid * DIM + 1] = sin(theta);
}

// 0x06 — Fold topology passthrough for the k/2-sided sub-block.
inline void fold_topology(__global const float* input,
                          __global float* output, uint gid, uint k) {
    uint side = 1u << (k / 2);
    if (gid >= side * side) return;
    output[gid * DIM] = input[gid];
}

// 0x07 — Spectral gap punch: phi^n, sqrt(5), L_n = phi^n + psi^n.
// Writes into this work-item's own DIM-slice so no other punch collides.
inline void spectral_gap(__global const ulong* n_values,
                         __global float* output_float, uint gid) {
    ulong n = n_values[gid];
    double phi_d = (1.0 + sqrt(5.0)) / 2.0;
    double psi_d = (1.0 - sqrt(5.0)) / 2.0;
    __global float* out = output_float + (ulong)gid * DIM;
    out[0] = (float)pow(phi_d, (double)n);
    out[1] = (float)sqrt(5.0);
    out[2] = (float)(pow(phi_d, (double)n) + pow(psi_d, (double)n));
}

// 0x08 — Poincare fold: x -> x / sqrt(1 + ||x||^2_w).
inline void poincare_fold(__global const float* x_11d,
                          __global float* folded, uint gid) {
    float norm_sq = 0.0f;
    for (int i = 0; i < DIM; i++) {
        float c = x_11d[gid * DIM + i];
        norm_sq += phi_weight(i) * c * c;
    }
    float denom = sqrt(1.0f + norm_sq);
    for (int i = 0; i < DIM; i++)
        folded[gid * DIM + i] = x_11d[gid * DIM + i] / denom;
}

// 0x09 — Poincare unfold: inverse fold, clamped below the ball boundary.
inline void poincare_unfold(__global const float* folded,
                            __global float* x_11d, uint gid) {
    float norm_sq = 0.0f;
    for (int i = 0; i < DIM; i++) {
        float c = folded[gid * DIM + i];
        norm_sq += phi_weight(i) * c * c;
    }
    float clamped = fmin(norm_sq, 1.0f - 1e-6f);
    float denom = sqrt(fmax(1e-6f, 1.0f - clamped));
    for (int i = 0; i < DIM; i++)
        x_11d[gid * DIM + i] = folded[gid * DIM + i] / denom;
}

// 0x0A — Poincare geodesic distance between this item's vector and a
// wrapped neighbour's vector: v_index = (gid + DIM * n_per_punch) % count,
// matching the CPU path exactly.
inline void geodesic_distance(__global const float* vecs,
                              __global float* distance,
                              uint gid, uint count, uint n_per_punch) {
    uint v_idx = (gid + DIM * n_per_punch) % count;
    float nu = 0.0f, nv = 0.0f, ds = 0.0f;
    for (int i = 0; i < DIM; i++) {
        float w = phi_weight(i);
        float ui = vecs[gid * DIM + i];
        float vi = vecs[v_idx * DIM + i];
        nu += w * ui * ui;
        nv += w * vi * vi;
        ds += w * (ui - vi) * (ui - vi);
    }
    float denom = (1.0f - nu) * (1.0f - nv);
    distance[gid * DIM] = acosh(1.0f + 2.0f * ds / fmax(denom, 1e-15f));
}

// 0x0B — Mint certificate: nibble token + coarse sign mask from a vector.
inline void mint_certificate(__global const float* folded,
                             __global ulong* token_out,
                             __global uint* mask_out, uint gid) {
    ulong token = 0;
    uint mask = 0;
    for (int i = 0; i < DIM; i++) {
        float c = folded[gid * DIM + i];
        ulong q = (ulong)(fabs(c) * LUCAS_15) & 0xFFFFUL;
        token = (token << 4) | (q & 0xFUL);
        if (fabs(c) > 0.5f) mask |= (1u << i);
    }
    token_out[(ulong)gid * DIM * DIM] = token;
    mask_out[gid] = mask;
}

// 0x0C — Salamander allocation: token picks a prime bucket, mask picks the
// slot inside it.
inline void salamander_alloc(__global const ulong* tokens,
                             __global const uint* masks,
                             __global uint* slot_out, uint gid) {
    ulong token = tokens[gid];
    uint mask = masks[gid];
    uint k = (uint)(token % (ulong)PRIME_COUNT);
    uint offset = k * SLOTS_PER_PRIME;
    uint prime = PRIME_TABLE[k];
    uint slot = mask % prime;
    slot_out[gid] = offset + slot;
}

// 0x0D — Beatty partition of {0..n-1} by the golden sequence floor(k*phi).
inline void beatty_partition(__global uint* partition,
                             uint gid, uint n_per_punch) {
    double alpha = 1.6180339887498949;
    partition[gid] = (uint)floor((gid + 1) * alpha) % n_per_punch;
}

// 0x0E — Cassini determinant sign: (-1)^k.
inline void cassini_det(__global const ulong* k_values,
                        __global long* det_out, uint gid) {
    ulong k = k_values[gid];
    det_out[gid] = ((k % 2) == 0) ? 1L : -1L;
}

// 0x0F — Decoupling mask validity: no two adjacent bits set.
inline void decoupling_mask(__global const uint* masks,
                            __global int* valid_out, uint gid) {
    uint M = masks[gid];
    valid_out[gid] = ((M & (M << 1)) == 0) ? 1 : 0;
}

// 0x10 — Millennium verify: placeholder bound table per problem id.
inline void millennium_verify(__global const uint* problem_ids,
                              __global int* valid_out,
                              __global float* bound_out, uint gid) {
    uint problem = problem_ids[gid] % 7u;
    valid_out[gid] = 1;
    bound_out[gid * DIM] = MILLENNIUM_BOUNDS[problem];
}

// 0x11 — Schema split: telemetry passthrough + zeroed proof channel.
inline void schema_split(__global const float* telemetry,
                         __global float* exec_out,
                         __global int* proof_out, uint gid) {
    exec_out[gid * DIM] = telemetry[gid];
    proof_out[gid] = 0;
}

// 0x12 — Quantum phase estimation (simulated classically)
inline void quantum_phase(__global const ulong* n_values,
                          __global float* phase_out, uint gid) {
    ulong n = n_values[gid];
    double PHI_d = (1.0 + sqrt(5.0)) / 2.0;
    double phi_pow = pow(PHI_d, (double)(n % 64));
    phase_out[gid * DIM] = (float)(phi_pow - floor(phi_pow));
}

// 0x13 — Quantum Hamiltonian simulation (simulated classically)
inline void quantum_hamiltonian(__global const ulong* n_values,
                                __global float* energy_out, uint gid) {
    ulong n = n_values[gid];
    double PHI_d = (1.0 + sqrt(5.0)) / 2.0;
    energy_out[gid * DIM] = (float)pow(PHI_d, -(double)(n % 32));
}

// 0x14 — Quantum Grover search (simulated classically)
inline void quantum_grover(__global const uint* problem_ids,
                           __global uint* found_out, uint gid) {
    uint problem = problem_ids[gid] % 7u;
    uint N = 2048;
    uint iterations = (uint)(3.14159f / 4.0f * sqrt((float)N));
    found_out[gid] = (problem + iterations) % N;
}

// 0x15 — Manifold compute: weighted squared norm of the 11D vector.
inline void manifold_compute(__global const float* x_11d,
                             __global float* out, uint gid) {
    float s = 0.0f;
    for (int i = 0; i < DIM; i++) {
        float c = x_11d[gid * DIM + i];
        s += phi_weight(i) * c * c;
    }
    out[gid * DIM] = s;
}

// 0x16 — Millennium all: emit all seven placeholder bounds per item.
inline void millennium_all(__global float* all_bounds, uint gid) {
    for (int i = 0; i < 7; i++) all_bounds[gid * DIM + i] = MILLENNIUM_BOUNDS[i];
}

// 0x17 — Hard gate: passport-valid AND non-adjacent mask, both read from
// input_int (never from an uninitialised output buffer).
inline void hard_gate(__global const uint* input_int,
                      __global int* gate_out, uint gid, uint count) {
    int valid = (int)input_int[gid];
    uint M = input_int[(gid + 1) % count];
    int non_adj = ((M & (M << 1)) == 0) ? 1 : 0;
    gate_out[gid] = (valid && non_adj) ? 1 : 0;
}

// 0x18 — Schema enforce: solver-data passthrough + zeroed proof channel.
inline void schema_enforce(__global const float* solver_data,
                           __global float* telemetry_out,
                           __global int* proof_out, uint gid) {
    telemetry_out[gid * DIM] = solver_data[gid];
    proof_out[gid] = 0;
}

// 0x19 — Immutable proof: zeroed channel.
inline void immutable_proof(__global int* proof_out, uint gid) {
    proof_out[gid] = 0;
}

// 0x1A — Phi-filter score: folded-manifold resonance score in [0,1].
// Stage A of the 3-stage hash pipeline (Metal phi_filter.metal parity).
// score = weighted energy of the folded vector, in [0,1) by construction.
// Scores >= 0.5 proceed to Stage B filter + Stage C SHA-256.
inline void phi_filter_score(__global const float* x_11d,
                             __global float* score_out, uint gid) {
    float norm_sq = 0.0f;
    for (int i = 0; i < DIM; i++) {
        float c = x_11d[gid * DIM + i];
        norm_sq += phi_weight(i) * c * c;
    }
    float denom = sqrt(1.0f + norm_sq);
    float acc = 0.0f;
    for (int i = 0; i < DIM; i++) {
        float f = x_11d[gid * DIM + i] / denom;
        acc += phi_weight(i) * f * f;
    }
    score_out[gid * DIM] = fmin(fmax(acc, 0.0f), 1.0f);
}

// 0x1B — SHA-256d grind marker: ordered nonce probe emission for host-side
// double-SHA256 verification (Stage C). The kernel does NOT implement SHA-256
// (no crypto builtins in OpenCL C); it emits the strided probe sequence while
// the host grinds real sha256d with early exit on hash <= target.
// Own-block write: mask + nonce land in [gid*DIM*DIM, (gid+1)*DIM*DIM).
inline void sha256d_grind_mark(__global const ulong* window_params,
                               __global ulong* nonce_block_out,
                               __global int* valid_out, uint gid) {
    ulong nonce_start = window_params[0];
    ulong window = window_params[1] > 0 ? window_params[1] : 1;
    ulong stride = window_params[2] > 0 ? window_params[2] : 1;
    ulong nonce = (nonce_start + (ulong)gid * stride) % window + nonce_start;
    nonce = nonce & 0xFFFFFFFFUL;
    __global ulong* block = nonce_block_out + (ulong)gid * DIM * DIM;
    block[0] = nonce;
    block[1] = stride;
    valid_out[gid] = 1;
}

__kernel void unified_punch_kernel(
    __global const float*  input_float,
    __global const ulong*  input_ulong,
    __global const uint*   input_int,
    __global const double* input_double,
    __global const uint*   punch_ids,
    __global float*  output_float,
    __global ulong*  output_ulong,
    __global int*    output_int,
    __global long*   output_long,
    __global double* output_double,
    const uint count,
    const uint n_per_punch
) {
    uint gid = get_global_id(0);
    if (gid >= count) return;
    uint punch = punch_ids[gid];
    switch (punch) {
        case 0x01: cassini_power(input_ulong, output_ulong, gid); break;
        case 0x02: zeckendorf_encode(input_ulong, output_ulong, gid); break;
        case 0x03: pisot_schedule(input_double, (__global uint*)output_int,
                                  output_double, gid); break;
        case 0x04: diophantine_check(input_ulong, output_int, gid, count); break;
        case 0x05: golden_angle_distribute(output_float, gid); break;
        case 0x06: fold_topology(input_float, output_float, gid, 4); break;
        case 0x07: spectral_gap(input_ulong, output_float, gid); break;
        case 0x08: poincare_fold(input_float, output_float, gid); break;
        case 0x09: poincare_unfold(input_float, output_float, gid); break;
        case 0x0A: geodesic_distance(input_float, output_float,
                                     gid, count, n_per_punch); break;
        case 0x0B: mint_certificate(input_float, output_ulong,
                                    (__global uint*)output_int, gid); break;
        case 0x0C: salamander_alloc(input_ulong, input_int,
                                    (__global uint*)output_int, gid); break;
        case 0x0D: beatty_partition((__global uint*)output_int,
                                    gid, n_per_punch); break;
        case 0x0E: cassini_det(input_ulong, output_long, gid); break;
        case 0x0F: decoupling_mask(input_int, output_int, gid); break;
        case 0x10: millennium_verify(input_int, output_int,
                                     output_float, gid); break;
        case 0x11: schema_split(input_float, output_float, output_int, gid); break;
        case 0x12: quantum_phase(input_ulong, output_float, gid); break;
        case 0x13: quantum_hamiltonian(input_ulong, output_float, gid); break;
        case 0x14: quantum_grover(input_int, (__global uint*)output_int, gid); break;
        case 0x15: manifold_compute(input_float, output_float, gid); break;
        case 0x16: millennium_all(output_float, gid); break;
        case 0x17: hard_gate(input_int, output_int, gid, count); break;
        case 0x18: schema_enforce(input_float, output_float,
                                  output_int, gid); break;
        case 0x19: immutable_proof(output_int, gid); break;
        case 0x1A: phi_filter_score(input_float, output_float, gid); break;
        case 0x1C: zeckendorf_decode(input_ulong, output_ulong, gid, n_per_punch); break;
        case 0x1B: sha256d_grind_mark(input_ulong, output_ulong,
                                      output_int, gid); break;
        default: break;
    }
}
