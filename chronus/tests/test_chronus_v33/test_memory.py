# tests/test_memory.py — Chronos GPU memory subsystem (mathematical, substrate-agnostic)
from __future__ import annotations

import numpy as np
import pytest

from chronus.v33.memory import (
    Table,
    QRAM,
    MPSStore,
    qsvt_from_block_enc,
    MemoryHierarchy,
    run_memory_self_tests,
)
from chronus.v33.engine import ChronosEngine


@pytest.mark.unit
def test_all_memory_self_tests():
    results = run_memory_self_tests()
    for name, msg in results.items():
        assert msg.endswith("PASS"), f"{name}: {msg}"


@pytest.mark.unit
def test_table_qram_roundtrip():
    t = Table.from_integers([3, 1, 4, 1], domain_bits=2, value_bits=3)
    q = QRAM(t)
    assert q.apply_basis(0, 0) == (0, 3)
    a, b = q.apply_basis(2, 0)
    a2, b2 = q.apply_basis(a, b)
    assert (a2, b2) == (2, 0)  # self-inverse


@pytest.mark.unit
def test_mps_ghz_compression():
    store = MPSStore(n_qubits=10, bond_dim=8)
    err = store.load_ghz()
    assert err == 0.0
    audit = store.audit()
    assert audit.is_compressed
    assert audit.compression_ratio > 10


@pytest.mark.unit
def test_qsvt_unitary():
    from chronus.v33.memory.block_encode import prepare_select
    X = np.array([[0, 1], [1, 0]], dtype=complex)
    Z = np.array([[1, 0], [0, -1]], dtype=complex)
    U, alpha = prepare_select(np.array([0.6, 0.4]), [X, Z], system_dim=2)
    from chronus.v33.memory.block_encode import BlockEnc
    be = BlockEnc(alpha=alpha, ancilla_bits=1, unitary=U, n_system=2)
    res = qsvt_from_block_enc(be, kind="chebyshev", degree=2)
    assert res.unitary is not None
    assert np.allclose(res.unitary.conj().T @ res.unitary, np.eye(res.unitary.shape[0]), atol=1e-6)


@pytest.mark.integration
def test_hierarchy_pipeline():
    hier = MemoryHierarchy(address_bits=6, value_bits=4, n_slots=4, mps_qubits=8, mps_bond_dim=8, seed=0)
    for i in range(16):
        hier.write(i, (i * 3) % 16)
    assert hier.read(5) == 15 % 16 or hier.read(5) == (5 * 3) % 16
    q = hier.qsvt(kind="chebyshev", degree=2, sparsity=2)
    assert q.unitary is not None
    rep = hier.report()
    assert rep.last_qsvt is not None


@pytest.mark.integration
def test_engine_spectral_preserves_energy(smoke_scene_source):
    eng = ChronosEngine(n_faces=32, layers=2)
    base = eng.render(smoke_scene_source)
    eng2 = ChronosEngine(n_faces=32, layers=2, enable_memory=True, memory_mps_qubits=8, memory_mps_bond_dim=8)
    spec = eng2.render_spectral(smoke_scene_source, qsvt_kind="chebyshev", qsvt_degree=2)
    assert abs(base.energy - spec.energy) < 1e-9
    assert spec.spectral_mode is True
    assert spec.qsvt_semantic is not None
    assert np.isclose(spec.distribution.sum(), 1.0)
