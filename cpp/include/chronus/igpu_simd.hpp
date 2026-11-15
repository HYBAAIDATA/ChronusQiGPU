#ifndef CHRONUS_IGPU_SIMD_HPP
#define CHRONUS_IGPU_SIMD_HPP

#include <cstdint>
#include <cstddef>
#include <vector>

namespace chronus {
namespace igpu {

// M15 Transformation Matrix over Z/256Z:
// M15 = [219, 98; 98, 121]
// M15_inv = [135, 98; 98, 37]
constexpr uint8_t M15_00 = 219;
constexpr uint8_t M15_01 = 98;
constexpr uint8_t M15_10 = 98;
constexpr uint8_t M15_11 = 121;

constexpr uint8_t M15_INV_00 = 135;
constexpr uint8_t M15_INV_01 = 98;
constexpr uint8_t M15_INV_10 = 98;
constexpr uint8_t M15_INV_11 = 37;

struct BytePair {
    uint8_t a;
    uint8_t b;
};

// Scalar reference fold/unfold for single pair
inline BytePair fold_pair_scalar(uint8_t a, uint8_t b) {
    uint8_t out_a = static_cast<uint8_t>((static_cast<uint32_t>(M15_00) * a + static_cast<uint32_t>(M15_01) * b) & 0xFF);
    uint8_t out_b = static_cast<uint8_t>((static_cast<uint32_t>(M15_10) * a + static_cast<uint32_t>(M15_11) * b) & 0xFF);
    return {out_a, out_b};
}

inline BytePair unfold_pair_scalar(uint8_t a, uint8_t b) {
    uint8_t out_a = static_cast<uint8_t>((static_cast<uint32_t>(M15_INV_00) * a + static_cast<uint32_t>(M15_INV_01) * b) & 0xFF);
    uint8_t out_b = static_cast<uint8_t>((static_cast<uint32_t>(M15_INV_10) * a + static_cast<uint32_t>(M15_INV_11) * b) & 0xFF);
    return {out_a, out_b};
}

// Vectorized 8-pair (16-byte) parallel fold/unfold
// Operates on contiguous memory buffer of pairs
void fold_pairs_simd(const uint8_t* in, uint8_t* out, size_t num_pairs);
void unfold_pairs_simd(const uint8_t* in, uint8_t* out, size_t num_pairs);

// Dual-space In-Place Linear Query:
// Computes q^T * x (mod 256) directly from folded data y = M15 * x
// via q'^T * y where q' = M15^(-T) * q = M15^(-1) * q
uint32_t dual_space_dot_product(const uint8_t* q, const uint8_t* folded_y, size_t num_pairs);

// Dual-space batch query: multiple query vectors against resident folded block
void dual_space_batch_query(
    const uint8_t* queries, // num_queries * (2 * num_pairs)
    size_t num_queries,
    const uint8_t* folded_y, // 2 * num_pairs
    size_t num_pairs,
    uint32_t* results // num_queries
);

} // namespace igpu
} // namespace chronus

#endif // CHRONUS_IGPU_SIMD_HPP
