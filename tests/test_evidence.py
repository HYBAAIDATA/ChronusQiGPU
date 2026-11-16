import json
from scripts.ci.build_evidence import build

def test_skipped_test_is_unqualified(tmp_path):
    junit=tmp_path/"junit.xml"
    junit.write_text('<testsuite><testcase name="a"/><testcase name="b"><skipped/></testcase></testsuite>')
    out=tmp_path/"evidence.json"
    assert build(junit,out)==1
    assert json.loads(out.read_text())["status"]=="UNQUALIFIED"

def test_failed_test_is_unqualified(tmp_path):
    junit=tmp_path/"junit.xml"
    junit.write_text('<testsuite><testcase name="a"><failure/></testcase></testsuite>')
    assert build(junit,tmp_path/"evidence.json")==1

def test_no_tests_fails_closed(tmp_path):
    junit=tmp_path/"junit.xml"
    junit.write_text("<testsuite/>")
    import pytest
    with pytest.raises(ValueError):
        build(junit,tmp_path/"evidence.json")
