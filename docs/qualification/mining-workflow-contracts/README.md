# Mining workflow selected qualification

Read `../../MINING_WORKFLOW_CONTRACTS.md` for the sixteen contracts and original
M1–M16 note reconciliation. New tests invoke the named support arsenal through
PYTHIA rather than merely checking for source strings.

## Actual results

**235 selected cases: 231 passed, 4 hardware-specific OpenCL skips, zero failures
or errors**, in normal and optimized Python. The interpreter modes are not
added together as though they were distinct tests. JUnit reports are retained.

Groups: canonical guard/execution/resident/chaos = 90 pass + 4 skip;
Salamander modes/AL HARAS/replay/recovery = 79 pass;
protocol/receipt/independently verifying loopback = 49 pass;
canonical scripted accept/reject/shadow = 3 pass;
new named quantum support = 10 pass.

## Reproduction

From a complete repository with its actual dependencies installed:

```sh
PYTHONPATH=chronus/mla1517_platform/python python -m pytest --noconftest -q \
  tests/test_p0_canonical_execution_boundary.py tests/test_execution_router.py \
  tests/test_resident_hendrix.py tests/test_mining_transport_chaos.py \
  tests/test_salamander_autonomic.py tests/test_salamander_mining_mode_acceptance.py \
  tests/test_mining_recovery_dispatch_boundary.py tests/test_salamander_authority_replay.py \
  tests/test_mining_quantum_support_contracts.py \
  chronus/mla1517_platform/python/test_stratum_adapter.py \
  chronus/mla1517_platform/python/test_stratum_session.py \
  chronus/mla1517_platform/python/test_stratum_state.py \
  chronus/mla1517_platform/python/test_stratum_events.py \
  chronus/mla1517_platform/python/test_production_transport.py \
  chronus/mla1517_platform/python/test_execution_receipt.py \
  chronus/mla1517_platform/python/test_loopback_pool_verdict.py \
  chronus/mla1517_platform/python/test_canonical_mining_workflow_e2e.py \
  --junitxml=mining-workflow.xml
# Repeat with python -O -m pytest. No suppression or continue-on-error.
python -m flake8 tests/test_mining_quantum_support_contracts.py
```

## Scope and restoration

Reviewed base b131edc408a37ff7c03534d694bfcdaf0c827abb, plus proposed PR #14
planner/transport changes and PR #17 guard/router changes. This is selected
qualification in a restored workspace using --noconftest, not a clean-install,
complete-repository or exact-final-head CI attestation. Supporting dependencies
are not all re-attested to the source base. The combined evidence intentionally
states that scope rather than presenting it as the state of main.

Actual repository dependencies restored byte-for-byte from that base:

- python_backend/phi_grover_v4.py (Git blob 20ab8b52a1d9bbddd70438f44dd55fdbeed17fa3)
- artifacts/pythia_training/real_nonces_200.csv (cc3962018183be038866eb20e5849233264eca70)
- artifacts/pythia_training/real_nonces_200.manifest.json (b1c14626b9d4132de389413308c0c254516de10c)
- scripts/provision_m3_tenant.py (7fc84b5e44f3e7d8cea76f8d4554bd655ccc9b9a)

Initial dependency failures were local restoration gaps, not fixed with stubs,
empty packages, disabled custody or bypassed proof checks. Restored existing
files are not proposed as new repository changes. The provisioning helper was
used by the existing isolated test fixture, not to configure a real tenant.

## Limits

The quantum arsenal probe observed 21 available module surfaces and one
unavailable surface (quantum2026), because quantum_compute_substrate is absent
from this selective workspace though present in the repository. Its affected
aliases are explicitly not qualified here. Inventory reachability is not execution.
The ten support tests validate named calls, not every alias or mining speedup.

Scripted canonical tests include deliberately easy targets. The separate verifying
loopback pool reconstructs and hashes wire submissions and retains local outcome
records. Neither supplies evidence of an external live pool accepting a share.
No physical accelerator/fleet/throughput evidence, blanket Intelligence modality
qualification, or complete recovery/soak/rollback certification is claimed.
Optimized pytest's standard assertion-rewriting warning is retained. Retained text
logs normalize trailing whitespace only; JUnit result files are unmodified.
CI check-run access was previously permission-blocked and remains unverified.
No merge, deployment, publication or live submission was performed.
