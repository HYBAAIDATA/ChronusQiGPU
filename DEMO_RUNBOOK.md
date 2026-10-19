# Demo Runbook — Chief of Staff Briefing (everything except mining)

> Untracked scratch file for the briefing. Safe to delete afterwards.
> All items marked ✅ were rehearsed live on this machine on 2026-10-16.

## 0. Start the stack (run ~2 min before the meeting)

```powershell
cd c:\Users\leonn\OneDrive\Desktop\PhiEnterprise-main
.\demo_boot.ps1
```

This serves the operator UI + control API at **http://127.0.0.1:3000** with **no
mining workers** (the execution-device gate stays closed by design).

Sanity check in a second terminal:

```powershell
Invoke-WebRequest http://127.0.0.1:3000/api/v1/healthz -UseBasicParsing
# expect: {"status": "ok", "schema_version": "chronus.mla1517.status/1", ...}  ✅
```

## 1. The offerings map (what "everything except mining" means)

| # | Offering | Where it shows | Backend |
|---|----------|----------------|---------|
| 1 | **Exact-math substrate** — Lucas/Cassini/Zeckendorf in BigInt, Q[√5] field arithmetic, closed-form Grover | UI tab **Algebra** | client-side (works even if backend dies) |
| 2 | **Intelligence layer** — 27-module orchestrator, self-test battery, AGI/ASI requirement scoring, memory, meta-evolution | UI tab **Intelligence** | live control API |
| 3 | **Enterprise multi-sector reasoning** — market tail-risk holonomy, energy thermodynamics, defense assurance, biotech resonance | named module in self-test report | `Intelligence` stack |
| 4 | **Sovereign security boundary (AL HARAS)** — signed denial receipts, subscription-gated privileged routes | curl demo (§3) + restricted Operations tab | control API |
| 5 | **Audit & evidence** — local verifiable checks, downloadable evidence pack, honesty invariants | UI tab **Audit** | client-side |
| 6 | **Search-manifold visualization** — Poincaré–Cassini traversal, 32-face frame | UI tab **Manifold** | canvas |

Skip **Observability** — it is pool/execution telemetry (mining-adjacent).

## 2. Demo script (~15 min, in this order)

1. **Algebra tab** (`#/algebra`) — drag the Lucas slider; Cassini identity
   re-proves itself live at every n; Grover hits Pr = 1 in one iteration.
   Talking point: *quantum transformations are exact mathematics, computed
   here with BigInt — no simulation, no approximation.*
2. **Intelligence tab** (`#/intelligence`) — click **run self-test**. The
   browser prompts for the operator credential: type `demo-key`. The battery
   runs in ~2 s and reports **13/13 PASS**, including the AGI/ASI verdict
   panel (GWT and Free Energy met; Penrose Orch-OR and IIT not met — the
   system scores itself honestly, it does not grade itself on a curve).
3. **Manifold tab** (`#/manifold`) — animated Poincaré–Cassini frame.
   Talking point: the traversal heuristic is a *search-order* over the
   pre-image domain; the panel is labelled "simulated" and never claims a
   SHA-256 shortcut.
4. **Audit tab** (`#/audit`) — N/N local checks pass; click **download
   evidence pack** to hand him a machine-readable JSON receipt of the run.
5. **Security boundary** (terminal, 30 s) — see §3.
6. **Operations tab** (10 s) — deliberately show the "Mining dashboard
   unavailable" panel: no mining surface renders without a control-plane
   entitlement. Fail-closed is the product, not an accident.

## 3. Security denial-ladder demo (terminal, while UI is open)

```powershell
# 1. no identity -> 400 signed boundary-denial receipt  ✅ verified
Invoke-WebRequest http://127.0.0.1:3000/api/v1/security/status -UseBasicParsing
```

Talking point: privileged namespaces (`/api/v1/security|toe|quantum|admin|…/`)
are mediated by a signed guardian boundary — every denial is a receipt with an
`evidence_id` and `payload_hash`. Escalation ladder: no tenant/actor → **400**,
no subscription token → **402**, malformed token → **403**, valid token →
allowed.

## 4. Verified today (2026-10-16, port 3111 rehearsal)

- ✅ `GET /` serves the built operator UI (fresh `dist/public`)
- ✅ `GET /api/v1/healthz` → 200 `status: ok`
- ✅ `GET /api/v1/intelligence/status` → 200 (orchestrator wiring 45-module
  registry, EUCLID cognition authority boundary)
- ✅ `GET /api/v1/intelligence/selftest|/agentic/status|/intelligence/maintenance|
  /intelligence/engineer/status` → 200
- ✅ `POST /api/v1/intelligence/selftest` (Bearer demo-key) → runs, ~2 s
- ✅ `GET /api/v1/security/status` → 400 signed `TENANT_AND_ACTOR_REQUIRED`
  denial receipt

## 5. Fixed defect (why the self-test now says 13/13)

`Intelligence/self_test.py:427` called `extended_nonce_schedule(10_000,
seed=42)` and asserted the result was ≤ 1000 entries. That held against the
TUQC variant (`cap=1000` default) but not the platform `turing_core`
(`cap=None` default → full 10 000-window), so the check failed whenever the
control plane's PYTHONPATH resolved `turing_core` to the platform module —
12/13 with a spurious `extended_algebra` failure. Fix: pass `cap=1000`
explicitly (accepted by both variants, matches the invariant asserted in
`pythia_turing_math.py:649` and TUQC `core.py:702`). Verified: **OVERALL: PASS**.

## 6. Caveats & recovery

- **Self-test button prompts for a credential** — enter `demo-key` (the
  `EUCLID_ADMIN_API_KEY` from `demo_boot.ps1`). Cancelling is remembered for
  the session; refresh the page to be re-prompted.
- **Manifold cursor stays at face 00/32** — no mining workers run, so the
  attempt counter is 0. Honest, not broken.
- **If the backend dies**, Algebra/Manifold/Audit still render (client-side);
  only Intelligence goes blank. Restart with `.\demo_boot.ps1`.
- **CLI fallback** for the self-test story:

  ```powershell
  $env:PYTHONPATH="$PWD;$PWD\chronus\mla1517_platform\python"
  python -X utf8 -m Intelligence.self_test
  # tail: OVERALL: PASS
  ```
