#ifndef CHRONUS_C_API_H
#define CHRONUS_C_API_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32) || defined(__CYGWIN__)
  #ifdef CHRONUS_BUILD_DLL
    #define CHRONUS_EXPORT __declspec(dllexport)
  #else
    #define CHRONUS_EXPORT __declspec(dllimport)
  #endif
#else
  #define CHRONUS_EXPORT __attribute__((visibility("default")))
#endif

// Version and feature queries
CHRONUS_EXPORT const char* chronus_get_version(void);
CHRONUS_EXPORT int chronus_has_avx2(void);

// M15 SIMD fold and unfold
CHRONUS_EXPORT void chronus_m15_fold_pairs(const uint8_t* in, uint8_t* out, size_t num_pairs);
CHRONUS_EXPORT void chronus_m15_unfold_pairs(const uint8_t* in, uint8_t* out, size_t num_pairs);

// Dual space in-place query
CHRONUS_EXPORT uint32_t chronus_dual_space_query(const uint8_t* q, const uint8_t* folded_y, size_t num_pairs);
CHRONUS_EXPORT void chronus_dual_space_batch_query(
    const uint8_t* queries,
    size_t num_queries,
    const uint8_t* folded_y,
    size_t num_pairs,
    uint32_t* results
);

// Quantum superposition & statevector
CHRONUS_EXPORT void* chronus_quantum_state_create(uint32_t num_qubits);
CHRONUS_EXPORT void chronus_quantum_state_free(void* state_ptr);
CHRONUS_EXPORT void chronus_quantum_state_get_amplitudes(const void* state_ptr, int32_t* out_amps, size_t max_len);
CHRONUS_EXPORT void chronus_quantum_state_apply_gate(void* state_ptr, const char* gate_name, uint32_t qubit);
CHRONUS_EXPORT void chronus_quantum_state_apply_cnot(void* state_ptr, uint32_t control, uint32_t target);
CHRONUS_EXPORT void chronus_quantum_state_prepare_superposition(void* state_ptr);
CHRONUS_EXPORT void* chronus_quantum_create_bell_state(int kind); // 0: Phi+, 1: Phi-, 2: Psi+, 3: Psi-
CHRONUS_EXPORT void* chronus_quantum_create_ghz_state(uint32_t num_qubits);
CHRONUS_EXPORT int32_t chronus_quantum_concurrence_determinant(const void* state_ptr);
CHRONUS_EXPORT int chronus_quantum_is_entangled(const void* state_ptr);
CHRONUS_EXPORT void chronus_quantum_grover_iterate(void* state_ptr, size_t marked_index);

// Exact Z[phi] and Z[sigma_m]
CHRONUS_EXPORT void chronus_phi_multiply(int64_t a1, int64_t b1, int64_t a2, int64_t b2, int64_t* out_a, int64_t* out_b);
CHRONUS_EXPORT void chronus_phi_power(uint32_t order, int64_t* out_a, int64_t* out_b);
CHRONUS_EXPORT int64_t chronus_metallic_sequence(uint32_t m, uint32_t order);

#ifdef __cplusplus
}
#endif

#endif // CHRONUS_C_API_H
