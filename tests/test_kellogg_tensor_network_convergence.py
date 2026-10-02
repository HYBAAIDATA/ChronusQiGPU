import zipfile

import numpy as np
import pytest

from kellogg import (
    CompressedQuantumState,
    CompressedTensorError,
    CompressionScheme,
    EngineConfig,
    HeisenbergHamiltonianMPO,
    IsingHamiltonianMPO,
    MatrixProductOperator,
    OperatorType,
    QuantumCompressedTensorEngine,
    QuantumOperator,
    TensorNetworkError,
    TensorTrain,
    hamiltonian_with_tensor_network,
    load_pv,
    mps_decompose,
    mps_reconstruct,
    natural_gradient_step,
    persistent_homology_comparison,
    quantum_fisher_metric,
    save_pv,
    topology_signature,
    tt_compress_with_budget,
    tt_decompose,
    tt_reconstruct,
    validate_pv,
)


def test_tensor_train_roundtrip_preserves_complex_dtype():
    rng = np.random.default_rng(7)
    tensor = rng.normal(size=(2, 3, 4)) + 1j * rng.normal(size=(2, 3, 4))
    train = TensorTrain(tensor, max_rank=64)
    np.testing.assert_allclose(train.reconstruct(), tensor, atol=1e-12)
    audit = train.audit(tensor)
    assert audit.ranks[0] == audit.ranks[-1] == 1
    assert audit.reconstruction_error < 1e-12
    assert "not physical" in audit.claim_boundary


def test_tt_compatibility_payload_and_error_budget():
    tensor = np.arange(24.0).reshape(2, 3, 4)
    payload = tt_decompose(tensor, max_rank=16)
    np.testing.assert_allclose(tt_reconstruct(payload), tensor, atol=1e-12)
    budgeted, error = tt_compress_with_budget(tensor, 1e-12, 16)
    np.testing.assert_allclose(tt_reconstruct(budgeted), tensor, atol=1e-12)
    assert error < 1e-12
    with pytest.raises(TensorNetworkError):
        tt_compress_with_budget(np.eye(8), 0.0, 1)


def test_mps_roundtrip_and_dimension_contract():
    rng = np.random.default_rng(9)
    state = rng.normal(size=16) + 1j * rng.normal(size=16)
    mps = mps_decompose(state, n_sites=4, chi=16)
    np.testing.assert_allclose(mps_reconstruct(mps), state, atol=1e-12)
    with pytest.raises(TensorNetworkError):
        mps_decompose(np.ones(15), n_sites=4, chi=4)


def test_mpo_identity_application_and_shape_failure():
    identity = np.eye(2).reshape(1, 2, 2, 1)
    operator = MatrixProductOperator([identity, identity])
    vector = np.arange(4.0)
    np.testing.assert_allclose(operator.apply_to_vector(vector), vector)
    assert operator.is_unitary()
    with pytest.raises(TensorNetworkError):
        operator.apply_to_vector(np.arange(3.0))


def test_hamiltonian_mpos_are_hermitian_and_keep_complex_terms():
    for operator in (IsingHamiltonianMPO(3), HeisenbergHamiltonianMPO(3)):
        matrix = operator.to_full_matrix()
        np.testing.assert_allclose(matrix, matrix.conj().T, atol=1e-12)
    heisenberg = HeisenbergHamiltonianMPO(2).to_full_matrix()
    assert np.iscomplexobj(heisenberg)


def test_hamiltonian_evolution_is_norm_preserving():
    hamiltonian = np.array([[0, 1], [1, 0]], dtype=complex)
    state = np.array([1, 0], dtype=complex)
    evolved, mps = hamiltonian_with_tensor_network(
        hamiltonian, state, n_sites=1, bond_dim=2, time=0.25
    )
    assert np.linalg.norm(evolved) == pytest.approx(1.0)
    np.testing.assert_allclose(mps_reconstruct(mps), evolved)


def test_topology_and_persistence_contracts():
    path = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    cycle = np.array([[0, 1, 1], [1, 0, 1], [1, 1, 0]])
    assert topology_signature(path) == (1, 0)
    assert topology_signature(cycle) == (1, 1)
    points = np.array([[0.0], [1.0], [2.0]])
    report = persistent_homology_comparison(points, points.copy(), max_epsilon=2, n_steps=4)
    assert report["topology_preserved"] is True


def test_quantum_fisher_uses_complex_modulus_and_step_normalizes():
    state = np.array([1.0, 0.0], dtype=complex)
    tangent = np.array([1j, 1.0], dtype=complex)
    assert quantum_fisher_metric(state, tangent) == pytest.approx(4.0)
    candidate = natural_gradient_step(
        state, np.array([[1.0, 0.0], [0.0, -1.0]]), eta=0.1
    )
    assert np.linalg.norm(candidate) == pytest.approx(1.0)


@pytest.fixture
def engine():
    return QuantumCompressedTensorEngine(
        EngineConfig(default_compression=CompressionScheme.TENSOR_TRAIN, default_max_rank=16)
    )


def test_compressed_tensor_schemes_roundtrip(engine):
    tensor = np.arange(16.0).reshape(2, 2, 2, 2)
    for scheme in (
        CompressionScheme.NONE,
        CompressionScheme.TENSOR_TRAIN,
        CompressionScheme.MPS,
    ):
        compressed = engine.load_tensor_from_host(tensor, scheme=scheme)
        np.testing.assert_allclose(
            engine.decompress_to_registers(compressed), tensor, atol=1e-12
        )
        assert compressed.metadata_dict()["claim_boundary"].startswith("representation")


def test_compressed_tensor_rejects_cross_owner_pulvini_custody(engine):
    with pytest.raises(CompressedTensorError, match="owned by Aethel"):
        engine.load_tensor_from_host(np.arange(8), scheme=CompressionScheme.PULVINI_FOLD)


def test_unitary_kraus_and_measurement_paths_preserve_density(engine):
    state = CompressedQuantumState(
        engine.load_tensor_from_host(np.array([1.0, 0.0], complex))
    )
    pauli_x = np.array([[0, 1], [1, 0]], complex)
    output = engine.apply_quantum_operator(
        state, QuantumOperator(OperatorType.UNITARY, kernel=pauli_x)
    )
    np.testing.assert_allclose(
        engine.decompress_to_registers(output.tensor), np.array([[0, 0], [0, 1]])
    )
    measurement = engine.measure_state(output, rng=np.random.default_rng(2))
    assert measurement.outcome == 1
    np.testing.assert_allclose(measurement.probabilities, [0, 1])
    bad = QuantumOperator(OperatorType.KRAUS, kraus_operators=[np.eye(2) * 0.5])
    with pytest.raises(CompressedTensorError, match="not trace preserving"):
        engine.apply_quantum_operator(state, bad)


def test_coherent_interference_preserves_phase(engine):
    zero = CompressedQuantumState(engine.load_tensor_from_host(np.array([1, 0], complex)))
    one = CompressedQuantumState(engine.load_tensor_from_host(np.array([0, 1], complex)))
    plus = engine.interfere_states([zero, one], [1, 1j])
    vector = engine.decompress_to_registers(plus.tensor)
    np.testing.assert_allclose(vector, np.array([1, 1j]) / np.sqrt(2), atol=1e-12)
    with pytest.raises(CompressedTensorError, match="eliminated"):
        engine.interfere_states([zero, zero], [1, -1])


def test_safe_authenticated_serialization_roundtrip(tmp_path, engine):
    tensor = engine.load_tensor_from_host(
        np.arange(24.0).reshape(2, 3, 4), scheme=CompressionScheme.TENSOR_TRAIN
    )
    path = tmp_path / "tensor.pv"
    save_pv(path, tensor, b"test-key")
    assert validate_pv(path, b"test-key")["authenticated"] is True
    restored = load_pv(path, b"test-key")
    np.testing.assert_allclose(
        engine.decompress_to_registers(restored), engine.decompress_to_registers(tensor)
    )
    with zipfile.ZipFile(path) as archive:
        assert "manifest.json" in archive.namelist()
    with pytest.raises(Exception):
        load_pv(path, b"wrong-key")
