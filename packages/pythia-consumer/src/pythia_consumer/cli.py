"""``pythia`` CLI — the consumer entry point.

    pythia version
    pythia census [--json]
    pythia products [--json]
    pythia node status [--api URL]
    pythia verify RECEIPT.json
    pythia console [--port N] [--api URL]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, census, verify


def _dump(payload) -> None:
    print(json.dumps(payload, indent=1, sort_keys=False))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pythia", description="PYTHIA consumer console")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version")

    p = sub.add_parser("census", help="local platform/backend census")
    p.add_argument("--json", action="store_true", help="JSON output (default)")

    sub.add_parser("products", help="list bundled/installed substrate products")

    p = sub.add_parser("node", help="node surface")
    n = p.add_subparsers(dest="node_cmd", required=True)
    s = n.add_parser("status", help="census + optional control-API reachability")
    s.add_argument("--api", metavar="URL", help="control API base URL to probe")

    p = sub.add_parser("verify", help="structurally verify a receipt file")
    p.add_argument("receipt", type=Path)

    p = sub.add_parser("console", help="serve the local console UI")
    p.add_argument("--port", type=int, default=8777)
    p.add_argument("--api", metavar="URL", help="control API base URL to probe")

    args = ap.parse_args(argv)

    if args.cmd == "version":
        print(f"hyba-pythia-consumer {__version__}")
        return 0
    if args.cmd == "census":
        _dump(census.node_status())
        return 0
    if args.cmd == "products":
        _dump(census.available_products())
        return 0
    if args.cmd == "node":
        _dump(census.node_status(api_url=args.api))
        return 0
    if args.cmd == "verify":
        try:
            receipt = json.loads(args.receipt.read_text())
        except (OSError, ValueError) as exc:
            print(f"cannot read receipt: {exc}", file=sys.stderr)
            return 2
        verdict = verify.verify_receipt(receipt)
        _dump(verdict)
        return 0 if verdict["verdict"] == "pass" else 1
    if args.cmd == "console":
        from .console import serve
        serve(port=args.port, api_url=args.api)
        return 0
    return 2
