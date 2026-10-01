"""Φ-invariants: the build breaks if the algebra is wrong."""

from __future__ import annotations

from chronus.seam.types import KernelName
from phi_rotation.cassini import cassini_identity, det_power
from phi_rotation.functor import kernel_to_invariant
from phi_rotation.korobov import fibonacci_lattice, three_distance_gaps
from phi_rotation.lucas import lucas, lucas_is_trace
from phi_rotation.morton import morton_step, phi_expansion
from phi_rotation.pisot import PHI, PSI, is_pisot_phi
from phi_rotation.ring import check_phi1
from phi_rotation.rotation import R, rotate_n


def test_phi1_ring():
    c = check_phi1()
    assert c["phi_sq_is_phi_plus_one"] is True
    assert c["norm_phi"] == -1
    assert c["trace_phi"] == 1


def test_phi2_rotation():
    assert R.det() == -1
    assert R.trace() == 1
    assert rotate_n(0).det() == 1
    assert rotate_n(3).det() == (-1) ** 3


def test_phi3_lucas_trace():
    assert lucas(0) == 2 and lucas(1) == 1
    for n in range(0, 16):
        assert lucas_is_trace(n)


def test_phi3_cassini():
    for n in range(1, 16):
        assert cassini_identity(n)
        assert det_power(n) == (-1) ** n


def test_phi3_pisot():
    assert is_pisot_phi()
    assert PHI > 1 and abs(PSI) < 1


def test_phi3_morton_deterministic():
    assert morton_step((0.1, 0.2), 8) == morton_step((0.1, 0.2), 8)
    assert set(phi_expansion(1 / PHI, 12)) <= {0, 1}


def test_phi3_three_distance():
    assert three_distance_gaps(PHI - 1, 20) <= 3
    assert len(fibonacci_lattice(8)) >= 1


def test_phi4_functor_names_kernels():
    assert kernel_to_invariant(KernelName.lucas_wind) == "Lucas"
    assert kernel_to_invariant(KernelName.cassini_step) == "Cassini"
    assert kernel_to_invariant(KernelName.korobov_point) == "Korobov"
