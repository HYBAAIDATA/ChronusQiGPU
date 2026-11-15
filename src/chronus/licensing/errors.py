"""Exceptions raised by the offline lease verifier.

Every failure raises LeaseError or one of its subclasses. Callers must treat
any LeaseError as "not entitled" and refuse the requested operation: the
verifier never returns a partially verified lease.
"""

__all__ = [
    "CapabilityNotLicensed",
    "ClockRollback",
    "HardwareMismatch",
    "LeaseError",
    "LeaseExpired",
    "LeaseNotYetValid",
    "LeaseRevoked",
    "LeaseRollback",
    "MalformedLease",
    "SignatureInvalid",
    "UnknownKey",
]


class LeaseError(Exception):
    """Base class for every lease, trust-store and local-state failure."""


class MalformedLease(LeaseError):
    """A document, envelope or JSON text violates the lease formats."""


class UnknownKey(LeaseError):
    """No usable pinned public key exists for the envelope's key identifier."""


class SignatureInvalid(LeaseError):
    """The Ed25519 signature does not verify under the pinned public key."""


class LeaseNotYetValid(LeaseError):
    """The verification time is before not_before, beyond the allowed clock skew."""


class LeaseExpired(LeaseError):
    """The verification time is at or after not_after, beyond the allowed clock skew."""


class HardwareMismatch(LeaseError):
    """The local hardware fingerprints do not satisfy the lease binding policy."""


class LeaseRevoked(LeaseError):
    """The lease is listed in a verified revocation list or in the local state."""


class LeaseRollback(LeaseError):
    """An older or reused lease serial, or damaged local state, was detected."""


class ClockRollback(LeaseError):
    """The clock is earlier than a time already recorded or attested by a signature."""


class CapabilityNotLicensed(LeaseError):
    """The verified lease does not grant the requested capability."""
