#!/usr/bin/env python3
"""Sign a HYBA revocation list (vendor side, offline signing workstation only).

    python scripts/licensing/issue_revocations.py \\
        --lease-id lease-0001 --ids-file revoked.txt \\
        --key /media/offline/hyba-lease-2026.pem --kid hyba-lease-2026 \\
        --out revocations-2026-11-11.json

Lists are cumulative: include every lease identifier revoked so far. The
document (schema hyba.revocations/1) is signed with the same key family as
leases, verified with the matching public key and written as canonical JSON.
The SHA-256 of the output file is printed for the issuance register.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _signing  # noqa: E402
from chronus.licensing import (  # noqa: E402
    LeaseError,
    TrustStore,
    validate_revocation_document,
    verify_revocations,
)


def _read_ids(path: Path):
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.split("#", 1)[0].strip()
        if value:
            ids.append(value)
    return ids


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sign a hyba.revocations/1 list with an offline Ed25519 key.")
    parser.add_argument("--lease-id", action="append", default=[], help="revoked lease identifier (repeatable)")
    parser.add_argument("--ids-file", type=Path, help="file with one revoked lease identifier per line")
    parser.add_argument("--issued-at", help="RFC 3339 UTC time YYYY-MM-DDTHH:MM:SSZ (default: now)")
    parser.add_argument("--key", required=True, help="Ed25519 private key PEM stored outside the repository")
    parser.add_argument("--kid", required=True, help="key identifier pinned in the trust store")
    parser.add_argument("--out", required=True, type=Path, help="signed envelope to write")
    parser.add_argument("--force", action="store_true", help="replace an existing output file")
    args = parser.parse_args(argv)
    try:
        key_path = _signing.private_key_path(args.key)
        lease_ids = list(args.lease_id)
        if args.ids_file is not None:
            lease_ids.extend(_read_ids(args.ids_file))
        document = {
            "schema": "hyba.revocations/1",
            "issued_at": args.issued_at or _signing.utc_now(),
            "lease_ids": sorted(set(lease_ids)),
        }
        validate_revocation_document(document)
        private_key = _signing.load_private_key(key_path)
        envelope = _signing.sign_envelope("revocations", document, private_key, args.kid)
        verify_revocations(envelope, trust_store=TrustStore({args.kid: _signing.raw_public_key(private_key)}))
        digest = _signing.write_output(args.out, envelope, force=args.force)
    except (_signing.ToolError, LeaseError, OSError) as exc:
        print(f"issue_revocations: {exc}", file=sys.stderr)
        return 2
    print(f"sha256 {digest}  {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
