"""Aethel persistent folded-state store — versioned fold graph.

One :class:`FoldBlock` is a named tensor held as a chain of immutable
:class:`NumericFoldState` versions. Every version carries content identity
(SHA-256 over dtype/shape/segment bytes, from :mod:`aethel.phi_fold`), fold
depth, lineage (the parent version it was committed against), and residency.

Semantics:

* ``commit_region`` performs a regional write through
  :func:`aethel.phi_fold.splice_region` — only the fold segments owning the
  write region are touched; untouched segments are shared verbatim with the
  parent version. The commit is atomic: it requires the caller's expected
  version and a unique ``commit_id`` (exactly-once per coordinate range and
  per commit id). A second commit with the same id fails closed.
* ``checkpoint``/``restore`` persist the whole graph to a single ``.npz``
  artifact — metadata as JSON plus each version's segments as named arrays.
  Restore verifies every recorded content hash; a tampered or incompatible
  artifact fails closed.
* ``evict`` drops payload bytes but keeps the block header (identity,
  lineage, content hash); ``regenerate`` re-materialises from a caller
  source and proves identity by digest equality — the regen path is not a
  cache-miss shortcut.
* ``invalidate_device`` marks every block bound to a device as lost; reads
  fail until the block is re-materialised. Host blocks (``device_id=None``)
  are never touched.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import numpy as np

from .errors import AethelError
from .phi_fold import (
    KernelBoundary,
    NumericFoldState,
    PhiFoldError,
    phi_fold,
    phi_unfold,
    splice_region,
    unfold_partial,
)

logger = logging.getLogger("aethel.fold_store")

CHECKPOINT_FORMAT = "aethel-fold-store/v1"


class FoldStoreError(AethelError):
    """A fold-store custody, version, or persistence contract was violated."""


class CommitConflictError(FoldStoreError):
    """An atomic commit saw a stale expected version or a duplicate commit id."""


class DeviceLostError(FoldStoreError):
    """The resident's backing device was invalidated and the state is gone."""


@dataclass(frozen=True)
class CommitRecord:
    """Evidence for one committed write to a block."""

    commit_id: str
    block: str
    from_version: int
    to_version: int
    region: Tuple[int, int]
    affected_levels: Tuple[int, ...]
    committed_ns: int


@dataclass(frozen=True)
class FoldBlockVersion:
    """One immutable version of a block's folded state."""

    version: int
    state: NumericFoldState
    lineage: Tuple[str, ...]
    commit_id: str
    created_ns: int


@dataclass
class FoldBlock:
    """A named tensor in folded custody: version chain + residency."""

    name: str
    versions: Dict[int, FoldBlockVersion] = field(default_factory=dict)
    current_version: int = 0
    device_id: Optional[str] = None
    residency: str = "resident"  # resident | evicted | device_lost
    evicted_header: Optional[dict] = None
    commits: Tuple[CommitRecord, ...] = ()
    _commit_ids: frozenset = frozenset()

    @property
    def current(self) -> FoldBlockVersion:
        try:
            return self.versions[self.current_version]
        except KeyError as exc:
            raise FoldStoreError(f"block {self.name!r} has no current version") from exc

    @property
    def state(self) -> NumericFoldState:
        return self.current.state


class PersistentFoldStore:
    """Thread-safe versioned fold graph with checkpoint/restore and eviction."""

    def __init__(self, default_depth: int = 1) -> None:
        if default_depth < 0:
            raise FoldStoreError("default_depth must be non-negative")
        self.default_depth = int(default_depth)
        self._blocks: Dict[str, FoldBlock] = {}
        self._lock = threading.RLock()

    # -- block lifecycle ---------------------------------------------------

    def create(
        self,
        name: str,
        array: np.ndarray,
        *,
        depth: Optional[int] = None,
        device_id: Optional[str] = None,
    ) -> FoldBlock:
        """Fold ``array`` into custody as version 0 of a new block."""
        if not name:
            raise FoldStoreError("block name is required")
        with self._lock:
            if name in self._blocks:
                raise FoldStoreError(f"block {name!r} already exists")
            state = phi_fold(np.asarray(array), depth=self.default_depth if depth is None else int(depth))
            version = FoldBlockVersion(
                version=0,
                state=state,
                lineage=("genesis",),
                commit_id="genesis",
                created_ns=time.time_ns(),
            )
            block = FoldBlock(
                name=name,
                versions={0: version},
                current_version=0,
                device_id=device_id,
                _commit_ids=frozenset({"genesis"}),
            )
            self._blocks[name] = block
            return block

    def block(self, name: str) -> FoldBlock:
        try:
            return self._blocks[name]
        except KeyError as exc:
            raise FoldStoreError(f"no block named {name!r}") from exc

    def names(self) -> Tuple[str, ...]:
        return tuple(sorted(self._blocks))

    # -- reads ---------------------------------------------------------------

    def _resident_block(self, name: str) -> FoldBlock:
        block = self.block(name)
        if block.residency == "device_lost":
            raise DeviceLostError(
                f"block {name!r} was bound to device {block.device_id!r}, which was "
                "invalidated; re-materialise the block before reading"
            )
        if block.residency == "evicted":
            raise FoldStoreError(
                f"block {name!r} is evicted; call regenerate() to re-materialise it"
            )
        return block

    def read(self, name: str) -> np.ndarray:
        """Reconstruct a resident block's payload element-exactly."""
        with self._lock:
            return phi_unfold(self._resident_block(name).state)

    def read_region(self, name: str, boundary: KernelBoundary) -> np.ndarray:
        """True addressed partial read of a resident block."""
        with self._lock:
            return unfold_partial(self._resident_block(name).state, boundary)

    def version(self, name: str) -> int:
        return self.block(name).current_version

    def lineage(self, name: str) -> Tuple[str, ...]:
        return self.block(name).current.lineage

    def content_hash(self, name: str) -> str:
        block = self.block(name)
        if block.residency == "evicted":
            return str(block.evicted_header["content_hash"])
        return block.state.content_hash

    # -- writes (atomic, exactly-once) ----------------------------------------

    def write_region(
        self,
        name: str,
        boundary: KernelBoundary,
        values: np.ndarray,
        *,
        commit_id: str,
        expected_version: Optional[int] = None,
    ) -> CommitRecord:
        """Stage-free alias for :meth:`commit_region`."""
        return self.commit_region(
            name, boundary, values, commit_id=commit_id, expected_version=expected_version
        )

    def commit_region(
        self,
        name: str,
        boundary: KernelBoundary,
        values: np.ndarray,
        *,
        commit_id: str,
        expected_version: Optional[int] = None,
    ) -> CommitRecord:
        """Atomically commit a regional write as a new block version.

        Exactly-once: ``commit_id`` must be unique per block and
        ``expected_version`` (when given) must equal the live version — a
        stale write or a retry of a landed commit both fail closed.
        """
        if not commit_id:
            raise FoldStoreError("commit_id is required")
        with self._lock:
            block = self._resident_block(name)
            if commit_id in block._commit_ids:
                raise CommitConflictError(
                    f"commit {commit_id!r} was already committed to block {name!r}"
                )
            if expected_version is not None and expected_version != block.current_version:
                raise CommitConflictError(
                    f"expected version {expected_version}, block {name!r} is at "
                    f"{block.current_version}"
                )
            try:
                new_state, affected = splice_region(block.state, boundary, values)
            except PhiFoldError as exc:
                raise FoldStoreError(str(exc)) from exc
            record = CommitRecord(
                commit_id=commit_id,
                block=name,
                from_version=block.current_version,
                to_version=block.current_version + 1,
                region=(boundary.offset, boundary.length),
                affected_levels=affected,
                committed_ns=time.time_ns(),
            )
            new_version = FoldBlockVersion(
                version=record.to_version,
                state=new_state,
                lineage=block.current.lineage + (f"v{block.current_version}:{commit_id}",),
                commit_id=commit_id,
                created_ns=record.committed_ns,
            )
            block.versions[record.to_version] = new_version
            block.current_version = record.to_version
            block.commits = block.commits + (record,)
            block._commit_ids = block._commit_ids | {commit_id}
            logger.debug(
                "commit %s to %r: v%d->v%d levels=%s",
                commit_id, name, record.from_version, record.to_version, affected,
            )
            return record

    # -- eviction / regeneration / device loss ---------------------------------

    def evict(self, name: str) -> dict:
        """Drop the block's payload bytes, keeping its identity header."""
        with self._lock:
            block = self._resident_block(name)
            state = block.state
            header = {
                "name": name,
                "version": block.current_version,
                "content_hash": state.content_hash,
                "dtype": np.dtype(state.dtype).str,
                "shape": state.original_shape,
                "original_size": state.original_size,
                "depth": state.depth,
                "lineage": list(block.current.lineage),
            }
            block.evicted_header = header
            block.versions = {}
            block.residency = "evicted"
            return header

    def regenerate(self, name: str, source: np.ndarray) -> FoldBlock:
        """Re-materialise an evicted block, proving identity by content hash.

        The regenerated payload must digest to the recorded header —
        regeneration is evidence-bearing recovery, not a blind reload.
        """
        with self._lock:
            block = self.block(name)
            if block.residency != "evicted":
                raise FoldStoreError(f"block {name!r} is not evicted")
            header = block.evicted_header
            state = phi_fold(np.asarray(source), depth=int(header["depth"]))
            if state.content_hash != header["content_hash"]:
                raise FoldStoreError(
                    f"regenerated payload for {name!r} does not match evicted "
                    "content identity — refusing to bind different data to the "
                    "same block lineage"
                )
            if state.dtype != np.dtype(header["dtype"]):
                raise FoldStoreError(
                    f"regenerated dtype {state.dtype} does not match evicted "
                    f"dtype {header['dtype']}"
                )
            version = FoldBlockVersion(
                version=int(header["version"]),
                state=state,
                lineage=tuple(header["lineage"]),
                commit_id="regenerate",
                created_ns=time.time_ns(),
            )
            block.versions = {version.version: version}
            block.residency = "resident"
            block.evicted_header = None
            return block

    def invalidate_device(self, device_id: str) -> Tuple[str, ...]:
        """Mark every block bound to ``device_id`` as lost (device-loss)."""
        lost: list[str] = []
        with self._lock:
            for name, block in self._blocks.items():
                if block.device_id == device_id and block.residency == "resident":
                    block.residency = "device_lost"
                    lost.append(name)
        return tuple(sorted(lost))

    def rematerialize(self, name: str, source: np.ndarray) -> FoldBlock:
        """Re-materialise a device-lost block, verifying content identity."""
        with self._lock:
            block = self.block(name)
            if block.residency != "device_lost":
                raise FoldStoreError(f"block {name!r} is not device-lost")
            state = phi_fold(np.asarray(source), depth=block.state.depth)
            if state.content_hash != block.state.content_hash:
                raise FoldStoreError(
                    f"re-materialised payload for {name!r} does not match the "
                    "lost version's content identity"
                )
            block.versions[block.current_version] = FoldBlockVersion(
                version=block.current_version,
                state=state,
                lineage=block.current.lineage,
                commit_id="rematerialize",
                created_ns=time.time_ns(),
            )
            block.residency = "resident"
            return block

    # -- persistence -----------------------------------------------------------

    def checkpoint(self, path: str | Path) -> Path:
        """Persist the entire fold graph to one ``.npz`` artifact."""
        path = Path(path)
        with self._lock:
            meta = {
                "format": CHECKPOINT_FORMAT,
                "created_ns": time.time_ns(),
                "blocks": [],
            }
            arrays: Dict[str, np.ndarray] = {}
            for name, block in self._blocks.items():
                entry = {
                    "name": name,
                    "current_version": block.current_version,
                    "device_id": block.device_id,
                    "residency": block.residency,
                    "evicted_header": block.evicted_header,
                    "versions": [],
                    "commits": [
                        {
                            "commit_id": c.commit_id,
                            "from_version": c.from_version,
                            "to_version": c.to_version,
                            "region": list(c.region),
                            "affected_levels": list(c.affected_levels),
                            "committed_ns": c.committed_ns,
                        }
                        for c in block.commits
                    ],
                }
                for version_id, version in sorted(block.versions.items()):
                    state = version.state
                    seg_names = []
                    for index, segment in enumerate(
                        (state.retained, *state.complements)
                    ):
                        key = f"seg__{name}__{version_id}__{index}"
                        arrays[key] = np.ascontiguousarray(segment)
                        seg_names.append(key)
                    entry["versions"].append(
                        {
                            "version": version.version,
                            "lineage": list(version.lineage),
                            "commit_id": version.commit_id,
                            "created_ns": version.created_ns,
                            "depth": state.depth,
                            "original_shape": list(state.original_shape),
                            "original_size": state.original_size,
                            "dtype": np.dtype(state.dtype).str,
                            "layout": state.layout,
                            "content_hash": state.content_hash,
                            "segments": seg_names,
                        }
                    )
                meta["blocks"].append(entry)
            arrays["__meta__"] = np.frombuffer(json.dumps(meta).encode("utf-8"), np.uint8)
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(path, **arrays)
            return path if path.suffix == ".npz" else Path(f"{path}.npz")

    @classmethod
    def restore(cls, path: str | Path) -> "PersistentFoldStore":
        """Rebuild a store from a checkpoint, verifying every content hash."""
        path = Path(path)
        if path.suffix != ".npz":
            path = Path(f"{path}.npz")
        with np.load(path, allow_pickle=False) as archive:
            meta = json.loads(bytes(archive["__meta__"].tolist()).decode("utf-8"))
            if meta.get("format") != CHECKPOINT_FORMAT:
                raise FoldStoreError(
                    f"checkpoint format {meta.get('format')!r} is not {CHECKPOINT_FORMAT!r}"
                )
            store = cls()
            for entry in meta["blocks"]:
                block = FoldBlock(
                    name=entry["name"],
                    current_version=int(entry["current_version"]),
                    device_id=entry.get("device_id"),
                    residency=entry["residency"],
                    evicted_header=entry.get("evicted_header"),
                )
                for ver in entry["versions"]:
                    segments = [archive[key] for key in ver["segments"]]
                    retained, complements = segments[0], tuple(segments[1:])
                    state = NumericFoldState(
                        retained=retained,
                        complements=complements,
                        depth=int(ver["depth"]),
                        original_shape=tuple(int(v) for v in ver["original_shape"]),
                        original_size=int(ver["original_size"]),
                        dtype=np.dtype(ver["dtype"]),
                        layout=ver.get("layout", "C"),
                        content_hash=ver["content_hash"],
                    )
                    if not state.verify_content_hash():
                        raise FoldStoreError(
                            f"checkpoint block {entry['name']!r} v{ver['version']} "
                            "fails content-hash verification — refusing to load "
                            "altered state"
                        )
                    block.versions[ver["version"]] = FoldBlockVersion(
                        version=int(ver["version"]),
                        state=state,
                        lineage=tuple(ver["lineage"]),
                        commit_id=ver["commit_id"],
                        created_ns=int(ver["created_ns"]),
                    )
                commits = tuple(
                    CommitRecord(
                        commit_id=c["commit_id"],
                        block=entry["name"],
                        from_version=int(c["from_version"]),
                        to_version=int(c["to_version"]),
                        region=tuple(c["region"]),
                        affected_levels=tuple(c["affected_levels"]),
                        committed_ns=int(c["committed_ns"]),
                    )
                    for c in entry.get("commits", [])
                )
                # Rebuild commit-id membership so restored blocks keep
                # exactly-once semantics (cannot reuse a landed commit id).
                ids = {
                    v["commit_id"] for v in entry["versions"]
                } | {c.commit_id for c in commits} | {"genesis"}
                block.commits = commits
                block._commit_ids = frozenset(ids)
                store._blocks[block.name] = block
            return store

    def status(self) -> Dict[str, object]:
        with self._lock:
            return {
                "format": CHECKPOINT_FORMAT,
                "blocks": {
                    name: {
                        "current_version": block.current_version,
                        "versions": len(block.versions),
                        "residency": block.residency,
                        "device_id": block.device_id,
                        "content_hash": self.content_hash(name),
                    }
                    for name, block in self._blocks.items()
                },
            }


__all__ = [
    "CHECKPOINT_FORMAT",
    "CommitConflictError",
    "CommitRecord",
    "DeviceLostError",
    "FoldBlock",
    "FoldBlockVersion",
    "FoldStoreError",
    "PersistentFoldStore",
]
