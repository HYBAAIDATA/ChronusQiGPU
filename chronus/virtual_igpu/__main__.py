"""Run Chronus Virtual iGPU as a standalone process or sidecar."""
from __future__ import annotations

import argparse
import os

from .runtime import RuntimeConfig, RuntimeDaemon
from .wire import build_server


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("CHRONUS_VIGPU_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("CHRONUS_VIGPU_PORT", "8765")))
    parser.add_argument(
        "--store", default=os.getenv("CHRONUS_VIGPU_STORE", ".chronus-virtual-igpu")
    )
    parser.add_argument("--require-hardware", action="store_true")
    parser.add_argument("--no-emulator", action="store_true")
    args = parser.parse_args()
    runtime = RuntimeDaemon(
        RuntimeConfig(
            store_root=args.store,
            include_emulator=not args.no_emulator,
            require_hardware=args.require_hardware,
        )
    )
    server = build_server(runtime, args.host, args.port)
    print(
        f"Chronus Virtual iGPU virtual_igpu_v1 listening on "
        f"http://{args.host}:{args.port}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())