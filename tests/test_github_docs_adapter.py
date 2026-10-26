"""Unit tests for Intelligence.github_docs_adapter.

Validates corpus discovery, indexing, search relevance, knowledge extraction,
semantic memory seeding, and tool registry integration.
"""

from __future__ import annotations

import pytest
from Intelligence.github_docs_adapter import (
    GitHubDocsCorpus,
    GitHubDocResult,
    extract_knowledge_facts,
    seed_github_knowledge,
    lucas_bound,
    CORE_CATEGORIES,
)
from Intelligence.pythia_tools import TOOLS, build_tool_registry


class MockSemanticMemory:
    """Mock semantic memory to verify knowledge seeding."""

    def __init__(self) -> None:
        self.concepts: dict = {}
        self.associations: list = []

    def add_concept(self, name: str, **kwargs) -> None:
        self.concepts[name] = kwargs

    def add_association(self, from_c: str, to_c: str, **kwargs) -> None:
        self.associations.append({"from": from_c, "to": to_c, **kwargs})


def test_corpus_instantiation() -> None:
    """Test that GitHubDocsCorpus instantiates with valid defaults."""
    corpus = GitHubDocsCorpus()
    assert corpus.root_path is not None
    assert corpus.content_path is not None


def test_corpus_search_and_indexing() -> None:
    """Test corpus indexing and search functionality."""
    corpus = GitHubDocsCorpus()
    if not corpus.is_available:
        pytest.skip("GitHub docs clone not available in test environment")

    total_indexed = corpus.build_index()
    assert total_indexed > 100, f"Expected >100 indexed files, got {total_indexed}"

    # Test search for actions
    action_results = corpus.search("workflow trigger", category="actions", max_results=3)
    assert len(action_results) > 0
    assert all(r.category == "actions" for r in action_results)
    assert all(isinstance(r, GitHubDocResult) for r in action_results)

    # Test search for rest api
    rest_results = corpus.search("rate limit headers", category="rest", max_results=3)
    assert len(rest_results) > 0
    assert all(r.category == "rest" for r in rest_results)


def test_corpus_get_article() -> None:
    """Test retrieving article content by relative path."""
    corpus = GitHubDocsCorpus()
    if not corpus.is_available:
        pytest.skip("GitHub docs clone not available in test environment")

    # Non-existent article returns None safely
    assert corpus.get_article("non_existent_article_xyz.md") is None


def test_knowledge_facts_contract() -> None:
    """Verify extracted knowledge facts conform to PYTHIA's memory schema."""
    facts = extract_knowledge_facts()
    assert len(facts) >= 5

    required_keys = {"concept", "category", "definition", "properties", "confidence", "provenance"}
    for fact in facts:
        assert required_keys.issubset(fact.keys()), f"Fact missing required keys: {fact}"
        assert isinstance(fact["concept"], str)
        assert isinstance(fact["properties"], dict)
        assert fact["confidence"] == 1.0


def test_seed_github_knowledge() -> None:
    """Test seeding into mock semantic memory."""
    mem = MockSemanticMemory()
    result = seed_github_knowledge(mem)

    assert result["concepts_seeded"] == len(mem.concepts)
    assert result["concepts_seeded"] >= 5
    assert result["associations_seeded"] == len(mem.associations)
    assert result["associations_seeded"] >= 4

    assert "github_actions_workflow" in mem.concepts
    assert "github_rest_api_protocol" in mem.concepts
    assert "github_webhook_verification" in mem.concepts
    assert "github_branch_rulesets" in mem.concepts
    assert "github_code_security_suite" in mem.concepts


def test_lucas_pool_bound() -> None:
    """Verify live Lucas pool verification route."""
    bound = lucas_bound(10)
    assert bound["module"] == "Intelligence.github_docs_adapter"
    assert "kernel" in bound


def test_tool_registry_integration() -> None:
    """Verify that github_docs_search is properly registered in PYTHIA tools."""
    tool_map = build_tool_registry()
    assert "github_docs_search" in tool_map
    tool = tool_map["github_docs_search"]
    assert tool.category == "knowledge"
    assert tool.callable_name == "search"
    assert "query" in tool.inputs
