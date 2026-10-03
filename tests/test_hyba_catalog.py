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


def test_uhd620_matches_on_its_reported_name_without_pci_evidence():
    """The device's own name must select its family, not a vendor fallback."""
    spec = catalog.find_spec("Intel(R) UHD Graphics 620", "Intel(R) Corporation")
    assert spec is not None
    assert spec.family == "intel-uhd-620"


def test_generic_graphics_never_beats_a_model_specific_rule():
    """"graphics" is a last resort: a named model always outranks it."""
    for name, family in (
        ("Intel(R) Iris Xe Graphics", "intel-iris-xe"),
        ("Intel(R) Arc Graphics", "intel-arc"),
        ("Intel(R) UHD Graphics 630", "intel-uhd-630"),
    ):
        spec = catalog.find_spec(name, "Intel(R) Corporation")
        assert spec is not None, name
        assert spec.family == family, name


def test_unlisted_gpu_is_generic_and_not_known():
    """A vendor string alone must not file a GPU under an unobserved model."""
    ident = identify.identify("Some Unlisted Intel GPU", "Intel(R) Corporation")
    assert ident.family == "intel-generic"
    assert ident.generic is True
    assert ident.known is False
    assert ident.match_evidence == ("generic-vendor:Intel",)
    assert "generic" in ident.as_dict()


def test_pci_evidence_outranks_a_name_alias():
    """The strongest evidence wins, regardless of catalog order."""
    spec = catalog.find_spec("NVIDIA H100 80GB HBM3", "NVIDIA", ("0x233a",))
    assert spec is not None
    assert spec.family == "nvidia-h100"


def test_vendor_conflict_is_respected():
    """A model whose vendor contradicts the observed one is never selected.

    The reported vendor still decides: a device claiming NVIDIA is reported as
    an unverified NVIDIA GPU, not as the Intel model its name resembles.
    """
    spec = catalog.find_spec("Intel(R) UHD Graphics 620", "NVIDIA")
    assert spec is not None
    assert spec.family == "nvidia-generic"
    assert spec.vendor == "NVIDIA"


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
