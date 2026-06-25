"""Migrate all DreamCatcher data from the dev SQLite DB into a target PostgreSQL DB.

Copies every table preserving IDs and relations, in FK-safe order:
  Category -> CategoryTranslation -> Product -> ProductTranslation -> ProductImage
  -> Order -> OrderItem -> Setting

Safety model:
  * DRY-RUN by default: prints per-table source/target counts + a few sample rows,
    writes NOTHING. Pass --commit to actually write.
  * Refuses to write if any target table already has rows, unless --force.
  * Opens the SQLite source read-only-ish (never modifies/deletes data.db).
  * After writing, resets Postgres ID sequences to MAX(id) so future inserts don't
    collide with the preserved IDs.

Usage:
  # dry run (no writes) — target from --target or env DB_URL/DATABASE_URL
  python scripts/migrate_sqlite_to_postgres.py --target "postgresql://user:pass@host/db"
  # execute
  python scripts/migrate_sqlite_to_postgres.py --target "..." --commit

Schema is created on the target via SQLModel.metadata.create_all (no Alembic needed
for this one-time jump; use Alembic later for incremental migrations).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))  # allow `import app.*` when run as a script

from sqlalchemy import func, text  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine, select  # noqa: E402

from app.config import _normalize_db_url  # noqa: E402
from app.models import (  # noqa: E402
    Category, CategoryTranslation, Product, ProductTranslation, ProductImage,
    Order, OrderItem, Setting,
)

# FK-safe order: parents before children.
MODELS = [Category, CategoryTranslation, Product, ProductTranslation, ProductImage,
          Order, OrderItem, Setting]

log = logging.getLogger("migrate")


def _setup_logging() -> None:
    logs = BASE_DIR / "logs"
    logs.mkdir(exist_ok=True)
    logfile = logs / "migration.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in (logging.FileHandler(logfile, encoding="utf-8"), logging.StreamHandler()):
        h.setFormatter(fmt)
        root.addHandler(h)


def _mask(url: str) -> str:
    """Hide the password in a DB URL for safe logging."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        creds, host = rest.split("@", 1)
        if ":" in creds:
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{host}"
    return url


def _count(session: Session, model) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def _reset_sequence(session: Session, model) -> None:
    """Postgres only: align the id sequence with MAX(id) after explicit-id inserts."""
    if "id" not in model.model_fields:
        return  # e.g. Setting (PK is `key`, no serial sequence)
    table = model.__tablename__
    session.exec(text(
        "SELECT setval(pg_get_serial_sequence(:t, 'id'), "
        "(SELECT COALESCE(MAX(id), 1) FROM " + table + "), true)"
    ).bindparams(t=table))


def main() -> int:
    ap = argparse.ArgumentParser(description="Migrate DreamCatcher SQLite -> PostgreSQL.")
    ap.add_argument("--source", default=str(BASE_DIR / "data.db"),
                    help="Path to the source SQLite file (default: data.db).")
    ap.add_argument("--target", default=os.getenv("DB_URL") or os.getenv("DATABASE_URL"),
                    help="Target DB URL (default: env DB_URL/DATABASE_URL).")
    ap.add_argument("--commit", action="store_true", help="Actually write (default: dry run).")
    ap.add_argument("--force", action="store_true", help="Allow writing into non-empty target tables.")
    args = ap.parse_args()

    _setup_logging()
    started = datetime.now(timezone.utc)

    src_path = Path(args.source)
    if not src_path.exists():
        log.error("Source SQLite not found: %s", src_path)
        return 2
    if not args.target:
        log.error("No target DB URL. Pass --target or set DB_URL/DATABASE_URL.")
        return 2

    target_url = _normalize_db_url(args.target)
    if target_url.startswith("sqlite"):
        log.error("Target resolves to SQLite (%s) — refusing. This tool targets PostgreSQL.",
                  _mask(target_url))
        return 2

    source_url = f"sqlite:///{src_path.as_posix()}"
    log.info("Migration start (%s). source=%s target=%s mode=%s",
             started.isoformat(), source_url, _mask(target_url),
             "COMMIT" if args.commit else "DRY-RUN")

    src_engine = create_engine(source_url, connect_args={"check_same_thread": False})
    tgt_engine = create_engine(target_url, pool_pre_ping=True)

    # Ensure the schema exists on the target before counting/inserting.
    SQLModel.metadata.create_all(tgt_engine)

    with Session(src_engine) as src, Session(tgt_engine) as tgt:
        # --- preflight: counts + sample rows + emptiness guard ---
        nonempty_targets = []
        for model in MODELS:
            sc, tc = _count(src, model), _count(tgt, model)
            sample = src.exec(select(model).limit(3)).all()
            log.info("table %-20s source=%-5d target=%-5d", model.__tablename__, sc, tc)
            for row in sample:
                log.info("    sample %s: %s", model.__tablename__, row.model_dump())
            if tc > 0:
                nonempty_targets.append(f"{model.__tablename__}({tc})")

        if nonempty_targets and not args.force:
            log.error("Target already has data in: %s. Refusing (use --force to override).",
                      ", ".join(nonempty_targets))
            return 3

        if not args.commit:
            log.info("DRY-RUN complete — nothing written. Re-run with --commit to migrate.")
            return 0

        # --- copy, preserving ids + relations, in FK-safe order ---
        total = 0
        for model in MODELS:
            rows = src.exec(select(model)).all()
            for r in rows:
                tgt.add(model(**r.model_dump()))
            tgt.commit()
            log.info("copied %-20s %d rows", model.__tablename__, len(rows))
            total += len(rows)

        # --- realign Postgres sequences with the preserved ids ---
        for model in MODELS:
            _reset_sequence(tgt, model)
        tgt.commit()
        log.info("sequences realigned")

        log.info("Migration COMPLETE — %d rows copied across %d tables.", total, len(MODELS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
