# MCP + SDK Packaging for EUCLID / PYTHIA Augmentation

This branch adds the Phase 0 skeleton for packaging the EUCLID aptitude (PYTHIA skills, evidence model, session gates) as a discoverable MCP bundle plus a supporting SDK.

## Components added

- `mcp/mcp_config.json` — template for connectors (Notion, storage) and owner-approval metadata. Secrets via env / MCP secrets only.
- `sdk/euclid_mcp/` — Python SDK skeleton with:
  - `start_session()` / `end_session()`
  - `invoke_skill()`
  - `produce_pack()` (evidence digest)
  - `require_owner_approval()` stub
- Existing `plugins/pythia/.mcp.json` remains the primary manifest (to be extended in follow-ups).

## Why this design

- MCP bundle = versioned, installable unit for hyperscalers and Notion agents.
- SDK = enforces session lifecycle, mandatory skills, evidence collection, and gates without leaking transport details.
- Separates delivery from authority (EUCLID contracts, THESEUS custody, CHRONUS execution).

## Phased roadmap (from design)

**Phase 0 (this PR)** — skeleton: manifests, SDK stubs, README.
**Phase 1** — Notion connector + canonical retrieval + evidence digests.
**Phase 2** — Docker/Helm, CI publish, owner-approval gate.
**Phase 3** — training pipeline templates (Kubeflow/Vertex/SageMaker) + THESEUS provenance.
**Phase 4** — hyperscaler pilot, observability, anti-hallucination hardening.

## Anti-hallucination controls (enforced by SDK + gates)

- Grounding required for factual claims.
- Verification before completion.
- `theorem_proven` remains `False`.
- Owner approval for high-risk / canonical promotion.

## Next steps

1. Merge this skeleton after owner review.
2. Implement Notion connector (Phase 1).
3. Wire session_start / stop_gate to SDK.
4. Add CI job for MCP artifact build.

Owner approval required: @EuclidUltimaPhi

theorem_proven remains False.
