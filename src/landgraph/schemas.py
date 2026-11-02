"""Schemas for FastAPI application.

The shapes of the JSON the API sends and receives.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Health(BaseModel):
    """Response body of the health check."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    status: Literal["ok"]
    """Always "ok" while the service is running."""


class Ready(BaseModel):
    """Response body of the readiness check."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    status: Literal["ready", "unavailable"]
    """"ready" if every check is "ok", otherwise "unavailable" (sent with HTTP 503)."""

    checks: dict[str, Literal["ok", "unavailable"]]
    """Result of each dependency check, e.g. {"database": "ok"}."""
