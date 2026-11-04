"""Load transformed data into the DB."""

import logging
from collections.abc import Callable
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq
from sqlalchemy import bindparam, func
from sqlalchemy.dialects.postgresql import Insert, insert

from landgraph import Database
from landgraph.models import Constraint, TitleBoundary

from .checkpoint import load_checkpoint, save_checkpoint
from .transform import (
    CONSTRAINT_COLUMNS,
    TITLE_BOUNDARY_COLUMNS,
    transform_constraints,
    transform_title_boundaries,
)

logger = logging.getLogger(__name__)
READ_BATCH_ROWS = 50_000  # rows read from the parquet file at a time
INSERT_SLICE_ROWS = 1_000  # rows sent to Postgres per executemany


def _title_boundary_upsert() -> Insert:
    """Upsert one title boundary, keyed on its INSPIRE ``reference``."""
    stmt = insert(TitleBoundary).values(
        reference=bindparam("reference"),
        entity=bindparam("entity"),
        geom=func.ST_Transform(
            func.ST_GeomFromText(bindparam("geometry"), 4326), 27700
        ),
        start_date=bindparam("start_date"),
        end_date=bindparam("end_date"),
        entry_date=bindparam("entry_date"),
    )
    return stmt.on_conflict_do_update(
        index_elements=[TitleBoundary.reference],
        set_={
            "entity": stmt.excluded.entity,
            "geom": stmt.excluded.geom,
            "start_date": stmt.excluded.start_date,
            "end_date": stmt.excluded.end_date,
            "entry_date": stmt.excluded.entry_date,
            "loaded_at": func.now(),
        },
    )


def _constraint_upsert() -> Insert:
    """Upsert one constraint feature, keyed on planning.data ``entity``."""
    stmt = insert(Constraint).values(
        entity=bindparam("entity"),
        dataset=bindparam("dataset"),
        reference=bindparam("reference"),
        name=bindparam("name"),
        geom=func.ST_Transform(
            func.ST_GeomFromText(bindparam("geometry"), 4326), 27700
        ),
        start_date=bindparam("start_date"),
        end_date=bindparam("end_date"),
        entry_date=bindparam("entry_date"),
    )
    return stmt.on_conflict_do_update(
        index_elements=[Constraint.entity],
        set_={
            "dataset": stmt.excluded.dataset,
            "reference": stmt.excluded.reference,
            "name": stmt.excluded.name,
            "geom": stmt.excluded.geom,
            "start_date": stmt.excluded.start_date,
            "end_date": stmt.excluded.end_date,
            "entry_date": stmt.excluded.entry_date,
            "loaded_at": func.now(),
        },
    )


# --------------------------------------------------------------------------
# OLD version, kept for comparison. It scans the whole national file at once,
# which peaked at 3.3-4.4 GB and crashed WSL. No checkpoints: a crash means
# starting again from the top (safe because of the upsert, but slow).
# Only change: it now calls transform_title_boundaries(pl.scan_parquet(path)),
# because the transform takes a LazyFrame instead of a path.
# --------------------------------------------------------------------------
def load_title_boundaries(db: Database, path: Path, batch_size: int = 1000) -> int:
    """Get transformed data from given path and load it."""
    stmt = _title_boundary_upsert()
    plan = transform_title_boundaries(pl.scan_parquet(path))
    total = 0
    for batch in plan.collect_batches(chunk_size=batch_size):
        with db.engine.begin() as conn:
            conn.execute(stmt, batch.to_dicts())
        total += batch.height
        logger.info("batch loaded", extra={"rows": batch.height, "rows_total": total})

    return total


# --------------------------------------------------------------------------
# NEW version: reads one row group at a time (~0.7 GB peak) and saves a
# checkpoint in the same transaction as each batch, so it can resume.
# --------------------------------------------------------------------------
def load_title_boundaries_resumable(
    db: Database, path: Path, read_batch_rows: int = READ_BATCH_ROWS
) -> int:
    """Load Swindon's title boundaries from the national file, resuming if interrupted.

    Returns:
        Number of rows upserted in this run (0 if the file was already fully loaded).
    """
    return _load_resumable(
        db,
        path,
        dataset="title-boundary",
        columns=TITLE_BOUNDARY_COLUMNS,
        transform=transform_title_boundaries,
        stmt=_title_boundary_upsert(),
        read_batch_rows=read_batch_rows,
    )


def load_constraints_resumable(
    db: Database, path: Path, dataset: str, read_batch_rows: int = READ_BATCH_ROWS
) -> int:
    """Load Swindon's features of one constraint layer (e.g. conservation areas).

    All constraint layers share the ``constraints`` table; ``dataset`` is also the
    checkpoint key, so each layer resumes independently.

    Returns:
        Number of rows upserted in this run (0 if the file was already fully loaded).
    """
    return _load_resumable(
        db,
        path,
        dataset=dataset,
        columns=CONSTRAINT_COLUMNS,
        transform=transform_constraints,
        stmt=_constraint_upsert(),
        read_batch_rows=read_batch_rows,
    )


def _load_resumable(
    db: Database,
    path: Path,
    dataset: str,
    columns: list[str],
    transform: Callable[[pl.LazyFrame], pl.LazyFrame],
    stmt: Insert,
    read_batch_rows: int,
) -> int:
    """The shared loop: row groups one at a time, upsert + checkpoint per batch."""
    parquet = pq.ParquetFile(path, pre_buffer=False)
    fingerprint = _fingerprint(path, parquet)

    # Step 1: where did the last run stop? (0, 0) means "start from the top".
    with db.engine.connect() as conn:
        start_row_group, committed_offset = load_checkpoint(conn, dataset, fingerprint)

    # A finished file points one past the last row group: say so and stop.
    if start_row_group >= parquet.num_row_groups:
        logger.info(
            "already fully loaded, nothing to do",
            extra={
                "dataset": dataset,
                "fingerprint": fingerprint,
                "progress": f"{parquet.num_row_groups}/{parquet.num_row_groups}",
            },
        )
        return 0

    mode = "fresh" if (start_row_group, committed_offset) == (0, 0) else "resume"
    logger.info(
        "load started",
        extra={
            "dataset": dataset,
            "fingerprint": fingerprint,
            "mode": mode,
            "row_groups_total": parquet.num_row_groups,  # a count, e.g. 31
            "resume_from_row_group": start_row_group,  # 0-based, as in the checkpoint
            "resume_from_row": committed_offset,  # rows of that group already saved
        },
    )

    # Step 2: go through the remaining row groups, one at a time.
    total = 0
    for row_group in range(start_row_group, parquet.num_row_groups):
        # Only the first row group of a resumed run can be partly done.
        skip_rows = committed_offset if row_group == start_row_group else 0
        kept = _load_row_group(
            db,
            dataset,
            columns,
            transform,
            stmt,
            parquet,
            fingerprint,
            row_group,
            skip_rows,
            read_batch_rows,
        )
        total += kept
        logger.info(
            "row group loaded",
            extra={
                "row_group": row_group,  # 0-based, matches the checkpoint table
                "progress": f"{row_group + 1}/{parquet.num_row_groups}",  # for people
                "rows": kept,
                "rows_total": total,
            },
        )

    logger.info("load finished", extra={"dataset": dataset, "rows_total": total})
    return total


def _load_row_group(
    db: Database,
    dataset: str,
    columns: list[str],
    transform: Callable[[pl.LazyFrame], pl.LazyFrame],
    stmt: Insert,
    parquet: pq.ParquetFile,
    fingerprint: str,
    row_group: int,
    skip_rows: int,
    read_batch_rows: int,
) -> int:
    """Load one row group batch by batch; each batch commits with its checkpoint.

    Returns:
        Number of rows upserted from this row group.
    """
    rows_in_group = parquet.metadata.row_group(row_group).num_rows
    batches = parquet.iter_batches(
        row_groups=[row_group],
        columns=columns,
        batch_size=read_batch_rows,
    )

    position = 0  # how many rows of this row group we have read so far
    kept = 0
    for arrow_batch in batches:
        batch_start = position
        position += arrow_batch.num_rows

        # Already committed by an earlier run: skip the whole batch.
        if position <= skip_rows:
            continue
        # The checkpoint falls inside this batch: drop the rows already committed.
        if batch_start < skip_rows:
            arrow_batch = arrow_batch.slice(skip_rows - batch_start)

        # Transform: Swindon box, clean columns. Most batches keep 0 rows.
        rows = transform(pl.from_arrow(arrow_batch).lazy()).collect()

        # Where the next run should start if we crash after this commit.
        # At the end of the row group, point at the next one, so it isn't re-read.
        if position == rows_in_group:
            next_row_group, next_offset = row_group + 1, 0
        else:
            next_row_group, next_offset = row_group, position

        # Load: data and checkpoint in ONE transaction: both commit, or neither.
        with db.engine.begin() as conn:
            for chunk in rows.iter_slices(INSERT_SLICE_ROWS):
                conn.execute(stmt, chunk.to_dicts())
            save_checkpoint(conn, dataset, fingerprint, next_row_group, next_offset)

        # INFO only when rows reached the DB; empty batches (most of them) are DEBUG.
        if rows.height:
            logger.info(
                "batch committed",
                extra={
                    "row_group": row_group,
                    "rows": rows.height,
                    "checkpoint": f"{next_row_group}:{next_offset}",
                },
            )
        else:
            logger.debug(
                "batch had no Swindon rows",
                extra={"row_group": row_group, "position": position},
            )

        kept += rows.height

    return kept


def _fingerprint(path: Path, parquet: pq.ParquetFile) -> str:
    """Cheap ID for this exact file: name, size in bytes, row count.

    A re-downloaded file gets a new fingerprint, so its load starts from the top.
    """
    return f"{path.name}:{path.stat().st_size}:{parquet.metadata.num_rows}"
