"""The consumer offer suite — one enumerable catalog with honest states.

Every offer reports what exists, what the detected device maps to, and the
evidence anchor. Nothing is stubbed: surfaces that are not productized say so.
"""

from __future__ import annotations

from typing import Any, Dict

from . import __version__, census

__all__ = ["offer_catalog"]

_OFFERS = [
    {
        "offer": "pythia",
        "name": "PYTHIA (free)",
        "surfaces": ["macbook", "imac", "mac-studio", "mac-mini", "mac-pro", "linux", "windows"],
        "delivers": "pythia CLI + local console: census, mint, receipt verification, offers",
    },
    {
        "offer": "pythia-node",
        "name": "PYTHIA Node",
        "surfaces": ["macbook", "imac", "mac-mini"],
        "delivers": "bundled substrate (iGPU + OVID + THESEUS); PYTHIA.app standalone",
    },
    {
        "offer": "pythia-node-large-memory",
        "name": "PYTHIA Node — large memory",
        "surfaces": ["mac-studio", "mac-pro"],
        "delivers": "≥96 GiB unified-memory tier — exact-state widths discrete GPUs can't hold",
    },
    {
        "offer": "pythia-companion",
        "name": "PYTHIA Companion",
        "surfaces": ["iphone"],
        "delivers": "installable PWA at /companion: on-device JS verifier, receipt wallet, node monitor",
    },
    {
        "offer": "pythia-studio",
        "name": "PYTHIA Studio",
        "surfaces": ["research"],
        "delivers": "intelligence workloads (TOE/EUCLID surface) — not productized; "
                    "PYTHIA_CIAAS_URL pass-through only",
    },
]


def offer_catalog(api_url: str | None = None) -> Dict[str, Any]:
    status = census.node_status(api_url=api_url)
    device = status.get("device") or {}
    bundled = sum(
        1 for p in status.get("products", [])
        if p.get("state") == "available" and p.get("origin") == "bundled"
    )
    is_mac = device.get("unified_memory") is True
    large = device.get("offer_tier") == "pythia-node-large-memory"

    states: Dict[str, str] = {
        "pythia": "installed",
        "pythia-node": ("this-device" if is_mac and not large else "absent"),
        "pythia-node-large-memory": ("this-device" if large else "absent"),
        "pythia-companion": "served",
        "pythia-studio": "not-productized",
    }
    notes: Dict[str, str] = {
        "pythia": f"hyba-pythia-consumer {__version__} running",
        "pythia-node": (f"{bundled}/3 bundled substrates available"
                        if is_mac else "requires Apple Silicon unified memory"),
        "pythia-node-large-memory": ("detected unified-memory tier ≥96 GiB"
                                     if large else "requires ≥96 GiB unified memory"),
        "pythia-companion": "served by `pythia console [--lan]` at /companion",
        "pythia-studio": "honest stub — no TOE/EUCLID consumer surface yet",
    }
    offers = [dict(o, state=states[o["offer"]], note=notes[o["offer"]]) for o in _OFFERS]
    return {
        "schema": "pythia.consumer.offers/1",
        "distribution": "hyba-pythia-consumer",
        "version": __version__,
        "device_offer_tier": device.get("offer_tier"),
        "offers": offers,
    }
