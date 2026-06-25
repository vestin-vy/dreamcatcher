"""Database engine, sessions, and schema init (SPEC §3)."""
from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

log = logging.getLogger("db")

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


# Small additive schema fixes that create_all() cannot apply on an EXISTING table:
# SQLModel.metadata.create_all() only creates missing tables whole — it never adds a
# new column to a table that already exists. So when a column is added to a model after
# the table was first created on a persistent DB (e.g. Postgres in prod), the live table
# stays stale and INSERTs referencing the new column fail. These idempotent ALTERs close
# that gap until proper Alembic migrations exist. (table, column, DDL type) — Postgres.
# `order` is a reserved word and must stay quoted.
_ADDITIVE_COLUMNS = [
    ('"order"', "anonymized_at", "TIMESTAMP WITHOUT TIME ZONE"),
    # Product images stored in the DB (survive ephemeral-disk redeploys).
    ("productimage", "content_type", "VARCHAR"),
    ("productimage", "data", "BYTEA"),
    ("productimage", "thumb_data", "BYTEA"),
]


def _reconcile_schema() -> None:
    """Apply idempotent additive column migrations create_all() can't (Postgres only).

    Skipped on SQLite (local dev recreates the schema via the seed). Each statement uses
    ADD COLUMN IF NOT EXISTS, so this is safe to run on every startup and never touches or
    drops existing data.
    """
    if _is_sqlite:
        return
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, column, ddl_type in _ADDITIVE_COLUMNS:
            bare = table.strip('"')
            if bare not in existing_tables:
                continue  # create_all() will build it whole with all current columns
            conn.execute(text(
                f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl_type}'
            ))
    log.info("Schema reconcile complete (%d additive column check(s)).", len(_ADDITIVE_COLUMNS))


def init_db() -> None:
    """Create all tables. Import models first so they register with SQLModel."""
    from app import models  # noqa: F401  (registers tables on import)

    SQLModel.metadata.create_all(engine)
    _reconcile_schema()


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a DB session."""
    with Session(engine) as session:
        yield session
