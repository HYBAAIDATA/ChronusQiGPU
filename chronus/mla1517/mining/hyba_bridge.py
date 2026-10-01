"""Production adapter from python_backend hyba_core_v1 into MLA1517.

Ordering and structure telemetry only. Never evaluates SHA256d, never
admits a share, never replaces M32SearchSolver or StratumProofAdapter.
Import and measurement fail closed: missing package -> available=False.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

LOG = logging.getLogger("chronus.mla1517.mining.hyba_bridge")

_PHI = (1.0 + 5.0**0.5) / 2.0
_STRUCTURE_THRESHOLD = 1.0 / _PHI


def _ensure_repo_root() -> None:
    here = Path(__file__).resolve()
    root = here.parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _load():
    _ensure_repo_root()
    from python_backend.mathematical_foundation.hilbert_manifold_solver import (  # noqa: WPS433
        ManifoldPrecomputationEngine,
        build_m32_normals,
    )
    from python_backend.mathematical_foundation.phi_complexity_theory import (  # noqa: WPS433
        PhiStructureAnalyzer,
    )
    from python_backend.phi_grover_v4 import (  # noqa: WPS433
        check_pow,
        cheap_resonance,
        phi_resonance,
    )
    from python_backend.pythia_mining.intelligence_chooser import (  # noqa: WPS433
        MiningIntelligenceChooser as HybaChooser,
    )

    return {
        "engine": ManifoldPrecomputationEngine.get_instance(),
        "normals": build_m32_normals(),
        "analyzer": PhiStructureAnalyzer(),
        "chooser": HybaChooser(),
        "phi_resonance": phi_resonance,
        "cheap_resonance": cheap_resonance,
        "check_pow": check_pow,
    }


try:
    _CORE = _load()
    AVAILABLE = True
    LOAD_ERROR: str | None = None
except Exception as exc:  # fail closed
    _CORE = None
    AVAILABLE = False
    LOAD_ERROR = f"{type(exc).__name__}: {exc}"
    LOG.warning("hyba_core unavailable; mining continues without it: %s", LOAD_ERROR)


def describe_share(share: Mapping[str, Any] | None) -> dict[str, Any]:
    """Serialize a pool share for logs. Proof status is caller-supplied."""
    share = share or {}
    return {
        "job_id": share.get("job_id"),
        "nonce": share.get("nonce"),
        "accepted": share.get("accepted"),
        "proof": share.get("proof", "sha256d"),
        "hyba_available": AVAILABLE,
    }


def measure_window(candidate_window: Iterable[int] | None) -> dict[str, Any]:
    """Score an observed nonce window. Does not touch consensus."""
    base = {
        "available": AVAILABLE,
        "load_error": LOAD_ERROR,
        "window_size": 0,
        "structure_parameter": None,
        "structure_detected": None,
        "mean_resonance": None,
        "faces": None,
        "proof": "sha256d",
        "gates_proof": False,
    }
    try:
        values = (
            [int(v) & 0xFFFFFFFF for v in candidate_window] if candidate_window is not None else []
        )
        base["window_size"] = len(values)
        if not AVAILABLE or _CORE is None or not values:
            return base
        parameter = float(_CORE["analyzer"].compute_structure_parameter(values, values))
        detected = parameter >= _STRUCTURE_THRESHOLD
        resonances = [_CORE["phi_resonance"](v) for v in values[:32]]
        faces = [_CORE["engine"].assign_voronoi_face(v) for v in values[:32]]
        base.update(
            {
                "structure_parameter": parameter,
                "structure_detected": detected,
                "mean_resonance": sum(resonances) / len(resonances),
                "faces": faces,
            }
        )
        return base
    except Exception as exc:
        LOG.error("hyba measure_window failed: %s", exc)
        base["load_error"] = f"{type(exc).__name__}: {exc}"
        return base


def face_of(nonce: int) -> int | None:
    if not AVAILABLE or _CORE is None:
        return None
    return int(_CORE["engine"].assign_voronoi_face(int(nonce) & 0xFFFFFFFF))


def resonance_of(nonce: int) -> float | None:
    if not AVAILABLE or _CORE is None:
        return None
    return float(_CORE["phi_resonance"](int(nonce) & 0xFFFFFFFF))
