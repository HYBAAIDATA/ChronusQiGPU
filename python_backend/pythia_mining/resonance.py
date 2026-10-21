# python_backend/pythia_mining/resonance.py
# Deterministic resonance table with persistent cache.
# Keyed by sha256 of face_probs rounded to 6 dp + nonce_range_shape.

import hashlib
from typing import Callable, Tuple, List

from python_backend.pythia_mining.precompute_cache import (
    load_resonance_table,
    persist_resonance_table,
)


def resonance_key(face_probs: List[float], nonce_range_shape: int) -> str:
    proto = ",".join(f"{p:.6f}" for p in face_probs) + f"|shape:{nonce_range_shape}"
    return hashlib.sha256(proto.encode("utf-8")).hexdigest()[:32]


def phi_guided_nonce_search(
    compute_table_fn: Callable[[List[float], int], List[float]],
    face_probs: List[float],
    nonce_range_shape: int,
) -> Tuple[int, str, List[float]]:
    key = resonance_key(face_probs, nonce_range_shape)
    blob, status = load_resonance_table(key)
    if status == "HIT":
        table = blob.get("table", [])
        if not table:
            return 0, "HIT", table
        chosen = int(max(range(len(table)), key=lambda i: table[i]))
        return chosen, "HIT", table
    # MISS: compute deterministically
    table = compute_table_fn(face_probs, nonce_range_shape)
    blob = {
        "version_hash": key,
        "truth_label": "precomputed-resonance",
        "table": table,
        "meta": {"nonce_range_shape": nonce_range_shape},
    }
    persist_resonance_table(key, blob)
    chosen = int(max(range(len(table)), key=lambda i: table[i])) if table else 0
    return chosen, "MISS", table
