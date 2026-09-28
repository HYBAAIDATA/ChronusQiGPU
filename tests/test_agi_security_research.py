"""Gateway security and corpus research: the two fail-closed contracts.

Both modules replace pre-consolidation classes that were never migrated, and
both have security/honesty implications, so the tests assert the *failure*
behaviour as carefully as the success behaviour:

* with no keys configured, verification fails closed rather than allowing access;
* keys are compared in constant time and never stored in the clear;
* research returns no sources when the corpus does not support the query.
"""

import hashlib

from agi.quantum_security import (
    APIKey,
    SecurityManager,
    digest_key,
    verify_api_key,
)
from agi.web_research import WebResearchEngine, get_research_engine, research_and_learn

# --------------------------------------------------------------------------
# quantum_security
# --------------------------------------------------------------------------


def test_digest_is_stable_and_hides_the_key():
    raw = "super-secret-value"
    digest = digest_key(raw)
    assert digest == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert raw not in digest


def test_manager_with_no_keys_fails_closed():
    manager = SecurityManager(keys=[])
    manager.load_from_environment(env={})
    assert manager.fail_closed is True
    ok, key, reason = manager.verify("anything")
    assert ok is False
    assert key is None
    assert reason == "fail_closed"


def test_verify_api_key_denies_when_unconfigured():
    # The process-wide manager is unconfigured in the test environment.
    assert verify_api_key("anything") is False


def test_registered_key_verifies_and_carries_its_identity():
    raw = "real-key-123"
    key = APIKey(key_id="k1", digest=digest_key(raw), role="admin", scopes=("read",))
    manager = SecurityManager(keys=[key])
    assert manager.fail_closed is False

    ok, matched, reason = manager.verify(raw)
    assert ok is True
    assert reason == "ok"
    assert matched is key
    assert matched.role == "admin"
    assert matched.has_scope("read") is True
    assert matched.has_scope("write") is False


def test_wrong_key_is_rejected():
    manager = SecurityManager(keys=[APIKey(key_id="k1", digest=digest_key("right"))])
    ok, matched, reason = manager.verify("wrong")
    assert ok is False
    assert matched is None
    assert reason == "invalid_key"


def test_missing_key_is_rejected_distinctly():
    manager = SecurityManager(keys=[APIKey(key_id="k1", digest=digest_key("right"))])
    ok, _matched, reason = manager.verify(None)
    assert ok is False
    assert reason == "missing_key"


def test_environment_loading_parses_entries():
    raw = "alpha"
    env = {"QUANTUM_SECURITY_API_KEYS": f"k1:{digest_key(raw)}:admin:read|write"}
    manager = SecurityManager(keys=[])
    assert manager.load_from_environment(env=env) == 1
    ok, key, _reason = manager.verify(raw)
    assert ok is True
    assert key.role == "admin"
    assert key.has_scope("write") is True


def test_stats_never_expose_key_material():
    raw = "top-secret"
    manager = SecurityManager(keys=[APIKey(key_id="k1", digest=digest_key(raw))])
    rendered = str(manager.stats())
    assert raw not in rendered
    assert "post_quantum_note" in manager.stats()


def test_wildcard_scope_grants_everything():
    key = APIKey(key_id="k", digest=digest_key("x"), scopes=("*",))
    assert key.has_scope("anything") is True


# --------------------------------------------------------------------------
# web_research
# --------------------------------------------------------------------------


def test_engine_indexes_a_real_corpus():
    engine = WebResearchEngine()
    assert engine.document_count > 0


def test_research_finds_real_repository_documents():
    engine = WebResearchEngine()
    result = engine.research("golden ratio lucas fibonacci", top_k=3)
    assert result.success is True
    assert result.sources
    for source in result.sources:
        assert source["path"]  # a real path, not a fabricated URL
        assert source["score"] > 0.0


def test_unsupported_query_returns_no_sources_rather_than_ones():
    engine = WebResearchEngine()
    result = engine.research("zzzqqqxxx nonexistent gibberishtoken", top_k=3)
    assert result.success is False
    assert result.sources == []
    assert result.reason


def test_empty_query_is_handled():
    engine = WebResearchEngine()
    assert engine.search("") == []
    assert engine.research("   ").success is False


def test_scores_are_descending():
    engine = WebResearchEngine()
    matches = engine.search("golden ratio", top_k=5)
    scores = [score for _doc, score in matches]
    assert scores == sorted(scores, reverse=True)


def test_research_is_reproducible():
    engine = WebResearchEngine()
    first = engine.research("cassini invariant", top_k=3)
    second = engine.research("cassini invariant", top_k=3)
    assert first.to_dict() == second.to_dict()


def test_module_level_helpers_return_plain_dicts():
    assert get_research_engine() is get_research_engine()
    payload = __import__("asyncio").run(research_and_learn("lucas sequence", top_k=2))
    assert set(payload) >= {"query", "success", "sources", "reason"}
    assert isinstance(payload["success"], bool)
