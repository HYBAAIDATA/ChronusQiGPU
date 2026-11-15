// SHA-256d nonce search kernel for Chronus iGPU mining.
//
// Clean-room implementation of FIPS 180-4 SHA-256d (SHA-256 applied twice),
// for the Bitcoin header layout: 80-byte header, nonce in bytes 76..79 LE.
// The host precomputes the midstate (compression of header bytes 0..63) with
// chronus.execution.asic_sha256.sha256_block, so each work item runs only
// the second block of the outer hash plus the single block of the inner hash.
//
// Each work item tests exactly one nonce: base_nonce + get_global_id(0).
// A nonce is reported when int.from_bytes(digest, "little") <= target,
// matching chronus.execution.mining semantics. Integer arithmetic only.

#define MASK32 0xffffffffU

__constant uint K[64] = {
    0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
    0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
    0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
    0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
    0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
    0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
    0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
    0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
    0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
    0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
    0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
    0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
    0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
    0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
    0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
    0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U,
};

inline uint rotr(uint x, uint n) {
    return (x >> n) | (x << (32 - n));
}

inline uint bswap32(uint x) {
    return ((x & 0x000000ffU) << 24) | ((x & 0x0000ff00U) << 8)
         | ((x & 0x00ff0000U) >> 8) | ((x & 0xff000000U) >> 24);
}

inline void compress(uint state[8], uint w[64]) {
    #pragma unroll
    for (int t = 16; t < 64; ++t) {
        uint s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >> 3);
        uint s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >> 10);
        w[t] = w[t - 16] + s0 + w[t - 7] + s1;
    }
    uint a = state[0], b = state[1], c = state[2], d = state[3];
    uint e = state[4], f = state[5], g = state[6], h = state[7];
    #pragma unroll
    for (int t = 0; t < 64; ++t) {
        uint big_s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        uint ch = (e & f) ^ (~e & g);
        uint temp1 = h + big_s1 + ch + K[t] + w[t];
        uint big_s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        uint maj = (a & b) ^ (a & c) ^ (b & c);
        uint temp2 = big_s0 + maj;
        h = g; g = f; f = e; e = d + temp1;
        d = c; c = b; b = a; a = temp1 + temp2;
    }
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

__kernel void sha256d_search(
    uint m0, uint m1, uint m2, uint m3,
    uint m4, uint m5, uint m6, uint m7,
    uint t0, uint t1, uint t2,
    uint base_nonce,
    uint tg0, uint tg1, uint tg2, uint tg3,
    uint tg4, uint tg5, uint tg6, uint tg7,
    __global uint* found,
    __global uint* found_count,
    uint max_results)
{
    uint nonce = base_nonce + get_global_id(0);

    // Outer SHA-256, block 2: header bytes 64..79, padding, 640-bit length.
    // The nonce occupies bytes 76..79 little-endian, i.e. bswapped as a
    // big-endian schedule word.
    uint state[8] = { m0, m1, m2, m3, m4, m5, m6, m7 };
    uint w[64];
    w[0] = t0; w[1] = t1; w[2] = t2; w[3] = bswap32(nonce);
    w[4] = 0x80000000U;
    #pragma unroll
    for (int i = 5; i < 15; ++i) { w[i] = 0U; }
    w[15] = 0x00000280U;  // 80 bytes * 8
    compress(state, w);

    // Inner SHA-256 over the 32-byte first digest: one block, 256-bit length.
    uint inner_state[8] = {
        0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU,
        0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U,
    };
    #pragma unroll
    for (int i = 0; i < 8; ++i) { w[i] = state[i]; }
    w[8] = 0x80000000U;
    #pragma unroll
    for (int i = 9; i < 15; ++i) { w[i] = 0U; }
    w[15] = 0x00000100U;  // 32 bytes * 8
    compress(inner_state, w);

    // Bitcoin compares int.from_bytes(digest, "little") <= target. The digest
    // words above are big-endian schedule words, so the little-endian value
    // words are their byte swaps.
    uint v[8] = {
        bswap32(inner_state[0]), bswap32(inner_state[1]),
        bswap32(inner_state[2]), bswap32(inner_state[3]),
        bswap32(inner_state[4]), bswap32(inner_state[5]),
        bswap32(inner_state[6]), bswap32(inner_state[7]),
    };
    uint tg[8] = { tg0, tg1, tg2, tg3, tg4, tg5, tg6, tg7 };

    bool le = true;
    #pragma unroll
    for (int j = 7; j >= 0; --j) {
        if (v[j] != tg[j]) { le = v[j] < tg[j]; break; }
    }
    if (!le) { return; }

    uint slot = atomic_inc(found_count);
    if (slot < max_results) {
        found[slot] = nonce;
    }
}
