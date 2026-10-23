"""Real local signatures/files; TEST authority is never production acceptance."""

import base64
import hashlib
import json
from pathlib import Path
import sys
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from hyba_turing_service import main as entrypoint
from hyba_turing_service.control import Unavailable, canonical
from hyba_turing_service.release import GATES
from test_release_scope import config_file


@pytest.fixture
def approved_config(tmp_path):
    path = config_file(tmp_path)
    config = json.loads(path.read_text())
    root = tmp_path / "approval"
    root.mkdir()
    evidence = b"TEST fixture, not deployment qualification"
    (root / "evidence.txt").write_bytes(evidence)
    key = Ed25519PrivateKey.generate()
    config["approval_public_key"] = base64.b64encode(
        key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    ).decode()
    config["approval_bundle"] = str(root)
    now = int(time.time())
    gate = dict(
        state="PASS",
        reviewer="TEST-REVIEWER",
        executed_at=now,
        artifact="evidence.txt",
        sha256=hashlib.sha256(evidence).hexdigest(),
    )
    manifest = dict(
        schema="turing.promotion.v1",
        billing_scope="deferred",
        commit=config["source_commit"],
        issued_at=now,
        expires_at=now + 60,
        gates={name: gate for name in GATES},
    )
    (root / "approval.json").write_text(
        json.dumps(
            dict(
                manifest=manifest,
                signature=base64.b64encode(key.sign(canonical(manifest).encode())).decode(),
            )
        )
    )
    # Preflight must work with NO access to runtime signing/session keys.
    for field in ("customer_key_file", "operator_key_file", "session_key_file"):
        Path(config[field]).unlink()
    path.write_text(json.dumps(config))
    return path, config


def invoke(monkeypatch, path, command, *options):
    monkeypatch.setattr(sys, "argv", ["turing-service", command, "--config", str(path), *options])
    entrypoint.main()


@pytest.mark.parametrize("mode", ["production", "controlled-pilot"])
def test_release_check_is_read_only_without_runtime_keys(approved_config, monkeypatch, mode):
    path, config = approved_config
    config["mode"] = mode
    path.write_text(json.dumps(config))
    before = {
        p.relative_to(path.parent): p.read_bytes() for p in path.parent.rglob("*") if p.is_file()
    }
    invoke(monkeypatch, path, "release-check")
    after = {
        p.relative_to(path.parent): p.read_bytes() for p in path.parent.rglob("*") if p.is_file()
    }
    assert after == before
    assert not Path(config["database"]).exists()
    assert not Path(config["custody_root"]).exists()


@pytest.mark.parametrize("command", ["release-check", "serve", "worker"])
def test_missing_approval_fails_before_secrets_or_state(approved_config, monkeypatch, command):
    path, config = approved_config
    (Path(config["approval_bundle"]) / "approval.json").unlink()
    with pytest.raises(Unavailable, match="signed promotion evidence"):
        invoke(monkeypatch, path, command)
    assert not Path(config["database"]).exists()
    assert not Path(config["custody_root"]).exists()


@pytest.mark.parametrize("command", ["release-check", "serve", "worker"])
def test_wrong_image_fails_before_secrets_or_state(approved_config, monkeypatch, command):
    path, config = approved_config
    Path(config["build_identity_file"]).write_text("b" * 40)
    with pytest.raises(ValueError, match="running image source"):
        invoke(monkeypatch, path, command)
    assert not Path(config["database"]).exists()


def test_publication_still_requires_its_additional_gate(approved_config, monkeypatch):
    path, config = approved_config
    with pytest.raises(Unavailable, match="signed promotion evidence"):
        invoke(monkeypatch, path, "release-check", "--publication")
    assert not Path(config["database"]).exists()


@pytest.mark.parametrize("command", ["serve", "worker"])
def test_approved_startup_still_requires_runtime_secrets(approved_config, monkeypatch, command):
    path, config = approved_config
    with pytest.raises(FileNotFoundError) as error:
        invoke(monkeypatch, path, command)
    assert error.value.filename == config["customer_key_file"]
    assert not Path(config["database"]).exists()


def test_pilot_is_not_implicitly_promoted(approved_config, monkeypatch):
    path, config = approved_config
    config["mode"] = "controlled-pilot"
    path.write_text(json.dumps(config))
    (Path(config["approval_bundle"]) / "approval.json").unlink()
    # Pilot runtime still requires secrets; explicit release-check still rejects.
    with pytest.raises(FileNotFoundError):
        invoke(monkeypatch, path, "worker")
    with pytest.raises(Unavailable):
        invoke(monkeypatch, path, "release-check")
    assert not Path(config["database"]).exists()


def test_deferred_billing_refuses_without_touching_secrets(approved_config, monkeypatch):
    path, config = approved_config
    with pytest.raises(ValueError, match="billing is deferred"):
        invoke(monkeypatch, path, "billing")
    assert not Path(config["database"]).exists()


@pytest.mark.parametrize("command", ["release-check", "serve", "worker"])
def test_rejected_startup_does_not_initialize_database_with_valid_keys(
    tmp_path, monkeypatch, command
):
    path = config_file(tmp_path)
    config = json.loads(path.read_text())
    # Image matches, keys are present, but there is no signed approval bundle.
    config["approval_bundle"] = str(tmp_path / "absent-approval")
    path.write_text(json.dumps(config))
    with pytest.raises(Unavailable):
        invoke(monkeypatch, path, command)
    assert not Path(config["database"]).exists()
    assert not Path(config["custody_root"]).exists()
