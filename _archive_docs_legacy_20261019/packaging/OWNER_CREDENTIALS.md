# Owner credentials setup — one evening checklist

Everything the workflows need that only the owner can create. None of it is a
secret stored in the repo: publication runs on **short-lived OIDC**, so the work
below is *registration and gating*, not password-keeping. Estimated effort:
~1 hour for the registries + GitHub environments; Apple items are a separate
track with their own account approval lag.

## 0. Before anything — confirm the publishing repository identity

All six publish workflows and the release verdicts declare the canonical
repository as **`QuantumPhiRedux/PhiMiner`**. This checkout's `origin` is
`PhiEnterprise/PhiEnterprise` (a mirror). OIDC tokens carry the repo the
workflow *runs on* — a pending publisher registered for `QuantumPhiRedux/PhiMiner`
will **fail** if the dispatch runs on `PhiEnterprise/PhiEnterprise`. Decide
tonight which repo publishes, and use that owner/repo pair consistently
everywhere below. (The rest of this file uses `QuantumPhiRedux/PhiMiner` —
the declared canonical identity.)

## 1. GitHub environments — the authorisation gates

Every upload job sits behind `environment: testpypi` or `environment: pypi`.
Create both in the publishing repo: **Settings → Environments → New environment**.

| Environment | Recommended protection | Purpose |
|---|---|---|
| `testpypi` | Required reviewer (yourself) | Gate before any TestPyPI upload |
| `pypi` | Required reviewer + wait timer (e.g. 30 min) | Gate before the irreversible PyPI upload |

Reviewer gating *is* the upload authorisation — `upload_authorised` stays
`false` in owner records until these exist. Do **not** add `PYPI_TOKEN` or
passwords as environment secrets; OIDC replaces them.

## 2. PyPI account + pending publishers

One account at <https://pypi.org> — enable **2FA (mandatory for publishing)**,
verify the email. Then **Account settings → Publishing → Add a new pending
publisher → GitHub** for each row below. A pending publisher both reserves the
name and authorises the first upload — no package needs to exist first.

Fields for **every** row: Owner `QuantumPhiRedux`, Repository `PhiMiner`,
Environment `pypi`.

| PyPI project name | Workflow name (exact filename) |
|---|---|
| `hyba-kellogg-tensor` | `kellogg-tensor.yml` |
| `hyba-turing-vqc` | `turing-release.yml` |
| `hyba-theseus-storage` | `storage-publication-preparation.yml` |
| `hyba-ovid-data-organisation` | `storage-publication-preparation.yml` |
| `hyba-toe-intelligence` | `toe-release.yml` |
| `hyba-euclid-intelligence` | `euclid-v17-release.yml` |
| `hyba-pythia-consumer` | `consumer-publication.yml` |

## 3. TestPyPI — same again

<https://test.pypi.org> is a **separate account database** — register again,
2FA again. Add the same seven pending publishers, same owner/repo/workflows,
but environment **`testpypi`**.

That's 14 pending-publisher entries total (7 names × 2 indexes).

## 4. Dependency order — what unlocks what

Sibling floors must resolve **on the target registry itself** — the workflows
fail closed otherwise (OVID's `hyba-theseus-storage==1.0.0` pin and EUCLID's
kellogg/toe/theseus presence gate are enforced in-lane).

```text
Wave 1 (no HYBA deps):  hyba-kellogg-tensor · hyba-theseus-storage · hyba-pythia-consumer
Wave 2:                 hyba-turing-vqc (needs kellogg) · hyba-ovid-data-organisation (needs theseus)
Wave 3:                 hyba-toe-intelligence (needs kellogg)
Wave 4:                 hyba-euclid-intelligence (needs kellogg + toe + theseus)
```

`hyba-pythia-consumer` is dependency-free — it vendors `aethel`/`hyba_db`/
`chronos_one_igpu` into the wheel, so it can publish in wave 1 on either index.

Each dispatch: `workflow_dispatch` with `rc_sha` = full frozen commit SHA and
`publish=testpypi` first; promote to `publish=pypi` only after the TestPyPI
smoke matrix is green.

## 5. Apple track — PYTHIA.app signing (separate, slower)

Needed to distribute `dist/PYTHIA.app` outside the build host. Approval lag
applies — start tonight if the app ships this cycle.

| Item | Where | Notes |
|---|---|---|
| Apple Developer Program | developer.apple.com | $99/yr; enrolment can take a day |
| **Developer ID Application** certificate | Xcode → Settings → Accounts → Manage Certificates | used by `codesign --deep --options runtime` |
| Notarisation credentials | App Store Connect → API key, or Apple ID + app-specific password + team ID | consumed by `xcrun notarytool` |
| Hardened runtime entitlements | evaluate at signing | none expected for stdlib HTTP + embedded Python |

Unsigned builds still work on the build host; Gatekeeper blocks them
elsewhere until signed + notarised. iPhone companion needs **no** App Store
release — it is a PWA. (True offline caching on iOS still requires a secure
origin; that's an HTTPS/native-shell question, not a credential.)

## 6. Explicitly do NOT

- Do **not** put registry API tokens or passwords in the repo, workflow files,
  environments, or logs — OIDC pending publishers replace them entirely.
- Do **not** set `upload_authorised: true` in owner records — it stays a false
  evidence field; authorisation is exercised through the gated environments.
- Do **not** claim names by manual `twine upload` of 1.0.0 — every release
  verdict fails closed on `1.0.0` already existing on PyPI. Pending publishers
  reserve the name without uploading anything.
- Do **not** skip TestPyPI — every lane enforces same-bytes promotion.

## 7. Verify it worked tomorrow

```bash
python packaging/portfolio_release_audit.py            # derived states should move off BLOCKED→QUALIFIED-only
python packaging/check_publication_catalog.py          # still PASS
gh workflow run consumer-publication.yml -f rc_sha=$(git rev-parse HEAD) -f publish=testpypi
```

A green TestPyPI dispatch is the first real registry evidence — the portfolio
audit then reports `TESTPYPI_VERIFIED` for that product.
