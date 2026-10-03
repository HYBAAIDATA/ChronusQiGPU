"""Chronus · Theseus · Ovid — unified production triad façade.

Opens the three owners with fail-closed health, shared claim boundaries,
and a single database-shaped API for the new storage model:

    put/get           — Theseus custody (prime + phyllotaxis + heal)
    fold/materialise  — Ovid working form
    chronus           — iGPU offering bind (optional; soft if unavailable)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .ovid import CLAIM_BOUNDARY as OVID_CLAIM
from .ovid import Ovid, open_ovid
from .theseus import CLAIM_BOUNDARY as THESEUS_CLAIM
from .theseus import Theseus, TheseusRecord, open_theseus


TRIAD_ID = "chronus.theseus.ovid"
TRIAD_CLAIM_BOUNDARY = (
    "Chronus·Theseus·Ovid is HYBA's production triad: Chronus binds measured "
    "iGPU compute; Theseus owns self-healing prime-manifold storage with "
    "sunflower phyllotaxis packing; Ovid owns fold-as-working-form "
    "metamorphosis. Geodesic search is handoff-only. The triad does not "
    "claim unbounded compute, hash preimages, zero-energy operation, or "
    "bypass of double-SHA256 targets."
)


@dataclass
class Triad:
    """Production façade over Chronus + Theseus + Ovid."""

    theseus: Theseus
    ovid: Ovid
    chronus_device: Any = None
    triad_id: str = TRIAD_ID
    _chronus_error: Optional[str] = None

    @property
    def claim_boundary(self) -> str:
        return TRIAD_CLAIM_BOUNDARY

    def put(self, payload: bytes, **kwargs: Any) -> TheseusRecord:
        return self.theseus.put(payload, **kwargs)

    def get(self, uid: str) -> bytes:
        return self.theseus.get(uid)

    def fold(self, payload: bytes):
        return self.ovid.metamorphose(payload)

    def materialise(self, form) -> bytes:
        return self.ovid.materialise(form)

    def verify(self) -> bool:
        return self.theseus.verify()

    def geodesic(self):
        return self.theseus.geodesic()

    def health(self) -> Dict[str, Any]:
        t_health = self.theseus.health()
        o_health = self.ovid.health()
        if self.chronus_device is not None:
            c_health: Dict[str, Any] = {
                "owner": "chronus",
                "status": "ok",
                "device_id": getattr(self.chronus_device, "device_id", "chronus"),
                "bound": True,
            }
            boundary = getattr(self.chronus_device, "claim_boundary", None)
            if boundary is None:
                # module-level CLAIM_BOUNDARY often used
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
                "reason": self._chronus_error or "chronus not opened",
            }
        t_ok = t_health.get("status") == "ok"
        o_ok = o_health.get("status") == "ok"
        if t_ok and o_ok and c_health.get("bound"):
            overall = "ok"
        elif t_ok and o_ok:
            overall = "storage_ready"
        elif t_ok or o_ok:
            overall = "degraded"
        else:
            overall = "unready"
        return {
            "triad": self.triad_id,
            "status": overall,
            "production_surface": True,
            "claim_boundary": TRIAD_CLAIM_BOUNDARY,
            "owners": {
                "chronus": c_health,
                "theseus": t_health,
                "ovid": o_health,
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
) -> Triad:
    """Open production triad. Chronus bind is best-effort; storage is mandatory."""
    ovid = open_ovid()
    theseus = open_theseus(durable=durable, ovid=ovid)
    chronus_device = None
    chronus_error = None
    if bind_chronus:
        try:
            from chronus import open_device

            chronus_device = open_device()
        except Exception as exc:
            chronus_error = f"{type(exc).__name__}: {exc}"
    triad = Triad(theseus=theseus, ovid=ovid, chronus_device=chronus_device)
    triad._chronus_error = chronus_error
    return triad


__all__ = [
    "TRIAD_ID",
    "TRIAD_CLAIM_BOUNDARY",
    "Triad",
    "open_triad",
]
