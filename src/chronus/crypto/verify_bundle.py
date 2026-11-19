"""Independent public-key-only dual-signature receipt verifier."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from chronus.crypto.signers import verify

def check(bundle: dict, public_keys: dict) -> None:
    message = bytes.fromhex(bundle["message_hex"])
    inner = bytes.fromhex(bundle["signatures"]["Ed25519"])
    outer = bytes.fromhex(bundle["signatures"]["ML-DSA-65"])
    verify("Ed25519", bytes.fromhex(public_keys["Ed25519"]), message, inner)
    envelope = hashlib.sha256(b"CHRONUS-V2-OUTER-v1\0" + message + inner).digest()
    verify("ML-DSA-65", bytes.fromhex(public_keys["ML-DSA-65"]), envelope, outer)

def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(prog="chronus-verify-bundle")
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--public-keys", required=True)
    args=parser.parse_args(argv)
    try:
        check(json.loads(Path(args.bundle).read_text()), json.loads(Path(args.public_keys).read_text()))
    except Exception as exc:
        print(f"INVALID_OR_UNAVAILABLE: {type(exc).__name__}: {exc}")
        return 1
    print("VALID")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
