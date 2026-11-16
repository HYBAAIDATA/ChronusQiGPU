#!/usr/bin/env python3
"""Bounded real-input Chronus benchmark; never generates workload data.

Only explicitly listed, SHA-256-pinned operator-supplied files are accepted.
A successful local integrity result is not production or hardware qualification.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time

import numpy as np
import yaml

from chronus.config import runtime_bounds
from chronus.ovid.transform import OvidTransformService
from chronus.pulvini import fold_verified, unfold_verified
from chronus.tensor.folded_state import ExactFoldState
from chronus.tensor.geodesic import PhiTensorCore
from chronus.triad import ProductionTriad

SCHEMA = "chronus.real-workload/1"
MANIFEST_SCHEMA = "chronus.real-workload-manifest/1"
MAX_BYTES = 16 * 1024 * 1024
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TENSOR_EXTS = {".npy"}
SNAPSHOT_EXTS = {".snapshot", ".state", ".fold", ".checkpoint"}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git_commit() -> str | None:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
        return value if re.fullmatch(r"[0-9a-f]{40,64}", value) else None
    except (OSError, subprocess.CalledProcessError):
        return None


def _latency(samples: list[int]) -> dict:
    if not samples:
        raise ValueError("at least one measured latency is required")
    ordered = sorted(samples)
    return {
        "count": len(ordered),
        "median_ns": int(statistics.median(ordered)),
        "p99_ns": ordered[math.ceil(0.99 * len(ordered)) - 1],
        "total_ns": sum(ordered),
    }


def discover(manifest_path: Path, *, max_bytes: int = MAX_BYTES) -> list[dict]:
    """Read a curated allowlist; a filename alone never proves provenance."""
    if max_bytes < 1 or max_bytes > MAX_BYTES:
        raise ValueError("max_bytes outside bounded policy")
    manifest_path = Path(manifest_path).resolve(strict=True)
    try:
        document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError("invalid YAML source manifest") from exc
    if not isinstance(document, dict) or document.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unsupported data manifest schema")
    entries = document.get("data_sources")
    if not isinstance(entries, list) or not entries:
        raise ValueError("no operator-declared workload files; refusing to generate inputs")
    if len(entries) > 16:
        raise ValueError("no more than 16 sources allowed per bounded run")
    discovered: list[dict] = []
    seen: set[Path] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("data source must be an object")
        raw_path, kind, digest = entry.get("path"), entry.get("kind"), entry.get("sha256")
        source_class = entry.get("source_class")
        if (not isinstance(raw_path, str) or not raw_path or
                kind not in {"tensor", "snapshot"} or
                not isinstance(digest, str) or not SHA256.fullmatch(digest) or
                source_class not in {"OPERATOR_DECLARED_PRODUCTION", "TEST_FIXTURE_NON_PRODUCTION",
                                     "PUBLIC_OBSERVED_DATASET"}):
            raise ValueError("source requires path, kind, full sha256, and explicit source_class")
        path = Path(raw_path)
        if not path.is_absolute():
            path = manifest_path.parent / path
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"source is not a regular non-symlink file: {raw_path}")
        path = path.resolve(strict=True)
        if path in seen:
            raise ValueError(f"duplicate source: {raw_path}")
        seen.add(path)
        if (kind == "tensor" and path.suffix.lower() not in TENSOR_EXTS or
                kind == "snapshot" and path.suffix.lower() not in SNAPSHOT_EXTS):
            raise ValueError(f"no safe registered decoder for {kind}: {path.suffix}")
        size = path.stat().st_size
        custody_max = runtime_bounds()["max_payload_bytes"]
        if not 0 < size <= max_bytes or size + (size % 2) > custody_max:
            raise ValueError(f"source exceeds input or effective OVID/THESEUS custody limit: {path.name}")
        discovered.append({
            "path": path, "kind": kind, "sha256": digest,
            "size_bytes": size, "source_class": source_class,
            "provenance": str(entry.get("provenance") or "UNVERIFIED"),
        })
    return discovered


def _read_verified(source: dict) -> bytes:
    path = source["path"]
    before = path.stat()
    if before.st_size != source["size_bytes"]:
        raise ValueError(f"source size changed: {path.name}")
    payload = path.read_bytes()
    after = path.stat()
    if (len(payload) != source["size_bytes"] or before.st_mtime_ns != after.st_mtime_ns or
            before.st_ino != after.st_ino or sha256(payload) != source["sha256"]):
        raise ValueError(f"source changed or SHA-256 mismatch: {path.name}")
    return payload



def _load_bounded_npy(payload: bytes) -> np.ndarray:
    """Validate an NPY header *before* NumPy can allocate decoded storage."""
    if len(payload) < 10 or payload[:6] != b"\x93NUMPY":
        raise ValueError("invalid NPY magic")
    version = payload[6]
    if version == 1:
        offset, length_bytes = 10, 2
    elif version in (2, 3):
        offset, length_bytes = 12, 4
    else:
        raise ValueError("unsupported NPY version")
    if len(payload) < offset:
        raise ValueError("truncated NPY header")
    header_length = int.from_bytes(payload[8:8 + length_bytes], "little")
    if header_length < 1 or header_length > 4096 or offset + header_length > len(payload):
        raise ValueError("NPY header outside bounded policy")
    encoding = "utf-8" if version == 3 else "latin1"
    try:
        header = ast.literal_eval(payload[offset:offset + header_length].decode(encoding))
    except (ValueError, SyntaxError, UnicodeError, TypeError) as exc:
        raise ValueError("malformed NPY header") from exc
    if not isinstance(header, dict) or set(header) != {"descr", "fortran_order", "shape"}:
        raise ValueError("invalid NPY metadata keys")
    if type(header["fortran_order"]) is not bool:
        raise ValueError("invalid NPY array order")
    shape = header["shape"]
    if not isinstance(shape, tuple) or len(shape) > 8 or any(
            type(dim) is not int or dim < 0 or dim > 1_000_000 for dim in shape):
        raise ValueError("NPY shape outside bounded policy")
    count = math.prod(shape)
    if not 1 <= count <= 1_000_000:
        raise ValueError("NPY element count outside bounded policy")
    try:
        dtype = np.dtype(header["descr"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid NPY dtype") from exc
    if dtype.kind not in "iufc" or dtype.hasobject or dtype.fields is not None:
        raise ValueError("unsafe or unsupported NPY dtype")
    if offset + header_length + count * dtype.itemsize != len(payload):
        raise ValueError("NPY declared shape does not match payload length")
    array = np.load(io.BytesIO(payload), allow_pickle=False)
    if not isinstance(array, np.ndarray) or array.shape != shape or array.dtype != dtype:
        raise ValueError("decoded NPY contract mismatch")
    return array

def _tensor_workload(payload: bytes, *, depth: int) -> dict:
    try:
        array = _load_bounded_npy(payload)
    except (ValueError, TypeError, OSError) as exc:
        raise ValueError("invalid or unsafe NumPy tensor input") from exc
    if not isinstance(array, np.ndarray) or array.dtype.kind not in "iufc":
        raise ValueError("tensor requires a non-object numeric dtype")
    if not 1 <= array.size <= 1_000_000 or not np.all(np.isfinite(array)):
        raise ValueError("tensor outside finite-value/element limits")

    started = time.perf_counter_ns()
    result = PhiTensorCore().execute("add", array, array)
    chronus_ns = time.perf_counter_ns() - started
    started = time.perf_counter_ns()
    reference = np.add(array, array)
    numpy_ns = time.perf_counter_ns() - started
    if not np.array_equal(result["output"], reference):
        raise ValueError("independent NumPy operation mismatch")
    if not np.all(np.isfinite(reference)):
        raise ValueError("non-finite tensor operation output")

    # Exact H4/tensor itinerary is not established for arbitrary NPY inputs.
    # Do not substitute floating-point Euclidean interpolation or claim a
    # geodesic/H4 production measurement.
    geodesic = {
        "status": "UNAVAILABLE",
        "reason": "no verified exact tensor-to-H4 geodesic workload contract",
    }

    started = time.perf_counter_ns()
    state, receipt = fold_verified(array, depth=depth, max_elements=1_000_000)
    fold_ns = time.perf_counter_ns() - started
    started = time.perf_counter_ns()
    restored = unfold_verified(state, receipt=receipt)
    unfold_ns = time.perf_counter_ns() - started
    canonical = np.asarray(array, dtype=np.complex128 if np.iscomplexobj(array) else np.float64)
    if (not np.all(np.isfinite(restored)) or
            not np.allclose(restored, canonical, rtol=1e-12, atol=1e-12)):
        raise ValueError("PULVINI reconstructed tensor exceeds recorded numerical tolerance")
    return {
        "operation": "tensor_reference_add_and_pulvini",
        "shape": list(array.shape), "dtype": str(array.dtype),
        "execution_backend": result["backend"],
        "chronus_add_call_ns": chronus_ns, "numpy_add_call_ns": numpy_ns,
        "addition_exact_match": True,
        "geodesic": geodesic,
        "pulvini": {
            "depth": state.depth, "normalization": state.normalization,
            "fold_ns": fold_ns, "unfold_ns": unfold_ns,
            "input_promoted_bytes": receipt.original_bytes,
            "working_set_bytes": receipt.folded_bytes,
            "kernel_bytes": receipt.kernel_bytes,
            "complete_retained_bytes": receipt.retained_bytes,
            "working_set_ratio": receipt.working_set_ratio,
            "complete_retained_ratio": receipt.retained_state_ratio,
            "relative_reconstruction_error": receipt.relative_reconstruction_error,
            "numerical_reconstruction_verified": True,
            "lossless_bytes_claim": False,
            "net_storage_compression_claim": False,
        },
    }


def _snapshot_workload(payload: bytes) -> dict:
    started = time.perf_counter_ns()
    folded = ExactFoldState.from_bytes(payload)
    fold_ns = time.perf_counter_ns() - started
    windows = ((0, min(64, len(payload))),
               (len(payload) // 2, min(len(payload), len(payload) // 2 + 64)),
               (max(0, len(payload) - 64), len(payload)))
    samples: list[int] = []
    for start, stop in windows:
        t0 = time.perf_counter_ns()
        recovered = folded.unfold_partial(start, stop)
        samples.append(time.perf_counter_ns() - t0)
        if recovered != payload[start:stop]:
            raise ValueError("partial unfold mismatch")
    t0 = time.perf_counter_ns()
    full = folded.unfold()
    full_ns = time.perf_counter_ns() - t0
    if full != payload:
        raise ValueError("snapshot byte-exact roundtrip mismatch")
    return {
        "operation": "exact_snapshot_partial_unfold",
        "original_bytes": len(payload), "folded_bytes": len(folded.folded),
        "fold_ns": fold_ns, "full_unfold_ns": full_ns,
        "partial_read_latency": _latency(samples),
        "byte_exact_roundtrip_verified": True,
        "byte_representation_ratio": folded.byte_ratio,
        "constant_time_complexity_proven": False,
        "net_compression_claim": False,
    }


def run_benchmark(manifest: Path, custody_db: Path, *, depth: int = 4,
                  max_bytes: int = MAX_BYTES, sources: list[dict] | None = None) -> dict:
    """Execute on supplied bytes only; never create or choose inputs."""
    if not 0 <= depth <= 32:
        raise ValueError("depth must be 0..32")
    if sources is None:
        sources = discover(manifest, max_bytes=max_bytes)
    custody_db = Path(custody_db).resolve()
    if custody_db in {source["path"] for source in sources}:
        raise ValueError("custody database must not overwrite a source")
    validated = [(source, _read_verified(source)) for source in sources]
    # Complete all deterministic validation and decoding before opening custody;
    # a bad later asset must never persist data from an earlier asset.
    pending: list[tuple[dict, bytes, dict]] = []
    ovid = OvidTransformService()
    payload_limit = runtime_bounds()["max_payload_bytes"]
    tenant_id = "real-workload-benchmark"
    for source, payload in validated:
        representation = ovid.fold(payload)
        receipt_bytes = json.dumps({
            **representation.envelope(),
            "tenant_id": tenant_id,
            "representation_object_id": sha256(representation.payload),
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(representation.payload) > payload_limit or len(receipt_bytes) > payload_limit:
            raise ValueError("source representation or custody receipt exceeds effective custody limit")
        workload = (_tensor_workload(payload, depth=depth)
                    if source["kind"] == "tensor" else _snapshot_workload(payload))
        pending.append((source, payload, workload))

    custody_db.parent.mkdir(parents=True, exist_ok=True)
    triad = ProductionTriad(str(custody_db))
    results: list[dict] = []
    stored: list[tuple[object, bytes]] = []
    for source, payload, workload in pending:
        t0 = time.perf_counter_ns()
        receipt = triad.put(tenant_id, payload)
        write_ns = time.perf_counter_ns() - t0
        stored.append((receipt, payload))
        results.append({
            "source_id": source["sha256"][:16],
            "source_sha256": source["sha256"],
            "source_class": source["source_class"],
            "provenance": source["provenance"],
            "input_format": source["path"].suffix.lower(),
            "input_bytes": source["size_bytes"],
            "workload": workload,
            "custody_write_call_ns": write_ns,
            "custody_receipt": receipt.to_dict(),
        })
    # Fresh service instance checks restart materialisation and hash-chain continuity.
    reloaded = ProductionTriad(str(custody_db))
    for result, (receipt, original) in zip(results, stored):
        t0 = time.perf_counter_ns()
        reconstructed = reloaded.materialise(receipt)
        result["custody_read_call_ns"] = time.perf_counter_ns() - t0
        if reconstructed != original or not reloaded.verify(receipt):
            raise ValueError("durable custody restart/readback/continuity failed")
        result["custody_restart_roundtrip_verified"] = True

    evidence = {
        "schema": SCHEMA,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "input_count": len(sources),
        "input_classification": "OPERATOR_DECLARED_NOT_INDEPENDENTLY_ATTESTED",
        "data_generated_by_benchmark": False,
        "result": "PASS",
        "scope": "local software execution, integrity and selected application-call timings",
        "production_qualification": "UNVERIFIED",
        "device_execution": "UNVERIFIED",
        "external_source_attestation": "UNVERIFIED",
        "signed_evidence": False,
        "entries": results,
    }
    evidence["integrity_sha256"] = sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--custody-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    args = parser.parse_args(argv)
    try:
        # Check all destinations before processing or persisting customer bytes.
        sources = discover(args.manifest, max_bytes=args.max_bytes)
        target = args.output.resolve()
        db = args.custody_db.resolve()
        protected = {source["path"] for source in sources}
        protected.update({args.manifest.resolve(), db,
                          Path(str(db) + "-wal"), Path(str(db) + "-shm"),
                          Path(str(db) + "-journal")})
        if target in protected:
            raise ValueError("evidence destination cannot overwrite manifest, input or custody files")
        if target.exists():
            raise ValueError("evidence destination already exists; refusing overwrite")
        evidence = run_benchmark(args.manifest, args.custody_db,
                                 depth=args.depth, max_bytes=args.max_bytes,
                                 sources=sources)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"result": "PASS", "evidence": str(target),
                          "production_qualification": "UNVERIFIED"}))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(json.dumps({"result": "FAIL", "reason": str(exc),
                          "production_qualification": "UNVERIFIED"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
