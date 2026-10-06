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
