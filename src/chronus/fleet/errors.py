# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Exceptions raised by the Chronus iGPU fleet.

Every refusal in the fleet is an exception rather than a silent substitution:
a device route that is absent, a self-test that does not match its known
answer, a tier whose connectors are missing, a scale grant whose signature
does not verify or a receipt that does not verify all stop the operation and
say why. Demand beyond a tier's entitlement is not an error: it is queued
until a signed scale grant covers it (``chronus.fleet.scale``).
"""

from __future__ import annotations

from chronus.backends.lattice import HardwareUnavailableError


class FleetError(Exception):
    """Base class for fleet errors."""


class DeviceUnavailableError(HardwareUnavailableError, FleetError):
    """A requested device route is absent or unusable; the request fails closed.

    Subclasses the repository's HardwareUnavailableError so existing callers
    that already handle missing hardware also handle the fleet's refusals.
    """


class SelfTestFailedError(DeviceUnavailableError):
    """An adapter produced an output whose digest differs from the known answer."""


class KernelError(FleetError, ValueError):
    """A kernel is unknown, has the wrong version or was given invalid input."""


class LatticeError(FleetError, ValueError):
    """A scheduling-lattice configuration is outside the resident rungs."""


class TierGateRejected(FleetError):
    """An operation needs something the current tier does not provide (for example TLS)."""

    def __init__(self, message: str, failures: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.failures = tuple(failures)


class ScaleGrantRejected(TierGateRejected):
    """A scale grant or tier selection is malformed, expired or not signed by the coordinator owner."""


class AuthenticationError(FleetError):
    """A request or response failed fleet-token authentication."""


class TransportError(FleetError):
    """The coordinator could not be reached or answered with an error."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class VerificationError(FleetError):
    """A result, receipt or ledger failed verification."""


class RecoveryError(FleetError):
    """A blind-check recovery could not restore verified results."""


class SignerUnavailableError(FleetError):
    """The ML-DSA-65 signer cannot be loaded; receipts are not issued unsigned."""


class LedgerError(FleetError):
    """The anchor ledger is malformed or could not be appended."""


class JobFailedError(FleetError):
    """A fleet job ended without a verified result."""

    def __init__(self, message: str, job_id: str | None = None) -> None:
        super().__init__(message)
        self.job_id = job_id
