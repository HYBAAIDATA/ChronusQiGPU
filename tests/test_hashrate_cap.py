"""The 1 EH/s ceiling is a limit on hashes this process may start."""

import pytest

from chronus.backends.lattice import HardwareUnavailableError
from chronus.execution.geometric_galois_miner import GeometricGaloisMiner
from chronus.execution.hashrate_cap import (
    HASHRATE_CAP_H_S,
    HashrateCap,
    hashes_per_second,
    override_process_cap,
    require_eh_s,
)
from chronus.execution.master_e2e_engine import StealthEngine
from chronus.execution.mining import search_nonce_range
from chronus.execution.mining_entrypoint import ChronusRealMiningEngine
from chronus.execution.opencl_sha256d import OpenCLSha256dMinerBackend
from chronus.stratum.endpoint import PoolEndpoint


GENESIS_HEADER = bytes.fromhex(
    "01000000"
    + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49ffff001d1dac2b7c"
)


def test_one_eh_is_the_hard_ceiling():
    assert hashes_per_second(1) == HASHRATE_CAP_H_S == 10**18
    assert require_eh_s(1.0) == 1.0
    with pytest.raises(ValueError):
        require_eh_s(1.1)
    with pytest.raises(ValueError):
        HashrateCap(HASHRATE_CAP_H_S + 1)


def test_bucket_grants_one_second_then_waits():
    now = {"ns": 5_000}
    cap = HashrateCap(4, clock=lambda: now["ns"])
    assert cap.allow(10) == 4
    assert cap.allow(1) == 0
    assert cap.wait_ns() == 250_000_000
    now["ns"] += 1_000_000_000
    assert cap.allow(4) == 4


def test_galois_search_and_cpu_range_stop_at_the_cap():
    cap = HashrateCap(3, clock=lambda: 0)
    with override_process_cap(cap):
        result = GeometricGaloisMiner().solve_header_range(bytes(76), 0, 0, 20)
        assert result.iterations_evaluated == 3
        blocked = GeometricGaloisMiner().solve_header_range(bytes(76), 0, 0, 20)
        assert blocked.iterations_evaluated == 0
        with pytest.raises(ValueError, match="hashrate cap"):
            search_nonce_range(GENESIS_HEADER, 0, 10, (1 << 256) - 1, workers=1)


def test_cpu_range_searches_only_the_granted_prefix():
    cap = HashrateCap(3, clock=lambda: 0)
    with override_process_cap(cap):
        result = search_nonce_range(GENESIS_HEADER, 0, 10, (1 << 256) - 1, workers=1)
    assert result["tested"] == 3


def test_mining_loop_charges_the_same_cap():
    cap = HashrateCap(2, clock=lambda: 0)
    engine = ChronusRealMiningEngine(
        PoolEndpoint("stratum.braiins.com", 3333, False), "acct.worker", "x"
    )
    job = {
        "version_hex": "20000000",
        "prevhash_hex": "00" * 32,
        "ntime_hex": "5d55fb43",
        "nbits_hex": "17148edf",
        "generation": 1,
        "revision": 0,
        "job_id": "job",
    }
    with override_process_cap(cap):
        engine._search_nonce_batch(job, b"\x00" * 32, "1fffe000", 0)
        assert engine.hashes_computed == 2
        engine._search_nonce_batch(job, b"\x00" * 32, "1fffe000", 0)
        assert engine.hashes_computed == 2
        assert engine._hash_throttled is True


def test_unavailable_igpu_search_does_not_spend_the_cap(monkeypatch):
    monkeypatch.setenv("CHRONUS_ENABLE_OPENCL_MINER", "0")
    cap = HashrateCap(3, clock=lambda: 0)
    with override_process_cap(cap):
        backend = OpenCLSha256dMinerBackend()
        with pytest.raises(HardwareUnavailableError):
            backend.search(b"\x00" * 80, 0, 10, 1)
        assert cap.available() == 3


def test_stealth_engine_cannot_raise_the_ceiling():
    with pytest.raises(ValueError):
        StealthEngine(max_cap_eh=10.0)
    engine = StealthEngine()
    assert engine.max_cap_eh == 1.0
    assert engine.active_stealth_eh == 1.0
