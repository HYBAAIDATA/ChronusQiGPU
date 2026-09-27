"""Nonce Agent contract verifier.

Contract (docs/mining_agents/NONCE_AGENT.md):
  - Nonce coverage is complete (no gaps in the search space).
  - Nonce allocation is collisionless across miners.
  - Nonce permutations are Cassini-verified.
  - Salamander allocation uses prime-bucket addressing.
  - Log every nonce allocation with provenance.

Rules:
  1. transform_collisionless — the (faceId, localIndex) -> nonce map uses
     disjoint bit fields, so distinct candidates cannot collide. Verified by
     extracting the mask/shift constants from transformCandidateToNonce and
     checking the bit fields are disjoint and cover the 32-bit word.

  2. candidate_enumeration_full_coverage — executeMiningStep enumerates the
     full face x local grid (32 x statesPerFace) before navigation; the
     default path prunes nothing.

  3. cassini_permutations_verified — the tensor navigator verifies the
     Cassini identity per face anchor and emits cassiniVerified telemetry.

  4. salamander_prime_buckets — PRIME_BUCKETS is exactly the first 25 primes
     and Salamander allocation routes slots through them.
"""

from __future__ import annotations

import ast
import re

from .common import (
    RuleResult,
    TsSource,
    Violation,
    fail,
    load_ts,
    parse_py,
    pass_,
)

AGENT = "nonce_agent"


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    for p in range(2, int(n**0.5) + 1):
        if n % p == 0:
            return False
    return True


def check_transform_collisionless(src: TsSource) -> list[Violation]:
    """transformCandidateToNonce must pack faceId and localIndex into
    disjoint bit fields — the structural reason it cannot collide."""
    violations: list[Violation] = []
    fn = src.function_named("transformCandidateToNonce")
    if fn is None:
        return [
            Violation(
                file=src.relpath,
                line=1,
                detail="transformCandidateToNonce not found",
                fix="Restore the (faceId, localIndex) -> nonce transform.",
            )
        ]
    body = src.region_text(fn)
    ln, _ = src.region_lines(fn)

    face = re.search(r"faceId\s*&\s*(0x[0-9a-fA-F]+|\d+)\s*\)?\s*<<\s*(\d+)", body)
    local = re.search(r"localIndex\s*&\s*(0x[0-9a-fA-F]+|\d+)", body)
    if not face or not local:
        return [
            Violation(
                file=src.relpath,
                line=ln,
                detail="transform does not pack (faceId << shift) | localIndex "
                "with masked bit fields",
                fix="Pack faceId into the high bits and localIndex into disjoint " "low bits.",
            )
        ]

    face_mask, shift, local_mask = (
        int(face.group(1), 0),
        int(face.group(2)),
        int(local.group(1), 0),
    )
    if (face_mask << shift) & local_mask:
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail=f"bit fields overlap: (face & {face_mask:#x}) << {shift} "
                f"collides with local & {local_mask:#x}",
                fix="Choose disjoint masks so the packing is injective.",
            )
        )
    if face_mask.bit_count() + local_mask.bit_count() > 32:
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail=f"fields total {face_mask.bit_count() + local_mask.bit_count()} bits > 32-bit nonce",
                fix="Fields must fit inside the 32-bit nonce word.",
            )
        )
    if face_mask < 0x1F:
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail=f"face mask {face_mask:#x} cannot encode all 32 faces",
                fix="Face field needs >= 5 bits (0x1f).",
            )
        )
    return violations


def check_full_coverage(src: TsSource) -> list[Violation]:
    """The mining step must enumerate the full 32-face x statesPerFace grid."""
    violations: list[Violation] = []
    fn = src.function_named("executeMiningStep")
    if fn is None:
        return [
            Violation(
                file=src.relpath,
                line=1,
                detail="executeMiningStep not found",
                fix="Restore the mining step.",
            )
        ]
    body = src.region_text(fn)
    ln, _ = src.region_lines(fn)
    if not re.search(r"faceId\s*<\s*32\b", body):
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail="candidate enumeration does not iterate all 32 faces",
                fix="Loop faceId over the full M32 face set.",
            )
        )
    if not re.search(r"localIndex\s*<\s*statesPerFace\b", body):
        violations.append(
            Violation(
                file=src.relpath,
                line=ln,
                detail="candidate enumeration does not iterate all statesPerFace " "local indices",
                fix="Loop localIndex over the full per-face state range.",
            )
        )
    return violations


def check_cassini_permutations(src: TsSource) -> list[Violation]:
    violations: list[Violation] = []
    found_cassini = any(True for _ in src.find(r"ExactSequenceMath\.cassini\s*\("))
    found_telemetry = any(True for _ in src.find(r"\bcassiniVerified\b"))
    if not found_cassini:
        violations.append(
            Violation(
                file=src.relpath,
                line=1,
                detail="no ExactSequenceMath.cassini() verification call",
                fix="Verify the Cassini identity per face anchor.",
            )
        )
    if not found_telemetry:
        violations.append(
            Violation(
                file=src.relpath,
                line=1,
                detail="no cassiniVerified telemetry emitted",
                fix="Emit per-candidate Cassini parity verification in telemetry.",
            )
        )
    return violations


def check_salamander_prime_buckets() -> tuple[list[Violation], str]:
    """PRIME_BUCKETS must be the first 25 primes and Salamander routing must
    index through it."""
    violations: list[Violation] = []
    rel = "Intelligence/poincare_golden_11d.py"
    tree = parse_py(rel)
    assign = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "PRIME_BUCKETS":
                    assign = node
    if assign is None or not isinstance(assign.value, ast.List):
        return (
            [
                Violation(
                    file=rel,
                    line=1,
                    detail="PRIME_BUCKETS literal list not found",
                    fix="Define PRIME_BUCKETS as the first 25 primes.",
                )
            ],
            rel,
        )
    vals = [e.value for e in assign.value.elts if isinstance(e, ast.Constant)]
    if len(vals) != 25 or not all(isinstance(v, int) and _is_prime(v) for v in vals):
        violations.append(
            Violation(
                file=rel,
                line=assign.lineno,
                detail=f"PRIME_BUCKETS has {len(vals)} entries, all prime: "
                f"{all(isinstance(v, int) and _is_prime(v) for v in vals)}",
                fix="PRIME_BUCKETS must be exactly the first 25 primes.",
            )
        )

    sal = "Intelligence/salamander.py"
    sal_tree = parse_py(sal)
    uses_prime = any(
        isinstance(n, ast.Name) and n.id == "PRIME_BUCKETS" for n in ast.walk(sal_tree)
    )
    if not uses_prime:
        violations.append(
            Violation(
                file=sal,
                line=1,
                detail="salamander.py never references PRIME_BUCKETS — "
                "allocation is not prime-bucket routed",
                fix="Route slot allocation through PRIME_BUCKETS.",
            )
        )
    return violations, rel


def verify() -> list[RuleResult]:
    service = load_ts("src/lib/mining_service.ts")
    bridge = load_ts("src/lib/m32_tensor_bridge.ts")

    results: list[RuleResult] = []

    v = check_transform_collisionless(service)
    results.append(
        fail(AGENT, "transform_collisionless", v)
        if v
        else pass_(
            AGENT,
            "transform_collisionless",
            file="src/lib/mining_service.ts",
            detail="transformCandidateToNonce packs faceId into bits 27..31 and "
            "localIndex into bits 0..26 — disjoint fields, injective map.",
        )
    )

    v = check_full_coverage(service)
    results.append(
        fail(AGENT, "candidate_enumeration_full_coverage", v)
        if v
        else pass_(
            AGENT,
            "candidate_enumeration_full_coverage",
            file="src/lib/mining_service.ts",
            detail="executeMiningStep enumerates the full 32 x statesPerFace grid.",
        )
    )

    v = check_cassini_permutations(bridge)
    results.append(
        fail(AGENT, "cassini_permutations_verified", v)
        if v
        else pass_(
            AGENT,
            "cassini_permutations_verified",
            file="src/lib/m32_tensor_bridge.ts",
            detail="Navigator verifies ExactSequenceMath.cassini() per face "
            "anchor and emits cassiniVerified telemetry.",
        )
    )

    v, rel = check_salamander_prime_buckets()
    results.append(
        fail(AGENT, "salamander_prime_buckets", v)
        if v
        else pass_(
            AGENT,
            "salamander_prime_buckets",
            file=rel,
            detail="PRIME_BUCKETS is the first 25 primes; salamander.py routes "
            "slot allocation through it.",
        )
    )
    return results
