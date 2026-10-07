"""Self-tests of Aethel's hardened unified substrate.

They lived only inside TURING's copy of the module; the copy is removed in
favour of the canonical ``aethel.hardened_unified_substrate``, so the checks
move here and run against the canonical implementation.
"""

import asyncio

import numpy as np

from aethel.hardened_unified_substrate import (
    MODULUS_Q,
    CassiniVerifier,
    DAGNode,
    DependencyDAG,
    GaloisPrimeSubstrate,
    HardenedZeckendorfCodec,
    ManifoldCurvature,
    MicroKernelLibrary,
    SPMDExecutor,
    UnifiedSubstrate,
    VirtualSM,
)


def test_cassini_rigorous():
    for n in range(1, 20):
        assert CassiniVerifier.verify(n), f"Cassini failed at n={n}"
    lucas_5 = CassiniVerifier.lucas(5)
    fib_5 = CassiniVerifier.fibonacci(5)
    assert (lucas_5, fib_5) == (11, 5)
    assert lucas_5**2 - 5 * fib_5**2 == 4 * (-1) ** 5 == -4


def test_cassini_verification_gate_rejects_wrong_values():
    assert CassiniVerifier.verify(10) is True
    assert CassiniVerifier.verify_with_values(5, 11, 6) is False


def test_zeckendorf_extended_covers_full_64_bit():
    n = 2**64 - 1
    mask = HardenedZeckendorfCodec.encode(n)
    assert HardenedZeckendorfCodec.verify_non_adjacent(mask)
    assert HardenedZeckendorfCodec.decode(mask) == n
    assert HardenedZeckendorfCodec.FIBONACCI[93] == 19740274219868223167


def test_galois_prime_substrate_round_trip():
    substrate = GaloisPrimeSubstrate(n_primes=25)
    payload = b"galois test payload"
    composite = substrate.commit(anchor=10, uuid_str="test1", payload=payload)
    assert composite > 0
    assert substrate.fetch("test1") == payload
    assert substrate.stats()["modulus"] == MODULUS_Q


def test_hardened_gemm_non_square():
    rng = np.random.default_rng(7)
    a = rng.standard_normal((37, 53)).astype(np.float32)
    b = rng.standard_normal((53, 41)).astype(np.float32)
    assert np.allclose(MicroKernelLibrary().gemm(a, b), a @ b, atol=1e-3)


def test_safe_dag_pruning_keeps_live_roots():
    dag = DependencyDAG()
    dag.add_node(DAGNode("A", lambda: np.array([1]), outputs=["bufA"]))
    dag.add_node(DAGNode("B", lambda x: x * 2, inputs=["bufA"], outputs=["bufB"]))
    dag.add_node(DAGNode("C", lambda x: x + 1, inputs=["bufA"], outputs=["bufC"]))
    dag.add_node(DAGNode("D", lambda x: x - 1, inputs=["bufC"], outputs=["bufD"]))
    assert dag.prune_dead_code() >= 0
    assert dag.nodes["A"].culled is False


def test_virtual_sm_executes():
    sm = VirtualSM(0, n_threads=4)
    try:
        assert sm.submit(lambda x: x * 2, 21).result() == 42
    finally:
        sm.shutdown()


def test_spmd_divergence_matches_numpy_where():
    data = np.array([1.0, 5.0, 2.0, 8.0])
    condition = data > 3.0
    result = SPMDExecutor(n_lanes=32).diverge(condition, lambda x: x * 10, lambda x: x + 1, data)
    assert np.allclose(result, np.where(condition, data * 10, data + 1))


def test_full_unified_substrate_ingest_and_retrieve():
    substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
    try:
        payload = b"unified hardened test payload" * 10

        async def roundtrip():
            uid = await substrate.ingest(payload, ManifoldCurvature.GOLDEN_DENSE)
            return await substrate.retrieve(uid)

        assert asyncio.run(roundtrip()) == payload
    finally:
        substrate.shutdown()


def test_unified_stats_sections():
    substrate = UnifiedSubstrate(n_primes=25, n_sms=4)
    try:
        stats = substrate.stats()
        for section in ("manifold", "compute", "cluster", "dag"):
            assert section in stats
    finally:
        substrate.shutdown()
