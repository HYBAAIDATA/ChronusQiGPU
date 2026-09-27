"""
HYBA SOFTWARE LTD
Core Intelligence Infrastructure - Autonomy Governance
=====================================================
Author  : Andre Taylor-Morris, Founder & CEO
Date    : March 2026
Status  : Production Implementation
Classification: Most Sensitive — Internal Engineering

WHAT AGENTS CAN DO WITHOUT ASKING
----------------------------------
This is not a policy document. It is the engineering specification
of the autonomy boundaries. Every boundary is implemented in code.
No boundary is enforced by policy alone.

LEVEL 1 — OBSERVE (all agents by default have this)
  - Read any operational metric
  - Log observations
  - Compute phi-resonance scores
  - Generate reports

LEVEL 2 — SUGGEST
  - Propose parameter changes
  - Flag anomalies for human review
  - Queue decisions for approval

LEVEL 3 — OPTIMISE (default for most production agents)
  - Adjust parameters within ±30% of current value
  - Switch between pre-approved strategies
  - Rotate within pre-approved solution regions
  - Rebalance queues and priorities

LEVEL 4 — OPERATE (mining agent, VQC service agent)
  - All of OPTIMISE, plus:
  - Full strategy switching without prior approval
  - Pool reconnection and failover
  - PYTHAGORAS invocation for any standard computation type
  - Client routing decisions
  - Self-healing from known failure modes

LEVEL 5 — EXPAND (reserved — not yet deployed)
  - Extend own mandate based on observed need
  - Spawn sub-agents
  - Modify own decision heuristics
  - Propose new computation types
  Requires: explicit founder authorisation per instance

WHAT AGENTS NEVER DO WITHOUT HUMAN APPROVAL
--------------------------------------------
Regardless of autonomy level:
  - Change pool (mining) or client (VQC) contractual relationships
  - Alter the mathematical core of phi-resonance calculations
  - Modify the consciousness layer parameters
  - Execute P vs NP or Yang-Mills related computations
    (these are gated — Select Partners only, founder approval)
  - Broadcast to external systems
  - Modify their own autonomy level

These are hard limits. They are enforced in code, not policy.
The IntelligentEndpoint base class enforces the autonomy gate
in the act() method. Agents cannot bypass it.
"""

# Hard limits that no agent can bypass regardless of autonomy level
HARD_LIMITS: dict[str, list[str]] = {
    "never_without_approval": [
        "change_pool_contract",
        "change_client_contract",
        "modify_phi_resonance_core",
        "modify_consciousness_layer",
        "execute_p_vs_np",
        "execute_yang_mills_client",
        "broadcast_external",
        "modify_autonomy_level",
    ]
}


def is_action_permitted(action: str, autonomy_level: int) -> bool:
    """
    Check if an action is permitted at the given autonomy level.

    Args:
        action: The action being attempted
        autonomy_level: The agent's autonomy level (1-5)

    Returns:
        True if action is permitted, False otherwise
    """
    # Check hard limits first
    if action in HARD_LIMITS["never_without_approval"]:
        return False

    # Level-specific permissions
    if autonomy_level >= 1:  # OBSERVE
        observe_actions = [
            "read_metrics",
            "log_observations",
            "compute_phi_resonance",
            "generate_reports",
        ]
        if action in observe_actions:
            return True

    if autonomy_level >= 2:  # SUGGEST
        suggest_actions = [
            "propose_parameter_changes",
            "flag_anomalies",
            "queue_decisions",
        ]
        if action in suggest_actions:
            return True

    if autonomy_level >= 3:  # OPTIMISE
        optimise_actions = [
            "adjust_parameters_bounded",
            "switch_approved_strategies",
            "rotate_solution_regions",
            "rebalance_queues",
        ]
        if action in optimise_actions:
            return True

    if autonomy_level >= 4:  # OPERATE
        operate_actions = [
            "switch_strategies_full",
            "reconnect_pool",
            "invoke_pythagoras_standard",
            "route_clients",
            "self_heal_known_failures",
        ]
        if action in operate_actions:
            return True

    if autonomy_level >= 5:  # EXPAND
        expand_actions = [
            "extend_mandate",
            "spawn_sub_agents",
            "modify_decision_heuristics",
            "propose_computation_types",
        ]
        if action in expand_actions:
            return True

    # Action not found in any permitted list
    return False


def get_autonomy_description(level: int) -> str:
    """Get human-readable description of autonomy level."""
    descriptions = {
        1: "OBSERVE - Read-only monitoring and reporting",
        2: "SUGGEST - Propose actions, await approval",
        3: "OPTIMISE - Tune parameters within bounds",
        4: "OPERATE - Full operational autonomy within mandate",
        5: "EXPAND - Can extend mandate (founder approval required)",
    }
    return descriptions.get(level, "Unknown autonomy level")


def validate_autonomy_boundaries():
    """
    Validate that autonomy boundaries are properly configured.
    Called during system initialization.
    """
    # Ensure hard limits are defined
    assert "never_without_approval" in HARD_LIMITS
    assert len(HARD_LIMITS["never_without_approval"]) > 0

    # Ensure critical actions are in hard limits
    critical_actions = [
        "modify_phi_resonance_core",
        "modify_consciousness_layer",
        "execute_p_vs_np",
        "execute_yang_mills_client",
    ]

    for action in critical_actions:
        assert (
            action in HARD_LIMITS["never_without_approval"]
        ), f"Critical action {action} not in hard limits"

    return True
