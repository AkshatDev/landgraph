"""FastAPI application: wiring, middleware and health checks.

``create_app`` builds the app (database, request logging, correlation IDs,
routers). Public endpoints live in versioned routers such as ``api_v1``;
``/health`` and ``/ready`` stay here, unversioned, because they serve the
platform rather than API clients. ``app`` at the bottom is what the server runs.
"""

import logging
import os
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from . import api_v1
from .db import Database
from .log_config import configure_logging
from .schemas import Health, Ready

logger = logging.getLogger(__name__)

API_STATEMENT_TIMEOUT_MS = 2000


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Run start-up and shutdown code for the app.

    Logging is configured here rather than in ``create_app()``:
    the server applies its own logging setup after importing the app,
    which would overwrite ours.

    Args:
        app: The application being started (unused; required by FastAPI).

    Yields:
        Control to FastAPI while the app is serving requests.
    """
    configure_logging()
    yield


def create_app(database_url: str) -> FastAPI:
    """Create and configure the FastAPI application.

    Builds the database engine (with a 2 s statement timeout for API queries),
    adds request logging and correlation-ID middleware, and registers the health
    checks and the ``/v1`` router. A factory rather than a global so tests can build
    an app against any database.

    Args:
        database_url: SQLAlchemy URL of the PostGIS database to query.

    Returns:
        The configured application.
    """
    app = FastAPI(lifespan=lifespan)
    # API requests should never wait long: Postgres cancels any query over 2 s.
    app.state.db = Database(database_url, statement_timeout_ms=API_STATEMENT_TIMEOUT_MS)

    @app.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Log one line per request with method, path, status code and duration.

        Args:
            request: The incoming request.
            call_next: Passes the request to the rest of the app and returns its response.

        Returns:
            The response from the rest of the app, unchanged.
        """
        start = time.perf_counter()
        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "request finished",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response

    @app.get("/health")
    async def health() -> Health:
        """Report that the process is up and serving requests (liveness).

        Does not touch the database, so it stays green during a database outage.
        \f
        Returns:
            Always ``{"status": "ok"}``.
        """  # noqa: D301 (\f hides the rest from /docs)
        return Health(status="ok")

    @app.get("/ready")
    def ready(request: Request, response: Response) -> Ready:
        """Report whether the app's dependencies are reachable (readiness).

        Checks the database with ``SELECT PostGIS_Version()``. Returns 503 when a
        dependency is unavailable, so the platform can stop sending traffic here.
        \f
        Args:
            request: The incoming request (gives access to the app's database).
            response: Used to set the 503 status code when a check fails.

        Returns:
            ``"ready"`` with every check ``"ok"``, or ``"unavailable"`` (HTTP 503).
        """  # noqa: D301 (\f hides the rest from /docs)
        checks: dict[str, Literal["ok", "unavailable"]] = {}
        try:
            with request.app.state.db.engine.connect() as conn:
                conn.execute(text("SELECT PostGIS_Version()"))
                checks["database"] = "ok"
        except SQLAlchemyError:
            logger.exception("database not ready")
            checks["database"] = "unavailable"
        if all(value == "ok" for value in checks.values()):
            return Ready(status="ready", checks=checks)
        response.status_code = 503
        return Ready(status="unavailable", checks=checks)

    # Public API, versioned. /health and /ready stay unversioned: they serve
    # infrastructure (load balancers, uptime checks), not API clients.
    app.include_router(api_v1.router)

    app.add_middleware(CorrelationIdMiddleware)
    return app


app = create_app(os.environ["DATABASE_URL"])
