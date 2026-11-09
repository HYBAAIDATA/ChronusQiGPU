# Network, invariants and domains — staged findings

## Network (step 2)

Blocked for acceptance: the complete checkout is unavailable as documented in `work_orders/unification_tree_and_field_blocked.md`. Real field, existing tensor code, project stubs and registry integration cannot be run on a complete tree. The requested over-cap instructions conflict: one says log and reject; another says truncate and log. No SVD, error bound or truncation is asserted.

A *local uncommitted* bounded exact MPS-only prototype was tested in a separate workspace using Python Fraction and a local stand-in registry, not the repository field or the committed test doubles. `artifacts/unification/network-tests-provisional.txt` records six passing tests and a 98% isolated provisional branch-coverage result for that uncommitted file, not a full-tree measurement and not seven-class acceptance. The prototype source SHA-256 was `86ba1db9abe83a7157ea570b7c4cb048acc0a0264b31f34c4b97f772dd28852a`. It rejects and records an over-cap bond rather than truncating. PEPS, MERA, custom, SVD, ledger completeness, real integration and domain E2E are missing. **The network module is not committed** under the seven-class gate. The test command, run in the isolated workspace, was `PYTHONPATH=src python -m pytest -v tests/unification/test_network_isolated.py --cov=hyba.unification.network --cov-branch --cov-report=term-missing --cov-report=json:artifacts/unification/network_coverage_provisional.json`; its source and test inputs are not committed and the log is not independently reproducible from this branch.

## Invariants (step 3)

Blocked: the specified enumeration, null-space/syzygy algorithm and five-invariant test were not implemented or run; no invariant count is claimed. `scripts/unification/threeform_orbit_probe.py` is an independent exact-rational diagnostic, **not** that algorithm. Command: `python scripts/unification/threeform_orbit_probe.py`; see `artifacts/unification/threeform-orbit-probe.txt`. It samples five three-forms, computes the rank of the 20×15 infinitesimal so(6) action matrix and records rank 15 / local orbit codimension 5 for these samples; the zero tensor has rank 0. This is a local dimension observation, not a proof of functional independence, complete generators, or a match of the requested algorithm. The paper reports five invariants for its specified case: https://arxiv.org/abs/2512.23750. `python -m pytest tests/unification/test_orbit_probe.py -v` tests the independent probe, not the unimplemented registry. No full-tree coverage is claimed.

## Domains (step 4)

Blocked: the real network, invariant registry and full checkout are unavailable. No storage compression result, adversarial detection, cohomology inference, protein structure or diagnosis was produced. No shared-network identity, domain isolation or real E2E test was run. Do not treat a test double as a security or clinical implementation.
