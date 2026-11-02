"""Manage the Database for this application."""

from sqlalchemy import Engine, create_engine


class Database:
    """Main class for managing database and connections to it for this application.

    Args:
        url: Database URL for connecting to it.
    """

    def __init__(self, url: str) -> None:
        """Initialize the class with a DB URL."""
        self.engine: Engine = create_engine(url)
        """Database engine from sqlalchemy using create_engine method.

        create_engine is a lazy method. No connection is made to the actual DB.
        First connection is made only when the engine is first used.
        """
