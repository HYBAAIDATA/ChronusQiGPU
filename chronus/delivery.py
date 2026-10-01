"""Chronus delivery contract.

Chronus has two first-class delivery modes:

* ``embedded`` — Chronus executes inside the customer's/container environment
  and binds directly to a local GPU/accelerator surface.
* ``cloud_instance`` — the customer uses a HYBA Chronus instance deployed into
  their chosen cloud and reached through the existing verified remote protocol.

Neither mode is a fallback for the other.  Selection is explicit and this
module never silently moves work between execution locations.

This surface is intentionally descriptive/provisioning-only.  It does not
replace, cap, throttle, or reroute any existing Chronus execution path.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Iterable, Optional, Sequence, Tuple


class DeliveryMode(str, Enum):
    EMBEDDED = "embedded"
    CLOUD_INSTANCE = "cloud_instance"


@dataclass(frozen=True)
class ChronusDelivery:
    mode: DeliveryMode
    available: bool
    execution_location: str
    transport: str
    endpoint: str
    devices: Tuple[Dict[str, Any], ...]
    capabilities: Tuple[str, ...]
    reason: str
    evidence: Tuple[str, ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "product": "Chronus",
            "delivery_mode": self.mode.value,
            "available": self.available,
            "execution_location": self.execution_location,
            "transport": self.transport,
            "endpoint": self.endpoint,
            "devices": [dict(device) for device in self.devices],
            "capabilities": list(self.capabilities),
            "reason": self.reason,
            "evidence": list(self.evidence),
        }


def _tuple_capabilities(values: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def probe_embedded(
    *,
    tensor_probe: Optional[Callable[[], Any]] = None,
) -> ChronusDelivery:
    """Describe an embedded/container Chronus binding.

    The existing tensor probe is used because it only reports available after
    a GPU/accelerator OpenCL device has been selected.  No CPU fallback is
    introduced here.
    """
    if tensor_probe is None:
        from .tensor_compute import probe as tensor_probe

    probe = tensor_probe()
    record = probe.as_dict() if hasattr(probe, "as_dict") else dict(probe)
    available = bool(record.get("available"))
    operations = tuple(record.get("operations") or ())
    dtypes = tuple(record.get("dtypes") or ())
    capabilities = [f"tensor:{operation}" for operation in operations]
    capabilities.extend(f"dtype:{dtype}" for dtype in dtypes)
    device_id = str(record.get("device_id", "") or "")
    device = {
        "device_id": device_id,
        "name": str(record.get("device_name", "") or ""),
        "platform": str(record.get("platform_name", "") or ""),
        "backend": "chronus-opencl" if available else "",
    }
    reason = str(record.get("reason", "") or "")
    return ChronusDelivery(
        mode=DeliveryMode.EMBEDDED,
        available=available,
        execution_location="customer_container",
        transport="in_process",
        endpoint="",
        devices=(device,) if available else (),
        capabilities=_tuple_capabilities(capabilities),
        reason=reason,
        evidence=("chronus.tensor_compute.probe",),
    )


def probe_cloud_instance(
    *,
    endpoints: Optional[Sequence[str]] = None,
    remote_probe: Optional[Callable[..., Any]] = None,
) -> ChronusDelivery:
    """Describe a Chronus instance deployed in the customer's chosen cloud.

    The existing remote protocol remains the authority.  It verifies endpoint
    reachability and imports only measured GPU/Chronus/accelerator devices.
    """
    if remote_probe is None:
        from .mla1517.remote_gpu import probe_first_reachable as remote_probe

    selected = None if endpoints is None else list(endpoints)
    client, devices, reason = remote_probe(selected)
    if client is None or not devices:
        return ChronusDelivery(
            mode=DeliveryMode.CLOUD_INSTANCE,
            available=False,
            execution_location="hyba_instance_in_customer_cloud",
            transport="remote_opencl_v1",
            endpoint="",
            devices=(),
            capabilities=(),
            reason=str(reason or "no reachable Chronus cloud instance"),
            evidence=("chronus.mla1517.remote_gpu.probe_first_reachable",),
        )

    endpoint = str(getattr(client, "endpoint", "") or "")
    records = []
    capabilities = set()
    for device in devices:
        record = device.as_dict() if hasattr(device, "as_dict") else dict(device)
        records.append(dict(record))
        caps = record.get("capabilities") or {}
        if isinstance(caps, dict):
            capabilities.update(str(name) for name, enabled in caps.items() if enabled)

    # The protocol's currently implemented executable surfaces are evidence,
    # not assumptions.  Health is queried when supported so future agents may
    # advertise additional endpoints without changing this contract.
    try:
        health = client.health()
    except Exception:
        health = {}
    for name in health.get("endpoints", ()) if isinstance(health, dict) else ():
        capabilities.add(f"remote:{name}")

    return ChronusDelivery(
        mode=DeliveryMode.CLOUD_INSTANCE,
        available=True,
        execution_location="hyba_instance_in_customer_cloud",
        transport="remote_opencl_v1",
        endpoint=endpoint,
        devices=tuple(records),
        capabilities=_tuple_capabilities(capabilities),
        reason=str(reason or ""),
        evidence=(
            "chronus.mla1517.remote_gpu.probe_first_reachable",
            "remote_opencl_v1:/v1/devices",
        ),
    )


def probe_delivery(
    mode: DeliveryMode | str,
    *,
    endpoints: Optional[Sequence[str]] = None,
    tensor_probe: Optional[Callable[[], Any]] = None,
    remote_probe: Optional[Callable[..., Any]] = None,
) -> ChronusDelivery:
    """Probe exactly the requested delivery mode; never cross-fallback."""
    selected = DeliveryMode(mode)
    if selected is DeliveryMode.EMBEDDED:
        return probe_embedded(tensor_probe=tensor_probe)
    return probe_cloud_instance(endpoints=endpoints, remote_probe=remote_probe)


__all__ = [
    "ChronusDelivery",
    "DeliveryMode",
    "probe_cloud_instance",
    "probe_delivery",
    "probe_embedded",
]
