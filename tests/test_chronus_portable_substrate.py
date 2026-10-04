import hashlib
import json
from pathlib import Path

import pytest

from chronus.virtual_igpu.abi import Workload, WorkloadKind
from chronus.virtual_igpu.capabilities import (
    DeviceLimits,
    KernelLimits,
    legal_local_size,
)
from chronus.virtual_igpu.evidence import EvidenceLedger
from chronus.virtual_igpu.optimizer import ActionClass, ClosedLoopOptimizer
from chronus.virtual_igpu.planner import (
    ChronusPlanner,
    CostVector,
    GeodesicRouter,
    lucas,
)


def evidence_record():
    return {
        "workload": {"id": "w", "tenant": "t", "operation": "fold"},
        "planner": {"plan_id": "p"},
        "substrate": {"adapter_id": "cpu"},
        "execution": {
            "status": "ok",
            "hardware_executed": False,
            "wall_time_ns": 10,
            "device_time_ns": None,
        },
        "validation": {"passed": True},
        "provenance": {"runtime": "test"},
    }


def test_device_and_compiled_kernel_limits_are_jointly_enforced():
    d = DeviceLimits(256, (256, 256, 64), 65536)
    k = KernelLimits(128, 16, 1024)
    assert legal_local_size((16, 8), d, k, 2048) == (16, 8)
    with pytest.raises(ValueError, match="work-group"):
        legal_local_size((16, 16), d, k)
    with pytest.raises(ValueError, match="local-memory"):
        legal_local_size((8, 8), d, k, 65000)


def test_evidence_ledger_is_durable_queryable_and_tamper_evident(tmp_path):
    ledger = EvidenceLedger(tmp_path, b"test-key")
    receipt = ledger.append(evidence_record())
    assert ledger.query(operation="fold")[0]["digest"] == receipt.digest
    assert hashlib.sha256(Path(receipt.path).read_bytes()).hexdigest() == receipt.digest
    assert ledger.get(receipt.digest)["validation"]["passed"] is True
    path = Path(receipt.path)
    value = json.loads(path.read_text())
    value["validation"]["passed"] = False
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="digest mismatch"):
        ledger.get(receipt.digest)


def test_geodesic_scheduler_uses_measured_cost():
    g = GeodesicRouter()
    g.connect("intent", "a", CostVector(latency=5))
    g.connect("intent", "b", CostVector(latency=1))
    g.connect("b", "a", CostVector(latency=1))
    assert g.shortest_path("intent", "a") == (("intent", "b", "a"), 2.0)


def test_lucas_planner_only_emits_advertised_legal_plans():
    w = Workload(id="w", kind=WorkloadKind.FOLD, input={"payload_utf8": "x"}, tenant="t")
    manifest = {
        "adapter_id": "cpu",
        "operations": ["fold"],
        "limits": {"legal_work_group_sizes": [1, 4], "max_batch_size": 100, "max_queue_depth": 4},
    }
    plans = ChronusPlanner().candidates(w, [manifest])
    assert plans and all(
        p.adapter_id == "cpu" and p.local_size[0] in {1, 4} and p.batch_size <= 100 for p in plans
    )
    assert lucas(plans[0].lucas_order) == plans[0].lucas_capacity


def test_optimizer_accepts_improvement_and_persists(tmp_path):
    applied = []
    rolled = []
    path = tmp_path / "learning.json"
    o = ClosedLoopOptimizer(path, minimum_samples=3, min_improvement=0.05, cooldown_trials=1)
    result = o.evaluate(
        context="matmul",
        candidate_id="b",
        action_class=ActionClass.BOUNDED_EXPERIMENT,
        baseline_samples=[10, 10, 10],
        candidate_samples=[8, 8, 8],
        apply=lambda: applied.append(1),
        rollback=lambda: rolled.append(1),
    )
    assert result.accepted and applied and not rolled
    assert ClosedLoopOptimizer(path).state["accepted"]["matmul"] == "b"


def test_optimizer_rolls_back_regression_and_enforces_cooldown(tmp_path):
    rolled = []
    o = ClosedLoopOptimizer(tmp_path / "learning.json", minimum_samples=2, cooldown_trials=1)
    result = o.evaluate(
        context="fold",
        candidate_id="bad",
        action_class=ActionClass.BOUNDED_EXPERIMENT,
        baseline_samples=[10, 10],
        candidate_samples=[12, 12],
        apply=lambda: None,
        rollback=lambda: rolled.append(1),
    )
    assert result.rollback and rolled
    with pytest.raises(RuntimeError, match="cooldown"):
        o.evaluate(
            context="fold",
            candidate_id="other",
            action_class=ActionClass.BOUNDED_EXPERIMENT,
            baseline_samples=[10, 10],
            candidate_samples=[8, 8],
            apply=lambda: None,
            rollback=lambda: None,
        )


def test_optimizer_denies_unapproved_and_forbidden_actions(tmp_path):
    o = ClosedLoopOptimizer(tmp_path / "learning.json", minimum_samples=1)
    for action in (ActionClass.REQUIRES_APPROVAL, ActionClass.FORBIDDEN):
        with pytest.raises(PermissionError):
            o.evaluate(
                context="x",
                candidate_id="x",
                action_class=action,
                baseline_samples=[1],
                candidate_samples=[0.5],
                apply=lambda: None,
                rollback=lambda: None,
            )
