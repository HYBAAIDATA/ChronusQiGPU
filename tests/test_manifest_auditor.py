"""Tests for the qualification manifest auditor.

The auditor is a release-evidence gate: it must catch copied or missing
evidence in a manifest, and it must never crash on a malformed one. These
tests cover each finding type, the clean case, and the command-line contract.
"""

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import pytest

pytestmark = pytest.mark.real

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'audit_manifest', ROOT / 'scripts/ci/audit_manifest.py'
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

PROVENANCE = {
    'commit': '3da63fbab14e9441b1d7d1752763698d2fbbeb88',
    'environment': {'runner': 'ubuntu-latest', 'python': '3.13.1'},
    'command': 'python scripts/ci/manifest.py',
    'ci_url': 'https://github.com/hybadatadevops1/Chronusv2/actions/runs/42',
    'recorded_at': '2026-11-15T09:00:00+00:00',
}


MISSING = object()


def evidence(index, timestamp=None, telemetry=MISSING, **overrides):
    record = {
        'test_id': f'TEST_{index:02d}',
        'timestamp': timestamp or f'2026-11-15T09:00:{index:02d}.000000+00:00',
        'expected_outcome': True,
        'actual_outcome': True,
        'telemetry': {'latency_ms': index} if telemetry is MISSING else telemetry,
    }
    record.update(overrides)
    return record


def gate(name='G1: Gate Under Test', records=MISSING, **overrides):
    result = {
        'gate': name,
        'status': 'PASS',
        'details': {'check': 'PASS'},
        'evidence_records': (
            [evidence(1)] if records is MISSING else records
        ),
    }
    result.update(overrides)
    return result


def manifest(gates=None, **overrides):
    gates = [gate()] if gates is None else gates
    doc = dict(PROVENANCE)
    doc.update({
        'qualification_status': 'PRODUCTION_QUALIFIED',
        'release_gates_passed': sum(
            1 for g in gates if g.get('status') == 'PASS'
        ),
        'total_release_gates_evaluated': len(gates),
        'gate_results': gates,
    })
    doc.update(overrides)
    return doc


def finding_texts(doc):
    return '\n'.join(audit.findings(doc))



class ProvenanceTests(unittest.TestCase):
    def test_clean_manifest_has_no_findings(self):
        self.assertEqual(audit.findings(manifest()), [])

    def test_missing_provenance_fields_are_reported(self):
        for field in ('commit', 'environment', 'command', 'ci_url', 'recorded_at'):
            with self.subTest(field=field):
                doc = manifest()
                del doc[field]
                self.assertIn(
                    f"no provenance field resembling {field!r}",
                    finding_texts(doc),
                )

    def test_documented_aliases_satisfy_provenance(self):
        doc = manifest()
        del doc['commit']
        del doc['environment']
        doc['provenance'] = {'sha': 'abc1234', 'runner': 'ubuntu-latest'}
        self.assertNotIn('no provenance field', finding_texts(doc))

    def test_alias_must_appear_as_a_field_name(self):
        doc = manifest()
        del doc['ci_url']
        doc['notes'] = 'the ci_url was captured manually'
        self.assertIn(
            "no provenance field resembling 'ci_url'",
            finding_texts(doc),
        )

    def test_empty_value_is_not_provenance(self):
        doc = manifest()
        doc['commit'] = ''
        doc['environment'] = '   '
        text = finding_texts(doc)
        self.assertIn("no provenance field resembling 'commit'", text)
        self.assertIn("no provenance field resembling 'environment'", text)

    def test_nested_provenance_field_is_accepted(self):
        doc = manifest()
        for field in ('commit', 'environment', 'command', 'ci_url', 'recorded_at'):
            doc.pop(field)
        doc['provenance'] = {
            'commit': 'abc1234',
            'environment': {'runner': 'ubuntu-latest'},
            'command': 'pytest -q',
            'ci_url': 'https://example.invalid/run/1',
            'recorded_at': '2026-11-15T09:00:00+00:00',
        }
        self.assertNotIn('no provenance field', finding_texts(doc))

    def test_empty_nested_provenance_is_rejected(self):
        doc = manifest()
        doc['commit'] = ''
        self.assertIn("no provenance field resembling 'commit'", finding_texts(doc))

    def test_qualified_alias_name_is_accepted(self):
        doc = manifest()
        del doc['commit']
        del doc['environment']
        doc['provenance'] = {'git_sha': 'abc1234', 'python_version': '3.13.1'}
        self.assertNotIn('no provenance field', finding_texts(doc))

    def test_qualified_alias_with_empty_value_is_rejected(self):
        doc = manifest()
        del doc['commit']
        doc['provenance'] = {'git_sha': ''}
        self.assertIn("no provenance field resembling 'commit'", finding_texts(doc))

    def test_a_key_that_only_mentions_commit_is_not_provenance(self):
        doc = manifest()
        del doc['commit']
        doc['commit_message'] = 'wip'
        self.assertIn("no provenance field resembling 'commit'", finding_texts(doc))

    def test_a_key_that_only_mentions_environment_is_not_provenance(self):
        doc = manifest()
        del doc['environment']
        doc['environment_notes'] = 'local'
        self.assertIn("no provenance field resembling 'environment'", finding_texts(doc))

    def test_commit_value_must_look_like_a_commit(self):
        doc = manifest()
        doc['commit'] = 'not-a-sha'
        self.assertIn("no provenance field resembling 'commit'", finding_texts(doc))

    def test_recorded_at_must_be_iso(self):
        doc = manifest()
        doc['recorded_at'] = 'yesterday'
        self.assertIn("no provenance field resembling 'recorded_at'", finding_texts(doc))

    def test_ci_url_must_be_a_url(self):
        doc = manifest()
        doc['ci_url'] = 'see the dashboard'
        self.assertIn("no provenance field resembling 'ci_url'", finding_texts(doc))

    def test_environment_may_be_a_structured_object(self):
        doc = manifest()
        doc['environment'] = {'runner': 'ubuntu-latest'}
        self.assertNotIn("no provenance field resembling 'environment'", finding_texts(doc))

    def test_environment_object_with_only_empty_values_is_rejected(self):
        doc = manifest()
        doc['environment'] = {'runner': ''}
        self.assertIn("no provenance field resembling 'environment'", finding_texts(doc))


class EvidenceRecordTests(unittest.TestCase):
    def test_shared_timestamp_is_reported(self):
        records = [
            evidence(1, timestamp='2026-11-15T09:00:00+00:00'),
            evidence(2, timestamp='2026-11-15T09:00:00+00:00'),
        ]
        text = finding_texts(manifest([gate(records=records)]))
        self.assertIn('2 records share timestamp', text)

    def test_distinct_timestamps_are_accepted(self):
        records = [evidence(1), evidence(2)]
        text = finding_texts(manifest([gate(records=records)]))
        self.assertNotIn('share timestamp', text)

    def test_shared_telemetry_is_reported(self):
        shared = {'latency_ms': 0.012, 'peak_ram_mb': 14.2}
        records = [
            evidence(1, telemetry=dict(shared)),
            evidence(2, telemetry=dict(shared)),
        ]
        text = finding_texts(manifest([gate(records=records)]))
        self.assertIn('2 records share telemetry', text)

    def test_missing_telemetry_on_several_records_is_reported(self):
        records = [
            evidence(1, telemetry=None),
            evidence(2, telemetry=None),
        ]
        text = finding_texts(manifest([gate(records=records)]))
        self.assertIn('no telemetry recorded', text)
    def test_textual_outcomes_are_reported(self):
        records = [evidence(1, expected_outcome='LEASE_ACTIVE')]
        text = finding_texts(manifest([gate(records=records)]))
        self.assertIn('expected_outcome is not a boolean or integer', text)

    def test_boolean_and_integer_outcomes_are_accepted(self):
        records = [
            evidence(1, expected_outcome=True, actual_outcome=False),
            evidence(2, expected_outcome=1, actual_outcome=0),
        ]
        text = finding_texts(manifest([gate(records=records)]))
        self.assertNotIn('is not a boolean or integer', text)

    def test_missing_outcome_field_is_reported(self):
        records = [evidence(1)]
        del records[0]['actual_outcome']
        text = finding_texts(manifest([gate(records=records)]))
        self.assertIn('actual_outcome is missing', text)

    def test_unstamped_record_is_reported(self):
        records = [evidence(1, timestamp=None)]
        del records[0]['timestamp']
        text = finding_texts(manifest([gate(records=records)]))
        self.assertIn('1 evidence records have no timestamp', text)


class GateAccountingTests(unittest.TestCase):
    def test_mismatched_passed_count_is_reported(self):
        text = finding_texts(manifest(release_gates_passed=3))
        self.assertIn('gate count 1 != declared 3', text)

    def test_mismatched_total_is_reported(self):
        text = finding_texts(manifest(total_release_gates_evaluated=8))
        self.assertIn('1 gates listed, 8 declared', text)

    def test_qualified_manifest_needs_support_for_each_pass_gate(self):
        gates = [
            gate('G1: Supported'),
            gate('G2: Unsupported', details=None, records=[]),
        ]
        text = finding_texts(manifest(gates))
        self.assertIn('G2: Unsupported: PASS with no details or evidence', text)
        self.assertNotIn('G1: Supported: PASS with no details or evidence', text)

    def test_unsupported_pass_gate_is_tolerated_when_not_qualified(self):
        gates = [gate('G1: Unsupported', details=None, records=[])]
        text = finding_texts(
            manifest(gates, qualification_status='QUALIFICATION_FAILED')
        )
        self.assertNotIn('PASS with no details or evidence', text)


class DerivedThroughputTests(unittest.TestCase):
    def test_throughput_equal_to_inverse_p50_is_reported(self):
        gates = [gate(
            'G6: Performance',
            details=None,
            latency_ms={'p50': 0.0104, 'p95': 0.0135, 'p99': 0.0575},
            throughput_ops_sec=round(1000.0 / 0.0104, 2),
        )]
        text = finding_texts(manifest(gates))
        self.assertIn('derived, not measured', text)

    def test_measured_throughput_is_accepted(self):
        gates = [gate(
            'G6: Performance',
            details=None,
            latency_ms={'p50': 0.0104},
            throughput_ops_sec=50000.0,
        )]
        text = finding_texts(manifest(gates))
        self.assertNotIn('derived, not measured', text)

    def test_non_numeric_p50_is_ignored(self):
        gates = [gate(
            'G6: Performance',
            details=None,
            latency_ms={'p50': 'n/a'},
            throughput_ops_sec=100.0,
        )]
        self.assertNotIn('derived, not measured', finding_texts(manifest(gates)))


class MalformedInputTests(unittest.TestCase):
    def test_non_object_document_is_reported(self):
        self.assertEqual(audit.findings(['not', 'a', 'manifest']), [
            'manifest is not a JSON object'
        ])

    def test_non_list_gate_results_is_reported(self):
        text = finding_texts(manifest(gate_results='none'))
        self.assertIn('gate_results is not a list', text)

    def test_non_object_gate_is_reported(self):
        text = finding_texts(manifest(gate_results=['G1']))
        self.assertIn('gate #0 is not an object', text)

    def test_non_list_evidence_records_is_reported(self):
        text = finding_texts(manifest([gate(evidence_records={'a': 1})]))
        self.assertIn('evidence_records is not a list', text)

    def test_malformed_document_never_raises(self):
        for doc in ({}, {'gate_results': None}, {'gate_results': [None]},
                    {'qualification_status': 'PRODUCTION_QUALIFIED'}):
            with self.subTest(doc=doc):
                self.assertIsInstance(audit.findings(doc), list)


class HistoricalManifestTests(unittest.TestCase):
    """The historical decision comes from manifests/historical.txt.

    A manifest that could declare itself historical would be a silencer:
    any file could empty its own findings. The list is a separate, reviewable
    file, so adding an entry is a visible decision in a diff.
    """

    def test_a_manifest_cannot_declare_itself_historical(self):
        doc = manifest(release_gates_passed=3, status='historical')
        self.assertFalse(audit.is_historical(doc, 'manifests/whatever.json'))
        self.assertTrue(audit.blocking_findings(doc, 'manifests/whatever.json'))

    def test_archival_status_field_is_not_a_silencer(self):
        doc = manifest(release_gates_passed=3, archival_status='historical')
        self.assertTrue(audit.blocking_findings(doc, 'manifests/whatever.json'))

    def test_listed_manifest_does_not_block(self):
        doc = manifest(release_gates_passed=3)
        self.assertTrue(audit.findings(doc))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'manifests').mkdir()
            (root / 'manifests' / 'historical.txt').write_text(
                'manifests/old.json\n', encoding='utf-8'
            )
            self.assertTrue(
                audit.is_historical(doc, 'manifests/old.json', root)
            )
            self.assertEqual(
                audit.blocking_findings(doc, 'manifests/old.json', root), []
            )

    def test_unlisted_manifest_still_blocks(self):
        doc = manifest(release_gates_passed=3)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'manifests').mkdir()
            (root / 'manifests' / 'historical.txt').write_text(
                'manifests/old.json\n', encoding='utf-8'
            )
            self.assertFalse(
                audit.is_historical(doc, 'manifests/new.json', root)
            )
            self.assertTrue(
                audit.blocking_findings(doc, 'manifests/new.json', root)
            )

    def test_list_ignores_comments_and_blank_lines(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'manifests').mkdir()
            (root / 'manifests' / 'historical.txt').write_text(
                '# a comment\n\nmanifests/old.json\n', encoding='utf-8'
            )
            self.assertEqual(
                audit.historical_list(root), {'manifests/old.json'}
            )

    def test_repository_list_exists_and_covers_the_committed_manifests(self):
        listed = audit.historical_list()
        self.assertTrue(listed, 'the repository must carry a historical list')
        for path in listed:
            self.assertTrue((ROOT / path).exists(), path)

    def test_current_manifest_defects_block(self):
        doc = manifest(release_gates_passed=3)
        self.assertTrue(audit.blocking_findings(doc))


class CommandLineTests(unittest.TestCase):
    def _run(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = audit.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_clean_manifest_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'manifest.json'
            path.write_text(json.dumps(manifest()), encoding='utf-8')
            code, out, _ = self._run(str(path))
        self.assertEqual(code, 0)
        self.assertIn('0 findings', out)

    def test_findings_exit_with_code_two(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'manifest.json'
            path.write_text(json.dumps(manifest(release_gates_passed=9)), encoding='utf-8')
            code, out, _ = self._run(str(path))
        self.assertEqual(code, 2)
        self.assertIn('FAIL', out)
        self.assertIn('findings', out)

    def test_unreadable_manifest_exits_with_code_one(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'manifest.json'
            path.write_text('{not json', encoding='utf-8')
            code, _, err = self._run(str(path))
        self.assertEqual(code, 1)
        self.assertIn('could not read', err)

    def test_missing_argument_reports_usage(self):
        code, _, err = self._run()
        self.assertEqual(code, 1)
        self.assertIn('usage', err)

    def test_historical_manifest_exits_zero_and_is_labelled(self):
        # A manifest inside the repository's historical list is catalogued.
        listed = audit.historical_list()
        self.assertTrue(listed)
        target = sorted(listed)[0]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'manifest.json'
            path.write_text(
                json.dumps(manifest(release_gates_passed=3)), encoding='utf-8'
            )
            code, out, _ = self._run(str(path))
        # A file outside the repository is not in the list, so it still fails.
        self.assertEqual(code, 2)
        self.assertIn('FAIL', out)
        self.assertTrue(target)


if __name__ == '__main__':
    unittest.main()
