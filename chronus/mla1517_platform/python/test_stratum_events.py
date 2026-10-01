"""Stratum snapshots become a bounded, literal telemetry event stream."""

from __future__ import annotations

from chronus.mla1517.mining.stratum_events import StratumEventLog

TARGET = "00000000" + "ff" * 28


def snap(
    state="READY",
    *,
    transport="CONNECTED",
    job_id="j1",
    generation=1,
    difficulty=8192,
    target=TARGET,
    accepted=0,
    rejected=0,
    unknown=0,
    error=None,
    submitted_job="j1",
):
    return {
        "state": state,
        "primary": {
            "pool_id": "braiins",
            "endpoint": "stratum.braiins.com:3333",
            "transport": transport,
            "subscribed": True,
            "authorized": state == "READY",
            "last_error": error,
        },
        "job": {
            "active": generation is not None,
            "generation": generation,
            "job_id": job_id,
            "clean_jobs": True,
            "difficulty": difficulty,
            "difficulty_source": "mining.set_difficulty",
            "share_target": target,
            "target_generation": 1,
        },
        "submission": {"job_id": submitted_job, "generation": generation},
        "counters": {
            "jobs_received": generation or 0,
            "disconnects": 0,
            "submitted": accepted + rejected + unknown,
            "accepted": accepted,
            "rejected": rejected,
            "unknown": unknown,
        },
    }


def test_session_edges_become_events():
    log = StratumEventLog(clock=lambda: 1.0)
    log.observe(
        snap("CONNECTING", transport="DISCONNECTED", generation=None, difficulty=None, target=None)
    )
    log.observe(snap())
    log.observe(snap(job_id="j2", generation=2))
    log.observe(snap(job_id="j2", generation=2, accepted=1, submitted_job="j2"))

    kinds = [event["kind"] for event in log.events()]
    assert kinds == ["state", "state", "job", "difficulty", "target", "job", "share"]
    connected = log.events()[1]
    assert (connected["previous"], connected["state"]) == ("CONNECTING", "READY")
    job = log.events()[2]
    assert (job["job_id"], job["difficulty"], job["share_target"]) == ("j1", 8192, TARGET)
    share = log.events()[-1]
    assert (share["result"], share["job_id"], share["total"]) == ("ACCEPTED", "j2", 1)
    assert log.payload()["totals"]["accepted"] == 1
    assert [event["seq"] for event in log.events()] == list(range(1, 8))


def test_share_totals_survive_a_reconnect():
    log = StratumEventLog()
    log.observe(snap(accepted=2))
    log.observe(snap("CONNECTING", transport="DISCONNECTED", generation=None, accepted=0))
    log.observe(snap(accepted=1))
    assert log.totals["accepted"] == 3
    assert [e["total"] for e in log.events() if e["kind"] == "share"] == [2, 3]


def test_authorization_failure_and_rejections_are_reported():
    log = StratumEventLog()
    log.observe(
        snap(
            "AUTH_FAILED",
            transport="DISCONNECTED",
            generation=None,
            error="mining.authorize was rejected",
        )
    )
    log.observe(snap(rejected=1, unknown=1))
    errors = [e for e in log.events() if e["kind"] == "error"]
    assert errors and "authorize" in errors[0]["message"]
    results = {e["result"] for e in log.events() if e["kind"] == "share"}
    assert results == {"REJECTED", "OUTCOME_UNKNOWN"}


def test_the_log_is_bounded_and_keeps_counting():
    log = StratumEventLog(maxlen=5)
    for generation in range(1, 20):
        log.observe(snap(job_id=f"j{generation}", generation=generation))
    assert len(log.events()) == 5
    assert log.payload()["last_seq"] > 5
    assert log.events()[-1]["job_id"] == "j19"
