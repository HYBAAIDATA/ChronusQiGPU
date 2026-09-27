"""Tests for the P-vs-NP memory model (illustrative, not a proof)."""

import numpy as np

from Intelligence.pvsnp_memory import (
    PVsNPMemoryProof,
    QuantumGPU,
    LucasQuantumMemory,
    UnlimitedQuantumStore,
)


def test_pvsnp_memory():
    proof = PVsNPMemoryProof()
    data = np.random.randn(2048)
    instance_id = proof.encode_instance(data)
    solution = proof.solve(instance_id)
    assert solution >= 0
    assert proof.verify(instance_id, solution)


def test_pvsnp_model_claims():
    proof = PVsNPMemoryProof()
    result = proof.prove_separation()
    assert result["separation"] is True
    assert result["equality_via_memory"] is True
    # Honesty gate: the model explicitly says it is not a proof.
    assert result["is_proof"] is False


def test_quantum_gpu_pvsnp():
    gpu = QuantumGPU()
    data = np.random.randn(2048)
    result = gpu.solve_pvsnp(data)
    assert "solution" in result
    assert result["verified"] is True


def test_quantum_gpu_telemetry():
    gpu = QuantumGPU()
    gpu.solve_pvsnp(np.random.randn(2048))
    tel = gpu.telemetry()
    assert tel["kernels_launched"] > 0
    assert tel["proof"]["separation"] is True


def test_lucas_memory_unlimited():
    mem = LucasQuantumMemory(max_lucas_index=31)
    for i in range(100):
        data = np.random.randn(256)
        addr = mem.allocate(data, lucas_index=i % 31)
        read_back = mem.read(addr)
        assert read_back is not None
    stats = mem.stats()
    assert stats["total_blocks"] == 100


def test_unlimited_quantum_store():
    store = UnlimitedQuantumStore(n_qubits=11)
    for i in range(10):
        amplitudes = np.random.randn(2048) + 1j * np.random.randn(2048)
        store.store_superposition(i, amplitudes)
    stats = store.stats()
    assert stats["stored_states"] == 10
