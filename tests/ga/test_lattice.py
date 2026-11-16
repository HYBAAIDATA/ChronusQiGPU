from concurrent.futures import ThreadPoolExecutor

import pytest

from ga.mathcore import PhyllotaxisLattice


def test_collisions_never_lose_records():
    lattice = PhyllotaxisLattice(capacity=101)
    lattice._digests = lambda _key: (0, 1)
    for index in range(100):
        lattice.store(f"key-{index}", {"index": index})

    assert lattice.count == 100
    for index in range(100):
        record = lattice.retrieve(f"key-{index}")
        assert record is not None
        assert record["value"] == {"index": index}


def test_retrieve_uses_the_recorded_open_addressing_index():
    lattice = PhyllotaxisLattice(capacity=101)
    lattice._digests = lambda _key: (0, 1)
    for index in range(80):
        lattice.store(f"key-{index}", index)

    assert lattice.indices["key-0"] == 0
    assert lattice.indices["key-79"] == 79
    assert lattice.retrieve("key-0")["value"] == 0
    assert lattice.retrieve("key-79")["value"] == 79
    assert lattice.retrieve("missing") is None


def test_threaded_collision_writes_are_consistent():
    lattice = PhyllotaxisLattice(capacity=1_009)
    lattice._digests = lambda _key: (0, 1)

    def store(index: int) -> None:
        lattice.store(f"thread-{index}", {"index": index})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(store, range(400)))

    assert len(lattice.indices) == 400
    assert lattice.count == 400
    assert all(lattice.retrieve(f"thread-{index}") is not None for index in range(400))


def test_composite_capacity_is_rejected_for_double_hashing():
    with pytest.raises(ValueError, match="not prime"):
        PhyllotaxisLattice(capacity=1_000_000)


def test_fibonacci_neighbors_do_not_repeat_the_first_offset():
    lattice = PhyllotaxisLattice(capacity=101)
    assert lattice._get_fibonacci_neighbors(50, 4) == [51, 49, 52, 48, 53, 47, 55, 45]


def test_spiral_query_rebuilds_the_exact_tree():
    lattice = PhyllotaxisLattice(capacity=101)
    lattice.store("center", {"nested": {"value": 1}})
    results = lattice.spiral_query("center", radius=0)
    assert [record["key"] for record in results] == ["center"]
    assert lattice._tree_dirty is False
