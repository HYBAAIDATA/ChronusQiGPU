"""Production HR API v2: Classical Block-Sparse Tensor Network Backend & Multi-GPU Search.

Target: production_hr_api-v2.py backend + search workload on multi-GPU.
Every claim from the spec is either implemented honestly under its real name
or refused in code. No silent 'quantum' relabeling.

Implements:
- PART 0: Charter enforcement & forbidden claim refusals
- PART 1: Strict Config, Bond, Node, ErrorLedger, SearchResult types
- PART 2: _initialize_tensor_network & _create_bond_structure
- PART 3: Contraction planner (search_contraction_trees, select_best_tree)
- PART 4: Search workload (build_search_index, search)
- PART 5: Multi-GPU sharding (plan_gpu_shards, execute_sharded_contraction)
- PART 6: API endpoints (POST /api/v1/quantum/tensor-representation, POST /api/v1/search)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

from chronus.tensor.enhanced_representation import (
    Config,
    ErrorLedger,
    SearchResult,
    build_search_index,
    plan_gpu_shards,
    search,
    topology_formula,
    _create_bond_structure,
    _initialize_tensor_network,
    HARD_CAP,
)
from chronus import __version__ as _CHRONUS_VERSION

logger = logging.getLogger("ProductionHRAPIv2")

app = FastAPI(
    title="Chronus Production HR API v2 (Classical Tensor Network Backend)",
    version=_CHRONUS_VERSION,
    description="Honest classical block-sparse tensor network engine with audited bounds and multi-GPU sharding.",
)

# In-memory document search index
_default_cfg = Config(
    n_sites=6,
    topology="MPS",
    chi_max=64,
    charge_group="U(1)",
    target_dim=6,
    device="cpu",
    gpu_shard_policy="shard_bonds",
)
_search_index = build_search_index(
    documents=[
        {"id": "doc_hr_001", "features": [0.8, 0.2, 0.9, 0.4, 0.1, 0.7]},
        {"id": "doc_hr_002", "features": [0.1, 0.9, 0.2, 0.8, 0.7, 0.3]},
        {"id": "doc_hr_003", "features": [0.5, 0.5, 0.6, 0.4, 0.5, 0.5]},
    ],
    cfg=_default_cfg,
)


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------


class TensorRepresentationRequest(BaseModel):
    target_dim: int = Field(default=6, ge=2, description="Target feature dimension depth (n sites)")
    topology: str = Field(default="MPS", description="Network topology: MPS, MPO, PEPS, MERA")
    chi_max: int = Field(default=64, ge=1, le=26214, description="Maximum bond dimension cap")
    charge_group: str = Field(default="U(1)", description="Symmetry charge sector: none, Z2, U(1), SU(2)")
    device: str = Field(default="cuda:0", description="Target hardware compute device")
    shard_policy: str = Field(default="shard_bonds", description="GPU shard policy: replicate, shard_bonds, shard_sites")
    budget_bytes: int = Field(default=1024 * 1024 * 1024, description="Peak contraction planner memory budget")


class SearchRequest(BaseModel):
    query: Dict[str, Any] = Field(..., description="Query dictionary containing 'features' vector")
    top_k: int = Field(default=5, ge=1, le=100, description="Top K items to return")


class DocumentBatchRequest(BaseModel):
    documents: List[Dict[str, Any]] = Field(..., description="List of document dicts with 'id' and 'features'")


# -----------------------------------------------------------------------------
# API Endpoints (PART 6)
# -----------------------------------------------------------------------------


@app.get("/health", response_model=Dict[str, Any])
def health() -> Dict[str, Any]:
    return {
        "status": "HEALTHY",
        "service": "ProductionHRAPIv2",
        "engine": "classical_block_sparse_tensor_network",
        "is_quantum": False,
        "indexed_documents": len(_search_index.documents),
    }


@app.post("/api/v1/quantum/tensor-representation", response_model=Dict[str, Any])
def handle_post_tensor_representation(req: TensorRepresentationRequest) -> Dict[str, Any]:
    """PART 6: POST /api/v1/quantum/tensor-representation.

    Response is honest: method is classical, latency is measured, error is bound.
    """
    cfg = Config(
        n_sites=req.target_dim,
        topology=req.topology,
        chi_max=req.chi_max,
        charge_group=req.charge_group,
        target_dim=req.target_dim,
        device=req.device,
        gpu_shard_policy=req.shard_policy,
        planner_budget_bytes=req.budget_bytes,
    )

    if cfg.chi_max > HARD_CAP(cfg.device):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requested chi_max={cfg.chi_max} exceeds hardware hard cap {HARD_CAP(cfg.device)}",
        )

    t0_ns = time.perf_counter_ns()
    network = _initialize_tensor_network(cfg)
    bonds = _create_bond_structure(network, cfg)
    # Target available compute devices
    available_devices = [req.device] if req.device != "cpu" else ["cpu"]
    plan = plan_gpu_shards(network, available_devices, cfg.gpu_shard_policy)
    t1_ns = time.perf_counter_ns()
    measured_latency_ms = (t1_ns - t0_ns) / 1_000_000.0

    max_possible_bonds = cfg.n_sites * (cfg.n_sites - 1) // 2
    density = len(bonds.bonds) / max(1, max_possible_bonds)

    return {
        "network_id": id(network),
        "topology": cfg.topology,
        "n_sites": cfg.n_sites,
        "chi_max": cfg.chi_max,
        "bond_structure_density": round(density, 4),
        "memory_bound_bytes": topology_formula(cfg.topology, cfg.n_sites, cfg.chi_max),
        "shard_plan": plan.as_dict(),
        "measured_latency_ms": round(measured_latency_ms, 4),
        "method": "classical_tensor_network",
        "is_quantum": False,  # MANDATORY
        "error_bound": getattr(network, "ledger", ErrorLedger()).global_bound,
        "refused_claims": [
            "0.01ms latency",
            "708x speedup",
            "100X information density",
        ],
    }


@app.get("/api/v1/quantum/tensor-representation")
def handle_get_tensor_representation() -> Response:
    """State-changing endpoint; refuse GET with 405 Method Not Allowed."""
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="State-changing endpoint; use POST.",
    )


@app.post("/api/v1/search", response_model=Dict[str, Any])
def handle_post_search(req: SearchRequest) -> Dict[str, Any]:
    """PART 4: Search workload via classical tensor network inner product."""
    res: SearchResult = search(query=req.query, index=_search_index, top_k=req.top_k)
    return {
        "ids": res.ids,
        "scores": res.scores.tolist(),
        "method": res.method,
        "is_quantum": res.is_quantum,  # MANDATORY False
        "error_bound": res.error_bound,
        "latency_ms": res.latency_ms,  # MEASURED, not claimed
        "refused_claims": [
            "0.01ms latency",
            "708x speedup",
            "100X information density",
        ],
    }


@app.post("/api/v1/documents/index", response_model=Dict[str, Any])
def handle_index_documents(req: DocumentBatchRequest) -> Dict[str, Any]:
    """Index new documents into the multi-GPU classical search index."""
    global _search_index
    _search_index = build_search_index(documents=req.documents, cfg=_default_cfg)
    return {
        "status": "INDEXED",
        "indexed_count": len(_search_index.documents),
        "is_quantum": False,
        "method": "classical_tensor_network",
    }
