"""Production Stratum V2 adapter for the canonical PYTHIA mining runtime.

This module does not create a second miner.  It adapts authenticated SV2
extended-channel work into the existing StratumRuntimeState and
StratumProofAdapter contracts so stale detection, nonce-space leasing, SHA256d
validation, submission truth, learning and telemetry remain single-source.

Remote SV2 is accepted only through an authenticated SecureChannel provider.
No plaintext/TLS downgrade is implemented here.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import os
import time
from collections import deque
from typing import Any, Callable

from manifold_pool_coordinator import PoolEndpoint

from mining.stratum_v2 import (
    NewExtendedMiningJob,
    SetExtranoncePrefix,
    SetNewPrevHash,
    SetTarget,
    SetupConnection,
    SessionState,
    StratumV2Client,
    SubmitSharesError,
    SubmitSharesSuccess,
    Sv2ProtocolError,
    Sv2TransportError,
)

from .pool_chain import bip34_height
from .stratum_adapter import (
    MAX_UINT256,
    StratumJob,
    StratumProofAdapter,
    SubscriptionState,
)
from .stratum_state import StratumRuntimeState

SecureChannelFactory = Callable[..., Any]


def _positive_float_env(name: str, default: float) -> float:
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


def _nonnegative_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def load_secure_channel_factory(spec: str | None = None) -> SecureChannelFactory:
    """Load the deployment-owned authenticated SV2 channel factory.

    The configured object must be a callable.  It may return either a
    SecureChannel directly or an awaitable resolving to one.  Cryptographic
    policy/keys remain deployment-owned; this mining adapter never substitutes
    another transport when the provider is absent.
    """

    selected = (spec or os.getenv("PYTHIA_SV2_CHANNEL_FACTORY", "")).strip()
    if not selected:
        raise Sv2TransportError(
            "SV2 endpoint configured but PYTHIA_SV2_CHANNEL_FACTORY is absent"
        )
    module_name, sep, attr = selected.partition(":")
    if not sep or not module_name or not attr:
        raise Sv2TransportError(
            "PYTHIA_SV2_CHANNEL_FACTORY must be 'module:callable'"
        )
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, attr)
    except Exception as exc:
        raise Sv2TransportError(
            f"could not load SV2 secure-channel factory {selected!r}"
        ) from exc
    if not callable(factory):
        raise Sv2TransportError(
            f"SV2 secure-channel factory {selected!r} is not callable"
        )
    return factory


def _v1_prevhash_hex(header_prev_hash: bytes) -> str:
    """Encode SV2's 32 header bytes into the V1 adapter's word-swapped form."""

    if not isinstance(header_prev_hash, bytes) or len(header_prev_hash) != 32:
        raise Sv2ProtocolError("SV2 prev_hash must contain 32 bytes")
    return b"".join(
        header_prev_hash[index : index + 4][::-1]
        for index in range(0, 32, 4)
    ).hex()


class ProductionStratumV2Client:
    """Authenticated SV2 extended-channel client with canonical PYTHIA state."""

    def __init__(
        self,
        endpoint: PoolEndpoint,
        *,
        username: str,
        password: str,
        channel_factory: SecureChannelFactory,
        request_timeout: float | None = None,
        nominal_hash_rate: float | None = None,
        max_target: int = MAX_UINT256,
        min_extranonce_size: int | None = None,
        status_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if endpoint.protocol != "v2":
            raise ValueError("ProductionStratumV2Client requires a v2 endpoint")
        if not username:
            raise ValueError("SV2 user identity is required")
        if not 0 < int(max_target) <= MAX_UINT256:
            raise ValueError("SV2 max_target must be a positive uint256")

        self.endpoint = endpoint
        self.username = username
        # Retained for the common client shape only.  The secure-channel
        # provider owns its own cryptographic credentials and may read
        # deployment secrets independently.
        self.password = password
        self.channel_factory = channel_factory
        self.request_timeout = (
            _positive_float_env("PYTHIA_SV2_REQUEST_TIMEOUT_S", 30.0)
            if request_timeout is None
            else float(request_timeout)
        )
        self.nominal_hash_rate = (
            _positive_float_env("PYTHIA_SV2_NOMINAL_HASHRATE_HS", 1.0)
            if nominal_hash_rate is None
            else float(nominal_hash_rate)
        )
        self.max_target = int(max_target)
        self.min_extranonce_size = (
            _nonnegative_int_env("PYTHIA_SV2_MIN_EXTRANONCE_SIZE", 4)
            if min_extranonce_size is None
            else int(min_extranonce_size)
        )
        if self.request_timeout <= 0 or self.nominal_hash_rate <= 0:
            raise ValueError("SV2 request timeout and nominal hashrate must be positive")
        if not 0 <= self.min_extranonce_size <= 32:
            raise ValueError("SV2 min_extranonce_size must be in [0, 32]")

        endpoint_text = f"{endpoint.host}:{endpoint.port}"
        redacted_worker = (username[:2] + "***") if len(username) > 2 else "***"
        self.runtime_state = StratumRuntimeState(
            pool_id=endpoint.name,
            endpoint=endpoint_text,
            worker=redacted_worker,
        )
        self.proof_adapter = StratumProofAdapter()
        self._status_sink = status_sink
        self._core: StratumV2Client | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._reader_error: BaseException | None = None
        self._pending_submissions: dict[int, asyncio.Future[bool]] = {}
        self._submit_rtt_ms: deque[float] = deque(maxlen=2048)
        self._stale_dropped = 0
        self._wire_writes = 0

    @property
    def connected(self) -> bool:
        core = self._core
        reader_ok = self._reader_task is not None and not self._reader_task.done()
        return bool(
            core is not None
            and core.state is SessionState.CHANNEL_OPEN
            and reader_ok
            and self._reader_error is None
            and self.runtime_state.transport_connected
        )

    def wire_writes_for(self, method: str) -> int:
        return self._wire_writes if str(method) == "mining.submit" else 0

    def record_stale_candidate(self) -> None:
        self._stale_dropped += 1
        self._publish_status()

    async def _build_channel(self) -> Any:
        produced = self.channel_factory(
            endpoint=self.endpoint,
            username=self.username,
            password=self.password,
        )
        if inspect.isawaitable(produced):
            produced = await produced
        if produced is None:
            raise Sv2TransportError("SV2 secure-channel factory returned no channel")
        if not getattr(produced, "secure", False):
            raise Sv2TransportError(
                "SV2 secure-channel factory returned an unauthenticated channel"
            )
        return produced

    async def connect(self) -> None:
        self.runtime_state.connecting()
        self._publish_status()
        try:
            channel = await self._build_channel()
            core = StratumV2Client(
                channel,
                SetupConnection(
                    protocol=0,
                    endpoint_host=self.endpoint.host,
                    endpoint_port=self.endpoint.port,
                    device_id=self.username,
                ),
                require_secure=True,
            )
            await core.open()
            self._core = core
            self.runtime_state.connected()
            self.runtime_state.subscribing()

            await core.open_extended_channel(
                request_id=1,
                nominal_hash_rate=self.nominal_hash_rate,
                max_target=self.max_target,
                user_identity=self.username,
                min_extranonce_size=self.min_extranonce_size,
            )
            if core.extranonce_size is None:
                raise Sv2ProtocolError(
                    "extended mining channel did not negotiate extranonce size"
                )
            subscription = self.proof_adapter.handle_subscribe_result(
                [[], core.extranonce_prefix.hex(), core.extranonce_size]
            )
            self.runtime_state.subscription_confirmed(subscription)
            if core.target is None:
                raise Sv2ProtocolError("extended mining channel did not supply a target")
            self.proof_adapter.target = core.target
            self.runtime_state.target_updated(
                target=core.target,
                source="sv2.open_extended_channel",
                value=f"{core.target:064x}",
            )
            # OpenExtendedMiningChannel.Success is the identity admission for
            # the channel.  There is no V1-style mining.authorize exchange.
            self.runtime_state.authorizing()
            self.runtime_state.authorization_confirmed()
            self._reader_task = asyncio.create_task(
                self._reader_loop(),
                name=f"pythia-sv2-reader:{self.endpoint.name}",
            )
            self._publish_status()
        except BaseException as exc:
            self.runtime_state.disconnected(str(exc))
            self._publish_status()
            await self.close()
            raise

    async def _reader_loop(self) -> None:
        assert self._core is not None
        try:
            while True:
                event = await self._core.receive_event()
                self.runtime_state.message_received()
                if isinstance(event, NewExtendedMiningJob):
                    if event.min_ntime is not None:
                        self._activate_job(event, clean_jobs=False)
                elif isinstance(event, SetNewPrevHash):
                    job = self._core.jobs.get(event.job_id)
                    if isinstance(job, NewExtendedMiningJob):
                        self._activate_job(job, clean_jobs=True)
                elif isinstance(event, SetTarget):
                    self.proof_adapter.target = event.maximum_target
                    self.proof_adapter._retarget_jobs()
                    self.runtime_state.target_updated(
                        target=event.maximum_target,
                        source="sv2.SetTarget",
                        value=f"{event.maximum_target:064x}",
                    )
                elif isinstance(event, SetExtranoncePrefix):
                    self._replace_extranonce_prefix(event.extranonce_prefix)
                elif isinstance(event, SubmitSharesSuccess):
                    self._resolve_success(event)
                elif isinstance(event, SubmitSharesError):
                    self._resolve_error(event)
                self._publish_status()
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            self._reader_error = exc
            for future in list(self._pending_submissions.values()):
                if not future.done():
                    future.set_exception(
                        ConnectionError(f"SV2 reader failed: {type(exc).__name__}: {exc}")
                    )
            self._pending_submissions.clear()
            self.runtime_state.disconnected(str(exc))
            self._publish_status()

    def _replace_extranonce_prefix(self, prefix: bytes) -> None:
        core = self._core
        if core is None or core.extranonce_size is None:
            raise Sv2ProtocolError("SV2 extranonce update without an open channel")
        subscription = SubscriptionState(prefix.hex(), core.extranonce_size)
        self.proof_adapter.subscription = subscription
        self.proof_adapter.current_job = None
        self.proof_adapter.jobs.clear()
        self.proof_adapter._extranonce2_counter = 0
        self.runtime_state.extranonce_updated(subscription)
        active = core.jobs.get(core.active_job_id) if core.active_job_id is not None else None
        if isinstance(active, NewExtendedMiningJob):
            self._activate_job(active, clean_jobs=True)

    def _activate_job(self, raw: NewExtendedMiningJob, *, clean_jobs: bool) -> None:
        core = self._core
        if (
            core is None
            or core.current_prev_hash is None
            or core.current_nbits is None
            or core.target is None
            or self.proof_adapter.subscription is None
        ):
            return
        ntime = (
            raw.min_ntime
            if raw.min_ntime is not None
            else core.current_min_ntime
        )
        if ntime is None:
            return
        job = StratumJob(
            job_id=str(raw.job_id),
            prevhash=_v1_prevhash_hex(core.current_prev_hash),
            coinb1=raw.coinbase_tx_prefix.hex(),
            coinb2=raw.coinbase_tx_suffix.hex(),
            merkle_branch=tuple(item.hex() for item in raw.merkle_path),
            version=f"{raw.version:08x}",
            nbits=f"{core.current_nbits:08x}",
            ntime=f"{ntime:08x}",
            clean_jobs=bool(clean_jobs),
            target=core.target,
        )
        self.proof_adapter.target = core.target
        normalized = self.proof_adapter.on_job_received(job)
        self.runtime_state.job_received(
            normalized,
            self.proof_adapter.subscription,
        )

    def _resolve_success(self, event: SubmitSharesSuccess) -> None:
        for sequence, future in list(self._pending_submissions.items()):
            if sequence <= event.last_sequence_number and not future.done():
                future.set_result(True)
                del self._pending_submissions[sequence]

    def _resolve_error(self, event: SubmitSharesError) -> None:
        future = self._pending_submissions.pop(event.sequence_number, None)
        if future is not None and not future.done():
            future.set_result(False)

    async def submit(self, params: list[Any]) -> bool:
        if len(params) != 5:
            raise Sv2ProtocolError(
                "canonical SV2 submission requires worker, job, extranonce, ntime, nonce"
            )
        if not self.connected or self._core is None:
            raise ConnectionError("SV2 channel is not connected")
        _worker, job_id_text, extranonce_hex, ntime_hex, nonce_hex = params
        try:
            job_id = int(str(job_id_text), 10)
            ntime = int(str(ntime_hex), 16)
            nonce = int(str(nonce_hex), 16)
            extranonce = bytes.fromhex(str(extranonce_hex))
        except (TypeError, ValueError) as exc:
            raise Sv2ProtocolError("invalid canonical SV2 submission fields") from exc

        raw = self._core.jobs.get(job_id)
        if not isinstance(raw, NewExtendedMiningJob):
            raise Sv2ProtocolError("SV2 submission refers to an unknown extended job")

        self.runtime_state.submission_started(str(job_id))
        self._publish_status()
        sequence = self._core.sequence_number
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending_submissions[sequence] = future
        started = time.monotonic()
        wrote = False
        try:
            await self._core.submit_extended(
                job_id=job_id,
                nonce=nonce,
                ntime=ntime,
                version=raw.version,
                extranonce=extranonce,
            )
            wrote = True
            self._wire_writes += 1
            result = await asyncio.wait_for(future, timeout=self.request_timeout)
        except BaseException as exc:
            self._pending_submissions.pop(sequence, None)
            if isinstance(exc, asyncio.CancelledError):
                raise
            if wrote:
                self.runtime_state.submission_unknown(str(exc))
            else:
                self.runtime_state.submission_not_written(str(exc))
            self._publish_status()
            raise
        self.runtime_state.submission_finished(result)
        self._submit_rtt_ms.append((time.monotonic() - started) * 1000.0)
        self._publish_status()
        return result

    def latest_job(self) -> StratumJob | None:
        return self.proof_adapter.current_job

    def status_snapshot(self) -> dict[str, Any]:
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
        submission["wire_writes"] = self._wire_writes
        submission["wire_writes_by_method"] = {"mining.submit": self._wire_writes}
        submission["rtt_ms"] = {
            "last": round(last, 3) if last is not None else None,
            "mean": round(mean, 3) if mean is not None else None,
            "p95": round(p95, 3) if p95 is not None else None,
            "samples": len(samples),
        }
        snapshot["protocol"] = "stratum_v2"
        snapshot["outcomes"] = {
            "candidate_total": candidate_total,
            "accepted_ratio": accepted / candidate_total if candidate_total else None,
            "rejected_ratio": rejected / candidate_total if candidate_total else None,
            "unknown_ratio": unknown / candidate_total if candidate_total else None,
            "stale_ratio": (
                self._stale_dropped / candidate_total if candidate_total else None
            ),
            "stale_dropped": self._stale_dropped,
        }
        snapshot["sv2"] = {
            "channel_id": self._core.channel_id if self._core is not None else None,
            "authenticated_transport": bool(
                self._core is not None and getattr(self._core.channel, "secure", False)
            ),
            "extended_channel": True,
        }
        return snapshot

    def _publish_status(self) -> None:
        if self._status_sink is None:
            return
        try:
            self._status_sink(self.status_snapshot())
        except Exception:
            # Status publication must not own protocol liveness.
            pass

    async def close(self) -> None:
        task = self._reader_task
        self._reader_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        for future in list(self._pending_submissions.values()):
            if not future.done():
                future.set_exception(ConnectionError("SV2 session closed"))
        self._pending_submissions.clear()
        core = self._core
        self._core = None
        if core is not None:
            await core.close()
        if self.runtime_state.transport_connected:
            self.runtime_state.disconnected("SV2 session closed")
        self._publish_status()


__all__ = [
    "ProductionStratumV2Client",
    "SecureChannelFactory",
    "load_secure_channel_factory",
]
