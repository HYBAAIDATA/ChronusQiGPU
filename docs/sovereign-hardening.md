# Sovereign Enterprise Hardening Runbook

This document is the operational companion to the pipeline changes in
`.github/workflows/ci.yml` and `.github/workflows/release.yml`. It covers the
controls that must be applied from the GitHub UI or with owner-level
credentials, because they sit outside what workflow code can enforce.

## 1. Build provenance attestations (implemented)

- `ci.yml` job `provenance` attests the Python distribution on every push to
  `main` and every `v*` tag via `actions/attest-build-provenance` with
  Sigstore/Fulcio OIDC signing. Statements appear under the repository
  **Attestations** tab.
- `release.yml` attests `dist/*`, the CycloneDX SBOM, and the qualification
  dossier on every tag.
- Verify any artifact offline:

  ```bash
  gh attestation verify dist/chronus-<version>.tar.gz --repo hybadatadevops1/Chronusv2
  ```

## 2. Threshold governance on `main` and `v*` tags (manual — owner action)

Repository rulesets on a private repository require GitHub Pro, and the
branch-protection API requires owner credentials. Apply once from the web UI
(**Settings → Rules → New ruleset**) or with a PAT:

```bash
gh api repos/hybadatadevops1/Chronusv2/rulesets -X POST --input - <<'JSON'
{
  "name": "sovereign-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/heads/main"], "exclude": [] } },
  "rules": [
    { "type": "required_signatures" },
    { "type": "pull_request", "parameters": { "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": true, "require_code_owner_review": false, "require_last_push_approval": true, "required_review_thread_resolution": true } },
    { "type": "required_status_checks", "parameters": { "required_status_checks": [{ "context": "Lint, compile and package" }, { "context": "Mathematical purity gate" }], "strict_required_status_checks_policy": true } },
    { "type": "non_fast_forward" }
  ]
}
JSON

gh api repos/hybadatadevops1/Chronusv2/rulesets -X POST --input - <<'JSON'
{
  "name": "sovereign-tags",
  "target": "tag",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/tags/v*"], "exclude": [] } },
  "rules": [ { "type": "required_signatures" }, { "type": "deletion" }, { "type": "update" } ]
}
JSON
```

Notes:

- `required_signatures` rejects any commit not signed by a registered
  GPG/SSH key (use a YubiKey/HSM-resident key). Do not activate before every
  maintainer has a hardware-backed signing key enrolled, or pushes to `main`
  will be refused.
- Protect the `azure-foundation` environment used by `cd.yml` with
  **required reviewers** (Settings → Environments → azure-foundation) so a
  second hardware-key holder must approve before Azure OIDC tokens mint.
- `cd.yml` already uses OIDC federated credentials (`id-token: write`,
  `azure/login` without a client secret). Keep static Azure secrets out of
  the repository; scope the federated credential subject to
  `repo:hybadatadevops1/Chronusv2:environment:azure-foundation`.

## 3. Ephemeral sovereign runners (manual — infrastructure action)

Deployable systemd unit, eBPF/LSM pre-flight hook, and registration scripts
ship in `infra/runners/al-haras/` (see its README for install and the
sovereign job template).

Public hosted runners are multi-tenant. For RTL netlists, PV companion-matrix
logic, and threshold-MPC key material, register self-hosted runners in
ephemeral mode:

- Deploy Actions Runner Controller (ARC) on your own cluster, or bare-metal
  machines, with the runner configured `--ephemeral` so each runner executes
  exactly one job and is destroyed.
- Prefer confidential-compute hosts (AMD SEV-SNP / Intel TDX) so job memory
  is hardware-encrypted against the hypervisor.
- Create a runner group (e.g. `sovereign-compute`) restricted to this
  repository, and switch sensitive jobs to `runs-on: sovereign-compute`.
- Keep `ubuntu-latest` for lint/coverage of public-facing code if fast
  feedback matters; anything touching `hw/`, `formal/`, or key material
  should run only on the sovereign pool.

## 4. Dependency and lockfile integrity (partially implemented)

- Frontend already enforces `pnpm install --frozen-lockfile` with a pinned
  pnpm version (10.12.4) and `cache-dependency-path`.
- Python: generate a hash-locked requirements file and install with
  `--require-hashes` in CI, e.g. via `uv pip compile --generate-hashes` or
  `pip-compile --generate-hashes`, then commit the lockfile.
- Mirror critical packages into a private registry (Azure Artifacts or an
  air-gapped devpi/bandersnatch mirror) so an upstream PyPI/npm compromise
  cannot poison a build.
- `release.yml` generates a CycloneDX SBOM (`sbom.cdx.json`) on every tag and
  attaches it to both the attestation and the GitHub Release.

## 5. Litigation-grade audit trail (manual — infrastructure action)

- Enable GitHub audit log streaming (organization settings) to an Azure
  Storage account with a WORM/immutability policy, or to Azure Event Hubs
  fronting immutable storage.
- Ship self-hosted runner kernel telemetry (journald, eBPF/AL HARAS hooks)
  to the same append-only store so pipeline history is preserved as forensic
  evidence.
- The release workflow bundles `manifests/` (qualification manifests), the
  SBOM, and `SHA256SUMS.txt` into
  `chronus-<tag>-qualification-dossier.tar.gz`, attested and attached to each
  release — the self-auditing dossier for counterparties and auditors.
