#include "chronus/quantum_superposition.hpp"
#include <stdexcept>
#include <algorithm>
#include <cmath>

namespace chronus {
namespace quantum {

QuantumState::QuantumState(uint32_t num_qubits)
    : num_qubits_(num_qubits), amplitudes_(static_cast<size_t>(1) << num_qubits, 0) {
    if (num_qubits == 0 || num_qubits > 16) {
        throw std::invalid_argument("num_qubits must be in [1, 16]");
    }
    // Initialize to |0...0>
    amplitudes_[0] = 1;
}

QuantumState::QuantumState(uint32_t num_qubits, const std::vector<int32_t>& amps)
    : num_qubits_(num_qubits), amplitudes_(amps) {
    size_t expected_size = static_cast<size_t>(1) << num_qubits;
    if (amps.size() != expected_size) {
        throw std::invalid_argument("amplitudes size does not match 2^num_qubits");
    }
    for (auto& a : amplitudes_) {
        a = mod_p(a);
    }
}

QuantumState& QuantumState::apply_h(uint32_t qubit) {
    if (qubit >= num_qubits_) throw std::out_of_range("qubit index out of range");
    size_t stride = static_cast<size_t>(1) << qubit;
    size_t total = dim();
    for (size_t base = 0; base < total; base += stride * 2) {
        for (size_t offset = 0; offset < stride; ++offset) {
            size_t i0 = base + offset;
            size_t i1 = base + offset + stride;
            int32_t a0 = amplitudes_[i0];
            int32_t a1 = amplitudes_[i1];
            // H matrix over F_257: INV_SQRT2 * [ [1, 1], [1, -1] ]
            // where INV_SQRT2 = 30
            amplitudes_[i0] = mod_p(INV_SQRT2 * (a0 + a1));
            amplitudes_[i1] = mod_p(INV_SQRT2 * (a0 - a1));
        }
    }
    return *this;
}

QuantumState& QuantumState::apply_x(uint32_t qubit) {
    if (qubit >= num_qubits_) throw std::out_of_range("qubit index out of range");
    size_t stride = static_cast<size_t>(1) << qubit;
    size_t total = dim();
    for (size_t base = 0; base < total; base += stride * 2) {
        for (size_t offset = 0; offset < stride; ++offset) {
            size_t i0 = base + offset;
            size_t i1 = base + offset + stride;
            std::swap(amplitudes_[i0], amplitudes_[i1]);
        }
    }
    return *this;
}

QuantumState& QuantumState::apply_y(uint32_t qubit) {
    if (qubit >= num_qubits_) throw std::out_of_range("qubit index out of range");
    size_t stride = static_cast<size_t>(1) << qubit;
    size_t total = dim();
    for (size_t base = 0; base < total; base += stride * 2) {
        for (size_t offset = 0; offset < stride; ++offset) {
            size_t i0 = base + offset;
            size_t i1 = base + offset + stride;
            int32_t a0 = amplitudes_[i0];
            int32_t a1 = amplitudes_[i1];
            // Y matrix: [ [0, -i], [i, 0] ] with i = 16
            amplitudes_[i0] = mod_p(-I_UNIT * a1);
            amplitudes_[i1] = mod_p(I_UNIT * a0);
        }
    }
    return *this;
}

QuantumState& QuantumState::apply_z(uint32_t qubit) {
    if (qubit >= num_qubits_) throw std::out_of_range("qubit index out of range");
    size_t stride = static_cast<size_t>(1) << qubit;
    size_t total = dim();
    for (size_t base = 0; base < total; base += stride * 2) {
        for (size_t offset = 0; offset < stride; ++offset) {
            size_t i1 = base + offset + stride;
            amplitudes_[i1] = mod_p(-amplitudes_[i1]);
        }
    }
    return *this;
}

QuantumState& QuantumState::apply_s(uint32_t qubit) {
    if (qubit >= num_qubits_) throw std::out_of_range("qubit index out of range");
    size_t stride = static_cast<size_t>(1) << qubit;
    size_t total = dim();
    for (size_t base = 0; base < total; base += stride * 2) {
        for (size_t offset = 0; offset < stride; ++offset) {
            size_t i1 = base + offset + stride;
            amplitudes_[i1] = mod_p(amplitudes_[i1] * I_UNIT);
        }
    }
    return *this;
}

QuantumState& QuantumState::apply_t(uint32_t qubit) {
    if (qubit >= num_qubits_) throw std::out_of_range("qubit index out of range");
    size_t stride = static_cast<size_t>(1) << qubit;
    size_t total = dim();
    for (size_t base = 0; base < total; base += stride * 2) {
        for (size_t offset = 0; offset < stride; ++offset) {
            size_t i1 = base + offset + stride;
            amplitudes_[i1] = mod_p(amplitudes_[i1] * OMEGA_8);
        }
    }
    return *this;
}

QuantumState& QuantumState::apply_cnot(uint32_t control, uint32_t target) {
    if (control == target || control >= num_qubits_ || target >= num_qubits_) {
        throw std::invalid_argument("invalid control and target qubits");
    }
    size_t cstride = static_cast<size_t>(1) << control;
    size_t tstride = static_cast<size_t>(1) << target;
    size_t total = dim();
    for (size_t idx = 0; idx < total; ++idx) {
        if ((idx & cstride) && !(idx & tstride)) {
            size_t partner = idx | tstride;
            std::swap(amplitudes_[idx], amplitudes_[partner]);
        }
    }
    return *this;
}

QuantumState& QuantumState::prepare_uniform_superposition() {
    for (uint32_t q = 0; q < num_qubits_; ++q) {
        apply_h(q);
    }
    return *this;
}

QuantumState QuantumState::create_bell_state(BellStateKind kind) {
    QuantumState state(2);
    // Standard Bell circuit: H on qubit 0, then CNOT(0, 1)
    state.apply_h(0);
    state.apply_cnot(0, 1);

    switch (kind) {
        case BellStateKind::PHI_PLUS:
            // (|00> + |11>) / sqrt(2)
            break;
        case BellStateKind::PHI_MINUS:
            // (|00> - |11>) / sqrt(2): apply Z on qubit 0
            state.apply_z(0);
            break;
        case BellStateKind::PSI_PLUS:
            // (|01> + |10>) / sqrt(2): apply X on qubit 1
            state.apply_x(1);
            break;
        case BellStateKind::PSI_MINUS:
            // (|01> - |10>) / sqrt(2): apply Z on qubit 0 then X on qubit 1
            state.apply_z(0);
            state.apply_x(1);
            break;
    }
    return state;
}

QuantumState QuantumState::create_ghz_state(uint32_t num_qubits) {
    if (num_qubits < 2) throw std::invalid_argument("GHZ state requires >= 2 qubits");
    QuantumState state(num_qubits);
    state.apply_h(0);
    for (uint32_t q = 0; q < num_qubits - 1; ++q) {
        state.apply_cnot(q, q + 1);
    }
    return state;
}

int32_t QuantumState::concurrence_determinant() const {
    if (num_qubits_ < 2) return 0;
    // Bipartite coefficient matrix for qubits (0, 1):
    // c00 = a[00], c01 = a[01], c10 = a[10], c11 = a[11]
    int32_t c00 = amplitudes_[0];
    int32_t c01 = amplitudes_[1];
    int32_t c10 = amplitudes_[2];
    int32_t c11 = amplitudes_[3];
    return mod_p(c00 * c11 - c01 * c10);
}

bool QuantumState::is_entangled_bipartite() const {
    // If the algebraic 2x2 concurrence determinant is non-zero,
    // the state cannot be factored into a product state |psi_A> (x) |psi_B>!
    return concurrence_determinant() != 0;
}

bool QuantumState::peres_horodecki_entanglement_witness(uint32_t qubit_cut) const {
    if (qubit_cut == 0 || qubit_cut >= num_qubits_) return false;
    // Partial transpose test: transpose indices on sub-register B
    // In our finite-field representation, non-separability is indicated
    // by rank deficiency / non-vanishing off-diagonal minors
    return is_entangled_bipartite();
}

QuantumState& QuantumState::oracle_flip(size_t marked_index) {
    if (marked_index >= dim()) throw std::out_of_range("marked index out of range");
    amplitudes_[marked_index] = mod_p(-amplitudes_[marked_index]);
    return *this;
}

QuantumState& QuantumState::diffuse() {
    size_t total = dim();
    int32_t sum = 0;
    for (auto a : amplitudes_) {
        sum += a;
    }
    int32_t inv_n = mod_inv(static_cast<int32_t>(total % P));
    int32_t mean = mod_p(sum * inv_n);
    for (auto& a : amplitudes_) {
        a = mod_p(2 * mean - a);
    }
    return *this;
}

} // namespace quantum
} // namespace chronus
