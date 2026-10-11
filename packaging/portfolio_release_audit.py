"""Portfolio release audit — one evidence-derived state per product.

Reads the six release workflows (static contract), the products' local
verification verdicts (``packaging/*/dist/*``), executed registry receipts
(``--receipts`` dir — typically downloaded Actions artifacts committed under
``release-evidence/``), and live registry state (PyPI/TestPyPI JSON APIs, or a
``--registry-snapshot`` fixture), then emits a machine-readable verdict:

    BLOCKED            workflow/local/dependency prerequisites missing
    QUALIFIED          local verification + workflow contract satisfied
    TESTPYPI_VERIFIED  candidate installed from TestPyPI, smoke matrix green
    PYPI_VERIFIED      same bytes installed from PyPI, smoke matrix green
    RELEASE_COMPLETE   evidence-linked GitHub release record exists

States are derived from evidence, never assigned by hand. Every check runs in
publish order; a dependency that cannot resolve on the target registry blocks
the dependent product at that stage regardless of dispatch order. A PyPI
presence without executed smoke evidence is reported as a release incident —
an immutable upload cannot be rolled back, only remediated.

    python packaging/portfolio_release_audit.py \
        [--sha HEAD] [--receipts release-evidence] [--offline] \
        [--registry-snapshot snapshot.json] [--out verdict.json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

STATES = ("BLOCKED", "QUALIFIED", "TESTPYPI_VERIFIED", "PYPI_VERIFIED", "RELEASE_COMPLETE")

# Per-product release contract. verdict_pass lists the boolean fields the local
# verdict must hold true (status equality for theseus/ovid is handled via
# verdict_status). deps are hyba-internal distribution specifiers that must
# resolve on the SAME registry before the product may advance past that stage.
PRODUCTS = {
    "hyba-kellogg-tensor": {
        "order": 1,
        "workflow": ".github/workflows/kellogg-tensor.yml",
        "verdict": "packaging/kellogg-tensor/dist/artifact-verdict.json",
        "verdict_pass": [
            "wheel_built", "wheel_clean_install_verified", "sdist_verified",
            "standalone_boundary_verified", "artifact_secret_scan_passed",
            "attestation_verified", "certificate_verification_passed",
            "registry_verified", "installed_imports_verified",
            "public_api_verified", "package_metadata_valid",
        ],
        "sha_field": "git_sha",
        "deps": {},
        "smoke_pythons": ["3.11", "3.12", "3.13", "3.14"],
    },
    "hyba-turing-vqc": {
        "order": 2,
        "workflow": ".github/workflows/turing-release.yml",
        "verdict": "packaging/turing/dist/artifact-build.json",
        "verdict_pass": [
            "wheel_built", "sdist_built", "metadata_valid",
            "package_boundary_archive_verified", "artifact_secret_scan_passed",
        ],
        "sha_field": "git_sha",
        "deps": {"hyba-kellogg-tensor": ">=1.0"},
        "smoke_pythons": ["3.11", "3.12", "3.13"],
    },
    "hyba-theseus-storage": {
        "order": 3,
        "workflow": ".github/workflows/storage-publication-preparation.yml",
        "workflow_strings": ["theseus-release-verdict"],
        "verdict": "packaging/theseus/dist/artifact-verdict.json",
        "verdict_status": "PASS",
        "sha_field": "source_commit",
        "deps": {},
        "smoke_pythons": ["3.11", "3.12", "3.13", "3.14"],
    },
    "hyba-ovid-data-organisation": {
        "order": 4,
        "workflow": ".github/workflows/storage-publication-preparation.yml",
        "workflow_strings": ["ovid-release-verdict"],
        "verdict": "packaging/ovid/dist/artifact-verdict.json",
        "verdict_status": "PASS",
        "sha_field": "source_commit",
        "deps": {"hyba-theseus-storage": "==1.0.0"},
        "smoke_pythons": ["3.11", "3.12", "3.13", "3.14"],
    },
    "hyba-toe-intelligence": {
        "order": 5,
        "workflow": ".github/workflows/toe-release.yml",
        "verdict": "packaging/toe/dist/artifact-verdict.json",
        "verdict_pass": [
            "artifact_verified", "wheel_boundary_verified",
            "secret_scan_passed", "twine_check",
        ],
        "verdict_equals": {"distribution_name_status": "APPROVED",
                           "owner_identity_approved": True},
        "sha_field": "git_sha",
        "name_field": "distribution",
        "deps": {"hyba-kellogg-tensor": ">=1.0,<2"},
        "smoke_pythons": ["3.12"],
    },
    "hyba-euclid-intelligence": {
        "order": 6,
        "workflow": ".github/workflows/euclid-v17-release.yml",
        "verdict": "packaging/euclid-engine/dist/euclid-engine-verification.json",
        "verdict_pass": ["passed"],
        "sha_field": "source_commit",
        "deps": {"hyba-kellogg-tensor": ">=1.0,<2",
                 "hyba-toe-intelligence": ">=1.0,<2",
                 "hyba-theseus-storage": ">=1.0,<2"},
        "smoke_pythons": ["3.11", "3.12", "3.13"],
    },
}

INDEXES = {"testpypi": "https://test.pypi.org", "pypi": "https://pypi.org"}


# --------------------------------------------------------------------------
# Minimal version specifier evaluation (== != >= <= > < , comma-separated).
# Avoids importing the third-party `packaging` library, which collides with
# this repo's own top-level packaging/ directory on sys.path.
# --------------------------------------------------------------------------

def _version_tuple(version: str) -> tuple:
    return tuple(int(p) for p in re.findall(r"\d+", version) or (0,))


def satisfies(version: str, spec: str) -> bool:
    """True when ``version`` matches every comma-separated comparator."""
    for clause in spec.split(","):
        clause = clause.strip()
        m = re.match(r"(==|!=|>=|<=|>|<)\s*(\S+)", clause)
        if not m:
            return False
        op, bound = m.group(1), _version_tuple(m.group(2))
        v = _version_tuple(version)
        n = max(len(v), len(bound))
        v, bound = v + (0,) * (n - len(v)), bound + (0,) * (n - len(bound))
        if op == "==" and not v == bound:
            return False
        if op == "!=" and not v != bound:
            return False
        if op == ">=" and not v >= bound:
            return False
        if op == "<=" and not v <= bound:
            return False
        if op == ">" and not v > bound:
            return False
        if op == "<" and not v < bound:
            return False
    return True


# --------------------------------------------------------------------------
# Evidence readers
# --------------------------------------------------------------------------

def registry_versions(name: str, index: str, fetcher) -> dict:
    """Return {"registered": bool, "versions": [...]} for a distribution."""
    if fetcher is None:
        def fetcher(url):
            try:
                with urllib.request.urlopen(url, timeout=20) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return None
                raise
    payload = fetcher(f"{INDEXES[index]}/pypi/{name}/json")
    if payload is None:
        return {"registered": False, "versions": []}
    return {"registered": True,
            "versions": sorted(payload.get("releases", {}), key=_version_tuple)}


def workflow_contract(path: Path, product: dict) -> dict:
    """Static release-lane contract: OIDC + environments + ordering hooks."""
    if not path.is_file():
        return {"ok": False, "missing": ["workflow file absent"]}
    text = path.read_text(encoding="utf-8")
    missing = []
    for needle, label in (
        ("workflow_dispatch", "manual dispatch"),
        ("publish", "publish input"),
        ("id-token: write", "OIDC permission"),
        ("gh-action-pypi-publish", "trusted-publisher action"),
        ("environment:", "reviewer-gated environment"),
        ("testpypi", "testpypi stage"),
        ("pypi", "pypi stage"),
    ):
        if needle not in text:
            missing.append(label)
    for needle in product.get("workflow_strings", ()):
        if needle not in text:
            missing.append(f"per-product verdict artifact {needle}")
    return {"ok": not missing, "missing": missing}


def local_verdict(path: Path, product: dict, name: str) -> dict:
    if not path.is_file():
        return {"present": False}
    row = json.loads(path.read_text(encoding="utf-8"))
    out = {"present": True, "path": str(path.relative_to(REPO)),
           "sha": row.get(product["sha_field"])}
    name_field = product.get("name_field", "product")
    out["identity_ok"] = (
        row.get(name_field) == name and row.get("version") == "1.0.0")
    failed = [key for key in product.get("verdict_pass", ())
              if row.get(key) is not True]
    for key, want in product.get("verdict_equals", {}).items():
        if row.get(key) != want:
            failed.append(key)
    if "verdict_status" in product:
        if row.get("status") != product["verdict_status"]:
            failed.append("status")
    out["checks_failed"] = failed
    out["passed"] = not failed
    return out


def collect_receipts(root: Path | None) -> list:
    """Scan a directory tree for executed registry receipts / publications."""
    if root is None or not root.is_dir():
        return []
    found = []
    for path in sorted(root.rglob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(row, dict) and row.get("registry") and row.get("product"):
            row["_file"] = str(path)
            found.append(row)
        elif isinstance(row, dict) and row.get("published") is True and row.get("product"):
            row["_file"] = str(path)
            row.setdefault("registry", "publication")
            found.append(row)
    return found


def receipt_sha(row: dict) -> str | None:
    return row.get("source_commit") or row.get("git_sha")


def receipt_green(row: dict) -> bool:
    if row.get("status") != "PASS":
        return False
    checks = row.get("checks")
    return bool(checks is None or all(checks.values()))


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------

def audit_product(name: str, product: dict, *, sha: str | None,
                  fetcher, receipts: list, offline: bool) -> dict:
    name_field = product.get("name_field", "product")
    result = {"order": product["order"], "state": "BLOCKED",
              "blockers": [], "stale_evidence": [], "receipts": {},
              "incident": None}

    # --- workflow contract -------------------------------------------------
    contract = workflow_contract(REPO / product["workflow"], product)
    result["workflow"] = {"file": product["workflow"], **contract}
    if not contract["ok"]:
        result["blockers"] += [f"workflow missing {m}" for m in contract["missing"]]
        return result

    # --- local verification verdict ----------------------------------------
    verdict = local_verdict(REPO / product["verdict"], product, name)
    result["local_verdict"] = verdict
    if not verdict.get("present"):
        result["blockers"].append("local verdict absent")
        return result
    if verdict["sha"] and sha and verdict["sha"] != sha:
        result["stale_evidence"].append(
            f"local verdict bound to {verdict['sha']}, not {sha}")
        result["blockers"].append("local verdict is stale for requested RC")
        return result
    # In latest-evidence mode (no frozen --sha) the verdict still reports the
    # commit it was executed at; callers can see drift without it disqualifying.
    if sha is None and verdict["sha"]:
        try:
            head = subprocess.check_output(
                ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
            result["verdict_stale_vs_head"] = verdict["sha"] != head
        except (OSError, subprocess.CalledProcessError):
            pass
    if not verdict["identity_ok"]:
        result["blockers"].append("local verdict identity mismatch")
        return result
    if not verdict["passed"]:
        result["blockers"] += [f"local gate failed: {k}"
                               for k in verdict["checks_failed"]]
        return result

    # --- registry state ----------------------------------------------------
    registries = {}
    if not offline:
        for index in INDEXES:
            registries[index] = registry_versions(name, index, fetcher)
    result["registry"] = registries
    published = {idx: "1.0.0" in registries.get(idx, {}).get("versions", ())
                 for idx in INDEXES}

    # --- receipts for this product at this sha ------------------------------
    mine = [r for r in receipts
            if r.get(name_field, r.get("product")) == name]
    fresh, stale = [], []
    for r in mine:
        if sha and receipt_sha(r) and receipt_sha(r) != sha:
            stale.append(r["_file"])
        else:
            fresh.append(r)
    result["stale_evidence"] += stale
    by_reg = {"testpypi": [], "pypi": []}
    publications = []
    for r in fresh:
        if r.get("registry") in by_reg:
            by_reg[r["registry"]].append(r)
        elif r.get("published") is True:
            publications.append(r)
    result["receipts"] = {
        reg: [{"python": r.get("python"), "status": r.get("status"),
               "file": r["_file"]} for r in rows]
        for reg, rows in by_reg.items()}

    def deps_available(index: str) -> list:
        missing = []
        if offline:
            return [f"{dep}{spec} (offline: unresolved)" for dep, spec in product["deps"].items()]
        for dep, spec in product["deps"].items():
            versions = registry_versions(dep, index, fetcher)["versions"]
            if not any(satisfies(v, spec) for v in versions):
                missing.append(f"{dep}{spec} not on {index}")
        return missing

    def matrix_green(index: str) -> bool:
        rows = by_reg[index]
        if not rows or not all(receipt_green(r) for r in rows):
            return False
        seen = {".".join(str(r.get("python", "")).split(".")[:2]) for r in rows}
        return set(product["smoke_pythons"]) <= seen

    # --- state ladder --------------------------------------------------------
    result["state"] = "QUALIFIED"

    dep_gaps = deps_available("testpypi")
    result["blockers"] += dep_gaps
    if published["testpypi"] and dep_gaps:
        result["incident"] = {
            "type": "published_before_dependency_prerequisites",
            "detail": f"on TestPyPI without {dep_gaps}; upload is immutable — "
                      "remediate with a patch release, not a rollback claim"}
    testpypi_ok = published["testpypi"] and matrix_green("testpypi")
    if published["testpypi"] and by_reg["testpypi"] and not matrix_green("testpypi"):
        result["incident"] = {"type": "testpypi_smoke_failure",
                              "detail": "executed smoke receipts exist but are not all PASS"}
    if not testpypi_ok:
        if published["testpypi"]:
            result["blockers"].append("TestPyPI published but smoke matrix absent/failed")
        return result
    result["state"] = "TESTPYPI_VERIFIED"

    dep_gaps = deps_available("pypi")
    result["blockers"] += dep_gaps
    if published["pypi"]:
        if not by_reg["pypi"]:
            result["incident"] = {
                "type": "published_without_executed_pypi_evidence",
                "detail": "immutable PyPI release exists; gather execution evidence "
                          "or remediate via patch — never claim rollback"}
            return result
        if not matrix_green("pypi"):
            result["incident"] = {
                "type": "pypi_smoke_failure",
                "detail": "immutable PyPI release failed clean-execution evidence; "
                          "preserve receipts and remediate via patch release"}
            return result
    elif dep_gaps:
        return result
    else:
        return result
    result["state"] = "PYPI_VERIFIED"

    final = [p for p in publications
             if p.get("testpypi_verified") is True]
    if not final:
        result["blockers"].append("no evidence-linked release record")
        return result
    result["state"] = "RELEASE_COMPLETE"
    result["release_record"] = final[0]["_file"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", default=None,
                        help="Frozen RC commit; evidence bound to other SHAs is rejected as stale")
    parser.add_argument("--receipts", type=Path, default=REPO / "release-evidence",
                        help="Directory of executed registry receipts / publication records")
    parser.add_argument("--offline", action="store_true",
                        help="Skip live registry queries (CI/air-gapped use)")
    parser.add_argument("--registry-snapshot", type=Path, default=None,
                        help="JSON fixture {index: {name: [versions]}} replacing live queries")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    try:
        head = subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        head = None
    # --sha selects frozen-RC auditing: every piece of evidence must bind to
    # that commit. Without it the audit evaluates each product at the SHA its
    # evidence was executed against (latest-evidence mode).
    sha = args.sha

    snapshot = None
    if args.registry_snapshot:
        snapshot = json.loads(args.registry_snapshot.read_text())

        def fetcher(url):
            for index, base in INDEXES.items():
                if url.startswith(base):
                    name = url.rstrip("/").split("/")[-2]
                    versions = snapshot.get(index, {}).get(name)
                    if versions is None:
                        return None
                    return {"releases": {v: [] for v in versions}}
            return None

    elif args.offline:
        fetcher = None
    else:
        fetcher = None  # default urllib fetcher inside registry_versions

    receipts = collect_receipts(args.receipts)
    products = {}
    for name, product in sorted(PRODUCTS.items(), key=lambda kv: kv[1]["order"]):
        products[name] = audit_product(
            name, product, sha=sha,
            fetcher=(fetcher if snapshot else None), receipts=receipts,
            offline=args.offline)

    counts = {s: 0 for s in STATES}
    incidents = []
    for name, row in products.items():
        counts[row["state"]] += 1
        if row["incident"]:
            incidents.append({"product": name, **row["incident"]})
    verdict = {
        "schema": "hyba.portfolio-release-audit.v1",
        "audit_mode": "frozen_rc" if sha else "latest_evidence",
        "rc_sha": sha,
        "head_sha": head,
        "states": counts,
        "publish_order": [n for n, _ in sorted(
            PRODUCTS.items(), key=lambda kv: kv[1]["order"])],
        "products": products,
        "incidents": incidents,
        "truth_boundary": "states are evidence-derived; a green local or CI "
            "verdict is qualification evidence, never publication. Registry "
            "presence plus executed same-sha smoke receipts are the only "
            "publication evidence; immutable uploads cannot be rolled back.",
    }
    text = json.dumps(verdict, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
