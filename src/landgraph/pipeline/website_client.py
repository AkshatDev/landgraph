"""Download national dataset files from files.planning.data.gov.uk.

Checks which formats exist with HEAD requests, picks the smallest, and streams
it into the ``raw/`` landing zone with progress logs. Never touches the database.
"""

import logging
import time
from datetime import date
from pathlib import Path

import httpx

from .exceptions import NoSupportedFormatError

PROGRESS_STEP_PERCENT = 10  # log a progress line every 10%

logger = logging.getLogger(__name__)


class WebClient:
    """Client for the planning.data.gov.uk file host.

    Args:
        client: An ``httpx.Client`` with ``base_url`` set to the file host. Injected
            so tests can pass one backed by ``httpx.MockTransport``.
    """

    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def check_data_size_and_formats(self, dataset: str) -> dict[str, int]:
        """Find which supported formats exist for ``dataset`` and how big each is.

        Sends a HEAD request per format (parquet, csv), so nothing is downloaded. The
        file host answers 403 (not 404) for files that don't exist; both are skipped.

        Args:
            dataset: planning.data.gov.uk dataset name, e.g. ``"title-boundary"``.

        Returns:
            ``{format: size in bytes}`` for every available format.

        Raises:
            NoSupportedFormatError: If none of the supported formats exists.
            httpx.HTTPStatusError: On any other HTTP error.
        """
        formats = ["parquet", "csv"]
        sizes = {}
        for fmt in formats:
            response = self.client.head(f"/dataset/{dataset}.{fmt}")
            if response.status_code in (403, 404):  # s3 returns a 403 for no resource.
                continue
            response.raise_for_status()
            size = response.headers.get("content-length")
            if not size:
                continue
            sizes[fmt] = int(size)

        if not sizes:
            raise NoSupportedFormatError(f"{dataset}: none of {formats} available")

        return sizes

    def download(self, dataset: str, raw_dir: Path) -> Path:
        """Download the smallest available format of ``dataset`` into ``raw_dir``.

        The file is saved as ``raw_dir/<dataset>/<YYYY-MM-DD>/<dataset>.<format>``.
        If that file already exists, nothing is downloaded (safe to re-run). The data
        is streamed in 1 MB chunks to a ``.part`` file and renamed only when complete,
        so an interrupted download never leaves a file that looks finished.

        Args:
            dataset: planning.data.gov.uk dataset name, e.g. ``"title-boundary"``.
            raw_dir: Root of the landing zone, usually ``raw``.

        Returns:
            Path of the downloaded (or already present) file.

        Raises:
            NoSupportedFormatError: If no supported format exists for ``dataset``.
            httpx.HTTPError: If the download fails.
        """
        sizes = self.check_data_size_and_formats(dataset)
        fmt = min(sizes, key=sizes.__getitem__)

        final_path = raw_dir / dataset / date.today().isoformat() / f"{dataset}.{fmt}"
        if final_path.exists():
            logger.info("already downloaded", extra={"path": str(final_path)})
            return final_path

        final_path.parent.mkdir(parents=True, exist_ok=True)
        part_path = final_path.with_name(final_path.name + ".part")

        total = sizes[fmt]
        logger.info(
            "download started",
            extra={"dataset": dataset, "format": fmt, "mb_total": _mb(total)},
        )
        start = time.perf_counter()
        done = 0
        next_percent = PROGRESS_STEP_PERCENT
        with self.client.stream("GET", f"/dataset/{dataset}.{fmt}") as response:
            response.raise_for_status()
            with part_path.open("wb") as file:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    file.write(chunk)
                    done += len(chunk)
                    percent = done * 100 // total
                    if percent >= next_percent:
                        _log_progress(dataset, percent, done, total, start)
                        # next multiple of the step above where we are now
                        step = PROGRESS_STEP_PERCENT
                        next_percent = (percent // step + 1) * step

        part_path.rename(final_path)
        seconds = time.perf_counter() - start
        logger.info(
            "download finished",
            extra={
                "path": str(final_path),
                "mb": _mb(done),
                "seconds": round(seconds, 1),
            },
        )
        return final_path


def _mb(n_bytes: int) -> float:
    """Convert bytes to megabytes, rounded for logs.

    Args:
        n_bytes: A size in bytes.

    Returns:
        The size in MB (1 MB = 1024 * 1024 bytes), rounded to one decimal place.
    """
    return round(n_bytes / 1024 / 1024, 1)


def _log_progress(
    dataset: str, percent: int, done: int, total: int, start: float
) -> None:
    """Log one progress line: percent, size so far, speed and time remaining.

    Args:
        dataset: Dataset being downloaded.
        percent: Whole percent done.
        done: Bytes downloaded so far.
        total: Total bytes expected (from ``Content-Length``).
        start: ``time.perf_counter()`` value when the download started.
    """
    elapsed = time.perf_counter() - start
    speed = done / elapsed if elapsed > 0 else 0.0  # bytes per second
    eta = (total - done) / speed if speed > 0 else None
    logger.info(
        "download progress",
        extra={
            "dataset": dataset,
            "percent": percent,
            "mb_done": _mb(done),
            "mb_total": _mb(total),
            "mb_per_s": _mb(int(speed)),
            "eta_s": round(eta) if eta is not None else None,
        },
    )
