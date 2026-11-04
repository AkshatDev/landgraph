"""Read-only spatial queries used by the API."""

import json

from sqlalchemy import Connection, func, select

from .models import Constraint, TitleBoundary
from .schemas import ConstraintRef, Parcel

WGS84 = 4326  # GPS lon/lat: what clients send and what web maps expect
BNG = 27700  # British National Grid, metres: how the table stores geometry


def find_parcels(conn: Connection, lat: float, lng: float) -> list[Parcel]:
    """Return every title boundary at the point, with the constraints overlapping it.

    Args:
        conn: An open database connection.
        lat: Latitude in WGS84.
        lng: Longitude in WGS84.

    Returns:
        The parcels at the point; empty if none (roads, rivers, unregistered land).
    """
    # The search point: make it (lng first!), label it as lon/lat, convert to metres
    # so it can be compared with the table's geometry.
    point = func.ST_Transform(func.ST_SetSRID(func.ST_MakePoint(lng, lat), WGS84), BNG)

    stmt = select(
        TitleBoundary.reference,
        # Area in m², because the stored geometry is in metres.
        func.round(func.ST_Area(TitleBoundary.geom)).label("area_m2"),
        # Outline back to lon/lat, as GeoJSON text.
        func.ST_AsGeoJSON(func.ST_Transform(TitleBoundary.geom, WGS84)).label(
            "geometry"
        ),
    ).where(func.ST_Intersects(TitleBoundary.geom, point))

    parcels = [
        Parcel(
            reference=row.reference,
            area_m2=row.area_m2,
            geometry=json.loads(row.geometry),  # GeoJSON text -> dict
        )
        for row in conn.execute(stmt)
    ]

    # Second query: which constraints overlap each of those parcels.
    by_parcel = find_constraints(conn, [p.reference for p in parcels])
    for parcel in parcels:
        parcel.constraints = by_parcel.get(parcel.reference, [])
    return parcels


def find_constraints(
    conn: Connection, references: list[str]
) -> dict[str, list[ConstraintRef]]:
    """Return the constraints overlapping each parcel, keyed by parcel reference.

    A spatial join: parcel and constraint rows match when their shapes share any
    area (``ST_Intersects``), not when one contains the other. A conservation area
    covering only a corner of a field still affects the whole site.

    Args:
        conn: An open database connection.
        references: Parcel INSPIRE IDs (from ``find_parcels``).

    Returns:
        ``{parcel reference: [constraints]}``; parcels with none are absent.
    """
    if not references:
        return {}

    stmt = (
        select(
            TitleBoundary.reference,
            Constraint.dataset,
            Constraint.entity,
            Constraint.name,
        )
        .join(Constraint, func.ST_Intersects(Constraint.geom, TitleBoundary.geom))
        .where(TitleBoundary.reference.in_(references))
    )

    result: dict[str, list[ConstraintRef]] = {}
    for row in conn.execute(stmt):
        result.setdefault(row.reference, []).append(
            ConstraintRef(dataset=row.dataset, entity=row.entity, name=row.name)
        )
    return result
