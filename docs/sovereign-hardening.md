# Sovereign Enterprise Hardening Runbook

This document is the operational companion to the pipeline changes in
`.github/workflows/ci.yml` and `.github/workflows/release.yml`. It covers the
controls that must be applied from the GitHub UI or with owner-level
credentials, because they sit outside what workflow code can enforce.

## 1. Build provenance and signatures (implemented)

**Plan constraint:** GitHub artifact attestations are unavailable on
user-owned private repositories (the API rejects them; they require a public
repository or an organization with GitHub Advanced Security). All attestation
steps are therefore `continue-on-error: true` and activate automatically once
the repository qualifies — no workflow edits needed.

Until then, cryptographic receipts come from **Sigstore keyless signing**
(cosign), which works on private repos today: every artifact gets a public
Fulcio OIDC certificate bound to this repo's workflow identity, plus a Rekor
transparency-log entry, in a `.sigstore.json` bundle.

- `ci.yml` job `provenance` attests the Python distribution on every push to
  `main` and every `v*` tag (activates when eligible).
- `release.yml` signs and attests `dist/*`, the CycloneDX SBOM, and the
  qualification dossier on every tag; `.sigstore.json` bundles are attached
  to the GitHub Release.
- `investor-evidence-dossier.yml` signs and attests the PDF certificate and
  raw telemetry; bundles are uploaded as workflow artifacts.
- Verify any artifact offline:

  ```bash
  cosign verify-blob --bundle <artifact>.sigstore.json \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    --certificate-identity-regexp '^https://github.com/hybadatadevops1/Chronusv2/' \
    <artifact>

  # once attestations are enabled:
  gh attestation verify <artifact> --repo hybadatadevops1/Chronusv2
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

`infra/runners/al-haras/` contains a systemd unit, root bootstrap and
teardown scripts, an ephemeral registration script and job hooks for a
self-hosted runner on a dedicated Linux host. Its README covers installation,
every configuration variable, what the BPF LSM attestation and the unsigned
pre-flight receipt do and do not establish, retention, deregistration, and
the job template. CI checks these files with `bash -n` and stub-based tests
(`tests/test_al_haras_runner_scripts.py`). They have not been validated on a
real host from this repository, and the LSM objects they load are not part
of it.

Public hosted runners are multi-tenant. For RTL netlists, PV companion-matrix
logic, and threshold-MPC key material, use self-hosted runners in ephemeral
mode:

- Register runners with `--ephemeral`, so that each takes exactly one job and
  GitHub de-registers it afterwards. `infra/runners/al-haras/` does this on a
  systemd host (bare metal or VM). Actions Runner Controller (ARC) on your
  own Kubernetes cluster is an alternative that these files do not cover.
- Prefer confidential-compute hosts (AMD SEV-SNP / Intel TDX) so job memory
  is hardware-encrypted against the hypervisor. The runner scripts neither
  collect nor verify any hardware attestation.
- Routing: runner groups exist only for organizations and enterprises. For
  this user-owned repository, register the runner at repository level and
  route jobs by label: `runs-on: [self-hosted, sovereign, al-haras-enforced]`.
  In an organization, create a runner group (e.g. `sovereign-compute`)
  restricted to this repository, set `RUNNER_GROUP` and the organization URL
  in the runner's settings file, and use
  `runs-on: { group: sovereign-compute, labels: [sovereign, al-haras-enforced] }`.
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
