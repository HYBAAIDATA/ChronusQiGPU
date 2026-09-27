"""PYTHIA skill loader — loads SKILL.md files into her semantic memory.

This module discovers SKILL.md files in ``Intelligence/skills/`` and loads
them into PYTHIA's semantic memory as ``skill_<name>`` concepts. It uses
the OpenSkills SDK's progressive disclosure architecture:

- **Layer 1 (Metadata)**: the YAML frontmatter (name, description, tags) —
  always loaded for skill discovery.
- **Layer 2 (Instruction)**: the markdown body (when to use, instructions,
  safety rules) — loaded on demand when the skill is selected.
- **Layer 3 (Resources)**: referenced tools and scripts — loaded when
  the skill is executed.

For PYTHIA (an emergent intelligence, not an LLM agent), we load all three
layers into semantic memory so she can reason about which skill to use for
which task.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger("Intelligence.skill_loader")

SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")


@dataclass
class PythiaSkill:
    """A loaded PYTHIA skill (from SKILL.md)."""

    name: str
    description: str
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    # Layer 2: instruction body.
    instructions: str = ""
    # Layer 3: referenced tools.
    tools: List[str] = field(default_factory=list)
    # File path.
    path: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
            "instructions": (
                self.instructions[:200] + "..."
                if len(self.instructions) > 200
                else self.instructions
            ),
            "tools": self.tools,
            "path": self.path,
        }


def _parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from a SKILL.md file."""
    frontmatter: Dict[str, Any] = {}
    body = content
    # Match ---\n...\n---\n
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if match:
        fm_text = match.group(1)
        body = match.group(2).strip()
        # Simple YAML parsing (avoid pyyaml dependency for basic cases).
        for line in fm_text.split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()
                # Strip quotes.
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                # Parse tags as list.
                if key == "tags" and val.startswith("["):
                    val = [t.strip().strip("\"'") for t in val.strip("[]").split(",") if t.strip()]
                frontmatter[key] = val
    return frontmatter, body


def _extract_tools(body: str) -> List[str]:
    """Extract tool references from the SKILL.md body."""
    tools: List[str] = []
    # Match lines starting with - `module.path`
    for match in re.finditer(r"^- `\s*([^\s`]+)\s*`", body, re.MULTILINE):
        tools.append(match.group(1))
    return tools


def discover_skills(skills_dir: str = SKILLS_DIR) -> List[PythiaSkill]:
    """Discover all SKILL.md files in the skills directory."""
    skills: List[PythiaSkill] = []
    if not os.path.isdir(skills_dir):
        logger.warning("Skills directory not found: %s", skills_dir)
        return skills
    for entry in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, entry, "SKILL.md")
        if not os.path.isfile(skill_path):
            continue
        try:
            with open(skill_path, "r", encoding="utf-8") as f:
                content = f.read()
            fm, body = _parse_frontmatter(content)
            tools = _extract_tools(body)
            skill = PythiaSkill(
                name=fm.get("name", entry),
                description=fm.get("description", ""),
                version=fm.get("version", "1.0.0"),
                tags=(
                    fm.get("tags", []) if isinstance(fm.get("tags"), list) else [fm.get("tags", "")]
                ),
                instructions=body,
                tools=tools,
                path=skill_path,
            )
            skills.append(skill)
            logger.info("Discovered skill: %s (%s)", skill.name, skill.description[:60])
        except Exception as e:
            logger.warning("Failed to load skill %s: %s", entry, e)
    return skills


def seed_skill_knowledge(memory_system) -> Dict[str, Any]:
    """Seed PYTHIA's semantic memory with skill knowledge.

    Each skill is loaded as a ``skill_<name>`` concept with its description,
    instructions, tools, and tags as properties.
    """
    skills = discover_skills()
    sem = memory_system.semantic
    skills_added = 0
    for skill in skills:
        try:
            sem.add_concept(
                f"skill_{skill.name}",
                category="skill",
                definition=skill.description,
                properties={
                    "version": skill.version,
                    "tags": skill.tags,
                    "instructions": skill.instructions,
                    "tools": skill.tools,
                    "path": skill.path,
                },
                confidence=1.0,
                provenance="skill_loader",
            )
            skills_added += 1
            # Associate skill with the tools it references.
            for tool_path in skill.tools:
                # Extract tool name from path (last component).
                tool_name = tool_path.split(".")[-1].split("(")[0].strip()
                sem.add_association(
                    f"skill_{skill.name}",
                    f"tool_{tool_name}",
                    relation="uses_tool",
                    weight=0.8,
                )
        except Exception as e:
            logger.warning("Failed to seed skill %s: %s", skill.name, e)
    logger.info("PYTHIA skill knowledge seeded: %d skills", skills_added)
    return {
        "skills_seeded": skills_added,
        "total_skills": len(skills),
        "skills": [s.as_dict() for s in skills],
    }


def get_skill_summary() -> Dict[str, Any]:
    """Return a summary of discovered skills."""
    skills = discover_skills()
    return {
        "total_skills": len(skills),
        "skills": [s.as_dict() for s in skills],
    }


__all__ = [
    "PythiaSkill",
    "discover_skills",
    "seed_skill_knowledge",
    "get_skill_summary",
    "SKILLS_DIR",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (amplitude_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result
