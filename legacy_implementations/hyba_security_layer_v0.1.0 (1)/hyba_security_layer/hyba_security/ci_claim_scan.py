"""AST scanner that fails CI on fake crypto and unearned claims.

Implements the AL HARAS Round 3 remediation: flag any sign/verify/encrypt
function whose body references no real cryptographic primitive, plus the
fake-keypair and XOR-cipher patterns found in the estate.

Usage:
    python3 -m hyba_security.ci_claim_scan <path> [<path> ...]
Exit code 1 on any finding, so CI fails fatally (no `|| echo`).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Final

# Recognised real primitives: module names AND concrete primitive symbols.
# Module names alone are not enough - `ChaCha20Poly1305(key).encrypt(...)`
# never mentions the word "cryptography".
CRYPTO_MODULES: Final[frozenset[str]] = frozenset(
    {
        "cryptography",
        "hmac",
        "nacl",
        "hashlib",
        "secrets",
        "ssl",
        # primitive symbols
        "ChaCha20Poly1305",
        "AESGCM",
        "AESCCM",
        "HKDF",
        "PBKDF2HMAC",
        "Fernet",
        "Ed25519PrivateKey",
        "Ed25519PublicKey",
        "X25519PrivateKey",
        "hashes",
        "sha256",
        "sha384",
        "sha512",
        "blake2b",
        "compare_digest",
        "urandom",
        "token_bytes",
        "pbkdf2_hmac",
    }
)

SENSITIVE_PREFIXES: Final[tuple[str, ...]] = (
    "sign",
    "_sign",
    "verify",
    "_verify",
    "encrypt",
    "_encrypt",
    "decrypt",
    "_decrypt",
    "seal",
    "protect",
)

# Files allowed to contain the defect patterns (negative-proof references).
#   legacy.py        - the P0-1 defect, retained only as a negative control
#   ci_claim_scan.py - this scanner, which must name the patterns it detects
#   claims.py        - the denylist definition itself
ALLOWLIST_SUFFIXES: Final[tuple[str, ...]] = (
    "hyba_security/legacy.py",
    "hyba_security/ci_claim_scan.py",
    "hyba_security/claims.py",
)

CLAIM_TERMS: Final[tuple[str, ...]] = (
    "aes-256-gcm",
    "quantum-resistant",
    "unhackable",
)

# A claim term inside a negation is a disclaimer, not a claim.
NEGATION_MARKERS: Final[tuple[str, ...]] = (
    "not ",
    "no ",
    "never",
    "false",
    "without",
    "absent",
    "roadmap",
    "restricted",
    "forbidden",
    "rejected",
)


def _is_negated(line: str) -> bool:
    return any(marker in line for marker in NEGATION_MARKERS)


def _false_valued_dict_keys(tree: ast.AST) -> set[int]:
    """ids of key nodes in `{"unhackable": False}` - these are disclaimers."""
    marked: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (
                    key is not None
                    and isinstance(value, ast.Constant)
                    and value.value is False
                ):
                    marked.add(id(key))
    return marked


def _names_in(node: ast.AST) -> set[str]:
    found: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            found.add(child.id)
        elif isinstance(child, ast.Attribute):
            found.add(child.attr)
        elif isinstance(child, ast.Import):
            for alias in child.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(child, ast.ImportFrom):
            if child.module:
                found.add(child.module.split(".")[0])
    return found


def _has_xor_over_bytes(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.BinOp) and isinstance(child.op, ast.BitXor):
            return True
    return False


def _build_primitive_resolver(tree: ast.AST):
    """Resolve primitive usage through same-module delegation.

    A wrapper that calls a local helper which hashes IS doing real crypto.
    Module-level imports are still never credited: only names referenced
    inside a function, or inside a local helper it actually calls, count.
    """
    defined: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined[node.name] = node

    direct: dict[str, set[str]] = {
        name: _names_in(node) for name, node in defined.items()
    }

    def resolve(name: str, seen: frozenset[str] = frozenset()) -> bool:
        if name in seen or name not in direct:
            return False
        names = direct[name]
        if names & CRYPTO_MODULES:
            return True
        for callee in names & defined.keys():
            if resolve(callee, seen | {name}):
                return True
        return False

    return resolve


def scan_source(source: str, filename: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    tree = ast.parse(source, filename=filename)
    resolve_primitive = _build_primitive_resolver(tree)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        body_src = ast.get_source_segment(source, node) or ""
        lowered = body_src.lower()

        # CRYPTO-3 applies to every function, not just sign/verify-named ones:
        # the fake keypair in the estate was called generate_keypair_pqc.
        if "public_key" in lowered and "sha256" in lowered and "token_bytes" in lowered:
            findings.append(
                {
                    "file": filename,
                    "line": node.lineno,
                    "function": node.name,
                    "rule": "CRYPTO-3",
                    "detail": "fake keypair: public key derived as a hash of the private key",
                }
            )

        name = node.name.lower()
        if not name.startswith(SENSITIVE_PREFIXES):
            continue

        # Only names referenced INSIDE the function, or inside a local helper it
        # calls, count. Crediting module-level imports would let one real
        # `import hashlib` launder every stub in the file.
        uses_primitive = resolve_primitive(node.name)

        if not uses_primitive:
            findings.append(
                {
                    "file": filename,
                    "line": node.lineno,
                    "function": node.name,
                    "rule": "CRYPTO-1",
                    "detail": "security-named function references no cryptographic primitive",
                }
            )

        if _has_xor_over_bytes(node):
            findings.append(
                {
                    "file": filename,
                    "line": node.lineno,
                    "function": node.name,
                    "rule": "CRYPTO-2",
                    "detail": "XOR construction on a security path (not an AEAD)",
                }
            )

    disclaimer_keys = _false_valued_dict_keys(tree)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in disclaimer_keys:
            continue
        for term in CLAIM_TERMS:
            for line in node.value.lower().splitlines():
                if term in line and not _is_negated(line):
                    findings.append(
                        {
                            "file": filename,
                            "line": node.lineno,
                            "function": "<string literal>",
                            "rule": "CLAIM-1",
                            "detail": f"unearned claim string: '{term}'",
                        }
                    )
                    break
    return findings


def scan_path(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    files = [root] if root.is_file() else sorted(root.rglob("*.py"))
    for path in files:
        posix = path.as_posix()
        if any(posix.endswith(suffix) for suffix in ALLOWLIST_SUFFIXES):
            continue
        source = path.read_text(encoding="utf-8")
        findings.extend(scan_source(source, posix))
    return findings


def main(argv: list[str]) -> int:
    targets = [Path(arg) for arg in argv[1:]] or [Path(".")]
    findings: list[dict[str, Any]] = []
    for target in targets:
        findings.extend(scan_path(target))

    report = {"findings": findings, "count": len(findings), "passed": not findings}
    print(json.dumps(report, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
