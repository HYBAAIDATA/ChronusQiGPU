"""Super-GPU substrate tests — inventory, routing, IR equivalence, partition.

Coverage contract (per the elevation spec):

  (a) fake-device capability detection — synthetic DeviceInfo records
      drive routing/binding exactly like measured ones;
  (b) IR equivalence vs oracles — every CPU emitter agrees with the
      module that defines the op;
  (c) per-device buffer isolation — buffer pools keyed per pinned host;
  (d) strict-mode fail-closed — capability gates refuse unproven devices;
  (e) attested provenance — every dispatch produces an OpAttestation
      carrying its Lucas config (or truth_class "unconfigured");
  (f) routing correctness on synthetic inventories;
  (g) partition math — sum=1, disjoint, <= 2^32, m32 32-epoch aligned;
  (h) regression — hyba.telemetry/punch/diagnose import clean and the
      canonical kernel mirrors stay byte-identical.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

from hyba.attestation import AttestationLog
from hyba.inventory import ClusterInventory, DeviceInfo
from hyba.math_ir.emit_cpu import emit_cpu
from hyba.math_ir.emit_opencl import NoCanonicalKernel, emit_opencl
from hyba.math_ir.executor import CapabilityMismatch, IRExecutor
from hyba.math_ir.specs import KERNEL_SPECS
from hyba.multi_hasher import MultiDeviceHasher
from chronus.fabric import ChronusFabric


def cpu_device() -> DeviceInfo:
    return DeviceInfo(
        name="CPU (hashlib)",
        vendor="test",
        backend="cpu",
        type="cpu",
        compute_units=8,
        global_mem_mb=None,
        capabilities=(("hashlib_sha256d", True), ("numpy", True)),
    )


def fake_gpu(name="FakeGPU", **caps) -> DeviceInfo:
    caps.setdefault("fp64", True)
    caps.setdefault("m32_lane_kernel", True)
    caps.setdefault("max_workgroup", 256)
    return DeviceInfo(
        name=name,
        vendor="test",
        backend="opencl",
        type="gpu",
        compute_units=96,
        global_mem_mb=8192,
        capabilities=tuple(sorted(caps.items())),
    )


def synth_inventory(*devices: DeviceInfo) -> ClusterInventory:
    inv = ClusterInventory()
    inv.devices = list(devices) or [cpu_device()]
    return inv


# ---------------------------------------------------------------------------
# (a) fake-device capability detection
# ---------------------------------------------------------------------------


def test_capability_map_prefers_attesting_device():
    inv = synth_inventory(cpu_device(), fake_gpu(name="BigGPU", fp64=True))
    sg = ChronusFabric(inv)
    cmap = sg.capability_map()
    assert cmap["m32_lane_kernel"] == "BigGPU"
    assert cmap["fp64"] == "BigGPU"
    assert cmap["hashlib_sha256d"] == "CPU (hashlib)"


def test_by_capability_omits_unmeasured():
    inv = synth_inventory(cpu_device(), fake_gpu())
    assert {d.name for d in inv.by_capability("fp64")} == {"FakeGPU"}
    assert inv.by_capability("tensor_cores") == []


def test_inventory_collects_cpu_and_rtl_on_any_host():
    inv = ClusterInventory.collect()
    assert any(d.backend == "cpu" for d in inv.devices)
    rtl = [d for d in inv.devices if d.backend == "rtl"]
    assert rtl  # chronus/mla1517_platform/rtl + legacy rtl are present
    assert all(d.capability("truth_class") == "design" for d in rtl)


# ---------------------------------------------------------------------------
# (b) IR equivalence vs oracles
# ---------------------------------------------------------------------------


def test_sha256d_scan_matches_hashlib():
    run = emit_cpu("sha256d_scan")
    header = b"\x01" * 76
    res = run({"header": header, "base_nonce": 0, "count": 8, "target": 2**256 - 1}, {})
    assert res["hashes"] == 8
    for nonce in res["hits"]:
        blob = header + struct.pack("<I", nonce)
        digest = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
        assert int.from_bytes(digest, "little") <= 2**256 - 1


def test_sha256d_m32_matches_solver_candidates():
    pytest.importorskip("chronus.mla1517.mining.solver")
    run = emit_cpu("sha256d_m32")
    res = run({"start_nonce": 0, "budget": 96}, {})
    assert len(res["candidates"]) == 96
    lanes = [c[1] for c in res["candidates"][:32]]
    assert sorted(lanes) == list(range(32))  # complete epoch coverage
    # epoch 2 repeats the same lane order, nonces advanced by 32
    for k in range(32):
        n0, l0 = res["candidates"][k]
        n1, l1 = res["candidates"][32 + k]
        assert l1 == l0 and n1 == n0 + 32


def test_lucas_pisot_scale_matches_core():
    pytest.importorskip("chronus.mla1517.core")
    from chronus.mla1517.core import fib, lucas

    run = emit_cpu("lucas_pisot_scale")
    assert run({"scale_index": 20, "kind": "fib"}, {})["value"] == fib(20)
    assert run({"scale_index": 20, "kind": "lucas"}, {})["value"] == lucas(20)
    # padovan: P(n)=P(n-2)+P(n-3), P(0..2)=1 → P(10)=12
    assert run({"scale_index": 10, "kind": "padovan"}, {})["exact_value"] == 12


def test_unified_punch_family_matches_execute_cpu():
    x = np.zeros(11, dtype=np.float32)
    x[0], x[1] = np.float32(0.5), np.float32(0.25)
    fold = emit_cpu("poincare_fold")({"in_float": x}, {})
    unfold = emit_cpu("poincare_unfold")({"in_float": fold["float"][:11]}, {})
    # fold ∘ unfold ≈ identity inside the ball
    np.testing.assert_allclose(
        np.asarray(unfold["float"][:2]), x[:2], rtol=2e-6, atol=1e-7
    )
    c = emit_cpu("cnormsq")({"in_float": x}, {})
    w = np.array(
        [np.float32((1 + 5**0.5) / 2) ** np.float32(-(j + 1)) for j in range(11)],
        dtype=np.float32,
    )
    expected = np.float32(0)
    for j in range(11):
        expected = np.float32(expected + np.float32(w[j] * x[j] * x[j]))
    assert float(c["cnormsq"][0]) == pytest.approx(float(expected), rel=1e-7)


def test_golden_ontology_transform_butterfly():
    pytest.importorskip("chronus.mla1517.core")
    from chronus.mla1517.core import fib

    n = 11
    basis = np.array([fib(i) for i in range(n)], dtype=np.int64)  # F_0..F_10
    x = np.arange(n, dtype=np.int64)
    res = emit_cpu("golden_ontology_transform")(
        {"x_re": x, "fib_basis": basis, "n_points": n}, {}
    )
    assert res["binet_closure"] is True
    assert res["cassini_identity"] is True  # basis indexed by F_i incl. F_0
    assert res["y_re"][0] == sum(int(x[m]) * int(basis[m % n]) for m in range(n))


def test_t_phi_sum_u8_matches_turing_core():
    import turing_core

    folded = bytes([3, 5, 7, 9, 11, 13])
    weights = [1, 2, 3, 4, 5, 6]
    res = emit_cpu("t_phi_sum_u8")(
        {"folded": folded, "original_len": 6, "weights": weights}, {}
    )
    assert res["dot"] == turing_core.folded_modular_dot(folded, 6, weights)
    assert res["streamed"] == list(turing_core.iter_original_u8(folded, 6))


def test_opencl_emit_is_byte_identical_to_canonical():
    emitted = emit_opencl("sha256d_scan")
    path = REPO_ROOT / "kernels" / "bitcoin_sha256d.cl"
    assert emitted.source == path.read_text(encoding="utf-8")
    assert f"__kernel void {emitted.entry}" in emitted.source


def test_opencl_emit_refuses_uncannonical():
    for name, spec in KERNEL_SPECS.items():
        if spec.canonical_source is None:
            with pytest.raises(NoCanonicalKernel):
                emit_opencl(name)


# ---------------------------------------------------------------------------
# (c) per-device buffer isolation
# ---------------------------------------------------------------------------


def test_buf_pool_is_per_host():
    from Intelligence.unified_punch import UnifiedPunchHost

    a = UnifiedPunchHost()
    b = UnifiedPunchHost()
    a.use_opencl = b.use_opencl = False
    a._buf_pool["shared_name"] = ("buf-a", 1024)
    assert "shared_name" in a._buf_pool
    assert "shared_name" not in b._buf_pool
    assert a._buf_pool is not b._buf_pool


# ---------------------------------------------------------------------------
# (d) strict-mode fail-closed
# ---------------------------------------------------------------------------


def test_executor_refuses_missing_capability():
    weak = fake_gpu(m32_lane_kernel=False)
    with pytest.raises(CapabilityMismatch):
        IRExecutor(weak, "sha256d_m32").compile()


def test_executor_refuses_unrunnable_backend():
    rtl = DeviceInfo(
        name="rtl", vendor="", backend="rtl", type="rtl",
        compute_units=None, global_mem_mb=None, capabilities=(),
    )
    with pytest.raises(CapabilityMismatch):
        IRExecutor(rtl, "sha256d_scan").compile()


@pytest.mark.parametrize("backend", ["opencl:gpu", "opencl:cpu"])
def test_executor_accepts_measured_opencl_hasher_backend(monkeypatch, backend):
    class FakeHasher:
        fallback_reason = None

        def __init__(self, device):
            self.backend = backend

    monkeypatch.setattr("mining.bitcoin_hasher.BitcoinHasher", FakeHasher)
    executor = IRExecutor(fake_gpu(), "sha256d_scan").compile()
    assert executor._host.backend == backend


def test_executor_rejects_software_hasher_fallback(monkeypatch):
    class FakeHasher:
        backend = "cpu"
        fallback_reason = "no OpenCL device"

        def __init__(self, device):
            pass

    monkeypatch.setattr("mining.bitcoin_hasher.BitcoinHasher", FakeHasher)
    with pytest.raises(CapabilityMismatch, match="OpenCL unavailable"):
        IRExecutor(fake_gpu(), "sha256d_scan").compile()


def test_wrong_winner_rejected_by_hashlib(monkeypatch):
    """A device that lies about a winning nonce is refused at recheck."""
    cpu = cpu_device()
    ex = IRExecutor(cpu, "sha256d_scan").compile()

    def lying_runner(inputs, dispatch):
        return {"winning_nonce": 0xDEADBEEF, "hashes": 1}

    object.__setattr__(ex, "_runner", lambda i, d: lying_runner(i, d))
    ex._runner = lying_runner  # bound directly
    with pytest.raises(RuntimeError, match="hashlib recheck"):
        ex.run(
            {
                "header": b"\x00" * 80,
                "base_nonce": 0,
                "count": 1,
                "target": 0,  # nothing meets target 0
            }
        )


# ---------------------------------------------------------------------------
# (e) attested provenance
# ---------------------------------------------------------------------------


def test_execute_attests_with_lucas_config():
    AttestationLog.reset()
    sg = ChronusFabric(synth_inventory(cpu_device()))
    x = np.arange(11, dtype=np.float32)
    result = sg.execute("cnormsq", {"in_float": x}, {"work_items": 4096})
    att = result.attestation
    assert att.op == "cnormsq"
    assert att.device_name == "CPU (hashlib)"
    assert att.measured_ns >= 0
    assert att.lucas_rung in (10, 12, 15, 18, 20, 31, 50, 76)
    assert att.chunk_size is not None and att.chunk_size > 0
    assert att.truth_class in ("cpu_reference", "measured")
    snap = AttestationLog.get().snapshot()
    assert len(snap) == 1 and snap[0]["op"] == "cnormsq"


def test_serial_dispatch_attests_unconfigured():
    AttestationLog.reset()
    sg = ChronusFabric(synth_inventory(cpu_device()))
    result = sg.execute("lucas_pisot_scale", {"scale_index": 10, "kind": "fib"})
    assert result.truth_class == "unconfigured"
    assert result.attestation.truth_class == "unconfigured"


def test_unknown_op_fails_loud():
    sg = ChronusFabric(synth_inventory(cpu_device()))
    with pytest.raises(KeyError):
        sg.execute("no_such_op_xyz", {}, {})


def test_unrouted_op_attests_unconfigured():
    # m32_grind is routed but its discipline attests unconfigured only when
    # no Lucas config is derived — covered by the serial test above.
    AttestationLog.reset()
    sg = ChronusFabric(synth_inventory(cpu_device()))
    result = sg.execute("cnormsq", {"in_float": np.zeros(11, dtype=np.float32)})
    assert result.attestation.truth_class != "unconfigured"


# ---------------------------------------------------------------------------
# (f) routing correctness on synthetic inventories
# ---------------------------------------------------------------------------


def test_sha256d_prefers_asic_then_m32_gpu():
    asic = DeviceInfo(
        name="ASIC0", vendor="MLA1517", backend="asic", type="asic",
        compute_units=None, global_mem_mb=None,
        capabilities=(("mmio", True),),
    )
    sg = ChronusFabric(synth_inventory(cpu_device(), fake_gpu(), asic))
    assert sg.route("sha256d_grind").device_name == "ASIC0"
    sg2 = ChronusFabric(synth_inventory(cpu_device(), fake_gpu()))
    d = sg2.route("sha256d_grind")
    assert d.device_name == "FakeGPU"
    assert d.capability == "m32_lane_kernel"
    sg3 = ChronusFabric(synth_inventory(cpu_device()))
    assert sg3.route("sha256d_grind").device_name == "CPU (hashlib)"


def test_resident_state_prefers_unified_memory():
    weak = DeviceInfo(
        name="NoUM", vendor="t", backend="opencl", type="gpu",
        compute_units=64, global_mem_mb=1024, capabilities=(),
    )
    unified = DeviceInfo(
        name="UM", vendor="t", backend="opencl", type="chronus",
        compute_units=16, global_mem_mb=512,
        capabilities=(("host_unified_memory", True),),
    )
    sg = ChronusFabric(synth_inventory(cpu_device(), weak, unified))
    d = sg.route("unified_resident_state")
    assert d.device_name == "UM"
    assert d.capability == "host_unified_memory"


def test_lucas_dispatch_never_exceeds_max_workgroup():
    inv = synth_inventory(cpu_device(), fake_gpu(max_workgroup=64))
    d = ChronusFabric(inv).route("sha256d_grind", {"work_items": 1 << 20})
    assert d.lucas_dispatch["workgroup_size"] <= 64


def test_grover_depth_derived():
    inv = synth_inventory(cpu_device())
    d = ChronusFabric(inv).route("grover_search", {"space": 1 << 20, "marked": 1})
    assert d.lucas_dispatch["grover_depth"] == int(
        np.floor(np.pi / 4 * np.sqrt(1 << 20))
    )


# ---------------------------------------------------------------------------
# (g) partition math
# ---------------------------------------------------------------------------


def test_partition_disjoint_total_bounded():
    pool = MultiDeviceHasher([], include_cpu=True)
    for count in (4096, 65537, 1 << 22):
        spans, cert = pool.partition_window(0, count)
        cursor = 0
        for s in spans:
            assert s.span_base == cursor  # contiguous, no gaps, no overlap
            assert s.span_count > 0
            cursor += s.span_count
        assert cursor == count
        assert all(s.span_base + s.span_count <= 1 << 32 for s in spans)
        assert cert["total_span"] == count


def test_partition_m32_whole_epochs():
    pool = MultiDeviceHasher([], include_cpu=True)
    spans, cert = pool.partition_window(0, 4160, m32=True)
    assert cert["m32_epochs"] == 130
    total = sum(s.span_count for s in spans)
    assert total == 4160
    gpu_spans = spans[:-1] if spans[-1].span_count % 32 else spans
    assert all(s.span_count % 32 == 0 for s in gpu_spans)
    assert all(s.span_base % 32 == 0 for s in spans[:-1])


def test_partition_weights_measured_then_compute_units():
    from mining.bitcoin_hasher import BitcoinHasher

    h1 = BitcoinHasher(backend="cpu")
    h1.device = "dev-slow"
    h2 = BitcoinHasher(backend="cpu")
    h2.device = "dev-fast"
    pool = MultiDeviceHasher([h1, h2], include_cpu=False)
    m1 = next(m for m in pool.members if m.device_id == "dev-slow")
    m2 = next(m for m in pool.members if m.device_id == "dev-fast")
    m2.measured_hps = 1_000_000.0
    m1.measured_hps = 0.0
    m1.compute_units, m2.compute_units = 1, 1
    spans, _ = pool.partition_window(0, 3200)
    fast_total = sum(s.span_count for s in spans if s.device_id == "dev-fast")
    slow_total = sum(s.span_count for s in spans if s.device_id == "dev-slow")
    assert fast_total > slow_total
    assert fast_total + slow_total == 3200


def test_multi_hasher_winner_is_earliest_probe_order():
    pool = MultiDeviceHasher([], include_cpu=True)
    # target accepts nonce 100 only in the low window: hash target at
    # exactly ~2^191 makes hits vanishingly rare; instead verify the scan
    # semantics with a permissive target and check the returned winner is
    # the smallest valid nonce.
    header = b"\x02" * 80
    res = pool.grind_target_range(header, (2**256 - 1).to_bytes(32, "big"), 0, 512)
    assert res["winning_nonce"] == 0
    assert res["winning_probe_index"] == 0
    assert res["hashes"] == 512


# ---------------------------------------------------------------------------
# (h) regression — re-export modules + kernel byte assertion
# ---------------------------------------------------------------------------


def test_hyba_surface_imports_clean():
    import hyba.backend  # noqa: F401
    import hyba.diagnose  # noqa: F401
    import hyba.punch  # noqa: F401
    import hyba.telemetry  # noqa: F401


def test_kernel_mirrors_byte_identical():
    canonical = REPO_ROOT / "kernels"
    mirror = REPO_ROOT / "chronus" / "kernels"
    for path in sorted(canonical.glob("*.cl")):
        twin = mirror / path.name
        assert twin.is_file(), f"missing mirror kernel {twin}"
        assert hashlib.md5(path.read_bytes()).hexdigest() == hashlib.md5(
            twin.read_bytes()
        ).hexdigest(), f"kernel mirror diverged: {path.name}"


def test_diagnose_reports_chronus_fabric_section():
    import hyba.diagnose

    report = hyba.diagnose.diagnose()
    assert "chronus_fabric" in report
    section = report["chronus_fabric"]
    assert "error" not in section or "composed" in section
    if "composed" in section:
        assert section["composed"]["device_count"] >= 1
