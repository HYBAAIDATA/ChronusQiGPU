"""Remote OpenCL hasher — a GPU anywhere executes the window; proof stays local.

Adapts ``chronus.mla1517.remote_gpu.RemoteGPUClient`` to the dispatch surface
``HashPipeline`` and ``ExecutionRouter`` expect from ``BitcoinHasher``.
Every remote reply is re-verified client-side inside ``execute_sha256d``
(digest recompute, target check, window membership), and the pipeline /
router re-check the winner again at their own boundaries — a network hop
never weakens the proof.

Honesty contract: ``backend`` reports ``remote_opencl`` — the transport —
while each :class:`~chronus.mla1517.remote_gpu.Sha256dResult` carries the
``execution_backend`` the agent actually used (``opencl:gpu``,
``opencl:cpu`` or ``cpu``). Route arms (``k_range``/``k_m32``) exist only
when the agent's health advertises the ``sha256d`` route; the gold
stride arm is deliberately absent because remote hendrix is not
implemented. An unreachable or unconfigured endpoint fails loudly at
bind time, never silently degrades to CPU.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Optional, Sequence

#: Seconds a single /v1/sha256d call may take before the wire fails.
#: A worst-case window (16M nonces on a small iGPU) is far slower than a
#: probe, so dispatch gets its own bound — override with
#: ``MLA1517_REMOTE_GPU_TIMEOUT`` (default matches the client's
#: SHA256D_DEFAULT_TIMEOUT_S). A timeout reports unavailability, never
#: a silently partial window.
DISPATCH_TIMEOUT_S = float(os.environ.get("MLA1517_REMOTE_GPU_TIMEOUT", "300"))


class RemoteHasherError(RuntimeError):
    """The remote hasher cannot bind — honest unavailability."""


@dataclass(frozen=True)
class RemoteRouteHandle:
    """A dispatch arm that physically exists on the remote agent.

    ``ExecutionRouter`` checks kernel handles with ``is not None``; this
    object is the remote analogue — its presence means the agent's
    health advertised the sha256d route, its fields record where the arm
    actually lives. It is not a local kernel handle and claims none.
    """

    endpoint: str
    kernel: str
    order: str


class RemoteOpenCLHasher:
    """BitcoinHasher-compatible dispatch to a remote GPU agent."""

    def __init__(
        self,
        endpoint: str,
        timeout: float = 5.0,
        dispatch_timeout: Optional[float] = None,
    ) -> None:
        from chronus.mla1517.remote_gpu import (
            SHA256D_MAX_BATCH,
            SHA256D_MAX_WINDOW,
            RemoteGPUClient,
        )

        self._client = RemoteGPUClient(endpoint, timeout=timeout)
        self.dispatch_timeout = DISPATCH_TIMEOUT_S if dispatch_timeout is None else dispatch_timeout
        self.endpoint = self._client.endpoint
        self.backend = "remote_opencl"
        self.fallback_reason: Optional[str] = None
        # launches/kernel_ms mirror BitcoinHasher semantics exactly: they
        # count DEVICE work only. A remote call the agent answered on its
        # own CPU is remote work but not a kernel launch — it accumulates
        # in remote_calls/remote_ms instead, so a router that reads
        # launches>0 sees real device execution, never transport activity.
        self.kernel_ms = 0.0
        self.launches = 0
        self.remote_calls = 0
        self.remote_ms = 0.0
        # Physical launch caps of the wire, mirroring BitcoinHasher's
        # grind_batch / m32_window_max: one remote call may carry at most
        # SHA256D_MAX_BATCH explicit nonces or SHA256D_MAX_WINDOW steps.
        self.grind_batch = SHA256D_MAX_BATCH
        self.m32_window_max = SHA256D_MAX_WINDOW
        self._device = "remote"
        self._vendor: Optional[str] = None
        self._sha256d_advertised = False
        try:
            health = self._client.health()
        except Exception:
            health = {}
        eps = health.get("endpoints")
        self._sha256d_advertised = isinstance(eps, list) and "sha256d" in eps
        try:
            devices = self._client.devices()
        except Exception:
            devices = []
        if devices:
            self._device = devices[0].name or "remote"
            self._vendor = devices[0].vendor or None
        self.last_execution_backend: Optional[str] = None
        self.last_measured_ns: Optional[int] = None
        self.last_temperature_c: Optional[float] = None
        self.last_power_w: Optional[float] = None
        if self._sha256d_advertised:
            self.k_range = RemoteRouteHandle(self.endpoint, "bitcoin_sha256d", "contiguous")
            self.k_m32 = RemoteRouteHandle(self.endpoint, "bitcoin_sha256d", "m32")
        self.refresh_telemetry()

    def refresh_telemetry(self) -> None:
        """Re-sample the agent's physical telemetry, if it serves it.

        The wire does not claim a power measurement that was not taken —
        fields stay ``None`` where the host has no probe.
        """
        try:
            rows = self._client.telemetry()
        except Exception:
            return
        for row in rows:
            if row.temperature_c is not None:
                self.last_temperature_c = row.temperature_c
            if row.power_w is not None:
                self.last_power_w = row.power_w

    @classmethod
    def from_env(cls, timeout: float = 5.0) -> "RemoteOpenCLHasher":
        """Bind the first configured endpoint, or fail closed.

        ``backend="remote"`` is an explicit request for remote execution;
        with no endpoint configured there is nothing to bind, so the
        error names the missing configuration rather than degrading.
        """
        from chronus.mla1517.remote_gpu import remote_endpoints

        endpoints = remote_endpoints()
        if not endpoints:
            raise RemoteHasherError(
                "backend 'remote' requires MLA1517_REMOTE_GPU_ENDPOINT "
                "or HYBA_REMOTE_OPENCL_ENDPOINTS"
            )
        return cls(endpoints[0], timeout=timeout)

    @property
    def device(self) -> str:
        return self._device

    @property
    def vendor(self) -> Optional[str]:
        return self._vendor

    def _dispatch(self, **kwargs):
        result = self._client.execute_sha256d(timeout=self.dispatch_timeout, **kwargs)
        self.remote_calls += 1
        measured_ms = (result.measured_ns or 0) / 1e6
        self.remote_ms += measured_ms
        self.last_execution_backend = result.execution_backend
        self.last_measured_ns = result.measured_ns
        if str(result.execution_backend).startswith("opencl"):
            self.launches += 1
            self.kernel_ms += measured_ms
        return result.nonce, result.digest, result.hashes

    def grind_target_range(self, header80, target_be, base_nonce, count):
        """Contiguous-window grind on the remote device."""
        return self._dispatch(
            header=header80,
            target_be=target_be,
            order="contiguous",
            base_nonce=base_nonce,
            count=count,
        )

    def grind_target_range_chunked(
        self, header80, target_be, base_nonce, count, stop_on_first: bool = True
    ):
        """Chunked semantics live agent-side; one call covers the window."""
        return self.grind_target_range(header80, target_be, base_nonce, count)

    def grind_target_m32(self, header80, target_be, base_nonce, lane_order, count):
        """M32 lane-order grind — the remote device runs the same traversal."""
        return self._dispatch(
            header=header80,
            target_be=target_be,
            order="m32",
            base_nonce=base_nonce,
            count=count,
            lane_order=list(lane_order),
        )

    def grind_target_batch(self, header80, target_be, nonces: Sequence[int]):
        """Explicit nonce list; the upload cost is the point of range modes."""
        return self._dispatch(
            header=header80,
            target_be=target_be,
            order="batch",
            nonces=[int(n) & 0xFFFFFFFF for n in nonces],
        )


class RemoteFleetHasher(RemoteOpenCLHasher):
    """One logical hasher over EVERY configured remote agent.

    Each window slices into disjoint per-agent ranges that run in
    parallel, each slice an independently client-verified /v1/sha256d
    call. Per-slice traversal honours the requested order (contiguous /
    m32 lane order / explicit batch); slices complete in wall-clock
    order — that concurrency is the point of a fleet, and partial
    coverage is never reported: any slice failure fails the whole call.

    Bind semantics: every endpoint that advertises ``sha256d`` joins the
    fleet; endpoints that don't are listed in ``skipped_endpoints`` with
    the reason, and a fleet of zero is an error, never a silent subset
    pretending to be the whole.
    """

    def __init__(
        self,
        endpoints: Sequence[str],
        timeout: float = 5.0,
        dispatch_timeout: Optional[float] = None,
    ) -> None:
        self._endpoints = [str(ep) for ep in endpoints]
        self.dispatch_timeout = DISPATCH_TIMEOUT_S if dispatch_timeout is None else dispatch_timeout
        self.backend = "remote_opencl"
        self.fallback_reason: Optional[str] = None
        self.kernel_ms = 0.0
        self.launches = 0
        self.remote_calls = 0
        self.remote_ms = 0.0
        self.grind_batch = 0
        self.m32_window_max = 0
        self.fleet_size = 0
        self._members: List[RemoteOpenCLHasher] = []
        self.skipped_endpoints: List[str] = []
        for ep in self._endpoints:
            try:
                member = RemoteOpenCLHasher(
                    ep, timeout=timeout, dispatch_timeout=self.dispatch_timeout
                )
            except Exception as exc:
                self.skipped_endpoints.append(f"{ep}: {type(exc).__name__}: {exc}")
                continue
            if not member._sha256d_advertised:
                self.skipped_endpoints.append(f"{ep}: agent does not serve sha256d")
                continue
            self._members.append(member)
        if not self._members:
            raise RemoteHasherError(
                "no configured endpoint serves sha256d "
                f"(skipped: {'; '.join(self.skipped_endpoints) or 'none'})"
            )
        self.fleet_size = len(self._members)
        first = self._members[0]
        # A call fans out to every member, each under its own wire cap —
        # the fleet's per-call capacity is honestly their sum.
        self.grind_batch = self.fleet_size * first.grind_batch
        self.m32_window_max = self.fleet_size * first.m32_window_max
        self.k_range = first.k_range
        self.k_m32 = first.k_m32
        self.last_execution_backend: Optional[str] = None
        self.last_measured_ns: Optional[int] = None
        self.last_temperature_c: Optional[float] = None
        self.last_power_w: Optional[float] = None
        self.refresh_telemetry()

    @classmethod
    def from_env(cls, timeout: float = 5.0) -> "RemoteFleetHasher":
        from chronus.mla1517.remote_gpu import remote_endpoints

        endpoints = remote_endpoints()
        if not endpoints:
            raise RemoteHasherError(
                "backend 'remote' requires MLA1517_REMOTE_GPU_ENDPOINT "
                "or HYBA_REMOTE_OPENCL_ENDPOINTS"
            )
        return cls(endpoints, timeout=timeout)

    @property
    def endpoint(self) -> str:
        return ",".join(m.endpoint for m in self._members)

    @property
    def device(self) -> str:
        return "fleet[" + ", ".join(m.device for m in self._members) + "]"

    @property
    def vendor(self) -> Optional[str]:
        vendors = {m.vendor for m in self._members if m.vendor}
        return next(iter(vendors)) if len(vendors) == 1 else None

    @property
    def _client(self):  # pragma: no cover - single-client callers get a fleet view
        return self._members[0]._client

    def refresh_telemetry(self) -> None:
        temps = []
        watts = []
        for m in self._members:
            m.refresh_telemetry()
            if m.last_temperature_c is not None:
                temps.append(m.last_temperature_c)
            if m.last_power_w is not None:
                watts.append(m.last_power_w)
        # The fleet's thermal figure is the hottest member, its draw the
        # sum — both honest measurements, never averages of missing data.
        self.last_temperature_c = max(temps) if temps else None
        self.last_power_w = sum(watts) if watts else None

    def _slice(self, order: str, base: int, count: int, nonces, lane_order) -> List[dict]:
        n = len(self._members)
        if order == "batch":
            k, rem = divmod(len(nonces), n)
            out, i = [], 0
            for m in range(n):
                take = k + (1 if m < rem else 0)
                if take:
                    out.append({"order": "batch", "nonces": list(nonces[i : i + take])})
                i += take
            return out
        out = []
        if order == "m32":
            # Serial m32 walks whole 32-step lane epochs: step s probes
            # base + lane[s % 32] + 32*(s // 32). A member's local sweep
            # only covers its region correctly when the region starts on an
            # epoch boundary and spans a whole number of epochs — anything
            # else produces coverage gaps, duplicate probes, and
            # out-of-window nonces. Slices therefore split whole epochs.
            if count % 32:
                raise ValueError("m32 grind window must be a multiple of 32")
            epochs, rem = divmod(count // 32, n)
            start = base
            for m in range(n):
                take = 32 * (epochs + (1 if m < rem else 0))
                if take:
                    out.append(
                        {
                            "order": "m32",
                            "base_nonce": start,
                            "count": take,
                            "lane_order": lane_order,
                        }
                    )
                    start += take
            return out
        # Contiguous slices are exact by construction: serial order visits
        # base+i, so any split into contiguous regions preserves coverage.
        k, rem = divmod(count, n)
        start = base
        for m in range(n):
            take = k + (1 if m < rem else 0)
            if take:
                out.append({"order": order, "base_nonce": start, "count": take})
                start += take
        return out

    def _dispatch(self, **kwargs):
        order = kwargs.get("order", "contiguous")
        header = kwargs["header"]
        target = kwargs["target_be"]
        if order == "batch":
            slices = self._slice("batch", 0, 0, kwargs["nonces"], None)
        else:
            slices = self._slice(
                order,
                kwargs["base_nonce"],
                kwargs["count"],
                None,
                kwargs.get("lane_order"),
            )
        if not slices:
            return None, None, 0

        members = self._members[: len(slices)]

        def _run(member, body):
            return member._client.execute_sha256d(
                header=header,
                target_be=target,
                timeout=self.dispatch_timeout,
                **body,
            )

        with ThreadPoolExecutor(max_workers=len(members)) as pool:
            results = list(pool.map(_run, members, slices))

        self.remote_calls += len(results)
        winner_nonce: Optional[int] = None
        winner_digest = None
        total_hashes = 0
        measured = []
        backends = set()
        # Slices are indexed in traversal order: the winner from the
        # earliest slice is the winner the serial order would find first.
        for res in results:
            total_hashes += res.hashes
            backends.add(res.execution_backend)
            if res.measured_ns is not None:
                measured.append(res.measured_ns)
            if winner_nonce is None and res.nonce is not None:
                winner_nonce, winner_digest = res.nonce, res.digest
            if str(res.execution_backend).startswith("opencl"):
                self.launches += 1
                self.kernel_ms += (res.measured_ns or 0) / 1e6
        # remote_ms is remote elapsed time: the fleet's wall clock is the
        # slowest slice, not summed device-seconds across members.
        self.remote_ms += (max(measured) if measured else 0) / 1e6
        self.last_execution_backend = "+".join(sorted(backends))
        self.last_measured_ns = max(measured) if measured else None
        return winner_nonce, winner_digest, total_hashes

    def grind_target_range(self, header80, target_be, base_nonce, count):
        return self._dispatch(
            header=header80,
            target_be=target_be,
            order="contiguous",
            base_nonce=base_nonce,
            count=count,
        )

    def grind_target_range_chunked(
        self, header80, target_be, base_nonce, count, stop_on_first: bool = True
    ):
        return self.grind_target_range(header80, target_be, base_nonce, count)

    def grind_target_m32(self, header80, target_be, base_nonce, lane_order, count):
        # Same window contract as the local hashers: a whole number of
        # 32-step lane epochs. Checked here because the epoch-aligned
        # slicing in _slice cannot carry a partial epoch.
        if int(count) % 32:
            raise ValueError("m32 grind window must be a multiple of 32")
        return self._dispatch(
            header=header80,
            target_be=target_be,
            order="m32",
            base_nonce=base_nonce,
            count=count,
            lane_order=list(lane_order),
        )

    def grind_target_batch(self, header80, target_be, nonces: Sequence[int]):
        return self._dispatch(
            header=header80,
            target_be=target_be,
            order="batch",
            nonces=[int(n) & 0xFFFFFFFF for n in nonces],
        )


def hasher_for_env(timeout: float = 5.0) -> RemoteOpenCLHasher:
    """Bind whatever the endpoint config describes: one agent or a fleet.

    A single endpoint binds the single-agent hasher unchanged; several
    endpoints bind the fleet — the configured topology is what runs,
    honestly reported through the same dispatch surface either way.
    """
    from chronus.mla1517.remote_gpu import remote_endpoints

    endpoints = remote_endpoints()
    if not endpoints:
        raise RemoteHasherError(
            "backend 'remote' requires MLA1517_REMOTE_GPU_ENDPOINT "
            "or HYBA_REMOTE_OPENCL_ENDPOINTS"
        )
    if len(endpoints) == 1:
        return RemoteOpenCLHasher(endpoints[0], timeout=timeout)
    return RemoteFleetHasher(endpoints, timeout=timeout)


__all__ = [
    "RemoteHasherError",
    "RemoteFleetHasher",
    "RemoteOpenCLHasher",
    "RemoteRouteHandle",
    "hasher_for_env",
]
