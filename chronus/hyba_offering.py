"""Chronus → HYBA GPU offering readiness.

Chronus is the product. HYBA consumes it as the accelerator / SuperGPU surface.
Mining is not the customer product; hasher plumbing may still appear as an
internal verification path.

This module prepares and reports the GPU stack for HYBA fleet use: capability
closure, virtual iGPU ABI, fabric composition, and Lucas scale envelopes sized
for the HYBA design target (1e19 H/s class work envelope — design target only,
never reported as measured throughput).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

# Design envelope for HYBA fleet prep (hashes/sec class). Integer only.
# Labelled design_target — not a measured claim, not release marketing copy.
HYBA_FLEET_DESIGN_TARGET_HS: int = 10**19  # 1e19 H/s class

ABI_VERSION = "virtual_igpu_v1"
OFFERING_ID = "chronus-hyba-gpu-v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class HybaGpuReadiness:
    """Structured readiness report for HYBA consumption of Chronus GPU."""

    ok: bool
    offering_id: str = OFFERING_ID
    product: str = "Chronus"
    consumer: str = "HYBA"
    mining_is_product: bool = False
    abi_version: str = ABI_VERSION
    design_target_hs: int = HYBA_FLEET_DESIGN_TARGET_HS
    design_target_kind: str = "design_envelope_not_measured"
    capabilities: dict[str, Any] = field(default_factory=dict)
    virtual_igpu: dict[str, Any] = field(default_factory=dict)
    fabric: dict[str, Any] = field(default_factory=dict)
    scale: dict[str, Any] = field(default_factory=dict)
    paradigm: dict[str, Any] = field(default_factory=dict)
    gaps: tuple[str, ...] = ()
    recorded_at: str = field(default_factory=_utc_now)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["gaps"] = list(self.gaps)
        return d


def _capability_closure() -> dict[str, Any]:
    from chronus.gpu_capabilities import gpu_capability_status

    status = gpu_capability_status()
    present = {k: bool(v.get("status")) for k, v in status.items()}
    return {
        "ok": all(present.values()) and len(present) >= 9,
        "surfaces": present,
        "count": len(present),
    }


def _virtual_igpu_probe(store_dir: str | None = None) -> dict[str, Any]:
    import tempfile
    from pathlib import Path

    from chronus.virtual_igpu.abi import ABI_VERSION as V, ExecutionPolicy, Workload, WorkloadKind
    from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
    from chronus.virtual_igpu.runtime import RuntimeDaemon

    root: Path
    tmp = None
    if store_dir is None:
        tmp = tempfile.TemporaryDirectory(prefix="hyba-gpu-")
        root = Path(tmp.name)
    else:
        root = Path(store_dir)
        root.mkdir(parents=True, exist_ok=True)

    try:
        daemon = RuntimeDaemon(adapters=[CPUEmulatorAdapter()], store_dir=root)
        daemon.attach()
        health = daemon.health()
        w = Workload(
            id="hyba-prep-store",
            kind=WorkloadKind.STORE,
            tenant="hyba",
            input={"payload_utf8": "hyba-offering"},
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
        )
        result = daemon.submit(w)
        trust_ok = (
            result.trust_class != "hardware_rooted"
            and result.hardware_rooted is False
            and result.status == "ok"
        )
        return {
            "ok": bool(health.get("running")) and trust_ok and V == ABI_VERSION,
            "abi_version": V,
            "state": health.get("state"),
            "adapters": health.get("adapters"),
            "sample_trust_class": result.trust_class,
            "sample_hardware_rooted": result.hardware_rooted,
        }
    finally:
        if tmp is not None:
            tmp.cleanup()


def _fabric_probe() -> dict[str, Any]:
    try:
        from hyba.inventory import ClusterInventory, DeviceInfo
        from hyba.virtual_gpu import SuperGPU
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    devices = [
        DeviceInfo(
            name="hyba-prep-cpu",
            vendor="HYBA",
            backend="cpu",
            type="cpu",
            compute_units=8,
            global_mem_mb=16384,
            capabilities=(("max_workgroup", 1),),
        ),
        DeviceInfo(
            name="hyba-prep-igpu",
            vendor="HYBA",
            backend="opencl",
            type="gpu",
            compute_units=32,
            global_mem_mb=8192,
            capabilities=(
                ("max_workgroup", 256),
                ("cgemv", True),
                ("tensor_op", True),
            ),
        ),
    ]
    inv = ClusterInventory(devices=list(devices), detected_at=0.0)
    fabric = SuperGPU.compose(inv) if hasattr(SuperGPU, "compose") else SuperGPU(inv)
    route = None
    try:
        route = fabric.route("cgemv", {"work_items": 4096})
    except Exception:
        try:
            route = fabric.route("tensor_op", {"work_items": 4096})
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": f"route_failed: {type(exc).__name__}: {exc}",
                "compute_units": int(getattr(fabric, "compute_units", 0) or 0),
                "devices": len(getattr(fabric, "devices", []) or []),
            }
    return {
        "ok": True,
        "mode": "prep_census",
        "compute_units": int(getattr(fabric, "compute_units", 0) or 0),
        "devices": len(getattr(fabric, "devices", []) or []),
        "capability_map": fabric.capability_map() if hasattr(fabric, "capability_map") else {},
        "sample_route": route.as_dict() if route is not None and hasattr(route, "as_dict") else None,
    }


def _scale_probe(physical_units: int = 80, ladder_index: int = 20) -> dict[str, Any]:
    from chronus.seam.scale import compute_effective_capacity, snap_work_items

    cap = compute_effective_capacity(physical_units, ladder_index=ladder_index)
    target = HYBA_FLEET_DESIGN_TARGET_HS
    ratio = max(1, int(cap.effective) // max(1, int(cap.physical))) if cap.physical else 1
    planned_physical = max(1, target // max(1, ratio)) if ratio else target
    return {
        "ok": True,
        "physical_units_sample": cap.physical,
        "ladder_index": cap.ladder_index,
        "lucas_L": cap.lucas_L,
        "effective_envelope": cap.effective,
        "work_items_snap_1m": snap_work_items(1_000_000),
        "design_target_hs": target,
        "design_target_kind": "design_envelope_not_measured",
        "planning_ratio_L": ratio,
        "planning_physical_units_at_rung": int(planned_physical),
        "note": cap.note,
    }


def _paradigm_probe() -> dict[str, Any]:
    try:
        from chronus.paradigm.thesis import THESIS_ID, assert_thesis_bounds, thesis_text

        rep = assert_thesis_bounds()
        return {
            "ok": bool(rep.get("ok")),
            "thesis_id": THESIS_ID,
            "sentence": thesis_text(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def prepare_hyba_gpu(
    *,
    store_dir: str | None = None,
    physical_units: int = 80,
    ladder_index: int = 20,
) -> HybaGpuReadiness:
    """Prepare and report Chronus GPU readiness for HYBA.

    Returns a structured report. ``ok`` is true when software surfaces required
    for HYBA consumption are green. Live device measurement remains a separate
    external gate and does not block software readiness.
    """
    caps = _capability_closure()
    vigpu = _virtual_igpu_probe(store_dir=store_dir)
    fabric = _fabric_probe()
    scale = _scale_probe(physical_units=physical_units, ladder_index=ladder_index)
    paradigm = _paradigm_probe()

    gaps: list[str] = []
    if not caps.get("ok"):
        gaps.append("gpu_capability_closure")
    if not vigpu.get("ok"):
        gaps.append("virtual_igpu_runtime")
    if not fabric.get("ok"):
        gaps.append("hyba_fabric_supergpu")
    if not scale.get("ok"):
        gaps.append("lucas_scale_contract")
    if not paradigm.get("ok"):
        gaps.append("paradigm_thesis")

    # Always-visible external gaps (not silent).
    gaps.extend(
        [
            "live_opencl_device_measurement",
            "hardware_rooted_attestation_keys",
        ]
    )

    software_ok = all(
        [
            bool(caps.get("ok")),
            bool(vigpu.get("ok")),
            bool(fabric.get("ok")),
            bool(scale.get("ok")),
            bool(paradigm.get("ok")),
        ]
    )

    return HybaGpuReadiness(
        ok=software_ok,
        capabilities=caps,
        virtual_igpu=vigpu,
        fabric=fabric,
        scale=scale,
        paradigm=paradigm,
        gaps=tuple(dict.fromkeys(gaps)),
    )


def prepare_hyba_gpu_dict(**kwargs: Any) -> dict[str, Any]:
    """Dict form of :func:`prepare_hyba_gpu` for JSON / CLI."""
    return prepare_hyba_gpu(**kwargs).as_dict()


def assert_hyba_gpu_software_ready(
    report: HybaGpuReadiness | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Raise if software readiness is not green (external device gaps allowed)."""
    rep = report if isinstance(report, HybaGpuReadiness) else None
    data = rep.as_dict() if rep is not None else (
        dict(report) if isinstance(report, Mapping) else prepare_hyba_gpu().as_dict()
    )
    external = {
        "live_opencl_device_measurement",
        "hardware_rooted_attestation_keys",
        "real_pool_ack_truth_class",
    }
    blocking = [g for g in data.get("gaps", ()) if g not in external]
    if not data.get("ok") or blocking:
        raise RuntimeError(
            f"HYBA GPU software readiness failed: gaps={blocking or data.get('gaps')}"
        )
    return data


__all__ = [
    "HYBA_FLEET_DESIGN_TARGET_HS",
    "OFFERING_ID",
    "HybaGpuReadiness",
    "prepare_hyba_gpu",
    "prepare_hyba_gpu_dict",
    "assert_hyba_gpu_software_ready",
]
