# Stratum V1 smoke

Offline accept round-trip and live framing check for the treasury mining path.

## Endianness

Both the smoke client and the fake pool compare digests with
`int.from_bytes(digest, "little")`. Sharing `"big"` on both sides is the
common-mode failure that lets a fake pool certify the client's own bug.

## Difficulty and search

Fake pool default is **difficulty `1/2**24`** (offline micro-target). Expected
hashes is `difficulty * 2^32` (~256 at the default). Bitcoin difficulty 1 is
~4e9 hashes and will not be found in 30s — error 23 is then the correct framing
result. Chronus structured search and QiGPU OpenCL raise **throughput**; they
do not change the SHA-256d oracle's expected trial count. `nbits` is harder
than the share target.

```bash
# Offline accept (default micro-difficulty)
python scripts/smoke/fake_pool.py --port 3333 --exit-after 30 &
MINING_BRAIINS_USER=smoke.worker PYTHONPATH=src \
  python scripts/smoke/stratum_smoke.py --target fake --submit-share --require-accept

# Bitcoin difficulty 1 (long search; framing may return error 23)
python scripts/smoke/fake_pool.py --port 3333 --difficulty 1 &
MINING_BRAIINS_USER=smoke.worker PYTHONPATH=src \
  python scripts/smoke/stratum_smoke.py --target fake --submit-share \
  --search geometric --share-seconds 600
```

`--require-accept` requires `--submit-share`. `--target fake` forces the local
preset host (does not inherit a live `MINING_*_HOST`). TLS schemes
(`stratum+ssl` / `stratum+tls`) open a verified SSL socket; unknown schemes
are rejected. Cleartext Stratum requires `--allow-cleartext` unless the
**connected peer IP** is loopback (full `127.0.0.0/8` / `::1`; hostname
spelling alone is not enough).
Mid-search `clean_jobs=True` advances work generation and aborts submit;
`set_difficulty` and non-clean notifies leave the selected job valid.

Transcripts land in `evidence/smoke/`.

CI regressions live in `tests/test_stratum_smoke.py` (pytest discovery under `tests/`).
