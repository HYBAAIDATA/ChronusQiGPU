"""Kellogg attestation — Layer 7: proof boundaries and version locks.

Every Kellogg computation can emit a ProofBoundary record declaring which
fields were exact, which crossings were float boundaries, and which
operations were refused as unrepresentable. ``attest`` binds the record to
a canonical digest, the package version lock, a Zeckendorf-11 token, and
a slice of the Cassini ledger — a reproducible certificate with no hidden
state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence, Tuple

from .exact_tensor import canonical_digest
from .scales import cassini_store, zeckendorf_11d

CONSENSUS_AUTHORITY = "double_sha256"


def _current_version() -> str:
    """The package's single version source: ``kellogg.__version__``."""
    import kellogg

    return getattr(kellogg, "__version__", "")


class VersionLockError(RuntimeError):
    """Missing, unparseable, or insufficient Kellogg version — fail closed."""


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
    the float plane — a formal certificate must come from the exact plane.
    """

    exact_fields: Tuple[str, ...] = ("Qsqrt2", "F4", "Zphi")
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
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def attest(
    computation: Mapping[str, Any] | Any,
    *,
    float_boundaries: Sequence[str] = (),
    unrepresentable: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> dict:
    """Bind a computation payload to a ProofBoundary attestation.

    ``computation`` is any JSON-serializable record of what was computed
    (inputs, steps, outputs). The attestation includes the canonical
    digest, the Kellogg version lock, the Zeckendorf-11 token of the
    digest's leading integer bits, and a Cassini ledger slice sized to the
    declared step count.
    """
    payload = computation if isinstance(computation, Mapping) else {"value": computation}
    digest = canonical_digest(payload)
    digest_int = int(digest, 16)
    steps = len(payload.get("steps", ())) if isinstance(payload.get("steps"), list) else 1
    boundary = ProofBoundary(
        float_boundaries=tuple(float_boundaries),
        unrepresentable=tuple(unrepresentable),
        theorem_proven=False,
        notes=tuple(notes),
    )
    return {
        "schema": "kellogg.attestation/v1",
        "boundary": boundary.to_dict(),
        "digest": digest,
        "version_lock": _current_version(),
        "zeckendorf": zeckendorf_11d(digest_int % (1 << 64)),
        "cassini": cassini_store(max(steps, 1)),
    }
