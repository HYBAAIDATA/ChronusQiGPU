# PYTHAGORAS v12.2 — Merge Closure Matrix

This continues the delivered v12.2 implementation. φ, EUCLID, Lucas/Pisot,
`PHI_WEIGHTS`, and their formulas are unchanged.

| Item | Status | Reproduction evidence |
|---|---|---|
| 1. Ruff E9/F | Done | `ruff check --select E9,F pythagoras` → `All checks passed!` (`RUFF_E9_F_RAW.txt`) |
| 2. Annealing EUCLID gate | Done | `python -m unittest pythagoras.tests.test_v12_2_gap_closures.TestSearchGapClosures.test_annealing_respects_euclid_gate` → `OK`; result reports `initial_euclid_intelligence` and `best_euclid_intelligence` |
| 3. Version 12.2.0 | Done | `python -c "import pythagoras; print(pythagoras.__version__)"` → `12.2.0`; runner banner also prints v12.2 |
| 4. v12.1 preservation | Done | Separate `pythagoras-engine-v12.1-preserved-20261001.zip`, SHA-256 in `V12_1_BASELINE.sha256`, and `git diff v12.1..v12.2 --stat` in `V12_1_TO_V12_2_DIFFSTAT.txt` |
| 5. Unused `pop_size` | Done | Decision: remove from effective state and collective consensus; constructor argument retained only for compatibility. `python -m unittest ...test_pop_size_is_not_reported_as_effective_search_state` → `OK` |
| 6. CGP description | Done | README and engine docstrings now say “CGP-inspired geometry”; `n_cols` is ranked operators evaluated per generation and `levels_back` is maximum composite-recipe length; no DAG population claim |
| 7. φ validation | Done | `python -m pythagoras.experiments.phi_validation --seeds 3 --generations 4 --bootstrap 2000 --out-json pythagoras/experiments/phi_validation_v12_2.json --out-md pythagoras/experiments/PHI_VALIDATION_v12_2.md` |
| 8. Tononi/Penrose audit | Done | Removed unused `calculate_integrated_information`; `core/tononi_penrose.py` now documents and exposes only measured `graph_integration` |
| 9. Corpus-dependent A/B/C | Done | Six raw 10-seed runs committed under `experiments/results_v12_2/`; `experiments/RESULTS_v12_2.md` reports 3/4/12 generations, mean and 95% CI, with paired B−C primary |

## Required interpretation

The held-out experiment does **not** validate φ as an independent universal
quality measure. Overall Δφ is negatively associated with maintainability-index
change, cyclomatic complexity has no monotonic association, and mypy errors do
not vary. ADD:AnnAssign variants show a positive complexity association, but
the AST-node control is also strong and maintainability is inconclusive.
See `experiments/PHI_VALIDATION_v12_2.md`.

The A/B/C matrix is corpus- and budget-dependent. On stdlib4, B beats
budget-matched C in total Δφ at 3, 4, and 12 generations. On the bundled
benchmarks, C beats B at 3 generations and ties it at 4 and 12. These are
internal φ-objective results, not external quality validation.

## Raw acceptance outputs

Command:

```bash
ruff check --select E9,F pythagoras
```

Output:

```text
All checks passed!
```

Command:

```bash
python -m unittest discover -s pythagoras/tests -t .
```

Output:

```text
.......................................................
----------------------------------------------------------------------
Ran 55 tests in 8.299s

OK
```

Repository-style command:

```bash
PYTHONPATH=. python -m pytest -q repo_tests pythagoras/tests
```

Output:

```text
............................................................             [100%]
60 passed in 8.62s
```
