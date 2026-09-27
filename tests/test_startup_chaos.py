"""Short deterministic startup race probes; no pool or device access."""
from __future__ import annotations

import os
import tempfile
import threading
import time

from worker_lifecycle import HeartbeatEmitter, HeartbeatReader


def test_reader_writer_race_never_accepts_partial_payload():
    os.environ["PYTHIA_IDENTITY_HMAC_SECRET"] = "11" * 32
    with tempfile.TemporaryDirectory() as directory:
        os.environ["PYTHIA_WORKER_HEARTBEAT_DIR"] = directory
        stop = threading.Event()
        observations: list[str] = []
        with HeartbeatEmitter("race", interval=0.002):
            reader = HeartbeatReader("race")

            def read_loop():
                while not stop.is_set():
                    observations.append(str(reader.poll()["kind"]))

            thread = threading.Thread(target=read_loop)
            thread.start()
            time.sleep(0.05)
            stop.set()
            thread.join(timeout=1)
        assert observations
        assert "malformed" not in observations
        assert "regressed" not in observations


def test_epoch_change_is_not_a_regression():
    os.environ["PYTHIA_IDENTITY_HMAC_SECRET"] = "11" * 32
    with tempfile.TemporaryDirectory() as directory:
        os.environ["PYTHIA_WORKER_HEARTBEAT_DIR"] = directory
        with HeartbeatEmitter("restart", interval=100.0):
            reader = HeartbeatReader("restart")
            assert reader.poll()["kind"] == "fresh"
            reader.last_seq = 999
        with HeartbeatEmitter("restart", interval=100.0):
            assert reader.poll()["kind"] == "epoch_change"


def test_emitter_report_surfaces_measured_counters():
    import json
    from pathlib import Path

    os.environ["PYTHIA_IDENTITY_HMAC_SECRET"] = "11" * 32
    with tempfile.TemporaryDirectory() as directory:
        os.environ["PYTHIA_WORKER_HEARTBEAT_DIR"] = directory
        with HeartbeatEmitter("miner-test", interval=0.005) as emitter:
            emitter.report(
                hashrate_hs=13_518_744.47,
                shares_accepted=2,
                total_hashes=811_597_824,
                backend="opencl:gpu",
                job_id="00",
            )
            time.sleep(0.05)
            payload = json.loads(
                (Path(directory) / "miner-test.metrics.json").read_text(encoding="utf-8")
            )
        counters = payload["counters"]
        assert counters["hashrate_hs"] == 13_518_744.47
        assert counters["shares_accepted"] == 2
        assert counters["total_hashes"] == 811_597_824
        assert counters["backend"] == "opencl:gpu"
        assert counters["job_id"] == "00"


def test_control_api_populates_record_from_emitter_counters():
    from control_api import _refresh_evidence
    from startup_contract import WorkerRecord

    os.environ["PYTHIA_IDENTITY_HMAC_SECRET"] = "11" * 32
    with tempfile.TemporaryDirectory() as directory:
        os.environ["PYTHIA_WORKER_HEARTBEAT_DIR"] = directory
        with HeartbeatEmitter("miner-viabtc", interval=0.005) as emitter:
            emitter.report(hashrate_hs=14_329_148.22, shares_accepted=1)
            record = WorkerRecord("miner-viabtc", "production_miner.py", "running")
            # The emitter's first tick writes metrics before report() lands;
            # poll until the reported counters are visible instead of racing
            # a fixed sleep against fsync-heavy ticks under suite load.
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                _refresh_evidence(record)
                if record.hashrate == 14_329_148.22:
                    break
                time.sleep(0.02)
        assert record.hashrate == 14_329_148.22
        assert record.shares_accepted == 1
        assert record.liveness is True
