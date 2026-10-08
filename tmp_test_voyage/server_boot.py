"""Boot a CIaaS HTTP server for the voyage test.

Usage: python server_boot.py --port PORT --state STATE_PATH --dim DIM
Prints STARTUP_HEALTH <json> then READY, then serves until killed.
"""
import argparse
import json
import sys

from toe.ciaas_api import CIaaSServer, CIaaSService
from toe.runtime import TOEIntelligenceRuntime, TOEIntelligenceRuntimeConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--dim", type=int, default=32)
    args = ap.parse_args()

    config = TOEIntelligenceRuntimeConfig(
        hilbert_dim=args.dim,
        enable_feedback=True,
        enable_evidence=True,
        enable_asi=True,
        enable_platform=False,
        production_ready=False,
        feedback_state_path=args.state,
    )
    runtime = TOEIntelligenceRuntime(config=config)
    service = CIaaSService(runtime=runtime)

    health = runtime.health()
    print("STARTUP_HEALTH " + json.dumps(health, default=str), flush=True)

    server = CIaaSServer(host="127.0.0.1", port=args.port, service=service)
    print("READY", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
