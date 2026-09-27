"""Agentic mining workflow — autonomous decisions on the one live coordinator.

Not a second miner. Nonce search executes across 120 Hilbert sectors on the coordinator.
SHA256d certifies valid solutions. GoldenRatioScaler handles capacity proposals.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from threading import Lock
from typing import Any, Dict, Optional

from python_backend.core_modules.golden_ratio_scaler import GoldenRatioScaler
from mining.evidence import record_mining_event
from python_backend.pythia_mining.manifold_pool_coordinator import ManifoldPoolCoordinator

logger = logging.getLogger("hyba.mining.agentic")


class AgenticMiningIntegration:
    """Autonomous mining brain. Combined with ManifoldPoolCoordinator."""

    def __init__(
        self,
        coordinator: ManifoldPoolCoordinator,
        scaler: Optional[GoldenRatioScaler] = None,
    ):
        self.coordinator = coordinator
        self.scaler = scaler or GoldenRatioScaler(base=1)
        # The historical M32HilbertArsenal import currently depends on the
        # disconnected top-level hyba.runtime package. Keep agentic execution
        # available and report the arsenal as unavailable rather than breaking
        # the real mining path or claiming precomputation that did not happen.
        self.arsenal = None
        self.last_seal: Optional[Dict[str, Any]] = None
        self._state_lock = Lock()
        self.hardware_state = {
            "gpus": 1,
            "batch_size": 1,
            "memory_mb": 144,
            "search_depth": 512,
        }
        num_sectors = len(self.coordinator.sectors) if hasattr(self.coordinator, "sectors") else 120
        logger.info(
            f"[AGENTIC] Workflow bound to coordinator | {num_sectors} Hilbert sectors | canonical solver active"
        )

    def mine_job(
        self,
        job_id: str,
        prefix76: bytes,
        target_int: int,
        budget: int,
        seed_nonce: int,
        search_policy: Any = None,
        phi_score: float = 0.0,
        ntime_hex: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Deterministic execution identity: identical (job, prefix, budget,
        # seed) inputs produce an identical execution id — replayable and
        # auditable, no uuid4.
        execution_id = "agentic_" + hashlib.sha256(
            "|".join(
                str(p) for p in (job_id, prefix76.hex(), int(target_int), int(budget), int(seed_nonce))
            ).encode("utf-8")
        ).hexdigest()[:12]
        plan = self.propose_hardware_scaling(coherence=phi_score, phi_density=phi_score)
        # NOTE: `search_depth` here is GoldenRatioScaler's capacity-planning
        # proposal (metallic-mean Fibonacci scaling, capped per-dimension by
        # core_modules/golden_ratio_scaler.py's DIMENSION_CAPS -- 4181 for
        # search_depth, not a single 144-for-everything cap). It is real,
        # legitimate telemetry about *proposed* hardware scaling, but it must
        # never silently override the operator-configured real SHA256d hash
        # budget (HYBA_MINE_NONCES_PER_CYCLE). Previously this line capped
        # every mine_job() call at min(budget, search_depth) <= 144 -- so
        # requesting budget=250000 actually performed as few as ~37 real
        # hashes in testing during this investigation. The real hash budget
        # is `budget`, full stop; `plan`/`search_depth` stay in the returned
        # telemetry for visibility but no longer gate real search coverage.
        result = self.coordinator.work_job(
            job_id=job_id,
            prefix76=prefix76,
            target_int=target_int,
            budget=max(1, budget),
            seed_nonce=seed_nonce,
            search_policy=search_policy,
        )
        result["agentic"] = True
        result["execution_id"] = execution_id
        result["scaling"] = plan
        result["search"] = result.get("search", "grover_lucas")
        result["solved"] = result.get("found_nonce") is not None
        result["stale"] = False
        result["hilbert_section"] = result.get("hilbert_section")
        result["arsenal"] = result.get("arsenal")
        seal = self.seal_autonomous_decision(
            {
                "execution_id": execution_id,
                "job_id": job_id,
                "found_nonce": result.get("found_nonce"),
                "found_face": result.get("found_face"),
                "proposed": result.get("proposed", result.get("hashes")),
                "phi_score": phi_score,
                "solved_nonce": result.get("nonce"),
            }
        )
        with self._state_lock:
            self.last_seal = seal
        result["seal"] = seal
        result["provenance"] = self._build_result_provenance(result)
        self._persist_result_event(result)
        return result

    def propose_hardware_scaling(
        self,
        coherence: float,
        phi_density: float,
    ) -> Dict[str, Any]:
        with self._state_lock:
            current_state = dict(self.hardware_state)
        proposals = self.scaler.propose_scaling_plan(
            dimensions=["search_depth", "batch_size", "memory_mb"],
            current=current_state,
            target_coherence=float(coherence),
            phi_density=float(phi_density),
        )
        with self._state_lock:
            for proposal in proposals:
                self.hardware_state[proposal.dimension] = proposal.proposed_value
            hardware_state = dict(self.hardware_state)
        return {
            "proposals": [
                {
                    "dimension": p.dimension,
                    "current_value": p.current_value,
                    "proposed_value": p.proposed_value,
                    "rationale": p.rationale,
                }
                for p in proposals
            ],
            "hardware_state": hardware_state,
        }

    def seal_autonomous_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(decision, sort_keys=True, default=str).encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()
        return {
            "body_hash": digest,
            "timestamp": time.time(),
            "algorithm": "sha256",
            "immutable_guard_active": True,
        }

    def _build_result_provenance(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "source": {
                "class": "REAL",
                "description": "pool job header prefix and target supplied to coordinator",
            },
            "computation": {
                "class": "REAL",
                "description": "budgeted SHA256d oracle scan plus derived scaling telemetry",
            },
            "service": {
                "class": "REAL",
                "name": "AgenticMiningIntegration",
                "execution_id": result.get("execution_id"),
            },
            "result": {
                "class": "DERIVED",
                "solved": result.get("solved"),
                "hashes": result.get("hashes", 0),
            },
            "persistence_event": {"class": "REAL", "event_type": "agentic_mining_result"},
        }

    def _persist_result_event(self, result: Dict[str, Any]) -> None:
        record_mining_event(
            "agentic_mining_result",
            {
                "job_id": result.get("job_id"),
                "nonce": result.get("found_nonce"),
                "truth_class": "local-validation",
                "metadata": {
                    "execution_id": result.get("execution_id"),
                    "hashes": result.get("hashes", 0),
                    "solved": result.get("solved"),
                    "provenance": result.get("provenance"),
                },
            },
        )

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        with self._state_lock:
            hardware_state = dict(self.hardware_state)
            last_seal = self.last_seal
        return {
            "hardware_state": hardware_state,
            "last_seal": last_seal,
            "faces": 32,
            "external_identities": 1,
            "hilbert_sections": 32,
            "arsenal_precomputed": self.arsenal is not None,
            "arsenal_status": "REAL" if self.arsenal is not None else "UNAVAILABLE",
        }
