"""Executed local release gate for the consumer bundle.

Verifies the built wheel/sdist in ``dist/`` and writes an evidence record to
``dist/artifact-verdict.json`` — the local verdict consumed by
``packaging/portfolio_release_audit.py``. Every check is actually executed:
artifact digests, twine metadata, a fresh-venv wheel install, and the CLI
surface (``pythia mint``/``verify``/``census``/``offers``) from the installed
copy. Nothing here asserts registry publication.

Usage::

    python verify_bundle.py            # verify dist/ artifacts, write verdict

Requires ``twine`` on the invoking interpreter (``pip install twine`` or the
package's ``dev`` extra).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
import venv
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
NAME = "hyba-pythia-consumer"
VERSION = "1.0.0"


def _run(cmd: list, cwd=None) -> tuple:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    dist = HERE / "dist"
    checks: dict = {}
    details: dict = {}

    # --- artifacts present and hashed --------------------------------------
    wheel = next(iter(sorted(dist.glob(f"{NAME.replace('-', '_')}-*.whl"))), None)
    sdist = next(iter(sorted(dist.glob(f"{NAME.replace('-', '_')}-*.tar.gz"))), None)
    checks["artifacts_present"] = wheel is not None and sdist is not None
    digests = {}
    if checks["artifacts_present"]:
        digests = {
            a.name: hashlib.sha256(a.read_bytes()).hexdigest()
            for a in (wheel, sdist)
        }

    # --- twine metadata check -----------------------------------------------
    if checks["artifacts_present"]:
        rc, out = _run([sys.executable, "-m", "twine", "check",
                        str(wheel), str(sdist)])
        checks["twine_check"] = rc == 0
        details["twine"] = out.strip()[-400:]
    else:
        checks["twine_check"] = False

    # --- catalog identity -----------------------------------------------------
    cat = json.loads((REPO / "packaging/publication_catalog.json").read_text())
    rows = [r for r in cat["packages"] if r["distribution"] == NAME]
    checks["catalog_identity"] = (
        len(rows) == 1 and rows[0].get("state") == "EXISTING_SCAFFOLD"
        and rows[0].get("first_public_version") == VERSION
    )

    # --- fresh-venv install + CLI smoke ---------------------------------------
    if checks["artifacts_present"]:
        with tempfile.TemporaryDirectory() as td:
            vdir = Path(td) / "v"
            venv.EnvBuilder(with_pip=True).create(vdir)
            py = vdir / ("Scripts/python.exe" if sys.platform == "win32"
                         else "bin/python")
            rc, out = _run([str(py), "-m", "pip", "install", str(wheel)])
            checks["wheel_install"] = rc == 0
            details["pip_install"] = out.strip()[-400:] if rc != 0 else "ok"
            if rc == 0:
                def cli(*args):
                    return _run([str(py), "-m", "pythia_consumer", *args],
                                cwd=td)
                rc, _ = _run([str(py), "-c",
                              "import importlib.metadata as md; "
                              f"assert md.version('{NAME}') == '{VERSION}'"])
                checks["installed_version"] = rc == 0
                mint_rc, mint_out = cli(
                    "mint", "--context", "local-verify", "--masks",
                    ",".join(["4"] * 11))
                # A bare exit code is not evidence — the minted payload must
                # actually parse as a receipt carrying a ZECK token.
                try:
                    minted = json.loads(mint_out)
                    checks["cli_mint"] = (mint_rc == 0
                                          and str(minted["token_hex"])
                                          .startswith("ZECK-"))
                except (json.JSONDecodeError, KeyError, AttributeError):
                    checks["cli_mint"] = False
                    details["mint"] = mint_out.strip()[-400:]
                receipt = Path(td) / "receipt.json"
                if checks["cli_mint"]:
                    receipt.write_text(mint_out)
                    vrc, vout = cli("verify", str(receipt))
                    try:
                        checks["cli_verify"] = (
                            vrc == 0
                            and json.loads(vout)["verdict"] == "pass")
                    except (json.JSONDecodeError, KeyError):
                        checks["cli_verify"] = False
                else:
                    checks["cli_verify"] = False
                crc, cout = cli("census")
                try:
                    checks["cli_census"] = (crc == 0
                                            and "device" in json.loads(cout))
                except json.JSONDecodeError:
                    checks["cli_census"] = False
                orc, oout = cli("offers")
                try:
                    checks["cli_offers"] = orc == 0 and json.loads(
                        oout)["schema"] == "pythia.consumer.offers/1"
                except (json.JSONDecodeError, KeyError):
                    checks["cli_offers"] = False
                # The package's own suite. Tests sys.path-insert src/, so this
                # exercises the staged bundle tree — the same bytes the wheel
                # carries (staged at build time), not the installed import.
                _run([str(py), "-m", "pip", "install", "pytest>=8,<10"])
                trc, tout = _run(
                    [str(py), "-m", "pytest",
                     str(HERE / "tests"), "-q", "-p", "no:cacheprovider"],
                    cwd=td)
                checks["tests_passed"] = trc == 0
                if trc != 0:
                    details["pytest"] = tout.strip()[-800:]
            else:
                for k in ("installed_version", "cli_mint", "cli_verify",
                          "cli_census", "cli_offers", "tests_passed"):
                    checks[k] = False

    try:
        head = subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        head = None

    verdict = {
        "schema": "hyba.local-artifact-verdict.v1",
        "product": NAME,
        "version": VERSION,
        "repository": "QuantumPhiRedux/PhiMiner",
        "source_commit": head,
        "generated_at": int(time.time()),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "details": details,
        "artifact_digests": digests,
        "bundle_note": ("bundle wheel vendors aethel/hyba_db/chronos_one_igpu; "
                        "not evidence of the singular sibling wheels' "
                        "qualification"),
        "publishable": False,
        "published": False,
    }
    out_path = dist / "artifact-verdict.json"
    out_path.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if verdict["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
