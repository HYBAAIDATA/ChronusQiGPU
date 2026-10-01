# PYTHAGORAS v12.2 A/B/C results

Reproduce each row with:

```bash
python -m pythagoras.experiments.replicate_march_2026 --corpus <stdlib4|benchmarks> --seeds 10 --generations <3|4|12> --out pythagoras/experiments/results_v12_2/<corpus>_<generations>g.json
```

Values are mean [95% CI] across 10 paired seeds. B−C total Δφ is the primary comparison.

| Corpus | Gens | A Δφ | B Δφ | C Δφ | A evals | B evals | C evals | B−C Δφ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| stdlib4 | 3 | 0.049009 [0.048406, 0.049613] | 0.099165 [0.099165, 0.099165] | 0.078372 [0.077933, 0.078810] | 27.000000 [27.000000, 27.000000] | 40.000000 [40.000000, 40.000000] | 43.000000 [43.000000, 43.000000] | 0.020793 [0.020355, 0.021232] |
| stdlib4 | 4 | 0.065182 [0.064664, 0.065699] | 0.102730 [0.101350, 0.104110] | 0.091294 [0.089092, 0.093496] | 36.000000 [36.000000, 36.000000] | 53.900000 [51.481317, 56.318683] | 52.500000 [50.772369, 54.227631] | 0.011436 [0.010601, 0.012270] |
| stdlib4 | 12 | 0.100227 [0.100227, 0.100227] | 0.103908 [0.103885, 0.103931] | 0.100227 [0.100227, 0.100227] | 83.000000 [83.000000, 83.000000] | 122.200000 [115.516990, 128.883010] | 113.900000 [110.324259, 117.475741] | 0.003681 [0.003658, 0.003704] |
| benchmarks | 3 | 0.167234 [0.167234, 0.167234] | 0.167234 [0.167234, 0.167234] | 0.202953 [0.202953, 0.202953] | 10.000000 [10.000000, 10.000000] | 18.000000 [18.000000, 18.000000] | 15.000000 [15.000000, 15.000000] | -0.035719 [-0.035719, -0.035719] |
| benchmarks | 4 | 0.184996 [0.184996, 0.184996] | 0.202953 [0.202953, 0.202953] | 0.202953 [0.202953, 0.202953] | 12.000000 [12.000000, 12.000000] | 24.000000 [24.000000, 24.000000] | 17.000000 [17.000000, 17.000000] | 0.000000 [0.000000, 0.000000] |
| benchmarks | 12 | 0.202953 [0.202953, 0.202953] | 0.202953 [0.202953, 0.202953] | 0.202953 [0.202953, 0.202953] | 21.000000 [21.000000, 21.000000] | 19.000000 [19.000000, 19.000000] | 21.000000 [21.000000, 21.000000] | 0.000000 [0.000000, 0.000000] |

## Reading

- Results are corpus- and budget-dependent; no single condition dominates every setting.
- Treat B versus budget-matched C—not B versus an unmatched A—as the primary adaptation comparison.
- Exact raw JSON and command summaries for all six runs are committed under `experiments/results_v12_2/`.
- These runs measure the internal φ objective. Independent quality evidence is reported separately by `python -m pythagoras.experiments.phi_validation --seeds 3 --generations 4 --bootstrap 2000`.
