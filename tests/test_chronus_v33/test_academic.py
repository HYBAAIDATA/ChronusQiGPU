# tests/test_academic.py -- academic enhancement modules (real math only).
from __future__ import annotations

import numpy as np
import pytest

from chronus.v33.academic.caltech import Caltech_Ising_Anyons, Caltech_Surface_Code, Caltech_Topological_Quantum
from chronus.v33.academic.cern import CERN_CavityQED, CERN_QFT_Enhancement, schwinger_critical_field
from chronus.v33.academic.mit import MIT_FaultTolerant_Control
from chronus.v33.academic.nist import NIST_Standards, NIST_Benchmark
from chronus.v33.academic.tensor_compression import MatrixProductState
from chronus.v33.academic.tokyotech import TokyoTech_Metrology
from chronus.v33.engine import ChronosEngine


@pytest.mark.unit
def test_ising_fusion_rules():
    anyons = Caltech_Ising_Anyons()
    assert anyons.fuse("sigma", "sigma") == ["1", "psi"]
    assert anyons.fuse("psi", "psi") == ["1"]
    assert anyons.fuse("1", "sigma") == ["sigma"]


@pytest.mark.unit
def test_braid_hadamard_matches_f_matrix():
    topo = Caltech_Topological_Quantum()
    H = topo.braid_hadamard()
    expected = (1 / np.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex)
    assert np.allclose(H, expected)


@pytest.mark.unit
def test_surface_code_decodes_single_error():
    code = Caltech_Surface_Code(distance=3)
    syndrome = code.measure_syndrome([4], "X")
    result = code.decode(syndrome, "X")
    assert result.logical_error is False
    assert (4, "X") in result.correction


@pytest.mark.unit
def test_cavity_qed_solves():
    cavity = CERN_CavityQED(fock_dim=3, n_atoms=1)
    result = cavity.solve()
    assert result.eigenvalues.ndim == 1
    assert np.all(np.isfinite(result.eigenvalues))
    # Ground energy should be the lowest eigenvalue.
    assert result.eigenvalues[0] == np.min(result.eigenvalues)


@pytest.mark.unit
def test_qed_corrections_finite():
    qft = CERN_QFT_Enhancement()
    corr = qft.corrections()
    assert corr["lamb_shift_hz"] > 0
    assert 0 < corr["anomalous_magnetic_moment"] < 0.01
    assert abs(schwinger_critical_field() - corr["schwinger_critical_field_v_per_m"]) < 1.0


@pytest.mark.unit
def test_kalman_pid_steps():
    ctrl = MIT_FaultTolerant_Control(state_dim=2, meas_dim=2)
    out = ctrl.step(np.array([0.1, -0.1]), target=np.array([1.0, 1.0]))
    assert out.shape == (2,)
    assert np.all(np.isfinite(out))


@pytest.mark.unit
def test_uhlmann_fidelity_self():
    std = NIST_Standards()
    v = np.array([1.0, 0.0, 0.0, 0.0], dtype=complex)
    rho = std.state_to_density_matrix(v)
    assert np.isclose(std.fidelity(rho, rho), 1.0)


@pytest.mark.unit
def test_metrology_formulas():
    m = TokyoTech_Metrology()
    assert np.isclose(m.squeezing_noise_reduction(10.0), 0.1)
    assert np.isclose(m.heisenberg_limit_improvement(1e4), 100.0)


@pytest.mark.unit
def test_mps_bell_state():
    mps = MatrixProductState(n_qubits=2, bond_dim=8)
    h = (1 / np.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex)
    cnot = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)
    mps.apply_single_qubit_gate(0, h)
    mps.apply_two_qubit_gate(0, cnot)
    # Bond index 1 is the cut between qubit 0 and qubit 1; Bell entropy = 1 bit.
    S = mps.entanglement_entropy(1)
    assert abs(S - 1.0) < 1e-10
    dense = mps.to_dense()
    expected = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
    # Global phase freedom.
    phase = np.exp(-1j * np.angle(dense[0] / expected[0])) if abs(dense[0]) > 1e-12 else 1.0
    assert np.allclose(dense * phase, expected, atol=1e-10)


@pytest.mark.unit
def test_mps_compression_audit_small():
    mps = MatrixProductState(n_qubits=10, bond_dim=8)
    audit = mps.audit_compression()
    assert audit.n_qubits == 10
    assert audit.dense_amplitude_count == 2 ** 10
    assert audit.mps_parameter_count > 0
    assert audit.compression_ratio == audit.dense_amplitude_count / audit.mps_parameter_count


@pytest.mark.integration
def test_nist_benchmark_determinism_score(smoke_scene_source):
    engine = ChronosEngine(n_faces=32, layers=2)

    def render_fn():
        return engine.render(smoke_scene_source)

    report = NIST_Benchmark().run_all(render_fn)
    assert report.scores["determinism_check"] == 1.0
    assert report.scores["quantum_volume"] >= 16
    assert report.scores["qft_roundtrip_error"] < 1e-10
    assert report.scores["qaoa_cost_reduction"] > 0.0
