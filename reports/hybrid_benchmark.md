# Hybrid substrate benchmark — raw numbers

Generated: 2026-09-29 14:36:02 UTC
Corpus (negative control): DETERMINISTIC SYNTHETIC (sha256-derived, fixed seed) | n=4 | target=2^252 | nonce_space=4096
Corpus (positive control): DETERMINISTIC SYNTHETIC (sha256-derived, fixed seed) | n=4 | target=2^240 | nonce_space=4096

## Negative control (easy target — no traversal can show advantage)

| config | completed | skipped | found_rate | mean probe idx | median | p95 | total hashes | wall s |
|---|---|---|---|---|---|---|---|---|
| gpu_only | 4 | 0 | 1.0 | 15.5 | 19.0 | 20.7 | 16384 | 1.578 |
| asic_only | 0 | 4 | n/a | n/a | n/a | nan | 0 | 0.000 |
| hybrid_even | 4 | 0 | 1.0 | 15.5 | 19.0 | 20.7 | 16384 | 1.547 |
| hybrid_lucas | 4 | 0 | 1.0 | 15.5 | 19.0 | 20.7 | 72 | 1.563 |

## Positive control (harder target — signal would be visible here)

| config | completed | skipped | found_rate | mean probe idx | median | p95 | total hashes | wall s |
|---|---|---|---|---|---|---|---|---|
| gpu_only | 4 | 0 | 0.2 | 1,050.0 | 1050 | 1,050.0 | 16384 | 1.610 |
| asic_only | 0 | 4 | n/a | n/a | n/a | nan | 0 | 0.000 |
| hybrid_even | 4 | 0 | 0.2 | 1,050.0 | 1050 | 1,050.0 | 16384 | 1.578 |
| hybrid_lucas | 4 | 0 | 0.2 | 1,050.0 | 1050 | 1,050.0 | 13852 | 1.532 |

## Paired differences (95% bootstrap CI, lucas − baseline)

| comparison | control | CI low | CI high | contains zero |
|---|---|---|---|---|
| lucas − gpu_only | negative | 0.0 | 0.0 | True |
| lucas − even split | negative | 0.0 | 0.0 | True |
| lucas − gpu_only | positive | 0.0 | 0.0 | True |
| lucas − even split | positive | 0.0 | 0.0 | True |

harness_trustworthy (negative CI contains zero): **True**

The paired-difference metric is *winner probe index*: the winner's
position in the logical traversal order. This is the only metric
comparable across configs, because physical work is bounded below
by launch granularity (a single launch computes its whole window
even when the winner is early). `total hashes` reports the
physical-cost metric separately: digests actually executed on
device, including hashes burned by windows later cancelled.
