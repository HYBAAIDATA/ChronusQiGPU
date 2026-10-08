"""Clean-registry execution receipts; metadata existence never qualifies a release.

Run after OIDC TestPyPI upload, then consume these receipts before uploading the
same archives to PyPI. This verifier is release tooling, not platform certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from verify_release_candidates import KELLOGG_CHECK, TURING_CHECK

PRODUCTS = {
    "kellogg-tensor": (KELLOGG_CHECK, {"3.11", "3.12", "3.13", "3.14"}),
    "turing-universal-quantum-computer": (TURING_CHECK, {"3.11", "3.12", "3.13"}),
}
REGISTRIES = {
    "testpypi": ("https://test.pypi.org", "test-files.pythonhosted.org"),
    "pypi": ("https://pypi.org", "files.pythonhosted.org"),
}
MANDATORY = ("clean_install", "import", "entry_point", "smoke", "restart_replay")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def qualification(path, sha, product):
    row = load(path)
    require(re.fullmatch(r"[0-9a-f]{40}", sha), "RC SHA must be full lowercase commit")
    require(row["git_sha"] == sha and row["product"] == product, "wrong candidate identity")
    require(row["version"] == "1.0.0", "first-public version must be 1.0.0")
    require(row.get("publishable") is True and row.get("published") is False, "unqualified candidate")
    mandatory = {"cross_version_verified", "tests_passed", "benchmarks_completed", "wheel_built"}
    mandatory |= ({"standalone_boundary_verified", "registry_verified", "sdist_verified",
                   "attestation_verified", "certificate_verification_passed", "wheel_clean_install_verified"}
                  if product == "kellogg-tensor" else
                  {"package_boundary_verified", "backend_admission_verified", "certificate_verified",
                   "witness_verified", "fresh_process_recovery_verified", "semantic_replay_verified",
                   "durable_custody_verified", "production_composition_verified", "sdist_verified"})
    require(all(row.get(key) is True for key in mandatory), "missing/failed mandatory qualification")
    if product == "kellogg-tensor":
        tests = row["tests"]
        require(tests["git_sha"] == sha and tests["passed"] > 0 and tests["returncode"] == 0
                and all(tests[k] == 0 for k in ("failed", "errors", "skipped")), "invalid source test evidence")
    else:
        require(row.get("formal_verification") == "PASS", "missing formal gate")
    for key, value in row.items():
        if key.endswith(("_verified", "_passed", "_valid", "_completed", "_built")):
            if key != "testpypi_verified":
                require(value is True, f"qualification gate failed: {key}")
    for kind in ("wheel", "sdist"):
        item = row[kind]
        require(Path(item["file"]).name == item["file"], "unsafe artifact filename")
        require(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]), "invalid archive digest")
    return row


def validate_receipts(paths, verdict, registry, sha):
    product = verdict["product"]
    expected = PRODUCTS[product][1]
    seen = set()
    rows = []
    for path in paths:
        row = load(path)
        signed = dict(row)
        actual = signed.pop("receipt_digest")
        require(digest(signed) == actual, "tampered registry receipt")
        require(row["source_commit"] == sha and row["product"] == product, "stale/wrong receipt")
        require(row["registry"] == registry and row["version"] == "1.0.0", "wrong registry/version")
        require(row["status"] == "PASS", "failed registry receipt")
        require(row["artifacts"] == {k: verdict[k] for k in ("wheel", "sdist")}, "artifact substitution")
        require(all(row["checks"].get(k) is True for k in MANDATORY), "missing executed registry check")
        require(row["ci_run_url"] == os.environ["CI_RUN_URL"], "different workflow run")
        for filename, key in (("commands.log", "commands_sha256"),
                              ("custody.json", "custody_sha256"),
                              ("install-report.json", "install_report_sha256")):
            require(file_digest(Path(path).parent / filename) == row[key], "missing/tampered executed log")
        version = ".".join(row["python"].split(".")[:2])
        require(version not in seen, "duplicate interpreter receipt")
        seen.add(version)
        rows.append(row)
    require(seen == expected, f"incomplete registry matrix: {seen} != {expected}")
    return rows


TURING_REPLAY = r'''
import json
from pathlib import Path
from turing_universal_quantum_computer.backends import Program, execute, execute_certified
from turing_universal_quantum_computer.certificates import (
    VQCComputationCertificate, RunWitness, verify_witness, replay_computation_certificate,
)
p = Program(2).then("h", 0).then("cx", 0, 1)
path = Path("custody.json")
if not path.exists():
    run = execute_certified(p)
    assert run.certificate.verify_integrity()
    assert verify_witness(run.witness)
    path.write_text(json.dumps({"certificate": run.certificate.to_dict(), "witness": run.witness.to_dict()}))
else:
    row = json.loads(path.read_text())
    cert = VQCComputationCertificate.from_dict(row["certificate"])
    witness = RunWitness.from_dict(row["witness"])
    assert cert.verify_integrity() and verify_witness(witness)
    replay_computation_certificate(p, cert, execute)
print("SERIALIZED_RECEIPT_REPLAY_PASS")
'''
KELLOGG_CUSTODY = r'''
import json
from pathlib import Path
from kellogg.custody import ResidentCustody, CustodyError
c = ResidentCustody()
payload = b"kellogg-standalone-release-custody"
ref = c.put(payload)
assert c.get(ref) == payload
c.release(ref)
try:
    c.get(ref)
except CustodyError:
    pass
else:
    raise RuntimeError("released resident payload was available")
assert c.regenerate(ref, payload) == ref and c.get(ref) == payload
path = Path("custody.json")
record = {"ref": ref, "provider": "kellogg.resident", "durable_platform_custody": "OUT_OF_SCOPE"}
if path.exists():
    assert json.loads(path.read_text()) == record
else:
    path.write_text(json.dumps(record))
print("RESIDENT_CUSTODY_REPLAY_PASS")
'''


def verify(args):
    verdict = qualification(args.verdict, args.sha, args.product)
    root = Path(args.out).resolve()
    root.mkdir(parents=True, exist_ok=True)
    logs = root / "commands.log"
    def run(command, cwd):
        with logs.open("a") as stream:
            stream.write(json.dumps({"command": command, "cwd": str(cwd)}) + "\n")
            stream.flush()
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith("PIP_") and k not in ("PYTHONPATH", "PYTHONHOME")}
            env["PIP_CONFIG_FILE"] = os.devnull
            proc = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)
        require(proc.returncode == 0, f"command failed ({proc.returncode}); see {logs}")
    host, file_host = REGISTRIES[args.registry]
    with urlopen(f"{host}/pypi/{args.product}/1.0.0/json", timeout=30) as response:
        metadata = json.load(response)
    files = {item["filename"]: item for item in metadata["urls"]}
    for kind in ("wheel", "sdist"):
        item = verdict[kind]
        archive = files[item["file"]]
        require(archive["digests"]["sha256"] == item["sha256"], "registry archive differs")
        require(urlparse(archive["url"]).hostname == file_host, "archive not on registry file host")
        with urlopen(archive["url"], timeout=60) as response:
            data = response.read()
        require(hashlib.sha256(data).hexdigest() == item["sha256"], "downloaded registry archive differs")
        (root / item["file"]).write_bytes(data)
    with tempfile.TemporaryDirectory(prefix="registry-clean-") as tmp:
        work = Path(tmp)
        run([sys.executable, "-m", "venv", str(work / "env")], work)
        py = str(work / "env" / "bin" / "python")
        run([py, "-m", "pip", "install", "--index-url", "https://pypi.org/simple/",
             "numpy>=1.26,<3", "sympy>=1.12,<2", "scipy>=1.11", "networkx>=3.0"], work)
        if args.product != "kellogg-tensor":
            dependency = load(args.dependency_manifest)
            require(dependency["git_sha"] == args.sha, "stale Kellogg build dependency")
            with urlopen("https://pypi.org/pypi/kellogg-tensor/1.0.0/json", timeout=30) as response:
                published_dependency = json.load(response)
            matching = [f for f in published_dependency["urls"] if f["filename"] == dependency["wheel"]["file"]]
            require(len(matching) == 1 and matching[0]["digests"]["sha256"] == dependency["wheel"]["sha256"],
                    "PyPI Kellogg is not this RC's qualified dependency")
            dependency_report = work / "dependency-install.json"
            run([py, "-m", "pip", "install", "--no-deps", "--only-binary=:all:",
                 "--no-cache-dir", "--index-url", "https://pypi.org/simple/",
                 "--report", str(dependency_report), "kellogg-tensor==1.0.0"], work)
            installed_dependency = load(dependency_report)["install"]
            require(len(installed_dependency) == 1 and
                    installed_dependency[0]["download_info"]["archive_info"]["hashes"]["sha256"] == dependency["wheel"]["sha256"],
                    "installed Kellogg is not the published qualified dependency")
            (root / "dependency-install-report.json").write_text(json.dumps(installed_dependency, indent=2))
        report = work / "install.json"
        run([py, "-m", "pip", "install", "--no-deps", "--only-binary=:all:",
             "--no-cache-dir", "--index-url", host + "/simple/", "--report", str(report),
             args.product + "==1.0.0"], work)
        installation = load(report)
        installed = [r for r in installation["install"]
                     if r["metadata"]["name"].lower().replace("_", "-") == args.product]
        require(len(installed) == 1 and installed[0]["metadata"]["version"] == "1.0.0", "missing/wrong registry-installed target")
        info = installed[0]["download_info"]
        require(urlparse(info["url"]).hostname == file_host, "target not downloaded from requested registry")
        require(info["archive_info"]["hashes"]["sha256"] == verdict["wheel"]["sha256"], "installed wheel differs")
        (root / "install-report.json").write_text(json.dumps(installation, indent=2))
        check = PRODUCTS[args.product][0]
        for iteration in range(2):
            code = check + '\nassert reg["ok"]\nassert not locals().get("failed", {})\nassert not locals().get("siblings", [])\nassert kellogg.__version__ == "1.0.0"\nassert not any(s in sys.modules for s in ("aethel", "chronus", "turing_core", "lucas", "toe", "mining", "Intelligence"))\n' + f'\nfrom pathlib import Path\nPath("check-{iteration}.json").write_text(json.dumps(locals().get("bench", {{}})))\n'
            run([py, "-I", "-c", code], work)
        # Cross-version digest is qualified by the workflow matrix, not by one interpreter.
        # Every other installed correctness/meta benchmark must execute and pass.
        for i in range(2):
            results = load(work / f"check-{i}.json")
            executed = {k: v for k, v in results.items() if k != "cross_version_digest"}
            require(executed and all(v is True for v in executed.values()), "installed benchmark incomplete/failed")
            require(results.get("cross_version_digest") is not False, "cross-version smoke contradicted matrix")
        require(load(work / "check-0.json") == load(work / "check-1.json"), "restart fixture differs")
        if args.product != "kellogg-tensor":
            cli = str(work / "env" / "bin" / "turing-vqc")
            run([cli, "--help"], work)
            (work / "smoke.vqc").write_text("init 2\nh 0\ncx 0 1\nprob\ncertify\n")
            before = logs.stat().st_size
            run([cli, "--quiet", "--script", str(work / "smoke.vqc")], work)
            output = logs.read_text()[before:]
            require("REFUSED" not in output and "certificate verified: True" in output,
                    "CLI did not certify the minimal operation")
        replay = TURING_REPLAY if args.product != "kellogg-tensor" else KELLOGG_CUSTODY
        for _ in range(2):
            run([py, "-I", "-c", replay], work)
        (root / "custody.json").write_bytes((work / "custody.json").read_bytes())
    receipt = {
        "schema": "hyba.registry-execution.v1", "product": args.product, "version": "1.0.0",
        "source_commit": args.sha, "registry": args.registry, "registry_url": host + "/project/" + args.product + "/1.0.0/",
        "python": platform.python_version(), "ci_run_url": os.environ["CI_RUN_URL"],
        "status": "PASS", "checks": {k: True for k in MANDATORY},
        "entry_point_scope": "turing-vqc" if args.product != "kellogg-tensor" else "library-only; isolated Python execution",
        "artifacts": {k: verdict[k] for k in ("wheel", "sdist")},
        "install_report_sha256": file_digest(root / "install-report.json"),
        "custody_sha256": file_digest(root / "custody.json"), "commands_sha256": file_digest(logs),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Standalone software qualification only; not iGPU or whole-platform certification"],
    }
    receipt["receipt_digest"] = digest(receipt)
    (root / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--product", choices=PRODUCTS, required=True)
    p.add_argument("--registry", choices=REGISTRIES, required=True)
    p.add_argument("--sha", required=True)
    p.add_argument("--verdict", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--dependency-manifest")
    p.add_argument("--receipts", help="Validate an executed matrix instead of installing")
    args = p.parse_args()
    if args.receipts:
        row = qualification(args.verdict, args.sha, args.product)
        rows = validate_receipts(Path(args.receipts).rglob("receipt.json"), row, args.registry, args.sha)
        row["testpypi_verified"] = args.registry == "testpypi" or row.get("testpypi_verified") is True
        row["published"] = args.registry == "pypi"
        row["registry_receipts"] = rows
        row["ci_run_url"] = os.environ["CI_RUN_URL"]
        Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True))
    else:
        verify(args)


if __name__ == "__main__":
    main()
