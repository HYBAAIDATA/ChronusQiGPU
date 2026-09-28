"""Real-pool voyage, read-only: live Stratum truth → leased plans → real execution.

Connects to a live pool as the operator's worker, waits for a genuine job and
share target, and runs the canonical path on it: Stratum identity →
agentic SearchPlan → nonce lease → Execution Router (OpenCL when bound) →
independent host recheck → proof-adapter validation. It NEVER sends
``mining.submit``; a locally valid candidate is reported, not submitted.

Usage:
    python real_pool_voyage.py --endpoint stratum.braiins.com:3333 \\
        --user ACCOUNT.WORKER --seconds 120 --backend auto
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

import mining_runtime
from manifold_pool_coordinator import StratumClient, parse_endpoint
from mla1517.mining.coordinator import IntelligentPoolCoordinator


async def run_real_pool_voyage(
    endpoint: str, user: str, password: str, seconds: float, backend: str, tls: bool
) -> dict[str, Any]:
    pool = parse_endpoint(endpoint, endpoint.split(":")[0], tls=tls)
    hasher = mining_runtime._execution_hasher(backend)
    coord = IntelligentPoolCoordinator(
        [pool], username=user, password=password, submit_enabled=False, execution_hasher=hasher
    )
    client = StratumClient(pool, username=user, password=password, request_timeout=20.0)
    report: dict[str, Any] = {
        "endpoint": endpoint,
        "submit": "NEVER (read-only voyage)",
        "backend": getattr(hasher, "backend", None),
        "device": getattr(hasher, "device", None),
        "generations_seen": set(),
        "executions": [],
        "local_candidates": 0,
        "proof_adapter_validated": 0,
    }
    started = time.monotonic()
    try:
        await asyncio.wait_for(client.connect(), 30)
        coord.client = client
        deadline = time.monotonic() + 60
        while not client.runtime_state.ready and time.monotonic() < deadline:
            await asyncio.sleep(0.2)
        report["stratum"] = client.status_snapshot()
        if not client.runtime_state.ready:
            report["result"] = "NO_READY_JOB_WITHIN_60S"
            return report
        while time.monotonic() - started < seconds:
            identity = coord._refresh_work_identity()
            if identity is None:
                await asyncio.sleep(0.2)
                continue
            report["generations_seen"].add(identity.generation)
            plan = coord._build_plan(identity)
            if plan is None or not coord.agentic.submit_plan(plan):
                await asyncio.sleep(0.2)
                continue
            plan = coord.agentic.consume_plan()
            if plan is None:
                continue
            reserved = coord.agentic.lease(plan.plan_id)
            lease = coord.agentic.begin_execution(plan)
            adapter = client.proof_adapter
            job = adapter.current_job
            header = adapter.build_header(job.job_id, lease.extranonce2, job.ntime, 0)
            record, candidate = await asyncio.to_thread(
                coord._router_for(plan).execute_plan,
                plan,
                header,
                job.target.to_bytes(32, "little"),
                identity=identity,
                lease=reserved.contract(),
                is_still_fresh=lambda: coord._identity_is(identity.key),
            )
            coord.agentic.finish_execution(lease.lease_id, scanned=record.completed_work_items > 0)
            entry = {
                "generation": identity.generation,
                "job_id": identity.job_id,
                "executed_route": record.executed_route,
                "evidence_class": record.evidence_class.value,
                "completion_state": record.completion_state.value,
                "hashes": record.hash_count,
                "kernel_ms": record.kernel_ms,
            }
            if candidate is not None:
                report["local_candidates"] += 1
                adapter.validate_candidate(
                    job_id=job.job_id,
                    extranonce2=lease.extranonce2,
                    ntime=job.ntime,
                    nonce=candidate["nonce"],
                )
                report["proof_adapter_validated"] += 1
                entry["candidate_nonce"] = candidate["nonce"]
            report["executions"].append(entry)
        report["result"] = "COMPLETED"
    finally:
        await client.close()
        report["generations_seen"] = sorted(report["generations_seen"])
        report["seconds"] = round(time.monotonic() - started, 1)
        report["agentic"] = {
            k: coord.agentic.snapshot()[k]
            for k in ("plans_created", "plans_consumed", "plans_invalidated", "plans_stale")
        }
    return report


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--user", required=True, help="the operator's own pool worker")
    parser.add_argument("--password", default="x")
    parser.add_argument("--seconds", type=float, default=120.0)
    parser.add_argument("--backend", default="auto", choices=("cpu", "auto", "gpu"))
    parser.add_argument("--tls", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(
        run_real_pool_voyage(
            args.endpoint, args.user, args.password, args.seconds, args.backend, args.tls
        )
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    _main()
