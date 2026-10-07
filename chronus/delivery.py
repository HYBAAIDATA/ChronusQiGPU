"""Chronus delivery contract.

Delivery modes use the canonical Virtual iGPU vocabulary
(:class:`chronus.virtual_igpu.abi.DeliveryMode`):

* ``embedded`` — Chronus executes inside the customer's/container environment
  as a first-class standalone software runtime, and may additionally bind to a
  local GPU/accelerator surface when one is available and selected.
* ``remote_service`` — the customer uses a HYBA Chronus instance deployed into
  their chosen cloud and reached through the existing verified remote protocol.
* ``local_sidecar`` — loopback daemon; not probed by this descriptive module.

No mode is a fallback for another. Selection is explicit and this module never
silently moves work between execution locations.

This surface is intentionally descriptive/provisioning-only. It does not
replace, cap, throttle, or reroute any existing Chronus execution path.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional, Sequence, Tuple

from .virtual_igpu.abi import DeliveryMode, ExecutionPolicy, ProductMode


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
    software_mode_available: bool = False
    accelerator_mode_available: bool = False
    product_modes: Tuple[str, ...] = ()
    # Compatibility: backend-selection policy vocabulary retained for existing callers.
    execution_modes: Tuple[str, ...] = ()
    accelerator_reason: str = ""

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
            "software_mode_available": self.software_mode_available,
            "accelerator_mode_available": self.accelerator_mode_available,
            "product_modes": list(self.product_modes),
            "execution_modes": list(self.execution_modes),
            "accelerator_reason": self.accelerator_reason,
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
    include_software: bool = True,
) -> ChronusDelivery:
    """Describe an embedded/container Chronus binding across local substrates.

    Chronus identity is independent of OpenCL and independent of the presence
    of a physical GPU. The standalone software runtime is a product mode in its
    own right, not a disguised fallback. Physical OpenCL, CUDA and Metal paths
    are probed separately and add the accelerator-enhanced mode only when they
    are actually available.

    ``tensor_probe`` remains a compatibility/test injection point. When it is
    supplied without ``native_probes``, only that injected OpenCL-style probe
    is evaluated, preserving the historical caller contract.
    """
    single_injected_probe = tensor_probe is not None and native_probes is None
    if single_injected_probe:
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
    software_available = False

    if include_software:
        from .virtual_igpu.adapters import CPUEmulatorAdapter

        software = CPUEmulatorAdapter()
        attestation = software.probe()
        manifest = software.capabilities()
        software_available = bool(attestation.available and manifest.available)
        evidence.append("chronus.virtual_igpu.adapters.CPUEmulatorAdapter")
        if software_available:
            capabilities.add(f"product_mode:{ProductMode.NATIVE_CHRONUS_GPU.value}")
            capabilities.update(
                f"software:{operation}" for operation in manifest.operations
            )
    for backend_name, probe_fn, evidence_name in probes:
        evidence.append(evidence_name)
        try:
            record = _probe_record(probe_fn)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            unavailable_reasons.append(
                detail if single_injected_probe else f"{backend_name}: {detail}"
            )
            continue
        if not bool(record.get("available")):
            detail = str(record.get("reason", "") or "runtime unavailable")
            unavailable_reasons.append(
                detail if single_injected_probe else f"{backend_name}: {detail}"
            )
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

    accelerator_available = bool(devices)
    if accelerator_available:
        capabilities.add(f"product_mode:{ProductMode.HOST_GPU_AUGMENTATION.value}")
    available = software_available or accelerator_available
    reason = "" if available else "; ".join(unavailable_reasons)
    accelerator_reason = (
        ""
        if accelerator_available
        else ("; ".join(unavailable_reasons) or "no physical accelerator observed")
    )
    product_modes = []
    execution_modes = []
    if software_available:
        product_modes.append(ProductMode.NATIVE_CHRONUS_GPU.value)
        execution_modes.append(ExecutionPolicy.STANDALONE_SOFTWARE.value)
    if accelerator_available:
        product_modes.append(ProductMode.HOST_GPU_AUGMENTATION.value)
        execution_modes.append(ExecutionPolicy.PREFERRED_ACCELERATOR.value)
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
        software_mode_available=software_available,
        accelerator_mode_available=accelerator_available,
        product_modes=tuple(product_modes),
        execution_modes=tuple(execution_modes),
        accelerator_reason=accelerator_reason,
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
    from .mla1517.remote_gpu import PROTOCOL_VERSION

    if remote_probe is None:
        from .mla1517.remote_gpu import probe_first_reachable as remote_probe

    selected = None if endpoints is None else list(endpoints)
    client, devices, reason = remote_probe(selected)
    if client is None or not devices:
        return ChronusDelivery(
            mode=DeliveryMode.REMOTE_SERVICE,
            available=False,
            execution_location="hyba_instance_in_customer_cloud",
            transport=PROTOCOL_VERSION,
            endpoint="",
            devices=(),
            capabilities=(),
            reason=str(reason or "no reachable Chronus cloud instance"),
            evidence=("chronus.mla1517.remote_gpu.probe_first_reachable",),
            software_mode_available=False,
            accelerator_mode_available=False,
            product_modes=(),
            execution_modes=(),
            accelerator_reason=str(reason or "no reachable Chronus cloud instance"),
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
        mode=DeliveryMode.REMOTE_SERVICE,
        available=True,
        execution_location="hyba_instance_in_customer_cloud",
        transport=PROTOCOL_VERSION,
        endpoint=endpoint,
        devices=tuple(records),
        capabilities=_tuple_capabilities(capabilities),
        reason=str(reason or ""),
        evidence=(
            "chronus.mla1517.remote_gpu.probe_first_reachable",
            f"{PROTOCOL_VERSION}:/v1/devices",
        ),
        software_mode_available=False,
        accelerator_mode_available=True,
        product_modes=(ProductMode.HOST_GPU_AUGMENTATION.value,),
        execution_modes=(ExecutionPolicy.PREFERRED_ACCELERATOR.value,),
        accelerator_reason="",
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
    if selected is DeliveryMode.LOCAL_SIDECAR:
        raise ValueError("local_sidecar delivery is not probed by chronus.delivery")
    if selected is DeliveryMode.EMBEDDED:
        return probe_embedded(
            tensor_probe=tensor_probe,
            native_probes=native_probes,
            include_software=True,
        )
    return probe_cloud_instance(endpoints=endpoints, remote_probe=remote_probe)


__all__ = [
    "ChronusDelivery",
    "DeliveryMode",
    "probe_cloud_instance",
    "probe_delivery",
    "probe_embedded",
]
