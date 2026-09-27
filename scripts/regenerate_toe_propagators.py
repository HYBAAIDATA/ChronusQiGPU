"""Regenerate ``toe/default_propagators.json`` — the scale-fold store seed.

``toe.bridge`` propagates states with U(t)=exp(-iHt/ℏ) for six fixed
forecast times over a fixed default oscillator Hamiltonian. Those seven
matrices are data-independent, so they are computed once here — via the
project's own ``ComplexMatrix.matrix_exp_unitary`` — serialized with a
canonical-JSON SHA-256 fingerprint (same convention as
``scripts/verify.py``), and loaded by ``toe.bridge`` at import.

Run from the repository root:

    python scripts/regenerate_toe_propagators.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Skip import-time seeding: this script pays the exponential cost itself.
os.environ["TOE_SKIP_PROPAGATOR_SEED"] = "1"

from toe.bridge import (  # noqa: E402
    TOEBridge,
    _FORECAST_TIMES,
    _PROPAGATOR_ARTIFACT_FORMAT,
    _PROPAGATOR_ARTIFACT_PATH,
    _build_propagator_table,
    _canonical_json_bytes,
    _matrix_to_payload,
)


def regenerate() -> str:
    """Recompute the default propagators and write the artifact. Returns the path."""
    bridge = TOEBridge()
    params = (bridge._dim, bridge._hbar, bridge._mass, bridge._omega)
    table = _build_propagator_table()
    doc = {
        "format": _PROPAGATOR_ARTIFACT_FORMAT,
        "generator": "ComplexMatrix.matrix_exp_unitary "
        "(scaling-and-squaring + Taylor, max_terms=30)",
        "hamiltonian": {
            "dim": params[0],
            "hbar": params[1],
            "mass": params[2],
            "omega": params[3],
        },
        "times": list(_FORECAST_TIMES),
        "H": _matrix_to_payload(bridge._hamiltonian()),
        "U": [_matrix_to_payload(table[t]) for t in _FORECAST_TIMES],
    }
    doc["fingerprint_sha256"] = hashlib.sha256(_canonical_json_bytes(doc)).hexdigest()
    with open(_PROPAGATOR_ARTIFACT_PATH, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, separators=(",", ":"))
    return _PROPAGATOR_ARTIFACT_PATH


if __name__ == "__main__":
    path = regenerate()
    size = os.path.getsize(path)
    print(f"wrote {path} ({size} bytes)")
