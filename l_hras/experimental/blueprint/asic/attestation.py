# l_hras/asic/attestation.py

import hashlib
import hmac
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List
from l_hras.experimental.blueprint.asic.types import *
from l_hras.experimental.blueprint.asic.capability import ASICCapability
from l_hras.experimental.blueprint.asic.hash import Job, Share

@dataclass
class AttestationLink:
    subject: str
    issuer: str
    signature: str
    timestamp: str
    chain_root: str

@dataclass
class AethelStore:
    blocks: Dict[str, 'Certificate'] = field(default_factory=dict)
    ledger: Dict[str, str] = field(default_factory=dict)
    receipts: Dict[str, str] = field(default_factory=dict)
    _key: bytes = field(default_factory=lambda: os.urandom(32), repr=False)

    def write(self, cert: 'Certificate') -> str:
        key = hashlib.sha256(cert.digest.encode()).hexdigest()[:16]
        self.blocks[key] = cert
        self.ledger[key] = cert.digest
        self.receipts[key] = hmac.new(
            self._key, f"{key}:{cert.digest}".encode(), hashlib.sha256
        ).hexdigest()
        return key

    def read(self, key: str) -> 'Certificate':
        return self.blocks[key]

    def verify_replay(self, key: str) -> bool:
        cert = self.blocks.get(key)
        expected = self.ledger.get(key)
        receipt = self.receipts.get(key, "")
        valid_receipt = hmac.compare_digest(
            receipt,
            hmac.new(self._key, f"{key}:{expected}".encode(), hashlib.sha256).hexdigest()
        ) if expected is not None else False
        return cert is not None and expected is not None and cert.digest == expected and valid_receipt

def asic_attest(asic: ASICCapability, job: Job, share: Share, cert: 'Certificate') -> 'Result':
    """Attest the share with the certificate."""
    # Compose the attestation
    attestation = AttestationLink(
        subject=share.hash.hex(),
        issuer=asic.device_id,
        signature=f"sig_{asic.device_id}",
        timestamp=str(time.time()),
        chain_root=cert.digest,
    )

    # Write to Aethel
    key = asic.aethel_store.write(cert)

    # Verify the write
    read_back = asic.aethel_store.read(key)
    if read_back.digest != cert.digest:
        return Err(ASICError.AETHEL_WRITE_FAILURE)

    return Ok({
        "attestation": attestation,
        "aethel_key": key,
    })

# Executable invariant catalogue; tests determine each outcome.
INVARIANTS = {
    'ASIC_A1': 'Every share is attested.',
    'ASIC_A2': 'Every certificate is written to Aethel.',
    'ASIC_A3': 'Forgery of the certificate fails replay.',
    'ASIC_A4': 'Forgery of the ledger fails replay.',
    'ASIC_A5': 'Forgery of both fails replay.',
}
