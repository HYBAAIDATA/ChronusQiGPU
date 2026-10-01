# Security

This document records PYTHIA's production security controls. See
`docs/PRODUCTION_READINESS_AUDIT.md` for the audit that verified them.

## Secrets & credentials

- Stratum worker account and password come from environment variables only:
  `MLA1517_STRATUM_USER` / `MLA1517_STRATUM_PASSWORD` (canonical), or the
  `VIABTC_ACCOUNT` / `BRAIINS_ACCOUNT` / `STRATUM_PASSWORD` aliases. There is no
  hardcoded default account; `mining/stratum_bridge.py` exits with an error if
  no worker is supplied.
- `main.py` auto-loads a repo-root `.env` (process env wins; `.env` fills gaps).
  `.env`, `.env.braiins`, `.env.viabtc` are gitignored; only `.env.example`
  templates are committed.
- `StratumIdentity` (see `chronus/mla1517_platform/python/startup_contract.py`)
  stores only `sha256(password)`; alias-conflict errors mask values `[:2]***`.
- `firebase-applet-config.json` contains a committed Firebase web apiKey that is
  unused by code. `firestore.rules` is default-deny + auth-required. Treat as
  flagged: rotate/revoke the key or remove the file.

## Pool transport

- TLS endpoints via `stratum+ssl://` / `stratum+tls://` schemes (always TLS), or
  `--tls` / `MLA1517_STRATUM_TLS=1` for bare `host:port`. `stratum+tcp://` is
  always plaintext. Unknown schemes are rejected. TLS uses
  `ssl.create_default_context()` (cert-verified).
- Failover is bounded: bounded reconnect backoff, no infinite retry.

## Live share submission gate

`is_live_submit_approved()` in `mining/stratum_bridge.py` requires ALL of:

- `HYBA_ENABLE_LIVE_SHARE_SUBMIT=="true"`
- `HYBA_LIVE_SHARE_APPROVAL_ID` non-empty
- `HYBA_AUTONOMOUS_EXTERNAL_ACTIONS=="true"`

Loopback hosts are permitted for tests only. Without the gate, submissions are
refused.

## Fail-closed invariants

- Missing MMIO/OpenCL device → unavailable/failed-closed, never a pass.
- Missing credentials → refused, never default credentials.
- Conflicting canonical/alias env values → `ConfigConflict`.
- Guardian dependency unavailable or raising → privileged routes answer
  `503 {"available": false, ...}`, never a dropped connection or silent allow
  (`control_api._guardian_preflight`).
- `PYTHIA_BITCOIN_NETWORK` set but node absent or reporting a different chain →
  startup aborts (`mining_runtime.assert_declared_chain`), never mines on an
  unverified network.
- Non-bool `mining.submit` result or rejected share → not reported as accepted.
- Proof of work is only real SHA256d; no synthetic acceptance, fixed hashrate,
  or theoretical multiplier is ever reported.
