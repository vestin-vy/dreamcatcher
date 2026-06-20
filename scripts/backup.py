"""Backup the database and uploaded images (SPEC-BILLING §6).

Copies `data.db` and `static/uploads/` into `backups/<UTC-timestamp>/`.

Run:  python -m scripts.backup
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def run() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = BASE_DIR / "backups" / stamp
    dest.mkdir(parents=True, exist_ok=True)

    db = BASE_DIR / "data.db"
    if db.exists():
        shutil.copy2(db, dest / "data.db")
        print(f"  data.db -> {dest / 'data.db'}")
    else:
        print("  data.db not found, skipping")

    uploads = BASE_DIR / "static" / "uploads"
    if uploads.exists():
        shutil.copytree(uploads, dest / "uploads", dirs_exist_ok=True)
        print(f"  static/uploads/ -> {dest / 'uploads'}")
    else:
        print("  static/uploads/ not found, skipping")

    print(f"Backup complete: {dest}")
    return dest


if __name__ == "__main__":
    run()
