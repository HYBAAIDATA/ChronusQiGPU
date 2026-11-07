"""Canonical signed 256-bit limb encoding and validation."""

LIMB_BITS = 64
LIMB_MASK = (1 << LIMB_BITS) - 1
MIN_SIGNED_256 = -(1 << 255)
MAX_SIGNED_256 = (1 << 255) - 1


def encode_int256(value: int) -> tuple[int, int, int, int]:
    """Encode an integer as four little-endian two's-complement 64-bit limbs."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("value must be an integer")
    if not MIN_SIGNED_256 <= value <= MAX_SIGNED_256:
        raise OverflowError("value is outside signed 256-bit range")
    unsigned = value % (1 << 256)
    return tuple((unsigned >> (LIMB_BITS * i)) & LIMB_MASK for i in range(4))


def decode_int256(limbs: tuple[int, int, int, int]) -> int:
    """Decode four little-endian two's-complement limbs without truncation."""
    if len(limbs) != 4 or any(
        not isinstance(limb, int) or isinstance(limb, bool) or not 0 <= limb <= LIMB_MASK
        for limb in limbs
    ):
        raise ValueError("limbs must contain four unsigned 64-bit integers")
    value = sum(limb << (LIMB_BITS * i) for i, limb in enumerate(limbs))
    return value - (1 << 256) if value & (1 << 255) else value
