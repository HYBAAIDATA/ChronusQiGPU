"""Explicit PYTHIA intelligence/agentic cycle over the canonical miner.

This module does not create another miner.  The production
``AgenticMiningController`` still owns generation-scoped SearchPlans and nonce
leases; Stratum still owns work identity; Chronus still executes; SHA256d and
the negotiated target still decide local validity; literal pool responses are
the only pool-outcome truth.

The purpose of this adapter is to make the intelligence organism visible and
correlated end-to-end.  It records the upstream production agentic plan,
PYTHIA memory recall, five-modal intelligence, supposition, Turing/quantum and
Kellogg tensor capability composition, execution outcome and learning in one
bounded evidence record.

A trained historical Turing VQC may contribute candidate *ordering* inside an
already-authorised nonce lease when ``PYTHIA_VQC_CHECKPOINT`` points to a
compatible checkpoint.  It can neither prune the lease nor validate a share.
Without a checkpoint, VQC guidance is reported unavailable rather than using
an untrained model as production evidence.

The historical ``Intelligence.agentic_mining.AgenticMiningWorkflow`` is kept
as research/advisory lineage.  It is never given a pool socket or submission
authority here.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace
from enum import Enum
import importlib.util
import os
from pathlib import Path
import time
import uuid
from typing import Any, Mapping

from .pythia_authority import (
    PythiaMiningAuthority,
    PythiaMiningDirective,
    PythiaQuantumArsenal,
)

SCHEMA = "pythia.agentic_mining_cycle/1"


def _safe(value: Any, *, depth: int = 0) -> Any:
    """Bound arbitrary intelligence objects into telemetry-safe evidence."""
    if depth >= 5:
        return repr(value)[:512]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {
            "bytes": len(value),
            "sha256_prefix": __import__("hashlib").sha256(value).hexdigest()[:16],
        }
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _safe(asdict(value), depth=depth + 1)
    if isinstance(value, Mapping):
        items = list(value.items())[:64]
        return {str(k): _safe(v, depth=depth + 1) for k, v in items}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe(v, depth=depth + 1) for v in list(value)[:64]]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _safe(to_dict(), depth=depth + 1)
        except Exception:
            pass
    as_dict = getattr(value, "as_dict", None)
    if callable(as_dict):
        try:
            return _safe(as_dict(), depth=depth + 1)
        except Exception:
            pass
    return repr(value)[:1024]


def _research_agentic_status() -> dict[str, Any]:
    """Classify the recovered six-phase workflow without activating it."""
    try:
        present = importlib.util.find_spec("Intelligence.agentic_mining") is not None
    except Exception as exc:
        return {
            "available": False,
            "role": "research_advisory_non_writer",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    return {
        "available": present,
        "module": "Intelligence.agentic_mining",
        "class": "AgenticMiningWorkflow",
        "role": "research_advisory_non_writer",
        "submission_authority": False,
        "reason": (
            "historical six-phase intelligence lifecycle retained as donor/advisory; "
            "canonical production submission remains in the Chronus/Stratum coordinator"
        ),
    }


class PythiaAgenticMiningAuthority(PythiaMiningAuthority):
    """PYTHIA mining authority with one correlated intelligence-cycle receipt."""

    def __init__(
        self,
        *,
        orchestrator: Any | None = None,
        quantum: PythiaQuantumArsenal | None = None,
        corpus_path: str | None = None,
        corpus: Any | None = None,
        backend_registry: Any | None = None,
    ) -> None:
        super().__init__(
            orchestrator=orchestrator,
            quantum=quantum,
            corpus_path=corpus_path,
            corpus=corpus,
            backend_registry=backend_registry,
        )
        self.last_agentic_cycle: dict[str, Any] | None = None
        self._vqc: Any | None = None
        self._vqc_checkpoint: str | None = None
        self._vqc_checkpoint_evidence: dict[str, Any] | None = None

    def _memory_recall(self, context: Mapping[str, Any]) -> dict[str, Any]:
        job = context.get("job_id", "unknown")
        generation = context.get("generation", "unknown")
        try:
            recalled = self.orchestrator.begin_memory_task(
                f"Bitcoin mining job {job} generation {generation}: recall relevant mining outcomes, "
                "failures, strategies and historical corpus context before planning"
            )
            return {"available": True, "result": _safe(recalled)}
        except Exception as exc:
            return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}

    def _five_modal_evidence(
        self,
        *,
        header: bytes,
        target_be: bytes,
        base_step: int,
    ) -> dict[str, Any]:
        try:
            result = self.orchestrator.counterfactual_analyze(
                header=header,
                target=target_be,
                current_nonce=base_step,
                n_counterfactuals=5,
            )
            return {
                "available": True,
                "modalities": [
                    "predictive",
                    "causal",
                    "counterfactual",
                    "topological",
                    "geometric",
                ],
                "result_type": type(result).__name__,
                "result": _safe(result),
            }
        except Exception as exc:
            return {
                "available": False,
                "modalities": [
                    "predictive",
                    "causal",
                    "counterfactual",
                    "topological",
                    "geometric",
                ],
                "reason": f"{type(exc).__name__}: {exc}",
            }

    def _compute_surfaces(self) -> dict[str, Any]:
        return {
            "turing_and_quantum_arsenal": self.quantum.inventory(),
            "historical_vqc_training_bridge": self._availability("Intelligence.bitcoin_vqc_training"),
            "quantum_gpu_substrate": {
                "system": self._availability("quantum_compute_substrate.system"),
                "memory": self._availability("quantum_compute_substrate.memory_hierarchy"),
                "quantum_2026": self._availability("quantum_compute_substrate.quantum_2026"),
            },
            "kellogg_tensor_only": {
                "authority": "tensor",
                "root": self._availability("kellogg"),
                "tensor_network": self._availability("kellogg.tensor_network"),
                "exact_tensor": self._availability("kellogg.exact_tensor"),
                "compressed_tensor": self._availability("kellogg.compressed_tensor"),
            },
            "chronus_execution": self.backend_inventory(),
        }

    @staticmethod
    def _header_for_vqc(header: bytes) -> dict[str, Any]:
        return {
            "version": int.from_bytes(header[0:4], "little"),
            "prev_hash": header[4:36][::-1].hex(),
            "merkle_root": header[36:68][::-1].hex(),
            "ntime": int.from_bytes(header[68:72], "little"),
            "nbits": int.from_bytes(header[72:76], "little"),
        }

    def _vqc_guidance(
        self,
        *,
        header: bytes,
        base_step: int,
        window: int,
    ) -> dict[str, Any]:
        enabled = os.getenv("PYTHIA_VQC_GUIDANCE", "1").strip().lower() not in {
            "0", "false", "off", "no"
        }
        if not enabled:
            return {"available": False, "state": "DISABLED"}
        checkpoint = os.getenv("PYTHIA_VQC_CHECKPOINT", "").strip()
        if not checkpoint:
            return {
                "available": False,
                "state": "NO_CHECKPOINT",
                "reason": "untrained VQC is never promoted into production search ordering",
            }
        checkpoint_path = Path(checkpoint)
        if not checkpoint_path.is_file():
            return {
                "available": False,
                "state": "CHECKPOINT_MISSING",
                "checkpoint": checkpoint,
            }
        try:
            if self._vqc is None:
                variational = None
                errors: list[str] = []
                for module_name in (
                    "turing_universal_quantum_computer.variational",
                    "turing_universal_quantum_computer.turing_universal_quantum_computer.variational",
                ):
                    try:
                        variational = __import__(module_name, fromlist=["*"])
                        break
                    except Exception as exc:
                        errors.append(f"{module_name}: {type(exc).__name__}: {exc}")
                if variational is None:
                    raise RuntimeError("; ".join(errors))
                self._vqc = variational.VariationalQuantumCircuit(variational.VQCConfig())
            if self._vqc_checkpoint != str(checkpoint_path):
                from Intelligence.bitcoin_vqc_training import load_checkpoint

                self._vqc_checkpoint_evidence = load_checkpoint(self._vqc, checkpoint_path)
                self._vqc_checkpoint = str(checkpoint_path)
            result = self._vqc.predict_with_confidence(self._header_for_vqc(header))
            raw = list(result.get("top_nonces") or result.get("candidates") or [])
            preferred: list[int] = []
            seen: set[int] = set()
            for value in raw:
                nonce = base_step + (int(value) % window)
                if nonce not in seen:
                    seen.add(nonce)
                    preferred.append(nonce)
            return {
                "available": True,
                "state": "ACTIVE",
                "truth_class": "trained_model_search_order_only",
                "confidence": float(result.get("confidence", 0.0)),
                "preferred_nonces": preferred,
                "checkpoint": _safe(self._vqc_checkpoint_evidence),
                "coverage_authority": False,
                "consensus_authority": False,
            }
        except Exception as exc:
            return {
                "available": False,
                "state": "DEGRADED",
                "checkpoint": checkpoint,
                "reason": f"{type(exc).__name__}: {exc}",
            }

    def plan(
        self,
        *,
        header: bytes,
        target_be: bytes,
        base_step: int,
        window: int,
        block_context: Mapping[str, Any] | None = None,
    ) -> PythiaMiningDirective:
        context = dict(block_context or {})
        recall = self._memory_recall(context)

        directive = super().plan(
            header=header,
            target_be=target_be,
            base_step=base_step,
            window=window,
            block_context=context,
        )

        # The base authority runs the five-modal engine for planning. Run one
        # bounded evidence pass as well so the actual result, not just a
        # boolean availability marker, is retained with this SearchPlan.
        five = self._five_modal_evidence(
            header=header,
            target_be=target_be,
            base_step=base_step,
        )
        vqc = self._vqc_guidance(header=header, base_step=base_step, window=window)
        if vqc.get("available"):
            merged: list[int] = []
            seen: set[int] = set()
            for nonce in list(vqc.get("preferred_nonces") or []) + list(directive.preferred_nonces):
                value = int(nonce)
                if base_step <= value < base_step + window and value not in seen:
                    seen.add(value)
                    merged.append(value)
                if len(merged) >= min(window, 10_000):
                    break
            directive = replace(
                directive,
                preferred_nonces=tuple(merged),
                lane_order=self._lane_order(merged, base_step),
                source=directive.source + "+trained_vqc",
            )

        compute = self._compute_surfaces()
        upstream = _safe(context.get("upstream_agentic_plan"))

        suppositions = tuple(directive.suppositions) + (
            {
                "kind": "mining_hypothesis",
                "source": "PYTHIA integrated intelligence cycle",
                "truth_class": "supposition_until_sha256d_evaluated",
                "basis": {
                    "guidance_source": directive.source,
                    "guidance_confidence": directive.confidence,
                    "preferred_nonce_count": len(directive.preferred_nonces),
                    "five_modal_evidence_available": bool(five.get("available")),
                    "trained_vqc_guidance": bool(vqc.get("available")),
                },
                "historical_lineage": {
                    "exact_SuppositionEngine_restored": False,
                    "surviving_prior": "legacy/python_backend/pythia_mining/precompute_cache.py:supposition-prior",
                    "research_inference": "Intelligence.agentic_mining.AgenticMiningWorkflow",
                },
            },
        )
        modalities = {
            **dict(directive.modalities),
            "five_modal_evidence": five,
            "memory_recall": recall,
            "vqc_guidance": vqc,
            "production_agentic_plan_present": upstream is not None,
        }
        resources = {
            **dict(directive.resources),
            "compute_surfaces": compute,
        }
        directive = replace(
            directive,
            modalities=modalities,
            suppositions=suppositions,
            resources=resources,
        )
        self.last_directive = directive

        cycle_id = str(uuid.uuid4())
        self.last_agentic_cycle = {
            "schema": SCHEMA,
            "cycle_id": cycle_id,
            "started_at": time.time(),
            "job": {
                "job_id": context.get("job_id"),
                "pool_session_id": context.get("pool_session_id"),
                "generation": context.get("generation"),
                "target_generation": context.get("target_generation"),
                "clean_jobs": context.get("clean_jobs"),
            },
            "roles": {
                "production_agentic_planner": "chronus.mla1517.mining.agentic_controller.AgenticMiningController",
                "mining_intelligence_and_composition": "PYTHIA",
                "quantum_vqc_algorithms": "Turing",
                "tensor": "Kellogg",
                "execution": "Chronus",
                "healing_optimisation": "Salamander",
                "security_governance": "AL HARAS",
                "work_identity": "Stratum",
                "proof_validity": "SHA256d + negotiated target",
            },
            "research_agentic_lineage": _research_agentic_status(),
            "stages": {
                "OBSERVE": {"state": "COMPLETE", "source": "authoritative Stratum context"},
                "RECALL": {
                    "state": "COMPLETE" if recall.get("available") else "UNAVAILABLE",
                    "evidence": recall,
                },
                "INTELLIGENCE": {
                    "state": "COMPLETE" if five.get("available") else "DEGRADED",
                    "evidence": five,
                },
                "SUPPOSE": {"state": "COMPLETE", "evidence": _safe(suppositions)},
                "COMPOSE": {
                    "state": "COMPLETE",
                    "evidence": _safe(compute),
                    "trained_vqc": _safe(vqc),
                },
                "PLAN": {
                    "state": "COMPLETE",
                    "upstream_agentic_plan": upstream,
                    "pythia_directive": directive.as_evidence(),
                },
                "EXECUTE": {"state": "PENDING"},
                "VERIFY": {"state": "PENDING"},
                "OUTCOME": {"state": "PENDING"},
                "LEARN": {"state": "PENDING"},
                "HEAL_OPTIMISE": {
                    "state": "EXTERNAL_CLOSED_LOOP",
                    "authority": "salamander.runtime.MiningAutonomyBridge + RecoveryGovernor + ClosedLoopOptimizer",
                },
            },
        }
        return directive

    def learn_execution(
        self,
        *,
        header: bytes,
        nonce: int | None,
        pool_accepted: bool | None,
        execution: Mapping[str, Any],
    ) -> None:
        super().learn_execution(
            header=header,
            nonce=nonce,
            pool_accepted=pool_accepted,
            execution=execution,
        )
        if self.last_agentic_cycle is None:
            return
        cycle = dict(self.last_agentic_cycle)
        stages = dict(cycle.get("stages") or {})
        stages["EXECUTE"] = {
            "state": "COMPLETE",
            "evidence": _safe(execution),
        }
        stages["VERIFY"] = {
            "state": "COMPLETE",
            "candidate_nonce": nonce,
            "authority": "canonical coordinator host SHA256d/target verification",
        }
        stages["OUTCOME"] = {
            "state": "COMPLETE",
            "pool_accepted": pool_accepted,
            "truth": (
                "literal pool response"
                if pool_accepted is not None
                else "no literal accepted/rejected pool outcome"
            ),
        }
        try:
            learning = {
                "pythia": _safe(self.orchestrator.pythia_status()),
                "memory": _safe(self.orchestrator.memory_status()),
                "agentic_intelligence": _safe(self.orchestrator.agentic_status()),
            }
            learn_state = "COMPLETE"
        except Exception as exc:
            learning = {"reason": f"{type(exc).__name__}: {exc}"}
            learn_state = "DEGRADED"
        stages["LEARN"] = {"state": learn_state, "evidence": learning}
        cycle["stages"] = stages
        cycle["completed_at"] = time.time()
        self.last_agentic_cycle = cycle

    def snapshot(self) -> dict[str, Any]:
        base = super().snapshot()
        base["agentic_mining"] = self.last_agentic_cycle
        base["agentic_architecture"] = {
            "canonical_live_writer": "GeodesicProductionMiningCoordinator / Stratum client",
            "production_planner": "AgenticMiningController",
            "pythia_authority": True,
            "research_workflow_submission_authority": False,
            "salamander_closed_loop": "wired by mining_runtime MiningAutonomyBridge",
            "trained_vqc_guidance": (
                "active only when PYTHIA_VQC_CHECKPOINT loads successfully; ordering only"
            ),
        }
        return base


__all__ = ["PythiaAgenticMiningAuthority", "SCHEMA"]