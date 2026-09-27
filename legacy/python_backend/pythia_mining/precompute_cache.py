# python_backend/pythia_mining/precompute_cache.py
# Deterministic, atomic, truth-labeled cache layer.
# Doctrine: numpy-only, no random, no heuristics, theorem_proven: False pinned.

import os
import json
import hashlib
import tempfile
from typing import Callable, Tuple, Dict, Any

CACHE_VERSION = "pythia-precompute-v1"
DEFAULT_DIR = os.environ.get("PYTHIA_PRECOMPUTE_DIR", "artifacts/pythia/precompute")
os.makedirs(DEFAULT_DIR, exist_ok=True)


def _write_atomic(path: str, data: Dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def geometry_version_hash(
    phi: float,
    lucas15: int,
    adjacency_thresholds: Dict[str, float],
) -> str:
    h = hashlib.sha256()
    h.update(CACHE_VERSION.encode("utf-8"))
    h.update(repr(phi).encode("utf-8"))
    h.update(str(int(lucas15)).encode("utf-8"))
    for k in sorted(adjacency_thresholds.keys()):
        h.update(f"{k}:{adjacency_thresholds[k]:.12g}".encode("utf-8"))
    return h.hexdigest()[:32]


def _cache_path_for_version(version_hash: str) -> str:
    return os.path.join(DEFAULT_DIR, f"geometry_{version_hash}.json")


def policy_prior_path() -> str:
    return os.path.join(DEFAULT_DIR, "policy_prior.json")


def resonance_table_path(key: str) -> str:
    return os.path.join(DEFAULT_DIR, f"resonance_{key}.json")


def load_or_build(
    version_hash: str,
    build_fn: Callable[[], Dict[str, Any]],
) -> Tuple[Dict[str, Any], str]:
    path = _cache_path_for_version(version_hash)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            blob = json.load(f)
        if (
            blob.get("version_hash") == version_hash
            and blob.get("truth_label") == "precomputed-geometry"
        ):
            return blob["tables"], "HIT"
    tables = build_fn()
    blob = {
        "version_hash": version_hash,
        "truth_label": "precomputed-geometry",
        "tables": tables,
    }
    _write_atomic(path, blob)
    return tables, "MISS"


def load_policy_prior() -> Dict[str, Any]:
    p = policy_prior_path()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"truth_label": "supposition-prior", "priors": {}}


def persist_policy_prior(prior_blob: Dict[str, Any]) -> None:
    prior_blob["truth_label"] = "supposition-prior"
    _write_atomic(policy_prior_path(), prior_blob)


def load_resonance_table(key: str) -> Tuple[Dict[str, Any], str]:
    p = resonance_table_path(key)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            blob = json.load(f)
        return blob, "HIT"
    return {}, "MISS"


def persist_resonance_table(key: str, table_blob: Dict[str, Any]) -> None:
    table_blob["truth_label"] = "precomputed-resonance"
    _write_atomic(resonance_table_path(key), table_blob)
