from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from .core import cassini, fib_pair, lucas, nth_prime, sha256_json, zeckendorf, zeckendorf_decode


@dataclass(frozen=True)
class MLAObject:
    """The canonical 11D object.

    Carries the legacy constructor fields plus every field of the canonical
    schema: ``object_id, payload_type, exact_state, scale_index, lucas_state,
    pisot_fold, binet_view, fibonacci_pair, zeckendorf_code, prime_address,
    polyhedral_location, transform_state, cassini_seal, residual_boundary,
    lineage, version``. Lossless mode retains the conjugate/residual
    information needed for reconstruction; ``residual_boundary`` is the
    declared bound for that retention.
    """

    payload: Any
    family: str
    scale: int
    sequence_index: int
    fibonacci_pair: tuple[int, int]
    lucas_scale: int
    zeckendorf_mask: int
    prime_index: int
    prime_address: int
    cassini_seal: int
    object_id: str
    schema_version: int = 1
    # --- canonical schema fields -------------------------------------------
    payload_type: str = "json"
    exact_state: tuple[int, int] = (0, 0)
    scale_index: int = 0
    lucas_state: int = 0
    pisot_fold: Any = None
    binet_view: Any = None
    zeckendorf_code: int = 0
    polyhedral_location: int = 0
    transform_state: int = 0
    residual_boundary: Any = 0
    lineage: Any = None
    version: int = 1

    @classmethod
    def create(
        cls, payload: Any, sequence_index: int, scale: int = 15, family: str = "fibonacci"
    ) -> "MLAObject":
        if not isinstance(sequence_index, int) or sequence_index < 1:
            raise ValueError("sequence_index must be >= 1")
        if not isinstance(scale, int) or scale < 1:
            raise ValueError("scale must be >= 1")
        pair = fib_pair(sequence_index)
        mask, _ = zeckendorf(sequence_index)
        fold = _canonical_pisot_fold(sequence_index)
        body = {
            "payload": payload,
            "family": family,
            "scale": scale,
            "sequence_index": sequence_index,
            "fibonacci_pair": pair,
            "lucas_scale": lucas(scale),
            "zeckendorf_mask": mask,
            "prime_index": sequence_index,
            "prime_address": nth_prime(sequence_index),
            "cassini_seal": cassini(sequence_index),
            "schema_version": 1,
            "payload_type": family,
            "exact_state": pair,
            "scale_index": sequence_index,
            "lucas_state": lucas(scale),
            "pisot_fold": fold,
            "binet_view": _canonical_binet_view(sequence_index),
            "zeckendorf_code": mask,
            "polyhedral_location": sequence_index % 20,
            "transform_state": _phyllotaxis_slot(sequence_index),
            "residual_boundary": fold["residual"],
            "lineage": {"created_at_index": sequence_index, "scale": scale},
            "version": 1,
        }
        return cls(**body, object_id=sha256_json(body))

    def validate(self) -> None:
        if self.schema_version != 1 or self.version != self.schema_version:
            raise ValueError("unsupported schema version")
        if self.fibonacci_pair != fib_pair(self.sequence_index):
            raise ValueError("Fibonacci state mismatch")
        if self.exact_state != tuple(self.fibonacci_pair):
            raise ValueError("exact state mismatch")
        if self.lucas_scale != lucas(self.scale) or self.lucas_state != self.lucas_scale:
            raise ValueError("Lucas scale mismatch")
        if self.zeckendorf_mask != zeckendorf(self.sequence_index)[0]:
            raise ValueError("Zeckendorf state mismatch")
        if self.zeckendorf_code != self.zeckendorf_mask:
            raise ValueError("Zeckendorf code mismatch")
        if zeckendorf_decode(self.zeckendorf_mask) != self.sequence_index:
            raise ValueError("Zeckendorf decode mismatch")
        if self.scale_index != self.sequence_index:
            raise ValueError("scale index mismatch")
        if self.prime_address != nth_prime(self.prime_index):
            raise ValueError("prime address mismatch")
        if self.cassini_seal != cassini(self.sequence_index):
            raise ValueError("Cassini seal mismatch")
        if self.polyhedral_location != self.sequence_index % 20:
            raise ValueError("polyhedral location mismatch")
        if self.transform_state != _phyllotaxis_slot(self.sequence_index):
            raise ValueError("transform state mismatch")
        body = asdict(self)
        body.pop("object_id")
        if sha256_json(body) != self.object_id:
            raise ValueError("object hash mismatch")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_pisot_fold(sequence_index: int) -> dict[str, Any]:
    """The lossless Pisot fold record for the canonical object."""
    from .pisot_fold import pisot_fold

    result = pisot_fold(sequence_index, lossless=True)
    residual = result.folded.residual
    return {
        "family": result.folded.family,
        "index": result.folded.index,
        "exactness_status": result.exactness_status,
        "lossless": result.folded.lossless,
        "residual": 0 if residual == 0 else str(residual),
        "cassini_seal": result.cassini_seal,
    }


def _canonical_binet_view(sequence_index: int) -> dict[str, Any]:
    """The algebraic Binet view of the canonical object — declared a view."""
    from .binet_view import binet_exact

    view = binet_exact(sequence_index)
    return {
        "view": "binet",
        "dominant": str(view.dominant),
        "conjugate": str(view.conjugate),
        "residual": str(view.residual),
        "is_exact": view.is_exact,
    }


def _phyllotaxis_slot(sequence_index: int) -> int:
    """Golden-angle slot of the index on the M32 fabric (transform state)."""
    PHI_INVERSE_MOD = 0x9E3779B9  # floor(2^32 / phi^2)-style golden hash
    return (sequence_index * PHI_INVERSE_MOD) & 0xFFFFFFFF
