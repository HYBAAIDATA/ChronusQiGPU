"""Chronus delivery contract.

Chronus has two first-class delivery modes:

* ``embedded`` — Chronus executes inside the customer's/container environment
  and binds directly to a local GPU/accelerator surface.
* ``cloud_instance`` — the customer uses a HYBA Chronus instance deployed into
  their chosen cloud and reached through the existing verified remote protocol.

Neither mode is a fallback for the other. Selection is explicit and this
module never silently moves work between execution locations.

This surface is intentionally descriptive/provisioning-only. It does not
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


def _probe_record(probe_fn: Callable[[], Any]) -> Dict[str, Any]:
    probe = probe_fn()
    return probe.as_dict() if hasattr(probe, "as_dict") else dict(probe)


def probe_embedded(
    *,
    tensor_probe: Optional[Callable[[], Any]] = None,
    native_probes: Optional[Sequence[Tuple[str, Callable[[], Any], str]]] = None,
) -> ChronusDelivery:
    """Describe an embedded/container Chronus binding across local substrates.

    Chronus identity is independent of OpenCL. By default the embedded probe
    observes OpenCL, CUDA, and Metal execution paths and reports every physical
    path that is actually available. No backend is silently substituted for
    another and no CPU fallback is introduced here.

    ``tensor_probe`` remains a compatibility/test injection point. When it is
    supplied without ``native_probes``, only that injected OpenCL-style probe
    is evaluated, preserving the historical caller contract.
    """
    if tensor_probe is not None and native_probes is None:
        probes: Sequence[Tuple[str, Callable[[], Any], str]] = (
            ("chronus-opencl", tensor_probe, "chronus.tensor_compute.probe"),
        )
    elif native_probes is not None:
        probes = native_probes
    else:
        from .native_tensor import probe_cuda, probe_metal
        from .tensor_compute import probe as opencl_probe

        probes = (
            ("chronus-opencl", opencl_probe, "chronus.tensor_compute.probe"),
            ("chronus-cuda", probe_cuda, "chronus.native_tensor.probe_cuda"),
            ("chronus-metal", probe_metal, "chronus.native_tensor.probe_metal"),
        )

    devices = []
    capabilities = set()
    evidence = []
    unavailable_reasons = []
    for backend_name, probe_fn, evidence_name in probes:
        evidence.append(evidence_name)
        try:
            record = _probe_record(probe_fn)
        except Exception as exc:
            unavailable_reasons.append(
                f"{backend_name}: {type(exc).__name__}: {exc}"
            )
            continue
        if not bool(record.get("available")):
            reason = str(record.get("reason", "") or "runtime unavailable")
            unavailable_reasons.append(f"{backend_name}: {reason}")
            continue
        operations = tuple(record.get("operations") or ())
        dtypes = tuple(record.get("dtypes") or ())
        capabilities.update(f"tensor:{operation}" for operation in operations)
        capabilities.update(f"dtype:{dtype}" for dtype in dtypes)
        capabilities.add(f"backend:{backend_name}")
        devices.append(
            {
                "device_id": str(record.get("device_id", "") or ""),
                "name": str(record.get("device_name", "") or ""),
                "platform": str(record.get("platform_name", "") or ""),
                "backend": backend_name,
            }
        )

    available = bool(devices)
    reason = "" if available else "; ".join(unavailable_reasons)
    return ChronusDelivery(
        mode=DeliveryMode.EMBEDDED,
        available=available,
        execution_location="customer_container",
        transport="in_process",
        endpoint="",
        devices=tuple(devices),
        capabilities=_tuple_capabilities(capabilities),
        reason=reason,
        evidence=tuple(evidence),
    )


def probe_cloud_instance(
    *,
    endpoints: Optional[Sequence[str]] = None,
    remote_probe: Optional[Callable[..., Any]] = None,
) -> ChronusDelivery:
    """Describe a Chronus instance deployed in the customer's chosen cloud.

    The existing remote protocol remains the authority. It verifies endpoint
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
    # not assumptions. Health is queried when supported so future agents may
    # advertise additional endpoints without changing this contract.
    try:
        health = client.health()
    except Exception:
        health = {}
    advertised = health.get("endpoints", ()) if isinstance(health, dict) else ()
    for name in advertised:
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
    native_probes: Optional[Sequence[Tuple[str, Callable[[], Any], str]]] = None,
    remote_probe: Optional[Callable[..., Any]] = None,
) -> ChronusDelivery:
    """Probe exactly the requested delivery mode; never cross-fallback."""
    selected = DeliveryMode(mode)
    if selected is DeliveryMode.EMBEDDED:
        return probe_embedded(
            tensor_probe=tensor_probe,
            native_probes=native_probes,
        )
    return probe_cloud_instance(endpoints=endpoints, remote_probe=remote_probe)


__all__ = [
    "ChronusDelivery",
    "DeliveryMode",
    "probe_cloud_instance",
    "probe_delivery",
    "probe_embedded",
]
