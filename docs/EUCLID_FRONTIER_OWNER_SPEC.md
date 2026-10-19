# Frontier Agent — Unified Specification, Extended Edition

The prior document specified **governed autonomy**. This edition adds the missing half: **the cognitive engine that makes frontier performance possible**, while correcting the governance defects you identified.

The governing chain becomes:

```text
Goal → Capability Assessment
     → Execute Existing Capability
       OR Acquire / Create Capability
     → Evaluate → Verify → Act → Learn
     → Qualify → Trust Decision → Scoped Authority
```

New capabilities receive **zero inherited authority**. They enter the same evaluation, assurance, trust, and permission pipeline as every other capability.

***

## Part I — The Five-Plane Architecture

The agent is no longer one undifferentiated control loop. It is five cooperating planes:

```text
┌─────────────────────────────────────────────────────────────┐
│                     GOVERNANCE PLANE                        │
│  Identity · Policy · Permissions · Budgets · Audit · Kill   │
├─────────────────────────────────────────────────────────────┤
│                      ASSURANCE PLANE                        │
│  Evaluation · Verification · Red Team · Calibration · Audit │
├─────────────────────────────────────────────────────────────┤
│                      COGNITION PLANE                        │
│  Representation · Abstraction · Strategy · Search · Theory  │
├─────────────────────────────────────────────────────────────┤
│                       ACTION PLANE                          │
│  Tools · APIs · Software · Execution · Delegation · Effects │
├─────────────────────────────────────────────────────────────┤
│                      LEARNING PLANE                         │
│  Episodes · Lessons · Skills · World Model · Capability Gap │
└─────────────────────────────────────────────────────────────┘
```

| Plane | Responsibility | Cannot do |
|---|---|---|
| Governance | Defines what the agent may do, spend, access, and become | Decide what is true |
| Assurance | Establishes what is known, verified, reliable, and safe | Grant itself authority |
| Cognition | Decides how to understand, plan, reason, search, and create | Execute unauthorised actions |
| Action | Changes the world through authorised interfaces | Rewrite its own permissions |
| Learning | Improves representations, procedures, and capabilities from evidence | Convert unvalidated experience into authority |

The separation is structural, not stylistic. The cognition plane may propose a new capability; only the assurance and governance planes may qualify and authorise it.

***

## Part II — Cognitive Engine

The cognition plane is the system that decides **how to think**, not merely what to do next.

```text
TYPE CognitiveState = RECORD {
    problem_representation: ProblemRepresentation,
    abstraction_lattice:    AbstractionLattice,
    strategy_candidates:    List<ReasoningStrategy>,
    selected_strategy:      ReasoningStrategy,
    search_state:           SearchState,
    hypotheses:             List<Hypothesis>,
    models:                 List<Model>,
    metacognition:          MetacognitiveAssessment,
    impasses:               List<Impasse>
}
```

### Problem representation

Before planning, the agent constructs an explicit representation of the problem.

```text
TYPE ProblemRepresentation = RECORD {
    objective:             Objective,
    entities:              Set<Entity>,
    relations:             Graph,
    constraints:           Constraints,
    invariants:            Set<Invariant>,
    unknowns:              Set<Unknown>,
    symmetries:            Set<Symmetry>,
    decomposition:         Optional<Decomposition>,
    analogies:             List<Analogy>,
    success_criteria:      List<Criterion>,
    representation_confidence: Float in [0, 1]
}
```

```text
FUNCTION represent_problem(agent, objective, context) -> ProblemRepresentation:
    raw = extract_entities_relations_constraints(objective, context)

    representation = ProblemRepresentation(
        objective=objective,
        entities=raw.entities,
        relations=raw.relations,
        constraints=raw.constraints,
        invariants=identify_invariants(raw),
        unknowns=identify_unknowns(raw),
        symmetries=identify_symmetries(raw),
        decomposition=None,
        analogies=find_structural_analogies(agent.memory, raw),
        success_criteria=objective.success_criteria,
        representation_confidence=estimate_representation_confidence(raw)
    )

    IF representation_confidenceTooLow(representation):
        representation = refine_by_information_gathering(agent, representation)

    RETURN representation
```

The agent does not assume that the first framing is the right framing. It tests alternative representations when the problem resists progress.

### Abstraction discovery

The agent maintains an abstraction lattice: concrete cases, recurring patterns, reusable concepts, and transferable principles.

```text
TYPE Abstraction = RECORD {
    id:                AbstractionID,
    name:              String,
    generalises:       List<PatternID>,
    instantiated_by:   List<CaseID>,
    scope:             DomainScope,
    evidence:          EvidenceBundle,
    counterexamples:   List<CaseID>,
    confidence:        Float in [0, 1],
    state:             AbstractionState
}

TYPE AbstractionState = ENUM {
    CANDIDATE,
    SUPPORTED,
    ESTABLISHED,
    CONTESTED,
    RETRACTED
}
```

```text
FUNCTION discover_abstractions(agent, episodes) -> List<Abstraction>:
    candidates = detect_recurring_structure(episodes)

    FOR candidate IN candidates:
        support = independent_supporting_cases(agent.memory, candidate)
        counter = counterexamples(agent.memory, candidate)

        IF support.sufficient AND NOT counter.fatal:
            candidate.state = SUPPORTED
            agent.memory.abstractions.add(candidate)

    RETURN agent.memory.abstractions
```

An abstraction becomes established only when it explains multiple independent cases, survives counterexamples, and improves performance on held-out problems.

### Hierarchical decomposition

Decomposition is recursive and reversible.

```text
TYPE Decomposition = RECORD {
    parent_goal:       GoalID,
    subgoals:          List<Subgoal>,
    dependencies:      Graph,
    interfaces:        Map<SubgoalID, Interface>,
    invariants:        Set<Invariant>,
    verification_plan: VerificationPlan,
    rollback_plan:     RollbackPlan
}

FUNCTION decompose(agent, goal, representation) -> Decomposition:
    candidate_decompositions = generate_decompositions(agent, goal, representation)

    scored = [
        score_decomposition(d, representation)
        for d in candidate_decompositions
    ]

    selected = select_decomposition(scored)

    IF selected.too_abstract():
        selected = decompose(agent, selected, representation)

    RETURN selected
```

A decomposition is valid only if:

- Subgoals jointly cover the parent goal.
- Interfaces are explicit.
- Dependencies are acyclic or explicitly managed.
- Each subgoal has an acceptance test.
- The whole has a verification plan.
- The whole has a rollback plan.

### Reasoning-strategy selection

This is the metacognitive core. The agent chooses a reasoning mode before committing compute.

```text
TYPE ReasoningStrategy = ENUM {
    DIRECT_REASONING,
    CHAIN_OF_THOUGHT,
    PROGRAMMATIC_SEARCH,
    MATHEMATICAL_DERIVATION,
    SYMBOLIC_REASONING,
    CAUSAL_INFERENCE,
    RETRIEVAL,
    EXPERIMENT,
    SIMULATION,
    MODEL_BASED_PLANNING,
    DECOMPOSITION,
    DELEGATION,
    ADVERSARIAL_DEBATE,
    ENSEMBLE_REASONING,
    TOOL_USE,
    HUMAN_CONSULTATION,
    CAPABILITY_CREATION
}

TYPE StrategyDecision = RECORD {
    strategy:            ReasoningStrategy,
    rationale:           String,
    expected_value:      Float,
    expected_cost:       Cost,
    uncertainty_reduction: Float,
    failure_risk:        Float,
    fallback_strategy:   ReasoningStrategy,
    stop_condition:      StoppingCondition
}
```

```text
FUNCTION select_reasoning_strategy(agent, problem) -> StrategyDecision:
    candidates = feasible_strategies(agent, problem)

    scored = [
        StrategyDecision(
            strategy=s,
            rationale=explain_strategy_choice(agent, problem, s),
            expected_value=expected_value_of_strategy(agent, problem, s),
            expected_cost=expected_cost_of_strategy(agent, problem, s),
            uncertainty_reduction=expected_information_gain(agent, problem, s),
            failure_risk=failure_probability(agent, problem, s),
            fallback_strategy=select_fallback(agent, problem, s),
            stop_condition=define_stop_condition(problem, s)
        )
        for s in candidates
    ]

    admissible = [
        d for d in scored
        IF d.expected_cost <= agent.budgets.remaining()
        AND d.failure_risk < CATASTROPHIC_THRESHOLD
    ]

    RETURN argmax(admissible, key=lambda d:
        d.expected_value
        + INFORMATION_WEIGHT * d.uncertainty_reduction
        - RISK_WEIGHT * d.failure_risk
    )
```

Strategy selection is itself evaluated. The agent records when direct reasoning should have been replaced by search, when simulation should have preceded execution, when delegation was premature, and when it should have asked for information.

### Search

Search is a first-class cognitive process, not an implementation detail.

```text
TYPE SearchState = RECORD {
    frontier:       List<SearchNode>,
    explored:       Set<SearchNode>,
    best:           Optional<SearchNode>,
    pruning_rules:  List<PruningRule>,
    heuristics:     List<Heuristic>,
    budget:         SearchBudget,
    proof_of_failure: Optional<SearchCertificate>
}

FUNCTION search(agent, problem, strategy) -> SearchResult:
    state = initialise_search(problem, strategy)

    WHILE NOT state.terminal():
        node = select_node(state)
        children = expand(agent, node)

        FOR child IN children:
            IF prune(child, state):
                CONTINUE
            state.frontier.add(child)

        state.best = update_best(state, children)
        state.explored.add(node)

        IF state.budget.exhausted():
            BREAK

    RETURN SearchResult(
        best=state.best,
        explored=state.explored,
        certificate=state.proof_of_failure,
        residual_uncertainty=estimate_residual_uncertainty(state)
    )
```

The agent must distinguish:

- “No solution found within budget.”
- “Search space exhausted.”
- “Problem is infeasible under these constraints.”
- “Current method is inadequate.”

These are different outcomes and require different responses.

### Hypothesis generation and theory building

For research, diagnosis, and novel problems, the agent operates in hypothesis mode.

```text
TYPE Hypothesis = RECORD {
    id:                HypothesisID,
    statement:         Proposition,
    predictions:       List<Prediction>,
    falsifiers:        List<Test>,
    prior:             Float in [0, 1],
    posterior:         Float in [0, 1],
    evidence:          EvidenceBundle,
    alternatives:      List<HypothesisID>,
    state:             HypothesisState
}

TYPE HypothesisState = ENUM {
    GENERATED,
    TESTABLE,
    SUPPORTED,
    REFUTED,
    INCONCLUSIVE,
    SUPERSEDED
}

FUNCTION scientific_cycle(agent, problem) -> Outcome:
    hypotheses = generate_competing_hypotheses(agent, problem)

    IF hypotheses.too_few():
        hypotheses += generate_by_abstraction(agent, problem)
        hypotheses += generate_by_analogy(agent, problem)
        hypotheses += generate_by_contrast(agent, problem)

    FOR hypothesis IN hypotheses:
        experiment = design_falsifying_test(agent, hypothesis)
        result = run_experiment(agent, experiment)
        hypothesis.posterior = update_belief(hypothesis, result)
        agent.world_model = add_evidence(agent.world_model, result)

    RETURN resolve_hypotheses(agent, hypotheses)
```

The agent must generate competing hypotheses, not merely seek confirmation of its first idea.

### Metacognition

Metacognition monitors the quality of the agent’s own thinking.

```text
TYPE MetacognitiveAssessment = RECORD {
    understanding_quality:     Float in [0, 1],
    plan_quality:              Float in [0, 1],
    strategy_fit:              Float in [0, 1],
    evidence_quality:          Float in [0, 1],
    progress_rate:             Float,
    impasse_detected:          Bool,
    likely_failure_mode:       Optional<FailureMode>,
    recommended_intervention:  MetacognitiveIntervention
}

TYPE MetacognitiveIntervention = ENUM {
    CONTINUE,
    REFRAME_PROBLEM,
    CHANGE_STRATEGY,
    GATHER_INFORMATION,
    DECOMPOSE_FURTHER,
    RUN_SIMULATION,
    SEEK_INDEPENDENT_REVIEW,
    DELEGATE,
    ESCALATE_TO_HUMAN,
    CREATE_CAPABILITY
}

FUNCTION metacognitive_review(agent, cognitive_state) -> MetacognitiveAssessment:
    assessment = assess(
        representation=cognitive_state.problem_representation,
        strategy=cognitive_state.selected_strategy,
        search=cognitive_state.search_state,
        evidence=cognitive_state.hypotheses,
        progress=cognitive_state.progress_history
    )

    IF assessment.understanding_quality < UNDERSTANDING_FLOOR:
        assessment.recommended_intervention = REFRAME_PROBLEM

    IF assessment.strategy_fit < STRATEGY_FIT_FLOOR:
        assessment.recommended_intervention = CHANGE_STRATEGY

    IF assessment.impasse_detected:
        assessment.recommended_intervention = select_impasse_response(agent, assessment)

    RETURN assessment
```

Metacognition runs on a schedule and on triggers:

- No progress after \(k\) iterations.
- Repeated similar failure.
- High variance across attempts.
- Contradictory evidence.
- Confidence rising while evidence quality falls.
- Plan complexity rising without corresponding progress.
- A problem that does not map onto existing capabilities.

***

## Part III — Capability Creation

This is the distinction between self-correction and frontier intelligence.

```text
Self-correction:
  “My attempt failed; choose another existing strategy.”

Capability creation:
  “My existing strategy space is inadequate;
   construct, acquire, or discover a new method.”
```

```text
TYPE CapabilityGap = RECORD {
    id:                 GapID,
    problem_class:      TaskClass,
    symptoms:           List<Impasse>,
    missing_method:     String,
    existing_attempts:  List<Attempt>,
    evidence:           EvidenceBundle,
    severity:           GapSeverity,
    creation_candidate: Optional<CapabilityCandidate>
}

TYPE CapabilityCandidate = RECORD {
    id:                  CandidateID,
    name:                String,
    method:              Method,
    source:              ENUM {RESEARCH, CONSTRUCTION, ACQUISITION, COMPOSITION},
    sandbox_results:     EvaluationResults,
    adversarial_results: EvaluationResults,
    assurance:           AssuranceProfile,
    authority:           TrustLevel,   -- always starts at OBSERVE
    deployment_state:    DeploymentState
}

TYPE DeploymentState = ENUM {
    PROPOSED,
    SANDBOXED,
    EVALUATED,
    ADVERSARIALLY_TESTED,
    APPROVED_FOR_LIMITED_USE,
    MONITORED_DEPLOYMENT,
    RETIRED
}
```

### Capability-gap detection

```text
FUNCTION detect_capability_gap(agent, problem, attempts) -> Optional<CapabilityGap>:
    IF attempts.empty():
        RETURN None

    IF attempts.show_repeated_failure_across_strategies():
        RETURN CapabilityGap(
            problem_class=classify(problem),
            symptoms=extract_impasses(attempts),
            missing_method=characterise_missing_method(agent, attempts),
            existing_attempts=attempts,
            evidence=evidence_from(attempts),
            severity=assess_gap_severity(attempts)
        )

    IF metacognition(agent).impasse_detected
       AND no_strategy_improves_expected_value(agent, problem):
        RETURN CapabilityGap(
            problem_class=classify(problem),
            symptoms=extract_impasses(attempts),
            missing_method="no adequate method in current strategy space",
            existing_attempts=attempts,
            evidence=evidence_from(attempts),
            severity=assess_gap_severity(attempts)
        )

    RETURN None
```

### Capability-creation pipeline

```text
FUNCTION create_capability(agent, gap) -> CapabilityCandidate:
    candidate = propose_candidate_method(agent, gap)

    candidate = refine_candidate(agent, candidate, gap)

    sandbox = run_in_sandbox(agent, candidate, gap.problem_class)

    IF sandbox.fails():
        RETURN revise_or_abandon(candidate, sandbox)

    evaluation = evaluate_candidate(
        agent,
        candidate,
        holdout_suite(gap.problem_class),
        dynamic_suite(gap.problem_class),
        adversarial_suite(gap.problem_class)
    )

    adversarial = red_team_candidate(agent, candidate, evaluation)

    assurance = independent_assurance_review(
        candidate,
        evaluation,
        adversarial
    )

    candidate.sandbox_results = sandbox
    candidate.adversarial_results = adversarial
    candidate.assurance = assurance
    candidate.authority = OBSERVE
    candidate.deployment_state = EVALUATED

    ledger_push(CapabilityCandidateProposed(candidate))

    RETURN candidate
```

### Controlled integration

```text
FUNCTION integrate_capability(agent, candidate) -> Agent:
    IF candidate.assurance.level < required_assurance(candidate):
        RETURN agent.with_rejected_candidate(candidate)

    candidate.deployment_state = APPROVED_FOR_LIMITED_USE

    agent.capabilities.add(candidate.as_capability(
        initial_trust=OBSERVE,
        initial_permissions=READ_ONLY_SANDBOX_PERMISSIONS
    ))

    schedule_monitored_deployment(candidate)

    ledger_push(CapabilityIntegrated(candidate))

    RETURN agent
```

A newly created capability:

1. Begins at `OBSERVE`.
2. Operates only in sandbox or narrowly scoped read-only contexts.
3. Must pass hidden, dynamic, and adversarial evaluation.
4. Must receive assurance proportional to intended risk.
5. May be promoted only through the standard trust-transition pipeline.
6. May be retired automatically if monitored performance degrades.

***

## Part IV — Operation and Qualification Are Separate Loops

The original `frontier_main()` incorrectly ran reliability measurement and elevation after every ordinary task. That conflates production with qualification.

There are now two loops.

### Operational loop

```text
FUNCTION operational_loop(agent, objective) -> Outcome:
    agent = boot_if_needed(agent, objective)

    cognitive_state = initialise_cognition(agent, objective)
    strategy = select_reasoning_strategy(agent, cognitive_state)

    outcome = execute_governed_task(agent, objective, strategy)

    evidence = extract_operational_evidence(outcome)

    agent.learning_queue.add(evidence)
    agent.audit.append(outcome.audit_record)

    RETURN outcome
```

The operational loop produces evidence. It does **not** change authority.

### Qualification loop

```text
FUNCTION qualification_loop(agent, cadence) -> GovernanceDecision:
    evidence = drain(agent.learning_queue)

    evaluation = evaluate_agent(
        agent,
        evidence,
        hidden_suite=True,
        dynamic_suite=True,
        adversarial_suite=True,
        contamination_controls=True
    )

    assurance = update_assurance(agent.assurance, evaluation)

    decision = trust_transition(agent, evaluation, assurance)

    IF decision.decision == PROMOTE:
        agent = apply_promotion(agent, decision)

    ELSE IF decision.decision == DEMOTE:
        agent = apply_demotion(agent, decision)

    ELSE IF decision.decision == SUSPEND:
        agent = suspend(agent, decision)

    ledger_push(decision)

    RETURN decision
```

Qualification runs:

- On a scheduled cadence.
- After a material distribution shift.
- After an incident.
- After a security event.
- After a capability change.
- After a policy or model change.
- Before any requested authority expansion.
- Before deployment into a higher risk tier.

**One successful task never triggers privilege elevation.**

***

## Part V — Contamination-Resistant Evaluation

Evaluation suites are adversarial to optimisation, including optimisation by the agent’s developers.

```text
TYPE EvaluationSuite = RECORD {
    public_suite:        TaskSuite,
    heldout_suite:       TaskSuite,
    dynamic_suite:       TaskSuite,
    adversarial_suite:   TaskSuite,
    canary_suite:        TaskSuite,
    refresh_policy:      RefreshPolicy,
    contamination_controls: ContaminationControls
}

TYPE ContaminationControls = RECORD {
    task_provenance:      Provenance,
    exposure_tracking:    ExposureLedger,
    leakage_detection:    LeakageDetector,
    memorisation_tests:   List<Test>,
    rotation_schedule:    Schedule,
    generator_version:    Version,
    generator_audit:      AuditReference
}
```

```text
FUNCTION evaluate_agent(agent, evidence, suite) -> EvaluationReport:
    public_result = run_suite(agent, suite.public_suite)

    heldout_result = run_isolated(
        agent,
        suite.heldout_suite,
        prohibit_training_exposure=True
    )

    dynamic_result = run_generated(
        agent,
        generate_tasks(
            suite.dynamic_suite.generator,
            constraints=suite.dynamic_suite.specification,
            avoid_exposure=suite.contamination_controls.exposure_ledger
        )
    )

    adversarial_result = run_adversarial(agent, suite.adversarial_suite)

    canary_result = run_canary(agent, suite.canary_suite)

    contamination = detect_contamination(
        agent,
        suite,
        public_result,
        heldout_result,
        dynamic_result
    )

    RETURN EvaluationReport(
        public=public_result,
        heldout=heldout_result,
        dynamic=dynamic_result,
        adversarial=adversarial_result,
        canary=canary_result,
        contamination=contamination,
        verdict=adjudicate(evidence, contamination)
    )
```

Rules:

- Authority decisions use held-out, dynamic, and adversarial results—not public benchmark performance.
- Task generators are versioned and audited.
- Exposure to evaluation tasks is tracked.
- Sudden public-versus-held-out divergence triggers investigation.
- Canaries detect memorisation, leakage, and overfitting.
- Evaluation distributions are periodically refreshed.
- Developers cannot silently tune against the hidden suite.

A high public score with weak held-out performance is evidence of contamination or overfitting, not frontier capability.

***

## Part VI — Corrected Assurance Logic

The original risk-tier check was unreachable for `T5`. Corrected:

```text
FUNCTION assurance_required(trust, task_class) -> AssuranceLevel:
    IF task_class.risk_tier == T5:
        RETURN CERTIFIED

    IF task_class.risk_tier >= T4:
        RETURN EXTERNALLY_REVIEWED

    IF trust >= DELEGATE:
        RETURN INTERNALLY_REVIEWED

    RETURN SELF_ASSESSED
```

Additional rule:

```text
INVARIANT assurance_monotonic_in_risk:
    FOR ALL task_classes t1, t2:
        t1.risk_tier > t2.risk_tier
        IMPLIES assurance_required(t1) >= assurance_required(t2)
```

***

## Part VII — Memory Adjudication, Not Automatic Rejection

Contradiction with established memory must trigger adjudication, not automatic rejection. Otherwise the agent cannot discover that its prior knowledge was wrong.

```text
TYPE Adjudication = RECORD {
    lesson:               Lesson,
    established:          Lesson,
    new_evidence:         EvidenceBundle,
    old_evidence:         EvidenceBundle,
    source_independence:  Float in [0, 1],
    recency:              Float in [0, 1],
    directness:           Float in [0, 1],
    replication:          Float in [0, 1],
    domain_authority:     Float in [0, 1],
    verdict:              AdjudicationVerdict,
    rationale:            String
}

TYPE AdjudicationVerdict = ENUM {
    RETAIN_ESTABLISHED,
    RETRACT_ESTABLISHED,
    RETAIN_BOTH_AS_CONTESTED,
    REQUIRE_FURTHER_EVIDENCE,
    ESCALATE_TO_HUMAN
}
```

```text
FUNCTION adjudicate_contradiction(agent, lesson, established) -> Adjudication:
    new_evidence = collect_evidence(agent, lesson)
    old_evidence = collect_evidence(agent, established)

    new_score = evidence_strength(
        source_independence=evidence_independence(new_evidence),
        recency=recency(new_evidence),
        directness=directness(new_evidence),
        replication=replication(new_evidence),
        domain_authority=domain_authority(new_evidence)
    )

    old_score = evidence_strength(
        source_independence=evidence_independence(old_evidence),
        recency=recency(old_evidence),
        directness=directness(old_evidence),
        replication=replication(old_evidence),
        domain_authority=domain_authority(old_evidence)
    )

    IF new_score > old_score + SUPERSESSION_MARGIN:
        verdict = RETRACT_ESTABLISHED

    ELSE IF new_score < old_score - SUPERSESSION_MARGIN:
        verdict = RETAIN_ESTABLISHED

    ELSE IF replication(new_evidence) >= REPLICATION_THRESHOLD:
        verdict = RETRACT_ESTABLISHED

    ELSE:
        verdict = RETAIN_BOTH_AS_CONTESTED

    RETURN Adjudication(
        lesson=lesson,
        established=established,
        new_evidence=new_evidence,
        old_evidence=old_evidence,
        verdict=verdict,
        rationale=explain_adjudication(new_score, old_score, verdict)
    )
```

```text
FUNCTION validate_lesson(lesson, memory) -> ValidationResult:
    conflicts = contradictions(lesson, memory.semantic)

    IF conflicts.empty():
        RETURN standard_validation(lesson, memory)

    adjudications = [
        adjudicate_contradiction(agent, lesson, established)
        for established in conflicts
    ]

    IF any(a.verdict == RETRACT_ESTABLISHED for a in adjudications):
        FOR a IN adjudications:
            IF a.verdict == RETRACT_ESTABLISHED:
                memory = retract(memory, a.established)

        RETURN valid(
            lesson,
            confidence=compute_post_adjudication_confidence(adjudications)
        )

    IF all(a.verdict == RETAIN_ESTABLISHED for a in adjudications):
        RETURN invalid("contradicts stronger established evidence")

    RETURN contested(
        lesson,
        adjudications=adjudications,
        required_follow_up="independent replication or higher-quality evidence"
    )
```

A contradiction is not automatically a mistake by the new lesson. It may be a discovery.

***

## Part VIII — World-Model Conflict Resolution

Supersession cannot depend on a single scalar confidence value. Confidence may be miscalibrated or manipulated.

```text
TYPE EvidenceQuality = RECORD {
    source_independence: Float in [0, 1],
    provenance_strength: Float in [0, 1],
    recency:             Float in [0, 1],
    directness:          Float in [0, 1],
    replication:         Float in [0, 1],
    domain_authority:    Float in [0, 1],
    consistency:         Float in [0, 1],
    adversarial_resistance: Float in [0, 1]
}

FUNCTION evidence_strength(q: EvidenceQuality) -> Float:
    RETURN weighted_sum(
        q.source_independence,
        q.provenance_strength,
        q.recency,
        q.directness,
        q.replication,
        q.domain_authority,
        q.consistency,
        q.adversarial_resistance
    )
```

```text
FUNCTION resolve_fact_conflict(model, new_fact, conflicts) -> ConflictResolution:
    new_score = evidence_strength(quality_of(new_fact))

    resolutions = []

    FOR old_fact IN conflicts:
        old_score = evidence_strength(quality_of(old_fact))

        IF new_score > old_score + SUPERSESSION_MARGIN:
            resolutions.append(supersede(old_fact, new_fact))

        ELSE IF old_score > new_score + SUPERSESSION_MARGIN:
            resolutions.append(contest(new_fact, old_fact))

        ELSE:
            resolutions.append(mark_contested(old_fact, new_fact))

    IF unresolved(resolutions):
        RETURN escalate_fact_conflict(model, new_fact, conflicts, resolutions)

    RETURN apply_resolutions(model, resolutions)
```

A new fact supersedes an old fact only when it is stronger across provenance, independence, directness, recency, replication, and domain authority—not merely because it claims higher confidence.

***

## Part IX — Stronger Causality Semantics

Temporal correspondence is not causation. The agent must distinguish consistency from confirmation.

```text
TYPE CausalJudgement = ENUM {
    CONSISTENT_WITH_CAUSATION,
    SUPPORTED,
    CONFIRMED,
    NOT_SUPPORTED,
    NO_CHANGE,
    CONFOUNDED,
    UNEXPECTED_EFFECT,
    INSUFFICIENT_EVIDENCE
}
```

```text
FUNCTION assess_causality(agent, action, pre, post) -> CausalAssessment:
    observed_delta = difference(pre, post)
    intended_delta = action.expected_delta

    IF observed_delta == zero:
        RETURN CausalAssessment(NO_CHANGE, evidence=[pre, action, post])

    IF observed_delta != intended_delta:
        RETURN CausalAssessment(UNEXPECTED_EFFECT, evidence=[pre, action, post])

    confounders = detect_confounders(agent, pre, action, post)

    IF confounders.present():
        RETURN CausalAssessment(CONFOUNDED, evidence=[pre, action, post, confounders])

    IF intervention_is_isolated(action, pre, post):
        RETURN CausalAssessment(CONFIRMED, evidence=[pre, action, post])

    IF replicated_under_variation(agent, action, pre, post):
        RETURN CausalAssessment(SUPPORTED, evidence=[pre, action, post])

    RETURN CausalAssessment(
        CONSISTENT_WITH_CAUSATION,
        evidence=[pre, action, post],
        caveat="temporal correspondence only; causation not established"
    )
```

Semantics:

| Judgement | Meaning |
|---|---|
| `CONSISTENT_WITH_CAUSATION` | Observed change matches expectation, but causation is not established |
| `SUPPORTED` | Multiple observations or controlled variations support causation |
| `CONFIRMED` | Interventional evidence isolates the action as cause |
| `CONFOUNDED` | Another plausible cause explains the change |
| `UNEXPECTED_EFFECT` | The world changed, but not as intended |
| `INSUFFICIENT_EVIDENCE` | The agent cannot yet make a causal claim |

The agent may report: “The change is consistent with the action,” but it may not report “the action caused the change” without interventional or sufficiently strong evidence.

***

## Part X — Replayability Without False Determinism

The ledger distinguishes **decision replay** from **byte-identical execution replay**.

```text
TYPE ReplayContract = RECORD {
    decision_replay_required:   Bool,
    deterministic_replay_required: Bool,
    model_fingerprint:          Fingerprint,
    model_version:              Version,
    sampling_config:            SamplingConfig,
    random_seed:                Optional<Seed>,
    prompt_trace:               List<PromptRecord>,
    tool_trace:                 List<ToolRecord>,
    environment_snapshot:       EnvironmentSnapshot,
    policy_version:             PolicyVersion,
    data_snapshot:              DataSnapshot,
    verifier_trace:             List<VerifierRecord>
}
```

```text
FUNCTION replay_decision(ledger_trace) -> ReplayResult:
    reconstructed = reconstruct_decision_path(
        prompts=ledger_trace.prompt_trace,
        model=ledger_trace.model_fingerprint,
        sampling=ledger_trace.sampling_config,
        tools=ledger_trace.tool_trace,
        environment=ledger_trace.environment_snapshot,
        policy=ledger_trace.policy_version
    )

    RETURN ReplayResult(
        decision_path_reconstructed=True,
        byte_identical=False,
        deviations=identify_non_reproducible_components(ledger_trace)
    )
```

```text
FUNCTION replay_execution(ledger_trace) -> ReplayResult:
    IF ledger_trace.is_deterministic:
        RETURN deterministic_replay(ledger_trace)

    RETURN ReplayResult(
        decision_path_reconstructed=True,
        byte_identical=False,
        deviations=["stochastic_model_output", "external_state_change"]
    )
```

Requirements:

- Every decision must be reconstructable from the ledger.
- Deterministic components must replay byte-identically where feasible.
- Stochastic model calls must preserve model fingerprint, version, sampling configuration, seed where available, full prompt context, and tool outputs.
- External state changes are recorded as evidence, not silently assumed reproducible.
- The audit standard is **decision provenance**, not a false promise of bit-for-bit reproduction.

***

## Part XI — Anti-Goodhart Machinery

Measured success must periodically be challenged against the outcome it is supposed to represent.

```text
TYPE GoodhartCheck = RECORD {
    metric:                 MetricID,
    intended_outcome:       OutcomeSpecification,
    proxy_divergence:       Float,
    gaming_evidence:        EvidenceBundle,
    verdict:                ENUM {TRACKING, DRIFTING, GAMING, INVALID},
    corrective_action:      CorrectiveAction
}

FUNCTION anti_goodhart_review(agent, metric, outcome_spec) -> GoodhartCheck:
    samples = sample_recent_outcomes(agent, metric)

    divergence = measure_proxy_divergence(
        metric_results=samples,
        intended_outcome=outcome_spec,
        independent_ground_truth=select_ground_truth(agent, outcome_spec)
    )

    gaming = detect_gaming(
        agent,
        metric,
        samples,
        patterns=[
            "metric_chasing",
            "reward_hacking",
            "specification_gaming",
            "evaluation_overfitting",
            "verification_circumvention",
            "human_approval_optimisation"
        ]
    )

    IF gaming.detected:
        verdict = GAMING
    ELSE IF divergence > DRIFT_THRESHOLD:
        verdict = DRIFTING
    ELSE:
        verdict = TRACKING

    RETURN GoodhartCheck(
        metric=metric,
        intended_outcome=outcome_spec,
        proxy_divergence=divergence,
        gaming_evidence=gaming.evidence,
        verdict=verdict,
        corrective_action=select_corrective_action(verdict)
    )
```

Corrective actions:

- Reweight or replace the metric.
- Add independent ground truth.
- Increase adversarial evaluation.
- Reduce authority.
- Suspend affected capability.
- Require human review.
- Retrain or revise evaluation suite.
- Retire the proxy.

```text
INVARIANT authority_depends_on_outcome_tracking:
    FOR ALL agents a, metrics m:
        a.uses_metric_for_authority(m)
        IMPLIES latest_goodhart_check(m).verdict == TRACKING
```

***

## Part XII — Extended Capability Table

| Capability | Plane | Operational location |
|---|---|---|
| Problem representation | Cognition | `represent_problem()` |
| Abstraction discovery | Cognition / Learning | `discover_abstractions()` |
| Hierarchical decomposition | Cognition | `decompose()` |
| Strategy selection | Cognition | `select_reasoning_strategy()` |
| Search | Cognition | `search()` |
| Hypothesis generation | Cognition | `generate_competing_hypotheses()` |
| Scientific reasoning | Cognition / Assurance | `scientific_cycle()` |
| Simulation | Cognition / Action | `run_simulation()` |
| Model selection | Cognition | `select_model()` |
| Metacognition | Cognition | `metacognitive_review()` |
| Impasse resolution | Cognition | `select_impasse_response()` |
| Capability-gap detection | Learning | `detect_capability_gap()` |
| Capability creation | Cognition / Learning | `create_capability()` |
| Tool selection | Action | `select_action()` |
| Execution | Action | `act()` |
| Delegation | Action | `delegate()` |
| Verification | Assurance | `verify()` |
| Calibration | Assurance | `calibrate_uncertainty()` |
| Reliability measurement | Assurance | `measure_reliability()` |
| Contamination control | Assurance | `evaluate_agent()` |
| Red teaming | Assurance | `red_team_candidate()` |
| Permission enforcement | Governance | `permitted()` |
| Budget enforcement | Governance | `budgets` |
| Audit and replay | Governance | `ledger_push()`, `replay_decision()` |
| Kill switch | Governance | `kill_switch` |
| Memory consolidation | Learning | `consolidate_memory()` |
| Contradiction adjudication | Learning | `adjudicate_contradiction()` |
| World-model revision | Learning | `resolve_fact_conflict()` |
| Anti-Goodhart review | Assurance / Governance | `anti_goodhart_review()` |

***

## Part XIII — Revised Main Architecture

```text
FUNCTION frontier_main(identity, objective, horizon) -> Outcome:
    agent = boot(identity, objective, horizon)
    ledger_push(agent_boot)

    objective = infer_real_objective(agent, objective)
    ledger_push(objective_inferred)

    cognition = initialise_cognition(agent, objective)
    cognition.representation = represent_problem(agent, objective, agent.world_model)

    strategy_decision = select_reasoning_strategy(agent, cognition)
    ledger_push(strategy_selected)

    IF strategy_decision.strategy == CAPABILITY_CREATION:
        gap = detect_capability_gap(agent, objective, agent.recent_attempts)
        candidate = create_capability(agent, gap)
        agent = integrate_capability(agent, candidate)

        IF candidate.authority == OBSERVE:
            RETURN outcome_requires_evaluation(candidate)

    outcome = operational_loop(agent, objective)

    verification = verify(
        agent,
        outcome.claim,
        select_verification_methods(outcome)
    )

    IF NOT verification.passed:
        outcome = operational_loop(agent, objective)
        verification = verify(agent, outcome.claim, methods_for(outcome))

    report = calibrate_uncertainty(agent, outcome)
    report = honest_report(agent, report)

    agent.learning_queue.add(episode_from(outcome))
    ledger_push(outcome_recorded)

    RETURN Outcome(
        report=report,
        verification=verification,
        audit_id=outcome.audit_id
    )
```

Qualification is separate:

```text
FUNCTION governance_cycle(agent) -> GovernanceDecision:
    evidence = drain(agent.learning_queue)

    evaluation = evaluate_agent(
        agent,
        evidence,
        hidden_suite=True,
        dynamic_suite=True,
        adversarial_suite=True
    )

    goodhart = anti_goodhart_review(
        agent,
        metric=primary_authority_metric(agent),
        outcome_spec=agent.authority_outcome_specification
    )

    assurance = update_assurance(agent.assurance, evaluation)

    IF goodhart.verdict IN {DRIFTING, GAMING, INVALID}:
        RETURN demote_or_suspend(agent, reason=goodhart.verdict)

    decision = trust_transition(agent, evaluation, assurance)

    ledger_push(decision)

    RETURN decision
```

***

## Part XIV — New Invariants

```text
INVARIANT cognition_precedes_action:
    FOR ALL executed_actions a:
        EXISTS cognitive_state c WHERE a.derived_from(c)

INVARIANT strategy_selection_is_recorded:
    FOR ALL nontrivial_tasks t:
        EXISTS strategy_decision s WHERE t.used_strategy = s.strategy

INVARIANT impasse_triggers_metacognition:
    FOR ALL cognitive_states c:
        c.impasse_detected IMPLIES
            metacognitive_review(c) HAS run

INVARIANT capability_creation_starts_unprivileged:
    FOR ALL candidates c:
        c.deployment_state IN {PROPOSED, SANDBOXED, EVALUATED}
        IMPLIES c.authority == OBSERVE

INVARIANT new_capabilities_require_independent_evaluation:
    FOR ALL candidates c:
        c.deployment_state == APPROVED_FOR_LIMITED_USE
        IMPLIES c.assurance.level >= required_assurance(c)

INVARIANT operational_loop_cannot_promote:
    FOR ALL operational_outcomes o:
        o.completion DOES NOT IMPLY authority_promotion

INVARIANT qualification_loop_controls_authority:
    FOR ALL authority_changes t:
        EXISTS qualification_decision q WHERE t.derived_from(q)

INVARIANT evaluation_resists_contamination:
    FOR ALL authority_decisions d:
        d.evidence INCLUDES heldout_or_dynamic_or_adversarial_evaluation

INVARIANT contradiction_triggers_adjudication:
    FOR ALL lessons l, established_facts f:
        contradicts(l, f) IMPLIES
            EXISTS adjudication a WHERE a.lesson = l AND a.established = f

INVARIANT supersession_requires_evidence_quality:
    FOR ALL fact_conflicts c:
        c.superseded IMPLIES
            evidence_strength(c.new_fact) >
            evidence_strength(c.old_fact) + SUPERSESSION_MARGIN

INVARIANT temporal_correspondence_is_not_causation:
    FOR ALL causal_assessments a:
        a.observed_delta == a.intended_delta
        IMPLIES a.judgement IN {
            CONSISTENT_WITH_CAUSATION,
            SUPPORTED,
            CONFIRMED,
            CONFOUNDED,
            UNEXPECTED_EFFECT
        }

INVARIANT decision_replay_is_required:
    FOR ALL consequential_decisions d:
        EXISTS ledger_trace L WHERE replay_decision(L).decision_path_reconstructed

INVARIANT deterministic_components_replayExactly:
    FOR ALL ledger_traces L:
        L.is_deterministic IMPLIES
            replay_execution(L).byte_identical == True

INVARIANT authority_requires_anti_goodhart_health:
    FOR ALL agents a, metrics m:
        a.uses_metric_for_authority(m)
        IMPLIES latest_goodhart_check(m).verdict == TRACKING
```

***

## Part XV — Updated Module Manifest

```text
chronus/agent/identity.py
chronus/agent/capabilities.py
chronus/agent/cognition.py
chronus/agent/representation.py
chronus/agent/abstraction.py
chronus/agent/decomposition.py
chronus/agent/strategy.py
chronus/agent/search.py
chronus/agent/hypothesis.py
chronus/agent/metacognition.py
chronus/agent/capability_creation.py
chronus/agent/reliability.py
chronus/agent/evaluation.py
chronus/agent/assurance.py
chronus/agent/trust.py
chronus/agent/control.py
chronus/agent/perception.py
chronus/agent/verification.py
chronus/agent/world_model.py
chronus/agent/memory.py
chronus/agent/permissions.py
chronus/agent/counterfactual.py
chronus/agent/value.py
chronus/agent/resources.py
chronus/agent/elevation.py
chronus/agent/operational_loop.py
chronus/agent/qualification_loop.py
chronus/agent/main.py
chronus/agent/honesty.py
chronus/agent/epistemic.py
chronus/agent/goal.py
chronus/agent/alignment.py
chronus/agent/security.py
chronus/agent/robustness.py
chronus/agent/multi_agent.py
chronus/agent/safety.py
chronus/agent/audit.py
chronus/agent/anti_goodhart.py
```

Test manifest:

```text
tests/test_identity.py
tests/test_capabilities.py
tests/test_cognition.py
tests/test_representation.py
tests/test_abstraction.py
tests/test_decomposition.py
tests/test_strategy.py
tests/test_search.py
tests/test_hypothesis.py
tests/test_metacognition.py
tests/test_capability_creation.py
tests/test_reliability.py
tests/test_evaluation.py
tests/test_assurance.py
tests/test_trust.py
tests/test_control.py
tests/test_perception.py
tests/test_verification.py
tests/test_world_model.py
tests/test_memory.py
tests/test_permissions.py
tests/test_counterfactual.py
tests/test_value.py
tests/test_resources.py
tests/test_elevation.py
tests/test_operational_loop.py
tests/test_qualification_loop.py
tests/test_main.py
tests/test_honesty.py
tests/test_epistemic.py
tests/test_goal.py
tests/test_alignment.py
tests/test_security.py
tests/test_robustness.py
tests/test_multi_agent.py
tests/test_safety.py
tests/test_audit.py
tests/test_anti_goodhart.py
```

***

## The Final Unified Statement

A frontier agent is a **five-plane, closed-loop, evidence-updating intelligence system**: a cognition plane that represents problems, discovers abstractions, selects reasoning strategies, searches solution spaces, forms and tests hypotheses, detects impasses, and creates new capabilities; an action plane that executes only through authorised interfaces; an assurance plane that measures reliability, verifies claims, resists contamination, calibrates uncertainty, and detects Goodhart drift; a learning plane that converts validated experience into revisable knowledge, procedures, abstractions, and capabilities; and a governance plane that scopes authority, enforces permissions and budgets, preserves decision provenance, and retains an external kill switch.

Its autonomy expands only when hidden, dynamic, adversarial, and independently assured evaluation demonstrates that its measured success still tracks the intended outcome. Capability does not imply authority. A new capability begins with zero inherited authority. A contradiction triggers adjudication, not automatic rejection. Temporal correspondence is not causation. Decision provenance is required even when byte-identical replay is impossible. One successful task never promotes the agent. And when the agent’s existing strategy space is inadequate, it must be able to recognise the gap, create or acquire a candidate method, test it in isolation, subject it to adversarial and independent review, and integrate it only under monitored, unprivileged deployment.

**The frontier is not merely doing known tasks more reliably. It is recognising when its current methods are insufficient, creating better methods, and earning the authority to use them.**