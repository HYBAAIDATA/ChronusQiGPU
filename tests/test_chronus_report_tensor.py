import sys
from types import SimpleNamespace


def test_tensor_report_is_evidence_first(monkeypatch):
    probe = SimpleNamespace(
        as_dict=lambda: {
            "available": True,
            "device_id": "opencl:intel:uhd",
            "device_name": "UHD",
        }
    )
    module = SimpleNamespace(probe=lambda: probe, _RUNTIME=None)
    monkeypatch.setitem(sys.modules, "chronus.tensor_compute", module)
    import chronus
    monkeypatch.setattr(chronus, "tensor_compute", module, raising=False)
    from chronus.report import _tensor_section

    section = _tensor_section()
    assert section["available"] is True
    assert section["last_execution_evidence"] == "Unavailable"