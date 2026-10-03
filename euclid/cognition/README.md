# EUCLID Cognition: the integrated primary intelligence loop

`euclid.cognition` makes the intelligence stack operate as **one executable
cognitive cycle** rather than a catalogue of independent modules.  This is
stage 1 of the integrated-intelligence release: the loop itself, its explicit
interfaces, its serialisable cognitive state, and honest deterministic
baselines that later learned/mathematical specialists must beat under
ablation.

## Architecture

`GeneralIntelligenceCore` is an orchestrator, not a god object.  It owns no
specialist implementation.  Every mechanism behind it is an explicit
`typing.Protocol` in `interfaces.py`:

| Interface | Role in the loop |
| --- | --- |
| `WorldModel` | action-conditioned prediction, imagined rollouts, error-driven correction, breakdown detection |
| `MemorySystem` | seven kinds (episodic, semantic, procedural, primitive, skill, strategy, causal), all with provenance |
| `AnalogyEngine` | structural (not surface) transfer, with superficial-analogy rejection |
| `Abducer` | competing explanations; no premature collapse |
| `Deducer` | consequences per hypothesis |
| `CausalDiscriminator` | interventions chosen to maximise hypothesis separation |
| `MetaLearner` | per-problem-class strategy policy with a negative-transfer guard |
| `MetaController` | evidence-driven control decisions (continue / replan / change strategy / halt) |
| `Planner` | hierarchical decomposition and repair |
| `SkillComposer` | skill/primitive composition into candidates |
| `ObjectiveFunction` | multi-objective ranking with auditable weights |
| `Executor` | the only path from cognition to world; routes through `euclid.governance` gates |

## The cycle

`represent -> retrieve -> analogy -> [abduce -> deduce -> discriminate ->
hypothesis update -> strategy -> plan -> compose -> imagine -> rank ->
execute -> compare -> metacontrol (replan?) -> learn] x cycles -> terminate`

Every transition lands in two places: the episode's hash-linked transition
ledger (`CognitiveState.verify_transitions`) and the shared append-only
`EvidenceChain` (`cognition-<phase>` kinds).  There is no opaque success
state: episodes terminate as `solved`, `stalled`, `aborted`, or
`unexecuted`, each with a recorded reason.

## Epistemic discipline

- Evidence carries `origin` (observed / imagined / retrieved / derived) and
  `status` (known / inferred / predicted / assumed / uncertain / contradicted).
- **Imagined rollouts can never carry observed standing** — enforced in the
  `EvidenceItem` constructor, not by convention.
- Hypotheses keep provenance, confidence, and supporting/refuting evidence;
  confirmation/refutation happens only through discriminating intervention
  evidence.

## Ablations

`AblationConfig` surgically disables world modelling, analogy, causal
reasoning, meta-learning, skill composition, or replanning.  Ablations are
recorded on the state and in the evidence chain, so an ablated run can never
masquerade as a full-system run.  This is the substrate for the release's
emergence tests (full system vs each removal).

## φ scheduling

`phi_schedule.phi_order` is a golden-ratio low-discrepancy exploration
ordering.  Per the #110 Lucas/Pisot precision contract it is classified
`exploratory-parametric`, computed in host binary64, and claims **no**
performance advantage.  Experiments must compare it against
`phi_schedule.neutral_order`.

## Falsification criteria

This stage is falsified if any of the following fail:

1. A novel problem cannot traverse the full loop with every transition
   inspectable (test: `test_full_loop_solves_novel_problem`).
2. Imagined evidence can be given observed standing (test:
   `test_imagined_evidence_can_never_be_observed`).
3. An ablated run is indistinguishable from a full run (test:
   `test_ablation_is_recorded_and_fail_closed`).
4. Superficial analogies are accepted as structural ones (test:
   `test_deep_analogy_candidate_superficial_rejected`).
5. Strategy preference transfers across problem classes without evidence
   (test: `test_negative_transfer_guard`).

## Non-claims

No general intelligence, production authority, mining/reward/consensus
authority, external validation, or production readiness is claimed.  All
cognition evidence is rehearsal-class research evidence.

## Acceptance

```bash
python scripts/check_cognition_loop.py
```
