"""Tests for the prime-addressed exponent store."""

import numpy as np

from Intelligence.prime_memory import (
    PrimeMemory,
    ExponentialPrimeStore,
    QuantumPrimeMemory,
)


def test_prime_memory_write_read():
    mem = PrimeMemory(n_primes=25)
    data = b"hello world"
    addr = mem.write(data)
    read = mem.read(addr)
    assert read == data


def test_prime_memory_exponents():
    mem = PrimeMemory(n_primes=25)
    data = b"\x00\x00\x00\x00\x00\x00\x00\x05"  # exponent 5
    addr = mem.write(data)
    assert addr.exponents[0] == 5


def test_prime_memory_stats():
    mem = PrimeMemory(n_primes=25)
    for i in range(10):
        mem.write(f"data_{i}".encode())
    stats = mem.stats()
    assert stats["total_writes"] == 10
    assert stats["capacity_states"] == 2**1600


def test_composite_is_computable():
    """The fingerprinted composite must be a fixed-size int, not p**e."""
    mem = PrimeMemory(n_primes=25)
    addr = mem.write(b"data")
    assert addr.composite.bit_length() <= 256
    assert len(addr.to_bytes()) <= 32


def test_exponential_prime_store():
    store = ExponentialPrimeStore(n_primes=25)
    addr = store.store("key1", b"value1")
    read = store.retrieve(addr)
    assert read == b"value1"


def test_quantum_prime_memory():
    qpm = QuantumPrimeMemory(n_qubits=11)
    amplitudes = np.random.randn(2048) + 1j * np.random.randn(2048)
    qpm.store_superposition(0, amplitudes)
    counts = qpm.measure(0, shots=100)
    assert sum(counts.values()) == 100


def test_crystallization():
    mem = PrimeMemory(n_primes=25)
    mem.write(b"permanent data")
    assert mem.crystallize(2)
    assert mem.cells[2].crystallized
