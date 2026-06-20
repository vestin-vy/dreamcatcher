"""Wholesale (B2B) ordering (SPEC-BILLING addendum 2), under the `/{lang}` prefix.

Same catalog as retail, but: a separate session cart, a per-line minimum of 10 units, NO
stock limit, prices hidden, and instead of payment the customer sends a request. The request
becomes an Order with is_wholesale=True / status 'wholesale' (number DCW-...). All POSTs are
CSRF-protected; the wholesale cart never touches stock.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app import cart as cart_mod
from app import orders as orders_mod
from app.cart import WHOLESALE_KEY, WHOLESALE_MIN_QTY
from app.deps import get_lang, get_session, get_site_settings
from app.models import Category, Product
from app.routes.public import active_categories, product_view
from app.security import verify_csrf
from app.templating import render

router = APIRouter()


def _int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _redirect(lang: str, path: str = "/wholesale/cart") -> RedirectResponse:
    return RedirectResponse(url=f"/{lang}{path}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{lang}/wholesale", name="wholesale")
def wholesale_catalog(
    request: Request,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
    site: dict = Depends(get_site_settings),
    category: str | None = None,
):
    query = select(Product).where(Product.is_active == True)  # noqa: E712
    if category:
        cat = session.exec(select(Category).where(Category.slug == category)).first()
        if cat:
            query = query.where(Product.category_id == cat.id)
    query = query.order_by(Product.sort_order, Product.created_at.desc())
    products = session.exec(query).all()
    return render(
        request, "public/wholesale.html", lang=lang, site=site,
        products=[product_view(p, lang) for p in products],
        categories=active_categories(session, lang),
        active_category=category, min_qty=WHOLESALE_MIN_QTY,
    )


@router.post("/{lang}/wholesale/cart/add")
async def wholesale_add(request: Request, lang: str = Depends(get_lang),
                        session: Session = Depends(get_session)):
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return _redirect(lang, "/wholesale")
    pid = _int(form.get("product_id"))
    qty = max(WHOLESALE_MIN_QTY, _int(form.get("qty"), default=WHOLESALE_MIN_QTY))
    product = session.get(Product, pid) if pid else None
    if product and cart_mod.is_wholesale_item(product):
        cart_mod.add(request, product.id, qty, key=WHOLESALE_KEY)
    return _redirect(lang)


@router.post("/{lang}/wholesale/cart/update")
async def wholesale_update(request: Request, lang: str = Depends(get_lang)):
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return _redirect(lang)
    pid = _int(form.get("product_id"))
    qty = _int(form.get("qty"), default=0)
    if pid:
        if qty <= 0:
            cart_mod.remove(request, pid, key=WHOLESALE_KEY)
        else:
            cart_mod.set_qty(request, pid, max(WHOLESALE_MIN_QTY, qty), key=WHOLESALE_KEY)
    return _redirect(lang)


@router.post("/{lang}/wholesale/cart/remove")
async def wholesale_remove(request: Request, lang: str = Depends(get_lang)):
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return _redirect(lang)
    pid = _int(form.get("product_id"))
    if pid:
        cart_mod.remove(request, pid, key=WHOLESALE_KEY)
    return _redirect(lang)


@router.get("/{lang}/wholesale/cart", name="wholesale_cart")
def wholesale_cart_page(request: Request, lang: str = Depends(get_lang),
                        session: Session = Depends(get_session),
                        site: dict = Depends(get_site_settings)):
    view = cart_mod.wholesale_view(request, session, lang)
    return render(request, "public/wholesale_cart.html", lang=lang, site=site,
                  cart=view, min_qty=WHOLESALE_MIN_QTY)


@router.get("/{lang}/wholesale/request", name="wholesale_request")
def wholesale_request_page(request: Request, lang: str = Depends(get_lang),
                           session: Session = Depends(get_session),
                           site: dict = Depends(get_site_settings)):
    view = cart_mod.wholesale_view(request, session, lang)
    if not view["lines"]:
        return _redirect(lang)
    return render(request, "public/wholesale_request.html", lang=lang, site=site, cart=view)


@router.post("/{lang}/wholesale/request")
async def wholesale_request_submit(request: Request, lang: str = Depends(get_lang),
                                   session: Session = Depends(get_session)):
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return _redirect(lang, "/wholesale/request")
    order = orders_mod.create_wholesale_order(request, session, lang, form)
    if order is None:
        return _redirect(lang)
    cart_mod.clear(request, key=WHOLESALE_KEY)
    return RedirectResponse(url=f"/{lang}/wholesale/success?order={order.number}",
                            status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{lang}/wholesale/success", name="wholesale_success")
def wholesale_success(request: Request, order: str = "", lang: str = Depends(get_lang),
                      site: dict = Depends(get_site_settings)):
    return render(request, "public/wholesale_success.html", lang=lang, site=site,
                  order_number=order)
