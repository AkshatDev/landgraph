"""Central logging configuration shared by the API and the pipeline.

Every module logs through ``logging.getLogger(__name__)``; this module decides
where those records go and what they look like (one JSON object per line).
"""

import os
from logging.config import dictConfig


def configure_logging() -> None:
    """Configure JSON logging to stdout for the whole process.

    Every record becomes one JSON line with time, level, logger name, message, any
    ``extra`` fields and the current correlation ID (request ID in the API, run ID
    in the pipeline). Existing loggers keep working (``disable_existing_loggers`` is
    off) and propagate to the root handler; uvicorn's access log is silenced because
    the app logs its own request line.

    The level comes from the ``LOG_LEVEL`` environment variable (default ``INFO``).
    Safe to call more than once: each call replaces the previous configuration.
    """
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.json.JsonFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            },
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "json",
                "filters": ["correlation_id"],
            }
        },
        "root": {"handlers": ["stdout"], "level": os.environ.get("LOG_LEVEL", "INFO")},
        "loggers": {
            "uvicorn": {"handlers": [], "propagate": True},
            "uvicorn.access": {"handlers": [], "propagate": False},
        },
        "filters": {
            "correlation_id": {"()": "asgi_correlation_id.CorrelationIdFilter"}
        },
    }

    dictConfig(config)
