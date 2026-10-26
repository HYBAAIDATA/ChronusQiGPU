# HYBA — Solution/Vendor Map & Repository Strategy

Assessment date: 2026-10-20. Enterprise applications and infrastructure first; mining is an optional funding workload. **This is an initial comparable-offering map, not a partnership directory or a replacement certification.**

## Answer: how many companies consolidate into HYBA?

The selected first-pass map spans **18 distinct vendor brands** across the ten current product charters plus AL HARAS and Hermitten platform lanes. NVIDIA and Intel appear in two lanes but are counted once each. Parent-company/legal-entity consolidation was not audited. The number is reproducible from `vendor-map.csv` using both a Python set and SQLite COUNT DISTINCT.

This means functional areas overlap offerings marketed by 18 vendors. It does **not** establish that HYBA replaces all of any vendor, supports equivalent connectors/hardware/regulatory duties, has their installed base, or has commercial relationships with them. No proven whole-vendor replacement count has been established. This list is selected, not an exhaustive market census or valuation model.

## Solution map

| HYBA lane | Selected comparable brands | Comparable surface and crucial boundary |
| --- | --- | --- |
| TOE | Dataiku, DataRobot, Palantir | Shared enterprise AI/analytics and operational reasoning; not parity with every governed connector, deployment or model.[^https://www.dataiku.com/product][^https://www.datarobot.com/product/ai-platform/][^https://palantir.com/docs/foundry/aip] |
| TURING VQC | IBM, Quantinuum, Classiq | Circuit simulation/construction/design; not equivalent physical QPU access or device fidelity. IBM source is a legacy Aer API category reference.[^https://docs.quantum.ibm.com/api/qiskit/0.30/qiskit.providers.aer.AerSimulator][^https://docs.quantinuum.com/tket/index.html][^https://classiq.io/quantum-algorithm-design] |
| Kellogg | NVIDIA, Intel | Tensor/numerical libraries; hardware ecosystems may complement HYBA rather than be displaced.[^https://developer.nvidia.com/cuda-toolkit][^https://www.intel.com/content/www/us/en/developer/tools/oneapi/overview.html] |
| Chronus | NVIDIA, Intel | Heterogeneous execution/tooling; no physical-hardware replacement or unmeasured GPU/iGPU performance claim. Chronos mathematics/ONE identity remains separate.[^https://developer.nvidia.com/cuda-toolkit][^https://www.intel.com/content/www/us/en/developer/tools/oneapi/overview.html] |
| Ovid | Databricks, Fivetran | Transform/materialisation, data movement and lineage overlap only; not a complete warehouse/lakehouse or connector-catalog equivalence.[^http://www.databricks.com/product][^https://fivetran.com/] |
| Theseus | Veeam, Rubrik | Custody/recovery overlap; a custody component is not a qualified fleet-wide backup platform.[^https://www.veeam.com/products/veeam-data-platform/backup-recovery.html?ad=pr1][^https://www.rubrik.com/solutions/backup-recovery] |
| SALAMANDER Enterprise | Dynatrace, PagerDuty | Health, incident workflow and bounded recovery overlap; no universal autonomous-operations certification.[^https://www.dynatrace.com/news/press-release/autonomous-operations-enterprise-ai/][^https://www.pagerduty.com/platform/incident-management/incident-response] |
| EUCLID | Adobe, Runway | Creative generation/editing workflow overlap; orchestration/provenance does not imply owning equivalent trained multimodal models.[^https://www.adobe.com/products/firefly.html][^http://runwayml.com/enterprise] |
| PULVINI | Unmapped in this pass | Primarily folding. No defensible one-to-one vendor selected; no universal compression substitution claim. |
| SALAMANDER Mining | Unmapped in this pass | Optional governed mining integration. No additional vendor selected or mining yield implied. |
| Hermitten | Finout | Capacity economics/measurement versus FinOps allocation; modeled savings are not reconciled customer billing.[^http://www.finout.io/] |
| AL HARAS | Permit.io | Policy/admission/authorization overlap; not independent security or compliance certification.[^https://docs.permit.io/overview/access-requests-and-approvals] |

## Ties, dependencies and integrations

The sources above verify vendors' own product categories, not a HYBA affiliation. No partnership, customer relationship, resale right or completed integration was verified by this map. Internal source declares NumPy and hyba-kellogg-tensor hard dependencies for TOE and bounded optional integration with Theseus/TURING/Chronus. CUDA/oneAPI and creative-model vendors should be treated as potential ecosystem complements unless an actual dependency/integration is separately verified.

A defensible consolidation claim should name the buyer workflow: data transformation/custody → tensor/device execution → reasoning → governed workflow → policy/measurement. Prove each claimed tool reduction with installed interfaces, workload accuracy, security, recovery, operating cost and a customer acceptance record. Do not add all vendor feature catalogs together and present that as HYBA's implemented scope.

## Architecture decision: modular monorepo now; selective repositories later

**Recommendation: keep the monorepo as the integration source for now. Separate products and distributable packages now; do not split every folder into a repository.** Funding pressure argues against multiplying release infrastructure while the interfaces, custody lineage and dependency closure remain unsettled. Mining revenue can fund release engineering, but financial timing alone is not a technical extraction gate.

The reviewed partial export contains reverse imports: TOE imports Kellogg while `kellogg/substrate.py:353` lazily imports TOE topology and `kellogg/toe_superposition.py:5` re-exports TOE mining decision logic. Intelligence, Lucas and ASI also cross these groups. AST observations include lazy/optional/research imports; they are not proof of an executed import cycle or an exhaustive dependency graph. They nevertheless show why moving folders unchanged would move coupling rather than remove it.

### Boundaries to enforce first

| Boundary | Rule |
| --- | --- |
| Foundational math: Kellogg / canonical algebra utilities | Must install and import without TOE, mining or workflow orchestration. Relocate optional topology/mining shims behind explicit extras/adapters; preserve compatibility via versioned deprecation, not copied engines |
| Execution: TURING and Chronus | Own their distinct VQC/device contracts; report unavailable hardware; depend on math, never on an optional mining workload |
| Representation/custody/folding: Ovid / Theseus / PULVINI | Separate authority and packages, stable versioned records; fix full custody transaction/restore gates before declaring independence |
| Intelligence: TOE | One common backend; per-domain adapters as extras/integration layer; no sector-specific backend clones |
| Workflows: EUCLID / SALAMANDER Enterprise | Consume versioned capabilities; do not duplicate custody/proof authority |
| Shared policy/economics: AL HARAS / Hermitten | Explicit interface and audit bindings; not authority assumed by every orchestrator |
| Mining integration | Optional top-level integration package; PYTHIA retains proof/share authority. Enterprise installs must work without mining |

### Extraction gates — not a migration already performed

1. Assign one owner and product/package contract, exact API/schema, license/IP scope and semver policy.
2. Declare one-way dependency graph and optional extras; exercise imports/clean installs without the root tree on PYTHONPATH.
3. Build wheel/sdist reproducibly; pin artifact digests and test supported version combinations in a local/self-hosted harness while paid CI is unavailable.
4. Separate unit/contract tests from integration suites; include negative controls, persistence migrations, SBOM/license checks and security boundaries.
5. Prove independent release and rollback without synchronized edits in another package. Select the first extraction by actual dependency closure, external consumers, access isolation and release cadence—not by an arbitrary product count.
6. If those gates pass, extract that offering with history/provenance, issues and release ownership intact. Retain an integration repository with pinned release manifests and end-to-end acceptance. Avoid Git submodule sprawl or duplicated source as a substitute for packaging.

Do not split source merely to reduce perceived repository size; no size, change-frequency or developer-throughput study was performed here. No new repositories were created, and no repo migration or publication is authorized by this recommendation. Production/publication HOLD remains independent of architecture choice.

## Unmapped portfolio work

Chronos mathematics/ONE, HERMES/PYTHIA enterprise lineage, CacheMind/Themis/Millennium and other pending catalog candidates require primary-specification resolution before adding competitors or increasing the count. PULVINI and SALAMANDER Mining remain explicitly unmapped rather than padded with superficial comparables. This map is a maintained decision aid, not the final full portfolio inventory.
