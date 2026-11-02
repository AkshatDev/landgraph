"""The main entry point for the application to start a FastAPI application."""

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

from .db import Database
from .log_config import configure_logging
from .schemas import Health, Ready

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Run start-up and shutdown code for the app.

    Logging is configured here rather than in ``create_app()``:
    the server applies its own logging setup after importing the app,
    which would overwrite ours.
    """
    configure_logging()
    yield


def create_app(database_url: str) -> FastAPI:
    """Create a FastAPI application."""
    app = FastAPI(lifespan=lifespan)
    app.state.db = Database(database_url)

    @app.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Log one line per request with method, path, status code and duration."""
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
        """Report that the service is running."""
        return Health(status="ok")

    @app.get("/ready")
    def ready(request: Request, response: Response) -> Ready:
        """Report whether all services are ready or not."""
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

    app.add_middleware(CorrelationIdMiddleware)
    return app


app = create_app(os.environ["DATABASE_URL"])
