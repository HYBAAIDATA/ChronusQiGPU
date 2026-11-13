"""Offline verification of HYBA Ed25519-signed leases.

Defence in depth for the sealed appliance: a lease states which licensee may
use which capabilities, until when, and on which hardware. It is an
entitlement and audit control. It cannot stop a party with full control of
the machine from patching the software; hosted execution, confidential
computing and the written licence carry that weight.

Envelope (a JSON object with exactly these members)::

    {"alg": "Ed25519", "kid": "<key id>", "lease": {...}, "signature": "<base64>"}

The signature is Ed25519 over ``canonical_bytes(envelope["lease"])``. A
revocation list uses the same envelope with the member ``"revocations"`` in
place of ``"lease"``; the ``schema`` member inside the signed object keeps the
two document types apart.

Verification order. Each step fails closed by raising a LeaseError subclass;
nothing is returned or recorded unless every step passes:

1. envelope structure and algorithm ........................ MalformedLease
2. pinned key for ``kid`` (an empty trust store fails) ...... UnknownKey
3. Ed25519 signature over the canonical lease .............. SignatureInvalid
4. lease schema ............................................ MalformedLease
5. revocation list, if supplied (steps 1-4 for the list) ... MalformedLease,
   UnknownKey or SignatureInvalid
6. local state integrity, if a state file is used .......... LeaseRollback
7. clock floor: lease issued_at, revocation list issued_at
   and the last recorded verification time ................. ClockRollback
8. lease serial against the highest serial recorded ........ LeaseRollback
9. validity window, allowing ``clock_skew_seconds`` ........ LeaseNotYetValid,
   LeaseExpired
10. revocation (supplied list and recorded revocations) .... LeaseRevoked
11. hardware binding policy ................................ HardwareMismatch
12. state update: highest serial, latest verification time
    and every revoked lease identifier seen so far.

The local state file is tamper-evident only. It carries a digest that exposes
accidental or casual edits, but anyone who controls the machine can delete or
rewrite it consistently, which resets the rollback and clock protection.
Enforcing those properties needs a hardware anchor: a TPM NV monotonic
counter, or a confidential-computing environment (AMD SEV-SNP, Intel TDX)
whose remote attestation gates key release.

This module performs no network access.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import secrets
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .canonical import MAX_DOCUMENT_BYTES, MAX_SAFE_INTEGER, canonical_bytes, loads_strict
from .errors import (
    CapabilityNotLicensed,
    ClockRollback,
    HardwareMismatch,
    LeaseError,
    LeaseExpired,
    LeaseNotYetValid,
    LeaseRevoked,
    LeaseRollback,
    MalformedLease,
    SignatureInvalid,
    UnknownKey,
)
from .fingerprint import collect_fingerprints, default_providers, is_fingerprint

__all__ = [
    "ALGORITHM",
    "DEFAULT_CLOCK_SKEW_SECONDS",
    "LEASE_SCHEMA",
    "REVOCATIONS_SCHEMA",
    "STATE_SCHEMA",
    "TRUST_STORE_SCHEMA",
    "RevocationList",
    "TrustStore",
    "VerifiedLease",
    "format_timestamp",
    "load_trust_store",
    "parse_timestamp",
    "validate_lease_document",
    "validate_revocation_document",
    "verify_lease",
    "verify_revocations",
]

ALGORITHM = "Ed25519"
LEASE_SCHEMA = "hyba.lease/1"
REVOCATIONS_SCHEMA = "hyba.revocations/1"
TRUST_STORE_SCHEMA = "hyba.trust-store/1"
STATE_SCHEMA = "hyba.lease-state/1"
DEFAULT_CLOCK_SKEW_SECONDS = 300
MAX_CLOCK_SKEW_SECONDS = 86400

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_TIME_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z")
_HEX64_RE = re.compile(r"[0-9a-f]{64}")
_LEASE_MEMBERS = frozenset(
    {
        "schema",
        "lease_id",
        "serial",
        "licensee",
        "product",
        "capabilities",
        "not_before",
        "not_after",
        "issued_at",
        "binding",
    }
)
_REVOCATION_MEMBERS = frozenset({"schema", "issued_at", "lease_ids"})
_STATE_MEMBERS = frozenset({"schema", "last_verified_at", "licensees", "revoked", "digest"})
_BINDING_POLICIES = ("all", "any", "threshold")
_MAX_CAPABILITIES = 256
_MAX_FINGERPRINTS = 64
_MAX_REVOKED = 100000
_MAX_LICENSEES = 10000
_MAX_NAME_LENGTH = 256


# --------------------------------------------------------------------------
# Timestamps


def parse_timestamp(value, what="timestamp"):
    """Parse an RFC 3339 UTC timestamp of the form YYYY-MM-DDTHH:MM:SSZ."""
    if not isinstance(value, str):
        raise MalformedLease(f"{what} must be an RFC 3339 UTC timestamp string")
    match = _TIME_RE.fullmatch(value)
    if match is None:
        raise MalformedLease(f"{what} must have the form YYYY-MM-DDTHH:MM:SSZ")
    year, month, day, hour, minute, second = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except ValueError as exc:
        raise MalformedLease(f"{what} is not a valid calendar time") from exc


def format_timestamp(moment):
    """Format an aware datetime as YYYY-MM-DDTHH:MM:SSZ (UTC, whole seconds)."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Trust store


class TrustStore:
    """Pinned Ed25519 public keys by key identifier (kid).

    Keys are raw 32-byte Ed25519 public keys; in JSON they are base64. File
    format: ``{"schema": "hyba.trust-store/1", "keys": {"<kid>": "<base64>"}}``.
    An empty store can be constructed but verifies nothing: every
    verification against it fails closed with UnknownKey. Problems with the
    store itself are reported as UnknownKey so that callers which catch
    LeaseError still refuse.
    """

    __slots__ = ("_keys",)

    def __init__(self, keys=None):
        parsed = {}
        if keys is not None:
            if not isinstance(keys, Mapping):
                raise UnknownKey("trust store keys must map key identifiers to public keys")
            for kid, material in keys.items():
                if not isinstance(kid, str) or _ID_RE.fullmatch(kid) is None:
                    raise UnknownKey(f"trust store key identifier {kid!r} is not valid")
                parsed[kid] = _public_key(kid, material)
        self._keys = parsed

    @classmethod
    def from_json(cls, text):
        try:
            document = loads_strict(text)
        except MalformedLease as exc:
            raise UnknownKey(f"trust store is not valid JSON: {exc}") from exc
        if (
            not isinstance(document, dict)
            or set(document) != {"schema", "keys"}
            or document["schema"] != TRUST_STORE_SCHEMA
        ):
            raise UnknownKey(
                f"trust store must be an object with exactly 'schema' ({TRUST_STORE_SCHEMA!r}) and 'keys'"
            )
        return cls(document["keys"])

    @classmethod
    def from_file(cls, path):
        try:
            with open(path, "rb") as handle:
                data = handle.read(MAX_DOCUMENT_BYTES + 1)
        except OSError as exc:
            raise UnknownKey(f"trust store could not be read: {exc.strerror or exc}") from exc
        return cls.from_json(data)

    def __len__(self):
        return len(self._keys)

    def __contains__(self, kid):
        return kid in self._keys

    @property
    def kids(self):
        return tuple(sorted(self._keys))

    def public_key(self, kid):
        if not self._keys:
            raise UnknownKey("trust store is empty; no lease can be verified")
        key = self._keys.get(kid)
        if key is None:
            raise UnknownKey(f"key identifier {kid!r} is not pinned in the trust store")
        return key

    def __repr__(self):
        return f"TrustStore(kids={list(self.kids)!r})"


def load_trust_store(path=None):
    """Load pinned keys from ``path``, or the trust store embedded in this package.

    The committed trust_store.json is empty; release builds embed the
    production public key (see packaging/partner/README.md). There is
    deliberately no environment-variable override at run time.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trust_store.json")
    return TrustStore.from_file(path)


def _public_key(kid, material):
    if isinstance(material, str):
        raw = _b64decode_canonical(material)
    elif isinstance(material, (bytes, bytearray)):
        raw = bytes(material)
    else:
        raw = None
    if raw is None or len(raw) != 32:
        raise UnknownKey(f"trust store entry {kid!r} is not a raw 32-byte Ed25519 public key")
    try:
        return Ed25519PublicKey.from_public_bytes(raw)
    except ValueError as exc:
        raise UnknownKey(f"trust store entry {kid!r} is not a valid Ed25519 public key") from exc


def _coerce_trust_store(value):
    if isinstance(value, TrustStore):
        return value
    if isinstance(value, Mapping):
        return TrustStore(value)
    raise TypeError("trust_store must be a TrustStore or a mapping of key identifiers to public keys")


def _b64decode_canonical(text):
    if not isinstance(text, str) or not text.isascii():
        return None
    try:
        raw = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        return None
    if base64.b64encode(raw).decode("ascii") != text:
        return None
    return raw


# --------------------------------------------------------------------------
# Envelopes and document schemas


def _open_envelope(envelope, member, trust_store, what):
    if isinstance(envelope, (str, bytes, bytearray, memoryview)):
        document = loads_strict(envelope)
    else:
        document = envelope
    if not isinstance(document, dict):
        raise MalformedLease(f"{what} envelope must be a JSON object")
    expected = {"alg", "kid", member, "signature"}
    if set(document) != expected:
        raise MalformedLease(f"{what} envelope must contain exactly the members {sorted(expected)}")
    if document["alg"] != ALGORITHM:
        raise MalformedLease(f"{what} envelope algorithm must be {ALGORITHM!r}")
    kid = document["kid"]
    if not isinstance(kid, str) or _ID_RE.fullmatch(kid) is None:
        raise MalformedLease(f"{what} envelope kid is not a valid key identifier")
    payload = document[member]
    if not isinstance(payload, dict):
        raise MalformedLease(f"{what} must be a JSON object")
    signature = _b64decode_canonical(document["signature"])
    if signature is None or len(signature) != 64:
        raise MalformedLease(f"{what} signature must be canonical base64 of 64 bytes")
    message = canonical_bytes(payload)
    public_key = trust_store.public_key(kid)
    try:
        public_key.verify(signature, message)
    except InvalidSignature:
        raise SignatureInvalid(f"{what} signature does not verify under key {kid!r}") from None
    return kid, payload, message


def _require_members(document, expected, what):
    present = set(document)
    missing = sorted(expected - present)
    unexpected = sorted(str(name) for name in present - expected)
    if missing or unexpected:
        problems = []
        if missing:
            problems.append(f"missing {missing}")
        if unexpected:
            problems.append(f"unexpected {unexpected}")
        raise MalformedLease(f"{what}: " + "; ".join(problems))


def _identifier(value, what):
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise MalformedLease(f"{what} must be 1-128 characters of A-Z, a-z, 0-9, '.', '_', ':' or '-'")
    return value


def _identifier_list(values, what, minimum, maximum):
    if not isinstance(values, (list, tuple)):
        raise MalformedLease(f"{what} must be an array")
    if not minimum <= len(values) <= maximum:
        raise MalformedLease(f"{what} must have between {minimum} and {maximum} entries")
    items = [_identifier(value, f"{what} entry") for value in values]
    if len(set(items)) != len(items):
        raise MalformedLease(f"{what} must not contain duplicates")
    return frozenset(items)


def _serial(value, what="serial"):
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_SAFE_INTEGER:
        raise MalformedLease(f"{what} must be an integer between 1 and 2**53 - 1")
    return value


class _Lease:
    __slots__ = (
        "lease_id",
        "serial",
        "licensee_id",
        "licensee_name",
        "product",
        "capabilities",
        "not_before",
        "not_after",
        "issued_at",
        "policy",
        "required_matches",
        "fingerprints",
    )


def _parse_lease(payload):
    if not isinstance(payload, dict):
        raise MalformedLease("lease must be a JSON object")
    _require_members(payload, _LEASE_MEMBERS, "lease")
    if payload["schema"] != LEASE_SCHEMA:
        raise MalformedLease(f"lease schema must be {LEASE_SCHEMA!r}")
    lease = _Lease()
    lease.lease_id = _identifier(payload["lease_id"], "lease_id")
    lease.serial = _serial(payload["serial"])
    licensee = payload["licensee"]
    if not isinstance(licensee, dict):
        raise MalformedLease("licensee must be an object")
    _require_members(licensee, {"id", "name"}, "licensee")
    lease.licensee_id = _identifier(licensee["id"], "licensee.id")
    name = licensee["name"]
    if (
        not isinstance(name, str)
        or not name
        or len(name) > _MAX_NAME_LENGTH
        or not name.isprintable()
    ):
        raise MalformedLease(f"licensee.name must be 1-{_MAX_NAME_LENGTH} printable characters")
    lease.licensee_name = name
    lease.product = _identifier(payload["product"], "product")
    lease.capabilities = _identifier_list(payload["capabilities"], "capabilities", 1, _MAX_CAPABILITIES)
    lease.not_before = parse_timestamp(payload["not_before"], "not_before")
    lease.not_after = parse_timestamp(payload["not_after"], "not_after")
    lease.issued_at = parse_timestamp(payload["issued_at"], "issued_at")
    if lease.not_before >= lease.not_after:
        raise MalformedLease("not_before must be earlier than not_after")
    if lease.issued_at >= lease.not_after:
        raise MalformedLease("issued_at must be earlier than not_after")
    lease.policy, lease.required_matches, lease.fingerprints = _parse_binding(payload["binding"])
    return lease


def _parse_binding(binding):
    if not isinstance(binding, dict):
        raise MalformedLease("binding must be an object")
    policy = binding.get("policy")
    if not isinstance(policy, str) or policy not in _BINDING_POLICIES:
        raise MalformedLease("binding.policy must be 'all', 'any' or 'threshold'")
    if policy == "threshold":
        expected = {"policy", "threshold", "fingerprints"}
    else:
        expected = {"policy", "fingerprints"}
    _require_members(binding, expected, "binding")
    values = binding["fingerprints"]
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= _MAX_FINGERPRINTS:
        raise MalformedLease(f"binding.fingerprints must be an array of 1 to {_MAX_FINGERPRINTS} entries")
    for value in values:
        if not is_fingerprint(value):
            raise MalformedLease("binding.fingerprints entries must have the form sha256:<64 lowercase hex digits>")
    fingerprints = frozenset(values)
    if len(fingerprints) != len(values):
        raise MalformedLease("binding.fingerprints must not contain duplicates")
    if policy == "all":
        required = len(fingerprints)
    elif policy == "any":
        required = 1
    else:
        threshold = binding["threshold"]
        if (
            not isinstance(threshold, int)
            or isinstance(threshold, bool)
            or not 1 <= threshold <= len(fingerprints)
        ):
            raise MalformedLease("binding.threshold must be an integer between 1 and the number of fingerprints")
        required = threshold
    return policy, required, fingerprints


def _parse_revocations(payload):
    if not isinstance(payload, dict):
        raise MalformedLease("revocation list must be a JSON object")
    _require_members(payload, _REVOCATION_MEMBERS, "revocation list")
    if payload["schema"] != REVOCATIONS_SCHEMA:
        raise MalformedLease(f"revocation list schema must be {REVOCATIONS_SCHEMA!r}")
    issued_at = parse_timestamp(payload["issued_at"], "revocation list issued_at")
    lease_ids = _identifier_list(payload["lease_ids"], "lease_ids", 0, _MAX_REVOKED)
    return issued_at, lease_ids


def validate_lease_document(document):
    """Check an unsigned lease object against the hyba.lease/1 schema (vendor tooling)."""
    canonical_bytes(document)
    _parse_lease(document)


def validate_revocation_document(document):
    """Check an unsigned revocation object against the hyba.revocations/1 schema."""
    canonical_bytes(document)
    _parse_revocations(document)


# --------------------------------------------------------------------------
# Results


class VerifiedLease:
    """A lease whose signature, schema, rollback state, validity window,
    revocation status and hardware binding were verified at ``verified_at``.

    Instances are read-only. ``require`` re-checks expiry at call time so a
    long-running process stops honouring a lease once it has expired.
    """

    __slots__ = (
        "lease_id",
        "serial",
        "licensee_id",
        "licensee_name",
        "product",
        "capabilities",
        "not_before",
        "not_after",
        "issued_at",
        "binding_policy",
        "kid",
        "lease_sha256",
        "verified_at",
        "clock_skew_seconds",
    )

    def __init__(self, lease, kid, lease_sha256, verified_at, clock_skew_seconds):
        values = (
            ("lease_id", lease.lease_id),
            ("serial", lease.serial),
            ("licensee_id", lease.licensee_id),
            ("licensee_name", lease.licensee_name),
            ("product", lease.product),
            ("capabilities", lease.capabilities),
            ("not_before", lease.not_before),
            ("not_after", lease.not_after),
            ("issued_at", lease.issued_at),
            ("binding_policy", lease.policy),
            ("kid", kid),
            ("lease_sha256", lease_sha256),
            ("verified_at", verified_at),
            ("clock_skew_seconds", clock_skew_seconds),
        )
        for name, value in values:
            object.__setattr__(self, name, value)

    def __setattr__(self, name, value):
        raise AttributeError("VerifiedLease is read-only")

    def __delattr__(self, name):
        raise AttributeError("VerifiedLease is read-only")

    def has(self, capability):
        """True when the lease grants ``capability`` (no expiry check)."""
        return isinstance(capability, str) and capability in self.capabilities

    def require(self, capability, *, now=None):
        """Raise unless the lease is unexpired at ``now`` and grants ``capability``.

        ``now`` defaults to the system clock (UTC).
        """
        moment = _utc(now)
        if moment - timedelta(seconds=self.clock_skew_seconds) >= self.not_after:
            raise LeaseExpired(f"lease {self.lease_id!r} expired at {format_timestamp(self.not_after)}")
        if not self.has(capability):
            raise CapabilityNotLicensed(f"capability {capability!r} is not licensed by lease {self.lease_id!r}")

    def as_dict(self):
        """Audit-friendly summary; contains no hardware identifiers."""
        return {
            "lease_id": self.lease_id,
            "serial": self.serial,
            "licensee": {"id": self.licensee_id, "name": self.licensee_name},
            "product": self.product,
            "capabilities": sorted(self.capabilities),
            "not_before": format_timestamp(self.not_before),
            "not_after": format_timestamp(self.not_after),
            "issued_at": format_timestamp(self.issued_at),
            "binding_policy": self.binding_policy,
            "kid": self.kid,
            "lease_sha256": self.lease_sha256,
            "verified_at": format_timestamp(self.verified_at),
        }

    def __repr__(self):
        return (
            f"VerifiedLease(lease_id={self.lease_id!r}, licensee_id={self.licensee_id!r}, "
            f"product={self.product!r}, serial={self.serial})"
        )


class RevocationList:
    """A verified hyba.revocations/1 document."""

    __slots__ = ("issued_at", "lease_ids", "kid", "sha256")

    def __init__(self, issued_at, lease_ids, kid, sha256):
        object.__setattr__(self, "issued_at", issued_at)
        object.__setattr__(self, "lease_ids", lease_ids)
        object.__setattr__(self, "kid", kid)
        object.__setattr__(self, "sha256", sha256)

    def __setattr__(self, name, value):
        raise AttributeError("RevocationList is read-only")

    def __delattr__(self, name):
        raise AttributeError("RevocationList is read-only")

    def __contains__(self, lease_id):
        return lease_id in self.lease_ids

    def __repr__(self):
        return f"RevocationList(issued_at={format_timestamp(self.issued_at)!r}, entries={len(self.lease_ids)})"


# --------------------------------------------------------------------------
# Local state (tamper-evident only)


def _state_digest(body):
    return "sha256:" + hashlib.sha256(STATE_SCHEMA.encode("ascii") + b"|" + canonical_bytes(body)).hexdigest()


class _LocalState:
    __slots__ = ("path", "last_verified_at", "licensees", "revoked")

    def __init__(self, path, last_verified_at, licensees, revoked):
        self.path = path
        self.last_verified_at = last_verified_at
        self.licensees = licensees
        self.revoked = revoked

    @classmethod
    def load(cls, path):
        path = os.fspath(path)
        try:
            with open(path, "rb") as handle:
                data = handle.read(MAX_DOCUMENT_BYTES + 1)
        except FileNotFoundError:
            return cls(path, None, {}, set())
        except OSError as exc:
            raise LeaseError(f"local lease state could not be read: {exc.strerror or exc}") from exc
        try:
            return cls._from_document(path, loads_strict(data))
        except MalformedLease as exc:
            raise LeaseRollback(f"local lease state is damaged or was modified ({exc}); refusing") from exc

    @classmethod
    def _from_document(cls, path, document):
        if not isinstance(document, dict):
            raise MalformedLease("state must be a JSON object")
        _require_members(document, _STATE_MEMBERS, "state")
        if document["schema"] != STATE_SCHEMA:
            raise MalformedLease("unknown state schema")
        body = {name: value for name, value in document.items() if name != "digest"}
        if document["digest"] != _state_digest(body):
            raise MalformedLease("integrity digest does not match")
        last_verified_at = parse_timestamp(document["last_verified_at"], "last_verified_at")
        licensees = document["licensees"]
        if not isinstance(licensees, dict) or len(licensees) > _MAX_LICENSEES:
            raise MalformedLease("licensees must be an object")
        records = {}
        for licensee_id, record in licensees.items():
            _identifier(licensee_id, "state licensee")
            if not isinstance(record, dict):
                raise MalformedLease("state licensee record must be an object")
            _require_members(record, {"serial", "lease_id", "lease_sha256"}, "state licensee record")
            digest = record["lease_sha256"]
            if not isinstance(digest, str) or _HEX64_RE.fullmatch(digest) is None:
                raise MalformedLease("state lease_sha256 must be 64 lowercase hex digits")
            records[licensee_id] = {
                "serial": _serial(record["serial"], "state serial"),
                "lease_id": _identifier(record["lease_id"], "state lease_id"),
                "lease_sha256": digest,
            }
        revoked = set(_identifier_list(document["revoked"], "state revoked", 0, _MAX_REVOKED))
        return cls(path, last_verified_at, records, revoked)

    def check_serial(self, lease, lease_sha256):
        record = self.licensees.get(lease.licensee_id)
        if record is None:
            return
        if lease.serial < record["serial"]:
            raise LeaseRollback(
                f"lease serial {lease.serial} is older than serial {record['serial']} "
                f"already recorded for licensee {lease.licensee_id!r}"
            )
        if lease.serial == record["serial"] and lease_sha256 != record["lease_sha256"]:
            raise LeaseRollback(
                f"lease serial {lease.serial} was already recorded for a different lease "
                f"of licensee {lease.licensee_id!r}"
            )

    def record(self, lease, lease_sha256, moment):
        record = self.licensees.get(lease.licensee_id)
        if record is None or lease.serial > record["serial"]:
            self.licensees[lease.licensee_id] = {
                "serial": lease.serial,
                "lease_id": lease.lease_id,
                "lease_sha256": lease_sha256,
            }
        if self.last_verified_at is None or moment > self.last_verified_at:
            self.last_verified_at = moment

    def save(self):
        if self.last_verified_at is None:
            raise LeaseError("local lease state has no verification time to record")
        body = {
            "schema": STATE_SCHEMA,
            "last_verified_at": format_timestamp(self.last_verified_at),
            "licensees": self.licensees,
            "revoked": sorted(self.revoked),
        }
        body["digest"] = _state_digest(body)
        data = canonical_bytes(body) + b"\n"
        directory = os.path.dirname(os.path.abspath(self.path))
        temporary = os.path.join(directory, f".{os.path.basename(self.path)}.{secrets.token_hex(8)}.tmp")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with open(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise LeaseError(f"local lease state could not be recorded: {exc.strerror or exc}") from exc


# --------------------------------------------------------------------------
# Verification


def verify_revocations(envelope, *, trust_store):
    """Verify a signed hyba.revocations/1 envelope with the pinned keys."""
    store = _coerce_trust_store(trust_store)
    kid, payload, message = _open_envelope(envelope, "revocations", store, "revocation list")
    issued_at, lease_ids = _parse_revocations(payload)
    return RevocationList(issued_at, lease_ids, kid, hashlib.sha256(message).hexdigest())


def verify_lease(
    envelope,
    *,
    trust_store,
    fingerprints=None,
    providers=None,
    now=None,
    revocations=None,
    state_path=None,
    clock_skew_seconds=DEFAULT_CLOCK_SKEW_SECONDS,
):
    """Verify a signed lease envelope offline and return a VerifiedLease.

    ``envelope`` is the envelope object or its JSON text (str or bytes).
    ``trust_store`` is a TrustStore or a mapping of kid to public key.
    Local hardware is described either by ``fingerprints`` (precomputed
    ``sha256:`` strings) or by ``providers``; with neither, the default
    providers are read. ``now`` is an aware datetime (default: system clock).
    ``revocations`` is an optional signed revocation envelope, verified with
    the same trust store. ``state_path`` enables the rollback and clock
    checks and is updated only after every check passes (and to remember
    revocations).

    Raises a LeaseError subclass on every failure; see the module docstring
    for the order of checks.
    """
    store = _coerce_trust_store(trust_store)
    skew_seconds = _skew_seconds(clock_skew_seconds)
    skew = timedelta(seconds=skew_seconds)
    moment = _utc(now)
    if fingerprints is not None and providers is not None:
        raise TypeError("pass either fingerprints or providers, not both")

    kid, payload, message = _open_envelope(envelope, "lease", store, "lease")
    lease = _parse_lease(payload)
    lease_sha256 = hashlib.sha256(message).hexdigest()

    revocation_list = None
    if revocations is not None:
        revocation_list = verify_revocations(revocations, trust_store=store)

    state = _LocalState.load(state_path) if state_path is not None else None

    floors = [("lease issued_at", lease.issued_at)]
    if revocation_list is not None:
        floors.append(("revocation list issued_at", revocation_list.issued_at))
    if state is not None and state.last_verified_at is not None:
        floors.append(("last recorded verification", state.last_verified_at))
    for label, floor in floors:
        if moment < floor - skew:
            raise ClockRollback(
                f"clock {format_timestamp(moment)} is earlier than the {label} "
                f"{format_timestamp(floor)} beyond the allowed skew"
            )

    if state is not None:
        state.check_serial(lease, lease_sha256)

    if moment < lease.not_before - skew:
        raise LeaseNotYetValid(f"lease {lease.lease_id!r} is not valid before {format_timestamp(lease.not_before)}")
    if moment >= lease.not_after + skew:
        raise LeaseExpired(f"lease {lease.lease_id!r} expired at {format_timestamp(lease.not_after)}")

    listed = revocation_list.lease_ids if revocation_list is not None else frozenset()
    remembered = state.revoked if state is not None else set()
    if lease.lease_id in listed or lease.lease_id in remembered:
        if state is not None and not listed <= state.revoked:
            state.revoked.update(listed)
            if state.last_verified_at is None:
                state.last_verified_at = moment
            state.save()
        raise LeaseRevoked(f"lease {lease.lease_id!r} has been revoked")

    local = _local_fingerprints(fingerprints, providers)
    matched = len(lease.fingerprints & local)
    if matched < lease.required_matches:
        raise HardwareMismatch(
            f"binding policy {lease.policy!r} requires {lease.required_matches} of "
            f"{len(lease.fingerprints)} fingerprints; {matched} matched"
        )

    if state is not None:
        state.revoked.update(listed)
        state.record(lease, lease_sha256, moment)
        state.save()
    return VerifiedLease(lease, kid, lease_sha256, moment, skew_seconds)


def _local_fingerprints(fingerprints, providers):
    if fingerprints is not None:
        if isinstance(fingerprints, (str, bytes)):
            raise TypeError("fingerprints must be an iterable of fingerprint strings")
        values = frozenset(fingerprints)
        for value in values:
            if not is_fingerprint(value):
                raise ValueError("fingerprints must have the form sha256:<64 lowercase hex digits>")
        return values
    return collect_fingerprints(default_providers() if providers is None else providers)


def _utc(now):
    if now is None:
        return datetime.now(timezone.utc)
    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(timezone.utc)


def _skew_seconds(value):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_CLOCK_SKEW_SECONDS:
        raise ValueError(f"clock_skew_seconds must be an integer between 0 and {MAX_CLOCK_SKEW_SECONDS}")
    return value
