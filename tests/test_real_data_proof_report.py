"""Non-production contract tests for the internal proof report serializer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

pytestmark = pytest.mark.simulated
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'demo'))
from real_data_proof_report import main, verified_report


def _sealed(source_class='TEST_FIXTURE_NON_PRODUCTION', recovered=True):
    evidence = {
        'schema': 'chronus.real-workload/1',
        'input_count': 1,
        'result': 'PASS', 'production_qualification': 'UNVERIFIED',
        'signed_evidence': False, 'data_generated_by_benchmark': False,
        'device_execution': 'UNVERIFIED', 'external_source_attestation': 'UNVERIFIED',
        'git_commit': 'a' * 40,
        'measured_at_utc': '2026-11-16T06:00:00+00:00',
        'entries': [{'source_class': source_class, 'source_sha256': 'b' * 64,
                     'input_bytes': 512, 'custody_restart_roundtrip_verified': recovered,
                     'workload': {'operation': 'exact_snapshot_partial_unfold',
                                  'byte_exact_roundtrip_verified': True}}],
    }
    evidence['integrity_sha256'] = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return evidence


def test_rejects_synthetic_test_fixture_as_customer_proof():
    with pytest.raises(ValueError, match='test fixtures'):
        verified_report(_sealed())


def test_rejects_tampered_evidence():
    content = _sealed('OPERATOR_DECLARED_PRODUCTION')
    content['entries'][0]['input_bytes'] = 4096
    with pytest.raises(ValueError, match='integrity SHA-256 mismatch'):
        verified_report(content)


def test_customer_brief_contains_no_unsupported_release_claim():
    report = verified_report(_sealed('OPERATOR_DECLARED_PRODUCTION'))
    assert '512 bytes' in report
    assert 'Production/release qualification: **UNVERIFIED**' in report
    assert 'not cryptographically signed' in report
    assert '13x' not in report


def test_rejects_missing_recovery_or_unknown_workload():
    with pytest.raises(ValueError, match='custody restart'):
        verified_report(_sealed('OPERATOR_DECLARED_PRODUCTION', recovered=False))


def test_cli_keeps_source_intact_on_refusal(tmp_path: Path, capsys):
    path = tmp_path / 'fake.json'
    path.write_text(json.dumps(_sealed()))
    output = tmp_path / 'report.md'
    assert main(['--evidence', str(path), '--output', str(output)]) == 2
    assert not output.exists()
    assert json.loads(path.read_text())['schema'] == 'chronus.real-workload/1'
    assert 'FAIL' in capsys.readouterr().err


def test_public_dataset_proof_is_never_labelled_customer_or_production():
    public = _sealed('PUBLIC_OBSERVED_DATASET')
    report = verified_report(public)
    assert '# Chronus public-data benchmark demonstration' in report
    assert 'not customer production data' in report
    assert 'Production/release qualification: **UNVERIFIED**' in report


def test_mixed_public_and_customer_proofs_fail_closed():
    proof = _sealed('PUBLIC_OBSERVED_DATASET')
    entry = dict(proof['entries'][0])
    entry['source_class'] = 'OPERATOR_DECLARED_PRODUCTION'
    entry['source_sha256'] = 'c' * 64
    proof['entries'].append(entry)
    proof['input_count'] = 2
    proof.pop('integrity_sha256')
    proof['integrity_sha256'] = hashlib.sha256(
        json.dumps(proof, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match='must be reported separately'):
        verified_report(proof)
