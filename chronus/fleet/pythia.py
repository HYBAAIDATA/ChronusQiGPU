"""Bounded local PYTHIA fleet using canonical leases and the Chronus triad.

PYTHIA supplies nonce order and retains pool/proof authority. This executor has
no Stratum client. Logical workers are not claims of independent physical GPUs.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid

from aethel.enterprise.records import OperationalRecord
from chronus.product import TIERS, CapacityExceeded, PackagedGPU
from chronus.igpu.host import HostGPUPlan
from chronus.virtual_igpu.abi import Workload, execution_policy_for_product_mode
from chronus.virtual_igpu.host_verify import sha256d, verify_hits
from .native_worker import NativeIGPUWorker, ExecutionResult
from .scheduler import FleetScheduler
from .worker_identity import WorkerIdentity


class PythiaFleet:
    backend = "chronus_vigpu"
    vendor = "HYBA"
    device = "Chronus bounded PYTHIA fleet"
    kernel_ms = 0.0
    launches = 0

    def __init__(
        self,
        root,
        *,
        tenant,
        tier="starter",
        workers=1,
        mode="independent",
        adapter_factory=None,
        allow_software_fallback=True,
    ):
        self.tier = TIERS[tier]
        if type(workers) is not int or not 1 <= workers <= self.tier.max_workers:
            raise CapacityExceeded("worker count exceeds selected tier")
        self.root, self.tenant = Path(root), tenant
        self._busy = threading.Lock()
        self.grind_batch = self.tier.max_items_per_request
        self.last_batch_evidence = None
        self.physical_device_executed = False
        self.nodes = {}
        self.workers = {}
        # Split the fleet's aggregate budgets; adding workers cannot multiply its entitlement.
        node_tier = replace(
            self.tier,
            max_workers=1,
            max_resident_bytes=self.tier.max_resident_bytes // workers,
            max_custody_bytes=self.tier.max_custody_bytes // workers,
            max_custody_records=self.tier.max_custody_records // workers,
        )
        instance = uuid.uuid4().hex
        for i in range(workers):
            wid = f"worker-{i:03d}"
            self.nodes[wid] = PackagedGPU(
                self.root / wid,
                tenant=tenant,
                tier=node_tier,
                mode=mode,
                adapters=adapter_factory() if adapter_factory else None,
                allow_software_fallback=allow_software_fallback,
            )
            self.workers[wid] = NativeIGPUWorker(
                WorkerIdentity(
                    worker_id=wid,
                    tenant=tenant,
                    instance_id=instance,
                    fencing_token=uuid.uuid4().hex,
                ),
                HostGPUPlan(total_items=self.grind_batch, lanes=1, backend="chronus_vigpu"),
            )
        self.scheduler = FleetScheduler(self.workers)

    def _record(self, job_id, stage, body, evidence_state):
        authority = next(iter(self.nodes.values())).triad.ovid
        record = OperationalRecord(
            record_id=f"pythia-{job_id}-{stage}",
            producer="pythia",
            producer_version="1.0.0",
            kind=f"pythia_fleet_{stage}",
            schema_version=1,
            payload=json.dumps(body, sort_keys=True).encode(),
            evidence_state=evidence_state,
            correlation_ids={"workload_id": job_id},
        )
        return authority.put_record(self.tenant, record)

    def _run_shard(self, worker, lease, header, target, nonces):
        node = self.nodes[worker.identity.worker_id]
        capacity = node.triad.capacity
        workload = Workload(
            id=lease.work_id,
            tenant=self.tenant,
            kind="sha256d_scan",
            input={"header80_hex": header.hex(), "target_hex": target.hex(), "nonces": nonces},
            execution_policy=execution_policy_for_product_mode(capacity.product_mode),
            allow_software_fallback=capacity.allow_software_fallback,
        )
        started = time.perf_counter()
        result = node.submit(workload)
        if result.status != "ok" or result.receipt["verification"]["verdict"] != "match":
            raise RuntimeError("fleet shard did not verify")
        output = result.output
        verify_hits(
            header[:76], output["hits"], int.from_bytes(target, "big"), allowed_nonces=nonces
        )
        checked = output["checked"]
        evaluations = output.get("sha256d_evaluations", checked)
        if not 0 < checked <= evaluations <= len(nonces):
            raise ValueError("invalid fleet work count")
        # Completion records cover the submitted positional lease, including
        # positions skipped after the first winning nonce in that shard.
        rows = [[nonce, i < checked] for i, nonce in enumerate(nonces)]
        completion = ExecutionResult(
            worker_id=worker.identity.worker_id,
            lease_id=lease.lease_id,
            work_id=lease.work_id,
            tenant=self.tenant,
            partition=lease.partition,
            generation=worker.identity.generation,
            fencing_token=lease.fencing_token,
            backend="chronus_vigpu",
            result=rows,
            output_digest=hashlib.sha256(repr(rows).encode()).hexdigest(),
            sha256d_evaluations=evaluations,
            elapsed_seconds=time.perf_counter() - started,
        )
        worker.complete_lease(lease.lease_id, completion)
        return completion, result

    def grind_target_batch(self, header80, target_be, nonces):
        header, target = bytes(header80), bytes(target_be)
        if len(header) != 80 or len(target) != 32:
            raise ValueError("PYTHIA requires an 80-byte header and 32-byte target")
        if len(nonces) > self.grind_batch:
            raise CapacityExceeded("PYTHIA batch exceeds tier")
        nonces = list(nonces)
        if any(type(n) is not int or not 0 <= n < 2**32 for n in nonces):
            raise ValueError("nonces must be uint32 integers")
        if not nonces:
            return None, None, 0
        if not self._busy.acquire(blocking=False):
            raise CapacityExceeded("PYTHIA fleet is busy")
        job_id = uuid.uuid4().hex
        started = time.perf_counter()
        self.last_batch_evidence = None
        self.physical_device_executed = False
        try:
            parts = []
            width = (len(nonces) + len(self.workers) - 1) // len(self.workers)
            for (wid, worker), start in zip(
                self.scheduler.workers.items(), range(0, len(nonces), width)
            ):
                end = min(len(nonces), start + width)
                lease = self.scheduler.issue_lease(
                    work_id=f"{job_id}-{start}-{end}",
                    tenant=self.tenant,
                    operation="pythia_sha256d",
                    input_data=nonces[start:end],
                    partition=(start, end),
                    target_worker=wid,
                    resource_budget={
                        "cpu_cores": 1,
                        "memory_mb": max(
                            1, self.nodes[wid].tier.max_resident_bytes // (1024 * 1024)
                        ),
                        "concurrency": 1,
                    },
                )
                if lease is None:
                    raise RuntimeError("no worker available for fleet partition")
                parts.append((worker, lease, nonces[start:end]))
            self._record(
                job_id,
                "intent",
                {
                    "tier": self.tier.manifest(),
                    "header_digest": hashlib.sha256(header).hexdigest(),
                    "nonce_digest": hashlib.sha256(json.dumps(nonces).encode()).hexdigest(),
                    "target": target.hex(),
                    "leases": [asdict(p[1]) for p in parts],
                },
                "GATED",
            )
            with ThreadPoolExecutor(
                max_workers=len(parts), thread_name_prefix="pythia"
            ) as executor:
                futures = [
                    executor.submit(self._run_shard, w, lease, header, target, batch)
                    for w, lease, batch in parts
                ]
                results = [future.result() for future in futures]
            total, winner, shards = 0, None, []
            for (worker, lease, _), (completion, result) in zip(parts, results):
                if not self.scheduler.register_result(
                    lease_id=lease.lease_id, worker=worker, result=completion
                ):
                    raise RuntimeError("stale or conflicting fleet completion")
                total += completion.sha256d_evaluations
                if winner is None and result.output["hits"]:
                    winner = result.output["hits"][0]["nonce"]
                shards.append(
                    {
                        "worker": worker.identity.worker_id,
                        "partition": lease.partition,
                        "fencing_token": lease.fencing_token,
                        "evaluations": completion.sha256d_evaluations,
                        "adapter_kind": result.attestation.get("kind"),
                        "custody": result.metrics["custody"],
                        "receipt": result.receipt,
                    }
                )
            elapsed = time.perf_counter() - started
            evidence = {
                "schema": "chronus.pythia-fleet/v1",
                "job_id": job_id,
                "tier": self.tier.name,
                "completion_state": "COMPLETE",
                "submitted_items": len(nonces),
                "sha256d_evaluations": total,
                "elapsed_seconds": elapsed,
                "measured_hashes_per_second": total / elapsed,
                "candidate_nonce": winner,
                "shards": shards,
                "live_pool_authority": False,
                "physical_fanout_observed": False,
            }
            evidence["custody_record"] = self._record(job_id, "complete", evidence, "PASS")
            self.last_batch_evidence = evidence
            self.physical_device_executed = all(
                shard["adapter_kind"] in {"opencl", "cuda", "rocm", "oneapi", "metal"}
                for shard in shards
            )
            self.launches += len(parts)
            self.kernel_ms += elapsed * 1000
            return (
                winner,
                sha256d(header[:76] + winner.to_bytes(4, "little")) if winner is not None else None,
                total,
            )
        except Exception:
            self.last_batch_evidence = {
                "completion_state": "DEVICE_ERROR",
                "job_id": job_id,
                "physical_fanout_observed": False,
            }
            raise
        finally:
            # Bound lease/history residency and revoke the completed batch's tokens.
            for wid in self.scheduler.workers:
                self.scheduler.terminate_worker(wid)
            self.workers = self.scheduler.workers
            self.scheduler = FleetScheduler(self.workers)
            self._busy.release()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Execute a synthetic, pool-free PYTHIA fleet check"
    )
    parser.add_argument("--root", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--tier", choices=tuple(TIERS), default="starter")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--items", type=int, default=256)
    parser.add_argument("--mode", choices=("independent", "host"), default="independent")
    args = parser.parse_args()
    if not 1 <= args.items <= TIERS[args.tier].max_items_per_request:
        parser.error("items exceed selected tier")
    fleet = PythiaFleet(
        args.root, tenant=args.tenant, tier=args.tier, workers=args.workers, mode=args.mode
    )
    fleet.grind_target_batch(bytes(range(80)), bytes(32), list(range(args.items)))
    print(json.dumps(fleet.last_batch_evidence, sort_keys=True))


if __name__ == "__main__":
    main()
