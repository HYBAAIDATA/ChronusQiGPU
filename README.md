# PYTHIA

**PYTHIA is HYBA's operational mining product.** Its singular function is to run the mining system, obtain honest device and pool measurements, sustain HYBA, and support Enterprise's route to market. Enterprise PRIME-DB, storage, treasury, and customer-product implementation are separate products and are not imported into PYTHIA.

## Runtime boundary

PYTHIA has a Python backend and a React/Vite frontend:

```text
React/Vite operator frontend
        ⇅  HTTP status/control requests
main.py → control_api.py
        ⇅
mla1517_platform_v3.4/python
  Python orchestration and exact reference
  C/C++ MMIO, transport, telemetry, persistence
  exact OpenCL payload
  negotiated Stratum coordinator
```

There is no Node/TypeScript backend in the canonical runtime. The frontend is a presentation layer; it does not own mining, proof checking, pool sockets, or hashrate claims.

## Entry points

```bash
# Operator API and built frontend
python3 main.py --host 0.0.0.0 --port 3000 --web-root dist/public

# Hardware miner; requires the actual MMIO device and pool credentials
PYTHONPATH=mla1517_platform_v3.4/python \\
  python3 mla1517_platform_v3.4/python/headless_miner.py \\
  --device /dev/uio0 \\
  --user <stratum-user.worker> \\
  --password x \\
  --submit

# Stratum TLS: stratum+ssl:// endpoints, or --tls / MLA1517_STRATUM_TLS=1 on bare host:port
```

The miner fails closed when the device, negotiated job, proof adapter, credentials, or explicit submission approval is absent. `main.py` is the control service; it does not fabricate an active mining result.

## Canonical structured mining path

The canonical mining package is `mla1517_platform_v3.4/python/mla1517/mining`:

- `geometry.py` defines the connected 32-lane M32 allocation and complete lane order.
- `lane.py` declares the structured M32 and flat exhaustive work contracts.
- `chooser.py` selects a declared order from observed job/candidate evidence and learns only from real pool responses.
- `solver.py` enumerates the selected lanes without overlap and checks every visited 80-byte header with real double-SHA256.
- `pow.py` owns compact-target decoding, header construction, SHA256d, and target comparison.
- `coordinator.py` composes the chooser with the real MMIO/vault/Stratum coordinator; a label never becomes a share.
- `verification.py` independently verifies observed block records against the supplied header template and target.

The M32/manifold layer is therefore a **structured search and work-allocation mechanism**. It is not treated as a cryptographic shortcut: only the negotiated SHA256d target can accept a share.

## Python intelligence and TOE boundary

TOE is a first-class top-level package (`toe/`), shipped in the distribution alongside `mla1517` and the `kellogg/` tensor substrate it consumes. `toe.bridge` exposes state tomography, trajectory propagation, causal analysis, causal-ladder processing, and algebraic-family detection over the Kellogg tensor. The tensor implementation lives only in `kellogg/`: the former `toe.quantum_tensor`/`toe.exact_tensor`/`toe.exact_field`/`toe.tensor_ml` and `Intelligence/quantum_tensor.py`/`Intelligence/exact_tensor.py` alias modules were retired — importing a retired path fails loudly rather than silently aliasing.

The canonical coordinator invokes TOE through `mla1517.mining.toe_adapter`: each observed vault record (real Stratum job + real hardware state) is analysed, and the resulting context feeds the `IntelligenceController` control-plane signals. This is advisory context, not a proof mechanism: when TOE is absent or incomplete the coordinator fails closed on that record and continues — and only the negotiated SHA256d target can accept a share.

The declared Lucas ladder is exactly `10, 12, 15, 18, 20, 31, 50, 76`. Device execution is accepted only when its result agrees with the exact reference and the strict hardware gate passes.

## Golden-stride ASIC-mode traversal

`kernels/bitcoin_sha256d.cl` ships `bitcoin_sha256d_gold`, an ASIC-style scan kernel: the device derives each probe nonce in-register as `nonce_i = (seed + i·GOLDEN_STRIDE) mod 2³²` with `GOLDEN_STRIDE = ⌊2³²/φ⌋ = 0x9E3779B9`, reuses the header midstate, reduces the earliest hit with `atomic_min`, and records hit probe-indices in a bounded hit FIFO.

- **Bijection is proved, not benchmarked.** `GOLDEN_STRIDE` is odd, so `gcd(stride, 2³²) = 1` and the walk is a permutation of the full nonce domain — the two-line proof is executed by `verify_golden_stride()` in `hyba/operating_model/lemma.py` and stated in `docs/lemma_golden_ordering.md`. The empirical uniqueness sweep in `tests/test_golden_stride.py` is a cross-check, not the proof.
- **Ordering only.** The φ-resonance ordering (`LEMMA_PHI_RESONANCE`, same doc) authorises `order_device_probe_walk`/`order_host_probe_walk` and nothing else; it is explicitly not a proof of quantum advantage or any Millennium problem. `use_ordering_lemma()` refuses unknown usages and non-φ strides.
- **FIFO depth is derived, not magic.** `GOLD_FIFO_DEPTH = fib(6) = 8` — drawn from the Lucas pool; the kernel `#define` must equal `BitcoinHasher.GOLD_FIFO_DEPTH` (a test asserts it).
- **Silicon gate.** `grind_target_gold()` on a host with an OpenCL device runs a self-check at init (first golden nonce at max target must match the hashlib digest) and reports `silicon_status()["device_run"]` as `PASS`. Without a device it stays `NOT_RUN` — the kernel is a hypothesis until silicon executes it, never `SUCCESS`-self-declared.
- **Calibration.** `scripts/brier_difficulty_sweep.py` drives the wired stack across a difficulty ladder and reports the self-model's Brier score for the quantum-stack emergence signal per difficulty (`reports/brier_difficulty_sweep.json`); it moves, and the movement is reported as measured.
- **Observable audit.** Every emitted observable is a stated measured statistic (see `QuantumStack.OBSERVABLE_DEFINITIONS`); the IIT-derived composite is emitted as `iit_composite`/`iit_composite_state` — named for what it computes.
- The adversarial live-run transcript (`hyba/operating_model/live_run.py`) exercises no-silicon, hard-target, FIFO-overflow, wrong-seed, and non-φ-stride injections; each must survive.

## Measurement contract

- Hashrate is emitted only from executed device work or accepted pool shares.
- A CPU run is never labelled iGPU execution.
- A Cassini seal or manifold invariant is internal correctness evidence, not Bitcoin proof-of-work.
- A pool share requires a live negotiated job, valid credentials, a complete algorithm-specific translation, and the pool's independent acknowledgement.
- Missing hardware, unsupported translation, overflow, stale job, torn state, or failed invariant is a fail-closed result.
- No synthetic pool acceptance, fixed hashrate, or theoretical multiplier is reported.

## Verification

```bash
python3 scripts/re_paper_gate.py
python3 -m pytest tests/ -x -q
python3 -m unittest discover -s mla1517_platform_v3.4/python

cd mla1517_platform_v3.4
python3 -m unittest discover
MLA1517_STRICT_HARDWARE_CI=1 MLA1517_GPU_BACKEND=opencl make test
```

A missing device must produce an unavailable/failed-closed gate. It must never be converted into a pass.

## Evidence boundary

The repository contains the canonical M32 structured scheduler, SHA256d proof boundary, MMIO-to-vault-to-Stratum path, measured chooser, Python TOE subsystem, and exact OpenCL contract. `docs/STRUCTURED_MINING_AUDIT.md` records which of those components are on the live call graph and which require an end-to-end behavioral test. `docs/PRODUCTION_READINESS_AUDIT.md` is the latest full-repo classification (production / experimental / test-only) with the executed test matrix.

Every named PYTHIA capability is an engineering requirement. If it is not present in the canonical Python path and verified by an executable test, it is an open implementation defect—not a simulated success and not silently reclassified as research.
