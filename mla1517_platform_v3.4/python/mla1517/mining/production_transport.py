"""Production transport hardening for the canonical mining coordinator.

This module deliberately wraps the existing, consensus-tested Stratum V1
implementation instead of creating a second mining stack.  It adds two
operational properties required by the production runtime:

* bounded, queue-backed socket writes so transport backpressure cannot grow
  without bound or stall the hashing worker; and
* aggressive first-endpoint failover with configurable sub-second connect
  budgets while retaining the coordinator's existing exponential reconnect
  policy across complete outage cycles.

All share construction, SHA256d verification, stale-generation checks,
submission truth and agentic/intelligence behaviour remain owned by the
existing coordinator and proof adapter.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Any

from manifold_pool_coordinator import (
    StratumAuthorizationError,
    StratumClient,
)

from .coordinator import IntelligentPoolCoordinator


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
    local job/target state and share outcome truth.  This subclass changes
    only transport scheduling.  Callers enqueue a frame and wait only for a
    bounded write acknowledgement; the dedicated writer task owns
    ``StreamWriter.drain()``.  A wedged socket therefore becomes a controlled
    connection failure instead of unbounded event-loop backpressure.
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

        import json

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


__all__ = ["ProductionMiningCoordinator", "ProductionStratumClient"]
