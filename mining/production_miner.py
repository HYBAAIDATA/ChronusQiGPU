"""Production Stratum V1 miner for the PYTHIA Bitcoin SHA-256d path.

This module is intentionally boring at the protocol boundary. HYBA/M32/TOE
components may order or partition nonce work, but the only acceptance predicate
is the exact 80-byte header, SHA-256d, and negotiated pool target.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import logging
import os
import signal
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .bitcoin_hasher import BitcoinHasher
from .stratum_bridge import build_header80
from toe.strict_quantum import certify_work_window, verify_certificate

LOG = logging.getLogger("pythia.production_miner")
MAX_UINT256 = (1 << 256) - 1
DIFF1_TARGET = 0x00000000FFFF0000000000000000000000000000000000000000000000000000


class ProtocolError(RuntimeError):
    pass


class SessionLost(ConnectionError):
    pass


@dataclass(frozen=True)
class PoolSpec:
    endpoint: "PoolEndpoint"
    worker: str
    password: str


@dataclass(frozen=True)
class PoolEndpoint:
    host: str
    port: int
    tls: bool


@dataclass(frozen=True)
class MiningJob:
    generation: int
    job_id: str
    prevhash: str
    coinb1: str
    coinb2: str
    merkle_branch: tuple[str, ...]
    version: str
    nbits: str
    ntime: str
    clean_jobs: bool
    target: int | None


def parse_endpoint(value: str) -> PoolEndpoint:
    """Parse host:port, stratum+tcp://, or stratum+ssl:// safely."""
    raw = value.strip()
    if not raw:
        raise ValueError("pool endpoint is empty")
    if "://" not in raw:
        raw = "stratum+tcp://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"stratum+tcp", "stratum+ssl", "stratum+tls", "tcp", "tls"}:
        raise ValueError(f"unsupported pool scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise ValueError("pool endpoint has no hostname")
    port = parsed.port or 3333
    if not 1 <= port <= 65535:
        raise ValueError("pool port is outside 1..65535")
    return PoolEndpoint(parsed.hostname, port, parsed.scheme in {"stratum+ssl", "stratum+tls", "tls"})


def parse_pool_spec(value: str) -> PoolSpec:
    """Parse endpoint|worker|password without persisting credentials."""
    parts = value.split("|", 2)
    if len(parts) != 3 or not all(parts):
        raise ValueError("pool spec must be endpoint|worker|password")
    return PoolSpec(parse_endpoint(parts[0]), parts[1], parts[2])


def configured_pool_specs(args: argparse.Namespace) -> list[PoolSpec]:
    raw_specs = list(args.pool_spec or [])
    if not raw_specs and os.getenv("PYTHIA_POOL_SPECS"):
        raw_specs = [item.strip() for item in os.environ["PYTHIA_POOL_SPECS"].split(";") if item.strip()]
    if raw_specs:
        return [parse_pool_spec(item) for item in raw_specs]
    if not args.pool or not args.worker or args.password is None:
        raise SystemExit("configure --pool/--worker/--password or PYTHIA_POOL_SPECS")
    return [PoolSpec(parse_endpoint(args.pool), args.worker, args.password)]


def _hex(value: Any, name: str, length: int | None = None) -> str:
    if not isinstance(value, str) or len(value) % 2:
        raise ProtocolError(f"{name} must be even-length hexadecimal")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise ProtocolError(f"{name} is not hexadecimal") from exc
    if length is not None and len(value) != length:
        raise ProtocolError(f"{name} must be exactly {length // 2} bytes")
    return value.lower()


def _dsha256(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()


def difficulty_target(difficulty: Any) -> int:
    """floor(DIFF1_TARGET / difficulty) as an exact rational.

    ``Fraction(str(difficulty))`` is exact for every pool wire form (int,
    float repr, decimal string); non-finite or malformed values raise before
    any arithmetic. No Decimal context precision — the quotient carries full
    256-bit precision before the floor. Same convention as
    ``mla1517.mining.stratum_adapter._target_from_difficulty``.
    """
    try:
        value = Fraction(str(difficulty))
    except (ValueError, ZeroDivisionError) as exc:
        raise ProtocolError("difficulty is not numeric") from exc
    if value <= 0:
        raise ProtocolError("difficulty must be positive and finite")
    quotient = Fraction(DIFF1_TARGET, 1) / value
    target = quotient.numerator // quotient.denominator
    if not 0 < target <= MAX_UINT256:
        raise ProtocolError("difficulty target is outside uint256")
    return target


def target_from_hex(value: Any) -> int:
    value = _hex(value, "target", 64)
    target = int(value, 16)
    if not 0 < target <= MAX_UINT256:
        raise ProtocolError("target must be positive uint256")
    return target


def _format_rate(hps: float) -> str:
    """Measured wall-clock rate in the unit that reads cleanly."""
    if hps >= 1e9:
        return f"{hps / 1e9:.2f} GH/s"
    if hps >= 1e6:
        return f"{hps / 1e6:.2f} MH/s"
    if hps >= 1e3:
        return f"{hps / 1e3:.2f} kH/s"
    return f"{hps:.2f} H/s"


def build_job_header(job: MiningJob, extranonce1: str, extranonce2: str) -> bytes:
    """Build the exact 80-byte wire header from a Stratum V1 job."""
    coinbase = bytes.fromhex(job.coinb1 + extranonce1 + extranonce2 + job.coinb2)
    root = _dsha256(coinbase)
    for branch in job.merkle_branch:
        # Stratum V1 supplies branch hashes in the internal byte order used by
        # the mining protocol. This is the same convention as the existing
        # proven bridge and its integration fixtures.
        root = _dsha256(root + bytes.fromhex(branch))
    return build_header80(job.version, job.prevhash, root[::-1].hex(), job.ntime, job.nbits)


def parse_notify(params: Any, generation: int, target: int | None) -> MiningJob:
    if not isinstance(params, list) or len(params) != 9:
        raise ProtocolError("mining.notify must contain exactly nine parameters")
    job_id, prevhash, coinb1, coinb2, branches, version, nbits, ntime, clean = params
    if not isinstance(job_id, str) or not job_id:
        raise ProtocolError("job id must be non-empty")
    if not isinstance(branches, list):
        raise ProtocolError("merkle branches must be an array")
    if not isinstance(clean, bool):
        raise ProtocolError("clean_jobs must be boolean")
    return MiningJob(
        generation=generation,
        job_id=job_id,
        prevhash=_hex(prevhash, "prevhash", 64),
        coinb1=_hex(coinb1, "coinb1"),
        coinb2=_hex(coinb2, "coinb2"),
        merkle_branch=tuple(_hex(branch, "merkle branch", 64) for branch in branches),
        version=_hex(version, "version", 8),
        nbits=_hex(nbits, "nBits", 8),
        ntime=_hex(ntime, "nTime", 8),
        clean_jobs=clean,
        target=target,
    )


@dataclass(frozen=True)
class ExecutionResult:
    winner: int | None
    digest: bytes | None
    hashes: int
    metadata: dict[str, Any]


class DirectExecutionAdapter:
    """Direct backend adapter retained for isolated CPU/OpenCL conformance."""

    def __init__(self, hasher: BitcoinHasher):
        self.hasher = hasher

    def execute(self, header: bytes, target: int, base_nonce: int, count: int) -> ExecutionResult:
        winner, digest, hashes = self.hasher.grind_target_range(
            header, target.to_bytes(32, "big"), base_nonce, count
        )
        return ExecutionResult(winner, digest, hashes, {
            "execution_path": "direct",
            "backend": self.hasher.backend,
            "device": self.hasher.device,
        })


class AethelExecutionAdapter:
    """End-to-end AETHEL → Tensor → TURING → iGPU adapter."""

    def __init__(self, *, n_qubits: int = 10000):
        from Intelligence.four_layer_stack import FourLayerMiningStack

        self.stack = FourLayerMiningStack(n_qubits=n_qubits)

    def execute(self, header: bytes, target: int, base_nonce: int, count: int) -> ExecutionResult:
        result = self.stack.mine_block(
            header, target.to_bytes(32, "big"),
            n_candidates=count, max_hashes=count, nonce_start=base_nonce,
        )
        igpu = result["layers"]["igpu"]
        winner = igpu["winning_nonce"]
        digest = bytes.fromhex(igpu["winning_hash"]) if igpu.get("winning_hash") else None
        return ExecutionResult(
            winner, digest, int(igpu["hashes_computed"]),
            {
                "execution_path": "aethel_tensor_turing_igpu",
                "aethel": result["layers"]["aethel"],
                "tensor": result["layers"]["tensor"],
                "turing": result["layers"]["turing"],
                "igpu": igpu,
                "fold_roundtrip_lossless": result["fold_roundtrip_lossless"],
                "strict_quantum": result["strict_quantum"],
                "cassini_holds": result["cassini_holds"],
            },
        )


class StratumV1Client:
    """Single-reader, correlated-request Stratum V1 client."""

    def __init__(self, endpoint: PoolEndpoint, worker: str, password: str, *, timeout: float = 15.0):
        if not worker:
            raise ValueError("worker is required")
        if not password:
            raise ValueError("password is required")
        self.endpoint = endpoint
        self.worker = worker
        self.password = password
        self.timeout = timeout
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.reader_task: asyncio.Task[None] | None = None
        self.pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.next_id = 1
        self.closed = True
        self.authorized = False
        self.extranonce1 = ""
        self.extranonce2_size = 0
        self.target: int | None = None
        self.job: MiningJob | None = None
        self.generation = 0
        self.job_event = asyncio.Event()
        self.accepted = 0
        self.rejected = 0
        self.last_error: str | None = None

    @property
    def connected(self) -> bool:
        return not self.closed and self.writer is not None and self.reader_task is not None and not self.reader_task.done()

    async def connect_and_authorize(self) -> None:
        await self.close()
        context = ssl.create_default_context() if self.endpoint.tls else None
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.endpoint.host, self.endpoint.port, ssl=context),
                timeout=self.timeout,
            )
        except Exception as exc:
            raise SessionLost(f"connect failed: {exc}") from exc
        self.closed = False
        self.reader_task = asyncio.create_task(self._read_loop(), name="stratum-reader")
        subscribed = await self.request("mining.subscribe", ["PYTHIA/production", None])
        self._apply_subscribe(subscribed)
        authorized = await self.request("mining.authorize", [self.worker, self.password])
        if authorized.get("error") is not None or authorized.get("result") is not True:
            raise ProtocolError(f"mining.authorize rejected: {authorized.get('error')!r}")
        self.authorized = True
        LOG.info("Stratum authorized endpoint=%s:%s tls=%s", self.endpoint.host, self.endpoint.port, self.endpoint.tls)

    async def close(self) -> None:
        self.closed = True
        if self.reader_task is not None:
            task, self.reader_task = self.reader_task, None
            if task is not asyncio.current_task():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        error = SessionLost("Stratum session closed")
        for future in self.pending.values():
            if not future.done():
                future.set_exception(error)
        self.pending.clear()
        if self.writer is not None:
            self.writer.close()
            with contextlib.suppress(Exception):
                await self.writer.wait_closed()
        self.reader = None
        self.writer = None
        self.authorized = False
        self.job = None
        self.job_event.clear()

    async def request(self, method: str, params: list[Any]) -> dict[str, Any]:
        if self.writer is None or self.closed:
            raise SessionLost("request on closed Stratum session")
        request_id = self.next_id
        self.next_id += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self.pending[request_id] = future
        payload = json.dumps({"id": request_id, "method": method, "params": params}, separators=(",", ":")).encode() + b"\n"
        try:
            self.writer.write(payload)
            await asyncio.wait_for(self.writer.drain(), timeout=self.timeout)
            return await asyncio.wait_for(future, timeout=self.timeout)
        except asyncio.TimeoutError as exc:
            self.pending.pop(request_id, None)
            raise SessionLost(f"Stratum {method} timed out") from exc
        except BaseException:
            self.pending.pop(request_id, None)
            raise

    async def _read_loop(self) -> None:
        assert self.reader is not None
        try:
            while not self.closed:
                try:
                    line = await asyncio.wait_for(self.reader.readline(), timeout=self.timeout)
                except asyncio.TimeoutError:
                    continue
                if not line:
                    raise SessionLost("pool closed the connection")
                try:
                    message = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ProtocolError("pool sent invalid JSON") from exc
                if not isinstance(message, dict):
                    raise ProtocolError("Stratum message is not an object")
                message_id = message.get("id")
                if message_id is not None:
                    try:
                        future = self.pending.pop(int(message_id))
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ProtocolError("unknown Stratum response id") from exc
                    if not future.done():
                        future.set_result(message)
                else:
                    await self._notification(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_error = str(exc)
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(exc)
            self.pending.clear()
            self.closed = True
            self.job_event.set()

    async def _notification(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        params = message.get("params", [])
        if method == "mining.set_difficulty":
            if not isinstance(params, list) or len(params) != 1:
                raise ProtocolError("invalid mining.set_difficulty")
            self._update_target(difficulty_target(params[0]))
            return
        if method == "mining.set_target":
            if not isinstance(params, list) or len(params) != 1:
                raise ProtocolError("invalid mining.set_target")
            self._update_target(target_from_hex(params[0]))
            return
        if method == "mining.set_extranonce":
            if not isinstance(params, list) or len(params) != 2:
                raise ProtocolError("invalid mining.set_extranonce")
            self.extranonce1 = _hex(params[0], "extranonce1")
            self.extranonce2_size = int(params[1])
            if not 0 <= self.extranonce2_size <= 16:
                raise ProtocolError("extranonce2 size outside 0..16 bytes")
            self.generation += 1
            self.job = None
            self.job_event.clear()
            return
        if method == "mining.notify":
            self.generation += 1
            self.job = parse_notify(params, self.generation, self.target)
            self.job_event.set()
            LOG.info("Job received id=%s clean_jobs=%s", self.job.job_id, self.job.clean_jobs)
            return
        if method == "client.reconnect":
            raise SessionLost("pool requested client reconnect")

    def _update_target(self, target: int) -> None:
        """Invalidate work computed against a superseded negotiated target."""
        changed = self.target != target
        self.target = target
        if changed and self.job is not None:
            self.generation += 1
            self.job = replace(self.job, target=target, generation=self.generation)
            self.job_event.set()

    def _apply_subscribe(self, response: dict[str, Any]) -> None:
        if response.get("error") is not None:
            raise ProtocolError(f"mining.subscribe rejected: {response['error']!r}")
        result = response.get("result")
        if not isinstance(result, list) or len(result) != 3:
            raise ProtocolError("invalid mining.subscribe result")
        self.extranonce1 = _hex(result[1], "extranonce1")
        if not isinstance(result[2], int) or isinstance(result[2], bool) or not 0 <= result[2] <= 16:
            raise ProtocolError("invalid extranonce2 size")
        self.extranonce2_size = result[2]

    async def wait_for_job(self, timeout: float = 30.0) -> MiningJob:
        if self.job is not None:
            return self.job
        try:
            await asyncio.wait_for(self.job_event.wait(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError("no mining.notify received") from exc
        if self.job is None:
            raise SessionLost(self.last_error or "Stratum reader stopped")
        return self.job

    async def submit(self, job: MiningJob, extranonce2: str, nonce: int) -> bool:
        if not self.authorized or self.job is None or self.job.generation != job.generation:
            return False
        response = await self.request("mining.submit", [self.worker, job.job_id, extranonce2, job.ntime, f"{nonce:08x}"])
        accepted = response.get("error") is None and response.get("result") is True
        if accepted:
            self.accepted += 1
        else:
            self.rejected += 1
        return accepted


class ProductionMiner:
    def __init__(self, client: StratumV1Client, executor: Any, *, window: int = 1 << 20, submit_enabled: bool = False):
        if not 1 <= window <= 1 << 20:
            raise ValueError("window must be between 1 and 1048576")
        self.client = client
        self.executor = executor
        self.window = window
        self.submit_enabled = submit_enabled
        self.extranonce2 = 0
        self.base_nonce = 0
        self.total_hashes = 0
        self.started = time.perf_counter()
        self.heartbeat = None
        self._session_active = False
        # Drain file: checked between windows, i.e. at a point where no GPU op is
        # in flight. On WSL2/dxgkrnl a docker stop that lands mid-OpenCL-call
        # leaves the process in uninterruptible sleep and wedges the container —
        # the only safe teardown on that stack is self-exit at a window boundary.
        stop_file = os.getenv("PYTHIA_STOP_FILE", "").strip()
        self.stop_file = Path(stop_file) if stop_file else None

    def _drain_requested(self) -> bool:
        return self.stop_file is not None and self.stop_file.exists()

    async def run_session(self, *, max_runtime: float | None = None, max_shares: int | None = None) -> bool:
        # One in-flight window, no unbounded submission queue. Never tear down
        # a device context while its native call is still using it.
        if self._session_active:
            raise RuntimeError("a mining session is already active")
        self._session_active = True
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="pythia-window") as pool:
            self._window_pool = pool
            try:
                return await self._run_session(max_runtime=max_runtime, max_shares=max_shares)
            finally:
                self._window_pool = None
                self._session_active = False

    async def _execute_window(self, header: bytes, target: int, base: int, count: int):
        adapter = DirectExecutionAdapter(self.executor) if isinstance(self.executor, BitcoinHasher) else self.executor
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(self._window_pool, adapter.execute, header, target, base, count)
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            # Cancellation cannot interrupt a native device call. Drain this
            # exact window before allowing shutdown/reconnect, without blocking
            # Stratum's reader. A wedged driver remains a qualification blocker.
            while not future.done():
                try:
                    await asyncio.shield(future)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if future.done() and not future.cancelled():
                future.exception()  # retrieve worker failures during cancellation
            raise

    async def _run_session(self, *, max_runtime: float | None = None, max_shares: int | None = None) -> bool:
        current_generation = -1
        while self.client.connected:
            if self._drain_requested():
                LOG.info("Stop file present; draining at window boundary")
                return self.client.accepted > 0 or not self.submit_enabled
            if max_runtime is not None and time.perf_counter() - self.started >= max_runtime:
                return self.client.accepted > 0
            if max_shares is not None and self.client.accepted >= max_shares:
                return True
            job = await self.client.wait_for_job()
            if job.generation != current_generation:
                current_generation = job.generation
                self.base_nonce = 0
                self.extranonce2 = 0
            if self.client.extranonce2_size == 0:
                extranonce2 = ""
            else:
                limit = 1 << (8 * self.client.extranonce2_size)
                if self.extranonce2 >= limit:
                    raise RuntimeError("extranonce2 space exhausted")
                extranonce2 = f"{self.extranonce2:0{self.client.extranonce2_size * 2}x}"
            header = build_job_header(job, self.client.extranonce1, extranonce2)
            if len(header) != 80:
                raise ProtocolError("constructed header is not 80 bytes")
            if job.target is None:
                await asyncio.sleep(0.05)
                continue
            remaining = (1 << 32) - self.base_nonce
            count = min(self.window, remaining)
            strict_quantum = certify_work_window(header[:76], self.base_nonce, count)
            if not verify_certificate(strict_quantum):
                raise ProtocolError("strict quantum work certificate failed")
            window_start = time.perf_counter()
            execution = await self._execute_window(header, job.target, self.base_nonce, count)
            window_seconds = time.perf_counter() - window_start
            execution.metadata["strict_quantum"] = strict_quantum
            winner, digest, hashes = execution.winner, execution.digest, execution.hashes
            self.total_hashes += hashes
            if self.heartbeat is not None:
                schedule = execution.metadata.get("schedule") or {}
                self.heartbeat.report(
                    hashrate_hs=hashes / window_seconds if window_seconds > 0 else 0.0,
                    total_hashes=self.total_hashes,
                    job_id=job.job_id,
                    job_generation=job.generation,
                    shares_accepted=self.client.accepted,
                    shares_rejected=self.client.rejected,
                    backend=str(execution.metadata.get("backend", "")),
                    device=str(execution.metadata.get("device", "")),
                    solver_workers=schedule.get("workers", 1),
                    nonce_stride=schedule.get("stride", 1),
                    nonce_coverage=schedule.get("coverage", count),
                )
            LOG.info(
                "Window done job=%s base=%s hashes=%d seconds=%.2f rate=%s",
                job.job_id,
                self.base_nonce,
                hashes,
                window_seconds,
                _format_rate(hashes / window_seconds) if window_seconds > 0 else "n/a",
            )
            if execution.metadata.get("execution_path") == "aethel_tensor_turing_igpu":
                LOG.info("AETHEL layers=%s", execution.metadata)
            LOG.debug("Strict quantum certificate mode=%s basis=%s window=%s", strict_quantum["mode"], strict_quantum["selected_basis"], count)
            if winner is not None and digest is not None:
                if self.client.job is None or self.client.job.generation != job.generation:
                    continue
                reference_digest = _dsha256(header[:76] + winner.to_bytes(4, "little"))
                if reference_digest != digest or int.from_bytes(reference_digest[::-1], "big") > job.target:
                    raise ProtocolError("hasher result failed independent SHA-256d target recheck")
                if not self.submit_enabled:
                    LOG.info("Dry-run candidate job=%s nonce=%08x; submission disabled", job.job_id, winner)
                    accepted = False
                else:
                    accepted = await self.client.submit(job, extranonce2, winner)
                    toe = getattr(self.executor, "toe", None)
                    if toe is not None:
                        toe.record_decision(
                            "pool_result", "quantum", "mining_submit_result",
                            {"job_id": job.job_id, "nonce": winner, "accepted": bool(accepted)},
                            8, verified=bool(accepted),
                        )
                        if not toe.verify_provenance():
                            raise ProtocolError("TOE provenance failed after pool result")
                    LOG.info("Share result accepted=%s job=%s nonce=%08x", accepted, job.job_id, winner)
                if accepted and max_shares is not None and self.client.accepted >= max_shares:
                    return True
            self.base_nonce += count
            if self.base_nonce >= 1 << 32:
                self.base_nonce = 0
                self.extranonce2 += 1
        raise SessionLost(self.client.last_error or "Stratum connection lost")


async def run(args: argparse.Namespace) -> int:
    # Orderly shutdown: SIGTERM (docker stop) must unwind through finally blocks so
    # the Stratum socket and the OpenCL device context are released. Without this,
    # Python's default SIGTERM disposition kills the process mid-GPU-operation and
    # the WSL2/dxgkrnl device stays pinned, leaving the container unkillable.
    task = asyncio.current_task()
    if task is not None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, task.cancel)
            except (NotImplementedError, RuntimeError):
                pass
    specs = configured_pool_specs(args)
    if args.submit and not args.dry_run:
        if (
            os.getenv("HYBA_ENABLE_LIVE_SHARE_SUBMIT") != "true"
            or not os.getenv("HYBA_LIVE_SHARE_APPROVAL_ID")
            or os.getenv("HYBA_AUTONOMOUS_EXTERNAL_ACTIONS") != "true"
        ):
            raise SystemExit(
                "live submission requires HYBA_ENABLE_LIVE_SHARE_SUBMIT=true, "
                "HYBA_LIVE_SHARE_APPROVAL_ID, and HYBA_AUTONOMOUS_EXTERNAL_ACTIONS=true"
            )
    backoff = 1.0
    pool_index = 0
    deadline = time.monotonic() + args.max_runtime if args.max_runtime else None
    while deadline is None or time.monotonic() < deadline:
        spec = specs[pool_index % len(specs)]
        pool_index += 1
        client = StratumV1Client(spec.endpoint, spec.worker, spec.password, timeout=args.timeout)
        try:
            await client.connect_and_authorize()
            backoff = 1.0
            execution_path = os.getenv("PYTHIA_EXECUTION_PATH", "aethel_hendrix").strip().lower()
            if execution_path == "aethel":
                executor = AethelExecutionAdapter(
                    n_qubits=int(os.getenv("PYTHIA_VQC_QUBITS", "10000"))
                )
                LOG.info("Execution path=AETHEL->Tensor->TURING->iGPU")
            elif execution_path == "aethel_hendrix":
                # Octopus model: one executor, N independent solver arms. The
                # Hendrix schedule gives every arm a disjoint coprime position
                # class — merged order covers the window exactly once.
                try:
                    workers = int(os.getenv("PYTHIA_SOLVER_WORKERS", "32"))
                except ValueError:
                    workers = 0
                if not 1 <= workers <= 600:
                    raise SystemExit("PYTHIA_SOLVER_WORKERS must be between 1 and 600")
                from .scaled_execution import LucasScaledAethelExecutionAdapter
                executor = LucasScaledAethelExecutionAdapter(workers=workers)
                LOG.info(
                    "Execution path=AETHEL->Tensor->Hendrix/Pisot->iGPU solver_workers=%d",
                    workers,
                )
            elif execution_path == "direct":
                hasher = BitcoinHasher(backend=args.backend)
                executor = DirectExecutionAdapter(hasher)
                LOG.info("Execution path=direct backend=%s device=%s", hasher.backend, hasher.device)
            else:
                raise SystemExit("PYTHIA_EXECUTION_PATH must be 'aethel_hendrix', 'aethel', or 'direct'")
            miner = ProductionMiner(
                client, executor, window=args.window,
                submit_enabled=args.submit and not args.dry_run,
            )
            worker_name = os.getenv("PYTHIA_WORKER_NAME", "").strip()
            emit_hb = os.getenv("PYTHIA_EMIT_HEARTBEAT", "").strip().lower() in ("1", "true", "yes", "on")
            if worker_name or emit_hb:
                try:
                    from worker_lifecycle import HeartbeatEmitter

                    miner.heartbeat = HeartbeatEmitter(worker_name or f"miner-{spec.endpoint.host}")
                    miner.heartbeat.__enter__()
                except Exception as exc:
                    LOG.warning("heartbeat emitter unavailable: %s", exc)
            try:
                remaining = (deadline - time.monotonic()) if deadline else None
                accepted = await miner.run_session(max_runtime=remaining, max_shares=args.max_shares)
            finally:
                if miner.heartbeat is not None:
                    miner.heartbeat.__exit__(None, None, None)
                    miner.heartbeat = None
            return 0 if accepted or args.dry_run else 2
        except asyncio.CancelledError:
            LOG.info("Shutdown requested; closing session on %s", spec.endpoint.host)
            return 0
        except (SessionLost, ProtocolError, TimeoutError, OSError, RuntimeError) as exc:
            LOG.warning(
                "Mining session ended on %s: %s; trying next pool in %.1fs",
                spec.endpoint.host, exc, backoff,
            )
            if deadline is not None and time.monotonic() + backoff >= deadline:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 60.0)
        finally:
            await client.close()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", default=os.getenv("PYTHIA_STRATUM_ENDPOINT"))
    parser.add_argument("--worker", default=os.getenv("PYTHIA_STRATUM_WORKER"))
    parser.add_argument("--password", default=os.getenv("PYTHIA_STRATUM_PASSWORD"))
    parser.add_argument(
        "--pool-spec", action="append", default=None,
        help="endpoint|worker|password; repeat for ordered failover pools",
    )
    parser.add_argument("--backend", choices=("auto", "opencl", "gpu", "cpu"), default=os.getenv("PYTHIA_HASH_BACKEND", "auto"))
    parser.add_argument("--window", type=int, default=int(os.getenv("PYTHIA_NONCE_WINDOW", str(1 << 20))))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("PYTHIA_STRATUM_TIMEOUT", "15")))
    parser.add_argument("--max-runtime", type=float, default=None)
    parser.add_argument("--max-shares", type=int, default=None)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default=os.getenv("PYTHIA_LOG_LEVEL", "INFO"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
