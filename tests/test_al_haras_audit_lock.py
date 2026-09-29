"""The persistent AL HARAS ledger builds and serialises writers on every OS."""

from __future__ import annotations

import threading

from al_haras.audit import HashChainAudit


def test_persistent_audit_builds_and_chains_on_this_platform(tmp_path):
    path = tmp_path / "audit" / "decisions.jsonl"
    audit = HashChainAudit(path)
    audit.append({"decision": "allow"})
    audit.append({"decision": "deny"})

    reopened = HashChainAudit(path)
    records = reopened.records
    assert len(records) == 2
    assert HashChainAudit.verify(records)
    assert records[1]["previous_hash"] == records[0]["record_hash"]


def test_concurrent_writers_keep_one_valid_chain(tmp_path):
    path = tmp_path / "decisions.jsonl"
    HashChainAudit(path)

    def writer(worker: int) -> None:
        ledger = HashChainAudit(path)
        for index in range(10):
            ledger.append({"worker": worker, "index": index})

    threads = [threading.Thread(target=writer, args=(worker,)) for worker in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    records = HashChainAudit(path).records
    assert len(records) == 40
    assert HashChainAudit.verify(records)
