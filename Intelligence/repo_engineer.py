"""Repo-aware engineering assistant with bounded inspection capabilities."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_TOOL_CALLS = 8
MAX_FILE_LINES = 240
MAX_FILE_BYTES = 512_000
MAX_TOOL_OUTPUT_CHARS = 14_000
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".hypothesis",
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".secret", ".credentials"}
CONTEXT_FILES = (
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/UNIFIED_RUNTIME.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    ".env.example",
)

ROUTE_KEYWORDS: dict[str, set[str]] = {
    "repository_map": {
        "repo", "repository", "codebase", "architecture", "runtime", "structure", "optimize", "optimization", "refine", "improve", "review"
    },
    "import_audit": {"import", "wiring", "module", "broken", "dependency", "integration"},
    "skill_lookup": {"skill", "skills", "training", "learning", "memory", "capability"},
    "focused_tests": {"test", "tests", "failing", "failure", "regression", "verify", "verification"},
}
NATIVE_CAPABILITIES = tuple(ROUTE_KEYWORDS)


def default_store_dir(repo_root: Path) -> Path:
    """Beside the other intelligences' state: ``PYTHIA_INTELLIGENCE_DIR`` when
    set (the deployed image points it at its writable volume; the source tree
    is read-only there), else the repository's own ``data/``."""
    configured = os.getenv("PYTHIA_INTELLIGENCE_DIR", "").strip()
    base = Path(configured) if configured else repo_root / "data"
    return base / "repo_engineer"


class RepoEngineer:
    """Route repository tasks through native audits, skills, tests, and memory."""

    def __init__(
        self,
        repo_root: Path | None = None,
        *,
        store_dir: Path | None = None,
    ) -> None:
        self.repo_root = (repo_root or REPO_ROOT).resolve()
        if str(self.repo_root) not in sys.path:
            sys.path.insert(0, str(self.repo_root))
        from Intelligence.pythia_learning import PythiaLearning
        from Intelligence.pythia_memory import PythiaMemorySystem
        from Intelligence.pythia_store import PythiaStore

        self.memory = PythiaMemorySystem()
        self.learning = PythiaLearning(n_units=32)
        self.store = PythiaStore(
            self.memory,
            self.learning,
            store_dir=store_dir or default_store_dir(self.repo_root),
        )
        self.store.load()
        self.context, self.context_files = self._load_context()

    @staticmethod
    def _engineering_guidance(content: str) -> str:
        sections = []
        for heading in (
            "### 4.4 Architecture & Package Boundaries",
            "### 4.5 Critical Security & Consensus Caveats",
        ):
            start = content.find(heading)
            if start < 0:
                continue
            end = content.find("\n### ", start + len(heading))
            sections.append(content[start:] if end < 0 else content[start:end])
        return "\n\n".join(sections) if sections else content[:6_000]

    def _load_context(self) -> tuple[str, list[str]]:
        chunks = []
        loaded = []
        budget = 24_000
        for relative in CONTEXT_FILES:
            path = self.repo_root / relative
            if not path.is_file() or budget <= 0:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if relative == "AGENTS.md":
                content = self._engineering_guidance(content)
            content = content[: min(6_000, budget)]
            chunks.append(f"## {relative}\n{content}")
            loaded.append(relative)
            budget -= len(content)
        top_level = sorted(
            item.name + ("/" if item.is_dir() else "")
            for item in self.repo_root.iterdir()
            if item.name not in EXCLUDED_DIRS
        )
        chunks.append("## Repository top-level\n" + "\n".join(top_level[:120]))
        return "\n\n".join(chunks), loaded

    def status(self) -> dict[str, Any]:
        feedback = self._feedback_scores()
        return {
            "provider": "in_repo",
            "model": "native capability router",
            "ready": True,
            "context_loaded": bool(self.context),
            "context_files": list(self.context_files),
            "tools": list(NATIVE_CAPABILITIES),
            "write_access": False,
            "learning": self.memory.status(),
            "store": self.store.status(),
            "route_feedback": feedback,
        }

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {word for word in re.findall(r"[a-z0-9_./-]+", text.lower()) if len(word) > 2}

    def _feedback_scores(self) -> dict[str, dict[str, float | int]]:
        totals: dict[str, list[int]] = {}
        for entry in self.store.journal.entries(limit=500, kind="repo_engineer_feedback"):
            payload = entry.get("payload", {})
            for route in payload.get("routes", []):
                counts = totals.setdefault(str(route), [0, 0])
                counts[0] += int(bool(payload.get("helpful")))
                counts[1] += 1
        return {
            route: {
                "helpful": helpful,
                "total": total,
                "rate": (helpful + 1) / (total + 2),
            }
            for route, (helpful, total) in sorted(totals.items())
        }

    def _select_routes(self, prompt: str) -> list[str]:
        tokens = self._tokens(prompt)
        feedback = self._feedback_scores()
        ranked = []
        for route, keywords in ROUTE_KEYWORDS.items():
            lexical_score = len(tokens & keywords)
            if lexical_score:
                learned_rate = float(feedback.get(route, {}).get("rate", 0.5))
                ranked.append((lexical_score + (learned_rate - 0.5) * 0.25, route))
        if not ranked:
            return ["repository_map", "import_audit"]
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [route for _, route in ranked[:3]]

    def _repo_map(self) -> dict[str, Any]:
        result = self._list_files(".")
        try:
            status = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            result["working_tree"] = status.stdout.splitlines()[:80] if status.returncode == 0 else []
        except (OSError, subprocess.TimeoutExpired):
            result["working_tree"] = []
        return result

    def _import_audit(self) -> dict[str, Any]:
        try:
            from scripts.import_audit import Auditor, live_files

            findings = Auditor(self.repo_root).audit(live_files(self.repo_root))
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
        return {
            "files_audited": len(live_files(self.repo_root)),
            "finding_count": len(findings),
            "findings": [
                {
                    "code": item.code,
                    "file": item.file,
                    "line": item.line,
                    "module": item.module,
                    "name": item.name,
                    "hidden": item.hidden,
                }
                for item in findings[:40]
            ],
            "truncated": len(findings) > 40,
        }

    def _skill_lookup(self, prompt: str) -> dict[str, Any]:
        try:
            from Intelligence.skill_loader import discover_skills

            skills = discover_skills()
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
        tokens = self._tokens(prompt)
        ranked = []
        for skill in skills:
            searchable = " ".join([skill.name, skill.description, *skill.tags]).lower()
            overlap = len(tokens & self._tokens(searchable))
            if overlap:
                ranked.append((overlap, skill))
        ranked.sort(key=lambda item: (-item[0], item[1].name))
        return {
            "skills_discovered": len(skills),
            "matches": [
                {
                    "name": skill.name,
                    "description": skill.description,
                    "tags": skill.tags,
                    "instructions": skill.instructions[:600],
                    "tools": skill.tools,
                }
                for _, skill in ranked[:5]
            ],
        }

    def _route(self, route: str, prompt: str) -> dict[str, Any]:
        if route == "repository_map":
            return self._repo_map()
        if route == "import_audit":
            return self._import_audit()
        if route == "skill_lookup":
            return self._skill_lookup(prompt)
        if route == "focused_tests":
            targets = re.findall(r"[\w./\\-]*test_[\w./\\-]+\.py", prompt)
            if not targets:
                return {"available": False, "reason": "include one approved test_*.py path to run a focused test"}
            return self._run_tests(targets[0].replace("\\", "/"))
        return {"error": "route_not_allowed"}

    @staticmethod
    def _format_report(task_id: str, routes: list[str], evidence: dict[str, Any]) -> str:
        lines = [
            f"In-repository engineering pass: {task_id}",
            "This report uses local deterministic capabilities; no hosted model was called.",
            "Selected routes: " + ", ".join(routes),
        ]
        audit = evidence.get("import_audit", {})
        if "finding_count" in audit:
            lines.append(
                f"Import/wiring audit: {audit['finding_count']} finding(s) across {audit['files_audited']} files."
            )
            for finding in audit.get("findings", [])[:12]:
                hidden = " (inside import-error handler)" if finding["hidden"] else ""
                lines.append(
                    f"  {finding['file']}:{finding['line']} {finding['code']} {finding['module']}{hidden}"
                )
        skills = evidence.get("skill_lookup", {})
        if skills:
            lines.append(f"Local skills discovered: {skills.get('skills_discovered', 0)}.")
            lines.extend(f"  Relevant skill: {item['name']}" for item in skills.get("matches", []))
        tests = evidence.get("focused_tests", {})
        if "returncode" in tests:
            lines.append(f"Focused test exit code: {tests['returncode']}.")
        if not audit.get("finding_count") and not skills.get("matches") and not tests:
            lines.append("No specific defect is asserted without a measured finding; use the repo map to choose a target.")
        lines.append("No source files were modified. Review evidence before choosing a change.")
        return "\n".join(lines)

    def _persist_episode(
        self,
        *,
        task_id: str,
        prompt: str,
        routes: list[str],
        tool_calls: list[dict[str, Any]],
        outcome: dict[str, Any],
        reward: float = 0.0,
        error_state: bool = False,
    ) -> None:
        self.memory.begin_task(prompt)
        self.memory.consolidate_task(
            trigger=prompt,
            plan=routes,
            tool_calls=tool_calls,
            outcome={"task_id": task_id, **outcome},
            reward=reward,
            error_state=error_state,
        )
        self.store.record_run("repo_engineer_task", {
            "task_id": task_id,
            "prompt": prompt,
            "routes": routes,
            "tool_calls": tool_calls,
            "outcome": outcome,
        })
        self.store.save()

    def ask(self, prompt: str) -> dict[str, Any]:
        prompt = prompt.strip()
        if not prompt or len(prompt) > 2_000:
            raise ValueError("prompt must be between 1 and 2000 characters")
        task_id = uuid.uuid4().hex
        routes = self._select_routes(prompt)
        evidence = {}
        tool_calls = []
        for route in routes:
            result = self._route(route, prompt)
            evidence[route] = result
            tool_calls.append({"tool": route, "ok": "error" not in result})
            self.memory.execute_step(route, result)
        report = {
            "task_id": task_id,
            "routes": routes,
            "evidence": evidence,
            "text": self._format_report(task_id, routes, evidence),
            "tool_calls": tool_calls,
            "feedback_pending": True,
        }
        self._persist_episode(
            task_id=task_id,
            prompt=prompt,
            routes=routes,
            tool_calls=tool_calls,
            outcome={"route_count": len(routes), "evidence_keys": sorted(evidence)},
            error_state=any("error" in result for result in evidence.values()),
        )
        return report

    def feedback(self, task_id: str, helpful: bool) -> dict[str, Any]:
        tasks = self.store.journal.entries(limit=500, kind="repo_engineer_task")
        task = next(
            (entry.get("payload", {}) for entry in reversed(tasks) if entry.get("payload", {}).get("task_id") == task_id),
            None,
        )
        if task is None:
            raise ValueError("unknown or expired engineering task")
        feedback_entries = self.store.journal.entries(limit=500, kind="repo_engineer_feedback")
        if any(entry.get("payload", {}).get("task_id") == task_id for entry in feedback_entries):
            raise ValueError("feedback already recorded for this task")
        routes = list(task.get("routes", []))
        reward = 1.0 if helpful else -1.0
        self._persist_episode(
            task_id=task_id,
            prompt=f"Operator feedback for engineering task {task_id}",
            routes=routes,
            tool_calls=task.get("tool_calls", []),
            outcome={"task_id": task_id, "helpful": helpful},
            reward=reward,
            error_state=not helpful,
        )
        self.store.record_run(
            "repo_engineer_feedback",
            {"task_id": task_id, "routes": routes, "helpful": helpful},
        )
        self.store.save()
        return {"task_id": task_id, "helpful": helpful, "route_feedback": self._feedback_scores()}

    def _path(self, raw_path: str) -> Path:
        candidate = (self.repo_root / raw_path).resolve()
        try:
            candidate.relative_to(self.repo_root)
        except ValueError as exc:
            raise ValueError("path must remain inside the repository") from exc
        if any(part in EXCLUDED_DIRS for part in candidate.parts):
            raise ValueError("path is inside an excluded generated or dependency directory")
        name = candidate.name.lower()
        if (
            name == ".env"
            or (name.startswith(".env.") and name != ".env.example")
            or name in {"id_rsa", "id_ed25519", "credentials.json", "secrets.json"}
            or candidate.suffix.lower() in SENSITIVE_SUFFIXES
        ):
            raise ValueError("sensitive files are not available to the repo engineer")
        return candidate

    def _list_files(self, directory: str) -> dict[str, Any]:
        base = self._path(directory or ".")
        if not base.is_dir():
            return {"error": "directory_not_found"}
        results = []
        for current, dirs, files in os.walk(base):
            dirs[:] = sorted(name for name in dirs if name not in EXCLUDED_DIRS)
            for name in sorted(files):
                path = Path(current) / name
                if path.suffix.lower() in {".py", ".ts", ".tsx", ".md", ".toml", ".json"}:
                    if name.lower() == ".env" or name.lower().startswith(".env."):
                        continue
                    results.append(path.relative_to(self.repo_root).as_posix())
                    if len(results) >= 200:
                        return {"files": results, "truncated": True}
        return {"files": results, "truncated": False}

    def _search_repo(self, query: str, directory: str) -> dict[str, Any]:
        query = query.strip()
        if not query or len(query) > 200:
            return {"error": "query_must_be_1_to_200_characters"}
        base = self._path(directory or ".")
        if not base.exists():
            return {"error": "directory_not_found"}
        if executable := shutil.which("rg"):
            command = [
                executable,
                "-n",
                "-F",
                "--no-heading",
                "--glob",
                "*.py",
                "--glob",
                "*.ts",
                "--glob",
                "*.tsx",
                "--glob",
                "*.md",
                "--glob",
                "*.toml",
                "--glob",
                "!**/.git/**",
                "--glob",
                "!**/node_modules/**",
                "--glob",
                "!**/.venv/**",
                "--glob",
                "!**/venv/**",
                "--glob",
                "!**/dist/**",
                "--glob",
                "!**/build/**",
                "--glob",
                "!**/__pycache__/**",
                "--glob",
                "!**/.pytest_cache/**",
                "--glob",
                "!**/.hypothesis/**",
                "--glob",
                "!**/.env",
                "--glob",
                "!**/.env.*",
                "--",
                query,
                base.relative_to(self.repo_root).as_posix() or ".",
            ]
            try:
                result = subprocess.run(
                    command,
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if result.returncode not in (0, 1):
                    return {"error": result.stderr[-1000:] or "search_failed"}
                return {
                    "matches": result.stdout[:MAX_TOOL_OUTPUT_CHARS],
                    "truncated": len(result.stdout) > MAX_TOOL_OUTPUT_CHARS,
                }
            except subprocess.TimeoutExpired:
                return {"error": "search_timed_out"}

        matches = []
        inspected = 0
        for current, dirs, files in os.walk(base):
            dirs[:] = [name for name in dirs if name not in EXCLUDED_DIRS]
            for name in files:
                path = Path(current) / name
                if (
                    path.suffix.lower() not in {".py", ".ts", ".tsx", ".md", ".toml"}
                    or name.lower() == ".env"
                    or name.lower().startswith(".env.")
                ):
                    continue
                inspected += 1
                if inspected > 2500:
                    return {"matches": matches, "truncated": True}
                try:
                    for line_number, line in enumerate(
                        path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                    ):
                        if query.casefold() in line.casefold():
                            matches.append(
                                f"{path.relative_to(self.repo_root).as_posix()}:{line_number}:{line[:300]}"
                            )
                            if len(matches) >= 60:
                                return {"matches": matches, "truncated": True}
                except OSError:
                    continue
        return {"matches": matches, "truncated": False}

    def _read_file(self, path: str, start_line: int, end_line: int) -> dict[str, Any]:
        target = self._path(path)
        if not target.is_file():
            return {"error": "file_not_found"}
        if target.stat().st_size > MAX_FILE_BYTES:
            return {"error": "file_too_large"}
        start = max(1, int(start_line))
        end = min(max(start, int(end_line)), start + MAX_FILE_LINES - 1)
        try:
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            return {"error": f"read_failed:{type(exc).__name__}"}
        return {
            "path": target.relative_to(self.repo_root).as_posix(),
            "start_line": start,
            "end_line": min(end, len(lines)),
            "content": "\n".join(lines[start - 1 : end])[:MAX_TOOL_OUTPUT_CHARS],
        }

    def _run_tests(self, target: str) -> dict[str, Any]:
        try:
            path = self._path(target)
        except ValueError as exc:
            return {"error": str(exc)}
        relative = path.relative_to(self.repo_root).as_posix()
        approved_root = relative.startswith("tests/") or relative.startswith(
            "chronus/mla1517_platform/python/"
        )
        if not approved_root or not path.is_file():
            return {"error": "test_target_not_allowed_or_not_found"}
        if not path.name.startswith("test_") or path.suffix.lower() != ".py":
            return {"error": "test_file_must_start_with_test_"}
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", relative, "-q", "--tb=short"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout[-8_000:],
                "stderr": result.stderr[-4_000:],
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "returncode": None,
                "stdout": str(exc.stdout or "")[-4_000:],
                "stderr": "focused test timed out after 180 seconds",
                "timed_out": True,
            }

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "list_repo_files":
            return self._list_files(str(arguments.get("directory", ".")))
        if name == "search_repo":
            return self._search_repo(
                str(arguments.get("query", "")), str(arguments.get("directory", "."))
            )
        if name == "read_repo_file":
            return self._read_file(
                str(arguments.get("path", "")),
                int(arguments.get("start_line", 1)),
                int(arguments.get("end_line", 80)),
            )
        if name == "run_focused_tests":
            return self._run_tests(str(arguments.get("target", "")))
        return {"error": "tool_not_allowed"}


__all__ = ["NATIVE_CAPABILITIES", "RepoEngineer"]
