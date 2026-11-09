# Tree access and field acceptance — blocked

## Step 0.5 at branch commit 4854c84a070788c2a455184a6340b2d23d164a40

GitHub MCP successfully listed `/`, `src/hyba`, `src/hyba/unification`, `src/hyba/unification/testing`, `src/chronus/tensor`, `src/chronus/security/al_haras`, `src/chronus/storage`, `tests`, `tests/unification` and `tests/vectors`. It returned full file contents for `src/hyba/unification/field.py`, the cyclotomic engine `src/chronus/security/al_haras/engine.py`, `src/chronus/tensor/network.py`, `src/chronus/tensor/types.py`, `src/chronus/tensor/adaptive_contraction.py`, `src/chronus/tensor/enhanced_representation.py`, `tests/test_falsifiable_tensor.py`, and `tests/test_property_invariants.py` (some read before this resume, at main; their branch tree blobs match). `tests/vectors` contains `regtest_block0.json`, not a unification fixture.

**A complete recursive tree and complete working checkout were not obtained.** The available MCP exposes individual directory listings/files, not a recursive checkout tool. A local search found no Git checkout; unauthenticated `git ls-remote` failed and `gh auth status` reported no login. Actual command output: `artifacts/unification/tree-access-output.txt`. Existing modules will not be re-exported to circumvent the full-tree requirement. This finding is not evidence that the repository itself is unreachable by the GitHub MCP.

## Step 1 — field full-tree gate

Blocked: the exact full-tree test and coverage command cannot run without a complete checkout. Previous field test and coverage artifacts are provisional partial-export results, not full-tree acceptance. No `field_coverage.json` or hash is fabricated. The requested generator formula is separately tested in `artifacts/unification/amendment-generator-check.txt` and the conflict recorded in `work_orders/unification_spec_amendment.md`. The seven requested classes using the new doubles have not been run on the full tree. No claim that the field is complete.

Next commands in an authenticated complete checkout at the PR head:

```sh
PYTHONPATH=src python -m pytest tests/unification -v --cov=hyba.unification.field --cov-branch --cov-fail-under=90 --cov-report=json:artifacts/unification/field_coverage.json --cov-report=term-missing
sha256sum artifacts/unification/field_coverage.json
```

The double-based field/network and field/network/domain tests still need to be authored and added before those commands can establish the requested seven classes. Real network and domain integration remain additional gates. Do not use CI as substitute in this run.
