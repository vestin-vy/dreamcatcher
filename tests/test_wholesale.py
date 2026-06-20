"""Wholesale (B2B) tests (SPEC-BILLING addendum 2): min-10 per line, NO stock cap, the
request becomes an is_wholesale Order (DCW-...) without touching stock.
"""
import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

try:
    from app.main import app
    from app.db import engine
    from app.models import Order, OrderItem, Product
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    app = None
    _IMPORT_ERROR = exc

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(scope="module")
def client():
    if app is None:
        pytest.skip(f"app.main:app not importable: {_IMPORT_ERROR}")
    return TestClient(app, base_url="https://testserver")


def _csrf(html):
    m = CSRF_RE.search(html)
    assert m, "no csrf token"
    return m.group(1)


def test_wholesale_catalog_renders(client):
    r = client.get("/el/wholesale")
    assert r.status_code == 200
    assert "/el/wholesale/cart/add" in r.text  # add-to-request forms present


def test_wholesale_min_qty_no_cap_and_request_creates_order(client):
    # Dedicated low-stock product to prove wholesale ignores stock entirely.
    with Session(engine) as session:
        prod = Product(slug="test-wholesale-item", price=15.0, stock=2,
                       track_stock=True, is_active=True)
        session.add(prod); session.commit(); session.refresh(prod)
        pid = prod.id

    try:
        csrf = _csrf(client.get("/el/wholesale").text)
        client.post("/el/wholesale/cart/remove", data={"csrf_token": csrf, "product_id": str(pid)})

        # Adding 3 must be bumped to the per-line minimum (10).
        client.post("/el/wholesale/cart/add", data={"csrf_token": csrf, "product_id": str(pid), "qty": "3"})
        cart = client.get("/el/wholesale/cart").text
        m = re.search(r'id="wq-%d"[^>]*value="(\d+)"' % pid, cart)
        assert m and int(m.group(1)) == 10, "min qty 10 not enforced"

        # Set 50 — far above stock (2) — must be allowed (no cap).
        client.post("/el/wholesale/cart/update", data={"csrf_token": csrf, "product_id": str(pid), "qty": "50"})
        cart = client.get("/el/wholesale/cart").text
        m = re.search(r'id="wq-%d"[^>]*value="(\d+)"' % pid, cart)
        assert m and int(m.group(1)) == 50, "wholesale must not cap to stock"

        # Send the request.
        r = client.post("/el/wholesale/request", data={
            "csrf_token": csrf, "customer_name": "B2B Buyer",
            "customer_email": "b2b@example.com", "customer_phone": "+30 1",
            "ship_address": "Rd 1", "ship_city": "Athens", "ship_postcode": "10001",
            "ship_country": "GR",
        }, follow_redirects=False)
        assert r.status_code == 303 and "/wholesale/success" in r.headers["location"]
        number = r.headers["location"].rsplit("=", 1)[-1]
        assert number.startswith("DCW-")

        with Session(engine) as session:
            order = session.exec(select(Order).where(Order.number == number)).first()
            assert order is not None
            assert order.is_wholesale is True
            assert order.status == "wholesale"
            item = session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).first()
            assert item is not None and item.qty == 50  # quantity kept as requested
            # Stock must be untouched by a wholesale request.
            prod2 = session.get(Product, pid)
            assert prod2.stock == 2
            # cleanup the order + items
            for it in list(order.items):
                session.delete(it)
            session.delete(order); session.commit()
    finally:
        with Session(engine) as session:
            p = session.get(Product, pid)
            if p:
                session.delete(p); session.commit()


def test_wholesale_success_page(client):
    r = client.get("/el/wholesale/success?order=DCW-TEST")
    assert r.status_code == 200
    assert "DCW-TEST" in r.text
