# Developer frontend — isolated candidate

A working, frontend-owned developer entry point for Kellogg, Chronus, Ovid,
Theseus and the existing MCP integration. This is a **candidate reference**, not
an announcement that packages, public repositories or support are available.
No backend service, credential, subscription or browser storage is used.

## Build and inspect

Use the repository's Node version (`.nvmrc`; existing frontend manifest pins
24.21.0). Local validation used Node 24.22.1 / npm 11.19.1 and recorded the
existing exact-engine warning; qualification on the pinned version is still due.
Run installation **inside** `frontend`: in this sandbox, npm 11.19.1's
`npm ci --prefix ...` failed with `Missing: frontend@0.1.0 from lock file`,
while `cd frontend && npm ci` succeeded against the unchanged lockfile.

```sh
cd frontend
npm ci
npm run check:developer
npm run test:developer:isolation
npm run serve:developer
# http://127.0.0.1:4173
```

`build:developer` emits only `dist/developer` at the repository root, then
runs the artifact policy. `serve:developer` serves that directory only,
with a no-network CSP, no-index headers, robots exclusion, nosniff, no-referrer,
no directory listing, no API and no history fallback for private paths.

The existing `build`, `dev`, `preview`, `lint` and `test:ts` commands are
unchanged and continue to concern the **private** frontend. `build:operator`
is an explicit alias for its existing build. Its `dist/public` name is historical:
**it is not a safe public release artifact**. Do not upload `dist/` wholesale.

## Browser acceptance

```sh
cd frontend/developer/qa
npm ci
npx playwright install chromium
npm test
# Or use an installed Chromium: CHROMIUM_PATH=/path/to/chromium npm test
```

Browser checks start a local static server on an ephemeral loopback port and
close it afterward. No backend is started. They exercise all eight routes at
1440×1000 and 390×844, axe WCAG A/AA checks, search/filter/reset/escaped input,
keyboard skip and route focus, history, no browser persistence, no external/API
requests, no-JavaScript fallback, CSP and private/static path rejection.
They write results and genuine screenshots under
`reports/frontend-developer/browser` at repository root.

Axe is an automated check, **not a screen-reader certification**. Keyboard checks
were exercised; assistive-technology and target-browser review remain separate.

## Structure and state

- `src/catalog.ts`: typed component responsibility/content registry; pinned
  reference URLs; explicit qualification limits. Not an API contract substitute.
- `src/routes.ts`: allowlisted static hash routes; unknown paths render not-found.
- `src/components/Primitives.tsx`: shared notice, state, badge and reference link.
- `src/styles/site.css`: shared layout and accessible interaction styling;
  imports the canonical repository brand tokens, not the private app stylesheet.
- `src/App.tsx`: shell, local component finder, component references, evaluation
  guide, not-found and render-error boundary.
- `scripts/`: static server, output policy/audit, adversarial isolation checks.
- `tests/`: scope, route, graph-boundary and artifact-policy tests.
- `qa/`: separately locked browser tooling. Not included in the production graph.

Loading, permission, service-error and stale backend states are not fabricated:
this candidate has no backend data lifecycle or account journey. A real
JavaScript-unavailable fallback, render-error boundary, empty search, unknown
route and MCP-unavailable setup state are provided. Any later service integration
must add typed owner contracts, permission/loading/error/stale states and real
integration execution evidence before being advertised.

## Public/private boundary

`vite.developer.config.ts` has a separate HTML root, no public-directory copy,
no API proxy, no public environment prefix and no source maps. Its load and
bundle hooks refuse modules outside developer source, installed dependencies,
the HTML entry and the one canonical token file. The negative build test actually
attempts to import the original private `src/App.tsx` and must fail. Environment,
public-directory and output-file canaries are also exercised.

The output audit checks generated HTML, JavaScript, CSS and manifest contents,
rejects source maps, unreviewed asset types, known private markers and common
secret signatures. This is **not** a complete secret scanner, dependency review,
Git-history audit or a claim that the whole repository is publication-safe.

## Visual identity

Canonical Oxford/midnight/primary blues and cream are consumed from
`docs/brand/hyba_tokens.css`. Georgia and system UI fonts are documented local
substitutes; no unlicensed font file or external font request is shipped.
`docs/brand` contains tokens and a style specimen, but no approved master-logo
asset. The text-only HYBA header is **not an approved master lockup**. Brand
approval/master-asset integration remains a publication gate. No hex or other
logo is invented.

## Shared ownership — website handoff

Use this entry point; do not create another public frontend.

Frontend ownership: build configuration, import/privacy policy, routes, reusable
primitives, tokens consumption, layout, accessibility and tests.
Website ownership proposal: source-backed public information architecture and
copy in `catalog.ts` and page sections in `App.tsx`, plus approved release links,
installation examples and metadata. Shared-file changes require coordination.
No website collaborator acknowledgement was received during this task: this is
a **proposed handoff**, not a claim that another agent agreed or implemented it.

Do not reuse `src/turing/PublicSite.tsx` for this release, import private UI
components, copy internal docs/assets, turn the private repository public or
advertise the excluded portfolio. No speculative dead-code deletion was made.

## Release and rollback

No hosting target/domain is established for this candidate. Existing Azure
Static Web Apps YAML still has generic root/API/build settings and deploys on
PR events; it was not repointed or dispatched. Node's loopback server above is a
validation server, not a claim of production hosting approval.

After owner approval, the host must serve **only** `dist/developer`, reproduce
the CSP/robots/no-referrer/nosniff behavior, keep the private API off that origin,
and validate direct/hash/subpath navigation. Keep noindex until approved public
URLs, legal copy and release destinations are verified. Do not invent canonical
URLs or a sitemap for an unknown domain. Hash routes work without rewriting
arbitrary request paths to a public or private SPA.

Retain the previous approved static artifact and host configuration before any
future deployment. Roll back to that artifact/configuration and verify headers,
hashes and routing; do not point a public host at `dist/public`. Nothing was
deployed by this change, so no deployment rollback was executed.

See `reports/frontend-developer/REVIEW.md` for the inventory, source matrix,
precise validation scope and unresolved release gates.
