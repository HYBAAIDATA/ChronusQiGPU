# HYBA Security Layer v0.1.0

Built on the three surfaces the AL HARAS Package Audit (20 Jul 2026) assessed as
real. Everything the audit called decorative or SIMULATED_INTERNAL is outside
the trust boundary.

## Trust boundary (IN)
| Module | Basis | Claim lane |
|---|---|---|
| `aead.py` | AEAD elevation (LANDED) | CLASSICAL_AEAD, not PQC |
| `audit_chain.py` | security_core.py (KEEP - real) | tamper-EVIDENT, not tamper-proof |
| `production_guard.py` | production_guard.py (KEEP - real) | fail-closed launch gate |
| `claims.py` | Round 3 claim discipline | enforces the lanes |
| `ci_claim_scan.py` | Round 3 CI recommendation | fatal, exit 1 |

## Outside the boundary (OUT)
honeypot_swarm, topological_counter_offensive, quantum_defense/*, the 1,748-line
QSS, and any PQC claim. `legacy.py` exists ONLY as a negative control and is not
exported from `__init__`.

## Run
    python3 tests/test_ipa_suite.py                      # 52/52
    python3 -m hyba_security.ci_claim_scan hyba_security # exit 0
    python3 -m hyba_security.ci_claim_scan tests/fixtures/known_bad_crypto.py # exit 1

The scanner is proven non-vacuous against a fixture reproducing S5 (XOR behind
an AES-256-GCM claim) and the Round 3 fake keypair.

## Known limits (stated, not hidden)
- Classical AEAD only. No post-quantum protection.
- Audit chain detects tampering; it does not prevent it. No external anchoring.
- Guard checks the environment it is given; it is not a runtime IDS.
