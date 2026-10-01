# l_hras/intelligences/predictive.py

import numpy as np
from dataclasses import dataclass
from typing import List
from l_hras.experimental.blueprint.core.types import Distribution

@dataclass
class PredictionModel:
    horizon: int
    features: List[str]
    weights: np.ndarray
    threshold: float
    attestation: str

def predict(model: PredictionModel, telemetry: dict) -> Distribution:
    """Predict the threat level."""
    x = np.array([telemetry.get(f, 0.0) for f in model.features])
    logits = float(np.dot(model.weights, x))
    prob = 1 / (1 + np.exp(-logits))  # sigmoid
    return Distribution(
        mean=prob,
        stddev=0.1,
        samples=len(telemetry),
        p50=prob,
        p95=min(prob * 1.2, 1.0),
        p99=min(prob * 1.5, 1.0),
    )
