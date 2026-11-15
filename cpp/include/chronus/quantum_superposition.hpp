#ifndef CHRONUS_QUANTUM_SUPERPOSITION_HPP
#define CHRONUS_QUANTUM_SUPERPOSITION_HPP

#include <cstdint>
#include <cstddef>
#include <vector>
#include <string>

namespace chronus {
namespace quantum {

constexpr int32_t P = 257;
constexpr int32_t SQRT2 = 60;
constexpr int32_t INV_SQRT2 = 30; // 30^2 = 900 = 3*257 + 129; 2*129 = 258 = 1 mod 257
constexpr int32_t I_UNIT = 16;     // 16^2 = 256 = -1 mod 257
constexpr int32_t OMEGA_8 = 4;     // 4^4 = 256 = -1 mod 257

inline int32_t mod_p(int32_t v) {
    int32_t r = v % P;
    return r < 0 ? r + P : r;
}

inline int32_t mod_inv(int32_t a) {
    a = mod_p(a);
    if (a <= 0) return 0;
    // Extended Euclidean Algorithm
    int32_t t = 0, newt = 1;
    int32_t r = P, newr = a;
    while (newr != 0) {
        int32_t quotient = r / newr;
        int32_t temp_t = t - quotient * newt;
        t = newt;
        newt = temp_t;
        int32_t temp_r = r - quotient * newr;
        r = newr;
        newr = temp_r;
    }
    if (r > 1) return 0; // Not invertible
    return mod_p(t);
}

enum class BellStateKind {
    PHI_PLUS,  // (|00> + |11>) / sqrt(2)
    PHI_MINUS, // (|00> - |11>) / sqrt(2)
    PSI_PLUS,  // (|01> + |10>) / sqrt(2)
    PSI_MINUS  // (|01> - |10>) / sqrt(2)
};

class QuantumState {
private:
    uint32_t num_qubits_;
    std::vector<int32_t> amplitudes_; // Size = 2^num_qubits_

public:
    explicit QuantumState(uint32_t num_qubits);
    QuantumState(uint32_t num_qubits, const std::vector<int32_t>& amps);

    uint32_t num_qubits() const { return num_qubits_; }
    size_t dim() const { return static_cast<size_t>(1) << num_qubits_; }
    const std::vector<int32_t>& amplitudes() const { return amplitudes_; }
    std::vector<int32_t>& amplitudes() { return amplitudes_; }

    // Gate operations over F_257
    QuantumState& apply_h(uint32_t qubit);
    QuantumState& apply_x(uint32_t qubit);
    QuantumState& apply_y(uint32_t qubit);
    QuantumState& apply_z(uint32_t qubit);
    QuantumState& apply_s(uint32_t qubit);
    QuantumState& apply_t(uint32_t qubit);
    QuantumState& apply_cnot(uint32_t control, uint32_t target);

    // Superposition preparation: apply H to all qubits
    QuantumState& prepare_uniform_superposition();

    // Entanglement generators
    static QuantumState create_bell_state(BellStateKind kind);
    static QuantumState create_ghz_state(uint32_t num_qubits);

    // Entanglement Witness & Algebraic Concurrence
    // For 2-qubit states, computes the determinant of the 2x2 coefficient matrix:
    // det(C) = (c00 * c11 - c01 * c10) mod 257.
    // Zero if and only if the state is a separable product state!
    int32_t concurrence_determinant() const;
    bool is_entangled_bipartite() const;

    // Multi-qubit partial transpose test across bipartite cut (qubit_cut)
    bool peres_horodecki_entanglement_witness(uint32_t qubit_cut) const;

    // Exact Grover Oracle & Inversion about Mean
    QuantumState& oracle_flip(size_t marked_index);
    QuantumState& diffuse();
};

} // namespace quantum
} // namespace chronus

#endif // CHRONUS_QUANTUM_SUPERPOSITION_HPP
