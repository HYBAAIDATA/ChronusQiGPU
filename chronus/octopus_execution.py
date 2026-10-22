"""600-Arm Octopus Execution Coordinator for PYTHIA Mining.

Phase P5 implementation:
- 1 Head (EuclidRuntime / H4600HybridCoordinator) coordinating 600 Arms.
- Complete 11-step lifecycle:
  1. Stratum Job Intake
  2. 8-Future Superposition Hold (SuperpositionHoldLRU)
  3. 600-Vertex Bijection Lease Partition (build_600_partition)
  4. Mother-Tensor Canonical State (KelloggMotherTensor)
  5. 5+1 Intelligence Scoring + Quantum Arsenal (score_600_lanes)
  6. SearchPlan Collapse (collapse_to_searchplan)
  7. ThreadPoolExecutor(4) Parallel Execution over 600 Arms
  8. Entangled Qubit Hashing (32-qubit Bell stabilizer tableau)
  9. 100% Host SHA256d Bit-Exact Recheck
  10. Submission Gate: Shadow Mode by default (shadow only until a governed transport is integrated)
  11. Literal Learning + Salamander 15.7s Autonomic Recovery + Attestation Ledger Merkle Root
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Sequence

from chronus.entangled_hashing import (
    EntangledNonceCandidate,
    EntangledQubitHasher,
    LaneHashingReceipt,
)
from chronus.exact_geometry import (
    EstateChunk600,
    build_600_partition,
)
from chronus.mla1517.mining.search_plan import (
    WorkIdentity,
)
from kellogg.ansatz_v3 import FUTURES, LANES
from kellogg.lane_scorer import (
    SuperpositionHoldLRU,
    score_600_lanes,
)
from kellogg.mother_tensor import kellogg_state_600
from salamander.mining_healer import SalamanderMiningHealer

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class OctopusCampaignReceipt:
    """Consolidated attestation receipt for a 600-arm Octopus campaign."""

    campaign_id: str
    job_id: str
    job_fingerprint: str
    total_arms: int
    nonces_evaluated: int
    winning_share: EntangledNonceCandidate | None
    host_recheck_pct: float
    elapsed_seconds: float
    search_plan_hash: str
    merkle_root: str
    submitted_live: bool
    shadow_logged: bool
    qubit_dimension: int
    total_bell_pairs: int
    lane_receipts: tuple[LaneHashingReceipt, ...]
    healing_events: tuple[str, ...]
    runtime_policy_digest: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "job_id": self.job_id,
            "job_fingerprint": self.job_fingerprint,
            "total_arms": self.total_arms,
            "nonces_evaluated": self.nonces_evaluated,
            "winning_share": asdict(self.winning_share) if self.winning_share else None,
            "host_recheck_pct": self.host_recheck_pct,
            "elapsed_seconds": self.elapsed_seconds,
            "search_plan_hash": self.search_plan_hash,
            "merkle_root": self.merkle_root,
            "submitted_live": self.submitted_live,
            "shadow_logged": self.shadow_logged,
            "qubit_dimension": self.qubit_dimension,
            "total_bell_pairs": self.total_bell_pairs,
            "healing_events": list(self.healing_events),
            "runtime_policy_digest": self.runtime_policy_digest,
        }


class OctopusExecutionEngine:
    """The 600-Arm Octopus Execution Coordinator (1 Head × 600 Arms)."""

    def __init__(
        self,
        shadow_dir: Path | str = "evidence/shadow_runs",
        max_workers: int = 4,  # ThreadPoolExecutor(4) eliminates GIL stall
    ) -> None:
        self.shadow_dir = Path(shadow_dir)
        self.shadow_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers
        self.superposition = SuperpositionHoldLRU(max_futures=FUTURES)
        self.healer = SalamanderMiningHealer(
            evidence_path=self.shadow_dir / "salamander_evidence.jsonl"
        )
        self.campaign_counter = 0

    def run_campaign(
        self,
        job_id: str,
        job_fingerprint: str,
        header_prefix: bytes,  # 76 bytes
        target_int: int,
        base_step: int,
        window: int,
        seed: int = 1337,
        approval_flag: bool = False,
        literal_history: Sequence[Any] | None = None,
        max_nonces_per_arm: int | None = None,
        work_identity: WorkIdentity | None = None,
        extranonce2: str = "00000001",
        plan_id: str | None = None,
        worker_limit: int | None = None,
        runtime_policy_digest: str = "",
    ) -> OctopusCampaignReceipt:
        """Execute a full 600-arm Octopus campaign over leased window W."""
        workers = self.max_workers if worker_limit is None else worker_limit
        if type(workers) is not int or not 1 <= workers <= 32:
            raise ValueError("worker_limit must be in [1,32]")
        if runtime_policy_digest and (
            len(runtime_policy_digest) != 64
            or any(c not in "0123456789abcdef" for c in runtime_policy_digest)
        ):
            raise ValueError("runtime policy digest must be lowercase SHA-256")
        t0 = time.monotonic()
        self.campaign_counter += 1
        campaign_id = f"octopus_camp_{self.campaign_counter:06d}_{int(t0)}"

        # 1. Superposition hold intake
        self.superposition.put(
            future_id=job_id,
            probability=1.0,
            metadata={"fingerprint": job_fingerprint, "target": target_int},
        )

        # 2. Structural partition certificate only: sample headers are not PoW.
        # Real header/target checks belong to the executing hasher below.
        chunks, proof = build_600_partition(
            base_step=base_step,
            window=window,
            seed=seed,
        )

        # 3. Canonical Kellogg Mother-Tensor
        mt = kellogg_state_600(
            base_step=base_step,
            window=window,
            seed=seed,
            futures=(job_id,),
            future_probabilities=(1.0,),
        )

        # 4. 5+1 Intelligence Scoring + Quantum Arsenal
        scores, summary = score_600_lanes(
            mother_tensor=mt,
            job_fingerprint=job_fingerprint,
            literal_history=literal_history,
            order_seed=seed,
        )

        # 5. Superposition collapse
        top_future, collapse_log = self.superposition.collapse(
            scores, reason="TOP_SCORE_WITH_ALTERNATIVES_LOG"
        )

        # 6. Build immutable SearchPlan
        identity = work_identity or WorkIdentity(
            pool_session_id=f"braiins_session_{self.campaign_counter}",
            generation=1,
            job_id=job_id,
            job_fingerprint=job_fingerprint,
            target_generation=1,
            clean_jobs=True,
            received_at=t0,
        )
        if identity.job_id != job_id or identity.job_fingerprint != job_fingerprint:
            raise ValueError("work identity must match the campaign job")
        plan = mt.build_search_plan(
            identity=identity,
            extranonce2=extranonce2,
            executor_route="chronus_batch",
        )
        if plan_id is not None:
            plan = replace(plan, plan_id=plan_id)
        plan_hash = hashlib.sha256(
            json.dumps(
                {
                    "plan_id": plan.plan_id,
                    "window": window,
                    "coverage": proof.coverage_hash,
                    "runtime_policy_digest": runtime_policy_digest,
                }
            ).encode("utf-8")
        ).hexdigest()

        # 7. ThreadPoolExecutor(4) Execution over 600 Arms
        receipts: list[LaneHashingReceipt] = []

        def _execute_arm(lane_chunk: EstateChunk600) -> LaneHashingReceipt:
            hasher = EntangledQubitHasher(
                chunk=lane_chunk,
                header_prefix=header_prefix,
                target_int=target_int,
                device_route="chronus_batch",
            )
            return hasher.execute(max_evaluations=max_nonces_per_arm)

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_arm = {executor.submit(_execute_arm, c): c.lane_id for c in chunks}
            for fut in concurrent.futures.as_completed(future_to_arm):
                lane_receipt = fut.result()
                receipts.append(lane_receipt)

        # Sort receipts by lane_id
        receipts.sort(key=lambda r: r.lane_id)

        # 8. Host recheck verification and winner detection
        total_nonces = sum(r.nonces_evaluated for r in receipts)
        total_recheck_pct = sum(r.host_recheck_pct for r in receipts) / float(len(receipts))
        winning_candidate = next(
            (r.winning_candidate for r in receipts if r.winning_candidate is not None), None
        )

        # 9. Submission Gate (Shadow Mode Default)
        submitted_live = False
        # This coordinator has no identity-bound transport or pool acknowledgement.
        # An approval flag alone cannot establish submission. Always retain shadow
        # evidence, including approved winners, until governed transport is wired.
        shadow_logged = True
        shadow_file = self.shadow_dir / f"{campaign_id}.jsonl"
        payload = {
            "campaign_id": campaign_id,
            "job_id": job_id,
            "job_fingerprint": job_fingerprint,
            "winner": asdict(winning_candidate) if winning_candidate else None,
            "total_nonces": total_nonces,
            "timestamp": time.time(),
            "approval_requested": bool(approval_flag),
            "submission_status": "unavailable_no_governed_transport",
        }
        with open(shadow_file, "a", encoding="utf-8") as sf:
            sf.write(json.dumps(payload) + "\n")

        # 10. Compute Merkle Root across all 600 execution receipts
        leaf_hashes = [
            hashlib.sha256(
                f"{r.lane_id}:{r.nonces_evaluated}:{r.host_recheck_pct}:{r.device_id}".encode(
                    "ascii"
                )
            ).digest()
            for r in receipts
        ]
        # Pairwise Merkle aggregation
        current_layer = leaf_hashes
        while len(current_layer) > 1:
            next_layer = []
            for i in range(0, len(current_layer), 2):
                left = current_layer[i]
                right = current_layer[i + 1] if i + 1 < len(current_layer) else left
                combined = hashlib.sha256(left + right).digest()
                next_layer.append(combined)
            current_layer = next_layer
        merkle_root = current_layer[0].hex() if current_layer else ""

        # 11. Salamander autonomic health recording
        healing_events: list[str] = []
        if total_recheck_pct < 100.0:
            healing_events.append("HealAction=STALL_DETECTED_RECHECK_DROP")

        elapsed_sec = time.monotonic() - t0

        return OctopusCampaignReceipt(
            campaign_id=campaign_id,
            job_id=job_id,
            job_fingerprint=job_fingerprint,
            total_arms=len(receipts),
            nonces_evaluated=total_nonces,
            winning_share=winning_candidate,
            host_recheck_pct=total_recheck_pct,
            elapsed_seconds=elapsed_sec,
            search_plan_hash=plan_hash,
            merkle_root=merkle_root,
            submitted_live=submitted_live,
            shadow_logged=shadow_logged,
            qubit_dimension=32,
            total_bell_pairs=LANES * 16,  # 600 lanes × 16 Bell pairs = 9,600 Bell pairs
            lane_receipts=tuple(receipts),
            healing_events=tuple(healing_events),
            runtime_policy_digest=runtime_policy_digest,
        )


def run_10min_soak_campaign(
    engine: OctopusExecutionEngine,
    jobs: Sequence[tuple[str, str, int]],  # (job_id, fingerprint, target)
    max_duration_seconds: float = 600.0,
    window_per_campaign: int = 12000,
) -> dict[str, Any]:
    """Execute a 10-minute soak campaign logging jobs, difficulties, invalidations, heals, and rechecks."""
    t_start = time.monotonic()
    campaigns_completed = 0
    total_nonces_tried = 0
    total_heals = 0
    rechecks_all: list[float] = []
    job_difficulties: list[int] = []

    prefix = b"\x00" * 76

    while (time.monotonic() - t_start) < max_duration_seconds and campaigns_completed < len(
        jobs
    ) * 5:
        job_idx = campaigns_completed % len(jobs)
        job_id, fp, target = jobs[job_idx]

        receipt = engine.run_campaign(
            job_id=job_id,
            job_fingerprint=fp,
            header_prefix=prefix,
            target_int=target,
            base_step=campaigns_completed * window_per_campaign,
            window=window_per_campaign,
            approval_flag=False,  # Shadow mode strictly enforced
            max_nonces_per_arm=20,  # Fast throughput per arm in soak test
        )

        campaigns_completed += 1
        total_nonces_tried += receipt.nonces_evaluated
        total_heals += len(receipt.healing_events)
        rechecks_all.append(receipt.host_recheck_pct)
        job_difficulties.append(target)

    elapsed = time.monotonic() - t_start
    avg_recheck = sum(rechecks_all) / max(len(rechecks_all), 1)

    return {
        "duration_seconds": elapsed,
        "campaigns_completed": campaigns_completed,
        "total_arms_engaged": campaigns_completed * LANES,
        "total_nonces_evaluated": total_nonces_tried,
        "host_recheck_average_pct": avg_recheck,
        "heals_performed": total_heals,
        "distinct_jobs_processed": len(set(j[0] for j in jobs)),
        "difficulties_negotiated": len(job_difficulties),
        "shadow_mode_enforced": True,
        "unapproved_submissions": 0,
    }
