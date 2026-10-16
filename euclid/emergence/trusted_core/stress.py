"""Stress testing suite for evaluating candidates outside their discovery envelope."""

from __future__ import annotations
import random
from typing import Tuple, Dict, Any, Optional

from ..models.candidate import EmergentCandidate, DiscoveryEnvelope
from ..substrate.executors import BaseExecutor


def stress_test(
    candidate: EmergentCandidate,
    envelope: DiscoveryEnvelope,
    executor: Optional[BaseExecutor] = None,
    noise_injection_steps: int = 10,
) -> Tuple[bool, Dict[str, Any]]:
    failure_reasons = []
    stress_metrics = {}

    effective_latency = envelope.max_observation_latency
    stress_metrics["tested_latency_ms"] = effective_latency
    if effective_latency > 5000.0:
        failure_reasons.append(f"Latency stress threshold exceeded: {effective_latency}ms")

    noise_tested = envelope.noise_tolerance
    stress_metrics["tested_noise_tolerance"] = noise_tested
    simulated_survivals = 0

    rng = random.Random(candidate.candidate_id.__hash__() & 0xFFFFFFFF)
    for _ in range(noise_injection_steps):
        perturbation = rng.uniform(0.0, noise_tested)
        if perturbation <= 0.80 or rng.random() > (perturbation - 0.70):
            simulated_survivals += 1

    survival_rate = simulated_survivals / max(1, noise_injection_steps)
    stress_metrics["noise_survival_rate"] = survival_rate
    if survival_rate < 0.70:
        failure_reasons.append(
            f"Noise resilience collapsed under expanded envelope (survival={survival_rate:.2f} < 0.70)"
        )

    stress_metrics["compute_budget_sec"] = envelope.compute_budget_sec
    if envelope.compute_budget_sec <= 0.001:
        failure_reasons.append("Unrealistically compressed compute budget under margin expansion")

    passed = len(failure_reasons) == 0
    details = {
        "execution_kind": "SIMULATED",
        "executor_invoked": False,
        "candidate_id": candidate.candidate_id,
        "expanded_envelope": envelope.to_dict(),
        "stress_metrics": stress_metrics,
        "failure_reasons": failure_reasons,
        "passed": passed,
    }

    return passed, details
