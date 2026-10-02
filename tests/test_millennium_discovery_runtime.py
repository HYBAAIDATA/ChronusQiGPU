"""Tests for the governed Millennium -> discovery-engine composition root."""

from __future__ import annotations

import asyncio

import pytest

from millennium.discovery_runtime import run_discovery_campaign


class _FakeSuite:
    last_instance = None

    def __init__(self, scale="standard"):
        self.scale = scale
        self.asserted = False
        self.only = None
        type(self).last_instance = self

    def run(self, only=None):
        self.only = only
        result = {
            "problem_id": "riemann",
            "problem": "Riemann Hypothesis",
            "clay_status": "OPEN",
            "evidence_class": "FINITE_RANGE_OBSERVATION",
            "established_scope": None,
            "honest_conclusion": "bounded residual series only",
            "proof_claim": False,
            "probe_work_units": 20,
            "probe_dimension": 20,
            "rh_bound_normalised_residual": [0.1, 0.05, 0.025],
        }
        return {
            "results": [result],
            "summary": [
                {
                    "problem_id": "riemann",
                    "proof_claim": False,
                    "evidence_class": "FINITE_RANGE_OBSERVATION",
                    "established_scope": None,
                }
            ],
        }

    def assert_no_established(self, report):
        assert report["summary"][0]["proof_claim"] is False
        self.asserted = True
        return True


class _FakeEngine:
    def __init__(self, output=None):
        self.output = output or {
            "discoveries_by_frontier": {"spectral": [{"candidate": "C1"}]},
            "theoretical_insights": [],
        }
        self.calls = []

    async def deep_mathematical_exploration(self, payloads, max_depth=10):
        self.calls.append((payloads, max_depth))
        return self.output


def test_riemann_probe_is_wired_to_discovery_engine_with_boundary():
    engine = _FakeEngine()
    report = asyncio.run(
        run_discovery_campaign(
            "riemann",
            scale="standard",
            max_depth=4,
            engine_factory=lambda: engine,
            suite_factory=_FakeSuite,
        )
    )

    suite = _FakeSuite.last_instance
    assert suite.only == ["riemann"]
    assert suite.asserted is True
    assert len(engine.calls) == 1
    payloads, depth = engine.calls[0]
    assert depth == 4
    assert payloads[0]["problem_id"] == "riemann"
    assert payloads[0]["series"] == [0.1, 0.05, 0.025]
    assert report["candidate_count"] == 1
    assert report["claim_boundary"]["status"] == "CANDIDATE_GENERATION_ONLY"
    assert report["claim_boundary"]["proof_claim"] is False
    assert len(report["campaign"]["input_sha256"]) == 64


def test_discovery_output_cannot_escalate_itself_to_proof():
    engine = _FakeEngine(output={"theorem_proven": True})
    with pytest.raises(RuntimeError, match="claim-boundary violation"):
        asyncio.run(
            run_discovery_campaign(
                "riemann",
                engine_factory=lambda: engine,
                suite_factory=_FakeSuite,
            )
        )


def test_invalid_problem_and_depth_fail_before_exploration():
    with pytest.raises(ValueError, match="unknown problem"):
        asyncio.run(run_discovery_campaign("not_a_problem"))
    with pytest.raises(ValueError, match="max_depth"):
        asyncio.run(run_discovery_campaign("riemann", max_depth=0))


def test_real_mathematical_engine_is_now_an_imported_runtime_dependency():
    from millennium.discovery_runtime import _default_engine_factory
    from millennium.mathematical_discovery import MathematicalDiscoveryEngine

    # Pin the production composition edge without executing the expensive run.
    assert _default_engine_factory.__module__ == "millennium.discovery_runtime"
    assert MathematicalDiscoveryEngine.__name__ == "MathematicalDiscoveryEngine"
