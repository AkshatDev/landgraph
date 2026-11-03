"""Transform data in local landing zone."""

from pathlib import Path

import polars as pl

# Swindon (planning.data entity 8600027) bounding box, widened by 0.02° (~1–2 km)
LON_MIN, LON_MAX = -1.8651 - 0.02, -1.6028 + 0.02
LAT_MIN, LAT_MAX = 51.4825 - 0.02, 51.6927 + 0.02


def swindon_title_boundaries(path: Path) -> pl.LazyFrame:
    """Plan: read the national file, keep rows in Swindon's box, clean the columns."""
    ld = (
        pl.scan_parquet(path)
        .select(
            "reference",
            "entity",
            "geometry",
            "point",
            "start-date",
            "end-date",
            "entry-date",
        )
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

    return ld
