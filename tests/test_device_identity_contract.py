from __future__ import annotations

import pytest

from mining.bitcoin_hasher import _select_opencl_device


class _DeviceType:
    GPU = 1


class _Device:
    def __init__(self, name: str, vendor: str = "Intel(R) Corporation", device_type: int = 1):
        self.name = name
        self.vendor = vendor
        self.type = device_type


class _Platform:
    def __init__(self, devices):
        self._devices = devices

    def get_devices(self):
        return self._devices


class _CL:
    device_type = _DeviceType()

    def __init__(self, devices):
        self._platforms = [_Platform(devices)]

    def get_platforms(self):
        return self._platforms


def test_exact_uhd620_identity_is_selected(monkeypatch):
    target = _Device("Intel(R) Graphics [0x5917]")
    monkeypatch.setenv("HYBA_REQUIRE_HYBA", "1")
    monkeypatch.setenv("HYBA_DEVICE_VENDOR", "Intel")
    monkeypatch.setenv("HYBA_DEVICE_PCI_IDS", "0x5917")
    monkeypatch.setenv("HYBA_DEVICE_NAME", "Intel(R) Graphics [0x5917]")
    selected = _select_opencl_device(_CL([_Device("Intel Iris Xe [0x9a49]"), target]), True)
    assert selected is target


def test_wrong_pci_identity_fails_closed(monkeypatch):
    monkeypatch.setenv("HYBA_REQUIRE_HYBA", "1")
    monkeypatch.setenv("HYBA_DEVICE_VENDOR", "Intel")
    monkeypatch.setenv("HYBA_DEVICE_PCI_IDS", "0x5917")
    monkeypatch.setenv("HYBA_DEVICE_NAME", "Intel(R) Graphics [0x5917]")
    with pytest.raises(RuntimeError, match="identity gate rejected"):
        _select_opencl_device(_CL([_Device("Intel Iris Xe [0x9a49]")]), True)
