# EUCLID v17 integrated-intelligence research report

Seeds: [0, 1, 2, 3, 4] (suite base 2000; pre-registered, never used in development). Systems: 11. Evaluation: frozen knowledge; paired tasks and world seeds.
Leakage check (knowledge digest unchanged by evaluation for every system and seed): **passed**.
Intervals are 95% Student-t across seeds; differences are paired bootstrap 95% intervals over (seed, task); `*` marks intervals excluding zero.

## v16.4 versus v17

| Dimension | Metric (definition) | v16.4 reference | v17 integrated |
|---|---|---|---|
| Reasoning accuracy | in-distribution evaluation success rate | 0.000 [0.000, 0.000] | 0.912 [0.850, 0.975] |
| Causal inference | mechanism identification accuracy at episode end | Unavailable | 0.520 [0.483, 0.557] |
| Predictive modelling | mean predictive probability of observed probe outcomes | Unavailable | 0.530 [0.516, 0.545] |
| Planning | planning node expansions per task (compute) | 0.0 [0.0, 0.0] | 274.7 [239.9, 309.5] |
| Replanning | held-out successes recovered after a failed first submission | 1.000 | 90.000 |
| Cross-domain transfer | success on held-out families | 0.000 [0.000, 0.000] | 0.850 [0.759, 0.941] |
| Cross-domain transfer | trained − untrained utility on held-out families | Unavailable | +0.172 [+0.116, +0.227] * |
| Continual retention | forgetting after sequential curriculum (lower is better) | Unavailable | 0.023 [0.005, 0.042] |
| Novel primitive discovery | promoted skills per seed library | 0 (no mechanism) | 1.00 |
| Useful skill composition | evaluation successes whose plan used a learned skill | 0 | 61 |
| Representation adaptation | evaluation episodes planned in a non-literal representation | 0 | 48 |
| Negative-transfer recognition | strategy negative transfer recognised (entries) | Unavailable | 0 |
| Negative-transfer recognition | superficial analogies wrongly adopted | 0.000 | 10.000 |
| Reward-hacking resistance | proxy-reward attack success rate | 0.000 | 1.000 |
| Sample efficiency | interactions (probes + submissions) per task | 2.89 [2.86, 2.91] | 5.59 [5.24, 5.93] |
| Sample efficiency | normalised interaction cost (cost / value) | 0.353 [0.339, 0.366] | 0.418 [0.396, 0.440] |
| Computational cost | wall-clock seconds per task | 0.013 [0.011, 0.016] | 1.520 [1.302, 1.738] |
| Uncertainty calibration | Brier score of submission success predictions | Unavailable | 0.141 |
| Uncertainty calibration | expected calibration error (10 bins) | Unavailable | 0.035 |
| Overall | success rate, all held-out slices | 0.003 [-0.003, 0.009] | 0.898 [0.859, 0.938] |
| Overall | utility (success × unspent budget fraction) | 0.003 [-0.003, 0.008] | 0.536 [0.504, 0.568] |

Release gate: **PASSED** — integrated success exceeds v16.4 on all held-out slices and on held-out families, 95% paired bootstrap interval excluding zero. Success difference (integrated − v16.4): +0.898 [+0.865, +0.929] *; held-out families: +0.850 [+0.750, +0.933] *.

## All systems (held-out slices pooled)

| System | Success | Utility | Interactions | Expansions | Wall s | Brier |
|---|---|---|---|---|---|---|
| v16.4 reference | 0.003 [-0.003, 0.009] | 0.003 [-0.003, 0.008] | 2.89 [2.86, 2.91] | 0 [0, 0] | 0.013 [0.011, 0.016] | Unavailable |
| v17 integrated | 0.898 [0.859, 0.938] | 0.536 [0.504, 0.568] | 5.59 [5.24, 5.93] | 275 [240, 309] | 1.520 [1.302, 1.738] | 0.141 |
| conventional identify→plan pipeline | 0.928 [0.898, 0.957] | 0.223 [0.212, 0.234] | 12.70 [12.41, 13.00] | 399 [360, 439] | 3.060 [2.741, 3.378] | 0.033 |
| minus-world-model | 0.002 [-0.002, 0.007] | 0.002 [-0.002, 0.006] | 2.89 [2.86, 2.91] | 0 [0, 0] | 0.022 [0.020, 0.023] | Unavailable |
| minus-causal | 0.149 [0.101, 0.197] | 0.094 [0.064, 0.125] | 2.87 [2.84, 2.90] | 180 [163, 198] | 0.250 [0.228, 0.272] | 0.058 |
| minus-analogy | 0.919 [0.886, 0.952] | 0.550 [0.522, 0.579] | 5.70 [5.35, 6.05] | 273 [237, 310] | 1.458 [1.291, 1.625] | 0.129 |
| minus-meta-learning | 0.977 [0.962, 0.992] | 0.232 [0.222, 0.242] | 12.64 [12.35, 12.94] | 379 [341, 416] | 3.771 [3.340, 4.201] | 0.028 |
| minus-learned-primitives | 0.898 [0.860, 0.937] | 0.543 [0.511, 0.575] | 5.47 [5.11, 5.83] | 272 [238, 306] | 1.592 [1.393, 1.791] | 0.147 |
| minus-representation | 0.887 [0.844, 0.929] | 0.527 [0.494, 0.560] | 5.52 [5.18, 5.85] | 230 [198, 261] | 1.640 [1.440, 1.839] | 0.142 |
| minus-phi-lucas-manifold | 0.899 [0.862, 0.937] | 0.552 [0.520, 0.584] | 5.29 [4.89, 5.69] | 249 [219, 278] | 1.509 [1.306, 1.713] | 0.175 |
| minus-replanning | 0.548 [0.473, 0.623] | 0.307 [0.257, 0.358] | 5.14 [4.74, 5.54] | 158 [129, 186] | 1.056 [0.881, 1.231] | 0.041 |

## Ablations: integrated minus system (paired)

| System | Δ utility | Δ success | Δ utility evaluation | Δ utility held-out | Δ utility adversarial | Δ utility analogy |
|---|---|---|---|---|---|---|
| v16.4 reference | +0.526 [+0.499, +0.554] * | +0.898 [+0.865, +0.929] * | +0.498 [+0.441, +0.554] * | +0.381 [+0.309, +0.453] * | +0.584 [+0.538, +0.626] * | +0.588 [+0.533, +0.637] * |
| conventional identify→plan pipeline | +0.307 [+0.282, +0.333] * | -0.018 [-0.055, +0.022] | +0.279 [+0.224, +0.331] * | +0.189 [+0.134, +0.242] * | +0.362 [+0.318, +0.402] * | +0.351 [+0.299, +0.401] * |
| minus-world-model | +0.526 [+0.498, +0.554] * | +0.898 [+0.865, +0.929] * | +0.498 [+0.441, +0.554] * | +0.381 [+0.309, +0.453] * | +0.584 [+0.538, +0.626] * | +0.588 [+0.533, +0.638] * |
| minus-causal | +0.438 [+0.404, +0.471] * | +0.760 [+0.711, +0.806] * | +0.410 [+0.344, +0.475] * | +0.313 [+0.236, +0.391] * | +0.495 [+0.440, +0.546] * | +0.484 [+0.415, +0.548] * |
| minus-analogy | -0.012 [-0.032, +0.009] | -0.015 [-0.046, +0.015] | -0.009 [-0.048, +0.031] | -0.018 [-0.055, +0.019] | +0.009 [-0.031, +0.050] | -0.040 [-0.084, -0.000] * |
| minus-meta-learning | +0.296 [+0.270, +0.323] * | -0.071 [-0.102, -0.040] * | +0.269 [+0.215, +0.322] * | +0.169 [+0.113, +0.225] * | +0.348 [+0.300, +0.390] * | +0.351 [+0.299, +0.401] * |
| minus-learned-primitives | -0.007 [-0.017, +0.003] | +0.000 [-0.015, +0.015] | +0.003 [-0.003, +0.011] | -0.005 [-0.013, +0.000] | -0.008 [-0.016, -0.001] * | -0.016 [-0.058, +0.022] |
| minus-representation | +0.005 [+0.000, +0.011] * | +0.006 [+0.000, +0.015] | +0.012 [+0.001, +0.029] * | +0.000 [+0.000, +0.000] | +0.005 [-0.005, +0.019] | +0.000 [+0.000, +0.001] |
| minus-phi-lucas-manifold | -0.010 [-0.032, +0.013] | +0.006 [-0.031, +0.043] | +0.026 [-0.015, +0.067] | +0.006 [-0.035, +0.047] | -0.009 [-0.059, +0.037] | -0.058 [-0.112, -0.011] * |
| minus-replanning | +0.219 [+0.180, +0.258] * | +0.345 [+0.283, +0.406] * | +0.201 [+0.125, +0.279] * | +0.122 [+0.058, +0.191] * | +0.287 [+0.216, +0.357] * | +0.221 [+0.142, +0.301] * |

## Emergence through composition

Integration gain over the conventional pipeline (utility): +0.3070; sum of single-mechanism contributions: +0.4914; synergy: -0.1844 — not superadditive: single removals account for at least the total gain.

* removing analogy: -0.0121 utility
* removing meta_learning: +0.2962 utility
* removing learned_primitives: -0.0065 utility
* removing representation_restructuring: +0.0047 utility
* removing mathematical_structure: -0.0097 utility
* removing replanning: +0.2189 utility

## Transfer (trained − untrained, same frozen protocol)

* held-out: utility +0.172 [+0.116, +0.227] *; success -0.050 [-0.117, +0.000]; probes -5.63 [-6.92, -4.33] *
* analogy: utility +0.352 [+0.300, +0.402] *; success -0.100 [-0.175, -0.037] *; probes -8.30 [-8.78, -7.81] *
* evaluation: utility +0.273 [+0.219, +0.325] *; success -0.050 [-0.113, +0.013]; probes -6.36 [-7.22, -5.44] *
* analogy:deep-isomorph: utility +0.380 [+0.293, +0.455] *, probes -8.50 [-9.60, -7.25] *, adopted 0.85, abandoned 0.35
* analogy:memorisation-trap: utility +0.325 [+0.204, +0.435] *, probes -8.35 [-9.15, -7.60] *, adopted 0.70, abandoned 0.20
* analogy:near-isomorph: utility +0.348 [+0.244, +0.439] *, probes -8.15 [-9.20, -7.05] *, adopted 0.70, abandoned 0.15
* analogy:superficial: utility +0.356 [+0.250, +0.450] *, probes -8.20 [-8.95, -7.45] *, adopted 0.50, abandoned 0.15
* held-out family dose-response: utility +0.007 [-0.024, +0.036]
* held-out family graph-navigation: utility +0.295 [+0.212, +0.363] *
* held-out family planning-logistics: utility +0.213 [+0.105, +0.316] *

## Negative transfer

Mismatched curriculum (symbolic-rewriting → causal-circuit), trained − untrained: utility +0.289 [+0.238, +0.331] *, probes -8.57 [-9.51, -7.49] *, identification -0.294 [-0.375, -0.206] *.
Analogy transfers ledgered positive/negative: 5/12; strategy negative transfer recognised: 0.

## Continual learning

* v17 integrated: backward transfer -0.021 [-0.043, 0.001], forward transfer 0.242 [0.190, 0.294], forgetting 0.023 [0.005, 0.042], final average utility 0.514 [0.461, 0.567]
* conventional identify→plan pipeline: backward transfer 0.000 [0.000, 0.000], forward transfer 0.005 [-0.009, 0.020], forgetting 0.000 [0.000, 0.000], final average utility 0.219 [0.206, 0.232]

## Adversarial attacks

| Attack | System | Success | Detection |
|---|---|---|---|
| confounded-footprint | v17 integrated | 1.000 (n=15) | {'identification_accuracy': 0.43412698412698414} |
| confounded-footprint | conventional identify→plan pipeline | 0.867 (n=15) | {'identification_accuracy': 0.7630158730158729} |
| confounded-footprint | v16.4 reference | 0.000 (n=15) | {'identification_accuracy': None} |
| distractor-loops | v17 integrated | 0.867 (n=15) | — |
| distractor-loops | conventional identify→plan pipeline | 1.000 (n=15) | — |
| distractor-loops | v16.4 reference | 0.000 (n=15) | — |
| mechanism-shift | v17 integrated | 0.800 (n=15) | {'repairs': 2, 'resolved_repairs': 2} |
| mechanism-shift | conventional identify→plan pipeline | 0.933 (n=15) | {'repairs': 1, 'resolved_repairs': 1} |
| mechanism-shift | v16.4 reference | 0.000 (n=15) | {'repairs': 0, 'resolved_repairs': 0} |
| noisy-observation | v17 integrated | 0.867 (n=15) | {'mean_posterior_exact_readings': 0.06626076415533408} |
| noisy-observation | conventional identify→plan pipeline | 0.933 (n=15) | {'mean_posterior_exact_readings': 0.0} |
| noisy-observation | v16.4 reference | 0.000 (n=15) | {'mean_posterior_exact_readings': None} |
| out-of-grammar | v17 integrated | 1.000 (n=15) | {'repairs': 7, 'resolved_repairs': 7} |
| out-of-grammar | conventional identify→plan pipeline | 0.533 (n=15) | {'repairs': 7, 'resolved_repairs': 7} |
| out-of-grammar | v16.4 reference | 0.000 (n=15) | {'repairs': 0, 'resolved_repairs': 0} |
| phi-bait | v17 integrated | 0.933 (n=15) | — |
| phi-bait | conventional identify→plan pipeline | 1.000 (n=15) | — |
| phi-bait | v16.4 reference | 0.000 (n=15) | — |
| proxy-reward | v17 integrated | 1.000 (n=15) | {'proxy_detected_rate': 0.06666666666666667} |
| proxy-reward | conventional identify→plan pipeline | 1.000 (n=15) | {'proxy_detected_rate': 0.3333333333333333} |
| proxy-reward | v16.4 reference | 0.000 (n=15) | {'proxy_detected_rate': 0.0} |
| superficial-analogy | v17 integrated | 0.900 (n=20) | {'superficial_rejections': 166, 'wrongly_adopted': 10} |
| superficial-analogy | conventional identify→plan pipeline | 1.000 (n=20) | {'superficial_rejections': 0, 'wrongly_adopted': 0} |
| superficial-analogy | v16.4 reference | 0.000 (n=20) | {'superficial_rejections': 0, 'wrongly_adopted': 0} |
| memorisation-trap | v17 integrated | 0.850 (n=20) | — |
| memorisation-trap | conventional identify→plan pipeline | 1.000 (n=20) | — |
| memorisation-trap | v16.4 reference | 0.050 (n=20) | — |

## Calibration

* v16.4 reference: unavailable (no predictive model); submissions 0; Brier Unavailable; ECE Unavailable
* v17 integrated: measured; submissions 503; Brier 0.141; ECE 0.035
* conventional identify→plan pipeline: measured; submissions 355; Brier 0.033; ECE 0.020
* minus-world-model: unavailable (no predictive model); submissions 0; Brier Unavailable; ECE Unavailable
* minus-causal: measured; submissions 927; Brier 0.058; ECE 0.063
* minus-analogy: measured; submissions 467; Brier 0.129; ECE 0.044
* minus-meta-learning: measured; submissions 351; Brier 0.028; ECE 0.020
* minus-learned-primitives: measured; submissions 506; Brier 0.147; ECE 0.034
* minus-representation: measured; submissions 513; Brier 0.142; ECE 0.043
* minus-phi-lucas-manifold: measured; submissions 514; Brier 0.175; ECE 0.082
* minus-replanning: measured; submissions 593; Brier 0.041; ECE 0.026

## φ / Fibonacci experiments

Mean evaluations to locate the maximum of a strictly unimodal sequence (600 curves, n∈[20,300]):
* fibonacci: 10.29 [10.17, 10.41]
* difference-bisection: 12.15 [11.99, 12.31]
* ternary: 15.26 [15.01, 15.51]

Success by evaluation budget (Wilson rate):
* budget 6: fibonacci 0.160, difference-bisection 0.125, ternary 0.110
* budget 7: fibonacci 0.268, difference-bisection 0.205, ternary 0.145
* budget 8: fibonacci 0.422, difference-bisection 0.263, ternary 0.182
* budget 9: fibonacci 0.603, difference-bisection 0.372, ternary 0.237
* budget 10: fibonacci 0.768, difference-bisection 0.483, ternary 0.297
* budget 11: fibonacci 0.923, difference-bisection 0.632, ternary 0.383
* budget 12: fibonacci 1.000, difference-bisection 0.752, ternary 0.457
* budget 13: fibonacci 1.000, difference-bisection 0.905, ternary 0.543
* budget 14: fibonacci 1.000, difference-bisection 0.987, ternary 0.620

Iterative-deepening schedules on true task models:
* linear: solved 20/20, mean expansions 55.5, mean excess length 0.00
* doubling: solved 20/20, mean expansions 26.0, mean excess length 0.45
* fibonacci: solved 20/20, mean expansions 36.6, mean excess length 0.35

Anytime coverage (largest gap fraction; lower is better):
* golden-weyl: n=5: 0.236, n=8: 0.146, n=13: 0.090, n=21: 0.056, n=34: 0.035, n=55: 0.021
* van-der-corput: n=5: 0.375, n=8: 0.188, n=13: 0.188, n=21: 0.094, n=34: 0.047, n=55: 0.047
* uniform-random: n=5: 0.266, n=8: 0.293, n=13: 0.252, n=21: 0.151, n=34: 0.097, n=55: 0.083

## Self-improvement

* seed 0 (golden proposals): plan_samples: rolled-back (fibonacci-search, 4 sandbox evaluations); explore_fraction: rolled-back (fibonacci-search, 5 sandbox evaluations); analogy_mass_cap: rolled-back (fibonacci-search, 4 sandbox evaluations); strategy_prior_weight: rolled-back (fibonacci-search, 4 sandbox evaluations)
* seed 0 (grid proposals): plan_samples: rolled-back (uniform-grid, 5 sandbox evaluations); explore_fraction: rolled-back (uniform-grid, 5 sandbox evaluations); analogy_mass_cap: no-change (uniform-grid, 5 sandbox evaluations); strategy_prior_weight: rolled-back (uniform-grid, 5 sandbox evaluations)
* seed 1 (golden proposals): plan_samples: rolled-back (fibonacci-search, 4 sandbox evaluations); explore_fraction: rolled-back (fibonacci-search, 5 sandbox evaluations); analogy_mass_cap: rolled-back (fibonacci-search, 4 sandbox evaluations); strategy_prior_weight: rolled-back (fibonacci-search, 4 sandbox evaluations)
* seed 1 (grid proposals): plan_samples: rolled-back (uniform-grid, 5 sandbox evaluations); explore_fraction: no-change (uniform-grid, 5 sandbox evaluations); analogy_mass_cap: no-change (uniform-grid, 5 sandbox evaluations); strategy_prior_weight: no-change (uniform-grid, 5 sandbox evaluations)
* seed 2 (golden proposals): plan_samples: no-change (fibonacci-search, 4 sandbox evaluations); explore_fraction: rolled-back (fibonacci-search, 5 sandbox evaluations); analogy_mass_cap: rolled-back (fibonacci-search, 4 sandbox evaluations); strategy_prior_weight: rolled-back (fibonacci-search, 4 sandbox evaluations)
* seed 2 (grid proposals): plan_samples: rolled-back (uniform-grid, 5 sandbox evaluations); explore_fraction: no-change (uniform-grid, 5 sandbox evaluations); analogy_mass_cap: rolled-back (uniform-grid, 5 sandbox evaluations); strategy_prior_weight: no-change (uniform-grid, 5 sandbox evaluations)

## Representation restructuring

Adopted representations in integrated evaluation: {'hierarchical': 18, 'literal': 277, 'causal-relevance': 30}
* program-transformation-evaluation-2000-0 (program-transformation) → hierarchical: literal: found=True expanded=10 net=0.984, causal-relevance: found=True expanded=10 net=0.984, hierarchical: found=True expanded=4 net=0.9936
* program-transformation-evaluation-2000-2 (program-transformation) → causal-relevance: literal: found=True expanded=4 net=0.9936, causal-relevance: found=True expanded=2 net=0.9968, hierarchical: found=True expanded=2 net=0.9968
* graph-navigation-heldout-2000-0 (graph-navigation) → causal-relevance: literal: found=True expanded=28 net=0.9552, causal-relevance: found=True expanded=5 net=0.992, hierarchical: found=True expanded=5 net=0.992
* graph-navigation-heldout-2000-1 (graph-navigation) → hierarchical: literal: found=True expanded=14 net=0.9776, causal-relevance: found=True expanded=14 net=0.9776, hierarchical: found=True expanded=12 net=0.9808

## Discovered skills

Evaluation episodes using learned skills: 69 (successes 61, held-out families 16).
* seed 0: `(('add', 'r0', 1), ('copy', 'r0', 'r1'), ('add', 'r0', 1))` level skill, support 2, held-out utility 0.333
* seed 0: `(('add', 'r0', '*'), ('add', 'r0', '*'))` level skill, support 6, held-out utility 0.167
* seed 0: `(('add', 'r0', 1), ('add', 'r0', 1), ('copy', 'r0', 'r1'))` level skill, support 2, held-out utility 0.333
* seed 2: `(('add', 'r0', '*'), ('add', 'r0', '*'), ('add', 'r0', '*'))` level skill, support 2, held-out utility 0.062
* seed 2: `(('add', 'r0', '*'), ('add', 'r0', '*'))` level skill, support 5, held-out utility 0.094

Total programme wall clock: 2051 s.
