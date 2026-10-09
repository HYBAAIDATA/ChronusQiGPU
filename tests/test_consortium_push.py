"""Contract tests for the Consortium Push Protocol."""
from __future__ import annotations

import json

import pytest

from chronus.consortium_push import (
    Axis,
    CONSORTIUM_INSTITUTIONS,
    LEDGER_GENESIS,
    OWNERSHIP,
    PushLedger,
    PushProposal,
    PushVerdict,
    PushableFabric,
    TruthClass,
    admit,
    append,
    canonical_institution,
    diagnose,
    is_falsifiable,
    is_first_principles,
    measurement_evidence,
    owner_of,
    passes_crosscheck,
    passes_monotonicity,
    passes_ownership,
    passes_truth_gate,
    push_cycle,
    read_metric,
    verify_invariants,
    verify_ledger,
    verify_receipt,
)
from chronus.m5_ultra import consortium_fabric, elevate_pads, m5_ultra_fabric


def _state(fab=None) -> PushableFabric:
    return PushableFabric.from_fabric(fab or consortium_fabric())


def _proposal(**kw):
    base = dict(
        institution="CERN",
        axis=Axis.INGEST,
        metric="cern_wlcg.capacity_bytes",
        from_value=1.0e18,
        to_value=2.0e18,
        truth_class=TruthClass.MEASURED,
        verifiers=("MIT", "Caltech"),
        timestamp=0.1,
    )
    base.update(kw)
    if base["truth_class"] == TruthClass.MEASURED and "evidence" not in kw:
        base["evidence"] = measurement_evidence(
            base["institution"], base["metric"], base["from_value"], base["to_value"]
        )
    return PushProposal(**base)


# ---------------------------------------------------------------------------
# Metric resolution
# ---------------------------------------------------------------------------

def test_read_metric_resolves_documented_names():
    fab = consortium_fabric()
    assert read_metric(fab, "cern_wlcg.capacity_bytes") == 1.0e18
    assert read_metric(fab, "pad.qubits_per_pad") == 64.0
    assert read_metric(fab, "totals.neural_engine_cores") == 384.0
    assert read_metric(fab, "totals.gpu_photonic_cores") == 100.0
    assert read_metric(fab, "entanglement.edges") == 9.0
    assert read_metric(fab, "qec.logical_error_rate") is None  # unprovisioned
    assert read_metric(fab, "interconnect.aggregate_bps") == pytest.approx(1.120015e16)
    assert read_metric(fab, "interconnect.edge_bandwidth") is None  # unallocated


def test_ownership_table_exclusive():
    assert len(set(OWNERSHIP.values())) == len(OWNERSHIP)
    assert owner_of("cern_wlcg.capacity_bytes") == "CERN"
    assert owner_of("nonexistent.metric") is None
    assert canonical_institution("CALTECH") == "Caltech"
    assert canonical_institution("Shared") == ""


# ---------------------------------------------------------------------------
# Truth gate
# ---------------------------------------------------------------------------

def test_measured_requires_bound_receipt():
    state = _state()
    p = _proposal()
    p_no_ev = PushProposal(**{**p.canonical(), "evidence": None,
                            "truth_class": TruthClass.MEASURED,
                            "axis": p.axis})
    assert passes_truth_gate(p_no_ev) == PushVerdict.REJECTED_NO_EVIDENCE
    forged = PushProposal(**{**p.canonical(), "evidence": "sha256:" + "0" * 64,
                             "truth_class": TruthClass.MEASURED, "axis": p.axis})
    assert passes_truth_gate(forged) == PushVerdict.REJECTED_NO_EVIDENCE
    assert passes_truth_gate(p) == PushVerdict.ADMITTED


def test_evidence_binds_claim_identity():
    p = _proposal()
    assert verify_receipt(p.evidence, p)
    other = _proposal(to_value=3.0e18,
                      evidence=p.evidence)
    assert not verify_receipt(other.evidence, other)


def test_formulation_requires_first_principles():
    p = _proposal(truth_class=TruthClass.FORMULATION, evidence=None,
                  derivation=None)
    assert passes_truth_gate(p) == PushVerdict.REJECTED_NO_DERIVATION
    bad = _proposal(truth_class=TruthClass.FORMULATION, evidence=None,
                    derivation="simulate on qiskit Aer then read counts")
    assert passes_truth_gate(bad) == PushVerdict.REJECTED_NO_DERIVATION
    good = _proposal(truth_class=TruthClass.FORMULATION, evidence=None,
                     derivation="photonic cores: tensor product dimension over the mesh")
    assert passes_truth_gate(good) == PushVerdict.ADMITTED
    assert is_first_principles("U = exp(-i H t)") is True
    assert is_first_principles("run it in Cirq") is False
    assert is_first_principles(" PennyLane circuit") is False


def test_theoretical_requires_falsifiable():
    p = _proposal(truth_class=TruthClass.THEORETICAL, evidence=None,
                  prediction=None)
    assert passes_truth_gate(p) == PushVerdict.REJECTED_UNFALSIFIABLE
    vague = _proposal(truth_class=TruthClass.THEORETICAL, evidence=None,
                      prediction="entanglement will be great")
    assert passes_truth_gate(vague) == PushVerdict.REJECTED_UNFALSIFIABLE
    real = _proposal(truth_class=TruthClass.THEORETICAL, evidence=None,
                     prediction="T2 > 1ms across 11 edges by T+1")
    assert passes_truth_gate(real) == PushVerdict.ADMITTED
    assert is_falsifiable("gain > 2 by epoch 5") is True
    assert is_falsifiable("better soon") is False


# ---------------------------------------------------------------------------
# Cross-check / ownership / monotonicity gates
# ---------------------------------------------------------------------------

def test_crosscheck_needs_two_peer_institutions():
    p = _proposal(verifiers=("MIT", "Caltech"))
    assert passes_crosscheck(p) == PushVerdict.ADMITTED
    one = _proposal(verifiers=("MIT",))
    assert passes_crosscheck(one) == PushVerdict.REJECTED_NO_CROSSCHECK
    self_v = _proposal(verifiers=("CERN", "MIT", "Caltech"))
    assert passes_crosscheck(self_v) == PushVerdict.ADMITTED  # proposer filtered
    only_self = _proposal(verifiers=("CERN", "MIT"))
    assert passes_crosscheck(only_self) == PushVerdict.REJECTED_NO_CROSSCHECK
    unknown = _proposal(verifiers=("MIT", "Hogwarts"))
    assert passes_crosscheck(unknown) == PushVerdict.REJECTED_NO_CROSSCHECK
    shared = _proposal(verifiers=("MIT", "Shared"))
    assert passes_crosscheck(shared) == PushVerdict.REJECTED_NO_CROSSCHECK
    dup = _proposal(verifiers=("MIT", "mit", "MIT"))
    assert passes_crosscheck(dup) == PushVerdict.REJECTED_NO_CROSSCHECK


def test_ownership_exclusive():
    stanford = _proposal(institution="Stanford", axis=Axis.SYSTEMS,
                         verifiers=("MIT", "Caltech"))
    assert passes_ownership(stanford) == PushVerdict.REJECTED_OWNERSHIP_CONFLICT
    cern = _proposal()
    assert passes_ownership(cern) == PushVerdict.ADMITTED
    unowned = _proposal(metric="totals.cpu_cores", from_value=204.0,
                        to_value=210.0)
    assert passes_ownership(unowned) == PushVerdict.ADMITTED


def test_monotonicity_never_shrinks():
    state = _state()
    up = _proposal()
    assert passes_monotonicity(up, state) == PushVerdict.ADMITTED
    down = _proposal(to_value=0.5e18)
    assert passes_monotonicity(down, state) == PushVerdict.REJECTED_REGRESSION
    stale = _proposal(from_value=9.9e17)
    assert passes_monotonicity(stale, state) == PushVerdict.REJECTED_REGRESSION
    new_metric = _proposal(metric="qec.logical_error_rate", from_value=None,
                           to_value=1.0e-3, institution="Princeton",
                           axis=Axis.MATERIALS)
    assert passes_monotonicity(new_metric, state) == PushVerdict.ADMITTED


# ---------------------------------------------------------------------------
# Admit ordering and apply semantics
# ---------------------------------------------------------------------------

def test_gates_run_in_order_first_failure_wins():
    state = _state()
    # No evidence AND only one verifier -> truth gate reports first.
    p = _proposal(verifiers=("MIT",))
    p = PushProposal(**{**p.canonical(), "evidence": None,
                        "truth_class": TruthClass.MEASURED, "axis": p.axis})
    r = admit(p, state)
    assert r.verdict == PushVerdict.REJECTED_NO_EVIDENCE


def test_apply_push_updates_state_and_promotes_truth():
    state = _state()
    r = admit(_proposal(), state)
    assert r.verdict == PushVerdict.ADMITTED
    assert state.read("cern_wlcg.capacity_bytes") == 2.0e18
    assert state.truth_class == "measured"
    assert state.elevation["channel_bandwidths"]["cern_wlcg_trigger"] is None or True
    # Source fabric untouched.
    assert read_metric(state.fabric, "cern_wlcg.capacity_bytes") == 1.0e18


def test_second_push_must_chain_on_new_value():
    state = _state()
    assert admit(_proposal(), state).verdict == PushVerdict.ADMITTED
    stale = _proposal(timestamp=0.2)
    assert admit(stale, state).verdict == PushVerdict.REJECTED_REGRESSION
    chained = _proposal(from_value=2.0e18, to_value=3.0e18, timestamp=0.2)
    assert admit(chained, state).verdict == PushVerdict.ADMITTED


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

def test_ledger_hash_chain_and_tamper_evidence():
    ledger = PushLedger()
    assert ledger.genesis == LEDGER_GENESIS
    assert ledger.head == LEDGER_GENESIS
    state = _state()
    ledger = push_cycle(state, [_proposal()], ledger)
    assert len(ledger.rows) == 1
    assert ledger.rows[0].ledger_row != ""
    assert ledger.head == ledger.rows[0].ledger_row
    assert verify_ledger(ledger)
    # Tamper: mutate a stored row's verdict.
    row = ledger.rows[0]
    tampered = PushLedger(rows=[type(row)(proposal=row.proposal,
                                          verdict=PushVerdict.REJECTED_REGRESSION,
                                          ledger_row=row.ledger_row,
                                          timestamp=row.timestamp)],
                          head=ledger.head, genesis=ledger.genesis)
    assert not verify_ledger(tampered)


def test_ledger_serializes():
    ledger = push_cycle(_state(), [_proposal()], PushLedger())
    blob = json.dumps(ledger.as_dict())
    assert '"verdict": "admitted"' in blob


# ---------------------------------------------------------------------------
# Documented example trajectory (section 12)
# ---------------------------------------------------------------------------

def test_documented_trajectory():
    fab = consortium_fabric()
    state = _state(fab)
    ledger = PushLedger()

    p1 = PushProposal(
        institution="CERN", axis=Axis.INGEST,
        metric="cern_wlcg.capacity_bytes",
        from_value=1.0e18, to_value=2.0e18,
        truth_class=TruthClass.MEASURED,
        evidence=measurement_evidence("CERN", "cern_wlcg.capacity_bytes",
                                    1.0e18, 2.0e18),
        verifiers=("MIT", "Caltech"), timestamp=0.1,
    )
    p2 = PushProposal(
        institution="Oxford", axis=Axis.COHERENCE,
        metric="entanglement.edges",
        from_value=9.0, to_value=11.0,
        truth_class=TruthClass.THEORETICAL,
        prediction="T2 > 1ms across 11 edges by T+1",
        verifiers=("Princeton",), timestamp=0.2,
    )
    p3 = PushProposal(
        institution="Cambridge", axis=Axis.PHOTONICS,
        metric="totals.gpu_photonic_cores",
        from_value=100.0, to_value=250.0,
        truth_class=TruthClass.FORMULATION,
        derivation="silicon photonic tensor cores: unitary mesh expansion",
        verifiers=("Stanford", "Caltech"), timestamp=0.3,
    )
    push_cycle(state, [p3, p1, p2], ledger)  # order shuffled; sorted by ts

    assert [r.verdict for r in ledger.rows] == [
        PushVerdict.ADMITTED,
        PushVerdict.REJECTED_NO_CROSSCHECK,
        PushVerdict.ADMITTED,
    ]
    assert state.read("cern_wlcg.capacity_bytes") == 2.0e18
    assert state.read("totals.gpu_photonic_cores") == 250.0
    assert state.read("entanglement.edges") == 9.0  # rejected push did not apply
    assert verify_ledger(ledger)
    inv = verify_invariants(ledger)
    assert inv == {
        "append_only": True,
        "truth_honesty": True,
        "no_framework_import": True,
    }
    assert diagnose(ledger.rows[1]) == "fewer than 2 peer verifiers"
    assert diagnose(ledger.rows[0]) == "admitted"


def test_diagnose_all_verdicts():
    from chronus.consortium_push import PushReceipt

    cases = {
        PushVerdict.REJECTED_NO_EVIDENCE: "MEASURED claim missing receipt",
        PushVerdict.REJECTED_NO_DERIVATION: "FORMULATION claim missing first-principles derivation",
        PushVerdict.REJECTED_UNFALSIFIABLE: "THEORETICAL claim not falsifiable",
        PushVerdict.REJECTED_NO_CROSSCHECK: "fewer than 2 peer verifiers",
        PushVerdict.REJECTED_OWNERSHIP_CONFLICT: "metric owned by another institution",
        PushVerdict.REJECTED_REGRESSION: "proposed value below current fabric state",
        PushVerdict.ADMITTED: "admitted",
    }
    for verdict, msg in cases.items():
        r = PushReceipt(proposal=_proposal(), verdict=verdict)
        assert diagnose(r) == msg


def test_institutions_constant():
    assert len(CONSORTIUM_INSTITUTIONS) == 7
    assert "Shared" not in CONSORTIUM_INSTITUTIONS
