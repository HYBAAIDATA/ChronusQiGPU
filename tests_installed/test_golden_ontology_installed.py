"""Exercise both exact and explicitly numerical paths from the installed wheel."""
from pathlib import Path
import subprocess
import pytest
from tests_installed.conftest import clean_env

pytestmark=pytest.mark.real

def test_installed_golden_ontology(venv_bin,tmp_path):
    program="""
import golden_ontology
from golden_ontology.fold import fold_words,unfold_words
from golden_ontology.substrate import PV_REGISTRY
from chronus.math.golden_nature import phyllotaxis_exact
from chronus.research.golden_nature_reference import phyllotaxis_disk
assert unfold_words(fold_words([1,2],7,8),7,8)==[1,2]
assert all(family.certify() for family in PV_REGISTRY.values())
assert len(phyllotaxis_exact(8))==len(phyllotaxis_disk(8))==8
print(golden_ontology.__file__)
"""
    run=subprocess.run([str(venv_bin("python")),"-c",program],cwd=tmp_path,
                       env=clean_env(),capture_output=True,text=True,timeout=120)
    assert run.returncode==0,run.stderr
    path=Path(run.stdout.strip()).resolve()
    assert "site-packages" in path.parts
    assert not path.is_relative_to(Path(__file__).resolve().parents[1])
