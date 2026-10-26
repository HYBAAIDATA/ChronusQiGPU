import socket
from hashlib import sha256
from dataclasses import replace
import pytest
from chronus.fleet.memory_ring import SoftwareMemoryRing
from chronus.fleet.authority_admission import AdmissionController, AuthorityGrant, TenantBudgetQuota
from chronus.fleet.workload_contracts import ResourceVector


def test_ring_direct_receive_borrow_backpressure_replay_and_fencing(tmp_path):
    key = b"m" * 32
    controller = AdmissionController(audit_dir=tmp_path, signing_key=key)
    controller.register_tenant(TenantBudgetQuota(tenant_id="tenant"))
    ring = SoftwareMemoryRing(tenant="tenant", controller=controller, slots=8, slot_bytes=32)
    rv = ResourceVector(
        cpu_time_ms=10,
        peak_memory_bytes=4096,
        custody_bytes=4096,
        custody_io_bps=4096,
        network_bytes=32,
        deadline_epoch_ms=20000,
        exactness_plane="exact",
        tenant_id="tenant",
    )
    payload = b"exact state bytes"
    digest = sha256(payload).hexdigest()
    work_id = ring.workload_id(0, 1, len(payload), digest)

    def grant(nonce):
        return AuthorityGrant.issue(
            signing_key=key,
            grant_id=nonce,
            tenant_id="tenant",
            workload_id=work_id,
            owner_authority="Chronus",
            resource_vector=rv,
            nonce=nonce,
            issued_at_ms=1000,
            ttl_ms=10000,
        )

    g = grant("first")

    def receive(g, body=payload):
        client, server = socket.socketpair()
        try:
            client.sendall(body)
            return ring.receive(
                server,
                slot=0,
                size=len(payload),
                digest=digest,
                generation=1,
                grant=g,
                resources=rv,
                capacity=controller.default_capacity_snapshot(now_ms=2000),
                now_ms=2000,
            )
        finally:
            client.close()
            server.close()

    assert receive(g).postcondition_verified
    assert not receive(g).postcondition_verified
    with ring.borrow(0, tenant="tenant", generation=1) as view:
        assert view.readonly and bytes(view) == payload
        with pytest.raises(BufferError):
            receive(grant("while-borrowed"))
    assert not receive(
        replace(grant("forged"), signature_hmac_sha256="0" * 64)
    ).postcondition_verified
    with pytest.raises(PermissionError):
        with ring.borrow(0, tenant="other", generation=1):
            pass
    with pytest.raises(ValueError, match="digest"):
        receive(grant("corrupt"), b"!" * len(payload))
    with ring.borrow(0, tenant="tenant", generation=1) as view:
        assert bytes(view) == payload
    controller.rotate_fencing_token(2)
    with pytest.raises(ValueError, match="stale"):
        with ring.borrow(0, tenant="tenant", generation=1):
            pass
    assert controller.audit_log_path.read_text()
