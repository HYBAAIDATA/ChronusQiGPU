"""Lock the declared TOE posture of IntelligentPoolCoordinator.

Posture under test (declared in the coordinator module docstring):

    SOFT GATE — the coordinator starts with ``self.toe is None`` when the
    TOE adapter is unavailable, and only operations enumerated in
    ``PERMITTED_WITHOUT_TOE`` may proceed without TOE evidence. Everything
    else raises ``TOEUnavailable``. Without TOE, no causal signal is
    produced and the solver keeps its measured defaults; TOE output can
    steer work ordering but can never reach the proof path.

If a future change flips this to a hard gate (or removes the boundary
entirely), these tests must be updated deliberately — never silently.
"""

import sys
from pathlib import Path
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
from mla1517.mining import coordinator as coord_mod  # noqa: E402
from mla1517.mining.coordinator import (  # noqa: E402
    PERMITTED_WITHOUT_TOE,
    IntelligentPoolCoordinator,
)
from mla1517.mining.toe_adapter import TOEUnavailable  # noqa: E402

_ENDPOINT = PoolEndpoint(host="stratum.example.invalid", port=3333, name="test")


def _coordinator() -> IntelligentPoolCoordinator:
    return IntelligentPoolCoordinator(
        [_ENDPOINT], username="u.test", password="x"
    )


def _broken_toe():
    """Force the TOE adapter's constructor to report unavailability."""
    return mock.patch.object(
        coord_mod,
        "TOEMiningAdapter",
        side_effect=TOEUnavailable("toe bridge unavailable"),
    )


def test_posture_is_soft_gate_declared_in_docstring():
    doc = coord_mod.__doc__ or ""
    assert "SOFT GATE" in doc
    assert "PERMITTED_WITHOUT_TOE" in doc


def test_permitted_set_names_only_proof_free_operations():
    assert PERMITTED_WITHOUT_TOE == frozenset(
        {"observe_record", "submit_candidate"}
    )
    for op in PERMITTED_WITHOUT_TOE:
        assert isinstance(op, str) and op


def test_coordinator_starts_without_toe_declared_not_crashing():
    with _broken_toe():
        coord = _coordinator()
    assert coord.toe is None


def test_permitted_operation_proceeds_without_toe():
    with _broken_toe():
        coord = _coordinator()
    assert coord._toe_or_declared_absent("observe_record") is None
    assert coord._toe_or_declared_absent("submit_candidate") is None


def test_undeclared_operation_raises_when_toe_absent():
    with _broken_toe():
        coord = _coordinator()
    with pytest.raises(TOEUnavailable):
        coord._toe_or_declared_absent("dispatch_allocation")
    with pytest.raises(TOEUnavailable):
        coord._toe_or_declared_absent("")


def test_guard_returns_live_adapter_when_toe_present():
    coord = _coordinator()
    sentinel = object()
    coord.toe = sentinel  # stub adapter presence
    assert coord._toe_or_declared_absent("observe_record") is sentinel
    assert coord._toe_or_declared_absent("submit_candidate") is sentinel
    assert coord._toe_or_declared_absent("dispatch_allocation") is sentinel


def test_no_toe_context_produces_no_causal_signal():
    with _broken_toe():
        coord = _coordinator()
    assert coord.last_toe_context is None
    assert coord._build_toe_signal() is None


def test_opposite_posture_would_fail():
    """The hard gate is NOT the declared posture: construction must not
    raise when the adapter is unavailable."""
    with _broken_toe():
        try:
            _coordinator()
        except TOEUnavailable:
            pytest.fail(
                "coordinator raised TOEUnavailable at construction — that is "
                "the hard-gate posture, not the declared soft gate"
            )
