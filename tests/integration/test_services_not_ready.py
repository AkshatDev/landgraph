"""Test /ready endpoint, test faliure case for each service."""

import os

from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from landgraph.app import create_app


def test_service_db_not_ready_check() -> None:
    bad_url = make_url(os.environ["DATABASE_URL"]).set(database="does_not_exist")
    with TestClient(
        create_app(bad_url.render_as_string(hide_password=False))
    ) as client:
        response = client.get("/ready")
        body = response.json()

    assert response.status_code == 503
    assert body["status"] == "unavailable"
    assert body["checks"]["database"] == "unavailable"
