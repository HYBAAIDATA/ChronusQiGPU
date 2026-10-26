"""EUCLID Cognitive Router (`src/api/routers/euclid_voice.py`).

Wires the Cognitive Reconciliation Report engine, the Metacognitive Gatekeeper,
the Split-Flight WebSocket Gateway, the Topological Knowledge Manifold, the
Cross-Domain Analogy Engine, the First Breath Runbook endpoints, and the Three
Provocation Experiments into the production FastAPI router.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from euclid.cognition.reconciliation_gateway import (
    ACTIVE_COGNITIVE_STATES,
    EPISODIC_MEMORY,
    GLOBAL_COGNITIVE_MANIFOLD,
    KNOWLEDGE_MANIFOLD,
    CrossDomainAnalogyEngine,
    ERNSpikePayload,
    MetacognitiveGatekeeper,
    ProvocationExperimentsSuite,
    generate_reconciliation_report,
    get_curriculum_sync,
    get_node_state,
    get_reflection_trace_sync,
    get_state_matrix_sync,
    get_widget_spec_sync,
    fast_reflex_interrupt_arc,
    process_ern_spike_signal,
    process_ern_spike_signal_sync,
    quorum_unlock_node,
    record_episodic_event,
)

router = APIRouter(prefix="/api/v1/euclid", tags=["Cognitive Engine"])


class ReconcileNodeRequest(BaseModel):
    user_id: str = "coach_prime"
    target_node: str
    remediation_constraint: str
    ricci_steps: int = 8


class AnalogyTransferRequest(BaseModel):
    source_node: str = "auth_module"
    error_signature: str = "Session token leak"
    target_domain: str = "dark_matter_decay"


@router.websocket("/voice/stream")
async def voice_stream_gateway(websocket: WebSocket, background_tasks: BackgroundTasks):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()

            # 1. Handle Interruption (ERN Spike) — Split-Flight Gateway
            if data.get("type") == "INTERRUPTION":
                payload = ERNSpikePayload(**data["payload"])
                # Fast reflex arc: lock-free capability quarantine (< 5ms)
                receipt = fast_reflex_interrupt_arc(payload)

                # Flight 1 (Reflex): Instant sub-200ms Audio Marker
                await websocket.send_json(
                    {
                        "stream_type": "AUDIO_MARKER",
                        "frame": "REFLEX_ENGAGED",
                        "text": "Hmm, let me trace that side-effect...",
                        "structural_acknowledgment": "Trace identified. Re-mapping topology now.",
                        "reflex_latency_ms": receipt.reflex_latency_ms,
                    }
                )

                # Flight 2 (Reflection): Commit ERN Spike & lock traumatized node
                process_ern_spike_signal_sync(payload)

            # 2. Handle Execution Request
            elif data.get("type") == "EXECUTION_REQUEST":
                node = str(data.get("target_node") or "")
                gate = MetacognitiveGatekeeper.verify_clearance_sync(node)

                if not gate["allow_write"]:
                    await websocket.send_json(
                        {
                            "stream_type": "VOCAL_OUTPUT",
                            "status": "BLOCKED",
                            "text": gate["verbal_fallback"],
                        }
                    )
                else:
                    await websocket.send_json(
                        {
                            "stream_type": "EXECUTION_GRANTED",
                            "status": "ALLOWED",
                            "reason": gate["reason"],
                        }
                    )

            # 3. Handle Reflection Loop / Manifold Reconciliation Request
            elif data.get("type") == "RECONCILE_REQUEST":
                node = str(data.get("target_node") or "")
                constraint = str(
                    data.get("remediation_constraint")
                    or f"Verified structural remap of {node}"
                )
                user_id = str(data.get("user_id") or "coach_prime")
                smoothed = KNOWLEDGE_MANIFOLD.reconcile_node_after_reflection(
                    target_node=node,
                    remediation_constraint=constraint,
                    user_id=user_id,
                )
                await websocket.send_json(
                    {
                        "stream_type": "RECONCILIATION_COMPLETE",
                        "status": "UNLOCKED",
                        "manifold": smoothed,
                    }
                )
            else:
                await websocket.send_json(
                    {"stream_type": "ERROR", "status": "INVALID_REQUEST",
                     "reason": "unsupported_message_type"}
                )
    except WebSocketDisconnect:
        return
    except Exception:
        # Never swallow an error and leave the peer waiting indefinitely.
        # No clearance is granted after a failed request.
        await websocket.close(code=1011)


@router.get("/learning/curriculum/{user_id}")
async def get_curriculum(user_id: str) -> Dict[str, Any]:
    return get_curriculum_sync(user_id)


@router.get("/ui/widget-spec")
async def get_widget_spec() -> Dict[str, Any]:
    spec = get_widget_spec_sync()
    spec["visual_states"] = {
        "GREEN": "Smooth Riemannian manifold (Homeostasis)",
        "RED": "Localized Ricci Curvature Spike (Trauma / Locked)",
        "GOLD": "Manifold smoothed back into equilibrium (Trauma-Hardened Mastery)",
    }
    return spec


@router.get("/state/matrix/{user_id}")
async def get_state_matrix(user_id: str) -> Dict[str, Any]:
    return get_state_matrix_sync(user_id)


@router.get("/learning/reflection-trace/{node_id}")
async def get_reflection_trace(node_id: str) -> Dict[str, Any]:
    return get_reflection_trace_sync(node_id)


@router.get("/validation/readiness")
async def get_validation_readiness() -> Dict[str, Any]:
    matrix = get_state_matrix_sync("coach_prime")
    ack = matrix["structural_acknowledgment"]
    no_apology_enforced = "sorry" not in ack.lower() and "apologize" not in ack.lower()
    return {
        "schema": "euclid.validation.readiness/1",
        "status": matrix["status"],
        "structural_acknowledgment": ack,
        "no_apology_rule_enforced": no_apology_enforced,
        "shannon_entropy_reduction": GLOBAL_COGNITIVE_MANIFOLD.calculate_real_entropy_reduction(),
        "entropy_bits": GLOBAL_COGNITIVE_MANIFOLD.calculate_cognitive_entropy(),
        "ricci_convergence_proof": GLOBAL_COGNITIVE_MANIFOLD.prove_ricci_convergence(),
        "episodic_ledger_path": "artifacts/research/episodic_memory.jsonl",
    }


@router.get("/manifold/status")
async def get_manifold_status() -> Dict[str, Any]:
    return KNOWLEDGE_MANIFOLD.snapshot()


@router.post("/reconcile")
async def reconcile_node(req: ReconcileNodeRequest) -> Dict[str, Any]:
    return KNOWLEDGE_MANIFOLD.reconcile_node_after_reflection(
        target_node=req.target_node,
        remediation_constraint=req.remediation_constraint,
        user_id=req.user_id,
        ricci_steps=req.ricci_steps,
    )


@router.post("/analogy/transfer")
async def transfer_analogy(req: AnalogyTransferRequest) -> Dict[str, Any]:
    engine = CrossDomainAnalogyEngine()
    return engine.transfer_trauma_to_science(
        source_node=req.source_node,
        error_signature=req.error_signature,
        target_domain=req.target_domain,
    )


class QuorumUnlockRequest(BaseModel):
    target_node: str
    signatures: List[Dict[str, str]] = Field(default_factory=list)
    reason: str = "Curator council quorum override"
    user_id: str = "curator_council"


QuorumUnlockRequest.model_rebuild()


@router.post("/quorum/unlock")
async def post_quorum_unlock(req: QuorumUnlockRequest) -> Dict[str, Any]:
    return quorum_unlock_node(
        target_node=req.target_node,
        signatures=req.signatures,
        reason=req.reason,
        user_id=req.user_id,
    )


@router.get("/experiments/run")
async def run_provocation_experiments() -> Dict[str, Any]:
    return ProvocationExperimentsSuite.run_all()


__all__ = [
    "ACTIVE_COGNITIVE_STATES",
    "EPISODIC_MEMORY",
    "ERNSpikePayload",
    "MetacognitiveGatekeeper",
    "generate_reconciliation_report",
    "get_curriculum",
    "get_node_state",
    "get_reflection_trace",
    "get_state_matrix",
    "get_validation_readiness",
    "get_widget_spec",
    "process_ern_spike_signal",
    "record_episodic_event",
    "router",
    "voice_stream_gateway",
]
