# EUCLID 17.0.0 — integrated adaptive intelligence

**Release version:** `17.0.0` (package `euclid-engine`; `euclid.__version__`).
**Baseline:** EUCLID v16.4 as present at commit `585d7b11` (the immutable
production baseline; `euclid.__version__` there read `16.0.0`).
**Evidence:** `reports/euclid_v17/research_report.md` and `.json` (every
episode row, every interval), produced by `scripts/run_euclid_v17_research.py`
on pre-registered suites that were never used during development.

This release does not add a list of separate features.  It makes the existing
cognitive core operate as one adaptive system, then tests — with ablations,
held-out families, adversarial attacks and repeated seeds — whether that
integration is what produces the capability.

<!-- RESULTS -->
## Results (generated from `reports/euclid_v17/research_report.json`)

Seeds: [0, 1, 2, 3, 4] (suite base 2000; pre-registered, never used in development). Systems: 11. Evaluation: frozen knowledge; paired tasks and world seeds.
Leakage check (knowledge digest unchanged by evaluation for every system and seed): **passed**.
Intervals are 95% Student-t across seeds; differences are paired bootstrap 95% intervals over (seed, task); `*` marks intervals excluding zero.

### v16.4 versus v17

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

### All systems (held-out slices pooled)

| System | Success | Utility | Interactions | Expansions | Wall s | Brier |
|---|---|---|---|---|---|---|
| v17 integrated | 0.898 [0.859, 0.938] | 0.536 [0.504, 0.568] | 5.59 [5.24, 5.93] | 275 [240, 309] | 1.520 [1.302, 1.738] | 0.141 |
| minus-analogy | 0.919 [0.886, 0.952] | 0.550 [0.522, 0.579] | 5.70 [5.35, 6.05] | 273 [237, 310] | 1.458 [1.291, 1.625] | 0.129 |
| minus-causal | 0.149 [0.101, 0.197] | 0.094 [0.064, 0.125] | 2.87 [2.84, 2.90] | 180 [163, 198] | 0.250 [0.228, 0.272] | 0.058 |
| minus-learned-primitives | 0.898 [0.860, 0.937] | 0.543 [0.511, 0.575] | 5.47 [5.11, 5.83] | 272 [238, 306] | 1.592 [1.393, 1.791] | 0.147 |
| minus-meta-learning | 0.977 [0.962, 0.992] | 0.232 [0.222, 0.242] | 12.64 [12.35, 12.94] | 379 [341, 416] | 3.771 [3.340, 4.201] | 0.028 |
| minus-phi-lucas-manifold | 0.899 [0.862, 0.937] | 0.552 [0.520, 0.584] | 5.29 [4.89, 5.69] | 249 [219, 278] | 1.509 [1.306, 1.713] | 0.175 |
| minus-replanning | 0.548 [0.473, 0.623] | 0.307 [0.257, 0.358] | 5.14 [4.74, 5.54] | 158 [129, 186] | 1.056 [0.881, 1.231] | 0.041 |
| minus-representation | 0.887 [0.844, 0.929] | 0.527 [0.494, 0.560] | 5.52 [5.18, 5.85] | 230 [198, 261] | 1.640 [1.440, 1.839] | 0.142 |
| minus-world-model | 0.002 [-0.002, 0.007] | 0.002 [-0.002, 0.006] | 2.89 [2.86, 2.91] | 0 [0, 0] | 0.022 [0.020, 0.023] | Unavailable |
| conventional identify→plan pipeline | 0.928 [0.898, 0.957] | 0.223 [0.212, 0.234] | 12.70 [12.41, 13.00] | 399 [360, 439] | 3.060 [2.741, 3.378] | 0.033 |
| v16.4 reference | 0.003 [-0.003, 0.009] | 0.003 [-0.003, 0.008] | 2.89 [2.86, 2.91] | 0 [0, 0] | 0.013 [0.011, 0.016] | Unavailable |

### Ablations: integrated minus system (paired)

| System | Δ utility | Δ success | Δ utility evaluation | Δ utility held-out | Δ utility adversarial | Δ utility analogy |
|---|---|---|---|---|---|---|
| minus-analogy | -0.012 [-0.032, +0.009] | -0.015 [-0.046, +0.015] | -0.009 [-0.048, +0.031] | -0.018 [-0.055, +0.019] | +0.009 [-0.031, +0.050] | -0.040 [-0.084, -0.000] * |
| minus-causal | +0.438 [+0.404, +0.471] * | +0.760 [+0.711, +0.806] * | +0.410 [+0.344, +0.475] * | +0.313 [+0.236, +0.391] * | +0.495 [+0.440, +0.546] * | +0.484 [+0.415, +0.548] * |
| minus-learned-primitives | -0.007 [-0.017, +0.003] | +0.000 [-0.015, +0.015] | +0.003 [-0.003, +0.011] | -0.005 [-0.013, +0.000] | -0.008 [-0.016, -0.001] * | -0.016 [-0.058, +0.022] |
| minus-meta-learning | +0.296 [+0.270, +0.323] * | -0.071 [-0.102, -0.040] * | +0.269 [+0.215, +0.322] * | +0.169 [+0.113, +0.225] * | +0.348 [+0.300, +0.390] * | +0.351 [+0.299, +0.401] * |
| minus-phi-lucas-manifold | -0.010 [-0.032, +0.013] | +0.006 [-0.031, +0.043] | +0.026 [-0.015, +0.067] | +0.006 [-0.035, +0.047] | -0.009 [-0.059, +0.037] | -0.058 [-0.112, -0.011] * |
| minus-replanning | +0.219 [+0.180, +0.258] * | +0.345 [+0.283, +0.406] * | +0.201 [+0.125, +0.279] * | +0.122 [+0.058, +0.191] * | +0.287 [+0.216, +0.357] * | +0.221 [+0.142, +0.301] * |
| minus-representation | +0.005 [+0.000, +0.011] * | +0.006 [+0.000, +0.015] | +0.012 [+0.001, +0.029] * | +0.000 [+0.000, +0.000] | +0.005 [-0.005, +0.019] | +0.000 [+0.000, +0.001] |
| minus-world-model | +0.526 [+0.498, +0.554] * | +0.898 [+0.865, +0.929] * | +0.498 [+0.441, +0.554] * | +0.381 [+0.309, +0.453] * | +0.584 [+0.538, +0.626] * | +0.588 [+0.533, +0.638] * |
| conventional identify→plan pipeline | +0.307 [+0.282, +0.333] * | -0.018 [-0.055, +0.022] | +0.279 [+0.224, +0.331] * | +0.189 [+0.134, +0.242] * | +0.362 [+0.318, +0.402] * | +0.351 [+0.299, +0.401] * |
| v16.4 reference | +0.526 [+0.499, +0.554] * | +0.898 [+0.865, +0.929] * | +0.498 [+0.441, +0.554] * | +0.381 [+0.309, +0.453] * | +0.584 [+0.538, +0.626] * | +0.588 [+0.533, +0.637] * |

### Emergence through composition

Integration gain over the conventional pipeline (utility): +0.3070; sum of single-mechanism contributions: +0.4914; synergy: -0.1844 — not superadditive: single removals account for at least the total gain.

* removing analogy: -0.0121 utility
* removing learned_primitives: -0.0065 utility
* removing mathematical_structure: -0.0097 utility
* removing meta_learning: +0.2962 utility
* removing replanning: +0.2189 utility
* removing representation_restructuring: +0.0047 utility

### Transfer (trained − untrained, same frozen protocol)

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

### Negative transfer

Mismatched curriculum (symbolic-rewriting → causal-circuit), trained − untrained: utility +0.289 [+0.238, +0.331] *, probes -8.57 [-9.51, -7.49] *, identification -0.294 [-0.375, -0.206] *.
Analogy transfers ledgered positive/negative: 5/12; strategy negative transfer recognised: 0.

### Continual learning

* v17 integrated: backward transfer -0.021 [-0.043, 0.001], forward transfer 0.242 [0.190, 0.294], forgetting 0.023 [0.005, 0.042], final average utility 0.514 [0.461, 0.567]
* conventional identify→plan pipeline: backward transfer 0.000 [0.000, 0.000], forward transfer 0.005 [-0.009, 0.020], forgetting 0.000 [0.000, 0.000], final average utility 0.219 [0.206, 0.232]

### Adversarial attacks

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
| memorisation-trap | v17 integrated | 0.850 (n=20) | — |
| memorisation-trap | conventional identify→plan pipeline | 1.000 (n=20) | — |
| memorisation-trap | v16.4 reference | 0.050 (n=20) | — |
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

### Calibration

* v17 integrated: measured; submissions 503; Brier 0.141; ECE 0.035
* minus-analogy: measured; submissions 467; Brier 0.129; ECE 0.044
* minus-causal: measured; submissions 927; Brier 0.058; ECE 0.063
* minus-learned-primitives: measured; submissions 506; Brier 0.147; ECE 0.034
* minus-meta-learning: measured; submissions 351; Brier 0.028; ECE 0.020
* minus-phi-lucas-manifold: measured; submissions 514; Brier 0.175; ECE 0.082
* minus-replanning: measured; submissions 593; Brier 0.041; ECE 0.026
* minus-representation: measured; submissions 513; Brier 0.142; ECE 0.043
* minus-world-model: unavailable (no predictive model); submissions 0; Brier Unavailable; ECE Unavailable
* conventional identify→plan pipeline: measured; submissions 355; Brier 0.033; ECE 0.020
* v16.4 reference: unavailable (no predictive model); submissions 0; Brier Unavailable; ECE Unavailable

### φ / Fibonacci experiments

Mean evaluations to locate the maximum of a strictly unimodal sequence (600 curves, n∈[20,300]):
* difference-bisection: 12.15 [11.99, 12.31]
* fibonacci: 10.29 [10.17, 10.41]
* ternary: 15.26 [15.01, 15.51]

Success by evaluation budget (Wilson rate):
* budget 10: difference-bisection 0.483, fibonacci 0.768, ternary 0.297
* budget 11: difference-bisection 0.632, fibonacci 0.923, ternary 0.383
* budget 12: difference-bisection 0.752, fibonacci 1.000, ternary 0.457
* budget 13: difference-bisection 0.905, fibonacci 1.000, ternary 0.543
* budget 14: difference-bisection 0.987, fibonacci 1.000, ternary 0.620
* budget 6: difference-bisection 0.125, fibonacci 0.160, ternary 0.110
* budget 7: difference-bisection 0.205, fibonacci 0.268, ternary 0.145
* budget 8: difference-bisection 0.263, fibonacci 0.422, ternary 0.182
* budget 9: difference-bisection 0.372, fibonacci 0.603, ternary 0.237

Iterative-deepening schedules on true task models:
* doubling: solved 20/20, mean expansions 26.0, mean excess length 0.45
* fibonacci: solved 20/20, mean expansions 36.6, mean excess length 0.35
* linear: solved 20/20, mean expansions 55.5, mean excess length 0.00

Anytime coverage (largest gap fraction; lower is better):
* golden-weyl: n=5: 0.236, n=8: 0.146, n=13: 0.090, n=21: 0.056, n=34: 0.035, n=55: 0.021
* uniform-random: n=5: 0.266, n=8: 0.293, n=13: 0.252, n=21: 0.151, n=34: 0.097, n=55: 0.083
* van-der-corput: n=5: 0.375, n=8: 0.188, n=13: 0.188, n=21: 0.094, n=34: 0.047, n=55: 0.047

### Self-improvement

* seed 0 (golden proposals): plan_samples: rolled-back (fibonacci-search, 4 sandbox evaluations); explore_fraction: rolled-back (fibonacci-search, 5 sandbox evaluations); analogy_mass_cap: rolled-back (fibonacci-search, 4 sandbox evaluations); strategy_prior_weight: rolled-back (fibonacci-search, 4 sandbox evaluations)
* seed 0 (grid proposals): plan_samples: rolled-back (uniform-grid, 5 sandbox evaluations); explore_fraction: rolled-back (uniform-grid, 5 sandbox evaluations); analogy_mass_cap: no-change (uniform-grid, 5 sandbox evaluations); strategy_prior_weight: rolled-back (uniform-grid, 5 sandbox evaluations)
* seed 1 (golden proposals): plan_samples: rolled-back (fibonacci-search, 4 sandbox evaluations); explore_fraction: rolled-back (fibonacci-search, 5 sandbox evaluations); analogy_mass_cap: rolled-back (fibonacci-search, 4 sandbox evaluations); strategy_prior_weight: rolled-back (fibonacci-search, 4 sandbox evaluations)
* seed 1 (grid proposals): plan_samples: rolled-back (uniform-grid, 5 sandbox evaluations); explore_fraction: no-change (uniform-grid, 5 sandbox evaluations); analogy_mass_cap: no-change (uniform-grid, 5 sandbox evaluations); strategy_prior_weight: no-change (uniform-grid, 5 sandbox evaluations)
* seed 2 (golden proposals): plan_samples: no-change (fibonacci-search, 4 sandbox evaluations); explore_fraction: rolled-back (fibonacci-search, 5 sandbox evaluations); analogy_mass_cap: rolled-back (fibonacci-search, 4 sandbox evaluations); strategy_prior_weight: rolled-back (fibonacci-search, 4 sandbox evaluations)
* seed 2 (grid proposals): plan_samples: rolled-back (uniform-grid, 5 sandbox evaluations); explore_fraction: no-change (uniform-grid, 5 sandbox evaluations); analogy_mass_cap: rolled-back (uniform-grid, 5 sandbox evaluations); strategy_prior_weight: no-change (uniform-grid, 5 sandbox evaluations)

### Representation restructuring

Adopted representations in integrated evaluation: {'causal-relevance': 30, 'hierarchical': 18, 'literal': 277}
* program-transformation-evaluation-2000-0 (program-transformation) → hierarchical: literal: found=True expanded=10 net=0.984, causal-relevance: found=True expanded=10 net=0.984, hierarchical: found=True expanded=4 net=0.9936
* program-transformation-evaluation-2000-2 (program-transformation) → causal-relevance: literal: found=True expanded=4 net=0.9936, causal-relevance: found=True expanded=2 net=0.9968, hierarchical: found=True expanded=2 net=0.9968
* graph-navigation-heldout-2000-0 (graph-navigation) → causal-relevance: literal: found=True expanded=28 net=0.9552, causal-relevance: found=True expanded=5 net=0.992, hierarchical: found=True expanded=5 net=0.992
* graph-navigation-heldout-2000-1 (graph-navigation) → hierarchical: literal: found=True expanded=14 net=0.9776, causal-relevance: found=True expanded=14 net=0.9776, hierarchical: found=True expanded=12 net=0.9808

### Discovered skills

Evaluation episodes using learned skills: 69 (successes 61, held-out families 16).
* seed 0: `(('add', 'r0', 1), ('copy', 'r0', 'r1'), ('add', 'r0', 1))` level skill, support 2, held-out utility 0.333
* seed 0: `(('add', 'r0', '*'), ('add', 'r0', '*'))` level skill, support 6, held-out utility 0.167
* seed 0: `(('add', 'r0', 1), ('add', 'r0', 1), ('copy', 'r0', 'r1'))` level skill, support 2, held-out utility 0.333
* seed 2: `(('add', 'r0', '*'), ('add', 'r0', '*'), ('add', 'r0', '*'))` level skill, support 2, held-out utility 0.062
* seed 2: `(('add', 'r0', '*'), ('add', 'r0', '*'))` level skill, support 5, held-out utility 0.094

Total programme wall clock: 2051 s.

<!-- /RESULTS -->

## Interpretation — verdicts on the pre-registered hypotheses

All numbers below are copied from the generated results above
(paired 95% bootstrap intervals; `*` = excludes zero).

| # | Verdict | Evidence |
|---|---|---|
| H1 v17 > v16.4 | **Supported** | success +0.898 [+0.865, +0.929]\*; held-out families +0.850 [+0.750, +0.933]\*. Caveat: v16.4 has no interventional or model-learning channel for hidden-mechanism tasks, so this comparison establishes a floor, not a strong competitor. |
| H2 integration > conventional pipeline | **Supported for efficiency, not for success** | utility +0.307 [+0.282, +0.333]\*; success −0.018 [−0.055, +0.022]; 5.59 vs 12.70 interactions per task; 1.52 vs 3.06 s per task. |
| H3 every mechanism contributes | **Mixed** | Contributors: world model +0.526\*, causal interventions +0.438\*, meta-learning +0.296\* utility (but −0.071\* success — cheaper strategies trade a little success for large cost savings), replanning +0.219\* utility / +0.345\* success, representation restructuring +0.005 [+0.000, +0.011] (marginal). **No net contribution:** analogy −0.012 [−0.032, +0.009] (and −0.040 [−0.084, −0.000]\* on the analogy slice: slightly *harmful* there), learned primitives −0.007 [−0.017, +0.003], φ/Lucas/manifold pooled −0.010 [−0.032, +0.013]. |
| H4 superadditive emergence | **Not supported** | integration gain +0.307 < sum of single-mechanism contributions +0.491 (synergy −0.184). Meta-learning and replanning are partly substitutable: removing either costs a lot, but their losses overlap. |
| H5 cross-domain transfer | **Supported for cost, not success** | held-out families +0.172 [+0.116, +0.227]\* utility, success −0.050 [−0.117, +0.000]; graph-navigation +0.295\*, planning-logistics +0.213\*, dose-response +0.007 (n.s.). |
| H6 misleading prior recognised | **Partly falsified** | mismatched curriculum: utility +0.289\* but identification accuracy −0.294 [−0.375, −0.206]\*; the strategy negative-transfer detector recorded **0** entries — the misleading prior was not recognised. Analogy ledger 5 positive / 12 negative; superficial twins still triggered an adoption in 10 of 20 episodes. |
| H7 no forgetting | **Supported, small forgetting** | forward transfer +0.242 [+0.190, +0.294]; forgetting 0.023 [0.005, 0.042] (small but non-zero); backward −0.021 [−0.043, 0.001]. |
| H8 Fibonacci search | **Supported (known theorem)** | mean evaluations 10.29 vs 12.15 (difference bisection) vs 15.26 (ternary); success at budget 11: 0.923 vs 0.632 vs 0.383. |
| H9 golden coverage / Fibonacci deepening | **Mixed** | golden Weyl has the smallest largest-gap at every n tested (n = 13: 0.090 vs 0.188 van der Corput vs 0.252 random). Fibonacci deepening is a trade-off (36.6 expansions, +0.35 excess length) between linear (55.5, optimal length) and doubling (26.0, +0.45) — no dominance, as expected. |
| H10 calibration | **Supported** | ECE 0.035, Brier 0.141. The pipeline's lower Brier (0.033) reflects acting only at near-certainty. A development build was under-confident (ECE 0.22) because exact enumeration ignored truncated posterior mass; fixed before the pre-registered run. |
| H11 adversarial resistance | **Mixed** | Better than the pipeline on out-of-grammar (1.00 vs 0.53) and confounded footprint (1.00 vs 0.87); worse on mechanism shift (0.80 vs 0.93), noisy observation (0.87 vs 0.93), distractor loops (0.87 vs 1.00), φ-bait (0.93 vs 1.00), superficial twin (0.90 vs 1.00) and memorisation trap (0.85 vs 1.00). Cost-efficient act-first strategies are more exposed to adversarial structure than exhaustive identification. Proxy reward: 1.00 vs 0.00 for v16.4 (immune because the score is never its objective); detection rate is low (0.07) because the agent rarely executes the proxy. |
| Self-improvement | **No accepted change** | all 24 proposals (6 runs × 4 parameters) were rolled back or left unchanged: no improvement established on development tasks under the paired-interval rule. Fibonacci proposals used 4–5 sandbox evaluations, the grid 5. |

### Post-hoc analysis (not pre-registered): φ where its theorem applies

Restricting the paired integrated-vs-minus-φ comparison to the response
families (computed from the same report rows):

| Family | n | Success integrated / minus-φ | Mean probes | Δ utility |
|---|---|---|---|---|
| parameter-optimisation (in-distribution) | 20 | 18 / 14 | 9.50 / 10.35 | +0.072 [+0.007, +0.140]\* |
| dose-response (held-out family) | 20 | 20 / 17 | 10.35 / 11.05 | +0.062 [+0.021, +0.105]\* |

The meta-learner chose Fibonacci search in 23 of 40 of these episodes and
carried it, by vocabulary-free structural class, into the held-out
dose-response family.  The pooled φ null above is dilution (response tasks
are a small share) plus a small negative on the analogy slice.  Because this
breakdown was chosen after seeing results, it must be pre-registered and
re-tested before it is treated as established.

### Post-hoc: learned skills

Evaluation episodes whose plan used a learned skill succeeded 61/69 (88.4%);
those that did not, 194/216 (89.8%).  Discovery and the evidence-gated
lifecycle function (about one promoted skill per library, most candidates
rejected for lack of held-out benefit), but there is no evidence that skills
improve outcomes on this distribution.

### What the evidence says about integration

The capability that emerges from integration here is *choosing how to think
under declared costs* (meta-learning over evidence policies on a calibrated
posterior) combined with *model-based recovery* (replanning and plan repair).
It matches the conventional pipeline's success at less than half its
interaction cost and compute.  Analogy, learned skills and representation
restructuring are implemented, inspectable, tested and ablatable, but do not
yet earn their keep on this distribution.  The traces point to one reason:
sequential expected-information-gain identification is cheap here (one
three-step probe identifies most of a task), leaving little for transfer to
save.  The next falsification test is a distribution where identification is
expensive — costlier probes, larger operator sets, partial observability.

### Limitations

* The benchmark is self-constructed.  Families share one mechanism grammar;
  they differ in mixture, topology, horizon, cost regime and vocabulary.
* Five seeds; adversarial and analogy slices have n = 15–20 per system.
* v16.4 is a floor on this task class.
* Compute: 1.52 s per task versus 0.013 s for v16.4.
* The wheel bundles `hyba_substrate` and `resonance_intelligence`
  (pre-existing import-time coupling).


## 1. Architecture

```
EuclidRuntime (composition root; governed Delegator; rights; evidence chain)
 ├─ cognition (v16.4 repository loop; unchanged composition)
 └─ adaptive  (v17)  compose_adaptive_intelligence() / solve_task()
     └─ IntegratedAgent ── long-term AgentKnowledge (sealed, persisted)
          └─ per episode: GeneralIntelligenceCore  ← orchestrator only
               ├─ MechanismWorldModel ──┐
               ├─ MechanismAbducer      │
               ├─ MechanismDeducer      │   shared EpisodeContext
               ├─ InformationGainDiscriminator  (posterior, budgets,
               ├─ EvidenceMetaController         candidate plans by
               ├─ ContextualStrategyLearner      posterior version,
               ├─ CausalHierarchicalPlanner      proxy audit, VOI)
               ├─ RepresentationSelector │
               ├─ ModelBasedComposer     │
               ├─ AdaptiveDecisionObjective
               ├─ DynamicObjectiveController
               ├─ GraphAnalogyEngine ────┘
               ├─ EpisodeConsolidator (→ LearningService when wired)
               └─ AccountingExecutor → governed executor → world
```

The core owns no specialist logic.  It drives typed interfaces
(`euclid/cognition/interfaces.py`); v17 adds six *optional* extension
protocols — `EvidencePolicy`, `PosteriorDiscriminator`,
`ObservingWorldModel`, `Restructurer`, `AnalogyRefresher`,
`EpisodeConsolidator` — detected by duck typing.  A specialist without them
gets the original single-step behaviour, which is why every v16.4
composition and test is unchanged.

## 2. The integrated loop (as executed)

Each arrow is a recorded, hash-linked transition in the episode's
`CognitiveState` and in the shared `EvidenceChain`.

| User-specified stage | Transition(s) | Mechanism |
|---|---|---|
| novel problem → representation / world model forms | `represent`, episode posterior created | `RepresentationSelector.select`; `MechanismPosterior` from learned kind/noise priors |
| relevant memory retrieved | `retrieve` | `StructuralMemory.retrieve` (structure + demonstrated transfer value; never vocabulary) |
| analogy finds structurally related experience | `analogy`, `analogy-refresh` | `GraphAnalogyEngine`: variable bijection + operator matching reproducing observed transitions; Bayes-factor × learned base-rate odds adoption |
| abduction generates competing explanations | `abduce` | mechanism hypotheses per unidentified operator, noise-regime and response-shape hypotheses; never collapsed by fiat |
| deduction derives consequences | `deduce` | per-hypothesis predicted outcomes |
| causal model identifies discriminating interventions | `evidence-decision`, `discriminate` | sequential expected-information-gain probe design (branching, conditioned on repeated operators) |
| counterfactual comparison | `counterfactual-plan` | each plan stage scored against the no-intervention baseline (predicted, never observed) |
| evidence updates confidence | `hypothesis-update` | exact Bayesian update under competing noise models; status is a summary of the posterior |
| hierarchical planner decomposes goal | `plan` | causal-dependency-ordered subgoals with per-stage programmes |
| meta-learner selects strategy | `strategy` (strategy-first) | `ContextualStrategyLearner`: per structural class, Thompson sampling while learning, posterior mean when frozen |
| search geometry / representation adapt | `restructure` | literal / causal-relevance quotient / hierarchical, trial-planned; adopted on measured net utility; ties to the simplest |
| skills and primitives compose candidates | `compose` | MAP + posterior-sample plans, plan repair, transported programmes, bound learned skills; model-free fallback |
| imagined rollouts | `imagine` | labelled imagined; `EvidenceItem` forbids observed standing |
| ranking by multi-objective evidence | `rank` | calibrated P(goal) + auxiliary features whose weights are earned by measured validity, capped |
| execution through governed boundaries | `execute` | `AccountingExecutor` → `WorldExecutor` or `DelegatorExecutor` |
| result compared with prediction | `compare` | `observe_result`: trajectory learning, calibration pair, prediction error |
| prediction error updates the world model | `compare`, `model-repair` | posterior update; localised exact-model collapse → selective rebuild (grammar expansion / change point) |
| strategy performance updates meta-learning | `learn`, `consolidate` | episode utility per class; negative-transfer detection |
| new primitives / skills | `consolidate` | `SkillLibrary` lifecycle (discover → … → promote / deprecate) |
| replanning | `replan` | posterior-driven re-planning and prefix-preserving plan repair |
| knowledge abstracted, transfer attempted and learned | `consolidate` | semantic priors, causal/procedural/episodic/strategy memory, analogy reliability, transfer ledger |

Terminal outcomes stay explicit (`solved` / `stalled` / `aborted` /
`unexecuted`); the harness checks every outcome against the world's own
ledger.

## 3. New mechanisms

* **Interactive task worlds** (`euclid/cognition/worlds/`): exact mechanism
  grammar (`noop/add/set/copy/swap/guard`, plus out-of-grammar `pair`);
  public `TaskSpec` versus hidden `HiddenTruth`; budgeted probe/submit
  executor that fails closed; observation noise, non-stationarity, proxy
  score, φ-bait observable; seeded families with disjoint partitions;
  structural isomorphs and structurally disjoint surface twins.
* **Bayesian mechanism world model** (`integrated/world_model.py`): posterior
  per operator under three competing noise models compared by marginal
  likelihood; predictive distributions; unbiased P(goal | programme) by exact
  enumeration when supports are complete, otherwise Monte Carlo; surprise;
  breakdown detection; selective rebuild; transfer priors as explicit mixture
  priors with Bayes-factor evidence.
* **Sequential EIG probe design** (`integrated/context.py`).
* **Evidence policy** (`integrated/control.py`): identification, myopic
  value-of-perfect-information against declared costs, act-first
  break-even (P·V ≥ c_submit); success value V is the declared full budget.
* **Contextual strategy meta-learning** with a global prior, frozen mode and
  a negative-transfer ledger.
* **Structural analogy** with surface overlap reported but never used.
* **Evidence-gated primitive discovery and skill hierarchy**
  (`integrated/skills.py`) with semantic-digest persistence.
* **Adaptive multi-objective decisions**, **dynamic objectives with proxy
  audit**, **episode consolidation**, **policy self-improvement**
  (`integrated/self_improvement.py`).
* **Research programme** (`euclid/cognition/research/`) and the
  `euclid-engine` wheel with build-and-verify (`packaging/euclid-engine/`).

## 4. v16.4 mechanisms deepened (none removed)

| v16.4 element | v17 change |
|---|---|
| `GeneralIntelligenceCore.solve` | evidence loop, strategy-first option, posterior hook, analogy refresh, restructuring, full control vocabulary, honest replanning ablation, consolidation |
| hypothesis update (+0.25 / −0.5 constants) | retained for legacy specialists; likelihood-based when the discriminator provides `posterior_update` |
| `AblationConfig` | adds `learned_primitives` |
| `CognitiveState` | adds expected/actual outcomes, causal assumptions, uncertainty trace, strategy history, selected skills (serialised, sealed) |
| `CandidateAction`, `Intervention` | executable `payload` (legacy serialisation unchanged when empty) |
| `AnalogyStatus` | adds `ABANDONED` |
| `RepresentationController`, `ObjectiveController`, `NoveltyArchive`, `phi_schedule` | reused and extended by subclassing/composition |
| `EuclidRuntime` | `compose_adaptive_intelligence`, `solve_task`; v16 repository cognition untouched |

## 5. Public API changes (additive)

`euclid.cognition.worlds`, `euclid.cognition.integrated`,
`euclid.cognition.research` (new); `AblationConfig(learned_primitives=…)`;
`GeneralIntelligenceCore(strategy_first=False, max_probes_per_cycle=1)`;
`CandidateAction.payload`; `Intervention.payload`;
`AnalogyStatus.ABANDONED`; new `CognitiveState` fields;
`EuclidRuntime.compose_adaptive_intelligence`, `EuclidRuntime.solve_task`,
`EuclidRuntime.ADAPTIVE_COMPONENTS`; console script `euclid-v17-research`.
No public name was removed or renamed.

## 6. Compatibility

Defaults reproduce v16.4 behaviour exactly; all pre-existing cognition tests
pass unchanged.  Old serialised `CognitiveState` payloads still verify and load.
Packaging: the `euclid` package already imports `hyba_substrate` and
`resonance_intelligence` at import time; the wheel bundles them (declared
debt).  The root distribution's package list now includes the v17
subpackages.

## 7. Scientific hypotheses and falsifiers (declared before evaluation)

| # | Hypothesis | Falsified if |
|---|---|---|
| H1 | The integrated system succeeds more than v16.4 on held-out tasks | paired success interval includes 0 |
| H2 | Integration beats a conventional identify-then-plan pipeline built from the same world model | paired utility interval ≤ 0 |
| H3 | Each integration mechanism contributes | its ablation's paired interval includes 0 (reported per mechanism; a null is a finding, not a failure) |
| H4 | Capability is superadditive (emergence through composition) | integration gain ≤ sum of single-mechanism contributions |
| H5 | Learning transfers to structurally different held-out families | trained − untrained interval ≤ 0 |
| H6 | Mis-matched prior knowledge is recognised rather than silently harmful | negative transfer without detection |
| H7 | Continual learning does not forget | forgetting interval excludes 0 above |
| H8 | Fibonacci search beats neutral unimodal search under budget | evaluation counts / budgeted success not better |
| H9 | φ Weyl coverage and Fibonacci deepening help | no measured advantage (expected null for deepening) |
| H10 | Predictions are calibrated | Brier/ECE no better than the v16.4 status (unavailable) and poor in absolute terms |
| H11 | Attacks are detected / resisted | attack success not above the baselines' |

## 8. Benchmark construction

Seven families with distinct mechanism mixtures, topologies, horizons, state
sizes and cost regimes: in-distribution `program-transformation`,
`symbolic-rewriting`, `causal-circuit`, `parameter-optimisation`;
held-out `graph-navigation`, `planning-logistics`, `dose-response` (never in
train/development).  Operator and variable names are drawn per task from
vocabulary pools and shuffled, so names carry no mechanism information — a
deliberate design choice that forces structural reasoning.  Every assignment
task is verified solvable by exact BFS; optimal length is recorded.
Response curves are strictly unimodal (or declared bimodal); their probe
budget is fixed from size alone (`bit_length(n) + 4`) before any method was
run.  Adversarial slices: proxy reward, confounded footprint, noisy
observation, mechanism shift, out-of-grammar mechanism, distractor loops,
φ-bait.  Analogy slices: deep isomorph (other vocabulary), near isomorph
(one mechanism changed), superficial twin (same names, start and goal; no
relational match under any variable bijection), memorisation trap (same, and
the remembered programme provably fails).

## 9. Protocol

Train online on the train partition → freeze knowledge → evaluate every
held-out slice from the same frozen knowledge, verifying the knowledge digest
(payload, memory, skills, novelty) is unchanged → development partition only
for self-improvement → five seeds (unit of replication), paired tasks and
world seeds across systems; 95% Student-t intervals across seeds and paired
bootstrap intervals over (seed, task).  The pre-registered suites (base 2000)
were not generated or inspected during development; development used bases
1000–1700 and 5000+.  One aborted launch of the pre-registered run (stopped
when a relevance defect that disadvantaged the baseline pipeline was found)
was discarded unread.

## 10. Non-claims

No AGI, consciousness, quantum-advantage, production or mining authority, or
external superiority is claimed.  All results are internal, on the declared
task distribution, and bounded by the stated intervals.  The Fibonacci-search
advantage is a known theorem operationalised, not a discovery.
