# Stratum V1 smoke

Offline accept round-trip and live framing check for the treasury mining path.

## Endianness

Both the smoke client and the fake pool compare digests with
`int.from_bytes(digest, "little")`. Sharing `"big"` on both sides is the
common-mode failure that lets a fake pool certify the client's own bug.

## Difficulty and search

Fake pool default is Bitcoin **difficulty 1** (`DIFF1`). Expected work is
~2³² SHA-256d evaluations. Chronus structured search (Zeckendorf/Galois) and
the QiGPU OpenCL kernel raise **throughput**; they do not reduce the oracle's
expected trial count. Fleet scale multiplies H/s further. `nbits` is harder
than the share target.

```bash
# Diff-1 fake pool + Chronus geometric search (needs PYTHONPATH=src)
python scripts/smoke/fake_pool.py --port 3333 &
MINING_BRAIINS_USER=smoke PYTHONPATH=src \
  python scripts/smoke/stratum_smoke.py --target fake --submit-share \
  --search geometric --share-seconds 600

# Optional CI micro-target (not Bitcoin diff1)
python scripts/smoke/fake_pool.py --port 3333 --difficulty 1e-7 &
MINING_BRAIINS_USER=smoke PYTHONPATH=src \
  python scripts/smoke/stratum_smoke.py --target fake --submit-share \
  --require-accept --search geometric
```

`--require-accept` requires `--submit-share`. `--target fake` forces the local
preset host (does not inherit a live `MINING_*_HOST`). TLS schemes
(`stratum+ssl` / `stratum+tls`) open a verified SSL socket; unknown schemes
are rejected. Cleartext Stratum requires `--allow-cleartext` unless the
**connected peer IP** is loopback (hostname spelling alone is not enough).
Mid-search `clean_jobs=True` advances work generation and aborts submit;
`set_difficulty` and non-clean notifies leave the selected job valid.

Transcripts land in `evidence/smoke/`.

CI regressions live in `tests/test_stratum_smoke.py` (pytest discovery under `tests/`).
