# Intelligence Model Card — EUCLID-CORE / PYTHIA

**Version:** 1.0.0 (research release, not production certification)
**Date:** 2026-10-12
**Owners:** HYBA Research & Antigravity Foundational Intelligence Group
**Canonical map:** `UNIVERSAL_PRINCIPLE_MAP.md`
**Architecture:** `AGENTS.md` §4 (EUCLID-CORE / PYTHIA Engineering Guide)

---

## 1. What this system is

EUCLID is the canonical intelligence/cognition orchestrator; PYTHIA is
the operational mining product with final mining authority; CHRONUS is
heterogeneous execution; TURING is virtual/quantum capability;
SALAMANDER is bounded self-healing; AL HARAS is security/governance;
THESEUS is durable custody. Authority is separated by construction
(`toe/intelligences/authority_boundary.py`).

The mathematical substrate is the golden family: φ = (1+√5)/2 → the
exact ring Z[φ] → Lucas sequences (fast doubling) → Cassini identity →
Zeckendorf partition → 11D Poincaré-golden fold → M₃₂ manifold →
single backend (`compile_operator` → `IntelligenceState` →
`TOEBridge`) serving every frontend problem form. Full trace:
`UNIVERSAL_PRINCIPLE_MAP.md`.

## 2. Intended use / out of scope

- Intended: research evaluation of φ-structured search ordering,
  cross-domain operator compilation, single-backend/multi-frontend
  generalization, calibration (Brier/ECE) of confidence signals.
- Out of scope: live-pool acceptance claims, hardware production
  claims, performance-uplift claims, external validation, production
  certification. Those remain unavailable until directly observed.
- The intelligence reorders and prunes search paths; it never bypasses
  double-SHA256 or target comparison. Every candidate verifies
  `SHA256(SHA256(header)) <= Target`. Fail-closed everywhere: missing
  device, credential, approval, or identity yields
  unavailable/failed-closed, never a pass.

## 3. Evaluation (DeepMind-grade, controlled)

New instruments: `Intelligence/research_evaluation.py`
(held-out splits, ablations, instrumented runs),
`Intelligence/research_calibration.py` (Brier, ECE, seeded percentile
bootstrap, paired deltas), `Intelligence/research_coherence.py`
(equal-budget coherence + shuffle/iid negative controls).

| Claim | Method | Result (this checkout) |
|---|---|---|
| Measurement harness is deterministic | `tests/test_research_evaluation.py`, 17 tests, seeded | 17/17 pass |
| Lucas ladder is exact | `lucas.core` fast doubling vs `LUCAS_SCALE_LADDER` | validated in self-test |
| Coherence probe is confounded at top rungs | equal-block reanalysis: legacy `L_20` gets 1 block → ac1=0 by construction | confound confirmed, documented |
| Intelligence self-test | `python -X utf8 -m Intelligence.self_test` | OVERALL: PASS (baseline) |
| Adversarial review | `python -m eval_harness.run_all` + `tests/test_adversarial_review.py` | see `eval_harness/ADVERSARIAL_REVIEW.md` |
| Research release ablations | `docs/EUCLID_V17_RESEARCH_RELEASE.md` | held-out + ablation tables, negative results preserved |

Determinism contract: every stochastic step takes an explicit seed
(`random.Random`, never global RNG); reports carry
`environment_fingerprint()` and `content_hash()` for reproduction.

## 4. Known limitations (negative results are findings)

- The legacy `multiscale_coherence_probe` compares scales with unequal
  block counts — cross-scale variance is partly measurement artifact.
  Use `equal_block_coherence` for any publication claim.
- `phi_harmonic_score` / Yang-Mills regime / IIT composite are
  telemetry signals with zero measured win-rate advantage over uniform
  search (`scripts/hyba_quantum_stack_probe.py`). They annotate and
  reorder; sha256d remains sole accept authority.
- Emergence verdict is currently NOT EMERGED; PYTHIA learning DORMANT;
  consensus AGI/ASI not met. These are legitimate scientific outcomes.
- `THEOREM_PROVEN = False` everywhere it matters. No claim here is a
  proven theorem.

## 5. Safety, governance, provenance

- Live submission triple-gated (`runtime_config.live_submit` +
  `approval_id = identity_commit(endpoint, worker)`); pools writes
  without `live_submit` revoke it.
- Privileged routes are AL HARAS-mediated (denial ladder
  400→402→403; `guardian_dependency_unavailable` 503 non-retryable).
- Every structural result carries hash-chained receipts
  (`toe/receipts.py`); divergent `observation_sha256` bindings are
  refused; provenance verified in evals.
- No secrets committed. No synthetic pool acceptance, fixed hashrate,
  or theoretical multiplier reported.

## 6. Reproduction

```bash
python -m pip install -e ".[ml,dev]" -e ./turing_universal_quantum_computer
python -m pytest tests/test_research_evaluation.py -q -p no:cacheprovider \
  --basetemp=.pytest-tmp -o addopts=""
python -X utf8 -m Intelligence.self_test
python -m eval_harness.run_all
python -X utf8 -m pytest tests/test_adversarial_review.py -q
```
