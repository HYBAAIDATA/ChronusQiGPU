"""Canonical mining path executed end-to-end against a verifying pool.

The loopback server in this file is NOT a fixture boolean: on every
``mining.submit`` it rebuilds the coinbase from extranonce1 + the submitted
extranonce2, folds the merkle branch, rebuilds the 80-byte header, hashes
SHA256d, and compares against the target it announced — ``result: true`` only
for a share that really meets it. The driver is the same code ``pythia-mine``
runs: ``mining_runtime._main_async`` → endpoint resolution → backend
selection → ``GeodesicProductionMiningCoordinator.run_execution_loop`` →
leased SearchPlan → ExecutionRouter (CPU reference hasher) → ``StratumClient``
→ ``StratumProofAdapter.validate_candidate`` → ``mining.submit`` → pool
verdict → ``MiningSession.share_log`` on disk. Only the server is test code;
nothing else is simulated. This is loopback evidence of the canonical
submit→verdict→durable-recording path — not evidence against a live pool.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import struct
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import mining_runtime
from test_agentic_voyages import bip34_coinb1, _line, until

DIFF1_TARGET = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
# A loopback share difficulty: ~2^8 expected SHA256d per accepted share —
# real grinding across several leased windows on the CPU lane, never
# trivially-easy (EASY_TARGET accepts any hash). The canonical CPU reference
# lane leases lucas(rung) nonces per plan (96 at the starting rung) under the
# exact profile with strict-M3 authorisation and custody on every window, so
# the former ~2^18 (thousands of windows per share) cannot complete in a test
# budget. Throughput lanes (OpenCL) lease their measured launch cap instead.
LOOPBACK_DIFFICULTY = 2.0**-24
LOOPBACK_TARGET = DIFF1_TARGET * (1 / LOOPBACK_DIFFICULTY)


def _stratum_prevhash_to_header_bytes(prevhash_hex: str) -> bytes:
    raw = bytes.fromhex(prevhash_hex)
    return b"".join(raw[index : index + 4][::-1] for index in range(0, 32, 4))


def _coinb2() -> str:
    # A standard single-P2PKH-output generation tail (all-zero pubkey hash).
    return (
        "ffffffff"
        "01"
        "00f2052a01000000"
        "1976a914" + "00" * 20 + "88ac"
        "00000000"
    )


def _job_params(job_id: str, *, height: int = 900_001, ntime: str = "65abcdef") -> list:
    return [
        job_id,
        "77" * 32,  # prevhash (network order, as pools send it)
        bip34_coinb1(height),
        _coinb2(),
        [],
        "20000000",
        "1d00ffff",
        ntime,
        True,
    ]


class VerifyingStratumPool:
    """Loopback Stratum V1 pool whose verdict is a recomputation, not a stub.

    Every ``mining.submit`` is verified wire-side: job binding, authorized
    worker, extranonce2 width, ntime/nonce shape, coinbase + merkle rebuild,
    header rebuild, SHA256d vs the announced target. Verdicts are appended to
    a JSONL pool log so the run leaves an independent record of what the pool
    actually decided.
    """

    EXTRANONCE1 = "f0042aa9"
    EXTRANONCE2_SIZE = 4

    def __init__(
        self,
        *,
        difficulty: float = LOOPBACK_DIFFICULTY,
        worker: str | None = None,
        log_path: Path | None = None,
    ) -> None:
        self.difficulty = difficulty
        self.target = int(DIFF1_TARGET * (1 / difficulty))
        self.worker = worker
        self.log_path = Path(log_path) if log_path else None
        self.jobs: dict[str, list] = {}
        self.current_job: list | None = None
        self.verdicts: list[dict] = []
        self.connections = 0

    def _log(self, event: dict) -> None:
        if self.log_path is not None:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, sort_keys=True) + "\n")

    def add_job(self, params: list) -> None:
        self.jobs[str(params[0])] = list(params)
        self.current_job = list(params)

    def _verify_share(self, params: list) -> tuple[bool, str, dict]:
        """Recompute the submitted share from wire params only."""
        detail: dict = {"params": list(params)}
        if len(params) != 5:
            return False, "wrong arity", detail
        worker, job_id, extranonce2, ntime, nonce_hex = params
        if self.worker is not None and worker != self.worker:
            return False, "unauthorized worker", detail
        job = self.jobs.get(job_id)
        if job is None:
            return False, "unknown job", detail
        try:
            en2 = bytes.fromhex(extranonce2)
            ntime_b = bytes.fromhex(ntime)
            nonce_b = bytes.fromhex(nonce_hex)
        except ValueError:
            return False, "malformed hex field", detail
        if len(en2) != self.EXTRANONCE2_SIZE:
            return False, "extranonce2 width", detail
        if len(ntime_b) != 4 or len(nonce_b) != 4:
            return False, "field width", detail
        _job_id, prevhash, coinb1, coinb2, merkle_branch, version, nbits, _nt, _cl = job
        coinbase = bytes.fromhex(coinb1 + self.EXTRANONCE1 + extranonce2 + coinb2)
        root = hashlib.sha256(hashlib.sha256(coinbase).digest()).digest()
        for branch in merkle_branch:
            root = hashlib.sha256(
                hashlib.sha256(root + bytes.fromhex(branch)).digest()
            ).digest()
        header = (
            bytes.fromhex(version)[::-1]
            + _stratum_prevhash_to_header_bytes(prevhash)
            + root
            + ntime_b[::-1]
            + bytes.fromhex(nbits)[::-1]
            + nonce_b[::-1]
        )
        digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        meets = int.from_bytes(digest, "little") <= self.target
        detail.update(
            block_hash=digest[::-1].hex(),
            digest_le=digest.hex(),
            target=f"{self.target:064x}",
            meets_target=meets,
        )
        return meets, ("share accepted" if meets else "low difficulty share"), detail

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.connections += 1
        authorized_worker: str | None = None
        try:
            subscribe = json.loads(await reader.readline())
            writer.write(
                _line(
                    {
                        "id": subscribe["id"],
                        "result": [
                            [["mining.notify", "ae12"]],
                            self.EXTRANONCE1,
                            self.EXTRANONCE2_SIZE,
                        ],
                        "error": None,
                    }
                )
            )
            authorize = json.loads(await reader.readline())
            authorized_worker = str(authorize["params"][0])
            allowed = self.worker is None or authorized_worker == self.worker
            writer.write(
                _line({"id": authorize["id"], "result": allowed, "error": None})
            )
            await writer.drain()
            if not allowed:
                return
            writer.write(
                _line(
                    {
                        "id": None,
                        "method": "mining.set_difficulty",
                        "params": [self.difficulty],
                    }
                )
            )
            if self.current_job is not None:
                writer.write(
                    _line(
                        {
                            "id": None,
                            "method": "mining.notify",
                            "params": self.current_job,
                        }
                    )
                )
            await writer.drain()
            while line := await reader.readline():
                message = json.loads(line)
                if message.get("method") != "mining.submit":
                    continue
                params = message.get("params") or []
                accepted, reason, detail = self._verify_share(list(params))
                verdict = {
                    "event": "mining.submit",
                    "worker": authorized_worker,
                    "accepted": accepted,
                    "reason": reason,
                    **detail,
                }
                self.verdicts.append(verdict)
                self._log(verdict)
                writer.write(
                    _line(
                        {"id": message["id"], "result": accepted, "error": None}
                    )
                )
                await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError, json.JSONDecodeError):
            pass
        finally:
            writer.close()


async def _served(pool: VerifyingStratumPool):
    server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


# ── the pool is a real verifier ────────────────────────────────────────── #


async def _roundtrip(port: int, messages: list[dict]) -> list[dict]:
    """Send JSON-lines on a raw socket and collect replies; no StratumClient."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    out: list[dict] = []
    try:
        for message in messages:
            writer.write(_line(message))
            await writer.drain()
        # Drain notifications until every request id has a reply.
        want = {m["id"] for m in messages}
        deadline = time.monotonic() + 10
        while want and time.monotonic() < deadline:
            reply = json.loads(await reader.readline())
            out.append(reply)
            want.discard(reply.get("id"))
    finally:
        writer.close()
    return out


def test_loopback_pool_rejects_a_share_that_misses_the_target():
    """A well-formed share that does not meet the announced target is refused."""

    async def _go() -> None:
        pool = VerifyingStratumPool(difficulty=1.0, worker="rig.1")
        job = _job_params("job-neg")
        pool.add_job(job)
        server, port = await _served(pool)
        try:
            # Pick a nonce that provably misses the diff-1 target so the
            # verdict is the pool's real verification, never an accident.
            en2 = "00000000"
            coinbase = bytes.fromhex(job[2] + pool.EXTRANONCE1 + en2 + job[3])
            root = hashlib.sha256(hashlib.sha256(coinbase).digest()).digest()
            base = (
                bytes.fromhex(job[5])[::-1]
                + _stratum_prevhash_to_header_bytes(job[1])
                + root
                + bytes.fromhex(job[7])[::-1]
                + bytes.fromhex(job[6])[::-1]
            )
            nonce = next(
                n
                for n in range(4096)
                if int.from_bytes(
                    hashlib.sha256(
                        hashlib.sha256(base + struct.pack("<I", n)).digest()
                    ).digest(),
                    "little",
                )
                > pool.target
            )
            replies = await _roundtrip(
                port,
                [
                    {"id": 1, "method": "mining.subscribe", "params": ["t/1"]},
                    {"id": 2, "method": "mining.authorize", "params": ["rig.1", "x"]},
                    {
                        "id": 3,
                        "method": "mining.submit",
                        "params": ["rig.1", "job-neg", en2, job[7], f"{nonce:08x}"],
                    },
                ],
            )
            submit_reply = next(r for r in replies if r.get("id") == 3)
            assert submit_reply["result"] is False
            assert pool.verdicts[-1]["accepted"] is False
            assert pool.verdicts[-1]["meets_target"] is False
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(_go())


def test_loopback_pool_rejects_wrong_worker_and_unknown_job():
    async def _go() -> None:
        pool = VerifyingStratumPool(difficulty=1.0, worker="rig.1")
        pool.add_job(_job_params("job-w"))
        server, port = await _served(pool)
        try:
            replies = await _roundtrip(
                port,
                [
                    {"id": 1, "method": "mining.subscribe", "params": ["t/1"]},
                    {"id": 2, "method": "mining.authorize", "params": ["rig.1", "x"]},
                    {
                        "id": 3,
                        "method": "mining.submit",
                        "params": [
                            "rig.other",
                            "job-w",
                            "00000000",
                            "65abcdef",
                            "00000000",
                        ],
                    },
                    {
                        "id": 4,
                        "method": "mining.submit",
                        "params": [
                            "rig.1",
                            "job-unknown",
                            "00000000",
                            "65abcdef",
                            "00000000",
                        ],
                    },
                ],
            )
            by_id = {r["id"]: r for r in replies}
            assert by_id[3]["result"] is False
            assert by_id[4]["result"] is False
            assert [v["reason"] for v in pool.verdicts] == [
                "unauthorized worker",
                "unknown job",
            ]
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(_go())


# ── the canonical path, executed ────────────────────────────────────────── #


def test_canonical_loopback_submit_to_pool_verdict_and_durable_recording(
    tmp_path, monkeypatch
):
    """pythia-mine's code path: submit → pool verdict → durable share_log.

    Drives ``mining_runtime._main_async`` (what the ``pythia-mine`` entry
    point calls) against the verifying loopback pool on the CPU lane with
    submission armed (``--submit``) and the M3 storage plane enabled. Asserts
    the pool's verdict, the durable MiningSession share_log entry, the causal
    ledger, and THESEUS-custodied mining records — and that the share hash the
    pool verified is the one the session recorded.
    """
    worker = "loopback.evidence"
    session_path = tmp_path / "mining_session.json"
    pool_log = tmp_path / "pool_verdicts.jsonl"

    monkeypatch.setenv("PYTHIA_ALLOW_UNLISTED_POOLS", "1")
    monkeypatch.setenv("PYTHIA_POOLS", "braiins")
    monkeypatch.setenv("PYTHIA_EXECUTION_DEVICE", "cpu")
    monkeypatch.setenv("PYTHIA_MINING_SESSION_PATH", str(session_path))
    monkeypatch.setenv("PYTHIA_MINING_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("PYTHIA_CAUSAL_LOG_PATH", str(tmp_path / "causal_ledger.jsonl"))
    monkeypatch.setenv(
        "PYTHIA_BACKEND_EVIDENCE_PATH", str(tmp_path / "backend_decisions.jsonl")
    )
    monkeypatch.setenv("PYTHIA_INTELLIGENCE_DIR", str(tmp_path / "intelligence"))
    monkeypatch.setenv(
        "PYTHIA_TELEMETRY_HISTORY_PATH", str(tmp_path / "telemetry_history.jsonl")
    )
    monkeypatch.setenv(
        "PYTHIA_RETARGET_TELEMETRY_PATH", str(tmp_path / "retarget_windows.json")
    )
    monkeypatch.setenv("PYTHIA_AGENTIC_STATE_PATH", str(tmp_path / "agentic.json"))
    monkeypatch.setenv(
        "PYTHIA_SALAMANDER_EVIDENCE_PATH", str(tmp_path / "salamander.jsonl")
    )
    monkeypatch.setenv("PYTHIA_WORKER_HEARTBEAT_DIR", str(tmp_path / "hb"))
    # The coordinator control socket is AF_UNIX; pytest's tmp_path plus a
    # long test name can exceed the ~108-char sun_path limit on Windows, so
    # give it a short path of its own.
    short_tmp = Path(tempfile.mkdtemp(prefix="lb-sock-"))
    monkeypatch.setenv(
        "MLA1517_COORDINATOR_CONTROL_SOCKET", str(short_tmp / "ctl.sock")
    )
    monkeypatch.setenv("PYTHIA_IDENTITY_HMAC_SECRET", "ab" * 32)
    # M3 storage plane: THESEUS-custodied mining records for the same voyage.
    # Live submission requires strict M3: provision the real AL HARAS +
    # THESEUS custody plane and admit the tenant as an operator would.
    from strict_m3_fixture import provision_strict_m3

    provision_strict_m3(
        tmp_path,
        monkeypatch.setenv,
        overrides={
            "PYTHIA_STORAGE_DB": str(tmp_path / "hyba.sqlite3"),
            "PYTHIA_STORAGE_ROOT": str(tmp_path / "cas"),
            "PYTHIA_STORAGE_CUSTODY_ROOT": str(tmp_path / "theseus-custody"),
            "PYTHIA_STORAGE_INTEGRITY_KEY_HEX": "11" * 32,
            "PYTHIA_STORAGE_CUSTODY_KEY_HEX": "22" * 32,
        },
    )
    monkeypatch.delenv("PYTHIA_BITCOIN_RPC_URL", raising=False)
    monkeypatch.delenv("PYTHIA_BITCOIN_NETWORK", raising=False)

    async def _run() -> dict:
        pool = VerifyingStratumPool(
            difficulty=LOOPBACK_DIFFICULTY, worker=worker, log_path=pool_log
        )
        pool.add_job(_job_params("job-e2e"))
        server, port = await _served(pool)
        monkeypatch.setenv("MLA1517_STRATUM_ENDPOINT", f"127.0.0.1:{port}")
        monkeypatch.setenv("MLA1517_STRATUM_USER", worker)
        args = SimpleNamespace(
            device=None,
            user=worker,
            password="x",
            submit=True,
            tls=False,
            map_bytes=8192,
            difficulty_mask=0,
            base_step=0,
            log_level="INFO",
        )
        task = asyncio.create_task(mining_runtime._main_async(args))
        try:
            def accepted_shares() -> list[dict]:
                if not session_path.exists():
                    return []
                try:
                    data = json.loads(session_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    return []
                return [
                    e
                    for e in data.get("share_log", [])
                    if e.get("state") == "ACCEPTED"
                ]

            try:
                await until(
                    lambda: len(accepted_shares()) >= 2,
                    timeout=240.0,
                    what="two pool-ACCEPTED shares in the durable share_log",
                )
            except AssertionError:
                state = None
                if session_path.exists():
                    try:
                        state = json.loads(
                            session_path.read_text(encoding="utf-8")
                        )
                    except json.JSONDecodeError:
                        state = "unparseable"
                raise AssertionError(
                    "canonical path produced no pool-ACCEPTED share; "
                    f"session_state={state!r} pool_connections="
                    f"{pool.connections} verdicts={pool.verdicts!r} "
                    f"runtime_alive={not task.done()}"
                )
            await asyncio.sleep(0.3)  # let the verdict write + recorder settle
            return {"share_log": accepted_shares(), "verdicts": list(pool.verdicts)}
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            server.close()
            await server.wait_closed()

    outcome = asyncio.run(_run())

    # The pool's verdict: at least two accepted shares, each independently
    # recomputed against the announced target.
    accepted_verdicts = [v for v in outcome["verdicts"] if v["accepted"]]
    assert len(accepted_verdicts) >= 2
    assert all(v["meets_target"] for v in accepted_verdicts)

    # Durable recording: the session file's share_log carries the same
    # display-order block hash the pool recomputed — verdict and custody
    # describe the same share.
    pool_hashes = {v["block_hash"] for v in accepted_verdicts}
    logged = {e["block_hash"] for e in outcome["share_log"]}
    assert logged & pool_hashes
    assert all(
        e["state"] == "ACCEPTED" and e.get("job_id") == "job-e2e"
        for e in outcome["share_log"]
    )

    # The causal voyage ledger was written.
    causal = tmp_path / "causal_ledger.jsonl"
    assert causal.exists() and '"submission_sent"' in causal.read_text(
        encoding="utf-8"
    )

    # Backend selection evidence exists for the CPU lane actually used.
    backend_log = tmp_path / "backend_decisions.jsonl"
    assert backend_log.exists()

    # THESEUS custody: the storage plane wrote custodied records for the
    # submission boundary (P1-6: shares leave process-local state).
    assert (tmp_path / "hyba.sqlite3").exists()
    assert any((tmp_path / "theseus-custody").rglob("*"))
    assert any((tmp_path / "cas").rglob("*"))
