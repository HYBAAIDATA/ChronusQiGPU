"""GPU-engine adoption: real device binding + Lucas-rung scaling.

Two invariants this suite pins:

1. No silicon expectation — the engine enumerates the devices actually
   present (cloud-container CPU or the user's GPU); a CPU device is
   guaranteed, and no fabricated accelerator names appear in reports.
2. Lucas scaling — ``scale_index`` in {10, 12, 15, 18, 20} scales the
   search space by the exact Lucas value L_n; off-ladder rungs are
   rejected; Grover's k* is recomputed over the scaled space.
"""

import math
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TUQC = _ROOT / "turing_universal_quantum_computer"
if str(_TUQC) not in sys.path:
    sys.path.insert(0, str(_TUQC))

import turing_universal_quantum_computer.quantum_cuda as qc  # noqa: E402

from lucas.ladder import CURRICULUM_RUNGS, FULL_LADDER  # noqa: E402

HEADER = bytes(80)
TARGET_ALWAYS = b"\xff" * 32
TARGET_NEVER = bytes(32)


def _k_star(space: int) -> int:
    return max(1, int(math.floor(math.pi / 4.0 * math.sqrt(space))))


# -- honest device binding -------------------------------------------------


def test_devices_are_enumerated_not_fabricated():
    devices = qc.list_devices()
    assert devices, "a CPU device must always be present"
    for label in devices.values():
        # Real enumeration reports a "name [backend]" string — never the
        # old fabricated catalogue entries.
        assert not label.startswith(("Turing-Q5 iGPU", "M3 iGPU", "H100-class iGPU", "Docker "))
    assert qc.device_name(0) == devices[0]


def test_simulator_binds_a_real_device_and_reports_it():
    sim = qc.create_simulator(0)
    # ``backend`` is the compute path (cpu or native metal); the bound
    # device census is reported separately — binding a user's CUDA GPU
    # must not masquerade as CUDA compute.
    assert sim.backend in {"cpu", "metal"}
    stats = sim.stats()
    assert stats["bound_backend"] in {"cpu", "cuda", "rocm", "opencl", "metal"}
    assert sim.device_label.endswith(f"[{stats['bound_backend']}]")
    assert stats["device_name"] == sim.device_label


def test_out_of_range_device_id_binds_to_first_enumerated():
    sim = qc.create_simulator(9999)
    assert sim.device_label == qc.list_devices()[0]


# -- Lucas-rung scaling ----------------------------------------------------


def test_scale_rungs_match_full_ladder():
    assert tuple(FULL_LADDER)[: len(CURRICULUM_RUNGS)] == CURRICULUM_RUNGS
    assert tuple(qc.QUANTUM_SCALE_RUNGS) == tuple(FULL_LADDER)


def test_scaled_space_is_exact_lucas_multiple():
    from turing_core import lucas

    sim = qc.QuantumSimulator(0)
    for idx in FULL_LADDER:
        assert sim.scaled_space(64, idx) == min(64 * lucas(idx), qc._MAX_NONCE_SPACE)


def test_scaled_space_clamps_at_nonce_width():
    sim = qc.QuantumSimulator(0)
    assert sim.scaled_space(1 << 28, 20) == 1 << 32


def test_off_ladder_scale_index_rejected():
    for bad in (7, 11, 13, 17, 0, -10):
        with pytest.raises(ValueError):
            qc.QuantumSimulator(0, scale_index=bad)
        with pytest.raises(ValueError):
            qc.create_simulator(0).scaled_space(64, bad)


def test_env_scale_index_override(monkeypatch):
    monkeypatch.setenv("QUANTUM_CUDA_SCALE_INDEX", "18")
    sim = qc.create_simulator(0)
    assert sim.scale_index == 18
    assert sim.stats()["lucas_value"] == 5778


def test_set_scale_index_live():
    sim = qc.create_simulator(0)
    assert sim.scale_index == 10
    sim.set_scale_index(20)
    assert sim.scale_index == 20
    assert sim.stats()["lucas_value"] == 15127
    with pytest.raises(ValueError):
        sim.set_scale_index(11)


# -- scaled kernel submission -----------------------------------------------


def test_grover_probes_at_most_scaled_k_star():
    sim = qc.create_simulator(0, scale_index=10)
    sim.submit_kernel("", "grover_amplitude_amplification", 64, HEADER, TARGET_NEVER, -1)
    stats = sim.stats()
    scaled = 64 * 123
    assert stats["scaled_space"] == scaled
    assert stats["lucas_value"] == 123
    # k* over the scaled space bounds probing exactly.
    assert stats["nonces_searched"] <= _k_star(scaled) + 1


def test_grover_winner_is_a_nonce_in_the_scaled_window():
    sim = qc.create_simulator(0, scale_index=10)
    winner = sim.submit_kernel(
        "",
        "grover_amplitude_amplification",
        4,
        HEADER,
        TARGET_ALWAYS,
        -1,
        base_nonce=1000,
    )
    assert 1000 <= winner < 1000 + 4 * 123


def test_other_algorithms_sweep_the_scaled_space():
    sim = qc.create_simulator(0, scale_index=15)
    sim.submit_kernel("", "quantum_walk_search", 8, HEADER, TARGET_NEVER, -1)
    assert sim.stats()["nonces_searched"] == 8 * 1364


def test_unscaled_callers_keep_default_rung_10():
    sim = qc.create_simulator(0)
    sim.submit_kernel("", "grover_amplitude_amplification", 16, HEADER, TARGET_ALWAYS, -1)
    assert sim.stats()["scale_index"] == 10
    assert sim.stats()["scaled_space"] == 16 * 123


# -- downstream propagation -------------------------------------------------


def test_grover_style_search_scales_k_star():
    from mining.search import GroverStyleSearch

    r = GroverStyleSearch().search(
        header=HEADER,
        schedule=list(range(64)),
        target=(1 << 256) - 1,
        scale_index=12,
    )
    assert r["scale_index"] == 12
    assert r["lucas_value"] == 322
    assert r["scaled_space"] == 64 * 322
    assert r["grover_k_star"] == _k_star(64 * 322)


def test_grover_style_search_rejects_off_ladder():
    from mining.search import GroverStyleSearch

    with pytest.raises(ValueError):
        GroverStyleSearch().search(header=HEADER, schedule=[1], target=0, scale_index=13)


def test_gpu_route_scales_grover_depth():
    from hyba.virtual_gpu import SuperGPU

    g = SuperGPU.compose()
    d = g.route("grover_search", {"space": 1 << 20, "scale_index": 18})
    assert d.lucas_dispatch["grover_depth"] == _k_star((1 << 20) * 5778)
    assert d.lucas_dispatch["scale_index"] == 18
    assert d.lucas_dispatch["lucas_value"] == 5778
    assert d.lucas_dispatch["scaled_space"] == (1 << 20) * 5778
    with pytest.raises(ValueError):
        g.route("grover_search", {"space": 1 << 20, "scale_index": 7})


def test_emit_grover_iterate_forwards_scale_index():
    from hyba.math_ir.emit_cpu import emit_grover_iterate

    emit = emit_grover_iterate()
    out = emit(
        {"header": HEADER, "schedule": list(range(32)), "target": (1 << 256) - 1},
        {"lucas_dispatch": {"scale_index": 10}},
    )
    assert out["scale_index"] == 10
    assert out["scaled_space"] == 32 * 123


# -- registry adoption ------------------------------------------------------


def test_engine_is_registered_and_instantiates():
    from Intelligence.registry import build_default_registry

    entry = build_default_registry().get("quantum_cuda")
    assert entry is not None and entry.loaded, entry.error if entry else None
    inst = entry.instantiate()
    assert inst is not None
    assert inst.scale_index == 10
