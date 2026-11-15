#include "chronus/exact_lattice.hpp"

namespace chronus {
namespace lattice {

PhiElementCpp phi_power_cpp(uint32_t order) {
    PhiElementCpp result{1, 0};
    PhiElementCpp base{0, 1}; // phi^1
    while (order > 0) {
        if (order & 1) {
            result = result.multiply(base);
        }
        order >>= 1;
        if (order > 0) {
            base = base.multiply(base);
        }
    }
    return result;
}

MetallicElementCpp metallic_power_cpp(uint32_t m, uint32_t order) {
    MetallicElementCpp result{m, 1, 0};
    MetallicElementCpp base{m, 0, 1};
    while (order > 0) {
        if (order & 1) {
            result = result.multiply(base);
        }
        order >>= 1;
        if (order > 0) {
            base = base.multiply(base);
        }
    }
    return result;
}

int64_t metallic_sequence_cpp(uint32_t m, uint32_t order) {
    return metallic_power_cpp(m, order).trace();
}

} // namespace lattice
} // namespace chronus
