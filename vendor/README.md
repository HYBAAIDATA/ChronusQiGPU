# Vendored reference implementations

## vendor/cgminer-3.7.2

cgminer v3.7.2 by Con Kolivas and contributors — the last release with GPU
(OpenCL) SHA-256d mining support and a complete Stratum V1 pool client.

- **Upstream:** https://github.com/ckolivas/cgminer (tag `v3.7.2`)
- **License:** GNU GPLv3 (see `cgminer-3.7.2/COPYING`); its OpenCL kernels
  derive from the public-domain poclbm/Phoenix kernels
- **Status here:** unmodified, **reference only** — it is not built, linked,
  or distributed as part of the Chronus package.

### Why it is here

Chronus implements its own MIT-licensed equivalents of the two components
this codebase is the canonical reference for:

| cgminer 3.7.2 (GPLv3, reference)      | Chronus adaptation (MIT)                          |
| ------------------------------------- | ------------------------------------------------- |
| `poclbm130302.cl`, `phatk121016.cl`   | `src/chronus/kernels/sha256d_search.cl`           |
| stratum client in `util.c`            | `src/chronus/execution/stratum.py`                |
| `ocl.c` device/queue management       | `src/chronus/execution/opencl_sha256d.py`         |

The Chronus modules are clean-room implementations of public standards
(FIPS 180-4 SHA-256, the Stratum V1 protocol as documented publicly) and are
cross-validated against `chronus.execution.asic_sha256` and known Bitcoin
block vectors. No cgminer code is copied into `src/`.
