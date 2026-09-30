"""Owner C — deterministic-seam contract tests for pythagoras/.

tests/test_pythagoras.py covers the coarse behaviors; this file pins the
exact bookkeeping contracts it leaves open: operator_distribution
normalization, the mutation-rate clip bounds, the primitive-weight EMA
formula, discovery promotion edge cases (threshold boundaries, weight clip,
idempotence), export_state/load_state roundtrip, and the deterministic
phi-resonance diagnostics.
"""

from __future__ import annotations

import pytest

from pythagoras.auto_primitive import AutoPrimitiveDiscovery
from pythagoras.meta_evolution import MetaEvolutionController
from pythagoras.phi_resonance import PHI, PhiResonanceCalculator

# --- MetaEvolutionController --------------------------------------------------------


def test_mutation_rate_direction_and_clip():
    meta = MetaEvolutionController(initial_mutation_rate=0.15, stall_threshold=3)
    meta.update(generation=1, fitness_history=[0.5, 0.6], primitive_gains={})
    assert meta.mutation_rate == pytest.approx(0.15 * 0.95)
    meta.update(generation=2, fitness_history=[0.6, 0.6], primitive_gains={})
    assert meta.mutation_rate == pytest.approx(0.15 * 0.95 * 1.05)

    hot = MetaEvolutionController(initial_mutation_rate=0.49)
    for g in range(50):
        hot.update(generation=g, fitness_history=[0.0, 0.0], primitive_gains={})
    assert hot.mutation_rate == 0.50  # clipped

    cold = MetaEvolutionController(initial_mutation_rate=0.02)
    for g in range(200):
        cold.update(generation=g, fitness_history=[0.0, 0.1], primitive_gains={})
    assert cold.mutation_rate == pytest.approx(0.01)  # floored


def test_annealing_activates_at_stall_threshold_and_cools():
    meta = MetaEvolutionController(initial_temperature=0.5, cooling_rate=0.85, stall_threshold=3)
    for g in range(2):
        meta.update(generation=g, fitness_history=[1.0, 1.0], primitive_gains={})
    assert meta.stall_count == 2
    assert meta.in_annealing_mode is False
    meta.update(generation=2, fitness_history=[1.0, 1.0], primitive_gains={})
    assert meta.stall_count == 3
    assert meta.in_annealing_mode is True
    assert meta.temperature == pytest.approx(0.5 * 0.85)
    # Progress resets the stall and exits annealing.
    meta.update(generation=3, fitness_history=[1.0, 1.1], primitive_gains={})
    assert meta.stall_count == 0 and meta.in_annealing_mode is False


def test_should_accept_deterministic_boundaries():
    meta = MetaEvolutionController()
    assert meta.should_accept(0.0) is True  # non-negative always accepted
    assert meta.should_accept(1e-9) is True
    assert meta.should_accept(-0.5) is False  # rejected outside annealing
    meta.in_annealing_mode = True
    meta.temperature = 1e-4
    # exp(-1.0 / 1e-4) ~ e^-10000 -> never accepted.
    assert all(meta.should_accept(-1.0) for _ in range(50)) is False


def test_primitive_weight_ema_and_operator_distribution():
    meta = MetaEvolutionController()
    meta.update(
        generation=0, fitness_history=[0.0, 0.1], primitive_gains={"op_a": 0.05, "op_b": 0.1}
    )
    # EMA: w = 0.9 * 0.5 + 0.1 * max(0, gain * 10)
    assert meta.primitive_weights["op_a"] == pytest.approx(0.9 * 0.5 + 0.1 * 0.5)
    assert meta.primitive_weights["op_b"] == pytest.approx(0.9 * 0.5 + 0.1 * 1.0)
    assert sum(meta.operator_distribution.values()) == pytest.approx(1.0)
    assert meta.operator_distribution["op_b"] > meta.operator_distribution["op_a"]
    # Negative gains are floored at zero inside the EMA.
    meta.update(generation=1, fitness_history=[0.1, 0.1], primitive_gains={"op_c": -0.5})
    assert meta.primitive_weights["op_c"] == pytest.approx(0.9 * 0.5)


def test_phase_transition_marks_triggering_primitive():
    meta = MetaEvolutionController(phase_transition_threshold=0.05)
    meta.update(
        generation=0, fitness_history=[0.0, 0.2], primitive_gains={"op_a": 0.01, "op_b": 0.09}
    )
    assert len(meta.phase_transitions) == 1
    pt = meta.phase_transitions[0]
    assert pt["triggering_primitive"] == "op_b"  # argmax gain
    assert pt["delta_phi"] == pytest.approx(0.2)
    flagged = [r for r in meta.provenance_log if r["is_phase_transition"]]
    assert [r["primitive"] for r in flagged] == ["op_b"]


def test_get_state_snapshot_honesty():
    meta = MetaEvolutionController()
    meta.update(generation=0, fitness_history=[0.0, 0.1], primitive_gains={"p": 0.2})
    state = meta.get_state()
    assert state["mutation_rate"] == meta.mutation_rate
    assert state["stall_count"] == meta.stall_count
    assert state["in_annealing_mode"] == meta.in_annealing_mode
    assert state["phase_transition_count"] == len(meta.phase_transitions)
    state["primitive_weights"]["p"] = -1.0  # snapshot is a copy
    assert meta.primitive_weights["p"] != -1.0


# --- AutoPrimitiveDiscovery -----------------------------------------------------------


def test_discovery_threshold_edges():
    d = AutoPrimitiveDiscovery(gain_threshold=0.05, consistency_threshold=3)
    for _ in range(2):  # below consistency threshold
        d.observe("pat_low_count", 0.9)
    assert d.discover() == []

    for _ in range(3):
        d.observe("pat_low_gain", 0.04)  # below gain threshold
    assert d.discover() == []

    for _ in range(3):
        d.observe("pat_ok", 0.06)
    (prim,) = d.discover()
    assert prim["name"] == "pat_ok"
    assert prim["n_observations"] == 3
    assert prim["avg_gain"] == pytest.approx(0.06)
    assert prim["weight"] == pytest.approx(min(1.0, max(0.1, 0.06 * 10.0)))
    assert prim["variance"] == pytest.approx(0.0)
    # Promotion is idempotent — a second sweep emits nothing new.
    assert d.discover() == []


def test_discovery_weight_clip_and_variance():
    d = AutoPrimitiveDiscovery(gain_threshold=0.01, consistency_threshold=2)
    for g in (0.05, 0.09):
        d.observe("big", g)  # avg 0.07 -> weight clipped to 0.7
    d.discover()
    prim = d.get_discovered()["big"]
    assert prim["weight"] == pytest.approx(0.7)
    assert prim["variance"] == pytest.approx(0.0004)


def test_discovery_export_load_state_roundtrip():
    d = AutoPrimitiveDiscovery(gain_threshold=0.01, consistency_threshold=1)
    d.observe("p1", 0.2)
    d.observe("p2", 0.3)
    d.discover()
    snapshot = d.export_state()

    restored = AutoPrimitiveDiscovery()
    restored.load_state(snapshot)
    assert restored.patterns == d.patterns
    assert restored.get_discovered() == d.get_discovered()
    assert restored.discovery_history == d.discovery_history
    # Restored state keeps promoting honestly (already discovered -> skipped).
    assert restored.discover() == []


# --- PhiResonanceCalculator ------------------------------------------------------------


_SIMPLE = "x = 1\n"
_NESTED = """
def outer():
    def inner():
        for i in range(10):
            if i:
                while True:
                    break
    return inner
"""


def test_compute_deterministic_bounded_and_syntax_safe():
    calc = PhiResonanceCalculator()
    s1, s2 = calc.compute(_NESTED), calc.compute(_NESTED)
    assert s1 == s2
    assert 0.0 <= s1 <= 1.0
    assert calc.compute("def broken(:\n") == 0.0
    assert calc.compute_components("def broken(:\n")["composite"] == 0.0


def test_compute_components_composite_is_mean():
    calc = PhiResonanceCalculator()
    c = calc.compute_components(_NESTED)
    assert c["composite"] == pytest.approx(
        (c["abstraction"] + c["depth_balance"] + c["density"]) / 3.0
    )


def test_component_boundary_values():
    calc = PhiResonanceCalculator()
    # No declarations and no control flow -> both components report 0.5.
    c = calc.compute_components(_SIMPLE)
    assert c["abstraction"] == 0.5
    assert c["depth_balance"] == 0.5
    # A single declaration is perfectly consistent.
    assert calc.compute_components("def f():\n    pass\n")["abstraction"] == 1.0
    # Perfectly nested control flow at golden-ratio depth: min/max == 0? Use
    # is_resonant as the only phi-threshold statement the module makes.
    assert calc.is_resonant(_NESTED) == (calc.compute(_NESTED) >= calc.phi_target)


def test_diagnose_manifold_deterministic_and_structured():
    calc = PhiResonanceCalculator()
    d1 = calc.diagnose_manifold(_NESTED)
    d2 = calc.diagnose_manifold(_NESTED)
    assert d1 == d2  # fully deterministic
    assert d1["base_phi"] == pytest.approx(calc.compute(_NESTED))
    assert isinstance(d1["perturbation_deltas"], list)
    assert len(d1["perturbation_deltas"]) >= 2
    assert d1["max_abs_gradient"] == max(abs(x) for x in d1["perturbation_deltas"])
    assert d1["is_degenerate_manifold"] is (d1["max_abs_gradient"] < 1e-5)
    assert d1["recommended_escape"] in (
        "non_local_restructure (function_split_refactor / simulated_annealing)",
        "gradient_following_cgp",
    )
    # A source with no function gets only perturbations 1 and 3.
    flat = calc.diagnose_manifold(_SIMPLE)
    assert len(flat["perturbation_deltas"]) == 2


def test_phi_constant_is_golden_conjugate():
    assert PHI == pytest.approx((5**0.5 - 1.0) / 2.0)
    assert PHI == pytest.approx(0.6180339887498949)
