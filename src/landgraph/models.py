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


class PipelineCheckpoint(Base):
    """How far ``load`` has got through one source file, for resuming after a crash.

    One row per (dataset, source file). It is written in the same transaction as
    the data, so it never claims rows that are not in the database.
    """

    __tablename__ = "pipeline_checkpoints"

    dataset: Mapped[str] = mapped_column(primary_key=True)
    """planning.data.gov.uk dataset name, e.g. ``title-boundary``."""

    source_fingerprint: Mapped[str] = mapped_column(primary_key=True)
    """Identifies the exact source file: ``<name>:<size in bytes>:<row count>``.

    A new download gets a new fingerprint, so its load starts from the beginning.
    """

    row_group: Mapped[int]
    """Next parquet row group to read. Equal to the file's row-group count when done."""

    row_offset: Mapped[int]
    """Rows of ``row_group`` already committed; reading resumes after them."""

    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    """When the checkpoint last moved. Set to ``now()`` in the upsert too."""


class Constraint(Base):
    """A planning constraint layer feature: conservation area, flood zone, listed building, etc.

    One table for every constraint dataset; ``dataset`` says which layer a row belongs to.
    Adding a new layer is a data load, not a schema change.
    """

    __tablename__ = "constraints"

    # autoincrement=False: the ID comes from planning.data, never from a sequence.
    entity: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )
    """planning.data.gov.uk entity number. Unique across all datasets, unlike
    ``reference`` (council codes such as ``CA10`` repeat across 41 councils)."""

    dataset: Mapped[str] = mapped_column(index=True)
    """planning.data dataset name, e.g. ``conservation-area``."""

    reference: Mapped[str | None]
    """The publishing organisation's own code. Not unique on its own."""

    name: Mapped[str | None]
    """Human-readable name, e.g. ``Swindon Town Gardens``."""

    geom: Mapped[str] = mapped_column(Geometry("GEOMETRY", srid=27700))
    """Shape in British National Grid (metres). Generic GEOMETRY because layers
    differ: polygons for areas and zones, points for listed buildings."""

    start_date: Mapped[datetime.date | None]
    """When the constraint started (e.g. designation date), if known."""

    end_date: Mapped[datetime.date | None]
    """When the constraint ended; empty while it is in force."""

    entry_date: Mapped[datetime.date | None]
    """When planning.data.gov.uk last updated this record."""

    loaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    """When our pipeline last wrote this row."""
