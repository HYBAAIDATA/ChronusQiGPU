# hyba-pythia-consumer

Consumer surface for the PYTHIA substrate — one installable package exposing
three tabs of the product:

- **Node** — honest hardware/platform census (chip, GPU backends, optional
  dependencies) plus control-API reachability. On Apple Silicon the census
  reports the device surface too: model family (MacBook, iMac, Mac Studio…),
  unified-memory GiB and the mapped offer tier (`pythia-node`,
  `pythia-node-large-memory` at ≥96 GiB).
- **Verify** — structural verification of substrate receipts: Zeckendorf
  certificates, non-adjacency masks, Cassini ledger rows, Lucas ladder anchors.
- **Intelligence** — pass-through status for a configured CIaaS endpoint
  (`PYTHIA_CIAAS_URL`); reports unavailable honestly when unconfigured.
- **Companion** — the iPhone surface: an installable PWA at `/companion` with
  a JavaScript port of the receipt verifier (BigInt + self-contained
  SHA-256, verdict-for-verdict parity with the Python contract, exercised
  under macOS JXA in `tests/test_companion.py`).

## Install

```bash
pip install hyba-pythia-consumer          # when published
python build_bundle.py && pip install dist/*.whl   # local build
```

The wheel is a **self-contained bundle**: `build_bundle.py` vendors the
sibling substrate sources (`aethel`/THESEUS, `hyba_db`/OVID,
`chronos_one_igpu`/iGPU) into the wheel because they are not yet published
distributions. Do not co-install this wheel with the singular sibling
wheels — the top-level namespaces would collide.

## Use

```bash
pythia census            # local hardware census (JSON, incl. device/offer tier)
pythia verify r.json     # structurally verify a receipt file
pythia console           # serve the three-tab console on http://127.0.0.1:8777
pythia console --lan     # also bind 0.0.0.0 and print the iPhone companion URL
```

## iPhone companion

`pythia console --lan` prints `http://<mac-ip>:8777/companion`. Open it on the
iPhone, then Share → Add to Home Screen. The companion verifies receipts
**on the iPhone itself** — the JS verifier computes the same canonical fold
as the Python contract (64-bit BigInt; `canonical_int` literals above 2^53
are rescued exactly at parse time). Verdicts are stored in a local wallet
(localStorage only — nothing leaves the device except the same-origin fetch
to the node's read-only `/api/status`).

Honest constraints: `--lan` has no auth — it exposes read-only census and
stateless receipt verification to anything on the local network, which is
why it is opt-in. The service worker (offline caching) registers only on
secure origins; over plain-LAN http iOS refuses it — the page still verifies
receipts client-side once loaded.

## macOS app

```bash
python build_app.py      # dist/PYTHIA.app — standalone runtime + bundled wheel
```

`build_app.py` embeds a python-build-standalone interpreter and installs the
wheel + deps into `Contents/Resources` — no Homebrew/system Python needed on
the target Mac. Builds are **unsigned**; signing (Developer ID) and
notarisation (`notarytool`) are owner-controlled steps for distribution.

## Honest boundaries

Receipt verification reports three distinct levels:

- **Structural** — required fields present and receipt invariants hold
  (token form, non-adjacency, producible coordinate masks).
- **Canonical binding** — the token is independently re-derived from
  `coordinate_masks` + `context_id` via the documented φ¹⁵/ZECK fold and
  matches `canonical_int`. Proves internal consistency under the published
  algorithm — anyone can compute the same fold, so this is **not**
  provenance.
- **Provenance authentication** — `unsupported`. No signature or
  key-distribution trust model exists yet; unsigned receipts are never
  reported as authenticated.
- The node census reports detected facts only; unavailable hardware and
  backends are reported as such, never stubbed.
- No mining is performed by this package.
