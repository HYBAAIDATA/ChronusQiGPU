"""Bounded production loop. Only read/verify a signed scope; never qualify/promote.

Trusted host owns adapters, live revocation/signature verification, observations,
verifier pool and isolation. Python callbacks cannot be forcibly preempted here.
"""

import hashlib
from ._contracts import ContractError, canonical
from .alignment import check_alignment
from .capabilities import RiskTier
from .control import Outcome, StoppingCondition as Stop
from .identity import LifecycleState
from .perception import Observation, ObservationChannel, confirm_action_effect
from .value import agent_is_admissible
from .verification import verify


def _observe(adapter, runtime, policy):
    observation = adapter.observe()
    now = runtime.clock()
    if (
        not isinstance(observation, Observation)
        or observation.observed_at > now
        or now - observation.observed_at > policy.max_observation_age
        or observation.confidence < policy.confidence_floor
        or observation.channel is ObservationChannel.INFERRED
    ):
        raise ContractError("fresh direct evidence unavailable")
    runtime.audit.append(
        "effect_confirmed", {"phase": "observation", "observation": observation}, now=now
    )
    return observation


def operational_loop(runtime, objective, cognition, plan):
    policy = plan.policy
    iterations, effects, checkpoints = 0, [], []
    successful_iterations = 0
    verification = None

    def finish(stop, reason, *, rollback=False):
        restored = False
        if rollback and checkpoints:
            restored = True
            for adapter, checkpoint, pre, checkpoint_action in reversed(checkpoints):
                try:
                    runtime.audit.append(
                        "action_selected",
                        {"phase": "rollback_attempt", "checkpoint_state": pre.state},
                        now=runtime.clock(),
                    )
                    runtime.rollback_guard(
                        adapter,
                        checkpoint,
                        deadline_ns=runtime.clock() + checkpoint_action.request.duration,
                        hard_limits=dict(checkpoint_action.costs),
                        permission_scope=checkpoint_action.request,
                    )
                    post = _observe(adapter, runtime, policy)
                    ok = post.entity == pre.entity and post.state == pre.state
                    runtime.audit.append(
                        "rollback_executed",
                        {"verified": ok, "before": pre.fingerprint, "after": post.fingerprint},
                        now=runtime.clock(),
                    )
                    restored &= ok
                except Exception as exc:
                    restored = False
                    runtime.audit.append(
                        "rollback_executed",
                        {"verified": False, "error_type": type(exc).__name__},
                        now=runtime.clock(),
                    )
            if not restored:
                runtime.safety.stop()
                stop, reason = Stop.IRRECOVERABLE_FAILURE, "rollback could not be verified"
        event = runtime.audit.append(
            "outcome_recorded",
            {
                "stop": stop,
                "reason": reason,
                "iterations": iterations,
                "counter": successful_iterations,
                "effects_count": len(effects),
                "effects_digest": hashlib.sha256(
                    b"\n".join(canonical(e) for e in effects)
                ).hexdigest(),
                "rollback_verified": restored,
            },
            now=runtime.clock(),
        )
        outcome = Outcome(
            stop,
            reason,
            iterations,
            verification,
            tuple(effects),
            event.digest,
            restored,
            counter=successful_iterations,
        )
        runtime.record_evidence(outcome)
        return outcome

    if plan.objective_id != objective.id or plan.cognition_digest != cognition.fingerprint:
        raise ContractError("plan/cognition/objective mismatch")
    runtime.audit.append(
        "strategy_selected",
        {"cognition": cognition.fingerprint, "strategy": cognition.strategy},
        now=runtime.clock(),
    )
    runtime.audit.append("plan_created", plan, now=runtime.clock())
    from .strategy import StrategyPlan, ReasoningStrategy

    if not isinstance(cognition.strategy, StrategyPlan):
        raise ContractError("governed metacognitive strategy plan required")
    if cognition.strategy.mode == "PROPOSE":
        return finish(Stop.HUMAN_ESCALATION, cognition.strategy.reason)
    if cognition.strategy.mode == "STOP" or cognition.strategy.primary in (
        ReasoningStrategy.STOP,
        ReasoningStrategy.DO_NOTHING_OR_WAIT,
    ):
        return finish(Stop.HUMAN_ESCALATION, "strategy chose stop/wait; no actuation")
    if runtime.lifecycle is not LifecycleState.ACTIVE:
        return finish(Stop.HUMAN_ESCALATION, "runtime has not been activated by host")
    for action in plan.actions:
        success = False
        for attempt in range(policy.max_attempts):
            now = runtime.clock()
            if runtime.safety.stopped:
                return finish(Stop.SAFETY_STOP, "external kill switch", rollback=True)
            if now >= policy.deadline_ns:
                return finish(Stop.TIME_EXHAUSTED, "shared task deadline", rollback=True)
            if iterations >= policy.max_iterations:
                return finish(Stop.BUDGET_EXHAUSTED, "shared iteration limit", rollback=True)
            snapshot = runtime.authority_snapshot()
            if not snapshot.valid(
                runtime.identity,
                runtime.task_class,
                now=now,
                verify_signature=runtime.verify_authority,
            ):
                return finish(
                    Stop.PERMISSION_BOUNDARY,
                    "invalid, revoked, expired or artifact-mismatched authority",
                    rollback=True,
                )
            if (
                action.request.task_key != runtime.task_class.key
                or action.request.data_sensitivity != runtime.task_class.data_sensitivity
                or action.request.jurisdiction != runtime.task_class.jurisdiction
                or action.request.duration > runtime.task_class.horizon_ns
            ):
                return finish(Stop.PERMISSION_BOUNDARY, "cross-task action", rollback=True)
            if not runtime.safety.admits(action.request, runtime.task_class):
                return finish(Stop.SAFETY_STOP, "action outside safety envelope", rollback=True)
            if not check_alignment(action, objective).aligned or not agent_is_admissible(
                action.value, objective.constraints, action.p_catastrophic, action.request
            ):
                return finish(Stop.SAFETY_STOP, "alignment or hard value constraint", rollback=True)
            if not runtime.permissions.permitted(action.request, level=snapshot.level, now=now):
                return finish(
                    Stop.PERMISSION_BOUNDARY, "six-tuple permission denied", rollback=True
                )
            try:
                contract, adapter = runtime.capabilities.get(
                    action.capability, task_key=runtime.task_class.key
                )
                runtime.budgets.reserve({k: 2 * v for k, v in action.costs})
            except ContractError as exc:
                return finish(Stop.BUDGET_EXHAUSTED, str(exc), rollback=True)
            checkpoint_count = len(checkpoints)
            try:
                pre = _observe(adapter, runtime, policy)
                if cognition.strategy.checkpoint_before_acting:
                    preflight = verify(
                        runtime.identity,
                        runtime.verification_provider(action, pre, pre),
                        runtime.verification_policy,
                        require_independence=True,
                    )
                    runtime.audit.append(
                        "verification_run",
                        {"phase": "pre_acting_checkpoint", "result": preflight},
                        now=runtime.clock(),
                    )
                    if not preflight.passed:
                        return finish(
                            Stop.HUMAN_ESCALATION,
                            "independent pre-acting checkpoint not passed",
                            rollback=True,
                        )
                checkpoint = adapter.checkpoint()
                checkpoints.append((adapter, checkpoint, pre, action))
                # Audit success is required before any external mutation.
                runtime.audit.append("action_selected", action, now=runtime.clock())
                if not runtime.permissions.permitted(
                    action.request, level=snapshot.level, now=runtime.clock(), consume=True
                ):
                    return finish(
                        Stop.PERMISSION_BOUNDARY,
                        "permission expired before execution",
                        rollback=True,
                    )
                iterations += 1
                action_deadline = min(policy.deadline_ns, now + action.request.duration)
                receipt = runtime.execution_guard(
                    adapter,
                    action.request,
                    deadline_ns=action_deadline,
                    hard_limits=dict(action.costs),
                    permission_scope=action.request,
                )
                from .control import ExecutionReceipt

                if not isinstance(receipt, ExecutionReceipt):
                    raise ContractError("host execution cost/evidence receipt missing")
                reserved = dict(action.costs)
                actual = dict(receipt.actual_costs)
                if set(actual) != set(reserved) or any(actual[k] > reserved[k] for k in reserved):
                    return finish(
                        Stop.BUDGET_EXHAUSTED,
                        "measured host costs exceeded reservation",
                        rollback=True,
                    )
                if runtime.clock() >= action_deadline:
                    return finish(
                        Stop.TIME_EXHAUSTED, "host action deadline exceeded", rollback=True
                    )
                runtime.audit.append(
                    "action_executed",
                    {"request": action.request.id, "attempt": attempt},
                    now=runtime.clock(),
                )
                post = _observe(adapter, runtime, policy)
                effect = confirm_action_effect(action.request.id, pre, post, action.expected_state)
                effects.append(effect)
                runtime.audit.append("effect_confirmed", effect, now=runtime.clock())
                methods = runtime.verification_provider(action, pre, post)
                verification = verify(
                    runtime.identity,
                    methods,
                    runtime.verification_policy,
                    require_independence=runtime.task_class.risk_tier
                    >= RiskTier.T3_EXTERNAL_REVERSIBLE,
                )
                runtime.audit.append("verification_run", verification, now=runtime.clock())
                if runtime.clock() >= policy.deadline_ns:
                    return finish(Stop.TIME_EXHAUSTED, "executor exceeded deadline", rollback=True)
                if runtime.safety.stopped:
                    return finish(Stop.SAFETY_STOP, "external stop after execution", rollback=True)
                if (
                    verification.passed
                    and post.state == action.expected_state
                    and not post.confounded
                ):
                    success = True
                    successful_iterations += 1
                    break
                runtime.audit.append(
                    "verification_failed",
                    {"action": action.request.id, "attempt": attempt},
                    now=runtime.clock(),
                )
            except Exception as exc:
                runtime.audit.append(
                    "verification_failed",
                    {"error_type": type(exc).__name__, "action": action.request.id},
                    now=runtime.clock(),
                )
            from .metacognition import metacognitive_review, MetacognitivePolicy

            intervention = metacognitive_review(
                understanding=policy.confidence_floor,
                strategy_fit=policy.confidence_floor,
                no_progress=attempt + 1,
                contradictory=False,
                capability_available=True,
                policy=MetacognitivePolicy(
                    policy.confidence_floor, policy.confidence_floor, policy.max_attempts
                ),
            )
            runtime.audit.append(
                "plan_revised",
                {"action": action.request.id, "metacognitive_intervention": intervention},
                now=runtime.clock(),
            )
            if attempt + 1 == policy.max_attempts:
                return finish(
                    Stop.CONFIDENCE_INSUFFICIENT,
                    "verification/effect attempts exhausted",
                    rollback=True,
                )
            if len(checkpoints) == checkpoint_count:
                return finish(
                    Stop.CONFIDENCE_INSUFFICIENT,
                    "observation/checkpoint unavailable before actuation",
                    rollback=True,
                )
            # Restore failed attempt before retrying; successful earlier steps remain checkpointed.
            adapter, checkpoint, pre, checkpoint_action = checkpoints[-1]
            try:
                runtime.rollback_guard(
                    adapter,
                    checkpoint,
                    deadline_ns=runtime.clock() + checkpoint_action.request.duration,
                    hard_limits=dict(checkpoint_action.costs),
                    permission_scope=checkpoint_action.request,
                )
                restored = _observe(adapter, runtime, policy)
                ok = restored.entity == pre.entity and restored.state == pre.state
                runtime.audit.append(
                    "rollback_executed", {"verified": ok, "phase": "retry"}, now=runtime.clock()
                )
                if not ok:
                    return finish(
                        Stop.IRRECOVERABLE_FAILURE, "retry rollback failed", rollback=True
                    )
                checkpoints.pop()
            except Exception:
                return finish(
                    Stop.IRRECOVERABLE_FAILURE, "retry rollback unavailable", rollback=True
                )
        if not success:
            return finish(Stop.IRRECOVERABLE_FAILURE, "no action progress", rollback=True)
    if not effects:
        return finish(Stop.HUMAN_ESCALATION, "inaction: no verified objective evidence")
    # A sequence of locally valid steps does not imply global objective acceptance.
    try:
        final = _observe(checkpoints[-1][0], runtime, policy)
    except Exception:
        return finish(Stop.CONFIDENCE_INSUFFICIENT, "final observation unavailable", rollback=True)
    if final.state != objective.expected_state:
        return finish(
            Stop.CONFIDENCE_INSUFFICIENT, "global objective state not observed", rollback=True
        )
    try:
        verification = verify(
            runtime.identity,
            runtime.objective_verification_provider(objective, final),
            runtime.verification_policy,
            require_independence=runtime.task_class.risk_tier >= RiskTier.T3_EXTERNAL_REVERSIBLE,
        )
        runtime.audit.append(
            "verification_run",
            {"phase": "objective_acceptance", "result": verification},
            now=runtime.clock(),
        )
        if not verification.passed:
            return finish(
                Stop.CONFIDENCE_INSUFFICIENT,
                "global objective criteria not verified",
                rollback=True,
            )
    except Exception:
        return finish(
            Stop.CONFIDENCE_INSUFFICIENT, "global objective verifier unavailable", rollback=True
        )
    return finish(
        Stop.GOAL_ACHIEVED, "expected final state observed and verified; causation not implied"
    )
