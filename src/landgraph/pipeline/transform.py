"""Polars transforms: one pure function per dataset, LazyFrame in, LazyFrame out.

Each keeps the rows whose centroid (``point``) lies inside the Swindon box from
``landgraph.coverage``, drops rows without geometry or a key, parses dates and
renames columns to match the table. No I/O and no database: easy to test.
"""

import polars as pl

from landgraph.coverage import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN

TITLE_BOUNDARY_COLUMNS = [
    "reference",
    "entity",
    "geometry",
    "point",
    "start-date",
    "end-date",
    "entry-date",
]


def transform_title_boundaries(lf: pl.LazyFrame) -> pl.LazyFrame:
    """Keep rows in Swindon's box, drop empty geometry/reference, parse dates, snake_case names.

    Args:
        lf: Rows with at least ``TITLE_BOUNDARY_COLUMNS``.

    Returns:
        Columns ``reference``, ``entity``, ``geometry`` (WKT, WGS84), and
        ``start_date``, ``end_date``, ``entry_date`` as dates (empty strings become null).
    """
    return (
        lf.select(TITLE_BOUNDARY_COLUMNS)
        .with_columns(
            lon=pl.col("point").str.extract(r"POINT \((\S+) ", 1).cast(pl.Float64),
            lat=pl.col("point").str.extract(r" (\S+)\)", 1).cast(pl.Float64),
        )
        .filter(
            pl.col("lon").is_between(LON_MIN, LON_MAX),
            pl.col("lat").is_between(LAT_MIN, LAT_MAX),
            pl.col("geometry").is_not_null() & (pl.col("geometry") != ""),
            pl.col("reference").is_not_null() & (pl.col("reference") != ""),
        )
        .with_columns(
            pl.col(c).replace("", None).str.to_date("%Y-%m-%d")
            for c in ["start-date", "end-date", "entry-date"]
        )
        .rename(
            {
                "start-date": "start_date",
                "end-date": "end_date",
                "entry-date": "entry_date",
            }
        )
        .drop("point", "lon", "lat")
    )


CONSTRAINT_COLUMNS = [
    "dataset",  # the source file's own label, e.g. "conservation-area"
    "entity",
    "reference",
    "name",
    "geometry",
    "point",
    "start-date",
    "end-date",
    "entry-date",
]


def transform_constraints(lf: pl.LazyFrame) -> pl.LazyFrame:
    """Keep constraint features whose centroid is in Swindon's box; clean the columns.

    Works for any planning.data constraint layer (conservation areas, listed
    buildings, ...). Filters on the centroid (``point``): right for small and
    medium shapes; very large ones (long flood zones) would need a real overlap
    test in PostGIS instead.

    The ``dataset`` label is kept from the source file, so every row says which
    layer it belongs to without the caller having to pass it in.

    Args:
        lf: Rows with at least ``CONSTRAINT_COLUMNS``.

    Returns:
        Columns ``dataset``, ``entity``, ``reference``, ``name``, ``geometry`` (WKT,
        WGS84), and ``start_date``, ``end_date``, ``entry_date`` as dates.
    """
    return (
        lf.select(CONSTRAINT_COLUMNS)
        .with_columns(
            lon=pl.col("point").str.extract(r"POINT \((\S+) ", 1).cast(pl.Float64),
            lat=pl.col("point").str.extract(r" (\S+)\)", 1).cast(pl.Float64),
        )
        .filter(
            pl.col("lon").is_between(LON_MIN, LON_MAX),
            pl.col("lat").is_between(LAT_MIN, LAT_MAX),
            pl.col("geometry").is_not_null() & (pl.col("geometry") != ""),
            pl.col("entity").is_not_null(),
        )
        .with_columns(
            pl.col(c).replace("", None).str.to_date("%Y-%m-%d")
            for c in ["start-date", "end-date", "entry-date"]
        )
        .rename(
            {
                "start-date": "start_date",
                "end-date": "end_date",
                "entry-date": "entry_date",
            }
        )
        .drop("point", "lon", "lat")
    )
