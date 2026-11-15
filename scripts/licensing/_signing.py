"""Shared helpers for the vendor-side lease tooling.

These scripts run on HYBA's offline signing workstation only. They are not
part of any distribution and must never be shipped to a participant.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import os
import secrets
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = str(REPO_ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: E402

from chronus.licensing import canonical_bytes  # noqa: E402


class ToolError(Exception):
    """A refusal or failure reported to the operator (exit status 2)."""


def private_key_path(value) -> Path:
    """Resolve the signing-key path and refuse unsafe locations.

    The key must live outside this repository (offline media, an encrypted
    volume or an HSM-backed export path) and, on POSIX systems, must not be
    readable by group or others.
    """
    resolved = Path(value).expanduser().resolve()
    repository = REPO_ROOT.resolve()
    if resolved == repository or repository in resolved.parents:
        raise ToolError(
            f"refusing to use a private key inside the repository tree ({repository}); "
            "keep signing keys on offline media or in an HSM, never in a working copy"
        )
    if not resolved.is_file():
        raise ToolError(f"private key file not found: {resolved}")
    if os.name == "posix":
        mode = stat.S_IMODE(resolved.stat().st_mode)
        if mode & 0o077:
            raise ToolError(f"private key {resolved} is accessible to other users (mode {mode:o}); run chmod 600")
    return resolved


def load_private_key(path: Path) -> Ed25519PrivateKey:
    data = path.read_bytes()
    try:
        key = serialization.load_pem_private_key(data, password=None)
    except TypeError:
        passphrase = getpass.getpass("Passphrase for the signing key: ").encode("utf-8")
        try:
            key = serialization.load_pem_private_key(data, password=passphrase)
        except (TypeError, ValueError) as exc:
            raise ToolError(f"cannot decrypt the private key: {exc}") from exc
    except ValueError as exc:
        raise ToolError(f"cannot load the private key: {exc}") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ToolError("the private key is not an Ed25519 key")
    return key


def raw_public_key(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def sign_envelope(member: str, document: dict, private_key: Ed25519PrivateKey, kid: str) -> dict:
    signature = private_key.sign(canonical_bytes(document))
    return {
        "alg": "Ed25519",
        "kid": kid,
        member: document,
        "signature": base64.b64encode(signature).decode("ascii"),
    }


def write_output(path: Path, envelope: dict, *, force: bool) -> str:
    """Write the envelope as canonical JSON and return the SHA-256 of the file."""
    data = canonical_bytes(envelope) + b"\n"
    path = Path(path)
    if path.exists() and not force:
        raise ToolError(f"{path} already exists; pass --force to replace it")
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
