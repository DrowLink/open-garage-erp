def test_health_reports_ready(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_is_a_human_friendly_landing_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Open Garage ERP" in response.text
    assert "/docs" in response.text
