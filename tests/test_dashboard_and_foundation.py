from pathlib import Path

import pytest
from sqlalchemy import text

from open_garage_erp.config import Settings
from open_garage_erp.database import build_session_factory


def test_dashboard_summary_counts_entities_and_open_orders(client):
    customer = client.post("/api/customers", json={"name": "Mary Jackson"}).json()
    vehicle = client.post(
        "/api/vehicles",
        json={"customer_id": customer["id"], "year": 2018, "make": "Mazda", "model": "3"},
    ).json()
    order = client.post(
        "/api/repair-orders",
        json={"vehicle_id": vehicle["id"], "description": "Tune up", "estimate_cents": 9900},
    ).json()
    client.patch(f"/api/repair-orders/{order['id']}/status", json={"status": "cancelled"})

    summary = client.get("/api/dashboard/summary")

    assert summary.status_code == 200
    assert summary.json() == {
        "customers": 1,
        "vehicles": 1,
        "repair_orders": 1,
        "open_repair_orders": 0,
        "estimate_total_cents": 9900,
    }


def test_dashboard_sums_estimates_without_sqlite_integer_overflow(client):
    customer = client.post("/api/customers", json={"name": "Dorothy Vaughan"}).json()
    vehicle = client.post(
        "/api/vehicles",
        json={"customer_id": customer["id"], "year": 2021, "make": "Ford", "model": "F-150"},
    ).json()
    maximum = 2**63 - 1
    for description in ("Engine", "Transmission"):
        response = client.post(
            "/api/repair-orders",
            json={
                "vehicle_id": vehicle["id"],
                "description": description,
                "estimate_cents": maximum,
            },
        )
        assert response.status_code == 201

    summary = client.get("/api/dashboard/summary")

    assert summary.status_code == 200
    assert summary.json()["estimate_total_cents"] == maximum * 2


def test_unknown_route_uses_json_error_envelope(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found", "details": None}
    }


def test_sqlite_connections_enable_foreign_keys(tmp_path: Path):
    factory = build_session_factory(f"sqlite:///{tmp_path / 'foreign-keys.db'}")

    with factory() as session:
        enabled = session.scalar(text("PRAGMA foreign_keys"))

    assert enabled == 1


def test_tests_inject_a_temporary_database(client, tmp_path: Path):
    configured_url = client.app.state.database_url

    assert configured_url.startswith(f"sqlite:///{tmp_path}")
    assert configured_url != "sqlite:///./data/open-garage.db"


def test_default_settings_use_a_local_relative_sqlite_database(monkeypatch):
    monkeypatch.delenv("OPEN_GARAGE_DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./data/open-garage.db"


def test_settings_reject_unsupported_database_dialects():
    with pytest.raises(ValueError, match="SQLite"):
        Settings(database_url="postgresql://localhost/garage")


def test_settings_reject_empty_sqlite_database_path():
    with pytest.raises(ValueError, match="path"):
        Settings(database_url="sqlite:///")


@pytest.mark.parametrize("database_url", ["sqlite:///?mode=memory", "sqlite:/// "])
def test_settings_rejects_effectively_empty_sqlite_database_paths(database_url):
    with pytest.raises(ValueError, match="path"):
        Settings(database_url=database_url)


def test_settings_rejects_in_memory_sqlite():
    with pytest.raises(ValueError, match="file-backed"):
        Settings(database_url="sqlite:///:memory:")


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///file:memdb-review?mode=memory&cache=shared&uri=true",
        "sqlite:///file:memdb-review",
        "sqlite:///garage.db?mode=memory",
        "sqlite:///garage.db?uri=true",
        "sqlite:///garage.db?cache=shared",
    ],
)
def test_settings_rejects_sqlite_uri_and_query_bypasses(database_url):
    with pytest.raises(ValueError, match="file-backed"):
        Settings(database_url=database_url)


@pytest.mark.parametrize(
    "database_url",
    ["sqlite:///relative.db", "sqlite:///./data/garage.db", "sqlite:////tmp/garage.db"],
)
def test_settings_accepts_file_backed_relative_and_absolute_paths(database_url):
    assert Settings(database_url=database_url).database_url == database_url


def test_database_directory_is_created_for_nested_relative_path(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings(database_url="sqlite:///nested/child/db.sqlite")

    settings.ensure_local_database_directory()

    assert (tmp_path / "nested/child").is_dir()


def test_ids_over_sqlite_integer_limit_are_validation_errors(client):
    response = client.post(
        "/api/vehicles",
        json={
            "customer_id": 2**63,
            "year": 2020,
            "make": "Honda",
            "model": "Civic",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
