"""Fixtures shared by all tests: the FastAPI app and a test client for it."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from landgraph import create_app


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """Create one FastAPI app per test module.

    Returns:
        A new application instance.
    """
    return create_app()


@pytest.fixture(scope="module")
def client(app: FastAPI) -> Iterator[TestClient]:
    """Create a test client that sends requests to the app without a server.

    Using ``with`` runs the app's startup and shutdown (lifespan) around the tests.

    Args:
        app: The application under test.

    Yields:
        A client for making HTTP requests to ``app``.
    """
    with TestClient(app) as client:
        yield client
