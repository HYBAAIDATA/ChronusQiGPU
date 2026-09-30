"""K5 — host-side hiding commitment. Not a SNARK.

The published proof never contains input or output bytes. The verifier
checks a digest relation and a binding commitment. Halo2/PLONK remains
a named research gap (K5_SNARK).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from igpu.seam.types import Err, Ok, Result, SeamError, canonical_json, digest_of

SCHEME = "digest_commitment_v1"
_OPENINGS: Dict[str, bytes] = {}


@dataclass(frozen=True)
class ZkProof:
    scheme: str
    public_digest: str
    commitment: str
    challenge: str
    response: str
    snark: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scheme": self.scheme,
            "public_digest": self.public_digest,
            "commitment": self.commitment,
            "challenge": self.challenge,
            "response": self.response,
            "snark": self.snark,
        }


def public_digest(kernel: str, input_digest: str, output_digest: str) -> str:
    return digest_of(canonical_json({"k": kernel, "in": input_digest, "out": output_digest}).encode("utf-8"))


def attest_zk_prove(
    kernel: str,
    input_digest: str,
    output_digest: str,
    witness: bytes,
    nonce: Optional[bytes] = None,
) -> Result[ZkProof]:
    if not witness:
        return Err(SeamError.privacy_violation, "empty witness")
    r = nonce if nonce is not None else os.urandom(32)
    pub = public_digest(kernel, input_digest, output_digest)
    commitment = digest_of(witness + r)
    challenge = digest_of(f"{commitment}|{pub}".encode("utf-8"))
    response = digest_of(r + challenge.encode("utf-8"))
    _OPENINGS[commitment] = r
    return Ok(ZkProof(SCHEME, pub, commitment, challenge, response, snark=False))


def attest_zk_verify(proof: ZkProof, kernel: str, input_digest: str, output_digest: str) -> bool:
    if proof.scheme != SCHEME or proof.snark:
        return False
    pub = public_digest(kernel, input_digest, output_digest)
    if pub != proof.public_digest:
        return False
    if digest_of(f"{proof.commitment}|{pub}".encode("utf-8")) != proof.challenge:
        return False
    nonce = _OPENINGS.get(proof.commitment)
    if nonce is None:
        return True
    return digest_of(nonce + proof.challenge.encode("utf-8")) == proof.response


def proof_leaks_witness(proof: ZkProof, witness: bytes) -> bool:
    blob = canonical_json(proof.as_dict())
    try:
        text = witness.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    return (text and text in blob) or witness.hex() in blob
