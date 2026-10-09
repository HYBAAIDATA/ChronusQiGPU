"""Keep mathematical placement intact under long Windows storage roots."""

from __future__ import annotations

import pytest

from aethel.enterprise.lifecycle import CompositionRoot
from aethel.filesystem_paths import windows_extended_path
from aethel.storage_topology import TheseusPhysicalStore, derive_storage_address


@pytest.mark.parametrize(
    "path,expected",
    [
        (r"C:\Users\name\Temp\..\storage", r"\\?\C:\Users\name\storage"),
        (r"\\server\share\folder", r"\\?\UNC\server\share\folder"),
        (r"\\?\C:\storage", r"\\?\C:\storage"),
        (r"\\?\UNC\server\share\folder", r"\\?\UNC\server\share\folder"),
    ],
)
def test_windows_root_encoding(path, expected):
    assert windows_extended_path(path) == expected


@pytest.mark.parametrize("path", [r"relative\path", r"C:relative", r"\rooted", r"\\.\device"])
def test_windows_root_rejects_relative_and_device_paths(path):
    with pytest.raises(ValueError):
        windows_extended_path(path)


def test_long_root_roundtrip_replica_heal_and_custody_reopen(tmp_path):
    # Each segment is portable; the complete root and canonical leaf exceed MAX_PATH.
    root = tmp_path.joinpath(*["long-storage-root-" + str(i) + "x" * 35 for i in range(5)])
    payload = b"long-root canonical mathematical address"
    physical = TheseusPhysicalStore(root / "blocks")
    address = physical.commit(payload, tenant_id="tenant-1", scope="long-path-test")
    assert address == derive_storage_address(payload, tenant_id="tenant-1", scope="long-path-test")
    assert len(str(physical.primary_path(address))) > 260
    physical.primary_path(address).unlink()
    assert physical.read(address) == payload
    assert physical.verify(address, payload)

    lifecycle = CompositionRoot(root / "custody", tenant="tenant-1", hmac_key=b"k" * 32)
    lifecycle.start()
    try:
        binding = lifecycle.data_port("euclid").put("long-path-test", payload)
    finally:
        lifecycle.stop()
    lifecycle.start()
    try:
        assert lifecycle.data_port("euclid").read(binding.binding_id) == payload
        assert lifecycle.fabric.verify(binding.binding_id)["passed"]
    finally:
        lifecycle.stop()
