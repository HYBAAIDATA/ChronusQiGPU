# Legacy PYTHIA acceleration paths

This directory is intentionally non-production and is excluded from the active
TypeScript/Python import path. It records the old M3/iGPU, projected scaling,
synthetic substrate, and quantum-walk surfaces that were removed from PYTHIA.

The canonical mining implementation is **only**:

```text
mla1517_platform_v3.4/
```

Do not add compatibility shims or restore imports from this directory. If a
capability is needed, implement it against the canonical Python/C/OpenCL
contract and add a real test.

## Consolidated non-canonical surfaces (2026 audit move)

The full non-canonical sweep moved ~640 tracked files here, preserving their
original relative paths (`legacy/<original path>`). This includes:

- `PYTHIA_Frontend/` — foreign TanStack-Start product (its embedded
  `artifacts/PYTHIA/` repository copy was deleted outright, not archived)
- `papers/`, `experiments/`, `training/`, `models/`, `data/`, `artifacts/` —
  research substrates and offline evidence
- `python_backend/`, `pythia/`, `advisor/`, `server.ts`, `orchestrator.py`,
  `pythia_agent.py`, `registry.py`, `self_test.py`, `toe.py` — duplicate
  backends, agents, registries and the monolithic TOE substrate
- `euclid/`, `mtheory/`, `pythagoras/asi`, `accel/`, `AETHEL_Subsystem/` —
  orphaned math/research libraries (canonical-reachable `pythagoras/`
  orchestrator/domain modules were kept in place)
- Non-canonical subtrees of `Intelligence/`, `mining/`, `hyba/`, `lucas/`,
  `core_engine/`, `src/`, `tests/`, `scripts/` (per-file import-closure triage)
- `bridge/`, `infra/`, `monitoring/`, `configs/`, `hardware/`,
  `iGPU_Accelerator_JV/` — deploy/design artifacts for non-canonical paths
- `.github/workflows/{ironclad,lucas-system,toe-tensor,mri-substrate-ci,
  pythia-boundary-gate}.yml` — CI gates that exclusively guarded
  non-canonical code
- Firebase/Firestore applet config and AI-Studio metadata for the removed
  foreign product surface

Canonical-reachable dependencies outside `mla1517_platform_v3.4/` were
deliberately kept in place: `turing_core.py`, the reachable subsets of
`Intelligence/`, `mining/`, `hyba/`, `lucas/`, `core_engine/`, `pythagoras/`,
`kernels/` (OpenCL sources loaded by path), `Intelligence/skills/`, and the
canonical gate scripts `scripts/{verify,re_paper_gate,drift_sentry}.py`.

Enterprise PRIME-DB and storage implementation is maintained separately in
`PHIDATA2/Enterprise`; it is not copied into, imported by, or interpreted as
part of PYTHIA.
