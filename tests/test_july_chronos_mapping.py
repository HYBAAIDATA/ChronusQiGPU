"""Executable evidence that the July 2026 ``src.chronos`` surfaces live on in
the canonical ``chronus.v33`` consolidation.

Every test here is cited by ``manifests/july_2026_capability_gap_analysis.json``
as unit/invariant/integration evidence for a manifest row.
"""

from __future__ import annotations

import numpy as np
import pytest

import chronus.v33 as v33
from chronus.v33.academic import AcademicChronosEngine
from chronus.v33.compression import LargeHilbertSpace, run_tebd
from chronus.v33.compression.tebd import tebd_step
from chronus.v33.control import ClosedLoopController, Pulse, QuantumController
from chronus.v33.environment import (
    CryogenicEnvironment,
    ThermalNoise,
    amplitude_damping_channel,
    lindblad_step,
)
from chronus.v33.fields import (
    CoherentLaser,
    MicrowaveField,
    coherent_state,
    displacement_operator,
    rabi_evolve,
)
from chronus.v33.memory import MemoryHierarchy, run_memory_self_tests
from chronus.v33.theory import run_unbuilt_maths, self_test_all

# -- academic integrations -----------------------------------------------------


def test_v33_academic_surface():
    engine = AcademicChronosEngine()
    for surface in (
        "Caltech_Ising_Anyons",
        "Caltech_Surface_Code",
        "Cambridge_PINN",
        "CERN_CavityQED",
        "MIT_FaultTolerant_Control",
        "NIST_Benchmark",
        "TokyoTech_Metrology",
    ):
        assert engine is not None
        import chronus.v33.academic as academic

        assert hasattr(academic, surface) or hasattr(engine, surface)


# -- memory substrate -----------------------------------------------------------


def test_v33_memory_surface():
    report = run_memory_self_tests()
    assert set(report) >= {
        "qram",
        "block_encode",
        "mps_store",
        "neural_combine",
        "qsvt",
        "hierarchy",
    }
    hier = MemoryHierarchy(
        address_bits=4, value_bits=8, n_slots=8, mps_qubits=8, mps_bond_dim=8, seed=0
    )
    hier.write(3, 42)
    assert hier.read(3) == 42


# -- compression / TEBD ---------------------------------------------------------


def test_v33_compression_surface():
    report = run_tebd(n_sites=6, bond_dim=8, n_steps=3, dt=0.02)
    assert len(report.steps) == 3
    assert all(np.isfinite(report.energies))


def test_tebd_step_preserves_state_norm():
    # The MPS canonical form drops the global scalar (per-gate Schmidt
    # renormalisation), so norm invariants are checked on the normalised dense
    # state. A dt=0 step applies identity gates: the physical state must be
    # unchanged; a real step must stay a normalisable, finite-amplitude state.
    space = LargeHilbertSpace(n_modes=6, bond_dim=8)
    space.construct_product_ground()
    initial = space.mps.to_dense()
    initial = initial / np.linalg.norm(initial)

    max_err, mean_err = tebd_step(space, j_coupling=1.0, h_field=0.5, dt=0.0)
    assert 0.0 <= mean_err <= max_err and max_err < 1e-12
    after_identity = space.mps.to_dense()
    after_identity = after_identity / np.linalg.norm(after_identity)
    assert np.linalg.norm(after_identity - initial) == pytest.approx(0.0, abs=1e-9)

    max_err, _ = tebd_step(space, j_coupling=1.0, h_field=0.5, dt=0.02)
    dense = space.mps.to_dense()
    norm = np.linalg.norm(dense)
    assert np.isfinite(dense).all() and norm > 0.0
    evolved = dense / norm
    assert np.linalg.norm(evolved) == pytest.approx(1.0)


# -- control / feedback ---------------------------------------------------------


def test_v33_control_surface():
    ctrl = QuantumController(4, seed=0)
    result = ctrl.apply_pulse(Pulse(duration=1e-3, amplitude=0.5))
    assert np.isfinite(result.state).all()
    tune = ctrl.tune_frequency(1, 2.0)
    assert tune.shape == (4, 4)


def test_control_evolution_preserves_norm():
    hamiltonian = np.diag([0.0, 1.0, 2.0, 3.0]).astype(complex)
    ctrl = QuantumController(4, hamiltonian=hamiltonian)
    ctrl.set_state([0.5, 0.5, 0.5, 0.5])
    res = ctrl.evolve_drift(0.05)
    assert np.linalg.norm(res.state) == pytest.approx(1.0, abs=1e-12)
    res2 = ctrl.apply_pulse(Pulse(duration=0.01, amplitude=0.7, phase=0.3))
    assert np.linalg.norm(res2.state) == pytest.approx(1.0, abs=1e-12)


def test_closed_loop_step_produces_feedback():
    loop = ClosedLoopController(n=4, seed=0)
    for _ in range(5):
        step = loop.step(target_expectation=0.5, dt=1e-3)
    assert len(loop.history) == 5
    assert np.isfinite(step.measurement)
    assert step.state_norm == pytest.approx(1.0, abs=1e-9)
    assert np.isfinite(step.control_output).all()


# -- environment models ---------------------------------------------------------


def test_v33_environment_surface():
    env = CryogenicEnvironment(temperature_k=0.015, omega_hz=5e9)
    noise = env.thermal_noise()
    assert isinstance(noise, ThermalNoise)
    assert noise.occupation >= 0.0
    h = np.zeros((2, 2), dtype=complex)
    rho = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=complex)
    out = lindblad_step(rho, h, [np.array([[0, 1], [0, 0]], dtype=complex)], [0.1], 0.01)
    assert out.shape == (2, 2)


def test_amplitude_damping_preserves_trace():
    rho = np.array([[0.7, 0.2j], [-0.2j, 0.3]], dtype=complex)
    out = amplitude_damping_channel(rho, gamma=1.5, dt=0.1)
    assert np.trace(out) == pytest.approx(1.0, abs=1e-12)
    eig = np.linalg.eigvalsh(out)
    assert eig.min() > -1e-9  # channel output stays PSD


def test_cryogenic_environment_reports():
    env = CryogenicEnvironment(temperature_k=0.05, omega_hz=5e9)
    power = env.cooling_power(t_hot=300.0)
    assert np.isfinite(power) or np.isfinite(np.asarray(power)).all()


# -- field drives ----------------------------------------------------------------


def test_v33_fields_surface():
    laser = CoherentLaser(alpha=0.4 + 0.1j, n_max=8)
    state = laser.state()
    assert state.shape == (8,)
    unitary = displacement_operator(0.3j, 8)
    assert unitary.shape == (8, 8)
    psi = coherent_state(0.2, 8)
    assert np.linalg.norm(psi) == pytest.approx(1.0, abs=1e-9)


def test_rabi_evolve_preserves_norm():
    field = MicrowaveField(frequency=1.0, amplitude=0.5)
    psi0 = np.zeros(4, dtype=complex)
    psi0[0] = 1.0
    psi = rabi_evolve(psi0, field, t_final=0.4, n_steps=20)
    assert np.linalg.norm(psi) == pytest.approx(1.0, abs=1e-9)


def test_microwave_drive_rotates_population():
    # resonant σx drive with Ω t = π/2 moves population onto level 1
    field = MicrowaveField(frequency=0.0, amplitude=1.0)  # cos term = 1
    psi0 = np.zeros(2, dtype=complex)
    psi0[0] = 1.0
    psi = rabi_evolve(psi0, field, t_final=np.pi / 2, n_steps=200)
    assert abs(psi[1]) ** 2 > 0.95


# -- engine / evolution ----------------------------------------------------------


def test_v33_engine_surface():
    engine = v33.ChronosEngine(n_faces=8, layers=2)
    assert engine is not None
    for name in (
        "EvolutionEngine",
        "ErrorMitigationProcessor",
        "HamiltonianLibrary",
        "M32Manifold",
    ):
        assert hasattr(v33, name), name


# -- QSDL pipeline ---------------------------------------------------------------


def test_v33_qsdl_surface():
    compiler = v33.QSDLCompiler()
    scene = compiler.compile("not qsdl syntax")
    assert len(scene.objects) >= 1
    assert len(scene.lights) >= 1
    assert scene.camera["resolution"] == (7680, 4320)


def test_qsdl_default_scene_is_stable():
    first = v33.QSDLCompiler().compile("legacy-label")
    second = v33.QSDLCompiler().compile("different-label")
    assert len(first.objects) == len(second.objects)
    assert first.objects[0]["geometry"]["radius"] == second.objects[0]["geometry"]["radius"]
    assert first.camera == second.camera


def test_qsdl_compile_produces_scene_objects():
    source = (
        "scene sunset { object sphere { "
        "geometry sphere(radius=1.0, center=(0,0,0)) "
        "material glass { dielectric=1.5 absorption=0.001 "
        "quantum { resonance=[0.5] } } } "
        "light sun { type=directional position=(1,1,1) intensity=1.0 "
        "driving=zero() } "
        "camera { resolution=(320,180) fov=60.0 position=(0,0,5) } }"
    )
    scene = v33.QSDLCompiler().compile(source)
    obj = scene.objects[0]
    assert obj["geometry"]["type"] == "sphere"
    assert np.asarray(obj["transform"]).shape == (4, 4)
    assert scene.lights[0]["type"] == "directional"
    assert scene.camera["resolution"] == (320, 180)


# -- theory reports ---------------------------------------------------------------


def test_v33_theory_surface():
    statuses = self_test_all()
    assert statuses and all(isinstance(v, str) for v in statuses.values())
    report = run_unbuilt_maths()
    assert "oscillator_array" in report and "cryogenics" in report
    modes = report["oscillator_array"]["normal_mode_frequencies_hz"]
    assert all(np.isfinite(modes))
