"""Read-only spatial queries used by the API."""

import json

from sqlalchemy import Connection, func, select

from .models import TitleBoundary
from .schemas import Parcel

WGS84 = 4326  # GPS lon/lat: what clients send and what web maps expect
BNG = 27700  # British National Grid, metres: how the table stores geometry


def find_parcels(conn: Connection, lat: float, lng: float) -> list[Parcel]:
    """Return every title boundary that contains (or touches) the point.

    Args:
        conn: An open database connection.
        lat: Latitude in WGS84.
        lng: Longitude in WGS84.

    Returns:
        The parcels at the point; empty if none (roads, rivers, unregistered land).
    """
    # The search point: make it (lng first!), label it as lon/lat, convert to metres
    # so it can be compared with the table's geometry.
    point = func.ST_Transform(
        func.ST_SetSRID(func.ST_MakePoint(lng, lat), WGS84), BNG
    )

    stmt = select(
        TitleBoundary.reference,
        # Area in m², because the stored geometry is in metres.
        func.round(func.ST_Area(TitleBoundary.geom)).label("area_m2"),
        # Outline back to lon/lat, as GeoJSON text.
        func.ST_AsGeoJSON(func.ST_Transform(TitleBoundary.geom, WGS84)).label(
            "geometry"
        ),
    ).where(func.ST_Intersects(TitleBoundary.geom, point))

    return [
        Parcel(
            reference=row.reference,
            area_m2=row.area_m2,
            geometry=json.loads(row.geometry),  # GeoJSON text -> dict
        )
        for row in conn.execute(stmt)
    ]
