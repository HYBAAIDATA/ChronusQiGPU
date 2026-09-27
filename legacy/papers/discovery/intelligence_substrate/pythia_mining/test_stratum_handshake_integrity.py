"""Regression tests for the PYTHIA StratumClient handshake -> share-acceptance
integrity remediation (findings M1-M6 + hygiene).

Covered invariants:
  - M1: mining.submit request ids never collide with reserved handshake ids
        1-2, and the id counter persists across reconnects.
  - M2: a pool verdict arriving after the submit timeout is reconciled into
        pool_accepted/pool_rejected through the late-ACK window instead of
        being silently dropped.
  - M3: firewall (local SHA256d) validation advances firewall_* counters
        only -- never pool_accepted.
  - M4: share_accepted/share_rejected evidence events carry the job_id and
        extranonce1 captured at submit time, not whichever job is current
        when the ACK arrives.
  - M5: a new session (or unexpected disconnect) invalidates current_job,
        fails pending futures with ConnectionError, clears the late-ACK
        window, and bumps session_epoch.
  - M6: clean_jobs=true bumps job_epoch; submissions computed against a
        retired epoch or job are rejected before any wire write.

Uses an in-memory Stratum v1 mock server, following the harness pattern of
tests/test_stratum_live_session.py.
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PYTHIA_MINING_DIR = _THIS_DIR
# Legacy relocation note: this suite lives next to the module under test.
# The repo root (when it exists at either layout depth) is also added so the
# optional `mining.evidence` / `python_backend` import fallbacks resolve the
# same way they do in deployment.
_REPO_ROOT = _THIS_DIR
for _ancestor in range(6):
    _cand = _REPO_ROOT
    if os.path.isdir(os.path.join(_cand, "mining")) or os.path.isdir(
        os.path.join(_cand, "python_backend")
    ):
        break
    _REPO_ROOT = os.path.dirname(_cand)
for _p in (_REPO_ROOT, _PYTHIA_MINING_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

import stratum_client as sc


class MockStratumServer:
    """In-memory Stratum v1 server driving StratumClient lifecycle tests.

    submit_ack_mode:
      "ack"      -> respond result:true immediately
      "delayed"  -> respond result:true after submit_delay seconds
      "held"     -> respond result:true only once submit_gate is set
      "reject"   -> respond result:false with an error tuple immediately
    """

    def __init__(
        self,
        submit_ack_mode: str = "ack",
        submit_delay: float = 0.0,
        job_id: str = "jobA",
    ):
        self.host = "127.0.0.1"
        self.port = 0
        self.server: Optional[asyncio.AbstractServer] = None
        self.received: List[Dict[str, Any]] = []
        self.submit_ack_mode = submit_ack_mode
        self.submit_delay = submit_delay
        self.submit_gate = asyncio.Event()
        self.submit_gate.set()
        self.default_job_id = job_id
        self._writer: Optional[asyncio.StreamWriter] = None

    async def start(self):
        self.server = await asyncio.start_server(self._handle, self.host, self.port)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        self.submit_gate.set()  # release any held submit handlers first
        try:
            await self.drop_client()
        except Exception:
            pass
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def drop_client(self):
        """Close the live client connection so the client sees remote EOF."""
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass
            self._writer = None

    def submits(self) -> List[Dict[str, Any]]:
        return [m for m in self.received if m.get("method") == "mining.submit"]

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._writer = writer
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                msg = json.loads(line.decode().strip())
                self.received.append(msg)
                method = msg.get("method")
                mid = msg.get("id")
                if method == "mining.subscribe":
                    await self._send(
                        writer,
                        {
                            "id": mid,
                            "result": [
                                [
                                    ["mining.set_difficulty", "b4b6693b72a50c7116db18d6497cac52"],
                                    ["mining.notify", "ae6812eb4cd7735a302a8a9dd95cf71f"],
                                ],
                                "08000002",
                                4,
                            ],
                            "error": None,
                        },
                    )
                elif method == "mining.authorize":
                    await self._send(writer, {"id": mid, "result": True, "error": None})
                    # Deliver an initial job promptly so connect()'s
                    # first-job wait does not stall for its full 10s bound.
                    await self.broadcast_job(job_id=self.default_job_id)
                elif method == "mining.submit":
                    if self.submit_ack_mode == "held":
                        await self.submit_gate.wait()
                    elif self.submit_ack_mode == "delayed" and self.submit_delay:
                        await asyncio.sleep(self.submit_delay)
                    if self.submit_ack_mode == "reject":
                        await self._send(
                            writer,
                            {"id": mid, "result": None, "error": [20, "mock reject", ""]},
                        )
                    else:
                        await self._send(writer, {"id": mid, "result": True, "error": None})
        except Exception:
            pass
        finally:
            try:
                writer.close()
            except Exception:
                pass
            if self._writer is writer:
                self._writer = None

    @staticmethod
    async def _send(writer: asyncio.StreamWriter, msg: Dict[str, Any]):
        writer.write((json.dumps(msg) + "\n").encode())
        await writer.drain()

    async def broadcast_job(self, job_id: str = "jobA", clean_jobs: bool = False):
        if self._writer is None:
            raise RuntimeError("No client connected to mock pool.")
        notify = {
            "id": None,
            "method": "mining.notify",
            "params": [
                job_id,
                "00" * 32,
                "01000000",
                "00",
                [],
                "00000002",
                "1c2ac4af",
                "66e85501",
                clean_jobs,
            ],
        }
        await self._send(self._writer, notify)


@pytest.fixture
def events(monkeypatch):
    """Capture record_mining_event emissions without a real evidence ledger."""
    captured: List[tuple] = []
    monkeypatch.setattr(
        sc, "record_mining_event", lambda name, payload: captured.append((name, payload))
    )
    return captured


@pytest.fixture
def armed_env(monkeypatch):
    """Arm pool egress + live submit for the duration of one test."""
    monkeypatch.setenv("HYBA_ENABLE_LIVE_STRATUM", "true")
    monkeypatch.setenv("HYBA_ENABLE_LIVE_SHARE_SUBMIT", "true")
    monkeypatch.setenv("HYBA_AUTONOMOUS_EXTERNAL_ACTIONS", "true")


def make_client(server: MockStratumServer, monkeypatch) -> sc.StratumClient:
    """Client pinned to the mock server only -- never touches real pools."""
    monkeypatch.setenv("HYBA_POOL_URL_FAILOVER", f"127.0.0.1:{server.port}")
    monkeypatch.setattr(sc.StratumClient, "DEFAULT_POOLS", [])
    client = sc.StratumClient(
        pool_url=f"127.0.0.1:{server.port}", worker_name="acct.worker1", password="x"
    )
    client.submit_timeout_seconds = 0.5
    return client


async def _wait_for(predicate, timeout: float = 3.0, interval: float = 0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return predicate()


# ---------------------------------------------------------------------------
# M1: submit ids never collide with the reserved handshake range
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_ids_clear_handshake_range_and_survive_reconnect(armed_env, monkeypatch):
    server = MockStratumServer()
    await server.start()
    client = make_client(server, monkeypatch)
    try:
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await _wait_for(lambda: client.current_job is not None)

        accepted, req_id = await client.submit_share(
            job_id=client.current_job["job_id"], nonce="00000001"
        )
        assert accepted is True
        submits = server.submits()
        assert len(submits) == 1
        assert submits[0]["id"] == req_id >= sc._SUBMIT_ID_FLOOR
        assert req_id not in sc._HANDSHAKE_REQUEST_IDS
        assert client.pool_accepted == 1

        # Reconnect: the counter must NOT be reseeded by connect().
        await client.close()
        await asyncio.sleep(0.05)
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await _wait_for(lambda: client.current_job is not None)
        accepted2, req_id2 = await client.submit_share(
            job_id=client.current_job["job_id"], nonce="00000002"
        )
        assert accepted2 is True
        assert req_id2 > req_id

        # Forcing the counter back into the reserved range hard-fails the
        # submit BEFORE any wire write (no share verdict can be swallowed).
        client._submit_counter = 1
        before = len(server.submits())
        with pytest.raises(RuntimeError):
            await client.submit_share(job_id=client.current_job["job_id"], nonce="00000003")
        assert len(server.submits()) == before
    finally:
        await client.close()
        await server.stop()


# ---------------------------------------------------------------------------
# M2: late pool verdicts reconcile instead of being dropped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_late_ack_reconciles_into_pool_accepted(armed_env, monkeypatch, events):
    server = MockStratumServer(submit_ack_mode="delayed", submit_delay=0.4)
    await server.start()
    client = make_client(server, monkeypatch)
    client.submit_timeout_seconds = 0.1
    try:
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await _wait_for(lambda: client.current_job is not None)
        job_id = client.current_job["job_id"]

        accepted, req_id = await client.submit_share(job_id=job_id, nonce="00000001")
        assert accepted is False  # timed out locally
        assert client.shares_timed_out == 1
        assert client.pool_accepted == 0
        assert req_id in client._late_acks

        # The delayed verdict arrives inside the grace window: reconcile.
        assert await _wait_for(lambda: client.pool_accepted == 1, timeout=3.0)
        assert client.late_acks_reconciled == 1
        assert req_id not in client._late_acks
        late_events = [p for n, p in events if n == "share_accepted_late"]
        assert len(late_events) == 1
        assert late_events[0]["job_id"] == job_id
        assert late_events[0]["truth_class"] == "pool-confirmed-late"
    finally:
        await client.close()
        await server.stop()


# ---------------------------------------------------------------------------
# M3: firewall validation never advances the pool-confirmed counter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_firewall_validation_counters_are_separate(armed_env, monkeypatch):
    server = MockStratumServer()
    await server.start()
    client = make_client(server, monkeypatch)
    try:
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await _wait_for(lambda: client.current_job is not None)
        job_id = client.current_job["job_id"]

        # Close the live-submit gate -> the firewall path validates locally.
        monkeypatch.setattr(client, "is_live_submit_approved", lambda: False)
        client.target = "ff" * 32  # every digest passes
        accepted, req_id = await client.submit_share(job_id=job_id, nonce="00000001")
        assert accepted is True
        assert req_id == sc.UNSUBMITTED_REQUEST_ID
        assert client.firewall_accepted == 1
        assert client.pool_accepted == 0
        assert server.submits() == []  # nothing ever reached the wire

        client.target = "00" * 32  # nothing passes
        accepted2, _ = await client.submit_share(job_id=job_id, nonce="00000002")
        assert accepted2 is False
        assert client.firewall_rejected == 1
        assert client.pool_rejected == 0
        # Aggregate compatibility: shares_accepted still reports the total.
        assert client.shares_accepted == 1
        assert client.shares_rejected == 1
    finally:
        await client.close()
        await server.stop()


# ---------------------------------------------------------------------------
# M4: evidence events carry the submit-time job, not the current one
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_share_verdict_attributed_to_submit_time_job(armed_env, monkeypatch, events):
    server = MockStratumServer(submit_ack_mode="held")
    server.submit_gate.clear()
    await server.start()
    client = make_client(server, monkeypatch)
    try:
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await _wait_for(lambda: client.current_job is not None)
        job_a = client.current_job["job_id"]

        task = asyncio.create_task(client.submit_share(job_id=job_a, nonce="00000001"))
        assert await _wait_for(lambda: len(server.submits()) == 1)

        # A notify lands between submit and ACK -- the verdict must still be
        # attributed to job_a, the job the share was built against.
        await server.broadcast_job(job_id="jobB", clean_jobs=False)
        assert await _wait_for(lambda: (client.current_job or {}).get("job_id") == "jobB")

        server.submit_gate.set()
        accepted, _ = await asyncio.wait_for(task, timeout=3.0)
        assert accepted is True
        accepted_events = [p for n, p in events if n == "share_accepted"]
        assert len(accepted_events) == 1
        assert accepted_events[0]["job_id"] == job_a
    finally:
        await client.close()
        await server.stop()


# ---------------------------------------------------------------------------
# M5: disconnect/reconnect invalidates session state and pending futures
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disconnect_fails_pending_submissions_and_invalidates_session(armed_env, monkeypatch):
    server = MockStratumServer(submit_ack_mode="held")
    server.submit_gate.clear()  # pool never answers: verdict depends on EOF
    await server.start()
    client = make_client(server, monkeypatch)
    client.submit_timeout_seconds = 30.0  # prove the failure isn't the timeout
    try:
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await _wait_for(lambda: client.current_job is not None)
        epoch0 = client.session_epoch
        job_id = client.current_job["job_id"]

        task = asyncio.create_task(client.submit_share(job_id=job_id, nonce="00000001"))
        assert await _wait_for(lambda: len(server.submits()) == 1)

        await server.drop_client()  # remote EOF on the client side
        accepted, req_id = await asyncio.wait_for(task, timeout=5.0)
        assert accepted is False
        assert client.shares_transport_failed == 1
        assert client.session_epoch > epoch0
        assert req_id not in client._pending_futures
        assert req_id not in client._late_acks
    finally:
        await client.close()
        await server.stop()


@pytest.mark.asyncio
async def test_new_session_invalidates_prior_job_context(armed_env, monkeypatch):
    server = MockStratumServer()
    await server.start()
    client = make_client(server, monkeypatch)
    try:
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await _wait_for(lambda: client.current_job is not None)
        epoch0 = client.session_epoch
        job_epoch0 = client.current_job.get("job_epoch")
        old_job = client.current_job["job_id"]

        await client.close()
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert client.session_epoch > epoch0

        # A share carrying the prior session's job epoch is refused before
        # the wire even when the pool re-issues the same job id -- the
        # extranonce1 it was hashed against is dead.
        ok, req_id = await client.submit_share(
            job_id=old_job, nonce="00000001", job_epoch=job_epoch0
        )
        assert ok is False
        assert req_id == sc.UNSUBMITTED_REQUEST_ID

        # A share naming a job that does not exist in the new session at all
        # is refused by the stale-job check.
        ok2, req_id2 = await client.submit_share(job_id="definitely-retired-job", nonce="00000002")
        assert ok2 is False
        assert req_id2 == sc.UNSUBMITTED_REQUEST_ID
        assert client.stale_submissions_rejected >= 2
        assert server.submits() == []
    finally:
        await client.close()
        await server.stop()


# ---------------------------------------------------------------------------
# M6: clean_jobs bumps job_epoch and retires in-flight context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clean_jobs_retires_stale_submissions(armed_env, monkeypatch):
    server = MockStratumServer()
    await server.start()
    client = make_client(server, monkeypatch)
    try:
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await _wait_for(lambda: client.current_job is not None)
        job_a = client.current_job["job_id"]
        epoch_a = client.job_epoch

        # clean_jobs=true: job_epoch bumps, queue drains, current_job moves.
        await server.broadcast_job(job_id="jobB", clean_jobs=True)
        assert await _wait_for(lambda: (client.current_job or {}).get("job_id") == "jobB")
        assert client.job_epoch == epoch_a + 1
        assert client.current_job["job_epoch"] == epoch_a + 1

        before = len(server.submits())

        # (a) old job id -> stale-job rejection, nothing on the wire.
        ok, req_id = await client.submit_share(job_id=job_a, nonce="00000001")
        assert ok is False
        assert req_id == sc.UNSUBMITTED_REQUEST_ID

        # (b) current job id but the pre-clean epoch -> epoch rejection.
        ok2, req_id2 = await client.submit_share(job_id="jobB", nonce="00000002", job_epoch=epoch_a)
        assert ok2 is False
        assert req_id2 == sc.UNSUBMITTED_REQUEST_ID

        assert client.stale_submissions_rejected >= 2
        assert len(server.submits()) == before

        # Same-epoch notify (clean_jobs=false) must NOT bump the epoch.
        await server.broadcast_job(job_id="jobC", clean_jobs=False)
        assert await _wait_for(lambda: (client.current_job or {}).get("job_id") == "jobC")
        assert client.job_epoch == epoch_a + 1
    finally:
        await client.close()
        await server.stop()


# ---------------------------------------------------------------------------
# Advisory 2: soft reconnect (client.reconnect on the SAME socket) is visible
# but must NOT invalidate the session or pending shares. Only a genuinely
# new socket (connect()/EOF) may bump session_epoch.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_reconnect_preserves_pending_shares(armed_env, monkeypatch, events):
    server = MockStratumServer(submit_ack_mode="held")
    await server.start()
    client = make_client(server, monkeypatch)
    try:
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await _wait_for(lambda: client.current_job is not None)
        epoch0 = client.session_epoch
        job_epoch0 = client.job_epoch

        # Put a share in flight with the pool holding its ACK.
        server.submit_gate.clear()
        submit_task = asyncio.create_task(
            client.submit_share(job_id=client.current_job["job_id"], nonce="00000001")
        )
        assert await _wait_for(lambda: len(client._pending_futures) == 1)

        # Soft reconnect: pool sends client.reconnect over the same socket.
        await MockStratumServer._send(
            server._writer,
            {"id": None, "method": "client.reconnect", "params": ["other.pool.io", "3333"]},
        )
        assert await _wait_for(lambda: client.client_reconnects == 1)

        # In-flight share must NOT be failed; session/job epochs untouched.
        assert not submit_task.done()
        assert len(client._pending_futures) == 1
        assert client.session_epoch == epoch0
        assert client.job_epoch == job_epoch0
        assert client.current_job is not None

        # Release the ACK -- the share still resolves to a pool verdict.
        server.submit_gate.set()
        ok, req_id = await asyncio.wait_for(submit_task, timeout=3.0)
        assert ok is True
        assert req_id >= sc._SUBMIT_ID_FLOOR
        assert client.pool_accepted == 1
        assert client.session_epoch == epoch0
        assert not any(
            name == "share_rejected" or "invalidated" in str(payload).lower()
            for name, payload in events
        )
    finally:
        await client.close()
        await server.stop()


@pytest.mark.asyncio
async def test_hard_reconnect_still_bumps_session_epoch(armed_env, monkeypatch):
    """Mirror check: a real new socket is still the invalidation boundary."""
    server = MockStratumServer(submit_ack_mode="held")
    await server.start()
    client = make_client(server, monkeypatch)
    try:
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await _wait_for(lambda: client.current_job is not None)
        epoch0 = client.session_epoch

        # In-flight share held by the pool -- a real new socket must fail it.
        server.submit_gate.clear()
        submit_task = asyncio.create_task(
            client.submit_share(job_id=client.current_job["job_id"], nonce="00000001")
        )
        assert await _wait_for(lambda: len(client._pending_futures) == 1)

        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await _wait_for(lambda: client.current_job is not None)
        # The old socket's teardown AND the new socket's setup are each a
        # real session boundary; the epoch must strictly increase.
        assert client.session_epoch > epoch0
        # The pending future was failed with ConnectionError; submit_share
        # surfaces that as a transport failure rather than a pool verdict.
        ok, req_id = await asyncio.wait_for(submit_task, timeout=3.0)
        assert ok is False
        assert client.pool_accepted == 0
        assert client.shares_transport_failed >= 1
        assert len(client._pending_futures) == 0
    finally:
        await client.close()
        await server.stop()
