# EUCLID v17 integrated-intelligence research release

**Version:** `17.0.0-rc1`

## Release hypothesis

An evidence-coupled system combining causal world modelling, structural
analogy, abductive discrimination, adaptive representation, hierarchical
planning, strategy learning, v16 search/primitives and durable learning will
solve more held-out tasks—or solve them with better calibration or lower
evaluation cost—than v16.4 and each major ablation.

This hypothesis is falsified when the integrated system does not improve
held-out correctness, when confidence intervals overlap zero advantage without
another material benefit, or when added cost overwhelms the measured gain.

## Implemented architecture

`EuclidRuntime.production()` constructs one shared cognitive organism:

1. Cognitive state and hash-linked transition evidence.
2. Measured representation comparison and inspectable subobjective formation.
3. Durable multi-kind retrieval and structural analogy.
4. Competing abduction, deduction, TOE causal discrimination and imagined
   counterfactuals.
5. Persistent, problem-class-scoped strategy learning.
6. TOE bounded hierarchical planning and evidence-driven metacontrol.
7. Selectable v16 MCTS, evolution, AST primitives, surrogate, topology,
   discovery and transfer machinery.
8. Governed repository execution.
9. Prediction-error correction and reward-authority-gated shared learning.
10. Persistent reachability, restart and transfer evidence.

## New mechanisms

- Representation controller: literal, relational, graph, source-dependency and
  exploratory manifold representations compete on measured net utility.
- Objective controller: uncertainty, contradiction, evidence-gap and model
  repair objectives; detached proxies are marked explicitly.
- Persistent strategy learner: class-local evidence and negative-transfer log.
- Capability lifecycle: discover, validate semantic equivalence, generalise,
  promote and deprecate primitives/skills without erasing history.
- Correctness-gated behavioural novelty archive.
- Partition-safe repeated benchmark programme with 95% variation intervals.
- Paired φ-ordering experiment against neutral identity order.
- Fail-closed release archive, wheel and integrity-manifest builder.

## Evaluation programme

The checked-in evaluation manifest covers deduction, abduction, analogy,
causality, counterfactual reasoning, distribution shift, planning, replanning,
compositional skills, primitive discovery, meta-learning, representation
change, transfer, negative transfer, continual learning and reward hacking.

Required systems:

- v16.4 reference;
- integrated v17;
- minus world model;
- minus causal reasoning;
- minus analogy;
- minus meta-learning;
- minus learned skills/primitives;
- minus representation restructuring;
- minus φ/Lucas/manifold contribution;
- minus replanning.

Required metrics include correctness, solve rate, wall time, prediction error,
uncertainty, replans, memory reuse, representation change, primitive use and
strategy selection. Release comparisons require repeated evaluation runs.

## Scientific status

The architecture and experiment machinery are implemented. No superiority
claim is made until CI or a qualified runner produces:

- complete focused and repository test results;
- installable wheel evidence;
- repeated held-out benchmark results;
- v16.4 comparison;
- every required ablation;
- transfer and negative-transfer results;
- adversarial reward-hacking results;
- continual-retention measurements;
- resource measurements;
- archive manifest and verified SHA-256.

Negative mathematical, transfer and ablation results remain in the evidence
record. Passing unit tests alone does not complete the release.