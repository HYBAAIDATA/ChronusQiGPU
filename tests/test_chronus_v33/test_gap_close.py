# tests/test_gap_close.py -- production tests for the five mathematical gaps.
from __future__ import annotations

import numpy as np
import pytest

from chronus.v33.emp import ErrorMitigationProcessor
from chronus.v33.evolution_engine import build_time_dependent_schedule
from chronus.v33.engine import ChronosEngine
from chronus.v33.hamiltonian import HamiltonianLibrary
from chronus.v33.weak_measurement import (
    WeakMeasurementSession,
    apply_weak_measurement,
    face_probe_observables,
    pure_state_to_density,
    uhlmann_fidelity,
    _self_test as wm_self_test,
)
from chronus.v33.emp import _self_test as emp_self_test
from chronus.v33.evolution_engine import _self_test as evo_self_test
from chronus.v33.hamiltonian import _self_test as ham_self_test


@pytest.mark.unit
def test_weak_measurement_self_test():
    assert wm_self_test() == "weak_measurement._self_test: PASS"


@pytest.mark.unit
def test_emp_self_test():
    assert emp_self_test() == "emp._self_test: PASS"


@pytest.mark.unit
def test_evolution_self_test():
    assert evo_self_test() == "evolution_engine._self_test: PASS"


@pytest.mark.unit
def test_hamiltonian_self_test():
    assert ham_self_test() == "hamiltonian._self_test: PASS"


@pytest.mark.unit
def test_weak_measurement_kraus_preserves_trace():
    n = 12
    psi = np.ones(n, dtype=complex) / np.sqrt(n)
    rho = pure_state_to_density(psi)
    o = face_probe_observables(n)[3]
    res = apply_weak_measurement(rho, o, epsilon=0.05)
    assert abs(np.trace(res.rho_after).real - 1.0) < 1e-10
    assert res.rho_after.shape == (n, n)


@pytest.mark.unit
def test_bayesian_inversion_high_fidelity_small_epsilon():
    n = 10
    psi = np.zeros(n, dtype=complex)
    psi[4] = 1.0
    session = WeakMeasurementSession.from_pure_state(psi, epsilon=0.005)
    probes = face_probe_observables(n)
    for i in (1, 4, 7):
        session.measure(probes[i], probe_id=i)
    rho_hat = session.compensate_observer_effect()
    fid = uhlmann_fidelity(pure_state_to_density(psi), rho_hat)
    assert fid > 0.99


@pytest.mark.unit
def test_emp_extrapolation_fills_unmeasured():
    n = 20
    psi = np.zeros(n, dtype=complex)
    psi[5] = 1.0
    emp = ErrorMitigationProcessor(n_faces=n, epsilon=0.01)
    budget = list(range(0, n, 3))
    report = emp.run_session(psi, probe_indices=budget)
    assert report.extrapolated_field.shape == (n,)
    assert abs(report.extrapolated_field.sum() - 1.0) < 1e-8
    assert int(np.argmax(report.compensated_distribution)) == 5


@pytest.mark.unit
def test_time_dependent_schedule_length():
    h = np.eye(4)
    sched = build_time_dependent_schedule(h, [(0.0, 1.0), (1.0, 2.0)], n_slices=8)
    assert len(sched) == 8
    total_dt = sum(dt for dt, _ in sched)
    assert abs(total_dt - 1.0) < 1e-12


@pytest.mark.unit
def test_scf_material_bridge_deterministic():
    lib = HamiltonianLibrary(n_faces=16)
    mat = {
        "dielectric": 1.5,
        "absorption": 0.001,
        "quantum_chemistry": True,
        "scf_grid_points": 120,
        "scf_max_iterations": 100,
    }
    objs = [{"geometry": {"radius": 1.0, "center": (0, 0, 0)}, "material": mat}]
    a = lib.build(objs, [])
    b = lib.build(objs, [])
    assert a.scf_energy is not None and np.isfinite(a.scf_energy)
    assert np.allclose(a.resonance_weights, b.resonance_weights)
    assert a.scf_energy == b.scf_energy
    assert a.resonance_weights.shape == (16,)


@pytest.mark.integration
def test_engine_emp_path_smoke(smoke_scene_source):
    engine = ChronosEngine(n_faces=32, layers=2, enable_emp=True, emp_readout_fraction=0.25)
    out = engine.render(smoke_scene_source)
    assert out.emp_enabled is True
    assert out.fidelity_to_ground is not None
    assert 0.0 <= out.fidelity_to_ground <= 1.0
    assert out.rendered_pixels_hit > 0
    assert np.isclose(out.distribution.sum(), 1.0)
    assert np.isfinite(out.energy)


@pytest.mark.integration
def test_engine_default_path_unchanged_energy(smoke_scene_source):
    """EMP-off path must remain the validated exact-ground-state baseline."""
    e1 = ChronosEngine(n_faces=32, layers=2, enable_emp=False)
    e2 = ChronosEngine(n_faces=32, layers=2, enable_emp=False)
    a = e1.render(smoke_scene_source)
    b = e2.render(smoke_scene_source)
    assert a.energy == b.energy
    assert a.emp_enabled is False
    assert a.fidelity_to_ground is None


@pytest.mark.integration
def test_engine_animation_keyframes_time_dependent():
    src = """
    scene anim {
        object sphere {
            geometry sphere(radius=1.0, center=(0,0,0))
            material glass { dielectric=1.5 absorption=0.001 quantum { resonance=[0.5] } }
            animate {
                property scale
                keyframes [ (0.0, 1.0), (1.0, 0.5), (2.0, 1.5) ]
            }
        }
        light sun { type=directional position=(1,1,1) intensity=1.0 driving=zero() }
        camera { resolution=(64,36) fov=60.0 position=(0,0,5) }
        quality { layers=2 evolution_steps=12 seed=0 }
    }
    """
    engine = ChronosEngine(n_faces=32, layers=2)
    out = engine.render(src)
    assert out.time_dependent is True
    assert np.isfinite(out.energy)
    assert out.rendered_pixels_hit > 0
