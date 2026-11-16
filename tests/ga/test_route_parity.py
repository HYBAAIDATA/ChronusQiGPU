import ast
from pathlib import Path

from ga.api import NonceRequest, QueryRequest, SearchRequest, StoreRequest, create_app

ROOT = Path(__file__).resolve().parents[2]
ORACLE = ROOT / "docs" / "research" / "golden_search.py"


def _oracle_tree() -> ast.Module:
    return ast.parse(ORACLE.read_text(encoding="utf-8-sig"))


def _oracle_routes() -> set[tuple[str, str]]:
    routes = set()
    for node in _oracle_tree().body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(
                decorator.func, ast.Attribute
            ):
                continue
            if decorator.func.attr in {"get", "post", "websocket"}:
                routes.add((decorator.func.attr, ast.literal_eval(decorator.args[0])))
    return routes


def _oracle_model_fields() -> dict[str, set[str]]:
    model_names = {"StoreRequest", "QueryRequest", "SearchRequest", "NonceRequest"}
    result = {}
    for node in _oracle_tree().body:
        if isinstance(node, ast.ClassDef) and node.name in model_names:
            result[node.name] = {
                statement.target.id
                for statement in node.body
                if isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
            }
    return result


def test_route_parity_with_preserved_v3_oracle():
    original = _oracle_routes()
    app = create_app()
    live = {
        (method.lower(), route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
        if method not in {"HEAD", "OPTIONS"}
    }
    assert original <= live


def test_request_field_parity_with_preserved_v3_oracle():
    live = {
        model.__name__: set(model.model_fields)
        for model in (StoreRequest, QueryRequest, SearchRequest, NonceRequest)
    }
    assert _oracle_model_fields() == live


def test_lazy_models_are_discoverable_and_preserve_identity():
    from ga import api, models

    assert {"StoreRequest", "QueryRequest", "SearchRequest", "NonceRequest"} <= set(
        dir(api)
    )
    assert api.StoreRequest is models.StoreRequest
