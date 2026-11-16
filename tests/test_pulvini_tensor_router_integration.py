"""Experimental PULVINI execution lives in the existing authenticated tensor API."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from chronus.service.auth_middleware import AuthenticatedIdentity, Role
from chronus.service.routers.tensor import router

pytestmark = pytest.mark.simulated


def _app(*, override: bool):
    app=FastAPI()
    app.include_router(router)
    if override:
        endpoint=next(route for route in router.routes
                      if getattr(route,"path","").endswith("/pulvini/linear"))
        assert len(endpoint.dependant.dependencies)==1
        require_principal=endpoint.dependant.dependencies[0].call
        app.dependency_overrides[require_principal]=lambda: AuthenticatedIdentity(
            tenant_id="tenant-test",user_id="test-principal",
            roles={Role.DEVELOPER},claims={"sub":"test-principal"},
        )
    return app


def _payload(**overrides):
    p={"left":[.5,1.5,-2.,3.], "right":[1.,-2.,4.,.5],
       "alpha":2., "beta":-1., "depth":3}
    p.update(overrides)
    return p


def test_route_requires_authenticated_principal(monkeypatch):
    monkeypatch.setenv("CHRONUS_PULVINI_API_ENABLED","1")
    response=TestClient(_app(override=False)).post("/v1/tensor/pulvini/linear",json=_payload())
    assert response.status_code==401


def test_default_disabled_even_for_authorised_principal(monkeypatch):
    monkeypatch.delenv("CHRONUS_PULVINI_API_ENABLED",raising=False)
    response=TestClient(_app(override=True)).post("/v1/tensor/pulvini/linear",json=_payload())
    assert response.status_code==503


def test_authorised_opt_in_linear_path_does_not_claim_production(monkeypatch):
    monkeypatch.setenv("CHRONUS_PULVINI_API_ENABLED","1")
    response=TestClient(_app(override=True)).post("/v1/tensor/pulvini/linear",json=_payload())
    assert response.status_code==200, response.text
    r=response.json()
    assert r["status"]=="PASS"
    assert r["tenant_id"]=="tenant-test"
    assert r["output"]==pytest.approx([0.,5.,-8.,5.5],abs=1e-12)
    assert r["metrics"]["backend"]=="numpy-reference-folded-channels"
    assert r["metrics"]["physical_accelerator_measured"] is False
    assert r["metrics"]["net_storage_savings_measured"] is False
    assert r["production_qualification"]=="UNVERIFIED"
    assert r["raw_input_persisted"] is False


def test_invalid_shape_and_nan_are_refused_without_artifact(monkeypatch):
    monkeypatch.setenv("CHRONUS_PULVINI_API_ENABLED","1")
    client=TestClient(_app(override=True))
    wrong=client.post("/v1/tensor/pulvini/linear",json=_payload(right=[1.]))
    assert wrong.status_code==422
    nonfinite=client.post("/v1/tensor/pulvini/linear",json=_payload(alpha="NaN"))
    assert nonfinite.status_code==422


def test_bounded_payload_fails_closed(monkeypatch):
    monkeypatch.setenv("CHRONUS_PULVINI_API_ENABLED","1")
    response=TestClient(_app(override=True)).post(
        "/v1/tensor/pulvini/linear",json=_payload(left=[1.]*4097,right=[2.]*4097))
    assert response.status_code==422
