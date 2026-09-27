"""Independent verification for Lucas benchmark artifacts.

This module intentionally does not import ``benchmark_harness``. It re-derives
workload fingerprints, matrix fingerprints, composite fingerprints, and every
measured candidate from serialized evidence only.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

NONCE_WIDTH_BYTES = 8


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(algorithm: str, value: bytes) -> bytes:
    if algorithm == "sha256d":
        return hashlib.sha256(hashlib.sha256(value).digest()).digest()
    return hashlib.new(algorithm, value).digest()


def quadratic_query_bound(search_space: int) -> int:
    root = math.isqrt(search_space)
    return root if root * root == search_space else root + 1


def verify_composite_fingerprint(artifact: dict[str, Any]) -> bool:
    fingerprints = artifact.get("fingerprints")
    if not isinstance(fingerprints, dict):
        return False
    payload = {
        "workload_fingerprint_sha256": fingerprints.get("workload_sha256"),
        "matrix_fingerprint_sha256": fingerprints.get("matrix_sha256"),
        "schema_version": artifact.get("schema_version"),
        "composite_version": artifact.get("composite_version"),
    }
    expected = sha256_hex(canonical_json_bytes(payload))
    return expected == fingerprints.get("composite_sha256")


def verify_run(artifact: dict[str, Any], result: dict[str, Any]) -> bool:
    workload = artifact.get("workload", {})
    public = dict(workload)
    declared_workload_fp = public.pop("fingerprint_sha256", None)
    workload_fp = sha256_hex(canonical_json_bytes(public))
    if workload_fp != declared_workload_fp:
        return False
    if result.get("workload_fingerprint") != workload_fp:
        return False
    if result.get("hash_algorithm") != workload.get("hash_algorithm"):
        return False
    if result.get("matrix_engine_fingerprint") != workload.get("matrix_engine_fingerprint"):
        return False
    if result.get("matrix_manifest") != workload.get("matrix_manifest"):
        return False
    if result.get("dimensions") != workload.get("dimensions"):
        return False
    if result.get("target_prefix_hex") != workload.get("target_prefix_hex"):
        return False

    if result.get("kind") == "modeled":
        return result.get("operations") == quadratic_query_bound(int(workload["search_space"]))
    if result.get("kind") != "measured" or not result.get("solution_found"):
        return False
    nonce = result.get("nonce")
    digest_hex = result.get("digest_hex")
    if not isinstance(nonce, int) or not isinstance(digest_hex, str):
        return False
    if not int(workload["nonce_min"]) <= nonce < int(workload["nonce_max"]):
        return False
    try:
        digest = bytes.fromhex(digest_hex)
        recomputed = _digest(
            workload["hash_algorithm"],
            bytes.fromhex(workload["seed_hex"]) + nonce.to_bytes(NONCE_WIDTH_BYTES, "big"),
        )
    except (ValueError, OverflowError, TypeError):
        return False
    return digest == recomputed and digest.startswith(bytes.fromhex(workload["target_prefix_hex"]))


def verify_artifact(artifact: dict[str, Any]) -> bool:
    claimed = artifact.get("artifact_sha256")
    if not isinstance(claimed, str):
        return False
    body = {key: value for key, value in artifact.items() if key != "artifact_sha256"}
    if sha256_hex(canonical_json_bytes(body)) != claimed:
        return False
    if not verify_composite_fingerprint(artifact):
        return False
    fingerprints = artifact["fingerprints"]
    if fingerprints["workload_sha256"] != artifact["workload"].get("fingerprint_sha256"):
        return False
    for result in artifact.get("results", []):
        if not verify_run(artifact, result):
            return False
    return bool(artifact.get("verification", {}).get("all_verified"))
