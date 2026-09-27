"""The six couplings in Intelligence/intelligence_integration.py must be
live wires with observable effect, not decorative calls. A stub
orchestrator fires each coupling and the test asserts the downstream
state actually changed.
"""

from types import SimpleNamespace

import numpy as np

from Intelligence.intelligence_integration import IntegratedIntelligence


class _Recorder:
    def __init__(self):
        self.calls = []

    def add_concept(self, **kwargs):
        self.calls.append(kwargs)


def _stub_orchestrator(**over):
    meta = SimpleNamespace(
        mutation_rate=0.9,
        primitives={"lane_shift": SimpleNamespace(weight=0.1)},
        _toe_signal=None,
    )
    stub = SimpleNamespace(
        meta_evolution=meta,
        memory=SimpleNamespace(semantic=_Recorder()),
        pythia=SimpleNamespace(n=4),
        taught=[],
        toe_predict=lambda data: {
            "confidence": 0.9,
            "state_tomography": {"energy": 1.0},
            "trajectory_prediction": {"trend": "up"},
        },
        memory_status=lambda: {"curriculum": {"tasks_completed": 40}},
        pythia_status=lambda: {"emergence_signal": 0.8, "germ_line": 3},
        guide_mining=lambda *a, **k: SimpleNamespace(nonce_schedule=[0, 1, 2]),
        meta_evolve_schedule=lambda sched, generations=0: {
            "delta_phi": 0.4,
            "results": [{"phase_transition": True,
                         "discovered_primitive": "lane_shift"}],
        },
        meta_evolution_status=lambda: {
            "primitives": [{"name": "lane_shift", "avg_gain": 0.5}]},
        teach=lambda patterns, labels: stub.taught.append((patterns, labels)),
    )
    for k, v in over.items():
        setattr(stub, k, v)
    return stub


def test_all_six_couplings_have_observable_effect():
    orch = _stub_orchestrator()
    integ = IntegratedIntelligence(orch)
    weight_before = orch.meta_evolution.primitives["lane_shift"].weight
    rate_before = orch.meta_evolution.mutation_rate

    result = integ.run_cycle(
        header=b"\x00" * 80, target=b"\xff" * 32,
        block_context={"block_height": 1, "header_bytes": b"\x01"},
        mining_success=True,
    )

    # wire 1 TOE -> meta: mutation rate driven toward exploit, signal stored
    assert orch.meta_evolution.mutation_rate != rate_before
    assert orch.meta_evolution._toe_signal == [0.9, 1.0, 1.0]
    # wire 2 meta -> memory: the discovered primitive was written
    assert orch.memory.semantic.calls and (
        orch.memory.semantic.calls[0]["concept"] == "lane_shift")
    # wire 3 memory -> TOE: curriculum gating produced capabilities
    assert result.curriculum_capabilities
    # wire 4 pythia -> meta: emergence boosted the primitive weight
    assert orch.meta_evolution.primitives["lane_shift"].weight > weight_before
    # wire 5 pythia -> TOE: emergence prior changed the confidence
    assert result.toe_confidence_calibrated != result.toe_confidence_raw
    # wire 6 meta -> pythia: the phase transition was fed back as a reward
    assert orch.taught and orch.taught[0][1] == [True]
    # calibration tracked every subsystem against the real outcome
    assert set(result.brier_scores) == {
        "toe", "meta_evolution", "pythia_learning"}


def test_couplings_degrade_honestly_without_signals():
    """No discovered primitive -> no memory write; no emergence -> no
    weight boost; a low curriculum gates back to tomography only."""
    orch = _stub_orchestrator(
        pythia_status=lambda: {"emergence_signal": 0.0, "germ_line": 0},
        memory_status=lambda: {"curriculum": {"tasks_completed": 0}},
        meta_evolve_schedule=lambda sched, generations=0: {
            "delta_phi": 0.0,
            "results": [{"phase_transition": False,
                         "discovered_primitive": None}],
        },
    )
    integ = IntegratedIntelligence(orch)
    weight_before = orch.meta_evolution.primitives["lane_shift"].weight

    integ.run_cycle(
        header=b"\x00" * 80, target=b"\xff" * 32,
        block_context={"block_height": 1},
        mining_success=False,
    )

    assert orch.memory.semantic.calls == []
    assert orch.meta_evolution.primitives["lane_shift"].weight == weight_before
    assert orch.taught == []


def test_archival_memory_stays_folded_and_unfolds_byte_exact():
    """Four-tier memory foldedness: archival stores the T_phi-folded form
    (never raw bytes) and retrieval is the exact inverse."""
    import turing_core
    from Intelligence.pythia_memory import ArchivalMemory

    archival = ArchivalMemory()
    data = np.arange(6, dtype=float) * 1.25
    entry = archival.store(data)
    raw = np.ascontiguousarray(data, dtype=np.float64).tobytes()
    # The stored form is the exact M15 fold of the raw bytes — asserted by
    # comparing to the shared fold, not by assuming any particular shape.
    assert entry.folded_data == turing_core.t_phi_fold(raw)
    assert np.array_equal(archival.retrieve(entry.entry_id, len(data)), data)
