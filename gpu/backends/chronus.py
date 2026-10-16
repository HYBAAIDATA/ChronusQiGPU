"""Compatibility facade for the canonical Chronus execution fabric.

This module predates the igpu -> chronus consolidation. Its old export map
named an igpu-era API (``ChronusConfig``, ``ChronusEngine``, ``Metrics``)
that never existed in :mod:`chronus`, so every attribute access raised
``AttributeError``. The facade now maps the same intent onto the real
surface:

- ``DeviceInfo`` -> :class:`chronus.detect.DetectedDevice`
- ``ChronusEngine`` -> :class:`chronus.engine.ChronusOpenCLEngine`
- ``Metrics`` -> :class:`chronus.telemetry.ChronusTelemetry`
- ``backend_available`` -> executed canonical software-adapter probe

There is no ``ChronusConfig`` in the canonical package, so the old name is
dropped rather than re-pointed at an unrelated class.

A physical device is an augmentation substrate, not a requirement: CHRONUS
executes its software fabric with no device present. ``backend_available``
therefore reports a detection fact, never a product precondition.
"""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "DeviceInfo": ("chronus.detect", "DetectedDevice"),
    "DetectionReport": ("chronus.detect", "DetectionReport"),
    "detect_all": ("chronus.detect", "detect_all"),
    "Chronus": ("chronus.device", "Chronus"),
    "ChronusEngine": ("chronus.engine", "ChronusOpenCLEngine"),
    "ChronusEngineUnavailable": ("chronus.engine", "ChronusOpenCLUnavailable"),
    "ChronusFabric": ("chronus.fabric", "ChronusFabric"),
    "Metrics": ("chronus.telemetry", "ChronusTelemetry"),
}

__all__ = sorted([*_EXPORTS, "backend_available", "physical_substrate_available"])


def _census() -> Any:
    try:
        return import_module("chronus.detect").detect_all()
    except Exception:
        return None


def backend_available() -> bool:
    """True only after the canonical independent software backend executes.

    Contract/spec presence is not execution evidence.  This probe runs the
    no-side-effect PROBE workload directly on ChronusSoftwareFabricAdapter;
    import, construction, validation, or execution failure returns False.
    Physical accelerator availability is reported separately.
    """
    try:
        adapters = import_module("chronus.virtual_igpu.adapters")
        abi = import_module("chronus.virtual_igpu.abi")
        adapter = adapters.ChronusSoftwareFabricAdapter()
        workload = abi.Workload(
            id="gpu-backends-chronus-availability",
            kind=abi.WorkloadKind.PROBE,
            tenant="compatibility-probe",
            execution_policy=abi.ExecutionPolicy.STANDALONE_SOFTWARE.value,
            allow_software_fallback=True,
        )
        result = adapter.execute(workload)
        return bool(
            result.status == "ok"
            and result.actual_adapter_id == adapter.id
            and result.output.get("probe", {}).get("available") is True
        )
    except Exception:
        return False


def physical_substrate_available() -> bool:
    """True when a device other than Chronus's virtual iGPU is detected.

    The virtual iGPU reports backend ``"chronus"``; CUDA/Metal/OpenCL tiers
    report physical hardware.
    """
    report = _census()
    if report is None:
        return False
    return any(d.backend != "chronus" for d in report.devices)


def __getattr__(name: str) -> Any:
    """Resolve the canonical Chronus API only when an attribute is requested."""
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value
