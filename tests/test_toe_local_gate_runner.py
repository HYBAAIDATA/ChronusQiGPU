"""Negative controls for local gate evidence; no production promotion."""
import subprocess

import pytest

from scripts import run_toe_production_gates as runner


@pytest.mark.parametrize('body,expected', [
    ('<testsuites><testsuite><testcase name="ok"/></testsuite></testsuites>', True),
    ('<testsuites/>', False),
    ('<testsuite><testcase><failure/></testcase></testsuite>', False),
    ('<testsuite><testcase><error/></testcase></testsuite>', False),
    ('<testsuite><testcase><skipped/></testcase></testsuite>', False),
    ('<testsuite><error/><testcase/></testsuite>', False),
    ('not xml', False),
])
def test_junit_fail_closed(tmp_path, body, expected):
    path = tmp_path / 'suite.xml'
    path.write_text(body)
    assert runner.junit_passes(path) is expected


def test_missing_junit_fails(tmp_path):
    assert not runner.junit_passes(tmp_path / 'absent.xml')


def test_baseline_includes_untracked(monkeypatch):
    calls = []

    def output(args, **kwargs):
        calls.append(args)
        return 'a' * 40 if 'rev-parse' in args else '?? untracked_source.py\n'

    monkeypatch.setattr(subprocess, 'check_output', output)
    assert runner.baseline() == ('a' * 40, False)
    assert '--untracked-files=all' in calls[-1]


def test_export_cannot_be_clean_checkout(monkeypatch):
    def unavailable(*args, **kwargs):
        raise subprocess.CalledProcessError(128, 'git')

    monkeypatch.setattr(subprocess, 'check_output', unavailable)
    assert runner.baseline() == (None, False)
