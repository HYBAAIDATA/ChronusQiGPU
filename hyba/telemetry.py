"""iGPU telemetry surface for the HYBA composition layer.

The canonical collector lives at :mod:`igpu.telemetry` (the consolidated iGPU
package). ``Intelligence/igpu_telemetry.py`` is a historical duplicate kept for
back-compat imports; this module re-exports the canonical names so operator
code under ``hyba`` never has to guess which surface is live.

Operator-facing aliases are provided for the names the elevation spec uses:
``IGpuTelemetryCollector`` = :class:`IgpuTelemetry`,
``attach_igpu_telemetry`` = :func:`attach_to_host`,
``get_last_igpu_telemetry`` = :func:`get_telemetry`,
``igpu_telemetry_hook`` = factory returning the same callable
:func:`attach_to_host` installs, and ``reset_igpu_telemetry`` =
:func:`reset_telemetry`.

LUCAS WIRING: coordinator module — re-exports only; adds no algorithm.
Substrate route: gap
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from igpu.telemetry import (
    ANCHOR_BUCKETS,
    DODECAHEDRAL_FACES,
    FACE_PAIRS,
    FRAME_FACES,
    HETEROTIC_GAUGE_DIMENSION,
    ICOSAHEDRAL_FACES,
    ICOSAHEDRAL_ISOTROPIC_SHARE,
    MANIFOLD_PUNCHES,
    PERFECT_NUMBER_496,
    PUNCH_NAMES,
    THEOREM_PROVEN,
    FrameTelemetry,
    IgpuTelemetry,
    attach_to_host,
    get_telemetry,
    reset_telemetry,
)

# The environment variable the collector honors (default on; "0"/"false" off).
EUCLID_IGPU_TELEMETRY = "EUCLID_IGPU_TELEMETRY"

# -- operator-facing aliases -------------------------------------------------
IGpuTelemetryCollector = IgpuTelemetry
attach_igpu_telemetry = attach_to_host
reset_igpu_telemetry = reset_telemetry


def get_last_igpu_telemetry() -> IgpuTelemetry:
    """The process-wide collector singleton (same object ``get_telemetry``)."""
    return get_telemetry()


def igpu_telemetry_hook(telemetry: Optional[IgpuTelemetry] = None) -> Callable[[Dict[str, Any]], None]:
    """Return the hook callable ``attach_to_host`` installs on a punch host.

    ``host.telemetry_hook`` receives ``event: dict`` payloads; on ``kind ==
    "dispatch"`` the event may also carry ``device_name``, ``capability_used``
    and ``lucas_rung`` for the SuperGPU provenance fields.
    """
    import types

    probe = types.SimpleNamespace()
    attach_to_host(probe, telemetry)
    return probe.telemetry_hook


__all__ = [
    "ANCHOR_BUCKETS",
    "DODECAHEDRAL_FACES",
    "EUCLID_IGPU_TELEMETRY",
    "FACE_PAIRS",
    "FRAME_FACES",
    "FrameTelemetry",
    "HETEROTIC_GAUGE_DIMENSION",
    "ICOSAHEDRAL_FACES",
    "ICOSAHEDRAL_ISOTROPIC_SHARE",
    "IGpuTelemetryCollector",
    "IgpuTelemetry",
    "MANIFOLD_PUNCHES",
    "PERFECT_NUMBER_496",
    "PUNCH_NAMES",
    "THEOREM_PROVEN",
    "attach_igpu_telemetry",
    "attach_to_host",
    "get_last_igpu_telemetry",
    "get_telemetry",
    "igpu_telemetry_hook",
    "reset_igpu_telemetry",
    "reset_telemetry",
]
