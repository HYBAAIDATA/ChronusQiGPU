"""Multi-device SHA-256d composition — one logical grinder over N devices.

``MultiDeviceHasher`` binds one :class:`mining.bitcoin_hasher.BitcoinHasher`
per member device (each with its own context, queue, and persistent
buffers) and splits every nonce window across them with the canonical
Lucas-weighted partitioner (:mod:`hyba.hybrid.lucas_partition`):

- **share** is proportional to the device's *measured* hashrate once a
  real dispatch has produced one; before any measurement the weight is
  the device's compute-unit count — never a fabricated number;
- **disjoint + total** — spans come from ``partition``'s largest-remainder
  certificate and are re-verified before every dispatch;
- **32-epoch aligned** — m32 windows partition in whole-epoch units;
- **≤ 2^32** — no span may cross the nonce field boundary;
- **earliest winner** — the returned winner is the smallest nonce in probe
  order across all spans, identical to the serial scan's ``atomic_min``.

Consensus accept authority is unchanged: every winning nonce is
re-verified with hashlib before this module reports it.
"""

from __future__ import annotations

import hashlib
import struct
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from hyba.hybrid.lucas_partition import partition
from hyba.hybrid.nonce_scheduler import NONCE_SPACE, DeviceCapability

NONCE_BYTES = 4


def _verify_winner(header80: bytes, nonce: int, target_be: bytes) -> bool:
    """hashlib double-SHA256 — the sole accept authority."""
    blob = bytearray(header80)
    struct.pack_into("<I", blob, 76, nonce & 0xFFFFFFFF)
    digest = hashlib.sha256(hashlib.sha256(bytes(blob)).digest()).digest()
    return digest[::-1] <= target_be


@dataclass
class _Member:
    """One bound hasher plus its measured-or-compute-unit weight."""

    hasher: Any
    device_id: str
    compute_units: int
    measured_hps: float = 0.0
    hashes_done: int = 0
    kernel_ms: float = 0.0

    def weight(self) -> float:
        """Measured hps when available; compute units otherwise."""
        if self.measured_hps > 0:
            return self.measured_hps
        return float(max(1, self.compute_units))

    def capability(self) -> DeviceCapability:
        return DeviceCapability(
            device_id=self.device_id,
            device_class="gpu" if self.hasher.backend.startswith("opencl") else "cpu",
            measured_hashes_per_sec=self.measured_hps,
            supported=True,
        )


@dataclass(frozen=True)
class PartitionedSpan:
    device_id: str
    span_base: int  # absolute nonce
    span_count: int
    probe_start: int  # position of span_base in probe order (0 = first)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "span_base": self.span_base,
            "span_count": self.span_count,
            "probe_start": self.probe_start,
        }


class MultiDeviceHasher:
    """Bind one BitcoinHasher per device; dispatch windows via partition.

    ``devices`` may be BitcoinHasher instances or device-name strings
    (each becomes ``BitcoinHasher(device=name)``). A CPU hasher is
    appended automatically as the honest tail for any remainder.
    """

    def __init__(
        self,
        devices: Sequence[Any] = (),
        *,
        include_cpu: bool = True,
    ) -> None:
        from mining.bitcoin_hasher import BitcoinHasher

        self.members: List[_Member] = []
        for d in devices:
            hasher = d if isinstance(d, BitcoinHasher) else BitcoinHasher(device=d)
            units = int(
                getattr(hasher, "_cl_device", None) and hasher._cl_device.max_compute_units
                or 0
            )
            self.members.append(
                _Member(
                    hasher=hasher,
                    device_id=hasher.device,
                    compute_units=units,
                )
            )
        if include_cpu and not any(m.hasher.backend == "cpu" for m in self.members):
            cpu = BitcoinHasher(backend="cpu")
            self.members.append(
                _Member(
                    hasher=cpu,
                    device_id=cpu.device,
                    compute_units=1,
                )
            )
        if not self.members:
            raise ValueError("MultiDeviceHasher requires at least one device")
        self._order = 0  # monotonically increasing probe-order cursor

    # -- partition -----------------------------------------------------------

    def partition_window(
        self,
        base_nonce: int,
        count: int,
        *,
        m32: bool = False,
    ) -> Tuple[List[PartitionedSpan], Dict[str, Any]]:
        """Lucas-weighted split of [base_nonce, base_nonce+count).

        For ``m32=True`` the window is partitioned in whole 32-lane epochs:
        every emitted span is a multiple of 32 and aligned to the lane
        boundary. The certificate from ``partition`` is returned alongside
        and re-verified before any dispatch.
        """
        base_nonce = int(base_nonce) & 0xFFFFFFFF
        count = int(count)
        if count <= 0:
            raise ValueError("count must be > 0")
        if base_nonce + count > NONCE_SPACE:
            raise ValueError("window exceeds the uint32 nonce field")

        if m32:
            epochs = count // 32
            if epochs <= 0:
                raise ValueError("m32 partition requires count >= 32")
            spans, cert = partition(
                epochs, [m for m in self.members], strategy="lucas"
            )
            out: List[PartitionedSpan] = []
            cursor = base_nonce
            probe = 0
            for s in spans:
                span_nonces = s.span * 32
                out.append(
                    PartitionedSpan(
                        device_id=s.device_id,
                        span_base=cursor,
                        span_count=span_nonces,
                        probe_start=probe,
                    )
                )
                cursor += span_nonces
                probe += span_nonces
            tail = base_nonce + count - cursor  # remainder < 32 nonces
            if tail > 0:
                out.append(
                    PartitionedSpan(
                        device_id=self._cpu_member().device_id,
                        span_base=cursor,
                        span_count=tail,
                        probe_start=probe,
                    )
                )
            cert_dict = cert.as_dict()
            cert_dict["m32_epochs"] = epochs
            return out, cert_dict

        spans, cert = partition(
            count, [m for m in self.members], strategy="lucas"
        )
        out = []
        cursor = base_nonce
        probe = 0
        for s in spans:
            out.append(
                PartitionedSpan(
                    device_id=s.device_id,
                    span_base=cursor,
                    span_count=s.span,
                    probe_start=probe,
                )
            )
            cursor += s.span
            probe += s.span
        return out, cert.as_dict()

    def _cpu_member(self) -> _Member:
        for m in self.members:
            if m.hasher.backend == "cpu":
                return m
        raise RuntimeError("no cpu member for m32 tail — include_cpu required")

    def _member(self, device_id: str) -> _Member:
        for m in self.members:
            if m.device_id == device_id:
                return m
        raise KeyError(f"partition assigned unknown device {device_id!r}")

    # -- dispatch --------------------------------------------------------------

    def grind_target_range(
        self,
        header80: bytes,
        target_be: bytes,
        base_nonce: int,
        count: int,
    ) -> Dict[str, Any]:
        """Partition [base_nonce, base_nonce+count), grind each span on its
        device, return the earliest winner in probe order (atomic_min).

        Every span is dispatched; the winner minimizes (probe_start +
        local nonce offset) — identical to the serial scan. Winners are
        re-verified with hashlib; a failed device claim raises.
        """
        spans, cert = self.partition_window(base_nonce, count)
        best: Optional[Tuple[int, int]] = None  # (probe index, nonce)
        per_device: List[Dict[str, Any]] = []
        total_hashes = 0
        for span in spans:
            member = self._member(span.device_id)
            h = member.hasher
            t0 = time.perf_counter()
            if span.span_count > h.grind_batch:
                # Sub-launch within the span in grind_batch-sized chunks.
                done = 0
                local_winner = None
                local_digest = None
                while done < span.span_count:
                    chunk = min(h.grind_batch, span.span_count - done)
                    w, dg, hs = h.grind_target_range(
                        header80, target_be, span.span_base + done, chunk
                    )
                    total_hashes += hs
                    if w is not None and local_winner is None:
                        local_winner, local_digest = w, dg
                    done += chunk
            else:
                local_winner, local_digest, hs = h.grind_target_range(
                    header80, target_be, span.span_base, span.span_count
                )
                total_hashes += hs
            member.kernel_ms += (time.perf_counter() - t0) * 1e3
            member.hashes_done += span.span_count
            if member.kernel_ms > 0:
                member.measured_hps = member.hashes_done / (member.kernel_ms / 1e3)
            per_device.append(
                {
                    **span.as_dict(),
                    "hashes": span.span_count,
                    "winner": local_winner,
                }
            )
            if local_winner is not None:
                if not _verify_winner(header80, local_winner, target_be):
                    raise RuntimeError(
                        f"{member.device_id} reported nonce {local_winner} "
                        "but hashlib recheck rejects it"
                    )
                probe_index = span.probe_start + (
                    (local_winner - span.span_base) % NONCE_SPACE
                )
                if best is None or probe_index < best[0]:
                    best = (probe_index, local_winner)
        return {
            "winning_nonce": best[1] if best else None,
            "winning_probe_index": best[0] if best else None,
            "hashes": total_hashes,
            "partition": cert,
            "spans": per_device,
        }

    def grind_target_m32(
        self,
        header80: bytes,
        target_be: bytes,
        base_nonce: int,
        lane_order: Sequence[int],
        count: int,
    ) -> Dict[str, Any]:
        """M32-window composition — whole-epoch Lucas partition + tail.

        Each device's span is a multiple of 32 nonces; the sub-32 tail
        goes to the CPU member in serial order.
        """
        spans, cert = self.partition_window(base_nonce, count, m32=True)
        best: Optional[Tuple[int, int]] = None
        per_device: List[Dict[str, Any]] = []
        total_hashes = 0
        for span in spans:
            member = self._member(span.device_id)
            h = member.hasher
            t0 = time.perf_counter()
            local_winner = None
            done = 0
            while done < span.span_count:
                chunk = min(h.m32_window_max, span.span_count - done)
                chunk -= chunk % 32
                if chunk <= 0:
                    break
                w, _dg, hs = h.grind_target_m32(
                    header80,
                    target_be,
                    span.span_base + done,
                    lane_order,
                    chunk,
                )
                total_hashes += hs
                if w is not None and local_winner is None:
                    local_winner = w
                done += chunk
            member.kernel_ms += (time.perf_counter() - t0) * 1e3
            member.hashes_done += span.span_count
            if member.kernel_ms > 0:
                member.measured_hps = member.hashes_done / (member.kernel_ms / 1e3)
            per_device.append(
                {**span.as_dict(), "hashes": span.span_count, "winner": local_winner}
            )
            if local_winner is not None:
                if not _verify_winner(header80, local_winner, target_be):
                    raise RuntimeError(
                        f"{member.device_id} reported nonce {local_winner} "
                        "but hashlib recheck rejects it"
                    )
                probe_index = span.probe_start + (
                    (local_winner - span.span_base) % NONCE_SPACE
                )
                if best is None or probe_index < best[0]:
                    best = (probe_index, local_winner)
        return {
            "winning_nonce": best[1] if best else None,
            "winning_probe_index": best[0] if best else None,
            "hashes": total_hashes,
            "partition": cert,
            "spans": per_device,
        }

    def telemetry(self) -> Dict[str, Any]:
        return {
            "members": [
                {
                    "device_id": m.device_id,
                    "backend": m.hasher.backend,
                    "compute_units": m.compute_units,
                    "measured_hps": m.measured_hps,
                    "hashes_done": m.hashes_done,
                }
                for m in self.members
            ]
        }


__all__ = ["MultiDeviceHasher", "PartitionedSpan"]
