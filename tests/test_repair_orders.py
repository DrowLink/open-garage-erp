import pytest

import open_garage_erp.app as app_module
from open_garage_erp.database import build_session_factory
from open_garage_erp.models import RepairOrder


def setup_vehicle(client):
    customer = client.post("/api/customers", json={"name": "Katherine Johnson"}).json()
    return client.post(
        "/api/vehicles",
        json={
            "customer_id": customer["id"],
            "year": 2019,
            "make": "Toyota",
            "model": "Camry",
        },
    ).json()


def test_create_list_and_get_repair_order_with_integer_cent_estimate(client):
    vehicle = setup_vehicle(client)

    created = client.post(
        "/api/repair-orders",
        json={
            "vehicle_id": vehicle["id"],
            "description": "Brake inspection",
            "estimate_cents": 12550,
        },
    )

    assert created.status_code == 201
    order = created.json()
    assert order["estimate_cents"] == 12550
    assert isinstance(order["estimate_cents"], int)
    assert order["status"] == "draft"
    assert order["vehicle_id"] == vehicle["id"]
    assert client.get("/api/repair-orders").json() == [order]
    assert client.get("/api/repair-orders/1").json() == order


def test_repair_order_rejects_unknown_vehicle_and_invalid_estimate(client):
    missing = client.post(
        "/api/repair-orders",
        json={"vehicle_id": 999, "description": "Oil change", "estimate_cents": 5000},
    )
    invalid = client.post(
        "/api/repair-orders",
        json={"vehicle_id": 1, "description": "Oil change", "estimate_cents": 1.5},
    )

    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == "Vehicle 999 not found"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_repair_order_status_transitions_are_validated(client):
    vehicle = setup_vehicle(client)
    order = client.post(
        "/api/repair-orders",
        json={"vehicle_id": vehicle["id"], "description": "Diagnosis", "estimate_cents": 0},
    ).json()

    approved = client.patch(f"/api/repair-orders/{order['id']}/status", json={"status": "approved"})
    started = client.patch(
        f"/api/repair-orders/{order['id']}/status", json={"status": "in_progress"}
    )
    completed = client.patch(
        f"/api/repair-orders/{order['id']}/status", json={"status": "completed"}
    )
    invalid = client.patch(f"/api/repair-orders/{order['id']}/status", json={"status": "draft"})

    assert approved.status_code == 200
    assert started.status_code == 200
    assert completed.json()["status"] == "completed"
    assert invalid.status_code == 409
    assert invalid.json()["error"]["code"] == "invalid_status_transition"


def test_repair_order_cannot_skip_from_draft_to_completed(client):
    vehicle = setup_vehicle(client)
    order = client.post(
        "/api/repair-orders",
        json={"vehicle_id": vehicle["id"], "description": "Diagnosis", "estimate_cents": 0},
    ).json()

    response = client.patch(
        f"/api/repair-orders/{order['id']}/status", json={"status": "completed"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"from": "draft", "to": "completed"}


def test_stale_status_transition_cannot_overwrite_terminal_state(client):
    vehicle = setup_vehicle(client)
    order = client.post(
        "/api/repair-orders",
        json={"vehicle_id": vehicle["id"], "description": "Diagnosis", "estimate_cents": 0},
    ).json()
    client.patch(f"/api/repair-orders/{order['id']}/status", json={"status": "approved"})
    client.patch(f"/api/repair-orders/{order['id']}/status", json={"status": "in_progress"})
    factory = build_session_factory(client.app.state.database_url)

    with factory() as completing_session, factory() as stale_session:
        assert completing_session.get(RepairOrder, order["id"]).status == "in_progress"
        assert stale_session.get(RepairOrder, order["id"]).status == "in_progress"
        app_module.transition_repair_order_status(completing_session, order["id"], "completed")

        with pytest.raises(app_module.InvalidStatusTransition) as conflict:
            app_module.transition_repair_order_status(stale_session, order["id"], "cancelled")

    assert conflict.value.current_status == "completed"
    assert client.get(f"/api/repair-orders/{order['id']}").json()["status"] == "completed"


def test_status_transition_updates_timestamp_without_changing_creation_time(client):
    vehicle = setup_vehicle(client)
    order = client.post(
        "/api/repair-orders",
        json={"vehicle_id": vehicle["id"], "description": "Diagnosis", "estimate_cents": 0},
    ).json()

    updated = client.patch(
        f"/api/repair-orders/{order['id']}/status", json={"status": "approved"}
    ).json()

    assert updated["created_at"] == order["created_at"]
    assert updated["updated_at"] > order["updated_at"]
