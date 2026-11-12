# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""ML-DSA-65 receipt signing with the existing Chronus signer.

The fleet does not implement a signature scheme. It loads ``MLDSASigner`` from
``chronus/chronus_gpiu-v36.py`` (the FIPS 204 ML-DSA-65 signer that signs v36
receipts through pyca/cryptography and OpenSSL) in the same way
``chronus.core.facade`` loads that module, and refuses to sign if the class is
not the FIPS 204 version or if cryptography lacks ML-DSA. Receipts are never
issued unsigned and never fall back to another algorithm.

Key custody: the fleet is the signer's tenant. Its 32-byte FIPS 204
key-generation seed is created with ``secrets`` on first start and stored in
the coordinator's state directory with mode 0600; only the 1,952-byte public
key leaves the coordinator. There is no KMS or HSM custody here (see
docs/claim-audit.md); a stolen state directory means a stolen signing key.
"""

from __future__ import annotations

import importlib.util
import os
import secrets
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from chronus.fleet.auth import secure_secret_file
from chronus.fleet.canonical import sha256_hex
from chronus.fleet.errors import SignerUnavailableError

SIGNATURE_ALGORITHM = "ML-DSA-65"
SIGNATURE_STANDARD = "FIPS 204"
SIGNER_SOURCE = "chronus/chronus_gpiu-v36.py MLDSASigner (pyca/cryptography, OpenSSL)"
SEED_FILENAME = "coordinator_mldsa65.seed"
V36_FILENAME = "chronus_gpiu-v36.py"
_MODULE_NAME = "chronus._fleet_v36_signer"
PUBLIC_KEY_BYTES = 1952


@lru_cache(maxsize=1)
def load_mldsa_signer() -> Any:
    """The MLDSASigner class from the v36 module, checked to be the FIPS 204 version."""
    try:
        from cryptography.hazmat.primitives.asymmetric import mldsa  # noqa: F401
    except ImportError as exc:
        raise SignerUnavailableError(
            "pyca/cryptography with ML-DSA support (>= 47) is required to sign fleet receipts"
        ) from exc
    import chronus

    path = Path(chronus.__file__).resolve().parent / V36_FILENAME
    if not path.is_file():
        raise SignerUnavailableError(f"{V36_FILENAME} not found next to the chronus package")
    module = sys.modules.get(_MODULE_NAME)
    if module is None:
        spec = importlib.util.spec_from_file_location(_MODULE_NAME, path)
        if spec is None or spec.loader is None:
            raise SignerUnavailableError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[_MODULE_NAME] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(_MODULE_NAME, None)
            raise SignerUnavailableError(f"loading {V36_FILENAME} failed: {exc}") from exc
    signer = getattr(module, "MLDSASigner", None)
    required = ("sign_mldsa", "verify_mldsa", "public_key_bytes")
    if signer is None or getattr(signer, "PREFIX", None) != "mldsa65_" or not all(
        hasattr(signer, name) for name in required
    ):
        raise SignerUnavailableError(
            "the v36 MLDSASigner is not the FIPS 204 ML-DSA-65 version (merged in PR #28)"
        )
    return signer


def key_id(public_key: bytes) -> str:
    return sha256_hex(public_key)


class FleetSigner:
    """Signs with one ML-DSA-65 key per fleet, derived from a stored FIPS 204 seed."""

    def __init__(self, seed: bytes) -> None:
        if not isinstance(seed, (bytes, bytearray)) or len(seed) != 32:
            raise SignerUnavailableError("an ML-DSA-65 key-generation seed is exactly 32 bytes")
        self._signer = load_mldsa_signer()
        self._seed = bytes(seed)
        self.public_key = self._signer.public_key_bytes(self._seed)
        if len(self.public_key) != PUBLIC_KEY_BYTES:
            raise SignerUnavailableError("unexpected ML-DSA-65 public key length")
        self.key_id = key_id(self.public_key)

    @classmethod
    def from_state_dir(cls, state_dir: str | Path) -> "FleetSigner":
        state = Path(state_dir)
        state.mkdir(parents=True, exist_ok=True)
        path = state / SEED_FILENAME
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(secrets.token_bytes(32))
        secure_secret_file(path)
        return cls(path.read_bytes())

    def sign(self, message: bytes) -> str:
        return self._signer.sign_mldsa(self._seed, message)

    def describe(self) -> dict[str, Any]:
        return {
            "algorithm": SIGNATURE_ALGORITHM,
            "standard": SIGNATURE_STANDARD,
            "implementation": SIGNER_SOURCE,
            "key_id": self.key_id,
            "public_key": self.public_key.hex(),
        }


def verify_signature(public_key: bytes, message: bytes, signature: str) -> bool:
    """True only when the ML-DSA-65 signature verifies; any error is a refusal."""
    return bool(load_mldsa_signer().verify_mldsa(bytes(public_key), message, signature))
