"""Hashrate governor: the rate the network sees stays under the configured cap.

Each test states a property that fails if the logic is wrong, not a
restatement of the implementation.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from manifold_pool_coordinator import PoolEndpoint
from chronus.mla1517.mining.hashrate_governor import (
    DEFAULT_CEILING_HS,
    MAX_NETWORK_FRACTION,
    HashrateGovernor,
    expected_hashes,
    poisson_interval,
)
from test_agentic_voyages import EASY_TARGET, FakePool, _connected, _job, _served, bip34_coinb1
from test_pool_only_mining import _poll, _pool_only_coordinator

MAINNET_LIKE_NBITS = "17034219"  # ~618 EH/s network


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _run(
    governor: HashrateGovernor,
    clock: Clock,
    *,
    seconds: float,
    window: int,
    raw_hs: float,
    shares_per_window: int = 0,
    share_target: int | None = None,
) -> int:
    """Drive windows as fast as the hardware allows; return hashes executed."""
    executed = 0
    while clock.now < seconds:
        if governor.admit():
            clock.now += window / raw_hs
            governor.record(hashes=window, share_target=share_target, shares=shares_per_window)
            executed += window
        else:
            clock.now += 0.05
    return executed


def test_long_run_rate_never_exceeds_the_cap():
    clock = Clock()
    governor = HashrateGovernor(target_hs=1_000.0, burst_s=10.0, clock=clock)
    window, seconds = 500, 600.0
    executed = _run(governor, clock, seconds=seconds, window=window, raw_hs=1e6)
    # Refill over the run, the initial burst, and at most one overdrawn window.
    assert executed <= 1_000.0 * (seconds + 10.0) + window
    # ...and the governor is not merely blocking: it delivers the cap.
    assert executed >= 1_000.0 * seconds * 0.95
    assert governor.deferred > 0
    assert governor.hashes == executed
    assert governor.charged_work == float(executed)


def test_shares_are_charged_by_the_work_they_prove():
    # A miner that finds shares with far fewer hashes than search needs is
    # seen by the network at the rate its shares imply. Charging only hashes
    # would let it run 10_000x over the cap.
    clock = Clock()
    governor = HashrateGovernor(target_hs=1_000.0, burst_s=10.0, clock=clock)
    share_target = (1 << 256) // 1_000_000 - 1  # a share proves 1e6 hashes
    _run(
        governor,
        clock,
        seconds=600.0,
        window=100,
        raw_hs=1e6,
        shares_per_window=1,
        share_target=share_target,
    )
    implied_rate = governor.shares * expected_hashes(share_target) / 600.0
    assert implied_rate <= 1_000.0 * (1 + 10.0 / 600.0) + expected_hashes(share_target) / 600.0
    assert governor.charged_work == governor.shares * expected_hashes(share_target)
    assert governor.hashes == 100 * governor.shares


# The policy numbers are asserted as literals: comparing against the module's
# own constants would pass whatever those constants were changed to.
TEN_EH_S = 1e19
ONE_PERCENT_OF_DIFFICULTY_1 = 71583.88055  # 0.01 * 2**256 // (0xffff * 2**208 + 1) / 600


def test_policy_limits_are_ten_exahashes_and_one_percent_of_the_network():
    assert DEFAULT_CEILING_HS == TEN_EH_S
    assert MAX_NETWORK_FRACTION == 0.01
    assert HashrateGovernor().burst_s == 30.0


def test_cap_is_the_lowest_limit_and_config_cannot_raise_the_network_share():
    governor = HashrateGovernor()
    assert governor.cap_hs == TEN_EH_S
    governor.configure(target_hs=5e15, ceiling_hs=TEN_EH_S)
    assert governor.cap_hs == 5e15
    governor.configure(target_hs=0.0, ceiling_hs=1e30)  # above the hard ceiling
    assert governor.cap_hs == TEN_EH_S
    governor.configure(target_hs=0.0, ceiling_hs=2e17)  # below it: the ceiling binds
    assert governor.cap_hs == 2e17
    governor.observe_network("1d00ffff")  # difficulty 1: ~7.16 MH/s network
    assert governor.network_hs == pytest.approx(7158388.055, rel=1e-9)
    assert governor.cap_hs == pytest.approx(ONE_PERCENT_OF_DIFFICULTY_1, rel=1e-9)
    governor.configure(target_hs=1e30, ceiling_hs=1e30)
    assert governor.cap_hs == pytest.approx(ONE_PERCENT_OF_DIFFICULTY_1, rel=1e-9)
    governor.observe_network(MAINNET_LIKE_NBITS)
    # 1% of mainnet (~6.2 EH/s) is below the 10 EH/s ceiling, so the network share binds.
    assert governor.cap_hs == pytest.approx(0.01 * governor.network_hs, rel=1e-9)
    for target, ceiling in (
        (-1.0, TEN_EH_S),
        (float("nan"), TEN_EH_S),
        (float("inf"), TEN_EH_S),
        (True, TEN_EH_S),
        ("5", TEN_EH_S),
        (0.0, 0.0),
        (0.0, -1.0),
    ):
        with pytest.raises(ValueError):
            governor.configure(target_hs=target, ceiling_hs=ceiling)
    # A rejected config changes nothing.
    assert governor.cap_hs == pytest.approx(0.01 * governor.network_hs, rel=1e-9)
    with pytest.raises(ValueError):
        HashrateGovernor(burst_s=0.0)
    assert HashrateGovernor(burst_s=0.5).burst_s == 0.5


def test_a_fresh_budget_is_the_burst_and_a_zero_balance_is_not_a_deficit():
    clock = Clock()
    governor = HashrateGovernor(target_hs=100.0, burst_s=10.0, clock=clock)
    # Frozen clock: exactly cap * burst = 1000 hashes are available.
    for _ in range(10):
        assert governor.admit() is True
        governor.record(hashes=100, share_target=None, shares=0)
    assert governor.snapshot()["budget_hashes"] == 0.0
    assert governor.admit() is True  # at zero the budget is spent, not overdrawn
    governor.record(hashes=1, share_target=None, shares=0)
    assert governor.admit() is False
    clock.now += 0.01  # refills at the cap: 100 H/s * 0.01 s = 1 hash
    assert governor.admit() is True
    assert (governor.admitted, governor.deferred, governor.hashes) == (12, 1, 1001)


def test_windows_are_validated_and_hashes_without_a_share_target_prove_nothing():
    governor = HashrateGovernor()
    for hashes, shares in ((-1, 0), (0, -1)):
        with pytest.raises(ValueError):
            governor.record(hashes=hashes, share_target=None, shares=shares)
    assert governor.record(hashes=0, share_target=None, shares=0) == 0.0
    assert governor.record(hashes=500, share_target=None, shares=0) == 500.0
    assert governor.expected_shares == 0.0 and governor.share_yield()["ratio"] is None


def test_expected_hashes_is_exact_integer_work():
    assert expected_hashes(0) == 2.0**256
    assert expected_hashes(1) == 2.0**255
    assert expected_hashes(2**256 - 1) == 1.0
    assert expected_hashes(2**255) == 1.0  # floor(2**256 / (2**255 + 1))
    with pytest.raises(ValueError):
        expected_hashes(-1)


def test_share_yield_is_one_for_search_and_above_one_only_when_shares_beat_it():
    target = (1 << 256) // 1_000 - 1  # 1_000 hashes per share by search
    search = HashrateGovernor()
    search.record(hashes=100_000, share_target=target, shares=100)
    result = search.share_yield()
    assert result["ratio"] == pytest.approx(1.0, rel=1e-3)
    assert result["expected"] == pytest.approx(100.0, rel=1e-9)
    # Garwood interval for 100 events, scaled by the 100 expected.
    assert result["ci95"] == pytest.approx([0.8136399, 1.2162679], rel=1e-5)

    solving = HashrateGovernor()
    solving.record(hashes=10_000, share_target=target, shares=100)
    lower, _ = solving.share_yield()["ci95"]
    assert lower > 1.0  # ten times the shares search explains, beyond noise

    assert HashrateGovernor().share_yield()["ratio"] is None

    every_hash = HashrateGovernor()  # a target every hash meets: 1 hash per share
    every_hash.record(hashes=40, share_target=2**256 - 1, shares=40)
    assert every_hash.share_yield()["expected"] == 40.0
    half = HashrateGovernor()  # half a share expected is still a measurement
    half.record(hashes=500, share_target=target, shares=0)
    assert half.share_yield()["ratio"] == 0.0


def test_poisson_interval_matches_exact_garwood_values():
    # Reference values: chi2.ppf(0.025, 2n)/2 and chi2.ppf(0.975, 2n + 2)/2.
    for n, lower, upper in ((0, 0.0, 3.6889), (1, 0.0253, 5.5716), (10, 4.7954, 18.3904)):
        got = poisson_interval(n)
        assert got[0] == pytest.approx(lower, abs=1e-4)
        assert got[1] == pytest.approx(upper, abs=1e-4)
    lower, upper = poisson_interval(1000)
    assert lower == pytest.approx(938.973, rel=1e-5) and upper == pytest.approx(1063.952, rel=1e-5)
    # Above 1000 events the Wilson-Hilferty approximation takes over.
    for n, lower, upper in ((1001, 939.94203, 1064.98311), (5000, 4862.35919, 5140.54895)):
        got = poisson_interval(n)
        assert got[0] == pytest.approx(lower, rel=1e-4)
        assert got[1] == pytest.approx(upper, rel=1e-4)


def test_configured_target_throttles_a_live_coordinator(tmp_path, monkeypatch):
    # The operator's runtime config must reach the miner: before this governor
    # the control API stored hashrate.target_hs and nothing read it.
    config = tmp_path / "runtime_config.json"
    # 0.02 H/s with a 30 s burst budgets 0.6 hashes: one window, then deficit.
    config.write_text(json.dumps({"hashrate": {"target_hs": 0.02, "ceiling_hs": 1e19}}))
    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(config))

    async def scenario():
        pool = FakePool(target=EASY_TARGET, job=_job("job-g", coinb1=bip34_coinb1(900_001)))
        server, port = await _served(pool)
        coord = _pool_only_coordinator([PoolEndpoint("127.0.0.1", port, "ckpool")])
        try:
            await _connected(coord, "job-g")
            assert await _poll(coord) is True
            outcomes = [await coord.search_current_job() for _ in range(5)]
            return coord, outcomes, list(pool.submits)
        finally:
            await coord.client.close()
            server.close()

    coord, outcomes, submits = asyncio.run(scenario())
    assert coord.governor.target_hs == 0.02
    snapshot = coord.intelligence_snapshot()["governor"]
    assert snapshot["cap_hs"] == 0.02
    assert (snapshot["admitted"], snapshot["deferred"]) == (1, 4)
    assert coord.last_execution["reason"] == "hashrate_governor"
    # Deferred windows never reach the pool.
    assert len(submits) == 1
    assert outcomes == [True, False, False, False, False]


def test_hashrate_governor_constants_and_cap_rules_are_locked():
    """Lock network fraction, block interval, default ceiling and Poisson alpha
    so mutations of MAX_NETWORK_FRACTION, BLOCK_INTERVAL_S or the 1% hard cap cannot survive."""
    from chronus.mla1517.mining.hashrate_governor import (
        MAX_NETWORK_FRACTION, BLOCK_INTERVAL_S, DEFAULT_CEILING_HS, poisson_interval
    )
    assert MAX_NETWORK_FRACTION == 0.01
    assert BLOCK_INTERVAL_S == 600.0
    assert DEFAULT_CEILING_HS == 1e19
    # Poisson interval uses alpha=0.05 by default (Garwood)
    lo, hi = poisson_interval(0)
    assert lo == 0.0 and hi > 0.0
    # Cap is the min of target, ceiling and 1% of network
    clock = Clock()
    gov = HashrateGovernor(target_hs=1e12, ceiling_hs=1e18, clock=clock)
    gov.observe_network(MAINNET_LIKE_NBITS)
    assert gov.cap_hs == min(1e12, 1e18, 0.01 * gov.network_hs)
