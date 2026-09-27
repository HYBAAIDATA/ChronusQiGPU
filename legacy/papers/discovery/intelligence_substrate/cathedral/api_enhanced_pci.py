"""
CATHEDRAL PILLAR 6: RESTFUL API & HEALTH MONITORING
===================================================
Restored from Cathedral AI System architecture.
Exposes clean FastAPI endpoints with Pydantic validation for code emergence,
causal blockchain analysis, quantum dodecahedral walks, and health monitoring.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from python_backend.cathedral.intrinsic_ai import IntrinsicAIOrchestrator

cathedral_router = APIRouter(prefix="/cathedral", tags=["Cathedral AI System"])

_orchestrator = IntrinsicAIOrchestrator()


class CodeAnalysisRequest(BaseModel):
    source_code: str = Field(..., description="Python source code string to analyze")
    filename: Optional[str] = Field(default="<interactive>", description="Optional filename")


class BlockchainBlockInput(BaseModel):
    height: int
    timestamp: int
    difficulty: float
    nonce: int
    tx_count: int
    block_hash: str


class BlockchainBatchRequest(BaseModel):
    blocks: List[BlockchainBlockInput]


class QuantumSearchRequest(BaseModel):
    target_vertex: int = Field(..., ge=0, le=19, description="Target vertex in [0, 19]")
    iterations: int = Field(default=2, ge=1, le=10, description="Grover search iterations")


class OrchestrationCycleRequest(BaseModel):
    source_code: Optional[str] = None
    blocks: Optional[List[BlockchainBlockInput]] = None
    target_vertex: int = 0


@cathedral_router.post("/analyze-code", summary="Emergent Intelligence from Code Complexity")
def analyze_code_emergence(request: CodeAnalysisRequest) -> Dict[str, Any]:
    """Parse AST complexity and build emergent neural causal graph."""
    res = _orchestrator.code_pci.analyze_source(request.source_code, filename=request.filename)
    if "causal_graph" in res:
        # Exclude raw numpy arrays for clean JSON serialization
        del res["causal_graph"]
    return res


@cathedral_router.post("/blockchain-causal", summary="Blockchain Causal Inference & Phi Resonance")
def analyze_blockchain_causality(request: BlockchainBatchRequest) -> Dict[str, Any]:
    """Ingest blockchain telemetry and compute time-lagged causal chains."""
    for b in request.blocks:
        _orchestrator.blockchain_causal.ingest_block(
            height=b.height,
            timestamp=b.timestamp,
            difficulty=b.difficulty,
            nonce=b.nonce,
            tx_count=b.tx_count,
            block_hash=b.block_hash,
        )
    links = _orchestrator.blockchain_causal.compute_causal_chains()
    prediction = _orchestrator.blockchain_causal.predict_next_state()
    return {
        "blocks_ingested": len(request.blocks),
        "total_history_size": len(_orchestrator.blockchain_causal.history),
        "causal_links": [vars(l) for l in links],
        "prediction": prediction,
    }


@cathedral_router.post("/quantum-dodecahedron", summary="Dodecahedral Quantum Grover Search")
def run_quantum_search(request: QuantumSearchRequest) -> Dict[str, Any]:
    """Execute Grover quantum search over 20-vertex dodecahedral geometry."""
    try:
        psi, prob = _orchestrator.quantum_miner.grover_dodecahedral_search(
            target_vertex=request.target_vertex,
            iterations=request.iterations,
        )
        chosen_vertex, confidence = _orchestrator.quantum_miner.observer_coupling_reduction(psi)
        return {
            "target_vertex": request.target_vertex,
            "target_probability": prob,
            "observer_collapsed_vertex": chosen_vertex,
            "observer_confidence": confidence,
            "geometry": "REGULAR_DODECAHEDRON_20_VERTICES",
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@cathedral_router.post("/self-improvement", summary="Code Intelligence Improvement Proposals")
def inspect_code_improvements(request: CodeAnalysisRequest) -> Dict[str, Any]:
    """Scan code for complexity hotspots and emit safe refactoring proposals."""
    proposals = _orchestrator.optimizer.inspect_and_propose(
        request.source_code, filename=request.filename
    )
    return {
        "proposals_count": len(proposals),
        "proposals": [vars(p) for p in proposals],
        "evolution_metrics": _orchestrator.optimizer.get_evolution_metrics(),
    }


@cathedral_router.post("/orchestrate-cycle", summary="Multi-Modal Cathedral Synthesis Cycle")
def execute_orchestration_cycle(request: OrchestrationCycleRequest) -> Dict[str, Any]:
    """Synthesize code emergence, blockchain causality, and quantum search into unified state."""
    raw_blocks = [b.dict() for b in request.blocks] if request.blocks else None
    state = _orchestrator.orchestrate_cycle(
        sample_code=request.source_code,
        block_telemetry_batch=raw_blocks,
        target_quantum_sector=request.target_vertex,
    )
    return vars(state)


@cathedral_router.get("/health", summary="Cathedral System Health & Metrics")
def cathedral_health() -> Dict[str, Any]:
    """Comprehensive status and metrics endpoint for Cathedral."""
    return _orchestrator.get_status_summary()
