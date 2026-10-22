import pytest
from chronus.virtual_igpu.memory import VirtualMemoryPlane


def test_binary_payload_survives_restart_without_string_collision(tmp_path):
    root = tmp_path / "memory"
    memory = VirtualMemoryPlane(root)
    binary = memory.store(b"\x00\xffopaque", tenant="a")
    text = memory.store("b'\\x00\\xffopaque'", tenant="a")
    assert binary.content_id != text.content_id
    assert binary.logical_bytes == len(b"\x00\xffopaque")
    restored = VirtualMemoryPlane(root)
    assert restored.retrieve(binary.object_id, tenant="a") == b"\x00\xffopaque"
    assert restored.lookup(binary.object_id, tenant="a").payload == b"\x00\xffopaque"
    with pytest.raises(PermissionError):
        restored.retrieve(binary.object_id, tenant="b")


def test_store_detaches_caller_mutable_payload(tmp_path):
    memory = VirtualMemoryPlane(tmp_path)
    payload = {"values": [1, 2]}
    handle = memory.store(payload, tenant="a")
    payload["values"].append(3)
    assert memory.lookup(handle.object_id, tenant="a").payload == {"values": [1, 2]}
    assert memory.retrieve(handle.object_id, tenant="a") == {"values": [1, 2]}
