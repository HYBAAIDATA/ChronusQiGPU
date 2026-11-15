from concurrent.futures import ThreadPoolExecutor

from ga.mathcore import GaloisField


def test_tables_build_once_under_concurrent_first_use():
    field = GaloisField()
    assert field.exp == []
    assert field.log == []
    assert field._ready is False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda value: field.mul(value, value + 1), range(1, 33))
        )

    assert len(results) == 32
    assert field.exp
    assert field.log
    assert field._ready is True
    assert len(field.exp) == field.order
    assert len(field.log) == field.q
    assert len(set(field.exp)) == field.order
