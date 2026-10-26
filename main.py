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
for _var in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ.setdefault(_var, "1")


def _add_project_paths() -> list[str]:
    """Register only verified project roots so PYTHONPATH stays predictable."""
    base = Path(__file__).resolve().parent
    candidate_dirs = [
        base,
        base / "chronus/mla1517_platform/python",
        base / "packages/chronos-one-igpu/src",
        base / "packages/pythia-consumer/src",
        base / "turing_universal_quantum_computer",
    ]
    verified = [str(path) for path in candidate_dirs if path.exists()]
    for path in verified:
        if path not in sys.path:
            sys.path.insert(0, path)
    return verified


_PROJECT_ROOTS = _add_project_paths()

_existing_pp = os.environ.get("PYTHONPATH", "")
_pp_parts = _existing_pp.split(os.pathsep) if _existing_pp else []
for _path in _PROJECT_ROOTS:
    if _path not in _pp_parts:
        _pp_parts.insert(0, _path)
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

import asyncio
import concurrent.futures
from typing import Any, Callable

_ML_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None


def get_ml_executor(max_workers: int = 4) -> concurrent.futures.ThreadPoolExecutor:
    """Return a shared ThreadPoolExecutor for offloading CPU-heavy ML work."""
    global _ML_EXECUTOR
    if _ML_EXECUTOR is None:
        _ML_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="pythia-ml-worker",
        )
    return _ML_EXECUTOR


async def evaluate_tree_channels_async(
    fn: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Offload heavy tree/channel evaluation to the async ML thread executor."""
    loop = asyncio.get_running_loop()
    executor = get_ml_executor()
    if kwargs:
        import functools

        p_fn = functools.partial(fn, *args, **kwargs)
        return await loop.run_in_executor(executor, p_fn)
    return await loop.run_in_executor(executor, fn, *args)


if __name__ == "__main__":
    main()
