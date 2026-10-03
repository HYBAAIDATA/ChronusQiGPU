"""Ovid — metamorphosis owner: folded data is the working form.

Ovid owns encode/decode transformations for the Chronus·Theseus·Ovid triad:

* ``metamorphose`` / ``fold_working`` — bytes → folded working form (Zeckendorf)
* ``materialise`` / ``unfold_egress`` — folded form → bytes (edge only)

Compute and Theseus custody operate on the **folded** representation.
Unfold is egress/materialisation, not the ambient store format.

Not a claim of physical shape-shifting or universe history reversal.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from .encoding import MAX_FOLD_LEN, fold, unfold
from .errors import FoldDomainOverflow, ZeckendorfInvariantError
from .zeckendorf import SparseTopology, apply_zeckendorf_compression


OWNER_ID = "ovid"
CLAIM_BOUNDARY = (
    "Ovid is the metamorphosis owner for HYBA storage: fold produces the "
    "working form; unfold materialises at the edge. Ovid does not reverse "
    "physical history, forge hash preimages, or abolish energy accounting."
)


@dataclass(frozen=True)
class FoldedWorkingForm:
    """Canonical working representation after Ovid metamorphosis."""

    vector: Any  # ZeckendorfVector
    sparse: SparseTopology
    digest: str
    raw_len: int
    folded_units: int
    owner: str = OWNER_ID

    def verify(self) -> bool:
        try:
            if not bool(self.vector.verify()):
                return False
            # folded_units tracks the Zeckendorf vector; sparse is parallel witness
            if self.folded_units != int(self.vector.folded_units):
                return False
            if self.raw_len < 0:
                return False
            return True
        except Exception:
            return False


@dataclass
class Ovid:
    """Production metamorphosis owner — fail-closed fold/unfold."""

    max_fold_len: int = MAX_FOLD_LEN
    owner_id: str = OWNER_ID
    _metrics: Dict[str, int] = field(
        default_factory=lambda: {
            "fold_ok": 0,
            "fold_reject": 0,
            "unfold_ok": 0,
            "unfold_reject": 0,
        }
    )

    @property
    def claim_boundary(self) -> str:
        return CLAIM_BOUNDARY

    def metamorphose(self, payload: bytes) -> FoldedWorkingForm:
        """Fold payload into the working form (primary ingress)."""
        if not isinstance(payload, (bytes, bytearray)):
            self._metrics["fold_reject"] += 1
            raise TypeError("Ovid.metamorphose requires bytes")
        data = bytes(payload)
        try:
            vector = fold(data, max_fold_len=self.max_fold_len)
            sparse = apply_zeckendorf_compression(data)
        except FoldDomainOverflow:
            self._metrics["fold_reject"] += 1
            raise
        except Exception:
            self._metrics["fold_reject"] += 1
            raise
        if not vector.verify():
            self._metrics["fold_reject"] += 1
            raise ZeckendorfInvariantError(
                "folded working form failed verify()"
            )
        digest = hashlib.sha256(data).hexdigest()
        form = FoldedWorkingForm(
            vector=vector,
            sparse=sparse,
            digest=digest,
            raw_len=len(data),
            folded_units=int(vector.folded_units),
        )
        if not form.verify():
            self._metrics["fold_reject"] += 1
            raise ZeckendorfInvariantError(
                "FoldedWorkingForm assembly failed verify()"
            )
        self._metrics["fold_ok"] += 1
        return form

    fold_working = metamorphose

    def materialise(self, form: FoldedWorkingForm) -> bytes:
        """Unfold working form to bytes (egress only)."""
        if not isinstance(form, FoldedWorkingForm):
            self._metrics["unfold_reject"] += 1
            raise TypeError("Ovid.materialise requires FoldedWorkingForm")
        if not form.verify():
            self._metrics["unfold_reject"] += 1
            raise ZeckendorfInvariantError(
                "working form failed verify before unfold"
            )
        try:
            out = unfold(form.vector)
        except Exception:
            self._metrics["unfold_reject"] += 1
            raise
        if len(out) != form.raw_len or hashlib.sha256(out).hexdigest() != form.digest:
            self._metrics["unfold_reject"] += 1
            raise ZeckendorfInvariantError(
                "materialise digest/length mismatch — refusing corrupt working form"
            )
        self._metrics["unfold_ok"] += 1
        return out

    unfold_egress = materialise

    def round_trip(self, payload: bytes) -> Tuple[FoldedWorkingForm, bytes]:
        form = self.metamorphose(payload)
        return form, self.materialise(form)

    def working_digest(self, form: FoldedWorkingForm) -> str:
        return form.digest

    def metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    def health(self) -> Dict[str, Any]:
        return {
            "owner": self.owner_id,
            "status": "ok",
            "max_fold_len": self.max_fold_len,
            "metrics": self.metrics(),
            "claim_boundary": CLAIM_BOUNDARY,
            "production_surface": True,
        }


def open_ovid(*, max_fold_len: int = MAX_FOLD_LEN) -> Ovid:
    return Ovid(max_fold_len=max_fold_len)


__all__ = [
    "OWNER_ID",
    "CLAIM_BOUNDARY",
    "FoldedWorkingForm",
    "Ovid",
    "open_ovid",
]
