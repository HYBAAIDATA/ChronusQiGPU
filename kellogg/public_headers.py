"""Real block headers. The nonce is the one the API returned.

Nothing in this module generates a nonce. A header is 80 bytes as
reconstructed from blockstream's block fields, and the last four are
that block's nonce.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "fixtures" / "btc_headers"
MANIFEST = DATA / "btc_headers_manifest.json"
MAX_TARGET = 0x00000000FFFF0000000000000000000000000000000000000000000000000000


def nbits_to_target(nbits: int) -> int:
    exponent = nbits >> 24
    mantissa = nbits & 0x007FFFFF
    if exponent <= 3:
        return mantissa >> (8 * (3 - exponent))
    return mantissa << (8 * (exponent - 3))


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def load_span(span: dict) -> bytes:
    blob = (DATA / span["file"]).read_bytes()
    if len(blob) != span["bytes"] or len(blob) != span["count"] * 80:
        raise ValueError(f"{span['file']} has a bad length")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != span["sha256"]:
        raise ValueError(f"{span['file']} sha256 does not match the manifest")
    return blob


def survey() -> dict:
    """Check every stored header against the target in its own bits field."""
    manifest = load_manifest()
    checked = 0
    pow_fail = 0
    zero_nonce_meets = 0
    chain_breaks = 0
    bits_runs = []
    nonce_805000 = None
    for span in manifest["spans"]:
        blob = load_span(span)
        first = span["first_height"]
        count = span["count"]
        run_bits = None
        run_start = first
        for index in range(count):
            raw = blob[index * 80 : (index + 1) * 80]
            height = first + index
            bits = int.from_bytes(raw[72:76], "little")
            nonce = int.from_bytes(raw[76:80], "little")
            target = nbits_to_target(bits)
            if int.from_bytes(sha256d(raw), "little") > target:
                pow_fail += 1
            zeroed = raw[:76] + b"\x00\x00\x00\x00"
            if int.from_bytes(sha256d(zeroed), "little") <= target:
                zero_nonce_meets += 1
            if index:
                previous = blob[(index - 1) * 80 : index * 80]
                if sha256d(previous) != raw[4:36]:
                    chain_breaks += 1
            if height == 805000:
                nonce_805000 = nonce
            if bits != run_bits:
                if run_bits is not None:
                    bits_runs.append((run_start, height - 1, run_bits))
                run_bits = bits
                run_start = height
            checked += 1
        bits_runs.append((run_start, first + count - 1, run_bits))
    return {
        "checked": checked,
        "pow_fail": pow_fail,
        "zero_nonce_meets": zero_nonce_meets,
        "chain_breaks": chain_breaks,
        "bits_runs": bits_runs,
        "nonce_805000": nonce_805000,
        "manifest": manifest,
    }


def render() -> str:
    result = survey()
    lines = [
        "# Public API nonces",
        "",
        "Source: `https://blockstream.info/api/blocks/{height}`.",
        "Requested heights 800000 through 809999. The API returned "
        f"{result['checked']} blocks and then HTTP 429.",
        "The nonce in each header is the `nonce` field from that response. "
        "No other nonce was generated.",
        "",
        "| heights | blocks | bits | difficulty |",
        "|---|---|---|---|",
    ]
    for start, end, bits in result["bits_runs"]:
        difficulty = MAX_TARGET / nbits_to_target(bits)
        lines.append(
            f"| {start}-{end} | {end - start + 1} | {bits} | {difficulty} |"
        )
    lines.extend(
        [
            "",
            "Not returned: 800000-804999 and 805010-808369.",
            "",
            "| check | result |",
            "|---|---|",
            f"| sha256d(header) <= target(bits) | {result['checked'] - result['pow_fail']} / {result['checked']} |",
            f"| previous-hash link inside each stored span | {result['chain_breaks']} breaks |",
            f"| nonce replaced by 0 still meets target | {result['zero_nonce_meets']} / {result['checked']} |",
            f"| nonce at height 805000 | {result['nonce_805000']} |",
            "",
            "808416 = 2016 × 401, so the bits change there is the retarget boundary.",
            "Height 805000 sits in the epoch that starts at 804384 = 2016 × 399. "
            "Its difficulty is 55621444139429.57. The work per block at that "
            "difficulty is that many times 2^32 hashes. The nonce that met the "
            "target is the one stored with the header.",
            "",
            "The traversal tables under `reports/traversal_*.md` measure address "
            "steps. They were not used to choose any nonce in this check.",
            "",
        ]
    )
    return "\n".join(lines)
