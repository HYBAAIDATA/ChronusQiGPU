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


def test_idle_time_does_not_raise_the_burst_and_republish_does_not_refill():
    now = {"ns": 0}
    cap = HashrateCap(4, clock=lambda: now["ns"])
    now["ns"] = 10 * 1_000_000_000
    assert cap.allow(100) == 4
    assert cap.allow(1) == 0
    cap.set_rate(4)
    assert cap.allow(1) == 0


def test_an_early_hit_returns_the_unsearched_grant():
    cap = HashrateCap(10, clock=lambda: 0)
    with override_process_cap(cap):
        hit = GeometricGaloisMiner().solve_header_range(bytes(76), (1 << 256) - 1, 0, 10)
    assert hit.found is True
    assert hit.iterations_evaluated == 1
    assert cap.available() == 9


def test_concurrent_callers_cannot_share_one_grant():
    import threading

    cap = HashrateCap(100, clock=lambda: 0)
    grants: list[int] = []
    lock = threading.Lock()

    def take() -> None:
        granted = cap.allow(100)
        with lock:
            grants.append(granted)

    threads = [threading.Thread(target=take) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(grants) == 100


def test_galois_search_and_cpu_range_stop_at_the_cap():
    cap = HashrateCap(3, clock=lambda: 0)
    with override_process_cap(cap):
        result = GeometricGaloisMiner().solve_header_range(bytes(76), 0, 0, 20)
        assert result.iterations_evaluated == 3
        blocked = GeometricGaloisMiner().solve_header_range(bytes(76), 0, 0, 20)
        assert blocked.iterations_evaluated == 0
        with pytest.raises(ValueError, match="hashrate cap"):
            search_nonce_range(GENESIS_HEADER, 0, 10, (1 << 256) - 1, workers=1)


def test_an_invalid_range_does_not_spend_the_cap():
    cap = HashrateCap(3, clock=lambda: 0)
    with override_process_cap(cap):
        with pytest.raises(ValueError):
            search_nonce_range(GENESIS_HEADER, -1, 0, 1)
        with pytest.raises(ValueError):
            search_nonce_range(GENESIS_HEADER, (1 << 32) - 3, (1 << 32) + 7, 1)
        with pytest.raises(ValueError):
            search_nonce_range(GENESIS_HEADER, 0, 4, 1, partition="spiral")
    assert cap.available() == 3


def test_backend_execute_stops_at_the_cap():
    from chronus.execution.geometric_galois_miner import GeometricGaloisMinerBackend

    cap = HashrateCap(4, clock=lambda: 0)
    with override_process_cap(cap):
        result = GeometricGaloisMinerBackend().execute(b"")
    assert result["tested"] == 4
    assert cap.available() == 0


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


def test_a_fresh_admin_keeps_a_lower_published_rate(tmp_path, monkeypatch):
    from chronus.execution.hashrate_cap import process_cap, publish_limit_file
    from chronus.execution.mining_admin import MiningAdminEngine

    path = tmp_path / "hashrate-cap"
    monkeypatch.setenv("CHRONUS_HASHRATE_LIMIT_FILE", str(path))
    publish_limit_file(0.25)
    before = process_cap().cap_h_s
    try:
        engine = MiningAdminEngine()
        assert engine.config.stealth_target_eh_s == 0.25
        assert path.read_text(encoding="ascii").strip() == "0.25"
        assert list(tmp_path.glob("*.tmp")) == []
    finally:
        if process_cap().cap_h_s != before:
            process_cap().set_rate(before)


def test_a_non_ascii_limit_file_leaves_the_rate_unchanged(tmp_path, monkeypatch):
    from chronus.execution.hashrate_cap import apply_published_limit, process_cap

    path = tmp_path / "hashrate-cap"
    path.write_bytes(b"\xff\xfe")
    monkeypatch.setenv("CHRONUS_HASHRATE_LIMIT_FILE", str(path))
    cap = HashrateCap(10, clock=lambda: 0)
    with override_process_cap(cap):
        apply_published_limit()
        assert process_cap().cap_h_s == 10


def test_concurrent_publish_keeps_a_valid_rate(tmp_path, monkeypatch):
    import threading

    from chronus.execution.hashrate_cap import publish_limit_file

    path = tmp_path / "hashrate-cap"
    monkeypatch.setenv("CHRONUS_HASHRATE_LIMIT_FILE", str(path))
    errors: list[BaseException] = []

    def publish(value: float) -> None:
        try:
            for _ in range(20):
                publish_limit_file(value)
        except BaseException as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=publish, args=(0.25,)),
        threading.Thread(target=publish, args=(0.5,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert path.read_text(encoding="ascii").strip() in {"0.25", "0.5"}
    assert list(tmp_path.glob("*.tmp")) == []


def test_a_second_process_adopts_the_published_limit(tmp_path, monkeypatch):
    import os
    import subprocess
    import sys

    path = tmp_path / "hashrate-cap"
    monkeypatch.setenv("CHRONUS_HASHRATE_LIMIT_FILE", str(path))
    from chronus.execution.hashrate_cap import publish_limit_file

    publish_limit_file(0.25)
    env = os.environ.copy()
    env["CHRONUS_HASHRATE_LIMIT_FILE"] = str(path)
    env["PYTHONPATH"] = "src"
    out = subprocess.check_output(
        [
            sys.executable,
            "-c",
            "from chronus.execution.hashrate_cap import apply_published_limit, process_cap\n"
            "apply_published_limit()\n"
            "print(process_cap().cap_h_s)",
        ],
        env=env,
        text=True,
    )
    assert int(out.strip()) == hashes_per_second(0.25)


def test_stealth_engine_cannot_raise_the_ceiling():
    with pytest.raises(ValueError):
        StealthEngine(max_cap_eh=10.0)
    engine = StealthEngine()
    assert engine.max_cap_eh == 1.0
    assert engine.active_stealth_eh == 1.0
