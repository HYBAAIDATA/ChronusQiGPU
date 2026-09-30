"""MLA1517 iGPU hardware contract — the machine-readable device identity.

The spec file is the device's self-description: topology, state model,
execution pipeline, memory system, supervision registers, and the
acceptance contract that states what is software-verified versus a future
implementation stage. Nothing in this module asserts a capability the spec
does not name, and ``acceptance_contract`` keeps the honest boundary between
``software_verified`` and ``next_implementation_stage`` visible.

Resolution order (first existing wins):

1. ``igpu/spec/mla1517_igpu_v1.json`` — the consolidated package copy.
2. ``<repo>/mla1517_platform_v3.4/hardware/mla1517_igpu_v1.json`` — the
   platform tree copy, for checkouts where the package data was stripped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_PKG_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_ROOT.parent

SPEC_NAME = "mla1517_igpu_v1.json"
_SPEC_CANDIDATES = (
    _PKG_ROOT / "spec" / SPEC_NAME,
    _REPO_ROOT / "mla1517_platform_v3.4" / "hardware" / SPEC_NAME,
)

# Geometric facts derivable from the contract, with documented defaults so
# the module stays importable even when the spec file is absent.
_DEFAULT_DIMENSIONS = 11
_DEFAULT_WARP = 32
_DEFAULT_ICO_NODES = 12
_DEFAULT_DODECA_NODES = 20


def spec_candidates() -> List[Path]:
    """Every path consulted for the contract, in resolution order."""
    return list(_SPEC_CANDIDATES)


def spec_path() -> Path:
    """First existing contract path, else the package-canonical path."""
    for candidate in _SPEC_CANDIDATES:
        if candidate.is_file():
            return candidate
    return _SPEC_CANDIDATES[0]


def load_spec(path: Optional[Any] = None) -> Dict[str, Any]:
    """Load the hardware contract JSON. Raises when no candidate exists."""
    resolved = Path(path) if path is not None else spec_path()
    return json.loads(resolved.read_text(encoding="utf-8"))


def _spec_or_default(spec: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if spec is not None:
        return spec
    try:
        return load_spec()
    except Exception:
        return {}


def product(spec: Optional[Dict[str, Any]] = None) -> str:
    return str(_spec_or_default(spec).get("product", "MLA1517 iGPU"))


def ontology(spec: Optional[Dict[str, Any]] = None) -> str:
    return str(
        _spec_or_default(spec).get(
            "ontology", "mathematical_state_is_the_native_compute_memory_unit"
        )
    )


def topology(spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The execution topology: warp width, node shells, nonce rule, UMA."""
    topo = dict(_spec_or_default(spec).get("topology", {}) or {})
    topo.setdefault("warp_width", _DEFAULT_WARP)
    topo.setdefault("icosahedral_execution_nodes", _DEFAULT_ICO_NODES)
    topo.setdefault("dodecahedral_memory_nodes", _DEFAULT_DODECA_NODES)
    topo.setdefault("logical_partitions", _DEFAULT_WARP)
    topo.setdefault("memory_address_space", "UMA")
    return topo


def state_model(spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The 11-axis state model. ``dimensions`` defaults to the documented 11."""
    model = dict(_spec_or_default(spec).get("state_model", {}) or {})
    model.setdefault("dimensions", _DEFAULT_DIMENSIONS)
    return model


def dimensions(spec: Optional[Dict[str, Any]] = None) -> int:
    """State-space dimension — 11 axes in the shipping contract."""
    try:
        return int(state_model(spec)["dimensions"])
    except (TypeError, ValueError):
        return _DEFAULT_DIMENSIONS


def frame_faces(spec: Optional[Dict[str, Any]] = None) -> int:
    """Execution + memory node count: 12 icosahedral + 20 dodecahedral = 32."""
    topo = topology(spec)
    return int(topo["icosahedral_execution_nodes"]) + int(
        topo["dodecahedral_memory_nodes"]
    )


def face_pairs(spec: Optional[Dict[str, Any]] = None) -> int:
    """C(faces, 2) face-pair channels — 496 for the shipping 32-face frame."""
    faces = frame_faces(spec)
    return faces * (faces - 1) // 2


def warp_width(spec: Optional[Dict[str, Any]] = None) -> int:
    try:
        return int(topology(spec)["warp_width"])
    except (TypeError, ValueError):
        return _DEFAULT_WARP


def execution_pipeline(spec: Optional[Dict[str, Any]] = None) -> List[str]:
    """The D1..D11 pipeline stages named by the contract, in order."""
    return list(_spec_or_default(spec).get("execution_pipeline", []) or [])


def execution_units(spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return dict(_spec_or_default(spec).get("execution_units", {}) or {})


def memory_system(spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return dict(_spec_or_default(spec).get("memory_system", {}) or {})


def deployment(spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return dict(_spec_or_default(spec).get("deployment", {}) or {})


def acceptance_contract(spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """What is software-verified today versus a named future stage."""
    return dict(_spec_or_default(spec).get("acceptance_contract", {}) or {})


def summary(spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One compact dict: identity + geometry + verification status."""
    loaded = _spec_or_default(spec)
    return {
        "product": product(loaded),
        "contract_version": loaded.get("contract_version", ""),
        "ontology": ontology(loaded),
        "dimensions": dimensions(loaded),
        "warp_width": warp_width(loaded),
        "frame_faces": frame_faces(loaded),
        "face_pairs": face_pairs(loaded),
        "memory_address_space": topology(loaded).get("memory_address_space", "UMA"),
        "memory_system": memory_system(loaded).get("name", ""),
        "acceptance_contract": acceptance_contract(loaded),
        "spec_path": str(spec_path()),
    }


__all__ = [
    "SPEC_NAME",
    "acceptance_contract",
    "deployment",
    "dimensions",
    "execution_pipeline",
    "execution_units",
    "face_pairs",
    "frame_faces",
    "load_spec",
    "memory_system",
    "ontology",
    "product",
    "spec_candidates",
    "spec_path",
    "state_model",
    "summary",
    "topology",
    "warp_width",
]
