"""Billing tests (SPEC-BILLING §7): VAT math, cart→checkout→demo-pay flow, webhook
idempotency, and that the success redirect does NOT confirm payment by itself.

Run:  python -m pytest -q
Assumes seed data is present (python -m app.seed) for the HTTP flow tests.
"""
import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

try:
    from app.main import app
    from app import cart as cart_mod
    from app import orders as orders_mod
    from app.db import engine
    from app.models import Order, OrderItem, Product
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    app = None
    _IMPORT_ERROR = exc


@pytest.fixture(scope="module")
def client():
    if app is None:
        pytest.skip(f"app.main:app not importable: {_IMPORT_ERROR}")
    # Use https so the session cookie is sent even when SESSION_HTTPS_ONLY is on
    # (production default); the cart + CSRF flow depends on the session persisting.
    return TestClient(app, base_url="https://testserver")


CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')
PID_RE = re.compile(r'name="product_id" value="(\d+)"')


def _csrf(html: str) -> str:
    m = CSRF_RE.search(html)
    assert m, "no csrf token found on page"
    return m.group(1)


# --- VAT math (gross / VAT-inclusive) ---------------------------------------

def test_vat_from_gross_24():
    # 124 gross at 24% contains 24.00 VAT (124 - 124/1.24 = 24.00).
    assert cart_mod.vat_from_gross(124.0, 24.0) == 24.0
    # 100 gross at 24% contains 19.35.
    assert cart_mod.vat_from_gross(100.0, 24.0) == 19.35
    # No rate -> no VAT.
    assert cart_mod.vat_from_gross(100.0, 0.0) == 0.0


# --- mark_order_paid: idempotent + decrements tracked stock -----------------

def test_mark_paid_idempotent_and_decrements_stock():
    if app is None:
        pytest.skip("app not importable")
    with Session(engine) as session:
        product = Product(slug="test-stock-item", price=50.0, track_stock=True, stock=3)
        session.add(product)
        session.commit()
        session.refresh(product)

        order = Order(number="TEST-IDEMP-1", status="pending", total=100.0,
                      subtotal=100.0, currency="EUR")
        session.add(order)
        session.commit()
        session.refresh(order)
        session.add(OrderItem(order_id=order.id, product_id=product.id,
                              title_snapshot="t", price_snapshot=50.0, qty=2, line_total=100.0))
        session.commit()
        session.refresh(order)

        first = orders_mod.mark_order_paid(session, order, "txn-1")
        second = orders_mod.mark_order_paid(session, order, "txn-1")  # redelivery
        assert first is True
        assert second is False
        assert order.status == "paid"

        session.refresh(product)
        assert product.stock == 1, "stock must decrement exactly once"

        # cleanup
        session.delete(session.get(OrderItem, order.items[0].id))
        session.delete(order)
        session.delete(product)
        session.commit()


# --- end-to-end: cart -> checkout -> demo pay -> paid via webhook path -------

def test_checkout_demo_flow_marks_paid(client):
    # Find an in-stock, priced product from the catalog.
    catalog = client.get("/el/catalog")
    assert catalog.status_code == 200
    csrf = _csrf(catalog.text)
    pid_match = PID_RE.search(catalog.text)
    assert pid_match, "no purchasable product on the catalog (seed first)"
    product_id = pid_match.group(1)

    # Add to cart.
    r = client.post("/el/cart/add",
                    data={"csrf_token": csrf, "product_id": product_id, "qty": "2"},
                    follow_redirects=False)
    assert r.status_code == 303
    cart = client.get("/el/cart")
    assert cart.status_code == 200 and "/el/product/" in cart.text

    # Submit checkout.
    r = client.post("/el/checkout", data={
        "csrf_token": csrf,
        "customer_name": "Test Buyer", "customer_email": "buyer@example.com",
        "customer_phone": "+30 000", "ship_address": "Street 1", "ship_city": "Athens",
        "ship_postcode": "10001", "ship_country": "GR", "shipping_method": "courier",
    }, follow_redirects=False)
    assert r.status_code == 303
    loc = r.headers["location"]
    assert "/checkout/pay/" in loc
    number = loc.rsplit("/", 1)[-1]

    # Demo pay page -> pay (mirrors the webhook path).
    pay = client.get(f"/el/checkout/pay/{number}")
    assert pay.status_code == 200
    pay_csrf = _csrf(pay.text)
    r = client.post(f"/el/checkout/pay/{number}", data={"csrf_token": pay_csrf},
                    follow_redirects=False)
    assert r.status_code == 303 and "success" in r.headers["location"]

    # The order must now be paid.
    with Session(engine) as session:
        order = session.exec(select(Order).where(Order.number == number)).first()
        assert order is not None
        assert order.status == "paid"
        assert order.viva_transaction_id


def test_webhook_idempotent_over_http(client):
    # Create a pending order through checkout, then POST the webhook twice.
    catalog = client.get("/el/catalog")
    csrf = _csrf(catalog.text)
    product_id = PID_RE.search(catalog.text).group(1)
    client.post("/el/cart/add",
                data={"csrf_token": csrf, "product_id": product_id, "qty": "1"})
    r = client.post("/el/checkout", data={
        "csrf_token": csrf, "customer_name": "WH", "customer_email": "wh@example.com",
        "ship_address": "A", "ship_city": "Athens", "ship_postcode": "1",
        "ship_country": "GR", "shipping_method": "courier",
    }, follow_redirects=False)
    number = r.headers["location"].rsplit("/", 1)[-1]

    payload = {"order_code": number, "status": "paid", "transaction_id": f"wh-{number}"}
    first = client.post("/payments/viva/webhook", json=payload)
    second = client.post("/payments/viva/webhook", json=payload)
    assert first.json()["applied"] is True
    assert second.json()["applied"] is False  # redelivery is a no-op


def test_out_of_stock_product_not_purchasable(client):
    # The seeded olive-leaf-band has stock 0 -> shows "Out of stock", no buy form.
    r = client.get("/en/product/olive-leaf-band")
    assert r.status_code == 200
    assert "Out of stock" in r.text
    assert "product__buy" not in r.text
    with Session(engine) as session:
        p = session.exec(select(Product).where(Product.slug == "olive-leaf-band")).first()
        assert p is not None and not cart_mod.is_purchasable(p)


def test_add_to_cart_caps_at_stock(client):
    # Dedicated product (stock 3) so other tests can't drain it; adding 10 must clamp to 3.
    with Session(engine) as session:
        prod = Product(slug="test-cap-item", price=20.0, stock=3, track_stock=True, is_active=True)
        session.add(prod); session.commit(); session.refresh(prod)
        pid = prod.id
    try:
        csrf = _csrf(client.get("/el/catalog").text)
        client.post("/el/cart/remove", data={"csrf_token": csrf, "product_id": str(pid)})
        client.post("/el/cart/add", data={"csrf_token": csrf, "product_id": str(pid), "qty": "10"})
        cart = client.get("/el/cart").text
        m = re.search(r'id="qty-%d"[^>]*value="(\d+)"' % pid, cart)
        assert m, "qty field for the item not found in cart"
        assert int(m.group(1)) == 3  # clamped to available stock
        client.post("/el/cart/remove", data={"csrf_token": csrf, "product_id": str(pid)})
    finally:
        with Session(engine) as session:
            p = session.get(Product, pid)
            if p:
                session.delete(p); session.commit()


def test_success_redirect_does_not_confirm_payment(client):
    catalog = client.get("/el/catalog")
    csrf = _csrf(catalog.text)
    product_id = PID_RE.search(catalog.text).group(1)
    client.post("/el/cart/add",
                data={"csrf_token": csrf, "product_id": product_id, "qty": "1"})
    r = client.post("/el/checkout", data={
        "csrf_token": csrf, "customer_name": "NoPay", "customer_email": "n@example.com",
        "ship_address": "A", "ship_city": "Athens", "ship_postcode": "1",
        "ship_country": "GR", "shipping_method": "courier",
    }, follow_redirects=False)
    number = r.headers["location"].rsplit("/", 1)[-1]

    # Visit success WITHOUT paying — must not flip the order to paid.
    client.get(f"/el/checkout/success?order={number}")
    with Session(engine) as session:
        order = session.exec(select(Order).where(Order.number == number)).first()
        assert order is not None and order.status == "pending"
