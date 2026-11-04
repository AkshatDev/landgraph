"""Paged API client for planning.data.gov.uk (alternative source; not used by the CLI).

Built first, then replaced by the bulk download after measuring: ~22 s per 100 rows
and disconnects at limit=500, against 41 s for the whole national file. Kept for small
incremental updates (filter by entry_date) and as the retry/backoff reference.
"""

import logging
import time
from collections.abc import Iterator

import httpx

SWINDON_ENTITY: int = 8600027
MAX_ATTEMPTS: int = 5

logger = logging.getLogger(__name__)


class Extract:
    """Paged reader for the planning.data.gov.uk entity API, limited to Swindon.

    Args:
        client: An ``httpx.Client`` with ``base_url`` set to the API host. Injected
            so tests can pass one backed by ``httpx.MockTransport``.
    """

    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def fetch_page(self, dataset: str, offset: int, limit: int) -> list[dict]:
        """Fetch one page of ``dataset`` inside Swindon, retrying temporary failures.

        Network errors, 5xx and 429 are retried up to ``MAX_ATTEMPTS`` times with
        exponential backoff (2, 4, 8, ... seconds). Other 4xx errors fail at once,
        because retrying a bad request can't succeed.

        Args:
            dataset: planning.data.gov.uk dataset name, e.g. ``"title-boundary"``.
            offset: Position of the first entity to return.
            limit: Number of entities per page.

        Returns:
            The entities on that page; an empty list means there are no more pages.

        Raises:
            httpx.HTTPStatusError: on a 4xx (other than 429), or a 5xx/429 that persists after retries.
            httpx.TransportError: if the network keeps failing after retries.
        """
        params = {
            "dataset": dataset,
            "offset": offset,
            "limit": limit,
            "geometry_entity": SWINDON_ENTITY,
            "field": [
                "reference",
                "entity",
                "geometry",
                "start-date",
                "end-date",
                "entry-date",
            ],
        }
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self.client.get("/entity.json", params=params)
                response.raise_for_status()
                data = response.json()
                return data["entities"]
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code < 500
                    and exc.response.status_code != 429
                ):
                    raise
                if attempt == MAX_ATTEMPTS:
                    raise
                logger.warning(
                    "retrying",
                    extra={"offset": offset, "attempt": attempt, "error": str(exc)},
                )
                time.sleep(2**attempt)

    def iter_pages(
        self, dataset: str, limit: int, start_offset: int = 0
    ) -> Iterator[tuple[int, list[dict]]]:
        """Yield every page of ``dataset`` inside Swindon, one page at a time.

        Pages are fetched lazily: the next page is requested only when the caller
        asks for it, so only one page is held in memory.

        Args:
            dataset: planning.data.gov.uk dataset name, e.g. ``"title-boundary"``.
            limit: Number of entities per page.
            start_offset: Offset to start from; pass a saved checkpoint to resume.

        Yields:
            ``(offset, entities)`` for each non-empty page, where ``offset`` is the
            position of the page's first entity.
        """
        offset = start_offset
        while True:
            entities = self.fetch_page(dataset, offset=offset, limit=limit)
            if not entities:
                return
            yield offset, entities
            if len(entities) < limit:
                return
            offset += limit
