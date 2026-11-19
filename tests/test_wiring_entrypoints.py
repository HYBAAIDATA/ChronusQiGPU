"""End-to-end wiring checks for the repository's declared entry points.

These tests guard the joins between packaging/deployment declarations
(pyproject console scripts, Dockerfile CMDs, .env.example, alembic) and the
code they point at, so a rename or missing migration fails CI instead of
failing at deploy time. They do not exercise hardware or live services.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

pytestmark = pytest.mark.real


def _src_text() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8", errors="replace") for p in SRC.rglob("*.py")
    )


def _env_example_keys() -> list[str]:
    keys = []
    for line in (ROOT / ".env.example").read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        # Commented-out "# KEY=value" lines document optional keys; check them too.
        m = re.match(r"^#?\s*([A-Z][A-Z0-9_]*)=", line)
        if m:
            keys.append(m.group(1))
    return keys


def test_env_example_keys_are_read_by_code() -> None:
    text = _src_text()
    keys = _env_example_keys()
    assert keys, ".env.example declares no keys"
    pool_vars = re.compile(r"^MINING_(BRAIINS|VIABTC)_(HOST|PORT|USER|PASSWORD|PASS)$")
    unread = []
    for key in keys:
        if pool_vars.match(key):
            # Read dynamically as f"MINING_{active_pool}_{field}".
            assert 'f"MINING_{active_pool}_' in text
            continue
        if f'"{key}"' not in text and f"'{key}'" not in text:
            unread.append(key)
    assert not unread, f".env.example keys never read under src/: {unread}"


def _console_scripts() -> dict[str, str]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10: parse the one flat table directly.
        section = re.search(r"^\[project\.scripts\]\s*$(.*?)(?=^\[)", text, re.M | re.S)
        assert section, "pyproject.toml has no [project.scripts] table"
        return dict(re.findall(r'^([\w.-]+)\s*=\s*"([^"]+)"', section.group(1), re.M))
    return tomllib.loads(text)["project"]["scripts"]


def test_console_scripts_resolve() -> None:
    scripts = _console_scripts()
    assert scripts
    for name, target in scripts.items():
        module_name, _, attr = target.partition(":")
        module = importlib.import_module(module_name)
        assert callable(getattr(module, attr)), f"{name} -> {target} is not callable"


def test_dockerfile_api_target_serves_health(monkeypatch: pytest.MonkeyPatch) -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    m = re.search(r'CMD \["uvicorn", "([\w.]+):(\w+)"', dockerfile)
    assert m, "api-runtime CMD no longer launches uvicorn"
    app = getattr(importlib.import_module(m.group(1)), m.group(2))
    from fastapi.testclient import TestClient

    from chronus.service.dependencies import service_config

    # Probe the in-process app only; never a configured remote execution adapter.
    monkeypatch.setattr(service_config, "execution_backend_url", None)

    with TestClient(app) as client:
        # Same probe as the Dockerfile/compose HEALTHCHECK.
        assert client.get("/health/ready").status_code == 200
        assert client.get("/health/live").status_code == 200


def test_miner_wrapper_targets_exist() -> None:
    wrapper = (ROOT / "chronus_live_miner.py").read_text(encoding="utf-8")
    m = re.search(r"from ([\w.]+) import \(([^)]*)\)", wrapper)
    assert m, "chronus_live_miner.py no longer forwards to a packaged entrypoint"
    module_name = m.group(1)
    names = [n.strip() for n in m.group(2).split(",") if n.strip()]
    path = SRC / Path(*module_name.split(".")).with_suffix(".py")
    assert path.exists(), f"miner wrapper imports missing module {module_name}"
    source = path.read_text(encoding="utf-8")
    for name in names:
        assert re.search(rf"^(async def|def|class) {name}\b", source, re.M), (
            f"{module_name} does not define {name}"
        )


def _alembic_revisions():
    pytest.importorskip("alembic")
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    assert len(script.get_heads()) == 1, "alembic history has multiple heads"
    return list(reversed(list(script.walk_revisions())))


def _run_upgrades(conn, revisions) -> None:
    import alembic.op as op_proxy
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    op_proxy._proxy = Operations(MigrationContext.configure(conn))
    try:
        for rev in revisions:
            rev.module.upgrade()
    finally:
        op_proxy._proxy = None


def _schema(conn) -> dict:
    import sqlalchemy as sa

    inspector = sa.inspect(conn)
    return {
        t: {c["name"] for c in inspector.get_columns(t)}
        for t in inspector.get_table_names()
    }


def _assert_matches_metadata(migrated: dict) -> None:
    from chronus.service.postgres_store import metadata

    expected = {t.name: {c.name for c in t.columns} for t in metadata.sorted_tables}
    missing_tables = sorted(set(expected) - set(migrated))
    assert not missing_tables, f"tables in store metadata but not in migrations: {missing_tables}"
    for table, cols in expected.items():
        assert cols == migrated[table], f"column drift in {table}: {cols ^ migrated[table]}"


def test_alembic_head_matches_store_metadata(tmp_path: Path) -> None:
    revisions = _alembic_revisions()
    import sqlalchemy as sa

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migrate.sqlite3'}")
    with engine.begin() as conn:
        _run_upgrades(conn, revisions)
        _assert_matches_metadata(_schema(conn))


def test_alembic_upgrade_over_runtime_created_schema(tmp_path: Path) -> None:
    """A DB stamped at 0001 whose store already ran metadata.create_all upgrades cleanly."""
    revisions = _alembic_revisions()
    import sqlalchemy as sa

    from chronus.service.postgres_store import metadata

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'runtime.sqlite3'}")
    with engine.begin() as conn:
        _run_upgrades(conn, revisions[:1])
        metadata.create_all(conn)  # what PostgresWorkloadStore.init_db() does
        conn.execute(
            sa.text(
                "INSERT INTO ciaas_capacity_ledger (event_id, tenant_id, previous_warps, "
                "new_active_warps, previous_storage_gb, new_storage_gb, reason) "
                "VALUES ('e1', 't1', 1, 2, 3, 4, 'keep')"
            )
        )
        _run_upgrades(conn, revisions[1:])
        _assert_matches_metadata(_schema(conn))
        kept = conn.execute(sa.text("SELECT reason FROM ciaas_capacity_ledger")).scalar_one()
        assert kept == "keep"


# Pre-existing spec dump whose path is pinned by historical qualification
# manifests; tracked in the wiring audit rather than renamed here.
_KNOWN_NON_IMPORTABLE = {"src/chronus/chronus_gpiu-v36.py"}


def test_packaged_modules_have_importable_names() -> None:
    bad = [
        p.relative_to(ROOT).as_posix()
        for p in (SRC / "chronus").rglob("*.py")
        if not p.stem.isidentifier()
        and p.relative_to(ROOT).as_posix() not in _KNOWN_NON_IMPORTABLE
    ]
    assert not bad, f"non-importable module filenames shipped in the wheel: {bad}"


def test_packaged_modules_have_no_import_time_side_effect_scripts() -> None:
    """One-off maintenance scripts must not live inside the shipped package."""
    offenders = []
    for p in (SRC / "chronus").rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^[a-z_]+ = ['\"][a-zA-Z]:[/\\]Users", text, re.M):
            offenders.append(p.relative_to(ROOT).as_posix())
    assert not offenders, f"hardcoded developer-machine paths at module level: {offenders}"
