from dataclasses import replace
import pytest
from chronus.agent._contracts import ContractError


def test_identity_no_float(identity):
    with pytest.raises(ContractError):
        replace(identity, born_at=True)


def test_identity_artifact_bound(identity):
    with pytest.raises(ContractError):
        replace(identity, model_fingerprint="model-name")
