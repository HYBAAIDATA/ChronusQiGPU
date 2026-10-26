# P0 notes implementation: canonical execution postcondition

## Scope and provenance

Repository: HYB-APHIDATA/HYBAEnterprise. Reviewed base:
`b131edc408a37ff7c03534d694bfcdaf0c827abb`.
This implements the original P0 requirement at the production router's return
boundary. It is not a new mining thesis, a proof validator, or a release certificate.
The earlier planner/transport changes remain separately proposed in draft PR #14.

## Notes → executable contract

| Original requirement | Implementation and disposition |
| --- | --- |
| Classify canonical execution independently of fallback provenance | Existing immutable SearchPlan `search_architecture` marker through `_is_pythia_lattice`; never inferred from missing fallback reason. |
| Canonical planning cannot silently substitute M32 | Router rejects non-Hendrix canonical plans before dispatch. Upstream generic solve-first plan preservation is separately in PR #14, not bundled here. |
| Preserve planned → requested → executed identity | New `search_authority_guard.require_canonical_execution` checks all three fields for every positive-work canonical execution before returning its candidate. |
| Canonical execution cannot have nonce-order fallback | Reject any non-None nonce-order fallback reason, including an empty string. |
| Keep compatibility separate | Noncanonical plans are not relabelled canonical. Existing ExecutionRecord validation continues to require explicit substitution provenance. No authority is granted by this helper. |
| Do not fabricate execution | Zero-work refusal may retain absent executed-order provenance; existing router candidate/count checks remain in force. |
| Distinguish backend fallback from algorithm replacement | A named device/route fallback may preserve exact Hendrix identity; algorithm substitution may not. |
| Preserve proof, leases and pool truth | No changes to hashing, target comparison, lease checks, full-estate traversal, Stratum writing, freshness or pool outcomes. |
| Valid patch rather than synthetic hunk headers | Git-generated binary-capable diff checked against a clean pinned source subset. This is not a full repository clone. |
| Blocking doctrine/P0/full regression and exact-head review | Remain release gates. No workflow or branch-protection settings changed; no invented CI result. |

The original named REQ IDs were not reconstructed into invented definitions.
This is the specific execution-provenance addition, not a claim that every original
P0 suite, candidate-estate audit, or full production qualification has completed.

## Qualification

- New tests: 21 cases.
- New boundary + existing execution-router suite: **51 passed, 4 skipped**,
  both normally and under optimized Python.
- New boundary + actual resident Hendrix + transport chaos: **60 passed**,
  both normally and under optimized Python.
- Unique selected tests: **90 passed, 4 skipped** in each interpreter mode
  (21 boundary cases appear in both commands; do not double-count them).
- Four skips are hardware-specific OpenCL tests, not native mathematics blockers.
- Full flake8 passed for the two new Python files. Modified modules compile.
- Optimized pytest reports its standard warning about assertions outside rewritten
  test modules; the production guard uses explicit exceptions, not `assert`.

Commands, from the repository root:

```sh
PYTHONPATH=chronus/mla1517_platform/python python -m pytest --noconftest -q \
  tests/test_p0_canonical_execution_boundary.py tests/test_execution_router.py
PYTHONPATH=chronus/mla1517_platform/python python -m pytest --noconftest -q \
  tests/test_p0_canonical_execution_boundary.py tests/test_resident_hendrix.py \
  tests/test_mining_transport_chaos.py
# Repeat both commands with `python -O -m pytest`.
python -m flake8 chronus/mla1517/mining/search_authority_guard.py \
  tests/test_p0_canonical_execution_boundary.py
python -m py_compile chronus/mla1517/mining/search_authority_guard.py \
  chronus/mla1517/mining/resident_router.py
```

Retained log copies normalize trailing whitespace only; raw logs remain local.

## Evidence limits and remaining release gates

Tests ran in a selectively restored source workspace, using `--noconftest`, not
an independently clean-installed complete repository. Some supporting dependencies
were restored from retained source and are not all attested to this exact head.
The router's original bytes were verified against the pinned Git blob. The new
boundary tests use explicitly labelled executor-result fixtures; the resident
regressions exercise the existing software execution path. Neither constitutes
physical accelerator evidence or an accepted live pool share.

Before merge/release: complete installed-repository doctrine, P0 and full regression;
review on the exact final head; required CI/branch protections; composed-system,
recovery/soak/rollback and deployment qualification. Previous check-run reads were
blocked by connector token permissions, so CI is unverified. Restore the actual
backend/corpus dependencies for the full canonical workflow, not mocks or bypasses.
Nothing merged, deployed, published, or enabled for live pool submission here.
