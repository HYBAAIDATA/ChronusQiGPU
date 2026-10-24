# Collaborative Automation & Automated Runbook Orchestration ("System of Execution")

**Implementation:** [`salamander/collaborative_automation.py`](../../salamander/collaborative_automation.py) | [`tools/collaborative_automation.py`](../../tools/collaborative_automation.py)  
**Control Plane API:** [`chronus/mla1517_platform/python/control_api.py`](../../chronus/mla1517_platform/python/control_api.py)  
**Contracts & Verification:** [`tests/test_collaborative_automation.py`](../../tests/test_collaborative_automation.py)  
**Operational Catalogue:** [`runbooks/catalogue.json`](../../runbooks/catalogue.json)

---

## 1. Executive Summary

HYBA/PYTHIA implements a governed **Collaborative Automation** layer inside the Salamander autonomic control plane (`salamander.collaborative_automation`). Rather than treating automation as isolated, fragile scripts or attempting to replace operator judgment, the engine serves as a **System of Execution** that interconnects:

1. **Cross-functional human teams** (`DevOps`, `SRE`, `TechOps`, `SecurityAnalyst`, `ArchitectureOwner`, `ReleaseManager`, `Stakeholder`, `IncidentResponse`) for judgment, awareness, and explicit checkpoint authorization.
2. **Bounded technological actuation** across four tool archetypes (`AI_ML`, `RPA`, `IT_AUTOMATION`, `IPAAS`).
3. **Bathtub Effect risk guardrails** (`BathtubGuard`) enforcing small-to-scale incremental bounds (`INCREMENTAL_SCALE_LADDER`), scope-lock digests, operator/resource preflight checks, and stall detection.
4. **Centralized Single Pane of Glass visibility** (`single_pane_dashboard()`) and hash-chained, tamper-evident audit provenance (`EvidenceLedger`).

---

## 2. Authority Boundaries & Falsifiability Contract

Collaborative Automation coordinates people and subsystem actuators without overriding any canonical HYBA/PYTHIA authority:

| Canonical Authority | Relationship to Collaborative Automation |
| :--- | :--- |
| **EUCLID / TOE** | Supplies `AI_ML` predictive, causal, and counterfactual advisory context. `ToolSelectionCriteria` enforces `advisory_only=True` for `AI_ML`—intelligence never self-approves a human checkpoint or overrides proof/security boundaries. |
| **PYTHIA** | Retains final mining authority, `SearchPlan` finalisation, SHA256d proof verification, and literal Stratum pool outcomes. Runbooks never fabricate shares or hashrate. |
| **CHRONUS** | Owns substrate-agnostic execution and fleet partition scheduling (`chronus.fleet`). Cloud/fleet migration runbooks coordinate partition provisioning and lease draining around Chronus. |
| **SALAMANDER** | Owns bounded homeostasis, recovery DAG execution (`RecoveryPlan`), and automatic verified rollback (`ActionKind.ROLLBACK`) when a step postcondition verifier rejects an outcome. |
| **AL HARAS** | Owns cryptographic identity, entitlement verification, and admission gating (`ALHarasActionAuthorizer`). |
| **OVID / THESEUS** | Own enduring storage lineage and rebuildable custody/witness projections. Every runbook step transition and human decision is hash-chained in Salamander's `EvidenceLedger`. |

---

## 3. Eliminating Siloed Chaos & Open-Source Orchestration Limitations

### 3.1 Cross-Team Task Deduplication (`CrossTeamTaskDeduplicator`)
Fragmented `DevOps`, `SRE`, and `TechOps` teams working in isolation often repeat manual verification or remediation steps. Every `CollaborativeStep` computes a deterministic task fingerprint over `(tenant_id, target, operation, parameters)`. When a downstream team schedules an identical verification or task that has already been verified in the same scope, `CrossTeamTaskDeduplicator` coalesces the step as `DEDUPLICATED` and links the prior `evidence_sha256` audit receipt.

### 3.2 Selecting the Right Automation Tool (`select_automation_tool`)
Each step binds to one of four canonical tool categories:
- **`AI_ML`**: Complex decision-making and predictive/causal analytics (strictly `advisory_only=True`).
- **`RPA`**: Rule-based, repetitive deterministic tasks (e.g., lease draining, regression sweeps).
- **`IT_AUTOMATION`**: Infrastructure, configuration, and bounded runtime actuation.
- **`IPAAS`**: Cross-system receipt transport, witness re-anchoring, and lineage handoffs.

### 3.3 Mitigating the "Bathtub Effect" (`BathtubGuard`)
Uncontrolled automation often suffers a sharp complexity spike and performance dip (the **Bathtub Effect**). `BathtubGuard` evaluates four operational risk dimensions prior to and after execution:
1. **`SCOPE_CREEP`**: Locks `initial_scope_sha256` and bounds step counts against the declared incremental scale phase (`INCREMENTAL_SCALE_LADDER = (1, 2, 3, 5, 8, 10, 12, 15, 18, 20, 31, 50, 76)`). Unapproved mid-flight step additions halt the runbook (`HALTED_BATHTUB_GUARD`).
2. **`TECHNICAL_CHALLENGES`**: Monitors failed postcondition verifications and triggers governed rollback (`StepStatus.ROLLED_BACK`) before cascading failure.
3. **`LACK_OF_RESOURCES`**: Verifies available human operators for `HUMAN_IN_THE_LOOP` / `COLLABORATIVE_HYBRID` checkpoints and remaining action budgets before actuation.
4. **`LOSS_OF_MOMENTUM`**: Detects stalled checkpoints exceeding `stall_timeout_ns`.

---

## 4. Four Canonical Collaborative Automation Workflows

`build_canonical_workflow_runbooks()` provides four dependency-ordered workflows alongside the seven operational recovery runbooks in [`runbooks/catalogue.json`](../../runbooks/catalogue.json):

1. **Cyber and IT Disaster Recovery (`cyber_it_disaster_recovery`)**:
   - Automated anomaly classification and instant engagement of `SRE`, `SecurityAnalyst`, and `TechOps`.
   - Automated lane quarantine (`quarantine_compromised_lanes`) with rollback (`restore_quarantined_lanes`).
   - Mandatory `HUMAN_IN_THE_LOOP` failover checkpoint requiring `SecurityAnalyst` or `Stakeholder` approval with recorded rationale.
   - `COLLABORATIVE_HYBRID` witness chain re-anchoring and immutable compliance receipt emission.
2. **Cloud & Fleet Migration (`cloud_migration`)**:
   - Automated upstream/downstream dependency mapping and Lucas fleet capacity verification.
   - Automated target partition provisioning and in-flight lease draining.
   - `HUMAN_IN_THE_LOOP` snapshot equivalence verification and cutover sign-off (`ArchitectureOwner` / `SRE`).
3. **Application Release Management (`application_release_management`)**:
   - Automated regression sweep, readiness gate checks, and signed container provenance verification.
   - Bounded canary deployment with automatic rollback (`rollback_canary_slice`) on postcondition rejection.
   - `HUMAN_IN_THE_LOOP` production release promotion (`ReleaseManager` / `SRE`).
4. **Technology Implementation (`technology_implementation`)**:
   - Deterministic prerequisite validation, sovereign policy boundary configuration, and phased rollout.
   - Real-time Single Pane of Glass stakeholder handover attestation (`Stakeholder` / `ArchitectureOwner`).

---

## 5. CLI and HTTP Control Plane Usage

### 5.1 Standard-Library CLI (`tools/collaborative_automation.py`)
```powershell
# Inspect the unified catalogue (4 canonical workflows + 7 repository catalogue runbooks)
python -m tools.collaborative_automation --catalogue

# Generate the real-time Single Pane of Glass operational dashboard
python -m tools.collaborative_automation --dashboard

# Execute a runbook (pauses at AWAITING_HUMAN when human decisions are not yet supplied)
python -m tools.collaborative_automation --run cyber_it_disaster_recovery

# Execute with explicit operator approvals recorded in the hash-chained audit ledger
python -m tools.collaborative_automation --run cyber_it_disaster_recovery --approve-all-human --actor sec-lead-01
```

### 5.2 Control Plane HTTP Endpoints (`control_api.py`)
- `GET /api/v1/automation/collaborative/status` — Single Pane of Glass dashboard (`hyba.collaborative.dashboard.v1`).
- `GET /api/v1/automation/runbooks` — Unified collaborative runbook catalogue and tool selection matrix (`hyba.collaborative.catalogue.v1`).
- `POST /api/v1/automation/collaborative/decision` — Record an authenticated human-in-the-loop judgment (`HumanDecision`).
- `POST /api/v1/automation/collaborative/run` — Execute a registered collaborative runbook and emit its hash-chained audit receipt.
