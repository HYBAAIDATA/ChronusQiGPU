# ARC-AGI-1 public dataset

Vendored official ARC-AGI-1 public task data for EUCLID benchmarking.

- Upstream: https://github.com/fchollet/ARC-AGI
- Pinned upstream commit: `399030444e0ab0cc8b4e199870fb20b863846f34`
- `data/training/`: all 400 public training tasks.
- `data/evaluation/`: all 400 public evaluation tasks.
- Task JSON files are preserved byte-for-byte; `dataset_manifest.json` records SHA-256 checksums.
- `LICENSE` and `UPSTREAM_README.md` are copied unchanged from that upstream revision.

Private and semi-private competition datasets are not distributed by the public repository and are not included. This is ARC-AGI-1, not ARC-AGI-2 or ARC-AGI-3.

## Evaluation discipline

Develop on training tasks only. Freeze solver revision, resource budget and attempt policy before public evaluation. Expected test outputs must remain in the scorer, not the solver input. Exact dimensions and every cell must match; a task is solved only if all its test inputs are solved. The original upstream protocol permits three trials per test input; report any different protocol explicitly. Public evaluation availability does not guarantee absence of prior exposure.

Dataset files were structurally validated and checksummed. The previous standalone-helper experiment has been withdrawn and its baseline directory removed. It did not administer ARC to instantiated EUCLID and is not a valid EUCLID intelligence baseline. No canonical-runtime ARC score is established. See `ADMINISTRATION_STATUS.md` for the source trace, cleanup provenance and exact execution blockers.

## Verify integrity

From the repository root:

```sh
python euclid/benchmarks/arc_agi_1/verify_dataset.py
```

The verifier validates counts, unique task IDs, task/grid schemas and all manifest checksums without printing puzzle contents.
