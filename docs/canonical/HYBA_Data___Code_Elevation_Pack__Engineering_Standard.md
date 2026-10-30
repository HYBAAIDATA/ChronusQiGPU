# HYBA Data — Code Elevation Pack (Engineering Standard)

<aside>
🏛️

**Rule:** The code must always be elevated to meet documentation.  

**Company:** HYBA Data · **Parent:** HYBA Software Ltd  

**Board:** Andre Taylor-Morris (sole shareholder & director)  

**Status:** Elevation **complete for engineering seals** — elevation 9/9 · capability 7/7 · master **OK**  

**Artifacts:** `CODE_ELEVATION_REPORT.json` · `CAPABILITY_ELEVATION_CLOSURE.json` · `M1_SEAL.json` · `PILOT_TELEMETRY_MEASUREMENT.json`

</aside>

---

## BLUF

We do **not** kick the can. Code was raised to match sealed capabilities: **M1 harness hash sealed**, **pilot telemetry → savings metering wired**, **online-gated Salamander**, **named multi-cloud runbooks**, **availability method pack**, **learn-to-learn with φ-fold memory**, claim lanes **RESTRICTED** (not banned). Residual open items are **human/production** (T3 customer, live multi-cloud PROVEN, long-window 99.999%, brand craft) — not deferred engineering.

---

## What shipped (code)

| Module | Path | Documentation it elevates to |
| --- | --- | --- |
| Sealed claims register | `hyba_data/sealed_claims.py` | [HYBA Data — Sealed Claims Register](HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md) |
| Sealed metric card | `hyba_data/sealed_metric_card.py` | [HYBA Data — Capabilities (Evidence-Tiered)](HYBA%20Data%20%E2%80%94%20Capabilities%20(Evidence-Tiered)%2031c54504aec9464eab78699130b7e654.md) metric card |
| Data-class gate | `hyba_data/data_class_gate.py` | Structured-only PULVINI claims |
| Savings metering | `hyba_data/savings_metering.py` | [HYBA Data — Pilot Measurement Protocol](HYBA%20Data%20%E2%80%94%20Pilot%20Measurement%20Protocol%209c56caf52be040a28f37da830164758e.md) formula |
| Elevation report | `hyba_data/elevation.py` | Full self-test + artifact |
| Tests | `hyba_data/test_elevation_standard.py` | Engineering standard |

**Wiring:** exported from `hyba_data/__init__.py`; included in `hyba_data/master.py` report under `elevation`.

---

## Behaviours enforced in code

1. **Claim lanes** — EXTERNAL / BOUNDED / INTERNAL / **RESTRICTED** (no permanent “banned”; implement → elevate).  
2. **M1 (~2.62×)** **BOUNDED with sealed test_hash** + max_error; **M2/M3** INTERNAL.  
3. **Universal compression** → **RESTRICTED** until elevated scope.  
4. **Data-class gate** — structured/φ-pattern eligible; noise rejected for external claims.  
5. **Savings formula** + **pilot telemetry wire** — fee **0 if unmeasured**.  
6. **INTERNAL multipliers** (6.94× / 7.155×) blocked unmeasured.  
7. **Copy gate** — restricted external phrases.  
8. **Salamander** heal/optimize **only when system ONLINE**.  
9. **Learn-to-learn** — web research → φ-fold memory → apply.  
10. **Mining** not Data GTM proof.

---

## How to run

```bash
cd HYBA_INTELLIGENCE_DEPLOY
export PYTHONPATH=python_backend
python3 -m hyba_data.test_elevation_standard   # 9 tests
python3 -m hyba_data.elevation                 # writes CODE_ELEVATION_REPORT.json
```

**Result (this session):** `failed=0 total=9` · `elevation_self_test_passed: true` · `status: ELEVATION_MODULES_ACTIVE`

---

## Elevation layer — closed vs residual

| Seal | Status |
| --- | --- |
| M1 production **test hash** in metric card | **CLOSED** — BOUNDED harness sealed |
| Telemetry → savings metering | **CLOSED** — `pilot_telemetry.py` (T2 hermetic; T3 = customer) |
| Named multi-cloud **runbooks** | **CLOSED** — AWS/Azure/GCP |
| Availability **method** pack | **CLOSED INTERNAL** — long-window EXTERNAL still needs production window |
| Multi-cloud **PROVEN** live cert | **Residual production** — cannot invent live clusters |
| T3 customer seal | **Residual commercial** — requires named customer |

### Modules (this elevation)

| Module | Path |
| --- | --- |
| Pilot telemetry | `hyba_data/pilot_telemetry.py` |
| System online gate | `hyba_data/system_runtime.py` |
| Learn-to-learn | `hyba_data/learn_to_learn.py` |
| Capability tests | `hyba_data/test_capability_elevation.py` |
| Runbooks | `runbooks/{aws,azure,gcp}/HYBA_DATA_PILOT.md` |
| Status | `doctrine_execution/CAPABILITY_ELEVATION_STATUS.md` |

---

## Engineering standard (operating law)

| Principle | Practice |
| --- | --- |
| Docs do not outrun code externally | Gates block unsealed claims |
| Elevate code first | Prefer raising tests/evidence over diluting doctrine |
| If code lags | Claim stays INTERNAL |
| Ship bar | Code + docs meet at HYBA standard |

---

## Related

- [HYBA Data — Sealed Claims Register](HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md)
- [HYBA Data — Marketing Master (External-Ready)](HYBA%20Data%20%E2%80%94%20Marketing%20Master%20(External-Ready)%202dd867f3c9674fe99353a4ab21ef67f5.md)
- [HYBA Data — Capabilities (Evidence-Tiered)](HYBA%20Data%20%E2%80%94%20Capabilities%20(Evidence-Tiered)%2031c54504aec9464eab78699130b7e654.md)
- [HYBA Data — Pilot Measurement Protocol](HYBA%20Data%20%E2%80%94%20Pilot%20Measurement%20Protocol%209c56caf52be040a28f37da830164758e.md)
- [Style System (Authoritative)](Style%20System%20(Authoritative)%20969d7f5bd3a94f12b667b734e8041acb.md)