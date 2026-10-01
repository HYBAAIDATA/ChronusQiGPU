from __future__ import annotations
import argparse
import json
import os
from .store import PrimeDB


def main() -> None:
    p = argparse.ArgumentParser(prog="mla1517")
    # MLA1517_DB puts the store on the deployment's volume (Dockerfile.production).
    p.add_argument("--db", default=os.getenv("MLA1517_DB", "prime.db"))
    sub = p.add_subparsers(dest="command", required=True)
    put = sub.add_parser("put")
    put.add_argument("--index", type=int, required=True)
    put.add_argument("--scale", type=int, default=15)
    put.add_argument("--family", default="fibonacci")
    put.add_argument("payload")
    get = sub.add_parser("get")
    get.add_argument("object_id")
    verify = sub.add_parser("verify")
    verify.add_argument("object_id")
    args = p.parse_args()
    db = PrimeDB(args.db)
    try:
        if args.command == "put":
            payload = json.loads(args.payload)
            print(
                json.dumps(
                    db.put(payload, args.index, args.scale, args.family).to_dict(), sort_keys=True
                )
            )
        elif args.command == "get":
            print(json.dumps(db.get(args.object_id).to_dict(), sort_keys=True))
        else:
            print(json.dumps(db.verify(args.object_id), sort_keys=True))
    finally:
        db.close()
