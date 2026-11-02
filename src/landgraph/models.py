"""Module for table schemas for this application."""

import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Parent class for all database models."""


class TitleBoundary(Base):
    """A registered land parcel (HM Land Registry INSPIRE polygon)."""

    __tablename__ = "title_boundaries"

    reference: Mapped[str] = mapped_column(primary_key=True)
    """Land Registry INSPIRE ID, e.g. ``24310103``. Stable across sources."""

    entity: Mapped[int] = mapped_column(BigInteger, unique=True)
    """planning.data.gov.uk entity number, for tracing a row back to the API."""

    geom: Mapped[str] = mapped_column(Geometry("MULTIPOLYGON", srid=27700))
    """Parcel outline in British National Grid (metres)."""

    start_date: Mapped[datetime.date | None]
    """When the polygon was first recorded, if known."""

    end_date: Mapped[datetime.date | None]
    """When the polygon stopped being current; empty for current parcels."""

    entry_date: Mapped[datetime.date | None]
    """When planning.data.gov.uk last updated this record."""

    loaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    """When our pipeline last wrote this row."""
