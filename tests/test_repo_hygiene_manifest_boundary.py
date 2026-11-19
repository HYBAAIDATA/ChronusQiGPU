"""Regression of the policy / qualification manifest boundary."""

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


def test_sensitive_content_rules_cover_json_secret_and_valuation():
    import json
    import re
    policy = json.loads((ROOT / "manifests/public_root_allowlist.json").read_text())
    rules = {rule["id"]: re.compile(rule["pattern"]) for rule in policy["forbidden_content_regexes"]}
    # Construct deliberately synthetic strings rather than hardcode credentials.
    jwt = "CHRONUS_" + "JWT_SECRET"
    assert rules["HARDCODED_CHRONUS_JWT_SECRET"].search(f'"{jwt}": "' + "A" * 24 + '"')
    prefix = "confidential" + " valuation"
    assert rules["CONFIDENTIAL_VALUATION_VALUE"].search(prefix + ": " + "$" + "123")
    assert not rules["CONFIDENTIAL_VALUATION_VALUE"].search("valuation methodology")


def test_capture_command_preserves_stream_bytes_and_exit_code(tmp_path):
    out = b"stdout\\x00\\xff\\n"
    err = b"stderr\\r\\n"
    command = [
        sys.executable, str(ROOT / "scripts/ci/capture_command.py"), str(tmp_path), "check", "--",
        sys.executable, "-c",
        f"import sys; sys.stdout.buffer.write({out!r}); sys.stderr.buffer.write({err!r}); sys.exit(7)",
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    assert result.returncode == 7
    assert result.stdout == out
    assert result.stderr == err
    assert (tmp_path / "check.stdout").read_bytes() == out
    assert (tmp_path / "check.stderr").read_bytes() == err
    assert (tmp_path / "check.exit_code").read_text() == "7\n"
