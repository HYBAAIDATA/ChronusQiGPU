"""Vendor catalog + dispatcher regression tests (no GPU required)."""

from hyba import catalog, identify
from hyba.dispatch import rank_devices


class _Device:
    def __init__(self, name, vendor="Intel(R) Corporation", dtype=4, cus=24):
        self.name = name
        self.vendor = vendor
        self.type = dtype
        self.max_compute_units = cus


class _Platform:
    def __init__(self, devices, pname="Intel(R) OpenCL HD Graphics"):
        self._devices = devices
        self.name = pname

    def get_devices(self):
        return self._devices


class _Type:
    GPU = 4


class _CL:
    device_type = _Type()

    def __init__(self, devices):
        self._devices = devices

    def get_platforms(self):
        return [_Platform(self._devices)]


def test_uhd620_identifies_as_intel_family():
    """UHD 620 + 0x5917 resolves to the Intel reference family."""
    spec = catalog.find_spec("Intel(R) UHD Graphics 620", "Intel(R) Corporation", ("0x5917",))
    assert spec is not None
    assert spec.family == "intel-uhd-620"
    assert spec.dispatch == "opencl"


def test_h100_identifies_with_pci_evidence():
    """H100 + 0x233a resolves to the NVIDIA datacenter family."""
    spec = catalog.find_spec("NVIDIA H100", "NVIDIA", ("0x233a",))
    assert spec is not None
    assert spec.family == "nvidia-h100"
    assert spec.dispatch == "cuda"


def test_mi300x_identifies_with_pci_evidence():
    """MI300X resolves to the AMD/HPE datacenter family."""
    spec = catalog.find_spec("AMD MI300X", "AMD", ("0x74a1",))
    assert spec is not None
    assert spec.family == "amd-mi300x"


def test_unknown_device_reports_not_known():
    """Unknown silicon is reported honestly, never invented."""
    ident = identify.identify("Mystery GPU 9000", "MysteryCorp")
    assert ident.known is False
    assert ident.family is None
    assert ident.dispatch == "cpu"


def test_rank_prefers_hyba_alias_then_gpu(monkeypatch):
    """HYBA-alias device wins; otherwise first GPU wins."""
    import hyba.dispatch as dispatch

    monkeypatch.setenv("HYBA_DEVICE_ALIAS", "hyba-mla1517,hyba_mla1517,mla1517,hyba")
    monkeypatch.setenv("HYBA_REQUIRE_HYBA", "0")
    devs = [_Device("Some CPU Device", "Intel", 2), _Device("Intel(R) UHD Graphics 620")]
    ranked = rank_devices(_CL(devs))
    assert ranked[0].name == "Intel(R) UHD Graphics 620"
    assert ranked[0].family == "intel-uhd-620"
    assert ranked[0].known is True
    assert dispatch.select(_CL(devs)).name == "Intel(R) UHD Graphics 620"
