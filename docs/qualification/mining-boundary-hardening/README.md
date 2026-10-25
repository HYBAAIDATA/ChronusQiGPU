# Mining boundary hardening — first closure pass

## Disposition

**Focused fixes qualified locally; whole mining release remains NOT QUALIFIED.**
Source base: `b131edc408a37ff7c03534d694bfcdaf0c827abb` in
HYB-APHIDATA/HYBAEnterprise. This work does not merge, deploy, enable live pool
submission, change repository visibility, publish treasury details, or certify
performance. Mining remains internal treasury infrastructure, not the product.

## Reproduced and fixed

### Planner identity contradicted advisory evidence

Both `IntelligentPoolCoordinator._baseline_plan` and `_build_plan` selected M32
whenever `solve_first is not None`, including empty/unavailable advice. This
replaced the configured nonce-order identity merely because evidence existed.
The canonical PYTHIA subclass subsequently binds Hendrix again; this finding is
therefore **contradictory upstream provenance**, not proof that every canonical
production dispatch was using M32.

Both builders now retain `self._nonce_order`. Lane-order advice, solve-first
receipts, lease bounds, identity, explicit compatibility configurations and
fallback provenance remain available. No quantum/search mathematics, coverage,
SHA256d, target comparison or pool semantics were changed.

### Non-finite transport bounds

`_positive_env` previously accepted NaN and positive infinity because `value <= 0`
is false for NaN and does not exclude infinity. Explicit timeout arguments had
similar gaps; queue-size arguments admitted booleans/noninteger bounds.

All four V1 timeouts (connect/request/write/enqueue) now require finite positive
numeric values. Queue capacity must be an actual positive integer, not bool or
float. Environment and explicit values are resolved before superclass status
publication. Existing defaults/Lucas queue scaling and explicit valid operator
settings remain unchanged. Per-request deadline overrides are also checked before
allocating correlation state or sending bytes. Cancelled requests release their
pending correlation futures without retrying a share or fabricating an outcome.
No retry, outcome or protocol policy was altered.

## Connection to the shared research

The useful TrustFi-SecNet connection at this stage is bounded, provenance-aware
operational evidence: reliable latency/failure observation must come before
adaptive trust/routing decisions. These fixes protect the existing planning and
transport seams rather than inserting an unvalidated learned model into hashing
or proof validation.

The separate AL HARAS shadow trust work is draft PR #12. It is **not included,
merged or activated** by this branch. Before connecting it to a production mining
composition root, review a real authenticated tenant-scoped collector and its
external deadlines, stale-snapshot behavior, audit durability, privacy and shadow
false-positive/latency measurements. A learned score may supply advisory evidence;
it cannot replace subscription/AL HARAS/M3 authorization, change SHA256d/targets,
expand leases, redefine freshness, fabricate pool truth or silently demote Hendrix.

Research: Yadav & Reddy, TrustFi-SecNet, ETASR 16(2), 34197–34204 (2026),
https://doi.org/10.48084/etasr.17614 (CC-BY 4.0). No trained-model reproduction,
paper accuracy/energy outcome, post-quantum cipher or quantum speedup is claimed.
Existing reviewed cryptography is untouched.

## Validation evidence

- Initial 62-case new suite: **35 failed / 27 passed before fixes**, then 62 passed.
  Nineteen further cases cover environment paths, per-request overrides and
  cancellation cleanup, including refusal before status publication: **81 passed**.
- New suite + existing execution-router suite: **111 passed / 4 skipped** normally,
  and the same 111 passed / 4 skipped under `python -O`. Counts are not additive
  across interpreter modes. Four OpenCL-only skips do not disqualify native
  mathematical/software execution and are not evidence of physical execution.
- Resident Hendrix + protocol chaos: **39 passed**.
- Production transport + execution receipts: **11 passed**.
- These disjoint final selected suites total **161 passing tests / 4 skips**.
- Black formatting checks for transport and the new test file; full flake8 for that test;
  fatal-error flake8 (`E9,F63,F7,F82`) and py_compile for the changed Python files.
  The coordinator was not blanket-reformatted; existing sources are not declared fully lint-clean.
- Checkout-subset Git diff/patch checks are recorded separately. They are not
  evidence of a full authenticated Git clone or full repository regression.

### Local environment and limits

Python 3.13 selective workspace, not a full clean-installed enterprise checkout.
Current mining directory (77 files), selected tests and platform source were
checked against GitHub blob IDs at the pinned base. Supporting sources were
restored from retained workspaces; not every transitive dependency is verified
against this head. Fifty of 55 top-level Turing package files verified; five
fresh-download attempts failed, so no complete current Turing source attestation
is made. Local installation of the declared `hyba-turing-vqc` package (without
fetching private dependencies) and SymPy resolved the initial math-import errors.
No mathematical implementation or test was stubbed to bypass those imports.

Runs use `--noconftest`; repository-wide conftest/plugin and clean-installed
packaging behavior remain unqualified. A larger resident run was interrupted
while diagnosing missing dependencies; it is not a pass. The successful 39-test
rerun is retained separately.

The attempted canonical workflow run stopped at default structural-store
bootstrap: `python_backend.phi_grover_v4` was missing in this selective workspace.
The repository still contains that dependency; this is **not established as a
repository import defect**. Backend/corpus restoration and exact-head workflow
rerun remain required. No gate was disabled, corpus invented or training receipt
fabricated. The earlier research/PULVINI test likewise cannot collect without
its backend dependencies. Failure evidence is retained, not hidden.

The final formatted-code combined run (focused + transport/receipts) also passes
122 tests with 4 skips normally and under optimized Python; the separate
39 resident/protocol tests bring the unique selected total to 154.

## Reproduction

Use the repository's normal dependency installation in a full checkout first.
For the selective local qualification the commands were:

```sh
export PYTHONPATH=chronus/mla1517_platform/python
python -m pytest --noconftest -q tests/test_execution_router.py tests/test_mining_boundary_hardening.py
python -O -m pytest --noconftest -q tests/test_execution_router.py tests/test_mining_boundary_hardening.py
python -m pytest --noconftest -q tests/test_resident_hendrix.py tests/test_mining_transport_chaos.py
python -m pytest --noconftest -q chronus/mla1517_platform/python/test_production_transport.py chronus/mla1517_platform/python/test_execution_receipt.py
python -m pytest --noconftest -q chronus/mla1517_platform/python/test_canonical_mining_workflow_e2e.py --maxfail=1
python -m black --check chronus/mla1517/mining/production_transport.py tests/test_mining_boundary_hardening.py
python -m flake8 --max-line-length=100 tests/test_mining_boundary_hardening.py
python -m flake8 --select=E9,F63,F7,F82 chronus/mla1517/mining/coordinator.py chronus/mla1517/mining/production_transport.py tests/test_mining_boundary_hardening.py
python -m py_compile chronus/mla1517/mining/coordinator.py chronus/mla1517/mining/production_transport.py tests/test_mining_boundary_hardening.py
```

## Remaining release gates — do not replace evidence with flags

| Gate | Status / required closure |
|---|---|
| Planner/advice authority | Focused regression passed; canonical doctrine and full installed-suite CI still required. |
| Exact itinerary/lease execution | Selected router/resident tests passed; complete canonical workflow remains blocked locally. |
| Host SHA256d/target/freshness | Existing proof authority unchanged; final-head end-to-end proof/stale-cancellation run required. |
| Single writer/literal outcomes | Transport and protocol chaos selected tests passed; no live-pool verdict obtained here. |
| M3 AL HARAS + THESEUS | Existing fail-closed path preserved; actual composed authorization/custody/restart tests required. |
| Salamander recovery | No change; fault injection, durable restore, bounded actuation and retain/rollback qualification required. |
| Intelligence/corpus/learning | Restore verified backend/corpus and rerun canonical workflow; never waive structural training. |
| Trust enrichment | Separate draft #12; authenticated collector and shadow calibration required before activation. |
| Runtime performance | Queue bounds validated; no fleet/load/soak, energy, hashrate or profitability result established. |
| Release/rollback | Exact-head CI, full package install, composed service journey, backup/restore and rollback evidence required. |

The governing source contracts reviewed were `docs/PYTHIA_MINING_AUTHORITY.md`,
`docs/PYTHIA_CANONICAL_MINING_SEARCH.md` and `docs/PRODUCTION_EXECUTION_WIRING.md`.
No physical GPU/QPU procurement requirement is introduced. Real hardware claims
and actual external pool acceptance remain separate evidence gates.
