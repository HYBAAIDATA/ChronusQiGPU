"""Chronus · Theseus · Ovid — unified production triad façade.

Ownership (transfer notes + production review):
    OVID     — authoritative durable folded state
    THESEUS  — rebuildable query/index projection from OVID
    CHRONUS  — ONE iGPU execution and measured evidence only

Legacy Theseus.put/get remains for existing callers. New production paths
use ovid_put/ovid_get. Chronus bind is optional and cannot be a storage
correctness oracle.
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
TRIAD_CLAIM_BOUNDARY = (
    "Chronus·Theseus·Ovid is HYBA's production triad: Chronus is ONE iGPU "
    "execution plane; Ovid owns authoritative durable folded state; Theseus "
    "is a rebuildable projection from Ovid. Geodesic search is handoff-only. "
    "The triad does not claim unbounded compute, hash preimages, zero-energy "
    "operation, multi-iGPU fabrics, or bypass of double-SHA256 targets."
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

    @property
    def claim_boundary(self) -> str:
        return TRIAD_CLAIM_BOUNDARY

    def put(self, payload: bytes, **kwargs: Any) -> TheseusRecord:
        record = self.theseus.put(payload, **kwargs)
        if self.ovid_authority is not None:
            self.ovid_authority.put(payload, parents=(record.uuid,))
            if self.theseus_projection is not None:
                self.theseus_projection.rebuild()
        return record

    def get(self, uid: str) -> bytes:
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
        ok = self.theseus.verify()
        if self.ovid_authority is not None:
            ok = ok and self.ovid_authority.verify()
        return ok

    def geodesic(self):
        return self.theseus.geodesic()

    def health(self) -> Dict[str, Any]:
        t_health = self.theseus.health()
        o_health = self.ovid.health()
        if self.ovid_authority is not None:
            o_health = {**o_health, **self.ovid_authority.health()}
        if self.chronus_device is not None:
            device_count = int(
                getattr(self.chronus_device, "device_count", ONE_IGPU_DEVICE_COUNT)
            )
            measured = bool(self._chronus_measured)
            c_health: Dict[str, Any] = {
                "owner": "chronus",
                "status": "ok" if measured and device_count == 1 else "bound_unmeasured",
                "device_id": getattr(self.chronus_device, "device_id", ONE_IGPU_DEVICE_ID),
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
        t_ok = t_health.get("status") == "ok"
        o_ok = o_health.get("status") == "ok"
        if t_ok and o_ok and c_health.get("status") == "ok":
            overall = "ok"
        elif t_ok and o_ok:
            overall = "storage_ready"
        elif t_ok or o_ok:
            overall = "degraded"
        else:
            overall = "unready"
        projection_health = (
            self.theseus_projection.health() if self.theseus_projection is not None else None
        )
        return {
            "triad": self.triad_id,
            "status": overall,
            "production_surface": True,
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
        return self.theseus.snapshot(directory)


def open_triad(
    *,
    durable: bool = True,
    bind_chronus: bool = True,
    ovid_root: str | Path | None = None,
    theseus_projection_root: str | Path | None = None,
) -> Triad:
    """Open production triad. Chronus bind is best-effort; OVID storage is mandatory."""
    ovid = open_ovid()
    theseus = open_theseus(durable=durable, ovid=ovid)
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
    )
    triad._chronus_error = chronus_error
    triad._chronus_measured = chronus_measured
    return triad


__all__ = [
    "TRIAD_ID",
    "TRIAD_CLAIM_BOUNDARY",
    "ONE_IGPU_DEVICE_ID",
    "ONE_IGPU_DEVICE_COUNT",
    "Triad",
    "open_triad",
]
