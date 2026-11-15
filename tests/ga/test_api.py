from pathlib import Path

from fastapi.testclient import TestClient

from ga.api import AppState, create_app
from ga.mathcore import PhyllotaxisLattice

ROOT = Path(__file__).resolve().parents[2]
AUTH = {"Authorization": "Bearer test-token"}


def _client(capacity: int = 101) -> TestClient:
    return TestClient(create_app(AppState(PhyllotaxisLattice(capacity))))


def test_store_retrieve_round_trip_and_bearer_header_presence_boundary():
    client = _client()
    assert client.post("/v1/store", json={"key": "alpha", "value": {}}).status_code in (
        401,
        403,
    )
    response = client.post(
        "/v1/store",
        headers=AUTH,
        json={"key": "alpha", "value": {"number": 1}, "sector": "general"},
    )
    assert response.status_code == 200
    assert response.json()["durability"] == "process_local"
    retrieved = client.get("/v1/retrieve/alpha")
    assert retrieved.status_code == 200
    assert retrieved.json()["data"]["value"]["number"] == 1


def test_api_collisions_do_not_lose_records():
    lattice = PhyllotaxisLattice(capacity=101)
    lattice._digests = lambda _key: (0, 1)
    client = TestClient(create_app(AppState(lattice=lattice)))
    for index in range(60):
        response = client.post(
            "/v1/store",
            headers=AUTH,
            json={"key": f"collision-{index}", "value": {"index": index}},
        )
        assert response.status_code == 200
    for index in range(60):
        response = client.get(f"/v1/retrieve/collision-{index}")
        assert response.json()["data"]["value"]["index"] == index


def test_spiral_query_and_structured_search_are_bounded():
    client = _client()
    client.post(
        "/v1/store",
        headers=AUTH,
        json={"key": "center", "value": {"x": 1}, "sector": "general"},
    )
    spiral = client.post(
        "/v1/query/spiral",
        json={"center_key": "center", "radius": 1_000_000},
    )
    assert spiral.status_code == 200
    assert spiral.json()["query_model"] == "exact_kd_tree_radius_query"

    for algorithm in ("golden", "galois", "ricci"):
        response = client.post(
            "/v1/search/structured",
            json={"target_hash": "a5", "algorithm": algorithm},
        )
        assert response.status_code == 200
        qualification = response.json()["qualification"]
        if algorithm == "ricci":
            assert qualification == "experimental_graph_curvature"
        else:
            assert qualification.startswith("deterministic_")


def test_experimental_operations_execute_and_status_reports_capabilities():
    client = _client()
    mining = client.post(
        "/v1/mining/golden-nonce",
        json={"block_header": "00", "difficulty_target": 1},
    )
    assert mining.status_code == 200
    assert mining.json()["attempts"] == 9_999
    optimized = client.post("/v1/optimize/ricci?iterations=1")
    assert optimized.status_code == 200
    assert optimized.json()["status"] == "optimized"

    status = client.get("/v1/status").json()
    assert status["qualification"] == "not_qualified"
    assert status["advertised_claims"] == {}
    assert status["authentication"] == "bearer_header_presence_only_not_verified"
    assert status["gauge_group"] == "SU(2)"
    assert isinstance(status["post_quantum_enabled"], bool)
    assert status["maths_is_maths_is_maths"] is False
