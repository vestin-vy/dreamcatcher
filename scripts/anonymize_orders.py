"""Anonymize old order PII per the retention policy (GDPR), Task 2 sweep entrypoint.

Anonymizes orders whose status is 'shipped' or 'cancelled', whose updated_at is older
than the retention window (admin Setting 'order_pii_retention_days', default 1095), and
that are not yet anonymized. Financial/accounting fields are always preserved.

DRY-RUN by default — lists what WOULD change and writes nothing. Pass --commit to apply.

Usage:
  python scripts/anonymize_orders.py            # dry run (no writes)
  python scripts/anonymize_orders.py --commit   # irreversibly anonymize due orders
  python scripts/anonymize_orders.py --days 365 # override retention window
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from sqlmodel import Session  # noqa: E402

from app.db import engine  # noqa: E402
from app import orders as orders_mod  # noqa: E402

log = logging.getLogger("anonymize")


def _setup_logging() -> None:
    logs = BASE_DIR / "logs"
    logs.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in (logging.FileHandler(logs / "anonymize.log", encoding="utf-8"),
              logging.StreamHandler()):
        h.setFormatter(fmt)
        root.addHandler(h)


def main() -> int:
    ap = argparse.ArgumentParser(description="Anonymize old order PII (GDPR retention).")
    ap.add_argument("--commit", action="store_true", help="Apply changes (default: dry run).")
    ap.add_argument("--days", type=int, default=None,
                    help="Override retention window in days (default: admin Setting).")
    args = ap.parse_args()

    _setup_logging()
    with Session(engine) as session:
        days = args.days if args.days is not None else orders_mod.pii_retention_days(session)
        mode = "COMMIT" if args.commit else "DRY-RUN"
        log.info("Anonymization sweep start (%s) retention=%d days mode=%s",
                 datetime.now(timezone.utc).isoformat(), days, mode)

        result = orders_mod.anonymize_sweep(session, retention_days=days, dry_run=not args.commit)
        for o in result["orders"]:
            log.info("  %-18s status=%-9s updated_at=%s",
                     o["number"], o["status"], o["updated_at"])
        if args.commit:
            log.info("Anonymized %d order(s).", result["count"])
        else:
            log.info("DRY-RUN: %d order(s) WOULD be anonymized. Re-run with --commit to apply.",
                     result["count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
