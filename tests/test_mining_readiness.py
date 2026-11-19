"""Mining release regressions using synthetic work and a loopback Stratum pool."""

import asyncio
import os
import importlib.util
import json
import sys
import unittest
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.usefixtures("mining_custody"), pytest.mark.simulated]

from chronus.execution.mining_entrypoint import ChronusRealMiningEngine
from chronus.stratum.gateway import StratumGateway
from chronus.stratum.gatekeeper import (
    DropReason, LocalPreSubmitGatekeeper, compute_share_target_exact, decode_nbits_target,
)
from chronus.stratum.sharding import NonceRange


def notify(job_id="job", clean=True):
    return [job_id, "00" * 32, "01000000", "00000000", [],
            "20000000", "207fffff", "60000000", clean]


@pytest.mark.parametrize("nbits", ["1d80ffff", "23000001", "00000000", -1, 1 << 32])
def test_invalid_compact_target(nbits):
    with pytest.raises(ValueError):
        decode_nbits_target(nbits)


def test_share_target_is_uint256():
    assert compute_share_target_exact(Fraction(1, 10**100)) == (1 << 256) - 1


def test_nonce_ranges_exhaust_without_rehashing_and_extranonce_does_not_wrap():
    miner = ChronusRealMiningEngine("localhost", 3333, "test", "x")
    miner.nonce_batch_size = 8
    miner.partitioner.ranges = [NonceRange(0, 0, 3, 0), NonceRange(1, 3, 6, 0)]
    miner.gateway._process_notify(notify())
    job = miner.gateway.jobs["job"]
    # Impossible target ensures every nonce is visited, including uneven final batches.
    assert miner._search_nonce_batch(job, bytes(32), "00000000", 0) is None
    assert miner.hashes_computed == 6
    assert miner._nonce_space_exhausted
    miner._search_nonce_batch(job, bytes(32), "00000000", 0)
    assert miner.hashes_computed == 6
    miner.gateway.extranonce2_size = 1
    miner.en2_counter = 254
    miner._advance_extranonce()
    assert miner._current_extranonce2 == "ff"
    assert not miner._nonce_cursors
    assert not miner._nonce_space_exhausted
    miner._advance_extranonce()
    assert miner._nonce_extranonce_exhausted
    assert miner._current_extranonce2 == "ff"


class TestMiningReadiness(unittest.IsolatedAsyncioTestCase):
    async def test_difficulty_is_bound_to_job_and_extranonce_invalidates_jobs(self):
        gw = StratumGateway("localhost", 3333, "test")
        await gw.handle_server_push({"method": "mining.set_difficulty", "params": [2]})
        gw._process_notify(notify())
        await gw.handle_server_push({"method": "mining.set_difficulty", "params": [4]})
        assert gw.jobs["job"]["difficulty"] == 2
        gw._process_notify(notify("next", False))
        assert gw.jobs["next"]["difficulty"] == 4
        await gw.handle_server_push({"method": "mining.set_extranonce", "params": ["ab", 2]})
        assert not gw.jobs
        assert not gw.job_history

    async def test_malformed_notify_does_not_destroy_valid_work(self):
        gw = StratumGateway("localhost", 3333, "test")
        gw._process_notify(notify())
        for index, value in [(1, "zz" * 32), (4, ["00"]), (6, "1d80ffff"), (8, "false")]:
            params = notify("bad")
            params[index] = value
            gw._process_notify(params)
            assert list(gw.jobs) == ["job"]
        for _ in range(20):
            gw._process_notify(notify(clean=False))
        assert gw.job_history == ["job"]
        previous = gw.current_difficulty
        for difficulty in [0, -1, "nan"]:
            # Invalid pool input is logged and ignored without killing the session.
            await gw.handle_server_push({"method": "mining.set_difficulty", "params": [difficulty]})
            assert gw.current_difficulty == previous

    async def test_malformed_session_pushes_preserve_active_work(self):
        gw = StratumGateway("localhost", 3333, "test")
        gw._process_notify(notify())
        original_job = gw.jobs["job"]
        original_revision = gw.work_revision
        original_extranonce = (gw.extranonce1_hex, gw.extranonce2_size)
        original_mask = gw.pool_mask_hex

        for params in (["zz", 2], ["ab", 0], ["ab", "2"]):
            await gw.handle_server_push({"method": "mining.set_extranonce", "params": params})
            assert gw.jobs["job"] is original_job
            assert (gw.extranonce1_hex, gw.extranonce2_size) == original_extranonce
            assert gw.work_revision == original_revision

        for mask in ("zzzzzzzz", "1", 1, "111111111"):
            await gw.handle_server_push({"method": "mining.set_version_mask", "params": [mask]})
            assert gw.jobs["job"] is original_job
            assert gw.pool_mask_hex == original_mask
            assert gw.work_revision == original_revision

    async def test_json_decimal_preserves_pool_difficulty(self):
        gw = StratumGateway("localhost", 3333, "test")
        gw.reader = asyncio.StreamReader()
        gw.reader.feed_data(b'{"method":"mining.set_difficulty","params":[0.123456789123456789]}\n')
        await gw.handle_server_push(await gw.read_message())
        assert gw.current_difficulty == Fraction(123456789123456789, 10**18)

    async def test_idle_pool_times_out(self):
        gw = StratumGateway("localhost", 3333, "test", pool_timeout_sec=0.02)
        gw.reader = asyncio.StreamReader()
        with pytest.raises(asyncio.TimeoutError):
            await gw.read_line()

    async def test_replaced_job_candidate_is_never_submitted(self):
        miner = ChronusRealMiningEngine("localhost", 3333, "test", "x")
        miner.gateway._process_notify(notify())
        miner.running = True
        miner.gateway.submission_policy.arm("synthetic-test", 2)
        calls = []

        def search(*args):
            calls.append(args)
            if len(calls) == 1:
                miner.gateway._process_notify(notify())  # same ID, different work object
                return 0, "00000000", 0
            miner.running = False
            return None

        with patch.object(miner, "_search_nonce_batch", side_effect=search), \
             patch.object(miner.gatekeeper, "verify_candidate", wraps=miner.gatekeeper.verify_candidate) as verify:
            await miner._mining_loop()
        verify.assert_not_called()
        assert miner.shares_submitted == 0
        assert miner.gatekeeper.verified_shares_count == 0

    async def test_exhaustion_advances_coinbase_in_running_loop(self):
        miner = ChronusRealMiningEngine("localhost", 3333, "test", "x")
        miner.gateway._process_notify(notify())
        miner.running = True
        miner.gateway.submission_policy.arm("synthetic-test", 2)
        seen = []

        def search(*args):
            seen.append(miner._current_extranonce2)
            miner._nonce_space_exhausted = True
            if len(seen) == 2:
                miner.running = False
            return None

        with patch.object(miner, "_search_nonce_batch", side_effect=search):
            await miner._mining_loop()
        assert seen == ["00000000", "00000001"]

    async def test_real_session_correlates_replies_and_exits_on_pool_eof(self):
        received = []
        finished = asyncio.Event()

        async def pool(reader, writer):
            try:
                while line := await reader.readline():
                    req = json.loads(line)
                    method = req["method"]
                    result = True
                    if method == "mining.configure":
                        result = {"version-rolling": False, "version-rolling.mask": "1fffe000"}
                    elif method == "mining.subscribe":
                        result = [[], "aabb", 4]
                    elif method == "mining.submit":
                        received.append(req)
                        # Unknown, duplicate and optional-extension responses must not count.
                        for rpc_id in [99999, req["id"], req["id"], 3]:
                            writer.write((json.dumps({"id": rpc_id, "result": True}) + "\n").encode())
                        await writer.drain()
                        return
                    writer.write((json.dumps({"id": req["id"], "result": result, "error": None}) + "\n").encode())
                    if method == "mining.authorize":
                        writer.write(b'{"method":"mining.set_difficulty","params":[0.000000000001]}\n')
                        writer.write((json.dumps({"method": "mining.notify", "params": notify()}) + "\n").encode())
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
                finished.set()

        server = await asyncio.start_server(pool, "127.0.0.1", 0)
        async with server:
            miner = ChronusRealMiningEngine("127.0.0.1", server.sockets[0].getsockname()[1], "synthetic.worker", "x")
            miner.nonce_batch_size = 8
            with patch.dict(os.environ, {
                "CHRONUS_ALLOWED_POOL_ENDPOINTS": json.dumps([str(miner.endpoint)]),
                "CHRONUS_MINING_SUBMIT_ARMED": "1",
                "CHRONUS_MINING_APPROVAL_REFERENCE": "synthetic-loopback-test",
                "CHRONUS_MINING_ACCEPTED_SHARE_TARGET": "2",
            }), pytest.raises((asyncio.IncompleteReadError, ConnectionError)):
                await asyncio.wait_for(miner.run(), 3)
            await finished.wait()
        assert received
        assert len(received[0]["params"]) == 5  # extension explicitly refused
        assert miner.shares_accepted == 1
        assert not miner.running
        assert miner.gateway.writer is None

    async def test_self_test_failure_prevents_connect(self):
        runner_path = Path(__file__).parents[1] / "deploy/hyba-mine/runner.py"
        spec = importlib.util.spec_from_file_location("mining_runner_test", runner_path)
        runner = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"bist": SimpleNamespace(run=lambda: {"bist": "FAIL"})}):
            spec.loader.exec_module(runner)
        with patch.object(runner.engine_module, "load_env_config", side_effect=AssertionError("must not configure or connect")):
            assert await runner.main() == 1


def test_harmonic_consensus_checks_kernel_not_zero_quadratic_form():
    from chronus.execution.geometric_galois_miner import HodgeSheafLaplacianConsensus
    consensus = HodgeSheafLaplacianConsensus(4)
    laplacian, norm = consensus.evaluate_laplacian([0, 1, 0, 16])
    assert norm == 0 and any(laplacian)
    assert not consensus.is_harmonic_consensus([0, 1, 0, 16])


def test_authored_search_finds_hit_beyond_old_amplitude_prefix():
    from chronus.execution.geometric_galois_miner import GeometricGaloisMiner, ZeckendorfBasePhiIndexer
    miner = GeometricGaloisMiner()
    # Synthetic target oracle isolates hit 150; this verifies traversal and actual
    # amplitude computation beyond the former first-100 truncation.
    evaluated = []
    def digest(header):
        nonce = int.from_bytes(header[-4:], "little")
        evaluated.append(nonce)
        return (0 if nonce == 150 else 1).to_bytes(32, "little")
    with patch("chronus.execution.geometric_galois_miner.sha256d", side_effect=digest):
        result = miner.solve_header_range(bytes(76), 0, 0, 200)
    assert evaluated == list(range(151))
    assert result.nonce == 150 and result.galois_amplitude == 1
    assert result.harmonic_consensus
    assert ZeckendorfBasePhiIndexer.decode(result.zeckendorf_indices) == 150


def test_authored_search_stops_at_uint32_boundary():
    from chronus.execution.geometric_galois_miner import GeometricGaloisMiner
    with patch("chronus.execution.geometric_galois_miner.sha256d", return_value=b"\xff" * 32):
        result = GeometricGaloisMiner().solve_header_range(bytes(76), 0, (1 << 32) - 2, 20)
    assert not result.found
    assert result.iterations_evaluated == 2


@pytest.mark.parametrize("lanes", [1, 2, 8, 31, 32])
def test_turing_scheduler_exact_coverage_and_bounded_state(lanes):
    from chronus.execution.mining_scheduler import TuringMiningScheduler
    scheduler = TuringMiningScheduler(bytes(range(32)))
    orders = []
    for _ in range(30):
        order = scheduler.order(lanes)
        orders.append(order)
        assert sorted(order) == list(range(lanes))
        assert sum(Fraction(weight) for weight in scheduler.last_evidence["born_weights"]) == 1
        assert all(abs(c).bit_length() < 32 for v in scheduler.swarm.state.vector for c in v.coeffs)
    assert orders[0] == orders[3]  # bounded three-stage discrete evolution
    if lanes > 2:
        assert orders[0] != orders[1]


def test_turing_scheduler_is_used_by_live_nonce_search():
    miner = ChronusRealMiningEngine("localhost", 3333, "test", "x")
    miner.gateway._process_notify(notify())
    miner.nonce_batch_size = 32
    candidate = miner._search_nonce_batch(miner.gateway.jobs["job"], bytes(32), "00000000", (1 << 256) - 1)
    first = miner.scheduler.last_evidence["lane_order"][0]
    assert candidate[0] == miner.partitioner.ranges[first].start_nonce
    assert miner.scheduler.last_evidence["overlay"] == {"dodecahedron_faces": 12, "icosahedron_faces": 20}
    assert miner.last_search_result.harmonic_consensus
    assert miner.last_search_result.galois_amplitude == 1


class TestMiningShutdown(unittest.IsolatedAsyncioTestCase):
    async def test_canonical_self_test_failure_prevents_socket_open(self):
        miner = ChronusRealMiningEngine("localhost", 3333, "test", "x")
        with patch("chronus.execution.mining_selftest.run", return_value={"bist": "FAIL"}), \
             patch.object(miner.gateway, "connect", side_effect=AssertionError("must not connect")):
            with pytest.raises(RuntimeError, match="self-test failed"):
                await miner.run()
        assert not miner.running

    async def test_cancellation_joins_bounded_search_worker(self):
        import threading
        started, release = threading.Event(), threading.Event()
        miner = ChronusRealMiningEngine("localhost", 3333, "test", "x")
        miner.gateway._process_notify(notify())
        miner.running = True
        miner.gateway.submission_policy.arm("synthetic-test", 2)
        def search(*args):
            started.set()
            assert release.wait(2)
            return None
        with patch.object(miner, "_search_nonce_batch", side_effect=search):
            task = asyncio.create_task(miner._mining_loop())
            try:
                assert await asyncio.to_thread(started.wait, 1)
                task.cancel()
                await asyncio.sleep(0.01)
                assert not task.done()
            finally:
                release.set()
            with pytest.raises(asyncio.CancelledError):
                await task


@pytest.mark.parametrize("value", ["1e1000000000", "1e-1000000000", "9" * 65, "NaN", "Infinity", "0", "-1"])
def test_pool_difficulty_resource_bounds(value):
    with pytest.raises(ValueError):
        StratumGateway._parse_difficulty(value)


class TestSessionTimeouts(unittest.IsolatedAsyncioTestCase):
    async def test_quiet_active_session_outlives_handshake_timeout(self):
        gw = StratumGateway("localhost", 3333, "test", pool_timeout_sec=0.01,
                            session_idle_timeout_sec=0.2)
        gw.reader = asyncio.StreamReader()
        async def delayed_push():
            await asyncio.sleep(0.03)
            gw.reader.feed_data(b'{"method":"mining.set_difficulty","params":[2]}\n')
        writer = asyncio.create_task(delayed_push())
        message = await gw.read_message()
        await writer
        assert message["params"] == [2]



def test_live_authored_search_uses_large_pv_acceleration_ladder():
    from chronus.execution.geometric_galois_miner import GeometricGaloisMiner
    miner = GeometricGaloisMiner()
    results = [miner.solve_header_range(bytes(76), (1 << 256) - 1, 0, 1) for _ in range(4)]
    assert [result.pv_scale_index for result in results] == [10**12, 10**15, 10**18, 10**20]
    assert all(result.found and result.iterations_evaluated == 1 for result in results)
    assert all(0 <= value < 257 for result in results for value in result.pv_marked_amplitude)


def test_small_batch_budget_is_global_across_lanes():
    miner = ChronusRealMiningEngine("localhost", 3333, "test", "x")
    miner.nonce_batch_size = 1
    miner.gateway._process_notify(notify())
    assert miner._search_nonce_batch(miner.gateway.jobs["job"], bytes(32), "00000000", 0) is None
    assert miner.hashes_computed == 1


def test_self_test_exception_emits_json_failure(capsys):
    from chronus.execution import mining_selftest
    with patch.object(mining_selftest, "_run_checks", side_effect=ArithmeticError("injected failure")):
        assert mining_selftest.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["bist"] == "FAIL"
    assert report["checks"][0]["error"] == "ArithmeticError"


class TestSubmissionWatchdog(unittest.IsolatedAsyncioTestCase):
    async def test_new_submission_times_out_while_socket_reader_is_idle(self):
        import time
        miner = ChronusRealMiningEngine("localhost", 3333, "test", "x")
        miner.running = True
        miner.gateway.submission_policy.arm("synthetic-test", 2)
        miner.gateway.pool_timeout_sec = 0.02
        watchdog = asyncio.create_task(miner._monitor_submissions())
        await asyncio.sleep(0)
        miner._pending_submits[1] = time.perf_counter_ns()
        miner._submission_changed.set()
        with pytest.raises(TimeoutError, match="acknowledgement timed out"):
            await asyncio.wait_for(watchdog, 0.2)


class TestRetainedWork(unittest.IsolatedAsyncioTestCase):
    async def test_non_clean_notify_keeps_pending_candidate_eligible(self):
        miner = ChronusRealMiningEngine("localhost", 3333, "test", "x")
        miner.last_search_result = SimpleNamespace(
            zeckendorf_indices=[], galois_amplitude=1,
            harmonic_consensus=True, polychoron_vertex_idx=0,
        )
        miner.gateway._process_notify(notify())
        original = miner.gateway.jobs["job"]
        revision = miner.gateway.work_revision
        miner.running = True
        miner.gateway.submission_policy.arm("synthetic-test", 2)
        calls = []

        def search(*args):
            calls.append(args)
            if len(calls) == 1:
                miner.gateway._process_notify(notify("next", clean=False))
                return 0, "00000000", 0
            miner.running = False
            return None

        with patch.object(miner, "_search_nonce_batch", side_effect=search), \
             patch.object(miner.gatekeeper, "verify_candidate", wraps=miner.gatekeeper.verify_candidate) as verify:
            await miner._mining_loop()
        assert miner.gateway.work_revision == revision
        assert miner.gateway.jobs["job"] is original
        assert verify.call_count == 1
        assert verify.call_args.kwargs["job_data"] is original

    async def test_replacement_id_changes_nonce_context_without_cleaning_other_jobs(self):
        gateway = StratumGateway("localhost", 3333, "test")
        gateway._process_notify(notify())
        original = gateway.jobs["job"]
        revision = gateway.work_revision
        gateway._process_notify(notify("other", clean=False))
        gateway._process_notify(notify(clean=False))
        assert gateway.work_revision == revision
        assert gateway.jobs["job"]["revision"] != original["revision"]
        assert "other" in gateway.jobs


def test_replacement_job_reuses_tuple_without_forgetting_other_job_duplicates():
    gateway=StratumGateway("localhost",3333,"test")
    gateway.current_difficulty=Fraction(1,10**100)
    gateway.pool_mask_hex="1fffe000"  # A successfully negotiated version-rolling mask.
    gateway._process_notify(notify("retained"))
    gateway._process_notify(notify(clean=False))
    gatekeeper=LocalPreSubmitGatekeeper()

    def verify(job_id, ntime_hex="60000000"):
        return gatekeeper.verify_candidate(
            job_data=gateway.jobs[job_id], extranonce1_hex="ab",
            extranonce2_hex="00000001", extranonce2_size=4,
            ntime_hex=ntime_hex, nonce_int=7, version_bits_hex="00000000",
            pool_mask_hex=gateway.pool_mask_hex, current_difficulty=gateway.current_difficulty,
            dedup_ledger=gateway.dedup_ledger, active_job_ids=gateway.jobs,
        )

    original=verify("job")
    assert original[0] and verify("retained")[0]
    assert verify("job")[1] is DropReason.DUP
    old_revision=gateway.jobs["job"]["revision"]
    replacement=notify(clean=False)
    replacement[2]+="ab"  # New coinbase, same job ID and submission tuple.
    gateway._process_notify(replacement)
    assert gateway.jobs["job"]["revision"]>old_revision
    replaced=verify("job")
    assert replaced[0] and replaced[2]!=original[2]
    assert verify("job")[1] is DropReason.DUP
    assert verify("retained")[1] is DropReason.DUP
    # A repeated notification with identical header inputs is still duplicate work.
    gateway._process_notify(replacement)
    assert verify("job")[1] is DropReason.DUP
    timestamp_only=list(replacement)
    timestamp_only[7]="60000001"
    gateway._process_notify(timestamp_only)
    assert verify("job")[1] is DropReason.DUP
    assert verify("job","60000001")[0]
    assert verify("job","60000001")[1] is DropReason.DUP
    equivalent=list(replacement)
    equivalent[2]=equivalent[2].upper()
    gateway._process_notify(equivalent)
    assert verify("job")[1] is DropReason.DUP
    masked_version=list(replacement)
    masked_version[5]="20002000"  # This bit is supplied by version rolling, not the base.
    gateway._process_notify(masked_version)
    assert verify("job")[1] is DropReason.DUP
    changed_version=list(replacement)
    changed_version[5]="40000000"  # An unmasked base bit changes the actual header.
    gateway._process_notify(changed_version)
    assert verify("job")[0]
    for index in range(17):
        gateway._process_notify(notify(f"next-{index}",clean=False))
    assert "job" not in gateway.jobs
    gateway._process_notify(replacement)
    assert verify("job")[0]  # No stale entry survives retirement of an inactive job ID.


def test_braiins_host_without_scheme_keeps_the_hostname(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTHIA_POOL_SPECS", "")
    monkeypatch.setenv("MINING_ACTIVE_POOL", "BRAIINS")
    monkeypatch.setenv("MINING_BRAIINS_HOST", "stratum.braiins.com")
    monkeypatch.setenv("MINING_BRAIINS_PORT", "3333")
    monkeypatch.setenv("MINING_BRAIINS_USER", "acct.worker")
    monkeypatch.setenv("MINING_BRAIINS_PASSWORD", "123")
    from chronus.execution.mining_entrypoint import load_env_config

    with caplog.at_level("WARNING"):
        label, endpoint, user, password = load_env_config()
    assert label == "BRAIINS"
    assert endpoint.host == "stratum.braiins.com"
    assert endpoint.port == 3333
    assert endpoint.tls is False
    assert user == "acct.worker"
    assert password == "123"
    assert "cleartext" not in caplog.text


def test_plaintext_fallback_warns_without_logging_the_password(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTHIA_POOL_SPECS", "")
    monkeypatch.setenv("MINING_ACTIVE_POOL", "BRAIINS")
    monkeypatch.setenv("MINING_BRAIINS_HOST", "stratum.braiins.com")
    monkeypatch.setenv("MINING_BRAIINS_PORT", "3333")
    monkeypatch.setenv("MINING_BRAIINS_USER", "acct.worker")
    monkeypatch.setenv("MINING_BRAIINS_PASSWORD", "not-a-placeholder")
    from chronus.execution.mining_entrypoint import load_env_config

    with caplog.at_level("WARNING"):
        _, endpoint, _, password = load_env_config()
    assert endpoint.tls is False
    assert password == "not-a-placeholder"
    assert "stratum+tcp" in caplog.text
    assert "stratum+ssl://" in caplog.text
    assert "not-a-placeholder" not in caplog.text


def test_padded_placeholder_warns_and_is_sent_unchanged(monkeypatch, tmp_path, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTHIA_POOL_SPECS", "")
    monkeypatch.setenv("MINING_ACTIVE_POOL", "BRAIINS")
    monkeypatch.setenv("MINING_BRAIINS_HOST", "stratum.braiins.com")
    monkeypatch.setenv("MINING_BRAIINS_PORT", "3333")
    monkeypatch.setenv("MINING_BRAIINS_USER", "acct.worker")
    monkeypatch.setenv("MINING_BRAIINS_PASSWORD", " 123 ")
    from chronus.execution.mining_entrypoint import load_env_config

    with caplog.at_level("WARNING"):
        _, endpoint, _, password = load_env_config()
    assert endpoint.tls is False
    assert password == " 123 "
    assert "cleartext" in caplog.text
    assert "stratum+ssl://" in caplog.text
    assert " 123 " not in caplog.text
