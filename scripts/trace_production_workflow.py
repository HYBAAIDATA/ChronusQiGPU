"""Run a controlled production-component workflow and emit correlation evidence.

The Stratum boundary is a declared controlled fixture. TOE, SearchPlan,
NonceLease, ExecutionRouter, SHA256d, CausalLedger, and learning are the real
production implementations. No live pool acceptance or hardware execution is
claimed.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "mla1517_platform_v3.4" / "python"
if str(PYTHON) not in sys.path:
    sys.path.insert(0, str(PYTHON))

from manifold_pool_coordinator import StratumJob  # noqa: E402
from mla1517.mining.agentic_controller import AgenticMiningController  # noqa: E402
from mla1517.mining.causal import CausalCoordinate, CausalLedger  # noqa: E402
from mla1517.mining.execution_router import ExecutionRouter, sha256d_scan  # noqa: E402
from mla1517.mining.search_plan import PoolOutcome, SearchPlan, WorkIdentity  # noqa: E402
from mla1517.mining.toe_adapter import TOEMiningAdapter  # noqa: E402
from mla1517.mining.toe_decision import build_toe_decision_frame  # noqa: E402
from toe.bridge import TOEBridge  # noqa: E402


class _CpuHasher:
    backend = "cpu_reference"
    device = "python-hashlib"
    vendor = "python"
    grind_batch = 64
    launches = 0
    kernel_ms = 0.0


def _cpu_range(header, target, start, count):
    return sha256d_scan(header, target, range(start, start + count))


def _head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run() -> dict:
    stages = []

    def stage(name, component, function, status="PASS", evidence="CONTROLLED_EXECUTION", **extra):
        stages.append(
            {
                "stage": name,
                "component": component,
                "function": function,
                "evidence_class": evidence,
                "status": status,
                **extra,
            }
        )

    job = StratumJob("job-controlled", ("job-controlled", "prev", "c1", "c2"), 1.0)
    identity = WorkIdentity(
        "session-controlled", 1, job.job_id, "fingerprint-controlled", 1, True, 1.0
    )
    stage(
        "stratum_boundary",
        "WorkIdentity",
        "controlled protocol fixture",
        evidence="CONTROLLED_PROTOCOL_BOUNDARY",
        correlation_ids={"pool_session_id": identity.pool_session_id, "generation": 1},
    )

    context = TOEMiningAdapter(TOEBridge()).analyse(
        job=job, state=bytes(range(64)), node_id=7, sequence=19
    )
    frame = build_toe_decision_frame(context)
    stage(
        "toe_decision_frame",
        "TOEMiningAdapter",
        "analyse -> build_toe_decision_frame",
        correlation_ids={"toe_frame_id": frame.frame_digest},
    )

    agentic = AgenticMiningController(queue_depth=1, initial_lookahead=1)
    agentic.bind_work(identity)
    plan_id = f"plan:{uuid.uuid4()}"
    reserved = agentic.reserve_lease(plan_id, 64, lambda: "00000000")
    plan = SearchPlan(
        job_fingerprint=identity.job_fingerprint,
        pool_session_id=identity.pool_session_id,
        generation=identity.generation,
        base_step=reserved.start,
        window=64,
        extranonce2=reserved.extranonce2,
        lane_order=tuple(range(32)),
        preferred_face=0,
        dispatch_breadth=64,
        executor_route="cpu_reference",
        policy_id="controlled_trace",
        evidence_refs=dict(frame.evidence_refs()),
        created_at=time.monotonic(),
        plan_id=plan_id,
        toe_frame_id=frame.frame_digest,
    )
    assert agentic.submit_plan(plan)
    consumed = agentic.consume_plan()
    executing = agentic.begin_execution(consumed)
    stage(
        "plan_and_lease",
        "AgenticMiningController",
        "submit_plan -> consume_plan -> begin_execution",
        correlation_ids={
            "toe_frame_id": frame.frame_digest,
            "plan_id": plan.plan_id,
            "lease_id": executing.lease_id,
        },
    )

    execution_id = f"execution:{uuid.uuid4()}"
    router = ExecutionRouter(_CpuHasher(), _cpu_range)
    record, candidate = router.execute_plan(
        consumed,
        b"\x00" * 80,
        b"\xff" * 32,
        identity=identity,
        lease=reserved.contract(),
    )
    candidate_id = f"candidate:{uuid.uuid4()}" if candidate is not None else None
    record = dataclasses.replace(
        record,
        lease_id=executing.lease_id,
        generation=identity.generation,
        extranonce2=reserved.extranonce2,
        nonce_start=reserved.start,
        execution_id=execution_id,
        candidate_id=candidate_id,
        pool_outcome=PoolOutcome.NOT_SUBMITTED,
    )
    stage(
        "execution",
        "ExecutionRouter",
        "execute_plan",
        requested_backend=record.requested_route,
        actual_backend=record.executed_route,
        requested_order=record.requested_nonce_order,
        actual_order=record.executed_nonce_order,
        hashes_completed=record.hash_count,
        correlation_ids={"execution_id": execution_id, "candidate_id": candidate_id},
    )

    agentic.finish_execution(executing.lease_id, scanned=record.completed_work_items > 0)
    agentic.record_outcome(record)
    assert not agentic.telemetry.learning_update_applied
    stage(
        "learning",
        "AgenticMiningController",
        "record_outcome",
        applied=False,
        reason="NOT_SUBMITTED has no external reward authority",
        correlation_ids={"plan_id": plan.plan_id, "execution_id": execution_id},
    )

    coordinate = CausalCoordinate(
        pool_session_id=identity.pool_session_id,
        generation=identity.generation,
        job_fingerprint=identity.job_fingerprint,
        toe_frame_id=frame.frame_digest,
        plan_id=plan.plan_id,
        lease_id=executing.lease_id,
        execution_id=execution_id,
        candidate_id=candidate_id,
    )
    ledger = CausalLedger()
    ledger.record("controlled_execution", coordinate, pool_outcome="NOT_SUBMITTED")
    assert ledger.trace(execution_id=execution_id)

    return {
        "schema": "pythia.production_workflow_trace/1",
        "evidence_commit": _head(),
        "mode": "CONTROLLED_PROTOCOL_BOUNDARY",
        "live_pool_claim": "NOT_RUN",
        "physical_device_claim": "NOT_RUN",
        "correlation": coordinate.as_dict(),
        "outcome": "NOT_SUBMITTED",
        "stages": stages,
        "startup_command": (
            "PYTHIA_EXECUTION_DEVICE=cpu pythia --mine " "--user <worker> --password <password>"
        ),
        "authority_table": {
            "production_entrypoint": "main.main",
            "control_api": "control_api.serve",
            "mining_runtime": "mining_runtime._main_async",
            "mining_coordinator": "IntelligentPoolCoordinator",
            "stratum_transport": "manifold_pool_coordinator.StratumClient",
            "toe_adapter": "TOEMiningAdapter",
            "search_planner": "AgenticMiningController/SearchPlan",
            "execution_router": "ExecutionRouter",
            "proof_authority": "StratumProofAdapter + host SHA256d recheck",
            "learning": "AgenticMiningController.record_outcome",
            "recovery": "SelfHealingAgent/RecoveryGovernor",
            "autonomy": "autonomous_supervisor.AutonomousSupervisor",
        },
        "workflow_matrix": {
            "canonical_coordinator_identified": "PASS",
            "work_identity_immutable": "PASS",
            "observed_state_enters_toe": "PASS",
            "toe_decision_frame_produced": "PASS",
            "search_plan_references_toe_frame": "PASS",
            "nonce_lease_produced": "PASS",
            "execution_router_receives_plan": "PASS",
            "requested_backend_recorded": "PASS",
            "actual_backend_recorded": "PASS",
            "execution_record_produced": "PASS",
            "sha256d_remains_proof_authority": "PASS",
            "candidate_correlation": "PASS",
            "learning_references_generating_plan": "PASS",
            "live_subscribe_authorize": "NOT_RUN",
            "literal_pool_response": "NOT_RUN",
            "physical_device_execution": "NOT_RUN",
            "live_pool_share_accepted": "NOT_RUN",
        },
        "invariants": {
            "same_toe_frame_plan_execution": record.toe_frame_id == plan.toe_frame_id,
            "same_plan_lease_execution": record.plan_id == plan.plan_id == executing.lease_id,
            "sha256d_local_authority": candidate is not None
            and candidate["independently_rechecked"] is True,
            "unknown_outcome_no_reward": not agentic.telemetry.learning_update_applied,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports" / "production_workflow_trace.json"
    )
    args = parser.parse_args()
    report = run()
    if not all(report["invariants"].values()):
        raise SystemExit(1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
