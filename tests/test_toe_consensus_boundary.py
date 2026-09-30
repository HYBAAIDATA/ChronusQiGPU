"""Consensus-boundary contract for the TOE causal signal.

A TOECausalSignal is feed-forward evidence: it may steer solver ordering and
gate dispatch, but it must never reach the double-SHA256 / target comparison.
These tests pin the two enforcement mechanisms in
``mla1517.mining.toe_signal``:

- ``boundary_token``: every signal carries a domain-separated SHA-256
  attestation bound to its feed-forward payload. A missing, malformed, or
  mismatched token fails ``is_valid()``, so the chooser/coordinator gates
  reject it (fail-closed).
- ``_assert_no_consensus_fields``: ``build_toe_signal`` refuses any TOE
  result carrying consensus-domain vocabulary (target, nonce, header,
  sha256d, ...) instead of sanitising it.
"""

import asyncio
import dataclasses
import struct
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

_PLATFORM = (
    Path(__file__).resolve().parent.parent
    / "mla1517_platform_v3.4"
    / "python"
)
if str(_PLATFORM) not in sys.path:
    sys.path.insert(0, str(_PLATFORM))

from manifold_pool_coordinator import PoolEndpoint  # noqa: E402
import mla1517.mining.pow as pow_module  # noqa: E402
from mla1517.hardware import VaultRecord  # noqa: E402
from mla1517.mining.chooser import MiningIntelligenceChooser  # noqa: E402
from mla1517.mining.coordinator import IntelligentPoolCoordinator  # noqa: E402
from mla1517.mining.solver import M32SearchSolver  # noqa: E402
from mla1517.mining.toe_adapter import TOEMiningContext  # noqa: E402
from mla1517.mining.toe_signal import (  # noqa: E402
    TOECausalSignal,
    TOEConsensusBoundaryError,
    build_toe_signal,
    lucas_ladder_status,
)


def _context(result) -> TOEMiningContext:
    return TOEMiningContext(
        job_id="job-boundary",
        node_id=3,
        sequence=1,
        result=result,
        execution_evidence={"backend": "stub"},
    )


def _clean_result() -> dict:
    return {
        "state_tomography": {"coherence": 0.9, "entropy": 0.4, "energy": 1.0},
        "trajectory_prediction": {
            "trend": "stable",
            "trend_rate": 0.1,
            "intervention_points": [
                {"time": 1.7, "fisher_info": 1.0, "is_optimal": True}
            ],
        },
    }


def _record() -> VaultRecord:
    return VaultRecord(
        node_id=3,
        sequence=1,
        state=struct.pack("<Q14I", 9, *([0] * 8), 1, 0, 0, 0, 0, 0),
    )


def test_every_signal_carries_valid_attestation():
    signal = build_toe_signal(_context(_clean_result()))
    assert signal.boundary_token.startswith("TOE-BND-")
    assert signal.boundary_token == signal.boundary_attestation()
    assert signal.is_valid()


def test_missing_or_tampered_token_fails_closed():
    # A forged token that does not match the payload is rejected. (An empty
    # token cannot survive construction — __post_init__ re-attests it.)
    forged = dataclasses.replace(
        build_toe_signal(_context(_clean_result())),
        boundary_token="TOE-BND-forged",
    )
    assert not forged.is_valid()

    # A non-string token is rejected too (no exception path, just False).
    malformed = dataclasses.replace(
        build_toe_signal(_context(_clean_result())), boundary_token=12345
    )
    assert not malformed.is_valid()

    # Mutating a payload field behind the token's back also fails closed.
    tampered = build_toe_signal(_context(_clean_result()))
    object.__setattr__(tampered, "face_bias", 5)
    assert tampered.boundary_token != tampered.boundary_attestation()
    assert not tampered.is_valid()

    # An invalid signal is a wiring no-op: the chooser must not apply it.
    solver = M32SearchSolver()
    solver.set_lane_start_offset(4)
    MiningIntelligenceChooser().choose(
        has_job=True, toe_signal=forged, solver=solver
    )
    assert solver.get_lane_start_offset() == 4


def test_consensus_vocabulary_in_result_fails_closed():
    for key in (
        "target", "nonce", "header", "sha256d", "share",
        "valid_hash", "share_valid", "pool_accepted", "block_confirmed",
    ):
        result = _clean_result()
        result["state_tomography"][key] = "0xdeadbeef"
        with pytest.raises(TOEConsensusBoundaryError):
            build_toe_signal(_context(result))
    # Deeply nested keys are rejected too, not just the top level.
    result = _clean_result()
    result["causal_analysis"] = {"edges": [{"block_header": "x"}]}
    with pytest.raises(TOEConsensusBoundaryError):
        build_toe_signal(_context(result))


def test_signal_declares_no_consensus_fields():
    field_names = {f.name for f in dataclasses.fields(TOECausalSignal)}
    forbidden = {
        "target", "bits", "nonce", "header", "block_header", "share",
        "difficulty", "sha256", "sha256d", "pow", "proof", "merkle_root",
        "block_hash", "extranonce", "extranonce2", "coinbase", "ntime",
        "submission", "candidate", "valid_hash", "share_valid",
        "pool_accepted", "block_confirmed",
    }
    assert field_names.isdisjoint(forbidden)


def test_ladder_attachment_preserves_attestation():
    """The coordinator attaches ladder via dataclasses.replace; the token
    deliberately excludes the advisory ladder field, so it stays valid."""
    signal = build_toe_signal(_context(_clean_result()))
    attached = dataclasses.replace(
        signal, ladder=lucas_ladder_status([0, 1, 1, 2, 3, 5])
    )
    assert attached.ladder is not None
    assert attached.boundary_token == signal.boundary_token
    assert attached.is_valid()


def test_consensus_path_never_reached_through_signal_pipeline():
    """Monkeypatch the consensus primitives to raise, then run the full
    signal path — build, boundary scan, chooser wiring, and a throttled
    coordinator dispatch — and prove none of them are ever invoked."""
    boom = AssertionError("consensus primitive reached from the TOE path")
    coord = IntelligentPoolCoordinator(
        [PoolEndpoint("127.0.0.1", 3333, "stub")], username="u", password="x"
    )
    job = SimpleNamespace(
        job_id="job-boundary",
        params=("job-boundary", "00" * 32, "cb1", "cb2"),
        received_at=1.0,
    )
    coord.client = SimpleNamespace(latest_job=lambda: job)
    torn = _clean_result()
    torn["state_tomography"]["entropy"] = 4.5  # derive causal_throttle=True
    coord.toe = SimpleNamespace(
        analyse=lambda **kwargs: _context(torn)
    )
    with mock.patch.object(pow_module, "sha256d", side_effect=boom), \
         mock.patch.object(pow_module, "check_pow", side_effect=boom), \
         mock.patch.object(pow_module, "compact_target", side_effect=boom):
        accepted = asyncio.run(coord.submit_record(_record()))
    assert accepted is False
    assert coord.last_toe_signal is not None
    assert coord.last_toe_signal.is_valid()
    assert coord.mining_intelligence.throttle is True


def test_poisoned_result_produces_no_signal_and_no_crash():
    """Fail-closed through the pipeline: a TOE result carrying a consensus
    key yields no signal, a warning, and the measured default contract."""
    coord = IntelligentPoolCoordinator(
        [PoolEndpoint("127.0.0.1", 3333, "stub")], username="u", password="x"
    )
    job = SimpleNamespace(
        job_id="job-poisoned",
        params=("job-poisoned", "00" * 32, "cb1", "cb2"),
        received_at=1.0,
    )
    coord.client = SimpleNamespace(latest_job=lambda: job)
    poisoned = _clean_result()
    poisoned["trajectory_prediction"]["target"] = "0xff"
    coord.toe = SimpleNamespace(analyse=lambda **kwargs: _context(poisoned))
    accepted = asyncio.run(coord.submit_record(_record()))
    assert accepted is False
    assert coord.last_toe_signal is None
    assert coord.mining_intelligence.throttle is False
    assert coord.solver.get_lane_start_offset() == 0
