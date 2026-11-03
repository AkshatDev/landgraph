"""Version 1 of the public API, served under ``/v1``.

Additive changes (new optional fields, new endpoints) stay in v1. A breaking change
(renamed or removed fields, changed units or CRS) goes into a new ``/v2`` router that
runs alongside this one until clients have moved.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError

from .coverage import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN
from .queries import find_parcels
from .schemas import SiteSnapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["v1"])


@router.get("/site-snapshot", responses={503: {"description": "Database unavailable"}})
def site_snapshot(
    request: Request,
    lat: Annotated[
        float,
        Query(ge=LAT_MIN, le=LAT_MAX, description="Latitude (WGS84), within Swindon"),
    ],
    lng: Annotated[
        float,
        Query(ge=LON_MIN, le=LON_MAX, description="Longitude (WGS84), within Swindon"),
    ],
) -> SiteSnapshot:
    """Return the land parcels at a point in Swindon.

    Empty `parcels` means no registered title at that point (roads, rivers,
    unregistered land). Points outside Swindon are rejected with 422.
    """
    try:
        with request.app.state.db.engine.connect() as conn:
            parcels = find_parcels(conn, lat=lat, lng=lng)
    except SQLAlchemyError:
        logger.warning("site snapshot failed: database unavailable", exc_info=True)
        raise HTTPException(status_code=503, detail="database unavailable") from None
    return SiteSnapshot(lat=lat, lng=lng, parcels=parcels)
