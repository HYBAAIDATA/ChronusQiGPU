"""``python -m chronus.seam.run --config config.toml``.

LEGACY SEAM HARNESS — this entry point drives ``chronus.seam.workflow``, which
uses ``mining.stratum_bridge.StratumBridge`` (the LEGACY Stratum client). It is
NOT the canonical production mining path; canonical mining is ``pythia-mine``
→ ``chronus.mla1517_platform.python.mining_runtime``. A passing report here is
protocol-layer evidence only.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore


def load_config(path: Path) -> dict:
    if tomllib is None:
        raise RuntimeError("Python 3.11+ required for tomllib")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Legacy 14-layer seam harness (non-canonical; "
        "production mining is pythia-mine)"
    )
    parser.add_argument("--config", default="config.toml")
    args = parser.parse_args(argv)
    config = load_config(Path(args.config))
    pool = config.get("pool") or {}
    custody = config.get("custody") or {}

    from .scale import snap_work_items
    from .workflow import run_workflow

    result = asyncio.run(
        run_workflow(
            str(pool.get("host", "127.0.0.1")),
            int(pool.get("port", 3333)),
            str(pool.get("worker", "pythia")),
            str(pool.get("password", "x")),
            # LUCAS_SCALED: the resolved batch window is a ladder stop.
            window=snap_work_items(int(config.get("window", pool.get("window", 4096)))),
            custody_dir=custody.get("dir") or os.getenv("PYTHIA_SEAM_CUSTODY_DIR") or None,
        )
    )
    print("accepted", result.accepted)
    print("layers", ",".join(result.layers))
    print("custody", result.extra.get("custody_state", "in-process"))
    return 0 if result.extra.get("replay_ok") and result.extra.get("forgery_rejected") else 1


if __name__ == "__main__":
    sys.exit(main())
