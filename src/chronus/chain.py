"""Dual-signature receipt chains with strict replay verification."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from typing import Any
from chronus.canon import canonical_bytes
from chronus.crypto.signers import DualSigner, SignerUnavailable, verify

GENESIS="00"*32

class ChainBroken(Exception):
    pass

def unsigned(receipt: dict[str, Any]) -> bytes:
    return canonical_bytes({k:v for k,v in receipt.items() if k!="signatures"})

def receipt_hash(receipt: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(receipt)).hexdigest()

@dataclass(frozen=True)
class Chain:
    signer: DualSigner

    @staticmethod
    def unsigned(receipt: dict[str, Any]) -> bytes:
        return unsigned(receipt)

    def seal(self, seq: int, prev_hash: str, payload: dict[str, Any]) -> dict[str, Any]:
        if type(seq) is not int or seq<0 or len(prev_hash)!=64:
            raise ValueError("invalid sequence or predecessor")
        body={"schema":"chronus.receipt/2","seq":seq,"prev_hash":prev_hash,"payload":payload}
        body["signatures"]={alg:sig.hex() for alg,sig in self.signer.sign(unsigned(body)).items()}
        return body

def verify_chain(receipts: list[dict[str, Any]], inner_pk: bytes, outer_pk: bytes) -> None:
    if not receipts:
        raise ChainBroken("empty chain")
    previous=GENESIS
    for i, receipt in enumerate(receipts):
        if type(receipt) is not dict or receipt.get("schema")!="chronus.receipt/2":
            raise ChainBroken(f"schema invalid at {i}")
        if receipt.get("seq")!=i:
            raise ChainBroken(f"seq gap at {i}")
        if receipt.get("prev_hash")!=previous:
            raise ChainBroken(f"prev_hash mismatch at {i}")
        sigs=receipt.get("signatures")
        if type(sigs) is not dict:
            raise ChainBroken(f"missing signatures at {i}")
        if "ML-DSA-65" not in sigs:
            raise SignerUnavailable(f"receipt {i} lacks ML-DSA-65")
        if "Ed25519" not in sigs:
            raise ChainBroken(f"receipt {i} lacks Ed25519")
        try:
            message=unsigned(receipt)
            inner=bytes.fromhex(sigs["Ed25519"])
            outer=bytes.fromhex(sigs["ML-DSA-65"])
            verify("Ed25519",inner_pk,message,inner)
            envelope=hashlib.sha256(b"CHRONUS-V2-OUTER-v1\0"+message+inner).digest()
            verify("ML-DSA-65",outer_pk,envelope,outer)
        except SignerUnavailable:
            raise
        except Exception as exc:
            raise ChainBroken(f"signature failure at {i}: {type(exc).__name__}") from exc
        previous=receipt_hash(receipt)
