"""Contract-plane audit harness for the iGPU execution path.

Fail-closed. Every claim printed here is an assertion backed by an
executable check. A crashed check or a false invariant marks the run FAILED
and the process exits non-zero.

This harness deliberately does not take a prose audit on trust. It
re-derives each contract's status from the repository as it actually is,
including whether the governing spec is present at all.

Usage:
    python scripts/audit_igpu_contracts.py
    python scripts/audit_igpu_contracts.py --report reports/igpu_contract_audit.json
    python scripts/audit_igpu_contracts.py --only spec,C2,seam
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import platform
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PRESENT = "PRESENT"
PARTIAL = "PARTIAL"
ABSENT = "ABSENT"


class Audit:
    """Fail-closed collector: a check is an assertion, not a log line."""

    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []
        self.notes: List[str] = []

    def record(self, contract: str, title: str, status: str, evidence: str, **detail: Any) -> str:
        self.checks.append(
            {"contract": contract, "title": title, "status": status, "evidence": evidence, **detail}
        )
        print(f"  [{status:<8}] {contract:<6} {title}")
        print(f"            {evidence}")
        return status

    def check(self, contract: str, title: str, passed: bool, **detail: Any) -> bool:
        self.record(
            contract,
            title,
            PRESENT if passed else PARTIAL,
            "assertion passed" if passed else "assertion FAILED",
            assertion=passed,
            **detail,
        )
        return passed

    def note(self, text: str) -> None:
        self.notes.append(text)
        print(f"  [NOTE] {text}")

    def fail(self, contract: str, title: str, reason: str) -> None:
        self.checks.append(
            {
                "contract": contract,
                "title": title,
                "status": "FAILED",
                "evidence": reason,
                "assertion": False,
            }
        )
        print(f"  [FAILED  ] {contract:<6} {title}")
        print(f"            {reason}")

    @property
    def failures(self) -> List[Dict[str, Any]]:
        return [c for c in self.checks if c["status"] == "FAILED" or c.get("assertion") is False]


def _import(module: str) -> Any:
    return importlib.import_module(module)


def _has_symbol(module: str, *names: str) -> Tuple[bool, List[str]]:
    mod = _import(module)
    missing = [n for n in names if not hasattr(mod, n)]
    return (not missing), missing


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(ROOT), capture_output=True, text=True, check=False
        ).stdout.strip()
    except Exception:
        return ""


def section_spec(a: Audit) -> None:
    print("\n=== spec ===")
    spec = ROOT / "CONTRACTS.md"
    if spec.exists():
        a.record("SPEC", "CONTRACTS.md present", PRESENT, str(spec))
        return
    in_history = _git("log", "--all", "--oneline", "--", "CONTRACTS.md")
    a.record(
        "SPEC",
        "CONTRACTS.md present",
        ABSENT,
        "absent from the working tree and from every commit "
        f"(`git log --all -- CONTRACTS.md` -> {in_history!r})",
    )
    a.note(
        "C1-C10 / 12.x numbering is taken from the audit request prose. Statuses "
        "below are evidence about THIS repository and cannot be a conformance "
        "verdict against a canonical spec that is not present here."
    )


def section_c2(a: Audit) -> None:
    print("\n=== C2 AssemblyLock ===")
    ok, missing = _has_symbol("hyba_profiles", "compile_assembly", "verify_lock", "AssemblyIntent")
    if not ok:
        a.fail("C2", "AssemblyLock + verify_lock", f"missing: {missing}")
        return
    from hyba_profiles import PROFILES, compile_assembly, verify_lock
    from hyba_profiles.model import AssemblyIntent, AssemblyLock, ModuleEvidence

    fields = [f.name for f in dataclasses.fields(AssemblyLock)]
    required = {"schema_version", "manifest_hash", "policy_hash", "evidence_hash", "signature"}
    frozen = bool(AssemblyLock.__dataclass_params__.frozen)
    a.check(
        "C2",
        "AssemblyLock is immutable, versioned and signed",
        required.issubset(fields) and frozen,
        fields=fields,
        frozen=frozen,
    )
    # Build a gate-passing intent from a real profile so the lock under test
    # is one the repository would actually accept.
    profile = "developer"
    spec = PROFILES[profile]
    modules = tuple(sorted(spec.required_modules))
    evidence = tuple(ModuleEvidence(m, "1.0", True, True, False, False, ("test",)) for m in modules)
    intent = AssemblyIntent(
        name="audit-probe",
        deployment_profile=profile,
        deployment_seed="seed-audit",
        industry="generic",
        use_cases=("probe",),
        risk_level="standard",
        sovereignty="private",
        exactness="exact",
        resilience="continuous",
        economics=("cost",),
        modules=modules,
        module_evidence=evidence,
        dominant_tiers=spec.dominant_tiers,
    )
    result = compile_assembly(intent, signing_key=b"k" * 32)
    own = verify_lock(result, b"k" * 32)
    foreign = verify_lock(result, b"j" * 32)
    a.check(
        "C2",
        "lock verifies under its own key and fails under a foreign key",
        own is True and foreign is False,
        verified_own_key=own,
        verified_foreign_key=foreign,
    )
    a.check(
        "C2",
        "lock carries a named signature algorithm",
        bool(result.lock.signature_algorithm),
        signature_algorithm=result.lock.signature_algorithm,
    )


def section_12_2(a: Audit) -> None:
    print("\n=== 12.2 Fold <-> Operator ===")
    ok, missing = _has_symbol("hyba_contracts", "FoldContract", "OperatorContract", "FoldMode")
    if not ok:
        a.fail("12.2", "FoldContract / OperatorContract / FoldMode", f"missing: {missing}")
        return
    from hyba_contracts import FoldContract, FoldMode, OperatorContract

    modes = {m.name for m in FoldMode}
    required_modes = {"PRESERVE", "TRANSFORM", "REHYDRATE", "REJECT"}
    a.check(
        "12.2",
        "all four fold modes declared (PRESERVE/TRANSFORM/REHYDRATE/REJECT)",
        required_modes.issubset(modes),
        modes=sorted(modes),
    )
    fold_fields = {f.name for f in dataclasses.fields(FoldContract)}
    op_fields = {f.name for f in dataclasses.fields(OperatorContract)}
    a.check(
        "12.2",
        "fold contract carries family/exactness/invariants/residual bound",
        {"family", "exactness_mode", "invariant_set", "residual_bound"}.issubset(fold_fields),
        fields=sorted(fold_fields),
    )
    a.check(
        "12.2",
        "operator contract carries mode, accepted families and proof rule",
        {"mode", "accepted_fold_families", "output_invariants", "proof_rule"}.issubset(op_fields),
        fields=sorted(op_fields),
    )


def _fold_contracts():
    from hyba_contracts import FoldContract, FoldMode, OperatorContract

    fold = FoldContract(
        family="audit.fold",
        domain="probe",
        exactness_mode="exact",
        encode=lambda v: (v, 0.0),
        decode=lambda f, r: f + r,
        supported_operators=("keep", "rehydrate"),
        invariant_set=("finite",),
        residual_bound=0.0,
        canonical_hash_rule="sha256",
        backend_requirements=("cpu",),
        version="1.0.0",
    )

    def op(name, mode, deterministic=True):
        return OperatorContract(
            operator=name,
            accepted_fold_families=("audit.fold",),
            mode=mode,
            input_invariants=("finite",),
            output_invariants=("finite",),
            residual_rule="none",
            proof_rule="sha256",
            deterministic=deterministic,
            backend_capabilities=("cpu",),
        )

    return {
        "audit.fold": fold,
        "forbidden": op("forbidden", FoldMode.REJECT),
        "keep": op("keep", FoldMode.PRESERVE),
        "rehydrate": op("rehydrate", FoldMode.REHYDRATE, deterministic=False),
    }


class _Proof:
    """Minimal proof stub carrying a real, valid BackendCertificate."""

    proof_id = "p1"

    def __init__(self) -> None:
        from hyba_contracts import BackendCertificate, BackendClass

        # validate() requires overflow_behavior == "fail_closed" plus evidence.
        self.backend_certificate = BackendCertificate(
            backend_name="audit-cpu",
            backend_class=BackendClass.CLASSICAL_EXACT,
            device_id="audit-cpu",
            exactness_modes=("exact",),
            overflow_behavior="fail_closed",
            supported_operators=("keep", "rehydrate"),
            attestation="audit-attestation",
            conformance_hash="0" * 64,
        )


class _Obj:
    object_id = "obj-1"
    pisot_fold = 1.0
    residual_boundary = 0.0


def section_12_2_behaviour(a: Audit) -> None:
    print("\n=== 12.2 behaviour (REJECT / REHYDRATE) ===")
    from hyba_services.folding import FoldExecutor, UnsupportedPairing

    regs = _fold_contracts()
    folds = {"audit.fold": regs["audit.fold"]}
    operators = {k: v for k, v in regs.items() if k != "audit.fold"}
    ex = FoldExecutor(
        folds,
        operators,
        proof=lambda *a, **k: _Proof(),
        sign=lambda body: "sig",
    )
    refused = False
    try:
        ex.execute(
            _Obj(),
            "audit.fold",
            "forbidden",
            run_folded=lambda *a: (0.0, 0.0),
            run_exact=lambda *a: 0.0,
        )
    except UnsupportedPairing:
        refused = True
    a.check("12.2", "FoldMode.REJECT refuses execution", refused, refused=refused)

    receipt = ex.execute(
        _Obj(),
        "audit.fold",
        "rehydrate",
        run_folded=lambda *a: (0.0, 0.0),
        run_exact=lambda *a: 2.0,
    )
    a.check(
        "12.2",
        "REHYDRATE runs the exact path and counts rehydration on the receipt",
        receipt.rehydration_count == 1,
        rehydration_count=receipt.rehydration_count,
        mode=receipt.mode.value,
    )


def section_receipts(a: Audit) -> None:
    print("\n=== C7 / C8 receipts + evidence ===")
    ok, missing = _has_symbol(
        "hyba_contracts", "ResultReceipt", "EvidenceObject", "BackendCertificate"
    )
    if not ok:
        a.fail("C7", "ResultReceipt / EvidenceObject", f"missing: {missing}")
        return
    from hyba_contracts import EvidenceObject, ResultReceipt

    rf = {f.name for f in dataclasses.fields(ResultReceipt)}
    a.check(
        "C7",
        "ResultReceipt records mode, rehydration count, invariants and proof",
        {"mode", "rehydration_count", "invariants_checked", "proof_id"}.issubset(rf),
        fields=sorted(rf),
    )
    ef = {f.name for f in dataclasses.fields(EvidenceObject)}
    a.check(
        "C8",
        "EvidenceObject binds payload hash, signature and a verify command",
        {"payload_hash", "signature", "verify_command"}.issubset(ef),
        fields=sorted(ef),
    )


def section_seam(a: Audit) -> None:
    print("\n=== seam execution path ===")
    try:
        from igpu.seam import buffer, kernel, store
        from igpu.seam.probe import Capability, CapabilityFeatures
        from igpu.seam.types import (
            BufferBacking,
            DeviceClass,
            DeviceState,
            Distribution,
            KernelName,
            PrivacyMode,
            SeamError,
            attest,
            digest_of,
        )
    except Exception as exc:
        a.fail("SEAM", "seam imports", f"{type(exc).__name__}: {exc}")
        return

    store.reset()
    cap = Capability(
        device_id="audit-dev",
        device_class=DeviceClass.cpu_reference,
        vendor="audit-vendor",
        model="m",
        firmware_digest=digest_of(b"audit-dev"),
        memory_bytes=0,
        compute_units=1,
        max_work_group=1,
        measured_hps=Distribution(1.0, 0.0, 1),
        supported_kernels={KernelName.sha256d_verify},
        kernel_costs={},
        features=CapabilityFeatures(),
        attestation_chain=[attest("audit-dev", issuer="probe:audit-dev")],
        privacy_mode=PrivacyMode.none,
        state=DeviceState.present,
    )
    store.put_cap(cap)

    # The audit's headline defect: allocate() must not raise. A crash here is
    # exactly the reported store.audit(kind=...) positional/keyword collision.
    try:
        allocated = buffer.allocate("audit-dev", 64, backing=BufferBacking.host_visible)
        kinds = [r["kind"] for r in store.audit_snapshot()]
        a.check(
            "SEAM",
            "buffer.allocate() succeeds and audits without a field-name collision",
            allocated.is_ok() and "buffer_allocate" in kinds,
            allocate_ok=allocated.is_ok(),
            audit_kinds=kinds,
        )
    except Exception as exc:
        a.fail(
            "SEAM",
            "buffer.allocate()",
            f"CRASH {type(exc).__name__}: {exc} -- this is the reported "
            "store.audit(kind=...) collision",
        )

    dispatched = kernel.dispatch("audit", "audit-dev", KernelName.sha256d_verify, b"x", "idem-1")
    a.check(
        "SEAM",
        "kernel dispatch returns an attested handle",
        dispatched.is_ok(),
        error=None if dispatched.is_ok() else dispatched.error.value,
    )
    absent = kernel.dispatch("audit", "no-such-device", KernelName.sha256d_verify, b"x", "idem-2")
    a.check(
        "SEAM",
        "dispatch to an absent device fails closed (device_absent)",
        (not absent.is_ok()) and absent.error is SeamError.device_absent,
        error=absent.error.value if not absent.is_ok() else None,
    )
    store.reset()


def section_tests(a: Audit) -> None:
    print("\n=== contract test suites ===")
    groups = {
        "seam/iGPU": [
            "tests/test_igpu_seam.py",
            "tests/test_igpu_scan.py",
            "tests/test_seam_axioms.py",
            "tests/test_seam_v2.py",
            "tests/test_device_identity_contract.py",
        ],
        "contract plane": [
            "tests/test_hyba_profiles.py",
            "tests/test_packs_versioning_observability.py",
        ],
        "mining contracts": [
            "tests/test_mining_contracts.py",
            "tests/test_mining_defect_classes.py",
            "tests/test_startup_contract.py",
        ],
    }
    summary: Dict[str, Any] = {}
    for label, files in groups.items():
        missing = [f for f in files if not (ROOT / f).exists()]
        if missing:
            a.fail("TESTS", f"pytest {label}", f"missing files: {missing}")
            continue
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *files],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        tail = [ln for ln in proc.stdout.splitlines() if "passed" in ln or "failed" in ln]
        summary[label] = {
            "command": f"python -m pytest -q {' '.join(files)}",
            "exit_code": proc.returncode,
            "result": tail[-1].strip() if tail else "",
        }
        a.check("TESTS", f"pytest {label} passes", proc.returncode == 0, **summary[label])
    print(f"  test summary: {json.dumps(summary)}")


def section_assurance(a: Audit) -> None:
    print("\n=== 12.12 AssurancePack ===")
    ok, missing = _has_symbol("hyba_contracts", "AssurancePack", "ControlMapping")
    if not ok:
        a.fail("12.12", "AssurancePack", f"missing: {missing}")
        return
    from hyba_contracts import STARTER_ASSURANCE_PACKS, emit_gap_report

    a.check(
        "12.12",
        "AssurancePack + starter packs + gap reporting exist",
        len(STARTER_ASSURANCE_PACKS) > 0,
        starter_packs=len(STARTER_ASSURANCE_PACKS),
        gap_reporter=bool(emit_gap_report),
    )


def section_governance(a: Audit) -> None:
    print("\n=== 12.8 / 12.9 / 12.10 governance artifacts ===")
    for rel, contract, title, loader in (
        ("claims.yaml", "12.8", "claims.yaml (release gate)", "al_haras.claims_yaml.load_claims"),
        (
            "pairings.yaml",
            "12.9",
            "pairings.yaml (pairing admission)",
            "al_haras.pairings.load_pairings",
        ),
    ):
        found = [p for p in ROOT.rglob(rel)] + [p for p in ROOT.rglob(rel.replace(".yaml", ".yml"))]
        if not found:
            a.record(contract, title, ABSENT, f"no {rel} (or .yml) anywhere in the repository")
            continue
        module_name, fn_name = loader.rsplit(".", 1)
        try:
            registry = getattr(_import(module_name), fn_name)(found[0])
            count = len(getattr(registry, "claims", getattr(registry, "verified", ())))
            a.record(
                contract,
                title,
                PRESENT,
                f"found: {[str(p.relative_to(ROOT)) for p in found]}; "
                f"loader parsed {count} entries",
            )
        except Exception as exc:
            a.record(
                contract,
                title,
                ABSENT,
                f"{rel} present but failed to load: {exc}",
            )
    signed = sorted(ROOT.glob("manifests/*.signed.json"))
    if not signed:
        compose_files = sorted(p.name for p in ROOT.glob("docker-compose*.yml"))
        a.record(
            "12.10",
            "signed, versioned deployment manifest",
            ABSENT,
            f"deployment is hand-composed ({compose_files}) with no signed manifest binding them",
        )
    else:
        import os

        from al_haras.deployment_manifest import load_manifest
        from al_haras.deployment_manifest import verify_manifest

        key = os.environ.get("DEPLOYMENT_MANIFEST_KEY", "").encode()
        dev_key = ROOT / "manifests" / "dev-signing.key"
        if not key and dev_key.exists():
            key = dev_key.read_bytes()
        verdicts = {}
        for path in signed:
            try:
                verdicts[path.name] = verify_manifest(load_manifest(path), key) if key else "NO_KEY"
            except Exception as exc:
                verdicts[path.name] = f"INVALID: {exc}"
        a.record(
            "12.10",
            "signed, versioned deployment manifest",
            PRESENT if all(v is True for v in verdicts.values()) else ABSENT,
            f"manifests: {verdicts}",
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", type=Path, help="write the JSON audit here")
    parser.add_argument(
        "--only",
        help="comma-separated sections (spec,C2,12.2,12.2b,receipts,assurance,governance,seam,tests)",
    )
    args = parser.parse_args(argv)

    sections: Dict[str, Callable[[Audit], None]] = {
        "spec": section_spec,
        "C2": section_c2,
        "12.2": section_12_2,
        "12.2b": section_12_2_behaviour,
        "receipts": section_receipts,
        "assurance": section_assurance,
        "governance": section_governance,
        "seam": section_seam,
        "tests": section_tests,
    }
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        unknown = wanted - set(sections)
        if unknown:
            parser.error(f"unknown section(s): {sorted(unknown)}")
        sections = {k: v for k, v in sections.items() if k in wanted}

    a = Audit()
    for name, fn in sections.items():
        try:
            fn(a)
        except Exception as exc:  # a crashed section is a failure, never a skip
            a.fail(
                name,
                f"section {name}",
                f"CRASH {type(exc).__name__}: {exc}\n{traceback.format_exc()[-600:]}",
            )

    failures = a.failures
    print("\n=== SUMMARY ===")
    print(f"  contracts audited : {len(a.checks)}")
    print(f"  failures          : {len(failures)}")
    for f in failures:
        print(f"    FAILED {f['contract']}: {f['title']} -- {f['evidence']}")
    status = "FAIL" if failures else "OK"
    print(f"  STATUS            : {status}")

    if args.report:
        payload = {
            "schema": "igpu.contract_audit/v1",
            "commit": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
            },
            "spec_present": (ROOT / "CONTRACTS.md").exists(),
            "contracts": a.checks,
            "notes": a.notes,
            "summary": {
                "contracts_audited": len(a.checks),
                "failures": len(failures),
                "status": status,
            },
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"  report            : {args.report}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
