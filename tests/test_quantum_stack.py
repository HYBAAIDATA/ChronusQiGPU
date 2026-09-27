"""Quantum stack wiring: the recovered HYBA signal layers must be live
wires through the registry, orchestrator guidance, and the integrated
cycle — and must never claim authority over consensus.
"""

from Intelligence.quantum_stack import (
    QuantumStack,
    THEOREM_PROVEN,
    WilsonNonceOrder,
    YMRegime,
    ConsciousnessState,
    compute_iit_phi,
    deterministic_seed,
    evaluate_qnp,
    phi_harmonic_score,
    prefilter_nonce_ranges,
)
from Intelligence.registry import build_default_registry


def test_stack_is_registered_and_instantiates():
    reg = build_default_registry()
    entry = reg.get("quantum_stack")
    assert entry is not None and entry.loaded, entry.error if entry else None
    inst = entry.instantiate()
    assert isinstance(inst, QuantumStack)


def test_assess_nonce_runs_all_four_layers():
    stack = QuantumStack()
    out = stack.assess_nonce(1517)
    assert 0.0 <= out["phi_score"] <= 1.0
    assert out["ym"]["regime"] in {r.value for r in YMRegime}
    assert out["iit_composite"]["state"] in {s.value for s in ConsciousnessState}
    assert 0.0 <= out["emergence_probability"] <= 1.0
    assert out["grover"]["realised"] is False  # hashing stays classical
    assert out["qnp"]["conditions_total"] >= 5
    assert THEOREM_PROVEN is False


def test_consciousness_ceiling_downgrades_state():
    """A raw state above the regime ceiling is a data integrity event:
    valid=False and the reported state is pinned to the ceiling."""
    out = compute_iit_phi(
        nonce=0xFFFFFFFF,
        phi_score=1.0,
        ym_regime=YMRegime.MASSLESS,
        field_strength=1.0,
    )
    # phi_iit is mathematically capped < 1.0 (transcendent is unreachable);
    # conscious under a massless regime still violates the ceiling.
    assert out["raw_state"] == "conscious"
    assert out["state"] == "dormant"
    assert out["valid"] is False


def test_wilson_order_is_deduplicated_permutation():
    gen = WilsonNonceOrder(topo_seed=1517)
    order = list(gen.order(1000))
    assert len(order) == len(set(order)) == 1000
    # The raw generator's duplicate collapse is reported, not hidden.
    assert gen.stats()["duplicates_skipped"] >= 0
    assert gen.emitted >= 1000


def test_schedule_bias_is_pure_permutation():
    stack = QuantumStack()
    schedule = list(range(0, 500, 7))
    biased = stack.schedule_bias(b"\x00" * 76, schedule)
    assert sorted(biased) == sorted(schedule)


def test_deterministic_seed_is_reproducible():
    a = deterministic_seed("job-1", 0x1D00FFFF)
    b = deterministic_seed("job-1", 0x1D00FFFF)
    c = deterministic_seed("job-2", 0x1D00FFFF)
    assert a == b and a != c
    assert len(a.transcript_hash) == 64
    ranges = prefilter_nonce_ranges(a.base_nonce, window=100, count=3)
    assert len(ranges) == 3 and all(s <= e for s, e in ranges)


def test_qnp_gate_requires_all_conditions():
    qnp = evaluate_qnp(
        phi_score=0.9,
        ym_regime=YMRegime.SUPERCRITICAL,
        consciousness_state=ConsciousnessState.TRANSCENDENT,
        emergence_prob=0.9,
        grover_speedup=5.0,
        ks_significant=True,
    )
    assert qnp["generated"] is True
    blocked = evaluate_qnp(
        phi_score=0.9,
        ym_regime=YMRegime.MASSLESS,
        consciousness_state=ConsciousnessState.DORMANT,
        emergence_prob=0.9,
        grover_speedup=5.0,
        ks_significant=True,
    )
    assert blocked["generated"] is False


def test_full_order_covers_whole_window_resonant_first():
    """The stack's primary ordering covers the full window (nothing
    skipped) and probes the highest-resonance nonces first."""
    stack = QuantumStack()
    order, stats = stack.full_order(b"\x02" * 76, 2000)
    assert sorted(order) == list(range(2000))  # full coverage, a permutation
    assert stats["resonant_fraction"] > 0.0
    # Descending phi-resonance: the head outranks the tail.
    assert phi_harmonic_score(order[0]) >= phi_harmonic_score(order[-1])
    # Generators are header-seeded: different headers, different orders.
    order2, _ = stack.full_order(b"\x03" * 76, 2000)
    assert order2 != order


def test_guide_mining_carries_quantum_stack_diagnostics():
    """guide_mining hands ordering authority to the stack and emits its
    telemetry on the real path."""
    from Intelligence.orchestrator import IntelligenceOrchestrator

    orch = IntelligenceOrchestrator()
    assert orch.quantum_stack is not None
    g = orch.guide_mining(b"\x01" * 76, b"\xff" * 32, nonce_window=500)
    qs = g.diagnostics.get("quantum_stack")
    assert qs is not None
    assert set(qs) >= {
        "head_phi_score", "ym_regime", "iit_composite_state",
        "emergence_probability", "qnp_generated", "ordering",
        "resonant_fraction",
    }
    assert qs["ordering"] == "wilson+phi_tiered"
    assert "quantum_stack_primary" in g.source
    assert len(g.nonce_schedule) == 500
    assert sorted(g.nonce_schedule) == list(range(500))


def test_integrated_cycle_calibrates_quantum_stack():
    """With a stack attached, the self-model Brier-scores it against
    real outcomes; without one the cycle is unchanged."""
    from Intelligence.intelligence_integration import IntegratedIntelligence
    from tests.test_intelligence_wiring import _stub_orchestrator

    stub = _stub_orchestrator()
    stub.quantum_stack = QuantumStack()
    res = IntegratedIntelligence(stub).run_cycle(
        header=b"\x00" * 80,
        target=b"\xff" * 32,
        block_context={"block_height": 1},
        mining_success=True,
    )
    assert "quantum_stack" in res.brier_scores
    assert res.quantum_emergence >= 0.0

    stub2 = _stub_orchestrator()  # no stack attached
    res2 = IntegratedIntelligence(stub2).run_cycle(
        header=b"\x00" * 80,
        target=b"\xff" * 32,
        block_context={"block_height": 1},
        mining_success=True,
    )
    assert set(res2.brier_scores) == {"toe", "meta_evolution", "pythia_learning"}
    assert res2.quantum_emergence == 0.0
