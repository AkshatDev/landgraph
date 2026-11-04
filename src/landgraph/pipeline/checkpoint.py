"""Read and write load checkpoints in the ``pipeline_checkpoints`` table.

A checkpoint is ``(row_group, row_offset)``: everything before that position in
one source file is already in the database. Both functions take a connection
so the caller controls the transaction.
"""

from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.postgresql import insert

from landgraph.models import PipelineCheckpoint


def load_checkpoint(
    conn: Connection, dataset: str, fingerprint: str
) -> tuple[int, int]:
    """Return where to resume loading one source file.

    Args:
        conn: An open database connection.
        dataset: Dataset name, e.g. ``"title-boundary"``.
        fingerprint: Identifies the exact source file (see ``load._fingerprint``).

    Returns:
        ``(row_group, row_offset)`` to resume from, or ``(0, 0)`` if this file has
        no checkpoint yet.
    """
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
    together or not at all. An upsert: the first save inserts, later ones update.

    Args:
        conn: The connection holding the open transaction with the batch's data.
        dataset: Dataset name, e.g. ``"title-boundary"``.
        fingerprint: Identifies the exact source file.
        row_group: Next row group to read (the file's row-group count when done).
        row_offset: Rows of ``row_group`` already committed.
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
