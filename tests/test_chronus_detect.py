"""Chronus contract device is the system's recognised GPU."""

from __future__ import annotations

from chronus.detect import detect_all, detect_chronus


def test_chronus_device_is_enumerated_from_the_contract():
    devices = detect_chronus()
    assert len(devices) == 1
    device = devices[0]
    assert device.backend == "chronus"
    assert device.is_gpu
    assert device.is_integrated
    assert device.vendor == "hyba"


def test_census_reports_chronus_first_and_default():
    report = detect_all()
    assert report.devices
    assert report.devices[0].backend == "chronus"
    default = report.default()
    assert default is not None
    assert default.backend == "chronus"
