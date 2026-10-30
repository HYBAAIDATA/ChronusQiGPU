# HYBA Data Only — Mining Purge & Claim Closures

<aside>
🏛️

**Repo posture:** HYBA Data and supporting acts only.  

**Mining:** implementation, tests, CI, frontend, and product surfaces **removed**.  

**Method:** Implement → test → unblock. Elevate code to documentation.  

**Board:** Andre Taylor-Morris, sole shareholder & director, HYBA Software Ltd.

</aside>

---

## BLUF

The freeze tree is now a **HYBA Data control plane**. Mining is out. Sealed claims are closed in code where evidence allows; remaining INTERNAL claims stay gated until long-window or production seals exist. Curiosity without judgment; implement and test; not afraid to be wrong.

---

## Ethos (operating spirit)

| Guide | Line |
| --- | --- |
| Maths | Operationalised 2500 years of mathematics |
| Whitman | Be curious, not judgmental |
| Kipling | *If* — head under pressure |
| Invictus | Master of fate; captain of soul |
| Williamson | Our light, not our darkness, most scares us |
| Thunder | Volume from conviction |
| Stance | Not afraid to be wrong. Curious as fuck. |
| Method | Implement. Test. Elevate. Unblock when evidence holds. |

---

## Mining purge

| Action | Result |
| --- | --- |
| Removed `python_backend/pythia_mining` | Gone |
| Removed miners, stratum tests, pool configs, mining dashboards/docs/artifacts | ~199 path removals (manifest) |
| Rewrote HYBA Data honest quantum without mining deps | `hyba_data.quantum_honest` |
| Substrate internal mining bridge / routes | Removed / emptied |
| Master / platform / tiers / adaptive UI | Data-only posture |
| Manifest | `artifacts/hyba_data/MINING_PURGE_MANIFEST.json` |
| Posture file | `REPO_POSTURE.md` |

**Residual:** historical prose in some non-critical docs/workflows may still contain the word “mining”; product runtime paths for HYBA Data no longer implement or depend on mining.

---

## Sealed claim closures (implement → test → elevate)

| Claim | Action | Status |
| --- | --- | --- |
| TECH_M1_2_62 | Progressive φ-fold harness + `test_hash` | **BOUNDED sealed** (measured ~1.6× depth-2; depth-1 ~1.33×; doctrine target 2.62 still aspirational for full PULVINI kernel seal) |
| COMM_GAIN_SHARE | Metering invariant | **EXTERNAL unblocked** (fee only when measured) |
| TECH_MULTICLOUD_STRATEGY | AWS/Azure/GCP certificate stubs + runbook paths | **EXTERNAL unblocked** (proven still INTERNAL) |
| TECH_SELF_HEAL | Autonomic cycle evidence | **BOUNDED** |
| TECH_99999 | Availability pack method | **INTERNAL** (pack exists; long window required) |
| GTM_MINING_PROOF | Repo purge | **BANNED** — mining not in repo |

**Tests:** elevation 9/9 PASS · claim closures 6/6 PASS · `CLAIM_CLOSURES.json` self_test **true**

**Run:**

```bash
export PYTHONPATH=python_backend
python3 -m hyba_data.test_elevation_standard
python3 -m hyba_data.test_claim_closures
python3 -m hyba_data.claim_closures
```

---

## Related

- [HYBA Data — Code Elevation Pack (Engineering Standard)](HYBA%20Data%20%E2%80%94%20Code%20Elevation%20Pack%20(Engineering%20Stand%20080cf1c058b14a8692d9431695ed928f.md)
- [HYBA Data — Sealed Claims Register](HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md)
- [HYBA Data — Capabilities (Evidence-Tiered)](HYBA%20Data%20%E2%80%94%20Capabilities%20(Evidence-Tiered)%2031c54504aec9464eab78699130b7e654.md)
- [Style System (Authoritative)](Style%20System%20(Authoritative)%20969d7f5bd3a94f12b667b734e8041acb.md)