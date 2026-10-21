from math import gcd
from euclid.pythagoras.quantum.lucas_pisot import (
    DOMAIN_SCALE_INDEX, HendrixStructuredSearch, resolve_scale, scaled_budget,
)


def test_all_declared_lucas_scales_are_exact_and_monotonic():
    values = [resolve_scale("test", n).lucas_value for n in (7, 10, 12, 15, 18, 20, 31, 50, 76)]
    assert values == sorted(values)
    assert values[0] == 29
    assert values[-1] == 7639424778862807


def test_domains_have_distinct_capability_rungs():
    assert set(DOMAIN_SCALE_INDEX) >= {"qubit_gate", "qft", "grover", "ctqw", "aqo", "memory", "structured_search"}
    assert scaled_budget("memory", 100) > scaled_budget("qubit_gate", 100)


def test_hendrix_schedule_covers_nonce_space_without_overlap():
    schedule = HendrixStructuredSearch(workers=7, scale_index=76).plan(1009)
    assert schedule.verify()
    all_nonces = [n for worker in range(schedule.workers) for n in schedule.worker_nonces(worker)]
    assert len(all_nonces) == len(set(all_nonces)) == 1009
    assert set(all_nonces) == set(range(1009))
    assert gcd(schedule.stride, schedule.nonce_count) == 1


def test_hendrix_search_is_deterministic_and_not_quantum_claim():
    engine = HendrixStructuredSearch(workers=4, scale_index=31)
    a = engine.search(100, lambda n: n == 73)
    b = engine.search(100, lambda n: n == 73)
    assert a == b
    assert a["winner"] == 73
    assert a["quantum_claim"] is False
