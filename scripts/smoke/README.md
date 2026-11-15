# Stratum V1 smoke

Offline accept round-trip and live framing check for the treasury mining path.

```bash
# Offline: fake pool (~256-hash share target) + smoke with --require-accept
python scripts/smoke/fake_pool.py --port 3333 &
MINING_BRAIINS_USER=smoke \
  python scripts/smoke/stratum_smoke.py --target fake --submit-share --require-accept
```

Both sides compare share digests with `int.from_bytes(digest, "little")` — the
same endianness on client and fake pool, so the pool cannot certify a shared bug.
Transcripts land in `evidence/smoke/`.

Live Braiins with `--submit-share` usually fails search then passes submit as
framing (`error 23`); use `--require-accept` only when a literal `true` is required.
