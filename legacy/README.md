# Legacy Subsystems (HISTORICAL MISNOMER — RESTORED & INTEGRATED)

> **OWNER-DIRECTED CANONICAL STATUS (October 2026):**
> Branding these modules as "legacy" or "excluded from the active import path" was an **audit misnomer**.
> Per governing Owner Declarations (`OWNER_DECLARATIONS.md`):
> 1. Chronus is the owner's GPU, its potential is exponential, limited by math only.
> 2. Quantum comes from mathematics: first-principles quantum mathematics and the entire quantum library (entanglement, QAOA, VQE, quantum walks, exact Grover) are active and canonical.
> 3. Enterprise data offerings, Intelligence, analytics, security, and multi-sector domains are core first-class capabilities.
> All swept capabilities (including `chronos/`, `Intelligence/` algorithms, `lucas/` components, and `mining/` production runners) have been restored to their active paths, integrated, and validated across the whole system.

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
