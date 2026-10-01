"""Production transport hardening for the canonical mining coordinator.

This module deliberately wraps the existing, consensus-tested Stratum V1
implementation instead of creating a second mining stack. It adds production
transport bounds, failover policy, truthful network telemetry, and MMIO-loop
outage behaviour while leaving proof construction and SHA256d authority in the
existing coordinator/proof adapter.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections import deque
from typing import Any, Mapping

from manifold_pool_coordinator import (
    StratumAuthorizationError,
    StratumClient,
)

from .causal import CausalCoordinate
from .coordinator import IntelligentPoolCoordinator, MMIOControlSink
from .pool_chain import bip34_height

LOG = logging.getLogger(__name__)


def _positive_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


class ProductionStratumClient(StratumClient):
    """Stratum V1 client with a bounded asynchronous outbound queue.

    ``StratumClient`` already owns protocol parsing, request correlation,
    local job/target state and share outcome truth. This subclass changes
    only transport scheduling and adds measured transport telemetry. A wedged
    socket becomes a controlled connection failure instead of unbounded
    event-loop backpressure.
    """

    def __init__(
        self,
        *args: Any,
        connect_timeout: float | None = None,
        request_timeout: float | None = None,
        write_timeout: float | None = None,
        enqueue_timeout: float | None = None,
        outbound_queue_size: int | None = None,
        **kwargs: Any,
    ) -> None:
        # Base __init__ publishes an initial status snapshot and therefore may
        # call our overridden _publish_status/status_snapshot immediately.
        self._submit_rtt_ms: deque[float] = deque(maxlen=2048)
        self._stale_dropped = 0
        super().__init__(
            *args,
            connect_timeout=(
                _positive_env("PYTHIA_STRATUM_CONNECT_TIMEOUT_S", 0.75)
                if connect_timeout is None
                else connect_timeout
            ),
            request_timeout=(
                _positive_env("PYTHIA_STRATUM_REQUEST_TIMEOUT_S", 30.0)
                if request_timeout is None
                else request_timeout
            ),
            **kwargs,
        )
        self.write_timeout = (
            _positive_env("PYTHIA_STRATUM_WRITE_TIMEOUT_S", 0.75)
            if write_timeout is None
            else write_timeout
        )
        self.enqueue_timeout = (
            _positive_env("PYTHIA_STRATUM_ENQUEUE_TIMEOUT_S", 0.25)
            if enqueue_timeout is None
            else enqueue_timeout
        )
        queue_size = (
            _positive_int_env("PYTHIA_STRATUM_OUTBOUND_QUEUE", 256)
            if outbound_queue_size is None
            else outbound_queue_size
        )
        if self.write_timeout <= 0 or self.enqueue_timeout <= 0:
            raise ValueError("Stratum transport timeouts must be positive")
        if queue_size <= 0:
            raise ValueError("outbound_queue_size must be positive")
        self._outbound: asyncio.Queue[tuple[bytes, asyncio.Future[None]]] = asyncio.Queue(
            maxsize=queue_size
        )
        self._writer_task: asyncio.Task[None] | None = None
        self._writer_error: BaseException | None = None

    @property
    def connected(self) -> bool:
        writer_ok = self._writer_task is None or not self._writer_task.done()
        return super().connected and writer_ok and self._writer_error is None

    def record_stale_candidate(self) -> None:
        """Record one observed candidate invalidated by a job/session change."""
        self._stale_dropped += 1
        self._publish_status()

    def status_snapshot(self) -> dict[str, Any]:
        """Return measured transport telemetry; unavailable values stay null."""
        snapshot = self.runtime_state.snapshot()
        snapshot["session_id"] = self.runtime_state.session_id
        generation = self.runtime_state.current_job or self.runtime_state.last_job
        block_height = bip34_height(generation.coinb1) if generation is not None else None
        snapshot.setdefault("job", {})["block_height"] = block_height

        counters = snapshot.get("counters", {})
        submitted = int(counters.get("submitted", 0) or 0)
        accepted = int(counters.get("accepted", 0) or 0)
        rejected = int(counters.get("rejected", 0) or 0)
        unknown = int(counters.get("unknown", 0) or 0)
        candidate_total = submitted + self._stale_dropped

        samples = list(self._submit_rtt_ms)
        ordered = sorted(samples)
        p95 = None
        if ordered:
            p95 = ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))]
        last = samples[-1] if samples else None
        mean = (sum(samples) / len(samples)) if samples else None

        submission = snapshot.setdefault("submission", {})
        submission["rtt_ms"] = {
            "last": round(last, 3) if last is not None else None,
            "mean": round(mean, 3) if mean is not None else None,
            "p95": round(p95, 3) if p95 is not None else None,
            "samples": len(samples),
        }
        snapshot["protocol"] = "stratum_v1"
        snapshot["outcomes"] = {
            "candidate_total": candidate_total,
            "accepted_ratio": accepted / candidate_total if candidate_total else None,
            "rejected_ratio": rejected / candidate_total if candidate_total else None,
            "unknown_ratio": unknown / candidate_total if candidate_total else None,
            "stale_ratio": self._stale_dropped / candidate_total if self._stale_dropped else None,
            "stale_dropped": self._stale_dropped,
        }
        # The persistent retarget tracker replaces this only when complete
        # difficulty-weighted share evidence exists for the active epoch.
        snapshot["effective_stratum_hashrate_hs"] = None
        return snapshot

    def _publish_status(self) -> None:
        if self._status_sink is None:
            return
        try:
            self._status_sink(self.status_snapshot())
        except Exception:
            LOG.exception("Stratum status sink failed")

    def _ensure_writer_task(self) -> None:
        if self.writer is None:
            raise ConnectionError("Stratum session is not connected")
        if self._writer_task is None or self._writer_task.done():
            self._writer_error = None
            self._writer_task = asyncio.create_task(
                self._writer_loop(), name=f"stratum-writer:{self.endpoint.name}"
            )

    async def _writer_loop(self) -> None:
        try:
            while not self._closed:
                payload, ack = await self._outbound.get()
                try:
                    if self.writer is None:
                        raise ConnectionError("Stratum writer disappeared")
                    self.writer.write(payload)
                    await asyncio.wait_for(self.writer.drain(), timeout=self.write_timeout)
                    if not ack.done():
                        ack.set_result(None)
                except BaseException as exc:
                    if not ack.done():
                        ack.set_exception(exc)
                    if isinstance(exc, asyncio.CancelledError):
                        raise
                    self._writer_error = exc
                    for future in self._pending.values():
                        if not future.done():
                            future.set_exception(ConnectionError(f"Stratum writer stopped: {exc}"))
                    self._pending.clear()
                    return
                finally:
                    self._outbound.task_done()
        except asyncio.CancelledError:
            raise

    async def _send_payload(self, payload: bytes) -> None:
        self._ensure_writer_task()
        loop = asyncio.get_running_loop()
        ack: asyncio.Future[None] = loop.create_future()
        try:
            await asyncio.wait_for(
                self._outbound.put((payload, ack)), timeout=self.enqueue_timeout
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"Stratum outbound queue remained full for {self.enqueue_timeout:.3f}s"
            ) from exc
        try:
            await asyncio.wait_for(
                ack, timeout=self.write_timeout + self.enqueue_timeout
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"Stratum socket write exceeded bounded transport budget "
                f"({self.write_timeout:.3f}s)"
            ) from exc

    async def request(
        self, method: str, params: list[Any], *, timeout: float | None = None
    ) -> Any:
        if not self.writer:
            raise ConnectionError("Stratum session is not connected")
        if self._reader_task is not None and self._reader_task.done():
            raise ConnectionError("Stratum reader has stopped; no response can arrive")
        if self._writer_error is not None:
            raise ConnectionError(f"Stratum writer has stopped: {self._writer_error}")

        request_id = self._next_id
        self._next_id += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._pending[request_id] = future
        payload = (
            json.dumps(
                {"id": request_id, "method": method, "params": params},
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        try:
            await self._send_payload(payload)
        except BaseException:
            self._pending.pop(request_id, None)
            if not future.done():
                future.cancel()
            raise

        limit = self.request_timeout if timeout is None else timeout
        try:
            return await asyncio.wait_for(future, timeout=limit)
        except asyncio.TimeoutError as exc:
            self._pending.pop(request_id, None)
            raise TimeoutError(
                f"Stratum request {method!r} timed out after {limit:.1f}s"
            ) from exc

    async def submit(self, params: list[Any]) -> Any:
        result = await super().submit(params)
        started = self.runtime_state.last_submit_at
        finished = self.runtime_state.last_response_at
        if started is not None and finished is not None and finished >= started:
            self._submit_rtt_ms.append((finished - started) * 1000.0)
            # Publish once more so this same accepted/rejected share carries its
            # measured RTT rather than waiting for the next protocol event.
            self._publish_status()
        return result

    async def close(self) -> None:
        if self._writer_task is not None:
            self._writer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._writer_task
            self._writer_task = None
        while not self._outbound.empty():
            try:
                _payload, ack = self._outbound.get_nowait()
            except asyncio.QueueEmpty:
                break
            if not ack.done():
                ack.set_exception(ConnectionError("Stratum session closed"))
            self._outbound.task_done()
        self._writer_error = None
        await super().close()


class ProductionMiningCoordinator(IntelligentPoolCoordinator):
    """Canonical intelligent coordinator with production transport policy."""

    def __init__(
        self,
        *args: Any,
        connect_timeout: float | None = None,
        request_timeout: float | None = None,
        write_timeout: float | None = None,
        outbound_queue_size: int | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault(
            "reconnect_delay", _positive_env("PYTHIA_RECONNECT_INITIAL_S", 0.25)
        )
        super().__init__(*args, **kwargs)
        self.production_connect_timeout = (
            _positive_env("PYTHIA_STRATUM_CONNECT_TIMEOUT_S", 0.75)
            if connect_timeout is None
            else connect_timeout
        )
        self.production_request_timeout = (
            _positive_env("PYTHIA_STRATUM_REQUEST_TIMEOUT_S", 30.0)
            if request_timeout is None
            else request_timeout
        )
        self.production_write_timeout = (
            _positive_env("PYTHIA_STRATUM_WRITE_TIMEOUT_S", 0.75)
            if write_timeout is None
            else write_timeout
        )
        self.production_outbound_queue_size = (
            _positive_int_env("PYTHIA_STRATUM_OUTBOUND_QUEUE", 256)
            if outbound_queue_size is None
            else outbound_queue_size
        )
        self._stale_candidates_dropped = 0
        self._stale_execution_ids: set[str] = set()

    def _observe_stale_from_last_execution(self) -> None:
        """Count only candidates invalidated by a changed canonical identity."""
        execution = self.last_execution
        if not isinstance(execution, Mapping) or not execution.get("executed"):
            return
        execution_id = execution.get("execution_id")
        if not isinstance(execution_id, str) or execution_id in self._stale_execution_ids:
            return
        if not execution.get("candidate_id") or execution.get("pool_outcome") != "NOT_SUBMITTED":
            return
        key = (
            execution.get("pool_session_id"),
            execution.get("generation"),
            execution.get("job_fingerprint"),
        )
        current, _reason = self._resolve_work_identity()
        if current is not None and current.key == key:
            # NOT_SUBMITTED can be shadow mode, duplicate suppression or chain
            # evidence refusal. None of those is a stale share.
            return
        self._stale_execution_ids.add(execution_id)
        self._stale_candidates_dropped += 1
        # When only the job generation changed inside the same Stratum
        # session, attach the stale count directly to that session telemetry.
        client = self.client
        session_id = execution.get("pool_session_id")
        if isinstance(client, ProductionStratumClient) and client.runtime_state.session_id == session_id:
            client.record_stale_candidate()
        self.causal.record(
            "candidate_stale_dropped",
            CausalCoordinate(
                pool_session_id=(session_id if isinstance(session_id, str) else None),
                generation=(
                    int(execution["generation"])
                    if isinstance(execution.get("generation"), int)
                    else None
                ),
                job_fingerprint=(
                    str(execution["job_fingerprint"])
                    if execution.get("job_fingerprint") is not None
                    else None
                ),
                execution_id=execution_id,
                candidate_id=(
                    str(execution["candidate_id"])
                    if execution.get("candidate_id") is not None
                    else None
                ),
            ),
            stale_candidates_dropped=self._stale_candidates_dropped,
        )

    def set_metrics_sink(self, sink: Any) -> None:
        """Publish measured hashing plus stale-candidate drop counters."""
        def wrapped(counters: Mapping[str, Any]) -> None:
            self._observe_stale_from_last_execution()
            sink({**dict(counters), "stale_candidates_dropped": self._stale_candidates_dropped})

        super().set_metrics_sink(wrapped)

    async def connect_with_failover(self) -> ProductionStratumClient:
        errors: list[str] = []
        authorization_failures = 0
        for offset in range(len(self.endpoints)):
            index = (self.endpoint_index + offset) % len(self.endpoints)
            endpoint = self.endpoints[index]
            client = ProductionStratumClient(
                endpoint,
                username=endpoint.username or self.username,
                password=endpoint.password or self.password,
                connect_timeout=self.production_connect_timeout,
                request_timeout=self.production_request_timeout,
                write_timeout=self.production_write_timeout,
                outbound_queue_size=self.production_outbound_queue_size,
                status_sink=self.stratum_status_sink,
            )
            try:
                await client.connect()
            except StratumAuthorizationError as exc:
                authorization_failures += 1
                errors.append(f"{endpoint.name}: {exc}")
                await client.close()
                continue
            except Exception as exc:
                errors.append(f"{endpoint.name}: {exc}")
                await client.close()
                continue

            self.endpoint_index = index
            self.client = client
            # Preserve IntelligentPoolCoordinator's post-handshake binding:
            # the first notify may arrive during subscribe/authorize.
            self._refresh_work_identity()
            self._precompute_wake.set()
            return client

        if authorization_failures == len(self.endpoints):
            raise StratumAuthorizationError("; ".join(errors))
        raise ConnectionError("; ".join(errors))

    async def run_hardware_loop(
        self,
        bridge: Any,
        *,
        difficulty_mask: int,
        base_step: int,
        poll_ms: int = 100,
        max_backoff_s: float | None = None,
    ) -> None:
        """Run the MMIO path with the same bounded failover policy as software.

        Pool loss stops the bridge before any reconnect wait, preventing stale
        work from continuing while no authoritative Stratum session exists.
        Every configured endpoint is attempted immediately; only a complete
        outage enters exponential backoff.
        """
        if self.submit_enabled and self.chain_observer is None:
            raise RuntimeError("live mining requires a Bitcoin chain observer")
        if max_backoff_s is None:
            max_backoff_s = _positive_env("PYTHIA_RECONNECT_MAX_S", 30.0)
        if max_backoff_s <= 0:
            raise ValueError("max_backoff_s must be positive")

        self._bridge = bridge
        self._base_step = base_step
        self._control_sink = MMIOControlSink(
            bridge,
            on_throttle=self._set_throttled,
            on_quarantine=self.quarantined_records.add,
            on_prune=self.proven_exclusions.append,
        )
        if self._agentic_state_path:
            self.agentic.load_state(self._agentic_state_path)
        self._precompute_task = asyncio.create_task(self._precompute_loop())
        try:
            try:
                await self._start_control_server()
            except OSError as exc:
                LOG.warning("coordinator control channel unavailable: %s", exc)
            bridge.set_difficulty_mask(difficulty_mask)
            bridge.set_base_step(base_step)
            running = False
            delay = self.reconnect_delay
            while True:
                if not self.client or not self.client.connected:
                    if running:
                        bridge.stop()
                        running = False
                    if self.client:
                        with contextlib.suppress(Exception):
                            await self.client.close()
                        self.client = None
                    try:
                        await self.connect_with_failover()
                    except Exception as exc:
                        kind = (
                            "every pool refused authorization"
                            if isinstance(exc, StratumAuthorizationError)
                            else "every pool unavailable"
                        )
                        LOG.warning("%s: %s; retrying in %.3fs", kind, exc, delay)
                        self._publish_metrics(force=True)
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, max_backoff_s)
                        continue
                    delay = self.reconnect_delay
                    LOG.info("hardware mining through %s", self.client.endpoint.name)

                permitted = await self.before_hardware_poll()
                if not permitted:
                    if running:
                        bridge.stop()
                        running = False
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(
                            self._work_wake.wait(), max(poll_ms / 1000, 0.01)
                        )
                    self._work_wake.clear()
                    continue
                if not running:
                    bridge.start()
                    running = True

                ring_path = os.getenv("MLA1517_PRIME_DB_RING")
                if ring_path:
                    record = await asyncio.to_thread(bridge.poll_vault_to_ring, ring_path, poll_ms)
                else:
                    record = await asyncio.to_thread(bridge.poll_vault, poll_ms)
                if record is not None:
                    try:
                        await self.submit_record(record)
                    except (ConnectionError, TimeoutError, asyncio.IncompleteReadError) as exc:
                        LOG.warning("submit connection lost: %s", exc)
                        if running:
                            bridge.stop()
                            running = False
                        if self.client:
                            with contextlib.suppress(Exception):
                                await self.client.close()
                        self.client = None
        finally:
            if self._precompute_task is not None:
                self._precompute_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._precompute_task
                self._precompute_task = None
            if self._agentic_state_path:
                self.agentic.save_state(self._agentic_state_path)
            if self.client is not None:
                with contextlib.suppress(Exception):
                    await self.client.close()
                self.client = None
            if self._control_server:
                self._control_server.close()
                with contextlib.suppress(Exception):
                    await self._control_server.wait_closed()
                self._control_server = None
                with contextlib.suppress(OSError):
                    os.unlink(self.control_socket_path)
            with contextlib.suppress(Exception):
                bridge.stop()
            if self.telemetry:
                self.telemetry.close()


__all__ = ["ProductionMiningCoordinator", "ProductionStratumClient"]
