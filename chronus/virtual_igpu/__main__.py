"""Run Chronus Virtual iGPU as a standalone process or sidecar."""
from __future__ import annotations

import argparse
import os

from .adapters import default_adapters
from .runtime import RuntimeDaemon
from .wire import serve


def main() -> int:
    parser = argparse.ArgumentParser(description="Chronus Virtual iGPU sidecar (virtual_igpu_v1)")
    parser.add_argument("--host", default=os.getenv("CHRONUS_VIGPU_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("CHRONUS_VIGPU_PORT", "8765")))
    parser.add_argument(
        "--store", default=os.getenv("CHRONUS_VIGPU_STORE", ".chronus-virtual-igpu")
    )
    parser.add_argument(
        "--no-emulator",
        action="store_true",
        help="Exclude CPU software adapter (fail closed if no physical adapter)",
    )
    args = parser.parse_args()
    adapters = default_adapters(include_cpu_emulator=not args.no_emulator)
    daemon = RuntimeDaemon(root=args.store, adapters=adapters)
    daemon.attach()
    server = serve(args.host, args.port, store=args.store)
    # serve() creates its own daemon; print bind info from args
    print(
        f"Chronus Virtual iGPU virtual_igpu_v1 listening on "
        f"http://{args.host}:{args.port} store={args.store}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        daemon.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
