"""Canonical mathematical physical-storage topology for THESEUS.

The topology binds the existing Aethel Fibonacci, Cassini, Galois-prime and
Vogel/Fermat phyllotaxis machinery into one serialisable address.  The address
is host-independent: absolute filesystem paths are projections derived from the
address and a caller-supplied storage root.

This module deliberately makes no performance, capacity, compression or
distributed-durability claim.  Its contract is deterministic placement,
cryptographic/mathematical verification, durable publication and bounded
primary/replica healing.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .fibonacci import cassini_holds, cassini_quadruple, fibonacci
from .filesystem_paths import filesystem_root
from .phyllotaxis import PhyllotaxisSite, pack_from_anchor, sector_lane
from .primes import GaloisPrimeSubstrate

STORAGE_ADDRESS_SCHEMA = "hyba.theseus-storage-address/v1"
STORAGE_GENERATION = 1
ANCHOR_MODULUS = 90
_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class StorageTopologyError(RuntimeError):
    """A THESEUS physical-placement or integrity contract was violated."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_segment(value: str, name: str) -> str:
    value = str(value)
    if value in {".", ".."} or not _SEGMENT.fullmatch(value):
        raise StorageTopologyError(f"unsafe {name} path segment: {value!r}")
    return value


def _fsync_directory(path: Path) -> None:
    """Best-effort directory fsync where the host supports it."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        try:
            os.fsync(fd)
        except OSError:
            # Windows and some filesystems do not expose directory fsync.
            pass
    finally:
        os.close(fd)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


@dataclass(frozen=True)
class TheseusStorageAddress:
    """Host-independent identity plus deterministic physical projections."""

    content_sha256: str
    fibonacci_index: int
    fibonacci_value: int
    cassini_quadruple: tuple[int, int, int, int]
    prime_key: int
    anchor: int
    phyllotaxis_index: int
    phyllotaxis_ring: int
    phyllotaxis_sector: int
    phyllotaxis_lane: int
    phyllotaxis_radius: float
    phyllotaxis_theta: float
    storage_generation: int
    tenant_id: str
    scope: str
    relative_path: str
    replica_relative_path: str

    @property
    def address_id(self) -> str:
        # Relative paths are derived projections, not identity.  A storage-root
        # relocation therefore cannot change the mathematical/storage identity.
        body = json.dumps(self.identity_dict(), sort_keys=True, separators=(",", ":"))
        return "tsa_" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:40]

    def identity_dict(self) -> dict[str, Any]:
        return {
            "schema": STORAGE_ADDRESS_SCHEMA,
            "content_sha256": self.content_sha256,
            "fibonacci_index": self.fibonacci_index,
            "fibonacci_value": self.fibonacci_value,
            "cassini_quadruple": list(self.cassini_quadruple),
            "prime_key": self.prime_key,
            "anchor": self.anchor,
            "phyllotaxis": {
                "index": self.phyllotaxis_index,
                "ring": self.phyllotaxis_ring,
                "sector": self.phyllotaxis_sector,
                "lane": self.phyllotaxis_lane,
                "radius": self.phyllotaxis_radius,
                "theta": self.phyllotaxis_theta,
            },
            "storage_generation": self.storage_generation,
            "tenant_id": self.tenant_id,
            "scope": self.scope,
        }

    def to_dict(self) -> dict[str, Any]:
        out = self.identity_dict()
        out.update(
            {
                "address_id": self.address_id,
                "relative_path": self.relative_path,
                "replica_relative_path": self.replica_relative_path,
            }
        )
        return out

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TheseusStorageAddress":
        if str(value.get("schema")) != STORAGE_ADDRESS_SCHEMA:
            raise StorageTopologyError("unsupported THESEUS storage-address schema")
        phy = dict(value.get("phyllotaxis") or {})
        try:
            address = cls(
                content_sha256=str(value["content_sha256"]),
                fibonacci_index=int(value["fibonacci_index"]),
                fibonacci_value=int(value["fibonacci_value"]),
                cassini_quadruple=tuple(int(x) for x in value["cassini_quadruple"]),
                prime_key=int(value["prime_key"]),
                anchor=int(value["anchor"]),
                phyllotaxis_index=int(phy["index"]),
                phyllotaxis_ring=int(phy["ring"]),
                phyllotaxis_sector=int(phy["sector"]),
                phyllotaxis_lane=int(phy["lane"]),
                phyllotaxis_radius=float(phy["radius"]),
                phyllotaxis_theta=float(phy["theta"]),
                storage_generation=int(value["storage_generation"]),
                tenant_id=str(value["tenant_id"]),
                scope=str(value["scope"]),
                relative_path=str(value["relative_path"]),
                replica_relative_path=str(value["replica_relative_path"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StorageTopologyError(f"invalid THESEUS storage address: {exc}") from exc
        if value.get("address_id") and str(value["address_id"]) != address.address_id:
            raise StorageTopologyError("THESEUS storage-address identity mismatch")
        return address


_PRIME_KEY_MEMO: "OrderedDict[tuple[int, str, int], int]" = OrderedDict()
_PRIME_KEY_MEMO_SIZE = 4096
_PRIME_KEY_LOCK = threading.Lock()


def _prime_key(anchor: int, digest: str, data: bytes) -> int:
    # Use the existing Galois substrate's exact commit algorithm.  The ephemeral
    # substrate is intentional: placement derivation must not depend on mutable
    # process state, while the canonical key must stay identical to Aethel's
    # implemented prime addressing.
    #
    # The commit is a pure function of the payload. Every caller computes
    # ``digest`` as SHA-256 of ``data`` itself, so a memo keyed on
    # (anchor, digest, length) returns exactly what recomputation would and
    # altered bytes always miss. Reconciliation re-derives every stored
    # file's address on each pass; without this it re-ran the prime commit
    # per file per pass on the mining event loop.
    if _sha(data) != digest:
        return int(GaloisPrimeSubstrate().commit(anchor, digest, data))
    key = (int(anchor), digest, len(data))
    with _PRIME_KEY_LOCK:
        hit = _PRIME_KEY_MEMO.get(key)
        if hit is not None:
            _PRIME_KEY_MEMO.move_to_end(key)
            return hit
    value = int(GaloisPrimeSubstrate().commit(anchor, digest, data))
    with _PRIME_KEY_LOCK:
        _PRIME_KEY_MEMO[key] = value
        _PRIME_KEY_MEMO.move_to_end(key)
        while len(_PRIME_KEY_MEMO) > _PRIME_KEY_MEMO_SIZE:
            _PRIME_KEY_MEMO.popitem(last=False)
    return value


def derive_storage_address(
    payload: bytes,
    *,
    tenant_id: str,
    scope: str,
    storage_generation: int = STORAGE_GENERATION,
) -> TheseusStorageAddress:
    """Derive the canonical THESEUS address for one immutable byte payload."""
    data = bytes(payload)
    tenant = _safe_segment(tenant_id, "tenant")
    scope_value = _safe_segment(scope, "scope")
    generation = int(storage_generation)
    if generation < 1:
        raise StorageTopologyError("storage_generation must be >= 1")

    digest = _sha(data)
    anchor = int(digest[:16], 16) % ANCHOR_MODULUS
    site: PhyllotaxisSite = pack_from_anchor(anchor, modulus=ANCHOR_MODULUS)
    lane = sector_lane(site)

    # The historical Theseus anchor domain is 0..89.  Shift by one to map it
    # bijectively into AddressSpace's valid positive Fibonacci-index domain.
    fib_index = anchor + 1
    fib_value = fibonacci(fib_index)
    witness = cassini_quadruple(fib_index)
    if not cassini_holds(witness):
        raise StorageTopologyError("Cassini witness derivation failed")
    prime_key = _prime_key(anchor, digest, data)

    components = (
        tenant,
        "theseus",
        f"g{generation:04d}",
        f"ring-{site.ring:04d}",
        f"sector-{site.sector:02d}",
        f"lane-{lane:02d}",
        f"site-{site.index:03d}",
        f"fib-{fib_index:03d}",
        f"prime-{prime_key:016x}",
        scope_value,
        f"{digest}.blk",
    )
    replica_components = (
        tenant,
        "theseus-replica",
        *components[2:],
    )
    return TheseusStorageAddress(
        content_sha256=digest,
        fibonacci_index=fib_index,
        fibonacci_value=fib_value,
        cassini_quadruple=witness,
        prime_key=prime_key,
        anchor=anchor,
        phyllotaxis_index=site.index,
        phyllotaxis_ring=site.ring,
        phyllotaxis_sector=site.sector,
        phyllotaxis_lane=lane,
        phyllotaxis_radius=site.radius,
        phyllotaxis_theta=site.theta,
        storage_generation=generation,
        tenant_id=tenant,
        scope=scope_value,
        relative_path=Path(*components).as_posix(),
        replica_relative_path=Path(*replica_components).as_posix(),
    )


def verify_storage_address(address: TheseusStorageAddress, payload: bytes) -> bool:
    """Re-derive every mathematical and path field; equality is the gate."""
    try:
        expected = derive_storage_address(
            bytes(payload),
            tenant_id=address.tenant_id,
            scope=address.scope,
            storage_generation=address.storage_generation,
        )
    except Exception:
        return False
    return expected == address and expected.address_id == address.address_id


class TheseusPhysicalStore:
    """Durable primary/replica block store controlled by mathematical address."""

    def __init__(self, root: str | Path) -> None:
        self.root = filesystem_root(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _path(self, relative: str, tenant_id: str) -> Path:
        candidate = (self.root / relative).resolve()
        root = self.root.resolve()
        try:
            rel = candidate.relative_to(root)
        except ValueError as exc:
            raise StorageTopologyError("storage path escapes configured root") from exc
        if not rel.parts or rel.parts[0] != _safe_segment(tenant_id, "tenant"):
            raise StorageTopologyError("storage path crosses tenant boundary")
        return candidate

    def primary_path(self, address: TheseusStorageAddress) -> Path:
        return self._path(address.relative_path, address.tenant_id)

    def replica_path(self, address: TheseusStorageAddress) -> Path:
        return self._path(address.replica_relative_path, address.tenant_id)

    def journal_path(self, tenant_id: str) -> Path:
        tenant = _safe_segment(tenant_id, "tenant")
        return self._path(f"{tenant}/.theseus/address-journal.jsonl", tenant)

    @staticmethod
    def _path_digest_ok(path: Path, digest: str, size: int | None = None) -> bool:
        try:
            return (
                path.is_file()
                and (size is None or path.stat().st_size == size)
                and _sha(path.read_bytes()) == digest
            )
        except OSError:
            return False

    def _journal_contains(self, path: Path, address_id: str) -> bool:
        if not path.is_file():
            return False
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise StorageTopologyError("THESEUS address journal is corrupt") from exc
                    if row.get("address_id") == address_id and row.get("state") == "COMMITTED":
                        return True
        except OSError as exc:
            raise StorageTopologyError(f"unable to read THESEUS address journal: {exc}") from exc
        return False

    def _append_journal(self, address: TheseusStorageAddress) -> None:
        path = self.journal_path(address.tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self._journal_contains(path, address.address_id):
            return
        entry = {
            "schema": "hyba.theseus-address-journal/v1",
            "state": "COMMITTED",
            "committed_at_ns": time.time_ns(),
            **address.to_dict(),
        }
        line = json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)

    def commit(
        self,
        payload: bytes,
        *,
        tenant_id: str,
        scope: str,
        storage_generation: int = STORAGE_GENERATION,
    ) -> TheseusStorageAddress:
        """Publish primary + replica + durable mathematical address journal.

        No caller-visible custody receipt should be emitted until this method
        returns successfully.
        """
        data = bytes(payload)
        address = derive_storage_address(
            data,
            tenant_id=tenant_id,
            scope=scope,
            storage_generation=storage_generation,
        )
        primary = self.primary_path(address)
        replica = self.replica_path(address)
        with self._lock:
            if not self._path_digest_ok(primary, address.content_sha256, len(data)):
                _atomic_write(primary, data)
            if not self._path_digest_ok(primary, address.content_sha256, len(data)):
                raise StorageTopologyError("primary read-back verification failed")

            if not self._path_digest_ok(replica, address.content_sha256, len(data)):
                _atomic_write(replica, data)
            if not self._path_digest_ok(replica, address.content_sha256, len(data)):
                raise StorageTopologyError("replica read-back verification failed")

            self._append_journal(address)
            if not self._journal_contains(self.journal_path(address.tenant_id), address.address_id):
                raise StorageTopologyError("address journal publication failed")
        return address

    def read(
        self,
        address: TheseusStorageAddress,
        *,
        heal: bool = True,
    ) -> bytes:
        """Read a mathematically verified block; heal primary from replica."""
        primary = self.primary_path(address)
        replica = self.replica_path(address)
        with self._lock:
            if self._path_digest_ok(primary, address.content_sha256):
                data = primary.read_bytes()
                if verify_storage_address(address, data):
                    return data

            if self._path_digest_ok(replica, address.content_sha256):
                data = replica.read_bytes()
                if not verify_storage_address(address, data):
                    raise StorageTopologyError("replica bytes do not match mathematical address")
                if heal:
                    _atomic_write(primary, data)
                    if not self._path_digest_ok(primary, address.content_sha256, len(data)):
                        raise StorageTopologyError("primary heal read-back verification failed")
                return data
        raise StorageTopologyError("no verified primary or replica for THESEUS address")

    @staticmethod
    def _journal_signature(path: Path) -> tuple[Any, ...] | None:
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        content_hash = None
        if os.name == "nt":
            try:
                with open(os.fspath(path), "rb") as stream:
                    content_hash = hashlib.sha256(stream.read()).digest()
            except OSError:
                pass
        return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, content_hash)

    @contextmanager
    def verification_batch(self, tenant_id: str):
        """One journal scan per reconciliation, never a cross-pass trust cache.

        Every object still verifies both physical replicas and its mathematical
        address. A journal replacement, append, truncation or edit invalidates
        the snapshot; no successful batch may outlive a changed journal.
        """
        path = self.journal_path(tenant_id)
        signature = self._journal_signature(path)
        committed: set[str] = set()
        if signature is not None:
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        row = json.loads(line)
                        if not isinstance(row, dict):
                            raise StorageTopologyError("THESEUS address journal row is not an object")
                        if row.get("state") == "COMMITTED":
                            if row.get("tenant_id") != tenant_id:
                                raise StorageTopologyError("cross-tenant address found in journal")
                            address_id = row.get("address_id")
                            if not isinstance(address_id, str) or not address_id:
                                raise StorageTopologyError("THESEUS committed journal row lacks address")
                            committed.add(address_id)
            except (OSError, ValueError) as exc:
                raise StorageTopologyError("THESEUS address journal failed batch replay") from exc

        active = True

        def unchanged() -> None:
            if self._journal_signature(path) != signature:
                raise StorageTopologyError("THESEUS address journal changed during verification batch")

        def verify(address: TheseusStorageAddress, payload: bytes | None = None) -> bool:
            if not active:
                raise StorageTopologyError("THESEUS verification batch is closed")
            unchanged()
            if address.tenant_id != tenant_id or address.address_id not in committed:
                return False
            return self._verify_physical(address, payload)

        unchanged()
        try:
            yield verify
            unchanged()
        finally:
            active = False

    def verify(self, address: TheseusStorageAddress, payload: bytes | None = None) -> bool:
        if not self._journal_contains(self.journal_path(address.tenant_id), address.address_id):
            return False
        return self._verify_physical(address, payload)

    def _verify_physical(self, address: TheseusStorageAddress, payload: bytes | None = None) -> bool:
        primary = self.primary_path(address)
        replica = self.replica_path(address)
        if payload is not None and not verify_storage_address(address, bytes(payload)):
            return False
        if not primary.is_file() or not replica.is_file():
            return False
        try:
            p = primary.read_bytes()
            r = replica.read_bytes()
        except OSError:
            return False
        return (
            p == r
            and _sha(p) == address.content_sha256
            and verify_storage_address(address, p)
        )

    def iter_addresses(self, tenant_id: str) -> tuple[TheseusStorageAddress, ...]:
        """Replay committed addresses from the durable mathematical journal."""
        path = self.journal_path(tenant_id)
        if not path.is_file():
            return ()
        out: list[TheseusStorageAddress] = []
        seen: set[str] = set()
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    if row.get("state") != "COMMITTED":
                        continue
                    address = TheseusStorageAddress.from_dict(row)
                except Exception as exc:
                    raise StorageTopologyError("THESEUS address journal failed replay") from exc
                if address.tenant_id != tenant_id:
                    raise StorageTopologyError("cross-tenant address found in journal")
                if address.address_id in seen:
                    continue
                seen.add(address.address_id)
                out.append(address)
        return tuple(out)


__all__ = [
    "ANCHOR_MODULUS",
    "STORAGE_ADDRESS_SCHEMA",
    "STORAGE_GENERATION",
    "StorageTopologyError",
    "TheseusPhysicalStore",
    "TheseusStorageAddress",
    "derive_storage_address",
    "verify_storage_address",
]
