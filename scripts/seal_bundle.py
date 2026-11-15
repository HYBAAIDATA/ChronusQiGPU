"""Build independent T2 conformance fixtures; requires ML-DSA backend."""
from __future__ import annotations
import argparse
import hashlib
import json
import ssl
import sys
from pathlib import Path
import cryptography
from chronus.canon import canonical_bytes
from chronus.chain import Chain,GENESIS,receipt_hash
from chronus.crypto.signers import DualSigner,Ed25519Signer,MlDsa65Signer

def build(root:Path)->None:
    if root.exists() and any(root.iterdir()):
        raise ValueError("bundle destination must be empty")
    root.mkdir(parents=True,exist_ok=True)
    signer=DualSigner(Ed25519Signer.generate("t2-inner-ephemeral"),MlDsa65Signer.generate("t2-outer-ephemeral"))
    chain=Chain(signer)
    keys={"Ed25519":signer.inner.public_bytes().hex(),"ML-DSA-65":signer.outer.public_bytes().hex()}
    (root/"public-keys.json").write_bytes(canonical_bytes(keys))
    clean=[]
    previous=GENESIS
    for seq in range(3):
        receipt=chain.seal(seq,previous,{"index":seq,"timestamp":"2026-01-01T00:00:00Z"})
        clean.append(receipt)
        previous=receipt_hash(receipt)
    tampered=[json.loads(canonical_bytes(r)) for r in clean]
    tampered[1]["payload"]["index"]=99
    missing=[json.loads(canonical_bytes(r)) for r in clean]
    del missing[1]["signatures"]["ML-DSA-65"]
    for name,items in (("clean",clean),("tampered",tampered),("ed25519-only",missing)):
        directory=root/"sets"/name
        directory.mkdir(parents=True)
        for index,item in enumerate(items):
            (directory/f"{index:04d}.json").write_bytes(canonical_bytes(item))
    manifest={"schema":"chronus-t2/1","stack":{"python":sys.version.split()[0],"cryptography":cryptography.__version__,"openssl":ssl.OPENSSL_VERSION},"expected":{"clean":0,"tampered":2,"ed25519-only":3},"files":{}}
    for file in sorted(root.rglob("*")):
        if file.is_file():
            manifest["files"][str(file.relative_to(root))]=hashlib.sha256(file.read_bytes()).hexdigest()
    raw=canonical_bytes(manifest)
    (root/"MANIFEST.json").write_bytes(raw)
    (root/"MANIFEST.sig.json").write_bytes(canonical_bytes({alg:sig.hex() for alg,sig in signer.sign(raw).items()}))
    # The generated keypair is ephemeral and NOT an independently pinned T2 identity.
    (root/"UNQUALIFIED_IDENTITY.txt").write_text("Ephemeral demonstration keys; evaluator must independently pin T2 public keys before acceptance.\n")

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    build(a.out)
    print("T2 fixtures created; identity remains UNQUALIFIED until independently pinned")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
