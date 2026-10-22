"""Optimized reads still authenticate both replicas on every invocation."""
import random
import pytest
from aethel.enterprise import compose, UnrecoverableCustodyError
from aethel.zeckendorf import HardenedZeckendorfCodec as Codec


def test_each_replica_is_validated_once_per_read(tmp_path, monkeypatch):
    custody = compose(tmp_path, hmac_key=b"single-pass-fixture-key-32bytes!!")
    custody.put(b"authenticated payload" * 64, record_id="one")
    calls = []
    original = custody._validate_dict
    def observed(data, expected_record_id=None):
        calls.append(expected_record_id)
        return original(data, expected_record_id)
    monkeypatch.setattr(custody, "_validate_dict", observed)
    assert custody.get("one") == b"authenticated payload" * 64
    assert calls == ["one", "one"]
    calls.clear()
    custody.corrupt_for_test("one", side="primary")
    assert custody.get("one") == b"authenticated payload" * 64
    assert calls == ["one", "one"]
    calls.clear()
    custody.corrupt_for_test("one", side="primary")
    custody.corrupt_for_test("one", side="replica")
    with pytest.raises(UnrecoverableCustodyError):
        custody.get("one")
    assert calls == ["one", "one"]
    custody.close()


def test_sparse_decoder_matches_independent_sum_for_entire_bit_domain():
    rng = random.Random(20261022)
    masks = [0, 1, *[1 << i for i in range(len(Codec.FIBONACCI)-1)]]
    masks += [rng.getrandbits(len(Codec.FIBONACCI)-1) for _ in range(2000)]
    for mask in masks:
        expected = sum(Codec.FIBONACCI[i+1] for i in range(mask.bit_length()) if mask & (1 << i))
        assert Codec.decode(mask) == expected
    with pytest.raises(ValueError):
        Codec.decode(1 << (len(Codec.FIBONACCI)-1))
    with pytest.raises(ValueError):
        Codec.decode(-1)
