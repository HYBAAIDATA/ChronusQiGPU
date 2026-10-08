from __future__ import annotations

from types import SimpleNamespace

from m3_mining_guard import M3MiningSubmissionGate


class _GuardianAPI:
    def __init__(self) -> None:
        self.calls = []

    def evaluate(self, *, headers, body, now=None, include_evidence=False):
        self.calls.append(
            {
                "headers": dict(headers),
                "body": dict(body),
                "now": now,
                "include_evidence": include_evidence,
            }
        )
        return 200, {
            "allowed": True,
            "reason": "ALLOWED",
            "evidence_id": "guardian-evidence-1",
            "policy_version": "policy-v1",
            "intelligence_evidence_hash": "toe-evidence-hash",
        }


def _gate(api) -> M3MiningSubmissionGate:
    gate = M3MiningSubmissionGate.__new__(M3MiningSubmissionGate)
    gate.recorder = SimpleNamespace()
    gate.tenant = "tenant-a"
    gate.actor = "pythia-miner"
    gate.subscription_token = "signed-token"
    gate.guardian_api = api
    return gate


def test_hot_path_uses_guardian_api_with_exact_work_as_observation():
    api = _GuardianAPI()
    gate = _gate(api)
    payload = {
        "pool_endpoint": "pool.example:3333",
        "worker": "acct.worker",
        "generation": 7,
        "job_fingerprint": "fp-7",
    }

    verdict = gate._evaluate_guardian(
        operation="mining.lease",
        resource="stratum://pool.example:3333",
        payload=payload,
        request_id="lease:session:7:fp-7",
    )

    assert verdict["allowed"] is True
    assert verdict["intelligence_evidence_hash"] == "toe-evidence-hash"
    assert verdict["http_status"] == 200
    assert len(api.calls) == 1
    call = api.calls[0]
    assert call["headers"] == {
        "x-hyba-tenant": "tenant-a",
        "x-hyba-actor": "pythia-miner",
        "authorization": "Bearer signed-token",
    }
    assert call["body"]["operation"] == "mining.lease"
    assert call["body"]["payload"] == payload
    assert call["body"]["observation"] == payload


def test_guardian_api_failure_is_a_fail_closed_verdict():
    class BrokenAPI:
        def evaluate(self, **kwargs):
            raise RuntimeError("provider unavailable")

    gate = _gate(BrokenAPI())
    verdict = gate._evaluate_guardian(
        operation="mining.submit",
        resource="stratum://pool.example:3333",
        payload={"generation": 7},
        request_id="candidate-1",
    )

    assert verdict["allowed"] is False
    assert verdict["reason"] == "AL_HARAS_UNAVAILABLE:RuntimeError"
    assert verdict["http_status"] == 503



class _RecoveryRecorder:
    def __init__(self) -> None:
        self.persisted = []

    def health(self, *, reconcile):
        return {"healthy": True}

    def persist_authorization(self, verdict, *, context):
        self.persisted.append((dict(verdict), dict(context)))
        return "fv-recovery-1"


def test_recovery_authorization_is_guarded_and_custodied_before_dispatch():
    api = _GuardianAPI()
    gate = _gate(api)
    gate.recorder = _RecoveryRecorder()
    record = SimpleNamespace(
        recovery_id="recovery:1",
        origin="self_healing_agent",
        commands=("RESTART_LANE",),
        reason="device error",
    )

    verdict = gate.authorize_recovery(
        record,
        "RESTART_LANE",
        "pythia.mining.runtime",
    )

    assert verdict["allowed"] is True
    assert verdict["authorization_evidence_id"] == "guardian-evidence-1"
    assert verdict["authorization_version_id"] == "fv-recovery-1"
    assert len(api.calls) == 1
    call = api.calls[0]
    assert call["body"]["operation"] == "mining.escalate"
    assert call["body"]["resource"] == "pythia.mining.runtime"
    assert call["body"]["payload"]["recovery_id"] == "recovery:1"
    assert call["body"]["payload"]["command"] == "RESTART_LANE"
    assert gate.recorder.persisted[0][1]["authority"] == "SALAMANDER"


def test_recovery_authorization_refuses_unhealthy_custody_without_guardian_call():
    api = _GuardianAPI()
    gate = _gate(api)
    gate.recorder = SimpleNamespace(
        health=lambda reconcile: {"healthy": False, "reason": "corrupt"}
    )
    record = SimpleNamespace(
        recovery_id="recovery:2",
        origin="self_healing_agent",
        commands=("RESTART_LANE",),
        reason="device error",
    )

    verdict = gate.authorize_recovery(
        record,
        "RESTART_LANE",
        "pythia.mining.runtime",
    )

    assert verdict["allowed"] is False
    assert verdict["reason"] == "THESEUS_STORAGE_UNHEALTHY"
    assert api.calls == []
