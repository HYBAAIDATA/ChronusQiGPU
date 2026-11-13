"""Hardware fingerprints for lease binding.

A fingerprint is::

    "sha256:" + hex(SHA-256(b"hyba.lease.fp/1|" + provider + b"|" + normalised value))

where ``provider`` is the provider name in ASCII. Leases carry only these
hashes. Raw identifiers stay inside this module: they are never written to a
lease, a log message or the local state file.

Each provider reads one identifier and returns ``None`` when it is not
available (missing file, permission denied, placeholder value); unavailable
identifiers are skipped. The lease's binding policy decides whether the
fingerprints that remain are sufficient, so a skipped identifier can only
reduce what matches. It never widens access.

Note for containers and virtual machines: /etc/machine-id may be absent or
shared between images, and /sys/class/dmi/id/product_uuid is normally readable
by root only. Inside a sealed appliance, bind leases to identifiers the
platform attests (exported to a file and read with FileProvider).
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Iterable, Optional, Protocol, runtime_checkable

__all__ = [
    "FINGERPRINT_DOMAIN",
    "DmiProductUuidProvider",
    "FileProvider",
    "FingerprintProvider",
    "MachineIdProvider",
    "collect_fingerprints",
    "default_providers",
    "fingerprint",
    "is_fingerprint",
]

FINGERPRINT_DOMAIN = b"hyba.lease.fp/1"
MAX_IDENTIFIER_BYTES = 64 * 1024

_FINGERPRINT_RE = re.compile(r"sha256:[0-9a-f]{64}")
_PROVIDER_NAME_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_MACHINE_ID_RE = re.compile(rb"[0-9a-f]{32}")
_UUID_RE = re.compile(rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_PLACEHOLDER_UUIDS = frozenset(
    {
        b"00000000-0000-0000-0000-000000000000",
        b"ffffffff-ffff-ffff-ffff-ffffffffffff",
        b"03000200-0400-0500-0006-000700080009",
    }
)


@runtime_checkable
class FingerprintProvider(Protocol):
    """Reads one hardware identifier.

    ``name`` is a short lowercase label (letters, digits, ".", "_", "-") that
    is hashed into the fingerprint. ``read()`` returns the normalised
    identifier bytes, or ``None`` when the identifier is unavailable.
    """

    name: str

    def read(self) -> Optional[bytes]: ...


def fingerprint(provider: str, value: bytes) -> str:
    """Return the fingerprint of a normalised identifier ``value``."""
    name = _provider_name(provider)
    if not isinstance(value, (bytes, bytearray)) or not value:
        raise ValueError("identifier value must be non-empty bytes")
    digest = hashlib.sha256(FINGERPRINT_DOMAIN + b"|" + name.encode("ascii") + b"|" + bytes(value))
    return "sha256:" + digest.hexdigest()


def is_fingerprint(value) -> bool:
    """True when ``value`` has the form ``sha256:<64 lowercase hex digits>``."""
    return isinstance(value, str) and _FINGERPRINT_RE.fullmatch(value) is not None


def collect_fingerprints(providers: Iterable[FingerprintProvider]) -> frozenset:
    """Fingerprints of every identifier the providers can read; unavailable ones are skipped."""
    found = set()
    for provider in providers:
        value = provider.read()
        if value is None:
            continue
        found.add(fingerprint(provider.name, value))
    return frozenset(found)


def default_providers():
    """The identifiers read when the caller supplies neither fingerprints nor providers."""
    return (MachineIdProvider(), DmiProductUuidProvider())


class MachineIdProvider:
    """systemd machine identifier (32 lowercase hex digits)."""

    name = "machine-id"

    def __init__(self, path="/etc/machine-id"):
        self.path = os.fspath(path)

    def read(self) -> Optional[bytes]:
        data = _read_identifier(self.path)
        if data is None:
            return None
        value = data.strip().lower()
        if _MACHINE_ID_RE.fullmatch(value) is None or value == b"0" * 32:
            return None
        return value


class DmiProductUuidProvider:
    """SMBIOS system UUID; skipped when unreadable (it is usually root-only)."""

    name = "dmi-product-uuid"

    def __init__(self, path="/sys/class/dmi/id/product_uuid"):
        self.path = os.fspath(path)

    def read(self) -> Optional[bytes]:
        data = _read_identifier(self.path)
        if data is None:
            return None
        value = data.strip().lower()
        if _UUID_RE.fullmatch(value) is None or value in _PLACEHOLDER_UUIDS:
            return None
        return value


class FileProvider:
    """Any exported identifier file, for example a TPM endorsement-key public
    key or a GPU UUID list.

    Line endings are normalised to LF and surrounding whitespace is removed.
    With ``sort_lines=True`` the file is treated as an unordered list: blank
    lines are dropped, each line is stripped, duplicates are removed and the
    lines are sorted, so enumeration order does not change the fingerprint.
    """

    def __init__(self, name: str, path, *, sort_lines: bool = False):
        self.name = _provider_name(name)
        self.path = os.fspath(path)
        self.sort_lines = bool(sort_lines)

    def read(self) -> Optional[bytes]:
        data = _read_identifier(self.path)
        if data is None:
            return None
        data = data.replace(b"\r\n", b"\n")
        if self.sort_lines:
            lines = sorted({line.strip() for line in data.split(b"\n") if line.strip()})
            value = b"\n".join(lines)
        else:
            value = data.strip()
        return value or None


def _provider_name(name) -> str:
    if not isinstance(name, str) or _PROVIDER_NAME_RE.fullmatch(name) is None:
        raise ValueError("provider name must be 1-64 characters of a-z, 0-9, '.', '_' or '-'")
    return name


def _read_identifier(path) -> Optional[bytes]:
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_IDENTIFIER_BYTES + 1)
    except OSError:
        return None
    if not data or len(data) > MAX_IDENTIFIER_BYTES:
        return None
    return data
