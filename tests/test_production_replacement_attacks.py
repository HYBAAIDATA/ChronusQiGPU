"""Attack real replacement paths; injected faults are never product evidence."""

import json
from dataclasses import replace

import pytest

from test_resident_hendrix import GENESIS, issue
from chronus.resident_hendrix import ResidentHendrix, seal
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.adapters.base import DispatchError, BackendAbsent
from chronos_one_igpu.igpu.execution_identity import verify_receipt


@pytest.fixture
def actual_execution():
    target = (0xFFFF << (8 * (0x1D - 3))).to_bytes(32, "big")
    _, plan = issue(1, 2083236893, target=target)
    with OneIGPU() as gpu:
        receipt = gpu.execute_hendrix(
            plan.as_dict(), GENESIS, target, position=0, count=1
        )
        assert receipt["host_verified"] and receipt["sha256d_evaluations"] == 1
        assert verify_receipt(receipt, plan.as_dict(), igpu=gpu)
        yield gpu, plan, receipt


def test_positive_old_api_resolves_to_bound_replacement(actual_execution):
    _gpu, plan, r = actual_execution
    assert (
        r["requested_algorithm"]
        == r["planned_algorithm"]
        == r["executed_algorithm"]
        == "hendrix_coprime_stride"
    )
    assert (
        r["implementation_digest"]
        == plan.as_dict()["execution_contract"]["implementation_digest"]
    )
    assert r["implementation_module"] == "chronos_one_igpu.igpu.hendrix_execution"
    assert r["fallback_used"] is False and r["fallback_reason"] is None


@pytest.mark.parametrize(
    "replacement", ["disabled", "numerical", "heuristic", "simulation"]
)
def test_live_operator_substitution_fails_before_hashing(monkeypatch, replacement):
    from chronos_one_igpu.igpu.resident_hendrix import ResidentHendrix as Live
    from chronos_one_igpu.engine import ChronosEngine
    from chronos_one_igpu.golden_quantum import (
        MathematicalQuantumState,
        GoldenQuantumComputer,
    )

    _, plan = issue()
    variants = {
        "disabled": None,
        "numerical": ChronosEngine.evolve,
        "heuristic": GoldenQuantumComputer.prioritize,
        "simulation": MathematicalQuantumState.__init__,
    }
    monkeypatch.setattr(Live, "batch", variants[replacement])
    with OneIGPU() as gpu:
        with pytest.raises(DispatchError, match="substituted"):
            gpu.execute_hendrix(plan.as_dict(), GENESIS, bytes(32), count=1)
        assert gpu.fabric.mining_adapter is None


def _corrupt_certificate(plan, stage):
    from lucas.fold import t_phi_fold, t_phi_unfold

    value = plan.as_dict()
    g = value["geometry"]
    t = g["transport"]
    raw = t_phi_unfold(bytes.fromhex(t["folded_hex"]), t["original_bytes"])
    payload = json.loads(raw)
    if stage == "M32":
        payload["m32"][0]["numerator"][0][0] += 1
    elif stage == "11D":
        payload["frames_11d"][0]["numerator"][10][0] += 1
    elif stage == "H4":
        payload["cells"][0][0] = payload["cells"][0][1]
    else:
        payload["quantum"]["rank"][0] = payload["quantum"]["rank"][1]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    import hashlib

    t.update(
        original_bytes=len(raw),
        folded_hex=t_phi_fold(raw).hex(),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
    )
    g["precompute_digest"] = t["raw_sha256"]
    g["digest"] = seal({k: v for k, v in g.items() if k != "digest"})
    value.pop("digest")
    return ResidentHendrix.issue(value)


@pytest.mark.parametrize("stage", ["M32", "11D", "H4", "quantum_walk"])
def test_resealed_corrupt_certificate_cannot_execute(stage):
    _, plan = issue()
    corrupt = _corrupt_certificate(plan, stage)
    with OneIGPU() as gpu:
        with pytest.raises((ValueError, ArithmeticError)):
            gpu.execute_hendrix(corrupt.as_dict(), GENESIS, bytes(32), count=1)
        assert gpu.fabric.mining_adapter is None


def test_quantum_amplitude_mutation_is_detected_at_next_exact_step(monkeypatch):
    from chronus.mla1517.mining.pythia_search import (
        _load_coined_cycle_walk,
        _exact_hilbert_walk_rank,
    )

    cls = _load_coined_cycle_walk()
    original = cls.step

    def corrupted_step(self):
        original(self)
        self.register.amplitudes = {
            k: 2 * v for k, v in self.register.amplitudes.items()
        }

    monkeypatch.setattr(cls, "step", corrupted_step)
    with pytest.raises(ArithmeticError, match="Born mass"):
        _exact_hilbert_walk_rank()


@pytest.mark.parametrize(
    "field",
    [
        "requested_algorithm",
        "planned_algorithm",
        "executed_algorithm",
        "implementation_module",
        "implementation_digest",
        "execution_mode",
    ],
)
def test_resealed_receipt_identity_mutation_fails_replay(actual_execution, field):
    gpu, plan, receipt = actual_execution
    altered = dict(receipt)
    altered[field] = "substituted"
    altered.pop("receipt_digest")
    altered["receipt_digest"] = seal(altered)
    with pytest.raises(DispatchError, match="identity"):
        verify_receipt(altered, plan.as_dict(), igpu=gpu)


def test_falsified_candidate_rejected_by_independent_consensus_verifier(
    actual_execution,
):
    gpu, plan, receipt = actual_execution
    altered = dict(receipt)
    altered["digest"] = "00" * 32
    altered.pop("receipt_digest")
    altered["receipt_digest"] = seal(altered)
    with pytest.raises(DispatchError, match="consensus verification"):
        verify_receipt(altered, plan.as_dict(), igpu=gpu)


def test_missing_requested_executor_does_not_choose_generic_cpu_scheduler():
    from chronus.mla1517.mining.resident_router import ProductionExecutionRouter
    from chronus.one_igpu_mining import ChronusOneIGPUHasher
    from test_resident_hendrix import reference_scan

    p, _ = issue()
    h = ChronusOneIGPUHasher(OneIGPU())
    h.grind_target_hendrix_plan = None
    with pytest.raises(RuntimeError, match="UNAVAILABLE"):
        ProductionExecutionRouter(h, cpu_executor=reference_scan).execute_plan(
            p, GENESIS, bytes(32)
        )


def test_unsealed_plan_has_no_route_to_execution():
    from chronus.mla1517.mining.resident_router import ProductionExecutionRouter
    from chronus.one_igpu_mining import ChronusOneIGPUHasher
    from test_resident_hendrix import reference_scan

    p, _ = issue()
    refs = {k: v for k, v in p.evidence_refs.items() if k != "resident_hendrix"}
    record, candidate = ProductionExecutionRouter(
        ChronusOneIGPUHasher(OneIGPU()), cpu_executor=reference_scan
    ).execute_plan(replace(p, evidence_refs=refs), GENESIS, bytes(32))
    assert candidate is None and record.hash_count == 0
