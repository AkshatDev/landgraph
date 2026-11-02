"""Tests for request logging: one structured log record per request."""

import json
import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient

from landgraph.app import create_app

APP_LOGGER = "landgraph.app"
FAKE_URL = "postgresql+psycopg://user:pass@localhost:5432/fake"


def app_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return only the records written by the app's own logger."""
    return [record for record in caplog.records if record.name == APP_LOGGER]


def app_json_lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    """Return the app's own log lines from stdout, each parsed from JSON."""
    output = capsys.readouterr().out
    lines = [json.loads(line) for line in output.splitlines()]
    return [line for line in lines if line["name"] == APP_LOGGER]


def test_request_is_logged_with_method_path_status_and_duration(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    client.get("/health")

    records = app_records(caplog)
    assert len(records) == 1
    record = records[0]
    assert record.levelname == "INFO"
    # Fields passed with ``extra=`` are added to the record at runtime, so a type
    # checker can't see them as attributes; read them from the record's dict.
    fields = vars(record)
    assert fields["method"] == "GET"
    assert fields["path"] == "/health"
    assert fields["status_code"] == 200
    assert isinstance(fields["duration_ms"], float)


def test_request_log_is_printed_as_json(capsys: pytest.CaptureFixture[str]) -> None:
    # Start the app inside this test, not via the shared ``client`` fixture: the
    # log handler keeps the stdout that existed when logging was configured, so
    # the app must start while ``capsys`` is active for it to see the output.
    with TestClient(create_app(FAKE_URL)) as client:
        client.get("/health")

    lines = app_json_lines(capsys)
    assert len(lines) == 1
    fields = lines[0]
    assert fields["levelname"] == "INFO"
    assert fields["method"] == "GET"
    assert fields["path"] == "/health"
    assert fields["status_code"] == 200
    assert isinstance(fields["duration_ms"], float)
