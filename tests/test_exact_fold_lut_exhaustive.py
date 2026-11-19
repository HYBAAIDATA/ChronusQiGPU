"""Finite-domain exact M15 pair-equivalence and real public observation checks."""
from dataclasses import replace
import hashlib
import io

import numpy as np
import pytest

from chronus.execution.structural import fold_pair, unfold_pair
from chronus.tensor.folded_state import ExactFoldState, _pair_luts

pytestmark = pytest.mark.real


def test_complete_65536_byte_pair_domain_is_exact():
    payload = b"".join(bytes((i >> 8, i & 255)) for i in range(65536))
    state = ExactFoldState.from_bytes(payload)
    expected = b"".join(bytes(fold_pair(i >> 8, i & 255)) for i in range(65536))
    assert state.folded == expected
    assert state.unfold() == payload
    assert state.unfold_partial(3, 129) == payload[3:129]
    a, b = _pair_luts()
    assert not a.flags.writeable and not b.flags.writeable
    for i in range(65536):
        mapped = int(a[i])
        assert int(b[mapped]) == i
        assert unfold_pair(mapped >> 8, mapped & 255) == (i >> 8, i & 255)


@pytest.mark.parametrize("size", [1, 2, 3, 63, 64, 65, 4097])
def test_odd_padding_partial_and_integrity_digest(size):
    payload = bytes(i % 251 for i in range(size))
    state = ExactFoldState.from_bytes(payload)
    assert state.original_length == size
    assert state.unfold() == payload
    assert len(state.folded) == size + (size & 1)
    assert state.unfold_partial(0, size) == payload
    assert state.unfold_partial(1, size) == payload[1:]
    if size > 1:
        assert state.unfold_partial(1, min(size, 9)) == payload[1:min(size, 9)]
    tampered = replace(state, folded=bytes([state.folded[0] ^ 1]) + state.folded[1:])
    with pytest.raises(ValueError, match="digest mismatch"):
        tampered.unfold()


@pytest.mark.real
@pytest.mark.parametrize("name,load,pinned", [
    ("digits", "load_digits", "0f1c225bbabf3d4eaccd81f73c9594ceec77d84c9b425ef0e4cc815743050529"),
    ("wine", "load_wine", "09af9db3ce2a52b3f168d5d9eb1d4d4ceba584fad9e0e9aba63ff536c192c6a6"),
    ("breast_cancer", "load_breast_cancer", "602e781b91843b0ea3dc8bf3ff3e63055985230cad47c45a5099780e3c33459f"),
])
def test_real_observed_uci_bytes_roundtrip(name, load, pinned):
    sklearn = pytest.importorskip("sklearn")
    if sklearn.__version__ != "1.8.0":
        pytest.skip("pinned scikit-learn 1.8.0 unavailable")
    from sklearn import datasets
    data = np.asarray(getattr(datasets, load)().data, dtype=np.float64)
    output = io.BytesIO()
    np.save(output, data, allow_pickle=False)
    payload = output.getvalue()
    assert hashlib.sha256(payload).hexdigest() == pinned
    state = ExactFoldState.from_bytes(payload)
    assert state.unfold() == payload
    assert state.unfold_partial(3, 131) == payload[3:131]
