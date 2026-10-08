# toe — a domain-general mathematical intelligence engine

`toe/` is TOE's source. The public, standalone description (what TOE is, evidence
classes, ownership boundaries) is [`packaging/toe/README.md`](../packaging/toe/README.md);
the recovered architecture is [`docs/toe/ARCHITECTURE.md`](../docs/toe/ARCHITECTURE.md);
the claim register is [`docs/toe/CLAIM_REGISTER.md`](../docs/toe/CLAIM_REGISTER.md).

TOE was discovered inside PYTHIA through an HR-shaped application
(`toe.engine.PredictiveEngine`). That vocabulary is lineage: one backend reasons over any
problem reduced to `toe.problem.Problem`, and `toe.adapters` are the only per-domain code.

## Layers

| Layer | Where |
|---|---|
| Composition root (tenancy, receipts, evidence chain, consensus boundary) | `toe/runtime.py` — `TOEIntelligenceRuntime.solve` / `learn`; HTTP surface `toe/ciaas_api.py` |
| Reasoning core | `toe/machine.py` — `TOEMachine.run` / `learn` / `replay` |
| Problem contract | `toe/problem.py` |
| Reasoning modules | `representation`, `intelligence_state`, `relationships`, `causal_ladder`, `causal_stack`, `uncertainty`, `policy`, `planning`, `meta_reasoning`, `precision`, `arbitration`, `decision_explanation`, `world_model`, `memory`, `topology`, `geometry`, `self_governance`, `receipts`, `custody` |
| Domain adapters | `toe/adapters/` (tabular, causal system, graph, temporal, code, scientific, legacy HR) |
| Enterprise analytics | `toe/unified/` |
| Monorepo-only consumer surfaces (not in the standalone wheel) | `toe/system.py`, `toe/intelligences/`, `toe/manifold_bridge.py`, `toe/hardened_unified_substrate.py` — PYTHIA's mining-facing coordinator |

KELLOGG (`kellogg/`) owns the tensor and exact-field mathematics TOE consumes; PYTHIA's
mining adapter is `chronus/mla1517/mining/toe_problem.py`; EUCLID's handle is
`euclid/cognition/toe_capabilities.py`.

## Consensus boundary

TOE never decides share or block validity. In mining it advises an operational setting;
PYTHIA authorises; `chronus.mla1517.mining.pow.check_pow` (double SHA256 + target) alone
decides validity. In mining mode the runtime refuses any consensus field as a TOE
decision variable.

## Verification

```bash
python -m pytest tests/test_toe*.py tests/test_euclid_toe_capabilities.py -q
python scripts/toe_mining_voyage.py                 # PYTHIA ↔ TOE end to end
python scripts/toe_ablation_study.py --n 60          # held-out ablations + controls
python scripts/toe_universal_principle_evidence.py   # the golden-family evidence pack
python packaging/toe/build_and_verify.py             # standalone wheel/sdist verification
```
