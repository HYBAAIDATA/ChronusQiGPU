# July 2026 HYBA/PULVINI Recovery Provenance

**Recovery audit date:** 4 October 2026  
**Recovered evidence date:** 24 July 2026  
**Repository:** `QuantumPhi2/PhiMiner`  
**Base audited:** `main` at `15c2f5ea350c30045ae301a595e8f61af19c0c18`

## Outcome

The preserved July implementation was already consolidated into the rebuilt repository. The recovery therefore does **not** copy the former `euclid.pythagoras.quantum.pulvini_enterprise` tree over newer code. Current modules remain canonical, and the July files remain provenance and capability evidence.

## Artifact custody

| Preserved artifact | SHA-256 | Disposition |
|---|---|---|
| `GEODESIC_TENSOR_ENGINE_20260724.zip` | `966ae765e76a516f9874d745f4f31e2560549b844388b85f044a1de1dc768398` | Original Geodesic baseline; superseded by the extended artifact for production consolidation. |
| `GEODESIC_TENSOR_ENGINE_EXTENDED_20260724.zip` | `43d4d3a39fd13fb525bf3acf0b822af1ef55c6b801616aeb9bf326a76dcfa44b` | Consolidated into the canonical Geodesic/Tensor/Chronus ownership split. |
| `PULVINI_V3_HERMES_COMPLETION_20260724.zip` | `a307f93ed32c1ba97ab6241b44f8789b16b33bab6f603e7bab1f9a0eef923277` | Consolidated into exact PULVINI, Geodesic, Tensor and Turing surfaces. |
| `HYBA_1000_QUBIT_VQC_20260724.zip` | `7b4ef03683de8bf03a189293bb72e4493c9a408c5722b38f4a1e2ca8f05e9038` | Consolidated into Turing's 1,000-qubit profile and bounded MIDAS VQC ranker. |

## Canonical mapping

| Preserved capability | Current canonical implementation | Recovery decision |
|---|---|---|
| Geodesic Tensor Engine, `MetricTensor`, `EnergyModel`, `PhiGPU`, `HybridGPU` | `python_backend/core_modules/geodesic_tensor_engine.py` | Current implementation retained; it preserves the July control surface while using exact repository-owned PULVINI semantics. |
| Exact fold/unfold custody | `python_backend/core_modules/math_folding.py` | Current exact transform retained instead of restoring the older floating-point authority. |
| Physical tensor/GPU execution | `chronus/tensor_compute.py`, `chronus/kernels/tensor_ops.cl`, `tensor/*` | Current Chronus/Tensor execution and provenance layers retained. |
| 1,000-logical-qubit machine | `turing_universal_quantum_computer/turing_universal_quantum_computer/phi_quantum_machine.py` | July facade combined with the stronger in-repository stabilizer implementation. |
| Discriminating 1,000-qubit verification | `turing_universal_quantum_computer/turing_universal_quantum_computer/phi_verification.py` | Current signed-Pauli verification retained; shot correlation remains diagnostic rather than proof. |
| 32-face M32 VQC | `turing_universal_quantum_computer/turing_universal_quantum_computer/phi_vqc.py` | July trainable ranker retained under the candidate-order-only boundary. |
| Mining consensus verification | Canonical mining hash pipeline | Unchanged. VQC and Geodesic planners may reorder supplied candidates but cannot create proofs or bypass SHA-256d/target verification. |

## Recovered source checksums

These hashes identify the preserved source files used during reconciliation. They are recorded so future audits can distinguish the July evidence from later canonical adaptations.

| Preserved file | SHA-256 |
|---|---|
| `formal.py` | `42a911ddc138da662dd3d53e515f0534b0c9e26830da64cfc1b64bb80143fb97` |
| `geodesic_tensor_engine.py` | `e627cd693452904bd1ba1145058a0504955e58d10ce88f0001ed8fdbb4b87525` |
| `phi_quantum_machine.py` | `ef48b957e129fd86fa96ffcf888cf9f04dd1d7b0c645ebd4026d756ce8ba9cfa` |
| `vqc_phi_grover.py` | `3d7bc18757ff133c8275347dc16150835e48196e7846bb27e502e5fd9fb0e958` |
| `test_geodesic_tensor_engine.py` | `6de6ab9e1c00ceeb5ff44411465cc74ebc146d74afcd95001d44558a3f51b6ea` |
| `test_geodesic_tensor_engine_extensions.py` | `979a95bb40f00958b9db219a83e5506b605f3286810815a4c14aebc6b6b508c8` |
| `test_phi_quantum_machine.py` | `c68fb82c9173b56c594d031809e577862e8f58bd3340ce4438cf42f5a147360f` |
| `test_vqc_phi_grover.py` | `f222109a9270c67356bce8be88fcb2cbc9222f85983730da1d014b455c09fd12` |
| `run_ultimate_integration.py` | `db257a326fab95478dc9b3c70181cb851e1684461183057644c0ef6d11c5dfaf` |
| `run_1000_qubit_vqc_integration.py` | `69b0f4aa7e163b095e8964e812f429435c9266914a586459f6bfb05ee256ad08` |

## Existing repository evidence

- `docs/GEODESIC_TENSOR_PRODUCTION_INTEGRATION.md` records the Geodesic/PULVINI consolidation and current ownership boundaries.
- `docs/TURING_1000_QUBIT_CONSOLIDATION.md` records the 1,000-qubit and VQC consolidation.
- `tests/test_geodesic_tensor_engine.py` and `tests/test_geodesic_tensor_extensions.py` gate the canonical Geodesic implementation.
- `turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py` gates exact checkpoint restoration, discriminating GHZ verification, the 1,000-qubit profile, M32 skeleton execution and candidate-set preservation.

## Historical evidence boundary

The July logs reported 61/61 integration operations, 110/110 property invariants, 12/12 operator-calculus checks and a later 144/144 combined regression. Those totals describe the preserved July artifacts. They are not asserted as current-branch CI results. Current executable truth is defined by the repository's present code, tests, CI and provenance records.

## Product boundary

- PULVINI/HERMES, the Geodesic Tensor Engine and the general 1,000-qubit machine remain HYBA Data/enterprise capabilities adapted into shared substrate packages.
- The nonce-ranking VQC remains a MIDAS/mining capability with no consensus authority.
- Private adjacency and feature structure remain injectable; this record does not disclose private topology or credentials.
