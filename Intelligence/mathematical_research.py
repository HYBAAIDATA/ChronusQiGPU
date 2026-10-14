"""Euclid / Salamander Mathematical Research, Conjecture Representation, and Proof Tracking Substrate.

Enforces Section 12 Scientific and Mathematical Protocol:
- Formal conjecture representation with explicit assumptions and domains
- Lemma dependency DAG tracking
- Strict separation between numerical experimentation and formal proof
- Provenance tracking for external theorems
- Honest claim boundary: NEVER label attempted proof as solved or verified
  without complete lemma closure and independent check.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple


class ConjectureStatus(str, Enum):
    CONJECTURED = "conjectured"
    EXPERIMENTALLY_EVIDENCED = "experimentally_evidenced"
    COUNTEREXAMPLE_FOUND = "counterexample_found"
    PARTIALLY_PROVEN = "partially_proven"
    FORMALLY_VERIFIED = "formally_verified"
    UNPROVEN_CLAIM = "unproven_claim"


@dataclass(frozen=True)
class Lemma:
    """Atomic step in a mathematical derivation with explicit dependency tracking."""

    lemma_id: str
    statement: str
    assumptions: Tuple[str, ...]
    dependencies: Tuple[str, ...]  # IDs of predecessor lemmas required
    provenance: str  # Literature reference or derivation origin
    is_verified: bool = False
    proof_method: str = "unverified"
    verification_receipt: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FormalConjecture:
    """Machine-readable formal representation of a mathematical conjecture."""

    conjecture_id: str
    domain: str
    statement: str
    assumptions: List[str]
    status: ConjectureStatus = ConjectureStatus.CONJECTURED
    lemmas: List[Lemma] = field(default_factory=list)
    counterexamples: List[Dict[str, Any]] = field(default_factory=list)
    numerical_experiments: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_steps: List[str] = field(default_factory=list)
    created_timestamp: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class ProofDAGError(ValueError):
    """Raised on invalid lemma dependency graphs (cycles, missing parents)."""


class MathematicalProofTracker:
    """Manages formal conjectures, lemma dependency DAGs, and proof states."""

    def __init__(self) -> None:
        self._conjectures: Dict[str, FormalConjecture] = {}

    def register_conjecture(
        self,
        conjecture_id: str,
        domain: str,
        statement: str,
        assumptions: Optional[Sequence[str]] = None,
        unresolved_steps: Optional[Sequence[str]] = None,
    ) -> FormalConjecture:
        """Register a new conjecture with explicit domains and assumptions."""
        if conjecture_id in self._conjectures:
            raise ValueError(f"Conjecture '{conjecture_id}' already registered")
        conj = FormalConjecture(
            conjecture_id=conjecture_id,
            domain=domain,
            statement=statement,
            assumptions=list(assumptions or []),
            unresolved_steps=list(unresolved_steps or []),
        )
        self._conjectures[conjecture_id] = conj
        return conj

    def get_conjecture(self, conjecture_id: str) -> Optional[FormalConjecture]:
        return self._conjectures.get(conjecture_id)

    def add_lemma(
        self,
        conjecture_id: str,
        lemma: Lemma,
    ) -> None:
        """Add a lemma to the conjecture proof DAG after cycle and dependency checks."""
        conj = self._conjectures.get(conjecture_id)
        if not conj:
            raise KeyError(f"Conjecture '{conjecture_id}' not found")

        # Verify dependencies exist
        existing_ids = {l.lemma_id for l in conj.lemmas}
        for dep in lemma.dependencies:
            if dep not in existing_ids:
                raise ProofDAGError(
                    f"Dependency '{dep}' not found in existing lemmas for {conjecture_id}"
                )

        if lemma.lemma_id in existing_ids:
            raise ProofDAGError(f"Duplicate lemma_id '{lemma.lemma_id}'")

        conj.lemmas.append(lemma)
        self.evaluate_proof_status(conjecture_id)

    def record_numerical_experiment(
        self,
        conjecture_id: str,
        experiment_name: str,
        parameters: Dict[str, Any],
        results: Dict[str, Any],
        consistent: bool,
    ) -> Dict[str, Any]:
        """Record numerical/heuristic experimental evidence.

        STRICT RULE: Numerical results provide evidence, NOT formal proof.
        Status moves at most to EXPERIMENTALLY_EVIDENCED if not already counterexampled.
        """
        conj = self._conjectures.get(conjecture_id)
        if not conj:
            raise KeyError(f"Conjecture '{conjecture_id}' not found")

        record = {
            "experiment_name": experiment_name,
            "parameters": parameters,
            "results": results,
            "consistent": consistent,
            "timestamp": time.time(),
            "claim": "NUMERICAL_EVIDENCE_NOT_FORMAL_PROOF",
        }
        conj.numerical_experiments.append(record)

        if not consistent:
            self.record_counterexample(
                conjecture_id,
                description=f"Experiment '{experiment_name}' produced inconsistent outcome",
                witness={"parameters": parameters, "results": results},
            )
        elif conj.status in (ConjectureStatus.CONJECTURED, ConjectureStatus.UNPROVEN_CLAIM):
            conj.status = ConjectureStatus.EXPERIMENTALLY_EVIDENCED

        return record

    def record_counterexample(
        self,
        conjecture_id: str,
        description: str,
        witness: Dict[str, Any],
    ) -> None:
        """Record a concrete counterexample, falsifying the conjecture or scope."""
        conj = self._conjectures.get(conjecture_id)
        if not conj:
            raise KeyError(f"Conjecture '{conjecture_id}' not found")

        entry = {
            "description": description,
            "witness": witness,
            "timestamp": time.time(),
        }
        conj.counterexamples.append(entry)
        conj.status = ConjectureStatus.COUNTEREXAMPLE_FOUND

    def verify_lemma(
        self,
        conjecture_id: str,
        lemma_id: str,
        proof_method: str,
        verification_receipt: str,
    ) -> None:
        """Mark a lemma as verified using a deterministic proof receipt."""
        conj = self._conjectures.get(conjecture_id)
        if not conj:
            raise KeyError(f"Conjecture '{conjecture_id}' not found")

        target_idx = -1
        for i, l in enumerate(conj.lemmas):
            if l.lemma_id == lemma_id:
                target_idx = i
                break
        if target_idx < 0:
            raise KeyError(f"Lemma '{lemma_id}' not found in {conjecture_id}")

        old_lemma = conj.lemmas[target_idx]
        new_lemma = Lemma(
            lemma_id=old_lemma.lemma_id,
            statement=old_lemma.statement,
            assumptions=old_lemma.assumptions,
            dependencies=old_lemma.dependencies,
            provenance=old_lemma.provenance,
            is_verified=True,
            proof_method=proof_method,
            verification_receipt=verification_receipt,
        )
        conj.lemmas[target_idx] = new_lemma
        self.evaluate_proof_status(conjecture_id)

    def evaluate_proof_status(self, conjecture_id: str) -> ConjectureStatus:
        """Determine status based on rigorous logical proof criteria."""
        conj = self._conjectures.get(conjecture_id)
        if not conj:
            raise KeyError(f"Conjecture '{conjecture_id}' not found")

        if conj.counterexamples:
            conj.status = ConjectureStatus.COUNTEREXAMPLE_FOUND
            return conj.status

        # If unresolved steps remain, it cannot be formally verified
        if conj.unresolved_steps:
            if any(l.is_verified for l in conj.lemmas):
                conj.status = ConjectureStatus.PARTIALLY_PROVEN
            elif conj.numerical_experiments:
                conj.status = ConjectureStatus.EXPERIMENTALLY_EVIDENCED
            else:
                conj.status = ConjectureStatus.CONJECTURED
            return conj.status

        if not conj.lemmas:
            conj.status = (
                ConjectureStatus.EXPERIMENTALLY_EVIDENCED
                if conj.numerical_experiments
                else ConjectureStatus.CONJECTURED
            )
            return conj.status

        # All lemmas must be verified
        all_verified = all(l.is_verified for l in conj.lemmas)
        if all_verified and len(conj.lemmas) > 0:
            conj.status = ConjectureStatus.FORMALLY_VERIFIED
        elif any(l.is_verified for l in conj.lemmas):
            conj.status = ConjectureStatus.PARTIALLY_PROVEN
        else:
            conj.status = (
                ConjectureStatus.EXPERIMENTALLY_EVIDENCED
                if conj.numerical_experiments
                else ConjectureStatus.CONJECTURED
            )

        return conj.status


__all__ = [
    "ConjectureStatus",
    "Lemma",
    "FormalConjecture",
    "ProofDAGError",
    "MathematicalProofTracker",
]
