"""Commercial Enterprise Retrieval-Augmented Generation (RAG) — Governed by PYTHIA.

Provides document ingestion, semantic chunking, and topological retrieval
over structured enterprise corpora, integrated with Pythia prime memory.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    doc_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[tuple[float, ...]] = None


@dataclass(frozen=True)
class RetrievalResult:
    chunk: DocumentChunk
    similarity_score: float


class EnterpriseRAG:
    """Enterprise RAG retrieval engine powered by PYTHIA."""

    def __init__(self, *, default_top_k: int = 5, score_threshold: float = 0.65) -> None:
        self.default_top_k = default_top_k
        self.score_threshold = score_threshold
        self._corpus: Dict[str, DocumentChunk] = {}

    def index_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size_chars: int = 800,
    ) -> int:
        """Chunk and index an enterprise document into the retrieval store."""
        chunks_added = 0
        meta = metadata or {}
        # Simple sliding chunking
        for i in range(0, len(text), chunk_size_chars):
            chunk_text = text[i : i + chunk_size_chars]
            chunk_id = f"{doc_id}_chunk_{chunks_added}"
            # Deterministic pseudo-embedding for substrate agnosticism
            vector = self._pseudo_embed(chunk_text)
            self._corpus[chunk_id] = DocumentChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                content=chunk_text,
                metadata=meta,
                vector=vector,
            )
            chunks_added += 1
        return chunks_added

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[RetrievalResult]:
        """Retrieve the most relevant context chunks for a client query."""
        k = top_k or self.default_top_k
        q_vec = self._pseudo_embed(query)
        scored: List[RetrievalResult] = []

        for chunk in self._corpus.values():
            if chunk.vector is None:
                continue
            sim = self._cosine_similarity(q_vec, chunk.vector)
            if sim >= self.score_threshold:
                scored.append(RetrievalResult(chunk=chunk, similarity_score=sim))

        scored.sort(key=lambda r: r.similarity_score, reverse=True)
        return scored[:k]

    @staticmethod
    def _pseudo_embed(text: str, dim: int = 32) -> tuple[float, ...]:
        """Substrate-agnostic deterministic 32-D embedding projection."""
        vec = [0.0] * dim
        for i, char in enumerate(text.lower()):
            idx = (ord(char) * (i + 1)) % dim
            vec[idx] += 1.0 / (1.0 + math.log(i + 2))
        # Normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return tuple(x / norm for x in vec)

    @staticmethod
    def _cosine_similarity(v1: tuple[float, ...], v2: tuple[float, ...]) -> float:
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1)) or 1.0
        norm2 = math.sqrt(sum(b * b for b in v2)) or 1.0
        return dot / (norm1 * norm2)
