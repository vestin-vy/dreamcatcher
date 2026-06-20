"""Capture responsive screenshots (SPEC §10 DoD) for the shop-with-billing build.

Assumes the dev server runs on http://127.0.0.1:8000 with seed data AND a session
cookie that works over http (run with SESSION_HTTPS_ONLY=false / DEBUG=true).

Run:  python scripts/shoot.py
Output: screenshots/<page>-<width>.png
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
WIDTHS = [375, 768, 1024, 1440]
OUT = Path(__file__).resolve().parent.parent / "screenshots"
ADMIN_USER = "admin"
ADMIN_PASS = "dreamcatcher"  # local dev password (see .env)
DEMO_PRODUCT = "aurora-solitaire-ring"  # priced + in stock

# Public pages shot at every width.
PUBLIC_PAGES = [
    ("home-el", "/el/"),
    ("home-en", "/en/"),
    ("catalog", "/el/catalog"),
    ("product", f"/el/product/{DEMO_PRODUCT}"),
    ("collections", "/el/collections"),
    ("about", "/el/about"),
    ("contact", "/el/contact"),
    ("terms", "/el/terms"),
    ("returns", "/el/returns"),
    ("privacy", "/el/privacy"),
]

# Admin pages shot at 1440 only (after login).
ADMIN_PAGES = [
    ("admin-dashboard", "/admin"),
    ("admin-products", "/admin/products"),
    ("admin-product-form", "/admin/products/new"),
    ("admin-categories", "/admin/categories"),
    ("admin-orders", "/admin/orders"),
    ("admin-settings", "/admin/settings"),
]


def _shot(page, name: str, width: int) -> None:
    out = OUT / f"{name}-{width}.png"
    page.screenshot(path=str(out), full_page=True)
    print(f"  {out.name}")


def shoot_public(browser) -> None:
    for width in WIDTHS:
        ctx = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=1, reduced_motion="reduce")
        page = ctx.new_page()
        for name, path in PUBLIC_PAGES:
            page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(350)
            _shot(page, name, width)

        # Cart + checkout need an item: add one from the product page, then shoot.
        page.goto(f"{BASE}/el/product/{DEMO_PRODUCT}", wait_until="networkidle")
        page.click("form.product__buy button[type=submit]")
        page.wait_for_url("**/el/cart", timeout=15000)
        page.wait_for_timeout(350)
        _shot(page, "cart", width)
        page.goto(f"{BASE}/el/checkout", wait_until="networkidle")
        page.wait_for_timeout(350)
        _shot(page, "checkout", width)
        ctx.close()


def shoot_buy_flow_and_admin(browser) -> None:
    """One full demo purchase at 1440 -> pay/success screenshots + a paid order;
    then log into the admin and shoot the management pages."""
    width = 1440
    # --- buy flow (creates a paid order) ---
    ctx = browser.new_context(viewport={"width": width, "height": 900}, reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(f"{BASE}/el/product/{DEMO_PRODUCT}", wait_until="networkidle")
    page.click("form.product__buy button[type=submit]")
    page.wait_for_url("**/el/cart")
    page.goto(f"{BASE}/el/checkout", wait_until="networkidle")
    page.fill("#customer_name", "Maria Demo")
    page.fill("#customer_email", "maria@example.com")
    page.fill("#customer_phone", "+30 210 000 0000")
    page.fill("#ship_address", "Ermou 1")
    page.fill("#ship_city", "Athens")
    page.fill("#ship_postcode", "10563")
    page.click("button[type=submit]")
    page.wait_for_url("**/checkout/pay/**", timeout=15000)
    page.wait_for_timeout(300)
    _shot(page, "checkout-pay", width)
    page.click("form button[type=submit]")  # simulate payment
    page.wait_for_url("**/checkout/success**", timeout=15000)
    page.wait_for_timeout(300)
    _shot(page, "checkout-success", width)
    ctx.close()

    # --- admin ---
    ctx = browser.new_context(viewport={"width": width, "height": 900}, reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(f"{BASE}/admin/login", wait_until="networkidle")
    _shot(page, "admin-login", width)
    page.fill("input[name=username]", ADMIN_USER)
    page.fill("input[name=password]", ADMIN_PASS)
    page.click("button[type=submit]")
    page.wait_for_url("**/admin", timeout=15000)

    for name, path in ADMIN_PAGES:
        page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(300)
        _shot(page, name, width)

    # Order detail for the most recent order (the one we just paid).
    page.goto(f"{BASE}/admin/orders", wait_until="networkidle")
    link = page.query_selector("table.table tbody tr td a")
    if link:
        link.click()
        page.wait_for_url("**/admin/orders/**", timeout=15000)
        page.wait_for_timeout(300)
        _shot(page, "admin-order-detail", width)
    ctx.close()

    # Admin login also at small widths (responsive check).
    for w in (375, 768, 1024):
        ctx = browser.new_context(viewport={"width": w, "height": 900}, reduced_motion="reduce")
        page = ctx.new_page()
        page.goto(f"{BASE}/admin/login", wait_until="networkidle")
        page.wait_for_timeout(250)
        _shot(page, "admin-login", w)
        ctx.close()


def main() -> int:
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            shoot_public(browser)
            shoot_buy_flow_and_admin(browser)
        finally:
            browser.close()
    print(f"Done -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
