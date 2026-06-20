"""Cart routes (SPEC-BILLING §2), under the `/{lang}` prefix.

GET renders the cart page; all mutating POSTs are CSRF-protected (the token is injected
into every page by `app.templating.render`).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app import cart as cart_mod
from app.deps import get_lang, get_session, get_site_settings
from app.security import verify_csrf
from app.templating import render

router = APIRouter()


def _vat_rate(site: dict) -> float:
    try:
        return float(site.get("vat_rate") or cart_mod.DEFAULT_VAT_RATE)
    except (TypeError, ValueError):
        return cart_mod.DEFAULT_VAT_RATE


@router.get("/{lang}/cart", name="cart")
def cart_page(
    request: Request,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
    site: dict = Depends(get_site_settings),
):
    view = cart_mod.cart_view(request, session, lang, vat_rate=_vat_rate(site))
    return render(request, "public/cart.html", lang=lang, site=site, cart=view)


@router.post("/{lang}/cart/add")
async def cart_add(
    request: Request,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
):
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return RedirectResponse(url=f"/{lang}/cart", status_code=status.HTTP_303_SEE_OTHER)
    from app.models import Product

    pid = _int(form.get("product_id"))
    qty = max(1, _int(form.get("qty"), default=1))
    product = session.get(Product, pid) if pid else None
    if product and cart_mod.is_purchasable(product):
        cart_mod.add(request, product.id, qty)
    # Return to the cart by default, or to the page the form came from.
    nxt = form.get("next") or f"/{lang}/cart"
    return RedirectResponse(url=nxt, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{lang}/cart/update")
async def cart_update(
    request: Request,
    lang: str = Depends(get_lang),
):
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return RedirectResponse(url=f"/{lang}/cart", status_code=status.HTTP_303_SEE_OTHER)
    pid = _int(form.get("product_id"))
    qty = _int(form.get("qty"), default=0)
    if pid:
        cart_mod.set_qty(request, pid, qty)
    return RedirectResponse(url=f"/{lang}/cart", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{lang}/cart/remove")
async def cart_remove(
    request: Request,
    lang: str = Depends(get_lang),
):
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return RedirectResponse(url=f"/{lang}/cart", status_code=status.HTTP_303_SEE_OTHER)
    pid = _int(form.get("product_id"))
    if pid:
        cart_mod.remove(request, pid)
    return RedirectResponse(url=f"/{lang}/cart", status_code=status.HTTP_303_SEE_OTHER)


def _int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default
