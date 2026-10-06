#!/usr/bin/env python3
"""M3 §16 observability surface: print measured file-plane stats as JSON.

    python scripts/storage_status.py --db data/hyba.db --tenant <id>
        --integrity-key-hex <64hex> [--custody-root DIR --custody-key-hex <hex>]

Custody verification runs only when a custody root+key is supplied; without
them custody columns report the registry's stored ids (unchecked, stated).
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True)
    parser.add_argument("--tenant", default=None)
    parser.add_argument("--integrity-key-hex", default=os.getenv("HYBA_INTEGRITY_KEY_HEX", ""))
    parser.add_argument("--custody-root", default=os.getenv("THESEUS_CUSTODY_ROOT", ""))
    parser.add_argument("--custody-key-hex", default=os.getenv("THESEUS_CUSTODY_KEY_HEX", ""))
    args = parser.parse_args()
    if not args.integrity_key_hex:
        parser.error("--integrity-key-hex or HYBA_INTEGRITY_KEY_HEX is required")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from hyba_db.store import OntologyStore

    custody = None
    if args.custody_root and args.custody_key_hex:
        from hyba_db.theseus_custody import TheseusFileCustody

        custody = TheseusFileCustody(
            root=args.custody_root, hmac_key=bytes.fromhex(args.custody_key_hex)
        )
    store = OntologyStore(args.db, bytes.fromhex(args.integrity_key_hex), custody=custody)
    try:
        stats = store.files.stats(args.tenant)
        stats["custody_verified"] = custody is not None
        print(json.dumps(stats, indent=2, sort_keys=True))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
