"""Validated Bitcoin corpus for PYTHIA learning and retrieval.

Every record retains the canonical 80-byte block header and its locally
verified block hash. Exact golden-family structures are stored alongside the
raw header as retrieval/index certificates. When explicitly enabled, the
corpus also retains the exact raw serialized block bytes returned by Bitcoin
Core, including transactions, content-addressed by SHA-256 and anchored to the
independently validated 80-byte header.

Raw-block custody is optional because full-chain storage is large and is not a
mining-runtime dependency. The fold/index never replaces source bytes.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from kellogg.scales import (
    binet_fold,
    cassini,
    cassini_verify,
    fibonacci,
    lucas,
    zeckendorf,
    zeckendorf_is_legal,
)

SCHEMA = "pythia.bitcoin_corpus/2"
DEFAULT_SCALE_INDICES = (10, 12, 15, 18, 20, 31, 50, 76)
DEFAULT_PATH = Path("artifacts") / "pythia" / "bitcoin_corpus.sqlite3"


@dataclass(frozen=True)
class FoldedBlockHeader:
    height: int
    block_hash: str
    header: bytes
    seed_hex: str
    zeckendorf_indices: tuple[int, ...]
    fibonacci_addresses: tuple[int, ...]
    cassini_certificates: tuple[tuple[int, int], ...]
    lucas_residues: Mapping[int, int]
    binet_certificates: Mapping[int, tuple[int, int]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "height": self.height,
            "block_hash": self.block_hash,
            "header_hex": self.header.hex(),
            "seed_hex": self.seed_hex,
            "zeckendorf_indices": list(self.zeckendorf_indices),
            "fibonacci_addresses": [str(value) for value in self.fibonacci_addresses],
            "cassini_certificates": [list(value) for value in self.cassini_certificates],
            "lucas_residues": {str(k): value for k, value in self.lucas_residues.items()},
            "binet_certificates": {
                str(k): [value[0], value[1]] for k, value in self.binet_certificates.items()
            },
        }


def fold_header(
    *,
    height: int,
    block_hash: str,
    header: bytes,
    scale_indices: Sequence[int] = DEFAULT_SCALE_INDICES,
) -> FoldedBlockHeader:
    """Build exact retrieval/storage coordinates for one verified header."""
    if type(height) is not int or height < 0:
        raise ValueError("height must be a non-negative integer")
    if not isinstance(header, (bytes, bytearray)) or len(header) != 80:
        raise ValueError("Bitcoin block header must be exactly 80 bytes")
    header = bytes(header)
    digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()[::-1].hex()
    if digest != block_hash:
        raise ValueError("header does not match supplied Bitcoin block hash")

    seed_bytes = hashlib.sha256(header).digest()
    seed = int.from_bytes(seed_bytes, "big")
    indices = tuple(zeckendorf(seed))
    if not zeckendorf_is_legal(indices):
        raise ArithmeticError("Zeckendorf non-adjacency invariant failed")
    addresses = tuple(fibonacci(index) for index in indices)
    if sum(addresses) != seed:
        raise ArithmeticError("Fibonacci addresses do not reconstruct the header seed")
    cassini_certificates = tuple((index, cassini(index)) for index in indices)
    if any(not cassini_verify(index) for index in indices):
        raise ArithmeticError("Cassini certificate failed for a Zeckendorf index")

    lucas_residues: dict[int, int] = {}
    binet_certificates: dict[int, tuple[int, int]] = {}
    for raw_index in scale_indices:
        index = int(raw_index)
        if index < 1:
            raise ValueError("scale indices must be positive")
        lv = lucas(index)
        lucas_residues[index] = seed % lv
        folded = binet_fold(index)
        if folded.a != fibonacci(index) or folded.b != 0:
            raise ArithmeticError("exact Binet certificate disagrees with Fibonacci value")
        if not cassini_verify(index):
            raise ArithmeticError("scale Cassini certificate failed")
        binet_certificates[index] = (folded.a, folded.b)

    return FoldedBlockHeader(
        height=height,
        block_hash=block_hash,
        header=header,
        seed_hex=seed_bytes.hex(),
        zeckendorf_indices=indices,
        fibonacci_addresses=addresses,
        cassini_certificates=cassini_certificates,
        lucas_residues=lucas_residues,
        binet_certificates=binet_certificates,
    )


class PythiaBitcoinCorpus:
    """SQLite-backed active-chain corpus plus exact folded retrieval indexes."""

    def __init__(self, path: str | Path = DEFAULT_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path), timeout=30.0, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "PythiaBitcoinCorpus":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _migrate(self) -> None:
        self._db.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS corpus_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS block_headers (
                height INTEGER PRIMARY KEY,
                block_hash TEXT NOT NULL UNIQUE,
                header BLOB NOT NULL CHECK(length(header) = 80),
                version INTEGER NOT NULL,
                previousblockhash TEXT NOT NULL,
                merkleroot TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                bits INTEGER NOT NULL,
                nonce INTEGER NOT NULL,
                chainwork TEXT,
                seed_hex TEXT NOT NULL,
                zeckendorf_json TEXT NOT NULL,
                fibonacci_addresses_json TEXT NOT NULL,
                cassini_json TEXT NOT NULL,
                lucas_residues_json TEXT NOT NULL,
                binet_json TEXT NOT NULL,
                observed_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS block_headers_seed_idx ON block_headers(seed_hex);
            CREATE TABLE IF NOT EXISTS raw_blocks (
                height INTEGER PRIMARY KEY,
                block_hash TEXT NOT NULL UNIQUE,
                raw_block BLOB NOT NULL CHECK(length(raw_block) > 80),
                raw_block_sha256 TEXT NOT NULL CHECK(length(raw_block_sha256) = 64),
                byte_count INTEGER NOT NULL CHECK(byte_count > 80),
                observed_at REAL NOT NULL,
                FOREIGN KEY(height) REFERENCES block_headers(height) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS raw_blocks_sha_idx ON raw_blocks(raw_block_sha256);
            INSERT OR REPLACE INTO corpus_meta(key, value)
                VALUES('schema', 'pythia.bitcoin_corpus/2');
            COMMIT;
            """
        )

    @staticmethod
    def _header_fields(header: bytes) -> dict[str, Any]:
        return {
            "version": int.from_bytes(header[0:4], "little"),
            "previousblockhash": header[4:36][::-1].hex(),
            "merkleroot": header[36:68][::-1].hex(),
            "timestamp": int.from_bytes(header[68:72], "little"),
            "bits": int.from_bytes(header[72:76], "little"),
            "nonce": int.from_bytes(header[76:80], "little"),
        }

    def put(
        self,
        *,
        height: int,
        block_hash: str,
        header: bytes,
        chainwork: str | None = None,
    ) -> FoldedBlockHeader:
        folded = fold_header(height=height, block_hash=block_hash, header=header)
        fields = self._header_fields(folded.header)
        payloads = folded.as_dict()
        existing = self._db.execute(
            "SELECT block_hash, header FROM block_headers WHERE height=?", (height,)
        ).fetchone()
        if existing is not None:
            if existing["block_hash"] != block_hash or bytes(existing["header"]) != folded.header:
                raise ValueError("active-chain corpus conflict at existing height")
            return folded
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._db.execute(
                """
                INSERT INTO block_headers(
                    height, block_hash, header, version, previousblockhash, merkleroot,
                    timestamp, bits, nonce, chainwork, seed_hex, zeckendorf_json,
                    fibonacci_addresses_json, cassini_json, lucas_residues_json,
                    binet_json, observed_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    height,
                    block_hash,
                    folded.header,
                    fields["version"],
                    fields["previousblockhash"],
                    fields["merkleroot"],
                    fields["timestamp"],
                    fields["bits"],
                    fields["nonce"],
                    chainwork,
                    folded.seed_hex,
                    json.dumps(payloads["zeckendorf_indices"], separators=(",", ":")),
                    json.dumps(payloads["fibonacci_addresses"], separators=(",", ":")),
                    json.dumps(payloads["cassini_certificates"], separators=(",", ":")),
                    json.dumps(payloads["lucas_residues"], separators=(",", ":")),
                    json.dumps(payloads["binet_certificates"], separators=(",", ":")),
                    time.time(),
                ),
            )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        return folded

    def put_raw_block(
        self,
        *,
        height: int,
        block_hash: str,
        raw_block: bytes,
        raw_block_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Retain exact serialized block bytes anchored to the stored header."""
        if not isinstance(raw_block, (bytes, bytearray)) or len(raw_block) <= 80:
            raise ValueError("raw Bitcoin block must contain header plus body")
        raw = bytes(raw_block)
        header_row = self._db.execute(
            "SELECT block_hash, header FROM block_headers WHERE height=?", (int(height),)
        ).fetchone()
        if header_row is None:
            raise ValueError("raw block requires an existing validated header row")
        if str(header_row["block_hash"]) != block_hash:
            raise ValueError("raw block hash conflicts with stored header identity")
        if raw[:80] != bytes(header_row["header"]):
            raise ValueError("raw block does not begin with the stored validated header")
        consensus_hash = hashlib.sha256(hashlib.sha256(raw[:80]).digest()).digest()[::-1].hex()
        if consensus_hash != block_hash:
            raise ValueError("raw block header does not match block hash")
        content_sha = hashlib.sha256(raw).hexdigest()
        if raw_block_sha256 is not None and raw_block_sha256 != content_sha:
            raise ValueError("raw block content SHA-256 mismatch")
        existing = self._db.execute(
            "SELECT block_hash, raw_block_sha256, byte_count FROM raw_blocks WHERE height=?",
            (int(height),),
        ).fetchone()
        if existing is not None:
            if (
                str(existing["block_hash"]) != block_hash
                or str(existing["raw_block_sha256"]) != content_sha
                or int(existing["byte_count"]) != len(raw)
            ):
                raise ValueError("raw-block corpus conflict at existing height")
            return {
                "height": height,
                "block_hash": block_hash,
                "raw_block_sha256": content_sha,
                "raw_block_bytes": len(raw),
            }
        self._db.execute(
            "INSERT INTO raw_blocks(height,block_hash,raw_block,raw_block_sha256,byte_count,observed_at) "
            "VALUES(?,?,?,?,?,?)",
            (int(height), block_hash, raw, content_sha, len(raw), time.time()),
        )
        return {
            "height": height,
            "block_hash": block_hash,
            "raw_block_sha256": content_sha,
            "raw_block_bytes": len(raw),
        }

    def latest_height(self) -> int | None:
        row = self._db.execute("SELECT MAX(height) AS h FROM block_headers").fetchone()
        return int(row["h"]) if row is not None and row["h"] is not None else None

    def count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM block_headers").fetchone()[0])

    def raw_block_count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM raw_blocks").fetchone()[0])

    def raw_block_at(self, height: int) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT height,block_hash,raw_block,raw_block_sha256,byte_count FROM raw_blocks WHERE height=?",
            (int(height),),
        ).fetchone()
        if row is None:
            return None
        return {
            "height": int(row["height"]),
            "block_hash": str(row["block_hash"]),
            "raw_block": bytes(row["raw_block"]),
            "raw_block_sha256": str(row["raw_block_sha256"]),
            "raw_block_bytes": int(row["byte_count"]),
        }

    def ingest_observer(
        self,
        observer: Any,
        *,
        start_height: int | None = None,
        end_height: int | None = None,
        include_raw_blocks: bool = False,
    ) -> dict[str, Any]:
        """Stream validated active-chain data from Bitcoin Core into the corpus."""
        if end_height is None:
            end_height = int(observer.height())
        if start_height is None:
            latest = self.latest_height()
            start_height = 0 if latest is None else latest + 1
        if start_height < 0 or end_height < start_height - 1:
            raise ValueError("invalid corpus height range")
        imported = 0
        raw_imported = 0
        first = start_height
        for height in range(start_height, end_height + 1):
            observed = observer.header_at(height)
            self.put(
                height=height,
                block_hash=str(observed["block_hash"]),
                header=bytes(observed["header"]),
                chainwork=(str(observed["chainwork"]) if observed.get("chainwork") else None),
            )
            imported += 1
            if include_raw_blocks:
                full = observer.raw_block_at(height)
                self.put_raw_block(
                    height=height,
                    block_hash=str(full["block_hash"]),
                    raw_block=bytes(full["raw_block"]),
                    raw_block_sha256=str(full["raw_block_sha256"]),
                )
                raw_imported += 1
        return {
            "schema": SCHEMA,
            "path": str(self.path),
            "start_height": first,
            "end_height": end_height,
            "imported": imported,
            "raw_blocks_requested": bool(include_raw_blocks),
            "raw_blocks_imported": raw_imported,
            "total": self.count(),
            "raw_block_total": self.raw_block_count(),
            "latest_height": self.latest_height(),
        }

    def rows(self, *, start_height: int = 0, limit: int | None = None) -> Iterator[dict[str, Any]]:
        sql = "SELECT * FROM block_headers WHERE height>=? ORDER BY height"
        params: list[Any] = [int(start_height)]
        if limit is not None:
            if limit <= 0:
                return
            sql += " LIMIT ?"
            params.append(int(limit))
        for row in self._db.execute(sql, params):
            yield {
                "height": int(row["height"]),
                "block_hash": str(row["block_hash"]),
                "header": bytes(row["header"]),
                "version": int(row["version"]),
                "previousblockhash": str(row["previousblockhash"]),
                "merkleroot": str(row["merkleroot"]),
                "time": int(row["timestamp"]),
                "bits": int(row["bits"]),
                "nonce": int(row["nonce"]),
                "seed_hex": str(row["seed_hex"]),
                "zeckendorf_indices": json.loads(row["zeckendorf_json"]),
                "fibonacci_addresses": [int(v) for v in json.loads(row["fibonacci_addresses_json"])],
                "cassini_certificates": json.loads(row["cassini_json"]),
                "lucas_residues": json.loads(row["lucas_residues_json"]),
                "binet_certificates": json.loads(row["binet_json"]),
            }

    def feed_orchestrator(
        self,
        orchestrator: Any,
        *,
        start_height: int = 0,
        limit: int | None = None,
        batch_size: int = 128,
    ) -> dict[str, Any]:
        """Feed corpus features into PYTHIA's existing learning + memory surfaces."""
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        import numpy as np

        fed = 0
        batches = 0
        batch: list[dict[str, Any]] = []

        def commit(items: list[dict[str, Any]]) -> None:
            nonlocal fed, batches
            if not items:
                return
            patterns = []
            for item in items:
                raw = bytes.fromhex(item["seed_hex"])
                patterns.append(np.asarray([value / 255.0 for value in raw[:32]], dtype=float))
            orchestrator.teach(patterns, [True] * len(patterns))
            orchestrator.consolidate_memory_task(
                trigger=f"bitcoin-corpus:{items[0]['height']}-{items[-1]['height']}",
                plan=[
                    "read locally verified canonical block headers",
                    "index by Zeckendorf/Fibonacci/Cassini/Binet structure",
                    "feed exact historical outcomes to PYTHIA learning",
                ],
                tool_calls=[
                    {
                        "tool": "PythiaBitcoinCorpus",
                        "count": len(items),
                        "first_height": items[0]["height"],
                        "last_height": items[-1]["height"],
                    }
                ],
                outcome={
                    "validated_headers": len(items),
                    "first_height": items[0]["height"],
                    "last_height": items[-1]["height"],
                },
                reward=1.0,
            )
            if getattr(orchestrator, "store", None) is not None:
                orchestrator.store.journal.append(
                    "bitcoin_corpus",
                    {
                        "first_height": items[0]["height"],
                        "last_height": items[-1]["height"],
                        "count": len(items),
                    },
                )
            fed += len(items)
            batches += 1

        for row in self.rows(start_height=start_height, limit=limit):
            batch.append(row)
            if len(batch) >= batch_size:
                commit(batch)
                batch = []
        commit(batch)
        if getattr(orchestrator, "store", None) is not None:
            orchestrator.store.save()
        return {"schema": SCHEMA, "fed": fed, "batches": batches}

    def status(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "path": str(self.path),
            "count": self.count(),
            "latest_height": self.latest_height(),
            "raw_block_count": self.raw_block_count(),
            "raw_block_custody": {
                "available": self.raw_block_count() > 0,
                "optional": True,
                "source": "Bitcoin Core getblock(hash, 0)",
                "exact_serialized_bytes_retained": True,
                "content_digest": "sha256(raw serialized block)",
                "consensus_anchor": "locally verified 80-byte header",
                "independent_transaction_body_verifier": False,
            },
            "folding": {
                "lossless_source_retained": True,
                "seed": "sha256(header)",
                "zeckendorf": True,
                "fibonacci_addresses": True,
                "cassini_certificates": True,
                "binet_scale_certificates": list(DEFAULT_SCALE_INDICES),
                "lucas_residue_scales": list(DEFAULT_SCALE_INDICES),
            },
        }


__all__ = [
    "DEFAULT_PATH",
    "DEFAULT_SCALE_INDICES",
    "FoldedBlockHeader",
    "PythiaBitcoinCorpus",
    "SCHEMA",
    "fold_header",
]
