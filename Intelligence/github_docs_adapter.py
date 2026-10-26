"""GitHub Docs Intelligence Adapter — adapts github/docs corpus for PYTHIA.

This module indexes, parses, and adapts the cloned `github/docs` repository
for consumption by PYTHIA and EUCLID agentic workflows. It translates raw
markdown documentation, REST schemas, and workflow guides into structured
semantic memory facts, queryable topic indices, and actionable operational tools.

Key domains indexed:
- **actions**: Workflow triggers, runners, syntax, matrix jobs, composite actions
- **rest**: REST API endpoints, headers, rate limits, pagination, authentication
- **webhooks**: Payload structures, HMAC SHA-256 verification, delivery events
- **code-security**: Secret scanning push protection, CodeQL SAST, Dependabot
- **repositories**: Branch rulesets, protected branches, environments, deployments
- **copilot**: AI-assisted development integration and capabilities
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Intelligence.github_docs_adapter")

# Default location for the cloned github/docs repository
DEFAULT_GITHUB_DOCS_PATH = os.environ.get(
    "GITHUB_DOCS_ROOT",
    r"C:\PythiaTemp\github-docs",
)

CORE_CATEGORIES = [
    "actions",
    "rest",
    "webhooks",
    "code-security",
    "repositories",
    "github-cli",
    "copilot",
    "graphql",
]


@dataclass
class GitHubDocResult:
    """A search result or extracted topic from the GitHub Docs corpus."""

    title: str
    category: str
    relative_path: str
    summary: str
    score: float = 1.0
    tags: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Structured Knowledge Seeds: Ready for PYTHIA semantic memory
# ---------------------------------------------------------------------------

GITHUB_KNOWLEDGE_FACTS: List[Dict[str, Any]] = [
    {
        "concept": "github_actions_workflow",
        "category": "ci_cd_automation",
        "definition": (
            "A configurable automated process composed of one or more jobs defined in YAML under "
            ".github/workflows/. Runs upon specified events (push, pull_request, schedule, workflow_dispatch)."
        ),
        "properties": {
            "config_dir": ".github/workflows/",
            "key_primitives": ["on", "jobs", "steps", "runs-on", "env", "secrets", "strategy.matrix"],
            "security": "Enforce minimal GITHUB_TOKEN permissions (read-all, write only on required scopes).",
        },
        "confidence": 1.0,
        "provenance": "github/docs/actions",
    },
    {
        "concept": "github_rest_api_protocol",
        "category": "api_integration",
        "definition": (
            "GitHub's HTTP REST API for querying and controlling repositories, pull requests, releases, "
            "and workflows. Standard endpoint prefix is https://api.github.com/."
        ),
        "properties": {
            "auth_header": "Authorization: Bearer <token>",
            "api_version_header": "X-GitHub-Api-Version: 2022-11-28",
            "rate_limit_authenticated": 5000,
            "rate_limit_headers": ["x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"],
        },
        "confidence": 1.0,
        "provenance": "github/docs/rest",
    },
    {
        "concept": "github_webhook_verification",
        "category": "event_driven_security",
        "definition": (
            "Cryptographic integrity verification of incoming GitHub webhooks via HMAC-SHA256 signature "
            "carried in the X-Hub-Signature-256 header, computed over the raw request payload using a shared secret."
        ),
        "properties": {
            "signature_header": "X-Hub-Signature-256",
            "algorithm": "hmac-sha256",
            "constant_time_comparison": True,
        },
        "confidence": 1.0,
        "provenance": "github/docs/webhooks",
    },
    {
        "concept": "github_branch_rulesets",
        "category": "governance_and_compliance",
        "definition": (
            "Unified governance rules controlling push, merge, and deletion behaviors on target branch patterns. "
            "Replaces legacy branch protection with layered evaluation, bypass actors, and status check enforcement."
        ),
        "properties": {
            "enforcement_levels": ["active", "evaluate", "disabled"],
            "core_rules": ["pull_request_reviews", "required_status_checks", "block_force_pushes", "deletion"],
        },
        "confidence": 1.0,
        "provenance": "github/docs/repositories",
    },
    {
        "concept": "github_code_security_suite",
        "category": "security_engineering",
        "definition": (
            "Integrated vulnerability management suite comprising Secret Scanning with Push Protection, "
            "Dependabot software supply chain security, and CodeQL semantic AST static analysis."
        ),
        "properties": {
            "push_protection": "Blocks commits containing high-entropy tokens before remote acceptance.",
            "codeql_sast": "Models-as-data semantic queries analyzing taint flow and data paths.",
            "dependabot": "Automated security updates and package manifest vulnerability scanning.",
        },
        "confidence": 1.0,
        "provenance": "github/docs/code-security",
    },
]

GITHUB_KNOWLEDGE_ASSOCIATIONS: List[Dict[str, Any]] = [
    {
        "from": "github_actions_workflow",
        "to": "github_code_security_suite",
        "relation": "executes_security_scanning",
        "weight": 0.95,
    },
    {
        "from": "github_rest_api_protocol",
        "to": "github_actions_workflow",
        "relation": "dispatches_and_monitors",
        "weight": 0.9,
    },
    {
        "from": "github_webhook_verification",
        "to": "github_rest_api_protocol",
        "relation": "secures_inbound_callbacks",
        "weight": 0.85,
    },
    {
        "from": "github_branch_rulesets",
        "to": "github_actions_workflow",
        "relation": "requires_passing_checks",
        "weight": 0.95,
    },
]


class GitHubDocsCorpus:
    """Parser, search index, and adapter for the GitHub Docs corpus."""

    def __init__(self, root_path: Optional[str] = None) -> None:
        self.root_path = Path(root_path or DEFAULT_GITHUB_DOCS_PATH)
        self.content_path = self.root_path / "content"
        self._index: Dict[str, List[Path]] = {}
        self._built = False

    @property
    def is_available(self) -> bool:
        """Return True if the corpus root and content directories exist."""
        return self.content_path.exists() and self.content_path.is_dir()

    def build_index(self) -> int:
        """Index markdown files by category."""
        if not self.is_available:
            logger.info("GitHub Docs corpus not found at %s", self.content_path)
            return 0

        self._index.clear()
        total_files = 0

        for cat in CORE_CATEGORIES:
            cat_dir = self.content_path / cat
            if cat_dir.exists():
                md_files = list(cat_dir.glob("**/*.md"))
                self._index[cat] = md_files
                total_files += len(md_files)

        self._built = True
        logger.info("Indexed %d GitHub Docs files across %d categories", total_files, len(self._index))
        return total_files

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        max_results: int = 5,
    ) -> List[GitHubDocResult]:
        """Search documentation articles matching the query.

        Args:
            query: Free-text search terms (e.g. 'actions matrix', 'rate limit')
            category: Optional category filter (e.g. 'actions', 'rest')
            max_results: Maximum results to return

        Returns:
            List of matching GitHubDocResult instances sorted by relevance score
        """
        if not self._built:
            self.build_index()

        terms = [t.lower() for t in query.split() if len(t) > 2]
        if not terms:
            return []

        results: List[GitHubDocResult] = []
        categories_to_search = [category] if category and category in self._index else list(self._index.keys())

        for cat in categories_to_search:
            for file_path in self._index.get(cat, []):
                try:
                    rel_path = file_path.relative_to(self.content_path).as_posix()
                    file_name = file_path.stem.replace("-", " ")
                    
                    # Read header and snippet
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        header_chunk = f.read(2048)

                    # Extract title from frontmatter or first heading
                    title = file_name.capitalize()
                    title_match = re.search(r"title:\s*['\"]?(.*?)['\"]?\s*\n", header_chunk)
                    if title_match:
                        title = title_match.group(1).strip()
                    elif header_chunk.startswith("#"):
                        first_line = header_chunk.splitlines()[0].lstrip("#").strip()
                        if first_line:
                            title = first_line

                    # Calculate match score
                    score = 0.0
                    text_lower = (title + " " + header_chunk).lower()
                    for term in terms:
                        if term in file_name.lower():
                            score += 5.0
                        if term in title.lower():
                            score += 3.0
                        if term in text_lower:
                            score += 1.0

                    if score > 0:
                        # Extract intro text as summary
                        intro_match = re.search(r"intro:\s*['\"]?(.*?)['\"]?\s*\n", header_chunk)
                        summary = intro_match.group(1).strip() if intro_match else ""
                        if not summary:
                            lines = [ln.strip() for ln in header_chunk.splitlines() if ln.strip() and not ln.startswith(("#", "---", "title:", "intro:"))]
                            summary = lines[0][:200] if lines else title

                        results.append(
                            GitHubDocResult(
                                title=title,
                                category=cat,
                                relative_path=rel_path,
                                summary=summary,
                                score=score,
                                tags=[cat],
                            )
                        )
                except Exception as e:
                    logger.debug("Failed to read doc file %s: %s", file_path, e)

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]

    def get_article(self, relative_path: str) -> Optional[str]:
        """Retrieve the markdown content of an article by relative path."""
        target = self.content_path / relative_path
        if not target.exists() or not target.is_file():
            return None
        try:
            with open(target, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.warning("Error reading article %s: %s", relative_path, e)
            return None


def extract_knowledge_facts() -> List[Dict[str, Any]]:
    """Return the structured knowledge facts for PYTHIA semantic memory."""
    return list(GITHUB_KNOWLEDGE_FACTS)


def seed_github_knowledge(semantic_memory: Optional[Any] = None) -> Dict[str, Any]:
    """Seed PYTHIA semantic memory with GitHub Docs concepts and associations.

    Args:
        semantic_memory: An instance of PYTHIA's SemanticMemory (optional)

    Returns:
        Dict summarizing concepts and associations seeded
    """
    concepts_added = 0
    associations_added = 0

    if semantic_memory is not None:
        for fact in GITHUB_KNOWLEDGE_FACTS:
            try:
                semantic_memory.add_concept(
                    fact["concept"],
                    category=fact["category"],
                    definition=fact["definition"],
                    properties=fact.get("properties", {}),
                    confidence=fact.get("confidence", 1.0),
                    provenance=fact.get("provenance", "github/docs"),
                )
                concepts_added += 1
            except Exception as e:
                logger.warning("Failed to seed concept %s: %s", fact["concept"], e)

        for assoc in GITHUB_KNOWLEDGE_ASSOCIATIONS:
            try:
                semantic_memory.add_association(
                    assoc["from"],
                    assoc["to"],
                    relation=assoc["relation"],
                    weight=assoc.get("weight", 0.5),
                )
                associations_added += 1
            except Exception as e:
                logger.warning("Failed to seed association: %s", e)

    return {
        "concepts_seeded": concepts_added,
        "associations_seeded": associations_added,
        "available_categories": CORE_CATEGORIES,
        "static_fact_count": len(GITHUB_KNOWLEDGE_FACTS),
    }


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Substrate route: amplitude. Proof of live execution wiring.
    """
    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result


__all__ = [
    "GitHubDocsCorpus",
    "GitHubDocResult",
    "GITHUB_KNOWLEDGE_FACTS",
    "GITHUB_KNOWLEDGE_ASSOCIATIONS",
    "extract_knowledge_facts",
    "seed_github_knowledge",
    "DEFAULT_GITHUB_DOCS_PATH",
    "lucas_bound",
]
