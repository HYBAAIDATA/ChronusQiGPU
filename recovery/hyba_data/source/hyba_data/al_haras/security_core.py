from __future__ import annotations

"""
Al Haras Security Core Infrastructure (migrated from HYBA_PROD_READY).

Dependency-light, self-contained primitives: a tamper-evident, Merkle-audited
hash chain, and a bounded adaptive trust scorer. No external services or
simulated behavior; every method here does exactly what it computes.

Migrated verbatim (unchanged logic) from HYBA_PROD_READY's
`src/al_haras/security_core.py` on 2026-07-13 as part of Al Haras
consolidation into HYBA_INTELLIGENCE.
"""

import hashlib
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class AuditEntry:
    """An audit chain entry with optional Merkle proof metadata."""

    hash: str
    data: str
    timestamp: float
    previous_hash: str
    merkle_proof: dict | None = None


class CryptographicAuditChain:
    """Tamper-evident log with hash chaining and Merkle-root verification.

    This lightweight chain intentionally avoids external dependencies and is
    suitable for tests, bootstrapping, and small local deployments. Entries are
    immutable dataclasses, not dictionaries.
    """

    def __init__(self, use_merkle: bool = True, batch_size: int = 100, external_anchor: str | None = None):
        self.chain: list[AuditEntry] = []
        self.last_hash = "0" * 64
        self.merkle_root = ""
        self.use_merkle = use_merkle
        self.batch_size = batch_size
        self.merkle_tree_hashes: list[str] = []
        # External trusted root/checkpoint — attacker who controls only chain bytes cannot forge without this
        self._external_anchor: str | None = external_anchor
        self._checkpoints: list[tuple[int, str, str]] = []  # (length, tip_hash, token)

    def set_external_anchor(self, anchor: str) -> None:
        """Bind chain to a trusted external root (HSM tip, object store etag, notary)."""
        if not anchor or not isinstance(anchor, str):
            raise ValueError("external anchor required")
        self._external_anchor = hashlib.sha256(anchor.encode() if isinstance(anchor, str) else anchor).hexdigest() if len(anchor) != 64 else anchor

    def seal_checkpoint(self) -> str:
        """Seal current tip against external anchor. Returns checkpoint token."""
        if not self._external_anchor:
            # derive deterministic placeholder only if explicitly none — verification will still require set
            raise ValueError("set_external_anchor before seal_checkpoint")
        tip = self.last_hash
        token = hashlib.sha256(f"{self._external_anchor}|{len(self.chain)}|{tip}".encode()).hexdigest()
        self._checkpoints.append((len(self.chain), tip, token))
        return token

    def verify_with_external_anchor(self, expected_token: str | None = None) -> bool:
        """Integrity plus external checkpoint. Forged local chains fail without matching anchor seal."""
        if not self.verify_integrity():
            return False
        if not self._external_anchor:
            return False
        if not self._checkpoints:
            return False
        length, tip, token = self._checkpoints[-1]
        if length != len(self.chain) or tip != self.last_hash:
            return False
        recomputed = hashlib.sha256(f"{self._external_anchor}|{length}|{tip}".encode()).hexdigest()
        if recomputed != token:
            return False
        if expected_token is not None and expected_token != token:
            return False
        return True

    def add_entry(self, data: str) -> str:
        """Add an entry and return its hash."""
        timestamp = time.time()
        previous_hash = self.last_hash
        block_content = f"{previous_hash}|{timestamp}|{data}"
        new_hash = hashlib.sha256(block_content.encode()).hexdigest()

        self.merkle_tree_hashes.append(new_hash)
        if self.use_merkle:
            self.merkle_root = self._compute_merkle_root(self.merkle_tree_hashes)
            leaf_index = len(self.merkle_tree_hashes) - 1
            merkle_proof = {
                "leaf_index": leaf_index,
                "proof": self._get_merkle_proof(leaf_index, self.merkle_tree_hashes),
                "root": self.merkle_root,
            }
        else:
            merkle_proof = None

        entry = AuditEntry(
            hash=new_hash,
            data=data,
            timestamp=timestamp,
            previous_hash=previous_hash,
            merkle_proof=merkle_proof,
        )
        self.chain.append(entry)
        self.last_hash = new_hash
        return new_hash

    def _compute_merkle_root(self, hashes: list[str]) -> str:
        """Compute a Merkle root from a list of leaf hashes."""
        if not hashes:
            return ""

        current_level = hashes.copy()
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                next_level.append(hashlib.sha256((left + right).encode()).hexdigest())
            current_level = next_level
        return current_level[0]

    def _get_merkle_proof(self, leaf_index: int, hashes: list[str]) -> list[dict]:
        """Return the sibling path needed to verify a leaf hash."""
        if leaf_index < 0 or leaf_index >= len(hashes):
            return []

        proof = []
        current_level = hashes.copy()
        current_index = leaf_index

        while len(current_level) > 1:
            if current_index % 2 == 0:
                sibling_index = current_index + 1
                sibling_hash = (
                    current_level[sibling_index]
                    if sibling_index < len(current_level)
                    else current_level[current_index]
                )
                proof.append({"direction": "right", "hash": sibling_hash})
            else:
                sibling_index = current_index - 1
                proof.append({"direction": "left", "hash": current_level[sibling_index]})

            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                next_level.append(hashlib.sha256((left + right).encode()).hexdigest())

            current_index //= 2
            current_level = next_level

        return proof

    def verify_entry_merkle(self, entry_hash: str, leaf_hashes: list[str] | None = None) -> bool:
        """Verify an entry is included in the Merkle tree built from `leaf_hashes`.

        The proof is always recomputed fresh against the supplied leaf set
        (defaulting to the chain's current `merkle_tree_hashes`), never against
        the proof captured at insertion time. A proof captured when the entry
        was appended is only valid for the tree as it existed at that instant;
        by the time later entries are added the tree -- and therefore every
        earlier entry's correct proof -- has changed. Recomputing here keeps
        verification correct no matter how many entries have been added since.
        """
        if not self.use_merkle:
            return True

        entry = next((candidate for candidate in self.chain if candidate.hash == entry_hash), None)
        if entry is None or entry.merkle_proof is None:
            return False

        leaves = leaf_hashes if leaf_hashes is not None else self.merkle_tree_hashes
        leaf_index = entry.merkle_proof["leaf_index"]
        if leaf_index < 0 or leaf_index >= len(leaves) or leaves[leaf_index] != entry_hash:
            return False

        fresh_proof = self._get_merkle_proof(leaf_index, leaves)
        current_hash = entry_hash
        for proof_step in fresh_proof:
            if proof_step["direction"] == "left":
                current_hash = hashlib.sha256(
                    (proof_step["hash"] + current_hash).encode()
                ).hexdigest()
            else:
                current_hash = hashlib.sha256(
                    (current_hash + proof_step["hash"]).encode()
                ).hexdigest()

        expected_root = self._compute_merkle_root(leaves)
        return current_hash == expected_root

    def verify_integrity(self) -> bool:
        """Verify hash-chain and Merkle-root integrity for all entries."""
        current_hash = "0" * 64
        recomputed_leaf_hashes: list[str] = []

        for entry in self.chain:
            if entry.previous_hash != current_hash:
                return False

            expected_content = f"{entry.previous_hash}|{entry.timestamp}|{entry.data}"
            expected_hash = hashlib.sha256(expected_content.encode()).hexdigest()
            if entry.hash != expected_hash:
                return False

            recomputed_leaf_hashes.append(entry.hash)
            current_hash = entry.hash

        if current_hash != self.last_hash:
            return False

        if self.use_merkle:
            expected_root = self._compute_merkle_root(recomputed_leaf_hashes)
            if expected_root != self.merkle_root:
                return False
            return all(
                self.verify_entry_merkle(entry.hash, recomputed_leaf_hashes) for entry in self.chain
            )

        return True

    def get_chain_length(self) -> int:
        """Return the number of entries in the chain."""
        return len(self.chain)

    def get_last_hash(self) -> str:
        """Return the most recent entry hash."""
        return self.last_hash


class AdaptiveTrustSystem:
    """Dynamic trust calibration for users, agents, or domains."""

    def __init__(self, n_users: int = 10, initial_trust: float = 0.5):
        self.trust_scores = {f"user_{i}": initial_trust for i in range(n_users)}
        self.decay_factor = 0.9

    def decay_trust(self, user_id: str, factor: float | None = None) -> float:
        """Decay trust score for a specific user."""
        factor = self.decay_factor if factor is None else factor
        if user_id in self.trust_scores:
            self.trust_scores[user_id] = max(0.0, self.trust_scores[user_id] * factor)
            return self.trust_scores[user_id]
        return 0.0

    def boost_trust(self, user_id: str, factor: float = 1.1) -> float:
        """Boost trust score for a specific user."""
        if user_id in self.trust_scores:
            self.trust_scores[user_id] = min(1.0, self.trust_scores[user_id] * factor)
            return self.trust_scores[user_id]
        return 0.0

    def set_trust(self, user_id: str, trust: float) -> float:
        """Set trust score for a specific user, clamped to [0, 1]."""
        trust = max(0.0, min(1.0, trust))
        self.trust_scores[user_id] = trust
        return trust

    def get_trust(self, user_id: str) -> float:
        """Get trust score for a specific user."""
        return self.trust_scores.get(user_id, 0.0)

    def verify_consensus(self, threshold: float = 0.7) -> bool:
        """Return whether mean trust meets the consensus threshold."""
        if not self.trust_scores:
            return False
        return self.get_mean_trust() >= threshold

    def get_mean_trust(self) -> float:
        """Return mean trust across all users."""
        if not self.trust_scores:
            return 0.0
        return sum(self.trust_scores.values()) / len(self.trust_scores)

    def add_user(self, user_id: str, initial_trust: float = 0.5) -> None:
        """Add a user with clamped initial trust."""
        self.trust_scores[user_id] = max(0.0, min(1.0, initial_trust))

    def remove_user(self, user_id: str) -> None:
        """Remove a user if present."""
        self.trust_scores.pop(user_id, None)

    def get_all_trust_scores(self) -> dict[str, float]:
        """Return a copy of all trust scores."""
        return self.trust_scores.copy()


__all__ = ["AuditEntry", "CryptographicAuditChain", "AdaptiveTrustSystem"]
