"""python -m igpu.seam.run --config config.toml"""

from __future__ import annotations

import argparse
import asyncio
import logging
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.toml")
    args = parser.parse_args(argv)
    cfg = load_config(Path(args.config))
    pool = cfg.get("pool") or {}
    from igpu.seam.workflow import run_workflow

    result = asyncio.run(
        run_workflow(
            str(pool.get("host", "127.0.0.1")),
            int(pool.get("port", 3333)),
            str(pool.get("worker", "pythia")),
            str(pool.get("password", "x")),
            window=int(cfg.get("window", pool.get("window", 4096))),
        )
    )
    print("accepted", result.accepted)
    print("layers", ",".join(result.layers))
    return 0 if result.extra.get("replay_ok") and result.extra.get("forge_fail") else 1


if __name__ == "__main__":
    sys.exit(main())
