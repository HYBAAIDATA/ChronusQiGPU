"""ASICSolver — NonceScheduler over a real ASIC protocol endpoint.

This module is a *protocol implementation*, not a device model. It speaks
to physical hardware through exactly three real channels:

- **Network bridge** (``HYBRID_ASIC_ENDPOINT=host:port``): a TCP endpoint
  running a stratum-to-device bridge or vendor control plane. Windows are
  sent as JSON lines; shares return the same way.
- **USB serial** (``HYBRID_ASIC_SERIAL=/dev/ttyUSBn`` or ``COMn``): a
  cgminer-style serial control channel, used only when ``pyserial`` is
  installed and the port opens.
- **PCIe** (``HYBRID_ASIC_PCIE=/dev/node``): a vendor driver node; only
  presence + readability is probed — dispatch over a vendor PCIe protocol
  requires a driver binding this module does not invent.

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


class ASICSolver:
    """Protocol solver for an attached ASIC. Real hardware or nothing."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        serial_port: Optional[str] = None,
        pcie_node: Optional[str] = None,
    ) -> None:
        self._endpoint = endpoint or os.environ.get("HYBRID_ASIC_ENDPOINT", "").strip() or None
        self._serial_port = (
            serial_port or os.environ.get("HYBRID_ASIC_SERIAL", "").strip() or None
        )
        self._pcie_node = (
            pcie_node or os.environ.get("HYBRID_ASIC_PCIE", "").strip() or None
        )
        self._capability: Optional[DeviceCapability] = None
        self._records: List[ExecutionAttestation] = []
        self._registry = AttestationRegistry.get()
        self._pending: Dict[int, Dict[str, Any]] = {}

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

        if self._endpoint:
            cap = self._probe_network(self._endpoint)
            if cap.supported:
                self._capability = cap
                return cap
        if self._serial_port:
            cap = self._probe_serial(self._serial_port)
            if cap.supported:
                self._capability = cap
                return cap
        if self._pcie_node:
            cap = self._probe_pcie(self._pcie_node)
            if cap.supported:
                self._capability = cap
                return cap

        self._capability = DeviceCapability(
            device_id="asic:unresponsive",
            device_class="asic",
            measured_hashes_per_sec=0.0,
            supported=False,
            reason_if_unsupported=(
                f"ASIC probe failed on all configured channels: {configured}"
            ),
            detail={"configured_channels": configured},
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
            return DeviceCapability(
                device_id=str(info.get("device_id", f"asic:{port}")),
                device_class="asic",
                measured_hashes_per_sec=float(info.get("measured_hashes_per_sec", 0.0)),
                supported=True,
                detail={"channel": "serial", "port": port, "serial": info.get("serial")},
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

    # -- NonceScheduler ------------------------------------------------------

    def dispatch(self, window: NonceWindow) -> DispatchHandle:
        cap = self.capability()
        if not cap.supported:
            raise ASICNotPresent(
                cap.reason_if_unsupported or "no ASIC is attached"
            )
        if cap.detail.get("channel") != "network":
            raise ASICNotPresent(
                "ASIC reachable but the channel has no dispatch protocol "
                "implemented (serial/PCIe bindings are not present)"
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
                json.dumps({"cmd": "dispatch", "window": window.as_dict(),
                            "handle_id": handle.handle_id}).encode() + b"\n"
            )
            self._pending[handle.handle_id] = {"handle": handle, "sock": sock}
        except Exception as exc:
            raise ASICNotPresent(f"dispatch channel failed: {exc}") from exc
        self._attest("dispatch", handle, reason="dispatched")
        return handle

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
        except Exception:
            self._pending.pop(handle.handle_id, None)
            return None
        if not line:
            return None
        try:
            msg = json.loads(line.decode("utf-8", "replace"))
        except Exception:
            return None
        if msg.get("type") == "share":
            share = Share(
                device_id=handle.device_id,
                job_id=handle.window.job_id,
                nonce=int(msg["nonce"]),
                digest=bytes.fromhex(str(msg["digest"])),
                nonces_tried=int(msg.get("nonces_tried", handle.window.span)),
                face=handle.window.face,
            )
            self._attest("share", handle, nonces_tried=share.nonces_tried, found=True)
            self._pending.pop(handle.handle_id, None)
            return share
        if msg.get("type") == "exhausted":
            self._attest("exhausted", handle, nonces_tried=handle.window.span,
                         reason="window_exhausted")
            self._pending.pop(handle.handle_id, None)
        return None

    def cancel(self, handle: DispatchHandle, reason: str = "cancelled") -> None:
        state = self._pending.pop(handle.handle_id, None)
        if state is None:
            return
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

    def attestation(self) -> List[ExecutionAttestation]:
        return list(self._records)

    def _attest(self, kind: str, handle: DispatchHandle, *, reason: str = "",
                nonces_tried: int = 0, found: bool = False) -> ExecutionAttestation:
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


__all__ = ["ASICSolver"]
