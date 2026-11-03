"""Check the machine's resources and turn them into safe settings for the pipeline.

Everything here is applied at runtime, before the load starts:

- ``check_memory``: refuse to start if free memory is too low (the national file
  once crashed WSL by running out of memory).
- ``apply_thread_limits``: cap pyarrow's CPU and I/O thread pools.
- ``batch_rows_for``: pick how many rows to read per batch from the parquet footer.

Polars threads are not set here: Polars fixes its thread pool when it is imported
(``POLARS_MAX_THREADS`` must be set before ``import polars``), so it can't be
changed at runtime. At ~50k rows per batch it makes little difference.

Note: inside Docker, ``psutil`` and ``os.cpu_count`` see the whole WSL VM, not a
container ``mem_limit``.
"""

import logging
import os
from pathlib import Path

import psutil
import pyarrow as pa
import pyarrow.parquet as pq

from .exceptions import InsufficientMemoryError

logger = logging.getLogger(__name__)

MB = 1024 * 1024
GB = 1024 * MB

# Peak measured for the load loop on the 3.9 GB title-boundary file was ~0.7 GB
# (one row group at a time). 1.5 GB leaves headroom for Python and the DB driver.
MIN_FREE_MEMORY = int(1.5 * GB)

BUDGET_SHARE = 0.25  # use at most this share of free memory for batch data
BUDGET_CAP = 1 * GB  # and never more than this, however much is free
MAX_THREADS = 4  # more threads read faster but hold more buffers at once

# Rough peak memory per batch, as a multiple of its raw size: the Arrow batch,
# the Polars copy, the transformed frame and temporary strings during parsing.
PEAK_MULTIPLIER = 4
MIN_BATCH_ROWS = 10_000  # smaller batches mean too many tiny transactions
# Measured on title-boundary (4 pyarrow threads): 50k rows -> 0.69 GB peak,
# 100k -> 0.73 GB, 250k -> 1.08 GB. Above 100k memory rises with little speed gain.
MAX_BATCH_ROWS = 100_000


class CheckResources:
    """A snapshot of free memory and CPUs, with the settings derived from it.

    Create one at the start of a run; the numbers are read once and logged.

    Attributes:
        available_memory: Free memory in bytes when the snapshot was taken.
        processing_budget: Bytes the load may use for batch data
            (``BUDGET_SHARE`` of free memory, at most ``BUDGET_CAP``).
        cpu_count: CPUs this process may run on.
        threads: Thread count for pyarrow (``cpu_count``, at most ``MAX_THREADS``).
    """

    def __init__(self) -> None:
        """Read free memory and CPU count from the OS and derive the limits."""
        self.available_memory: int = psutil.virtual_memory().available

        # Leave the rest for PostgreSQL, Docker, WSL and Python itself.
        self.processing_budget: int = min(
            int(self.available_memory * BUDGET_SHARE), BUDGET_CAP
        )

        # process_cpu_count respects CPU affinity (e.g. `taskset`); cpu_count doesn't.
        self.cpu_count: int = os.process_cpu_count() or 1
        self.threads: int = min(self.cpu_count, MAX_THREADS)

        logger.info(
            "resources checked",
            extra={
                "available_mb": _mb(self.available_memory),
                "budget_mb": _mb(self.processing_budget),
                "cpu_count": self.cpu_count,
                "threads": self.threads,
            },
        )

    def check_memory(self, minimum_bytes: int = MIN_FREE_MEMORY) -> None:
        """Stop before starting if there isn't enough free memory.

        Failing here with a clear message is better than the OS killing the
        process (or the whole WSL VM) halfway through.

        Args:
            minimum_bytes: Free memory needed to run safely.

        Raises:
            InsufficientMemoryError: If free memory is below ``minimum_bytes``.
        """
        if self.available_memory < minimum_bytes:
            raise InsufficientMemoryError(
                f"{_mb(self.available_memory)} MB free, need {_mb(minimum_bytes)} MB; "
                "close notebooks or other containers and try again"
            )

    def apply_thread_limits(self) -> None:
        """Cap pyarrow's thread pools for this process.

        ``cpu_count`` threads decode parquet columns; ``io_thread_count`` threads
        read from disk. Both default to all CPUs, and each thread holds its own
        buffers, so fewer threads means a lower memory peak.
        """
        pa.set_cpu_count(self.threads)
        pa.set_io_thread_count(self.threads)
        logger.info("pyarrow threads set", extra={"threads": self.threads})

    def batch_rows_for(self, path: Path, columns: list[str] | None = None) -> int:
        """Choose how many rows to read per batch so a batch fits the memory budget.

        Uses only the parquet footer (no data is read): the uncompressed size of
        the columns we read, divided by the row count, gives bytes per row.

        Args:
            path: The parquet file to be loaded.
            columns: Columns that will be read. ``None`` counts all of them.

        Returns:
            Rows per batch, between ``MIN_BATCH_ROWS`` and ``MAX_BATCH_ROWS``.
        """
        metadata = pq.ParquetFile(path).metadata

        wanted = set(columns) if columns else None
        uncompressed_bytes = 0
        for rg in range(metadata.num_row_groups):
            row_group = metadata.row_group(rg)
            for col in range(row_group.num_columns):
                chunk = row_group.column(col)
                if wanted is None or chunk.path_in_schema in wanted:
                    uncompressed_bytes += chunk.total_uncompressed_size

        bytes_per_row = max(uncompressed_bytes / max(metadata.num_rows, 1), 1)
        rows = int(self.processing_budget / (bytes_per_row * PEAK_MULTIPLIER))
        batch_rows = max(MIN_BATCH_ROWS, min(rows, MAX_BATCH_ROWS))

        logger.info(
            "batch size chosen",
            extra={
                "path": str(path),
                "bytes_per_row": round(bytes_per_row),
                "budget_mb": _mb(self.processing_budget),
                "batch_rows": batch_rows,
            },
        )
        return batch_rows


def _mb(n_bytes: int) -> float:
    """Convert bytes to megabytes, rounded for logs."""
    return round(n_bytes / MB, 1)
