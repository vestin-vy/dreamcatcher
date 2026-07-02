"""Order service (SPEC-BILLING §1, §3): shipping config, order creation, mark-as-paid.

Pure-ish helpers shared by checkout, the webhook, and the admin. Prices are gross
(VAT-inclusive); the VAT amount is back-computed from the gross total.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, func, select

from app import cart as cart_mod
from app.models import Order, OrderItem, Product, Setting


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- shipping methods (stored as a `shipping_methods` site setting) ----------
# One method per line: "slug|Greek label|English label|cost"
DEFAULT_SHIPPING = "courier|Ταχυμεταφορά|Courier|5\npickup|Παραλαβή από το κατάστημα|Store pickup|0"


def parse_shipping_methods(site: dict, lang: str) -> list[dict]:
    raw = (site.get("shipping_methods") or DEFAULT_SHIPPING).strip()
    methods: list[dict] = []
    for line in raw.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4 or not parts[0]:
            continue
        slug, label_el, label_en, cost_raw = parts[0], parts[1], parts[2], parts[3]
        try:
            cost = float(cost_raw.replace(",", "."))
        except ValueError:
            cost = 0.0
        methods.append({"slug": slug, "label": label_el if lang == "el" else label_en, "cost": cost})
    return methods


def shipping_cost_for(site: dict, slug: str) -> tuple[str, float]:
    """Return (slug, cost) for the chosen method, defaulting to the first method."""
    methods = parse_shipping_methods(site, "en")
    for m in methods:
        if m["slug"] == slug:
            return m["slug"], m["cost"]
    if methods:
        return methods[0]["slug"], methods[0]["cost"]
    return "", 0.0


# --- order number -----------------------------------------------------------

def generate_order_number(session: Session, prefix: str = "DC") -> str:
    """Sequential, human-readable: <PREFIX>-YYYYMMDD-NNNN (per day, per prefix).
    Retail uses "DC", wholesale uses "DCW"."""
    today = _utcnow().strftime("%Y%m%d")
    full = f"{prefix}-{today}-"
    count = session.exec(
        select(func.count()).select_from(Order).where(Order.number.like(f"{full}%"))
    ).one()
    return f"{full}{count + 1:04d}"


# --- create order from cart -------------------------------------------------

def create_order_from_cart(
    request, session: Session, lang: str, form: dict, site: dict
) -> Order | None:
    """Create a pending Order + OrderItems from the current cart. Returns None if empty."""
    vat_rate = _vat_rate(site)
    view = cart_mod.cart_view(request, session, lang, vat_rate=vat_rate)
    if not view["lines"]:
        return None

    ship_slug, ship_cost = shipping_cost_for(site, (form.get("shipping_method") or "").strip())
    subtotal = view["subtotal"]
    total = round(subtotal + ship_cost, 2)
    vat_amount = cart_mod.vat_from_gross(total, vat_rate)

    order = Order(
        number=generate_order_number(session),
        status="pending",
        customer_name=(form.get("customer_name") or "").strip(),
        customer_email=(form.get("customer_email") or "").strip(),
        customer_phone=(form.get("customer_phone") or "").strip(),
        ship_address=(form.get("ship_address") or "").strip(),
        ship_city=(form.get("ship_city") or "").strip(),
        ship_postcode=(form.get("ship_postcode") or "").strip(),
        ship_country=(form.get("ship_country") or "GR").strip() or "GR",
        shipping_method=ship_slug,
        shipping_cost=ship_cost,
        subtotal=subtotal,
        vat_amount=vat_amount,
        vat_rate=vat_rate,
        total=total,
        currency=view["currency"],
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    for it in view["lines"]:
        session.add(OrderItem(
            order_id=order.id,
            product_id=it["id"],
            title_snapshot=it["title"],
            price_snapshot=it["price"],
            qty=it["qty"],
            line_total=it["line_total"],
        ))
    session.commit()
    session.refresh(order)
    return order


# --- wholesale request (no payment, no stock cap, no decrement) -------------

def create_wholesale_order(request, session: Session, lang: str, form: dict) -> Order | None:
    """Create a wholesale Order (status 'wholesale') from the wholesale cart.

    Unlike retail: no VAT/shipping/payment, stock is NOT capped or decremented; quantities
    are taken as requested. `subtotal` is stored as an indicative reference for the admin.
    """
    view = cart_mod.wholesale_view(request, session, lang)
    if not view["lines"]:
        return None

    order = Order(
        number=generate_order_number(session, prefix="DCW"),
        status="wholesale",
        is_wholesale=True,
        customer_name=(form.get("customer_name") or "").strip(),
        customer_email=(form.get("customer_email") or "").strip(),
        customer_phone=(form.get("customer_phone") or "").strip(),
        ship_address=(form.get("ship_address") or "").strip(),
        ship_city=(form.get("ship_city") or "").strip(),
        ship_postcode=(form.get("ship_postcode") or "").strip(),
        ship_country=(form.get("ship_country") or "GR").strip() or "GR",
        subtotal=view["subtotal"],
        total=view["subtotal"],  # indicative; final price negotiated on contact
        currency=view["currency"],
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    for it in view["lines"]:
        session.add(OrderItem(
            order_id=order.id,
            product_id=it["id"],
            title_snapshot=it["title"],
            price_snapshot=it["unit_price"],
            qty=it["qty"],
            line_total=it["line_total"],
        ))
    session.commit()
    session.refresh(order)
    return order


# --- buyer session binding (anti-enumeration) --------------------------------
# Order numbers are sequential and human-readable, so the public pay/success pages
# must not resolve an arbitrary number: only the session that created the order may
# open them. (The webhook is server-to-server and is NOT session-bound.)

SESSION_ORDERS_KEY = "my_orders"
_SESSION_ORDERS_MAX = 10


def remember_order(request, number: str) -> None:
    """Record an order number in the buyer's session (newest first, capped)."""
    mine = [n for n in request.session.get(SESSION_ORDERS_KEY, []) if n != number]
    mine.insert(0, number)
    request.session[SESSION_ORDERS_KEY] = mine[:_SESSION_ORDERS_MAX]


def session_owns_order(request, number: str) -> bool:
    """True if this session created the order (see remember_order)."""
    return bool(number) and number in request.session.get(SESSION_ORDERS_KEY, [])


# --- mark paid (idempotent) -------------------------------------------------

def mark_order_paid(session: Session, order: Order, transaction_id: str | None) -> bool:
    """Transition a pending order to paid exactly once.

    Idempotent (SPEC-BILLING §6): if the order is already paid, or this transaction was
    already recorded, do nothing and return False. Otherwise mark paid, record the
    transaction, decrement tracked stock, and return True.
    """
    if order.status == "paid":
        return False
    if transaction_id and order.viva_transaction_id == transaction_id:
        return False

    order.status = "paid"
    order.viva_transaction_id = transaction_id
    order.updated_at = _utcnow()
    session.add(order)

    # Decrement stock for tracked products.
    for item in order.items:
        if item.product_id is None:
            continue
        product = session.get(Product, item.product_id)
        if product and product.track_stock:
            product.stock = max(0, product.stock - item.qty)
            session.add(product)

    session.commit()
    return True


def find_order_by_ref(session: Session, ref: str) -> Order | None:
    """Locate an order by its provider code or its human-readable number."""
    if not ref:
        return None
    order = session.exec(select(Order).where(Order.viva_order_code == ref)).first()
    if order:
        return order
    return session.exec(select(Order).where(Order.number == ref)).first()


def apply_payment_result(session: Session, result) -> bool:
    """Resolve a PaymentResult to an order and mark it paid (idempotently).

    Shared by the Viva webhook endpoint and the demo pay page so both exercise the exact
    same mark-paid path. Returns True only on the first successful application.
    """
    if result is None or not result.is_paid:
        return False
    order = find_order_by_ref(session, result.order_ref)
    if not order:
        return False
    return mark_order_paid(session, order, result.transaction_id)


def _vat_rate(site: dict) -> float:
    try:
        return float(site.get("vat_rate") or cart_mod.DEFAULT_VAT_RATE)
    except (TypeError, ValueError):
        return cart_mod.DEFAULT_VAT_RATE


# --- GDPR: order PII anonymization + retention (Task 2) ----------------------
# Neutral placeholders that IRREVERSIBLY replace contact/shipping PII. ship_country
# is intentionally NOT here — a coarse region is kept. Financial/accounting fields
# (number, status, totals, vat_*, currency, item snapshots, viva_* ids, timestamps)
# are preserved for tax-law record-keeping.
ANON_PLACEHOLDERS = {
    "customer_name": "[anonymized]",
    "customer_email": "anonymized@example.invalid",
    "customer_phone": "",
    "ship_address": "[removed]",
    "ship_city": "[removed]",
    "ship_postcode": "",
}
DEFAULT_PII_RETENTION_DAYS = 1095  # 3 years


def pii_retention_days(session: Session) -> int:
    """Read the admin-configured retention (Setting), falling back to the default."""
    row = session.get(Setting, "order_pii_retention_days")
    try:
        return int(row.value) if row and str(row.value).strip() else DEFAULT_PII_RETENTION_DAYS
    except (TypeError, ValueError):
        return DEFAULT_PII_RETENTION_DAYS


def anonymize_order(session: Session, order: Order) -> bool:
    """Irreversibly overwrite an order's PII; preserve financial fields. Idempotent:
    returns False if the order is already anonymized."""
    if order.anonymized_at is not None:
        return False
    for field, value in ANON_PLACEHOLDERS.items():
        setattr(order, field, value)
    order.anonymized_at = _utcnow()
    session.add(order)
    session.commit()
    return True


def orders_due_for_anonymization(session: Session, retention_days: int | None = None) -> list[Order]:
    """Shipped/cancelled orders older than the retention window, not yet anonymized."""
    days = retention_days if retention_days is not None else pii_retention_days(session)
    cutoff = _utcnow() - timedelta(days=days)
    return session.exec(
        select(Order)
        .where(
            Order.anonymized_at.is_(None),  # noqa: E711  (SQLAlchemy IS NULL)
            Order.status.in_(("shipped", "cancelled")),
            Order.updated_at < cutoff,
        )
        .order_by(Order.updated_at)
    ).all()


def anonymize_sweep(session: Session, retention_days: int | None = None,
                    dry_run: bool = False) -> dict:
    """Anonymize every order due for it. dry_run lists what WOULD change, writes nothing."""
    due = orders_due_for_anonymization(session, retention_days)
    preview = [{"number": o.number, "status": o.status, "updated_at": o.updated_at} for o in due]
    if dry_run:
        return {"committed": False, "count": len(due), "orders": preview}
    changed = sum(1 for o in due if anonymize_order(session, o))
    return {"committed": True, "count": changed, "orders": preview}
