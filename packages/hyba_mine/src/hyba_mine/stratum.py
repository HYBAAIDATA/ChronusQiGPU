# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Stratum V1 for HYBA Mine: TLS, reconnect, stale jobs and literal pool replies.

``StratumConnection`` is one socket (plain TCP or ``stratum+ssl`` with
certificate and host-name verification) with a reader task that matches
replies to requests by id and queues server pushes. ``PoolSession`` runs the
handshake (BIP310 ``mining.configure`` for version rolling, ``mining.subscribe``,
optional ``mining.extranonce.subscribe``, ``mining.authorize``), applies
``mining.set_difficulty``, ``mining.notify``, ``mining.set_extranonce``,
``mining.set_version_mask`` and ``client.reconnect``, reconnects with a doubling
back-off across the pool's published endpoints (also when the pool has been
silent for ``IDLE_TIMEOUT_SECONDS``, which catches a connection that died
while the Mac slept), and submits shares. ``client.reconnect`` is honoured
on the configured endpoints only; HYBA Mine never follows a redirect to an
unlisted host.

Job parsing and header construction reuse ``chronus.execution.stratum``
(``StratumJob``); this module adds the session state that decides when a job
is stale: a job belongs to one connection generation and one extranonce
epoch, ``clean_jobs`` drops every earlier job, and a reconnect drops them all.
A pool reply is returned exactly as received; nothing is inferred from
silence.

Version rolling (BIP310) rolls only bits that the pool granted and HYBA Mine
asked for (``1fffe000``): ``version_mask`` is that intersection. The pool
rebuilds nVersion with the mask *it* sent (``pool_version_mask``, which may be
wider), as ``(job_version & ~pool_mask) | (bits & pool_mask)``, so the 6th
submit param is the hashed version under the pool's mask
(``submit_version_bits``), never the bits under the narrower rolling mask.
A pool that answers ``mining.configure`` with an error, ``false``, a malformed
mask or not at all gets unrolled work and 5-param submits; a pool that closes
the connection on ``mining.configure`` is reconnected without it
(``configure_dropped``) and also gets unrolled work. ``mining.set_version_mask``
changes the masks at once and does not cancel jobs; a share whose hashed
version the pool's current mask would not rebuild is never sent
(``VersionMaskMismatch``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from collections import OrderedDict
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Callable, Optional

from chronus.execution.stratum import StratumJob
from chronus.stratum.bip310 import (
    DEFAULT_CLIENT_MASK_HEX,
    build_mining_submit_params,
    parse_and_intersect_version_mask,
)

from hyba_mine import __version__
from hyba_mine.control import utc_now
from hyba_mine.credentials import PoolLogin
from hyba_mine.logsafe import SECRETS, redact_payload
from hyba_mine.pools import PoolEndpoint, PoolProfile
from hyba_mine.plan import MASK32
from hyba_mine.work import CLIENT_VERSION_MASK, VERSION_ROLLING_MIN_BITS, MiningJob, version_fits

log = logging.getLogger("hyba_mine.stratum")

USER_AGENT = f"hyba-mine/{__version__}"
MAX_LINE_BYTES = 1 << 20
MAX_JOBS = 16
MAX_PENDING_REQUESTS = 1024
MAX_PUSH_BACKLOG = 64
REQUEST_TIMEOUT_SECONDS = 60.0
BACKOFF_SECONDS = (1, 2, 4, 8, 16, 32, 60)
IDLE_TIMEOUT_SECONDS = 300.0
CONFIGURE_TIMEOUT_SECONDS = 5.0
DISCONNECTED = "_hyba.disconnected"
_HEX = frozenset("0123456789abcdefABCDEF")


class StratumError(RuntimeError):
    pass


class ConnectionLost(StratumError):
    pass


class HandshakeFailed(StratumError):
    pass


class AuthorizationRejected(StratumError):
    """The pool refused the login; reconnecting would not help."""


class VersionMaskMismatch(StratumError):
    """Rolled version bits that the pool's current version mask does not allow."""


def make_ssl_context(cafile: Optional[str] = None) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=cafile)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def literal(message: Optional[dict]) -> Optional[dict]:
    """A pool reply as received, with any registered login text removed."""
    if message is None:
        return None
    data = redact_payload(message)
    if data != message:
        data["_redacted"] = True
    return data


def _is_hex(text: str, length: Optional[int] = None) -> bool:
    return isinstance(text, str) and len(text) % 2 == 0 and set(text) <= _HEX and (length is None or len(text) == length)


def _mask_hex(value: Any) -> Optional[str]:
    """A BIP310 mask as 8 lower-case hex digits, or None when it is not 1..8 hex digits."""
    if not isinstance(value, str) or not 1 <= len(value) <= 8 or not set(value) <= _HEX:
        return None
    return f"{int(value, 16):08x}"


def validate_job(job: StratumJob) -> None:
    if not _is_hex(job.prevhash, 64):
        raise ValueError("prevhash must be 64 hex characters")
    for name in ("version", "nbits", "ntime"):
        if not _is_hex(getattr(job, name), 8):
            raise ValueError(f"{name} must be 8 hex characters")
    if not _is_hex(job.coinb1) or not _is_hex(job.coinb2):
        raise ValueError("coinbase parts must be hex")
    if any(not _is_hex(branch, 64) for branch in job.merkle_branch):
        raise ValueError("merkle branches must be 64 hex characters each")
    if not job.job_id:
        raise ValueError("job id must not be empty")


class StratumConnection:
    """One Stratum V1 socket with id-matched replies and a push queue."""

    def __init__(
        self,
        endpoint: PoolEndpoint,
        *,
        ssl_context: Optional[ssl.SSLContext] = None,
        connect_timeout: float = 15.0,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.endpoint = endpoint
        self.ssl_context = ssl_context
        self.connect_timeout = connect_timeout
        self.user_agent = user_agent
        self.pushes: asyncio.Queue = asyncio.Queue(maxsize=MAX_PUSH_BACKLOG)
        self.closed = asyncio.Event()
        self.close_reason: Optional[str] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._pending: dict[int, asyncio.Future] = {}
        self._expiry_handles: dict[int, asyncio.TimerHandle] = {}
        self._next_id = 1
        self._task: Optional[asyncio.Task] = None
        self.last_received = 0.0

    async def open(self) -> None:
        context = None
        if self.endpoint.tls:
            context = self.ssl_context or make_ssl_context()
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(
                self.endpoint.host,
                self.endpoint.port,
                ssl=context,
                server_hostname=self.endpoint.host if context is not None else None,
                limit=MAX_LINE_BYTES,
            ),
            timeout=self.connect_timeout,
        )
        self.last_received = asyncio.get_running_loop().time()
        self._task = asyncio.create_task(self._read_loop(), name=f"stratum-read-{self.endpoint.host}")

    async def _read_loop(self) -> None:
        reason = "the pool closed the connection"
        try:
            assert self._reader is not None
            while True:
                line = await self._reader.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    message = json.loads(text)
                except json.JSONDecodeError:
                    log.debug("ignored a malformed line from the pool")
                    continue
                if not isinstance(message, dict):
                    continue
                self.last_received = asyncio.get_running_loop().time()
                if message.get("method"):
                    await self._server_method(message)
                    continue
                request_id = message.get("id")
                if isinstance(request_id, str) and request_id.isdigit():
                    request_id = int(request_id)
                future = self._pending.pop(request_id, None) if isinstance(request_id, int) and not isinstance(request_id, bool) else None
                handle = self._expiry_handles.pop(request_id, None) if future is not None else None
                if handle is not None:
                    handle.cancel()
                if future is not None and not future.done():
                    future.set_result(message)
        except asyncio.CancelledError:
            reason = "HYBA Mine closed the connection"
            raise
        except (OSError, ssl.SSLError, ValueError, asyncio.IncompleteReadError, ConnectionLost) as exc:
            reason = f"connection error: {type(exc).__name__}"
        finally:
            self._mark_closed(reason)

    async def _server_method(self, message: dict) -> None:
        method = message.get("method")
        request_id = message.get("id")
        if request_id is not None and method in ("mining.ping", "client.get_version"):
            result = "pong" if method == "mining.ping" else self.user_agent
            try:
                await self._send({"id": request_id, "result": result, "error": None})
            except ConnectionLost:
                pass
            return
        try:
            self.pushes.put_nowait(message)
        except asyncio.QueueFull:
            raise ConnectionLost("pool push backlog exceeded") from None

    def _mark_closed(self, reason: str) -> None:
        if self.closed.is_set():
            return
        self.close_reason = reason
        self.closed.set()
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionLost(reason))
        self._pending.clear()
        for handle in self._expiry_handles.values():
            handle.cancel()
        self._expiry_handles.clear()
        if self.pushes.full():
            self.pushes.get_nowait()
        self.pushes.put_nowait({"method": DISCONNECTED, "params": [reason]})

    async def _send(self, message: dict) -> None:
        if self.closed.is_set() or self._writer is None:
            raise ConnectionLost(self.close_reason or "not connected")
        self._writer.write((json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8"))
        try:
            await self._writer.drain()
        except (OSError, ssl.SSLError) as exc:
            self._mark_closed(f"connection error: {type(exc).__name__}")
            raise ConnectionLost(self.close_reason) from exc

    def _expire_request(self, request_id: int) -> None:
        self._expiry_handles.pop(request_id, None)
        future = self._pending.pop(request_id, None)
        if future is not None and not future.done():
            future.set_exception(asyncio.TimeoutError("pool response deadline expired"))

    async def request(self, method: str, params: list, *, expiry: float = REQUEST_TIMEOUT_SECONDS) -> tuple[int, asyncio.Future]:
        if len(self._pending) >= MAX_PENDING_REQUESTS:
            raise ConnectionLost("too many unanswered pool requests")
        request_id = self._next_id
        self._next_id += 1
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        self._expiry_handles[request_id] = asyncio.get_running_loop().call_later(
            expiry, self._expire_request, request_id
        )
        try:
            await self._send({"id": request_id, "method": method, "params": params})
        except BaseException:
            self._pending.pop(request_id, None)
            handle = self._expiry_handles.pop(request_id, None)
            if handle is not None:
                handle.cancel()
            future.cancel()
            raise
        return request_id, future

    async def call(self, method: str, params: list, timeout: float) -> dict:
        request_id, future = await self.request(method, params)
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(request_id, None)
            handle = self._expiry_handles.pop(request_id, None)
            if handle is not None:
                handle.cancel()
            if not future.done():
                future.cancel()

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await asyncio.wait_for(self._writer.wait_closed(), timeout=5)
            except (OSError, ssl.SSLError, asyncio.TimeoutError):
                pass
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._mark_closed("HYBA Mine closed the connection")


@dataclass(frozen=True)
class Submission:
    request_id: int
    future: asyncio.Future
    endpoint: PoolEndpoint
    generation: int
    # The 6th submit param as sent, or None when 5 params were sent (no version rolling).
    version_bits: Optional[str] = None


class PoolSession:
    """Keeps one pool connected and turns its pushes into jobs."""

    def __init__(
        self,
        profile: PoolProfile,
        login: PoolLogin,
        *,
        record: Callable[[str, dict], Any],
        tls_policy: str = "prefer",
        ssl_context: Optional[ssl.SSLContext] = None,
        user_agent: str = USER_AGENT,
        connect_timeout: float = 15.0,
        rpc_timeout: float = 30.0,
        backoff: tuple = BACKOFF_SECONDS,
        endpoints: Optional[tuple] = None,
        idle_timeout: float = IDLE_TIMEOUT_SECONDS,
        version_rolling: bool = True,
        configure_timeout: float = CONFIGURE_TIMEOUT_SECONDS,
    ) -> None:
        self.profile = profile
        self.login = login
        self.record = record
        self.endpoints = endpoints or profile.ordered_endpoints(tls_policy)
        self.ssl_context = ssl_context
        self.user_agent = user_agent
        self.connect_timeout = connect_timeout
        self.rpc_timeout = rpc_timeout
        self.backoff = backoff
        self.idle_timeout = idle_timeout
        self.generation = 0
        self.epoch = 0
        self.extranonce1 = b""
        self.extranonce2_size = 0
        self.difficulty: Optional[Fraction] = None
        self.jobs: "OrderedDict[str, MiningJob]" = OrderedDict()
        self.current: Optional[MiningJob] = None
        self.endpoint: Optional[PoolEndpoint] = None
        self.connected = asyncio.Event()
        self.changed = asyncio.Event()
        self.fatal: Optional[BaseException] = None
        self._conn: Optional[StratumConnection] = None
        self._stopping = asyncio.Event()
        self._finished = False
        self._productive = False
        self.clean_seq = 0
        self._watchers: set[asyncio.Event] = set()
        # BIP310: whether to ask for version rolling, whether the pool granted it on
        # this connection (6-param submits), the mask HYBA Mine rolls (the pool's mask
        # intersected with the request), the pool's own mask (what the pool rebuilds
        # nVersion with) and the last outcome.
        self.request_version_rolling = version_rolling
        self.configure_timeout = configure_timeout
        self.version_rolling = False
        self.version_mask = 0
        self.pool_version_mask = 0
        self.version_negotiation: dict = {}
        # Set when the pool closed the connection in answer to mining.configure: later
        # connections of this session skip mining.configure (unrolled work, 5-param submits).
        self._skip_configure = False

    # ----------------------------------------------------------------- state
    def is_valid(self, job: MiningJob) -> bool:
        return (
            self.connected.is_set()
            and job.generation == self.generation
            and job.epoch == self.epoch
            and self.jobs.get(job.job_id) is job
        )

    def current_job(self) -> Optional[MiningJob]:
        job = self.current
        return job if job is not None and self.is_valid(job) else None

    def submit_version_bits(self, version: int) -> int:
        """The 6th submit param for a header hashed with ``version``.

        The pool rebuilds nVersion as ``(job & ~pool_mask) | (bits & pool_mask)``
        with its own mask, so the bits sent are the hashed version under that mask.
        Bits the pool's mask covers but HYBA Mine does not roll carry the job's own
        value, so the rebuilt header is the hashed one.
        """
        return version & self.pool_version_mask & MASK32

    def version_compatible(self, job: MiningJob, version: Optional[int], version_bits: int) -> bool:
        """True when the pool, with its current mask, rebuilds the header version that was hashed.

        ``version_bits`` are the unit's rolled bits and must lie inside the mask HYBA
        Mine asked for; what is checked against the pool's mask is ``version`` itself.
        """
        if version is None:
            return False
        if not self.version_rolling:
            return version == job.base_version and version_bits == 0
        if version_bits & ~CLIENT_VERSION_MASK & MASK32:
            return False
        return version_fits(job.base_version, version, self.submit_version_bits(version), self.pool_version_mask)

    def stale_reason(self, job: MiningJob, version: Optional[int] = None, version_bits: Optional[int] = None) -> Optional[str]:
        """Why ``job`` can no longer be mined on this session, or None while it is valid.

        With ``version``/``version_bits`` (a rolled unit), a valid job whose rolled
        version no longer fits the pool's version mask is stale as
        ``version_mask_changed``.
        """
        if self.is_valid(job):
            if version_bits is not None and not self.version_compatible(job, version, version_bits):
                return "version_mask_changed"
            return None
        if self._stopping.is_set() or self._finished or self.fatal is not None:
            return "session_stopped"
        if not self.connected.is_set() or job.generation != self.generation:
            return "connection_lost"
        if job.epoch != self.epoch:
            return "extranonce_changed"
        if job.clean_seq < self.clean_seq:
            return "clean_jobs"
        return "job_dropped"

    async def wait_stale(self, job: MiningJob, version: Optional[int] = None, version_bits: Optional[int] = None) -> str:
        """Return the stale reason as soon as ``job`` stops being valid.

        Each waiter has its own event, so clearing it never hides a change from
        another waiter. A notify with clean_jobs=false leaves earlier jobs
        valid, so it does not end the wait.
        """
        event = asyncio.Event()
        self._watchers.add(event)
        try:
            while True:
                event.clear()
                reason = self.stale_reason(job, version, version_bits)
                if reason:
                    return reason
                await event.wait()
        finally:
            self._watchers.discard(event)

    def _notify(self) -> None:
        self.changed.set()
        for event in list(self._watchers):
            event.set()

    def _invalidate(self) -> None:
        self.jobs.clear()
        self.current = None
        self._notify()

    # ------------------------------------------------------------- lifecycle
    def stop(self) -> None:
        self._stopping.set()
        self._notify()

    async def disconnect(self) -> None:
        if self._conn is not None:
            await self._conn.close()

    async def run(self, max_attempts: Optional[int] = None) -> None:
        failures = 0
        index = 0
        attempts = 0
        while not self._stopping.is_set() and (max_attempts is None or attempts < max_attempts):
            attempts += 1
            endpoint = self.endpoints[index % len(self.endpoints)]
            established = False
            try:
                established = await self._serve(endpoint)
            except AuthorizationRejected as exc:
                self.fatal = exc
                self.record("pool_auth_rejected", {"pool": self.profile.pool_id, "endpoint": endpoint.url, "reply": literal(exc.args[0] if exc.args and isinstance(exc.args[0], dict) else None)})
                self._finished = True
                self._notify()
                return
            except (OSError, ssl.SSLError, asyncio.TimeoutError, StratumError) as exc:
                self.record(
                    "pool_connect_failed",
                    {"pool": self.profile.pool_id, "endpoint": endpoint.url, "tls": endpoint.tls,
                     "error": SECRETS.redact(f"{type(exc).__name__}: {exc}")[:300]},
                )
                index += 1
            else:
                if not self._productive:
                    index += 1
            if self._stopping.is_set():
                break
            # The back-off resets only after a connection that delivered a job,
            # so a pool that accepts the login and then hangs up is not hammered.
            failures = 0 if established and self._productive else failures + 1
            delay = self.backoff[min(failures, len(self.backoff) - 1)] if self.backoff else 0
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
        self._finished = True
        self._invalidate()

    async def _serve(self, endpoint: PoolEndpoint) -> bool:
        conn = StratumConnection(
            endpoint, ssl_context=self.ssl_context, connect_timeout=self.connect_timeout, user_agent=self.user_agent
        )
        await conn.open()
        self._conn = conn
        self._productive = False
        established = False
        reason = "closed"
        try:
            await self._handshake(conn)
            self.generation += 1
            self.epoch = 0
            self.difficulty = None
            self.endpoint = endpoint
            self.jobs.clear()
            self.current = None
            self.connected.set()
            established = True
            self.record(
                "pool_connected",
                {
                    "pool": self.profile.pool_id,
                    "endpoint": endpoint.url,
                    "tls": endpoint.tls,
                    "generation": self.generation,
                    "extranonce1": self.extranonce1.hex(),
                    "extranonce2_size": self.extranonce2_size,
                    "version_rolling": self.version_rolling,
                    "version_mask": f"{self.version_mask:08x}",
                    "pool_version_mask": f"{self.pool_version_mask:08x}",
                    "version_negotiation": self.version_negotiation,
                    **self.login.public(),
                },
            )
            loop = asyncio.get_running_loop()
            while not self._stopping.is_set():
                quiet = loop.time() - conn.last_received
                if quiet >= self.idle_timeout:
                    reason = f"no message from the pool for {quiet:.0f} s"
                    break
                try:
                    message = await asyncio.wait_for(conn.pushes.get(), timeout=self.idle_timeout - quiet)
                except asyncio.TimeoutError:
                    continue
                if message.get("method") == DISCONNECTED:
                    reason = "HYBA Mine closed the session" if self._stopping.is_set() else str((message.get("params") or ["closed"])[0])
                    break
                if self._apply(message, conn) == "reconnect":
                    reason = "pool asked for a reconnect"
                    break
        finally:
            self.connected.clear()
            self._invalidate()
            await conn.close()
            self._conn = None
            if established:
                self.record("pool_disconnected", {"pool": self.profile.pool_id, "generation": self.generation, "reason": SECRETS.redact(reason)})
        return established

    async def _handshake(self, conn: StratumConnection) -> None:
        await self._configure(conn)
        reply = await conn.call("mining.subscribe", [self.user_agent], self.rpc_timeout)
        result = reply.get("result")
        if reply.get("error") or not isinstance(result, list) or len(result) < 3:
            raise HandshakeFailed("the pool refused mining.subscribe")
        extranonce1, size = result[1], result[2]
        if not _is_hex(extranonce1) or not isinstance(size, int) or isinstance(size, bool) or not 1 <= size <= 32:
            raise HandshakeFailed("mining.subscribe returned an unusable extranonce")
        self.extranonce1 = bytes.fromhex(extranonce1)
        self.extranonce2_size = size
        if self.profile.extranonce_subscribe:
            try:
                await conn.call("mining.extranonce.subscribe", [], 5)
            except asyncio.TimeoutError:
                pass
        reply = await conn.call("mining.authorize", [self.login.username, self.login.password], self.rpc_timeout)
        if reply.get("result") is not True or reply.get("error"):
            raise AuthorizationRejected(reply)

    async def _configure(self, conn: StratumConnection) -> None:
        """BIP310 ``mining.configure``: adopt only the mask the pool granted.

        A pool that ignores, refuses or mangles the request gets unrolled work. A
        pool that closes the connection on it raises ``ConnectionLost`` out of this
        attempt; later connections then skip ``mining.configure`` (``configure_dropped``).
        """
        self.version_rolling = False
        self.version_mask = 0
        self.pool_version_mask = 0
        if not self.request_version_rolling:
            self.version_negotiation = {"outcome": "disabled"}
            return
        if self._skip_configure:
            self.version_negotiation = {
                "outcome": "configure_dropped",
                "reason": "the pool closed the connection in answer to mining.configure; "
                          "not sent again in this session",
            }
            return
        requested = {"version-rolling.mask": DEFAULT_CLIENT_MASK_HEX,
                     "version-rolling.min-bit-count": VERSION_ROLLING_MIN_BITS}
        reply: Optional[dict] = None
        pool_hex: Optional[str] = None
        try:
            reply = await conn.call("mining.configure", [["version-rolling"], requested], self.configure_timeout)
        except asyncio.TimeoutError:
            outcome = "no_reply"
        except ConnectionLost:
            # A legacy pool may hang up on an unknown method: reconnect without it.
            self._skip_configure = True
            self.record("pool_protocol_warning", {"method": "mining.configure", "pool": self.profile.pool_id,
                                                  "reason": "the pool closed the connection in answer to "
                                                            "mining.configure; reconnecting without version rolling"})
            raise
        else:
            result = reply.get("result")
            if reply.get("error"):
                outcome = "unsupported"
            elif not isinstance(result, dict):
                outcome = "malformed"
            elif result.get("version-rolling") is not True:
                outcome = "declined"
            else:
                pool_hex = _mask_hex(result.get("version-rolling.mask"))
                if pool_hex is None:
                    outcome = "malformed"
                else:
                    granted = int(parse_and_intersect_version_mask(pool_hex, DEFAULT_CLIENT_MASK_HEX,
                                                                   VERSION_ROLLING_MIN_BITS), 16)
                    if granted == 0:
                        outcome = "below_min_bits"
                    else:
                        outcome = "granted"
                        self.version_rolling = True
                        self.version_mask = granted
                        self.pool_version_mask = int(pool_hex, 16)
        negotiation = {
            "outcome": outcome,
            "requested_mask": DEFAULT_CLIENT_MASK_HEX,
            "min_bit_count": VERSION_ROLLING_MIN_BITS,
            "pool_mask": pool_hex,
            "granted_mask": f"{self.version_mask:08x}",
        }
        if pool_hex is not None and int(pool_hex, 16) & ~CLIENT_VERSION_MASK:
            # Not rolled, but covered by the pool's mask: submits carry the job's own value there.
            negotiation["pool_bits_not_rolled"] = f"{int(pool_hex, 16) & ~CLIENT_VERSION_MASK & MASK32:08x}"
        if outcome != "granted":
            negotiation["reply"] = literal(reply)
        self.version_negotiation = negotiation

    def _apply(self, message: dict, conn: StratumConnection) -> Optional[str]:
        method = message.get("method")
        params = message.get("params") or []
        if not isinstance(params, (list, tuple)):
            self.record("pool_protocol_warning", {"method": method, "reason": "params must be an array"})
            return None
        if method == "mining.set_difficulty":
            value = params[0] if params else None
            try:
                if isinstance(value, bool):
                    raise ValueError
                difficulty = Fraction(str(value))
                if difficulty <= 0:
                    raise ValueError
            except (ValueError, ZeroDivisionError):
                self.record("pool_protocol_warning", {"method": method, "reason": "difficulty is not a positive number"})
                return None
            self.difficulty = difficulty
            self.record("difficulty", {"pool": self.profile.pool_id, "generation": self.generation, "difficulty": str(difficulty), "literal": value})
        elif method == "mining.notify":
            try:
                job = StratumJob.from_notify(list(params))
                validate_job(job)
            except (ValueError, TypeError) as exc:
                self.record("pool_protocol_warning", {"method": method, "reason": str(exc)[:200]})
                return None
            if job.clean_jobs:
                self.clean_seq += 1
                self.jobs.clear()
            difficulty = self.difficulty
            mining_job = MiningJob(
                job=job,
                pool_id=self.profile.pool_id,
                generation=self.generation,
                epoch=self.epoch,
                extranonce1=self.extranonce1,
                extranonce2_size=self.extranonce2_size,
                difficulty=difficulty if difficulty is not None else Fraction(1),
                received_at=utc_now(),
                clean_seq=self.clean_seq,
            )
            self.jobs[job.job_id] = mining_job
            while len(self.jobs) > MAX_JOBS:
                self.jobs.popitem(last=False)
            self.current = mining_job
            self._productive = True
            view = mining_job.ledger_view()
            if difficulty is None:
                view["difficulty_source"] = "stratum default (no mining.set_difficulty received yet)"
            self.record("job", view)
            self._notify()
        elif method == "mining.set_extranonce":
            if len(params) < 2 or not _is_hex(params[0]) or not isinstance(params[1], int) or isinstance(params[1], bool) or not 1 <= params[1] <= 32:
                self.record("pool_protocol_warning", {"method": method, "reason": "unusable extranonce"})
                return None
            self.extranonce1 = bytes.fromhex(params[0])
            self.extranonce2_size = params[1]
            self.epoch += 1
            self._invalidate()
            self.record("extranonce", {"pool": self.profile.pool_id, "generation": self.generation, "epoch": self.epoch, "extranonce1": params[0], "extranonce2_size": params[1]})
        elif method == "mining.set_version_mask":
            if not self.version_rolling:
                self.record("pool_protocol_warning", {"method": method, "reason": "mining.set_version_mask without negotiated version rolling; ignored"})
                return None
            mask_hex = _mask_hex(params[0] if params else None)
            if mask_hex is None:
                # Fail closed: roll nothing new until the pool sends a usable mask. The pool still
                # rebuilds nVersion with the last mask it sent, so keep that mask: shares already
                # hashed under it must keep matching the version the pool reconstructs.
                new, pool_mask = 0, self.pool_version_mask
                self.record("pool_protocol_warning", {"method": method, "reason": "unusable version mask; rolling paused (new units use no version bits)"})
            else:
                new = int(parse_and_intersect_version_mask(mask_hex, DEFAULT_CLIENT_MASK_HEX, VERSION_ROLLING_MIN_BITS), 16)
                pool_mask = int(mask_hex, 16)
            previous, self.version_mask = self.version_mask, new
            self.pool_version_mask = pool_mask
            self.record("version_mask", {"pool": self.profile.pool_id, "generation": self.generation,
                                         "previous_mask": f"{previous:08x}", "pool_mask": mask_hex,
                                         "granted_mask": f"{new:08x}", "literal": literal({"params": params})})
            # BIP310: jobs stay valid; units rolled under the old mask are checked by their watchers.
            self._notify()
        elif method == "client.reconnect":
            self.record("pool_reconnect_requested", {"pool": self.profile.pool_id, "literal": literal({"params": params})})
            return "reconnect"
        elif method == "client.show_message":
            self.record("pool_message", {"pool": self.profile.pool_id, "text": SECRETS.redact(str(params[0] if params else ""))[:500]})
        return None

    # ---------------------------------------------------------------- submit
    async def submit(self, job: MiningJob, en2: bytes, nonce: int, *,
                     version: Optional[int] = None, version_bits: int = 0,
                     reply_expiry: float = 2 * REQUEST_TIMEOUT_SECONDS) -> Submission:
        if self._conn is None or not self.is_valid(job):
            raise ConnectionLost("the job is no longer valid on this connection")
        if version is None and version_bits == 0:
            version = job.base_version
        if not self.version_compatible(job, version, version_bits):
            raise VersionMaskMismatch("rolled version bits are outside the pool's current version mask")
        params = build_mining_submit_params(
            self.login.username, job.job_id, en2.hex(), job.job.ntime, f"{nonce:08x}",
            f"{self.submit_version_bits(version):08x}" if self.version_rolling else None,
        )
        request_id, future = await self._conn.request("mining.submit", params, expiry=reply_expiry)
        return Submission(request_id, future, self._conn.endpoint, self.generation,
                          params[5] if len(params) == 6 else None)

    async def wait_for_job(self, timeout: Optional[float] = None) -> Optional[MiningJob]:
        deadline = None if timeout is None else asyncio.get_running_loop().time() + timeout
        while not self._stopping.is_set() and self.fatal is None and not self._finished:
            job = self.current_job()
            if job is not None:
                return job
            self.changed.clear()
            remaining = None if deadline is None else deadline - asyncio.get_running_loop().time()
            if remaining is not None and remaining <= 0:
                return None
            try:
                await asyncio.wait_for(self.changed.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                return None
        return None


async def handshake_probe(
    profile: PoolProfile,
    login: PoolLogin,
    *,
    tls_policy: str = "prefer",
    ssl_context: Optional[ssl.SSLContext] = None,
    timeout: float = 30.0,
    endpoints: Optional[tuple] = None,
) -> dict:
    """Pre-flight: connect, subscribe, authorize and wait for the first job, then close."""
    errors = []
    for endpoint in endpoints or profile.ordered_endpoints(tls_policy):
        records: list = []
        session = PoolSession(
            profile, login, record=lambda kind, data: records.append((kind, data)),
            ssl_context=ssl_context, connect_timeout=min(timeout, 15.0), rpc_timeout=timeout,
            backoff=(), endpoints=(endpoint,),
        )
        task = asyncio.create_task(session.run(max_attempts=1))
        try:
            job = await session.wait_for_job(timeout=timeout)
        finally:
            session.stop()
            await session.disconnect()
            try:
                await asyncio.wait_for(task, timeout=10)
            except asyncio.TimeoutError:
                task.cancel()
        if job is not None:
            return {
                "endpoint": endpoint.url,
                "tls": endpoint.tls,
                "extranonce2_size": job.extranonce2_size,
                "first_job_id": job.job_id,
                "difficulty": str(job.difficulty),
                "difficulty_from_pool": session.difficulty is not None,
                "version_rolling": session.version_rolling,
                "version_mask": f"{session.version_mask:08x}",
                "pool_version_mask": f"{session.pool_version_mask:08x}",
                "version_negotiation": session.version_negotiation,
            }
        if isinstance(session.fatal, AuthorizationRejected):
            raise session.fatal
        failed = [data.get("error") for kind, data in records if kind == "pool_connect_failed"]
        errors.append(f"{endpoint.url}: {failed[-1] if failed else 'no job received within the timeout'}")
    raise HandshakeFailed("; ".join(errors))
