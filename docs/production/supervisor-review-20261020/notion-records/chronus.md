<b>Locked identity:</b> hardware-aware enterprise acceleration and truthful execution evidence, scoped to Chronus hardware capabilities. This record does not rename packages.

<b>Naming correction from current source review:</b> the publication catalog distinguishes <code>hyba-chronos-mathematics</code>, <code>hyba-chronos-one-igpu</code>, <code>hyba-chronus-igpu</code> and planned <code>hyba-chronus-tensor</code>. Chronos must not be treated as a blanket spelling alias for Chronus. The earlier alias assumption is withdrawn. Map each distribution to its actual API/version and evidence before publication; the mathematics package needs its own scoped contract rather than inheriting this hardware charter.

<mention url="https://app.notion.com/p/bf7c43276c4c466b8cf55683b410282d">Whole-System Release Decision — Production & Publication</mention>.

<b>Status:</b> authority baseline documented; callable/transport mapping and target hardware qualification open.

## Owned authority

Device probing and fingerprinting, scheduling, memory/transfer handling, eligible CPU/iGPU/GPU execution, invariant verification and evidence of where work actually ran. Kellogg owns tensor mathematics/artifact semantics. Ovid owns versioned fold/materialise; Theseus owns durable custody. Chronus must not change canonical digests or correctness to obtain throughput.

## Contract and API inventory

| Surface | Required obligation |
| --- | --- |
| Capability manifest | Identify actual device/backend and limits; unknown hardware facts remain null, not guessed from vendor marketing |
| Execution request | Bind operation, input shape/dtype, resource limits, required backend/device, exactness and permitted fallback policy |
| Execution result | Identify actual execution backend/device, output identity, transfer and compute evidence, refusal/degradation state |
| Device-required mode | Fail closed when the requested device/path is unavailable; no silent host fallback |
| Host mode | Label host execution honestly, including historical <code>kellogg-host</code> label where applicable |

Historical source surfaces include <code>chronus.phi_gpu</code>, <code>chronus.v33</code> and Kellogg-backed MPS/TT/MPO integration. A separate tensor control API is recorded in the production closeout; its routes must not be assumed to be identical to every Chronus package API. Exact exports, schemas and authentication bindings remain to be reconciled at a pinned commit.

A child adapter or micro-tether does not create another physical iGPU. Dated topology references are not device measurements. Do not claim FP64 or folded-native support merely from scheduling eligibility.

## Non-mining acceptance requirement

Run a representative enterprise tensor operation against a CPU/reference baseline; confirm output/error bounds, requested-device refusal, actual device identity and complete transfer/compute timing. Include unavailable-device and resource-exhaustion cases. No new benchmark execution is asserted.

## Mining boundary

Optional mining execution remains subordinate to canonical hashing, target and pool authorities. Scheduling estimates and algebraic dimensions are not hashes per second or accepted shares.

## Customer schedule

Specify supported hardware/software matrix, operation classes, fallback policy and customer prerequisites. Do not promise universal GPU acceleration or vendor-specific bandwidth absent measurement. Fees, support/SLA and license are separate approved commercial terms.

## Source traceability

- <mention url="https://app.notion.com/p/083f5e3ca1f84472bdddd6386f9cac89">Converge July tensor capabilities into Kellogg and close Chronus GPU gaps</mention>
- <mention url="https://app.notion.com/p/5d54be90d6ed483aa70f99740cfb5324">feat(aethel): Chronus·Theseus·Ovid enterprise custody substrate</mention>
- <mention url="https://app.notion.com/p/12dd4186d005470d958096c7227ab2b9">Production & Publication Closeout — Evidence and Gates</mention>
- <mention url="https://app.notion.com/p/3f113476fb44496e99a2fcbb37546ccb">HYBA — Enterprise Product Lock Register</mention>