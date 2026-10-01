"""The knowledge fabric: shared, entangled knowledge across intelligences."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from chronus.mla1517.knowledge import JournalCorrupted, KnowledgeFabric


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def _fabric(journal=None) -> KnowledgeFabric:
    return KnowledgeFabric(journal, clock=Clock())


def test_facts_are_versioned_per_source_and_topic_and_unchanged_values_do_not_churn():
    k = _fabric()
    first = k.publish("mining.world", "mining.world", {"rate": 1.0}, evidence="measured")
    again = k.publish("mining.world", "mining.world", {"rate": 1.0}, evidence="measured")
    assert again is first and len(k.facts) == 1
    second = k.publish("mining.world", "mining.world", {"rate": 2.0}, evidence="measured")
    assert (first.version, second.version) == (1, 2)
    assert k.observe("mining.world") == second
    other = k.publish("salamander", "mining.world", {"rate": 9.0}, evidence="declared")
    assert k.observe("mining.world", source="mining.world") == second
    assert k.observe("mining.world") == other  # the latest from any source
    assert k.observe("nothing.here") is None


def test_superseding_a_fact_decoheres_everything_derived_from_it():
    k = _fabric()
    events = []
    k.subscribe("*", lambda event, fact: events.append((event, fact.topic)))
    world = k.publish("world", "mining.world", {"h": 1}, evidence="measured")
    policy = k.publish(
        "policy", "mining.policy", {"w": 96}, evidence="computed", depends_on=[world]
    )
    finding = k.publish(
        "discovery", "discovery.policy", {"law": "x"}, evidence="simulated", depends_on=[policy]
    )
    unrelated = k.publish("governor", "mining.governor", {"cap": 1e18}, evidence="computed")
    assert not any(k.stale(f) for f in (world, policy, finding, unrelated))

    k.publish("world", "mining.world", {"h": 2}, evidence="measured")
    assert k.stale(policy) and k.stale(finding)  # transitively, at once
    assert not k.stale(unrelated)
    assert ("decohered", "mining.policy") in events and ("decohered", "discovery.policy") in events

    renewed = k.publish(
        "policy",
        "mining.policy",
        {"w": 96},
        evidence="computed",
        depends_on=[k.observe("mining.world")],
    )
    assert not k.stale(renewed)  # same value, fresh basis: coherent again


def test_a_fact_derived_from_superseded_knowledge_is_born_stale():
    k = _fabric()
    old = k.publish("world", "mining.world", {"h": 1}, evidence="measured")
    k.publish("world", "mining.world", {"h": 2}, evidence="measured")
    late = k.publish("policy", "mining.policy", {"w": 1}, evidence="computed", depends_on=[old])
    assert k.stale(late)


def test_invalid_knowledge_is_refused():
    k = _fabric()
    with pytest.raises(ValueError, match="unknown fact"):
        k.publish("policy", "mining.policy", {}, evidence="computed", depends_on=["f" * 64])
    with pytest.raises(ValueError, match="evidence"):
        k.publish("policy", "mining.policy", {}, evidence="rumour")
    with pytest.raises(ValueError):
        k.publish("", "mining.policy", {}, evidence="computed")
    for not_json in ({1, 2}, {"t": (1, 2)}, {1: "int key"}, float("nan")):
        with pytest.raises((TypeError, ValueError)):
            k.publish("policy", "mining.policy", not_json, evidence="computed")
    assert k.facts == {}


def test_the_joint_digest_names_one_shared_world():
    a, b = _fabric(), _fabric()
    for fabric in (a, b):
        fabric.publish("world", "mining.world", {"h": 1}, evidence="measured")
    assert a.joint_digest() == b.joint_digest()  # the same knowledge: the same world
    b.publish("world", "mining.world", {"h": 5}, evidence="measured")
    assert a.joint_digest() != b.joint_digest()

    shared = []
    k = _fabric()
    world = k.publish("world", "mining.world", {"h": 1}, evidence="measured")
    k.publish("policy", "mining.policy", {"w": 1}, evidence="computed", depends_on=[world])
    shared.append(k.joint_digest())
    k.publish("world", "mining.world", {"h": 2}, evidence="measured")
    shared.append(k.joint_digest())
    assert shared[0] != shared[1]  # a decoherence changes the joint state


def test_two_fabrics_on_one_journal_share_knowledge_and_its_decoherence(tmp_path):
    journal = tmp_path / "knowledge.jsonl"
    miner, discovery = _fabric(journal), _fabric(journal)
    world = miner.publish("world", "mining.world", {"h": 1}, evidence="measured")
    assert discovery.sync() == 1
    finding = discovery.publish(
        "discovery", "discovery.policy", {"law": "x"}, evidence="simulated", depends_on=[world]
    )
    assert miner.sync() == 1 and miner.observe("discovery.policy") == finding
    miner.publish("world", "mining.world", {"h": 2}, evidence="measured")
    discovery.sync()
    assert discovery.stale(finding)
    assert miner.joint_digest() == discovery.joint_digest()
    fresh = _fabric(journal)  # a process started later replays everything
    assert fresh.joint_digest() == miner.joint_digest() and len(fresh.facts) == 3


def test_a_separate_process_can_publish_into_the_same_world(tmp_path):
    journal = tmp_path / "knowledge.jsonl"
    here = _fabric(journal)
    world = here.publish("world", "mining.world", {"h": 1}, evidence="measured")
    platform = Path(__file__).resolve().parent
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(platform)!r})
        from chronus.mla1517.knowledge import KnowledgeFabric
        k = KnowledgeFabric({str(journal)!r})
        world = k.observe("mining.world")
        k.publish("salamander", "salamander.recovery", {{"state": "VERIFIED"}},
                  evidence="measured", depends_on=[world])
        """)
    subprocess.run([sys.executable, "-c", script], check=True, timeout=60)
    assert here.sync() == 1
    recovery = here.observe("salamander.recovery")
    assert recovery.depends_on == (world.fact_id,) and not here.stale(recovery)


def test_a_tampered_journal_is_refused_not_repaired(tmp_path):
    journal = tmp_path / "knowledge.jsonl"
    k = _fabric(journal)
    k.publish("world", "mining.world", {"h": 1}, evidence="measured")
    k.publish("governor", "mining.governor", {"cap": 1.0}, evidence="computed")
    lines = journal.read_text().splitlines()
    record = json.loads(lines[0])
    record["fact"]["value"] = {"h": 1000}
    journal.write_text(json.dumps(record) + "\n" + lines[1] + "\n")
    reader = _fabric(journal)
    assert reader.integrity_error and "chain break" in reader.integrity_error
    assert reader.facts == {}
    with pytest.raises(JournalCorrupted):
        reader.publish("x", "y", {}, evidence="declared")


def test_a_line_still_being_written_is_not_consumed(tmp_path):
    journal = tmp_path / "knowledge.jsonl"
    writer = _fabric(journal)
    writer.publish("world", "mining.world", {"h": 1}, evidence="measured")
    complete = journal.read_text()
    journal.write_text(complete + '{"prev": "partial')  # a writer mid-line
    reader = _fabric(journal)
    assert len(reader.facts) == 1 and reader.integrity_error is None


def test_the_snapshot_reports_sources_topics_and_staleness():
    k = _fabric()
    world = k.publish("world", "mining.world", {"h": 1}, evidence="measured")
    k.publish("policy", "mining.policy", {"w": 1}, evidence="computed", depends_on=[world])
    k.publish("world", "mining.world", {"h": 2}, evidence="measured")
    snap = k.snapshot()
    assert (snap["facts"], snap["current"], snap["stale"]) == (3, 2, 1)
    assert snap["sources"] == ["policy", "world"]
    assert snap["recent"][0]["value"] == {"h": 2} and snap["recent"][0]["stale"] is False


def test_a_mining_coordinator_shares_what_it_learns(tmp_path, monkeypatch):
    import asyncio

    from manifold_pool_coordinator import PoolEndpoint
    from test_agentic_voyages import EASY_TARGET, FakePool, _connected, _job, _served, bip34_coinb1
    from test_pool_only_mining import _poll, _pool_only_coordinator

    monkeypatch.setenv("PYTHIA_INTELLIGENCE_DIR", str(tmp_path))
    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "absent.json"))

    async def mine():
        pool = FakePool(target=EASY_TARGET, job=_job("job-k", coinb1=bip34_coinb1(900_001)))
        server, port = await _served(pool)
        coord = _pool_only_coordinator([PoolEndpoint("127.0.0.1", port, "ckpool")])
        try:
            await _connected(coord, "job-k")
            assert await _poll(coord) is True
            await coord.search_current_job()
            return coord
        finally:
            await coord.client.close()
            server.close()

    coord = asyncio.run(mine())
    knowledge = coord.knowledge
    world = knowledge.observe("mining.world")
    policy = knowledge.observe("mining.policy")
    governor = knowledge.observe("mining.governor")
    assert world.source == "mining.world_model" and world.evidence == "measured"
    assert policy.depends_on == (world.fact_id,) and not knowledge.stale(policy)
    assert governor.value["shares"] == 1
    # Another process (here: another fabric on the same journal) sees it all.
    other = KnowledgeFabric(tmp_path / "knowledge.jsonl")
    assert other.joint_digest() == knowledge.joint_digest()
    topics = coord.intelligence_snapshot()["knowledge"]["topics"]
    assert {"mining.governor", "mining.policy", "mining.world"} <= set(topics)
    # The questions it is asked, and how its learning stands, are shared too.
    assert {"question.window.elapsed", "learning.window.elapsed"} <= set(topics)
    assert knowledge.observe("learning.shares.follow.work").value["observed"] == 1
