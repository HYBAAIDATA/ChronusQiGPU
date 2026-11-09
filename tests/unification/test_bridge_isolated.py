"""Standalone bridge tests; network check accesses primary reference pages."""
import subprocess, sys
from pathlib import Path
import pytest
from hypothesis import given, settings, strategies as st
from hyba.unification.bridge import REFERENCES, fetch_reference, render, validate

class TestInvariant:
    def test_five_cited_fronts(self):
        assert len(REFERENCES)==5
        assert len({r[0] for r in REFERENCES})==5
        for key,title,url,claim in REFERENCES:
            assert f'[{key}]({url})' in render() and claim in render()

class TestProperty:
    @settings(max_examples=100,derandomize=True,deadline=None)
    @given(st.lists(st.sampled_from(REFERENCES),min_size=1,max_size=5,unique_by=lambda r:r[0]))
    def test_every_selected_claim_has_its_key(self, refs):
        text=render(tuple(refs))
        for key,title,url,claim in refs:
            assert claim in text and f'[{key}]({url})' in text

class TestAdversarial:
    def test_duplicate_invalid_key_and_url(self):
        with pytest.raises(ValueError): validate((REFERENCES[0],REFERENCES[0]))
        with pytest.raises(ValueError): validate((('x','title','http://example.com','claim'),))
        with pytest.raises(ValueError): fetch_reference('https://example.com')

class TestEdge:
    def test_empty_malformed_missing_text(self):
        with pytest.raises(ValueError): validate(())
        with pytest.raises(ValueError): validate((('x','y'),))
        with pytest.raises(ValueError): validate((('x','title','https://example.com',''),))

class TestUnit:
    @pytest.mark.parametrize('reference',REFERENCES,ids=[r[0] for r in REFERENCES])
    def test_primary_reference_fetches(self,reference):
        status,url=fetch_reference(reference[0]); assert 200 <= status < 400; assert url.startswith('https://')

class TestIntegration:
    def test_render_and_validate(self):
        assert validate(REFERENCES) and 'not an exhaustive citation-network review' in render()

class TestEndToEnd:
    def test_generated_bridge_file(self,tmp_path):
        output=tmp_path/'bridge.md'
        subprocess.run([sys.executable,'-m','hyba.unification.bridge','--output',str(output)],check=True)
        assert output.read_text(encoding='utf-8')==render()
