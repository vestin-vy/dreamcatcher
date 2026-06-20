"""Database engine, sessions, and schema init (SPEC §3)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# check_same_thread=False so SQLite works across FastAPI's threadpool.
engine = create_engine(
    settings.DB_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create all tables. Import models first so they register with SQLModel."""
    from app import models  # noqa: F401  (registers tables on import)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a DB session."""
    with Session(engine) as session:
        yield session
