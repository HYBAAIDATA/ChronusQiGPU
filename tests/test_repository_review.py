"""Native review admission, confinement, receipts and actual dispatch contracts."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from Intelligence.repository_review import ReviewPolicy, ReviewRejected, review_repository


def policy_for(files, **limits):
    return ReviewPolicy(
        tuple((path, hashlib.sha256(data).hexdigest()) for path, data in files.items()), **limits
    )


def place(root, files):
    for path, data in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def test_source_is_reviewed_never_executed_or_modified(tmp_path):
    sentinel = tmp_path / "was-executed"
    files = {
        "a.py": f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\nexec('x=1')\n".encode()
    }
    place(tmp_path, files)
    before = {p: (tmp_path / p).read_bytes() for p in files}
    result = review_repository(repo_root=tmp_path, policy=policy_for(files))
    assert result["status"] == "REVIEWED_READ_ONLY"
    assert result["semantic_verdict"] == "NOT_ESTABLISHED"
    assert result["finding_count"] == 1
    assert not sentinel.exists()
    assert before == {p: (tmp_path / p).read_bytes() for p in files}
    assert "touch" not in json.dumps(result)  # No source text returned.


def test_receipt_is_deterministic_and_content_bound(tmp_path):
    files = {"b.py": b"x = 1\n", "a.py": b"def f(): pass\ndef f(): pass\n"}
    place(tmp_path, files)
    first = review_repository(repo_root=tmp_path, policy=policy_for(files))
    second = review_repository(
        repo_root=tmp_path, policy=policy_for(dict(reversed(list(files.items()))))
    )
    assert first == second
    expected = first.pop("receipt_sha256")
    assert (
        expected
        == hashlib.sha256(
            json.dumps(first, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()
    )
    assert first["files"][0]["findings"] == [{"code": "REDEFINED_BINDING_REVIEW", "line": 2}]


def test_syntax_error_is_evidence_not_a_successful_test(tmp_path):
    files = {"a.py": b"def secret(:\n"}
    place(tmp_path, files)
    result = review_repository(repo_root=tmp_path, policy=policy_for(files))
    assert result["files"][0]["findings"] == [{"code": "PYTHON_SYNTAX_ERROR", "line": 1}]
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize(
    "path",
    [
        "../a.py",
        "/a.py",
        "a/../b.py",
        "a\\b.py",
        "a//b.py",
        ".env.py",
        ".git/a.py",
        "a.txt",
        "a\0.py",
    ],
)
def test_invalid_paths_are_refused(path):
    with pytest.raises(ReviewRejected):
        policy_for({path: b""})


@pytest.mark.parametrize(
    "manifest",
    [
        (),
        [],
        (("a.py", "0" * 63),),
        (("a.py", "G" * 64),),
        (("a.py", "0" * 64),) * 2,
        (("a.py", "0" * 64),) * 65,
    ],
)
def test_manifest_shape_duplicates_and_count_are_refused(manifest):
    with pytest.raises(ReviewRejected):
        ReviewPolicy(manifest)


@pytest.mark.parametrize(
    "limit,value",
    [
        ("max_file_bytes", True),
        ("max_file_bytes", 0),
        ("max_file_bytes", 262145),
        ("max_total_bytes", 1048577),
        ("max_findings", 129),
        ("max_findings", 1.2),
    ],
)
def test_resource_domains_are_exact_and_bounded(limit, value):
    with pytest.raises(ReviewRejected):
        policy_for({"a.py": b""}, **{limit: value})


def test_hash_mismatch_refuses_without_receipt(tmp_path):
    files = {"a.py": b"x=1"}
    place(tmp_path, files)
    (tmp_path / "a.py").write_bytes(b"x=2")
    with pytest.raises(ReviewRejected, match="approved manifest"):
        review_repository(repo_root=tmp_path, policy=policy_for(files))


def test_missing_path_refuses(tmp_path):
    with pytest.raises(ReviewRejected, match="unsafe or unreadable"):
        review_repository(repo_root=tmp_path, policy=policy_for({"a.py": b""}))


@pytest.mark.parametrize("kind", ["file", "parent", "root"])
def test_symlinks_are_refused(tmp_path, kind):
    real = tmp_path / "real"
    real.mkdir()
    files = {"a.py": b"x=1"}
    place(real, files)
    root = tmp_path / "scope"
    root.mkdir()
    path = "a.py"
    try:
        if kind == "file":
            (root / path).symlink_to(real / path)
        elif kind == "parent":
            (root / "nested").symlink_to(real, target_is_directory=True)
            path = "nested/a.py"
        else:
            root.rmdir()
            root.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation requires privilege on Windows")
    with pytest.raises(ReviewRejected):
        review_repository(repo_root=root, policy=policy_for({path: b"x=1"}))


def test_fifo_does_not_block_or_get_read(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation requires os.mkfifo")
    os.mkfifo(tmp_path / "a.py")
    with pytest.raises(ReviewRejected, match="nonregular"):
        review_repository(repo_root=tmp_path, policy=policy_for({"a.py": b""}))


@pytest.mark.parametrize(
    "limits", [{"max_file_bytes": 2}, {"max_total_bytes": 6}, {"max_findings": 1}]
)
def test_budget_exhaustion_has_no_partial_receipt(tmp_path, limits):
    files = {"a.py": b"eval('0')\n", "b.py": b"eval('1')\n"}
    place(tmp_path, files)
    with pytest.raises(ReviewRejected):
        review_repository(repo_root=tmp_path, policy=policy_for(files, **limits))


def test_python_declared_encoding_is_supported(tmp_path):
    files = {"a.py": b"# coding: latin-1\nname='caf\xe9'\n"}
    place(tmp_path, files)
    assert review_repository(repo_root=tmp_path, policy=policy_for(files))["finding_count"] == 0


def test_no_implicit_permissions_or_callable_extension(tmp_path):
    with pytest.raises(ReviewRejected):
        review_repository(repo_root=tmp_path, policy={})
    with pytest.raises(TypeError):
        review_repository(
            repo_root=tmp_path, policy=policy_for({"a.py": b""}), callback=lambda: True
        )


def test_actual_dispatch_runs_native_adapter_with_discovered_local_skill(tmp_path):
    from Intelligence.salamander import SalamanderEngine
    from Intelligence.skill_loader import load_skills

    skills_dir = Path(__file__).resolve().parents[1] / "Intelligence" / "skills"
    skills = load_skills(str(skills_dir))
    assert "repository-review" in skills
    engine = SalamanderEngine.__new__(SalamanderEngine)  # Constructor deliberately excluded.
    engine.skills = skills
    files = {"a.py": b"x=1"}
    place(tmp_path, files)
    engine.repo_root = tmp_path
    engine.repository_review_policies = {"fixture": policy_for(files)}
    result = engine.execute_skill("repository-review", review_id="fixture")
    assert result["status"] == "REVIEWED_READ_ONLY"
    assert engine.skills["repository-review"].name == "repository-review"


def test_dispatch_refuses_unequipped_and_unknown_skill():
    from Intelligence.salamander import SalamanderEngine
    from Intelligence.skill_loader import PythiaSkill

    engine = SalamanderEngine.__new__(SalamanderEngine)
    engine.skills = {"other": PythiaSkill("other", "guidance", instructions="Do not execute me")}
    engine.repo_root = Path(__file__).resolve().parents[1]
    with pytest.raises(KeyError, match="not equipped"):
        engine.execute_skill("repository-review")
    assert engine.execute_skill("other")["status"] == "GUIDANCE"
    with pytest.raises(KeyError):
        engine.execute_skill("nonexistent")
