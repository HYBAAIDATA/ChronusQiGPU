"""Target: production_hr_api-v2.py backend + search workload on multi-GPU.

Every claim from the spec is either implemented honestly under its real name
or refused in code. No silent 'quantum' relabeling.
"""

from __future__ import annotations

import os
import sys

# Ensure package roots are in sys.path
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_REPO_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from chronus.tensor.enhanced_representation import (
    Bond,
    BondStructure,
    Config,
    ContractionCertificate,
    ContractionTree,
    EnhancedTensorRepresentation,
    ErrorLedger,
    SearchResult,
    ShardPlan,
    TruncationRecord,
    build_search_index,
    execute_sharded_contraction,
    plan_gpu_shards,
    search,
    search_contraction_trees,
    select_best_tree,
    topology_formula,
    _create_bond_structure,
    _create_entanglement_map,
    _initialize_tensor_network,
    claim_superposition_speedup,
    parallel_evaluate,
)
from chronus.service.production_hr_api_v2 import app

__all__ = [
    "Config",
    "Bond",
    "BondStructure",
    "ContractionCertificate",
    "ContractionTree",
    "ErrorLedger",
    "SearchResult",
    "ShardPlan",
    "TruncationRecord",
    "EnhancedTensorRepresentation",
    "_initialize_tensor_network",
    "_create_entanglement_map",
    "_create_bond_structure",
    "topology_formula",
    "search_contraction_trees",
    "select_best_tree",
    "parallel_evaluate",
    "claim_superposition_speedup",
    "build_search_index",
    "search",
    "plan_gpu_shards",
    "execute_sharded_contraction",
    "app",
]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("production_hr_api-v2:app", host="0.0.0.0", port=8000, reload=False)
