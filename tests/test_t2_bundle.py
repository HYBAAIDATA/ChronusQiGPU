import pytest
from chronus.crypto.signers import ml_dsa_available,SignerUnavailable
from scripts.seal_bundle import build
from scripts.check_bundle import check
import json

pytestmark = pytest.mark.real

def test_t2_positive_negative_and_tamper(tmp_path):
    if not ml_dsa_available():
        with pytest.raises(SignerUnavailable):
            build(tmp_path/"bundle")
        return
    root=tmp_path/"bundle"
    build(root)
    keys=json.loads((root/"public-keys.json").read_text())
    assert check(root,keys)==0
    altered=root/"sets"/"clean"/"0001.json"
    altered.write_text(altered.read_text().replace('"index":1','"index":88'))
    assert check(root,keys)==2
