"""Runner refusal tests; not product qualification."""
import importlib.util
from pathlib import Path
import json
import pytest

@pytest.fixture
def mod():
    path=Path(__file__).resolve().parents[1]/'scripts/run_closeout_qualification.py'
    spec=importlib.util.spec_from_file_location('closeout_runner',path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_partial_non_git_snapshot_is_blocked(tmp_path,mod):
    root=tmp_path/'source'; root.mkdir(); out=tmp_path/'evidence'; temp=tmp_path/'temp'
    assert mod.main(['--root',str(root),'--evidence-dir',str(out),'--temp-root',str(temp)])==2
    assert json.loads((out/'qualification.json').read_text())['production_ready'] is False

def test_artifacts_inside_source_are_refused_without_writing(tmp_path,mod):
    assert mod.main(['--root',str(tmp_path),'--evidence-dir',str(tmp_path/'out'),'--temp-root',str(tmp_path.parent/'safe-temp')])==2
    assert not (tmp_path/'out').exists()

def test_missing_or_skipped_junit_is_not_green(tmp_path,mod):
    p=tmp_path/'junit.xml'; assert mod.junit_outcome(p,0,'')['state']=='FAIL'
    p.write_text('<testsuites><testsuite tests="2" skipped="1" errors="0" failures="0"/></testsuites>')
    assert mod.junit_outcome(p,0,'')['state']=='FAIL'

def test_arena_exact_count_and_xpass_require_review(tmp_path,mod):
    p=tmp_path/'junit.xml'; p.write_text('<testsuites><testsuite tests="99" skipped="0" errors="0" failures="0"/></testsuites>')
    assert mod.junit_outcome(p,0,'',arena=True)['state']=='FAIL'
    p.write_text('<testsuites><testsuite tests="100" skipped="0" errors="0" failures="0"/></testsuites>')
    assert mod.junit_outcome(p,0,'',arena=True)['state']=='PASS'
    assert mod.junit_outcome(p,0,'1 xpassed',arena=True)['state']=='FAIL'

@pytest.mark.parametrize('timeout',['0','-1','nan','inf'])
def test_invalid_timeout_refused(tmp_path,mod,timeout):
    assert mod.main(['--root',str(tmp_path/'source'),'--evidence-dir',str(tmp_path/'out'),
                     '--temp-root',str(tmp_path/'tmp'),'--timeout',timeout])==2
    assert not (tmp_path/'out').exists()

def test_prior_artifacts_are_not_reused_or_overwritten(tmp_path,mod):
    out=tmp_path/'out'; out.mkdir(); marker=out/'qualification.json'; marker.write_text('old evidence')
    assert mod.main(['--root',str(tmp_path/'source'),'--evidence-dir',str(out),
                     '--temp-root',str(tmp_path/'tmp')])==2
    assert marker.read_text()=='old evidence'
