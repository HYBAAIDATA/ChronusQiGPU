# l_hras/tests/test_all.py

import numpy as np
from l_hras.experimental.blueprint.substrate.phi_rotation import R_MATRIX, PHI_ELEMENT
from l_hras.experimental.blueprint.substrate.lucas import lucas, lucas_fast_doubling
from l_hras.experimental.blueprint.substrate.cassini import cassini
from l_hras.experimental.blueprint.substrate.pisot import is_pisot, pisot_decay
from l_hras.experimental.blueprint.fold.vector11d import Vector11D, DIM
from l_hras.experimental.blueprint.fold.klein import fold_11d, unfold_11d
from l_hras.experimental.blueprint.fold.zeckendorf import zeckendorf_encode, zeckendorf_decode
from l_hras.experimental.blueprint.fold.certificate import zeckendorf_certificate
from l_hras.experimental.blueprint.modules.oscillator import oscillator_lattice
from l_hras.experimental.blueprint.modules.cryostat import cryostat_temperature
from l_hras.experimental.blueprint.modules.cavity import superconducting_cavity
from l_hras.experimental.blueprint.modules.photonic import photonic_interconnect
from l_hras.experimental.blueprint.modules.anyonic import anyon_braid
from l_hras.experimental.blueprint.modules.metrology import quantum_metrology
from l_hras.experimental.blueprint.modules.qcd import lhc_qcd
from l_hras.experimental.blueprint.modules.control import real_time_control
from l_hras.experimental.blueprint.modules.error_correction import surface_code
from l_hras.experimental.blueprint.modules.chemistry import kohn_sham_1d

# ============================================================
# SUBSTRATE TESTS
# ============================================================

def test_phi_rotation():
    assert round(float(np.linalg.det(R_MATRIX))) == -1
    assert np.trace(R_MATRIX) == 1

def test_lucas():
    for n in range(20):
        assert lucas(n) == lucas_fast_doubling(n)

def test_cassini():
    for n in range(1, 20):
        assert cassini(n) == 5 * ((-1) ** (n + 1))

def test_pisot():
    assert is_pisot((1 + np.sqrt(5)) / 2, (1 - np.sqrt(5)) / 2)
    values = [pisot_decay(n) for n in range(1, 101)]
    assert all(a > b for a, b in zip(values, values[1:]))
    assert values[-1] < 1e-10

# ============================================================
# FOLD TESTS
# ============================================================

def test_fold_roundtrip():
    for _ in range(100):
        x = Vector11D(np.random.randn(DIM) * 0.5)
        y = fold_11d(x)
        x_back = unfold_11d(y)
        assert np.allclose(x.components, x_back.components, atol=1e-14)

def test_zeckendorf_roundtrip():
    for n in range(1000):
        assert zeckendorf_decode(zeckendorf_encode(n)) == n

def test_certificate():
    x = Vector11D(np.random.randn(DIM))
    cert = zeckendorf_certificate(x)
    assert cert.digest is not None
    assert len(cert.masks) == DIM

# ============================================================
# MODULE TESTS
# ============================================================

def test_oscillator():
    couplings = np.random.randn(5, 5)
    couplings = couplings @ couplings.T
    result = oscillator_lattice(couplings)
    assert len(result.frequencies) == 5

def test_cryostat():
    result = cryostat_temperature(1.0, 0.1)
    assert result.efficiency > 0
    assert result.efficiency < 1

def test_cavity():
    result = superconducting_cavity(4.2, 9.2)
    assert result.gap > 0
    assert result.Q_factor > 0

def test_photonic():
    couplings = np.random.randn(3, 3)
    result = photonic_interconnect(3, couplings, 1.0)
    assert result.propagator.shape == (3, 3)

def test_anyonic():
    result = anyon_braid(5)
    assert result.unitary
    assert result.yang_baxter

def test_metrology():
    state = np.array([1, 0], dtype=complex)
    generator = np.array([[0, 1], [1, 0]], dtype=complex)
    result = quantum_metrology(state, generator)
    assert result.fisher_information >= 0

def test_qcd():
    result = lhc_qcd(100.0, 1.0)
    assert result.alpha_s > 0
    assert result.debye_mass > 0

def test_control():
    A = np.array([[-1, 0], [0, -2]], dtype=float)
    B = np.array([[1], [1]], dtype=float)
    Q = np.eye(2)
    R = np.eye(1)
    result = real_time_control(A, B, Q, R)
    assert result.gain.shape == (1, 2)

def test_error_correction():
    result = surface_code(3)
    assert result.distance == 3
    assert len(result.stabilizers) > 0

def test_chemistry():
    result = kohn_sham_1d(n_electrons=2, n_grid=50, max_iter=10)
    assert result.energy is not None
    assert len(result.density) == 50
