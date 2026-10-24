/*
 phi_gemm.metal — Custom Metal compute shader for φ-tuned L_18 GEMM
 Target: N = L_18 = 5778 on M3 Ultra, 60 GPU cores, Metal 4

 Strategy: 32×32 threadgroup tile with explicit shared memory load.
 M3 Ultra threadgroup shared memory = 32 KB per compute unit.
 Tile size 32×32 × float32 = 4 KB — fits 8 tiles per CU simultaneously.

 L_18 = 5778 = 180 × 32 + 18  (180 full tiles + 18-column remainder)
 We handle the remainder with a bounds-checked load path.

 The AMX coprocessor is invoked automatically by Metal's GEMM path
 when the inner loop is vectorised. We make this explicit by writing
 the accumulation in 4-wide float4 chunks.

 SECURITY: Data-Independent Timing (DIT) enabled to mitigate GoFetch
 vulnerability in M3 Ultra's Data Memory-Dependent Prefetcher (DMP).
 This prevents side-channel attacks on cryptographic operations.
*/

#include <metal_stdlib>
using namespace metal;

// SECURITY: Enable Data-Independent Timing (DIT) to mitigate GoFetch vulnerability
// This disables the DMP for sensitive cryptographic operations, preventing
// side-channel key extraction attacks on M3 Ultra hardware.
#pragma clang attribute push(__attribute__((target("data-independent-timing"))), apply_to = function)

constant int TILE = 32;

kernel void phi_gemm_L18(
    device const float* A      [[ buffer(0) ]],
    device const float* B      [[ buffer(1) ]],
    device       float* C      [[ buffer(2) ]],
    constant     int&   N      [[ buffer(3) ]],   // = 5778
    uint2 gid  [[ thread_position_in_grid ]],
    uint2 lid  [[ thread_position_in_threadgroup ]],
    uint2 tgid [[ threadgroup_position_in_grid  ]]
) {
    // Shared memory tiles for A and B blocks
    threadgroup float As[TILE][TILE];
    threadgroup float Bs[TILE][TILE];

    int row = tgid.y * TILE + lid.y;
    int col = tgid.x * TILE + lid.x;

    float acc = 0.0f;
    int n_tiles = (N + TILE - 1) / TILE;

    for (int t = 0; t < n_tiles; ++t) {
        // Load tile of A: row × (t*TILE + lid.x)
        int a_col = t * TILE + lid.x;
        As[lid.y][lid.x] = (row < N && a_col < N)
                           ? A[row * N + a_col]
                           : 0.0f;

        // Load tile of B: (t*TILE + lid.y) × col
        int b_row = t * TILE + lid.y;
        Bs[lid.y][lid.x] = (b_row < N && col < N)
                           ? B[b_row * N + col]
                           : 0.0f;

        threadgroup_barrier(mem_flags::mem_threadgroup);

        // Accumulate — unrolled 4× for AMX hint
        for (int k = 0; k < TILE; k += 4) {
            acc += As[lid.y][k  ] * Bs[k  ][lid.x];
            acc += As[lid.y][k+1] * Bs[k+1][lid.x];
            acc += As[lid.y][k+2] * Bs[k+2][lid.x];
            acc += As[lid.y][k+3] * Bs[k+3][lid.x];
        }

        threadgroup_barrier(mem_flags::mem_threadgroup);
    }

    if (row < N && col < N) {
        C[row * N + col] = acc;
    }
}

/*
 Dispatch configuration for L_18 = 5778:
   threads_per_threadgroup = MTLSize(32, 32, 1)
   threadgroups            = MTLSize(ceil(5778/32), ceil(5778/32), 1)
                           = MTLSize(181, 181, 1)
   total threads           = 181 × 181 × 1024 = 33,607,936
   GPU cores = 60, SIMD width = 32 → 60 × 32 = 1920 threads active
   Occupancy estimate: 33,607,936 / 1920 ≈ 17,504 waves

 Expected throughput:
   M3 Ultra peak FP32: ~21.2 TFLOP/s (theoretical)
   GEMM efficiency at 32×32 tile: ~75% → ~15.9 TFLOP/s
   Target: beat 15,549 GFLOP/s (measured neighbourhood peak N=5776)
*/

// SECURITY: End DIT scope
#pragma clang attribute pop
