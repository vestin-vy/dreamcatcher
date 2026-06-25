"""Order anonymization + retention tests (Task 2). Pure DB — no TestClient/sockets."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, select

try:
    from app.db import engine
    from app.models import Order, OrderItem
    from app import orders as orders_mod
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    engine = None
    _IMPORT_ERROR = exc


def _skip_if_no_app():
    if engine is None:
        pytest.skip(f"app not importable: {_IMPORT_ERROR}")


def _make_order(session, number, status, days_old, with_pii=True):
    ts = datetime.now(timezone.utc) - timedelta(days=days_old)
    o = Order(
        number=number, status=status,
        customer_name="Jane Doe", customer_email="jane@example.com", customer_phone="+30 210",
        ship_address="Ermou 1", ship_city="Athens", ship_postcode="10563", ship_country="GR",
        subtotal=100.0, vat_amount=19.35, vat_rate=24.0, total=100.0, currency="EUR",
        created_at=ts, updated_at=ts,
    )
    session.add(o); session.commit(); session.refresh(o)
    session.add(OrderItem(order_id=o.id, title_snapshot="Ring", price_snapshot=100.0,
                          qty=1, line_total=100.0))
    session.commit(); session.refresh(o)
    return o


def _cleanup(session, *orders):
    for o in orders:
        fresh = session.get(Order, o.id)
        if fresh:
            for it in list(fresh.items):
                session.delete(it)
            session.delete(fresh)
    session.commit()


def test_anonymize_order_overwrites_pii_keeps_financials():
    _skip_if_no_app()
    with Session(engine) as s:
        o = _make_order(s, "TEST-ANON-PII", "shipped", days_old=5000)
        before = (o.number, o.status, o.total, o.subtotal, o.vat_amount, o.currency,
                  o.items[0].price_snapshot)
        try:
            assert orders_mod.anonymize_order(s, o) is True
            s.refresh(o)
            # PII overwritten
            assert o.customer_name == "[anonymized]"
            assert o.customer_email == "anonymized@example.invalid"
            assert o.customer_phone == ""
            assert o.ship_address == "[removed]" and o.ship_city == "[removed]"
            assert o.ship_postcode == ""
            assert o.ship_country == "GR"          # coarse region kept
            assert o.anonymized_at is not None
            # financials preserved
            assert (o.number, o.status, o.total, o.subtotal, o.vat_amount, o.currency,
                    o.items[0].price_snapshot) == before
            # idempotent
            assert orders_mod.anonymize_order(s, o) is False
        finally:
            _cleanup(s, o)


def test_sweep_selects_only_eligible_and_dry_run_is_noop():
    _skip_if_no_app()
    with Session(engine) as s:
        old_shipped = _make_order(s, "TEST-SWEEP-SHIP", "shipped", days_old=5000)
        old_cancelled = _make_order(s, "TEST-SWEEP-CANC", "cancelled", days_old=5000)
        old_paid = _make_order(s, "TEST-SWEEP-PAID", "paid", days_old=5000)      # wrong status
        recent_shipped = _make_order(s, "TEST-SWEEP-NEW", "shipped", days_old=1)  # too recent
        try:
            dry = orders_mod.anonymize_sweep(s, retention_days=1095, dry_run=True)
            nums = {row["number"] for row in dry["orders"]}
            assert {"TEST-SWEEP-SHIP", "TEST-SWEEP-CANC"} <= nums
            assert "TEST-SWEEP-PAID" not in nums and "TEST-SWEEP-NEW" not in nums
            assert dry["committed"] is False
            s.refresh(old_shipped)
            assert old_shipped.anonymized_at is None  # dry run wrote nothing

            res = orders_mod.anonymize_sweep(s, retention_days=1095, dry_run=False)
            assert res["committed"] is True and res["count"] >= 2
            for o in (old_shipped, old_cancelled):
                s.refresh(o); assert o.anonymized_at is not None
            for o in (old_paid, recent_shipped):
                s.refresh(o); assert o.anonymized_at is None
        finally:
            _cleanup(s, old_shipped, old_cancelled, old_paid, recent_shipped)
