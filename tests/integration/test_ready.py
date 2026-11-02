"""Test /ready endpoint."""

from fastapi.testclient import TestClient


def test_services_are_ready_check(client: TestClient) -> None:
    response = client.get("/ready")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ready"
    assert set(body["checks"].values()) == {"ok"}
