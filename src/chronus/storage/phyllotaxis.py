"""Phyllotaxis addressing: golden-ratio distribution of stored records.

Phyllotaxis in nature packs seeds by successive golden-turn rotations of the
golden ratio conjugate 1/phi**2. The same constant distributes integer keys
uniformly over a fixed lane count: the Knuth multiplicative hash uses
floor(2**64 * (phi - 1)). Vogel's model places record n at radius sqrt(n) and
angle n golden turns; this module assigns each stored record a deterministic
spiral coordinate and a golden-hash lane.

``PhyllotaxisMesh`` is the deterministic key-mapping facade: any key is
hashed to a lane and a golden-angle spiral coordinate with no stored state.
"""

import hashlib
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


def metallic_conjugate_64(m: int) -> int:
    """floor(2**64 * frac(sigma_m)): the m-th metallic fixed-point constant.

    frac(sigma_m) = (sqrt(m^2 + 4) - m) / 2, computed with exact integer
    square roots so no floating point enters the derivation. m = 1 reproduces
    the golden (Knuth) constant 0x9E3779B97F4A7C15.
    """
    if not isinstance(m, int) or isinstance(m, bool) or m < 1:
        raise ValueError("m must be a positive integer")
    from math import isqrt

    scaled_root = isqrt((m * m + 4) << 128)  # floor(sqrt(m^2+4) * 2**64)
    return (scaled_root - (m << 64)) // 2


def metallic_lane(digest: bytes, lane_count: int, m: int) -> int:
    """Map a digest onto a lane using the m-th metallic mean conjugate."""
    if not isinstance(digest, bytes) or not digest:
        raise ValueError("digest must be non-empty bytes")
    if not isinstance(lane_count, int) or isinstance(lane_count, bool) or lane_count < 1:
        raise ValueError("lane_count must be a positive integer")
    key = int.from_bytes(digest[:8], "big")
    product = (key * metallic_conjugate_64(m)) & _MASK64
    return (product * lane_count) >> 64


def golden_angle_hash(key: str | bytes) -> int:
    """Hash a key to a 64-bit fixed-point golden-angle position in [0, 2**64).

    The SHA-256 digest of the key is multiplied by the golden ratio conjugate
    fixed-point constant; the low 64 bits are the key's golden-angle position
    on the storage circle (the fractional part of digest/2**64 golden turns).
    """
    if isinstance(key, str):
        if not key:
            raise ValueError("key must be non-empty")
        key = key.encode("utf-8")
    if not isinstance(key, bytes) or not key:
        raise ValueError("key must be non-empty str or bytes")
    digest = hashlib.sha256(key).digest()
    return (int.from_bytes(digest, "big") * GOLDEN_RATIO_CONJUGATE_64) & _MASK64


class PhyllotaxisMesh:
    """Stateless golden-ratio mesh mapping keys to lanes and spiral coordinates."""

    def __init__(self, lanes: int = 32) -> None:
        if not isinstance(lanes, int) or isinstance(lanes, bool) or lanes < 1:
            raise ValueError("lanes must be a positive integer")
        self.lanes = lanes

    def map_key(self, key: str | bytes) -> tuple[int, dict]:
        """Return ``(lane, coordinate)`` for a key; pure and deterministic."""
        position = golden_angle_hash(key)
        lane = (position * self.lanes) >> 64
        digest = hashlib.sha256(
            key.encode("utf-8") if isinstance(key, str) else key
        ).digest()
        # Second digest slice fixes a deterministic radius ring so the
        # coordinate needs no allocation counter.
        ring = int.from_bytes(digest[8:16], "big") & 0xFFFF
        return lane, {
            "lane": lane,
            "golden_angle_position": position,
            "turn_fraction": [position, 1 << 64],
            "ring": ring,
            "model": "vogel-spiral",
        }

    def map_key_multiscale(
        self, key: str | bytes, silver_lanes: int = 8, bronze_lanes: int = 4
    ) -> dict:
        """Nested metallic hierarchy: golden local lane, silver partition, bronze route.

        Each tier uses its own metallic conjugate, so the tiers are
        algebraically independent lenses over the same key.
        """
        raw = key.encode("utf-8") if isinstance(key, str) else key
        digest = hashlib.sha256(raw).digest()
        lane, coords = self.map_key(key)
        return {
            "golden_lane": lane,
            "silver_partition": metallic_lane(digest, silver_lanes, 2),
            "bronze_route": metallic_lane(digest, bronze_lanes, 3),
            "coordinate": coords,
        }
