"""Database access: one engine per process, with every wait bounded.

``Database`` owns the SQLAlchemy engine and its connection pool, and creates
missing tables. Queries live elsewhere (``queries.py``, ``pipeline/``) and take a
connection from this engine.
"""

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
    """Owns the SQLAlchemy engine and its connection pool for one process.

    Every wait is bounded, so a slow or unreachable database makes requests fail
    fast (the API turns these errors into 503) instead of piling up: at most 2 s
    for a free pooled connection, 5 s to open a new one, and an optional server-side
    statement timeout. The API sets that timeout; the pipeline doesn't, because its
    batch upserts and table creation may legitimately take longer.

    Attributes:
        engine: The SQLAlchemy engine. Lazy: no connection is made until first use.
    """

    def __init__(self, url: str, statement_timeout_ms: int | None = None) -> None:
        """Create the engine. No connection is opened until the first query.

        Args:
            url: SQLAlchemy database URL, e.g. ``postgresql+psycopg://user:pass@host/db``.
            statement_timeout_ms: If set, Postgres cancels any statement running longer
                than this many milliseconds. ``None`` (the default) means no limit.
        """
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
        """Create any missing tables and their indexes (including the GiST indexes).

        Existing tables are left unchanged: this does not add, drop or alter columns,
        so it is not a migration tool. Called by the pipeline before loading, never by
        the API (which should not need permission to change the schema).
        """
        Base.metadata.create_all(self.engine)


def _set_statement_timeout(engine: Engine, timeout_ms: int) -> None:
    """Run ``SET statement_timeout`` on every new connection the pool opens.

    It's a session setting, so it lasts for the life of the connection and
    applies to every query sent over it. Postgres enforces it on the server, so a
    cancelled query stops using database resources (a client-side timeout alone
    would leave it running).

    Args:
        engine: The engine whose new connections should get the timeout.
        timeout_ms: Maximum statement duration in milliseconds.
    """

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, _record: Any) -> None:  # noqa: ANN401
        """Set the timeout on a freshly opened DBAPI connection.

        Args:
            dbapi_connection: The raw psycopg connection SQLAlchemy just opened.
            _record: SQLAlchemy's pool bookkeeping for that connection (unused).
        """
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET statement_timeout = {int(timeout_ms)}")
        dbapi_connection.commit()
