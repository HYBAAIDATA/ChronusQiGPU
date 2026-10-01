"""Remote OpenCL hasher — a GPU anywhere executes the window; proof stays local.

Adapts ``mla1517.remote_gpu.RemoteGPUClient`` to the dispatch surface
``HashPipeline`` and ``ExecutionRouter`` expect from ``BitcoinHasher``.
Every remote reply is re-verified client-side inside ``execute_sha256d``
(digest recompute, target check, window membership), and the pipeline /
router re-check the winner again at their own boundaries — a network hop
never weakens the proof.

Honesty contract: ``backend`` reports ``remote_opencl`` — the transport —
while each :class:`~mla1517.remote_gpu.Sha256dResult` carries the
``execution_backend`` the agent actually used (``opencl:gpu``,
``opencl:cpu`` or ``cpu``). Route arms (``k_range``/``k_m32``) exist only
when the agent's health advertises the ``sha256d`` route; the gold
stride arm is deliberately absent because remote hendrix is not
implemented. An unreachable or unconfigured endpoint fails loudly at
bind time, never silently degrades to CPU.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


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

    def __init__(self, endpoint: str, timeout: float = 30.0) -> None:
        from chronus.mla1517.remote_gpu import (
            SHA256D_MAX_BATCH,
            SHA256D_MAX_WINDOW,
            RemoteGPUClient,
        )

        self._client = RemoteGPUClient(endpoint, timeout=timeout)
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
        if self._sha256d_advertised:
            self.k_range = RemoteRouteHandle(self.endpoint, "bitcoin_sha256d", "contiguous")
            self.k_m32 = RemoteRouteHandle(self.endpoint, "bitcoin_sha256d", "m32")

    @classmethod
    def from_env(cls, timeout: float = 30.0) -> "RemoteOpenCLHasher":
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
        result = self._client.execute_sha256d(**kwargs)
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


__all__ = ["RemoteHasherError", "RemoteOpenCLHasher", "RemoteRouteHandle"]
