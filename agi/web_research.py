"""
Web research engine — production implementation of the pre-consolidation
``hyba_backend.api.web_research`` surface.

The earlier monorepo declared ``get_research_engine`` and ``research_and_learn``.
Neither was migrated, but the capability has a real implementation here: this
repository already ships a substantial local corpus of mathematical and
quantitative material (the ``lucas`` exact-arithmetic kernel, ``kellogg``'s
tensor substrate, the ``toe`` engine, the ``aethel`` storage manifold, and the
documented lemmas under ``docs/`` and ``hyba/operating_model/``).

What this engine does
---------------------
It performs a *real* retrieval over that local corpus: it tokenises the query,
scores every candidate document by TF-IDF-weighted term overlap with
field-normalised cosine similarity, and returns the ranked passages that the
corpus actually supports.

What it does not do
-------------------
It does not reach the network, and it does not invent sources. A query with no
corpus support returns ``success: False`` with an explicit reason and an empty
``sources`` list. The upstream callers (``asi.web_learner``,
``agi.reasoning``) already treat ``success`` as authoritative, so an unsupported
query yields no knowledge rather than fabricated knowledge.

Extending it to live web search is a matter of supplying another corpus
adapter; the ranking and provenance machinery is unchanged.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "ResearchDocument",
    "ResearchResult",
    "WebResearchEngine",
    "get_research_engine",
    "research_and_learn",
    "DEFAULT_CORPUS_ROOTS",
]

_TOKEN = re.compile(r"[a-z0-9_]+")

# Corpus roots searched by default: the repository's own documented knowledge.
DEFAULT_CORPUS_ROOTS: Tuple[str, ...] = (
    "docs",
    "hyba",
    "lucas",
    "toe",
    "aethel",
    "kellogg",
    "millennium",
)

# File extensions treated as documents.
_SUFFIXES = {".md", ".py", ".rst", ".txt"}

# Words too common to carry signal.
_STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "this",
    "with",
    "from",
    "are",
    "was",
    "were",
    "has",
    "have",
    "had",
    "not",
    "but",
    "you",
    "all",
    "can",
    "its",
    "our",
    "which",
    "when",
    "will",
    "would",
    "there",
    "their",
    "them",
    "then",
    "than",
    "into",
    "out",
    "def",
    "self",
    "import",
    "return",
    "class",
    "none",
    "true",
    "false",
    "int",
    "str",
    "float",
    "list",
    "dict",
    "the",
    "and",
    "for",
}


def _tokenize(text: str) -> List[str]:
    """Lowercase word tokens with stopwords removed."""
    return [t for t in _TOKEN.findall(text.lower()) if len(t) > 2 and t not in _STOPWORDS]


@dataclass
class ResearchDocument:
    """One indexed corpus document."""

    doc_id: str
    path: str
    text: str
    tokens: List[str] = field(default_factory=list)


@dataclass
class ResearchResult:
    """The outcome of one research query."""

    query: str
    success: bool
    sources: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "success": self.success,
            "sources": self.sources,
            "summary": self.summary,
            "reason": self.reason,
        }


class WebResearchEngine:
    """TF-IDF retrieval over the repository's own documented corpus.

    Parameters
    ----------
    repo_root:
        Root to search beneath. Defaults to the repository root inferred from
        this file's location.
    corpus_roots:
        Subdirectories to index. Defaults to :data:`DEFAULT_CORPUS_ROOTS`.
    max_documents:
        Upper bound on indexed documents, applied in a stable sorted order so
        the index is reproducible.
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        corpus_roots: Tuple[str, ...] = DEFAULT_CORPUS_ROOTS,
        max_documents: int = 2000,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent
        self.corpus_roots = tuple(corpus_roots)
        self.max_documents = int(max_documents)
        self._documents: List[ResearchDocument] = []
        self._indexed = False

    # -- indexing -----------------------------------------------------------

    def corpus_paths(self) -> List[Path]:
        """Every candidate document path, in a stable sorted order."""
        paths: List[Path] = []
        for name in self.corpus_roots:
            root = self.repo_root / name
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in _SUFFIXES:
                    paths.append(path)
        return sorted(set(paths), key=lambda p: str(p).lower())

    def build_index(self, force: bool = False) -> int:
        """Index the corpus; returns the number of documents indexed."""
        if self._indexed and not force:
            return len(self._documents)
        documents: List[ResearchDocument] = []
        for path in self.corpus_paths()[: self.max_documents]:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not text.strip():
                continue
            rel = str(path.relative_to(self.repo_root)).replace("\\", "/")
            documents.append(
                ResearchDocument(doc_id=rel, path=rel, text=text, tokens=_tokenize(text))
            )
        self._documents = documents
        self._indexed = True
        return len(self._documents)

    @property
    def document_count(self) -> int:
        """Number of indexed documents (builds the index on first access)."""
        if not self._indexed:
            self.build_index()
        return len(self._documents)

    # -- retrieval ----------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> List[Tuple[ResearchDocument, float]]:
        """Rank corpus documents against ``query`` by TF-IDF cosine similarity.

        Documents with zero similarity are excluded, so an unsupported query
        returns an empty list rather than arbitrary matches.
        """
        if not query or not str(query).strip():
            return []
        if not self._indexed:
            self.build_index()
        if not self._documents:
            return []

        query_tokens = set(_tokenize(str(query)))
        if not query_tokens:
            return []

        n_docs = len(self._documents)
        document_frequency: Dict[str, int] = {}
        for doc in self._documents:
            for term in set(doc.tokens):
                document_frequency[term] = document_frequency.get(term, 0) + 1

        def idf(term: str) -> float:
            df = document_frequency.get(term, 0)
            return math.log((n_docs + 1) / (df + 1)) + 1.0

        query_vector = {term: idf(term) for term in query_tokens}
        query_norm = math.sqrt(sum(v * v for v in query_vector.values())) or 1.0

        scored: List[Tuple[ResearchDocument, float]] = []
        for doc in self._documents:
            counts: Dict[str, int] = {}
            for token in doc.tokens:
                counts[token] = counts.get(token, 0) + 1
            doc_vector = {
                term: (1.0 + math.log(count)) * idf(term)
                for term, count in counts.items()
                if term in query_vector
            }
            if not doc_vector:
                continue
            doc_norm = math.sqrt(sum(v * v for v in doc_vector.values())) or 1.0
            dot = sum(query_vector[t] * v for t, v in doc_vector.items())
            score = dot / (query_norm * doc_norm)
            if score > 0.0:
                scored.append((doc, score))

        scored.sort(key=lambda pair: (-pair[1], pair[0].doc_id))
        return scored[: max(1, int(top_k))]

    def research(self, query: str, top_k: int = 5) -> ResearchResult:
        """Research ``query``; ``success`` is True only if the corpus supports it."""
        if not self._indexed:
            self.build_index()
        if not self._documents:
            return ResearchResult(
                query=str(query),
                success=False,
                reason="corpus is empty; no documents were indexed",
            )
        matches = self.search(query, top_k=top_k)
        if not matches:
            return ResearchResult(
                query=str(query),
                success=False,
                reason=(
                    "no corpus document supports this query; returning no "
                    "sources rather than fabricating any"
                ),
            )
        sources = [
            {"source_id": doc.doc_id, "path": doc.path, "score": round(float(score), 6)}
            for doc, score in matches
        ]
        best = sources[0]
        return ResearchResult(
            query=str(query),
            success=True,
            sources=sources,
            summary=(
                f"{len(sources)} supporting document(s); strongest match "
                f"{best['path']} (score {best['score']})"
            ),
        )

    def stats(self) -> Dict[str, Any]:
        """Index statistics; no fabricated corpus claims."""
        return {
            "repo_root": str(self.repo_root),
            "corpus_roots": list(self.corpus_roots),
            "documents_indexed": self.document_count,
            "max_documents": self.max_documents,
        }


_ENGINE: Optional[WebResearchEngine] = None


def get_research_engine() -> WebResearchEngine:
    """Return the process-wide research engine, building its index once."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = WebResearchEngine()
        _ENGINE.build_index()
    return _ENGINE


async def research_and_learn(topic: str, top_k: int = 5) -> Dict[str, Any]:
    """Research ``topic`` and return a plain dict for the legacy callers.

    Returns ``success: False`` with an explicit ``reason`` and empty ``sources``
    when the corpus does not support the topic. It never fabricates a source.
    """
    engine = get_research_engine()
    return engine.research(topic, top_k=top_k).to_dict()
