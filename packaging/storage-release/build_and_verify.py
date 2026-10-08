"""Stage unchanged canonical code and verify installed storage publication candidates.

This preparation runner does NOT publish, self-award production readiness, import
from editable source, or replace missing subsystem integrations with fake objects.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRODUCTS = {"theseus": ("hyba-theseus", "aethel"), "ovid": ("hyba-ovid", "hyba_db")}
SECRET_PATTERNS = [re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
                   re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
                   re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
                   re.compile(rb"pypi-AgEI[A-Za-z0-9_-]{20,}")]


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_sha():
    return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()


def source_inventory(root, package):
    files = {}
    imports = []
    for path in sorted((root / package).rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
            continue
        require(not path.is_symlink(), "canonical source cannot be a symlink")
        files[path.relative_to(root).as_posix()] = sha(path)
        if path.suffix == ".py":
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend({"file":path.relative_to(root).as_posix(), "line":node.lineno,
                                    "module":item.name} for item in node.names)
                elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                    imports.append({"file":path.relative_to(root).as_posix(), "line":node.lineno, "module":node.module})
    require(files and package + "/__init__.py" in files, "missing canonical package source")
    return {"owned_package":package, "files_sha256":files, "absolute_imports":imports,
            "import_review":"static inventory; installed imports are authoritative; external integrations not certified"}


def inspect_wheel(wheel, inventory):
    package = inventory["owned_package"]
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
        top = {name.split("/",1)[0] for name in names if "/" in name}
        require(all(p == package or ".dist-info" in p for p in top), "foreign product or duplicate namespace bundled")
        for name, expected in inventory["files_sha256"].items():
            require(name in names and hashlib.sha256(z.read(name)).hexdigest() == expected,
                    "canonical source omitted/changed: " + name)
        for name in names:
            require(not name.startswith("/") and ".." not in Path(name).parts, "unsafe wheel member path")
            if name.endswith("/"):
                continue
            data = z.read(name)
            require(not any(pattern.search(data) for pattern in SECRET_PATTERNS), "secret-shaped payload in archive")
    return {"source_identity":"PASS", "nonoverlapping_file_ownership":"PASS", "secret_pattern_scan":"PASS"}


def junit_counts(path):
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    counts = {key:sum(int(row.attrib.get(key,0)) for row in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    require(counts["tests"] > 0 and all(counts[k] == 0 for k in ("failures","errors","skipped")),
            "required source suite must execute with zero failures/errors/skips")
    return counts


def required_tests(product):
    patterns = (("test_aethel_*.py","test_theseus_*.py","test_enterprise_*.py","test_entangled_custody_*.py",
                 "test_fold_store.py","test_chronus_theseus_ovid_triad.py") if product == "theseus" else
                ("test_ovid_*.py","test_hyba_ontology_store.py","test_m3_file_registry.py",
                 "test_m3_storage_voyage.py","test_storage_database_ontology_v3.py"))
    selected = sorted({path for pattern in patterns for path in (REPO / "tests").glob(pattern)})
    for pattern in patterns:
        require(list((REPO / "tests").glob(pattern)), "mandatory test pattern absent: " + pattern)
    return selected


def run_source_tests(product, out):
    log = out / "source-tests.log"
    junit = out / "source-tests.xml"
    junit.unlink(missing_ok=True)
    command = [sys.executable,"-m","pytest","-q",*[str(p) for p in required_tests(product)],"--junitxml="+str(junit)]
    with log.open("w") as stream:
        result=subprocess.run(command,cwd=REPO,stdout=stream,stderr=subprocess.STDOUT)
    require(result.returncode == 0, "source suite failed; see source-tests.log")
    return {"source_commit":git_sha(),"command":command,"counts":junit_counts(junit),"log_sha256":sha(log),
            "scope":"source product/boundary tests; not a replacement for installed composition"}


INSTALL_CHECK = r'''
import importlib, importlib.metadata, json, hashlib, sys
from pathlib import Path
product, package, manifest = sys.argv[1:]
row=json.loads(Path(manifest).read_text())
assert importlib.metadata.version(product) == "1.0.0"
owner=importlib.import_module(package)
assert "site-packages" in str(owner.__file__)
site=Path(owner.__file__).parent.parent
for name, expected in row["files_sha256"].items():
    assert hashlib.sha256((site/name).read_bytes()).hexdigest() == expected, name
    if name.endswith(".py"):
        module=name[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module=module[:-9]
        imported=importlib.import_module(module)
        assert "site-packages" in str(imported.__file__), module
print("INSTALLED_CANONICAL_SOURCE_IDENTITY_PASS")
'''


def build(product, source_tests):
    name, package = PRODUCTS[product]
    out = REPO / "packaging" / product / "dist"
    out.mkdir(parents=True,exist_ok=True)
    for pattern in ("*.whl","*.tar.gz","artifact-verdict.json"):
        for p in out.glob(pattern):p.unlink()
    inventory = source_inventory(REPO, package)
    (out / "source-inventory.json").write_text(json.dumps(inventory,indent=2))
    record = {"product":name,"version":"1.0.0","source_commit":git_sha(),"status":"FAIL",
              "qualification_scope":"standalone software preparation", "production_ready":False,
              "published":False,"identity_approved":False,"source_suites":"NOT_RUN"}
    def run(command,cwd,expected=0):
        env={k:v for k,v in os.environ.items() if k not in ("PYTHONPATH","PYTHONHOME") and not k.startswith("PIP_")}
        env["PIP_CONFIG_FILE"]=os.devnull
        env["SOURCE_DATE_EPOCH"]=subprocess.check_output(["git","-C",str(REPO),"show","-s","--format=%ct","HEAD"],text=True).strip()
        with (out / "commands.log").open("a") as stream:
            stream.write(json.dumps({"command":command,"cwd":str(cwd)})+"\n");stream.flush()
            result=subprocess.run(command,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT)
        require((result.returncode==0) if expected==0 else (result.returncode!=0), "command outcome violated verification contract")
    try:
        with tempfile.TemporaryDirectory(prefix="storage-package-") as directory:
            tmp=Path(directory);stage=tmp / "stage";stage.mkdir();(stage / "src").mkdir()
            shutil.copytree(REPO / package,stage / "src" / package,
                            ignore=shutil.ignore_patterns("__pycache__","*.pyc","*.pyo"))
            for file in ("pyproject.toml","README.md"):shutil.copy2(REPO / "packaging" / product / file,stage / file)
            shutil.copy2(REPO / "LICENSE",stage / "LICENSE")
            run([sys.executable,"-m","build","--outdir",str(out),str(stage)],tmp)
            wheel=next(out.glob("*.whl"));sdist=next(out.glob("*.tar.gz"))
            run([sys.executable,"-m","twine","check",str(wheel),str(sdist)],tmp)
            record["archive_inspection"]=inspect_wheel(wheel,inventory)
            record["wheel"]={"file":wheel.name,"sha256":sha(wheel)}
            record["sdist"]={"file":sdist.name,"sha256":sha(sdist)}
            for kind,archive in (("wheel",wheel),("sdist",sdist)):
                work=tmp / kind;work.mkdir()
                run([sys.executable,"-m","venv",str(work / "env")],work)
                py=str(work / "env" / ("Scripts/python.exe" if os.name=="nt" else "bin/python"))
                dependency=[]
                if product=="ovid":
                    dep=REPO / "packaging" / "theseus" / "dist"
                    dep_record=json.loads((dep / "artifact-verdict.json").read_text())
                    require(dep_record["source_commit"] == git_sha() and dep_record["status"]=="PASS", "stale/unverified THESEUS dependency")
                    dep_wheel=dep / dep_record["wheel"]["file"]
                    require(sha(dep_wheel)==dep_record["wheel"]["sha256"], "THESEUS dependency changed")
                    dependency=[str(dep_wheel)]
                run([py,"-m","pip","install","--index-url","https://pypi.org/simple/",*dependency,str(archive)],work)
                run([py,"-I","-c",INSTALL_CHECK,name,package,str(out / "source-inventory.json")],work)
                cli=(str(work / "env" / ("Scripts" if os.name=="nt" else "bin") /
                     ("hyba-theseus" if product=="theseus" else "pythia-storage-db-gate")))
                run([cli,"--help"],work)
                if product=="ovid":
                    run([cli,"--db","absent.db","--root","absent-files","--tenant","unknown",
                         "--custody-root","absent-custody"],work,expected=1)
                voyage=work / "voyage.py";shutil.copy2(HERE / "voyage.py",voyage)
                for keyfile in ("custody.key","integrity.key"):
                    key=work / keyfile;key.write_bytes(secrets.token_bytes(32));key.chmod(0o600)
                for phase in ("write","restart","negative"):
                    run([py,"-I",str(voyage),"--product",product,"--phase",phase,"--root",str(work)],work)
            if source_tests:record["source_suites"]=run_source_tests(product,out)
            record["status"]="PASS"
            record["commands_sha256"]=sha(out / "commands.log")
            record["limitations"]=["Package smoke is not whole-platform qualification",
                "Registry installation/publication not executed by this runner",
                "Producer semantic revalidation is not self-awarded",
                "External hardware/cloud/security integrations not certified"]
    except Exception as exc:
        record["error"]=f"{type(exc).__name__}: {exc}"
        raise
    finally:
        (out / "artifact-verdict.json").write_text(json.dumps(record,indent=2,sort_keys=True))
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--product",choices=(*PRODUCTS,"all"),required=True)
    p.add_argument("--source-tests",action="store_true")
    args=p.parse_args()
    for product in PRODUCTS if args.product=="all" else (args.product,):build(product,args.source_tests)

if __name__=="__main__":
    main()
