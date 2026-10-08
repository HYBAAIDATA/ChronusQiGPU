#!/usr/bin/env python3
"""Async Stratum coordinator for MLA1517 Aethel winner records.

Important protocol boundary:
standard Braiins/ViaBTC Stratum pools validate their own coin's PoW header
and difficulty target. A Cassini-sealed MLA1517 11D record is not, by itself,
a valid Bitcoin/Dogecoin/etc. Stratum share. Therefore the default translator
refuses to submit unless a real pool-job translation is present. This prevents
the coordinator from sending invalid shares to public pools.

The networking, subscription, authorization, reconnect, failover, and
submission machinery is production-oriented. The algorithm-specific adapter
must be supplied when the pool and MLA1517 proof system are formally bridged.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from chronus.mla1517.hardware import MMIOBridge, VaultRecord
from chronus.mla1517.telemetry import TelemetryWriter
from chronus.mla1517.mining.stratum_adapter import StratumProofAdapter
from chronus.mla1517.mining.stratum_state import StratumRuntimeState

LOG = logging.getLogger("chronus.mla1517.stratum")


class StratumProtocolError(RuntimeError):
    """The remote endpoint returned an invalid or unsupported protocol reply."""


class StratumAuthorizationError(StratumProtocolError):
    """A pool rejected the configured worker identity."""


class StratumTranslationError(RuntimeError):
    """The MLA1517 proof is not mapped to the selected pool algorithm."""


@dataclass(frozen=True)
class PoolEndpoint:
    host: str
    port: int
    name: str
    tls: bool = False
    # Per-pool credentials: pools use different worker formats (account.worker
    # vs BTC address), so failover must authorize and submit with the
    # credentials of the pool actually connected. None falls back to the
    # coordinator-wide username/password.
    username: str | None = None
    password: str | None = field(default=None, repr=False)
    # Pools such as NiceHash deliver extranonce changes only to subscribers.
    extranonce_subscribe: bool = False
    protocol: str = "v1"


@dataclass(frozen=True)
class StratumJob:
    job_id: str
    params: tuple[Any, ...]
    received_at: float


_TLS_SCHEMES = {"stratum+ssl", "stratum+tls", "ssl", "tls"}
_TCP_SCHEMES = {"stratum+tcp", "stratum", "tcp"}
_SV2_SCHEMES = {"sv2", "stratum2", "stratum2+noise", "stratum+v2"}


def parse_endpoint(value: str, name: str, *, tls: bool = False) -> PoolEndpoint:
    # Accept [scheme://]HOST:PORT and bracketed IPv6 [HOST]:PORT.  Unbracketed
    # IPv6 is deliberately rejected because its final colon is ambiguous with
    # PORT.  ssl/tls schemes force TLS; tcp schemes force plaintext; a bare
    # endpoint keeps the caller's default.
    text = value.strip()
    protocol = "v1"
    if "://" in text:
        scheme, _, text = text.partition("://")
        scheme = scheme.strip().lower()
        if scheme in _SV2_SCHEMES:
            protocol = "v2"
            tls = False
        elif scheme in _TLS_SCHEMES:
            tls = True
        elif scheme in _TCP_SCHEMES:
            tls = False
        else:
            raise ValueError(f"unsupported endpoint scheme {scheme!r} in {value!r}")
    value = text
    if value.startswith("["):
        close = value.find("]")
        if close <= 1 or close + 1 >= len(value) or value[close + 1] != ":":
            raise ValueError(f"endpoint must be HOST:PORT or [IPv6]:PORT, got {value!r}")
        host = value[1:close]
        port_text = value[close + 2 :]
    else:
        host, separator, port_text = value.rpartition(":")
        if not separator or not host or ":" in host:
            raise ValueError(f"endpoint must be HOST:PORT or [IPv6]:PORT, got {value!r}")
    if not host or not port_text:
        raise ValueError(f"endpoint must be HOST:PORT, got {value!r}")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError(f"invalid port in endpoint {value!r}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"invalid port in endpoint {value!r}")
    return PoolEndpoint(host, port, name, tls, protocol=protocol)


LEGACY_12D_FORMAT = "<IffIIfIIfiII"
CURRENT_HOT_STATE_FORMAT = "<Q14I"


def _u32_network_hex(value: int) -> str:
    """Encode a uint32 as the byte-reversed hex used by Stratum V1."""
    return struct.pack("<I", value & 0xFFFFFFFF)[::-1].hex()


def _decode_legacy_12d(raw_11d_buffer: bytes) -> tuple[int, int, int]:
    """Decode the explicitly proposed legacy 12-field compatibility layout."""
    required = struct.calcsize(LEGACY_12D_FORMAT)
    if len(raw_11d_buffer) < required:
        raise ValueError(f"legacy compatibility buffer must contain at least {required} bytes")
    unpacked = struct.unpack(LEGACY_12D_FORMAT, raw_11d_buffer[:required])
    nonce = unpacked[0]
    cassini = unpacked[9]
    time_state = unpacked[10]
    if cassini not in (1, -1):
        raise ValueError(f"Hardware Fault: Invalid Cassini Seal ({cassini})")
    return nonce, time_state, cassini


def format_mla1517_to_stratum_share(
    raw_11d_buffer: bytes,
    worker_name: str,
    job_id: str,
    extranonce2: str,
) -> str:
    """Serialize the proposed legacy 12-field state as a Stratum V1 candidate.

    This implements the requested struct-unpack/byte-order translation exactly.
    It is a transport serializer only: the result has Stratum's JSON shape,
    but it does not prove that the pool's own PoW hash target is satisfied.
    The production coordinator does not call this function without a negotiated
    algorithm adapter.
    """
    nonce, time_state, _cassini = _decode_legacy_12d(raw_11d_buffer)
    submit_payload = {
        "id": 4,
        "method": "mining.submit",
        "params": [
            worker_name,
            job_id,
            extranonce2,
            _u32_network_hex(time_state),
            _u32_network_hex(nonce),
        ],
    }
    return json.dumps(submit_payload, separators=(",", ":")) + "\n"


def format_mla1517_hot_state_candidate(
    raw_11d_buffer: bytes,
    worker_name: str,
    job_id: str,
    extranonce2: str,
) -> str:
    """Serialize the actual packed MLA1517 v1 hot descriptor as a candidate.

    The current hardware ABI is ``<Q14I``: D1 is uint64, D2-D11 are uint32,
    followed by route control and reserved words. It is not the proposed
    float-heavy 12-field layout, so both decoders remain explicit.
    """
    if len(raw_11d_buffer) != 64:
        raise ValueError("MLA1517 hot state must be exactly 64 bytes")
    unpacked = struct.unpack(CURRENT_HOT_STATE_FORMAT, raw_11d_buffer)
    nonce = unpacked[0] & 0xFFFFFFFF
    cassini_u32 = unpacked[9]
    cassini = cassini_u32 if cassini_u32 < 0x80000000 else cassini_u32 - 0x100000000
    if cassini not in (1, -1):
        raise ValueError(f"Hardware Fault: Invalid Cassini Seal ({cassini})")
    time_state = unpacked[10]
    submit_payload = {
        "id": 4,
        "method": "mining.submit",
        "params": [
            worker_name,
            job_id,
            extranonce2,
            _u32_network_hex(time_state),
            _u32_network_hex(nonce),
        ],
    }
    return json.dumps(submit_payload, separators=(",", ":")) + "\n"


def format_mla1517_submission_params(
    state_11d: bytes | Mapping[str, Any],
    *,
    worker_name: str,
    job: StratumJob,
) -> list[Any]:
    """Return safe, negotiated ``mining.submit`` parameters.

    A standard Stratum share needs pool-job fields such as job id, extranonce2,
    ntime, and nonce, plus an algorithm-specific proof. The 64-byte MLA1517
    hot descriptor does not contain those fields. Refuse by default rather
    than inventing a payload that a public pool will reject.

    A negotiated adapter may pass a mapping with:
      ``stratum_params``: the exact five or algorithm-specific submit fields.
    """
    if isinstance(state_11d, Mapping):
        supplied = state_11d.get("stratum_params")
        if isinstance(supplied, Sequence) and not isinstance(supplied, (str, bytes, bytearray)):
            return [worker_name, *list(supplied)]
    if not isinstance(state_11d, (bytes, bytearray)) or len(state_11d) != 64:
        raise StratumTranslationError("MLA1517 state must be exactly 64 bytes")
    raise StratumTranslationError(
        "no negotiated MLA1517-to-Stratum algorithm adapter; "
        f"job {job.job_id!r} cannot be submitted to a standard pool"
    )


class StratumClient:
    """One resilient JSON-lines Stratum session with request correlation."""

    def __init__(
        self,
        endpoint: PoolEndpoint,
        *,
        username: str,
        password: str,
        agent: str = "MLA1517/1.0",
        connect_timeout: float = 10.0,
        request_timeout: float = 30.0,
        status_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.agent = agent
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._jobs: dict[str, StratumJob] = {}
        self._closed = False
        self.proof_adapter = StratumProofAdapter()
        self._status_sink = status_sink
        endpoint_text = f"{self.endpoint.host}:{self.endpoint.port}"
        redacted_worker = (username[:2] + "***") if len(username) > 2 else "***"
        self.runtime_state = StratumRuntimeState(
            pool_id=self.endpoint.name,
            endpoint=endpoint_text,
            worker=redacted_worker,
        )
        self._publish_status()

    def _publish_status(self) -> None:
        if self._status_sink is None:
            return
        try:
            self._status_sink(self.runtime_state.snapshot())
        except Exception:
            LOG.exception("Stratum status sink failed")

    def status_snapshot(self) -> dict[str, Any]:
        return self.runtime_state.snapshot()

    @property
    def connected(self) -> bool:
        return (
            not self._closed
            and self.writer is not None
            and self._reader_task is not None
            and not self._reader_task.done()
        )

    async def connect(self) -> None:
        self.runtime_state.connecting()
        self._publish_status()
        kwargs: dict[str, Any] = {}
        if self.endpoint.tls:
            import ssl

            kwargs["ssl"] = ssl.create_default_context()
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.endpoint.host, self.endpoint.port, **kwargs),
                timeout=self.connect_timeout,
            )
        except Exception as exc:
            self.runtime_state.disconnected(str(exc))
            self._publish_status()
            raise
        self._closed = False
        self.proof_adapter.drop_session()
        self._jobs.clear()
        self.runtime_state.connected()
        self._publish_status()
        self._reader_task = asyncio.create_task(self._read_loop())
        self.runtime_state.subscribing()
        self._publish_status()
        subscription = await self.request("mining.subscribe", [self.agent, None])
        subscription_state = self.proof_adapter.handle_subscribe_result(subscription)
        self.runtime_state.subscription_confirmed(subscription_state)
        if self.proof_adapter.current_job is not None:
            # A notify that raced ahead of the subscribe response is
            # registered as a Stratum generation now that it can be.
            self.runtime_state.job_received(self.proof_adapter.current_job, subscription_state)
        self._publish_status()
        self.runtime_state.authorizing()
        self._publish_status()
        authorized = await self.request("mining.authorize", [self.username, self.password])
        if authorized is not True:
            self.runtime_state.authorization_failed("mining.authorize was rejected")
            self._publish_status()
            await self.close()
            raise StratumAuthorizationError("mining.authorize was rejected")
        self.runtime_state.authorization_confirmed()
        self._publish_status()
        if self.endpoint.extranonce_subscribe:
            try:
                await self.request("mining.extranonce.subscribe", [], timeout=5.0)
            except (StratumProtocolError, TimeoutError) as exc:
                # Optional extension: without it the pool reconnects us on an
                # extranonce change instead of pushing mining.set_extranonce.
                LOG.warning("%s declined mining.extranonce.subscribe: %s", self.endpoint.name, exc)
        LOG.info("Pool: %s connected", self.endpoint.name)
        LOG.info("Subscription: extranonce1=%s", self.proof_adapter.subscription.extranonce1)
        LOG.info("Authorized: true")

    async def close(self) -> None:
        self._closed = True
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionError("Stratum session closed"))
        self._pending.clear()
        if self.writer:
            self.writer.close()
            with contextlib.suppress(Exception):
                await self.writer.wait_closed()
        self.writer = None
        self.reader = None
        self.proof_adapter.drop_session()
        self._jobs.clear()
        self.runtime_state.disconnected("Stratum session closed")
        self._publish_status()

    async def _read_loop(self) -> None:
        assert self.reader is not None
        try:
            while not self._closed:
                line = await self.reader.readline()
                if not line:
                    raise ConnectionError("Stratum socket closed")
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise StratumProtocolError("Stratum message must be a JSON object")
                self.runtime_state.message_received()
                if "id" in message and message["id"] is not None:
                    try:
                        response_id = int(message["id"])
                    except (TypeError, ValueError) as exc:
                        raise StratumProtocolError(
                            "Stratum response id must be an integer"
                        ) from exc
                    future = self._pending.pop(response_id, None)
                    if future is None:
                        LOG.warning("orphan Stratum response: %s", message)
                    elif "error" in message and message["error"]:
                        future.set_exception(StratumProtocolError(str(message["error"])))
                    else:
                        future.set_result(message.get("result"))
                else:
                    await self._handle_notification(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(exc)
            self._pending.clear()
            if not self._closed:
                LOG.warning("%s reader stopped: %s", self.endpoint.name, exc)
                self.proof_adapter.drop_session()
                self._jobs.clear()
                self.runtime_state.disconnected(str(exc))
                self._publish_status()

    async def _handle_notification(self, message: Mapping[str, Any]) -> None:
        method = message.get("method")
        params = message.get("params", [])
        handled = None
        if method in {
            "mining.notify",
            "mining.set_difficulty",
            "mining.set_target",
            "mining.set_extranonce",
        }:
            handled = self.proof_adapter.handle_message(message)
        if method == "mining.notify" and params:
            job_id = str(params[0])
            self._jobs[job_id] = StratumJob(job_id, tuple(params), time.time())
            subscription = self.proof_adapter.subscription
            job = self.proof_adapter.current_job
            if job is None:
                raise StratumProtocolError("mining.notify did not create an active job")
            if subscription is None:
                # Pools commonly send the first notify straight after the
                # subscribe response, before connect() has consumed it.
                LOG.debug("job %s held until the subscription is confirmed", job_id)
                return
            self.runtime_state.job_received(job, subscription)
            self._publish_status()
            LOG.info("Job received: %s", job_id)
        elif method in {"mining.set_difficulty", "mining.set_target"}:
            if not isinstance(handled, int):
                raise StratumProtocolError(f"{method} did not produce a target")
            value = params[0] if isinstance(params, Sequence) and params else None
            self.runtime_state.target_updated(target=handled, source=str(method), value=value)
            self._publish_status()
            LOG.info("%s update from %s: %s", method, self.endpoint.name, params)
        elif method == "mining.set_extranonce":
            subscription = self.proof_adapter.subscription
            if subscription is None:
                raise StratumProtocolError("mining.set_extranonce removed subscription state")
            self.runtime_state.extranonce_updated(subscription)
            self._publish_status()
        elif method == "client.reconnect":
            # Honour the request by ending this session; the hardware loop
            # reconnects to the CONFIGURED endpoint. A host/port redirect is
            # logged but never followed, so a pool cannot divert the miner.
            LOG.warning("%s requested reconnect: %s", self.endpoint.name, params)
            raise ConnectionError("pool requested client.reconnect")

    async def request(
        self, method: str, params: list[Any], *, timeout: float | None = None
    ) -> Any:
        if not self.writer:
            raise ConnectionError("Stratum session is not connected")
        if self._reader_task is not None and self._reader_task.done():
            raise ConnectionError("Stratum reader has stopped; no response can arrive")
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
        self.writer.write(payload)
        await self.writer.drain()
        limit = self.request_timeout if timeout is None else timeout
        try:
            return await asyncio.wait_for(future, timeout=limit)
        except asyncio.TimeoutError as exc:
            self._pending.pop(request_id, None)
            raise TimeoutError(f"Stratum request {method!r} timed out after {limit:.1f}s") from exc

    async def submit(self, params: list[Any]) -> Any:
        if len(params) < 2:
            raise StratumProtocolError("mining.submit parameters have no job id")
        self.runtime_state.submission_started(str(params[1]))
        self._publish_status()
        try:
            result = await self.request("mining.submit", params)
        except Exception as exc:
            self.runtime_state.submission_unknown(str(exc))
            self._publish_status()
            raise
        self.runtime_state.submission_finished(result)
        self._publish_status()
        return result

    def latest_job(self) -> StratumJob | None:
        return max(self._jobs.values(), key=lambda job: job.received_at, default=None)


class ManifoldPoolCoordinator:
    """Failover coordinator connecting Aethel records to a pool adapter."""

    def __init__(
        self,
        endpoints: Sequence[PoolEndpoint],
        *,
        username: str,
        password: str,
        submit_enabled: bool = False,
        reconnect_delay: float = 2.0,
        stratum_status_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if not endpoints:
            raise ValueError("at least one pool endpoint is required")
        self.endpoints = tuple(endpoints)
        self.username = username
        self.password = password
        self.submit_enabled = submit_enabled
        self.reconnect_delay = reconnect_delay
        self.stratum_status_sink = stratum_status_sink
        self.client: StratumClient | None = None
        self.endpoint_index = 0
        telemetry_path = os.getenv("MLA1517_TELEMETRY_PATH")
        if telemetry_path and not os.path.isabs(telemetry_path):
            # Resolve against the repo root: the process CWD may have been
            # changed by a supervising parent before this coordinator spawned.
            telemetry_path = str(Path(__file__).resolve().parents[3] / telemetry_path)
        self.telemetry = TelemetryWriter(telemetry_path) if telemetry_path else None
        self.control_socket_path = os.getenv(
            "MLA1517_COORDINATOR_CONTROL_SOCKET",
            "/dev/shm/mla1517_coordinator.sock",
        )
        self._control_server: asyncio.AbstractServer | None = None

    async def force_failover(self, target: str = "secondary") -> bool:
        """Close the active session and select the requested endpoint."""
        if target != "secondary" or len(self.endpoints) < 2:
            return False
        if self.client:
            await self.client.close()
        self.client = None
        self.endpoint_index = 1
        return True

    async def _handle_control_request(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if request.get("op") == "failover":
            ok = await self.force_failover(str(request.get("target", "secondary")))
            return {"status": "ok" if ok else "error"}
        return {"status": "error", "reason": "unsupported operation"}

    async def _control_handler(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request = json.loads((await asyncio.wait_for(reader.readline(), 2.0)).decode())
            if not isinstance(request, dict):
                raise ValueError("control request must be a JSON object")
            reply = await self._handle_control_request(request)
        except Exception as exc:
            reply = {"status": "error", "reason": str(exc)}
        writer.write((json.dumps(reply) + "\n").encode())
        await writer.drain()
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()

    async def _start_control_server(self) -> None:
        if os.name == "nt":
            # No AF_UNIX on Windows: loopback TCP, rendezvous file carries
            # the bound host:port for the salamander failover client.
            self._control_server = await asyncio.start_server(
                self._control_handler, host="127.0.0.1", port=0
            )
            bound = self._control_server.sockets[0].getsockname()
            Path(self.control_socket_path).write_text(f"{bound[0]}:{bound[1]}", encoding="utf-8")
            return
        with contextlib.suppress(FileNotFoundError):
            os.unlink(self.control_socket_path)
        self._control_server = await asyncio.start_unix_server(
            self._control_handler, path=self.control_socket_path
        )

    async def connect_with_failover(self) -> StratumClient:
        errors: list[str] = []
        authorization_failures = 0
        for offset in range(len(self.endpoints)):
            index = (self.endpoint_index + offset) % len(self.endpoints)
            endpoint = self.endpoints[index]
            client = StratumClient(
                endpoint,
                username=endpoint.username or self.username,
                password=endpoint.password or self.password,
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
            return client
        if authorization_failures == len(self.endpoints):
            raise StratumAuthorizationError("; ".join(errors))
        raise ConnectionError("; ".join(errors))

    async def submit_candidate(
        self,
        *,
        job_id: str,
        extranonce2: str,
        ntime: str,
        nonce: int | str,
    ) -> bool:
        """Validate a live candidate before invoking ``mining.submit``.

        This is the only coordinator method that can submit a candidate. The
        proof adapter consumes the negotiated job and target first; a pool
        acknowledgement is the only source of an accepted result.
        """
        if not self.client:
            raise ConnectionError("no active Stratum client")
        proof = self.client.proof_adapter.validate_candidate(
            job_id=job_id, extranonce2=extranonce2, ntime=ntime, nonce=nonce
        )
        if not self.submission_permitted():
            LOG.info("submit disabled; proof was checked but no network write occurred")
            return False
        result = await self.client.submit([self.client.username, *proof.submission_params])
        if type(result) is not bool:
            raise StratumProtocolError("mining.submit must return a boolean result")
        accepted = result is True
        if accepted and self.telemetry:
            self.telemetry.add_accepted()
        LOG.info(
            "proof-checked share response accepted=%s endpoint=%s",
            accepted,
            self.client.endpoint.name,
        )
        return accepted

    async def submit_record(self, record: VaultRecord) -> bool:
        if not self.client:
            raise ConnectionError("no active Stratum client")
        job = self.client.latest_job()
        if job is None:
            LOG.warning("dropping node %d record: no Stratum job", record.node_id)
            return False
        if isinstance(record.state, Mapping):
            LOG.error("record state is not a proof; use submit_candidate after SHA256d validation")
            return False
        try:
            params = format_mla1517_submission_params(
                record.state,
                worker_name=self.client.username,
                job=job,
            )
        except StratumTranslationError as exc:
            LOG.error("share not submitted: %s", exc)
            return False
        if not self.submission_permitted():
            LOG.info("submit disabled; validated share payload shape only")
            return False
        result = await self.client.submit(params)
        if type(result) is not bool:
            raise StratumProtocolError("mining.submit must return a boolean result")
        accepted = result is True
        if accepted and self.telemetry:
            self.telemetry.add_accepted()
        LOG.info("share response accepted=%s endpoint=%s", accepted, self.client.endpoint.name)
        return accepted

    def submission_permitted(self) -> bool:
        """Whether a proof-checked share may be written to the pool now."""
        return self.submit_enabled

    async def before_hardware_poll(self) -> bool:
        return True

    async def run_hardware_loop(
        self,
        bridge: MMIOBridge,
        *,
        difficulty_mask: int,
        base_step: int,
        poll_ms: int = 100,
    ) -> None:
        await self._start_control_server()
        bridge.set_difficulty_mask(difficulty_mask)
        bridge.set_base_step(base_step)
        running = False
        try:
            while True:
                if not self.client or not self.client.connected:
                    if self.client:
                        await self.client.close()
                    try:
                        await self.connect_with_failover()
                    except StratumAuthorizationError:
                        LOG.exception("all Stratum endpoints rejected authorization")
                        raise
                    except Exception as exc:
                        LOG.warning("all Stratum endpoints unavailable: %s", exc)
                        await asyncio.sleep(self.reconnect_delay)
                        continue
                permitted = await self.before_hardware_poll()
                if not permitted:
                    if running:
                        bridge.stop()
                        running = False
                    await asyncio.sleep(max(poll_ms / 1000, 0.01))
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
                    except (ConnectionError, asyncio.IncompleteReadError) as exc:
                        LOG.warning("submit connection lost: %s", exc)
                        if self.client:
                            await self.client.close()
                        self.client = None
        finally:
            if self._control_server:
                self._control_server.close()
                await self._control_server.wait_closed()
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self.control_socket_path)
            bridge.stop()
            if self.telemetry:
                self.telemetry.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default=os.getenv("MLA1517_MMIO_DEVICE"))
    parser.add_argument(
        "--map-bytes", type=int, default=int(os.getenv("MLA1517_MMIO_BYTES", "8192"))
    )
    parser.add_argument(
        "--difficulty-mask",
        type=lambda value: int(value, 0),
        default=int(os.getenv("MLA1517_DIFFICULTY_MASK", "0x3f"), 0),
    )
    parser.add_argument("--base-step", type=int, default=int(os.getenv("MLA1517_BASE_STEP", "0")))
    parser.add_argument("--user", default=os.getenv("MLA1517_STRATUM_USER"))
    parser.add_argument("--password", default=os.getenv("MLA1517_STRATUM_PASSWORD", "x"))
    parser.add_argument(
        "--submit", action="store_true", help="enable only after a negotiated adapter is installed"
    )
    parser.add_argument(
        "--tls",
        action="store_true",
        default=os.getenv("MLA1517_STRATUM_TLS", "").strip().lower() in ("1", "true", "yes", "on"),
        help="require TLS on bare pool endpoints (stratum+ssl:// endpoints always use TLS)",
    )
    parser.add_argument("--log-level", default=os.getenv("MLA1517_LOG_LEVEL", "INFO"))
    return parser


async def _main_async(args: argparse.Namespace) -> None:
    if not args.device:
        raise SystemExit("--device or MLA1517_MMIO_DEVICE is required")
    if not args.user:
        raise SystemExit("--user or MLA1517_STRATUM_USER is required")
    endpoints = [
        parse_endpoint(
            os.getenv("MLA1517_BRAIINS_ENDPOINT", "stratum.braiins.com:3333"),
            "braiins",
            tls=args.tls,
        ),
        parse_endpoint(
            os.getenv("MLA1517_VIABTC_ENDPOINT", "btc.viabtc.io:3333"),
            "viabtc",
            tls=args.tls,
        ),
    ]
    coordinator = ManifoldPoolCoordinator(
        endpoints,
        username=args.user,
        password=args.password,
        submit_enabled=args.submit,
    )
    with MMIOBridge(args.device, map_bytes=args.map_bytes) as bridge:
        await coordinator.run_hardware_loop(
            bridge,
            difficulty_mask=args.difficulty_mask,
            base_step=args.base_step,
        )


def main() -> None:
    args = _build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
