"""Run the pipeline: ``python -m landgraph.pipeline <command>``.

download <dataset>          file host → raw/ (no DB)
load <dataset> <raw file>   raw/ → transform → PostGIS, resumable via checkpoints
"""

import argparse
import logging
import os
import sys
import uuid
from pathlib import Path

import httpx
from asgi_correlation_id import correlation_id

from landgraph import Database
from landgraph.log_config import configure_logging

from .load import load_constraints_resumable, load_title_boundaries_resumable
from .resources import CheckResources
from .transform import CONSTRAINT_COLUMNS, TITLE_BOUNDARY_COLUMNS
from .website_client import WebClient

BASE_URL = "https://www.planning.data.gov.uk"
CONSTRAINT_DATASETS = ["conservation-area"]  # layers stored in the constraints table
FILES_URL = "https://files.planning.data.gov.uk"
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse the command line into a command and its arguments.

    Returns:
        The parsed arguments: ``command`` (``download`` or ``load``), ``dataset``,
        and ``raw_dir`` (download) or ``path`` (load).
    """
    parser = argparse.ArgumentParser(prog="python -m landgraph.pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    download = sub.add_parser("download", help="download a dataset into the raw folder")
    download.add_argument("dataset")
    download.add_argument("--raw-dir", type=Path, default=Path("raw"))

    load = sub.add_parser("load", help="load a downloaded file into the database")
    load.add_argument("dataset")
    load.add_argument("path", type=Path)

    return parser.parse_args()


def main() -> None:
    """Run one pipeline command: ``download`` or ``load``.

    ``download`` only touches the file host; ``load`` only touches the local file
    and the database. For ``load`` it checks free memory, caps pyarrow threads,
    sizes batches from the parquet footer, creates missing tables, then calls the
    loader for the dataset's table.

    Raises:
        ValueError: If ``load`` is given a dataset it can't load yet.
        KeyError: If ``DATABASE_URL`` is not set (``load`` only).
        InsufficientMemoryError: If there isn't enough free memory to load safely.
    """
    args = parse_args()
    logger.info(
        "pipeline started", extra={"command": args.command, "dataset": args.dataset}
    )

    if args.command == "download":
        with httpx.Client(
            base_url=FILES_URL, timeout=httpx.Timeout(30.0, read=120.0)
        ) as client:
            path = WebClient(client).download(args.dataset, args.raw_dir)
        logger.info("pipeline finished", extra={"path": str(path)})

    elif args.command == "load":
        if args.dataset == "title-boundary":
            columns = TITLE_BOUNDARY_COLUMNS
        elif args.dataset in CONSTRAINT_DATASETS:
            columns = CONSTRAINT_COLUMNS
        else:
            raise ValueError(
                f"load supports title-boundary and {CONSTRAINT_DATASETS}, "
                f"got {args.dataset}"
            )

        resources = CheckResources()
        resources.check_memory()
        resources.apply_thread_limits()
        batch_rows = resources.batch_rows_for(args.path, columns)
        db = Database(os.environ["DATABASE_URL"])
        db.create_tables()

        if args.dataset == "title-boundary":
            rows = load_title_boundaries_resumable(
                db, args.path, read_batch_rows=batch_rows
            )
        else:
            rows = load_constraints_resumable(
                db, args.path, args.dataset, read_batch_rows=batch_rows
            )
        logger.info("pipeline finished", extra={"rows": rows})


def run() -> None:
    """Entry point: set a run ID, configure logging, run the command, exit cleanly.

    Every log line of this run carries the same correlation ID. Any unhandled
    error is logged once, with its traceback, and the process exits with status 1
    so schedulers and CI see the failure.
    """
    correlation_id.set(uuid.uuid4().hex)
    configure_logging()
    try:
        main()
    except Exception:
        logger.exception("pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    run()
