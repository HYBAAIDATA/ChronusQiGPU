"""Tononi/Penrose mathematical model shipped with PYTHAGORAS v12.

The values produced here are model outputs derived from AST graph statistics.
They are not measurements of physical gravitational decoherence and must not be
published as Mining operational telemetry without the explicit ``MODELED``
evidence class returned by this module.
"""

from __future__ import annotations

import math
from typing import Any, Dict


class TononiPenroseSubstrate:
    """Evaluate the v12 graph-integration/decoherence model."""

    @staticmethod
    def calculate_integrated_information(
        node_count: int,
        edge_count: int,
        depth: int,
    ) -> Dict[str, Any]:
        if node_count < 0 or edge_count < 0 or depth < 0:
            raise ValueError("node_count, edge_count, and depth must be non-negative")

        connectivity = edge_count / max(node_count * (node_count - 1), 1)
        phi_raw = round(math.log(max(depth, 1) + 1) * connectivity * 10.0, 6)

        e_gravitational_model = node_count * 1.618e-34
        hbar = 1.0545718e-34
        decoherence_model = round(
            hbar / max(e_gravitational_model, 1e-40),
            6,
        )

        return {
            "tononi_integrated_phi": phi_raw,
            "penrose_decoherence_time_sec": decoherence_model,
            "graph_connectivity": round(connectivity, 6),
            "evidence_class": "MODELED",
            "physical_measurement": False,
            "model_inputs": {
                "node_count": node_count,
                "edge_count": edge_count,
                "depth": depth,
            },
        }
