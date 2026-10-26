# φ validation — PYTHAGORAS v12.2

Reproduce: `python -m pythagoras.experiments.phi_validation --seeds 3 --generations 4 --bootstrap 2000`

Expected before running: positive association with maintainability change, complexity improvement, and mypy-error reduction. AST-node change is a control and is not treated as quality evidence.

| Outcome | All ρ (95% CI) | ADD:AnnAssign variants ρ (95% CI) |
|---|---:|---:|
| Δ maintainability index | -0.7335 (-0.9847, -0.1109) | -0.3660 (-0.9474, 0.4211) |
| Cyclomatic-complexity improvement | 0.0000 (-0.6868, 0.9199) | 0.9354 (0.7490, 0.9733) |
| Mypy-error reduction | n/a (n/a, n/a) | n/a (n/a, n/a) |
| Δ AST nodes (control) | -0.1917 (-0.8148, 0.6668) | -0.8831 (-0.9597, -0.5335) |

## ADD:AnnAssign

- Steps: 19
- Mean Δφ: 0.0014
- Range: 0.0009 to 0.0021

Interpret correlations against the committed output; do not infer quality validation when the confidence interval crosses zero or when Δφ tracks the AST-node control more strongly than independent measures.

## Result

This run does **not** validate the expected quality directions. Overall Δφ is negatively associated with maintainability-index change, cyclomatic complexity shows no monotonic association, and mypy error count does not vary. In the ADD:AnnAssign subset, complexity improvement is positively associated with Δφ, but maintainability remains inconclusive and the AST-node control is also strong. The annotation-driven φ gain therefore cannot yet be separated from structural-size effects or treated as independent code-quality evidence.
