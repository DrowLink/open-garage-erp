import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from open_garage_erp.app import RequestBodyLimitMiddleware, create_app
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


def test_settings_reject_malformed_database_urls():
    with pytest.raises(ValueError, match="valid SQLAlchemy database URL"):
        Settings(database_url="not-a-database-url")


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


def test_request_body_larger_than_configured_limit_is_rejected(tmp_path: Path):
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'body-limit.db'}",
            max_request_body_bytes=32,
        )
    )

    with TestClient(app) as limited_client:
        response = limited_client.post(
            "/api/customers",
            content=b"x" * 33,
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json() == {
        "error": {
            "code": "request_too_large",
            "message": "Request body exceeds the configured limit of 32 bytes",
            "details": {"max_bytes": 32},
        }
    }


def test_over_limit_chunked_body_is_rejected_before_body_ignoring_endpoint_runs(
    tmp_path: Path,
):
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'chunked-body-limit.db'}",
            max_request_body_bytes=32,
        )
    )

    with TestClient(app) as limited_client:
        response = limited_client.request(
            "GET",
            "/health",
            content=(chunk for chunk in (b"x" * 16, b"x" * 17)),
        )

    assert "content-length" not in response.request.headers
    assert response.request.headers["transfer-encoding"] == "chunked"
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_chunked_body_within_limit_is_accepted():
    response_messages = []
    request_messages = iter(
        [
            {"type": "http.request", "body": b"ab", "more_body": True},
            {"type": "http.request", "body": b"cd", "more_body": False},
        ]
    )

    async def body_reading_app(scope, receive, send):
        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            body.extend(message["body"])
            more_body = message.get("more_body", False)
        assert body == b"abcd"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        return next(request_messages)

    async def capture_send(message):
        response_messages.append(message)

    middleware = RequestBodyLimitMiddleware(body_reading_app, max_body_bytes=4)
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"transfer-encoding", b"chunked")],
    }

    asyncio.run(middleware(scope, receive, capture_send))

    assert response_messages[0]["status"] == 200


@pytest.mark.parametrize(
    "headers",
    [
        [(b"content-length", b"invalid")],
        [(b"content-length", b"-1")],
        [(b"content-length", b"1"), (b"content-length", b"2")],
        [(b"content-length", b"1, 2")],
    ],
)
def test_invalid_content_length_is_rejected_without_reading_body(headers):
    receive_called = False
    response_messages = []

    async def app(scope, receive, send):
        raise AssertionError("invalid framing must not reach the application")

    async def unreadable_receive():
        nonlocal receive_called
        receive_called = True
        raise AssertionError("invalidly framed request body must not be read")

    async def capture_send(message):
        response_messages.append(message)

    middleware = RequestBodyLimitMiddleware(app, max_body_bytes=32)
    scope = {"type": "http", "method": "POST", "headers": headers}

    asyncio.run(middleware(scope, unreadable_receive, capture_send))

    assert receive_called is False
    assert response_messages[0]["status"] == 413


def test_post_body_without_content_length_within_limit_is_accepted():
    response_messages = []
    request_messages = iter(
        [{"type": "http.request", "body": b"abcd", "more_body": False}]
    )

    async def body_reading_app(scope, receive, send):
        assert (await receive())["body"] == b"abcd"
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():
        return next(request_messages)

    async def capture_send(message):
        response_messages.append(message)

    middleware = RequestBodyLimitMiddleware(body_reading_app, max_body_bytes=4)
    scope = {"type": "http", "method": "POST", "headers": []}

    asyncio.run(middleware(scope, receive, capture_send))

    assert response_messages[0]["status"] == 204


def test_over_limit_body_cannot_start_downstream_response_or_side_effect():
    response_messages = []
    side_effects = []
    request_messages = iter(
        [
            {"type": "http.request", "body": b"ab", "more_body": True},
            {"type": "http.request", "body": b"cd", "more_body": False},
        ]
    )

    async def response_starting_app(scope, receive, send):
        side_effects.append("application ran")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await receive()
        await receive()
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        return next(request_messages)

    async def capture_send(message):
        response_messages.append(message)

    middleware = RequestBodyLimitMiddleware(response_starting_app, max_body_bytes=3)
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"content-length", b"3")],
    }

    asyncio.run(middleware(scope, receive, capture_send))

    assert side_effects == []
    response_starts = [
        message for message in response_messages if message["type"] == "http.response.start"
    ]
    assert len(response_starts) == 1
    assert response_starts[0]["status"] == 413
