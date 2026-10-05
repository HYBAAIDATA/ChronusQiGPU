from __future__ import annotations

import pytest

from aethel.enterprise.lifecycle import CompositionRoot


@pytest.fixture()
def root(tmp_path):
    lifecycle = CompositionRoot(
        tmp_path / "organism-custody",
        hmac_key=b"entangled-lifecycle-test-key-32bytes",
        allow_insecure_dev_key=True,
    )
    try:
        yield lifecycle
    finally:
        lifecycle.stop()


def test_shared_fabric_exists_before_consumers_start(root):
    observed = {}

    def start_consumer():
        observed["fabric"] = root.fabric
        observed["custody"] = root.custody
        observed["ready"] = root.fabric is not None and root.custody is not None

    root.register_consumer("pythia", start_consumer, lambda: None)
    custody = root.start()

    assert observed["ready"] is True
    assert observed["fabric"] is root.fabric
    assert observed["custody"] is custody
    assert root.fabric.custody is custody


def test_every_port_uses_same_fabric_and_same_theseus_custody(root):
    custody = root.start()
    pythia = root.data_port("pythia")
    turing = root.data_port("turing")
    salamander = root.data_port("salamander")
    al_haras = root.data_port("al_haras")

    assert pythia.fabric is turing.fabric is salamander.fabric is al_haras.fabric
    assert pythia.fabric is root.fabric
    assert root.fabric.custody is custody

    binding = pythia.put(
        "shared_observation",
        {"source": "pythia", "value": 17},
        share_with=("turing", "salamander", "al_haras"),
    )
    assert turing.read(binding.binding_id) == pythia.read(binding.binding_id)
    assert salamander.read(binding.binding_id) == pythia.read(binding.binding_id)
    assert al_haras.read(binding.binding_id) == pythia.read(binding.binding_id)


def test_readiness_reports_shared_entangled_custody(root):
    root.start()
    status = root.readiness()

    assert status["ready"] is True
    assert status["entangled_custody"]["theseus_owner"] == "theseus"
    assert status["entangled_custody"]["ovid_owner"] == "ovid"
    assert status["entangled_custody"]["bindings"] == 0


def test_data_port_fails_closed_before_start(tmp_path):
    lifecycle = CompositionRoot(
        tmp_path / "not-started",
        hmac_key=b"entangled-lifecycle-test-key-32bytes",
        allow_insecure_dev_key=True,
    )
    with pytest.raises(RuntimeError, match="not started"):
        lifecycle.data_port("pythia")


def test_stop_releases_shared_references(root):
    root.start()
    root.stop()

    assert root.fabric is None
    assert root.custody is None
    assert root.readiness() == {"ready": False, "reason": "not_started"}
