"""Fail-closed five-lens acceptance; never grants production qualification."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HEX = re.compile(r"[0-9a-f]{64}\Z")
FINDINGS = "evidence/five_lens/findings.json"
ARTIFACTS = "evidence/five_lens/artifacts.json"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


def require(condition, why):
    if not condition:
        raise ValueError(why)


def tracked(path):
    require(isinstance(path, str) and not Path(path).is_absolute(), "invalid evidence path")
    p = ROOT / path
    require(p.resolve().is_relative_to(ROOT) and p.is_file(), f"missing evidence: {path}")
    require(bool(git("ls-files", "--", path).strip()), f"untracked evidence: {path}")
    return p


def evidence(record):
    p = tracked(record["path"])
    d = record["sha256"]
    require(isinstance(d, str) and HEX.fullmatch(d) and sha(p) == d,
            f"invalid or mismatched digest: {p}")
    return p


def tests(*nodes):
    with tempfile.TemporaryDirectory() as temp:
        xml = Path(temp) / "tests.xml"
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs",
                               *nodes, "-o", "addopts=", f"--junitxml={xml}"],
                              cwd=ROOT, capture_output=True, text=True)
        print(proc.stdout, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        cases = list(ET.parse(xml).getroot().iter("testcase")) if xml.exists() else []
        require(proc.returncode == 0 and cases and
                not any(c.find(tag) is not None for c in cases
                        for tag in ("failure", "error", "skipped")), "test failed, skipped or not run")


def item1():
    doc = tracked("docs/settlement/IPMVP_CONFORMITY.md").read_text()
    require(all(x in doc for x in ("Option C", "Option D", "measurement boundary",
                                   "reporting period", "baseline period", "adjustments")),
            "missing M&V contract")
    tests("tests/test_ipmvp.py")


def item2():
    require(len(tracked("docs/executive/CEO_STAKE_MEMO.md").read_text().splitlines()) <= 60,
            "memo exceeds page proxy")
    register = read("claims/register.json")
    for entry in register["claims"]:
        require(entry.get("evidence"), f"uncited claim: {entry['code']}")
        for record in entry["evidence"]:
            evidence(record)
    require((ROOT / "claims/archive_uncited").is_dir(), "uncited claims archive missing")
    for p in (ROOT / "claims").rglob("*.md"):
        if "archive_uncited" not in p.parts:
            require(any(sha(f) in p.read_text() for f in (ROOT / "evidence").rglob("*")
                        if f.is_file()), f"uncited claim file: {p}")
    tests("tests/test_claim_archive.py")
    require(not list(ROOT.glob("SOVEREIGN_*")) and not list(ROOT.glob("RELEASE_*")),
            "historical root claims remain")
    # Root sovereign and release claim review has to be independently accepted
    # against its original catalogue; presence alone is not closure.
    require(read(FINDINGS)["qualification"] == "HOLD", "qualification gate changed")


def item3():
    tracked("docs/analysts/TEI_INITIATION.md")
    for name in ("interview_guide.md", "counterfactual_disclosure.md",
                 "worksheet.json", "consents.json"):
        tracked("evidence/tei/inputs/" + name)
    worksheet = read("evidence/tei/inputs/worksheet.json")
    require(set(("benefits", "costs", "flexibility", "risk")) <= set(worksheet),
            "TEI pillars absent")
    for pillar in ("benefits", "costs", "flexibility", "risk"):
        row = worksheet[pillar]
        if row["value"] is not None:
            evidence(row["evidence"])
    consents = read("evidence/tei/inputs/consents.json")
    # Empty is an honest initiation artifact but not a completed study or finding.
    if consents["contacts"]:
        for person in consents["contacts"]:
            require(person["name"].strip(), "unnamed reference")
            evidence(person["consent"])


def item4():
    from scripts.benchmarks.fold_residency_campaign import run_trace
    from chronus.math.fold_ledger import OPS_FOLDED, OPS_BOUNDARY
    script = "scripts/benchmarks/fold_residency_campaign.py"
    dataset = "evidence/residency/inputs/traces.json"
    require("PRE-REGISTERED" in tracked(script).read_text().split('"""')[1],
            "baseline not pre-registered")
    tests("tests/test_fold_residency_campaign.py")
    runs = sorted((ROOT / "evidence/residency").glob("*/campaign.json"))
    require(bool(runs), "no committed campaign artifact")
    expected = read(dataset)["classes"]
    valid = False
    for path in runs:
        a = json.loads(tracked(str(path.relative_to(ROOT))).read_text())
        if a["script_sha256"] != sha(ROOT / script) or a["dataset_sha256"] != sha(ROOT / dataset):
            continue
        source = a["source_commit"]
        require(path.parent.name == source and re.fullmatch(r"[0-9a-f]{40}", source),
                "campaign source path mismatch")
        require(subprocess.run(["git", "merge-base", "--is-ancestor", source, "HEAD"],
                               cwd=ROOT).returncode == 0, "campaign source is not an ancestor")
        for rel in (script, dataset, "src/chronus/math/fold_ledger.py"):
            require(hashlib.sha256(git("show", f"{source}:{rel}")).hexdigest() == sha(ROOT / rel),
                    "campaign source drift")
        require(set(a["classes"]) == set(expected) == {"event_log", "object_store", "analytics"},
                "missing campaign class")
        require("measured, not benchmarked" in a["note"], "scope label missing")
        for name, spec in expected.items():
            row = a["classes"][name]
            candidate, baseline = run_trace(spec, 7), run_trace(spec, 0)
            require(row["candidate"] == candidate and row["baseline"] == baseline,
                    "campaign replay mismatch")
            counts = candidate["op_multiset"]
            require(set(counts) <= OPS_FOLDED | OPS_BOUNDARY, "unknown operation")
            fraction = Fraction(sum(n for op,n in counts.items() if op in OPS_FOLDED),
                                sum(counts.values()))
            require(row["residency"] == f"{fraction.numerator}/{fraction.denominator}",
                    "residency mismatch")
            require(row["prediction"] == spec["prediction"], "prediction drift")
            require(row["dataset_sha256"] == sha(ROOT / dataset), "dataset digest mismatch")
            for key in ("output", "observations", "op_multiset"):
                require(candidate[key] == baseline[key], "unequal work")
        valid = True
    require(valid, "no campaign for current script and data")


def item5():
    for path in ("docs/analysts/ANALYST_PACKAGE.md", "STATUS.md", "LICENSE", "CONTRIBUTING.md"):
        tracked(path)
    require((ROOT / "manifests/historical").is_dir(), "historical manifest directory missing")
    require(not (ROOT / "PRODUCTION_QUALIFIED.json").exists() and
            not list(ROOT.glob("RELEASE_DECISION_*")), "root release decisions not reconciled")
    tests("tests/test_qualification_manifest_truth.py", "tests/test_qualification_register_parses.py")


def item6():
    for name in ("financial_records_archive", "medical_imaging_pacs", "regulated_ai_checkpointing"):
        tracked(f"deploy/reference_architectures/{name}.md")
    tracked("go_to_market/PARTNER_READINESS.md")
    tracked("go_to_market/NAMED_ROSTER.md")
    roster = read("go_to_market/roster.json")["entries"]
    roles = {"support", "dispute", "security", "maintainer", "qc"}
    require({entry["role"].lower() for entry in roster} == roles, "named roles missing")
    for row in roster:
        name = row["name"].strip()
        require(name and name.upper() not in {"TBD", "TODO", "UNKNOWN", "UNAVAILABLE"}
                and "<" not in name, "placeholder human")
        evidence(row["consent"])
        if row["role"].lower() == "dispute":
            require(row["sla"].strip(), "dispute SLA missing")


def findings():
    registry = read(FINDINGS)
    require(registry["qualification"] == "HOLD", "gate cannot promote qualification")
    items = registry["items"]
    ids = {x["id"] for x in items}
    require({"MV-INPUTS", "MV-OPTION-D", "CLAIM-PURGE", "TEI-CONSENT",
             "FOLDED-RESIDENCY", "ANALYST-PACKAGE", "OPERATING-ROSTER", "PARADIGM-QC"} <= ids,
            "required finding missing")
    require(len(ids) == len(items), "duplicate finding")
    for row in items:
        require(row["status"] in {"OPEN", "CLOSED"}, "invalid finding state")
        if row["status"] == "CLOSED":
            evidence(row["evidence"])
            commit = row["referencing_commit"]
            require(re.fullmatch(r"[0-9a-f]{40}", commit) and
                    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"],
                                   cwd=ROOT).returncode == 0, "missing referencing commit")
    pending = [row["id"] for row in items if row["status"] == "OPEN"]
    require(not pending, "open findings: " + ", ".join(pending))
    require(registry["qc"] == "ACCEPTED", "independent QC pending")


def manifest():
    data = read(ARTIFACTS)
    required = {
        "docs/settlement/IPMVP_CONFORMITY.md", "tests/test_ipmvp.py",
        "docs/executive/CEO_STAKE_MEMO.md", "docs/analysts/TEI_INITIATION.md",
        "scripts/benchmarks/fold_residency_campaign.py", "docs/analysts/ANALYST_PACKAGE.md",
        "go_to_market/NAMED_ROSTER.md", "go_to_market/PARTNER_READINESS.md",
        "deploy/reference_architectures/financial_records_archive.md",
        "deploy/reference_architectures/medical_imaging_pacs.md",
        "deploy/reference_architectures/regulated_ai_checkpointing.md",
    }
    require(required <= {r["path"] for r in data["artifacts"]}, "incomplete digest manifest")
    for record in data["artifacts"]:
        evidence(record)


VALIDATORS = {"lens_wharton_ipmvp": item1, "lens_mckinsey_purge": item2,
              "lens_forrester_tei": item3, "lens_gartner_residency": item4,
              "lens_gartner_package": item5, "lens_accenture_model": item6,
              "artifact_integrity": manifest, "findings_and_qc": findings}


def main():
    require(not git("status", "--porcelain", "--untracked-files=no").strip(),
            "closure requires clean tracked worktree")
    results = {}
    for name, validator in VALIDATORS.items():
        try:
            validator()
            results[name] = {"pass": True}
        except (OSError, ValueError, KeyError, TypeError, RuntimeError,
                subprocess.CalledProcessError, ET.ParseError, ImportError) as exc:
            results[name] = {"pass": False, "reason": str(exc)}
    content = {"source_commit": git("rev-parse", "HEAD").decode().strip(),
               "results": results, "all_lenses_closed": all(r["pass"] for r in results.values()),
               "production_qualification": "NOT_ASSESSED_BY_THIS_GATE"}
    envelope = {"schema": "chronus.five-lens/1", "content": content,
                "digest": hashlib.sha256(json.dumps(content, sort_keys=True,
                    separators=(",", ":")).encode()).hexdigest()}
    result = json.dumps(envelope, indent=2, sort_keys=True) + "\n"
    print(result)
    out = ROOT / "reference-evidence/five-lens-closure.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result)
    return 0 if content["all_lenses_closed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
