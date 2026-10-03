"""Keep prohibited throughput and speedup claims out of external operations docs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ROOT_DOCS = {"readme.md", "deployment.md"}
CLAIMS_FILE = "claims.yaml"
RATE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:[kmgtpe]\s*)?"
    r"(?:h\s*/\s*s|hash(?:es)?\s*/\s*s|(?:kilo|mega|giga|tera|peta|exa)?hash(?:es)?"
    r"\s+(?:/|per)\s+second)\b",
    re.IGNORECASE,
)
GPU_EQUIVALENCE = re.compile(
    r"\b(?:one|a|single)\s+(?:device|gpu|chip)\b.{0,80}"
    r"\b(?:equals?|equivalent to|matches?)\b.{0,40}"
    r"\b\d[\d,]*\s+(?:nvidia\s+)?gpus?\b",
    re.IGNORECASE,
)
MULTIPLIER = re.compile(
    r"\b(?P<signal>lucas|pisot|kellogg|toe|tensor|geometric|quantum)\b"
    r".{0,100}\b(?P<action>amplif(?:y|ies|ied)|multiply|multipl(?:y|ies)|"
    r"boost(?:s|ed)?|accelerat(?:e|es|ed)|speed\s+up)\b"
    r".{0,100}\b(?:hash\s*rate|hashes|throughput|sha.?256d|proof.of.work)\b",
    re.IGNORECASE,
)
NEGATION = re.compile(r"(?:\bnot|\bnever|\bno|do not|does not|cannot|can't)\s*$", re.I)


def external_doc(path: Path, root: Path) -> bool:
    """Return whether a markdown file is operator-facing deployment material."""
    relative = path.relative_to(root).as_posix().lower()
    if relative in ROOT_DOCS:
        return True
    parts = Path(relative).parts
    if parts[0] in {"deploy", "runbooks"}:
        return True
    return parts[0] == "docs" and any(
        "deploy" in part or "production" in part or "runbook" in part for part in parts[1:]
    )


def _exact_claim_pattern(text: str) -> re.Pattern[str]:
    return re.compile(re.escape(text).replace(r"\ ", r"\s+"), re.IGNORECASE)


def _approved_hypothesis(path: Path, root: Path, text: str, phrase: str) -> bool:
    """Research hypotheses are allowed only when labelled under experiments/."""
    relative = path.relative_to(root).as_posix()
    if not relative.startswith("experiments/"):
        return False
    pattern = _exact_claim_pattern(phrase)
    for paragraph in re.split(r"\n\s*\n", text):
        if pattern.search(paragraph) and re.search(
            r"\b(?:research\s+)?hypothesis\b", paragraph, re.I
        ):
            return True
    return False


def _claim_register(root: Path) -> list[dict[str, object]]:
    document = yaml.safe_load((root / CLAIMS_FILE).read_text(encoding="utf-8"))
    claims = document.get("claims", []) if isinstance(document, dict) else []
    if not isinstance(claims, list):
        raise ValueError(f"{CLAIMS_FILE} must contain a claims list")
    return [claim for claim in claims if isinstance(claim, dict)]


def _document_paths(root: Path) -> list[Path]:
    paths = []
    for path in root.rglob("*.md"):
        if any(part in {".git", ".venv", "node_modules", "legacy"} for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        if external_doc(path, root) or relative.startswith("experiments/"):
            paths.append(path)
    return sorted(paths)


def scan(root: Path = ROOT) -> list[str]:
    """Find prohibited assertions in external docs and misplaced hypotheses."""
    root = root.resolve()
    claims = _claim_register(root)
    disallowed = [
        (str(claim["status"]), str(claim["text"]))
        for claim in claims
        if claim.get("status") in {"PROHIBITED", "REFUTED"} and isinstance(claim.get("text"), str)
    ]
    hypotheses = [
        claim
        for claim in claims
        if claim.get("status") == "HYPOTHESIS" and isinstance(claim.get("text"), str)
    ]
    findings: list[str] = []
    for path in _document_paths(root):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(root).as_posix()
        is_external = external_doc(path, root)
        if is_external:
            for status, claim in disallowed:
                if _exact_claim_pattern(claim).search(text):
                    findings.append(f"{relative}: contains {status} claim text: {claim}")
            if RATE.search(text):
                findings.append(f"{relative}: contains a numerical hashrate assertion")
            if GPU_EQUIVALENCE.search(text):
                findings.append(f"{relative}: contains an unsupported device/GPU equivalence")
            for match in MULTIPLIER.finditer(text):
                prefix = text[max(0, match.start("action") - 24) : match.start("action")]
                if not NEGATION.search(prefix):
                    findings.append(
                        f"{relative}: links {match.group('signal')} to mining throughput"
                    )
                    break
        for claim in hypotheses:
            phrase = str(claim["text"])
            if not _exact_claim_pattern(phrase).search(text):
                continue
            if is_external or not _approved_hypothesis(path, root, text, phrase):
                findings.append(
                    f"{relative}: HYPOTHESIS claim must be clearly labelled under experiments/: {phrase}"
                )
    return findings


def main() -> int:
    findings = scan()
    if findings:
        for finding in findings:
            print(f"FAIL — {finding}", file=sys.stderr)
        return 1
    print("PASS — external deployment documentation respects claims.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
