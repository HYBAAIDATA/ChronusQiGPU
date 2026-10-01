import numpy as np
import pytest

import chronus
from chronus.gpu_capabilities import (
    BufferIntegrityGate,
    ChronusTensorPipeline,
    GPUCapabilityError,
    TensorInvariantVerifier,
    gpu_capability_status,
    memory_hierarchy_from_topology,
    probe_opencl_topology,
    reference_gpu_topology,
)
from kellogg import (
    CompressionScheme,
    EngineConfig,
    MatrixProductOperator,
    QuantumCompressedTensorEngine,
)


class MockOpenCLDevice:
    name = "Mock Integrated GPU"
    vendor = "HYBA"
    max_compute_units = 32
    max_clock_frequency = 1450
    global_mem_size = 8 << 30
    local_mem_size = 64 << 10
    max_work_group_size = 256
    host_unified_memory = True


def test_gpu_capability_closure_matrix_is_complete():
    status = gpu_capability_status()
    assert set(status) == {
        "geodesic_scheduling",
        "memory_hierarchy",
        "gpu_topology_specs",
        "integrity_gates",
        "tensor_network_decomposition",
        "mps_tt_mpo",
        "compression",
        "serialization",
        "invariant_verification",
    }
    assert all(record["status"] for record in status.values())


def test_opencl_topology_captures_only_reported_facts():
    topology = probe_opencl_topology(MockOpenCLDevice(), platform_name="mock")
    assert topology.compute_units == 32
    assert topology.clock_mhz == 1450
    assert topology.global_memory_bytes == 8 << 30
    assert topology.host_unified_memory is True
    assert topology.tensor_cores is None
    assert topology.pcie_bandwidth_bytes_per_second is None
    assert topology.nvlink_bandwidth_bytes_per_second is None


def test_historical_reference_is_not_reported_as_measurement():
    topology = reference_gpu_topology("h100")
    assert topology.truth_class == "historical_public_reference"
    assert topology.measured_by_chronus is False
    assert topology.global_memory_bytes == 80_000_000_000
    assert topology.nvlink_bandwidth_bytes_per_second == pytest.approx(0.9e12)


def test_memory_hierarchy_preserves_unknown_levels_as_null():
    topology = probe_opencl_topology(MockOpenCLDevice())
    hierarchy = memory_hierarchy_from_topology(topology)
    by_name = {level.name: level for level in hierarchy.levels}
    assert by_name["global"].capacity_bytes == 8 << 30
    assert by_name["local_shared"].capacity_bytes == 64 << 10
    assert by_name["l2"].capacity_bytes is None
    assert by_name["registers"].capacity_bytes is None
    assert hierarchy.measured is True


def test_buffer_integrity_gate_detects_tamper_and_replay():
    original = np.arange(32, dtype=np.float32)
    gate = BufferIntegrityGate(b"test-key")
    attestation = gate.attest(original, device_fingerprint="device")
    tampered = original.copy()
    tampered[-1] += 1
    with pytest.raises(GPUCapabilityError, match="digest mismatch"):
        gate.verify(tampered, attestation)
    assert gate.verify(original, attestation)
    with pytest.raises(GPUCapabilityError, match="replayed or reordered"):
        gate.verify(original, attestation)


def test_buffer_integrity_gate_binds_shape_and_dtype():
    original = np.arange(8, dtype=np.int32)
    gate = BufferIntegrityGate()
    attestation = gate.attest(original)
    with pytest.raises(GPUCapabilityError):
        gate.verify(original.reshape(2, 4), attestation)


def test_chronus_pipeline_delegates_tt_and_mps_math_to_kellogg():
    pipeline = ChronusTensorPipeline()
    tensor = np.arange(24.0).reshape(2, 3, 4)
    train = pipeline.decompose(tensor, "tt", max_rank=16)
    np.testing.assert_allclose(train.reconstruct(), tensor)
    state = np.arange(16.0)
    mps = pipeline.decompose(state, "mps", max_rank=16)
    assert len(mps) == 4
    with pytest.raises(GPUCapabilityError, match="power-of-two"):
        pipeline.decompose(np.arange(15.0), "mps")


def test_chronus_pipeline_applies_mpo_with_explicit_host_evidence():
    identity = np.eye(2).reshape(1, 2, 2, 1)
    operator = MatrixProductOperator([identity, identity])
    vector = np.arange(4.0)
    output, evidence = ChronusTensorPipeline().apply_mpo(operator, vector)
    np.testing.assert_allclose(output, vector)
    assert evidence.backend == "kellogg-host"
    assert evidence.hardware_executed is False
    assert evidence.verified_against_kellogg is True


def test_invariant_verifier_reports_norm_canonicality_and_entropy():
    pipeline = ChronusTensorPipeline()
    bell = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
    mps = pipeline.decompose(bell, "mps", max_rank=4)
    report = pipeline.verify_network(mps, require_normalized=True)
    assert report.passed
    assert report.normalized
    assert report.left_canonical_approx
    assert report.entanglement_entropy_bits == pytest.approx(1.0)


def test_invariant_verifier_rejects_broken_bond():
    verifier = TensorInvariantVerifier()
    left = np.ones((1, 2, 2))
    right = np.ones((3, 2, 1))
    report = verifier.verify_cores([left, right])
    assert not report.bond_dimensions_valid
    assert not report.passed


def test_pipeline_uses_safe_kellogg_serialization(tmp_path):
    engine = QuantumCompressedTensorEngine(
        EngineConfig(default_compression=CompressionScheme.TENSOR_TRAIN)
    )
    compressed = engine.load_tensor_from_host(np.arange(16.0).reshape(4, 4))
    pipeline = ChronusTensorPipeline()
    path = tmp_path / "transfer.pv"
    pipeline.serialize(path, compressed, authentication_key=b"transfer-key")
    restored = pipeline.deserialize(path, authentication_key=b"transfer-key")
    np.testing.assert_allclose(
        engine.decompress_to_registers(restored),
        engine.decompress_to_registers(compressed),
    )


def test_chronus_public_surface_is_lazy_and_complete():
    assert chronus.BufferIntegrityGate is BufferIntegrityGate
    assert chronus.ChronusTensorPipeline is ChronusTensorPipeline
    assert callable(chronus.reference_gpu_topology)
