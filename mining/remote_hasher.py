"""Remote OpenCL hasher — a GPU anywhere executes the window; proof stays local.

Adapts ``mla1517.remote_gpu.RemoteGPUClient`` to the dispatch surface
``HashPipeline`` expects from ``BitcoinHasher``. Every remote reply is
re-verified client-side inside ``execute_sha256d`` (digest recompute,
target check, window membership), and the pipeline re-checks the winner
again at its own boundary — a network hop never weakens the proof.

Honesty contract: ``backend`` reports ``remote_opencl`` — the transport —
while each :class:`~mla1517.remote_gpu.Sha256dResult` carries the
``execution_backend`` the agent actually used (``opencl:gpu``,
``opencl:cpu`` or ``cpu``). An unreachable or unconfigured endpoint fails
loudly at bind time, never silently degrades to CPU.
"""

from __future__ import annotations

from typing import Optional, Sequence


class RemoteHasherError(RuntimeError):
    """The remote hasher cannot bind — honest unavailability."""


class RemoteOpenCLHasher:
    """BitcoinHasher-compatible dispatch to a remote GPU agent."""

    def __init__(self, endpoint: str, timeout: float = 30.0) -> None:
        from mla1517.remote_gpu import RemoteGPUClient

        self._client = RemoteGPUClient(endpoint, timeout=timeout)
        self.endpoint = self._client.endpoint
        self.backend = "remote_opencl"
        self.fallback_reason: Optional[str] = None
        self.kernel_ms = 0.0
        self.launches = 0
        self._device = "remote"
        try:
            devices = self._client.devices()
        except Exception:
            devices = []
        if devices:
            self._device = devices[0].name or "remote"
        self.last_execution_backend: Optional[str] = None
        self.last_measured_ns: Optional[int] = None

    @classmethod
    def from_env(cls, timeout: float = 30.0) -> "RemoteOpenCLHasher":
        """Bind the first configured endpoint, or fail closed.

        ``backend="remote"`` is an explicit request for remote execution;
        with no endpoint configured there is nothing to bind, so the
        error names the missing configuration rather than degrading.
        """
        from mla1517.remote_gpu import remote_endpoints

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

    def _dispatch(self, **kwargs):
        result = self._client.execute_sha256d(**kwargs)
        self.launches += 1
        if result.measured_ns is not None:
            self.kernel_ms += result.measured_ns / 1e6
        self.last_execution_backend = result.execution_backend
        self.last_measured_ns = result.measured_ns
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


__all__ = ["RemoteHasherError", "RemoteOpenCLHasher"]
