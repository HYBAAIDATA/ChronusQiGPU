"""Build persistent local wheelhouse for euclid-engine dependency closure.
Copies kellogg/toe/aethel from this checkout, builds wheels into
packaging/wheelhouse/, alongside the already-built euclid wheel.
"""
from pathlib import Path
import shutil, subprocess, sys
REPO = Path(__file__).resolve().parent.parent
HOUSE = REPO / "packaging" / "wheelhouse"
HOUSE.mkdir(exist_ok=True)
def sh(c, cwd): print("$", " ".join(map(str,c)), flush=True); subprocess.run(list(map(str,c)), check=True, cwd=str(cwd))
import tempfile
with tempfile.TemporaryDirectory(prefix="wheelhouse-") as tmp:
    tmp = Path(tmp)
    for product, package, src_layout in (("kellogg-tensor","kellogg",False),("toe","toe",False),("theseus","aethel",True)):
        proj = tmp / product; proj.mkdir()
        dest = proj / "src" if src_layout else proj
        dest.mkdir(exist_ok=True)
        shutil.copytree(REPO/package, dest/package, ignore=shutil.ignore_patterns("tests","__pycache__","*.pyc","var"))
        for n in ("pyproject.toml","README.md"):
            shutil.copy2(REPO/"packaging"/product/n, proj/n)
        shutil.copy2(REPO/"LICENSE", proj/"LICENSE")
        sh([sys.executable,"-m","build","--wheel","--outdir",HOUSE,proj], cwd=tmp)
    # also stage euclid wheel
    for w in (REPO/"packaging"/"euclid-engine"/"dist").glob("hyba_euclid_intelligence-*.whl"):
        shutil.copy2(w, HOUSE/w.name)
print("wheelhouse:", sorted(p.name for p in HOUSE.glob("*.whl")))
