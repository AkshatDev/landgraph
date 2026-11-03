"""Transform data in local landing zone."""

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
    """Keep rows in Swindon's box, drop empty geometry/reference, parse dates, snake_case names."""
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
