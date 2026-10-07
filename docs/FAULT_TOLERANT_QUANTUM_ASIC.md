# Fault-Tolerant Quantum ASIC Engineering Model

## Delivered scope

The quantum-ASIC specification is implemented as a deterministic, fail-closed engineering model in `mining.fault_tolerant_asic`. Mining owns it: the capacity model and the 10 EH/s certificates are hashrate claims, so they are not part of the TURING virtual quantum computer, which they consume for exact algebra.

The implementation covers every computable subsystem in the supplied specification:

| Specification surface | Implementation |
| --- | --- |
| Refrigeration cascade | `RefrigerationStage`, `DilutionRefrigerator` |
| Cooling-power law and Carnot minimum | `cooling_power()`, `minimum_work()` |
| Wiring heat and capacity | `wiring_heat()`, `line_capacity()`, `WiringBudget` |
| Transmon loss budget | `TransmonCoherence` |
| Transmon electrical/gate contract | `TransmonQubit` |
| Tunable coupling and residual ZZ | `TunableCoupler` |
| Dispersive readout | `ReadoutResonator` |
| Die geometry and I/O count | `QuantumChipLayout` |
| Surface-code threshold and overhead | `SurfaceCode` |
| Syndrome cycle | `SyndromeExtraction` |
| MWPM planning envelope | `Decoder` |
| Logical-qubit lifetime and gates | `LogicalQubit` |
| Room-temperature control | `RoomTemperatureControl` |
| Cryogenic control | `CryoCMOS` |
| Superconducting control estimate | `RSFQ` |
| Attenuation/amplification chain | `SignalChain` |
| Shor/Grover/chemistry/QAOA/boson resources | `APPLICATIONS` |
| Refrigerator/power/cost/runtime scaling | `ScalingModel` |
| Four-threshold gate | `ThresholdEvaluation` |
| Production evidence and promotion | `EvidenceRecord`, `ProductionEvidence` |
| Complete stack and digest report | `QuantumAsicStack` |

## Production behavior

The software model is designed for production use as a calculator and validation boundary:

- all physical quantities are validated for finite, legal ranges;
- impossible or internally inconsistent configurations raise immediately;
- refrigerator counts use ceiling division—partial refrigerators are impossible;
- surface-code distance must be odd and at least three;
- logical and stack code parameters must match;
- decoder latency and throughput are both checked;
- application estimates are labelled `modelled`, never `executed`;
- reports are content-addressed with SHA-256;
- hardware readiness cannot be asserted using booleans alone;
- each readiness claim requires a unique, hash-addressed evidence record;
- independent review must be `independently_reproduced`;
- the physical stack is ready only after all cryogenic, chip, decoder, control, logical-qubit, and application evidence is present.

## Corrected scientific boundary

The attached document combines sound formulas, engineering assumptions, forecasts, and several claims that cannot be promoted to theorems from those assumptions alone. The implementation therefore applies these corrections:

1. The four threshold checks are necessary planning gates, not a mathematical proof that a useful machine is sufficient or buildable.
2. The decoder model distinguishes per-patch syndrome rate from the document’s system-wide `10^12 bit/s` promotion threshold.
3. Surface-code logical-error estimates are model outputs, not hardware measurements.
4. Application resources are estimates. No RSA-2048, AES-256, FeMoco, QAOA, or boson-sampling execution is claimed.
5. Landauer accounting applies to logically irreversible information erasure, not exclusively to quantum measurement.
6. Cooling, wiring, decoder, control, and qubit parameters are configurable because the values in the specification are design assumptions—not universal constants.
7. The Turing virtual quantum computer remains an exact mathematical engine. It is not relabelled as physical transmon hardware.

## Evidence promotion

A production evidence record contains:

```python
EvidenceRecord(
    category="qubit_chip_measurements",
    state=EvidenceState.MEASURED,
    artifact_digest="<sha256 of immutable result artifact>",
    source="<laboratory or test system>",
    observed_at="<ISO-8601 timestamp>",
)
```

Required categories:

- `software_tests`
- `independent_model_review`
- `cryogenic_measurements`
- `qubit_chip_measurements`
- `decoder_hardware_measurements`
- `control_stack_measurements`
- `logical_qubit_demonstration`
- `application_execution`

Missing evidence is returned explicitly by `ProductionEvidence.missing`.

## Verification

The focused standard-library test suite covers thermodynamics, wiring, coherence, transmon and coupler contracts, readout, chip geometry, surface-code calculations, syndrome extraction, decoder limits, logical qubits, room/cryo control, RSFQ, signal chain, all application profiles, scaling, threshold gates, evidence promotion, digest reports, invalid configurations, the capacity-surface exports, and the Mining integration test (`tests/test_mining_quantum_asic_integration.py`).

Passing these tests establishes correctness of the software model against its declared contracts. It does not establish physical feasibility, fabricated-silicon performance, or fault-tolerant quantum computation.
