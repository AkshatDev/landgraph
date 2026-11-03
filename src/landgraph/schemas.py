"""Schemas for FastAPI application.

The shapes of the JSON the API sends and receives.
"""

from typing import Any, Literal

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


class Parcel(BaseModel):
    """One registered land parcel (HM Land Registry INSPIRE polygon) at the queried point."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    reference: str
    """INSPIRE ID, e.g. "24397490". Stable across data refreshes."""

    area_m2: float
    """Parcel area in square metres (computed in British National Grid, EPSG:27700)."""

    geometry: dict[str, Any]
    """Parcel outline as GeoJSON in WGS84 lon/lat (EPSG:4326), ready for a web map."""


class SiteSnapshot(BaseModel):
    """What we know about a location: the parcels that contain the point."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    lat: float
    """Latitude of the queried point (WGS84)."""

    lng: float
    """Longitude of the queried point (WGS84)."""

    parcels: list[Parcel]
    """Parcels at the point. Usually one; more where titles overlap; empty where no
    land is registered (roads, rivers, unregistered land)."""
