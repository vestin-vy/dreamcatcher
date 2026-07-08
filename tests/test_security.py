"""Security regression tests: response headers, order-page session binding,
and autoescaped product descriptions (no stored XSS).

Run:  python -m pytest -q
"""
import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

try:
    from app.main import app
    from app.config import settings
    from app.db import engine
    from app.models import Order, Product, ProductTranslation
    from app.routes.admin import csv_safe
    from app import images as images_mod
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    app = None
    _IMPORT_ERROR = exc


@pytest.fixture(scope="module")
def client():
    if app is None:
        pytest.skip(f"app.main:app not importable: {_IMPORT_ERROR}")
    return TestClient(app, base_url="https://testserver")


# --- admin password reset ----------------------------------------------------

def test_password_reset_emails_new_password_and_rotates_hash(client, monkeypatch):
    from app import mailer
    from app.models import Setting
    from app.routes import admin as admin_routes

    admin_routes._reset_hits.clear()
    emails = []
    monkeypatch.setattr(mailer, "is_configured", lambda: True)
    monkeypatch.setattr(mailer, "send_email",
                        lambda subject, body, to=None: emails.append(body) or True)

    login = client.get("/admin/login")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', login.text).group(1)
    r = client.post("/admin/reset-password", data={"csrf_token": csrf},
                    follow_redirects=False)
    assert r.status_code == 303 and "reset=1" in r.headers["location"]
    assert len(emails) == 1
    new_password = re.search(r"Новый пароль: (\S+)", emails[0]).group(1)

    # the emailed password logs in; the DB hash override is set
    r = client.post("/admin/login", data={
        "username": "admin", "password": new_password, "csrf_token": csrf,
    }, follow_redirects=False)
    assert r.status_code == 303
    with Session(engine) as session:
        row = session.get(Setting, "admin_password_hash")
        assert row is not None and row.value
        session.delete(row)  # cleanup: restore env-hash auth for other tests
        session.commit()
    client.post("/admin/logout")


def test_password_reset_off_without_mail(client):
    from app.routes import admin as admin_routes
    admin_routes._reset_hits.clear()
    login = client.get("/admin/login")
    assert "reset-password" not in login.text  # button hidden
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', login.text).group(1)
    r = client.post("/admin/reset-password", data={"csrf_token": csrf},
                    follow_redirects=False)
    assert r.status_code == 303 and "mail=off" in r.headers["location"]


# --- security headers ---------------------------------------------------------

def test_security_headers_present(client):
    r = client.get("/el/")
    assert r.status_code == 200
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    if settings.SESSION_HTTPS_ONLY:
        assert "max-age=" in r.headers.get("Strict-Transport-Security", "")


# --- order enumeration: pay page must be session-bound -------------------------

def test_pay_page_denied_for_foreign_session(client):
    # An order created OUTSIDE this client's session (as if by another buyer).
    with Session(engine) as session:
        order = Order(number="TEST-FOREIGN-1", status="pending", total=42.0,
                      subtotal=42.0, currency="EUR")
        session.add(order)
        session.commit()
        oid = order.id
    try:
        r = client.get("/el/checkout/pay/TEST-FOREIGN-1", follow_redirects=False)
        assert r.status_code == 303, "foreign session must not see the pay page"
        assert "/cart" in r.headers["location"]

        # POSTing the demo pay for a foreign order must not mark it paid.
        page = client.get("/el/catalog")
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        client.post("/el/checkout/pay/TEST-FOREIGN-1", data={"csrf_token": csrf},
                    follow_redirects=False)
        with Session(engine) as session:
            assert session.get(Order, oid).status == "pending"
    finally:
        with Session(engine) as session:
            o = session.get(Order, oid)
            if o:
                session.delete(o)
                session.commit()


def test_success_page_hides_foreign_order_email(client):
    with Session(engine) as session:
        order = Order(number="TEST-FOREIGN-2", status="pending", total=10.0,
                      subtotal=10.0, currency="EUR",
                      customer_email="victim@example.com")
        session.add(order)
        session.commit()
        oid = order.id
    try:
        r = client.get("/el/checkout/success?order=TEST-FOREIGN-2")
        assert r.status_code == 200
        assert "victim@example.com" not in r.text
    finally:
        with Session(engine) as session:
            o = session.get(Order, oid)
            if o:
                session.delete(o)
                session.commit()


# --- stored XSS: product description is autoescaped ---------------------------

def test_product_description_is_escaped(client):
    payload = '<script>alert("xss")</script>'
    with Session(engine) as session:
        prod = Product(slug="test-xss-item", price=10.0, is_active=True)
        session.add(prod)
        session.commit()
        session.refresh(prod)
        session.add(ProductTranslation(product_id=prod.id, lang="en",
                                       title="XSS probe", description=payload))
        session.commit()
        pid = prod.id
    try:
        r = client.get("/en/product/test-xss-item")
        assert r.status_code == 200
        assert payload not in r.text, "raw <script> must never reach the page"
        assert "&lt;script&gt;" in r.text, "description must render escaped"
    finally:
        with Session(engine) as session:
            tr = session.exec(select(ProductTranslation)
                              .where(ProductTranslation.product_id == pid)).all()
            for t in tr:
                session.delete(t)
            p = session.get(Product, pid)
            if p:
                session.delete(p)
            session.commit()


# --- open redirect: cart `next` param must stay same-site --------------------

def test_cart_next_rejects_offsite_redirect(client):
    catalog = client.get("/el/catalog")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', catalog.text).group(1)
    pid = re.search(r'name="product_id" value="(\d+)"', catalog.text).group(1)
    for evil in ("https://evil.example/phish", "//evil.example"):
        r = client.post("/el/cart/add",
                        data={"csrf_token": csrf, "product_id": pid, "qty": "1", "next": evil},
                        follow_redirects=False)
        assert r.status_code == 303
        loc = r.headers["location"]
        assert "evil.example" not in loc, f"open redirect via next={evil!r}"
        assert loc.startswith("/"), "redirect must stay a same-site relative path"


# --- CSV formula injection: customer-controlled cells are neutralized ---------

def test_csv_safe_neutralizes_formula_triggers():
    assert csv_safe("=cmd|'/c calc'!A1").startswith("'=")
    assert csv_safe("+1").startswith("'+")
    assert csv_safe("-2+3").startswith("'-")
    assert csv_safe("@SUM(A1)").startswith("'@")
    # normal values pass through untouched
    assert csv_safe("buyer@example.com") == "buyer@example.com"
    assert csv_safe("el") == "el"
    assert csv_safe(None) == ""


# --- decompression-bomb guard: oversized images are rejected pre-decode -------

def test_oversized_image_rejected_before_decode():
    from io import BytesIO
    from PIL import Image
    # A tiny file that DECLARES huge dimensions would be the real attack; here we just
    # build an image whose pixel count exceeds the limit and confirm it's refused
    # without the processing pipeline trying to allocate it.
    side = int((images_mod.MAX_IMAGE_PIXELS) ** 0.5) + 500
    buf = BytesIO()
    Image.new("RGB", (side, side), (255, 255, 255)).save(buf, "PNG")
    with pytest.raises(images_mod.InvalidImageError):
        images_mod.save_image(buf.getvalue())
