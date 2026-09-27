"""Identify helper + DeviceIdentity record for the vendor catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from hyba.catalog import _norm, find_spec


@dataclass
class DeviceIdentity:
    """Observed device identity: catalog match + raw evidence."""

    name: str
    vendor: str = ""
    pci_ids: Tuple[str, ...] = ()
    family: str | None = None
    backends: Tuple[str, ...] = ()
    dispatch: str = "cpu"
    known: bool = False
    match_evidence: Tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> Dict[str, Any]:
        """JSON-safe identity record for telemetry and status."""
        return {
            "name": self.name,
            "vendor": self.vendor,
            "pci_ids": list(self.pci_ids),
            "family": self.family,
            "backends": list(self.backends),
            "dispatch": self.dispatch,
            "known": self.known,
            "match_evidence": list(self.match_evidence),
        }


def identify(
    name: Any = "",
    vendor: Any = "",
    pci_ids: Tuple[str, ...] = (),
) -> DeviceIdentity:
    """Identify a device against the catalog from observed evidence."""
    spec = find_spec(name, vendor, pci_ids)
    evidence: List[str] = []
    name_l = _norm(name)
    if spec is not None:
        for alias in spec.aliases:
            if alias and alias in name_l:
                evidence.append(f"alias:{alias}")
        for spec_id in spec.pci_ids:
            token = spec_id.lower()
            bare = token[2:] if token.startswith("0x") else token
            if (token and token in name_l) or (bare and bare in name_l):
                evidence.append(f"pci:{spec_id}")
        for given in pci_ids or ():
            item = str(given).strip().lower()
            if item:
                evidence.append(f"pci-env:{given}")
        if _norm(vendor):
            evidence.append(f"vendor:{str(vendor).strip()}")
    return DeviceIdentity(
        name=str(name or "").strip(),
        vendor=str(vendor or "").strip(),
        pci_ids=tuple(pci_ids or ()),
        family=spec.family if spec else None,
        backends=tuple(spec.backends) if spec else (),
        dispatch=spec.dispatch if spec else "cpu",
        known=spec is not None and bool(evidence),
        match_evidence=tuple(evidence),
    )


__all__ = ["DeviceIdentity", "identify"]
