"""Bounded production bridge from the validated Bitcoin corpus to Turing VQC.

The recovered July VQC lineage already contains
``VQCTrainingDataGenerator.generate_from_blocks``.  This module connects that
training surface to ``PythiaBitcoinCorpus`` without making historical winning
nonces into a claim of future predictive power.

Training is explicit and bounded.  It is never run synchronously in the live
Stratum hot path.  Checkpoints are written atomically and include corpus range
and source metadata so a mining decision can identify what model state it used.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any

import numpy as np

from .bitcoin_corpus import PythiaBitcoinCorpus

SCHEMA = "pythia.bitcoin_vqc_training/1"


def _turing_variational():
    errors: list[str] = []
    for name in (
        "turing_universal_quantum_computer.variational",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.variational",
    ):
        try:
            module = __import__(name, fromlist=["*"])
            return module
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    raise RuntimeError("Turing variational VQC unavailable: " + "; ".join(errors))


def corpus_training_blocks(
    corpus: PythiaBitcoinCorpus,
    *,
    start_height: int = 0,
    limit: int = 32,
) -> list[dict[str, Any]]:
    """Translate locally verified corpus rows into the VQC's historical format."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    blocks: list[dict[str, Any]] = []
    for row in corpus.rows(start_height=start_height, limit=limit):
        blocks.append(
            {
                "height": row["height"],
                "block_hash": row["block_hash"],
                "header": {
                    "version": row["version"],
                    "prev_hash": row["previousblockhash"],
                    "merkle_root": row["merkleroot"],
                    "ntime": row["time"],
                    "nbits": row["bits"],
                },
                "nonce": row["nonce"],
                # The generator accepts an optional target. Keep it absent
                # rather than deriving a second consensus implementation here.
                "target": 0,
            }
        )
    return blocks


def _checkpoint_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_checkpoint(
    vqc: Any,
    path: str | Path,
    *,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Atomically persist VQC parameters and evidence metadata."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    best = getattr(vqc, "best_params", None)
    payload = {
        "schema": SCHEMA,
        "created_at": time.time(),
        **metadata,
    }
    fd, tmp_name = tempfile.mkstemp(prefix=dest.name + ".", suffix=".npz", dir=str(dest.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        np.savez_compressed(
            tmp,
            theta=np.asarray(vqc.theta),
            best_params=(np.asarray(best) if best is not None else np.asarray([], dtype=float)),
            has_best=np.asarray([best is not None], dtype=np.uint8),
            metadata_json=np.asarray([json.dumps(payload, sort_keys=True, separators=(",", ":"))]),
        )
        with tmp.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {
        "schema": SCHEMA,
        "checkpoint": str(dest),
        "sha256": _checkpoint_sha256(dest),
        "metadata": payload,
    }


def load_checkpoint(vqc: Any, path: str | Path) -> dict[str, Any]:
    """Restore a checkpoint into an already-constructed compatible VQC."""
    source = Path(path)
    with np.load(source, allow_pickle=False) as data:
        theta = np.asarray(data["theta"])
        if theta.shape != np.asarray(vqc.theta).shape:
            raise ValueError(
                f"VQC checkpoint theta shape {theta.shape} does not match runtime {np.asarray(vqc.theta).shape}"
            )
        vqc.theta = theta.copy()
        has_best = bool(int(np.asarray(data["has_best"]).reshape(-1)[0]))
        best = np.asarray(data["best_params"])
        vqc.best_params = best.copy() if has_best else None
        metadata = json.loads(str(np.asarray(data["metadata_json"]).reshape(-1)[0]))
    return {
        "schema": SCHEMA,
        "checkpoint": str(source),
        "sha256": _checkpoint_sha256(source),
        "metadata": metadata,
    }


class BitcoinVQCTrainer:
    """Explicit bounded historical trainer for Turing's 32-face VQC."""

    def __init__(self, corpus: PythiaBitcoinCorpus, *, vqc: Any | None = None) -> None:
        self.corpus = corpus
        module = _turing_variational()
        self.generator = module.VQCTrainingDataGenerator()
        self.vqc = vqc if vqc is not None else module.VariationalQuantumCircuit(module.VQCConfig())

    def train(
        self,
        *,
        start_height: int = 0,
        limit: int = 32,
        epochs: int = 1,
        batch_size: int = 8,
        checkpoint_path: str | Path | None = None,
    ) -> dict[str, Any]:
        if epochs <= 0 or batch_size <= 0:
            raise ValueError("epochs and batch_size must be positive")
        blocks = corpus_training_blocks(self.corpus, start_height=start_height, limit=limit)
        if not blocks:
            raise ValueError("no validated Bitcoin corpus rows in requested training range")
        training_data = self.generator.generate_from_blocks(blocks)
        result = self.vqc.train(training_data, epochs=epochs, batch_size=batch_size)
        evidence: dict[str, Any] = {
            "schema": SCHEMA,
            "truth_boundary": (
                "historical valid nonces are supervised examples only; training is not evidence of future-nonce prediction"
            ),
            "first_height": blocks[0]["height"],
            "last_height": blocks[-1]["height"],
            "examples": len(blocks),
            "epochs": epochs,
            "batch_size": batch_size,
            "training_result": result,
        }
        if checkpoint_path is not None:
            evidence["checkpoint"] = save_checkpoint(
                self.vqc,
                checkpoint_path,
                metadata={
                    "first_height": blocks[0]["height"],
                    "last_height": blocks[-1]["height"],
                    "examples": len(blocks),
                    "epochs": epochs,
                    "batch_size": batch_size,
                },
            )
        return evidence


__all__ = [
    "BitcoinVQCTrainer",
    "SCHEMA",
    "corpus_training_blocks",
    "load_checkpoint",
    "save_checkpoint",
]