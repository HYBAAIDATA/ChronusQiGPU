"""Run a Python worker script inside the sovereign boundary.

``python -m al_haras.sovereign_exec SCRIPT [ARGS...]`` installs the AL HARAS
sovereign control plane from the environment (refusing to start on an
invalid configuration, exit 78) and then runs SCRIPT as ``__main__``
exactly as ``python SCRIPT`` would. Supervisors use
:func:`al_haras.sovereign_control.worker_argv` so every worker process of a
sovereign deployment carries the same boundary as the control API.
"""

from __future__ import annotations

import os
import runpy
import sys

from .sovereign_control import ENV_ROLE, SovereignConfigError, install_from_env


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m al_haras.sovereign_exec SCRIPT [ARGS...]", file=sys.stderr)
        raise SystemExit(64)
    script = sys.argv[1]
    try:
        install_from_env(role=os.environ.get(ENV_ROLE) or f"worker:{os.path.basename(script)}")
    except SovereignConfigError as exc:
        print(f"sovereign configuration error: {exc}", file=sys.stderr)
        raise SystemExit(78) from exc
    sys.argv = sys.argv[1:]
    sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
