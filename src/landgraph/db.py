"""Manage the Database for this application."""

from typing import Any

from sqlalchemy import Engine, create_engine, event

from .models import Base

# Connection pool: how many connections this process keeps open to Postgres.
POOL_SIZE = 5  # connections kept open and reused
MAX_OVERFLOW = 5  # extra connections allowed under load, closed when returned
POOL_TIMEOUT_S = 2  # max wait for a free connection before giving up

# Opening a new connection (network + TLS + auth). Neon can take ~1 s to wake up.
CONNECT_TIMEOUT_S = 5


class Database:
    """Main class for managing database and connections to it for this application.

    Every wait is bounded, so a slow or unreachable database makes requests fail
    fast (the API turns these errors into 503) instead of piling up.

    Args:
        url: Database URL for connecting to it.
        statement_timeout_ms: If set, Postgres cancels any single SQL statement
            that runs longer than this. Opt-in: the API sets it, the pipeline
            doesn't (its batch upserts and table creation may legitimately take
            longer).
    """

    def __init__(self, url: str, statement_timeout_ms: int | None = None) -> None:
        """Initialize the class with a DB URL."""
        self.engine: Engine = create_engine(
            url,
            pool_pre_ping=True,  # test a pooled connection before handing it out
            pool_size=POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_timeout=POOL_TIMEOUT_S,
            connect_args={"connect_timeout": CONNECT_TIMEOUT_S},
        )
        """Database engine from sqlalchemy using create_engine method.

        create_engine is a lazy method. No connection is made to the actual DB.
        First connection is made only when the engine is first used.
        """

        if statement_timeout_ms is not None:
            _set_statement_timeout(self.engine, statement_timeout_ms)

    def create_tables(
        self,
    ) -> None:
        """Create any missing tables. Existing tables are left unchanged."""
        Base.metadata.create_all(self.engine)


def _set_statement_timeout(engine: Engine, timeout_ms: int) -> None:
    """Run ``SET statement_timeout`` on every new connection the pool opens.

    It's a session setting, so it lasts for the life of the connection and
    applies to every query sent over it.
    """

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _record: Any) -> None:  # noqa: ANN401
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET statement_timeout = {int(timeout_ms)}")
        dbapi_connection.commit()
