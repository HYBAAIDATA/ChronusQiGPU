"""Evidence locks for distributed enterprise scopes (Rule 7 — software-measured).

Scopes proven here:
  - distributed_consensus_software_multi_node_local
  - multi_root_multi_node_custody_software
  - cross_region_dr_software_simulated_regions
  - hyperscaler_soak_software_local_fleet
  - chronus_hardware_perf_measured
  - solutions_api_readiness_software
  - enterprise_hyba_certification_gate_software
"""
from __future__ import annotations

import json
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from aethel.enterprise import (
    ChronusPerfProbe,
    CrossRegionDR,
    HybaEnterpriseCertificate,
    HyperscalerSoak,
    MultiNodeCluster,
    SolutionsAPI,
    compose,
)
from aethel.enterprise.authenticity import content_digest
from aethel.enterprise.errors import (
    CertificationError,
    ConsensusError,
    NotLeaderError,
)

HMAC = b"test-distributed-hmac-key!!"  # >=16 bytes
assert len(HMAC) >= 16


@pytest.fixture()
def base(tmp_path: Path) -> Path:
    return tmp_path / "dist"


def _cluster(base: Path, n: int = 3) -> MultiNodeCluster:
    return MultiNodeCluster.bootstrap(
        n,
        base / "cluster",
        HMAC,
        allow_insecure_dev_key=True,
    )


# ---------------------------------------------------------------------------
# 1–2. Consensus + leader failover
# ---------------------------------------------------------------------------


def test_three_node_elects_leader(base: Path) -> None:
    c = _cluster(base, 3)
    try:
        leader = c.wait_leader(timeout=5.0)
        assert leader.role == "leader"
        h = c.health()
        assert h["leader"] == str(leader.node_id)
        assert h["claim_scope_consensus"] == (
            "distributed_consensus_software_multi_node_local"
        )
        assert h["alive"] == 3
    finally:
        c.close()


def test_put_replicates_and_survives_leader_loss(base: Path) -> None:
    c = _cluster(base, 3)
    try:
        leader = c.wait_leader(timeout=5.0)
        old_id = str(leader.node_id)
        payload = b"replicated-payload-v1"
        meta = c.put("rec-1", payload)
        assert meta["index"] >= 1
        assert c.get("rec-1") == payload
        assert c.majority_has("rec-1", payload)

        # stop leader; elect new; get still works
        c.stop_node(old_id)
        assert c.leader() is None or str(c.leader().node_id) != old_id
        new_leader = c.wait_leader(timeout=5.0)
        assert str(new_leader.node_id) != old_id
        assert new_leader.role == "leader"
        assert c.get("rec-1") == payload
        # still majority among alive (2 of 3 original; both should have data)
        alive_hits = sum(
            1
            for n in c.alive_nodes()
            if n.get_local("rec-1") == payload
        )
        assert alive_hits >= 2
    finally:
        c.close()


def test_follower_propose_raises_not_leader(base: Path) -> None:
    c = _cluster(base, 3)
    try:
        leader = c.wait_leader(timeout=5.0)
        followers = [n for n in c.alive_nodes() if n.node_id != leader.node_id]
        assert followers
        with pytest.raises(NotLeaderError):
            followers[0].propose("put", record_id="x", payload=b"nope")
    finally:
        c.close()


# ---------------------------------------------------------------------------
# 3. Multi-root
# ---------------------------------------------------------------------------


def test_multi_root_distinct_paths_and_majority_commit(base: Path) -> None:
    c = _cluster(base, 3)
    try:
        c.wait_leader(timeout=5.0)
        assert c.multi_root is not None
        assert c.multi_root.distinct_roots() is True
        paths = list(c.multi_root.root_paths().values())
        assert len(set(Path(p).resolve() for p in paths)) == 3
        payload = b"multi-root-data"
        c.put("mr-1", payload)
        # committed on majority roots via custody.get
        hits = 0
        for n in c.nodes.values():
            try:
                if n.custody.get("mr-1") == payload:
                    hits += 1
            except Exception:
                pass
        assert hits >= 2
        h = c.health()
        assert h["distinct_roots"] is True
        assert h["claim_scope_multi_root"] == "multi_root_multi_node_custody_software"
    finally:
        c.close()


# ---------------------------------------------------------------------------
# 4. Cross-region DR
# ---------------------------------------------------------------------------


def test_cross_region_dr_failover_reads_from_dr(base: Path) -> None:
    c = _cluster(base / "primary", 3)
    dr = CrossRegionDR(
        region_a=c,
        region_b_root=base / "region_b",
        hmac_key=HMAC,
        allow_insecure_dev_key=True,
    )
    try:
        c.wait_leader(timeout=5.0)
        payload = b"dr-critical-record"
        dr.put("dr-1", payload)
        snap = dr.replicate_snapshot()
        assert snap["claim_scope"] == "cross_region_dr_software_simulated_regions"
        assert snap["records"] >= 1

        # wipe/stop primary region
        fo = dr.failover()
        assert fo["active_region"] == "b"
        assert fo["primary_alive"] == 0
        assert dr.get("dr-1") == payload

        # failback elects again
        fb = dr.failback()
        assert fb["active_region"] == "a"
        assert fb["leader"]
    finally:
        dr.close()


# ---------------------------------------------------------------------------
# 5. Hyperscaler soak (local fleet)
# ---------------------------------------------------------------------------


def test_hyperscaler_soak_local_fleet(base: Path) -> None:
    c = _cluster(base, 3)
    try:
        c.wait_leader(timeout=5.0)
        soak = HyperscalerSoak(c, min_ops=200, min_workers=4)
        report = soak.run(workers=4, ops=200, fail_on_error=True)
        d = report.to_dict()
        assert d["ops_ok"] >= 200
        assert d["ops_fail"] == 0
        assert d["workers"] >= 4
        assert d["elapsed_s"] > 0
        assert d["throughput"] > 0
        assert d["claim_scope"] == "hyperscaler_soak_software_local_fleet"
    finally:
        c.close()


# ---------------------------------------------------------------------------
# 6. Chronus perf probe (honest)
# ---------------------------------------------------------------------------


def test_chronus_perf_probe_honest_timings(base: Path) -> None:
    probe = ChronusPerfProbe(
        base / "perf",
        HMAC,
        allow_insecure_dev_key=True,
    )
    report = probe.measure(ops=12, payload_size=128)
    d = report.to_dict()
    assert d["ops"] >= 12
    assert len(d["samples"]) >= 12
    assert all(isinstance(x, float) and x >= 0 for x in d["samples"])
    assert isinstance(d["p50"], float) and d["p50"] >= 0
    assert isinstance(d["p95"], float) and d["p95"] >= 0
    assert d["claim_scope"] == "chronus_hardware_perf_measured"
    assert d["device_flops"] is None  # never invent
    assert d["invented_metrics"] is False
    assert d["path"] in {"cpu", "chronus_accel"}
    assert isinstance(d["cpu_only"], bool)
    if d["path"] == "cpu":
        assert d["cpu_only"] is True
    if d["path"] == "chronus_accel":
        assert d["cpu_only"] is False
        assert d["parity_ok"] is True


# ---------------------------------------------------------------------------
# 7. Solutions API readiness
# ---------------------------------------------------------------------------


def test_solutions_api_readiness_true_after_smoke(base: Path) -> None:
    api = SolutionsAPI()
    api.create_store(
        "s1",
        base / "store1",
        HMAC,
        allow_insecure_dev_key=True,
    )
    r = api.readiness()
    assert r["solutions_api_ready"] is True
    assert r["claim_scope"] == "solutions_api_readiness_software"
    assert r["production_ready"] is False
    api.put("s1", "a", b"hello")
    assert api.get("s1", "a") == b"hello"
    h = api.health()
    assert "s1" in h["stores"]


def test_solutions_api_readiness_false_when_broken(base: Path) -> None:
    api = SolutionsAPI()
    api.create_store(
        "s1",
        base / "store_b",
        HMAC,
        allow_insecure_dev_key=True,
    )
    api.mark_broken()
    r = api.readiness()
    assert r["solutions_api_ready"] is False


def test_solutions_api_with_cluster(base: Path) -> None:
    c = _cluster(base, 3)
    try:
        c.wait_leader(timeout=5.0)
        api = SolutionsAPI()
        api.attach_cluster("c1", c)
        api.put("c1", "k", b"via-api")
        assert api.get("c1", "k") == b"via-api"
        st = api.cluster_status("c1")
        assert st["leader"]
        r = api.readiness()
        assert r["solutions_api_ready"] is True
    finally:
        c.close()


# ---------------------------------------------------------------------------
# 8. HYBA enterprise certificate gate
# ---------------------------------------------------------------------------


def test_hyba_certificate_pass_when_all_ok(base: Path) -> None:
    c = _cluster(base, 3)
    try:
        c.wait_leader(timeout=5.0)

        def check_leader() -> bool:
            return c.leader() is not None

        def check_put() -> dict:
            c.put("cert-1", b"ok")
            return {"ok": c.get("cert-1") == b"ok"}

        cert = HybaEnterpriseCertificate(
            required_evidence=[
                ("leader_elected", check_leader),
                ("put_get", check_put),
                "tests.test_enterprise_distributed_substrate",
            ]
        )
        issued = cert.issue()
        assert issued["status"] == "PASS"
        assert issued["claim_scope"] == "enterprise_hyba_certification_gate_software"
        assert issued["production_ready"] is False
        assert issued["evidence"]["leader_elected"]["status"] == "PASS"
        assert issued["evidence"]["put_get"]["status"] == "PASS"
    finally:
        c.close()


def test_hyba_certificate_fail_if_one_check_fails(base: Path) -> None:
    def ok() -> bool:
        return True

    def bad() -> bool:
        return False

    cert = HybaEnterpriseCertificate(
        required_evidence=[("ok", ok), ("forced_fail", bad)]
    )
    issued = cert.issue()
    assert issued["status"] == "FAIL"
    assert issued["evidence"]["forced_fail"]["status"] == "FAIL"
    assert issued["evidence"]["ok"]["status"] == "PASS"


def test_hyba_certificate_fail_on_exception() -> None:
    def boom() -> None:
        raise RuntimeError("forced")

    cert = HybaEnterpriseCertificate(required_evidence=[("boom", boom)])
    issued = cert.issue()
    assert issued["status"] == "FAIL"
    assert "error" in issued["evidence"]["boom"]


def test_hyba_certificate_empty_evidence_fails() -> None:
    cert = HybaEnterpriseCertificate(required_evidence=[])
    issued = cert.issue()
    assert issued["status"] == "FAIL"


# ---------------------------------------------------------------------------
# 9. Concurrent multi-thread attach (custody + cluster)
# ---------------------------------------------------------------------------


def test_concurrent_cluster_puts(base: Path) -> None:
    c = _cluster(base, 3)
    try:
        c.wait_leader(timeout=5.0)

        def job(i: int) -> bytes:
            rid = f"thr-{i}"
            payload = f"p-{i}".encode()
            c.put(rid, payload)
            return c.get(rid)

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(job, range(24)))
        assert len(results) == 24
        assert all(r.startswith(b"p-") for r in results)
    finally:
        c.close()


def _mp_worker(root_s: str, key: bytes, q: "mp.Queue[object]") -> None:
    """Child: open existing root, read seed, put unique id, verify, close."""
    import os
    import traceback

    pid = os.getpid()
    try:
        root = Path(root_s)
        cust = compose(root, hmac_key=key, allow_insecure_dev_key=True)
        try:
            seed = cust.get("seed")
            if seed != b"parent-seed":
                raise AssertionError(f"seed mismatch: {seed!r}")
            rid = f"child-{pid}"
            payload = f"from-{pid}".encode()
            cust.put(payload, record_id=rid)
            got = cust.get(rid)
            if got != payload:
                raise AssertionError(f"roundtrip fail {rid}: {got!r}")
            q.put(("ok", pid))
        finally:
            cust.close()
    except Exception:  # noqa: BLE001
        q.put(("err", traceback.format_exc()))


def test_simultaneous_multiprocess_attach_reopen(base: Path) -> None:
    """Parent seeds root; children attach concurrently; parent verifies all records.

    Uses multiprocessing spawn context for Windows stability. Children never race
    the parent's first open; each writes a unique record_id.
    """
    root = base / "mp_root"
    # Parent creates custody, puts seed, closes before children attach.
    parent = compose(root, hmac_key=HMAC, allow_insecure_dev_key=True)
    try:
        parent.put(b"parent-seed", record_id="seed")
        assert parent.get("seed") == b"parent-seed"
    finally:
        parent.close()

    ctx = mp.get_context("spawn")
    q: mp.Queue = ctx.Queue()
    n_children = 3
    procs = [
        ctx.Process(target=_mp_worker, args=(str(root), HMAC, q))
        for _ in range(n_children)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
        assert p.exitcode == 0, f"child exitcode={p.exitcode}"

    results = [q.get(timeout=10) for _ in procs]
    assert len(results) == n_children
    errors = [r for r in results if r[0] != "ok"]
    assert not errors, f"child failures: {errors}"
    pids = {r[1] for r in results}
    assert len(pids) == n_children

    # Parent reopens and verifies seed + every child record.
    verify = compose(root, hmac_key=HMAC, allow_insecure_dev_key=True)
    try:
        assert verify.get("seed") == b"parent-seed"
        for pid in pids:
            rid = f"child-{pid}"
            assert verify.get(rid) == f"from-{pid}".encode()
    finally:
        verify.close()


# ---------------------------------------------------------------------------
# Catalogue / claim honesty
# ---------------------------------------------------------------------------


def test_capabilities_json_lists_new_scopes() -> None:
    path = Path(__file__).resolve().parents[1] / "aethel" / "capabilities.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = path.read_text(encoding="utf-8")
    assert '"production_ready": true' not in raw
    ids = {c["id"] for c in data["claims"]}
    required = {
        "distributed_consensus_software_multi_node_local",
        "multi_root_multi_node_custody_software",
        "cross_region_dr_software_simulated_regions",
        "hyperscaler_soak_software_local_fleet",
        "chronus_hardware_perf_measured",
        "solutions_api_readiness_software",
        "enterprise_hyba_certification_gate_software",
    }
    assert required <= ids
    for cl in data["claims"]:
        if cl["id"] in required:
            assert cl.get("production_ready") is False
            assert "test_enterprise_distributed_substrate" in str(
                cl.get("evidence_tests")
            )


def test_bridge_extended_scopes_and_new_ready_ids() -> None:
    from aethel.enterprise_bridge import CapStatus, report

    r = report()
    assert r.production_ready is False
    assert "distributed_consensus_software_multi_node_local" in (
        r.extended_software_scopes or []
    )
    ids = {c.id: c for c in __import__('aethel.enterprise_bridge', fromlist=['CAPABILITIES']).CAPABILITIES}
    for cid in [
        "E.STORE.CONSENSUS_LOCAL",
        "E.STORE.MULTI_ROOT",
        "E.STORE.DR_SIMULATED",
        "E.STORE.SOAK_LOCAL_FLEET",
        "E.COMPUTE.CHRONUS_PERF_PROBE",
        "E.API.SOLUTIONS_SOFTWARE_FACADE",
        "E.GOV.HYBA_CERT_GATE",
    ]:
        assert cid in ids
        assert ids[cid].status == CapStatus.READY


def test_import_smoke_public_exports() -> None:
    import aethel.enterprise as ent

    for name in [
        "MultiNodeCluster",
        "MultiRootCustody",
        "CrossRegionDR",
        "HyperscalerSoak",
        "ChronusPerfProbe",
        "SolutionsAPI",
        "HybaEnterpriseCertificate",
        "ConsensusError",
        "NotLeaderError",
        "QuorumLostError",
        "RegionFailoverError",
        "SoakThresholdError",
        "CertificationError",
    ]:
        assert hasattr(ent, name), name
