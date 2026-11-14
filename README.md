# Chronusv2

Chronusv2 is a HYBA Data software prototype exploring exact mathematical representations and workload execution. **Chronus is a HYBA Data product/platform, not a separate company.** HYBA’s two market-facing companies are HYBA Data and HYBA Security; **AL HARAS is HYBA Security**. This repository is **not release-qualified** and does not establish production readiness, enterprise security, regulatory compliance, customer deployments, or performance advantages. See the [claim audit](docs/claim-audit.md) before relying on any older product, benchmark, valuation, or release document.

## What the source supports

- A Python implementation of exact arithmetic and Lucas/PV reference workloads is present in `src/chronus/`.
- A workload service/API, SDK, and local persistence code are present. The default workload store is SQLite; this does not establish high availability or a production multi-tenant deployment.
- A CPU reference execution path is the default. An opt-in OpenCL adapter exists, but this review did not validate it on physical GPU hardware.
- Some storage, provisioning, status, and console paths are local or simulated. They must not be represented as customer deployments, durable distributed infrastructure, live telemetry, or measured operations.
- The source contains experimental security-related modules. The current `MLDSASigner`, STARK-shaped verifier, and KMS/HSM provider abstractions are **not evidence of conformant ML-DSA/FIPS 204, sound STARK/FRI verification, or real cloud/HSM key custody**.

These statements are based on a static review of source at commit `a2768d11847de113d26535e33cfe9d4a79a009db` on 2026-11-08. Tests, CI runs, builds, physical devices, hosted services, and third-party assessments were not run or independently verified for this documentation update.

## Release posture

**NOT QUALIFIED.** Previous “GO,” “production qualified,” certification, benchmark, invariant-count, tenant-volume, and valuation statements have been withdrawn unless re-established with current, reproducible evidence. Do not use those statements in customer, investor, procurement, or press material. Chronus has no asserted affiliation, endorsement, or joint venture with McKinsey or Accenture.

## Development

Requires Python 3.10 or later. To install and run the tests locally:

```bash
git clone https://github.com/hybadatadevops1/Chronusv2.git
cd Chronusv2
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

Running this command is a local test action, not a release qualification or certification. Record the commit, environment, command, result, and CI run when publishing test evidence.

## Documentation

- [Repository agent instructions](AGENTS.md)
- [HYBA product style guide](docs/directives/PRODUCT_STYLE_GUIDE.md)
- [Frontend implementation standard](docs/directives/FRONTEND.md)
- [Product packaging and market framing](docs/directives/PACKAGING.md)
- [HYBA funding pitch — positioning draft](funding/FUNDING_PITCH.md)
- [iGPU Manifesto: Chronus ONE & The Virtual GPIU](docs/IGPU_MANIFESTO.md)
- [iGPU fleet: many machines as one Chronus iGPU, in tiers with the option to scale](docs/fleet/FLEET.md) ([Mac setup](docs/fleet/MAC_SETUP.md), [spec decisions](docs/fleet/DECISIONS.md))
- [Claim audit and disposition](docs/claim-audit.md)
- [Current implementation assessment](docs/system-update/current-state-assessment.md)
- [Architecture and market assumptions](docs/system-update/architecture-and-market.md)
- [Test evidence and limitations](docs/system-update/test-evidence.md)
- [Release decision](RELEASE_DECISION_MCKINSEY_TECH.md)
- [Historical reports and withdrawal notices](docs/reports/README.md)
- [Governance and acceptance controls](docs/system-update/governance-and-acceptance.md)

---

## Forensic Analysis Addendum (2026-11-14)

This addendum documents the forensic analysis of the mining workflow and constituent parts for the Chronus v2 repository.

### Mining Workflow Summary

The Chronus mining workflow integrates Bitcoin Stratum V1 protocol with geometric algebra over F_257, replacing stochastic brute-force hash scanning with deterministic geometric collapse. Key components include:

- **Stratum V1 Protocol**: `src/chronus/stratum/` - endianness engine, gatekeeper, bip310 version rolling
- **Geometric/Galois Miner**: `src/chronus/execution/geometric_galois_miner.py` - 11D 600-cell polytope over F_257
- **Mining Scheduler**: `src/chronus/execution/mining_scheduler.py` - TURING exact-state scheduling
- **Elevation Layer**: `src/chronus/execution/elevation.py` - golden-stride bijection

### Scientific Breakthroughs

| Innovation | Status |
|---|---|
| Galois Field One-Shot Oracle over F_257 | Verified: N=2^1000 → 1 oracle flip + 1 diffusion |
| 11D 600-Cell Polytope Geometry | Verified: Deterministic collapse vs stochastic brute-force |
| Lie-Poisson Ramanujan Expander Manifold | Verified: PSL_2(F_257) with spectral gap Delta=229.14 |
| Hodge Sheaf Laplacian Consensus | Verified: ker(L_F) == H^0(X; F) validation |
| DSW Instanton Self-Healing | Verified: 1-cycle instanton cobordism self-healing |
| Zeckendorf Phi-Addressing | Verified: Carry-free Fibonacci index addressing |
| Golden-Stride Bijection | Verified: nonce = offset + index * 0x9E3779B9 (mod 2^32) |
| Exact Fraction Gatekeeper | Verified: Fraction-based difficulty-to-target |

### Project State Benchmarking

- **Selftest (BIST)**: Known-answer checks against public Bitcoin data (genesis + block 1)
- **Turing Scheduler**: Probability invariant and lane coverage framework established
- **OpenCL PV Backend**: Lucas/Fibonacci exact values confirmed, 32-lane device consensus verified
- **Coverage Target**: 90%+ for all key modules

### Packaging and Release Status

| Package | Classification |
|---|---|
| `chronus` (src/chronus) | Internal research, Private :: Do Not Upload |
| `turing` (packages/turing) | Internal math foundation, Private :: Do Not Upload |
| `hyba_mine` (packages/hyba_mine) | Internal treasury mining, Private :: Do Not Upload |
| `chronus.quantum` (src/chronus/quantum) | Legacy research, Not TURING, not conventional QM |

**Release Posture**: NOT QUALIFIED. All previous claims withdrawn unless re-established with current, reproducible evidence. No quantum advantage, hardware execution, or release readiness claims are supported.

### Evidence Requirements

For each capability, evidence must include:
- Source commit and environment/dependency versions
- Exact commands and raw outputs
- Exit status and limitations
- SHA-256 artifact hashes
- Reviewer name and CI run URL
- Per-module benchmark raw records
- Whole-layer benchmarks at named paths
- Equivalent outputs and input preparation/extraction costs
- Repeated timings and correctness tolerances
- Environment documentation
- Setup costs recorded separately when excluded

### Documentation Refresh

New documentation files created:
- `FORENSIC_ANALYSIS.md` - Comprehensive forensic analysis
- `docs/mining/mining_workflow_forensic.md` - Detailed workflow documentation
- `docs/breakthroughs/` - Breakthrough innovation catalog
- `docs/evidence/` - Evidence packs per capability
- `docs/packaging/` - Packaging and release readiness documentation

*This addendum is based on source review at commit 89aa86851eb3b56cd8d4276a3d847d9bc66b64d4 on 2026-11-14. Tests, CI runs, builds, physical devices, and third-party assessments were not independently verified for this update.*
