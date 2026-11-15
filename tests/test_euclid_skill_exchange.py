"""Authorization, custody and bounded-response regressions for EUCLID skill exchange."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from euclid.cognition.integrated.skills import SkillLibrary, SkillRecord
from hyba_mcp.euclid_skill_exchange import EuclidSkillExchange


class Exchange(EuclidSkillExchange):
    def __init__(self, knowledge, *, persisted_tenant="tenant", authorize=None):
        runtime = SimpleNamespace(_adaptive_tenant_id="tenant")
        super().__init__(
            runtime,
            authorize=authorize or (lambda actor, tenant, mission, tool: True),
        )
        self._knowledge = knowledge
        self._persisted_tenant = persisted_tenant
        self._custody_error = None

    def _verified_knowledge(self):
        if self._custody_error is not None:
            raise self._custody_error
        return self._knowledge, self._persisted_tenant, "binding-1"


def knowledge_with_skill(*, provenance="test-fixture"):
    library = SkillLibrary()
    record = SkillRecord(
        "skill-test",
        (("add", "r0", 1),),
        "skill",
        provenance,
        status="promoted",
        semantic="a" * 64,
        held_out_utility=1.0,
        adversarial_failures=0,
    )
    library.records[record.skill_id] = record
    return SimpleNamespace(skills=library, memory=SimpleNamespace())


def test_authorization_denial_occurs_before_custody_access():
    exchange = Exchange(
        knowledge_with_skill(),
        authorize=lambda *_: False,
    )
    exchange._custody_error = AssertionError("custody must not be touched")
    with pytest.raises(PermissionError, match="access denied"):
        exchange.execute_tool(
            "euclid_skills_list", {"mission_id": "mission"}, actor_id="actor"
        )


def test_authorizer_failure_fails_closed():
    def broken(*_):
        raise OSError("policy unavailable")

    exchange = Exchange(knowledge_with_skill(), authorize=broken)
    with pytest.raises(PermissionError, match="authorizer unavailable"):
        exchange.execute_tool(
            "euclid_skills_list", {"mission_id": "mission"}, actor_id="actor"
        )


def test_persisted_tenant_mismatch_is_denied():
    exchange = Exchange(knowledge_with_skill(), persisted_tenant="other-tenant")
    with pytest.raises(PermissionError, match="tenant mismatch"):
        exchange.execute_tool(
            "euclid_skills_list", {"mission_id": "mission"}, actor_id="actor"
        )


def test_corrupt_or_unavailable_custody_fails_closed():
    exchange = Exchange(knowledge_with_skill())
    exchange._custody_error = RuntimeError("custody seal mismatch")
    with pytest.raises(RuntimeError, match="custody seal mismatch"):
        exchange.execute_tool(
            "euclid_skills_list", {"mission_id": "mission"}, actor_id="actor"
        )


def test_promoted_skill_export_and_render_are_bounded_and_read_only():
    exchange = Exchange(knowledge_with_skill())
    listed = exchange.execute_tool(
        "euclid_skills_list", {"mission_id": "mission"}, actor_id="actor"
    )
    assert [row["skill_id"] for row in listed["skills"]] == ["skill-test"]
    fetched = exchange.execute_tool(
        "euclid_skill_get",
        {"mission_id": "mission", "skill_id": "skill-test"},
        actor_id="actor",
    )
    assert fetched["skill"]["status"] == "promoted"
    rendered = exchange.execute_tool(
        "euclid_skill_render",
        {"mission_id": "mission", "skill_id": "skill-test", "roles": {"r0": 0}},
        actor_id="actor",
    )
    assert rendered["execution_performed"] is False
    assert rendered["authority_granted"] is False


def test_memory_recall_fails_closed_until_custody_has_mission_binding():
    exchange = Exchange(knowledge_with_skill())
    with pytest.raises(PermissionError, match="mission-scoped"):
        exchange.execute_tool(
            "euclid_memory_recall",
            {
                "mission_id": "mission",
                "features": ["class:assign|small|balanced"],
            },
            actor_id="actor",
        )


def test_pipe_delimited_structural_features_pass_argument_validation():
    args = EuclidSkillExchange._validate_arguments(
        "euclid_memory_recall",
        {
            "mission_id": "mission",
            "features": ["class:assign|small|balanced"],
        },
    )
    assert args["features"] == ["class:assign|small|balanced"]


def test_complete_response_size_limit_is_enforced():
    exchange = Exchange(knowledge_with_skill(provenance="x" * 70000))
    with pytest.raises(RuntimeError, match="total size limit"):
        exchange.execute_tool(
            "euclid_skill_get",
            {"mission_id": "mission", "skill_id": "skill-test"},
            actor_id="actor",
        )


@pytest.mark.parametrize(
    "arguments",
    [
        {"mission_id": "mission", "skill_id": "skill-test", "extra": True},
        {"mission_id": "mission", "skill_id": "../escape"},
        {"mission_id": "mission", "skill_id": "skill-test", "roles": {"bad": 0}},
    ],
)
def test_argument_validation_rejects_uncontracted_or_invalid_render_inputs(arguments):
    with pytest.raises(ValueError):
        EuclidSkillExchange._validate_arguments("euclid_skill_render", arguments)
