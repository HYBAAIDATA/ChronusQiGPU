"""Measured repetition-load stress; no random survival probabilities or asserted envelope coverage."""
from __future__ import annotations
import secrets
from ..substrate import engine


def stress_test(candidate, envelope, executor=None, noise_injection_steps=10, *,
                margin=1.5, challenge=None):
    if executor is None:
        return False, {'execution_kind': 'UNAVAILABLE', 'executor_invoked': False,
                       'failure_reasons': ['measured executor required']}
    if not engine.finite_number(margin) or margin < 1.5:
        raise ValueError('stress margin >=1.5 required')
    expected = candidate.discovery_envelope.scale_margin(margin).to_dict()
    if envelope.to_dict() != expected:
        raise ValueError('expanded envelope mismatch')
    result = executor.reproduce(candidate.reproduction_steps, challenge=challenge or secrets.token_hex(32),
        stress_factor=margin, candidate_fingerprint=candidate.compute_fingerprint(), expanded_envelope=expected)
    passed = result.observed
    # Actual CPU elapsed per trial must also fit the expanded decision budget.
    trials = result.details.get('trials', [])
    if (not engine.finite_number(envelope.compute_budget_sec) or envelope.compute_budget_sec <= 0
            or not trials or any(t['duration_ms'] / 1000 > envelope.compute_budget_sec for t in trials)):
        passed = False
    return passed, {'execution_kind': result.details['execution_kind'], 'executor_invoked': True,
        'candidate_id': candidate.candidate_id, 'expanded_envelope': expected,
        'tested_margin': margin, 'stress_axes': ['repetition_count', 'elapsed_compute_budget'],
        'untested_axes': ['noise_injection', 'observation_latency', 'parameter_bound_corners'],
        'execution': result.to_dict(), 'passed': passed}
