"""Salamander's skill grafts: known source, compatible licence, one at a time."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from Intelligence import skill_graft
from Intelligence.skill_graft import Graft, GraftRejected, graft, graft_next, verify, verify_one
from Intelligence.skill_loader import _parse_frontmatter, load_skills, skills_for

MIT = "MIT License\n\nCopyright (c) 2025 Upstream\n\nPermission is hereby granted, free of charge, ...\n"
UPSTREAM = "https://example.invalid/upstream"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _skill(name: str, body: str = "Find the root cause first.") -> str:
    return f"---\nname: {name}\ndescription: Use when {name} applies\n---\n\n# {name}\n\n{body}\n"


@pytest.fixture()
def upstream(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "upstream"
    for name in ("alpha", "beta"):
        (repo / "skills" / name).mkdir(parents=True)
        (repo / "skills" / name / "SKILL.md").write_text(_skill(name))
    (repo / "skills" / "alpha" / "notes.md").write_text("reviewed upstream\n")
    (repo / "LICENSE").write_text(MIT)
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "skills")
    return repo, _git(repo, "rev-parse", "HEAD")


def _spec(commit: str, name: str = "alpha", **overrides) -> Graft:
    fields = dict(
        name=name,
        repo=UPSTREAM,
        commit=commit,
        path=f"skills/{name}",
        licence="MIT",
        licence_file="LICENSE",
        applies_to=("repair",),
    )
    import hashlib

    expected = {
        "LICENSE": hashlib.sha256(MIT.encode()).hexdigest(),
        "SKILL.md": hashlib.sha256(_skill(name).encode()).hexdigest(),
    }
    if name == "alpha":
        expected["notes.md"] = hashlib.sha256(b"reviewed upstream\n").hexdigest()
    fields["manifest_sha256"] = skill_graft.manifest_digest(expected)
    fields.update(overrides)
    return Graft(**fields)


def test_a_graft_is_taken_whole_from_the_commit_not_the_working_tree(upstream, tmp_path):
    repo, commit = upstream
    (repo / "skills" / "alpha" / "SKILL.md").write_text(_skill("alpha", "UNREVIEWED EDIT"))
    skills = tmp_path / "skills"
    skills.mkdir()
    record = graft(_spec(commit), repo, skills)

    grafted = skills / "alpha"
    assert "UNREVIEWED EDIT" not in (grafted / "SKILL.md").read_text()
    assert (grafted / "LICENSE").read_text() == MIT  # the licence travels with the skill
    assert sorted(record["files"]) == ["LICENSE", "SKILL.md", "notes.md"]
    assert (record["commit"], record["licence_file"]) == (commit, "LICENSE")
    assert verify_one(grafted, _spec(commit)) == []
    assert graft(_spec(commit), repo, skills) == record  # the same graft again: unchanged
    assert not list(skills.glob(".graft-*"))


def test_a_graft_that_changes_is_rejected_and_never_equipped(upstream, tmp_path, monkeypatch):
    repo, commit = upstream
    monkeypatch.setattr(skill_graft, "GRAFT_PLAN", (_spec(commit),))
    skills = tmp_path / "skills"
    skills.mkdir()
    graft(_spec(commit), repo, skills)
    equipped = load_skills(str(skills))["alpha"]
    assert equipped.provenance["commit"] == commit and equipped.applies_to == ["repair"]
    assert [s.name for s in skills_for("repair", str(skills))] == ["alpha"]

    (skills / "alpha" / "notes.md").write_text("edited in place\n")
    (skills / "alpha" / "extra.py").write_text("print('hi')\n")
    (skills / "alpha" / "LICENSE").unlink()
    problems = verify(skills)["alpha"]
    assert "notes.md: changed since it was grafted" in problems
    assert "extra.py: not part of the graft" in problems
    assert "LICENSE: missing" in problems
    assert "alpha" not in load_skills(str(skills))


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"licence": "Apache-2.0"}, "is not the Apache-2.0 licence"),
        ({"licence": "source-available"}, "is not graftable"),
        ({"path": "skills/beta"}, "must name itself 'alpha'"),
        ({"commit": "f" * 40}, "git ls-tree -r failed"),
        ({"path": "skills/missing"}, "has no SKILL.md"),
    ],
)
def test_incompatible_or_mislabelled_tissue_is_refused(upstream, tmp_path, overrides, reason):
    repo, commit = upstream
    skills = tmp_path / "skills"
    skills.mkdir()
    with pytest.raises(GraftRejected, match=reason):
        graft(replace(_spec(commit), **overrides), repo, skills)
    assert list(skills.iterdir()) == []  # nothing half-grafted is left behind


def test_a_local_skill_is_never_replaced_by_a_graft(upstream, tmp_path):
    repo, commit = upstream
    local = tmp_path / "skills" / "alpha"
    local.mkdir(parents=True)
    (local / "SKILL.md").write_text(_skill("alpha", "ours"))
    with pytest.raises(GraftRejected, match="local skill"):
        graft(_spec(commit), repo, tmp_path / "skills")
    assert "ours" in (local / "SKILL.md").read_text()


def test_grafts_are_taken_one_at_a_time_and_halt_on_a_rejected_one(upstream, tmp_path, monkeypatch):
    from chronus.mla1517.knowledge import KnowledgeFabric

    repo, commit = upstream
    monkeypatch.setattr(skill_graft, "GRAFT_PLAN", (_spec(commit), _spec(commit, "beta")))
    skills = tmp_path / "skills"
    skills.mkdir()
    fabric = KnowledgeFabric()
    sources = {UPSTREAM: repo}

    assert graft_next(sources, skills, fabric)["name"] == "alpha"
    assert sorted(p.name for p in skills.iterdir()) == ["alpha"]
    assert graft_next(sources, skills, fabric)["name"] == "beta"
    assert graft_next(sources, skills, fabric) is None  # the plan has taken
    fact = fabric.observe("salamander.skill.beta")
    assert (fact.evidence, fact.value["commit"], fact.value["files"]) == ("declared", commit, 2)

    (skills / "alpha" / "SKILL.md").write_text(_skill("alpha", "tampered"))
    with pytest.raises(GraftRejected, match="grafts are rejected"):
        graft_next(sources, skills, fabric)
    announced = skill_graft.announce(KnowledgeFabric(), skills)
    assert [f.topic for f in announced] == ["salamander.skill.beta"]  # never the rejected one

    monkeypatch.setattr(skill_graft, "GRAFT_PLAN", (_spec(commit, "gamma"),))
    with pytest.raises(GraftRejected, match="no local checkout"):
        graft_next({}, tmp_path / "fresh")


def test_the_repository_grafts_verify_against_the_plan():
    grafts = verify()
    assert grafts
    equipped = load_skills(str(skill_graft.SKILLS_DIR))
    for name, problems in grafts.items():
        retired = (skill_graft.SKILLS_DIR / name / "DEPRECATED.md").exists()
        if retired:
            # Retired instructions are not silently re-admitted by ignoring
            # the extra file or rewriting the pinned upstream manifest.
            expected = sorted(
                f"{p.relative_to(skill_graft.SKILLS_DIR / name).as_posix()}: not part of the graft"
                for p in (skill_graft.SKILLS_DIR / name).rglob("DEPRECATED.md")
            )
            assert sorted(problems) == expected
            assert name not in equipped
        else:
            assert problems == []
    plan = [spec.name for spec in skill_graft.GRAFT_PLAN]
    # Grafted in plan order: a prefix of the plan, nothing outside it.
    assert list(grafts) == sorted(plan[: len(grafts)])
    attributes = (REPO_ROOT / ".gitattributes").read_text()
    assert "Intelligence/skills/** -text" in attributes  # no EOL rewrite on checkout
    for name in grafts:
        skill_md = (skill_graft.SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        assert _parse_frontmatter(skill_md)[0]["name"] == name


def test_salamander_repairs_with_the_grafted_discipline():
    from Intelligence.self_healing.self_repair import (
        ClassifiedFailure,
        PytestFailure,
        _build_repair_prompt,
    )

    failure = PytestFailure("tests/t.py::t", "tests/t.py", 3, "failure", "boom", "Trace", "suite")
    cf = ClassifiedFailure(failure, "unclassified", "n/a", "no rule applies")
    prompt = _build_repair_prompt(cf, "x = 1\n", "tests/t.py")
    for name in ("systematic-debugging", "verification-before-completion"):
        assert f"### Skill: {name}" not in prompt  # explicitly retired grafts
    assert "Respond in exactly two parts" in prompt


def test_salamander_hands_back_guidance_not_a_claimed_execution():
    from Intelligence.salamander import SalamanderEngine

    engine = SalamanderEngine()
    with pytest.raises(KeyError):
        engine.execute_skill("verification-before-completion")
    result = engine.execute_skill("assess-landscape")
    assert result["status"] == "GUIDANCE"
    assert result["instructions"]
    assert result["skill"] == "assess-landscape"


def test_repair_prompt_includes_a_verified_graft(upstream, tmp_path, monkeypatch):
    from Intelligence import skill_loader
    from Intelligence.self_healing.self_repair import ClassifiedFailure, PytestFailure, _build_repair_prompt
    repo, commit = upstream
    monkeypatch.setattr(skill_graft, "GRAFT_PLAN", (_spec(commit),))
    skills = tmp_path / "skills"
    skills.mkdir()
    graft(_spec(commit), repo, skills)
    original = skill_loader.skills_for
    monkeypatch.setattr(skill_loader, "skills_for", lambda purpose: original(purpose, str(skills)))
    failure = PytestFailure("tests/t.py::t", "tests/t.py", 3, "failure", "boom", "Trace", "suite")
    prompt = _build_repair_prompt(ClassifiedFailure(failure, "unclassified", "n/a", "none"), "x=1", "tests/t.py")
    assert "### Skill: alpha (from https://example.invalid/upstream@" in prompt
    assert "Find the root cause first." in prompt
