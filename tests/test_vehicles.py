def create_customer(client):
    return client.post("/api/customers", json={"name": "Grace Hopper"}).json()


def test_create_list_and_get_vehicle_linked_to_customer(client):
    customer = create_customer(client)
    payload = {
        "customer_id": customer["id"],
        "vin": "1M8GDM9AXKP042788",
        "year": 2020,
        "make": "Honda",
        "model": "Civic",
        "license_plate": "GARAGE1",
    }

    created = client.post("/api/vehicles", json=payload)

    assert created.status_code == 201
    vehicle = created.json()
    assert vehicle["id"] == 1
    assert vehicle["customer_id"] == customer["id"]
    assert vehicle["vin"] == payload["vin"]
    assert vehicle["created_at"].endswith("Z")
    assert client.get("/api/vehicles").json() == [vehicle]
    assert client.get("/api/vehicles/1").json() == vehicle


def test_vehicle_rejects_unknown_customer(client):
    response = client.post(
        "/api/vehicles",
        json={"customer_id": 999, "year": 2022, "make": "Ford", "model": "Transit"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Customer 999 not found", "details": None}
    }


def test_vehicle_not_found_uses_error_envelope(client):
    response = client.get("/api/vehicles/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_duplicate_vin_returns_conflict_error(client):
    customer = create_customer(client)
    payload = {
        "customer_id": customer["id"],
        "vin": "1M8GDM9AXKP042788",
        "year": 2020,
        "make": "Honda",
        "model": "Civic",
    }
    assert client.post("/api/vehicles", json=payload).status_code == 201

    duplicate = client.post("/api/vehicles", json=payload)

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "integrity_conflict"


def test_session_is_usable_after_integrity_conflict(client):
    customer = create_customer(client)
    payload = {
        "customer_id": customer["id"],
        "vin": "1M8GDM9AXKP042788",
        "year": 2020,
        "make": "Honda",
        "model": "Civic",
    }
    assert client.post("/api/vehicles", json=payload).status_code == 201
    assert client.post("/api/vehicles", json=payload).status_code == 409

    payload["vin"] = "1HGCM82633A004352"
    recovered = client.post("/api/vehicles", json=payload)

    assert recovered.status_code == 201
    assert len(client.get("/api/vehicles").json()) == 2
