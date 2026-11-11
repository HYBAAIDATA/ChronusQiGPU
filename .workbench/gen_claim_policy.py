#!/usr/bin/env python3
"""Generate scripts/ci/claim_token_policy.json from a reviewed classification.

Every current-file occurrence of a policy token must be classified below with a
basis and a note; an unclassified occurrence stops the generator.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
EXCLUDED = ["vendor/", "archive/", "chronus_source_backup/", "docs/directives/"]
M, R, C = "mathematical-term", "refusal-or-denial", "claim-under-implementation"
BASIS = {
    "artifacts/qigpu/exact_library/qudit_qec.py": (M, "Dense p^n Hilbert-space size compared with O(n^2) tableau memory"),
    "artifacts/qigpu/manifest_607fe50583004bc5d31ae2e81c5026322d03e27ae38d6f9010b26c1e05b5a230.json": (M, "Recorded output of the qudit stabilizer example; dense-space growth"),
    "artifacts/qigpu/manifest_a02ccf33decd178dadfd8d1d250add7598b152d28fc532d816ec2ea78cc3b20c.json": (M, "Recorded output of the qudit stabilizer example; dense-space growth"),
    "artifacts/qigpu/manifest_c53bcc8c5e952b9a485d7b2e221ccbd2267ca1d4e0c0f24c1313de90a7f08bab.json": (M, "Recorded output of the qudit stabilizer example; dense-space growth"),
    "artifacts/qigpu/manifest_d26d7a53afd14a128d9545d7165fa57ae9945e6d000dff6fc811347c32e978a5.json": (M, "Recorded output of the qudit stabilizer example; dense-space growth"),
    "docs/FINOPS_AND_COMMERCIAL_ROI_BRIEF.md": (C, "Commercial brief; its claims are tracked for implementation in the claims register"),
    "docs/executive/CHRONUS_GPIU_AL_HARAS_MASTER_DOSSIER.md": (C, "Executive dossier; its claims are tracked for implementation in the claims register"),
    "docs/IGPU_MANIFESTO.md": (C, "Manifesto; its capability statements are tracked for implementation in the claims register"),
    "docs/specifications/Chronus_GPIU_v3.0_Specification.html": (C, "Version 3.0 specification; its claims are tracked for implementation in the claims register"),
    "docs/qigpu/pasted-text.txt": (R, "Model states that generic trigonometric values are not guaranteed cyclotomic"),
    "docs/system-update/mining-and-accelerators.md": (M, "Index arithmetic avoids materialising fast-growing coefficients"),
    "evidence/acceleration/capability-report.md": (R, "Evidence report states the result is not an advantage claim"),
    "evidence/acceleration/findings_tensor_baseline.md": (M, "Matrix-exponent gate construction in the measured baseline"),
    "evidence/cyclotomic/exact-mps-prototype.md": (M, "Output-length growth bound of the exact contraction"),
    "exact_primitive_library-v3.py": (M, "Cayley transform versus transcendental functions; dense p^n space versus O(n^2) tableau"),
    "frontend/app/mining/page.tsx": (M, "Contraction of the conjugate |psi|^n towards zero (|psi| < 1)"),
    "frontend/public/chronus-observatory.html": (C, "Observatory page; its statements are tracked for implementation in the claims register"),
    "qigpu_acceleration_system.py": (R, "Module states there is no universal compression"),
    "reviews/acceleration_review.md": (R, "Review explains why the speed-up claims are not established"),
    "reviews/attestation-file-review-2026-11-11.md": (R, "Review challenging an unsupported qubit count"),
    "scripts/ci/regional_failover_burst_test.py": (M, "Retry back-off schedule (engineering term)"),
    "src/chronus/tensor/charter.py": (R, "Charter lists phrases the system refuses to claim"),
    "src/chronus/tensor/exact_mps.py": (M, "Output-length growth bound of the exact contraction"),
    "src/chronus/tensor/evolution.py": (M, "Generator of a small local unitary step (calculus term)"),
    "src/chronus/tensor/adaptive_contraction.py": (R, "Listed among refused claims returned to callers"),
    "src/chronus/tensor/enhanced_representation.py": (R, "Listed among refused claims returned to callers"),
    "src/chronus/service/production_hr_api_v2.py": (R, "Listed among refused claims returned to callers"),
    "src/turing/physics/cayley.py": (M, "Cayley transform avoids transcendental matrix functions"),
    "src/turing/stabilizer/tableau.py": (M, "Dense p^n space compared with O(n^2) symplectic tableau"),
    "tests/test_falsifiable_tensor.py": (R, "Test asserts the claim audit refuses the phrase"),
}

tokens = [bytes(t).lower() for t in json.loads((ROOT / "scripts/ci/claim_token_bytes.json").read_text())]
entries, unclassified = [], []
for raw in subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0"):
    if not raw:
        continue
    rel = raw.decode("utf-8", "surrogateescape")
    if rel.startswith(tuple(EXCLUDED)):
        continue
    path = ROOT / rel
    if path.is_symlink() or not path.is_file():
        continue
    data = path.read_bytes().lower()
    for index, token in enumerate(tokens):
        count = data.count(token)
        if not count:
            continue
        if rel not in BASIS:
            unclassified.append((rel, index, count))
            continue
        basis, note = BASIS[rel]
        entries.append({"path": rel, "token": index, "count": count, "basis": basis, "note": note})

if unclassified:
    print("UNCLASSIFIED OCCURRENCES:")
    for item in unclassified:
        print("  ", item)
    sys.exit(1)

policy = {
    "description": (
        "Reviewed exceptions for scripts/ci/check_forbidden_claims.py. Excluded prefixes hold "
        "third-party code and preserved historical material; every allowlist entry records the "
        "exact occurrence count and the basis for the wording."
    ),
    "excluded_prefixes": EXCLUDED,
    "allowlist": sorted(entries, key=lambda e: (e["path"], e["token"])),
}
(ROOT / "scripts/ci/claim_token_policy.json").write_text(json.dumps(policy, indent=2) + "\n")
print(f"claim policy: {len(entries)} allowlist entries across {len({e['path'] for e in entries})} files")
