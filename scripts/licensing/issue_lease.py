#!/usr/bin/env python3
"""Sign a HYBA lease (vendor side, offline signing workstation only).

    python scripts/licensing/issue_lease.py \\
        --lease lease.json --key /media/offline/hyba-lease-2026.pem \\
        --kid hyba-lease-2026 --out participant-01.lease.json

The unsigned lease is checked against the hyba.lease/1 schema, signed with
the Ed25519 private key (PEM, read from a path outside this repository),
verified end to end with the matching public key and written as canonical
JSON. The SHA-256 of the output file is printed for the issuance register.
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
    loads_strict,
    parse_timestamp,
    validate_lease_document,
    verify_lease,
)


def _self_check(envelope, private_key, kid):
    lease = envelope["lease"]
    moment = max(parse_timestamp(lease["not_before"]), parse_timestamp(lease["issued_at"]))
    verify_lease(
        envelope,
        trust_store=TrustStore({kid: _signing.raw_public_key(private_key)}),
        fingerprints=lease["binding"]["fingerprints"],
        now=moment,
        clock_skew_seconds=0,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sign a hyba.lease/1 document with an offline Ed25519 key.")
    parser.add_argument("--lease", required=True, type=Path, help="unsigned lease JSON (schema hyba.lease/1)")
    parser.add_argument("--key", required=True, help="Ed25519 private key PEM stored outside the repository")
    parser.add_argument("--kid", required=True, help="key identifier pinned in the trust store")
    parser.add_argument("--out", required=True, type=Path, help="signed envelope to write")
    parser.add_argument("--force", action="store_true", help="replace an existing output file")
    args = parser.parse_args(argv)
    try:
        key_path = _signing.private_key_path(args.key)
        lease = loads_strict(args.lease.read_bytes())
        validate_lease_document(lease)
        private_key = _signing.load_private_key(key_path)
        envelope = _signing.sign_envelope("lease", lease, private_key, args.kid)
        _self_check(envelope, private_key, args.kid)
        digest = _signing.write_output(args.out, envelope, force=args.force)
    except (_signing.ToolError, LeaseError, OSError) as exc:
        print(f"issue_lease: {exc}", file=sys.stderr)
        return 2
    print(f"sha256 {digest}  {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
