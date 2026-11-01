"""Smoke tests: Make sure PostGIS is installed."""

import os

from sqlalchemy import Engine, create_engine, text


def test_postgis_installed() -> None:
    """The PostGIS extension is enabled in the database (fails on plain Postgres).

    Running - docker compose exec db psql -c 'SELECT PostGIS_Version();' returns
        postgis_version
        ---------------------------------------
        3.6 USE_GEOS=1 USE_PROJ=1 USE_STATS=1
        (1 row)

    """
    db_url: str = os.environ["DATABASE_URL"]
    engine: Engine = create_engine(db_url)

    with engine.connect() as conn:
        version = conn.execute(text("SELECT PostGIS_Version()")).scalar_one()

    assert version.startswith("3.")
