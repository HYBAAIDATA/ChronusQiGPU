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


__all__ = [
    "EnterpriseCustodyError",
    "AuthorityBoundaryError",
    "UnrecoverableCustodyError",
    "ResourceExhausted",
    "ConcurrencyConflict",
    "SchemaVersionError",
    "AuthenticityError",
    "ReadOnlyModeError",
]
