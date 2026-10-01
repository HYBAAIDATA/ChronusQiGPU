# l_hras/aethel/store.py

import hashlib
from dataclasses import dataclass, field
from typing import Dict
from l_hras.experimental.blueprint.fold.certificate import Certificate

@dataclass
class AethelStore:
    """Fibonacci address space."""
    blocks: Dict[str, Certificate] = field(default_factory=dict)
    ledger: Dict[str, str] = field(default_factory=dict)

    def write(self, cert: Certificate) -> str:
        """Write a certificate."""
        key = hashlib.sha256(cert.digest.encode()).hexdigest()[:16]
        self.blocks[key] = cert
        self.ledger[key] = cert.digest
        return key

    def read(self, key: str) -> Certificate:
        """Read a certificate."""
        return self.blocks[key]

    def verify_replay(self, key: str) -> bool:
        """Verify the certificate replays."""
        cert = self.blocks[key]
        expected = self.ledger[key]
        return cert.digest == expected
