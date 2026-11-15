"""Offline Ed25519 lease verification (defence in depth for the sealed appliance).

Hosted execution is HYBA's default channel and needs no lease. Inside a
sealed appliance the lease records entitlement: which licensee may use which
capabilities, for how long and on which hardware. Verification is offline,
fails closed on every error and makes no network access::

    from chronus.licensing import load_trust_store, verify_lease

    lease = verify_lease(
        envelope_bytes,
        trust_store=load_trust_store(),
        state_path="/var/lib/hyba/lease-state.json",
    )
    lease.require("example-capability")

See docs/distribution/partner-distribution.md for the format, the order of
checks and the limits of what a lease can enforce.
"""

from .canonical import MAX_DOCUMENT_BYTES, canonical_bytes, loads_strict
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
from .fingerprint import (
    DmiProductUuidProvider,
    FileProvider,
    FingerprintProvider,
    MachineIdProvider,
    collect_fingerprints,
    default_providers,
    fingerprint,
    is_fingerprint,
)
from .lease import (
    ALGORITHM,
    DEFAULT_CLOCK_SKEW_SECONDS,
    LEASE_SCHEMA,
    REVOCATIONS_SCHEMA,
    STATE_SCHEMA,
    TRUST_STORE_SCHEMA,
    RevocationList,
    TrustStore,
    VerifiedLease,
    format_timestamp,
    load_trust_store,
    parse_timestamp,
    validate_lease_document,
    validate_revocation_document,
    verify_lease,
    verify_revocations,
)

__all__ = [
    "ALGORITHM",
    "DEFAULT_CLOCK_SKEW_SECONDS",
    "LEASE_SCHEMA",
    "MAX_DOCUMENT_BYTES",
    "REVOCATIONS_SCHEMA",
    "STATE_SCHEMA",
    "TRUST_STORE_SCHEMA",
    "CapabilityNotLicensed",
    "ClockRollback",
    "DmiProductUuidProvider",
    "FileProvider",
    "FingerprintProvider",
    "HardwareMismatch",
    "LeaseError",
    "LeaseExpired",
    "LeaseNotYetValid",
    "LeaseRevoked",
    "LeaseRollback",
    "MachineIdProvider",
    "MalformedLease",
    "RevocationList",
    "SignatureInvalid",
    "TrustStore",
    "UnknownKey",
    "VerifiedLease",
    "canonical_bytes",
    "collect_fingerprints",
    "default_providers",
    "fingerprint",
    "format_timestamp",
    "is_fingerprint",
    "load_trust_store",
    "loads_strict",
    "parse_timestamp",
    "validate_lease_document",
    "validate_revocation_document",
    "verify_lease",
    "verify_revocations",
]
