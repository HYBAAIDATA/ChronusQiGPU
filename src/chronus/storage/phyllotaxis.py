"""Phyllotaxis addressing: golden-ratio distribution of stored records.

Phyllotaxis in nature packs seeds by successive golden-turn rotations of the
golden ratio conjugate 1/phi**2. The same constant distributes integer keys
uniformly over a fixed lane count: the Knuth multiplicative hash uses
floor(2**64 * (phi - 1)). Vogel's model places record n at radius sqrt(n) and
angle n golden turns; this module assigns each stored record a deterministic
spiral coordinate and a golden-hash lane.
"""

from dataclasses import dataclass

# floor(2**64 * (phi - 1)); the golden ratio conjugate in fixed point.
GOLDEN_RATIO_CONJUGATE_64 = 0x9E3779B97F4A7C15
_MASK64 = (1 << 64) - 1
_CONVERGENT_DEPTH = 64


def golden_lane(digest: bytes, lane_count: int) -> int:
    """Map a content digest onto a lane via golden-ratio multiplicative hashing."""
    if not isinstance(digest, bytes) or not digest:
        raise ValueError("digest must be non-empty bytes")
    if not isinstance(lane_count, int) or isinstance(lane_count, bool) or lane_count < 1:
        raise ValueError("lane_count must be a positive integer")
    key = int.from_bytes(digest[:8], "big")
    product = (key * GOLDEN_RATIO_CONJUGATE_64) & _MASK64
    return (product * lane_count) >> 64


@dataclass(frozen=True)
class PhyllotaxisCoordinate:
    """Deterministic spiral position of the n-th stored record (Vogel model)."""

    sequence: int
    golden_turns_numerator: int
    golden_turns_denominator: int
    lane: int

    def to_dict(self) -> dict:
        return {
            "sequence": self.sequence,
            "golden_turns": [self.golden_turns_numerator, self.golden_turns_denominator],
            "lane": self.lane,
            "model": "vogel-spiral",
        }


def phyllotaxis_coordinate(
    sequence: int, digest: bytes, lane_count: int
) -> PhyllotaxisCoordinate:
    """Assign record ``sequence`` its golden-turn angle and golden-hash lane."""
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise ValueError("sequence must be a non-negative integer")
    # Exact rational golden-turn fraction: n / phi**2 mod 1 evaluated with the
    # Fibonacci convergent F_k / F_{k+2} at a fixed depth for determinism.
    fibs = [0, 1]
    while len(fibs) < _CONVERGENT_DEPTH + 4:
        fibs.append(fibs[-1] + fibs[-2])
    numerator = (sequence * fibs[_CONVERGENT_DEPTH]) % fibs[_CONVERGENT_DEPTH + 2]
    return PhyllotaxisCoordinate(
        sequence=sequence,
        golden_turns_numerator=numerator,
        golden_turns_denominator=fibs[_CONVERGENT_DEPTH + 2],
        lane=golden_lane(digest, lane_count),
    )
