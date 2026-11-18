# Chronus project map

This is the repository operating model. It keeps the root decision-led and
makes the boundary between maintained implementation, evidence, deployment,
and historical material explicit.

## Root rule

Add a file to the repository root only when it is one of these:

1. a standard project control (`AGENTS.md`, `LICENSE`, `SECURITY.md`);
2. a reproducible setup or build entrypoint (`pyproject.toml`, `Makefile`,
   `Dockerfile`, `docker-compose.yml`, `alembic.ini`);
3. a current release or qualification decision (`STATUS.md`,
   `RELEASE_DECISION_MCKINSEY_TECH.md`, current manifests); or
4. the primary project brief (`README.md`).

Everything else belongs in the most specific maintained or historical area.

## Placement decisions

| Material | Location | Why |
| --- | --- | --- |
| Maintained runtime | `src/chronus/` | Importable product implementation |
| Web product preview | `frontend/` | Independently runnable Next.js application |
| Release and evidence checks | `scripts/ci/` | Explicit, reviewable control surface |
| Research and prototype scripts | `scripts/research/` | Runnable but not presented as maintained product surface |
| Deployment entrypoints | `deploy/runtime/` | Runtime packaging separate from source and research |
| Historical demos | `archive/root-demos/` | Preserved for provenance without implying current product scope |
| Repair drafts, captured output, and old snapshots | `archive/root-artifacts/` | Retained, searchable, and clearly non-authoritative |
| Product and technical decisions | `docs/` | Structured documentation with current directives taking precedence |
| Results and provenance | `evidence/` | Commit- and environment-bound records |

## Decision hierarchy

Use the newest applicable source and current evidence in this order:

`AGENTS.md → docs/directives/ → docs/claim-audit.md → release decision → source and tests → historical archive`

Historical files help explain provenance or regression intent. They do not
override current directives and do not become live product claims by being
present in the tree.

## Working agreement

- Keep one clear user question or decision per product screen.
- Label measured, estimated, simulated, illustrative, stale, unavailable, and
  unverified data explicitly.
- Do not put generated outputs, temporary repair scripts, or prototype dumps in
  the root.
- Prefer a small README beside an archive or research area over unexplained
  file names.
- Update references and tests when a maintained path changes.

