# 00 — Authority Matrix

## Owners

### Ovid — transform only

- Owns fold/unfold and `ovid_transform_version`.
- Produces canonical working forms and content digests **before** custody write when used in composition.
- **Must not:** open journals, decide heal policy, bind devices, or enforce quotas beyond transform size guards owned by governance.

### Theseus (EnterpriseCustody) — custody only

- Owns durable envelopes under a single root: primary, replica, journal, generations, idempotency keys.
- Owns integrity checks (content digest) and authenticity verification (HMAC) at the storage boundary.
- **Must not:** redefine Ovid transforms, run Chronus kernels as a requirement for correct digests, or embed AL HARAS policy engines.

### Chronus — acceleration only

- Optional flag `chronus_accel=True` may select an accelerated encode path.
- **Invariant:** accelerated path digest **must equal** CPU path digest (`parity.assert_cpu_accel_parity`).
- Default path is CPU. Absence of Chronus is not a custody failure.

### Geodesic — outside

- `GeodesicHandoff` remains outside the custody substrate.
- Requests for geodesic when unavailable raise a **typed** error (`EngineUnavailable` / geodesic-unavailable class), not a silent null store.

### AL HARAS — security authority

- Optional `SecurityHook` adapter: `before_put` / `after_put` / `after_heal`.
- May **deny** (`before_put` → false/exception) and receive evidence events.
- Theseus does **not** absorb guardian rules; hooks only forward measured evidence and gate writes when the adapter says so.

## Non-absorption rules

1. No owner may silently perform another owner’s duty.
2. Policy denial is AL HARAS (or caller); custody records the denial outcome via hooks/telemetry only.
3. Transform version mismatches are Ovid/schema errors, not “best-effort decode.”
4. Accel is never required for correctness.
5. Geodesic/Intelligence remains EXTERNAL unless separately measured.

## Composition order

1. Schema + authenticity key material present.
2. Journal recover + replica heal on open.
3. Hooks attached (optional).
4. Consumers start only after custody reports ready.
5. On stop: halt consumers → flush journal → close root.
