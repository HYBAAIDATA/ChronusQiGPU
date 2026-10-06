"""Kellogg attestation — Layer 7: proof boundaries and version locks.

Every Kellogg computation can emit a ProofBoundary record declaring which
fields were exact, which crossings were float boundaries, and which
operations were refused as unrepresentable. attest binds the record to
a canonical computation digest, the package version lock, a Zeckendorf-11
token, a Cassini ledger slice, and a digest of the complete attestation
envelope. verify_attestation replays those bindings fail-closed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence, Tuple

from .exact_tensor import canonical_digest
from .scales import cassini_store, zeckendorf_11d

CONSENSUS_AUTHORITY = "double_sha256"
ATTESTATION_SCHEMA = "kellogg.attestation/v1"
_ATTESTATION_DOMAIN = b"kellogg.attestation.envelope/v1\0"
_EXACT_FIELDS = ("Qsqrt2", "F4", "Zphi")


def _current_version() -> str:
    """The package's single version source: kellogg.__version__."""
    import kellogg

    return getattr(kellogg, "__version__", "")


class VersionLockError(RuntimeError):
    """Missing, unparseable, or insufficient Kellogg version — fail closed."""


class AttestationError(RuntimeError):
    """Malformed, tampered, or semantically invalid Kellogg attestation."""


def _parse_semver(text: str) -> Tuple[int, int, int]:
    parts = str(text).strip().split(".")
    if len(parts) != 3 or any(not p.isdigit() for p in parts):
        raise VersionLockError(f"unparseable semantic version: {text!r}")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def verify_version(expected: str, *, actual: str | None = None) -> bool:
    """Fail-closed version gate: actual must be a valid semver >= expected."""
    current = _current_version() if actual is None else actual
    if not current:
        raise VersionLockError("kellogg version is missing")
    if _parse_semver(current) < _parse_semver(expected):
        raise VersionLockError(
            f"kellogg {current} is below the required floor {expected}"
        )
    return True


@dataclass(frozen=True)
class ProofBoundary:
    """The honest boundary record for one computation.

    theorem_proven defaults to False and is never settable to True from
    this attestation surface. Formal proof evidence must come from its
    dedicated proof system rather than being inferred from tensor execution.
    """

    exact_fields: Tuple[str, ...] = _EXACT_FIELDS
    float_boundaries: Tuple[str, ...] = ()
    unrepresentable: Tuple[str, ...] = ()
    theorem_proven: bool = False
    consensus_authority: str = CONSENSUS_AUTHORITY
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "exact_fields": list(self.exact_fields),
            "float_boundaries": list(self.float_boundaries),
            "unrepresentable": list(self.unrepresentable),
            "theorem_proven": self.theorem_proven,
            "consensus_authority": self.consensus_authority,
            "notes": list(self.notes),
        }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _envelope_digest(unsigned: Mapping[str, Any]) -> str:
    return hashlib.sha256(_ATTESTATION_DOMAIN + _canonical_bytes(unsigned)).hexdigest()


def _step_count(payload: Mapping[str, Any]) -> int:
    steps = payload.get("steps", ())
    return len(steps) if isinstance(steps, list) else 1


def _unsigned_attestation(
    payload: Mapping[str, Any],
    boundary: Mapping[str, Any],
    *,
    version_lock: str,
) -> dict[str, Any]:
    digest = canonical_digest(payload)
    digest_int = int(digest, 16)
    return {
        "schema": ATTESTATION_SCHEMA,
        "boundary": dict(boundary),
        "digest": digest,
        "version_lock": version_lock,
        "zeckendorf": zeckendorf_11d(digest_int % (1 << 64)),
        "cassini": cassini_store(max(_step_count(payload), 1)),
    }


def attest(
    computation: Mapping[str, Any] | Any,
    *,
    float_boundaries: Sequence[str] = (),
    unrepresentable: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> dict:
    """Bind a computation payload to a ProofBoundary attestation.

    computation is any canonical-digest-compatible record of what was
    computed. The returned v1 surface retains its existing schema and fields,
    with attestation_digest added to bind the boundary metadata and all replay
    material to one deterministic envelope.
    """
    payload = computation if isinstance(computation, Mapping) else {"value": computation}
    boundary = ProofBoundary(
        float_boundaries=tuple(str(item) for item in float_boundaries),
        unrepresentable=tuple(str(item) for item in unrepresentable),
        theorem_proven=False,
        notes=tuple(str(item) for item in notes),
    ).to_dict()
    unsigned = _unsigned_attestation(
        payload,
        boundary,
        version_lock=_current_version(),
    )
    return {
        **unsigned,
        "attestation_digest": _envelope_digest(unsigned),
    }


def verify_attestation(
    computation: Mapping[str, Any] | Any,
    attestation: Mapping[str, Any],
    *,
    allow_legacy_unbound: bool = False,
) -> bool:
    """Replay and verify a Kellogg attestation.

    Verification is semantic rather than a shape check: computation digest,
    version lock, Zeckendorf token, Cassini slice, authority/proof boundary,
    and complete envelope digest must agree. Historical v1 records that
    predate attestation_digest can be admitted only explicitly.
    """
    if not isinstance(attestation, Mapping):
        raise AttestationError("attestation must be a mapping")
    if attestation.get("schema") != ATTESTATION_SCHEMA:
        raise AttestationError(
            f"unsupported Kellogg attestation schema {attestation.get('schema')!r}"
        )

    allowed = {
        "schema",
        "boundary",
        "digest",
        "version_lock",
        "zeckendorf",
        "cassini",
        "attestation_digest",
    }
    unknown = sorted(set(attestation) - allowed)
    if unknown:
        raise AttestationError(f"attestation has unknown field(s): {unknown}")

    boundary = attestation.get("boundary")
    if not isinstance(boundary, Mapping):
        raise AttestationError("attestation boundary is missing or malformed")
    boundary_allowed = {
        "exact_fields",
        "float_boundaries",
        "unrepresentable",
        "theorem_proven",
        "consensus_authority",
        "notes",
    }
    unknown_boundary = sorted(set(boundary) - boundary_allowed)
    if unknown_boundary:
        raise AttestationError(
            f"attestation boundary has unknown field(s): {unknown_boundary}"
        )
    if tuple(boundary.get("exact_fields", ())) != _EXACT_FIELDS:
        raise AttestationError("Kellogg exact-field declaration was altered")
    if boundary.get("theorem_proven") is not False:
        raise AttestationError("Kellogg tensor attestation cannot assert theorem_proven")
    if boundary.get("consensus_authority") != CONSENSUS_AUTHORITY:
        raise AttestationError("Kellogg attestation cannot alter consensus authority")
    for name in ("float_boundaries", "unrepresentable", "notes"):
        values = boundary.get(name)
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise AttestationError(f"boundary {name} must be a list of strings")

    payload = computation if isinstance(computation, Mapping) else {"value": computation}
    version_lock = attestation.get("version_lock")
    if not isinstance(version_lock, str) or not version_lock:
        raise AttestationError("attestation version lock is missing")
    try:
        verify_version(version_lock)
    except VersionLockError as exc:
        raise AttestationError(str(exc)) from exc

    expected = _unsigned_attestation(
        payload,
        boundary,
        version_lock=version_lock,
    )
    for field in ("digest", "zeckendorf", "cassini"):
        if attestation.get(field) != expected[field]:
            raise AttestationError(f"Kellogg attestation {field} mismatch")

    bound_digest = attestation.get("attestation_digest")
    if bound_digest is None:
        if not allow_legacy_unbound:
            raise AttestationError(
                "legacy Kellogg attestation lacks the bound envelope digest"
            )
    else:
        if not isinstance(bound_digest, str) or len(bound_digest) != 64:
            raise AttestationError("attestation_digest is not a SHA-256 hex digest")
        try:
            int(bound_digest, 16)
        except ValueError as exc:
            raise AttestationError("attestation_digest is not hexadecimal") from exc
        if bound_digest != _envelope_digest(expected):
            raise AttestationError("Kellogg attestation envelope digest mismatch")

    return True
