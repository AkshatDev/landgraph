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

from .load import load_title_boundaries_resumable
from .resources import CheckResources
from .transform import TITLE_BOUNDARY_COLUMNS
from .website_client import WebClient

BASE_URL = "https://www.planning.data.gov.uk"
FILES_URL = "https://files.planning.data.gov.uk"
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse the command line."""
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
    """Orchestrator for ETL pipeline."""
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
        if args.dataset != "title-boundary":
            raise ValueError(
                f"load supports only title-boundary for now, got {args.dataset}"
            )
        resources = CheckResources()
        resources.check_memory()
        resources.apply_thread_limits()
        batch_rows = resources.batch_rows_for(args.path, TITLE_BOUNDARY_COLUMNS)
        db = Database(os.environ["DATABASE_URL"])
        db.create_tables()
        rows = load_title_boundaries_resumable(
            db, args.path, read_batch_rows=batch_rows
        )
        logger.info("pipeline finished", extra={"rows": rows})


def run() -> None:
    """Start the runner for ETL pipeline, pick whatever stage you want."""
    correlation_id.set(uuid.uuid4().hex)
    configure_logging()
    try:
        main()
    except Exception:
        logger.exception("pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    run()
