#!/usr/bin/env python3
"""PYTHIA Python backend entrypoint.

The React application is static. All control and status requests terminate in
the canonical Python MLA1517 service. There is no Node server and no
simulated backend. Hardware mining remains fail-closed until the canonical
device/coordinator requirements are present.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Bound BLAS/OpenMP thread allocation to 1 thread per worker to avoid thread exhaustion
# and memory allocation failure ("OpenBLAS error: Memory allocation still failed after 10 retries")
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_var, "1")

_PROJECT_ROOT = Path(__file__).resolve().parent
_CANONICAL_PYTHON = _PROJECT_ROOT / "chronus/mla1517_platform" / "python"
_CHRONOS_IGPU = _PROJECT_ROOT / "packages" / "chronos-one-igpu" / "src"
_PYTHIA_CONSUMER = _PROJECT_ROOT / "packages" / "pythia-consumer" / "src"
_TURING = _PROJECT_ROOT / "turing_universal_quantum_computer"
for _p in [str(_PROJECT_ROOT), str(_CANONICAL_PYTHON), str(_CHRONOS_IGPU), str(_PYTHIA_CONSUMER), str(_TURING)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

_existing_pp = os.environ.get("PYTHONPATH", "")
_pp_parts = _existing_pp.split(os.pathsep) if _existing_pp else []
for _p in [str(_CHRONOS_IGPU), str(_PYTHIA_CONSUMER), str(_CANONICAL_PYTHON), str(_PROJECT_ROOT), str(_TURING)]:
    if _p not in _pp_parts:
        _pp_parts.insert(0, _p)
os.environ["PYTHONPATH"] = os.pathsep.join(_pp_parts)

# Sovereign deployments (HYBA_SOVEREIGN_MODE=private|air_gapped) install the
# AL HARAS egress/ingestion/storage boundary before any service code loads;
# an invalid sovereign configuration refuses to start (exit 78, EX_CONFIG).
# Connected mode (the default) installs nothing.
from al_haras.sovereign_control import SovereignConfigError, install_from_env  # noqa: E402

try:
    install_from_env(role="control-api")
except SovereignConfigError as _exc:
    print(f"sovereign configuration error: {_exc}", file=sys.stderr)
    raise SystemExit(78) from _exc

from control_api import main  # noqa: E402


if __name__ == "__main__":
    main()
