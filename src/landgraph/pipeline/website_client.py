"""A module for gathering info from data source website and other utility functions."""

import logging
import time
from datetime import date
from pathlib import Path

import httpx

from .exceptions import NoSupportedFormatError

PROGRESS_STEP_PERCENT = 10  # log a progress line every 10%

logger = logging.getLogger(__name__)


class WebClient:
    """Get information from the website regarding any dataset and other utils."""

    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def check_data_size_and_formats(self, dataset: str) -> dict[str, int]:
        """Check if a given dataset exists and return formats with sizes."""
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
        If that file already exists, nothing is downloaded (safe to re-run).

        Returns:
            Path of the downloaded (or already present) file.
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
    """Convert bytes to megabytes, rounded for logs."""
    return round(n_bytes / 1024 / 1024, 1)


def _log_progress(
    dataset: str, percent: int, done: int, total: int, start: float
) -> None:
    """Log one progress line: percent, size so far, speed and time remaining."""
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
