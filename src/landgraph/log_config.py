"""Setup logging configuration."""

import os
from logging.config import dictConfig


def configure_logging() -> None:
    """Configure JSON logging to stdout for the whole app.

    The level comes from the ``LOG_LEVEL`` environment variable (default ``INFO``).
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
            }
        },
        "root": {"handlers": ["stdout"], "level": os.environ.get("LOG_LEVEL", "INFO")},
        "loggers": {
            "uvicorn": {"handlers": [], "propagate": True},
            "uvicorn.access": {"handlers": [], "propagate": False},
        },
    }

    dictConfig(config)
