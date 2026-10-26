"""Historical versioned Chronus / Theseus / Ovid composition.

The enterprise profile assigns custody to Theseus and transformation to Ovid.
The historical Ovid-root store is a separate, explicit legacy profile; it is
never dual-written or silently migrated into enterprise custody. Chronus is
optional execution evidence, not a storage-correctness authority.

New GPIU capacity uses ``chronus.triad.ChronusTriad`` with OVID enterprise
authority and rebuildable THESEUS discovery. These historical profiles keep
their stored formats and call contracts; opening them does not migrate data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .ovid import CLAIM_BOUNDARY as OVID_CLAIM
from .ovid import Ovid, open_ovid
from .ovid_authority import OvidAuthority, OvidObject, open_ovid_authority
from .theseus import CLAIM_BOUNDARY as THESEUS_CLAIM
from .theseus import Theseus, TheseusRecord, open_theseus
from .theseus_projection import TheseusProjection, open_theseus_projection

TRIAD_ID = "chronus.theseus.ovid"
ONE_IGPU_DEVICE_ID = "chronos_igpu"
ONE_IGPU_DEVICE_COUNT = 1
THESEUS_CUSTODY_PROFILE = "theseus-custody/v1"
LEGACY_OVID_PROFILE = "legacy-ovid-root/v1"
TRIAD_CLAIM_BOUNDARY = (
    "Enterprise composition: Theseus owns custody, Ovid owns transformation, "
    "and Chronus owns execution evidence. The legacy Ovid-root profile is "
    "explicitly separate. No automatic storage migration, physical execution, "
    "unbounded compute or hash-preimage claim is made; this implementation does not make an unbounded compute or hash-preimage claim."
)


@dataclass
class Triad:
    """Production façade over Chronus + Theseus + Ovid."""

    theseus: Theseus
    ovid: Ovid
    chronus_device: Any = None
    triad_id: str = TRIAD_ID
    ovid_authority: Optional[OvidAuthority] = None
    theseus_projection: Optional[TheseusProjection] = None
    _chronus_error: Optional[str] = None
    _chronus_measured: bool = False
    storage_profile: str = THESEUS_CUSTODY_PROFILE

    def __post_init__(self) -> None:
        if self.storage_profile not in (THESEUS_CUSTODY_PROFILE, LEGACY_OVID_PROFILE):
            raise ValueError("unknown storage authority profile")
        if self.storage_profile == THESEUS_CUSTODY_PROFILE:
            if self.ovid_authority is not None or self.theseus_projection is not None:
                raise ValueError("enterprise custody cannot bind a legacy Ovid root")
        elif self.ovid_authority is None or self.theseus_projection is None:
            raise ValueError("legacy profile requires its Ovid root and projection")

    def _require_enterprise(self) -> None:
        if self.storage_profile != THESEUS_CUSTODY_PROFILE:
            raise RuntimeError(
                "legacy Ovid profile requires explicit ovid_put/ovid_get"
            )

    @property
    def claim_boundary(self) -> str:
        return TRIAD_CLAIM_BOUNDARY

    def put(self, payload: bytes, **kwargs: Any) -> TheseusRecord:
        self._require_enterprise()
        return self.theseus.put(payload, **kwargs)

    def get(self, uid: str) -> bytes:
        self._require_enterprise()
        return self.theseus.get(uid)

    def ovid_put(self, payload: bytes, **kwargs: Any) -> OvidObject:
        if self.ovid_authority is None:
            raise RuntimeError("OVID authority root is not bound")
        obj = self.ovid_authority.put(payload, **kwargs)
        if self.theseus_projection is not None:
            self.theseus_projection.rebuild()
        return obj

    def ovid_get(self, object_id: str) -> bytes:
        if self.ovid_authority is None:
            raise RuntimeError("OVID authority root is not bound")
        return self.ovid_authority.get_bytes(object_id)

    def rebuild_theseus(self) -> str:
        if self.theseus_projection is None:
            raise RuntimeError("THESEUS projection is not bound")
        return self.theseus_projection.rebuild()

    def delete_theseus_projection(self) -> None:
        if self.theseus_projection is None:
            raise RuntimeError("THESEUS projection is not bound")
        self.theseus_projection.delete()

    def fold(self, payload: bytes):
        return self.ovid.metamorphose(payload)

    def materialise(self, form) -> bytes:
        return self.ovid.materialise(form)

    def verify(self) -> bool:
        if self.storage_profile == LEGACY_OVID_PROFILE:
            return self.ovid_authority is not None and self.ovid_authority.verify()
        return self.theseus.verify()

    def geodesic(self):
        self._require_enterprise()
        return self.theseus.geodesic()

    def health(self) -> Dict[str, Any]:
        t_health = self.theseus.health()
        o_health = self.ovid.health()
        legacy_health = (
            self.ovid_authority.health() if self.ovid_authority is not None else None
        )
        storage_ok = self.verify()
        disk_bound = (
            self.theseus.durable_dir is not None
            if self.storage_profile == THESEUS_CUSTODY_PROFILE
            else True
        )
        if self.chronus_device is not None:
            device_count = int(
                getattr(self.chronus_device, "device_count", ONE_IGPU_DEVICE_COUNT)
            )
            measured = bool(self._chronus_measured)
            c_health: Dict[str, Any] = {
                "owner": "chronus",
                "status": (
                    "ok" if measured and device_count == 1 else "bound_unmeasured"
                ),
                "device_id": getattr(
                    self.chronus_device, "device_id", ONE_IGPU_DEVICE_ID
                ),
                "bound": True,
                "measured_dispatch": measured,
                "device_count": device_count,
                "one_igpu": device_count == 1,
            }
            boundary = getattr(self.chronus_device, "claim_boundary", None)
            if boundary is None:
                try:
                    from chronus.device import CLAIM_BOUNDARY as CB

                    boundary = CB
                except Exception:
                    boundary = None
            if boundary:
                c_health["claim_boundary"] = boundary
        else:
            c_health = {
                "owner": "chronus",
                "status": "unbound",
                "bound": False,
                "measured_dispatch": False,
                "device_count": 0,
                "one_igpu": True,
                "reason": self._chronus_error or "chronus not opened",
            }
        t_ok = storage_ok
        o_ok = o_health.get("status") == "ok"
        if t_ok and o_ok and not disk_bound:
            overall = "memory_only"
        elif t_ok and o_ok and c_health.get("status") == "ok":
            overall = "ok"
        elif t_ok and o_ok:
            overall = "storage_ready" if disk_bound else "memory_only"
        elif t_ok or o_ok:
            overall = "degraded"
        else:
            overall = "unready"
        projection_health = (
            self.theseus_projection.health()
            if self.theseus_projection is not None
            else None
        )
        return {
            "triad": self.triad_id,
            "status": overall,
            "production_surface": True,
            "production_qualified": False,
            "storage_profile": self.storage_profile,
            "custody": {
                "component": (
                    "aethel.theseus.Theseus"
                    if self.storage_profile == THESEUS_CUSTODY_PROFILE
                    else "aethel.ovid_authority.OvidAuthority"
                ),
                "authority": (
                    "theseus"
                    if self.storage_profile == THESEUS_CUSTODY_PROFILE
                    else "legacy-ovid-root"
                ),
                "disk_bound": disk_bound,
                "integrity_verified": storage_ok,
                "schema": (
                    "theseus_index.json"
                    if self.storage_profile == THESEUS_CUSTODY_PROFILE
                    else "ovid-authority/v1"
                ),
            },
            "claim_boundary": TRIAD_CLAIM_BOUNDARY,
            "one_igpu": {
                "required": True,
                "device_id": ONE_IGPU_DEVICE_ID,
                "device_count": c_health.get("device_count", 0),
            },
            "owners": {
                "chronus": c_health,
                "theseus": t_health,
                "ovid": o_health,
                "theseus_projection": projection_health,
                "legacy_ovid_root": legacy_health,
            },
            "theseus_claim": THESEUS_CLAIM,
            "ovid_claim": OVID_CLAIM,
        }

    def metrics(self) -> Dict[str, Any]:
        return {
            "triad": self.triad_id,
            "theseus": self.theseus.metrics(),
            "ovid": self.ovid.metrics(),
        }

    def snapshot(self, directory: str) -> Dict[str, Any]:
        self._require_enterprise()
        return self.theseus.snapshot(directory)


def open_triad(
    *,
    durable: bool = True,
    durable_dir: str | Path | None = None,
    storage_profile: str = THESEUS_CUSTODY_PROFILE,
    bind_chronus: bool = True,
    ovid_root: str | Path | None = None,
    theseus_projection_root: str | Path | None = None,
) -> Triad:
    """Open a named authority profile without migrating or dual-writing stores.

    ``durable=True`` without ``durable_dir`` remains memory-only for backwards
    compatibility and is reported as such. Use a directory for restart custody.
    Existing Ovid-root callers must explicitly select LEGACY_OVID_PROFILE.
    """
    if storage_profile not in (THESEUS_CUSTODY_PROFILE, LEGACY_OVID_PROFILE):
        raise ValueError("unknown storage authority profile")
    if storage_profile == THESEUS_CUSTODY_PROFILE:
        if ovid_root is not None or theseus_projection_root is not None:
            raise ValueError(
                "legacy roots require explicit legacy-ovid-root/v1 profile"
            )
    elif ovid_root is None or durable_dir is not None:
        raise ValueError(
            "legacy profile needs ovid_root and cannot bind enterprise custody"
        )
    ovid = open_ovid()
    theseus = open_theseus(durable=durable, durable_dir=durable_dir, ovid=ovid)
    authority = None
    projection = None
    if ovid_root is not None:
        authority = open_ovid_authority(ovid_root, ovid=ovid)
        proj_root = theseus_projection_root
        if proj_root is None:
            proj_root = Path(ovid_root).parent / "theseus_projection"
        projection = open_theseus_projection(proj_root, authority)
    chronus_device = None
    chronus_error = None
    chronus_measured = False
    if bind_chronus:
        try:
            from chronus.one_igpu import OneIGPU

            chronus_device = OneIGPU(mode="standalone")
            setattr(chronus_device, "device_id", ONE_IGPU_DEVICE_ID)
            setattr(chronus_device, "device_count", ONE_IGPU_DEVICE_COUNT)
            result = chronus_device.dispatch([1, 2, 3])
            result.verify()
            chronus_measured = True
        except Exception as exc:
            chronus_error = f"{type(exc).__name__}: {exc}"
            if chronus_device is None:
                try:
                    from chronus import open_device

                    chronus_device = open_device()
                    setattr(chronus_device, "device_count", ONE_IGPU_DEVICE_COUNT)
                except Exception as inner:
                    chronus_error = f"{type(inner).__name__}: {inner}"
    triad = Triad(
        theseus=theseus,
        ovid=ovid,
        chronus_device=chronus_device,
        ovid_authority=authority,
        theseus_projection=projection,
        storage_profile=storage_profile,
    )
    triad._chronus_error = chronus_error
    triad._chronus_measured = chronus_measured
    return triad


__all__ = [
    "TRIAD_ID",
    "THESEUS_CUSTODY_PROFILE",
    "LEGACY_OVID_PROFILE",
    "TRIAD_CLAIM_BOUNDARY",
    "ONE_IGPU_DEVICE_ID",
    "ONE_IGPU_DEVICE_COUNT",
    "Triad",
    "open_triad",
]
