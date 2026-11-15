#include "chronus/igpu_simd.hpp"
#include <cstring>

#if defined(__AVX2__)
#include <immintrin.h>
#endif

namespace chronus {
namespace igpu {

void fold_pairs_simd(const uint8_t* in, uint8_t* out, size_t num_pairs) {
    size_t i = 0;

#if defined(__AVX2__)
    // Process 16 pairs (32 bytes) at a time using AVX2
    const __m256i m00 = _mm256_set1_epi16(M15_00);
    const __m256i m01 = _mm256_set1_epi16(M15_01);
    const __m256i m10 = _mm256_set1_epi16(M15_10);
    const __m256i m11 = _mm256_set1_epi16(M15_11);
    const __m256i mask_ff = _mm256_set1_epi16(0x00FF);

    for (; i + 16 <= num_pairs; i += 16) {
        // Load 32 bytes of interleaved (a, b) pairs
        __m256i raw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(in + i * 2));
        
        // Unpack low and high byte lanes into 16-bit words
        // Evens are a, Odds are b
        __m256i a_16 = _mm256_and_si256(raw, mask_ff);
        __m256i b_16 = _mm256_and_si256(_mm256_srli_epi16(raw, 8), mask_ff);

        // out_a = 219 * a + 98 * b (mod 256)
        __m256i prod_a0 = _mm256_mullo_epi16(a_16, m00);
        __m256i prod_a1 = _mm256_mullo_epi16(b_16, m01);
        __m256i res_a = _mm256_and_si256(_mm256_add_epi16(prod_a0, prod_a1), mask_ff);

        // out_b = 98 * a + 121 * b (mod 256)
        __m256i prod_b0 = _mm256_mullo_epi16(a_16, m10);
        __m256i prod_b1 = _mm256_mullo_epi16(b_16, m11);
        __m256i res_b = _mm256_and_si256(_mm256_add_epi16(prod_b0, prod_b1), mask_ff);

        // Pack res_a and res_b back into interleaved bytes
        __m256i interleaved = _mm256_or_si256(res_a, _mm256_slli_epi16(res_b, 8));
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(out + i * 2), interleaved);
    }
#endif

    // Scalar tail or baseline execution
    for (; i < num_pairs; ++i) {
        uint8_t a = in[i * 2];
        uint8_t b = in[i * 2 + 1];
        BytePair folded = fold_pair_scalar(a, b);
        out[i * 2] = folded.a;
        out[i * 2 + 1] = folded.b;
    }
}

void unfold_pairs_simd(const uint8_t* in, uint8_t* out, size_t num_pairs) {
    size_t i = 0;

#if defined(__AVX2__)
    // Process 16 pairs (32 bytes) at a time using AVX2 with M15_inv
    const __m256i inv00 = _mm256_set1_epi16(M15_INV_00);
    const __m256i inv01 = _mm256_set1_epi16(M15_INV_01);
    const __m256i inv10 = _mm256_set1_epi16(M15_INV_10);
    const __m256i inv11 = _mm256_set1_epi16(M15_INV_11);
    const __m256i mask_ff = _mm256_set1_epi16(0x00FF);

    for (; i + 16 <= num_pairs; i += 16) {
        __m256i raw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(in + i * 2));
        __m256i a_16 = _mm256_and_si256(raw, mask_ff);
        __m256i b_16 = _mm256_and_si256(_mm256_srli_epi16(raw, 8), mask_ff);

        __m256i prod_a0 = _mm256_mullo_epi16(a_16, inv00);
        __m256i prod_a1 = _mm256_mullo_epi16(b_16, inv01);
        __m256i res_a = _mm256_and_si256(_mm256_add_epi16(prod_a0, prod_a1), mask_ff);

        __m256i prod_b0 = _mm256_mullo_epi16(a_16, inv10);
        __m256i prod_b1 = _mm256_mullo_epi16(b_16, inv11);
        __m256i res_b = _mm256_and_si256(_mm256_add_epi16(prod_b0, prod_b1), mask_ff);

        __m256i interleaved = _mm256_or_si256(res_a, _mm256_slli_epi16(res_b, 8));
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(out + i * 2), interleaved);
    }
#endif

    for (; i < num_pairs; ++i) {
        uint8_t a = in[i * 2];
        uint8_t b = in[i * 2 + 1];
        BytePair unfolded = unfold_pair_scalar(a, b);
        out[i * 2] = unfolded.a;
        out[i * 2 + 1] = unfolded.b;
    }
}

uint32_t dual_space_dot_product(const uint8_t* q, const uint8_t* folded_y, size_t num_pairs) {
    // Compile query q into dual fold-space: q' = M15^(-1) * q
    // Then compute q'^T * y (mod 256) sum
    uint32_t total = 0;
    for (size_t i = 0; i < num_pairs; ++i) {
        uint8_t qa = q[i * 2];
        uint8_t qb = q[i * 2 + 1];
        BytePair q_prime = unfold_pair_scalar(qa, qb);

        uint8_t ya = folded_y[i * 2];
        uint8_t yb = folded_y[i * 2 + 1];

        uint32_t prod_a = static_cast<uint32_t>(q_prime.a) * ya;
        uint32_t prod_b = static_cast<uint32_t>(q_prime.b) * yb;
        total = (total + prod_a + prod_b) & 0xFF;
    }
    return total;
}

void dual_space_batch_query(
    const uint8_t* queries,
    size_t num_queries,
    const uint8_t* folded_y,
    size_t num_pairs,
    uint32_t* results
) {
    for (size_t q_idx = 0; q_idx < num_queries; ++q_idx) {
        const uint8_t* q_vec = queries + q_idx * (num_pairs * 2);
        results[q_idx] = dual_space_dot_product(q_vec, folded_y, num_pairs);
    }
}

} // namespace igpu
} // namespace chronus
