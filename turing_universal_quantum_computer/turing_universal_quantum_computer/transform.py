"""OVID representation-transformation consumption for the TURING VQC (WF04).

OVID owns representation transformation (fold/materialise).  TURING consumes
it; it does not fold state itself.  The contract exercised here:

* ``metamorphose(bytes) -> FoldedWorkingForm`` — exact content-addressed fold;
* ``materialise(form) -> bytes`` — digest- and length-verified restore.

Truth rule (WF04): a fold is *claimed exact* only after a digest-verified
materialise roundtrip on the same bytes — metamorphose alone is not evidence
of losslessness, and a folded form is never passed to a backend as if it were
a state.  When the aethel/OVID package is absent the transform is UNAVAILABLE
and the pipeline fails closed rather than substituting a private codec.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "OVID_TRANSFORM_ID",
    "TransformRecord",
    "OvidTransform",
    "ovid_available",
    "open_transform",
]

#: Declared identifier for the transform contract exercised here.
OVID_TRANSFORM_ID = "ovid.metamorphose_fold.v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ovid_available() -> bool:
    try:
        from aethel import ovid as _ovid  # noqa: F401
    except Exception:
        return False
    return True


@dataclass(frozen=True)
class TransformRecord:
    """Evidence for one fold/materialise roundtrip."""

    transform: str
    state: str  # PASS / FAIL / UNAVAILABLE
    raw_len: int
    digest: str
    folded_units: int
    roundtrip_identical: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class OvidTransform:
    """Thin, fail-closed adapter over ``aethel.ovid``.

    Keeps no private fold implementation: every call delegates to OVID and
    returns the OVID objects (``FoldedWorkingForm``) for THESEUS to custodise.
    """

    def __init__(self) -> None:
        from aethel.ovid import open_ovid

        self._ovid = open_ovid()

    def fold_state(self, state_bytes: bytes) -> tuple[Any, TransformRecord]:
        """Fold VQC state bytes; prove exactness by immediate roundtrip.

        Returns ``(folded_form, record)``.  ``record.state`` is PASS only when
        materialise restores the identical bytes (digest + content checked).
        A failed roundtrip raises ``TransformRefuted`` — a corrupt fold is
        never handed onward.
        """
        if not isinstance(state_bytes, (bytes, bytearray)) or not state_bytes:
            raise ValueError("fold_state requires non-empty bytes")
        raw = bytes(state_bytes)
        form = self._ovid.metamorphose(raw)
        restored = self._ovid.materialise(form)
        identical = restored == raw
        record = TransformRecord(
            transform=OVID_TRANSFORM_ID,
            state="PASS" if identical else "REFUTED",
            raw_len=getattr(form, "raw_len", len(raw)),
            digest=getattr(form, "digest", _sha256(raw)),
            folded_units=getattr(form, "folded_units", -1),
            roundtrip_identical=identical,
            reason=(
                "digest-verified roundtrip identical"
                if identical
                else "materialise returned bytes that differ from the fold input"
            ),
        )
        if not identical:
            raise TransformRefuted(
                f"{OVID_TRANSFORM_ID}: roundtrip mismatch on {len(raw)} bytes"
            )
        return form, record

    def materialise_state(self, form: Any, expected_bytes: bytes | None = None) -> bytes:
        """Restore state bytes; digest enforcement is OVID's, and we re-check
        content against ``expected_bytes`` when supplied."""
        restored = self._ovid.materialise(form)
        if expected_bytes is not None and restored != expected_bytes:
            raise TransformRefuted(
                f"{OVID_TRANSFORM_ID}: materialised bytes differ from expected content"
            )
        return restored


class TransformRefuted(RuntimeError):
    """A fold/materialise roundtrip failed verification — fail closed."""


def open_transform() -> OvidTransform:
    """Open the OVID consumption adapter; raises ``OvidUnavailable`` if absent."""
    if not ovid_available():
        raise OvidUnavailable(
            "aethel.ovid is not importable; OVID transform is UNAVAILABLE "
            "on this host (no private substitute is permitted)"
        )
    return OvidTransform()


class OvidUnavailable(RuntimeError):
    """OVID contract cannot be exercised on this host."""
