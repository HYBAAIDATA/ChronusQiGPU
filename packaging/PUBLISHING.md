# Publishing HYBA Software Limited packages to PyPI

Status on 7 October 2026, checked from this repository:

| Item | Finding |
|---|---|
| `kellogg-tensor` on PyPI / TestPyPI | Not registered (HTTP 404) — the name is available |
| `turing-universal-quantum-computer` on PyPI | Not registered — available |
| `chronos-core` on PyPI | Not registered — available |
| PyPI organization for HYBA | None found under `hyba`, `hyba-software`, `hyba-software-limited` |
| Existing company PyPI user account | Cannot be determined from outside: PyPI user pages sit behind a bot challenge. The owner must check by signing in. |
| PyPI credentials on the build machine | None (no `.pypirc`, no `TWINE_*`/`PYPI_*` variables, no keyring) |
| Existing publishing workflow in this repo | `.github/workflows/kellogg-tensor.yml` — verified-artifact OIDC path with `none`, `testpypi`, and `pypi` dispatch modes |
| GitHub Actions | **EXTERNAL RELEASE INFRASTRUCTURE BLOCKER**: KELLOGG run `37631272987` created jobs but executed zero steps; restore organization Actions billing/spend before the fresh release gate can run |

Publishing uses **PyPI trusted publishing**: GitHub Actions proves its identity
to PyPI with a short-lived OIDC token, so no PyPI password or API token is
ever created, stored, or pasted anywhere. The release workflow is
`.github/workflows/kellogg-tensor.yml`.

## Owner actions, in order

1. **Restore GitHub Actions.** In the `QuantumPhiRedux` account, open
   Settings → Billing & plans, resolve the failed payment or raise the
   spending limit. Until this is done no CI job runs and nothing can publish.

2. **Choose the company account.** Sign in at <https://pypi.org/account/login/>
   with the company mailbox you intend to use (a role address such as
   `pypi@<company domain>`, not a personal address). If no account exists,
   register at <https://pypi.org/account/register/>.

3. **Verify the email.** PyPI sends a verification link; publishing and
   project creation are blocked until it is clicked.

4. **Enable two-factor authentication** (required by PyPI to publish):
   Account settings → Two factor authentication → add a security key
   (WebAuthn) and/or an authenticator app (TOTP). Download the recovery codes
   and store them in the company password manager. Add a second owner later
   so access never depends on one person.

5. **Create the organization** (recommended): Your organizations → Create,
   name "HYBA Software Limited", type Company. PyPI reviews organization
   requests; company organizations are a paid plan. Make your account an
   Owner. Projects can be transferred into it later if review takes time.

6. **Register the pending trusted publisher** (the project does not exist
   yet): Your account → Publishing → Add a new pending publisher:
   - PyPI project name: `kellogg-tensor`
   - Owner: `QuantumPhiRedux`
   - Repository name: `PhiMiner`
   - Workflow name: `kellogg-tensor.yml`
   - Environment name: `pypi`

   Repeat on TestPyPI (<https://test.pypi.org>, a separate account with its
   own email verification and 2FA) with environment name `testpypi`.

7. **Create the GitHub environments** `testpypi` and `pypi` in the repository
   (Settings → Environments) and add a required reviewer from HYBA Software
   Limited to each, so every publish needs a human approval.

8. **Verify then publish Kellogg.** First run Actions → kellogg-tensor on current
   `main` with `publish = none` and require the final `release-verdict.json` to
   report `publishable: true`. Then run the same workflow with
   `publish = testpypi`; install
   `pip install -i https://test.pypi.org/simple/ kellogg-tensor` in a clean
   environment to confirm; then run again with `publish = pypi`.

9. **Then TURING.** `turing-universal-quantum-computer` depends on
   `kellogg-tensor>=1.0`, so it is published after Kellogg is live, with its
   own pending publisher (same repository, a TURING release workflow,
   environment `pypi`).

Nothing in these steps needs a credential to be shared with anyone: steps
2–7 are done by the owner in the PyPI and GitHub web interfaces.
