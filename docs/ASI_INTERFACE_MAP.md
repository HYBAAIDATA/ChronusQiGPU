# ASI Interface Map — Manifold Elevation Baseline

Recorded before the S-2 / S-3 / S-11 manifold elevation. Every scalar
contract below is load-bearing: existing tests depend on these exact
signatures and return shapes.

## Baseline (recorded pre-change)

```
pytest tests/test_asi_framework.py tests/test_intelligence_poincare_salamander.py -v --no-cov
=> 102 passed, 0 failed  (164.72s)
```

## Substrate (read-only — DO NOT MODIFY)

`Intelligence/poincare_golden_11d.py`

| Symbol | Signature | Contract |
|---|---|---|
| `compute_poincare_norm_sq` | `(x11) -> float` | `||x||_phi^2 = sum phi^{-(i+1)} x_i^2` |
| `poincare_golden_distance` | `(u11, v11) -> float` | `acosh(1 + 2||u-v||_phi^2 / ((1-||u||^2)(1-||v||^2)))` |
| `fold_poincare_11d_vector` | `(x11, num_passes=3) -> (PoincareFoldedArray, int)` | Klein contraction `x/sqrt(1+||x||_phi^2)`; strictly inside ball |
| `unfold_poincare_11d_vector` | `(folded11, num_passes=3) -> ndarray` | Exact preimage via payload; roundtrip `< 1e-14` |
| `PoincareFoldedArray` | `np.ndarray` subclass | carries `_poincare_preimage` payload |
| `PHI_POWERS` | `ndarray[11]` | `phi^{-(i+1)}`, i = 0..10 |
| `generate_zeckendorf_decoupling_mask` | `(primary_dim, total_dims=11) -> int` | `mask & (mask << 1) == 0` — exact integer invariant |
| `compute_zeckendorf_certificate` | `(x11, context_id="") -> ZeckendorfCertificate` | non-adjacent mask, canonical int, prime-bucket slot |

Isometry used by the bridge: `y_i = phi^{-(i+1)/2} x_i` maps the golden
ball `B_phi^11` onto the standard Poincaré ball `B^11` and the golden
metric `ds^2 = 4 sum phi^{-(i+1)} dx_i^2 / (1-||x||_phi^2)^2` onto
`ds^2 = 4|dy|^2/(1-|y|^2)^2` (curvature -1). Exact, not approximate.

## S-2 — `pythagoras/asi/causal_reasoning.py`

| Public interface | Input | Output | Test contract |
|---|---|---|---|
| `CausalModel` (dataclass) | `variables: list[str]`, `edges: dict[str,list[str]]`, `functions: dict[str,callable]`, `noise: dict` | — | `_xyz_model()` fixture |
| `CausalModel.from_adjacency` | `adjacency: np.ndarray`, `names`, `functions`, `exogenous` | `CausalModel` | new — arbitrary DAGs over 𝔹¹¹ |
| `CausalReasoningEngine.observe` | `evidence: dict` | `dict[var -> float]` | `observe({"x":3.0})` → `y=6.0, z=7.0` |
| `CausalReasoningEngine.intervene` | `do: dict, evidence: dict|None` | `dict[var -> float]` | `intervene({"y":10.0},{"x":3.0})` → `y=10.0, z=11.0` |
| `CausalReasoningEngine.counterfactual` | `do: dict, observed: dict` | `dict[var -> float]` | `counterfactual({"x":5.0},{x:1,y:2,z:3})` → `y=10.0, z=11.0` |
| `CausalReasoningEngine.discover_causal_structure` | `data: list[dict]` | `dict[var -> list[str]]` | returns dict containing `"x"` |
| `CausalReasoningEngine.adjacency_matrix` | — | `np.ndarray` N×N | new — {0,1} adjacency |
| `CausalReasoningEngine.severed_adjacency` | `do_vars: Sequence[str]` | `np.ndarray` | new — incoming columns zeroed |
| `CausalReasoningEngine.topological_order` | — | `list[str]` | new — Kahn order, lenient fallback |
| `CausalReasoningEngine.intervene_matrix` | `do: dict, evidence` | `dict[var -> float]` | new — matrix-path do, order-invariant |
| `CausalReasoningEngine.from_manifold_state` | `state: np.ndarray` (ball) | `CausalReasoningEngine` | new — 11-var SCM from 𝔹¹¹ state |
| `CausalReasoningEngine.intervene_on_state` | `state`, `do` (name or index keys), `evidence`, `prior` | `ManifoldCausalResult` | new — `do` on 11-D state; `prior=` composes do-operators exactly |
| `ManifoldCausalResult` | `state, values, adjacency, intervened, interventions, exogenous` | `.to_scalar()` / `.scalar` | new — dual-mode result |

## S-3 — `pythagoras/asi/information_integration.py`

| Public interface | Input | Output | Test contract |
|---|---|---|---|
| `InformationIntegrationMeasurer` | `subsystems: dict[str, callable]` | — | 3 callables parity/mod3/mod5 |
| `.measure_phi` | `inputs: list` | `dict` with keys `total_system_information`, `sum_of_parts_information`, `integrated_information_phi`, `integration_ratio`, `is_integrated` | all keys present |
| `.find_minimum_information_partition` | `inputs: list` | `dict{minimum_phi, partition}` | partition non-None |
| `.measure_phi_manifold` | `state: np.ndarray` (ball) | `ManifoldPhiResult` | new — Φ via state→covariance→Gaussian MIP |
| `.measure_phi_covariance` | `cov: np.ndarray` | `ManifoldPhiResult` | new — min over 2^(N-1)−1 bipartitions of Gaussian MI |
| `.measure_phi_density` | `rho: np.ndarray`, `site_dims` | `ManifoldPhiResult` | new — quantum relative entropy MIP |
| `.phi_scalar` | — | `float` | new — last manifold Φ scalar projection |
| `ManifoldPhiResult` | `phi, partition, method, state, n_sites, partitions_evaluated` | `.phi_scalar` / `.to_scalar()` | new — dual-mode result |

Divergence choice (stated in-code): relative entropy — Gaussian RE for
covariance inputs (Barrett & Seth 2011, canonical for continuous linear
systems) and quantum RE for density matrices (exact partial trace +
von Neumann entropy). Both vanish exactly on product states.

## S-11 — `pythagoras/asi/predictive_processing.py`

| Public interface | Input | Output | Test contract |
|---|---|---|---|
| `BeliefState` (dataclass) | `predicted_phi, predicted_delta, uncertainty, precision, free_energy` | — | attribute reads |
| `ActiveInferenceResult` (dataclass) | `perception, action, expected_free_energy, actual_free_energy, learning_signal` | — | attribute reads |
| `PredictiveProcessingEngine.perceive` | `observed_phi: float, observed_delta: float` | `BeliefState` | posterior moves, `precision > 0` |
| `PredictiveProcessingEngine.act` | `candidate_mutations: list, surrogate_predictions: list` | `ActiveInferenceResult` | chosen action in list; EFE <= max scalar bound |
| `PredictiveProcessingEngine.update_precision` | `observed_error: float` | `None` (mutates beliefs) | large error lowers precision |
| `PredictiveProcessingEngine.get_free_energy_trajectory` | — | `list[float]` | len == #perceives |
| attrs | `beliefs`, `belief_history`, `learning_rate`, `surrogate` | — | direct access in tests |
| `PredictiveProcessingEngine.perceive_manifold` | `observation` (ball), `depth`, `step_size`, `tol`, `max_sweeps` | `ManifoldBelief` | new — hierarchical geodesic descent |
| `ManifoldBelief` | `belief_state, predicted_state, free_energy, layers, errors, free_energy_history, converged, steps` | `.predicted_phi` / `.to_scalar()` | new — dual-mode result |

## Shared adapter — `pythagoras/asi/manifold_bridge.py`

| Interface | Contract |
|---|---|
| `standardize` / `unstandardize` | exact isometry `y_i = phi^{-(i+1)/2} x_i` between `B_phi^11` and `B^11` |
| `mobius_add`, `exp_map`, `log_map` | curvature −1 gyrovector ops on the standard ball |
| `geodesic_descent`, `geodesic_towards` | Riemannian gradient + Armijo descent; in-ball iterates |
| `lift_state` / `project_state` | fold/unfold preserving `PoincareFoldedArray` payloads; roundtrip `< 1e-14` |
| `state_to_graph` | 11-D state → weighted DAG adjacency (upper-triangular, acyclic) |
| `state_to_covariance` | 11-D state → SPD covariance |
| `state_to_prior_layers` | state → hierarchy of ball points via golden smoothing |
| `golden_smoothing_kernel` | public kernel used as generative map g |
| `iter_bipartitions`, `gaussian_mutual_information`, `mutual_information_density`, `minimum_information_partition` | MIP machinery (Gaussian RE and QRE routes) |
| `topological_sort`, `sever_incoming_edges` | DAG utilities for S-2 surgery |
| `scalar_projection` | canonical `.to_scalar()` — golden-weighted norm in `[0, 1)` |
| `as_ball_vector`, `fold_ambient_vector`, `unfold_ball_vector` | validated ball/ambient conversion |

## Scalar returns that MUST remain valid

- `measure_phi(...)["integrated_information_phi"]` — `float`, rounded to 4dp
- `find_minimum_information_partition(...)["minimum_phi"]` — `float`, rounded 4dp
- `observe` / `intervene` / `counterfactual` — flat `dict[str, float]`
- `perceive` — `BeliefState` with scalar `predicted_phi` / `precision` / `free_energy`
- `act` — `ActiveInferenceResult.expected_free_energy` is a `float`
- `get_free_energy_trajectory` — `list[float]`

## Unimplemented targets

(None — all three elevations were implementable over the existing
substrate. This section is updated honestly if that changes.)

## Known limitations (honest disclosures, not gaps)

- `measure_phi_manifold` on a **single** state vector yields Φ = 0: the
  state→covariance projection is rank-deficient, so the information
  localises in one eigendirection. Genuine Φ requires an ensemble —
  pass a covariance (`measure_phi_covariance`) or density matrix
  (`measure_phi_density`) directly.
- S-11 `perceive_manifold` linearises the generative map through the
  golden smoothing kernel `g = K`; a small ridge (`1e-9`) is the
  exogenous-noise floor that keeps the conditional solve non-singular.
- MIP is exact enumeration over `2^(N-1) − 1` bipartitions — fine at
  N ≤ 16 sites; beyond that a greedy/spectral heuristic would be needed.
