# Canonical console journeys

Status: implemented console candidate; production/publication HOLD. This is the mining console, not the whole HYBA enterprise portfolio. Mining remains an optional funding workload. No Node service is introduced.

## Authority and transport

Static React → `main.py` → `chronus/mla1517_platform/python/control_api.py`. `src/api/main` is the separate EUCLID gateway; it is not substituted for the canonical MLA1517 control service. The console does not infer EUCLID availability from an MLA1517 HTTP response.

`useConsole` checks `GET /api/v1/control/session` immediately and every 30 seconds, then polls `GET /api/v1/mla1517/status` every 5 seconds only for a server-confirmed CEO principal. Operator authentication uses a Secure HttpOnly cookie from POST `/api/auth/login`; the browser must not require an operator key or compare the authenticated principal with stale storage. Subscription credentials remain a separate tab-session boundary. Requests have a 10-second deadline, stale-response epoch guards and noninteractive polling. A failure clears snapshots; it never keeps a stale green verdict. A server role change may take the session-check interval to be observed; status 401/403 revokes immediately on that response. This is not push revocation.

Mining evidence remains a separate request at the same parent cadence: `GET /api/v1/mining/evidence`. CEO proof uses the authenticated HttpOnly session; AL HARAS independently receives the subscription bearer and X-HYBA tenant/actor headers. A CEO role is not a subscription grant. The aggregate does not embed guardian-protected mining evidence.

## CEO golden path

| Step / route | Source / action | Entitlement | Fail-closed UI |
|---|---|---|---|
| Land, any `#/<view>` | session endpoint above | principal + server role `ceo` | No mining requests/panels; access reason visible |
| Authenticate, Control session | principal + credential POST to `/api/auth/login`, then cookie-based session check | role comes from server map, never key possession alone | Refused/unknown identity remains restricted |
| Optional evidence subscription | tenant/actor/subscription form | AL HARAS validates independently | Evidence unavailable; no invented receipt |
| `#/operations` readiness | status `ready_to_mine.ready/reason` | CEO read | Missing verdict = not reported; offline = Control API offline |
| Operations terminal | status stratum/runtime/workers/device + console owner sections | CEO read; mutations retain server/guardian checks | Absent data = not reported; controls disabled offline/config absent |
| Operations actions | existing config and supervised-run endpoints in WIRING.md | backend mutation/guardian authority | Error surfaced; next canonical poll updates read state, no optimistic success |
| `#/observability` | status.console.telemetry + fabric | CEO read | Empty source or unavailable marker; no generated telemetry |
| `#/algebra` | status.console.verification + selftest | CEO read | No local theorem score or pass inference |
| `#/intelligence` | status.console.intelligence + cognition | CEO read | No locally synthesized confidence/cognition |
| `#/manifold` | status.console.fabric + agentic | CEO read | Backend document lens, no simulated particle topology |
| `#/audit` | status.console.audit | CEO read (not certified tenant export) | Raw backend records can be inspected; tenant-scoped export disabled until contract exists |
| Sign out / revoke / outage | credential event, session verdict, fetch failure/deadline | none until reauthorized | Snapshots/receipts cleared; late responses ignored; no stale green |

The session and source status remain visible on all routes. Hash links are keyboard-accessible, active route has aria-current, and navigation scrolls within its own region on narrow screens. Loading, missing, error and denied states are explicit. No separate local Audit.runAudit or animated Manifold is in the live App import graph. Historical reference/test files are retained; TURING's separate application is not rewritten.

## Other requested journeys: policy gaps are explicit

| Persona | Current server policy and console | Required enterprise journey | Qualification |
|---|---|---|---|
| Operator | Existing server role `operator`; no CEO mining entitlement; this mining console is restricted | Non-mining Operations workspace without Stratum on separately authorized endpoints | NOT IMPLEMENTED in this tranche; must not expose mining to approximate it |
| Analyst | No analyst role in inspected control role enum | Intelligence/Manifold read-only with non-mining sources | UNAVAILABLE until server policy + API + isolation tests |
| Auditor | No auditor role / tenant-export contract in inspected source | Authorized tenant-scoped audit export only | UNAVAILABLE; no client-invented role or global export masquerading as tenant data |

## Truth and release limits

- Frontend renders backend verdicts and supplied receipts. SHA256d/target validation and pool acknowledgement retain mining acceptance authority. No frontend score is a share acceptance.
- Zero supplied by a backend is retained; missing values are not zero. Historical accepted-share counters do not mark the current submission accepted.
- Source/timestamp labels are provenance context, not per-number cryptographic receipts. The inspected status schema does not supply a digest/evidence class for every number. The optional five-field receipt renderer is NOT proof that the producer publishes qualified receipts.
- The `console` extension is not a transactionally atomic cross-owner snapshot. Each owner retains its own evidence semantics and timestamps.
- API shape tests use actual current-source functions extracted with AST and deterministic injected owner fixtures. They do not boot the complete service. Browser screenshots are visibly labelled test fixtures, not live mining/device proof.
- Full nested owner schemas, complete service/caller compatibility, deployed identity/TLS/CORS, live hardware, independent subscription integration, tenant stress, and product/API sign-offs remain unqualified. Production/publication HOLD remains.

## Cookie-session closeout regression

Login/logout and explicit subscription changes invalidate all prior snapshots and abort old requests even when all JavaScript operator identity fields remain empty. A change during an outstanding entitlement check queues a fresh check; late results cannot restore the old state. A server-confirmed change of CEO principal clears the previous principal's snapshots. Refresh rechecks entitlement before polling. The rendered login/logout journey and denial/race coverage use transport fixtures: they qualify client behavior, not deployed identity/TLS/CORS. See `docs/PRODUCTION_CLOSEOUT.md` and the retained evidence.
