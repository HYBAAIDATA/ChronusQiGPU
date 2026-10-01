# PYTHAGORAS v12 — Mining repository integration

PYTHAGORAS v12 is integrated into `PYTHIPhiMiner` as the repository's meta-evolutionary code-intelligence substrate.

## Authority and runtime boundaries

- **EUCLID** owns repository-level Intelligence evaluation through `EuclidIntelligenceEngine` and the Lucas/Pisot scaling contract `L_n * 20^(phi * t_p)`.
- **PYTHAGORAS** owns candidate search, structural resonance, CGP, surrogate-guided mutation, meta-evolution, geometry evolution, primitive discovery and persistent evolutionary state.
- **SALAMANDER** owns transactional publication of evolved repository source. PYTHAGORAS may propose a candidate; Salamander performs backup, repository verification and commit-or-rollback.
- **AL HARAS** receives candidate validity-gate evidence through the v12 multi-agent manifold.
- **PYTHIA** receives search-state and geometry/phase-transition records. Mining share authority remains the existing SHA256d/Stratum path.

The superseded V6.0–V6.5 engine implementation files are not part of the active package. Their capabilities are provided by the current repository engine (`pythagoras/orchestrator.py`, `meta_evolution.py`, `geometry_evolution.py`, `auto_primitive.py`, `cgp.py`, and the code-domain mutation substrate).

## v12 surfaces

- `adapter.py` — stable host façade.
- `core/euclid_intelligence.py` — EUCLID Intelligence evaluator.
- `core/phi_metric.py` — v12 structural metric.
- `core/primitives.py` — v12 primitive vocabulary mapped to current operators.
- `core/tononi_penrose.py` — mathematical model, explicitly labelled `MODELED`; never physical Mining telemetry.
- `agents/manifold.py` — shared 11D coordination state.
- `agents/orchestrator.py` — measured EUCLID/SALAMANDER/AL HARAS/PYTHIA cycle.
- `healing.py` — v12-to-Salamander transactional healing bridge.
- `enterprise/roi_governance.py` — measured governance fields plus optional caller-supplied economic modelling.
- `benchmarks/` — the supplied v12 benchmark corpus.
- `run_pythagoras.py` — verification and opt-in healing entry point.

## Verify the integrated payload

```bash
python -m pythagoras.run_pythagoras --generations 5
```

This exercises analysis, evolution, invariants, governance, multi-agent coordination and the manifold without writing repository files.

## Run verified repository healing

```bash
python -m pythagoras.run_pythagoras \
  --repo-root . \
  --heal-file pythagoras/example.py \
  --generations 20 \
  --verify-cmd "python -m pytest -q tests/test_pythagoras.py tests/test_c_pythagoras.py"
```

A candidate is never published by this path without the Salamander verification transaction. If the verification command fails, the original file is restored. Test files are not eligible for autonomous writes.

## Evidence boundary

No value produced by the Tononi/Penrose model or optional ROI model is Mining operational evidence. Pool state, hashrate, accepted/rejected shares and related dashboard fields continue to come only from the existing real mining execution/telemetry pipeline.
