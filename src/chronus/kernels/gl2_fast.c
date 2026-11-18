/*
 * gl2_fast.c — Zero-LUT SIMD Datapath & Hardware CRC-32C for GL(2, Z/256Z)
 *
 * Compile:
 *   gcc -O3 -march=native -Wall -Wextra -Werror -shared -fPIC gl2_fast.c -o libgl2_fast.so
 */

#include <stddef.h>
#include <stdint.h>

#if defined(__AVX2__)
#include <immintrin.h>
#endif

#if defined(__ARM_NEON) || defined(__ARM_NEON__)
#include <arm_neon.h>
#endif

#if defined(__SSE4_2__)
#include <nmmintrin.h>
#endif

#if defined(__ARM_FEATURE_CRC32)
#include <arm_acle.h>
#endif

static inline void affine_step_scalar(
    const uint8_t * restrict src,
    uint8_t * restrict dst,
    size_t num_pairs,
    uint8_t m00, uint8_t m01, uint8_t m10, uint8_t m11
) {
    for (size_t i = 0; i < num_pairs; ++i) {
        uint8_t x = src[2 * i];
        uint8_t y = src[2 * i + 1];
        dst[2 * i]     = (uint8_t)(m00 * x + m01 * y);
        dst[2 * i + 1] = (uint8_t)(m10 * x + m11 * y);
    }
}

#if defined(__AVX2__)
static inline void affine_step_avx2(
    const uint8_t * restrict src,
    uint8_t * restrict dst,
    size_t num_pairs,
    uint8_t m00, uint8_t m01, uint8_t m10, uint8_t m11
) {
    const __m256i mask_lo = _mm256_set1_epi16(0x00FF);
    const __m256i v_m00   = _mm256_set1_epi16((int16_t)m00);
    const __m256i v_m01   = _mm256_set1_epi16((int16_t)m01);
    const __m256i v_m10   = _mm256_set1_epi16((int16_t)m10);
    const __m256i v_m11   = _mm256_set1_epi16((int16_t)m11);

    size_t i = 0;
    for (; i + 16 <= num_pairs; i += 16) {
        __m256i pairs = _mm256_loadu_si256((const __m256i *)(src + 2 * i));
        __m256i x = _mm256_and_si256(pairs, mask_lo);
        __m256i y = _mm256_srli_epi16(pairs, 8);

        __m256i u = _mm256_add_epi16(_mm256_mullo_epi16(x, v_m00), _mm256_mullo_epi16(y, v_m01));
        __m256i v = _mm256_add_epi16(_mm256_mullo_epi16(x, v_m10), _mm256_mullo_epi16(y, v_m11));

        __m256i out = _mm256_or_si256(
            _mm256_and_si256(u, mask_lo),
            _mm256_slli_epi16(v, 8)
        );
        _mm256_storeu_si256((__m256i *)(dst + 2 * i), out);
    }
    if (i < num_pairs) {
        affine_step_scalar(src + 2 * i, dst + 2 * i, num_pairs - i, m00, m01, m10, m11);
    }
}
#elif defined(__ARM_NEON) || defined(__ARM_NEON__)
static inline void affine_step_neon(
    const uint8_t * restrict src,
    uint8_t * restrict dst,
    size_t num_pairs,
    uint8_t m00, uint8_t m01, uint8_t m10, uint8_t m11
) {
    const uint8x16_t v_m00 = vdupq_n_u8(m00);
    const uint8x16_t v_m01 = vdupq_n_u8(m01);
    const uint8x16_t v_m10 = vdupq_n_u8(m10);
    const uint8x16_t v_m11 = vdupq_n_u8(m11);

    size_t i = 0;
    for (; i + 16 <= num_pairs; i += 16) {
        uint8x16x2_t xy = vld2q_u8(src + 2 * i);
        uint8x16x2_t uv;
        uv.val[0] = vmlaq_u8(vmulq_u8(xy.val[0], v_m00), xy.val[1], v_m01);
        uv.val[1] = vmlaq_u8(vmulq_u8(xy.val[0], v_m10), xy.val[1], v_m11);
        vst2q_u8(dst + 2 * i, uv);
    }
    if (i < num_pairs) {
        affine_step_scalar(src + 2 * i, dst + 2 * i, num_pairs - i, m00, m01, m10, m11);
    }
}
#endif

void gl2_fold_pairs(const uint8_t * restrict src, uint8_t * restrict dst, size_t num_pairs) {
#if defined(__AVX2__)
    affine_step_avx2(src, dst, num_pairs, 219, 98, 98, 121);
#elif defined(__ARM_NEON) || defined(__ARM_NEON__)
    affine_step_neon(src, dst, num_pairs, 219, 98, 98, 121);
#else
    affine_step_scalar(src, dst, num_pairs, 219, 98, 98, 121);
#endif
}

void gl2_unfold_pairs(const uint8_t * restrict src, uint8_t * restrict dst, size_t num_pairs) {
#if defined(__AVX2__)
    affine_step_avx2(src, dst, num_pairs, 135, 98, 98, 37);
#elif defined(__ARM_NEON) || defined(__ARM_NEON__)
    affine_step_neon(src, dst, num_pairs, 135, 98, 98, 37);
#else
    affine_step_scalar(src, dst, num_pairs, 135, 98, 98, 37);
#endif
}

/* [REVIEW FIX R1] gl2_fold_truncated_pairs removed from production (no-truncation contract);
   the lossy projection is audited in Python only: tests/quotient_geometry_audit.py */

uint32_t gl2_crc32c(uint32_t crc, const uint8_t * restrict buf, size_t len) {
    uint32_t c = crc ^ 0xFFFFFFFFu;
    size_t i = 0;
#if defined(__SSE4_2__) && defined(__x86_64__)
    for (; i + 8 <= len; i += 8) {
        uint64_t word;
        __builtin_memcpy(&word, buf + i, sizeof(word));
        c = (uint32_t)_mm_crc32_u64((uint64_t)c, word);
    }
    for (; i < len; ++i) {
        c = _mm_crc32_u8(c, buf[i]);
    }
#elif defined(__ARM_FEATURE_CRC32)
    for (; i + 8 <= len; i += 8) {
        uint64_t word;
        __builtin_memcpy(&word, buf + i, sizeof(word));
        c = __crc32cd(c, word);
    }
    for (; i < len; ++i) {
        c = __crc32cb(c, buf[i]);
    }
#else
    for (; i < len; ++i) {
        c ^= buf[i];
        for (int b = 0; b < 8; ++b) {
            c = (c >> 1) ^ (0x82F63B78u & -(c & 1u));
        }
    }
#endif
    return c ^ 0xFFFFFFFFu;
}

