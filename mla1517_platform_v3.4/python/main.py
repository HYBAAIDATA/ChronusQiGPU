#!/usr/bin/env python3
"""Canonical PYTHIA entrypoint.

The default mode is the Python operator API. Live hardware mining is an
explicit mode and remains subject to the existing device, credential, proof,
and submission gates in ``mining_runtime``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mine", action="store_true", help="run the gated MLA1517 mining coordinator"
    )
    parser.add_argument("--host", default=os.getenv("PYTHIA_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PYTHIA_PORT", "3000")))
    parser.add_argument(
        "--web-root", type=Path, default=Path(os.getenv("PYTHIA_WEB_ROOT", "dist/public"))
    )
    args, remainder = parser.parse_known_args()
    if not args.mine:
        from control_api import serve

        serve(host=args.host, port=args.port, web_root=args.web_root)
        return
    from mining_runtime import main as mining_main

    # The hardware runtime owns its own strict CLI. Preserve only its arguments;
    # the API-only flags must never leak into the mining parser.
    sys.argv = [sys.argv[0], *remainder]
    mining_main()


if __name__ == "__main__":
    main()
