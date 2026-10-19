# TURING publication workspace

This directory is a draft workspace, not a submitted paper or a claim of measured
advantage. The reusable implementation stays in the canonical Python package;
experiments/results are maintained separately. `main.tex` has the manuscript
structure; the implementation/limitations section states this change's scope.

Before submission: define the specific research contribution and independent
baselines, run and archive the experiments on a frozen commit, regenerate tables
and any future figures from the archived outputs, audit every empirical claim,
complete author/venue/license review and cite actual software/data releases.
Do not fabricate results, dates, tags or a DOI to fill a template.

Generate table TeX with `../experiments/analyze_results.py --output paper/tables`.
The draft does not automatically include an absent or unreviewed generated table.
