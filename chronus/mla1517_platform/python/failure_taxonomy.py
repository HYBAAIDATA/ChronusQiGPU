"""Canonical machine-readable failure classes (service constitution §9).

The governance declaration of this enum lives in
``governance/service_fabric.yaml`` (``failure_classes``); the constitution
suite (``tests/test_service_constitution.py``) proves the two sets are
identical, so this module is the runtime mirror — never a second source of
truth.

Every error body the control plane emits carries ``failure_class``.  The
HTTP status remains transport truth; the class is the machine-readable
truth a caller routes on.  ``status_for`` gives each class its default HTTP
status; a route may override the status when its own transport semantics
differ (e.g. a 404 for an unknown path carries ``NOT_FOUND``).
"""

from __future__ import annotations

from enum import Enum
from http import HTTPStatus
from typing import Any


class FailureClass(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORISED = "UNAUTHORISED"
    FORBIDDEN = "FORBIDDEN"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    VERSION_UNSUPPORTED = "VERSION_UNSUPPORTED"
    STALE = "STALE"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"
    CUSTODY_FAILURE = "CUSTODY_FAILURE"
    EXECUTION_FAILURE = "EXECUTION_FAILURE"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    EXTERNAL_REJECT = "EXTERNAL_REJECT"
    RATE_LIMITED = "RATE_LIMITED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"


FAILURE_CLASSES: frozenset[str] = frozenset(cls.value for cls in FailureClass)

_DEFAULT_STATUS: dict[FailureClass, HTTPStatus] = {
    FailureClass.INVALID_REQUEST: HTTPStatus.BAD_REQUEST,
    FailureClass.UNAUTHORISED: HTTPStatus.UNAUTHORIZED,
    FailureClass.FORBIDDEN: HTTPStatus.FORBIDDEN,
    FailureClass.DEPENDENCY_UNAVAILABLE: HTTPStatus.SERVICE_UNAVAILABLE,
    FailureClass.TIMEOUT: HTTPStatus.GATEWAY_TIMEOUT,
    FailureClass.CONTRACT_MISMATCH: HTTPStatus.UNPROCESSABLE_ENTITY,
    FailureClass.VERSION_UNSUPPORTED: HTTPStatus.BAD_REQUEST,
    FailureClass.STALE: HTTPStatus.CONFLICT,
    FailureClass.INTEGRITY_FAILURE: HTTPStatus.INTERNAL_SERVER_ERROR,
    FailureClass.CUSTODY_FAILURE: HTTPStatus.INTERNAL_SERVER_ERROR,
    FailureClass.EXECUTION_FAILURE: HTTPStatus.INTERNAL_SERVER_ERROR,
    FailureClass.VERIFICATION_FAILURE: HTTPStatus.INTERNAL_SERVER_ERROR,
    FailureClass.EXTERNAL_REJECT: HTTPStatus.BAD_GATEWAY,
    FailureClass.RATE_LIMITED: HTTPStatus.TOO_MANY_REQUESTS,
    FailureClass.NOT_CONFIGURED: HTTPStatus.SERVICE_UNAVAILABLE,
    FailureClass.NOT_APPLICABLE: HTTPStatus.BAD_REQUEST,
    FailureClass.INTERNAL_ERROR: HTTPStatus.INTERNAL_SERVER_ERROR,
    FailureClass.NOT_FOUND: HTTPStatus.NOT_FOUND,
}

_STATUS_DEFAULT: dict[int, FailureClass] = {
    int(HTTPStatus.BAD_REQUEST): FailureClass.INVALID_REQUEST,
    int(HTTPStatus.UNAUTHORIZED): FailureClass.UNAUTHORISED,
    int(HTTPStatus.FORBIDDEN): FailureClass.FORBIDDEN,
    int(HTTPStatus.NOT_FOUND): FailureClass.NOT_FOUND,
    int(HTTPStatus.METHOD_NOT_ALLOWED): FailureClass.NOT_APPLICABLE,
    int(HTTPStatus.CONFLICT): FailureClass.NOT_APPLICABLE,
    int(HTTPStatus.REQUEST_ENTITY_TOO_LARGE): FailureClass.INVALID_REQUEST,
    int(HTTPStatus.UNPROCESSABLE_ENTITY): FailureClass.CONTRACT_MISMATCH,
    int(HTTPStatus.TOO_MANY_REQUESTS): FailureClass.RATE_LIMITED,
    int(HTTPStatus.INTERNAL_SERVER_ERROR): FailureClass.INTERNAL_ERROR,
    int(HTTPStatus.BAD_GATEWAY): FailureClass.EXTERNAL_REJECT,
    int(HTTPStatus.SERVICE_UNAVAILABLE): FailureClass.DEPENDENCY_UNAVAILABLE,
    int(HTTPStatus.GATEWAY_TIMEOUT): FailureClass.TIMEOUT,
}


def status_for(failure_class: FailureClass) -> HTTPStatus:
    return _DEFAULT_STATUS[failure_class]


def class_for_status(status: int) -> FailureClass:
    """Best machine class for an HTTP status when the emitter did not
    declare one — used to guarantee the error envelope on pass-through
    bodies (guardian receipts, forwarded verdicts)."""
    return _STATUS_DEFAULT.get(int(status), FailureClass.INTERNAL_ERROR)


def error_payload(
    failure_class: FailureClass,
    *,
    error: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Standard error body: ``failure_class`` first, ``ok: False``."""
    body: dict[str, Any] = {"ok": False, "failure_class": failure_class.value}
    if error is not None:
        body["error"] = error
    body.update(fields)
    return body


def ensure_failure_class(status: int, payload: Any) -> Any:
    """Inject ``failure_class`` into an error body that lacks one.

    Applied at the single response choke point so every error body —
    including forwarded guardian receipts — carries the canonical class.
    """
    if int(status) < 400 or not isinstance(payload, dict):
        return payload
    if "failure_class" not in payload:
        payload = dict(payload)
        payload["failure_class"] = class_for_status(status).value
    return payload
