# Mining recovery dispatch qualification

## Outcome

Two reproduced dispatch defects are repaired: completed proposals could execute
again, and an acknowledgement exception could subsequently become VERIFIED on a
healthy observation. Dispatch now claims an active, owned proposal once, serializes
concurrent dispatch, rejects reentrant attempts, validates the complete command
list before any action, and retains acknowledgement exceptions as FAILED evidence.
Observations during unfinished dispatch cannot prematurely verify that action.

This is a bounded software repair, not a production release or hardware/pool claim.
Continuation of draft PR #153; no merge, deployment or live actuation performed.

## Provenance

- Mining source/testing baseline: `668ade9f2a8297d5f27ac10e016c128d847c71b9`.
- Repair committed as `6bf95069424d6234896d3f9d3fa46f300263a5d0`.
- Concurrent custody continuation `46ae67c7c84d97f470e8ff91d061e8a487f7f6c5`
  was present on the shared review branch when the repair was pushed and was
  preserved. Its changed files were not in this local test closure; the 135-test
  rerun is NOT a new qualification of that concurrent custody implementation.
  The final combined branch still needs a clean-checkout integration run.
- User's acceptance suite retrieved unchanged from
  `f58ccc7c4f1d406f1cc1c190faace72d1c6b57cd`;
  Git blob `90316ee121da0299de9b554e924467d3a23f28f7`.
- That suite was added AFTER pinned base `cd80d037`; the earlier file-not-found
  result at the base is reconciled, not evidence the new commit is absent.
- Local environment is a pinned MCP-retrieved source closure, not a Git checkout.
  Source dependencies were retrieved rather than replaced with import stubs.
- New tests import the real mining package; action callbacks record unit effects.
  Existing healer tests use mock Stratum jobs/adapters. No physical MMIO or pool
  response is inferred from those fixtures.

## Changes and compatibility

`RecoveryGovernor.dispatch` accepts an active, identity-owned PROPOSED record only.
Completed, foreign, copied-ID, already-dispatched and deferred records cannot be
re-executed. A new attempt requires a fresh proposal and fresh authorization.
The inspected coordinator call sites already create one proposal per dispatch.
Whole-plan command/callable validation precedes side effects; a broken step
iterator closes FAILED. Acknowledgement True/False/None semantics are preserved,
except an exception now closes FAILED and is re-raised. Existing AL HARAS
PermissionError strings and live-supervisor lane-write deferral are preserved.
A per-governor reentrant lock prevents duplicate concurrent dispatch; this is not
cross-process or distributed exactly-once execution. It does not make every
observation, supervisor callback or checkpoint globally transactional.

## Executed results

| Suite | Passed |
|---|---:|
| User's mining-mode acceptance | 27 |
| Salamander autonomic | 22 |
| Euclid mining curriculum | 4 |
| Poincare/Salamander intelligence | 28 |
| New mining dispatch boundary regressions | 16 |
| Existing mining healer fixtures | 6 |
| Existing Chronus107 production integration | 4 |
| **Combined software run** | **107** |
| Separate agent capability/lifecycle/production-factory run | **135** |

Both final runs have zero failures/skips. Syntax compilation also passed.
The exact new 16-test file against unchanged parent recovery source produced
**11 failures and 5 passes**; after the repair all 16 pass. The before-fix log is
retained, not removed. The earlier 14-case intermediate test version had 10
failures/4 passes; it is not the final suite count.

Commands:

```sh
PYTHIA_STRUCTURE_BOOTSTRAP=false PYTHIA_NONCE_ORDER=m32 \
PYTHONPATH=.:chronus/mla1517_platform/python \
python -m pytest -q --noconftest \
 tests/test_salamander_mining_mode_acceptance.py \
 tests/test_salamander_autonomic.py \
 tests/test_euclid_mining_curriculum.py \
 tests/test_intelligence_poincare_salamander.py \
 tests/test_mining_recovery_dispatch_boundary.py \
 tests/test_salamander_mining_healer.py \
 tests/test_chronus107_production_mining.py

python -m unittest discover -s tests -p 'test_agent_capabilit*.py' -v
```

## Failed attempts and scope limits

Earlier collection failed until the real Lucas, MLA/platform, Aethel enterprise,
compiler/format/assembler/ISA, curriculum/domain and seed dependencies were
retrieved. These were local closure omissions, not repaired source defects.
With default structural bootstrap, three passport tests could not initialize
because `python_backend` structural-training dependencies were not in this
closure. With the default Hendrix route, five healer fixtures could not initialize
because the Turing package was not present. The explicit software configuration
above avoids those unavailable integrations; it does NOT qualify them or silently
change production defaults. `--noconftest` means repository-wide pytest fixtures
and the standard CI invocation are not claimed verified by this run.

The committed acceptance file's `_control_surface` helper mirrors the coordinator
handler: its passing tests are not an end-to-end service/API transport test.
The four Chronus107 tests are not the full inherited `check_chronus107` chain.
That complete chain and hosted required CI have not been executed here.

Physical OpenCL remains unavailable in this sandbox (no exposed device/vendor
paths; pyopencl absent). Live-pool submission, acceptance, share discovery,
performance/profitability, custody crash recovery and production owner/security
acceptance remain unproven. Existing enterprise release gates remain in force.
The two user-mentioned IDE agents are not exposed as executable tools/processes
in this session; no independent agent review is claimed.

Recommendation: review and run required CI/target-host qualification on this
repair; retain production HOLD until the outstanding deployment gates have
actual evidence. Successful tests are retained as earned software evidence.
