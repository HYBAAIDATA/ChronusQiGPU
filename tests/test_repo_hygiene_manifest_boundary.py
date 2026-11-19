"""Regression of the policy / qualification manifest boundary."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.real
ROOT = Path(__file__).resolve().parents[1]


def test_policy_manifest_is_validated_without_qualification_claims():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci/audit_manifests.py")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert "--- manifests/public_root_allowlist.json: 0 blocking finding(s)" in result.stdout
    assert "validated repository hygiene policy (not qualification evidence)" in result.stdout


@pytest.mark.parametrize("mutation", ["wrong_schema", "empty_paths", "broken_regex", "empty_regexes"])
def test_invalid_policy_is_rejected(mutation):
    code = """
import json, sys
sys.path.insert(0, 'scripts/ci')
from check_repo_hygiene import validate_policy
doc = json.loads(open('manifests/public_root_allowlist.json').read())
mutation = sys.argv[1]
if mutation == 'wrong_schema':
    doc['schema_version'] = 'unknown'
elif mutation == 'empty_paths':
    doc['forbidden_path_globs'] = []
elif mutation == 'broken_regex':
    doc['forbidden_content_regexes'][0]['pattern'] = '('
elif mutation == 'empty_regexes':
    doc['forbidden_content_regexes'] = []
validate_policy(doc)
"""
    result = subprocess.run([sys.executable, "-c", code, mutation], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "ValueError:" in result.stderr or "re.PatternError:" in result.stderr or "re.error:" in result.stderr
