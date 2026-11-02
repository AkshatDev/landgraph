"""Run the pipeline: ``python -m landgraph.pipeline``.

For now it only extracts: it fetches a few pages and logs what it got.
Transform, load and checkpoints will be added here.
"""

import argparse
import logging
import sys
import uuid
from pathlib import Path

import httpx
from asgi_correlation_id import correlation_id

from landgraph.log_config import configure_logging

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
    """Fetch pages of a dataset and log each one."""
    # parser = argparse.ArgumentParser(prog="python -m landgraph.pipeline")
    # parser.add_argument("dataset", nargs="?", default="title-boundary")
    # parser.add_argument("--limit", type=int, default=50, help="entities per page")
    # parser.add_argument("--start-offset", type=int, default=0)
    # parser.add_argument("--max-pages", type=int, default=3, help="stop early (demo)")
    # args = parser.parse_args()

    # logger.info("pipeline started", extra=vars(args))

    # with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
    #     extract = Extract(client)
    #     pages = extract.iter_pages(
    #         args.dataset, limit=args.limit, start_offset=args.start_offset
    #     )
    #     for page_number, (offset, entities) in enumerate(pages, start=1):
    #         logger.info(
    #             "page received",
    #             extra={"page": page_number, "offset": offset, "rows": len(entities)},
    #         )
    #         if page_number == args.max_pages:
    #             break
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
        raise NotImplementedError("load is not built yet")

    logger.info("runner finished")


def run() -> None:
    """Start the runner for ETL pipleline, pick whatever stage you want."""
    correlation_id.set(uuid.uuid4().hex)
    configure_logging()
    try:
        main()
    except Exception:
        logger.exception("pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    run()
