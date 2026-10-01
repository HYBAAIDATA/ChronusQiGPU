"""Safe, checksummed persistence for Kellogg compressed tensors.

The ``.pv`` compatibility names now write a ZIP container containing canonical
JSON and NumPy ``.npy`` members. Loading never enables pickle. Every array has
a SHA-256 digest; optional HMAC-SHA256 authenticates the entire manifest.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from .compressed_tensor import CompressedTensor, CompressionScheme, Precision

MAGIC = "KELLOGG_TENSOR"
VERSION = 1


class TensorSerializationError(ValueError):
    """A tensor artifact is malformed, corrupt or unauthenticated."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    except (TypeError, ValueError) as exc:
        raise TensorSerializationError("tensor metadata must be JSON serializable") from exc


def _arrays(tensor: CompressedTensor) -> list[np.ndarray]:
    raw = tensor.raw_storage
    values = [raw] if isinstance(raw, np.ndarray) else list(raw)
    if not values:
        raise TensorSerializationError("compressed tensor has no storage arrays")
    arrays = [np.asarray(value) for value in values]
    if any(array.dtype.hasobject for array in arrays):
        raise TensorSerializationError("object arrays cannot be serialized")
    return arrays


def _npy_bytes(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    return buffer.getvalue()


def save_pv(
    path: str | os.PathLike[str],
    obj: CompressedTensor,
    authentication_key: bytes | None = None,
) -> int:
    """Atomically persist a compressed tensor and return bytes written."""
    if not isinstance(obj, CompressedTensor):
        raise TensorSerializationError("save_pv requires a CompressedTensor")
    arrays = _arrays(obj)
    payloads = [_npy_bytes(array) for array in arrays]
    manifest = {
        "magic": MAGIC,
        "version": VERSION,
        "tensor": obj.metadata_dict(),
        "arrays": [
            {
                "name": f"arrays/{index}.npy",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
            for index, payload in enumerate(payloads)
        ],
        "authenticated": authentication_key is not None,
    }
    unsigned = _canonical(manifest)
    if authentication_key is not None:
        if not isinstance(authentication_key, bytes) or not authentication_key:
            raise TensorSerializationError("authentication_key must be non-empty bytes")
        manifest["hmac_sha256"] = hmac.new(authentication_key, unsigned, hashlib.sha256).hexdigest()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", _canonical(manifest))
            for record, payload in zip(manifest["arrays"], payloads):
                archive.writestr(record["name"], payload)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination.stat().st_size


def _read(
    path: str | os.PathLike[str], authentication_key: bytes | None
) -> tuple[dict[str, Any], list[np.ndarray]]:
    source = Path(path)
    if not source.is_file():
        raise TensorSerializationError(f"tensor artifact does not exist: {source}")
    try:
        with zipfile.ZipFile(source, "r") as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                raise TensorSerializationError("tensor artifact has no manifest")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("magic") != MAGIC or manifest.get("version") != VERSION:
                raise TensorSerializationError("unsupported tensor artifact magic or version")
            signature = manifest.pop("hmac_sha256", None)
            authenticated = bool(manifest.get("authenticated"))
            if authenticated:
                if authentication_key is None:
                    raise TensorSerializationError("authentication key is required")
                expected = hmac.new(
                    authentication_key, _canonical(manifest), hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(str(signature), expected):
                    raise TensorSerializationError("tensor artifact authentication failed")
            elif authentication_key is not None:
                raise TensorSerializationError(
                    "authentication key supplied for an unsigned artifact"
                )
            arrays = []
            for record in manifest.get("arrays", []):
                name = record.get("name")
                if name not in names or not str(name).startswith("arrays/"):
                    raise TensorSerializationError("tensor artifact is missing an array member")
                payload = archive.read(name)
                if len(payload) != int(record.get("bytes", -1)):
                    raise TensorSerializationError("tensor array byte count mismatch")
                if not hmac.compare_digest(
                    hashlib.sha256(payload).hexdigest(), str(record.get("sha256"))
                ):
                    raise TensorSerializationError("tensor array checksum mismatch")
                arrays.append(np.load(io.BytesIO(payload), allow_pickle=False))
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError) as exc:
        raise TensorSerializationError("invalid tensor artifact") from exc
    if not arrays:
        raise TensorSerializationError("tensor artifact contains no arrays")
    return manifest, arrays


def load_pv(
    path: str | os.PathLike[str], authentication_key: bytes | None = None
) -> CompressedTensor:
    """Load and verify a tensor artifact without pickle execution."""
    manifest, arrays = _read(path, authentication_key)
    meta = manifest.get("tensor")
    if not isinstance(meta, dict):
        raise TensorSerializationError("tensor metadata is missing")
    try:
        scheme = CompressionScheme(meta["compression_scheme"])
        raw: Any = arrays[0] if scheme is CompressionScheme.NONE else arrays
        reserved = {
            "compression_scheme",
            "logical_shape",
            "precision",
            "original_dtype",
            "storage_bytes",
            "logical_bytes",
            "representation_ratio",
            "reconstruction_error",
            "fidelity_guarantee",
            "entropy_estimate",
            "trace_norm",
            "ranks",
            "claim_boundary",
        }
        extra = {key: value for key, value in meta.items() if key not in reserved}
        return CompressedTensor(
            raw_storage=raw,
            compression_scheme=scheme,
            logical_shape=tuple(int(value) for value in meta["logical_shape"]),
            precision=Precision(meta["precision"]),
            original_dtype=str(meta["original_dtype"]),
            reconstruction_error=float(meta.get("reconstruction_error", 0.0)),
            fidelity_guarantee=float(meta.get("fidelity_guarantee", 1.0)),
            entropy_estimate=float(meta.get("entropy_estimate", 0.0)),
            trace_norm=float(meta.get("trace_norm", 0.0)),
            ranks=tuple(int(value) for value in meta.get("ranks", [])),
            metadata=extra,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TensorSerializationError("invalid compressed-tensor metadata") from exc


def validate_pv(
    path: str | os.PathLike[str], authentication_key: bytes | None = None
) -> dict[str, Any]:
    """Validate an artifact and return non-secret structural evidence."""
    manifest, arrays = _read(path, authentication_key)
    return {
        "valid": True,
        "magic": manifest["magic"],
        "version": manifest["version"],
        "authenticated": manifest["authenticated"],
        "array_count": len(arrays),
        "array_bytes": sum(int(array.nbytes) for array in arrays),
        "compression_scheme": manifest["tensor"]["compression_scheme"],
    }


__all__ = [
    "MAGIC",
    "VERSION",
    "TensorSerializationError",
    "load_pv",
    "save_pv",
    "validate_pv",
]
