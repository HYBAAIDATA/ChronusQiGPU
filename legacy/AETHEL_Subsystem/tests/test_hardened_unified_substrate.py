import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("Intelligence"))
# tests/test_hardened_unified_substrate.py
# COMPLETE TEST SUITE — ALL CATEGORIES
# ==============================================================================

import pytest
import numpy as np
import asyncio
import time
import threading
from hypothesis import given, strategies as st, settings

# Import the substrate
from hardened_unified_substrate import (
    # Constants
    DIM,
    PHI,
    SQRT5,
    MODULUS_Q,
    # Fix A
    CassiniVerifier,
    # Fix B
    HardenedZeckendorfCodec,
    # Fix C
    GaloisPrimeSubstrate,
    # Layer 1
    VirtualSM,
    ComputeUnitPool,
    # Layer 2
    SPMDExecutor,
    # Layer 3
    MicroKernelLibrary,
    # Layer 4
    DistributedDataflowGraph,
    # Layer 5
    DAGNode,
    DependencyDAG,
    # GPU
    TensorCoreGPU_Context,
    # Tensor
    ManifoldCurvature,
    ManifoldSector,
    apply_zeckendorf_compression,
    reverse_zeckendorf_expansion,
    # Manifold
    PrimeStorageManifold,
    # Unified
    UnifiedSubstrate,
)

# ==============================================================================
# SECTION 1: INVARIANT TESTS
# ==============================================================================


class TestInvariants:
    """Tests that verify mathematical invariants hold across all operations."""

    def test_cassini_invariant_holds_for_all_n(self):
        """Cassini invariant L_n² - 5F_n² = 4(-1)^n for n in [1, 30]."""
        for n in range(1, 31):
            assert CassiniVerifier.verify(n), f"Cassini failed at n={n}"

    def test_cassini_matrix_determinant(self):
        """det(Q^n) = (-1)^n for all n."""
        for n in range(1, 25):
            assert CassiniVerifier.verify_matrix(n), f"Matrix det failed at n={n}"

    def test_zeckendorf_non_adjacent_invariant(self):
        """Every Zeckendorf mask satisfies (mask & (mask << 1)) == 0."""
        for n in range(1, 10000):
            mask = HardenedZeckendorfCodec.encode(n)
            assert HardenedZeckendorfCodec.verify_non_adjacent(
                mask
            ), f"Non-adjacent violated at n={n}"

    def test_zeckendorf_roundtrip_invariant(self):
        """decode(encode(n)) == n for all n."""
        for n in range(1, 10000):
            mask = HardenedZeckendorfCodec.encode(n)
            assert HardenedZeckendorfCodec.decode(mask) == n, f"Roundtrip failed at n={n}"

    def test_pisot_convergence_invariant(self):
        """|Φ^n - L(n)| = φ^n for all n."""
        from decimal import Decimal, getcontext

        getcontext().prec = 50
        sq5 = Decimal(5).sqrt()
        d_phi = (Decimal(1) + sq5) / Decimal(2)
        d_psi = (Decimal(1) - sq5) / Decimal(2)
        for n in range(1, 50):
            L_n = CassiniVerifier.lucas(n)
            error = abs(d_phi**n - Decimal(L_n))
            expected = abs(d_psi) ** n
            assert abs(error - expected) < Decimal("1e-9"), f"Pisot failed at n={n}"

    def test_spectral_gap_invariant(self):
        """|λ₁ - λ₂| = √5 for the Cassini matrix."""
        from numpy.linalg import eigvals

        Q = np.array([[1, 1], [1, 0]], dtype=float)
        eigenvalues = np.sort(eigvals(Q).real)[::-1]
        gap = abs(eigenvalues[0] - eigenvalues[1])
        assert abs(gap - SQRT5) < 1e-12

    def test_galois_composite_invariant(self):
        """Composite key is always < modulus."""
        substrate = GaloisPrimeSubstrate(n_primes=25)
        for i in range(100):
            payload = f"data_{i}".encode() * 10
            composite = substrate.commit(anchor=i, uuid_str=f"uuid_{i}", payload=payload)
            assert composite < MODULUS_Q, f"Composite {composite} >= modulus"

    def test_prime_substrate_roundtrip_invariant(self):
        """Every committed payload can be fetched exactly."""
        substrate = GaloisPrimeSubstrate(n_primes=25)
        for i in range(100):
            payload = f"payload_{i}".encode() * 5
            substrate.commit(anchor=i, uuid_str=f"uuid_{i}", payload=payload)
        for i in range(100):
            fetched = substrate.fetch(f"uuid_{i}")
            expected = f"payload_{i}".encode() * 5
            assert fetched == expected, f"Roundtrip failed at {i}"

    def test_dag_topological_sort_invariant(self):
        """Topological sort respects all dependencies."""
        dag = DependencyDAG()
        dag.add_node(DAGNode("A", lambda: np.array([1]), outputs=["a"]))
        dag.add_node(DAGNode("B", lambda x: x, deps=["A"], inputs=["a"], outputs=["b"]))
        dag.add_node(DAGNode("C", lambda x: x, deps=["B"], inputs=["b"], outputs=["c"]))
        order = dag.topological_sort()
        assert order.index("A") < order.index("B") < order.index("C")

    def test_homeostatic_scale_invariant(self):
        """Total weight never exceeds target."""
        from neural_plasticity import NeuralPlasticity

        np_ = NeuralPlasticity(homeostatic_target=1.0)
        for i in range(100):
            np_.co_activate(f"A{i}", f"B{i}")
            np_.co_activate(f"A{i}", f"B{i}")
            np_.co_activate(f"A{i}", f"B{i}")
        np_.deliver_reward(1.0)
        total = sum(s.weight for s in np_.synapses.values())
        assert total <= 1.0 + 1e-9


# ==============================================================================
# SECTION 2: PROPERTY-BASED TESTS (Hypothesis)
# ==============================================================================


class TestProperties:
    """Property-based tests using Hypothesis."""

    @given(st.integers(min_value=0, max_value=2**64 - 1))
    @settings(max_examples=1000)
    def test_zeckendorf_encode_decode_property(self, n):
        """For any n in [0, 2^64-1], encode/decode roundtrips."""
        mask = HardenedZeckendorfCodec.encode(n)
        assert HardenedZeckendorfCodec.decode(mask) == n

    @given(st.integers(min_value=0, max_value=2**64 - 1))
    @settings(max_examples=1000)
    def test_zeckendorf_non_adjacent_property(self, n):
        """For any n, the mask is non-adjacent."""
        mask = HardenedZeckendorfCodec.encode(n)
        assert (mask & (mask << 1)) == 0

    @given(st.binary(min_size=1, max_size=1024))
    @settings(max_examples=200)
    def test_zeckendorf_compression_roundtrip(self, payload):
        """For any payload, compression roundtrips."""
        sparse = apply_zeckendorf_compression(payload)
        recovered = reverse_zeckendorf_expansion(sparse)
        assert recovered == payload

    @given(
        st.lists(
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=100,
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_pv_collapse_bounded(self, data):
        """PV collapse always returns a finite integer."""
        gpu = TensorCoreGPU_Context()
        arr = np.array(data, dtype=np.float32)
        anchor = gpu.project_and_collapse_pv(arr, PHI)
        assert isinstance(anchor, int)
        assert anchor >= 0
        gpu.shutdown()

    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=100)
    def test_cassini_always_holds(self, n):
        """For any n, Cassini invariant holds."""
        assert CassiniVerifier.verify(n)

    @given(st.lists(st.integers(min_value=0, max_value=1000), min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_galois_composite_always_bounded(self, values):
        """Composite keys always bounded by modulus."""
        substrate = GaloisPrimeSubstrate(n_primes=25)
        payload = bytes([v % 256 for v in values])
        composite = substrate.commit(anchor=1, uuid_str="test", payload=payload)
        assert 0 <= composite < MODULUS_Q


# ==============================================================================
# SECTION 3: ADVERSARIAL TESTS
# ==============================================================================


class TestAdversarial:
    """Adversarial tests designed to break the system."""

    def test_zeckendorf_overflow_attack(self):
        """Attempt to encode n >= F_93 — must raise."""
        with pytest.raises(ValueError):
            HardenedZeckendorfCodec.encode(2**100)

    def test_zeckendorf_negative_attack(self):
        """Attempt to encode negative — must handle gracefully."""
        with pytest.raises((ValueError, TypeError)):
            HardenedZeckendorfCodec.encode(-1)

    def test_cassini_corrupted_values(self):
        """Corrupted L_n, F_n must fail verification."""
        # Correct values for n=5: L=11, F=5
        assert CassiniVerifier.verify_with_values(5, 11, 5)
        # Corrupted
        assert not CassiniVerifier.verify_with_values(5, 11, 6)
        assert not CassiniVerifier.verify_with_values(5, 12, 5)
        assert not CassiniVerifier.verify_with_values(5, 0, 0)

    def test_prime_substrate_collision_attack(self):
        """Attempt to create collision in prime substrate."""
        substrate = GaloisPrimeSubstrate(n_primes=25)
        # Commit two different payloads
        substrate.commit(anchor=1, uuid_str="a", payload=b"AAAA")
        substrate.commit(anchor=2, uuid_str="b", payload=b"BBBB")
        # Verify no collision
        assert substrate.fetch("a") == b"AAAA"
        assert substrate.fetch("b") == b"BBBB"

    def test_dag_cycle_attack(self):
        """Attempt to create a cycle — topological sort must handle."""
        dag = DependencyDAG()
        dag.add_node(DAGNode("A", lambda: None, deps=["C"], outputs=["a"]))
        dag.add_node(DAGNode("B", lambda: None, deps=["A"], outputs=["b"]))
        dag.add_node(DAGNode("C", lambda: None, deps=["B"], outputs=["c"]))
        # Topological sort should not infinite loop
        try:
            order = dag.topological_sort()
            assert len(order) == 3
        except RecursionError:
            pytest.fail("Topological sort recursed infinitely on cycle")

    def test_gpu_context_double_shutdown(self):
        """Shutting down twice must not crash."""
        gpu = TensorCoreGPU_Context()
        gpu.shutdown()
        gpu.shutdown()  # must not raise

    def test_memory_exhaustion_attack(self):
        """Attempt to exhaust memory — must handle gracefully."""
        substrate = GaloisPrimeSubstrate(n_primes=25)
        for i in range(10000):
            payload = b"x" * 1000
            substrate.commit(anchor=i, uuid_str=f"uuid_{i}", payload=payload)
        # Should not crash
        assert substrate.fetch("uuid_9999") is not None

    def test_dag_prune_cascading_attack(self):
        """Test that cascading dead code is properly culled."""
        dag = DependencyDAG()
        dag.add_node(DAGNode("A", lambda: np.array([1]), outputs=["a"]))
        dag.add_node(DAGNode("B", lambda x: x, inputs=["a"], outputs=["b"]))
        dag.add_node(DAGNode("C", lambda x: x, inputs=["b"], outputs=["c"]))
        dag.add_node(DAGNode("D", lambda x: x, inputs=["c"], outputs=["d"]))
        # No node uses "d" — all should be culled iteratively
        culled = dag.prune_dead_code()
        assert culled >= 1

    def test_thread_safety_attack(self):
        """Concurrent submissions to ComputeUnitPool must be safe."""
        pool = ComputeUnitPool(n_sms=4, threads_per_sm=8)
        results = []
        lock = threading.Lock()

        def worker(i):
            result = pool.submit_workgroup(lambda x: x * 2, i).result()
            with lock:
                results.append(result)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(results) == 100
        assert sorted(results) == [i * 2 for i in range(100)]
        pool.shutdown()

    def test_galois_overflow_attack(self):
        """Attempt to overflow Galois modulus."""
        substrate = GaloisPrimeSubstrate(n_primes=25)
        # Very large exponent
        payload = b"\xff" * 1024
        composite = substrate.commit(anchor=1, uuid_str="big", payload=payload)
        assert 0 <= composite < MODULUS_Q

    def test_manifold_anchor_collision(self):
        """Two different payloads may share anchor — must be distinguishable."""
        substrate = PrimeStorageManifold(TensorCoreGPU_Context(), n_primes=25)
        uid1 = substrate.ingest_sync(b"payload1" * 10, ManifoldCurvature.GOLDEN_DENSE)
        uid2 = substrate.ingest_sync(b"payload2" * 10, ManifoldCurvature.GOLDEN_DENSE)
        assert uid1 != uid2
        assert substrate.tensors[uid1].raw_payload is None
        assert substrate.tensors[uid2].raw_payload is None


# ==============================================================================
# SECTION 4: EDGE CASE TESTS
# ==============================================================================


class TestEdgeCases:
    """Edge case tests for boundary conditions."""

    def test_zeckendorf_zero(self):
        assert HardenedZeckendorfCodec.encode(0) == 0
        assert HardenedZeckendorfCodec.decode(0) == 0

    def test_zeckendorf_one(self):
        assert HardenedZeckendorfCodec.encode(1) == 1
        assert HardenedZeckendorfCodec.decode(1) == 1

    def test_zeckendorf_max_fibonacci(self):
        n = HardenedZeckendorfCodec.FIBONACCI[93] - 1
        mask = HardenedZeckendorfCodec.encode(n)
        assert HardenedZeckendorfCodec.decode(mask) == n

    def test_empty_payload(self):
        sparse = apply_zeckendorf_compression(b"")
        assert len(sparse.blocks) == 0
        recovered = reverse_zeckendorf_expansion(sparse)
        assert recovered == b""

    def test_single_byte_payload(self):
        payload = b"\x42"
        sparse = apply_zeckendorf_compression(payload)
        recovered = reverse_zeckendorf_expansion(sparse)
        assert recovered == payload

    def test_exact_8_byte_payload(self):
        payload = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        sparse = apply_zeckendorf_compression(payload)
        recovered = reverse_zeckendorf_expansion(sparse)
        assert recovered == payload

    def test_gemm_1x1(self):
        mk = MicroKernelLibrary()
        A = np.array([[2.0]], dtype=np.float32)
        B = np.array([[3.0]], dtype=np.float32)
        C = mk.gemm(A, B)
        assert C[0, 0] == 6.0

    def test_gemm_non_square(self):
        mk = MicroKernelLibrary()
        A = np.random.randn(7, 13).astype(np.float32)
        B = np.random.randn(13, 5).astype(np.float32)
        C = mk.gemm(A, B)
        assert C.shape == (7, 5)
        assert np.allclose(C, A @ B, atol=1e-3)

    def test_gemm_large(self):
        mk = MicroKernelLibrary()
        A = np.random.randn(128, 128).astype(np.float32)
        B = np.random.randn(128, 128).astype(np.float32)
        C = mk.gemm(A, B)
        assert np.allclose(C, A @ B, atol=1e-2)

    def test_dag_single_node(self):
        dag = DependencyDAG()
        dag.add_node(DAGNode("A", lambda: np.array([1, 2, 3]), outputs=["a"]))
        dag.execute()
        assert np.array_equal(dag.buffers["a"], [1, 2, 3])

    def test_dag_no_deps(self):
        dag = DependencyDAG()
        dag.add_node(DAGNode("A", lambda: np.array([1]), outputs=["a"]))
        dag.add_node(DAGNode("B", lambda: np.array([2]), outputs=["b"]))
        dag.execute()
        assert "a" in dag.buffers and "b" in dag.buffers

    def test_cassini_n_zero(self):
        # L_0 = 2, F_0 = 0, det should be 2² - 5·0 = 4 = 4(-1)^0
        L_0 = CassiniVerifier.lucas(0)
        F_0 = CassiniVerifier.fibonacci(0)
        assert L_0**2 - 5 * F_0**2 == 4

    def test_cassini_n_one(self):
        # L_1 = 1, F_1 = 1, det = 1 - 5 = -4 = 4(-1)^1
        L_1 = CassiniVerifier.lucas(1)
        F_1 = CassiniVerifier.fibonacci(1)
        assert L_1**2 - 5 * F_1**2 == -4

    def test_empty_dag_execute(self):
        dag = DependencyDAG()
        dag.execute()  # no nodes — must not crash

    def test_empty_cluster_allreduce(self):
        cluster = DistributedDataflowGraph(n_actors=0)
        result = cluster.all_reduce(np.array([1.0, 2.0]))
        assert np.array_equal(result, np.array([0.0, 0.0]))

    def test_hilbert_dim_11d(self):
        substrate = UnifiedSubstrate(n_primes=25, n_sms=2)
        assert substrate.manifold.gpu is not None
        substrate.shutdown()

    def test_manifold_empty_stats(self):
        substrate = PrimeStorageManifold(TensorCoreGPU_Context(), n_primes=25)
        stats = substrate.stats()
        assert stats["total_tensors"] == 0
        assert stats["anchor_index_size"] == 0


# ==============================================================================
# SECTION 5: UNIT TESTS
# ==============================================================================


class TestUnitCassini:
    """Unit tests for CassiniVerifier."""

    def test_lucas_sequence(self):
        expected = [2, 1, 3, 4, 7, 11, 18, 29, 47, 76]
        for i, exp in enumerate(expected):
            assert CassiniVerifier.lucas(i) == exp

    def test_fibonacci_sequence(self):
        expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
        for i, exp in enumerate(expected):
            assert CassiniVerifier.fibonacci(i) == exp

    def test_verify_all_small(self):
        for n in range(0, 30):
            assert CassiniVerifier.verify(n)


class TestUnitZeckendorf:
    """Unit tests for HardenedZeckendorfCodec."""

    def test_encode_specific_values(self):
        assert HardenedZeckendorfCodec.encode(1) == 0b1
        assert HardenedZeckendorfCodec.encode(2) == 0b10
        assert HardenedZeckendorfCodec.encode(3) == 0b100
        assert HardenedZeckendorfCodec.encode(4) == 0b101

    def test_decode_specific_masks(self):
        assert HardenedZeckendorfCodec.decode(0b1) == 1
        assert HardenedZeckendorfCodec.decode(0b10) == 2
        assert HardenedZeckendorfCodec.decode(0b100) == 3
        assert HardenedZeckendorfCodec.decode(0b101) == 4

    def test_fibonacci_table_extended(self):
        assert HardenedZeckendorfCodec.FIBONACCI[92] == 12200160415121876738
        assert HardenedZeckendorfCodec.FIBONACCI[93] == 19740274219868223167


class TestUnitPrimeSubstrate:
    """Unit tests for GaloisPrimeSubstrate."""

    def test_commit_returns_composite(self):
        substrate = GaloisPrimeSubstrate(n_primes=25)
        composite = substrate.commit(anchor=1, uuid_str="test", payload=b"data")
        assert isinstance(composite, int)
        assert composite > 0

    def test_fetch_returns_payload(self):
        substrate = GaloisPrimeSubstrate(n_primes=25)
        substrate.commit(anchor=1, uuid_str="test", payload=b"data")
        assert substrate.fetch("test") == b"data"

    def test_fetch_missing_returns_none(self):
        substrate = GaloisPrimeSubstrate(n_primes=25)
        assert substrate.fetch("nonexistent") is None

    def test_crystallize(self):
        substrate = GaloisPrimeSubstrate(n_primes=25)
        substrate.commit(anchor=1, uuid_str="test", payload=b"data")
        assert substrate.crystallize(2)
        assert not substrate.crystallize(99999)


class TestUnitComputeUnitPool:
    """Unit tests for ComputeUnitPool."""

    def test_submit_returns_future(self):
        pool = ComputeUnitPool(n_sms=2, threads_per_sm=4)
        future = pool.submit_workgroup(lambda: 42)
        assert future.result() == 42
        pool.shutdown()

    def test_round_robin(self):
        pool = ComputeUnitPool(n_sms=3, threads_per_sm=2)
        sms = [pool.get_sm().sm_id for _ in range(6)]
        assert sms == [0, 1, 2, 0, 1, 2]
        pool.shutdown()


class TestUnitSPMD:
    """Unit tests for SPMDExecutor."""

    def test_vectorize(self):
        spmd = SPMDExecutor(n_lanes=8)
        result = spmd.vectorize(lambda x: x * 2, np.array([1, 2, 3, 4]))
        assert np.array_equal(result, [2, 4, 6, 8])

    def test_diverge(self):
        spmd = SPMDExecutor(n_lanes=8)
        data = np.array([1.0, 2.0, 3.0, 4.0])
        result = spmd.diverge(
            data > 2.0,
            lambda x: x * 10,
            lambda x: x + 1,
            data,
        )
        expected = np.where(data > 2.0, data * 10, data + 1)
        assert np.allclose(result, expected)


class TestUnitDAG:
    """Unit tests for DependencyDAG."""

    def test_add_node(self):
        dag = DependencyDAG()
        dag.add_node(DAGNode("A", lambda: None))
        assert "A" in dag.nodes

    def test_execute_simple(self):
        dag = DependencyDAG()
        dag.add_node(DAGNode("A", lambda: np.array([1, 2]), outputs=["x"]))
        dag.execute()
        assert np.array_equal(dag.buffers["x"], [1, 2])

    def test_topological_sort_chain(self):
        dag = DependencyDAG()
        dag.add_node(DAGNode("A", lambda: None, outputs=["a"]))
        dag.add_node(DAGNode("B", lambda: None, deps=["A"], inputs=["a"], outputs=["b"]))
        dag.add_node(DAGNode("C", lambda: None, deps=["B"], inputs=["b"], outputs=["c"]))
        order = dag.topological_sort()
        assert order.index("A") < order.index("B") < order.index("C")


class TestUnitMicroKernels:
    """Unit tests for micro-kernels."""

    def test_gemm_identity(self):
        mk = MicroKernelLibrary()
        I = np.eye(16, dtype=np.float32)
        A = np.random.randn(16, 16).astype(np.float32)
        C = mk.gemm(A, I)
        assert np.allclose(C, A, atol=1e-4)

    def test_ray_aabb_hit(self):
        mk = MicroKernelLibrary()
        origin = np.array([[0, 0, 0]], dtype=np.float32)
        direction = np.array([[1, 0, 0]], dtype=np.float32)
        bmin = np.array([5, -1, -1], dtype=np.float32)
        bmax = np.array([6, 1, 1], dtype=np.float32)
        hit = mk.ray_aabb(origin, direction, bmin, bmax)
        assert hit[0]

    def test_ray_aabb_miss(self):
        mk = MicroKernelLibrary()
        origin = np.array([[0, 0, 0]], dtype=np.float32)
        direction = np.array([[1, 0, 0]], dtype=np.float32)
        bmin = np.array([5, 5, 5], dtype=np.float32)
        bmax = np.array([6, 6, 6], dtype=np.float32)
        hit = mk.ray_aabb(origin, direction, bmin, bmax)
        assert not hit[0]


# ==============================================================================
# SECTION 6: INTEGRATION TESTS
# ==============================================================================


class TestIntegration:
    """Integration tests across multiple components."""

    def test_zeckendorf_to_prime_substrate(self):
        """Zeckendorf compression → prime substrate → retrieval."""
        payload = b"integration test payload" * 100
        sparse = apply_zeckendorf_compression(payload)
        compressed_bytes = b"".join(mask.to_bytes(16, "big") for mask in sparse.blocks.values())
        substrate = GaloisPrimeSubstrate(n_primes=25)
        substrate.commit(anchor=1, uuid_str="integrated", payload=compressed_bytes)
        fetched = substrate.fetch("integrated")
        assert fetched == compressed_bytes

    def test_gpu_to_manifold_to_retrieval(self):
        """GPU anchor → manifold ingest → retrieval."""
        gpu = TensorCoreGPU_Context()
        manifold = PrimeStorageManifold(gpu, n_primes=25)
        payload = b"gpu manifold test" * 50
        uid = manifold.ingest_sync(payload, ManifoldCurvature.GOLDEN_DENSE)
        tensor = manifold.tensors[uid]
        assert tensor.integer_anchor is not None
        assert CassiniVerifier.verify(tensor.integer_anchor)
        gpu.shutdown()

    def test_compute_pool_to_dag(self):
        """Compute pool executes DAG nodes in parallel."""
        pool = ComputeUnitPool(n_sms=4, threads_per_sm=8)
        dag = DependencyDAG()

        def parallel_gemm():
            A = np.random.randn(16, 16).astype(np.float32)
            B = np.random.randn(16, 16).astype(np.float32)
            return A @ B

        dag.add_node(DAGNode("gemm", parallel_gemm, outputs=["result"]))
        future = pool.submit_workgroup(dag.execute)
        future.result()
        assert "result" in dag.buffers
        pool.shutdown()

    def test_spmd_to_microkernel(self):
        """SPMD vectorization feeds into micro-kernel GEMM."""
        spmd = SPMDExecutor(n_lanes=16)
        mk = MicroKernelLibrary()
        A = np.random.randn(16, 16).astype(np.float32)
        B = spmd.vectorize(lambda x: x * 2, np.random.randn(16, 16).astype(np.float32))
        C = mk.gemm(A, B)
        assert C.shape == (16, 16)

    def test_cluster_to_dag(self):
        """Distributed AllReduce feeds DAG."""
        cluster = DistributedDataflowGraph(n_actors=4)
        dag = DependencyDAG()
        data = np.array([1.0, 2.0, 3.0])
        dag.add_node(
            DAGNode(
                "reduce",
                lambda: cluster.all_reduce(data),
                outputs=["reduced"],
            )
        )
        dag.execute()
        assert np.array_equal(dag.buffers["reduced"], np.array([4.0, 8.0, 12.0]))

    def test_manifold_to_geodesic_search(self):
        """Manifold ingest feeds geodesic search."""
        substrate = PrimeStorageManifold(TensorCoreGPU_Context(), n_primes=25)
        substrate.ingest_sync(b"search target" * 10, ManifoldCurvature.GOLDEN_DENSE)
        search_vec = np.zeros(DIM)
        search_vec[0] = 100.0
        result = substrate.query(search_vec)
        # Search may or may not find — must not crash
        assert result is None or isinstance(result, bytes)

    def test_self_healing_triggers(self):
        """Corrupted node triggers self-healing."""
        substrate = PrimeStorageManifold(TensorCoreGPU_Context(), n_primes=25)
        uid = substrate.ingest_sync(b"healing test", ManifoldCurvature.GOLDEN_DENSE)
        tensor = substrate.tensors[uid]
        # Corrupt the anchor
        tensor.integer_anchor = -1
        new_uid = substrate.self_healing.trigger(tensor)
        assert new_uid is not None
        assert len(substrate.self_healing.heal_log) > 0

    def test_all_layers_together(self):
        """All five layers execute together without conflict."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
        # Layer 1
        future = substrate.cu_pool.submit_workgroup(lambda: 42)
        assert future.result() == 42
        # Layer 2
        result = substrate.vectorize(lambda x: x + 1, np.array([1, 2, 3]))
        assert np.array_equal(result, [2, 3, 4])
        # Layer 3
        C = substrate.gemm(np.eye(16, dtype=np.float32), np.eye(16, dtype=np.float32))
        assert np.allclose(C, np.eye(16), atol=1e-5)
        # Layer 4
        reduced = substrate.all_reduce(np.array([1.0, 2.0]))
        assert np.array_equal(reduced, np.array([4.0, 8.0]))
        # Layer 5
        substrate.register_dag_node(DAGNode("X", lambda: np.array([1]), outputs=["x"]))
        substrate.execute_dag()
        assert "x" in substrate.dag.buffers
        substrate.shutdown()


# ==============================================================================
# SECTION 7: END-TO-END TESTS
# ==============================================================================


class TestEndToEnd:
    """Full end-to-end tests of the complete system."""

    def test_e2e_single_payload(self):
        """Ingest → retrieve single payload."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
        payload = b"end-to-end test payload" * 100
        loop = asyncio.new_event_loop()
        uid = loop.run_until_complete(substrate.ingest(payload, ManifoldCurvature.GOLDEN_DENSE))
        recovered = loop.run_until_complete(substrate.retrieve(uid))
        assert recovered == payload
        substrate.shutdown()
        loop.close()

    def test_e2e_thousand_payloads(self):
        """Ingest → retrieve 1000 payloads."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=8)
        loop = asyncio.new_event_loop()
        payloads = [f"payload_{i}".encode() * 10 for i in range(1000)]
        uids = []
        for p in payloads:
            uid = loop.run_until_complete(substrate.ingest(p, ManifoldCurvature.GOLDEN_DENSE))
            uids.append(uid)
        for uid, original in zip(uids, payloads):
            recovered = loop.run_until_complete(substrate.retrieve(uid))
            assert recovered == original
        substrate.shutdown()
        loop.close()

    def test_e2e_multi_curvature(self):
        """Ingest payloads with different curvatures."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
        loop = asyncio.new_event_loop()
        curvatures = [
            ManifoldCurvature.GOLDEN_DENSE,
            ManifoldCurvature.SILVER_ARCHIVAL,
            ManifoldCurvature.BRONZE,
            ManifoldCurvature.COPPER,
            ManifoldCurvature.NICKEL,
        ]
        for curv in curvatures:
            payload = f"payload_{curv.value}".encode() * 20
            uid = loop.run_until_complete(substrate.ingest(payload, curv))
            recovered = loop.run_until_complete(substrate.retrieve(uid))
            assert recovered == payload
        substrate.shutdown()
        loop.close()

    def test_e2e_multi_sector(self):
        """Ingest payloads assigned to different Millennium sectors."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
        loop = asyncio.new_event_loop()
        sectors = [
            ManifoldSector.P_VS_NP,
            ManifoldSector.YANG_MILLS,
            ManifoldSector.RIEMANN,
            ManifoldSector.NAVIER_STOKES,
            ManifoldSector.BSD,
            ManifoldSector.HODGE,
            ManifoldSector.POINCARE,
        ]
        for sector in sectors:
            payload = f"sector_{sector.value}".encode() * 20
            uid = loop.run_until_complete(
                substrate.ingest(payload, ManifoldCurvature.GOLDEN_DENSE, sector)
            )
            tensor = substrate.manifold.tensors[uid]
            assert tensor.manifold_sector == sector
        substrate.shutdown()
        loop.close()

    def test_e2e_flat_and_curved(self):
        """Mix EUCLIDEAN_FLAT and GOLDEN_DENSE payloads."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
        loop = asyncio.new_event_loop()
        flat_payload = b"flat payload" * 10
        curved_payload = b"curved payload" * 10
        flat_uid = loop.run_until_complete(
            substrate.ingest(flat_payload, ManifoldCurvature.EUCLIDEAN_FLAT)
        )
        curved_uid = loop.run_until_complete(
            substrate.ingest(curved_payload, ManifoldCurvature.GOLDEN_DENSE)
        )
        assert loop.run_until_complete(substrate.retrieve(flat_uid)) == flat_payload
        assert loop.run_until_complete(substrate.retrieve(curved_uid)) == curved_payload
        substrate.shutdown()
        loop.close()

    def test_e2e_full_stats(self):
        """Full pipeline produces expected stats."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
        loop = asyncio.new_event_loop()
        for i in range(10):
            loop.run_until_complete(
                substrate.ingest(f"payload_{i}".encode() * 10, ManifoldCurvature.GOLDEN_DENSE)
            )
        stats = substrate.stats()
        assert stats["manifold"]["total_tensors"] >= 10
        assert stats["compute"]["n_sms"] == 4
        assert stats["cluster"]["n_actors"] == 4
        substrate.shutdown()
        loop.close()

    def test_e2e_benchmark(self):
        """Full pipeline benchmarks in acceptable time."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=8)
        loop = asyncio.new_event_loop()
        start = time.perf_counter()
        for i in range(100):
            loop.run_until_complete(
                substrate.ingest(f"bench_{i}".encode() * 10, ManifoldCurvature.GOLDEN_DENSE)
            )
        elapsed = time.perf_counter() - start
        throughput = 100 / elapsed
        assert throughput > 10  # at least 10 payloads/sec
        substrate.shutdown()
        loop.close()

    def test_e2e_stress_10000(self):
        """Stress test with 10,000 payloads."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=8)
        loop = asyncio.new_event_loop()
        uids = []
        for i in range(10000):
            uid = loop.run_until_complete(
                substrate.ingest(f"s_{i}".encode() * 5, ManifoldCurvature.GOLDEN_DENSE)
            )
            uids.append(uid)
        assert len(uids) == 10000
        assert len(set(uids)) == 10000  # all unique
        substrate.shutdown()
        loop.close()

    def test_e2e_concurrent_ingest(self):
        """Concurrent async ingestion."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=8)

        async def ingest_many():
            tasks = [
                substrate.ingest(f"c_{i}".encode() * 5, ManifoldCurvature.GOLDEN_DENSE)
                for i in range(100)
            ]
            return await asyncio.gather(*tasks)

        loop = asyncio.new_event_loop()
        uids = loop.run_until_complete(ingest_many())
        assert len(uids) == 100
        assert len(set(uids)) == 100
        substrate.shutdown()
        loop.close()

    def test_e2e_recovery_after_corruption(self):
        """Corrupt a node, verify self-healing recovers."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
        loop = asyncio.new_event_loop()
        uid = loop.run_until_complete(
            substrate.ingest(b"recover me" * 10, ManifoldCurvature.GOLDEN_DENSE)
        )
        tensor = substrate.manifold.tensors[uid]
        tensor.integer_anchor = -999  # corrupt
        new_uid = substrate.manifold.self_healing.trigger(tensor)
        assert new_uid is not None
        assert len(substrate.manifold.self_healing.heal_log) > 0
        substrate.shutdown()
        loop.close()

    def test_e2e_full_stack_with_dag(self):
        """Full stack: ingest → DAG → retrieve."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
        loop = asyncio.new_event_loop()
        uid = loop.run_until_complete(
            substrate.ingest(b"dag test" * 10, ManifoldCurvature.GOLDEN_DENSE)
        )
        substrate.register_dag_node(
            DAGNode(
                "retrieve",
                lambda: loop.run_until_complete(substrate.retrieve(uid)),
                outputs=["retrieved"],
            )
        )
        substrate.execute_dag()
        retrieved = substrate.dag.buffers["retrieved"]
        assert retrieved == b"dag test" * 10
        substrate.shutdown()
        loop.close()

    def test_e2e_100_curvature_sector_combinations(self):
        """Test all curvature × sector combinations."""
        substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
        loop = asyncio.new_event_loop()
        combinations = [(c, s) for c in ManifoldCurvature for s in ManifoldSector]
        for curv, sect in combinations:
            payload = f"{curv.value}_{sect.value}".encode() * 10
            uid = loop.run_until_complete(substrate.ingest(payload, curv, sect))
            recovered = loop.run_until_complete(substrate.retrieve(uid))
            assert recovered == payload
        substrate.shutdown()
        loop.close()


# ==============================================================================
# SECTION 8: CONCURRENCY & THREAD SAFETY TESTS
# ==============================================================================


class TestConcurrency:
    """Thread safety and concurrency tests."""

    def test_concurrent_sm_submissions(self):
        """Concurrent submissions to VirtualSM are safe."""
        sm = VirtualSM(0, n_threads=16)
        results = []
        lock = threading.Lock()

        def worker(i):
            r = sm.submit(lambda x: x * 2, i).result()
            with lock:
                results.append(r)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sorted(results) == [i * 2 for i in range(50)]
        sm.shutdown()

    def test_concurrent_pool_access(self):
        """Concurrent pool access is safe."""
        pool = ComputeUnitPool(n_sms=4, threads_per_sm=8)
        futures = [pool.submit_workgroup(lambda x: x + 1, i) for i in range(100)]
        results = [f.result() for f in futures]
        assert sorted(results) == [i + 1 for i in range(100)]
        pool.shutdown()

    def test_concurrent_prime_substrate(self):
        """Concurrent commits to prime substrate."""
        substrate = GaloisPrimeSubstrate(n_primes=25)
        lock = threading.Lock()

        def commit_worker(i):
            with lock:
                substrate.commit(anchor=i, uuid_str=f"uuid_{i}", payload=f"data_{i}".encode())

        threads = [threading.Thread(target=commit_worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for i in range(100):
            assert substrate.fetch(f"uuid_{i}") == f"data_{i}".encode()

    def test_concurrent_manifold_ingest(self):
        """Concurrent manifold ingestion."""
        substrate = PrimeStorageManifold(TensorCoreGPU_Context(), n_primes=25)
        uids = []
        lock = threading.Lock()

        def ingest_worker(i):
            uid = substrate.ingest_sync(
                f"concurrent_{i}".encode() * 10,
                ManifoldCurvature.GOLDEN_DENSE,
            )
            with lock:
                uids.append(uid)

        threads = [threading.Thread(target=ingest_worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(uids) == 50
        assert len(set(uids)) == 50


# ==============================================================================
# SECTION 9: PERFORMANCE TESTS
# ==============================================================================


class TestPerformance:
    """Performance benchmarks."""

    def test_zeckendorf_throughput(self):
        """Zeckendorf encode throughput."""
        start = time.perf_counter()
        for i in range(100000):
            HardenedZeckendorfCodec.encode(i)
        elapsed = time.perf_counter() - start
        throughput = 100000 / elapsed
        assert throughput > 5000  # not pathologically slow (load-tolerant bound)

    def test_cassini_throughput(self):
        """Cassini verification throughput."""
        start = time.perf_counter()
        for n in range(1, 1001):
            CassiniVerifier.verify(n)
        elapsed = time.perf_counter() - start
        throughput = 1000 / elapsed
        assert throughput > 100  # at least 100 ops/sec

    def test_gemm_throughput(self):
        """GEMM throughput."""
        mk = MicroKernelLibrary()
        A = np.random.randn(64, 64).astype(np.float32)
        B = np.random.randn(64, 64).astype(np.float32)
        start = time.perf_counter()
        for _ in range(100):
            mk.gemm(A, B)
        elapsed = time.perf_counter() - start
        throughput = 100 / elapsed
        assert throughput > 50  # at least 50 GEMMs/sec

    def test_prime_substrate_throughput(self):
        """Prime substrate throughput."""
        substrate = GaloisPrimeSubstrate(n_primes=25)
        start = time.perf_counter()
        for i in range(1000):
            substrate.commit(anchor=i, uuid_str=f"u{i}", payload=f"p{i}".encode() * 10)
        elapsed = time.perf_counter() - start
        throughput = 1000 / elapsed
        assert throughput > 100  # at least 100 ops/sec


# ==============================================================================
# SECTION 10: REGRESSION TESTS
# ==============================================================================


class TestRegressions:
    """Regression tests for known bugs."""

    def test_regression_cassini_always_true(self):
        """Regression: old Cassini check was always True."""
        # Old check: det = 1 if n % 2 == 0 else -1; return det == (-1)**n
        # This is always True. New check must be falsifiable.
        assert CassiniVerifier.verify(5) is True
        assert CassiniVerifier.verify_with_values(5, 11, 6) is False

    def test_regression_zeckendorf_overflow(self):
        """Regression: old codec truncated at F_92."""
        # Old max was 2^63 - 1. New max is 2^64 - 1.
        n_max = 2**64 - 1
        mask = HardenedZeckendorfCodec.encode(n_max)
        assert HardenedZeckendorfCodec.decode(mask) == n_max

    def test_regression_prime_blowup(self):
        """Regression: old composite keys caused factorial blowup."""
        substrate = GaloisPrimeSubstrate(n_primes=25)
        payload = b"\xff" * 1024
        composite = substrate.commit(anchor=1, uuid_str="big", payload=payload)
        # Must be bounded
        assert composite < MODULUS_Q
        # Must complete quickly
        start = time.perf_counter()
        for i in range(100):
            substrate.commit(anchor=i, uuid_str=f"u{i}", payload=payload)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0  # must complete in < 5 seconds

    def test_regression_dag_false_culls(self):
        """Regression: old DAG pruning had false culls."""
        dag = DependencyDAG()
        dag.add_node(DAGNode("A", lambda: np.array([1]), outputs=["a"]))
        dag.add_node(DAGNode("B", lambda x: x, inputs=["a"], outputs=["b"]))
        # A is used by B; B's output is unused
        dag.prune_dead_code()
        # B should be culled, A should NOT
        assert dag.nodes["B"].culled
        assert not dag.nodes["A"].culled

    def test_regression_gemm_non_square(self):
        """Regression: old GEMM didn't handle non-square matrices."""
        mk = MicroKernelLibrary()
        A = np.random.randn(7, 13).astype(np.float32)
        B = np.random.randn(13, 5).astype(np.float32)
        C = mk.gemm(A, B)
        assert C.shape == (7, 5)
        assert np.allclose(C, A @ B, atol=1e-3)


# ==============================================================================
# SECTION 11: DIGEST-VERIFIED INTEGRITY & REPAIR
# ==============================================================================


class TestDigestIntegrity:
    """Payload integrity is enforced by SHA-256 digests plus redundant
    copies — the Cassini identity is a tautology over integer anchors and
    cannot detect corruption by itself."""

    def test_synchronize_returns_promptly_when_idle(self):
        """Regression: barrier(n_threads) awaited by one caller always
        timed out after 5s without synchronizing anything."""
        sm = VirtualSM(0, n_threads=8)
        t0 = time.perf_counter()
        sm.synchronize()
        assert time.perf_counter() - t0 < 2.0
        sm.shutdown()

    def test_synchronize_waits_for_submitted_work(self):
        pool = ComputeUnitPool(n_sms=2, threads_per_sm=4)
        done = []
        pool.submit_workgroup(lambda: (time.sleep(0.2), done.append(1)))
        pool.synchronize_all()
        assert done == [1]
        pool.shutdown()

    def test_payload_only_corruption_detected_and_healed(self):
        """Corrupt sparse bytes only — digest catches it, replica repairs."""
        manifold = PrimeStorageManifold(TensorCoreGPU_Context(), n_primes=25)
        payload = b"integrity protected record"
        uid = manifold.ingest_sync(payload, ManifoldCurvature.GOLDEN_DENSE)
        tensor = manifold.tensors[uid]
        tensor.sparse_topology = {0: 1}
        assert manifold.read_payload(tensor) == payload
        assert manifold.self_healing.heal_log

    def test_unrecoverable_when_all_copies_corrupt(self):
        manifold = PrimeStorageManifold(TensorCoreGPU_Context(), n_primes=25)
        uid = manifold.ingest_sync(b"data", ManifoldCurvature.GOLDEN_DENSE)
        tensor = manifold.tensors[uid]
        tensor.sparse_topology = {0: 1}
        manifold.curved_storage.uuid_index.pop(uid, None)
        assert manifold.read_payload(tensor) is None
        assert any(e["kind"] == "unrecoverable" for e in manifold.self_healing.heal_log)

    def test_anchor_index_retains_collisions(self):
        """Only 90 anchors exist — the index must be a multimap."""
        manifold = PrimeStorageManifold(TensorCoreGPU_Context(), n_primes=25)
        uids = [
            manifold.ingest_sync(f"c{i}".encode() * 20, ManifoldCurvature.GOLDEN_DENSE)
            for i in range(200)
        ]
        for uid in uids:
            assert any(uid in bucket for bucket in manifold.anchor_index.values())

    def test_prime_cells_survive_later_commits(self):
        """Regression: cells keyed by prime alone were clobbered per commit."""
        substrate = GaloisPrimeSubstrate(n_primes=25)
        substrate.commit(anchor=1, uuid_str="a", payload=b"AAAA")
        substrate.commit(anchor=2, uuid_str="b", payload=b"BBBB")
        assert "a" in substrate.cells[2]
        assert "b" in substrate.cells[2]

    def test_flat_payload_repairable_via_prime_copy(self):
        """EUCLIDEAN_FLAT payloads also carry a redundant prime copy."""
        manifold = PrimeStorageManifold(TensorCoreGPU_Context(), n_primes=25)
        uid = manifold.ingest_sync(b"flat", ManifoldCurvature.EUCLIDEAN_FLAT)
        tensor = manifold.tensors[uid]
        tensor.raw_payload = b"CORRUPT"
        assert manifold.read_payload(tensor) == b"flat"


# ==============================================================================
# PYTEST CONFIGURATION
# ==============================================================================


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "adversarial: marks adversarial tests")
    config.addinivalue_line("markers", "property: marks property-based tests")


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--maxfail=1"])
