"""Claim register for the unified analytics narrative.

Status is one of MEASURED, DECLARED, MODELED, UNSUPPORTED.
A claim is MEASURED only when a test asserts the behaviour.
MODELED means a formula reproduces a stated scenario from declared inputs.
DECLARED means the mechanism exists and the test locks that mechanism,
not the marketing magnitude. UNSUPPORTED means the repository does not
implement the claim.
"""

from __future__ import annotations

from dataclasses import dataclass


STATUSES = ("MEASURED", "DECLARED", "MODELED", "UNSUPPORTED")


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    module: str
    status: str
    test: str
    note: str


CLAIMS: tuple[Claim, ...] = (
    Claim("A1", "Replace 19+ systems", "toe/unified/catalog.py", "DECLARED",
          "tests/test_toe_unified_connectors.py::test_each_displaced_class_binds",
          "Nineteen classes exist and each one binds to a fixture. That is not removal of a customer's installed systems."),
    Claim("A2", "90% cost reduction", "toe/unified/economics.py", "MODELED",
          "tests/test_toe_unified_economics.py::test_document_scenario_numbers",
          "The draft's 19-system inputs produce savings of 58000000 and 145000000. Those inputs are not a measurement of a deployment."),
    Claim("A3", "1000+ pre-built connectors", "toe/unified/catalog.py", "MEASURED",
          "tests/test_toe_unified_catalog.py::test_catalog_count_and_classes",
          "The catalog length is 1063."),
    Claim("A4", "Instant deployment via 1000+ connectors", "toe/unified/connectors.py", "DECLARED",
          "tests/test_toe_unified_connectors.py::test_each_protocol_binds",
          "Six protocols bind to fixtures. A catalog row is not a live vendor endpoint."),
    Claim("A5", "Heal on call and on the health loop", "toe/unified/operations.py", "MEASURED",
          "tests/test_toe_unified_operations.py::test_reprobe_and_quarantine",
          "heal() re-probes and quarantines when called. monitor.start() calls the same heal without a further call."),
    Claim("B1", "Indexed reads versus a full scan", "toe/unified/data_layer.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_indexed_reads_are_two_orders_faster",
          "On 100 entities of 20 rows, an indexed read examines 100 times fewer rows. The processing gate opens at a reduction of 0.90."),
    Claim("B2", "Action weights reorder the interface", "toe/unified/consciousness.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_consciousness_reorders_from_actions",
          "observe() adds weight for a widget. rank() follows that weight."),
    Claim("B3", "Adaptive interface from user actions", "toe/unified/adaptive.py", "DECLARED",
          "tests/test_toe_unified_bi_adaptive.py::test_adaptive_reads_only_declared_signals",
          "The only inputs are user, widget, depth, and time."),
    Claim("B4", "Health loop runs after start", "toe/unified/monitor.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_monitor_runs_without_a_manual_heal",
          "start() ticks and calls heal without a further heal() from the caller."),
    Claim("B5", "Universal connectivity of 1000+ connectors", "toe/unified/catalog.py", "MEASURED",
          "tests/test_toe_unified_catalog.py::test_catalog_count_and_classes",
          "Same catalog count as A3."),
    Claim("C1", "Single source of truth", "toe/unified/data_layer.py", "DECLARED",
          "tests/test_toe_unified_data_layer.py::test_concurrent_ingest_one_record",
          "One digest is stored once, including under concurrent ingest. There is no enterprise-wide store outside this process."),
    Claim("C2", "Real-time streaming and batch processing", "toe/unified/data_layer.py", "DECLARED",
          "tests/test_toe_unified_data_layer.py::test_batch_and_stream_dedup",
          "Both modes call the same ingest. No latency bound is declared."),
    Claim("C3", "Compressed payload storage", "toe/unified/data_layer.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_storage_round_trip_compresses",
          "Each new payload is zlib-compressed under its digest. The repetitive fixture stores at least twice smaller and restores exactly."),
    Claim("C4", "Automatic data quality and governance", "toe/unified/data_layer.py", "DECLARED",
          "tests/test_toe_unified_data_layer.py::test_malformed_row_rejected",
          "A non-object row is rejected before any write. Quarantine still requires heal()."),
    Claim("C5", "Train, deploy, retrain, rollback", "toe/unified/intelligence.py", "MEASURED",
          "tests/test_toe_unified_intelligence.py::test_train_retrain_rollback",
          "With eval_rows, retrain retains the live model if held-out accuracy falls. Direct manual training without evaluation remains a trusted operation."),
    Claim("C6", "Corrections move the decision threshold", "toe/unified/consciousness.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_corrections_raise_accuracy",
          "The threshold becomes the midpoint of corrected class scores. On the fixture, accuracy rises to 1."),
    Claim("C7", "Drift sample retrains from the health loop", "toe/unified/monitor.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_drift_retrains_without_calling_retrain",
          "Drift below 0.5 triggers a candidate only with disjoint held-out rows; promotion requires non-regression, the configured accuracy floor and an unchanged live version. Missing evidence blocks automatic promotion."),
    Claim("C8", "Cross-domain transfer", "toe/unified/intelligence.py", "MEASURED",
          "tests/test_toe_unified_intelligence.py::test_transfer_overlap",
          "Missing features are zero-filled and the overlap is reported."),
    Claim("C9", "Dynamic dashboard generation", "toe/unified/bi.py", "DECLARED",
          "tests/test_toe_unified_bi_adaptive.py::test_dashboard_order_follows_use",
          "Declared widgets are reordered. New widgets are not created."),
    Claim("C10", "Selectivity query plan", "toe/unified/optimizer.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_selective_filter_runs_first",
          "Filters run in ascending selectivity. The chosen examine-cost is below the reverse order."),
    Claim("C11", "Real-time predictive insights", "toe/unified/industries.py", "DECLARED",
          "tests/test_toe_unified_industries.py::test_manufacturing_schemas",
          "The functions return when called. No latency bound is declared."),
    Claim("C12", "Natural language query interface", "toe/unified/bi.py", "MEASURED",
          "tests/test_toe_unified_bi_adaptive.py::test_grammar_accepts_and_rejects",
          "The accepted grammar is the parser's four patterns plus health and roi."),
    Claim("C13", "Health loop ticks without a manual heal", "toe/unified/monitor.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_monitor_runs_without_a_manual_heal",
          "Same loop as B4."),
    Claim("C14", "Predictive maintenance", "toe/unified/industries.py", "DECLARED",
          "tests/test_toe_unified_industries.py::test_manufacturing_schemas",
          "maintenance_trend is a least-squares slope. It does not emit a failure time."),
    Claim("C15", "Automatic scaling from queue depth", "toe/unified/operations.py", "MEASURED",
          "tests/test_toe_unified_operations.py::test_worker_formula",
          "workers = clamp(1, ceil(queue/batch), max_workers), or 1 when the queue is empty."),
    Claim("C16", "Live model swap and connector reload", "toe/unified/platform.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_predict_during_swap",
          "predict keeps returning a class while retrain swaps the model and reload replaces credentials. Stored rows remain."),
    Claim("D1", "Licensing cost range 38M to 95M", "toe/unified/economics.py", "MODELED",
          "tests/test_toe_unified_economics.py::test_document_scenario_numbers",
          "19 times 2M and 19 times 5M."),
    Claim("D2", "Integration cost range 10M to 25M", "toe/unified/economics.py", "MODELED",
          "tests/test_toe_unified_economics.py::test_document_scenario_numbers",
          "Those are scenario inputs, added into current_annual."),
    Claim("D3", "Maintenance cost range 15M to 30M", "toe/unified/economics.py", "MODELED",
          "tests/test_toe_unified_economics.py::test_document_scenario_numbers",
          "Scenario inputs, not a measured team cost."),
    Claim("D4", "Infrastructure cost range 5M to 15M", "toe/unified/economics.py", "MODELED",
          "tests/test_toe_unified_economics.py::test_document_scenario_numbers",
          "Scenario inputs."),
    Claim("D5", "Data-scientist reference workload is 4 steps to 1", "toe/unified/productivity.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_reference_workloads",
          "increase is 3.0. Live samples are recorded separately."),
    Claim("D6", "Analyst reference workload is 7 steps to 2", "toe/unified/productivity.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_reference_workloads",
          "increase is 2.5."),
    Claim("D7", "Operations reference overhead is 100 units to 20", "toe/unified/productivity.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_reference_workloads",
          "reduction is 0.8."),
    Claim("D8", "Time-to-insight reference is 5 seconds to 1", "toe/unified/productivity.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_reference_workloads",
          "faster is 4.0."),
    Claim("D9", "Consistent data policy", "toe/unified/data_layer.py", "DECLARED",
          "tests/test_toe_unified_data_layer.py::test_policy_recorded",
          "One policy record per entity. Batch and stream share that record."),
    Claim("D10", "One role check on platform actions", "toe/unified/security.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_one_security_check_denies_then_allows",
          "When enforcement is on, an unknown actor is denied. An operator grant allows ingest."),
    Claim("D11", "Audit trail", "toe/unified/data_layer.py", "DECLARED",
          "tests/test_toe_unified_data_layer.py::test_audit_is_append_only",
          "The log is an append-only list in process. It is not a regulatory filing."),
    Claim("E1", "Risk, fraud, regulatory totals, customer 360", "toe/unified/industries.py", "MEASURED",
          "tests/test_toe_unified_industries.py::test_finance_schemas",
          "Each function returns the declared keys on a fixture."),
    Claim("E2", "Maintenance, quality, inventory, energy", "toe/unified/industries.py", "MEASURED",
          "tests/test_toe_unified_industries.py::test_manufacturing_schemas",
          "Each function returns the declared keys on a fixture."),
    Claim("E3", "23-system case saves 45M", "toe/unified/economics.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_financial_case_saves_45m",
          "Current cost 55M, platform 10M, savings 45M."),
    Claim("E4", "Risk-model reference workload is 4 steps to 1", "toe/unified/productivity.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_reference_workloads",
          "reduction is 0.75."),
    Claim("E5", "Regulatory-reporting reference workload is 10 steps to 1", "toe/unified/productivity.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_reference_workloads",
          "reduction is 0.90."),
    Claim("E6", "Fraud precision lift on the separable fixture", "toe/unified/industries.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_fraud_lift_on_separable_fixture",
          "Flag-all precision is 0.25. exact_linear precision is 1. Improvement is 3."),
    Claim("E7", "Healthcare patient-risk prediction", "toe/unified/industries.py", "DECLARED",
          "tests/test_toe_unified_industries.py::test_healthcare_pack_uses_numeric_risk",
          "The healthcare pack calls the same numeric risk_scores function. It is not a clinical model."),
    Claim("E8", "Sensor batch carries an operator digest", "toe/unified/industries.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_sensor_batch_carries_operator",
          "Rising readings return direction rising, channel opcua, and a stable operator digest."),
    Claim("E9", "Supply-chain inventory position", "toe/unified/industries.py", "DECLARED",
          "tests/test_toe_unified_industries.py::test_manufacturing_schemas",
          "inventory_position sums qty by sku. It does not plan a supply chain."),
    Claim("F1", "Scholarship split across three universities", "toe/unified/impact.py", "MEASURED",
          "tests/test_toe_unified_impact.py::test_split_sums_to_allocation",
          "Oxford, Imperial, and Cambridge receive equal shares of the allocated amount."),
    Claim("F2", "A disbursement record per institution", "toe/unified/impact.py", "DECLARED",
          "tests/test_toe_unified_impact.py::test_split_sums_to_allocation",
          "One recognition is stored. The three shares are computed, not stored as separate payments."),
    Claim("F3", "Scholarship outcomes from allocated value", "toe/unified/impact.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_scholarship_outcomes",
          "150000 at unit cost 50000 is 3 scholarships across 3 partnerships and the Caribbean and Africa regions."),
    Claim("F4", "recognize_value reaches the three-way split", "toe/unified/impact.py", "MEASURED",
          "tests/test_toe_unified_impact.py::test_recognize_value_flow",
          "The platform method writes one ledger entry and the split follows."),
    Claim("G1", "Processing-reduction gate at 0.90", "toe/unified/platform.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_indexed_reads_are_two_orders_faster",
          "The gate opens after benchmark_processing records a reduction of at least 0.90."),
    Claim("G2", "Satisfaction gate at 0.95", "toe/unified/platform.py", "MEASURED",
          "tests/test_toe_unified_phases.py::test_satisfaction_gate",
          "The gate opens only when the mean of supplied ratings is at least 0.95."),
    Claim("G3", "Unplanned-downtime gate at zero", "toe/unified/platform.py", "MEASURED",
          "tests/test_toe_unified_phases.py::test_downtime_gate",
          "The gate closes when unplanned_downtime is set above zero."),
    Claim("G4", "Enterprise-systems gate at 500", "toe/unified/platform.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_five_hundred_systems_gate",
          "The gate opens when 500 connectors are bound."),
    Claim("G5", "ROI gate at 4.0", "toe/unified/platform.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_roi_gate_opens_at_400_percent",
          "The 23-system case has a 3-year ROI above 4."),
    Claim("G6", "Patent gate at 10", "toe/unified/patents.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_patent_gate_opens_at_ten",
          "file_patent increments the register. The gate opens at 10."),
    Claim("H1", "Integration-complexity default Low", "toe/unified/risks.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_risk_defaults_and_observed_rate",
          "With no observations the label is Low. One hundred successes move it to Very Low."),
    Claim("H2", "Performance-scalability default Very Low", "toe/unified/risks.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_risk_defaults_and_observed_rate",
          "Default label, before any observations."),
    Claim("H3", "User-adoption default Low", "toe/unified/risks.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_risk_defaults_and_observed_rate",
          "Default label, before any observations."),
    Claim("H4", "Export and re-import", "toe/unified/platform.py", "MEASURED",
          "tests/test_toe_unified_portability.py::test_export_import_round_trip",
          "JSON records re-import into a new instance with the same digests."),
    Claim("H5", "Competitive-response default High", "toe/unified/risks.py", "MEASURED",
          "tests/test_toe_unified_elevation.py::test_risk_defaults_and_observed_rate",
          "Default label. It does not change until observations are recorded."),
    Claim("I1", "Every ingest carries an operator digest", "toe/unified/platform.py", "MEASURED",
          "tests/test_toe_unified_ingest_digest.py::test_digest_stable_and_tamper_evident",
          "The digest is stable and changes when the payload changes."),
    Claim("I2", "compile_operator runs on the ingest path", "toe/unified/platform.py", "MEASURED",
          "tests/test_toe_unified_ingest_digest.py::test_digest_stable_and_tamper_evident",
          "The receipt stores that digest."),
    Claim("I3", "Fail closed without credentials", "toe/unified/connectors.py", "MEASURED",
          "tests/test_toe_unified_failclosed.py::test_missing_credentials_write_nothing",
          "Each protocol raises and no row is stored."),
    Claim("I4", "Re-probe, quarantine, release, worker count", "toe/unified/operations.py", "MEASURED",
          "tests/test_toe_unified_operations.py::test_quarantine_is_reversible",
          "Quarantine hides rows. release() puts them back."),
    Claim("I5", "Phase gates follow measured thresholds", "toe/unified/platform.py", "MEASURED",
          "tests/test_toe_unified_phases.py::test_closed_gates_on_an_empty_platform",
          "An empty platform does not open connector, satisfaction, or savings gates."),
)


def by_id() -> dict[str, Claim]:
    return {claim.id: claim for claim in CLAIMS}


LAYERS = ("invariant", "adversarial", "property", "unit", "integration", "e2e", "benchmark")
IMPLEMENTATION_STATUSES = (
    "IMPLEMENTED_REAL",
    "IMPLEMENTED_FIXTURE",
    "IMPLEMENTED_UNTESTED",
    "SCAFFOLD",
    "ABSENT",
)

# Claims whose tests cross modules, and claims whose tests include hostile or generated inputs.
PIPELINE = frozenset({"A1", "A4", "C1", "C5", "C7", "C12", "E3", "F4", "G5", "I1", "I4"})
BOUNDARY = frozenset({"A4", "A5", "C1", "C4", "C5", "C7", "C15", "D11", "F1", "G2", "I1", "I3", "I4", "I5"})


def implementation_status(claim: Claim) -> str:
    """Second axis. Evidence status is unchanged."""
    if claim.status == "UNSUPPORTED":
        return "ABSENT"
    if claim.status == "MODELED":
        return "IMPLEMENTED_REAL"
    if claim.status == "MEASURED":
        return "IMPLEMENTED_REAL"
    return "IMPLEMENTED_FIXTURE"


def required_layers(claim: Claim) -> tuple[str, ...]:
    required: list[str] = ["unit"]
    if claim.status in {"MEASURED", "DECLARED"}:
        required.append("invariant")
    if claim.status in {"MEASURED", "MODELED"}:
        required.append("benchmark")
    if claim.id in PIPELINE:
        required.extend(["integration", "e2e"])
    if claim.id in BOUNDARY:
        required.extend(["adversarial", "property"])
    return tuple(dict.fromkeys(required))


def render_coverage(present: dict[str, set[str]]) -> str:
    lines = [
        "# Unified analytics coverage map",
        "",
        "Evidence status is unchanged. Implementation status is the second axis.",
        "Benchmark numbers are in `reports/toe_unified_benchmark.json`.",
        "Datasets: UCI Iris (`tests/fixtures/toe_unified/iris.data`) and the program cost sheet.",
        "",
        "| claim_id | evidence_status | implementation_status | tests_present | tests_required | gap_summary |",
        "|---|---|---|---|---|---|",
    ]
    for claim in CLAIMS:
        got = tuple(layer for layer in LAYERS if layer in present.get(claim.id, ()))
        need = required_layers(claim)
        gap = tuple(layer for layer in need if layer not in got)
        lines.append(
            "| {id} | {evidence} | {impl} | {present} | {required} | {gap} |".format(
                id=claim.id,
                evidence=claim.status,
                impl=implementation_status(claim),
                present=", ".join(got) or "—",
                required=", ".join(need),
                gap=", ".join(gap) or "none",
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_disposition() -> str:
    lines = [
        "# Unified analytics claim disposition",
        "",
        "Authority for the narrative that is not stored in this repository.",
        "Status is `MEASURED`, `DECLARED`, `MODELED`, or `UNSUPPORTED`.",
        "`MEASURED` and `MODELED` and `DECLARED` each name a test.",
        "Every row names a test. There is no unsupported row.",
        "",
        "| id | status | module | test | claim | note |",
        "|---|---|---|---|---|---|",
    ]
    for claim in CLAIMS:
        module = claim.module or "—"
        test = claim.test or "—"
        lines.append(
            f"| {claim.id} | {claim.status} | `{module}` | `{test}` | {claim.text} | {claim.note} |"
        )
    lines.append("")
    return "\n".join(lines)
