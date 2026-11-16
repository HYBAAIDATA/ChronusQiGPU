"""Import-safe application factory for the GA research namespace.

The seven paths from the preserved v3 research source remain available with
experimental implementations and explicit runtime metadata.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Annotated, Any

from ga.mathcore import (
    FIB_HASH_64,
    GALOIS,
    GOLDEN_ANGLE,
    MASK64,
    PHI,
    PhyllotaxisLattice,
    PostQuantum,
    RicciFlowOptimizer,
    YangMillsConnection,
)

_MODEL_NAMES = frozenset(
    {"StoreRequest", "QueryRequest", "SearchRequest", "NonceRequest"}
)


def __getattr__(name: str) -> Any:
    """Lazily expose the original request-model identities."""
    if name in _MODEL_NAMES:
        from ga import models

        return getattr(models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Expose lazy request models to interactive and static tooling."""
    return sorted(set(globals()) | _MODEL_NAMES)


@dataclass
class AppState:
    lattice: PhyllotaxisLattice = field(
        default_factory=lambda: PhyllotaxisLattice(1_000_003)
    )
    ricci: RicciFlowOptimizer = field(default_factory=RicciFlowOptimizer)
    yang_mills: YangMillsConnection = field(default_factory=YangMillsConnection)
    post_quantum: PostQuantum = field(default_factory=PostQuantum)


def _validated_hash(value: str) -> int:
    if not value or len(value) > 128:
        raise ValueError(
            "target_hash must contain between 1 and 128 hexadecimal characters"
        )
    try:
        return int(value, 16)
    except ValueError as exc:
        raise ValueError("target_hash must be hexadecimal") from exc


def _galois_payload(target: int) -> dict[str, Any]:
    element = target % GALOIS.q
    return {
        "algorithm": "galois_field_mapping",
        "field": "GF(2^16)",
        "element": element,
        "coefficients": GALOIS.index_to_poly(element).tolist(),
        "trace": GALOIS.trace(element),
        "qualification": "deterministic_software_mapping",
    }


def _golden_payload(lattice: PhyllotaxisLattice, target: int) -> dict[str, Any]:
    coding = lattice._zeckendorf_index(target)
    coordinate_index = coding % lattice.capacity
    x, y = lattice.golden_coordinate(coordinate_index)
    return {
        "algorithm": "golden_angle_mapping",
        "index": coding,
        "zeckendorf_valid": coding & (coding >> 1) == 0,
        "coordinate_index": coordinate_index,
        "coordinates": {"x": x, "y": y},
        "phi": PHI,
        "qualification": "deterministic_coordinate_mapping",
    }


def create_app(state: AppState | None = None) -> Any:
    """Create the experimental FastAPI application without import side effects."""
    from fastapi import Depends, FastAPI, HTTPException
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    from ga.models import NonceRequest, QueryRequest, SearchRequest, StoreRequest

    runtime = state or AppState()
    security = HTTPBearer()

    app = FastAPI(
        title="GA Research API",
        version="0.1.0.dev0",
        description=(
            "Internal experimental API. No production, security, performance, "
            "or mathematical-proof status is implied."
        ),
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.ga = runtime

    @app.post("/v1/store", tags=["storage"])
    async def store_data(
        request: StoreRequest,
        _credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    ) -> dict[str, Any]:
        encoded_value = {
            **request.value,
            "sector": request.sector,
            "galois_encoded": GALOIS.index_to_poly(
                int.from_bytes(
                    hashlib.sha256(request.key.encode("utf-8")).digest()[:2], "big"
                )
            ).tolist(),
        }
        index = runtime.lattice.store(request.key, encoded_value)
        x, y = runtime.lattice.golden_coordinate(index)
        return {
            "status": "stored",
            "key": request.key,
            "phyllotactic_index": index,
            "coordinates": {"x": x, "y": y},
            "golden_angle": GOLDEN_ANGLE,
            "sector": request.sector,
            "durability": "process_local",
        }

    @app.get("/v1/retrieve/{key}", tags=["storage"])
    async def retrieve_data(key: str) -> dict[str, Any]:
        result = runtime.lattice.retrieve(key)
        if result is None:
            raise HTTPException(status_code=404, detail="key not found")
        return {
            "status": "found",
            "data": result,
            "access_model": "direct_index_after_double_hashed_insert",
            "durability": "process_local",
        }

    @app.post("/v1/query/spiral", tags=["storage"])
    async def spiral_query(request: QueryRequest) -> dict[str, Any]:
        results = runtime.lattice.spiral_query(request.center_key, request.radius)
        if request.sector is not None:
            results = [
                result
                for result in results
                if result.get("value", {}).get("sector") == request.sector
            ]
        return {
            "center_key": request.center_key,
            "radius": request.radius,
            "results_count": len(results),
            "results": results,
            "query_model": "exact_kd_tree_radius_query",
        }

    @app.post("/v1/search/structured", tags=["math"])
    async def structured_search(request: SearchRequest) -> dict[str, Any]:
        try:
            target = _validated_hash(request.target_hash)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if request.algorithm == "galois":
            return _galois_payload(target)
        if request.algorithm == "golden":
            return _golden_payload(runtime.lattice, target)
        from ga.mathcore import np

        coding = runtime.lattice._zeckendorf_index(target)
        coordinate_index = coding % runtime.lattice.capacity
        target_point = np.array(runtime.lattice.golden_coordinate(coordinate_index))
        stored = runtime.lattice.coordinates()
        points = (
            np.vstack((stored, target_point))
            if len(stored)
            else target_point.reshape(1, 2)
        )
        runtime.ricci.set_points(points, steps=0)
        return {
            "algorithm": "weighted_forman_ricci",
            "target_node": len(points) - 1,
            "coordinates": {"x": float(target_point[0]), "y": float(target_point[1])},
            "summary": runtime.ricci.summary(),
            "qualification": "experimental_graph_curvature",
        }

    @app.post("/v1/mining/golden-nonce", tags=["research"])
    async def golden_nonce_mining(request: NonceRequest) -> dict[str, Any]:
        header_bytes = request.block_header.encode()
        best_nonce = None
        best_hash = None
        attempts = 0
        for n in range(1, 10_000):
            nonce_candidate = ((n * FIB_HASH_64) & MASK64) >> 32
            test_hash = hashlib.sha256(
                header_bytes + nonce_candidate.to_bytes(4, "big")
            ).hexdigest()
            attempts += 1
            if int(test_hash, 16) < request.difficulty_target:
                best_nonce = nonce_candidate
                best_hash = test_hash
                break
        return {
            "nonce": best_nonce,
            "hash": best_hash,
            "attempts": attempts,
            "method": "integer_golden_weyl_walk",
            "bounded_candidates": 9_999,
            "qualification": "experimental_bounded_search",
        }

    @app.get("/v1/status", tags=["ops"])
    async def system_status() -> dict[str, Any]:
        return {
            "platform": "GA research namespace",
            "stage": "route_compatibility",
            "qualification": "not_qualified",
            "advertised_claims": {},
            "authentication": "bearer_header_presence_only_not_verified",
            "storage": "process_local_non_durable",
            "field": "GF(2^16)",
            "ricci_dimension": runtime.ricci.dim,
            "gauge_group": runtime.yang_mills.group,
            "post_quantum_enabled": runtime.post_quantum.enabled,
            "maths_is_maths_is_maths": False,
        }

    @app.post("/v1/optimize/ricci", tags=["research"])
    async def ricci_optimize(iterations: int = 100) -> dict[str, Any]:
        if not 1 <= iterations <= 10_000:
            raise HTTPException(
                status_code=422, detail="iterations must be in [1, 10000]"
            )
        from ga.mathcore import np

        runtime.ricci.set_points(runtime.lattice.coordinates(), steps=0)
        runtime.ricci.flow(iterations)
        return {
            "status": "optimized",
            "iterations": iterations,
            "metric_determinant": float(np.linalg.det(runtime.ricci.metric)),
            "summary": runtime.ricci.summary(),
            "qualification": "experimental_weighted_forman_flow",
        }

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "stage": "foundation",
            "qualification": "not_qualified",
        }

    return app
