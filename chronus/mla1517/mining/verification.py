"""Independent verification helpers for observed mining work.

This is the promoted part of the historical winner-rate work: rebuild and
verify an external block header locally before using its nonce as evidence.
It does not infer a mining advantage from geometry or resonance.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Any, Mapping

from .pow import check_pow, compact_target, sha256d


@dataclass(frozen=True)
class BlockVerification:
    valid: bool
    nonce: int | None
    block_id_match: bool
    target_match: bool
    header: bytes | None
    reason: str


def _header_variant(block: Mapping[str, Any], *, reverse_previous: bool,
                    reverse_merkle: bool) -> bytes:
    previous = bytes.fromhex(str(block["previousblockhash"]))
    merkle = bytes.fromhex(str(block["merkle_root"]))
    bits = int(str(block["bits"]), 16) if isinstance(block["bits"], str) else int(block["bits"])
    return (
        struct.pack("<I", int(block["version"]) & 0xFFFFFFFF)
        + (previous[::-1] if reverse_previous else previous)
        + (merkle[::-1] if reverse_merkle else merkle)
        + struct.pack("<III", int(block["timestamp"]) & 0xFFFFFFFF,
                      bits & 0xFFFFFFFF, int(block["nonce"]) & 0xFFFFFFFF)
    )


def verify_block_record(block: Mapping[str, Any]) -> BlockVerification:
    """Verify a supplied block record's header identity and compact target."""
    try:
        target = compact_target(block["bits"])
        matches: list[bytes] = []
        expected_id = str(block["id"]).lower()
        for reverse_previous in (True, False):
            for reverse_merkle in (True, False):
                header = _header_variant(
                    block,
                    reverse_previous=reverse_previous,
                    reverse_merkle=reverse_merkle,
                )
                digest = sha256d(header)
                if digest[::-1].hex() == expected_id:
                    matches.append(header)
        if len(matches) != 1:
            return BlockVerification(False, None, False, False, None,
                                     f"expected one header-id match, found {len(matches)}")
        header = matches[0]
        target_match = check_pow(header, target)
        nonce = int(block["nonce"])
        return BlockVerification(target_match, nonce, True, target_match, header,
                                 "verified" if target_match else "header id matched but target failed")
    except (KeyError, TypeError, ValueError) as exc:
        return BlockVerification(False, None, False, False, None, f"invalid block record: {exc}")
