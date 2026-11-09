#ifndef CHRONUS_EXACT_LATTICE_HPP
#define CHRONUS_EXACT_LATTICE_HPP

#include <cstdint>
#include <cstddef>
#include <vector>
#include <array>

namespace chronus {
namespace lattice {

// Signed 256-bit limb representation: 4 little-endian 64-bit limbs
struct Int256Limbs {
    std::array<uint64_t, 4> limbs; // [0] = lowest 64 bits, [3] = highest 64 bits
    bool is_negative() const {
        return (limbs[3] & 0x8000000000000000ULL) != 0;
    }
};

// PhiElement in Z[phi]: (a + b * phi)
// Fold rule: phi^2 = phi + 1
struct PhiElementCpp {
    int64_t a;
    int64_t b;

    PhiElementCpp multiply(const PhiElementCpp& other) const {
        // (a + b*phi)*(c + d*phi) = (a*c + b*d) + (a*d + b*c + b*d)*phi
        int64_t res_a = a * other.a + b * other.b;
        int64_t res_b = a * other.b + b * other.a + b * other.b;
        return {res_a, res_b};
    }

    int64_t trace() const {
        return 2 * a + b;
    }

    int64_t norm() const {
        return a * a + a * b - b * b;
    }
};

// Metallic Ring Element in Z[sigma_m]: (a + b * sigma_m)
// Fold rule: sigma_m^2 = m * sigma_m + 1
struct MetallicElementCpp {
    uint32_t m;
    int64_t a;
    int64_t b;

    MetallicElementCpp multiply(const MetallicElementCpp& other) const {
        int64_t res_a = a * other.a + b * other.b;
        int64_t res_b = a * other.b + b * other.a + static_cast<int64_t>(m) * b * other.b;
        return {m, res_a, res_b};
    }

    int64_t trace() const {
        return 2 * a + static_cast<int64_t>(m) * b;
    }

    int64_t norm() const {
        return a * a + static_cast<int64_t>(m) * a * b - b * b;
    }
};

// Fast doubling power of phi^order
PhiElementCpp phi_power_cpp(uint32_t order);

// Fast doubling power of sigma_m^order
MetallicElementCpp metallic_power_cpp(uint32_t m, uint32_t order);

// Metallic sequence value T_n = Tr(sigma_m^n)
int64_t metallic_sequence_cpp(uint32_t m, uint32_t order);

} // namespace lattice
} // namespace chronus

#endif // CHRONUS_EXACT_LATTICE_HPP
