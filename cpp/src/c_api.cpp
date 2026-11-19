#define CHRONUS_BUILD_DLL
#include "chronus/c_api.h"
#include "chronus/igpu_simd.hpp"
#include "chronus/quantum_superposition.hpp"
#include "chronus/exact_lattice.hpp"

#include <cstring>
#include <new>

#ifndef CHRONUS_VERSION_STRING
#error "CHRONUS_VERSION_STRING must be defined by the build (cpp/CMakeLists.txt reads chronus.__version__)"
#endif

const char* chronus_get_version(void) {
    return CHRONUS_VERSION_STRING "-cpp-igpu";
}

int chronus_has_avx2(void) {
#if defined(__AVX2__)
    return 1;
#else
    return 0;
#endif
}

void chronus_m15_fold_pairs(const uint8_t* in, uint8_t* out, size_t num_pairs) {
    if (!in || !out || num_pairs == 0) return;
    chronus::igpu::fold_pairs_simd(in, out, num_pairs);
}

void chronus_m15_unfold_pairs(const uint8_t* in, uint8_t* out, size_t num_pairs) {
    if (!in || !out || num_pairs == 0) return;
    chronus::igpu::unfold_pairs_simd(in, out, num_pairs);
}

uint32_t chronus_dual_space_query(const uint8_t* q, const uint8_t* folded_y, size_t num_pairs) {
    if (!q || !folded_y || num_pairs == 0) return 0;
    return chronus::igpu::dual_space_dot_product(q, folded_y, num_pairs);
}

void chronus_dual_space_batch_query(
    const uint8_t* queries,
    size_t num_queries,
    const uint8_t* folded_y,
    size_t num_pairs,
    uint32_t* results
) {
    if (!queries || !folded_y || !results || num_queries == 0 || num_pairs == 0) return;
    chronus::igpu::dual_space_batch_query(queries, num_queries, folded_y, num_pairs, results);
}

void* chronus_quantum_state_create(uint32_t num_qubits) {
    try {
        return new chronus::quantum::QuantumState(num_qubits);
    } catch (...) {
        return nullptr;
    }
}

void chronus_quantum_state_free(void* state_ptr) {
    if (state_ptr) {
        delete static_cast<chronus::quantum::QuantumState*>(state_ptr);
    }
}

void chronus_quantum_state_get_amplitudes(const void* state_ptr, int32_t* out_amps, size_t max_len) {
    if (!state_ptr || !out_amps) return;
    const auto* state = static_cast<const chronus::quantum::QuantumState*>(state_ptr);
    const auto& amps = state->amplitudes();
    size_t to_copy = amps.size() < max_len ? amps.size() : max_len;
    std::memcpy(out_amps, amps.data(), to_copy * sizeof(int32_t));
}

void chronus_quantum_state_apply_gate(void* state_ptr, const char* gate_name, uint32_t qubit) {
    if (!state_ptr || !gate_name) return;
    auto* state = static_cast<chronus::quantum::QuantumState*>(state_ptr);
    if (std::strcmp(gate_name, "H") == 0) {
        state->apply_h(qubit);
    } else if (std::strcmp(gate_name, "X") == 0) {
        state->apply_x(qubit);
    } else if (std::strcmp(gate_name, "Y") == 0) {
        state->apply_y(qubit);
    } else if (std::strcmp(gate_name, "Z") == 0) {
        state->apply_z(qubit);
    } else if (std::strcmp(gate_name, "S") == 0) {
        state->apply_s(qubit);
    } else if (std::strcmp(gate_name, "T") == 0) {
        state->apply_t(qubit);
    }
}

void chronus_quantum_state_apply_cnot(void* state_ptr, uint32_t control, uint32_t target) {
    if (!state_ptr) return;
    auto* state = static_cast<chronus::quantum::QuantumState*>(state_ptr);
    try {
        state->apply_cnot(control, target);
    } catch (...) {}
}

void chronus_quantum_state_prepare_superposition(void* state_ptr) {
    if (!state_ptr) return;
    auto* state = static_cast<chronus::quantum::QuantumState*>(state_ptr);
    state->prepare_uniform_superposition();
}

void* chronus_quantum_create_bell_state(int kind) {
    try {
        auto bell_kind = static_cast<chronus::quantum::BellStateKind>(kind % 4);
        auto state = chronus::quantum::QuantumState::create_bell_state(bell_kind);
        return new chronus::quantum::QuantumState(std::move(state));
    } catch (...) {
        return nullptr;
    }
}

void* chronus_quantum_create_ghz_state(uint32_t num_qubits) {
    try {
        auto state = chronus::quantum::QuantumState::create_ghz_state(num_qubits);
        return new chronus::quantum::QuantumState(std::move(state));
    } catch (...) {
        return nullptr;
    }
}

int32_t chronus_quantum_concurrence_determinant(const void* state_ptr) {
    if (!state_ptr) return 0;
    const auto* state = static_cast<const chronus::quantum::QuantumState*>(state_ptr);
    return state->concurrence_determinant();
}

int chronus_quantum_is_entangled(const void* state_ptr) {
    if (!state_ptr) return 0;
    const auto* state = static_cast<const chronus::quantum::QuantumState*>(state_ptr);
    return state->is_entangled_bipartite() ? 1 : 0;
}

void chronus_quantum_grover_iterate(void* state_ptr, size_t marked_index) {
    if (!state_ptr) return;
    auto* state = static_cast<chronus::quantum::QuantumState*>(state_ptr);
    try {
        state->oracle_flip(marked_index);
        state->diffuse();
    } catch (...) {}
}

void chronus_phi_multiply(int64_t a1, int64_t b1, int64_t a2, int64_t b2, int64_t* out_a, int64_t* out_b) {
    if (!out_a || !out_b) return;
    chronus::lattice::PhiElementCpp p1{a1, b1};
    chronus::lattice::PhiElementCpp p2{a2, b2};
    auto res = p1.multiply(p2);
    *out_a = res.a;
    *out_b = res.b;
}

void chronus_phi_power(uint32_t order, int64_t* out_a, int64_t* out_b) {
    if (!out_a || !out_b) return;
    auto res = chronus::lattice::phi_power_cpp(order);
    *out_a = res.a;
    *out_b = res.b;
}

int64_t chronus_metallic_sequence(uint32_t m, uint32_t order) {
    return chronus::lattice::metallic_sequence_cpp(m, order);
}
