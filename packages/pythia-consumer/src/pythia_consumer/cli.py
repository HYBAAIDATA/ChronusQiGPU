"""``pythia`` CLI — the consumer entry point.

    pythia version
    pythia census [--json]
    pythia products [--json]
    pythia offers
    pythia node status [--api URL]
    pythia mint [--context STR] [--data FILE] [--masks m0,…,m10]
    pythia verify RECEIPT.json
    pythia console [--port N] [--api URL] [--lan]
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

    sub.add_parser("offers", help="consumer offer catalog with honest states")

    p = sub.add_parser("mint", help="mint a receipt you can verify (fold-consistent, provenance unsupported)")
    p.add_argument("--context", default="", help="context_id bound into the receipt")
    p.add_argument("--data", type=Path, help="derive coordinate masks from this file's SHA-256")
    p.add_argument("--masks", help="explicit comma-separated 11 producible masks")

    p = sub.add_parser("node", help="node surface")
    n = p.add_subparsers(dest="node_cmd", required=True)
    s = n.add_parser("status", help="census + optional control-API reachability")
    s.add_argument("--api", metavar="URL", help="control API base URL to probe")

    p = sub.add_parser("verify", help="structurally verify a receipt file")
    p.add_argument("receipt", type=Path)

    p = sub.add_parser("console", help="serve the local console UI")
    p.add_argument("--port", type=int, default=8777)
    p.add_argument("--api", metavar="URL", help="control API base URL to probe")
    p.add_argument("--lan", action="store_true",
                   help="bind 0.0.0.0 so LAN devices (iPhone companion at "
                        "/companion) can reach the console — no auth; "
                        "exposes read-only census and stateless verify")

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
    if args.cmd == "offers":
        from . import offers
        _dump(offers.offer_catalog())
        return 0
    if args.cmd == "mint":
        from . import mint
        try:
            masks = ([int(x) for x in args.masks.split(",")]
                     if args.masks else None)
            data = args.data.read_bytes() if args.data else None
            _dump(mint.mint_receipt(context_id=args.context,
                                    coordinate_masks=masks, data=data))
            return 0
        except (OSError, ValueError) as exc:
            print(f"cannot mint: {exc}", file=sys.stderr)
            return 2
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
        serve(port=args.port, api_url=args.api, lan=args.lan)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
