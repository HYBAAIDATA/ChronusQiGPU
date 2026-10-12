"""Typed errors for the enterprise custody substrate."""
from __future__ import annotations


class EnterpriseCustodyError(Exception):
    """Base for enterprise custody failures."""


class AuthorityBoundaryError(EnterpriseCustodyError):
    """Cross-owner or non-absorption violation."""


class UnrecoverableCustodyError(EnterpriseCustodyError):
    """No intact replica; heal impossible."""


class ResourceExhausted(EnterpriseCustodyError):
    """Quota exceeded (payload, records, or tenant bytes)."""


class ConcurrencyConflict(EnterpriseCustodyError):
    """Generation or idempotency conflict."""


class SchemaVersionError(EnterpriseCustodyError):
    """Unknown or unsupported format / transform version."""


class AuthenticityError(EnterpriseCustodyError):
    """HMAC authenticity verification failed."""


class ReadOnlyModeError(EnterpriseCustodyError):
    """Mutation attempted while custody is read-only."""


class ConsensusError(EnterpriseCustodyError):
    """Distributed consensus protocol failure."""


class NotLeaderError(ConsensusError):
    """Mutation requires the Raft leader."""


class QuorumLostError(ConsensusError):
    """Majority of nodes unavailable or did not ack commit."""


class RegionFailoverError(EnterpriseCustodyError):
    """Cross-region DR failover/failback/read failure."""


class SoakThresholdError(EnterpriseCustodyError):
    """Hyperscaler soak exceeded failure threshold."""


class CertificationError(EnterpriseCustodyError):
    """HYBA enterprise certification gate error."""


__all__ = [
    "EnterpriseCustodyError",
    "AuthorityBoundaryError",
    "UnrecoverableCustodyError",
    "ResourceExhausted",
    "ConcurrencyConflict",
    "SchemaVersionError",
    "AuthenticityError",
    "ReadOnlyModeError",
    "ConsensusError",
    "NotLeaderError",
    "QuorumLostError",
    "RegionFailoverError",
    "SoakThresholdError",
    "CertificationError",
    "InvalidRecordIdError",
]


class InvalidRecordIdError(EnterpriseCustodyError, KeyError, ValueError):
    """A record id is not a bounded identifier (path fragment, traversal, symlink)."""
