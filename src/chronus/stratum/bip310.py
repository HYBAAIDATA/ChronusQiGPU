"""
Chronus BIP310 Version-Rolling & ExtraNonce Protocol Module.

BIP310 Protocol Standards:
--------------------------
- mining.configure negotiate mask parameter "1fffe000"
- min-bit-count >= 16 bits
- Version rolling replaces bits in nVersion matching negotiated mask
- Submit payload arity:
  * 6 parameters when version rolling active:
    [worker_name, job_id, extranonce2_hex, ntime_hex, nonce_hex, version_bits_hex]
  * 5 parameters when version rolling inactive:
    [worker_name, job_id, extranonce2_hex, ntime_hex, nonce_hex]
"""

from typing import Optional, Tuple

DEFAULT_CLIENT_MASK_HEX: str = "1fffe000"
MIN_BIT_COUNT: int = 16


def get_mining_configure_payload() -> list:
    return ["version-rolling",
            {"version-rolling.mask": DEFAULT_CLIENT_MASK_HEX,
             "version-rolling.min-bit-count": MIN_BIT_COUNT}]


def parse_and_intersect_version_mask(server_mask_hex: str, client_mask_hex: str = DEFAULT_CLIENT_MASK_HEX) -> str:
    """
    Intersects client mask with server mask returned by pool during mining.configure.
    Returning "00000000" means the client refuses version rolling because the negotiated mask is below the BIP310 minimum.
    Returns 8-character hex mask string.
    """
    server_mask = int(server_mask_hex, 16)
    client_mask = int(client_mask_hex, 16)
    intersected = server_mask & client_mask
    if intersected.bit_count() < MIN_BIT_COUNT:
        return "00000000"  # refuse to roll
    return f"{intersected:08x}"


def build_mining_submit_params(
    worker_name: str,
    job_id: str,
    extranonce2_hex: str,
    ntime_hex: str,
    nonce_hex: str,
    version_bits_hex: Optional[str] = None
) -> list:
    base = [worker_name, job_id, extranonce2_hex, ntime_hex, nonce_hex]
    if version_bits_hex is not None:
        return base + [version_bits_hex]
    return base


def apply_version_rolling(base_version_hex_or_int: str | int, pool_mask_hex_or_int: str | int, rolled_bits_int: int) -> Tuple[int, str]:
    """
    BIP310 Version Rolling:
    Constrains rolled bits to pool_mask and applies to base version.
    Returns (final_version_int, version_bits_hex).
    """
    base_ver = int(base_version_hex_or_int, 16) if isinstance(base_version_hex_or_int, str) else base_version_hex_or_int
    mask = int(pool_mask_hex_or_int, 16) if isinstance(pool_mask_hex_or_int, str) else pool_mask_hex_or_int

    masked_bits = rolled_bits_int & mask
    final_version = (base_ver & ~mask) | masked_bits
    version_bits_hex = f"{masked_bits:08x}"

    return final_version, version_bits_hex


def format_extranonce2(counter: int, extranonce2_size: int) -> str:
    """
    Formats a sequential integer ExtraNonce2 counter into an exact hex string
    padded to extranonce2_size * 2 characters.
    """
    if extranonce2_size <= 0:
        raise ValueError(f"ExtraNonce2 size must be positive, got {extranonce2_size}")
    max_val = (1 << (extranonce2_size * 8)) - 1
    if counter > max_val:
        raise ValueError(f"ExtraNonce2 counter {counter} exceeds max value {max_val} for size {extranonce2_size} bytes.")

    return counter.to_bytes(extranonce2_size, byteorder="big").hex()


def compute_shard_version_bits(shard_id: int, total_shards: int, pool_mask: int) -> int:
    """
    Computes a distinct, non-overlapping version_bits offset for a specific shard.
    Prevents duplicate search work across parallel searcher processes.
    """
    if total_shards <= 0:
        raise ValueError("Total shards must be positive.")
    if shard_id < 0 or shard_id >= total_shards:
        raise ValueError(f"Shard ID {shard_id} out of bounds [0, {total_shards-1}]")

    # Shift shard_id into available mask bits
    # Shift by 13 aligns with mask 0x1fffe000
    shifted_bits = (shard_id << 13) & pool_mask
    return shifted_bits
