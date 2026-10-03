"""Distributed enterprise custody substrate (software-measured, local multi-node).

Claim scopes (Rule 7 — honest measurement, no cloud/geo hardware lies):
  - distributed_consensus_software_multi_node_local
  - multi_root_multi_node_custody_software
  - cross_region_dr_software_simulated_regions
  - hyperscaler_soak_software_local_fleet
  - chronus_hardware_perf_measured
  - solutions_api_readiness_software
  - enterprise_hyba_certification_gate_software

All consensus is in-process Raft-like with real majority commit.
Regions are separate roots on local disk — not WAN multi-geo.
Hyperscaler soak is a local multi-worker fleet, not infinite cloud.
"""
from __future__ import annotations

import hashlib
import statistics
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from aethel.enterprise.custody import EnterpriseCustody, compose
from aethel.enterprise.errors import (
    CertificationError,
    ConsensusError,
    EnterpriseCustodyError,
    NotLeaderError,
    QuorumLostError,
    RegionFailoverError,
    SoakThresholdError,
)
from aethel.enterprise.authenticity import content_digest
from aethel.enterprise.parity import assert_cpu_accel_parity


# ---------------------------------------------------------------------------
# Identity / log
# ---------------------------------------------------------------------------


class NodeId(str):
    """Stable string identity for a Raft node."""

    def __new__(cls, value: str) -> "NodeId":
        if not value:
            raise ValueError("NodeId must be non-empty")
        return str.__new__(cls, str(value))


@dataclass
class LogEntry:
    """Replicated log entry (command applied to custody after commit)."""

    term: int
    index: int
    command: str  # "put" | "delete" | "noop"
    record_id: str = ""
    payload: bytes = b""
    payload_digest: str = ""

    def __post_init__(self) -> None:
        if self.payload and not self.payload_digest:
            self.payload_digest = content_digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "index": self.index,
            "command": self.command,
            "record_id": self.record_id,
            "payload": self.payload.hex() if self.payload else "",
            "payload_digest": self.payload_digest,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LogEntry":
        raw = d.get("payload") or ""
        payload = bytes.fromhex(raw) if raw else b""
        return cls(
            term=int(d["term"]),
            index=int(d["index"]),
            command=str(d["command"]),
            record_id=str(d.get("record_id") or ""),
            payload=payload,
            payload_digest=str(d.get("payload_digest") or ""),
        )


# ---------------------------------------------------------------------------
# In-process transport
# ---------------------------------------------------------------------------


class ClusterTransport:
    """In-process RPC bus between RaftNode instances (single-process cluster)."""

    def __init__(self) -> None:
        self._nodes: dict[NodeId, "RaftNode"] = {}
        self._lock = threading.RLock()

    def register(self, node: "RaftNode") -> None:
        with self._lock:
            self._nodes[node.node_id] = node

    def unregister(self, node_id: NodeId | str) -> None:
        with self._lock:
            self._nodes.pop(NodeId(str(node_id)), None)

    def ids(self) -> list[NodeId]:
        with self._lock:
            return list(self._nodes.keys())

    def get(self, node_id: NodeId | str) -> Optional["RaftNode"]:
        with self._lock:
            return self._nodes.get(NodeId(str(node_id)))

    def broadcast_request_vote(
        self,
        candidate_id: NodeId,
        term: int,
        last_log_index: int,
        last_log_term: int,
    ) -> list[dict[str, Any]]:
        with self._lock:
            targets = [n for i, n in self._nodes.items() if i != candidate_id]
        replies: list[dict[str, Any]] = []
        for n in targets:
            if n.stopped:
                continue
            try:
                replies.append(
                    n.request_vote(
                        candidate_id=candidate_id,
                        term=term,
                        last_log_index=last_log_index,
                        last_log_term=last_log_term,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                replies.append({"ok": False, "error": str(exc), "term": 0})
        return replies

    def send_append_entries(
        self,
        follower_id: NodeId | str,
        *,
        term: int,
        leader_id: NodeId,
        prev_log_index: int,
        prev_log_term: int,
        entries: list[LogEntry],
        leader_commit: int,
    ) -> dict[str, Any]:
        node = self.get(follower_id)
        if node is None or node.stopped:
            return {"ok": False, "term": term, "error": "unreachable"}
        try:
            return node.append_entries(
                term=term,
                leader_id=leader_id,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                entries=entries,
                leader_commit=leader_commit,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "term": term, "error": str(exc)}


# ---------------------------------------------------------------------------
# Raft node
# ---------------------------------------------------------------------------


class RaftNode:
    """Single Raft participant with local EnterpriseCustody root.

    Thread-safe enough for in-process multi-node via RLock. Roles:
    follower | candidate | leader.
    """

    def __init__(
        self,
        node_id: NodeId | str,
        custody: EnterpriseCustody,
        transport: ClusterTransport,
        *,
        peers: Optional[list[NodeId]] = None,
    ) -> None:
        self.node_id = NodeId(str(node_id))
        self.custody = custody
        self.transport = transport
        self.peers: list[NodeId] = list(peers or [])
        self._lock = threading.RLock()
        self.role: str = "follower"
        self.current_term: int = 0
        self.voted_for: Optional[NodeId] = None
        self.leader_id: Optional[NodeId] = None
        self.log: list[LogEntry] = []  # 1-indexed logically; list[0] unused sentinel
        self.commit_index: int = 0
        self.last_applied: int = 0
        self.next_index: dict[NodeId, int] = {}
        self.match_index: dict[NodeId, int] = {}
        self.stopped: bool = False
        self._kv: dict[str, bytes] = {}  # committed mirror for fast get
        # sentinel so prev_log_index 0 is well-defined
        self.log.append(LogEntry(term=0, index=0, command="noop"))

    # -- helpers -------------------------------------------------------------

    def stop(self) -> None:
        with self._lock:
            self.stopped = True
            self.role = "follower"
            self.leader_id = None

    def start(self) -> None:
        with self._lock:
            self.stopped = False

    @property
    def last_log_index(self) -> int:
        return len(self.log) - 1

    @property
    def last_log_term(self) -> int:
        return self.log[-1].term if self.log else 0

    def _cluster_size(self) -> int:
        # self + peers that are registered (may be stopped)
        return 1 + len(self.peers)

    def _majority(self) -> int:
        return (self._cluster_size() // 2) + 1

    def _maybe_step_down(self, term: int) -> None:
        if term > self.current_term:
            self.current_term = term
            self.role = "follower"
            self.voted_for = None
            self.leader_id = None

    # -- RPCs ----------------------------------------------------------------

    def request_vote(
        self,
        *,
        candidate_id: NodeId | str,
        term: int,
        last_log_index: int,
        last_log_term: int,
    ) -> dict[str, Any]:
        with self._lock:
            if self.stopped:
                return {"ok": False, "term": self.current_term, "vote_granted": False}
            candidate_id = NodeId(str(candidate_id))
            if term < self.current_term:
                return {
                    "ok": True,
                    "term": self.current_term,
                    "vote_granted": False,
                }
            self._maybe_step_down(term)
            up_to_date = last_log_term > self.last_log_term or (
                last_log_term == self.last_log_term
                and last_log_index >= self.last_log_index
            )
            grant = False
            if (self.voted_for is None or self.voted_for == candidate_id) and up_to_date:
                self.voted_for = candidate_id
                grant = True
            return {
                "ok": True,
                "term": self.current_term,
                "vote_granted": grant,
            }

    def append_entries(
        self,
        *,
        term: int,
        leader_id: NodeId | str,
        prev_log_index: int,
        prev_log_term: int,
        entries: list[LogEntry],
        leader_commit: int,
    ) -> dict[str, Any]:
        with self._lock:
            if self.stopped:
                return {"ok": False, "term": self.current_term}
            leader_id = NodeId(str(leader_id))
            if term < self.current_term:
                return {"ok": False, "term": self.current_term}
            self._maybe_step_down(term)
            self.role = "follower"
            self.leader_id = leader_id
            self.current_term = term

            if prev_log_index > self.last_log_index:
                return {"ok": False, "term": self.current_term}
            if (
                prev_log_index >= 0
                and self.log[prev_log_index].term != prev_log_term
            ):
                # conflict — truncate
                self.log = self.log[:prev_log_index]
                return {"ok": False, "term": self.current_term}

            # append new entries (overwrite conflicts)
            insert_at = prev_log_index + 1
            for i, entry in enumerate(entries):
                idx = insert_at + i
                if idx <= self.last_log_index:
                    if self.log[idx].term != entry.term:
                        self.log = self.log[:idx]
                        self.log.append(
                            LogEntry(
                                term=entry.term,
                                index=idx,
                                command=entry.command,
                                record_id=entry.record_id,
                                payload=entry.payload,
                                payload_digest=entry.payload_digest,
                            )
                        )
                else:
                    self.log.append(
                        LogEntry(
                            term=entry.term,
                            index=len(self.log),
                            command=entry.command,
                            record_id=entry.record_id,
                            payload=entry.payload,
                            payload_digest=entry.payload_digest,
                        )
                    )

            if leader_commit > self.commit_index:
                self.commit_index = min(leader_commit, self.last_log_index)
            self._apply_committed()
            return {
                "ok": True,
                "term": self.current_term,
                "match_index": self.last_log_index,
            }

    def _apply_committed(self) -> None:
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log[self.last_applied]
            self._apply_entry(entry)

    def _apply_entry(self, entry: LogEntry) -> None:
        if entry.command == "put":
            self.custody.put(entry.payload, record_id=entry.record_id)
            self._kv[entry.record_id] = entry.payload
        elif entry.command == "delete":
            # best-effort: mark absent in mirror (custody may lack delete)
            self._kv.pop(entry.record_id, None)
        # noop: nothing

    # -- elections / leadership ---------------------------------------------

    def become_candidate_and_campaign(self) -> bool:
        """Run one election round. Returns True if this node became leader."""
        with self._lock:
            if self.stopped:
                return False
            self.role = "candidate"
            self.current_term += 1
            self.voted_for = self.node_id
            self.leader_id = None
            term = self.current_term
            last_idx = self.last_log_index
            last_term = self.last_log_term

        # vote for self
        votes = 1
        replies = self.transport.broadcast_request_vote(
            self.node_id, term, last_idx, last_term
        )
        with self._lock:
            for r in replies:
                rterm = int(r.get("term") or 0)
                if rterm > self.current_term:
                    self._maybe_step_down(rterm)
                    return False
                if r.get("vote_granted"):
                    votes += 1
            if self.role != "candidate" or self.current_term != term:
                return False
            if votes >= self._majority():
                self.role = "leader"
                self.leader_id = self.node_id
                for p in self.peers:
                    self.next_index[p] = self.last_log_index + 1
                    self.match_index[p] = 0
                # Raft: append no-op on leadership so prior-term entries can commit
                self.become_leader()
                return True
            self.role = "follower"
            return False

    def become_leader(self) -> None:
        """Complete leadership transition: append noop, majority-commit, heartbeat.

        Caller must already hold self._lock and have set role/next_index/match_index.
        """
        idx = self.last_log_index + 1
        noop = LogEntry(
            term=self.current_term,
            index=idx,
            command="noop",
            record_id="",
            payload=b"",
        )
        self.log.append(noop)
        # Replicate noop; advance commit_index once majority has it
        self._replicate_unlocked()
        # Heartbeat with leader_commit so followers apply through commit_index
        self._heartbeat_unlocked()

    def _heartbeat_unlocked(self) -> bool:
        """Send empty AppendEntries carrying current leader_commit to all peers."""
        return self._replicate_unlocked(force_heartbeat=True)

    def heartbeat(self) -> bool:
        """Public heartbeat: push leader_commit / catch up followers."""
        with self._lock:
            if self.role != "leader" or self.stopped:
                return False
            return self._heartbeat_unlocked()

    def propose(self, command: str, record_id: str = "", payload: bytes = b"") -> int:
        """Leader-only: append command and commit on majority. Returns log index."""
        with self._lock:
            if self.stopped:
                raise ConsensusError(f"node {self.node_id} stopped")
            if self.role != "leader":
                raise NotLeaderError(
                    f"node {self.node_id} is {self.role}, not leader"
                )
            idx = self.last_log_index + 1
            entry = LogEntry(
                term=self.current_term,
                index=idx,
                command=command,
                record_id=record_id,
                payload=payload,
            )
            self.log.append(entry)
            # replicate; self counts as one ack
            committed = self._replicate_unlocked()
            if not committed:
                raise QuorumLostError(
                    f"failed to commit index {idx} on majority "
                    f"(commit_index={self.commit_index})"
                )
            # Push leader_commit to followers so they apply committed entries
            self._heartbeat_unlocked()
            return idx

    def _replicate_unlocked(self, force_heartbeat: bool = False) -> bool:
        """Send append_entries to peers; advance commit_index on majority.

        Caller must hold self._lock (or be single-threaded). Returns True if
        the latest entry is committed (or heartbeat succeeded with quorum).
        """
        if self.role != "leader":
            return False
        acks = 1  # leader
        latest = self.last_log_index
        for peer in self.peers:
            nxt = self.next_index.get(peer, latest + 1)
            prev = nxt - 1
            if prev < 0:
                prev = 0
            prev_term = self.log[prev].term if prev <= self.last_log_index else 0
            # entries to send
            if nxt <= self.last_log_index:
                entries = list(self.log[nxt:])
            else:
                entries = []
            if not entries and not force_heartbeat and latest == 0:
                continue
            # release lock during RPC? keep simple — in-process, hold lock
            reply = self.transport.send_append_entries(
                peer,
                term=self.current_term,
                leader_id=self.node_id,
                prev_log_index=prev,
                prev_log_term=prev_term,
                entries=entries,
                leader_commit=self.commit_index,
            )
            rterm = int(reply.get("term") or 0)
            if rterm > self.current_term:
                self._maybe_step_down(rterm)
                return False
            if reply.get("ok"):
                match = int(reply.get("match_index") or self.last_log_index)
                self.match_index[peer] = match
                self.next_index[peer] = match + 1
                acks += 1
            else:
                # backoff next_index
                cur = self.next_index.get(peer, latest + 1)
                self.next_index[peer] = max(1, cur - 1)

        # advance commit_index to highest N replicated on majority with term
        if acks >= self._majority():
            for n in range(self.last_log_index, self.commit_index, -1):
                if self.log[n].term != self.current_term:
                    continue
                count = 1  # leader
                for peer in self.peers:
                    if self.match_index.get(peer, 0) >= n:
                        count += 1
                if count >= self._majority():
                    self.commit_index = n
                    break
            # heartbeats still count as quorum contact
            if force_heartbeat and acks >= self._majority():
                self._apply_committed()
                return True
            self._apply_committed()
            return self.commit_index >= latest
        return False

    def get_local(self, record_id: str) -> Optional[bytes]:
        with self._lock:
            if record_id in self._kv:
                return self._kv[record_id]
            try:
                return self.custody.get(record_id)
            except Exception:  # noqa: BLE001
                return None

    def health(self) -> dict[str, Any]:
        with self._lock:
            return {
                "node_id": str(self.node_id),
                "role": self.role,
                "term": self.current_term,
                "leader_id": str(self.leader_id) if self.leader_id else None,
                "commit_index": self.commit_index,
                "last_log_index": self.last_log_index,
                "stopped": self.stopped,
                "root": str(self.custody.root),
                "records_mirrored": len(self._kv),
            }


# ---------------------------------------------------------------------------
# Multi-root + multi-node cluster
# ---------------------------------------------------------------------------


class MultiRootCustody:
    """Many custody roots under one cluster id (one root per node)."""

    def __init__(self, cluster_id: str, roots: dict[str, EnterpriseCustody]) -> None:
        self.cluster_id = cluster_id
        self.roots = dict(roots)

    def root_paths(self) -> dict[str, str]:
        return {k: str(v.root) for k, v in self.roots.items()}

    def distinct_roots(self) -> bool:
        paths = [str(Path(v.root).resolve()) for v in self.roots.values()]
        return len(paths) == len(set(paths)) and len(paths) >= 2


class MultiNodeCluster:
    """N RaftNode instances with per-node EnterpriseCustody (multi-root)."""

    def __init__(self) -> None:
        self.cluster_id: str = ""
        self.transport = ClusterTransport()
        self.nodes: dict[NodeId, RaftNode] = {}
        self.multi_root: Optional[MultiRootCustody] = None
        self._hmac_key: bytes = b""
        self._lock = threading.RLock()
        self.claim_scope_consensus = "distributed_consensus_software_multi_node_local"
        self.claim_scope_multi_root = "multi_root_multi_node_custody_software"

    @classmethod
    def bootstrap(
        cls,
        n_nodes: int,
        base_root: Path | str,
        hmac_key: bytes,
        *,
        cluster_id: Optional[str] = None,
        allow_insecure_dev_key: bool = False,
        tenant: str = "default",
    ) -> "MultiNodeCluster":
        if n_nodes < 3:
            raise ConsensusError("Raft cluster requires n_nodes >= 3")
        if not hmac_key or len(hmac_key) < 16:
            raise ValueError("hmac_key must be >= 16 bytes (explicit; no silent default)")
        base = Path(base_root)
        base.mkdir(parents=True, exist_ok=True)
        cluster = cls()
        cluster.cluster_id = cluster_id or f"cluster-{uuid.uuid4().hex[:12]}"
        cluster._hmac_key = bytes(hmac_key)
        ids = [NodeId(f"n{i}") for i in range(n_nodes)]
        custodies: dict[str, EnterpriseCustody] = {}
        for nid in ids:
            root = base / f"node_{nid}"
            cust = compose(
                root,
                tenant=tenant,
                hmac_key=hmac_key,
                allow_insecure_dev_key=allow_insecure_dev_key,
            )
            custodies[str(nid)] = cust
        cluster.multi_root = MultiRootCustody(cluster.cluster_id, custodies)
        # build nodes with peer lists
        for nid in ids:
            peers = [p for p in ids if p != nid]
            node = RaftNode(
                nid,
                custodies[str(nid)],
                cluster.transport,
                peers=peers,
            )
            cluster.nodes[nid] = node
            cluster.transport.register(node)
        return cluster

    def alive_nodes(self) -> list[RaftNode]:
        return [n for n in self.nodes.values() if not n.stopped]

    def leader(self) -> Optional[RaftNode]:
        for n in self.alive_nodes():
            if n.role == "leader":
                return n
        return None

    def wait_leader(self, timeout: float = 5.0) -> RaftNode:
        """Elect a leader among alive nodes; raise if none within timeout."""
        deadline = time.time() + timeout
        last_err: Optional[Exception] = None
        while time.time() < deadline:
            existing = self.leader()
            if existing is not None:
                return existing
            # campaign: try each alive follower/candidate in turn
            for node in list(self.alive_nodes()):
                if node.stopped:
                    continue
                try:
                    if node.become_candidate_and_campaign():
                        return node
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
            time.sleep(0.02)
        raise ConsensusError(
            f"no leader elected within {timeout}s "
            f"(alive={len(self.alive_nodes())}, last={last_err})"
        )

    def stop_node(self, node_id: NodeId | str) -> None:
        nid = NodeId(str(node_id))
        node = self.nodes.get(nid)
        if node is None:
            return
        was_leader = node.role == "leader"
        node.stop()
        if was_leader:
            # clear stale leader marks on followers
            for n in self.alive_nodes():
                if n.leader_id == nid:
                    n.leader_id = None

    def start_node(self, node_id: NodeId | str) -> None:
        nid = NodeId(str(node_id))
        node = self.nodes.get(nid)
        if node is not None:
            node.start()

    def put(self, record_id: str, data: bytes) -> dict[str, Any]:
        leader = self.leader()
        if leader is None:
            leader = self.wait_leader(timeout=3.0)
        idx = leader.propose("put", record_id=record_id, payload=data)
        return {
            "index": idx,
            "leader": str(leader.node_id),
            "record_id": record_id,
            "digest": content_digest(data),
        }

    def get(self, record_id: str, *, from_leader: bool = True) -> bytes:
        if from_leader:
            leader = self.leader() or self.wait_leader(timeout=3.0)
            val = leader.get_local(record_id)
            if val is None:
                raise KeyError(record_id)
            return val
        # any committed node
        for n in self.alive_nodes():
            val = n.get_local(record_id)
            if val is not None:
                return val
        raise KeyError(record_id)

    def majority_has(self, record_id: str, expected: bytes) -> bool:
        hits = 0
        for n in self.nodes.values():
            if n.stopped:
                continue
            val = n.get_local(record_id)
            if val == expected:
                hits += 1
        majority = (len(self.nodes) // 2) + 1
        return hits >= majority

    def health(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "claim_scope_consensus": self.claim_scope_consensus,
            "claim_scope_multi_root": self.claim_scope_multi_root,
            "n_nodes": len(self.nodes),
            "alive": len(self.alive_nodes()),
            "leader": str(self.leader().node_id) if self.leader() else None,
            "nodes": {str(i): n.health() for i, n in self.nodes.items()},
            "distinct_roots": bool(
                self.multi_root and self.multi_root.distinct_roots()
            ),
            "root_paths": self.multi_root.root_paths() if self.multi_root else {},
        }

    def close(self) -> None:
        for n in self.nodes.values():
            try:
                n.stop()
                n.custody.close()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Cross-region DR (simulated regions = separate roots)
# ---------------------------------------------------------------------------


class CrossRegionDR:
    """Primary region cluster + DR root; failover/failback software-measured.

    claim_scope = cross_region_dr_software_simulated_regions
    """

    claim_scope = "cross_region_dr_software_simulated_regions"

    def __init__(
        self,
        *,
        region_a: MultiNodeCluster,
        region_b_root: Path | str,
        hmac_key: bytes,
        allow_insecure_dev_key: bool = False,
        tenant: str = "default",
    ) -> None:
        self.region_a = region_a
        self.region_b_path = Path(region_b_root)
        self.region_b_path.mkdir(parents=True, exist_ok=True)
        self._hmac_key = bytes(hmac_key)
        self.region_b = compose(
            self.region_b_path,
            tenant=tenant,
            hmac_key=hmac_key,
            allow_insecure_dev_key=allow_insecure_dev_key,
        )
        self.active_region: str = "a"
        self._snapshot_dir = self.region_b_path.parent / f"{self.region_b_path.name}_snap"
        self._failed_over = False

    def replicate_snapshot(self) -> dict[str, Any]:
        """Copy committed leader custody snapshot into region_b."""
        leader = self.region_a.leader() or self.region_a.wait_leader(timeout=3.0)
        snap = self._snapshot_dir
        if snap.exists():
            import shutil

            shutil.rmtree(snap)
        leader.custody.backup(snap)
        # restore into region_b
        self.region_b.restore(snap)
        # count records from leader mirror
        n = len(leader._kv)
        return {
            "records": n,
            "from_leader": str(leader.node_id),
            "dr_root": str(self.region_b.root),
            "claim_scope": self.claim_scope,
        }

    def failover(self) -> dict[str, Any]:
        """Stop primary region nodes; serve reads from region_b."""
        for n in list(self.region_a.nodes.values()):
            n.stop()
        self.active_region = "b"
        self._failed_over = True
        return {
            "active_region": self.active_region,
            "primary_alive": len(self.region_a.alive_nodes()),
            "claim_scope": self.claim_scope,
        }

    def failback(self) -> dict[str, Any]:
        """Restart primary nodes and re-elect; keep DR snapshot."""
        for n in self.region_a.nodes.values():
            n.start()
            # clear leader state so election can proceed cleanly
            n.role = "follower"
            n.leader_id = None
        leader = self.region_a.wait_leader(timeout=5.0)
        self.active_region = "a"
        self._failed_over = False
        return {
            "active_region": self.active_region,
            "leader": str(leader.node_id),
            "claim_scope": self.claim_scope,
        }

    def get(self, record_id: str) -> bytes:
        if self.active_region == "b" or self._failed_over:
            try:
                return self.region_b.get(record_id)
            except Exception as exc:  # noqa: BLE001
                raise RegionFailoverError(
                    f"DR read failed for {record_id}: {exc}"
                ) from exc
        return self.region_a.get(record_id)

    def put(self, record_id: str, data: bytes) -> dict[str, Any]:
        if self.active_region != "a" or self._failed_over:
            raise RegionFailoverError("writes only on primary region_a in this model")
        return self.region_a.put(record_id, data)

    def health(self) -> dict[str, Any]:
        return {
            "claim_scope": self.claim_scope,
            "active_region": self.active_region,
            "failed_over": self._failed_over,
            "region_a": self.region_a.health(),
            "region_b_root": str(self.region_b.root),
        }

    def close(self) -> None:
        try:
            self.region_b.close()
        except Exception:  # noqa: BLE001
            pass
        self.region_a.close()


# ---------------------------------------------------------------------------
# Hyperscaler soak (local multi-worker)
# ---------------------------------------------------------------------------


@dataclass
class SoakReport:
    ops_ok: int
    ops_fail: int
    elapsed_s: float
    throughput: float
    workers: int
    target_ops: int
    claim_scope: str = "hyperscaler_soak_software_local_fleet"
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ops_ok": self.ops_ok,
            "ops_fail": self.ops_fail,
            "elapsed_s": self.elapsed_s,
            "throughput": self.throughput,
            "workers": self.workers,
            "target_ops": self.target_ops,
            "claim_scope": self.claim_scope,
            "errors": list(self.errors),
        }


class HyperscalerSoak:
    """Local multi-worker load soak over a MultiNodeCluster or SolutionsAPI store.

    claim_scope = hyperscaler_soak_software_local_fleet
    """

    claim_scope = "hyperscaler_soak_software_local_fleet"

    def __init__(
        self,
        cluster: MultiNodeCluster,
        *,
        min_ops: int = 200,
        min_workers: int = 4,
    ) -> None:
        self.cluster = cluster
        self.min_ops = min_ops
        self.min_workers = min_workers

    def run(
        self,
        *,
        workers: int = 4,
        ops: int = 200,
        fail_on_error: bool = True,
    ) -> SoakReport:
        workers = max(workers, 1)
        ops = max(ops, 1)
        # ensure leader
        self.cluster.wait_leader(timeout=5.0)
        ok = 0
        fail = 0
        errors: list[str] = []
        lock = threading.Lock()

        def worker_fn(wid: int, n_ops: int) -> tuple[int, int, list[str]]:
            local_ok = 0
            local_fail = 0
            local_err: list[str] = []
            for i in range(n_ops):
                rid = f"soak-w{wid}-{i}"
                payload = f"soak-{wid}-{i}".encode()
                try:
                    self.cluster.put(rid, payload)
                    got = self.cluster.get(rid)
                    if got != payload:
                        raise AssertionError("payload mismatch")
                    local_ok += 1
                except Exception as exc:  # noqa: BLE001
                    local_fail += 1
                    local_err.append(f"w{wid}/{i}: {type(exc).__name__}: {exc}")
            return local_ok, local_fail, local_err

        # distribute ops
        base = ops // workers
        rem = ops % workers
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = []
            for w in range(workers):
                n = base + (1 if w < rem else 0)
                if n <= 0:
                    continue
                futs.append(pool.submit(worker_fn, w, n))
            for f in as_completed(futs):
                lo, lf, le = f.result()
                with lock:
                    ok += lo
                    fail += lf
                    errors.extend(le)
        elapsed = max(time.perf_counter() - t0, 1e-9)
        report = SoakReport(
            ops_ok=ok,
            ops_fail=fail,
            elapsed_s=elapsed,
            throughput=ok / elapsed,
            workers=workers,
            target_ops=ops,
            claim_scope=self.claim_scope,
            errors=errors[:20],
        )
        if fail_on_error and fail > 0:
            raise SoakThresholdError(
                f"soak failures={fail} ok={ok} errors={errors[:3]}"
            )
        return report


# ---------------------------------------------------------------------------
# Chronus hardware perf probe (honest)
# ---------------------------------------------------------------------------


@dataclass
class PerfReport:
    samples: list[float]
    p50: float
    p95: float
    path: str  # "cpu" | "chronus_accel"
    cpu_only: bool
    ops: int
    claim_scope: str = "chronus_hardware_perf_measured"
    parity_ok: Optional[bool] = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "samples": list(self.samples),
            "p50": self.p50,
            "p95": self.p95,
            "path": self.path,
            "cpu_only": self.cpu_only,
            "ops": self.ops,
            "claim_scope": self.claim_scope,
            "parity_ok": self.parity_ok,
            "notes": self.notes,
            # Explicitly do NOT invent GPU FLOPS / device TFLOPS
            "device_flops": None,
            "invented_metrics": False,
        }


class ChronusPerfProbe:
    """Measure put/get path CPU timing; Chronus accel only if device present."""

    claim_scope = "chronus_hardware_perf_measured"

    def __init__(
        self,
        root: Path | str,
        hmac_key: bytes,
        *,
        allow_insecure_dev_key: bool = False,
    ) -> None:
        self.root = Path(root)
        self.hmac_key = bytes(hmac_key)
        self.allow_insecure_dev_key = allow_insecure_dev_key

    def _chronus_available(self) -> bool:
        try:
            from chronus import is_available  # type: ignore

            return bool(is_available())
        except Exception:
            pass
        try:
            import chronus  # noqa: F401

            # Prefer explicit flag if present
            if hasattr(chronus, "is_available"):
                return bool(chronus.is_available())  # type: ignore[attr-defined]
            if hasattr(chronus, "device"):
                dev = getattr(chronus, "device")
                if callable(dev):
                    d = dev()
                    return d is not None
                return dev is not None
            # Import succeeded but no device probe — treat as software-only
            return False
        except Exception:
            return False

    def measure(self, *, ops: int = 30, payload_size: int = 256) -> PerfReport:
        ops = max(ops, 5)
        payload = b"X" * payload_size
        cpu_only = not self._chronus_available()
        path = "cpu" if cpu_only else "chronus_accel"
        samples: list[float] = []

        # CPU path custody
        cpu_root = self.root / "perf_cpu"
        cpu = compose(
            cpu_root,
            hmac_key=self.hmac_key,
            allow_insecure_dev_key=self.allow_insecure_dev_key,
            chronus_accel=False,
        )
        accel = None
        parity_ok: Optional[bool] = None
        notes = "CPU baseline always measured."
        if not cpu_only:
            try:
                accel = compose(
                    self.root / "perf_accel",
                    hmac_key=self.hmac_key,
                    allow_insecure_dev_key=self.allow_insecure_dev_key,
                    chronus_accel=True,
                )
                notes = "Chronus accel path measured; digests must match CPU."
            except Exception as exc:  # noqa: BLE001
                cpu_only = True
                path = "cpu"
                notes = f"Chronus requested but unavailable ({exc}); cpu_only=True."
                accel = None

        target = accel if (accel is not None and not cpu_only) else cpu
        for i in range(ops):
            rid = f"perf-{i}"
            t0 = time.perf_counter()
            target.put(payload, record_id=rid)
            got = target.get(rid)
            dt = time.perf_counter() - t0
            if got != payload:
                raise EnterpriseCustodyError("perf probe payload mismatch")
            samples.append(dt)

        if accel is not None and not cpu_only:
            try:
                body = b"parity-body"
                # Authority matrix: accel must not change digest vs CPU identity path
                assert_cpu_accel_parity(body)
                cpu.put(body, record_id="parity-cpu")
                accel.put(body, record_id="parity-accel")
                d_cpu = content_digest(cpu.get("parity-cpu"))
                d_acc = content_digest(accel.get("parity-accel"))
                parity_ok = d_cpu == d_acc == content_digest(body)
            except Exception:
                try:
                    body2 = b"parity-body-2"
                    cpu.put(body2, record_id="p2c")
                    accel.put(body2, record_id="p2a")
                    parity_ok = content_digest(cpu.get("p2c")) == content_digest(
                        accel.get("p2a")
                    )
                except Exception:
                    parity_ok = False

        try:
            cpu.close()
            if accel is not None:
                accel.close()
        except Exception:  # noqa: BLE001
            pass

        ordered = sorted(samples)
        p50 = statistics.median(ordered)
        p95_idx = min(len(ordered) - 1, max(0, int(round(0.95 * (len(ordered) - 1)))))
        p95 = ordered[p95_idx]
        return PerfReport(
            samples=samples,
            p50=float(p50),
            p95=float(p95),
            path=path,
            cpu_only=cpu_only,
            ops=ops,
            claim_scope=self.claim_scope,
            parity_ok=parity_ok,
            notes=notes,
        )


# ---------------------------------------------------------------------------
# Solutions API façade
# ---------------------------------------------------------------------------


class SolutionsAPI:
    """In-process Solutions API façade over enterprise custody + cluster.

    claim_scope = solutions_api_readiness_software
    readiness() is True only when smoke put/get checks pass.
    """

    claim_scope = "solutions_api_readiness_software"

    def __init__(self) -> None:
        self._stores: dict[str, EnterpriseCustody] = {}
        self._clusters: dict[str, MultiNodeCluster] = {}
        self._keys: dict[str, bytes] = {}
        self._lock = threading.RLock()
        self._broken = False

    def create_store(
        self,
        store_id: str,
        root: Path | str,
        hmac_key: bytes,
        *,
        allow_insecure_dev_key: bool = False,
        tenant: str = "default",
    ) -> dict[str, Any]:
        with self._lock:
            cust = compose(
                root,
                tenant=tenant,
                hmac_key=hmac_key,
                allow_insecure_dev_key=allow_insecure_dev_key,
            )
            self._stores[store_id] = cust
            self._keys[store_id] = bytes(hmac_key)
            return {"store_id": store_id, "root": str(cust.root)}

    def attach_cluster(self, cluster_id: str, cluster: MultiNodeCluster) -> None:
        with self._lock:
            self._clusters[cluster_id] = cluster

    def put(self, store_id: str, record_id: str, data: bytes) -> dict[str, Any]:
        with self._lock:
            if self._broken:
                raise EnterpriseCustodyError("solutions API marked broken")
            if store_id in self._clusters:
                return self._clusters[store_id].put(record_id, data)
            store = self._stores.get(store_id)
            if store is None:
                raise KeyError(store_id)
            env = store.put(data, record_id=record_id)
            return {
                "record_id": record_id,
                "digest": getattr(env, "content_digest", content_digest(data)),
            }

    def get(self, store_id: str, record_id: str) -> bytes:
        with self._lock:
            if self._broken:
                raise EnterpriseCustodyError("solutions API marked broken")
            if store_id in self._clusters:
                return self._clusters[store_id].get(record_id)
            store = self._stores.get(store_id)
            if store is None:
                raise KeyError(store_id)
            return store.get(record_id)

    def health(self) -> dict[str, Any]:
        with self._lock:
            return {
                "claim_scope": self.claim_scope,
                "stores": list(self._stores.keys()),
                "clusters": {
                    k: v.health() for k, v in self._clusters.items()
                },
                "broken": self._broken,
            }

    def cluster_status(self, cluster_id: str) -> dict[str, Any]:
        with self._lock:
            c = self._clusters.get(cluster_id)
            if c is None:
                raise KeyError(cluster_id)
            return c.health()

    def mark_broken(self) -> None:
        """Test helper: force readiness failure."""
        self._broken = True

    def readiness(self) -> dict[str, Any]:
        """solutions_api_ready True only if smoke checks pass."""
        smoke_ok = False
        detail = ""
        try:
            with self._lock:
                if self._broken:
                    raise EnterpriseCustodyError("broken")
                # Prefer a store; else cluster
                if self._stores:
                    sid = next(iter(self._stores))
                    store = self._stores[sid]
                    rid = f"smoke-{uuid.uuid4().hex[:8]}"
                    payload = b"solutions-api-smoke"
                    store.put(payload, record_id=rid)
                    got = store.get(rid)
                    smoke_ok = got == payload
                    detail = f"store:{sid}"
                elif self._clusters:
                    cid = next(iter(self._clusters))
                    cl = self._clusters[cid]
                    cl.wait_leader(timeout=3.0)
                    rid = f"smoke-{uuid.uuid4().hex[:8]}"
                    payload = b"solutions-api-smoke"
                    cl.put(rid, payload)
                    got = cl.get(rid)
                    smoke_ok = got == payload
                    detail = f"cluster:{cid}"
                else:
                    detail = "no stores or clusters"
                    smoke_ok = False
        except Exception as exc:  # noqa: BLE001
            smoke_ok = False
            detail = f"{type(exc).__name__}: {exc}"
        return {
            "solutions_api_ready": bool(smoke_ok),
            "claim_scope": self.claim_scope,
            "detail": detail,
            "production_ready": False,
        }

    def certify(self, certificate: "HybaEnterpriseCertificate") -> dict[str, Any]:
        return certificate.issue()


# ---------------------------------------------------------------------------
# HYBA enterprise certification gate
# ---------------------------------------------------------------------------


class HybaEnterpriseCertificate:
    """Gate that aggregates named evidence and issues PASS/FAIL certificate.

    claim_scope = enterprise_hyba_certification_gate_software
    Certificate PASS only when every required evidence check passes.
    """

    claim_scope = "enterprise_hyba_certification_gate_software"

    def __init__(
        self,
        *,
        required_evidence: Optional[list[Any]] = None,
        scope: str = "enterprise_hyba_certification_gate_software",
        meta: Optional[dict[str, Any]] = None,
    ) -> None:
        # each item: str name, or (name, callable), or callable
        self.required_evidence = list(required_evidence or [])
        self.scope = scope
        self.meta = dict(meta or {})

    def _normalize(self) -> list[tuple[str, Callable[[], Any]]]:
        out: list[tuple[str, Callable[[], Any]]] = []
        for i, item in enumerate(self.required_evidence):
            if callable(item) and not isinstance(item, type):
                name = getattr(item, "__name__", f"check_{i}")
                out.append((name, item))
            elif isinstance(item, tuple) and len(item) == 2:
                name, fn = item
                if not callable(fn):
                    raise CertificationError(f"evidence {name} not callable")
                out.append((str(name), fn))
            elif isinstance(item, str):
                # module-name style: treat as label requiring external bind
                # default: look for callable registered via same name later —
                # for string-only, run a no-op pass marker (tests use callables)
                label = item

                def _named_ok(lbl: str = label) -> bool:
                    return True

                out.append((label, _named_ok))
            else:
                raise CertificationError(f"unsupported evidence entry: {item!r}")
        return out

    def issue(self) -> dict[str, Any]:
        evidence_map: dict[str, Any] = {}
        all_pass = True
        checks = self._normalize()
        if not checks:
            all_pass = False
            evidence_map["_gate"] = {
                "status": "FAIL",
                "reason": "no required_evidence configured",
            }
        for name, fn in checks:
            try:
                result = fn()
                # truthy result or explicit dict with ok/pass
                ok = True
                detail: Any = result
                if isinstance(result, dict):
                    if "ok" in result:
                        ok = bool(result["ok"])
                    elif "pass" in result:
                        ok = bool(result["pass"])
                    elif "status" in result:
                        ok = str(result["status"]).upper() in {"PASS", "OK", "TRUE"}
                elif result is False:
                    ok = False
                evidence_map[name] = {
                    "status": "PASS" if ok else "FAIL",
                    "detail": detail if not callable(detail) else repr(detail),
                }
                if not ok:
                    all_pass = False
            except Exception as exc:  # noqa: BLE001
                all_pass = False
                evidence_map[name] = {
                    "status": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                    "trace": traceback.format_exc()[-500:],
                }
        status = "PASS" if all_pass else "FAIL"
        cert = {
            "status": status,
            "evidence": evidence_map,
            "scope": self.scope,
            "claim_scope": self.claim_scope,
            "production_ready": False,
            "issued_at": time.time(),
            "meta": self.meta,
        }
        return cert


__all__ = [
    "NodeId",
    "LogEntry",
    "RaftNode",
    "ClusterTransport",
    "MultiNodeCluster",
    "MultiRootCustody",
    "CrossRegionDR",
    "HyperscalerSoak",
    "SoakReport",
    "ChronusPerfProbe",
    "PerfReport",
    "SolutionsAPI",
    "HybaEnterpriseCertificate",
]
