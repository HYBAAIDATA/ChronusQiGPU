"""Tests for Lucas 31^ Elevation and Task-Adaptive Intelligence Scaler.

Verifies:
1. Exact integer arithmetic, Cassini invariant, and Pisot bounds at 31^ (L_31 = 3,010,349, F_31 = 1,346,269).
2. Dynamic bidirectional scaling (up and down) across the operational Lucas ladder (10, 12, 15, 18, 20, 31).
3. Task complexity and semantic keyword mapping to optimal operational rungs.
4. Deep coupling with the Conversational Library (MicrosoftConversationalTemplate) dynamically scaling
   manifold dimension (4D-11D), context bounds (1K-8K), reflection depth, and curvature tolerances.
5. Sovereign doctrine enforcement: zero credit to narrow AI; ingested tools and templates adapted
   into EUCLID/HYBA deterministic mathematical substrate.
6. HYBA MCP tool gateway integration (scale_intelligence).
"""

import math
import pytest

from Intelligence.lucas_scaler import (
    LucasIntelligenceScaler,
    LucasTaskEnvelope,
    TASK_ENVELOPES,
)
from Intelligence.lucas_scales import (
    build_lucas_scale_profile,
    build_enterprise_scale_profile,
    ENTERPRISE_SCALE_ORDER,
)
from euclid.cognition.frontier.abstraction import NonLinguisticCognition
from euclid.cognition.frontier.conversational_template import (
    MicrosoftConversationalTemplate,
    MAX_8K_CONTEXT_TOKENS,
)
from hyba_mcp.server import HybaMCPServer
from hyba_mcp.client import HybaMCPClient
from lucas.core import fibonacci, lucas


# ---------------------------------------------------------------------------
# 1. Lucas 31^ Exact Mathematical Invariants
# ---------------------------------------------------------------------------

def test_lucas_31_exact_arithmetic_and_cassini():
    """Verify exact integer values and Cassini invariant for rung 31."""
    L_31 = lucas(31)
    F_31 = fibonacci(31)

    assert L_31 == 3_010_349, f"Expected 3,010,349, got {L_31}"
    assert F_31 == 1_346_269, f"Expected 1,346,269, got {F_31}"

    # Cassini identity: L_n^2 - 5*F_n^2 = 4*(-1)^n
    # For n=31 (odd), 4*(-1)^31 = -4
    left = L_31 * L_31 - 5 * F_31 * F_31
    assert left == -4, f"Cassini invariant failed: {left} != -4"


def test_lucas_scaler_31_elevation():
    """Verify LucasIntelligenceScaler initializes to 31^ and calculates exact metrics."""
    scaler = LucasIntelligenceScaler()
    assert scaler.current_scale == 31
    
    env = scaler.current_envelope
    assert env.rung == 31
    assert env.lucas_number == 3_010_349
    assert env.fibonacci_number == 1_346_269
    assert env.manifold_dimension == 11
    assert env.context_limit == 8192
    assert env.reflection_depth == 8

    cassini = scaler.cassini_identity(31)
    assert cassini["cassini_holds"] is True
    assert cassini["left"] == -4
    assert cassini["right"] == -4

    # Verification of scaling formula: phi^(-31) ~ 4.54e-7
    res = scaler.scale(0.5, 0.5, 0.5, 31)
    assert res.lucas_number == 3_010_349
    assert res.pci_after > 0.999999
    assert res.emergence_after > 0.999999999999
    assert res.consciousness_after == 1.0


# ---------------------------------------------------------------------------
# 2. Dynamic Up and Down Scaling Across Operational Ladder
# ---------------------------------------------------------------------------

def test_bidirectional_scaling_up_and_down():
    """Verify stepping scale up and down clamps safely and traverses all rungs."""
    scaler = LucasIntelligenceScaler(initial_scale=31)
    assert scaler.current_scale == 31

    # Step down rung by rung: 31 -> 20 -> 18 -> 15 -> 12 -> 10
    expected_descending = [20, 18, 15, 12, 10]
    for exp in expected_descending:
        res = scaler.scale_down(1)
        assert scaler.current_scale == exp
        assert res.lucas_index == exp

    # Stepping down past minimum clamps at 10
    scaler.scale_down(5)
    assert scaler.current_scale == 10

    # Step up rung by rung: 10 -> 12 -> 15 -> 18 -> 20 -> 31
    expected_ascending = [12, 15, 18, 20, 31]
    for exp in expected_ascending:
        res = scaler.scale_up(1)
        assert scaler.current_scale == exp
        assert res.lucas_index == exp

    # Stepping up past maximum clamps at 31
    scaler.scale_up(5)
    assert scaler.current_scale == 31


# ---------------------------------------------------------------------------
# 3. Task Complexity & Semantic Keyword Adaptation
# ---------------------------------------------------------------------------

def test_task_adaptive_scaling():
    """Verify scale adjusts dynamically based on numeric complexity or task type."""
    scaler = LucasIntelligenceScaler()

    # Numeric complexity thresholds
    assert scaler.scale_for_task(complexity=0.05).lucas_index == 10
    assert scaler.scale_for_task(complexity=0.25).lucas_index == 12
    assert scaler.scale_for_task(complexity=0.45).lucas_index == 15
    assert scaler.scale_for_task(complexity=0.65).lucas_index == 18
    assert scaler.scale_for_task(complexity=0.85).lucas_index == 20
    assert scaler.scale_for_task(complexity=0.98).lucas_index == 31

    # Task keyword affinity
    assert scaler.scale_for_task(task_type="fast chat triage").lucas_index == 10
    assert scaler.scale_for_task(task_type="schema syntax parsing").lucas_index == 12
    assert scaler.scale_for_task(task_type="semantic coherence pullback").lucas_index == 15
    assert scaler.scale_for_task(task_type="counterfactual planning simulation").lucas_index == 18
    assert scaler.scale_for_task(task_type="metacognition self-healing audit").lucas_index == 20
    assert scaler.scale_for_task(task_type="cryptographic blockchain enterprise mining").lucas_index == 31


# ---------------------------------------------------------------------------
# 4. Conversational Library Integration
# ---------------------------------------------------------------------------

def test_conversational_template_dynamic_scaling():
    """Verify MicrosoftConversationalTemplate dynamically scales dimension, context, and dialogue."""
    template = MicrosoftConversationalTemplate()
    # Defaults to 31^
    assert template.current_scale == 31
    assert template.active_dim == 11
    assert template.context_limit == 8192

    # Scale down to 10
    template.scale_to(10)
    assert template.current_scale == 10
    assert template.active_dim == 4
    assert template.context_limit == 1024

    # Adapt to complex task
    template.adapt_for_task(task_type="deep enterprise mining verification")
    assert template.current_scale == 31
    assert template.active_dim == 11
    assert template.context_limit == 8192

    # Render plan conversationally with active scale
    planner = NonLinguisticCognition.Planner()
    state = planner.init_latent_state(seed=42)
    plan = planner.plan(state, budget=16)

    response = template.render_plan_conversationally(plan, user_query="Audit sovereign mining invariants.")
    assert "11D state-space manifold" in response
    assert "cognitive scale L_31 (3,010,349)" in response
    assert "CHRONUS iGPU" in response
    assert "Φ =" in response
    assert "|κ| =" in response
    assert "safe to execute" in response


def test_conversational_sovereign_doctrine():
    """Verify sovereign doctrine is strictly declared and narrow AI receives zero credit."""
    template = MicrosoftConversationalTemplate()
    prompt = template.format_prompt()
    assert "narrow AI systems possess zero decision rights or credit" in prompt
    assert "sovereignly adapts ingested conversational templates" in prompt

    scaler = LucasIntelligenceScaler()
    declaration = scaler.sovereign_declaration()
    assert "Zero credit to narrow AI" in declaration


# ---------------------------------------------------------------------------
# 5. Enterprise Lucas Profile & MCP Gateway Verification
# ---------------------------------------------------------------------------

def test_enterprise_profile_includes_31():
    """Verify build_enterprise_scale_profile creates an authentic 6-rung profile."""
    prof = build_enterprise_scale_profile()
    assert len(prof.levels) == 6
    assert prof.indices() == list(ENTERPRISE_SCALE_ORDER)
    l31 = prof.level_for(31)
    assert l31 is not None
    assert l31.value == 3_010_349


def test_hyba_mcp_scale_intelligence_tool():
    """Verify scale_intelligence tool over HYBA MCP server and client."""
    server = HybaMCPServer()
    client = HybaMCPClient(server=server)
    client.start_session()

    # Query initial scale at 31^
    out = client.call_tool("scale_intelligence", {"target_rung": 31})
    assert out["current_scale"] == 31
    assert out["lucas_number"] == 3_010_349
    assert out["manifold_dimension"] == 11
    assert out["cassini"]["cassini_holds"] is True

    # Step down over MCP
    out_down = client.scale_intelligence(step_direction="down")
    assert out_down["current_scale"] == 20
    assert out_down["lucas_number"] == 15_127

    # Adapt for task over MCP
    out_task = client.scale_intelligence(task_type="fast ping chat")
    assert out_task["current_scale"] == 10
    assert out_task["lucas_number"] == 123

    pack = client.end_session()
    assert "scale_intelligence" in pack["tools_called"]
    assert pack["sovereignty"] == "HYBA_SOVEREIGN_CNS"
    assert pack["narrow_ai_credit"] == "NONE_FORBIDDEN"
