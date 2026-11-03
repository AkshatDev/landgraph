"""Gets current checkpoint for data load into the DB."""

from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.postgresql import insert

from landgraph.models import PipelineCheckpoint


def load_checkpoint(
    conn: Connection, dataset: str, fingerprint: str
) -> tuple[int, int]:
    """Get the last checkpoint FROM the DB for a source DB."""
    stmt = select(PipelineCheckpoint.row_group, PipelineCheckpoint.row_offset).where(
        PipelineCheckpoint.dataset == dataset,
        PipelineCheckpoint.source_fingerprint == fingerprint,
    )
    row = conn.execute(stmt).one_or_none()
    return row if row else (0, 0)


def save_checkpoint(
    conn: Connection,
    dataset: str,
    fingerprint: str,
    row_group: int,
    row_offset: int,
) -> None:
    """Record how far the load has got, inside the caller's transaction.

    Takes a ``Connection`` (not a ``Database``) on purpose: the caller passes the
    same connection it used for the data upsert, so data and checkpoint commit
    together or not at all.
    """
    stmt = insert(PipelineCheckpoint).values(
        dataset=dataset,
        source_fingerprint=fingerprint,
        row_group=row_group,
        row_offset=row_offset,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            PipelineCheckpoint.dataset,
            PipelineCheckpoint.source_fingerprint,
        ],
        set_={
            "row_group": stmt.excluded.row_group,
            "row_offset": stmt.excluded.row_offset,
            "updated_at": func.now(),
        },
    )
    conn.execute(stmt)
