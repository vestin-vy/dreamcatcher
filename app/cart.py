"""Server-side shopping cart (SPEC-BILLING §2).

The cart lives in the signed session cookie as `{ "<product_id>": qty }` — only ids and
quantities are stored. Prices are ALWAYS read fresh from the DB; they are snapshotted onto
the Order only at checkout time (`app/routes/checkout.py`).

All prices in this project are gross (VAT-inclusive); see `vat_from_gross`.
"""
from __future__ import annotations

from fastapi import Request
from sqlmodel import Session

from app.models import Product

CART_KEY = "cart"
DEFAULT_VAT_RATE = 24.0  # Greece; overridden by the `vat_rate` site setting.


# --- session helpers --------------------------------------------------------

def get_cart(request: Request) -> dict[str, int]:
    """Return the raw cart mapping `{product_id(str): qty}` from the session."""
    cart = request.session.get(CART_KEY)
    if not isinstance(cart, dict):
        return {}
    # Normalise to {str: int}, dropping anything malformed.
    clean: dict[str, int] = {}
    for k, v in cart.items():
        try:
            qty = int(v)
        except (TypeError, ValueError):
            continue
        if qty > 0:
            clean[str(k)] = qty
    return clean


def _save(request: Request, cart: dict[str, int]) -> None:
    request.session[CART_KEY] = cart


def cart_count(request: Request) -> int:
    """Total number of items (sum of quantities) — for the header badge."""
    return sum(get_cart(request).values())


def add(request: Request, product_id: int, qty: int = 1) -> None:
    cart = get_cart(request)
    pid = str(product_id)
    cart[pid] = cart.get(pid, 0) + max(1, qty)
    _save(request, cart)


def set_qty(request: Request, product_id: int, qty: int) -> None:
    cart = get_cart(request)
    pid = str(product_id)
    if qty <= 0:
        cart.pop(pid, None)
    else:
        cart[pid] = qty
    _save(request, cart)


def remove(request: Request, product_id: int) -> None:
    set_qty(request, product_id, 0)


def clear(request: Request) -> None:
    request.session.pop(CART_KEY, None)


# --- money ------------------------------------------------------------------

def vat_from_gross(gross: float, rate: float) -> float:
    """VAT amount contained within a gross (VAT-inclusive) total."""
    if not rate:
        return 0.0
    return round(gross - gross / (1.0 + rate / 100.0), 2)


def is_purchasable(product: Product) -> bool:
    """A product can be added to the cart only if it has a real price and stock."""
    if product is None or not product.is_active:
        return False
    if product.price_on_request or product.price is None:
        return False
    if product.track_stock and product.stock <= 0:
        return False
    return True


# --- view model -------------------------------------------------------------

def cart_view(request: Request, db: Session, lang: str, vat_rate: float = DEFAULT_VAT_RATE) -> dict:
    """Build a template-friendly view of the cart with live prices and totals.

    Lines whose product disappeared / became non-purchasable are dropped (and the
    session is pruned). Quantities are clamped to available stock when tracked.
    """
    from app.routes.public import product_view  # lazy import avoids an import cycle

    cart = get_cart(request)
    items: list[dict] = []
    subtotal = 0.0
    pruned = dict(cart)
    changed = False

    for pid, qty in cart.items():
        product = db.get(Product, int(pid))
        if not is_purchasable(product):
            pruned.pop(pid, None)
            changed = True
            continue
        if product.track_stock and qty > product.stock:
            qty = product.stock
            pruned[pid] = qty
            changed = True
        line_total = round(product.price * qty, 2)
        subtotal = round(subtotal + line_total, 2)
        pv = product_view(product, lang)
        pv.update({"qty": qty, "line_total": line_total})
        items.append(pv)

    if changed:
        _save(request, pruned)

    vat = vat_from_gross(subtotal, vat_rate)
    return {
        # Key is "lines" (not "items") because Jinja's `cart.items` would resolve to the
        # dict's built-in .items() method instead of this value.
        "lines": items,
        "count": sum(i["qty"] for i in items),
        "subtotal": subtotal,
        "vat": vat,
        "vat_rate": vat_rate,
        "total": subtotal,  # shipping is added at checkout
        "currency": "EUR",
    }
