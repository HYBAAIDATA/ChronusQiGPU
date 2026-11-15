"""Root Entrypoint & Integration for Chronus HYBA Production HR API.

Implements and exposes the exact first-principles modules outlined in HYBA:
- EnhancedTensorRepresentation
- AdaptiveTensorContractionPathway
- CausalInterferenceEngine
- FastAPI Production Application (app)
"""

from __future__ import annotations

import sys
import os

# Ensure package roots are on sys.path
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_REPO_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from chronus.tensor.enhanced_representation import (
    EnhancedTensorRepresentation,
    TensorNetworkNDArray,
)
from chronus.tensor.adaptive_contraction import (
    AdaptiveTensorContractionPathway,
)
from chronus.tensor.causal_intelligence import (
    CausalInterferenceEngine,
)
from chronus.service.production_hr_api import app

__all__ = [
    "EnhancedTensorRepresentation",
    "TensorNetworkNDArray",
    "AdaptiveTensorContractionPathway",
    "CausalInterferenceEngine",
    "app",
]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("production_hr_api:app", host="0.0.0.0", port=8000, reload=False)
