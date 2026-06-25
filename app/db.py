"""Database engine, sessions, and schema init (SPEC §3)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# Engine selection is conditional on the backend:
#   * SQLite (local dev) needs check_same_thread=False to work across FastAPI's threadpool.
#   * PostgreSQL (prod) must NOT receive that arg; instead use pool_pre_ping to drop
#     connections dropped by the managed DB / idle timeouts.
_is_sqlite = settings.DB_URL.startswith("sqlite")
_engine_kwargs = {
    "echo": settings.DEBUG,
    "connect_args": {"check_same_thread": False} if _is_sqlite else {},
}
if not _is_sqlite:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(settings.DB_URL, **_engine_kwargs)


def init_db() -> None:
    """Create all tables. Import models first so they register with SQLModel."""
    from app import models  # noqa: F401  (registers tables on import)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a DB session."""
    with Session(engine) as session:
        yield session
