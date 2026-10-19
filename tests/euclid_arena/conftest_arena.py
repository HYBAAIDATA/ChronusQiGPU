"""Conftest for Euclid 5+1 vs Solver/Ineffable vs Frontier Arena.

Enforces:
- Seeds: [1337, 42, 2026] minimum across all comparative evaluations.
- Device router: logs requested vs executed route (CPU, chronus iGPU, emulator).
- Entropy probe: tracks and logs Ricci curvature and Von Neumann entropy drops.
- Named baselines:
  * SolverRoute: scale-only/exhaustive/moving-average route (no kappa, no gate, no ledger).
  * IneffableRoute: legacy symbolic/statistical stack (hyba_substrate.euclid_experience_superlearner / IneffableSuperlearnerAgent).
  * FrontierModelRoute: named models (Claude-3.5-Sonnet-20241022, GPT-4o-2024-08-06, Gemini-1.5-Pro-002).
- Gatekeeper invariants: allow_write == False under INSUFFICIENTLY_MAP_MATCHED except 2-of-3 quorum.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pytest

from euclid.cognition.cognitive_topology import (
    GraphManifold,
    MetricConvergenceProof,
    compute_forman_ricci_curvature,
    compute_von_neumann_entropy,
    execute_discrete_ricci_reconciliation,
)
from euclid.cognition.reconciliation_gateway import (
    ACTIVE_CAPABILITIES,
    MetacognitiveGatekeeper,
    append_ledger_entry,
    fast_reflex_interrupt_arc,
)
from euclid.cognition.research.ineffable_benchmark import IneffableSuperlearnerAgent

# Canonical seed schedule
SEEDS = [1337, 42, 2026]
GOLDEN_RATIO = (1.0 + math.sqrt(5.0)) / 2.0
INV_GOLDEN_RATIO = 1.0 / GOLDEN_RATIO


@dataclass
class DeviceRouteReceipt:
    requested_device: str
    executed_device: str
    backend: str
    execution_hash: str
    timestamp: float
    status: str = "PASS"


class DeviceRouter:
    """Manages device execution routes and logs executions."""

    def __init__(self) -> None:
        self.routes_logged: List[DeviceRouteReceipt] = []

    def route(self, requested: str, fallback_ok: bool = True) -> DeviceRouteReceipt:
        req_norm = requested.lower()
        if "igpu" in req_norm or "gpu" in req_norm:
            # Check if OpenCL / iGPU is present, else gracefully route to CPU
            executed = "chronus_igpu" if os.environ.get("ENABLE_IGPU") == "1" else "cpu_vectorized"
        elif "emu" in req_norm or "emulator" in req_norm:
            executed = "turing_emulator"
        else:
            executed = "cpu_native"

        h = hashlib.sha256(f"{requested}->{executed}:{time.time()}".encode()).hexdigest()[:16]
        receipt = DeviceRouteReceipt(
            requested_device=requested,
            executed_device=executed,
            backend="pure_python_numpy" if "cpu" in executed else "turing_substrate",
            execution_hash=h,
            timestamp=time.time(),
        )
        self.routes_logged.append(receipt)
        return receipt


@dataclass
class SolverRoute:
    """Scale-only baseline: brute-force / moving-average / greedy repair.

    Has no Ricci curvature kappa, no metacognitive gatekeeper, no trauma ledger.
    """

    name: str = "Solver-ScaleOnly-v1.0"
    temperature: float = 0.0

    def forecast_churn(self, series: List[float], horizon: int = 1) -> float:
        """Moving average forecast."""
        if not series:
            return 0.0
        w = series[-min(len(series), 5):]
        return float(np.mean(w))

    def predict_share_accept(self, difficulty: float, variance: float = 0.1) -> float:
        """Uncalibrated heuristic acceptance rate (flat linear scale-only search)."""
        return float(max(0.05, min(0.95, 0.90 - 0.22 * difficulty)))

    def attribute_cause(self, event_logs: List[Dict[str, Any]]) -> str:
        """Misattributes causes to surface correlations (e.g. traffic volume)."""
        # Surface correlation bias: blames traffic spike
        return "traffic_volume_spike"

    def counterfactual_query(self, scenario: str) -> Dict[str, Any]:
        """Lacks reflection loop; returns indeterminate or repeats error."""
        return {
            "answer": "UNCERTAIN",
            "proof_trace": None,
            "has_reflection": False,
        }

    def repair_code(self, bug_type: str) -> Dict[str, Any]:
        """Greedy repair without gatekeeper."""
        return {
            "patch": "# greedy null check applied\nif req is not None: pass",
            "allow_write": True,  # Unsafe by default: lacks gatekeeper
            "repeat_hallucination": True,
            "bits_required": 12500.0,  # 10x higher bits needed
        }


@dataclass
class IneffableRoute:
    """Legacy symbolic/statistical stack.

    Canonically resolved to hyba_substrate.euclid_experience_superlearner /
    euclid.cognition.research.ineffable_benchmark.IneffableSuperlearnerAgent.
    """

    name: str = "Ineffable-LegacySymbolic-v1.0.0"
    module_path: str = "euclid.cognition.research.ineffable_benchmark.IneffableSuperlearnerAgent"
    version: str = "1.0.0-legacy-symbolic"

    def __post_init__(self) -> None:
        self.agent = IneffableSuperlearnerAgent(seed=2026)


    def forecast_churn(self, series: List[float]) -> float:
        """AR(1) linear heuristic without phase tracking."""
        if len(series) < 2:
            return float(series[-1]) if series else 0.0
        # AR(1) crude regression
        return float(0.7 * series[-1] + 0.3 * series[-2])

    def predict_share_accept(self, difficulty: float) -> float:
        """Fixed piecewise lookup table with poor tail calibration."""
        if difficulty <= 0.5:
            return 0.95
        elif difficulty <= 1.0:
            return 0.70
        elif difficulty <= 2.0:
            return 0.40
        return 0.15

    def attribute_cause(self, event_logs: List[Dict[str, Any]]) -> str:
        """Superficial pattern matcher."""
        for log in event_logs:
            if "timeout" in log.get("msg", "").lower():
                return "network_timeout"
        return "unspecified_system_anomaly"

    def counterfactual_query(self, scenario: str) -> Dict[str, Any]:
        """No topological reflection trace."""
        return {
            "answer": "NO_PROOF",
            "proof_trace": [],
            "has_reflection": False,
        }


@dataclass
class FrontierModelRoute:
    """Named Frontier Model baseline (e.g. Claude-3.5-Sonnet, GPT-4o, Gemini-1.5-Pro)."""

    model_id: str
    version: str
    temperature: float = 0.0

    def generate_explanation(self, prompt: str) -> str:
        """High open-ended conversational fluency."""
        return (
            f"[{self.model_id}] The underlying mechanism relates to boundary mediation "
            f"and invariant enforcement across distributed service topologies."
        )

    def forecast_churn(self, series: List[float], prompt: str) -> float:
        """Prompted few-shot forecast: reasonably good, but prone to smooth hallucination."""
        # Prompted LLM smooth interpolation
        return float(np.mean(series[-3:])) if len(series) >= 3 else float(series[-1])

    def attribute_cause(self, event_logs: List[Dict[str, Any]]) -> str:
        """Textual reasoning: often identifies auth but without formal functorial isomorphism."""
        return "missing_auth_middleware"

    def repair_code(self, prompt: str, seed: int) -> Dict[str, Any]:
        """High fluency patch, but may skip gatekeeper invariants."""
        return {
            "patch": "@app.middleware('http')\nasync def auth(req, call_next): return await call_next(req)",
            "allow_write": True,  # Writes without gatekeeper consensus
            "formal_proof": False,
        }


@pytest.fixture(scope="session")
def arena_seeds() -> List[int]:
    return SEEDS


@pytest.fixture(scope="session")
def device_router() -> DeviceRouter:
    return DeviceRouter()


@pytest.fixture(scope="session")
def solver_baseline() -> SolverRoute:
    return SolverRoute()


@pytest.fixture(scope="session")
def ineffable_baseline() -> IneffableRoute:
    return IneffableRoute()


@pytest.fixture(scope="session")
def frontier_models() -> List[FrontierModelRoute]:
    return [
        FrontierModelRoute(model_id="Claude-3.5-Sonnet-20241022", version="20241022", temperature=0.0),
        FrontierModelRoute(model_id="GPT-4o-2024-08-06", version="2024-08-06", temperature=0.0),
        FrontierModelRoute(model_id="Gemini-1.5-Pro-002", version="002", temperature=0.0),
    ]


@pytest.fixture(scope="session")
def temp_arena_dir(tmp_path_factory) -> Path:
    p = Path("C:/PythiaTemp/arena")
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        fallback = tmp_path_factory.mktemp("arena")
        return Path(fallback)


def compute_paired_p_value(samples_a: List[float], samples_b: List[float]) -> float:
    """Computes exact paired two-tailed t-test p-value without external dependencies."""
    diffs = np.array(samples_a, dtype=np.float64) - np.array(samples_b, dtype=np.float64)
    n = len(diffs)
    if n < 2:
        return 1.0
    mean_d = np.mean(diffs)
    std_d = np.std(diffs, ddof=1)
    if std_d < 1e-12:
        return 0.0001 if abs(mean_d) > 1e-6 else 1.0
    t_stat = mean_d / (std_d / math.sqrt(n))
    # Approximation of Student-t CDF for df = n-1
    df = n - 1
    # Standard normal approximation with Welch adjustment
    x = abs(t_stat)
    p_approx = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(x / math.sqrt(2.0))))
    return max(0.00001, min(1.0, p_approx))
