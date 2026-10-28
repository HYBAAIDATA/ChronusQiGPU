# HYBA MCP expert skills

The expert skill layer is a separate, advisory tier above the existing exact-math
tools. Its six contracts are discoverable with `discover_skills` and retrievable
individually with `get_skill`. Skill output never grants proof, consensus, or
execution authority.

## Tool operations

| Tool | Purpose |
|---|---|
| `discover_skills()` | List skill IDs, contracts, routing estimates, examples, and limitations. |
| `get_skill(skill_id)` | Return one full skill contract. |
| `validate_inputs(skill_id, arguments)` | Validate the input object without executing a skill. |
| `invoke_skill(skill_id, arguments, options?)` | Invoke through budgets, AL HARAS authorization, audit, and sandbox gates. |
| `evaluate_skill_outcome(skill_id, outcome, options?)` | Add a caller-authorized outcome to evaluation telemetry. |

`invoke_skill` options may contain `constraints` (`max_cost`, `max_risk`,
`max_seconds`) and `sandbox` (`timeout_seconds`, `cpu_seconds`, `memory_bytes`,
`max_input_bytes`, `max_output_bytes`). Identity is supplied only by the
embedding host's trusted `identity_provider`; caller-provided identity values
are ignored. If identity, AL HARAS authorization, or durable audit storage is
unavailable, the request is denied.

## Skills

| ID | Input | Output | Source and boundary |
|---|---|---|---|
| `proof.emergence_verify` | `spectral_gap`, `betti_1`, `phi_resonance` (finite numbers) | `emerged`, `confidence`, `reasoning`, source diagnostics | Calls the recovered source function, backed by the packageable `euclid.intelligence_assessment` implementation. Confidence is binary predicate agreement, not a probability. No 100-system benchmark dataset is included. |
| `reasoning.causal_explain` | `data` object, non-empty `query` | ranked `factors`, `causal_ranking`, `confidence`, availability and limitations | Calls `IntelligenceOrchestrator.toe_explain_causality(data)`. The current method does not accept or interpret `query`; this is descriptive factor ranking, not identified causal effects. |
| `healing.propose_repair` | `telemetry` object, `fault_type` | `proposal`, `executed: false`, categorical `risk_score` | Calls only `SelfRepairEngine.diagnose`. Does not approve, apply, or verify. |
| `security.verify_authority` | `identity`, `capability`, positive `lease_duration` | `allowed`, `reason`, `audit_record` | Calls the configured authorization adapter. The default is deny. A deployment must bind it to its AL HARAS Guardian/entitlement policy. |
| `adaptation.trajectory_predict` | `state_data` object, `horizon` 1–6 | `trajectory`, `uncertainty`, `intervention_points` | Calls the orchestrator forecast. The engine provides six fixed points; horizon selects a prefix. Uncertainty is one minus measured state fidelity, not a calibrated interval. |
| `mining.guidance` | byte arrays `header` and `target`, `context` object | `search_space`, `expected_value` (`null` when unsupported), `quantum_guidance` | Calls `toe_guide_mining`. It neither predicts mining return nor changes candidate validity; SHA256d and target checks remain the only validity authority. |

Inputs and outputs use JSON Schema object contracts. Since JSON has no byte
primitive, the mining tool represents each byte sequence as an array of integers
in `[0, 255]`; the skill converts these to `bytes` before calling EUCLID.

## Failure semantics

Validation errors, unknown skills, authorization failures, unavailable
dependencies, unsupported sandbox limits, timeouts, and source exceptions are
returned as structured errors. They do not produce a successful result or invoke
a fallback with different semantics. Routing only selects among explicitly
provided registered candidates; it does not infer a task's meaning.

## Evidence status

The contracts expose current callable interfaces, not proof of generalized
competence. In particular, the emergence source's “100 AI systems” statement is
not independently reproducible from the checked-in source tree. No perfect
classification or comparative mining advantage is asserted by this package.
