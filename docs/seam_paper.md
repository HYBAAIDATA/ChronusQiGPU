# The Seam: A Capability-Declared, Attested, Thermodynamic Device Abstraction

## Abstract

The Seam is a contract between substrate and silicon. Invariants are either computationally checked, modeled with sourced constants, or named as gaps with a path and a cost. There is no third state.

## 1. Introduction

Every system that talks to silicon lies about what the silicon can do. The seam measures what is there, declares what is not, and fails closed when it cannot deliver.

## 2–4. Axioms, layers, invariants

See `chronus/seam/axioms.py` and `standard/seam_standard.toml`.

## 5. Proofs

Algebraic claims are executed in `standard/check_invariants.py`. A Lean 4 kernel model of the Python seam is a declared partnership gap, not a silent sorry.

## 6. Thermodynamic model

`thermo/model.py`. Sources: CODATA 2018, Sandia 2LAL 2002, Younis & Knight 1993, Lincoln Lab AQFP. Each model has a falsification test.

## 7. Benchmarks

`bench/seam_bench.py` on the host reference. Discrete-GPU silicon numbers remain a hardware gap until measured.

## 8. Gaps

- K5 ZK attestation — research, ~90 days
- ASIC1 synthesis — hardware, ~1 year
- Q3 TLA+ in CI — ~14 days
- Lean kernel checking — partnership

## 9. Standard

Levels: minimal, core, hash, extended, full. Third parties run `conformance/tests/conformance.py`.

## 10. Conclusion

The certificate is the collapse. Claimed level and proved level are both published.
