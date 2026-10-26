# Agent 2 qualification — component scope only

**NOT a commercial launch certificate.** The `/enterprise` route has no service binding. No authenticated HTTP contract, installed engine execution, backup/restore cutover or production build is established.

- Branch base: `b131edc408a37ff7c03534d694bfcdaf0c827abb`.
- Native Node isolated boundary tests: initial 24 = 23 pass / 1 fail in new Agent 2 code; final expanded 25 = 25 pass / 0 fail / 0 skip. Failure was unsupported exactness incorrectly receiving a verified display label; repaired. Added JSON-evidence serialization validation. These are adapter doubles, NOT a repaired engine regression.
- Standalone `boundary.ts` strict TypeScript check: exit 0; full React/repository typecheck not run.
- Isolated esbuild React component bundle: executed by browser fixture harness, not the repository production build.
- Browser fixture: eight desktop scenarios; two mobile layout checks; expanded evidence and export; tenant-switch clearing. Synthetic adapter only, no external requests. Screenshots visibly say COMPONENT FIXTURE. `browser-results.json` identifies checks; screenshot hashes identify the separate evidence archive.
- Manual visual inspection: all eleven retained fixture screenshots inspected individually after spacing repair. This does not qualify full-app CSS integration, keyboard/screen-reader acceptance or WCAG conformity.
- New-file formatting: Prettier check retained. No repo-wide lint/production build, installed package regression, actual service acceptance, CI, hardware, provider, Docker, cloud, deployment or publication claimed.

Full packet and requirement ledger: `docs/launch/COMMERCIAL_LAUNCH_PACKET.md`, `docs/launch/requirements.csv`.

## Reproduce scoped tests

```sh
node --experimental-transform-types --test --test-reporter=tap scripts/enterprise_boundary.test.mjs
node scripts/enterprise_browser_qa.cjs
# Set CHROMIUM_PATH if not /usr/local/bin/chromium.
```

Browser harness uses local esbuild, playwright, React and Chromium. Executed tools were sandbox-provided, NOT installed from repository lockfiles; pinning that test environment remains open. Native Node's TypeScript transform is experimental. Tool versions and source hashes are recorded, not assumed equal to the repository's dependency installation.

## Screenshot retention

Eleven PNG files are delivered in `HYBA-Agent2-qualification-fixtures.zip`, separately from repository text. Each carries the fixture warning. `screenshot-manifest.json` binds their byte hashes. The archive also contains exact source, logs and reproduction harnesses. It is not a full repository archive and must not be used as a substitute for installed-system acceptance.

## Joint completion

A combined candidate preserving PR #13, safe transactional restore, actual authenticated service/admission/revocation contract and full clean installation remain blocking inputs. User/operator brand, support, legal and commercial approvals remain independent. Neither agent's local unit counts close the joint workflow.
