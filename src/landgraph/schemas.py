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


class DBready(BaseModel):
    """Response body of the is_db_ready check."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    status: Literal["ready", "unavailable"]
    """Always "ok" while the service is running."""
