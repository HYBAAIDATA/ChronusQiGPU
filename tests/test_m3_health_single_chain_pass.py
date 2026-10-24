"""One measured mining-lineage verdict per health result, including denials."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from chronus.mla1517.mining.storage_recorder import MiningStorageRecorder


@pytest.mark.parametrize('valid', [True, False])
def test_health_uses_one_current_chain_verdict(valid):
    recorder = MiningStorageRecorder.__new__(MiningStorageRecorder)
    recorder.tenant_id = 'tenant-a'
    recorder.root = Path('/unused-isolated-health-fixture')
    recorder.strict = True
    recorder.errors = 0
    recorder.last_error = None
    recorder._last_health = None
    chain = Mock(return_value=valid)
    recorder.files = SimpleNamespace(
        verify_database=Mock(return_value={'passed': True, 'file_plane_ok': True}),
        reconcile_files=Mock(return_value=SimpleNamespace(passed=True, unresolved=())),
        verify_mining=chain,
    )
    result = recorder.health()
    assert result['healthy'] is valid
    assert result['mining_chain_ok'] is valid
    chain.assert_called_once_with('tenant-a')
