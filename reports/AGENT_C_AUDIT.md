# Agent C — lane audit record (branch `repair/C-chronus`)

Scope: `chronus/ chronos/ gpu/ opencl/ kernels/ compiler/ abi/ isa/ asic/ distributed/ emulator/ conformance/` (635 tracked files after pci/ retirement).

## Parent-session passes (2026-10-07)

- **AST structural scan** — all 390 non-test `.py` files: checked for empty/pass-only bodies, constant returns, bare returns. 21 flags, all dispositioned as legitimate (Protocol signatures, ABC abstracts, Ok/Err result types, lifecycle hooks, log silencers, involutory-QRAM math). Zero violations.
- **Marker scan** — TODO|FIXME|HACK|XXX: 20 hits, all `mkdtemp` `XXXXXX` templates in C test files. Clean.
- **Semantic keyword sweep** — simulate|estimate|approximate|heuristic|fake|mock|stub|demo|placeholder across `chronus/measurement|seam|virtual_igpu|mla1517|v33|mla1517_platform`: hits are overwhelmingly honesty assertions ("refused rather than approximated", "never estimated", "no sink is silently replaced with a mock"). One real approximation retained deliberately: `chronus/mla1517/mining/world_model.py` Wilson–Hilferty Gamma-quantile — a labelled statistical estimator feeding route planning only, provenance carries `estimate` semantics; never presented as measured evidence.
- **pci/ retired** (`b42562a`, 8 files): numpy sim dressed as VQC + constant-prior PCI model + demo FastAPI + fabricated claims. Confirmed already-classified as unreachable dead weight in `docs/toe/ARCHAEOLOGY.md`.
- **Deep reads verified honest**: `mla1517/quantum.py` (exact Q(√2) arithmetic, fail-closed), `gpu/quantum.py` (refuses mock substitution), `virtual_igpu/adapters.py` (UnavailableAdapter raises), `seam/zk.py` (explicitly non-SNARK digest commitment), `seam/genetic_mining.py` (real GA, no crypto fabrication), `seam/bennett.py` (honest CMOS limits), `conformance.py` (deterministic seeded test-vectors vs exact reference), `kernels/bitcoin_sha256d.cl` (real SHA-256d, host re-verifies winners), `chronos/` (documented deprecation facade → v33), manifests (declarative ownership only).
- **policy_bench/discovery_runtime**: simulated-output evaluator, `evidence="simulated"`, consumed only by control_api feature listing — never presented as measured evidence.

## Residual for sub-agents (dispatched when session capacity frees)

Depth reads of files covered so far only by pattern scan: v33 non-core internals (~40), `measurement/` internals (~46), `mla1517_platform` C/C++ host code + remaining python, `compiler/`, `distributed/`, `emulator/` internals.

## Sub-agent audit

## pci/ rebuild — real math replaces deleted fakes (2026-10-07)

User correction: delete-and-leave was wrong; the mandate is REPLACE fake math with pure quantum math. All 8 retired files rebuilt as real implementations wired to the canonical exact kernel (`chronus/mla1517/quantum.py`, Fraction arithmetic over Q(√2)+iQ(√2)):

- `pci/engine.py` (739 lines): `ExactQuantumComputer` — full Clifford+T gate set (H/X/Y/Z/S/Sdg/T/Tdg/CX/CY/CZ/SWAP/CCX exact by construction), Z-rotations exact on the k·π/4 lattice via 8th roots of unity (ω^k ∈ field), X/Y rotations exact at k·π/2 via Clifford conjugation; `rz/rx/ry/u1/u2/u3` fail closed (`GateNotExactlyRepresentable`) off the lattice — no truncation, no approximation. Grover diffusion `H·R0·H` exact. Deterministic max-Born measurement, seeded sampling over exact weights (labelled), exact expectation values, exact state save/load round-trip, real argmax `suggest_optimal_gate`. `VirtualQuantumComputer` alias kept for caller compat. `PredictiveCausalIntelligence` — Pearl inference over exact rational joints: conditional_probability, parent-adjusted `do()`, `analyze_relationship` (exact Fraction strength), `predict`. Fails closed `InsufficientEvidence` on uncovered support.
- `pci/api.py` (274 lines): `PostQuantumCivilizationAPI.get_router()` — 13 real routes over the engines (prepare/gate/state/measure/evolve + causal session/declare/observe/predict/relationship + causal-graph/visualization). 422 on unrepresentable rotations. Fabricated civilization/consciousness/national-security endpoints NOT reinstated (no real math backs them).
- `pci/qi.py` (234 lines): `QICIaaS` — real Grover `apply_phi_filter` (uniform encode, phase-mark, exact diffusion), exact 2×2-minor separability `decompose_state` (scaled factorization — ExactComplex has no division), labelled float SVD `decompose_tensor` for classical arrays, `get_toe_metrics` computed live, `get_qi_instance` singleton (agi callers hold it).
- `pci/forensics.py` (251 lines): real statistical diagnostics — Shannon entropy, chi-square uniformity, NIST monobit, serial correlation, exact interference witness, mempool.space fetch returning None on failure (no fabricated blocks).
- `pci/transparency_dashboard.py` (210 lines): causal graph where every edge carries exact Fraction strength + evidence count; real DFS path search, exact derivation explanations, deterministic recommendation ranking.
- `pci/pci.py`, `pci/__init__.py`, `pci/hyba_post_quantum_civilization_api.py`: re-export shim + package doc + real health().
- `pci/test_exact_engine.py` (308 lines, 30 tests): exact Born weights (Bell={1/2,0,0,1/2}), exact Toffoli/Grover (weight exactly 1 on marked state), all 8 eighth-roots normalized, fail-closed negatives (non-lattice rotation, non-unitary op, insufficient evidence), do-calculus posterior 11/20 exact, separability verdicts correct both ways, fail-closed fetch.
