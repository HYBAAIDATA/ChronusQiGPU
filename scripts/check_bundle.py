"""Validate T2 manifest, file hashes, dual signatures, positive and negative sets."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from chronus.canon import canonical_bytes
from chronus.crypto.signers import SignerUnavailable,verify
from chronus.chain import verify_chain,ChainBroken

def check(root:Path,keys:dict)->int:
    try:
        raw=(root/"MANIFEST.json").read_bytes()
        manifest=json.loads(raw)
        if canonical_bytes(manifest)!=raw or manifest["schema"]!="chronus-t2/1":
            return 2
        signatures=json.loads((root/"MANIFEST.sig.json").read_text())
        inner=bytes.fromhex(signatures["Ed25519"])
        outer=bytes.fromhex(signatures["ML-DSA-65"])
        verify("Ed25519",bytes.fromhex(keys["Ed25519"]),raw,inner)
        envelope=hashlib.sha256(b"CHRONUS-V2-OUTER-v1\0"+raw+inner).digest()
        verify("ML-DSA-65",bytes.fromhex(keys["ML-DSA-65"]),envelope,outer)
        for name,digest in manifest["files"].items():
            target=(root/name).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                return 2
        if set(manifest["expected"])!={"clean","tampered","ed25519-only"}:
            return 2
        for name,expected in manifest["expected"].items():
            receipts=[json.loads(p.read_text()) for p in sorted((root/"sets"/name).glob("*.json"))]
            try:
                verify_chain(receipts,bytes.fromhex(keys["Ed25519"]),bytes.fromhex(keys["ML-DSA-65"]))
                result=0
            except SignerUnavailable:
                result=3
            except (ChainBroken,ValueError,TypeError,KeyError):
                result=2
            if result!=expected:
                print(f"FAIL {name}: observed {result}, expected {expected}")
                return 2
            print(f"OK {name}: {result}")
        return 0
    except SignerUnavailable:
        return 3
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 2

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("bundle",type=Path)
    p.add_argument("--public-keys",type=Path,required=True,help="Evaluator-controlled pinned public keys, not extracted from bundle")
    a=p.parse_args()
    return check(a.bundle,json.loads(a.public_keys.read_text()))
if __name__=="__main__":
    raise SystemExit(main())
