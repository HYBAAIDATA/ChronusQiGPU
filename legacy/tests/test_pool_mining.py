"""Tests for pool-aware mining (full_prompt.md Step 7.1 / 7.3).

Validates the pool profiles, the "no pool = no mining" safety gate,
Lucas-scaled scheduling, the incremental scaling ladder, and the
non-bypassable hard-cap reconciliation: the pool ceilings are policy inputs,
``ABSOLUTE_HARD_CAP_EHS`` (20 EH/s) is the boundary.
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PYTHIA_DIR = os.path.dirname(_THIS_DIR)

for p in (_PYTHIA_DIR, os.path.abspath(".")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from Intelligence.pool_aware_miner import (
    ABSOLUTE_HARD_CAP_EHS,
    CANONICAL_SCALE_INDICES,
    PoolAwareMiner,
    PoolConfig,
    PoolType,
    POOL_CONFIGS,
    START_N,
    lucas_bound,
)
from lucas.core import lucas

# ---------------------------------------------------------------------------
# Pool profile specification (Step 7.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pool,ceiling,max_n",
    [
        (PoolType.CKPOOL, 300.0, 50),
        (PoolType.NICEHASH, 20.0, 45),
        (PoolType.BRAIINS, 20.0, 45),
    ],
)
def test_pool_configs_match_spec(pool, ceiling, max_n):
    config = POOL_CONFIGS[pool]
    assert config.ceiling_ehs == ceiling
    assert config.start_ehs == 1.32
    assert config.start_n == START_N
    assert config.max_n == max_n


def test_all_three_pools_declared():
    assert set(POOL_CONFIGS) == {PoolType.CKPOOL, PoolType.NICEHASH, PoolType.BRAIINS}


def test_lucas_numbers_are_exact():
    assert lucas(10) == 123
    assert lucas(12) == 322
    assert lucas(15) == 1364
    assert lucas(18) == 5778
    assert lucas(20) == 15127


# ---------------------------------------------------------------------------
# Safety gate: no pool = no mining
# ---------------------------------------------------------------------------


def test_start_refused_when_disconnected():
    miner = PoolAwareMiner()
    assert miner.status()["safety_gate"] == "closed"
    with pytest.raises(RuntimeError, match="no pool = no mining"):
        miner.start()


@pytest.mark.parametrize("action", ["scale_to", "scale_up", "scale_down"])
def test_scaling_refused_when_disconnected(action):
    miner = PoolAwareMiner()
    with pytest.raises(RuntimeError, match="no pool = no mining"):
        if action == "scale_to":
            miner.scale_to(15)
        else:
            getattr(miner, action)()


def test_stop_is_legal_when_disconnected():
    miner = PoolAwareMiner()
    assert miner.stop() == {"running": False}


# ---------------------------------------------------------------------------
# Connect / disconnect lifecycle
# ---------------------------------------------------------------------------


def test_connect_opens_gate_and_starts_at_start_point():
    miner = PoolAwareMiner()
    result = miner.connect(PoolType.BRAIINS)
    assert result["connected"] == "braiins"
    st = miner.status()
    assert st["connected"] is True
    assert st["safety_gate"] == "open"
    assert st["lucas_index"] == START_N
    assert st["running"] is False


def test_connect_validates_argument_type():
    miner = PoolAwareMiner()
    with pytest.raises(TypeError):
        miner.connect("braiins")  # type: ignore[arg-type]


def test_disconnect_closes_gate_and_stops():
    miner = PoolAwareMiner(pool=PoolType.CKPOOL)
    assert miner.start()["running"] is True
    result = miner.disconnect()
    assert result["disconnected"] == "ckpool"
    assert result["gate_closed"] is True
    st = miner.status()
    assert st["running"] is False
    assert st["safety_gate"] == "closed"
    with pytest.raises(RuntimeError):
        miner.start()


def test_start_reports_running_state():
    miner = PoolAwareMiner(pool=PoolType.NICEHASH)
    started = miner.start()
    assert started["running"] is True
    assert started["pool"] == "nicehash"
    assert miner.status()["running"] is True
    miner.stop()
    assert miner.status()["running"] is False


# ---------------------------------------------------------------------------
# Lucas-scaled scheduling
# ---------------------------------------------------------------------------


def test_scale_to_sets_index_and_ladder_values():
    miner = PoolAwareMiner(pool=PoolType.BRAIINS)
    for n in CANONICAL_SCALE_INDICES:
        report = miner.scale_to(n)
        assert report["lucas_index"] == n
        assert report["lucas_number"] == lucas(n)
        assert report["was_clamped"] is False


def test_scale_to_clamps_above_pool_max():
    miner = PoolAwareMiner(pool=PoolType.NICEHASH)
    report = miner.scale_to(60)  # max_n = 45
    assert report["lucas_index"] == 45
    assert report["was_clamped"] is True


def test_scale_to_clamps_below_start():
    miner = PoolAwareMiner(pool=PoolType.BRAIINS)
    report = miner.scale_to(1)
    assert report["lucas_index"] == START_N
    assert report["was_clamped"] is True


def test_scale_up_climbs_canonical_ladder():
    miner = PoolAwareMiner(pool=PoolType.BRAIINS)
    for expected in [12, 15, 18, 20]:
        assert miner.scale_up()["lucas_index"] == expected


def test_scale_down_descends_canonical_ladder():
    miner = PoolAwareMiner(pool=PoolType.BRAIINS)
    miner.scale_to(20)
    for expected in [18, 15, 12, 10]:
        assert miner.scale_down()["lucas_index"] == expected


def test_scale_down_floors_at_start_point():
    miner = PoolAwareMiner(pool=PoolType.BRAIINS)
    miner.scale_to(START_N)
    assert miner.scale_down()["lucas_index"] == START_N


def test_scale_up_ceiling_at_pool_max():
    miner = PoolAwareMiner(pool=PoolType.NICEHASH)
    miner.scale_to(45)
    assert miner.scale_up()["lucas_index"] == 45


# ---------------------------------------------------------------------------
# Hard-cap reconciliation: pool ceilings never override the safety boundary
# ---------------------------------------------------------------------------


def test_default_physical_base_hits_start_point():
    miner = PoolAwareMiner(pool=PoolType.BRAIINS)
    # physical × L_10 is the largest exact product at or below the
    # 1.32 EH/s start point (integer math, no float ULP drift).
    assert miner.physical_hashrate_hps * lucas(START_N) == int(1.32 * 1e18) // lucas(
        START_N
    ) * lucas(START_N)
    assert miner.raw_hashrate_ehs() == pytest.approx(1.32, rel=1e-9)


def test_effective_never_exceeds_hard_cap_even_ckpool():
    miner = PoolAwareMiner(pool=PoolType.CKPOOL, safety_cap_ehs=ABSOLUTE_HARD_CAP_EHS)  # 300 EH/s policy ceiling
    miner.scale_to(50)
    assert miner.raw_hashrate_ehs() > ABSOLUTE_HARD_CAP_EHS
    assert miner.effective_hashrate_ehs() <= ABSOLUTE_HARD_CAP_EHS
    report = miner.scale_to(50)
    assert report["dominant_bound"] == "hard_cap"
    assert report["effective_ehs"] == ABSOLUTE_HARD_CAP_EHS


def test_effective_never_exceeds_configured_safety_cap():
    miner = PoolAwareMiner(pool=PoolType.CKPOOL, safety_cap_ehs=5.0)
    miner.scale_to(30)
    assert miner.effective_hashrate_ehs() <= 5.0


def test_safety_cap_constructor_request_clamped_to_hard_cap():
    miner = PoolAwareMiner(pool=PoolType.CKPOOL, safety_cap_ehs=9999.0)
    assert miner.safety_cap_ehs == ABSOLUTE_HARD_CAP_EHS


def test_pool_ceiling_below_raw_dominates_when_lower():
    miner = PoolAwareMiner(
        pool=PoolType.BRAIINS,
        physical_hashrate_hps=10**19,
        safety_cap_ehs=ABSOLUTE_HARD_CAP_EHS,
    )
    miner.scale_to(20)
    # raw ≫ both ceilings; the Braiins policy ceiling (20 EH/s) now equals the
    # non-bypassable hard cap (20 EH/s), so the hard cap is reported on the tie
    # rather than the pool policy that merely agrees with it.
    report = miner.scale_to(20)
    assert report["dominant_bound"] == "hard_cap"
    assert report["effective_ehs"] == ABSOLUTE_HARD_CAP_EHS


def test_pool_policy_binds_when_strictly_below_hard_cap():
    """A pool ceiling strictly below the hard cap must be reported, unmasked."""
    miner = PoolAwareMiner(pool=PoolType.BRAIINS, physical_hashrate_hps=10**19)
    miner.config = PoolConfig(
        pool=PoolType.BRAIINS,
        ceiling_ehs=5.0,
        start_ehs=1.32,
        start_n=START_N,
        max_n=45,
    )
    report = miner.scale_to(20)
    assert report["dominant_bound"] == "pool_ceiling"
    assert report["effective_ehs"] == 5.0


def test_status_kernel_and_theorem_honesty():
    miner = PoolAwareMiner(pool=PoolType.BRAIINS)
    st = miner.status()
    assert st["kernel"] == "mining_kernel"
    assert st["theorem_proven"] is False


def test_lucas_bound_route_is_live():
    result = lucas_bound(10)
    assert result["module"] == "Intelligence.pool_aware_miner"
    assert "bound" in result or "value" in result or "kernel" in result
