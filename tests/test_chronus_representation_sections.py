import pytest
from aethel.representation_views import BasisPermutation, BasisView
from chronus.fleet.sections import Section, glue, commit_sections, TenantSectionCustody
from chronus.virtual_igpu.memory import VirtualMemoryPlane
from chronus.fleet.authority_admission import AdmissionController, AuthorityGrant, TenantBudgetQuota
from chronus.fleet.workload_contracts import ResourceVector


def test_basis_adjoint_composition_tensor_laws_and_zero_copy():
    p = BasisPermutation((2, 0, 1))
    q = BasisPermutation((1, 0, 2))
    identity = BasisPermutation.identity(3)
    assert p.then(p.adjoint()) == identity
    assert p.then(q).adjoint() == q.adjoint().then(p.adjoint())
    assert p.tensor(q).adjoint() == p.adjoint().tensor(q.adjoint())
    payload = b"abcdef"
    view = BasisView(payload, 2, identity).transformed(p)
    assert view.payload is payload and view.item(0).obj is payload
    assert bytes(view.item(0)) == b"ef" and view.data_bytes_copied == 0
    recovered = view.transformed(p.adjoint())
    assert b"".join(recovered.item(i) for i in range(3)) == payload


def test_sections_overlap_restriction_and_tenant_boundaries():
    a, b = "a" * 64, "b" * 64
    left = Section("tenant", 1, {"x": a, "y": b})
    right = Section("tenant", 1, {"y": b, "z": a})
    global_section = glue([left, right], ["x", "y", "z"])
    assert global_section.restrict(["x", "y"]) == left
    with pytest.raises(ValueError, match="overlap"):
        glue([left, Section("tenant", 1, {"y": a})], ["x", "y"])
    with pytest.raises(ValueError, match="tenant"):
        glue([left, Section("other", 1, {"z": a})], ["x", "y", "z"])
    with pytest.raises(ValueError, match="cover"):
        glue([left], ["x", "y", "z"])


def test_section_commit_uses_existing_authority_and_ovid_custody(tmp_path):
    key = b"s" * 32
    custody = TenantSectionCustody(VirtualMemoryPlane(tmp_path / "memory"), "tenant")
    ref = custody.put(b"exact synthetic state")
    controller = AdmissionController(audit_dir=tmp_path, signing_key=key)
    controller.register_tenant(TenantBudgetQuota(tenant_id="tenant"))
    resources = ResourceVector(
        cpu_time_ms=10,
        peak_memory_bytes=4096,
        custody_bytes=4096,
        custody_io_bps=4096,
        network_bytes=0,
        deadline_epoch_ms=20000,
        exactness_plane="exact",
        tenant_id="tenant",
    )
    grant = AuthorityGrant.issue(
        signing_key=key,
        grant_id="section",
        tenant_id="tenant",
        workload_id="glue",
        owner_authority="OVID",
        resource_vector=resources,
        policy_epoch=1,
        fencing_token=1,
        nonce="section-once",
        issued_at_ms=1000,
        ttl_ms=9000,
    )
    args = dict(
        custody=custody,
        controller=controller,
        grant=grant,
        resources=resources,
        capacity=controller.default_capacity_snapshot(now_ms=2000),
        workload_id="glue",
        now_ms=2000,
    )
    sections = [Section("tenant", 1, {"x": ref})]
    receipt = commit_sections(sections, ["x"], **args)
    assert receipt.postcondition_verified
    assert controller.audit_log_path.read_text()
    with pytest.raises(ValueError, match="version"):
        commit_sections(sections, ["x"], **args)


def test_section_custody_cross_tenant_reference_is_refused(tmp_path):
    memory = VirtualMemoryPlane(tmp_path)
    left = TenantSectionCustody(memory, "left")
    right = TenantSectionCustody(memory, "right")
    ref = right.put(b"private synthetic state")
    with pytest.raises(PermissionError):
        left.get(ref)
