"""ASICSolver — NonceScheduler over a real ASIC protocol endpoint.

This module is a *protocol implementation*, not a device model. It speaks
to physical hardware through exactly three real channels:

- **Network bridge** (``HYBRID_ASIC_ENDPOINT=host:port``): a TCP endpoint
  running a stratum-to-device bridge or vendor control plane. Windows are
  sent as JSON lines; shares return the same way.
- **USB serial** (``HYBRID_ASIC_SERIAL=/dev/ttyUSBn`` or ``COMn``): a
  cgminer-style serial control channel. ``pyserial`` presence + a
  responsive port is probed and recorded, but a serial reply does NOT
  make the solver ``supported`` — no serial dispatch protocol exists in
  this module, and ``supported`` means dispatch-capable.
- **PCIe** (``HYBRID_ASIC_PCIE=/dev/node``): a vendor driver node; only
  presence + readability is probed — dispatch over a vendor PCIe protocol
  requires a driver binding this module does not invent.

Work binding: ``prepare(job_id, header80)`` binds the 80-byte block
header to a job id before any window of that job is dispatched — the
same contract :class:`GPUSolver` already honours and the coordinator
already invokes. ``dispatch`` sends the bound 76-byte header prefix
(``header_prefix_hex``) alongside the window; an endpoint that never
received the header cannot produce a valid share, and ``dispatch``
refuses to send a window whose job was never prepared.

Fail-closed contract: when no channel is configured *and* responsive,
``capability().supported`` is False with a concrete reason, ``dispatch``
raises :class:`ASICNotPresent`, and the coordinator's hybrid path
degrades to GPU-only with an attestation gap. Nothing here simulates an
ASIC; there is no test hook that fabricates a device.
"""

from __future__ import annotations

import json
import os
import socket
import time
from typing import Any, Dict, List, Optional

from hyba.hybrid.nonce_scheduler import (
    ASICNotPresent,
    AttestationRegistry,
    DeviceCapability,
    DispatchHandle,
    ExecutionAttestation,
    NonceWindow,
    Share,
    next_handle_id,
)

_PROBE_TIMEOUT_S = 2.0
ASIC_HASH_KERNEL = "sha256d_scan"
OPTIONAL_ASIC_KERNELS = frozenset(
    {"sha256d_midstate", "sha256d_merkle", "fold_certificate", "attest_result"}
)


class ASICSolver:
    """Protocol solver for an attached ASIC. Real hardware or nothing."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        serial_port: Optional[str] = None,
        pcie_node: Optional[str] = None,
    ) -> None:
        self._endpoint = endpoint or os.environ.get("HYBRID_ASIC_ENDPOINT", "").strip() or None
        self._serial_port = serial_port or os.environ.get("HYBRID_ASIC_SERIAL", "").strip() or None
        self._pcie_node = pcie_node or os.environ.get("HYBRID_ASIC_PCIE", "").strip() or None
        self._capability: Optional[DeviceCapability] = None
        self._records: List[ExecutionAttestation] = []
        self._registry = AttestationRegistry.get()
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._finished: Dict[int, int] = {}
        self._jobs: Dict[str, bytes] = {}

    # -- probing ------------------------------------------------------------

    def capability(self) -> DeviceCapability:
        """Probe each configured channel once; cache the honest result."""
        if self._capability is not None:
            return self._capability
        configured = [
            name
            for name, val in (
                ("network", self._endpoint),
                ("serial", self._serial_port),
                ("pcie", self._pcie_node),
            )
            if val
        ]
        if not configured:
            self._capability = DeviceCapability(
                device_id="asic:none",
                device_class="asic",
                measured_hashes_per_sec=0.0,
                supported=False,
                reason_if_unsupported=(
                    "no ASIC channel configured: HYBRID_ASIC_ENDPOINT, "
                    "HYBRID_ASIC_SERIAL and HYBRID_ASIC_PCIE are all unset"
                ),
            )
            return self._capability

        probes: List[DeviceCapability] = []
        if self._endpoint:
            probes.append(self._probe_network(self._endpoint))
        if self._serial_port:
            probes.append(self._probe_serial(self._serial_port))
        if self._pcie_node:
            probes.append(self._probe_pcie(self._pcie_node))
        for cap in probes:
            if cap.supported:
                self._capability = cap
                return cap

        channel_reasons = [c.reason_if_unsupported for c in probes if c.reason_if_unsupported]
        self._capability = DeviceCapability(
            device_id="asic:unresponsive",
            device_class="asic",
            measured_hashes_per_sec=0.0,
            supported=False,
            reason_if_unsupported=(
                "ASIC probe found no dispatch-capable channel: " + "; ".join(channel_reasons)
                if channel_reasons
                else f"ASIC probe failed on all configured channels: {configured}"
            ),
            detail={
                "configured_channels": configured,
                "channel_results": [c.as_dict() for c in probes],
            },
        )
        return self._capability

    def _probe_network(self, endpoint: str) -> DeviceCapability:
        host, _, port_s = endpoint.rpartition(":")
        try:
            port = int(port_s)
            with socket.create_connection((host, port), timeout=_PROBE_TIMEOUT_S) as sock:
                sock.settimeout(_PROBE_TIMEOUT_S)
                sock.sendall(b'{"cmd":"capability"}\n')
                reply = sock.makefile("rb").readline()
            info = json.loads(reply.decode("utf-8", "replace"))
            hps = float(info.get("measured_hashes_per_sec", 0.0))
            advertised = {str(k) for k in info.get("kernels", [ASIC_HASH_KERNEL])}
            if ASIC_HASH_KERNEL not in advertised:
                return DeviceCapability(
                    device_id=str(info.get("device_id", f"asic:{endpoint}")),
                    device_class="asic",
                    measured_hashes_per_sec=0.0,
                    supported=False,
                    reason_if_unsupported="ASIC does not advertise sha256d_scan",
                    detail={"channel": "network", "advertised_kernels": sorted(advertised)},
                )
            return DeviceCapability(
                device_id=str(info.get("device_id", f"asic:{endpoint}")),
                device_class="asic",
                measured_hashes_per_sec=hps,
                supported=True,
                detail={
                    "channel": "network",
                    "endpoint": endpoint,
                    "serial": info.get("serial"),
                    "firmware": info.get("firmware"),
                    "protocol_version": info.get("protocol_version", "legacy-v1"),
                    "advertised_kernels": sorted(advertised),
                    "optional_kernels": sorted(advertised & OPTIONAL_ASIC_KERNELS),
                },
            )
        except Exception as exc:
            return DeviceCapability(
                device_id=f"asic:{endpoint}",
                device_class="asic",
                measured_hashes_per_sec=0.0,
                supported=False,
                reason_if_unsupported=f"network probe failed: {type(exc).__name__}: {exc}",
            )

    def _probe_serial(self, port: str) -> DeviceCapability:
        try:
            import serial  # pyserial — optional dependency
        except Exception:
            return DeviceCapability(
                device_id=f"asic:{port}",
                device_class="asic",
                measured_hashes_per_sec=0.0,
                supported=False,
                reason_if_unsupported="pyserial not installed; serial channel unusable",
            )
        try:
            with serial.Serial(port, baudrate=115200, timeout=_PROBE_TIMEOUT_S) as ser:
                ser.write(b'{"cmd":"capability"}\n')
                reply = ser.readline()
            info = json.loads(reply.decode("utf-8", "replace"))
            # The device answered, but a serial dispatch protocol does not
            # exist in this module — ``supported`` means dispatch-capable,
            # so the honest record is present-but-unsupported. Presence
            # evidence (identity, measured rate) rides in detail.
            return DeviceCapability(
                device_id=str(info.get("device_id", f"asic:{port}")),
                device_class="asic",
                measured_hashes_per_sec=float(info.get("measured_hashes_per_sec", 0.0)),
                supported=False,
                reason_if_unsupported=(
                    "serial device responded to the capability probe but no "
                    "serial dispatch protocol is implemented; supported "
                    "requires a dispatch-capable channel"
                ),
                detail={
                    "channel": "serial",
                    "port": port,
                    "responsive": True,
                    "serial": info.get("serial"),
                },
            )
        except Exception as exc:
            return DeviceCapability(
                device_id=f"asic:{port}",
                device_class="asic",
                measured_hashes_per_sec=0.0,
                supported=False,
                reason_if_unsupported=f"serial probe failed: {type(exc).__name__}: {exc}",
            )

    def _probe_pcie(self, node: str) -> DeviceCapability:
        if os.path.exists(node) and os.access(node, os.R_OK):
            return DeviceCapability(
                device_id=f"asic:pcie:{node}",
                device_class="asic",
                measured_hashes_per_sec=0.0,
                supported=False,
                reason_if_unsupported=(
                    "PCIe node present but no driver binding is implemented; "
                    "refusing to fabricate a protocol"
                ),
            )
        return DeviceCapability(
            device_id=f"asic:pcie:{node}",
            device_class="asic",
            measured_hashes_per_sec=0.0,
            supported=False,
            reason_if_unsupported=f"PCIe node {node} not present or unreadable",
        )

    def supports_kernel(self, kernel: str) -> bool:
        """Return only capabilities explicitly advertised by responsive hardware."""
        cap = self.capability()
        return bool(cap.supported and kernel in set(cap.detail.get("advertised_kernels", [])))

    # -- job binding -------------------------------------------------------

    def prepare(self, job_id: str, header80: bytes) -> None:
        """Bind the 80-byte block header a job's windows will grind."""
        if len(header80) != 80:
            raise ValueError(f"header must be 80 bytes, got {len(header80)}")
        self._jobs[str(job_id)] = bytes(header80)

    # -- NonceScheduler ------------------------------------------------------

    def dispatch(self, window: NonceWindow) -> DispatchHandle:
        cap = self.capability()
        if not cap.supported:
            raise ASICNotPresent(cap.reason_if_unsupported or "no ASIC is attached")
        if cap.detail.get("channel") != "network":
            raise ASICNotPresent(
                "ASIC reachable but the channel has no dispatch protocol "
                "implemented (serial/PCIe bindings are not present)"
            )
        header = self._jobs.get(window.job_id)
        if header is None:
            raise ASICNotPresent(
                f"job {window.job_id!r} has no bound header; call "
                "prepare(job_id, header80) first — the endpoint must hash "
                "the requested block header"
            )
        handle = DispatchHandle(
            handle_id=next_handle_id(),
            device_id=cap.device_id,
            window=window,
            dispatched_ns=time.monotonic_ns(),
        )
        try:
            host, _, port_s = self._endpoint.rpartition(":")
            sock = socket.create_connection((host, int(port_s)), timeout=_PROBE_TIMEOUT_S)
            sock.sendall(
                json.dumps(
                    {
                        "cmd": "dispatch",
                        "window": window.as_dict(),
                        "header_prefix_hex": header[:76].hex(),
                        "handle_id": handle.handle_id,
                    }
                ).encode()
                + b"\n"
            )
            self._pending[handle.handle_id] = {"handle": handle, "sock": sock}
        except Exception as exc:
            raise ASICNotPresent(f"dispatch channel failed: {exc}") from exc
        self._attest("dispatch", handle, reason="dispatched")
        return handle

    def outcome(self, handle: DispatchHandle) -> Optional[str]:
        """Terminal outcome kind recorded for a finished handle, if any."""
        for rec in reversed(self._records):
            if rec.handle_id == handle.handle_id:
                return rec.kind
        return None

    def poll(self, handle: DispatchHandle) -> Optional[Share]:
        state = self._pending.get(handle.handle_id)
        if state is None:
            return None
        sock = state["sock"]
        try:
            sock.settimeout(0.001)
            line = sock.makefile("rb").readline()
        except socket.timeout:
            return None
        except Exception as exc:
            # A channel error is a terminal failure, not exhaustion: the
            # window's nonces were NOT covered and the record must say so.
            self._attest("failed", handle, reason=f"asic_channel_error: {exc}")
            self._finished[handle.handle_id] = 0
            self._pending.pop(handle.handle_id, None)
            return None
        if not line:
            # Orderly close with no payload — same story: uncovered window.
            self._attest("failed", handle, reason="asic_channel_eof")
            self._finished[handle.handle_id] = 0
            self._pending.pop(handle.handle_id, None)
            return None
        try:
            msg = json.loads(line.decode("utf-8", "replace"))
        except Exception:
            return None
        if msg.get("type") == "share":
            nonce = int(msg["nonce"])
            tried = int(msg.get("nonces_tried", handle.window.span))
            share = Share(
                device_id=handle.device_id,
                job_id=handle.window.job_id,
                nonce=nonce,
                digest=bytes.fromhex(str(msg["digest"])),
                nonces_tried=tried,
                face=handle.window.face,
                # Contiguous traversal: the share's depth inside its window.
                probe_index=nonce - handle.window.base_nonce + 1,
            )
            self._attest("share", handle, nonces_tried=tried, found=True)
            self._finished[handle.handle_id] = tried
            self._pending.pop(handle.handle_id, None)
            return share
        if msg.get("type") == "exhausted":
            # An exhausted declaration is a coverage claim: it asserts the whole
            # assigned span was searched. The endpoint may report nonces_tried,
            # but it must never report LESS than the span we assigned -- that
            # would silently promote a partial sweep to full coverage in layer
            # accounting. Absent the field the wire contract is "I covered it
            # all", so it defaults to the span. A short declaration is recorded
            # at its true count and flagged, never rounded up.
            claimed = msg.get("nonces_tried")
            span = handle.window.span
            tried = span if claimed is None else int(claimed)
            if tried < span:
                self._attest(
                    "exhausted_partial",
                    handle,
                    nonces_tried=tried,
                    reason="window_exhausted_below_span",
                )
            else:
                self._attest("exhausted", handle, nonces_tried=tried, reason="window_exhausted")
            self._finished[handle.handle_id] = tried
            self._pending.pop(handle.handle_id, None)
        return None

    def cancel(self, handle: DispatchHandle, reason: str = "cancelled") -> None:
        state = self._pending.pop(handle.handle_id, None)
        if state is None:
            return
        # The wire reports no partial-progress counter; a cancelled
        # window's executed count is unknown, so it records zero — never
        # a fabricated mid-flight estimate.
        self._finished[handle.handle_id] = 0
        try:
            state["sock"].sendall(
                json.dumps({"cmd": "cancel", "handle_id": handle.handle_id}).encode() + b"\n"
            )
            state["sock"].close()
        except Exception:
            pass
        self._attest("cancelled", handle, reason=reason)

    def is_done(self, handle: DispatchHandle) -> bool:
        return handle.handle_id not in self._pending

    def hashed_count(self, handle: DispatchHandle) -> int:
        """Total hashes the channel reported for this handle so far."""
        return int(self._finished.get(handle.handle_id, 0))

    def attestation(self) -> List[ExecutionAttestation]:
        return list(self._records)

    def _attest(
        self,
        kind: str,
        handle: DispatchHandle,
        *,
        reason: str = "",
        nonces_tried: int = 0,
        found: bool = False,
    ) -> ExecutionAttestation:
        record = ExecutionAttestation(
            kind=kind,
            device_id=handle.device_id,
            device_class="asic",
            handle_id=handle.handle_id,
            window=handle.window,
            timestamp_ns=time.monotonic_ns(),
            nonces_tried=nonces_tried,
            found=found,
            reason=reason,
            detail={"module": "hyba.hybrid.asic_solver"},
        )
        self._records.append(record)
        self._registry.record(record)
        return record


__all__ = ["ASIC_HASH_KERNEL", "OPTIONAL_ASIC_KERNELS", "ASICSolver"]
