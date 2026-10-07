# Product release status — pick up here

Last updated 7 October 2026 (branch `feat/kellogg-turing-products`).

HYBA Software Limited ships each subsystem as its own product. Every first
public release is **1.0.0**. Order: **Kellogg first, then TURING**, then the
remaining products one at a time (OVID, THESEUS, CHRONUS, EUCLID, ...).

## Kellogg — `kellogg-tensor` 1.0.0 (release candidate)

Exact tensor networks over Q(zeta_8): custody-backed MPS/MPO/TT, certificates,
exact channels and Fisher information, surface code, golden substrate, TT-SVD,
DMRG. Source `kellogg/`; packaging `packaging/kellogg-tensor/`.

Done and evidenced:
- Standalone: imports only stdlib + numpy; Aethel custody bound by protocol.
- `kellogg.spec.REGISTRY` (88 items) verifies; every canonical-spec item has a
  status (EXACT / FLOAT / CORRECTED / REFUTED / DELEGATED / RESEARCH / NOT_STARTED).
- `tests/test_kellogg_product.py` and the Kellogg-touching repo tests pass.
- All 15 correctness benchmarks pass on the full run; cross-version digest
  identical on CPython 3.11.17, 3.12.10, 3.13.16 and 3.14.2.
- Wheel built and verified in a clean venv (no sibling product loaded) on 3.12.

Remaining:
1. Full benchmark run to completion with results committed to
   `benchmarks/tensor/results/` — the cost grids now have hard wall-clock
   limits (`python -m benchmarks.tensor.run_all`; set `KELLOGG_BENCH_PYTHONS`
   to the 3.11/3.13/3.14 interpreters for the cross-version check).
2. Rebuild the 1.0.0 wheel (`python packaging/kellogg-tensor/build_and_verify.py`)
   and run `packaging/verify_release_candidates.py` on 3.11, 3.12, 3.13, 3.14.
3. Owner actions for PyPI and GitHub billing: `packaging/PUBLISHING.md`.

## TURING — `turing-universal-quantum-computer` 1.0.0 (release candidate)

The virtual quantum computer. Source `turing_universal_quantum_computer/`;
wheel build `packaging/turing/build_wheel.py`.

Done:
- Consumes Kellogg (`exact_tensor`, `quantum_tensor`, `exact_field` are
  aliases; dependency `kellogg-tensor>=1.0`).
- New `mps_exact` backend + representation: Clifford+T at any width under a
  static Schmidt bound; the full pipeline (plan, execute, certify, THESEUS
  custody, replay) passes on GHZ_10000 + T + S. Console shows MPS registers.
- Corrections: surface code k=0 -> planar code k=1 with exact distance;
  dual frame was the mirror; forked entropy bug; `_replay` merge damage;
  missing import in `aethel/enterprise/system_relations.py`.
- Carve-out (owner decisions): capacity/ASIC/hashrate, thermodynamics and the
  mining execution plane moved to `mining/`; 15 duplicate modules and the
  unused kernels removed in favour of their owners (all checked: identical or
  older than the owner; TURING-only self-tests ported to
  `tests/test_aethel_hardened_substrate_selftests.py`).
- `product_registry.py` (every module with role, purpose, execution paths;
  carve-outs; corrections) and `benchmark.py` (correctness, cost, meta).
- Targeted verification after the carve-out: TURING product, boundary,
  release, MPS, surface-code, refusal, custody and certificate tests pass;
  repo tests for Mining, Aethel self-tests, system fabric, relations,
  pipeline, Kellogg and parity pass.

Remaining:
1. Full TURING suite (`cd turing_universal_quantum_computer && python -m pytest tests -q`,
   ~16 min) and full repo suite (`python -m pytest tests/ -q`, ~40 min; 19
   failures there pre-date this work and belong to other products).
2. TURING full benchmark run (`python -m turing_universal_quantum_computer.benchmark --out ...`).
3. Build the TURING wheel and verify it with the local Kellogg wheel on
   3.11-3.14 (`packaging/verify_release_candidates.py --kellogg ... --turing ...`).
4. Lean kernels in `turing_universal_quantum_computer/formal/` are unverified:
   CI cannot run (GitHub billing) and the local disk had < 1 GB free for the
   ~800 MB toolchain. The file also proves the 10 EH/s capacity floor, which is
   Mining's claim — split it when Lean runs again.
5. Residue kept by purpose (recorded in the registry, review with the owner):
   `pisot`/`hendrix`, the `lucas` kernel fork, `quantum_cuda`, `phi_vqc`,
   `midas_vqc`. The Chronus platform copy of TURING math
   (`chronus/mla1517_platform/python/pythia_turing_math.py`) still carries the
   mirror dodecahedron and orders mining work — fix in the Chronus/PYTHIA review.
6. Claim-audit lint is phrase-based; two paraphrases it misses are recorded
   in the `claim_boundary` benchmark (`known_lint_gaps`).

## CHRONUS — owner is pushing it

The owner is taking CHRONUS forward. This branch touches `chronus/` only to
repoint three imports made necessary by the TURING carve-out:
`pythia_authority.py` (`turing.search` -> `mining.search`, twice) and
`system_fabric.py` (`vqc` module -> `mining.scaled_execution`). Item 5's
`pythia_turing_math.py` mirror-frame fix is left for that work.

## Blockers needing the owner

- GitHub Actions does not start jobs: failed payment / spending limit
  (Settings -> Billing & plans of `QuantumPhiRedux`).
- PyPI: company account, email verification, 2FA, trusted publishers —
  exact steps in `packaging/PUBLISHING.md`. All four names are unregistered.
- Disk C: had ~1 GB free (238 GB used).

## Environment notes

- Extra interpreters used for evidence (uv / python-build-standalone) lived
  in the session scratchpad; uv also placed `python3.11.exe` / `python3.13.exe`
  shims in `C:\Users\andre\.local\bin` (not on PATH; safe to delete).
- `turing-universal-quantum-computer` is installed editable; after a version
  change run `pip install -e ./turing_universal_quantum_computer --no-deps`.
