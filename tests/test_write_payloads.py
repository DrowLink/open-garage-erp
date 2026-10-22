import pytest


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "post",
            "/api/auth/login",
            {
                "shop_id": 1,
                "email": "owner@example.com",
                "password": "password",
                "unexpected": True,
            },
        ),
        ("post", "/api/customers", {"name": "Ada Lovelace", "unexpected": True}),
        (
            "post",
            "/api/vehicles",
            {
                "customer_id": 1,
                "year": 2020,
                "make": "Honda",
                "model": "Civic",
                "unexpected": True,
            },
        ),
        (
            "post",
            "/api/repair-orders",
            {
                "vehicle_id": 1,
                "description": "Brake inspection",
                "estimate_cents": 12550,
                "unexpected": True,
            },
        ),
        (
            "patch",
            "/api/repair-orders/1/status",
            {"status": "approved", "unexpected": True},
        ),
    ],
)
def test_api_write_payloads_reject_unknown_fields(client, method, path, payload):
    response = getattr(client, method)(path, json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"] == [
        {
            "location": ["body", "unexpected"],
            "message": "Extra inputs are not permitted",
            "type": "extra_forbidden",
        }
    ]
