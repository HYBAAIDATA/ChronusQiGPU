"""THESEUS custody tenant/record isolation (production review finding R02).

Regression tests for the 2026-10-04 OVID/THESEUS/Chronus review:
distinct tenant ids must never share a directory, record ids are bounded
identifiers rather than path fragments, and a validly MAC'd envelope is
bound to the tenant and record id it was written for.
"""

from __future__ import annotations

import json
import os
import shutil

import pytest

from aethel.enterprise.custody import EnterpriseCustody
from aethel.enterprise.errors import (
    AuthenticityError,
    InvalidRecordIdError,
    UnrecoverableCustodyError,
)

REFUSED = (AuthenticityError, UnrecoverableCustodyError)

KEY = b"theseus-r02-isolation-key-32bytes!!"


def _custody(root, tenant="default"):
    return EnterpriseCustody(root, tenant=tenant, hmac_key=KEY)


def test_distinct_tenants_never_share_a_directory(tmp_path):
    names = ["a/b", "a?b", "a_b", "a b", "a\\b", "A_B"]
    roots = set()
    for name in names:
        custody = _custody(tmp_path, name)
        try:
            roots.add(custody.tenant_root.resolve())
        finally:
            custody.close()
    assert len(roots) == len(names)
    for root in roots:
        assert root.parent == (tmp_path / "tenants").resolve()


def test_safe_tenant_ids_keep_their_existing_directory(tmp_path):
    custody = _custody(tmp_path, "acme-prod_01")
    try:
        assert custody.tenant_root == tmp_path / "tenants" / "acme-prod_01"
    finally:
        custody.close()


def test_colliding_tenants_cannot_read_each_others_records(tmp_path):
    first = _custody(tmp_path, "a/b")
    first.put(b"tenant a/b secret", record_id="shared-name")
    first.close()
    second = _custody(tmp_path, "a?b")
    try:
        with pytest.raises(KeyError):
            second.get("shared-name")
    finally:
        second.close()


@pytest.mark.parametrize(
    "record_id",
    [
        "../escape",
        "..",
        "a/../../b",
        "/etc/passwd",
        "sub/dir",
        "back\\slash",
        ".hidden",
        "x" * 129,
        "nul\x00byte",
        "colon:stream",
    ],
)
def test_record_ids_are_bounded_identifiers(tmp_path, record_id):
    custody = _custody(tmp_path)
    try:
        with pytest.raises(InvalidRecordIdError):
            custody.put(b"payload", record_id=record_id)
        with pytest.raises(KeyError):
            custody.get(record_id)
    finally:
        custody.close()
    assert not any(p.name == "passwd" for p in tmp_path.rglob("*"))


def test_invalid_record_id_reads_as_not_found(tmp_path):
    custody = _custody(tmp_path)
    try:
        with pytest.raises(KeyError):
            custody.get("../../outside")
    finally:
        custody.close()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_symlinked_record_file_is_refused(tmp_path):
    custody = _custody(tmp_path)
    try:
        custody.put(b"real", record_id="real")
        outside = tmp_path / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        (custody.primary_dir / "planted.json").symlink_to(outside)
        with pytest.raises(KeyError):
            custody.get("planted")
    finally:
        custody.close()


def test_envelope_copied_from_another_tenant_is_rejected(tmp_path):
    source = _custody(tmp_path, "tenant-a")
    source.put(b"tenant-a payload", record_id="invoice-1")
    src_primary = source._primary_path("invoice-1")
    src_replica = source._replica_path("invoice-1")
    source.close()

    target = _custody(tmp_path, "tenant-b")
    try:
        shutil.copy2(src_primary, target.primary_dir / "invoice-1.json")
        shutil.copy2(src_replica, target.replica_dir / "invoice-1.json")
        # Same MAC key, valid MAC: still refused, because the envelope is
        # bound to tenant-a.
        assert json.loads(src_primary.read_text())["tenant"] == "tenant-a"
        with pytest.raises(REFUSED):
            target.get("invoice-1")
    finally:
        target.close()


def test_envelope_renamed_to_another_record_id_is_rejected(tmp_path):
    custody = _custody(tmp_path)
    try:
        custody.put(b"original", record_id="alpha")
        for directory in (custody.primary_dir, custody.replica_dir):
            shutil.copy2(directory / "alpha.json", directory / "beta.json")
        with pytest.raises(REFUSED):
            custody.get("beta")
        assert custody.get("alpha") == b"original"
    finally:
        custody.close()
