# Frontend developer release — implementation review

## Outcome and evidence boundary

Implemented an isolated, working React/Vite developer frontend and actual
build-time exclusion of the existing private application. **Draft / not ready
for publication**: public destinations, component first-use execution, master
brand assets, full-checkout private regressions and repository-history review
remain unresolved. Nothing was merged, published, deployed or mined.

Inspection baseline: `main` at `b131edc408a37ff7c03534d694bfcdaf0c827abb`.
Branch: `frontend/github-first-developer-boundary-20261025`.
Source file retrieval used authenticated GitHub MCP. Unauthenticated git checkout
was denied (`could not read Username`), so the local staging folder is a partial
retrieval, **not a complete checkout**. Local new-frontend results must not be
promoted into whole-repository or installed-component qualification.

## Frontend inventory and boundary map

| Existing location / entry | Classification from inspected evidence | Interface / data | Treatment |
|---|---|---|---|
| Root `package.json` | Private operator wrapper | Delegates to frontend npm scripts | Unchanged |
| `frontend/index.html` → `src/main.tsx` → `App.tsx`; `/` and six hash views | Private operational console | `useConsole` checks `/api/v1/control/session`, polls canonical status and separately reads subscription-protected evidence; login uses cookie-session endpoints | All source and original build behavior preserved; never import into public graph |
| `frontend/src/turing/TuringApp.tsx`; `/turing`, `/turing/app` | Out-of-tranche evaluation workspace | Existing workspace implementation; not exercised here | Preserved, excluded from developer graph |
| `/turing/product`, capabilities, how-it-works, enterprise, documentation, security, research, contact, legal/privacy, legal/terms | Existing broader public-facing copy, **not approved for this five-item release** | `PublicSite` contains article copy and a local JSON enquiry export, not a submitted sales request; hard-coded old repository destination | Preserved, not imported or linked by candidate |
| `frontend/contracts`, `scripts/serve_console_fixture.py` | Contract/fixture tooling | Fixture output is not live backend or product evidence | Not copied or used as a real integration |
| `frontend/src/lib`, `security`, `views`, existing components | Private app libraries and legacy lenses | Live/owner-derived and various legacy mathematical helpers; not all established as active | No speculative deletion or promotion |
| `legacy/PYTHIA_Frontend/package.json` | Legacy candidate from path/search; runtime not inspected | Unknown | Keep private/excluded; not declared safely dead |
| `recovery/hyba_data/source/hyba_data/frontend/package.json` | Recovery-source candidate from search; runtime not inspected | Unknown | Not a launch frontend; excluded |
| `services/resilience-gateway/package.json` | Service candidate, not verified as browser UI | Not inspected | Excluded; no invented product work |
| `external/sample-saas-multi-agents-workshop` packages | External example candidates | Not inspected | Excluded; do not advertise as HYBA integrations |
| `docs/brand/hyba_style_system.html`, token CSS | Brand reference, not a production app | Static reference | Canonical token CSS is the only outside-source import allowed |
| `demo_dashboard`, other root examples/artifacts | Additional repository directories, runtime role not established | Not inspected | Excluded, not silently declared obsolete |
| **New** `frontend/developer/index.html` → developer `src/main.tsx` | Public-candidate, standalone static frontend | Local filtering/routing only; no service calls or fixtures | Separate config and `dist/developer`; no credentials or API dependence |

Package-manifest search returned ten entries including evidence manifests; it is
a discovery aid, not an exhaustive executable-app certification. Existing main
imports the private console and TURING eagerly, so merely hiding navigation
would not remove their code from a combined build. Original Vite also discovers
private API ports and proxies `/api` during development. The new config does
neither. Original `dist/public` remains **private despite its name**.

No public package/downloader or interactive component API was found qualified
for this new browser entry. It is deliberately a developer reference, not five
invented dashboards. The browser exercises real local search/routing and static
artifact handling; no mocked response is represented as a backend integration.

## Private/public asset and configuration map

| Surface | Existing private build | Developer candidate |
|---|---|---|
| Entry graph | Original `src/main.tsx`, App and TURING | `developer/src` only |
| API/environment | `PYTHIA_API_URL`, active-port file, `PYTHIA_PORT`; existing `VITE_PYTHIA...` client configuration | No proxy, no port-file read, `envPrefix: []`, no `import.meta.env` in client |
| Credentials | Existing operator session and independent subscription flow | No input, cookie access, browser storage or credential persistence |
| Styles/assets | Private index.css and original app graph | Canonical brand token CSS + developer stylesheet; no publicDir copy or font/network asset |
| Output | `dist/public`; original sourcemaps false | `dist/developer`; sourcemaps false, manifest, audited known text asset types |
| Serving | Existing Python service and operator web-root | Isolated static loopback validation server, connect-src none, private paths 404 |
| Artifact publication | Not permitted | No output upload/deploy/visibility change; full `dist/` must never be published |

## Open work preserved

Open PRs inspected: #13 non-mining enterprise audit, #14 private mining transport,
#15 integrated launch qualification, #16 commercial backup experience, #17
canonical execution provenance. None was merged, cherry-picked or edited.
Owner's five-item launch scope supersedes older portfolio documents; it does
not justify deleting unrelated private/commercial work. The implementation only
adds developer files and additive scripts to `frontend/package.json`.

## Content/source matrix

All references below are pinned to the inspection baseline. Actual UI links to
four components require repository access; they are not advertised as approved
public releases. MCP setup/download links are withheld rather than fabricated.

| Route / reader | Core statement | Inspected source | Limits / destination |
|---|---|---|---|
| `#/` / developer choosing an owner | Five components; distinct responsibilities | Owner's current scope; component contracts below | Candidate, not release announcement; local component links |
| `#/components/kellogg` / tensor developer | Tensor system and mathematical operations; exact/float boundary | `packaging/kellogg-tensor/README.md` | Reference says NumPy, Python 3.11–3.14; not requalified here; pinned component reference |
| `#/components/chronus` / execution developer | iGPU/heterogeneous execution, not tensor mathematics | `docs/CHRONUS.md`, `isa/chronus1.md`, `abi/chronus1-abi.md` | No measured device/performance claim; links use ISA/ABI, **not mixed operational/mining documentation** |
| `#/components/ovid` / representation developer | Transformation/materialisation/lineage; no durable custody | `docs/OVID_INTERFACE_CONTRACT.md` | Exactness/domain/version distinctions retained; pinned transformation contract |
| `#/components/theseus` / custody developer | Durable custody and recovery; producers revalidate meaning | `docs/THESEUS_INTERFACE_CONTRACT.md` | Access contract and persistent environment required; pinned custody contract |
| `#/components/mcp` / integration developer | Existing `hyba_mcp.server`, `hyba-mcp-server`, line-oriented stdio JSON-RPC | Actual `hyba_mcp/server.py` compared with `README_MCP.md` | Source review only; no browser HTTP endpoint or install command invented |
| `#/guide` / evaluator | Distinguish access, installed artifacts, tests and support | Component contracts; `docs/STANDALONE_RELEASE_RC_PLAN.md`; `LICENSE` | No unexecuted first-use command advertised; license verification outstanding |
| unknown hash / any reader | Not part of candidate | Actual route allowlist | Not-found with recovery link; no routing into private app |

### MCP discrepancy — internal review, not public bundled content

Actual implemented tool table has **nine** names:
`lucas`, `fibonacci`, `cassini`, `zeckendorf`, `ladder_verify`,
`ladder_capacity`, `largest_feasible_tile`, `sha256d_verify`,
`scale_intelligence`. README lists eight, omitting `scale_intelligence`.
The server imports `chronus.mla1517.mining.pow` at module load; the scale tool
imports `Intelligence.lucas_scaler` on execution. Therefore an unmodified server
artifact cannot be assumed independent of private or out-of-tranche code.
No server rewrite, filtered replacement MCP implementation or wider product
publication was attempted. Owner/backend release work must establish a reviewed
distribution/dependency boundary and actual tools/list evidence. An internal
dependency may remain a dependency without becoming a launch product, but private
mining code must not be included by assumption.

### Registered MCP alternatives (not additional launch products)

The internal `.mcp.json` registers `hyba-mcp` as `python -m hyba_mcp.server`
with `PYTHONPATH=${REPO_ROOT}`, plus `exact-kernel` via
`mcp/exact_kernel/server.py` and experimental/internal-review `cogito` via
`mcp/cogito/server.py`. The exact-kernel source identifies version 0.2.1 and
lists seven tools (the first seven mathematical/tiling tools above); it imports
Chronus Lucas modules. Cogito identifies version 0.1.0 and imports the TOE
capability adapter. Neither was executed or promoted to a new launch product.
The manifest is explicitly internal registration, not a verified public client
configuration. Selection/distribution approval must account for these existing
surfaces rather than inventing a new MCP package or silently publishing all
registered servers. The public candidate describes only the inspected primary
server and withholds setup until that gate is closed.

### Licenses and brand

Repository `LICENSE`: BSD-3-Clause, PhiEnterprise, 2026.
Kellogg component README: MIT, HYBA Software Limited, 2026. This difference is
recorded, not interpreted as authority to choose a license for all components.
Inspect the exact approved artifact's legal files and dependency notices before
redistribution. No blanket open-source or registry-availability claim was made.

Brand reference uses canonical HYBA tokens. Approved master logo/font assets were
not present in `docs/brand` (only token CSS and style HTML). Text header/Georgia
and system font substitutions are documented; approved-lockup compliance is not
claimed. No other organisation's logo or invented hex mark was used.

## Validation executed

See `validation.log`, `isolation.json` and `browser/results.json` for exact
recorded results. Local environment: Node 24.22.1, npm 11.19.1, Linux, bundled
Chromium (exact version in browser results). Existing pinned Node 24.21.0 still
needs a target-version rerun.

- `cd frontend && npm ci`: PASS; 195 packages, one existing high-severity
  dependency advisory. Root/prefix installation initially failed in this
  staging environment; cwd installation resolved it without editing the lock.
- `npm run lint:developer`: PASS (strict tsc, including new build config/tests).
- `npm run test:developer`: **37 passed**, three test files, no skips.
- `npm run build:developer`: PASS (Vite 8.3.5 + generated-output inspection).
- `npm run test:developer:isolation`: PASS. Actual import of private App rejected;
  env and public-directory canaries excluded; injected output canary rejected;
  final production artifact reaudited with file SHA-256s.
- Browser production artifact: **16 route/viewport axe checks**, zero reported
  WCAG A/AA violations; eight routes at desktop and mobile, keyboard skip/route
  focus/history, filter/reset/no-match/escaped input, no console runtime errors,
  no external/API requests, no cookies/browser storage, real no-JavaScript
  fallback, CSP and private-path HTTP checks passed. This is not a manual
  screen-reader or all-browser certification.
- Genuine candidate PNGs: 16 route/viewport captures, two empty-search captures,
  one JavaScript-disabled capture. Images were visually inspected, and a short
  page footer/no-JavaScript fallback defect found during review was fixed before
  final capture. Artifact helper also captured the built HTML.
- Existing private lint/build attempts: **UNAVAILABLE AS QUALIFICATION**. They
  failed on missing retrieved modules/index in the partial staging tree. These
  are retrieval limitations, not attributed repository defects. Private source
  and existing script semantics are preserved; no live private regression or
  authenticated screenshot is claimed.
- Full repository, source/installed component, hardware, registry, history and
  release tests: NOT RUN. No mining or backend process was activated.

`npm audit` reported existing `body-parser <2.4.0`, high DoS advisory
`GHSA-27r3-jxmh-p828`, through the existing Express dependency. No Express server
is used by this frontend. It is outside the browser graph but remains a tooling
supply-chain issue; do not interpret a clean static bundle as dependency closure.
No unrelated dependency upgrade/removal was made without usage validation.

### Screenshots and before/after honesty

Candidate screenshot hashes and dimensions are in `screenshots.json`. PNGs are
retained in the session evidence archive and reproducible with the checked-in
QA script; they are not committed through the text-only source-writing tool.
No genuine runnable baseline screenshot was obtained from the incomplete
checkout. **No before screenshot is supplied or reconstructed from a mock**.
Capture the baseline and private journeys from a full authorised checkout to
close that acceptance item. Candidate screenshots are UI evidence, not product
execution evidence, and contain no private telemetry or actual credentials.

## Remaining issues, reproduction and closure criteria

| ID | Issue / reproduce or inspect | Closure criterion |
|---|---|---|
| F01 | Existing `frontend/src/main.tsx` imports private App + TURING; `npm run build` still emits private `dist/public` | Keep backwards compatibility; host/release owner explicitly selects only developer artifact and proves API/origin separation. Never deploy whole dist |
| F02 | `hyba_mcp/server.py`: nine tools vs README eight; private import at module load | Backend owner approves distribution/tool/dependency scope; clean install and tools/list/call runs on approved artifact, with no private code shipped; then add verified setup |
| F03 | Current UI source references require repository access; no approved standalone public destinations established | Owner provides/approves actual five-component destinations; resolve them as intended readers, update registry/matrix, retain response evidence |
| F04 | No installed component quick starts executed from complete source/approved artifacts | Execute approved first-use paths in supported environments, bind version/source and actual logs; add only verified instructions |
| F05 | Root BSD/component MIT statements differ; master assets absent | Owner/legal verifies per-artifact licenses/notices and approved lockup/font use; replace text-only substitute, rerun visual/a11y checks |
| F06 | Partial retrieval means private lint/build/regressions and before screenshots unavailable | Full authenticated checkout; run unchanged lint/test/build and non-activating private regression journeys; genuine baseline desktop/mobile captures; no mining starts |
| F07 | `.github/workflows/azure-staticwebapp.yml` uploads on PR events; azure-package live smoke starts operator journeys | This commit uses `[skip ci]` to suppress push/pull_request Actions (the inspected label-only pull_request_target workflow may still label the PR). Do not clear skip or rerun blanket CI before approval/safe-only job selection. Confirm no deploy/live-smoke occurred; explicitly run build-only validation when authorised |
| F08 | Current repository contains private mining material/history and unreviewed artifacts | Dedicated tracked-file, history, artifact/secret audit; identify any exact rotation/remediation obligations. No visibility change/history rewrite without approval; bundle audit alone cannot close this |
| F09 | Existing body-parser high advisory; exact Node pin not exercised | Verify transitive patch/Express usage in a full checkout, reviewed lock update if warranted; npm audit plus original regressions; run candidate checks on pinned Node |
| F10 | Website shared-file coordination proposed, not acknowledged | Website implementer accepts this single entry, ownership and source matrix before shared-file edits; no second site and no excluded-product work |

## Publication checklist

Completed: implemented candidate; separate import graph/output; local tests/build;
real production browser/a11y checks; no backend dependency; output canaries;
source matrix; honest status/license/availability copy; reproducible QA.

Not completed: owner release destinations; component installs/examples;
MCP distribution closure; approved logo/legal assets; full private regression;
before captures; complete repo/history/secret audit; hosting/domain decisions;
collaborator acknowledgement; pinned-runtime and reviewed dependency closure.

No production metadata/domain, support commitment, pricing, performance,
compliance or registry publication was invented. The candidate is intentionally
noindex and has no canonical/sitemap for an unapproved domain. Existing hosting
workflows are not evidence of a correctly configured public deployment.
