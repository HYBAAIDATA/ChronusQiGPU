# Unified analytics coverage map

Evidence status is unchanged. Implementation status is the second axis.
Benchmark numbers are in `reports/toe_unified_benchmark.json`.
Datasets: UCI Iris (`tests/fixtures/toe_unified/iris.data`) and the program cost sheet.

| claim_id | evidence_status | implementation_status | tests_present | tests_required | gap_summary |
|---|---|---|---|---|---|
| A1 | DECLARED | IMPLEMENTED_FIXTURE | unit, integration, e2e | unit, invariant, integration, e2e | invariant |
| A2 | MODELED | IMPLEMENTED_REAL | unit, benchmark | unit, benchmark | none |
| A3 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| A4 | DECLARED | IMPLEMENTED_FIXTURE | invariant, adversarial, unit, integration | unit, invariant, integration, e2e, adversarial, property | e2e, property |
| A5 | MEASURED | IMPLEMENTED_REAL | adversarial, unit, benchmark | unit, invariant, benchmark, adversarial, property | invariant, property |
| B1 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| B2 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| B3 | DECLARED | IMPLEMENTED_FIXTURE | unit | unit, invariant | invariant |
| B4 | MEASURED | IMPLEMENTED_REAL | invariant, unit, e2e, benchmark | unit, invariant, benchmark | none |
| B5 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| C1 | DECLARED | IMPLEMENTED_FIXTURE | invariant, property, unit, integration, e2e | unit, invariant, integration, e2e, adversarial, property | adversarial |
| C2 | DECLARED | IMPLEMENTED_FIXTURE | invariant, unit | unit, invariant | none |
| C3 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| C4 | DECLARED | IMPLEMENTED_FIXTURE | adversarial, unit | unit, invariant, adversarial, property | invariant, property |
| C5 | MEASURED | IMPLEMENTED_REAL | invariant, adversarial, property, unit, integration, e2e, benchmark | unit, invariant, benchmark, integration, e2e, adversarial, property | none |
| C6 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| C7 | MEASURED | IMPLEMENTED_REAL | property, unit, integration, benchmark | unit, invariant, benchmark, integration, e2e, adversarial, property | invariant, e2e, adversarial |
| C8 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| C9 | DECLARED | IMPLEMENTED_FIXTURE | unit | unit, invariant | invariant |
| C10 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| C11 | DECLARED | IMPLEMENTED_FIXTURE | unit | unit, invariant | invariant |
| C12 | MEASURED | IMPLEMENTED_REAL | unit, integration, benchmark | unit, invariant, benchmark, integration, e2e | invariant, e2e |
| C13 | MEASURED | IMPLEMENTED_REAL | invariant, unit, benchmark | unit, invariant, benchmark | none |
| C14 | DECLARED | IMPLEMENTED_FIXTURE | unit | unit, invariant | invariant |
| C15 | MEASURED | IMPLEMENTED_REAL | adversarial, property, unit, benchmark | unit, invariant, benchmark, adversarial, property | invariant |
| C16 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| D1 | MODELED | IMPLEMENTED_REAL | unit, benchmark | unit, benchmark | none |
| D2 | MODELED | IMPLEMENTED_REAL | unit, benchmark | unit, benchmark | none |
| D3 | MODELED | IMPLEMENTED_REAL | unit, benchmark | unit, benchmark | none |
| D4 | MODELED | IMPLEMENTED_REAL | unit, benchmark | unit, benchmark | none |
| D5 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| D6 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| D7 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| D8 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| D9 | DECLARED | IMPLEMENTED_FIXTURE | unit | unit, invariant | invariant |
| D10 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| D11 | DECLARED | IMPLEMENTED_FIXTURE | invariant, property, unit | unit, invariant, adversarial, property | adversarial |
| E1 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| E2 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| E3 | MEASURED | IMPLEMENTED_REAL | unit, integration, benchmark | unit, invariant, benchmark, integration, e2e | invariant, e2e |
| E4 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| E5 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| E6 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| E7 | DECLARED | IMPLEMENTED_FIXTURE | unit | unit, invariant | invariant |
| E8 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| E9 | DECLARED | IMPLEMENTED_FIXTURE | unit | unit, invariant | invariant |
| F1 | MEASURED | IMPLEMENTED_REAL | invariant, adversarial, property, unit, benchmark | unit, invariant, benchmark, adversarial, property | none |
| F2 | DECLARED | IMPLEMENTED_FIXTURE | unit | unit, invariant | invariant |
| F3 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| F4 | MEASURED | IMPLEMENTED_REAL | unit, integration, e2e, benchmark | unit, invariant, benchmark, integration, e2e | invariant |
| G1 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| G2 | MEASURED | IMPLEMENTED_REAL | invariant, adversarial, unit, e2e, benchmark | unit, invariant, benchmark, adversarial, property | property |
| G3 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| G4 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| G5 | MEASURED | IMPLEMENTED_REAL | unit, integration, benchmark | unit, invariant, benchmark, integration, e2e | invariant, e2e |
| G6 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| H1 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| H2 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| H3 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| H4 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| H5 | MEASURED | IMPLEMENTED_REAL | unit, benchmark | unit, invariant, benchmark | invariant |
| I1 | MEASURED | IMPLEMENTED_REAL | invariant, adversarial, property, unit, integration, e2e, benchmark | unit, invariant, benchmark, integration, e2e, adversarial, property | none |
| I2 | MEASURED | IMPLEMENTED_REAL | invariant, unit, benchmark | unit, invariant, benchmark | none |
| I3 | MEASURED | IMPLEMENTED_REAL | invariant, adversarial, unit, benchmark | unit, invariant, benchmark, adversarial, property | property |
| I4 | MEASURED | IMPLEMENTED_REAL | invariant, adversarial, unit, integration, benchmark | unit, invariant, benchmark, integration, e2e, adversarial, property | e2e, property |
| I5 | MEASURED | IMPLEMENTED_REAL | invariant, adversarial, unit, benchmark | unit, invariant, benchmark, adversarial, property | property |
