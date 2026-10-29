def test_create_list_and_get_customer(client):
    created = client.post(
        "/api/customers",
        json={"name": "Ada Lovelace", "email": "ada@example.com", "phone": "+1 555 0100"},
    )

    assert created.status_code == 201
    customer = created.json()
    assert customer["id"] == 1
    assert customer["name"] == "Ada Lovelace"
    assert customer["email"] == "ada@example.com"
    assert customer["created_at"].endswith("Z")
    assert customer["updated_at"].endswith("Z")

    listed = client.get("/api/customers")
    assert listed.status_code == 200
    assert listed.json() == [customer]

    fetched = client.get("/api/customers/1")
    assert fetched.status_code == 200
    assert fetched.json() == customer


def test_customer_validation_and_not_found_use_consistent_errors(client):
    invalid = client.post("/api/customers", json={"name": ""})
    missing = client.get("/api/customers/999")

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    assert isinstance(invalid.json()["error"]["details"], list)
    assert missing.status_code == 404
    assert missing.json() == {
        "error": {"code": "not_found", "message": "Customer 999 not found", "details": None}
    }


def test_update_customer_changes_only_supplied_fields(client):
    customer = client.post(
        "/api/customers",
        json={"name": "Ada Lovelace", "email": "ada@example.com", "phone": "+1 555 0100"},
    ).json()

    response = client.patch(
        f"/api/customers/{customer['id']}",
        json={"name": "Ada Byron", "expected_updated_at": customer["updated_at"]},
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Ada Byron"
    assert updated["email"] == "ada@example.com"
    assert updated["phone"] == "+1 555 0100"
    assert updated["created_at"] == customer["created_at"]
    assert updated["updated_at"] > customer["updated_at"]


def test_update_customer_rejects_a_stale_timestamp(client):
    customer = client.post("/api/customers", json={"name": "Ada Lovelace"}).json()
    current = client.patch(
        f"/api/customers/{customer['id']}",
        json={"name": "Ada Byron", "expected_updated_at": customer["updated_at"]},
    ).json()

    response = client.patch(
        f"/api/customers/{customer['id']}",
        json={"name": "Stale overwrite", "expected_updated_at": customer["updated_at"]},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "stale_update",
            "message": "Customer was modified after the supplied timestamp",
            "details": {"current_updated_at": current["updated_at"]},
        }
    }
    assert client.get(f"/api/customers/{customer['id']}").json()["name"] == "Ada Byron"


def test_customer_update_requires_a_change(client):
    customer = client.post("/api/customers", json={"name": "Ada Lovelace"}).json()

    response = client.patch(
        f"/api/customers/{customer['id']}",
        json={"expected_updated_at": customer["updated_at"]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_archive_customer_records_timestamp_without_deleting_customer(client):
    customer = client.post("/api/customers", json={"name": "Ada Lovelace"}).json()

    response = client.post(
        f"/api/customers/{customer['id']}/archive",
        json={"expected_updated_at": customer["updated_at"]},
    )

    assert response.status_code == 200
    archived = response.json()
    assert archived["archived_at"].endswith("Z")
    assert archived["updated_at"] == archived["archived_at"]
    assert client.get(f"/api/customers/{customer['id']}").json() == archived


def test_customer_list_excludes_archived_customers(client):
    archived_customer = client.post(
        "/api/customers", json={"name": "Archived Customer"}
    ).json()
    active_customer = client.post("/api/customers", json={"name": "Active Customer"}).json()
    client.post(
        f"/api/customers/{archived_customer['id']}/archive",
        json={"expected_updated_at": archived_customer["updated_at"]},
    )

    response = client.get("/api/customers")

    assert response.status_code == 200
    assert response.json() == [active_customer]


def test_archive_unknown_customer_returns_not_found(client):
    response = client.post(
        "/api/customers/999/archive",
        json={"expected_updated_at": "2026-01-01T12:00:00Z"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Customer 999 not found", "details": None}
    }


def test_archive_customer_rejects_a_stale_timestamp(client):
    customer = client.post("/api/customers", json={"name": "Ada Lovelace"}).json()
    current = client.patch(
        f"/api/customers/{customer['id']}",
        json={"name": "Ada Byron", "expected_updated_at": customer["updated_at"]},
    ).json()

    response = client.post(
        f"/api/customers/{customer['id']}/archive",
        json={"expected_updated_at": customer["updated_at"]},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "stale_update",
            "message": "Customer was modified after the supplied timestamp",
            "details": {"current_updated_at": current["updated_at"]},
        }
    }
    assert client.get(f"/api/customers/{customer['id']}").json()["archived_at"] is None
