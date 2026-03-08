"""Database session management."""

import threading
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    """Database manager."""

    def __init__(self, database_url: str, db_echo: bool = False):
        """Initialize database connection."""
        self.database_url = database_url
        self.db_echo = db_echo
        self.engine = create_engine(
            database_url,
            echo=db_echo,
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def init_db(self) -> None:
        """Initialize database tables."""
        from .models import Base

        Base.metadata.create_all(bind=self.engine)

    def drop_db(self) -> None:
        """Drop all database tables."""
        from .models import Base

        Base.metadata.drop_all(bind=self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session]:
        """Get database session."""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()


_db: Database | None = None
_db_lock = threading.Lock()


def get_db() -> Database:
    """Get global database instance."""
    global _db
    if _db is None:
        with _db_lock:
            if _db is None:
                from ..config import get_settings

                settings = get_settings()
                _db = Database(settings.database_url, settings.db_echo)
    return _db


def init_db() -> None:
    """Initialize database."""
    get_db().init_db()


def drop_db() -> None:
    """Drop database tables."""
    get_db().drop_db()


@contextmanager
def get_session() -> Generator[Session]:
    """Get database session."""
    db = get_db()
    with db.get_session() as session:
        yield session
