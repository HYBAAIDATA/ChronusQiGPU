# 06 — Acceptance Test Matrix (A1–A20)

| ID | Statement | Lock |
| :--- | :--- | :--- |
| **A1** | put → get → restart/recover → get identical payload | restart recover |
| **A2** | corrupt replica → heal → get ok | heal |
| **A3** | all replicas bad → `UnrecoverableCustodyError` | fail-closed |
| **A4** | concurrent threads put/get without corruption | concurrency |
| **A5** | tampered MAC → `AuthenticityError` / reject | MAC |
| **A6** | unknown `format_version` → `SchemaVersionError` | schema |
| **A7** | quota exceed → `ResourceExhausted` | governance |
| **A8** | tenant A cannot read tenant B | isolation |
| **A9** | hook `before_put` deny → no durable write | hooks |
| **A10** | idempotency_key replay returns same generation | idempotency |
| **A11** | backup then restore directory → payloads match | backup |
| **A12** | `chronus_accel` off or absent — custody works; digest stable | no chronus mode |
| **A13** | geodesic unavailable → typed error, not silent success | geodesic typed |
| **A14** | telemetry unknown metric → `None` (never fabricate) | telemetry |
| **A15** | CPU vs accel parity helper holds for sample payloads | parity |
| **A16** | read_only mode rejects put/delete | read_only |
| **A17** | delete removes record; provenance retains event | delete |
| **A18** | journal incomplete tail dropped on recover | journal |
| **A19** | endurance light: 50 put/get/heal cycles; counters measured | endurance scoped |
| **A20** | claim boundary: single-root measured; not hyperscaler READY | claim scope |

Tests live in `tests/test_enterprise_custody_substrate.py` (A1–A19 style) plus capability bridge locks for A20.
