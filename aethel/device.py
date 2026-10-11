"""Aethel Chronus SKU: storage and manifold execution ride with Chronus.

``standalone`` binds the Aethel execution context directly to Chronus.
``nested`` keeps the virtual-SM pool inside a host GPU while Chronus still owns
the offering/runtime identity. Turing remains the compute substrate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional

from aethel.chronus import ChronusContext
from aethel.storage import AddressSpace, FibonacciAddress

if TYPE_CHECKING:
    from chronus.seam.scale import ChronusScale

Mode = Literal["standalone", "nested"]


def _sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _u256(digest: bytes) -> int:
    return int.from_bytes(digest[::-1], "big")


@dataclass(frozen=True)
class DeviceTicket:
    mode: Mode
    address: FibonacciAddress
    work_items: int
    lucas_L: int
    backend: str
    ledger_ok: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "product": "Chronus",
            "compute_substrate": "Turing",
            "mode": self.mode,
            "index": self.address.index,
            "fibonacci": self.address.value,
            "work_items": self.work_items,
            "lucas_L": self.lucas_L,
            "backend": self.backend,
            "ledger_ok": self.ledger_ok,
        }


class ChronusSku:
    """Aethel SKU bound to the Chronus iGPU offering."""

    def __init__(
        self,
        mode: Mode = "standalone",
        punch_host=None,
        require_gpu: bool = False,
    ):
        if mode not in ("standalone", "nested"):
            raise ValueError(mode)
        self.mode = mode
        self.space = AddressSpace()
        self.ctx = ChronusContext(
            punch_host=punch_host,
            require_gpu=bool(require_gpu and mode == "standalone"),
        )

    def ingest(
        self,
        job_id: str,
        requested: int,
        payload: str = "",
    ) -> DeviceTicket:
        from chronus.seam.scale import scale_job

        scale: ChronusScale = scale_job(job_id, requested, payload)
        body = json.dumps(
            {
                "job_id": job_id,
                "product": "Chronus",
                "compute_substrate": "Turing",
                "mode": self.mode,
                "scale": scale.as_dict(),
                "sms": getattr(self.ctx.cu_pool, "n_sms", 8),
                "gpu_active": self.ctx.gpu_active,
                "backend": self.ctx.projection_backend,
            },
            default=str,
        ).encode("utf-8")
        address = self.space.write(body)
        return DeviceTicket(
            mode=self.mode,
            address=address,
            work_items=scale.work_items,
            lucas_L=scale.lucas_L,
            backend=self.ctx.projection_backend,
            ledger_ok=self.space.verify(),
        )

    def scan_nonce(
        self,
        header76: bytes,
        target: int,
        window: int,
    ) -> Optional[int]:
        if not isinstance(header76, (bytes, bytearray)) or len(header76) != 76:
            raise ValueError("header76 must be 76 bytes")
        if not isinstance(target, int) or target < 0:
            raise TypeError("target must be a non-negative int")
        window = max(0, int(window))
        host = self.ctx.punch_host
        if self.ctx.gpu_active and hasattr(host, "scan_sha256d"):
            return host.scan_sha256d(bytes(header76), target, window)

        header76_bytes = bytes(header76)
        n_sms = max(1, int(self.ctx.cu_pool.n_sms))
        chunk = max(1, (window + n_sms - 1) // n_sms)
        hits = []

        def work(start: int, end: int) -> Optional[int]:
            for nonce in range(start, end):
                digest = _sha256d(header76_bytes + nonce.to_bytes(4, "little"))
                if _u256(digest) <= target:
                    return nonce
            return None

        futures = []
        for index in range(n_sms):
            start = index * chunk
            end = min(window, start + chunk)
            if start >= end:
                continue
            futures.append(self.ctx.cu_pool.submit_workgroup(work, start, end))
        self.ctx.cu_pool.synchronize_all()
        for future in futures:
            nonce = future.result()
            if nonce is not None:
                hits.append(int(nonce))
        return min(hits) if hits else None


__all__ = ["ChronusSku", "DeviceTicket", "Mode"]
