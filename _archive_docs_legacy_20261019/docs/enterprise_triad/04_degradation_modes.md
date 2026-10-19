# 04 — Degradation Modes

| Mode | Trigger | Behavior | Typed signal |
| :--- | :--- | :--- | :--- |
| **OK** | Primary+replica+journal healthy | Full R/W | `health()["status"]=="ok"` |
| **DEGRADED_REPLICA** | One replica copy corrupt/missing | R/W; auto-heal attempted | `health()["degraded"]=True` |
| **RECOVERING** | Open-time journal replay | Mutations blocked until ready | readiness false |
| **READ_ONLY** | Operator flag or integrity quarantine | Gets allowed; puts/deletes fail | `ReadOnlyModeError` |
| **AUTH_FAIL** | MAC mismatch on read/heal | Record inaccessible | `AuthenticityError` |
| **UNRECOVERABLE** | All replicas bad | Store refuses record / may refuse root | `UnrecoverableCustodyError` |
| **QUOTA_HOLD** | Tenant bytes/records/payload exceed | Reject new puts | `ResourceExhausted` |
| **NO_CHRONUS** | Accel unavailable or disabled | CPU path only; digests unchanged | health note, not error |
| **GEODESIC_OUTSIDE** | Intelligence engine missing | Typed unavailable; custody unaffected | `EngineUnavailable` / geodesic typed |
| **HOOK_DENY** | AL HARAS before_put deny | No write | deny event + exception/False |

Fail-closed preference: when integrity and availability conflict, **refuse** rather than serve unverified bytes.
