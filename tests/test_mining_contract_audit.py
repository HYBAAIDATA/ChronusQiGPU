import pytest

from mining.hash_pipeline import HashPipeline


class _NeverCalledHasher:
    backend = "test"
    device = "test"

    def __getattr__(self, name):
        raise AssertionError(f"hasher must not be called for invalid input: {name}")


@pytest.mark.parametrize(
    ("header", "target", "message"),
    [
        (bytes(79), bytes(32), "header must be 80 bytes"),
        (bytes(80), bytes(31), "target must be 32 bytes"),
    ],
)
def test_hash_pipeline_input_contract_survives_python_optimized_mode(
    header, target, message
):
    pipeline = HashPipeline(host=object(), hasher=_NeverCalledHasher())
    with pytest.raises(ValueError, match=message):
        pipeline.grind(header, target, [0])
    with pytest.raises(ValueError, match=message):
        pipeline.grind_m32(header, target, 0, tuple(range(32)), 32)