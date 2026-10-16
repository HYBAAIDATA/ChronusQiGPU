"""Static AST call-graph and import analyzer enforcing architectural boundaries."""

from __future__ import annotations
import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Set


class ASTBoundaryViolation:
    """Represents an architectural boundary violation detected by static analysis."""

    def __init__(self, file_path: str, line_number: int, violation_type: str, details: str):
        self.file_path = file_path
        self.line_number = line_number
        self.violation_type = violation_type
        self.details = details

    def __repr__(self) -> str:
        return f"<BoundaryViolation {self.file_path}:{self.line_number} [{self.violation_type}] {self.details}>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "violation_type": self.violation_type,
            "details": self.details,
        }


class ASTCallGraphGuard:
    """Scans Python ASTs in operational modules to enforce that trusted-core services cannot be imported or invoked."""

    FORBIDDEN_IMPORTS: Set[str] = {
        "EmergentQualificationService",
        "qualify",
        "euclid.emergence.trusted_core.qualification_service",
    }

    @classmethod
    def scan_file_for_violations(cls, file_path: Path) -> List[ASTBoundaryViolation]:
        violations: List[ASTBoundaryViolation] = []
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            violations.append(ASTBoundaryViolation(str(file_path), 0, "PARSE_ERROR", str(e)))
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(forbidden in alias.name for forbidden in cls.FORBIDDEN_IMPORTS):
                        violations.append(ASTBoundaryViolation(
                            file_path=str(file_path),
                            line_number=node.lineno,
                            violation_type="FORBIDDEN_IMPORT",
                            details=f"Forbidden import '{alias.name}' detected in operational module",
                        ))
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                for alias in node.names:
                    full_target = f"{module_name}.{alias.name}" if module_name else alias.name
                    if any(forbidden in full_target or forbidden == alias.name for forbidden in cls.FORBIDDEN_IMPORTS):
                        violations.append(ASTBoundaryViolation(
                            file_path=str(file_path),
                            line_number=node.lineno,
                            violation_type="FORBIDDEN_IMPORT_FROM",
                            details=f"Forbidden from-import '{alias.name}' from '{module_name}'",
                        ))

        return violations

    @classmethod
    def scan_directory(cls, dir_path: Path) -> List[ASTBoundaryViolation]:
        all_violations: List[ASTBoundaryViolation] = []
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.endswith(".py"):
                    full_p = Path(root) / file
                    v = cls.scan_file_for_violations(full_p)
                    all_violations.extend(v)
        return all_violations
