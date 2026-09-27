"""Axiom-level seam: thermodynamics, Bennett checkpoints, signatures."""

from __future__ import annotations

from igpu.seam.axioms import AXIOMS
from igpu.seam.bennett import dispatch_reversible, pebble_bounds
from igpu.seam.signatures import signature_of
from igpu.seam.thermodynamics import (
    Technology,
    ThermoPolicy,
    advantage_factor,
    conventional_energy,
    landauer_bound,
    measure_thermodynamic,
)
from igpu.seam.types import KernelName, Ok


def test_axioms_are_named():
    assert set(AXIOMS) == {"A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"}


def test_t1_measurement_has_four_energy_components():
    m = measure_thermodynamic(Technology.adiabatic_cmos_2lal, KernelName.reversible_matmul_f4, 0, reversible=True)
    d = m.as_dict()
    for key in ("conventional_energy", "adiabatic_energy", "landauer_bound", "net_energy"):
        assert key in d
    assert m.uncomputation_savings >= 0.0


def test_a5_landauer_positive():
    assert landauer_bound(1) > 0.0
    assert landauer_bound(0) == 0.0


def test_a6_adiabatic_beats_conventional_when_slow():
    from igpu.seam.thermodynamics import adiabatic_energy

    conv = conventional_energy(1e-15, 0.8)
    slow = adiabatic_energy(1e-15, 0.8, 1e3, 1e-3)
    assert slow < conv
    assert advantage_factor(1e-3, 1e3, 1e-15) > 1.0


def test_k6_reversible_kernel_declares_inverse():
    sig = signature_of(KernelName.reversible_matmul_f4)
    assert sig.reversible is True
    assert sig.inverse is KernelName.reversible_matmul_f4
    assert sig.landauer_bits == 0
    assert sig.checkpoint_strategy is not None


def test_k6_hash_is_irreversible():
    sig = signature_of(KernelName.sha256d_scan)
    assert sig.reversible is False
    assert sig.inverse is None
    assert sig.landauer_bits >= 1


def test_k8_bennett_uncomputes_garbage():
    out = dispatch_reversible(KernelName.reversible_matmul_f4, [b"seed"], total_steps=16)
    assert isinstance(out, Ok)
    run = out.value
    assert run.garbage_uncomputed is True
    assert run.restored == b"seed"
    assert run.landauer_bits == len(run.live) * 8
    assert run.measurement is not None
    assert run.measurement.technology is Technology.cpu_reference


def test_bennett_pebble_bounds():
    space, time = pebble_bounds(4, 2)
    assert space == 2 * (4 - 1) + 1
    assert time == (2 * 4 - 1) ** 2


def test_thermo_policy_names_exist():
    assert ThermoPolicy.min_energy.value == "min_energy"
    assert ThermoPolicy.max_reversible.value == "max_reversible"
