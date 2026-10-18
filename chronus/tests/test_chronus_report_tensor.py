import json
import sys
from types import SimpleNamespace

import chronus.report as report_module


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

    section = report_module._tensor_section()

    assert section["available"] is True
    assert section["last_execution_evidence"] == "Unavailable"


def test_tensor_section_prefers_sys_modules_entry(monkeypatch):
    """_tensor_section must honor the sys.modules stub (no hardware import)."""
    probe = SimpleNamespace(as_dict=lambda: {"available": False, "reason": "stubbed"})
    module = SimpleNamespace(probe=lambda: probe, _RUNTIME=None)
    monkeypatch.setitem(sys.modules, "chronus.tensor_compute", module)

    section = report_module._tensor_section()

    assert section["available"] is False
    assert section["reason"] == "stubbed"
    assert section["last_execution_evidence"] == "Unavailable"


def test_report_sections_carry_elapsed_ms(monkeypatch):
    """Every canonical section records elapsed_ms and stays JSON-safe."""
    monkeypatch.setattr(report_module, "_opencl_section", lambda: {"importable": False})
    monkeypatch.setattr(report_module, "_vendor_section", lambda: {"probes": []})
    monkeypatch.setattr(report_module, "_hasher_section", lambda: {"backend": "cpu"})
    monkeypatch.setattr(report_module, "_punch_section", lambda: {"use_opencl": False})
    monkeypatch.setattr(
        report_module, "_tensor_section", lambda: {"last_execution_evidence": "Unavailable"}
    )

    doc = report_module.report()

    assert set(doc) == {"opencl", "vendors", "hasher", "punch", "tensor"}
    for section in doc.values():
        assert isinstance(section["elapsed_ms"], int)
        assert section["elapsed_ms"] >= 0
    json.dumps(doc, default=str)


def test_report_document_envelope_keeps_canonical_sections(monkeypatch):
    """report_document stamps schema + time without breaking the 5-key contract."""
    monkeypatch.setattr(report_module, "_opencl_section", lambda: {"importable": False})
    monkeypatch.setattr(report_module, "_vendor_section", lambda: {"probes": []})
    monkeypatch.setattr(report_module, "_hasher_section", lambda: {"backend": "cpu"})
    monkeypatch.setattr(report_module, "_punch_section", lambda: {"use_opencl": False})
    monkeypatch.setattr(
        report_module, "_tensor_section", lambda: {"last_execution_evidence": "Unavailable"}
    )

    doc = report_module.report_document()

    assert doc["schema"] == report_module.REPORT_SCHEMA
    assert doc["generated_at"]
    sections = {key: doc[key] for key in ("opencl", "vendors", "hasher", "punch", "tensor")}
    assert len(sections) == 5


def test_report_exports_public_surface():
    assert report_module.__all__ == ["REPORT_SCHEMA", "report", "report_document", "main"]
    assert report_module.REPORT_SCHEMA == "chronus-report-v1"
